import json
import shutil
from pathlib import Path

import mlflow.sklearn
import numpy as np
import pandas as pd
import pytest

from src import experiments, registry
from src.config import ROOT, load_config
from src.model_card import render_model_card
from src.pipeline import write_json


@pytest.fixture(scope="module")
def packaged(tmp_path_factory):
    """A real six-run experiment and package, entirely in a temporary directory."""
    root = tmp_path_factory.mktemp("lesson7-source")
    for name in ["uv.lock", "dvc.lock"]:
        shutil.copyfile(ROOT / name, root / name)
    shutil.copytree(ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "metadata").mkdir()
    write_json(root / "metadata/data_manifest.json", {"sha256": "synthetic"})
    config = load_config()
    config["data"]["features"] = ["age", "pdays", "job"]
    frame = pd.DataFrame(
        {
            "age": [20, 60] * 40,
            "pdays": [999, 5] * 40,
            "job": ["admin.", "student"] * 40,
            "y": ["no", "yes"] * 40,
        }
    )
    validation = pd.DataFrame(
        {
            "age": [21, 61] * 10,
            "pdays": [999, 6] * 10,
            "job": ["admin.", "student"] * 10,
            "y": ["no", "yes"] * 10,
        },
        index=range(80, 100),
    )
    assert frame.index.intersection(validation.index).empty
    assert set(map(tuple, frame.to_numpy())).isdisjoint(map(tuple, validation.to_numpy()))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(experiments, "ROOT", root)
        patch.setattr(registry, "ROOT", root)
        patch.setattr(
            experiments, "training_inputs", lambda cfg: (frame, validation, {"sha256": "synthetic"})
        )
        summary = experiments.run_experiments(ROOT / "configs/experiments.yaml", config=config)
        batch = next((root / "artifacts/lesson5").iterdir())
        # A fixture has no Git repository; supply a clearly synthetic source revision.
        summary["provenance"]["git_sha"] = "a" * 40
        write_json(batch / "summary.json", summary)
        package = root / "package"
        digest = registry.package_existing(batch, "logistic", package, validation)
    return package, digest, validation, batch, root


@pytest.fixture
def local(tmp_path, packaged):
    package, digest, frame, _, _ = packaged
    store = registry.LocalRegistry(tmp_path / "registry")
    first = store.register(package, digest)
    return store, first, frame


def altered_package(packaged, tmp_path, change):
    source, _, _, _, _ = packaged
    path = tmp_path / "changed-package"
    shutil.copytree(source, path)
    metadata = registry.read_json(path / "lineage.json")
    change(metadata)
    # Deliberately permit invalid JSON numbers to exercise untrusted metadata.
    (path / "lineage.json").write_text(json.dumps(metadata), encoding="utf-8")
    write_json(
        path / "manifest.json",
        {
            p.relative_to(path).as_posix(): experiments.sha256(p)
            for p in sorted(path.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        },
    )
    return path, experiments.sha256(path / "manifest.json")


def test_roundtrip_versions_aliases_and_approval(local, packaged):
    store, first, frame = local
    package, digest, _, _, _ = packaged
    second = store.register(package, digest)
    assert (first, second) == ("1", "2")
    assert store.aliases() == {}
    store.challenger(first)
    assert store.check(first)["eligible"]
    with pytest.raises(PermissionError):
        store.promote(first, expected=None)
    receipt = store.promote(first, expected=None, approved=True)
    assert store.aliases()["champion"] == first
    store.challenger(second)
    with pytest.raises(ValueError, match="changed since review"):
        store.promote(second, expected=None, approved=True)
    store.promote(second, expected=first, approved=True)
    assert str(store.client.get_model_version_by_alias(store.name, "challenger").version) == second
    metadata = store.metadata(first)
    assert (
        metadata["source_run_id"] == registry.read_json(package / "lineage.json")["source_run_id"]
    )
    x = frame[list(metadata["schema"])]
    np.testing.assert_allclose(store.predict(first, x), store.predict(second, x), atol=1e-12)
    original = mlflow.sklearn.load_model(str(package / "model"))
    np.testing.assert_array_equal(original.predict(x), store.load(second).predict(x))
    assert receipt["previous"] is None
    assert store.client.get_model_version(store.name, first).current_stage == "None"


def test_rollback_restores_prior_version_and_checks_integrity(local, packaged):
    store, first, _ = local
    store.challenger(first)
    initial = store.promote(first, expected=None, approved=True)
    second = store.register(packaged[0], packaged[1])
    store.challenger(second)
    receipt = store.promote(second, expected=first, approved=True)
    with pytest.raises(PermissionError):
        store.rollback(receipt["event"], expected=second)
    with pytest.raises(ValueError):
        store.rollback(receipt["event"], expected=first, approved=True)
    store.rollback(receipt["event"], expected=second, approved=True)
    assert store.aliases()["champion"] == first
    store.rollback(initial["event"], expected=first, approved=True)
    assert "champion" not in store.aliases()
    with pytest.raises(ValueError):
        store.rollback(initial["event"], expected=first, approved=True)


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m["metrics"].pop("average_precision"),
        lambda m: m["metrics"].update(average_precision=None),
        lambda m: m["metrics"].update(average_precision=float("nan")),
        lambda m: m["metrics"].update(average_precision=-0.1),
        lambda m: m["metrics"].update(average_precision=0.5),  # equals synthetic Dummy
        lambda m: m["metrics"].update(recall_yes=0),
        lambda m: m.update(evaluation_split="final_test"),
        lambda m: m.update(replay_evaluated=True),
        lambda m: m["parameters"].update(decision_threshold=0.4),
    ],
)
def test_promotion_fail_closed(local, packaged, tmp_path, change):
    store, first, _ = local
    package, digest = altered_package(packaged, tmp_path, change)
    # MLflow itself rejects None/NaN metrics in some versions; either boundary blocks.
    with pytest.raises((ValueError, KeyError, TypeError)):
        candidate = store.register(package, digest)
        store.challenger(candidate)
        store.promote(candidate, expected=None, approved=True)
    assert "champion" not in store.aliases()
    assert store.metadata(first)["evaluation_split"] == "validation"


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m["metrics"].update(average_precision=0.9),
        lambda m: m["schema"].update(age="string"),
        lambda m: m.update(raw_sha256="changed"),
        lambda m: m["split_sha256"].update(validation="changed"),
    ],
)
def test_incompatible_or_regressing_challenger(local, packaged, tmp_path, change):
    store, first, _ = local
    store.challenger(first)
    store.promote(first, expected=None, approved=True)
    path, digest = altered_package(packaged, tmp_path, change)
    with pytest.raises((ValueError, KeyError)):
        candidate = store.register(path, digest)
        store.challenger(candidate)
        store.promote(candidate, expected=first, approved=True)
    assert store.aliases()["champion"] == first


@pytest.mark.parametrize("target", ["model/model.skops", "lineage.json", "manifest.json"])
def test_tampering_blocks_load_promotion_and_rollback(local, target):
    store, first, _ = local
    store.challenger(first)
    receipt = store.promote(first, expected=None, approved=True)
    second = store.register(
        store.package_path(first),
        store.client.get_model_version(store.name, first).tags["manifest_sha256"],
    )
    store.challenger(second)
    receipt = store.promote(second, expected=first, approved=True)
    path = store.package_path(first) / target
    with path.open("ab") as stream:
        stream.write(b"tampering")
    with pytest.raises(ValueError):
        store.load(first)
    with pytest.raises(ValueError):
        store.check(first)
    with pytest.raises(ValueError):
        store.rollback(receipt["event"], expected=second, approved=True)
    assert store.aliases()["champion"] == second


@pytest.mark.parametrize("kind", ["missing", "extra", "order", "float", "null", "category"])
def test_input_schema(local, kind):
    store, first, frame = local
    x = frame[["age", "pdays", "job"]].copy()
    if kind == "missing":
        x = x.drop(columns="age")
    elif kind == "extra":
        x["duration"] = 1
    elif kind == "order":
        x = x[["job", "age", "pdays"]]
    elif kind == "float":
        x["age"] = x.age.astype(float)
    elif kind == "null":
        x.loc[frame.index[0], "job"] = None
    else:
        x.loc[frame.index[0], "job"] = "undocumented"
    with pytest.raises(ValueError):
        store.predict(first, x)


def test_missing_lineage_and_schema_block_registration(packaged, tmp_path):
    for key in ("git_sha", "dependencies", "preprocessing_sha256", "source_run_id"):
        root = tmp_path / key
        path, digest = altered_package(packaged, root, lambda m, key=key: m.pop(key))
        with pytest.raises(ValueError, match="Incomplete lineage"):
            registry.LocalRegistry(root / "registry").register(path, digest)


def test_source_validation_and_artifact_guards(packaged, tmp_path, monkeypatch):
    _, _, frame, batch, root = packaged
    monkeypatch.setattr(registry, "ROOT", root)
    with pytest.raises(ValueError, match="validation partition"):
        registry.package_existing(batch, "logistic", tmp_path / "wrong", frame.iloc[:2])
    copied = tmp_path / "batch"
    shutil.copytree(batch, copied)
    with (copied / "logistic/pipeline.joblib").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        registry.package_existing(copied, "logistic", tmp_path / "tampered", frame)


def test_exclusive_alias_writer(local):
    store, first, _ = local
    (store.directory / "alias.lock").touch()
    with pytest.raises(FileExistsError):
        store.challenger(first)
    assert store.aliases() == {}


def test_model_card_documents_limits_and_registry():
    text = (ROOT / "docs/MODEL_CARD.md").read_text(encoding="utf-8")
    for phrase in ("0.008816", "794", "champion", "challenger", "lineage", "not deployed"):
        assert phrase in text


def test_generated_card_uses_lineage_and_alias_resolution(local):
    store, first, _ = local
    store.challenger(first)
    assert store.resolve("challenger") == first
    origin = store.lineage(first)
    assert origin["model_version"] == first
    assert origin["container_image"] is None
    card = render_model_card(origin["lineage"])
    assert f"{origin['lineage']['metrics']['average_precision']:.9f}" in card
    assert origin["lineage"]["source_run_id"] in card
    assert "Descriptive subgroups" in card
    assert "not deployed" in card


def test_run_metric_tampering_blocks_promotion(local):
    store, first, _ = local
    item = store.client.get_model_version(store.name, first)
    store.client.log_metric(item.run_id, "average_precision", 0.2)
    with pytest.raises(ValueError, match="run/lineage mismatch"):
        store.check(first)
    assert "champion" not in store.aliases()


def test_signature_and_file_set_integrity(local):
    store, first, _ = local
    path = store.package_path(first)
    (path / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="file set"):
        store.load(first)


@pytest.mark.parametrize("state", ["no_champion", "champion", "other_challenger"])
def test_notebook_preserves_initial_registry_state(local, packaged, tmp_path, state):
    from scripts.verify_lesson7 import execute_notebook

    store, first, _ = local
    store.challenger(first)
    if state == "champion":
        store.promote(first, expected=None, approved=True)
    elif state == "other_challenger":
        second = store.register(packaged[0], packaged[1])
        store.challenger(second)
    item = store.client.get_model_version(store.name, first)
    evidence = tmp_path / "evidence.json"
    write_json(
        evidence,
        {
            "schema_version": 2,
            "paths_relative_to": "evidence_parent",
            "registry_directory": "registry",
            "model_name": store.name,
            "model_version": first,
            "packaging_run_id": item.run_id,
            "manifest_sha256": item.tags["manifest_sha256"],
        },
    )
    before = store.snapshot()
    database_hash = experiments.sha256(store.directory / "registry.db")
    execute_notebook(evidence, tmp_path / "notebook/executed.ipynb")
    assert store.snapshot() == before
    assert experiments.sha256(store.directory / "registry.db") == database_hash


def test_evidence_rejects_missing_or_mismatched_registry(local, tmp_path):
    store, first, _ = local
    item = store.client.get_model_version(store.name, first)
    evidence = tmp_path / "evidence.json"
    record = {
        "schema_version": 2,
        "paths_relative_to": "evidence_parent",
        "registry_directory": "missing",
        "model_name": store.name,
        "model_version": first,
        "packaging_run_id": item.run_id,
        "manifest_sha256": item.tags["manifest_sha256"],
    }
    write_json(evidence, record)
    with pytest.raises(ValueError, match="existing registry"):
        registry.LocalRegistry.from_evidence(evidence)
    assert not (tmp_path / "missing").exists()
    record.update(registry_directory="registry", manifest_sha256="changed")
    write_json(evidence, record)
    with pytest.raises(ValueError, match="version differ"):
        registry.LocalRegistry.from_evidence(evidence)


def test_rebuild_selects_its_generated_batch_without_discovery(tmp_path, monkeypatch):
    from scripts import verify_lesson7

    monkeypatch.setattr(verify_lesson7, "ROOT", tmp_path)
    selected = []
    monkeypatch.setattr(
        verify_lesson7, "run_experiments", lambda *, output: selected.append(output)
    )
    monkeypatch.setattr(verify_lesson7, "prepare", lambda batch, output: selected.append(batch))
    output = tmp_path / "artifacts/lesson7/new"
    assert verify_lesson7.rebuild(output) == output / "evidence.json"
    assert selected[0] == selected[1]
    assert selected[0].parent == tmp_path / "artifacts/lesson5"
    output.mkdir(parents=True)
    with pytest.raises(ValueError, match="new output"):
        verify_lesson7.rebuild(output)


def test_reproduction_manifest_is_public_only():
    from scripts.reproduce_lesson7 import PUBLICATION_FILES, WORKING_TREE_FILES

    assert len(PUBLICATION_FILES) == len(set(PUBLICATION_FILES)) == 23
    assert len(WORKING_TREE_FILES) == 20
    forbidden_stems = {"AI_USAGE", "MOODLE_COMPLIANCE"}
    assert not any(Path(name).name.split(".")[0] in forbidden_stems for name in PUBLICATION_FILES)
    assert not any(
        name.startswith(("private_notes/", "data/", "artifacts/")) for name in PUBLICATION_FILES
    )


def test_reproduction_read_guard_blocks_original_assets(tmp_path):
    import subprocess
    import sys

    from scripts.reproduce_lesson7 import source_read_guard

    source = tmp_path / "source"
    workspace = source / "artifacts/lesson7/new"
    workspace.mkdir(parents=True)
    permitted = workspace / "permitted.txt"
    permitted.write_text("new workspace", encoding="utf-8")
    code = source_read_guard(source, workspace)
    code += "\nassert guard_self_test() == 7"
    code += f"\nassert Path({str(permitted)!r}).read_text() == 'new workspace'"
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
