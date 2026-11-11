"""Rebuild or select experiments and prepare a fresh validation-only registry."""

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.config import ROOT
from src.data.download import verify_manifest
from src.experiments import run_experiments, sha256
from src.model_card import render_model_card
from src.pipeline import chronological_split, write_json
from src.registry import LocalRegistry, package_existing, read_json


def fresh_id() -> str:
    """Return a collision-resistant local execution identifier."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]


def validation_from_batch(batch: Path) -> pd.DataFrame:
    """Read only the manifest-verified validation partition for a selected batch."""
    config = read_json(batch / "data_config.json")
    manifest = read_json(ROOT / config["data"]["manifest"])
    raw = ROOT / config["data"]["raw"]
    verify_manifest(raw, manifest)
    return chronological_split(pd.read_csv(raw, sep=";"), config["split"])["validation"]


def prepare(batch: Path, output: Path | None = None, *, model_card: Path | None = None) -> dict:
    """Register a selected batch's winner; never promote the main registry."""
    batch = batch.resolve()
    if not batch.is_relative_to((ROOT / "artifacts/lesson5").resolve()):
        raise ValueError("Use a trusted local lesson5 batch")
    summary = read_json(batch / "summary.json")
    candidate = summary["selection"]["winner"]
    if candidate is None:
        raise ValueError("The selected batch has no eligible validation winner")
    validation = validation_from_batch(batch)
    output = (output or ROOT / "artifacts/lesson7" / fresh_id()).resolve()
    if not output.is_relative_to((ROOT / "artifacts/lesson7").resolve()):
        raise ValueError("Outputs must stay under artifacts/lesson7")
    output.mkdir(parents=True, exist_ok=False)
    package = output / "package"
    digest = package_existing(batch, candidate, package, validation)
    registry = LocalRegistry(output / "registry")
    model_version = registry.register(package, digest)
    # A failed quality check must not assign even the candidate alias.
    decision = registry.check(model_version)
    registry.challenger(model_version)
    metadata = registry.metadata(model_version)
    if model_card is not None:
        model_card.write_text(render_model_card(metadata), encoding="utf-8")
    evidence = {
        "schema_version": 2,
        "paths_relative_to": "evidence_parent",
        "registry_directory": "registry",
        "source_batch_directory": batch.relative_to(ROOT).as_posix(),
        "source_batch": batch.name,
        "source_run_id": metadata["source_run_id"],
        "source_git_sha": metadata["git_sha"],
        "source_working_tree_dirty": metadata["working_tree_dirty"],
        "model_name": registry.name,
        "model_version": model_version,
        "packaging_run_id": registry.client.get_model_version(registry.name, model_version).run_id,
        "manifest_sha256": digest,
        "raw_sha256": metadata["raw_sha256"],
        "preprocessing_sha256": metadata["preprocessing_sha256"],
        "aliases": registry.aliases(),
        "quality_decision": decision,
        "roundtrip_predictions_equal": True,
        "historical_training_repeated": False,
        "final_test_evaluated": False,
        "replay_evaluated": False,
        "deployed": False,
        "packaging_source_sha256": sha256(ROOT / "src/registry.py"),
    }
    write_json(output / "evidence.json", evidence)
    return evidence


def rebuild(output: Path | None = None) -> Path:
    """Create one new batch through the existing training implementation, then select it."""
    output = (output or ROOT / "artifacts/lesson7" / fresh_id()).resolve()
    if output.exists() or not output.is_relative_to((ROOT / "artifacts/lesson7").resolve()):
        raise ValueError("Choose a new output directory under artifacts/lesson7")
    batch = ROOT / "artifacts/lesson5" / fresh_id()
    run_experiments(output=batch)
    prepare(batch, output)
    return output / "evidence.json"


def execute_notebook(evidence: Path, destination: Path) -> None:
    """Execute a read-only notebook copy against explicitly selected registry evidence."""
    import nbformat
    from nbclient import NotebookClient

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    notebook = nbformat.read(ROOT / "notebooks/03_model_registry.ipynb", as_version=4)
    nbformat.validate(notebook)
    environment = {
        **os.environ,
        "BANK_MARKETING_REGISTRY_EVIDENCE": str(evidence.resolve()),
        "IPYTHONDIR": str(destination.parent / "ipython"),
        "JUPYTER_RUNTIME_DIR": str(destination.parent / "jupyter-runtime"),
    }
    NotebookClient(
        notebook,
        timeout=180,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    ).execute(env=environment)
    nbformat.write(notebook, destination)


def main() -> None:
    """Choose a generated batch explicitly or rebuild; print a portable evidence handoff."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--batch", type=Path)
    source.add_argument("--rebuild", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model-card", type=Path)
    parser.add_argument("--execute-notebook", action="store_true")
    args = parser.parse_args()
    if args.rebuild:
        evidence = rebuild(args.output)
        if args.model_card:
            record = read_json(evidence)
            store = LocalRegistry.from_evidence(evidence)
            args.model_card.write_text(
                render_model_card(store.metadata(record["model_version"])), encoding="utf-8"
            )
    else:
        output = args.output or ROOT / "artifacts/lesson7" / fresh_id()
        prepare(args.batch, output, model_card=args.model_card)
        evidence = output / "evidence.json"
    if args.execute_notebook:
        execute_notebook(evidence, evidence.parent / "notebook/executed.ipynb")
    print("EVIDENCE=" + evidence.resolve().relative_to(ROOT).as_posix(), flush=True)


if __name__ == "__main__":
    main()
