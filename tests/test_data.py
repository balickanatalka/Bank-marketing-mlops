import hashlib
import io
from zipfile import ZipFile

import pandas as pd
import pytest

from src.data.download import ensure_data, extract_csv, verify_manifest
from src.data.validation import CATEGORICAL, NUMERIC, validate_dataframe


@pytest.fixture
def frame():
    data = {c: [1, 2] for c in NUMERIC}
    data.update({c: ["unknown", "unknown"] for c in CATEGORICAL})
    data["y"] = ["no", "yes"]
    return pd.DataFrame(data)


def test_valid_fixture(frame):
    assert validate_dataframe(frame, expected_rows=2)["class_counts"] == {"no": 1, "yes": 1}


@pytest.mark.parametrize("fault", ["missing", "extra", "type", "target", "null", "duplicate"])
def test_reject_bad_data(frame, fault):
    if fault == "missing":
        frame = frame.drop(columns="y")
    elif fault == "extra":
        frame["extra"] = 0
    elif fault == "type":
        frame["age"] = "bad"
    elif fault == "target":
        frame["y"] = "maybe"
    elif fault == "null":
        frame.loc[0, "job"] = None
    else:
        frame.columns = ["age"] * len(frame.columns)
    with pytest.raises(ValueError):
        validate_dataframe(frame, expected_rows=2)


def test_hash_tamper(tmp_path):
    path = tmp_path / "data.csv"
    path.write_bytes(b"original")
    manifest = {"sha256": hashlib.sha256(b"original").hexdigest(), "size_bytes": 8}
    verify_manifest(path, manifest)
    path.write_bytes(b"changed!")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_manifest(path, manifest)


def test_nested_download_without_network(tmp_path, monkeypatch):
    import json

    csv = b"fixture"
    nested, outer = io.BytesIO(), io.BytesIO()
    with ZipFile(nested, "w") as archive:
        archive.writestr("bank-additional/bank-additional-full.csv", csv)
    with ZipFile(outer, "w") as archive:
        archive.writestr("bank-additional.zip", nested.getvalue())
    assert extract_csv(outer.getvalue()) == csv
    monkeypatch.setattr("src.data.download.urlopen", lambda *a, **k: io.BytesIO(outer.getvalue()))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sha256": hashlib.sha256(csv).hexdigest(), "size_bytes": 7}))
    path = tmp_path / "raw.csv"
    ensure_data(path, manifest)
    assert path.read_bytes() == csv
    path.write_bytes(b"tamper")
    with pytest.raises(ValueError):
        ensure_data(path, manifest)
