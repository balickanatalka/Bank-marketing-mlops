"""Reject substituted image bytes and attestations before reporting integrity."""

import hashlib
import io
import json
import tarfile

import pytest

from scripts.verify_image_evidence import SLSA, SPDX, SYFT_VERSION, verify_cyclonedx, verify_image


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


@pytest.fixture
def cyclonedx_candidate(tmp_path):
    archive = tmp_path / "image.tar"
    digest = image_archive(archive)
    image = verify_image(archive, digest)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "metadata": {
            "component": {"type": "container", "version": image["platform_manifest_digest"]},
            "tools": {"components": [{"name": "syft", "version": SYFT_VERSION}]},
        },
        "components": [{"type": "library", "name": "fixture"}],
    }
    report = tmp_path / "sbom.cdx.json"
    report.write_text(json.dumps(document), encoding="utf-8")
    return archive, digest, image, report, document


def test_cyclonedx_binds_report_and_reverified_archive(cyclonedx_candidate):
    archive, digest, image, report, _ = cyclonedx_candidate
    result = verify_cyclonedx(archive, digest, report)
    assert result["status"] == "PASS"
    assert result["cyclonedx_subject_digest"] == image["platform_manifest_digest"]
    assert result["cyclonedx_sha256"] == hashlib.sha256(report.read_bytes()).hexdigest()
    assert result["cyclonedx_components"] == 1
    assert result["signature_verified"] is False


@pytest.mark.parametrize(
    "damage",
    [
        "wrong_subject",
        "index_subject",
        "config_subject",
        "subject_type",
        "metadata",
        "format",
        "spec_version",
        "version",
        "bool_version",
        "components",
        "invalid_component",
        "producer",
        "producer_type",
        "json",
        "object",
        "missing",
    ],
)
def test_reject_unbound_or_invalid_cyclonedx(cyclonedx_candidate, damage):
    archive, digest, image, report, document = cyclonedx_candidate
    if damage in {"wrong_subject", "index_subject", "config_subject"}:
        document["metadata"]["component"]["version"] = {
            "wrong_subject": "sha256:" + "0" * 64,
            "index_subject": digest,
            "config_subject": image["config_digest"],
        }[damage]
    elif damage == "subject_type":
        document["metadata"]["component"]["type"] = "file"
    elif damage == "metadata":
        document["metadata"] = []
    elif damage == "format":
        document["bomFormat"] = "SPDX"
    elif damage == "spec_version":
        document["specVersion"] = "unknown"
    elif damage == "version":
        del document["version"]
    elif damage == "bool_version":
        document["version"] = True
    elif damage == "components":
        document["components"] = []
    elif damage == "invalid_component":
        document["components"] = [{"type": "library"}]
    elif damage == "producer":
        document["metadata"]["tools"]["components"][0]["version"] = "0.0.0"
    elif damage == "producer_type":
        document["metadata"]["tools"] = []
    if damage == "missing":
        report.unlink()
    else:
        report.write_text(
            "{" if damage == "json" else json.dumps([] if damage == "object" else document),
            encoding="utf-8",
        )
    with pytest.raises((ValueError, OSError)):
        verify_cyclonedx(archive, digest, report)


def test_cyclonedx_rejects_archive_changed_after_initial_verification(cyclonedx_candidate):
    archive, digest, _, report, _ = cyclonedx_candidate
    archive.write_bytes(b"substituted archive")
    with pytest.raises((ValueError, tarfile.TarError)):
        verify_cyclonedx(archive, digest, report)
