"""Prepare pinned public UCI data and require evidence that its quality test ran."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from src.config import ROOT
from src.data.download import URL, ensure_data
from src.data.validation import validate_dataframe

CSV_NAME = "bank-additional-full.csv"
QUALITY_CLASS = "tests.test_uci_quality"
QUALITY_TEST = "test_uci_validation_quality_gate"
MANIFEST = ROOT / "metadata/data_manifest.json"


def prepare(directory: Path) -> dict:
    """Download into a new directory and validate exact bytes and the raw schema."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["source_url"] != URL:
        raise ValueError("UCI source differs from the pinned official downloader")
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / CSV_NAME
    ensure_data(source, MANIFEST)
    validation = validate_dataframe(
        pd.read_csv(source, sep=manifest["delimiter"]), expected_rows=manifest["rows"]
    )
    report = {
        "status": "PASS",
        "scope": "manifest_verified_uci_data",
        "source_url": URL,
        "sha256": manifest["sha256"],
        "size_bytes": source.stat().st_size,
        "validation": validation,
        "license": manifest["license"],
        "quality_test_executed": False,
    }
    with (directory / "validation.json").open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
    return report


def verify_tests(junit: Path) -> dict:
    """Fail if the exact real-data gate is absent, duplicated, skipped or failed."""
    root = ET.parse(junit).getroot()
    matches = [
        case
        for case in root.iter("testcase")
        if case.get("classname") == QUALITY_CLASS and case.get("name") == QUALITY_TEST
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one real UCI quality test in JUnit")
    case = matches[0]
    if any(case.find(tag) is not None for tag in ("skipped", "failure", "error")):
        raise ValueError("Real UCI quality gate was skipped or failed")
    return {
        "status": "PASS",
        "scope": "real_uci_quality_gate_executed",
        "test": f"{QUALITY_CLASS}.{QUALITY_TEST}",
        "quality_test_executed": True,
    }


def main() -> None:
    """Expose separate preparation and JUnit evidence gates for a clean runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("prepare")
    download.add_argument("--directory", type=Path, required=True)
    verify = commands.add_parser("verify-tests")
    verify.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.directory) if args.command == "prepare" else verify_tests(args.junit)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
