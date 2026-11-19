"""Reject substituted image bytes and attestations before reporting integrity."""

import hashlib
import io
import json
import tarfile

import pytest

from scripts.verify_image_evidence import SLSA, SPDX, verify_image


def image_archive(path, *, damage=None):
    blobs = {}

    def add(value):
        raw = json.dumps(value).encode()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        blobs["blobs/sha256/" + digest.split(":")[1]] = raw
        return {"digest": digest, "size": len(raw)}

    runtime = add({"config": add({"architecture": "amd64"}), "layers": [add({"data": 1})]})
    runtime["platform"] = {"os": "linux", "architecture": "amd64"}
    layers = []
    for kind, predicate in [
        (SPDX, {"packages": [{"name": "fixture"}]}),
        (SLSA, {"buildDefinition": {"buildType": "fixture"}}),
    ]:
        if damage == "missing_sbom" and kind == SPDX:
            continue
        if damage == "missing_provenance" and kind == SLSA:
            continue
        layers.append(
            add(
                {
                    "predicateType": kind,
                    "predicate": predicate,
                    "subject": [
                        {
                            "digest": {
                                "sha256": "0" * 64
                                if damage == "subject"
                                else runtime["digest"].split(":")[1]
                            }
                        }
                    ],
                }
            )
        )
    attestation = add({"layers": layers})
    attestation["annotations"] = {
        "vnd.docker.reference.type": "attestation-manifest",
        "vnd.docker.reference.digest": runtime["digest"],
    }
    index = add({"manifests": [runtime, attestation]})
    blobs["index.json"] = json.dumps({"manifests": [index]}).encode()
    if damage == "bytes":
        blobs[next(iter(blobs))] = b"x" * len(blobs[next(iter(blobs))])
    with tarfile.open(path, "w") as tar:
        for name, raw in blobs.items():
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            tar.addfile(member, io.BytesIO(raw))
    return index["digest"]


def test_image_attestations_bind_to_verified_platform(tmp_path):
    archive = tmp_path / "image.tar"
    digest = image_archive(archive)
    report = verify_image(archive, digest)
    assert report["status"] == "PASS"
    assert report["image_index_digest"] == digest
    assert report["signature_verified"] is False


@pytest.mark.parametrize(
    "damage", ["digest", "bytes", "subject", "missing_sbom", "missing_provenance"]
)
def test_reject_substituted_image_or_attestation(tmp_path, damage):
    archive = tmp_path / "image.tar"
    digest = image_archive(archive, damage=damage)
    if damage == "digest":
        digest = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        verify_image(archive, digest)
