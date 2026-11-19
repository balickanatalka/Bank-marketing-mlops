"""Portable, read-only serving packages anchored by an external receipt hash."""

import argparse
import shutil
from pathlib import Path

import mlflow.sklearn

from src.experiments import sha256
from src.pipeline import write_json
from src.registry import LocalRegistry, read_json, verify_package


def export_bundle(evidence: Path, version: str, destination: Path) -> str:
    """Export one eligible registered version without training or alias changes.

    Return the receipt SHA-256 to pin outside the mounted bundle. An unsigned
    hash protects integrity only while the receipt anchor remains trusted.
    """
    store = LocalRegistry.from_evidence(evidence)
    gate = store.check(version)
    item = store.client.get_model_version(store.name, version)
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(store.package_path(version), destination / "package")
    metadata = verify_package(destination / "package", item.tags["manifest_sha256"])
    write_json(
        destination / "ml-bom.json",
        {
            "schema_version": 1,
            "dataset": metadata["data_manifest"],
            "model": {
                "name": store.name,
                "version": version,
                "manifest_sha256": item.tags["manifest_sha256"],
                "metrics": metadata["metrics"],
                "source_run_id": metadata["source_run_id"],
                "packaging_run_id": item.run_id,
            },
            "code_git_sha": metadata["git_sha"],
            "uv_lock_sha256": metadata["uv_lock_sha256"],
            "deployed": False,
        },
    )
    write_json(
        destination / "receipt.json",
        {
            "schema_version": 1,
            "model_name": store.name,
            "model_version": version,
            "packaging_run_id": item.run_id,
            "package_manifest_sha256": item.tags["manifest_sha256"],
            "ml_bom_sha256": sha256(destination / "ml-bom.json"),
            "registry_gate": gate,
            "deployed": False,
        },
    )
    return sha256(destination / "receipt.json")


def load_bundle(directory: Path, expected_hash: str):
    """Verify the receipt, complete file manifest and dependencies before loading."""
    if not expected_hash or sha256(directory / "receipt.json") != expected_hash:
        raise ValueError("Serving receipt integrity failure")
    receipt = read_json(directory / "receipt.json")
    if (
        receipt["schema_version"] != 1
        or receipt["registry_gate"]["eligible"] is not True
        or receipt["registry_gate"]["version"] != receipt["model_version"]
        or not receipt["model_version"].isdecimal()
        or int(receipt["model_version"]) < 1
    ):
        raise ValueError("Invalid serving receipt")
    package = directory / "package"
    if sha256(directory / "ml-bom.json") != receipt["ml_bom_sha256"]:
        raise ValueError("ML-BOM integrity failure")
    metadata = verify_package(package, receipt["package_manifest_sha256"])
    model = mlflow.sklearn.load_model(str(package / "model"))
    return model, metadata, receipt


def main() -> None:
    """Print the external trust anchor for a newly exported bundle."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(export_bundle(args.evidence, args.version, args.output))


if __name__ == "__main__":
    main()
