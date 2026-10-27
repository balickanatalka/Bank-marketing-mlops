import json

import pytest

from scripts import verify_lesson3 as verifier


@pytest.mark.parametrize("change", ["modified", "missing"])
def test_integrity_failure_overrides_pass(tmp_path, monkeypatch, change):
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    protected = tmp_path / "protected.txt"
    protected.write_text("original", encoding="utf-8")
    before = {"protected.txt": verifier.digest(protected)}
    if change == "modified":
        protected.write_text("changed", encoding="utf-8")
    else:
        protected.unlink()
    evidence = {"status": "PASS"}
    output = verifier.write_evidence(
        evidence, before, checks_complete=True, download_requested=True, output_dir=tmp_path
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["existing_files_unchanged"] is False


@pytest.mark.parametrize(
    ("complete", "download", "error", "expected"),
    [
        (True, True, None, "PASS"),
        (True, False, None, "INCOMPLETE_UCI_NOT_RUN"),
        (False, True, None, "FAIL"),
        (True, True, "failed step", "FAIL"),
    ],
)
def test_final_status_accounts_for_all_checks(tmp_path, complete, download, error, expected):
    evidence = {"status": "PASS"}
    if error:
        evidence["error"] = error
    output = verifier.write_evidence(
        evidence, {}, checks_complete=complete, download_requested=download, output_dir=tmp_path
    )
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == expected


@pytest.mark.parametrize(
    "private_path",
    [
        r"C:\Users\fictional-user\private folder\data.csv",
        r"C:\\Users\\fictional-user\\private folder\\data.csv",
        "X:/private folder/data.csv",
        r"\\private-server\share\private folder\data.csv",
        "/home/fictional-user/private folder/data.csv",
    ],
)
def test_report_and_cli_redact_error_paths(tmp_path, monkeypatch, capsys, private_path):
    message = f"Unable to open '{private_path}'"
    output = verifier.write_evidence(
        {"error": message, "steps": [{"stderr": message}]},
        {},
        checks_complete=False,
        download_requested=True,
        output_dir=tmp_path,
    )
    text = output.read_text(encoding="utf-8")
    assert "private folder" not in text
    assert "fictional-user" not in text
    assert "private-server" not in text

    def fail():
        raise OSError(message)

    monkeypatch.setattr(verifier, "main", fail)
    with pytest.raises(SystemExit) as error:
        verifier.cli()
    assert error.value.code == 1
    terminal = capsys.readouterr().err
    assert "private folder" not in terminal
    assert "fictional-user" not in terminal
    assert "private-server" not in terminal
    assert "Traceback" not in terminal


def test_sanitizer_preserves_metrics_and_public_source(monkeypatch, tmp_path):
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    metric = "39 passed; SHA-256=74adfc; https://archive.ics.uci.edu/dataset/222/bank+marketing"
    text = verifier.sanitize_output(f"{tmp_path}/reports; {metric}")
    assert str(tmp_path) not in text
    assert metric in text


def test_new_report_preserves_existing_reports(tmp_path):
    old = tmp_path / "lesson3.json"
    old.write_bytes(b"historical evidence")
    first = verifier.write_evidence(
        {}, {}, checks_complete=True, download_requested=True, output_dir=tmp_path
    )
    first_bytes = first.read_bytes()
    second = verifier.write_evidence(
        {}, {}, checks_complete=True, download_requested=True, output_dir=tmp_path
    )
    assert first != second
    assert old.read_bytes() == b"historical evidence"
    assert first.read_bytes() == first_bytes
