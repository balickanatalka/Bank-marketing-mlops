"""Verify local OCI image bytes and the subjects of its BuildKit attestations."""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

SPDX = "https://spdx.dev/Document"
SLSA = "https://slsa.dev/provenance/v1"
SYFT_VERSION = "1.57.2"


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


def verify_cyclonedx(archive: Path, expected_digest: str, report: Path) -> dict:
    """Bind a Syft 1.57.2 CycloneDX report to freshly verified OCI bytes.

    Check the report structure, producer and platform subject. This is an
    integrity check, not cryptographic signing or full JSON Schema validation.
    """
    image = verify_image(archive, expected_digest)
    if report.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("CycloneDX report exceeds size limit")
    raw = report.read_bytes()
    document = json.loads(raw)
    if (
        not isinstance(document, dict)
        or document.get("bomFormat") != "CycloneDX"
        or document.get("specVersion") != "1.7"
        or type(document.get("version")) is not int
        or document["version"] < 1
    ):
        raise ValueError("Invalid CycloneDX format or version")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Missing CycloneDX metadata")
    subject = metadata.get("component", {})
    if (
        not isinstance(subject, dict)
        or subject.get("type") != "container"
        or subject.get("version") != image["platform_manifest_digest"]
    ):
        raise ValueError("CycloneDX subject differs from verified platform manifest")
    tools = metadata.get("tools", {})
    producers = tools.get("components", []) if isinstance(tools, dict) else []
    if not isinstance(producers, list) or not any(
        isinstance(tool, dict)
        and tool.get("name") == "syft"
        and tool.get("version") == SYFT_VERSION
        for tool in producers
    ):
        raise ValueError("Unexpected CycloneDX producer")
    components = document.get("components")
    if (
        not isinstance(components, list)
        or not components
        or not all(
            isinstance(component, dict)
            and isinstance(component.get("name"), str)
            and component["name"].strip()
            and isinstance(component.get("type"), str)
            and component["type"].strip()
            for component in components
        )
    ):
        raise ValueError("Missing or invalid CycloneDX components")
    return {
        **image,
        "cyclonedx_spec_version": document["specVersion"],
        "cyclonedx_components": len(components),
        "cyclonedx_sha256": hashlib.sha256(raw).hexdigest(),
        "cyclonedx_subject_digest": subject["version"],
        "syft_version": SYFT_VERSION,
    }


def main() -> None:
    """Verify an OCI export and print a compact report only after all checks pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--cyclonedx", type=Path)
    args = parser.parse_args()
    result = (
        verify_cyclonedx(args.archive, args.digest, args.cyclonedx)
        if args.cyclonedx is not None
        else verify_image(args.archive, args.digest)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
