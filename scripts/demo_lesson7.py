"""Demonstrate UCI promotion/rollback in a separate, explicitly disposable registry."""

import argparse
from pathlib import Path

from scripts.verify_lesson7 import execute_notebook, validation_from_batch
from src.config import ROOT
from src.pipeline import write_json
from src.registry import LocalRegistry, package_existing, read_json


def demonstrate(evidence_path: Path) -> dict:
    """Use real saved UCI pipelines; never change the registry selected by evidence."""
    evidence = read_json(evidence_path)
    main = LocalRegistry.from_evidence(evidence_path)
    before = main.snapshot()
    parent = evidence_path.resolve().parent
    demo = parent / "isolated-demo"
    demo.mkdir(exist_ok=False)
    package = parent / "package"
    store = LocalRegistry(demo / "registry")
    first = store.register(package, evidence["manifest_sha256"])
    item = store.client.get_model_version(store.name, first)
    demo_evidence = {
        "schema_version": 2,
        "paths_relative_to": "evidence_parent",
        "registry_directory": "registry",
        "model_name": store.name,
        "model_version": first,
        "packaging_run_id": item.run_id,
        "manifest_sha256": evidence["manifest_sha256"],
    }
    selected = demo / "evidence.json"
    write_json(selected, demo_evidence)
    store.challenger(first)
    execute_notebook(selected, demo / "without-champion/executed.ipynb")
    initial = store.promote(first, expected=None, approved=True)
    execute_notebook(selected, demo / "with-champion/executed.ipynb")
    # Two releases of the same verified winner exercise successful version rollback.
    second = store.register(package, evidence["manifest_sha256"])
    store.challenger(second)
    receipt = store.promote(second, expected=first, approved=True)
    store.rollback(receipt["event"], expected=second, approved=True)
    assert store.aliases()["champion"] == first
    batch = ROOT / evidence["source_batch_directory"]
    other_package = demo / "other-package"
    digest = package_existing(
        batch, "logistic_balanced", other_package, validation_from_batch(batch)
    )
    other = store.register(other_package, digest)
    store.challenger(other)
    rejected = False
    try:
        store.promote(other, expected=first, approved=True)
    except ValueError:
        rejected = True
    if not rejected:
        raise AssertionError("The lower-AP UCI candidate was not blocked")
    assert store.aliases()["champion"] == first
    store.rollback(initial["event"], expected=first, approved=True)
    assert "champion" not in store.aliases()
    assert main.snapshot() == before
    result = {
        "status": "PASS",
        "real_uci_models": True,
        "successful_versions": "two releases of the same validation winner",
        "rejected_candidate": "logistic_balanced",
        "regression_blocked": rejected,
        "promotion_and_rollback": True,
        "notebook_without_champion": "PASS",
        "notebook_with_champion": "PASS",
        "main_registry_unchanged": True,
        "deployed": False,
    }
    write_json(demo / "result.json", result)
    return result


def main() -> None:
    """Run only against the explicitly supplied new evidence file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    print(demonstrate(args.evidence))


if __name__ == "__main__":
    main()
