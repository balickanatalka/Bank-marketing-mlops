"""Verify local OCI image bytes and the subjects of its BuildKit attestations."""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

SPDX = "https://spdx.dev/Document"
SLSA = "https://slsa.dev/provenance/v1"


def verify_image(archive: Path, expected_digest: str) -> dict:
    """Check an exported image against a trusted build digest, without extraction.

    This proves content integrity and attestation binding, not a signature or
    builder identity. The archive must contain one linux/amd64 runtime image.
    """
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_digest):
        raise ValueError("Expected a complete SHA-256 image index digest")
    with tarfile.open(archive) as tar:

        def member(name):
            item = tar.getmember(name)
            if not item.isfile():
                raise ValueError("OCI content must be a regular file")
            return item

        def blob(descriptor, *, decode=True):
            digest = descriptor["digest"]
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                raise ValueError("Invalid OCI blob digest")
            item = member("blobs/sha256/" + digest.split(":")[1])
            if item.size != descriptor["size"]:
                raise ValueError("OCI blob size mismatch")
            with tar.extractfile(item) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest.split(":")[1]:
                    raise ValueError("OCI blob hash mismatch")
            if decode:
                if item.size > 64 * 1024 * 1024:
                    raise ValueError("OCI JSON metadata exceeds size limit")
                with tar.extractfile(item) as stream:
                    return json.load(stream)
            return None

        root = json.load(tar.extractfile(member("index.json")))
        matching = [d for d in root["manifests"] if d["digest"] == expected_digest]
        if len(matching) != 1:
            raise ValueError("Export differs from expected image index digest")
        index = blob(matching[0])
        runtime = [
            d
            for d in index["manifests"]
            if d.get("platform", {}).get("os") == "linux"
            and d["platform"].get("architecture") == "amd64"
        ]
        if len(runtime) != 1:
            raise ValueError("Expected exactly one linux/amd64 runtime manifest")
        selected = runtime[0]
        manifest = blob(selected)
        blob(manifest["config"])
        for layer in manifest["layers"]:
            blob(layer, decode=False)
        statements = {}
        for descriptor in index["manifests"]:
            annotations = descriptor.get("annotations", {})
            if annotations.get("vnd.docker.reference.type") != "attestation-manifest":
                continue
            if annotations.get("vnd.docker.reference.digest") != selected["digest"]:
                raise ValueError("Attestation manifest references a different image")
            attestation = blob(descriptor)
            for layer in attestation["layers"]:
                statement = blob(layer)
                subjects = statement.get("subject", [])
                if not subjects or any(
                    s.get("digest") != {"sha256": selected["digest"].split(":")[1]}
                    for s in subjects
                ):
                    raise ValueError("Attestation subject differs from runtime manifest")
                predicate_type = statement["predicateType"]
                if predicate_type in statements:
                    raise ValueError("Duplicate attestation predicate")
                statements[predicate_type] = statement["predicate"]
        if not statements.get(SPDX, {}).get("packages"):
            raise ValueError("Missing or empty SPDX SBOM attestation")
        if not statements.get(SLSA, {}).get("buildDefinition", {}).get("buildType"):
            raise ValueError("Missing SLSA v1 build provenance attestation")
    return {
        "status": "PASS",
        "image_index_digest": expected_digest,
        "platform_manifest_digest": selected["digest"],
        "config_digest": manifest["config"]["digest"],
        "layers_verified": len(manifest["layers"]),
        "sbom_packages": len(statements[SPDX]["packages"]),
        "predicate_types": sorted(statements),
        "signature_verified": False,
    }


def main() -> None:
    """Verify an OCI export and print a compact report only after all checks pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    print(json.dumps(verify_image(args.archive, args.digest), indent=2))


if __name__ == "__main__":
    main()
