"""Fail-closed UCI preparation and proof of execution, without network in unit tests."""

import hashlib
import io
import json
import xml.etree.ElementTree as ET
from urllib.error import URLError
from zipfile import ZipFile

import pytest

from scripts import ci_uci
from scripts.ci_smoke import synthetic_fixture


@pytest.fixture
def public_download(tmp_path, monkeypatch):
    def configure(frame=None):
        frame = synthetic_fixture() if frame is None else frame
        content = frame.to_csv(index=False, sep=";").encode()
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "source_url": ci_uci.URL,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                    "rows": len(frame),
                    "columns": len(frame.columns),
                    "delimiter": ";",
                    "license": "synthetic unit-test fixture",
                }
            ),
            encoding="utf-8",
        )
        nested, outer = io.BytesIO(), io.BytesIO()
        with ZipFile(nested, "w") as archive:
            archive.writestr("bank-additional/bank-additional-full.csv", content)
        with ZipFile(outer, "w") as archive:
            archive.writestr("bank-additional.zip", nested.getvalue())
        monkeypatch.setattr(ci_uci, "MANIFEST", manifest)

        def response(url, **kwargs):
            assert url == ci_uci.URL
            return io.BytesIO(outer.getvalue())

        monkeypatch.setattr("src.data.download.urlopen", response)
        return manifest, content

    return configure


def test_download_checks_manifest_and_schema_without_using_local_data(tmp_path, public_download):
    _, content = public_download()
    directory = tmp_path / "download"
    report = ci_uci.prepare(directory)
    assert report["status"] == "PASS"
    assert report["quality_test_executed"] is False
    assert report["validation"]["rows"] == 320
    assert report["sha256"] == hashlib.sha256(content).hexdigest()
    assert (directory / ci_uci.CSV_NAME).read_bytes() == content
    with pytest.raises(FileExistsError):
        ci_uci.prepare(directory)


@pytest.mark.parametrize("fault", ["hash", "schema", "unavailable", "source"])
def test_invalid_or_unavailable_data_cannot_produce_pass_report(
    tmp_path, public_download, monkeypatch, fault
):
    frame = synthetic_fixture()
    if fault == "schema":
        frame = frame.drop(columns="age")
    manifest, _ = public_download(frame)
    if fault in {"hash", "source"}:
        metadata = json.loads(manifest.read_text())
        metadata["sha256" if fault == "hash" else "source_url"] = (
            "0" * 64 if fault == "hash" else "https://invalid.example/data.zip"
        )
        manifest.write_text(json.dumps(metadata), encoding="utf-8")
    if fault == "unavailable":

        def offline(*args, **kwargs):
            raise URLError("offline")

        monkeypatch.setattr("src.data.download.urlopen", offline)
        monkeypatch.setattr("src.data.download.time.sleep", lambda _: None)
    directory = tmp_path / "rejected"
    with pytest.raises((ValueError, URLError)):
        ci_uci.prepare(directory)
    assert not (directory / "validation.json").exists()


def test_junit_requires_the_exact_real_quality_case(tmp_path):
    root = ET.Element("testsuite")
    ET.SubElement(root, "testcase", classname=ci_uci.QUALITY_CLASS, name=ci_uci.QUALITY_TEST)
    report = tmp_path / "tests.xml"
    ET.ElementTree(root).write(report)
    assert ci_uci.verify_tests(report)["quality_test_executed"] is True


@pytest.mark.parametrize(
    "fault", ["skipped", "failure", "error", "missing", "duplicate", "class", "name", "xml"]
)
def test_missing_or_nonpassing_quality_test_blocks_job(tmp_path, fault):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    case = ET.SubElement(
        suite, "testcase", classname=ci_uci.QUALITY_CLASS, name=ci_uci.QUALITY_TEST
    )
    if fault in {"skipped", "failure", "error"}:
        ET.SubElement(case, fault)
    elif fault == "missing":
        suite.remove(case)
    elif fault == "duplicate":
        ET.SubElement(suite, "testcase", classname=ci_uci.QUALITY_CLASS, name=ci_uci.QUALITY_TEST)
    elif fault in {"class", "name"}:
        case.set("classname" if fault == "class" else "name", "another_test")
    report = tmp_path / "tests.xml"
    ET.ElementTree(root).write(report)
    if fault == "xml":
        report.write_text("<broken", encoding="utf-8")
    with pytest.raises((ValueError, ET.ParseError)):
        ci_uci.verify_tests(report)


def test_missing_junit_cannot_pass(tmp_path):
    with pytest.raises(FileNotFoundError):
        ci_uci.verify_tests(tmp_path / "absent.xml")
