"""Local, validation-only model packaging and controlled MLflow aliases.

Only trusted local sklearn artifacts may be loaded. Hashes detect accidental
modification; they are not signatures against an administrator changing the DB.
"""

import hashlib
import json
import math
from contextlib import contextmanager
from importlib.metadata import version as dependency_version
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import joblib
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.entities import Metric, Param
from mlflow.models import Model, infer_signature
from threadpoolctl import threadpool_limits

from src.config import ROOT, SAFE_FEATURES
from src.data.schema import CATEGORIES, INTEGER_BOUNDS
from src.experiments import sha256
from src.pipeline import config_hash, write_json

MODEL_NAME = "bank-marketing-validation"


def read_json(path: Path) -> dict:
    """Read UTF-8 metadata without executing an artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


def input_schema(features: list[str]) -> dict:
    """Describe ordered pre-contact inputs using the existing data contract."""
    if not features or len(set(features)) != len(features) or not set(features) <= SAFE_FEATURES:
        raise ValueError("Unsafe input schema")
    return {name: "integer" if name in INTEGER_BOUNDS else "string" for name in features}


def validate_input(frame: pd.DataFrame, schema: dict) -> None:
    """Reject extra/missing/reordered columns, nulls and invalid domain values."""
    if list(frame.columns) != list(schema) or frame.empty or frame.isna().any().any():
        raise ValueError("Input columns/order/nulls differ from schema")
    for name, kind in schema.items():
        column = frame[name]
        if kind == "integer":
            low, high = INTEGER_BOUNDS[name]
            if (
                not pd.api.types.is_integer_dtype(column)
                or pd.api.types.is_bool_dtype(column)
                or (column < low).any()
                or (high is not None and (column > high).any())
            ):
                raise ValueError(f"Invalid integer input: {name}")
        elif (
            not column.map(lambda value: isinstance(value, str)).all()
            or not column.isin(CATEGORIES[name]).all()
        ):
            raise ValueError(f"Invalid categorical input: {name}")


def verify_package(path: Path, expected_hash: str) -> dict:
    """Check the registry-anchored manifest and exact file set before unpickling."""
    if sha256(path / "manifest.json") != expected_hash:
        raise ValueError("Package manifest integrity failure")
    manifest = read_json(path / "manifest.json")
    files = {p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file()}
    if files != set(manifest) | {"manifest.json"}:
        raise ValueError("Package file set changed")
    for relative, digest in manifest.items():
        target = (path / relative).resolve()
        if not target.is_relative_to(path.resolve()) or sha256(target) != digest:
            raise ValueError("Package artifact integrity failure")
    metadata = read_json(path / "lineage.json")
    required = {
        "source_run_id",
        "git_sha",
        "raw_sha256",
        "dependencies",
        "source_sha256",
        "uv_lock_sha256",
        "dvc_lock_sha256",
        "split_sha256",
        "parameters",
        "metrics",
        "schema",
        "evaluation_split",
        "protocol",
        "data_config",
        "data_manifest",
        "source_model_sha256",
        "preprocessing_sha256",
        "recall_floor",
        "dummy_ap",
    }
    if not required <= metadata.keys() or any(metadata[k] is None for k in required):
        raise ValueError("Incomplete lineage")
    if any(not metadata[key] for key in ("git_sha", "source_run_id", "dependencies")):
        raise ValueError("Incomplete lineage")
    if metadata["schema"] != input_schema(metadata["data_config"]["data"]["features"]):
        raise ValueError("Schema differs from data configuration")
    if (
        config_hash(metadata["protocol"]) != metadata["protocol_sha256"]
        or config_hash(metadata["data_config"]) != metadata["data_config_sha256"]
        or metadata["data_manifest"]["sha256"] != metadata["raw_sha256"]
        or metadata["source_sha256"]["src/features/build.py"] != metadata["preprocessing_sha256"]
    ):
        raise ValueError("Inconsistent lineage hashes")
    if sha256(path / "model/code/src/features/build.py") != metadata["preprocessing_sha256"]:
        raise ValueError("Packaged preprocessing differs from training")
    for dependency, pinned in metadata["dependencies"].items():
        if dependency_version(dependency) != pinned:
            raise ValueError(f"Package dependency mismatch: {dependency}")
    serialization = metadata.get("serialization", {})
    if serialization != {"format": "skops", "version": dependency_version("skops")}:
        raise ValueError("Package serialization dependency mismatch")
    signature = Model.load(str(path / "model/MLmodel")).signature
    expected_types = {"integer": "long", "string": "string"}
    if (
        signature is None
        or signature.inputs is None
        or [(column.name, column.type.name) for column in signature.inputs.inputs]
        != [(name, expected_types[kind]) for name, kind in metadata["schema"].items()]
    ):
        raise ValueError("MLflow signature differs from input schema")
    return metadata


def package_existing(
    batch: Path, candidate: str, destination: Path, validation: pd.DataFrame
) -> str:
    """Package a recorded pipeline, verify lineage and reproduce validation scores.

    The caller supplies validation only. Its complete fingerprint must equal the
    original experiment fingerprint. No fit, final-test or replay access occurs.
    Return the SHA-256 of the new package manifest for the registry anchor.
    """
    summary = read_json(batch / "summary.json")
    provenance = summary["provenance"]
    result = summary["results"][candidate]
    protocol = read_json(batch / "protocol.json")
    config = read_json(batch / "data_config.json")
    manifest = read_json(ROOT / config["data"]["manifest"])
    if (
        provenance["evaluation_split"] != "validation"
        or provenance["final_test_evaluated"] is not False
        or provenance["replay_evaluated"] is not False
        or config_hash(protocol) != provenance["protocol_sha256"]
        or config_hash(config) != provenance["data_config_sha256"]
        or manifest["sha256"] != provenance["raw_sha256"]
        or sha256(batch / candidate / "pipeline.joblib") != result["model_sha256"]
        or sha256(ROOT / "src/features/build.py")
        != provenance["source_sha256"]["src/features/build.py"]
    ):
        raise ValueError("Source experiment integrity/provenance failure")
    digest = hashlib.sha256(
        validation.to_csv(index=False, lineterminator="\n").encode()
    ).hexdigest()
    if digest != provenance["split_sha256"]["validation"]:
        raise ValueError("Only the recorded validation partition is permitted")
    for dependency, pinned in provenance["dependencies"].items():
        if dependency_version(dependency) != pinned:
            raise ValueError(f"Source dependency mismatch: {dependency}")
    uri = "sqlite:///" + (batch.resolve() / "tracking/mlflow.db").as_posix()
    source_client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    for name in (candidate, "dummy", "logistic"):
        recorded = summary["results"][name]
        run = source_client.get_run(recorded["run_id"])
        if (
            run.info.status != "FINISHED"
            or run.data.tags.get("evaluation_split") != "validation"
            or run.data.params != {k: str(v) for k, v in recorded["parameters"].items()}
            or run.data.metrics
            != {k: float(v) for k, v in recorded["metrics"].items() if v is not None}
        ):
            raise ValueError("Source MLflow run differs from experiment summary")
    features = config["data"]["features"]
    schema = input_schema(features)
    x = validation[features]
    validate_input(x, schema)
    pipeline = joblib.load(batch / candidate / "pipeline.joblib")
    from src.pipeline import classification_metrics

    with threadpool_limits(limits=1):
        scores = pipeline.predict_proba(x)[:, 1]
        metrics = classification_metrics((validation.y == "yes").astype(int), scores >= 0.5, scores)
    for key, value in metrics.items():
        if value is not None and not math.isclose(value, result["metrics"][key], abs_tol=1e-12):
            raise ValueError("Validation metrics do not reproduce")
    destination.mkdir(parents=True, exist_ok=False)
    lineage = {
        **provenance,
        "source_run_id": result["run_id"],
        "parameters": result["parameters"],
        "metrics": result["metrics"],
        "schema": schema,
        "protocol": protocol,
        "data_config": config,
        "data_manifest": manifest,
        "source_model_sha256": result["model_sha256"],
        "preprocessing_sha256": provenance["source_sha256"]["src/features/build.py"],
        "dummy_ap": summary["results"]["dummy"]["metrics"]["average_precision"],
        "recall_floor": summary["results"]["logistic"]["metrics"]["recall_yes"],
        "package_format": 1,
        "deployed": False,
        "error_analysis": read_json(batch / candidate / "errors.json"),
        "serialization": {"format": "skops", "version": dependency_version("skops")},
    }
    write_json(destination / "lineage.json", lineage)
    mlflow.sklearn.save_model(
        pipeline,
        str(destination / "model"),
        signature=infer_signature(x, pipeline.predict(x)),
        input_example=pd.DataFrame(
            {
                name: [30 if name == "age" else 999 if name == "pdays" else 0]
                if kind == "integer"
                else [sorted(CATEGORIES[name])[0]]
                for name, kind in schema.items()
            }
        ),
        serialization_format="skops",
        skops_trusted_types=["src.features.build.history_features"],
        pip_requirements=[
            f"{name}=={pinned}" for name, pinned in provenance["dependencies"].items()
        ]
        + [f"skops=={dependency_version('skops')}"],
        code_paths=[str(ROOT / "src")],
        metadata={"evaluation_split": "validation", "deployed": False},
    )
    reloaded = mlflow.sklearn.load_model(str(destination / "model"))
    with threadpool_limits(limits=1):
        np.testing.assert_allclose(reloaded.predict_proba(x)[:, 1], scores, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(reloaded.predict(x), pipeline.predict(x))
    write_json(
        destination / "manifest.json",
        {
            p.relative_to(destination).as_posix(): sha256(p)
            for p in sorted(destination.rglob("*"))
            if p.is_file()
        },
    )
    return sha256(destination / "manifest.json")


class LocalRegistry:
    """A local SQLite registry with single-writer alias transitions.

    All alias writers must use this wrapper and its exclusive filesystem lock.
    MLflow provides no alias compare-and-swap; direct UI/API edits bypass it.
    """

    def __init__(self, directory: Path, name: str = MODEL_NAME):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.uri = "sqlite:///" + (self.directory / "registry.db").as_posix()
        self.client = MlflowClient(tracking_uri=self.uri, registry_uri=self.uri)

    @classmethod
    def from_evidence(cls, evidence_path: Path):
        """Open an existing registry using a portable, explicit evidence handoff."""
        evidence = read_json(evidence_path)
        if (
            evidence.get("schema_version") != 2
            or evidence.get("paths_relative_to") != "evidence_parent"
        ):
            raise ValueError("Use schema-2 evidence generated for this registry")
        parent = evidence_path.resolve().parent
        directory = (parent / evidence["registry_directory"]).resolve()
        if not directory.is_relative_to(parent) or not (directory / "registry.db").is_file():
            raise ValueError("Evidence must point to an existing registry inside its directory")
        store = cls(directory, name=evidence["model_name"])
        item = store.client.get_model_version(store.name, str(evidence["model_version"]))
        if (
            item.run_id != evidence["packaging_run_id"]
            or item.tags["manifest_sha256"] != evidence["manifest_sha256"]
        ):
            raise ValueError("Evidence and registered version differ")
        store.metadata(str(evidence["model_version"]))
        return store

    def snapshot(self) -> dict:
        """Capture aliases and version identities to detect changes during a read-only demo."""
        versions = self.client.search_model_versions(filter_string=f"name = '{self.name}'")
        return {
            "aliases": self.aliases(),
            "versions": sorted(
                (str(item.version), item.run_id, item.current_stage, sorted(item.tags.items()))
                for item in versions
            ),
        }

    @contextmanager
    def _writer(self):
        lock = self.directory / "alias.lock"
        handle = lock.open("x")
        try:
            with handle:
                yield
        finally:
            lock.unlink()

    def aliases(self) -> dict:
        """Return aliases without treating backend errors as missing aliases."""
        return {
            alias: str(model_version)
            for alias, model_version in self.client.get_registered_model(self.name).aliases.items()
        }

    def register(self, package: Path, manifest_hash: str) -> str:
        """Create a new version and packaging run; never assign an alias."""
        metadata = verify_package(package, manifest_hash)
        with self._writer():
            names = {m.name for m in self.client.search_registered_models()}
            if self.name not in names:
                self.client.create_registered_model(
                    self.name, tags={"scope": "academic-validation"}
                )
            experiments = self.client.search_experiments(filter_string="name = 'lesson7-packaging'")
            experiment_id = (
                experiments[0].experiment_id
                if experiments
                else self.client.create_experiment(
                    "lesson7-packaging", artifact_location=(self.directory / "runs").as_uri()
                )
            )
            run = self.client.create_run(
                experiment_id,
                tags={
                    "source_run_id": metadata["source_run_id"],
                    "evaluation_split": "validation",
                    "git_sha": metadata["git_sha"],
                    "deployed": "false",
                },
            )
            run_id = run.info.run_id
            try:
                self.client.log_batch(
                    run_id,
                    params=[Param(k, str(v)) for k, v in metadata["parameters"].items()],
                    metrics=[
                        Metric(k, float(v), 0, 0)
                        for k, v in metadata["metrics"].items()
                        if v is not None
                    ],
                )
                self.client.log_artifacts(run_id, str(package.resolve()), artifact_path="package")
                source = self.client.get_run(run_id).info.artifact_uri + "/package/model"
                result = self.client.create_model_version(
                    self.name,
                    source,
                    run_id=run_id,
                    tags={
                        "manifest_sha256": manifest_hash,
                        "source_run_id": metadata["source_run_id"],
                        "deployed": "false",
                    },
                )
                self.client.set_terminated(run_id)
            except Exception:
                self.client.set_terminated(run_id, "FAILED")
                raise
            self.metadata(result.version)
            return str(result.version)

    def package_path(self, model_version: str) -> Path:
        """Resolve the registered local artifact location, never a remote URI."""
        item = self.client.get_model_version(self.name, str(model_version))
        parsed = urlparse(item.source)
        if parsed.scheme != "file" or parsed.netloc:
            raise ValueError("Only local file artifacts are supported")
        path = Path(unquote(parsed.path.lstrip("/") if parsed.path[2:3] == ":" else parsed.path))
        path = path.resolve().parent
        if not path.is_relative_to(self.directory):
            raise ValueError("Artifact is outside this local registry")
        return path

    def metadata(self, model_version: str) -> dict:
        """Read verified lineage linked to an MLflow model version and run."""
        item = self.client.get_model_version(self.name, str(model_version))
        metadata = verify_package(self.package_path(model_version), item.tags["manifest_sha256"])
        run = self.client.get_run(item.run_id)
        if (
            run.info.status != "FINISHED"
            or item.tags["source_run_id"] != metadata["source_run_id"]
            or run.data.metrics
            != {k: float(v) for k, v in metadata["metrics"].items() if v is not None}
            or run.data.params != {k: str(v) for k, v in metadata["parameters"].items()}
        ):
            raise ValueError("Registry run/lineage mismatch")
        return metadata

    def load(self, model_version: str):
        """Load an integrity-checked complete sklearn Pipeline by exact version."""
        self.metadata(model_version)
        return mlflow.sklearn.load_model(str(self.package_path(model_version) / "model"))

    def resolve(self, alias: str) -> str:
        """Resolve a mutable alias once, then use the returned exact version."""
        return str(self.client.get_model_version_by_alias(self.name, alias).version)

    def lineage(self, model_version: str) -> dict:
        """Follow version to packaging run, original run and verified provenance."""
        metadata = self.metadata(model_version)
        item = self.client.get_model_version(self.name, str(model_version))
        return {
            "model_name": self.name,
            "model_version": str(model_version),
            "packaging_run_id": item.run_id,
            "lineage": metadata,
            "container_image": None,
            "deployed": False,
        }

    def predict(self, model_version: str, frame: pd.DataFrame) -> np.ndarray:
        """Validate the raw feature contract and return class probabilities."""
        metadata = self.metadata(model_version)
        validate_input(frame, metadata["schema"])
        return self.load(model_version).predict_proba(frame)

    def check(self, model_version: str) -> dict:
        """Fail closed on missing metrics, changed lineage or champion regression."""
        candidate = self.metadata(model_version)
        if (
            candidate["evaluation_split"] != "validation"
            or candidate["final_test_evaluated"] is not False
            or candidate["replay_evaluated"] is not False
            or candidate["parameters"]["decision_threshold"] != 0.5
        ):
            raise ValueError("Promotion requires untouched holdouts and threshold 0.5")
        ap, recall = (candidate["metrics"][key] for key in ("average_precision", "recall_yes"))
        values = [ap, recall, candidate["dummy_ap"], candidate["recall_floor"]]
        if any(
            not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
            for v in values
        ):
            raise ValueError("Missing/nonfinite/out-of-range metrics")
        if ap <= candidate["dummy_ap"] or recall < candidate["recall_floor"]:
            raise ValueError("Validation AP/recall gate failed")
        champion = self.aliases().get("champion")
        if champion:
            previous = self.metadata(champion)
            for key in (
                "schema",
                "raw_sha256",
                "split_sha256",
                "protocol_sha256",
                "data_config_sha256",
            ):
                if candidate[key] != previous[key]:
                    raise ValueError(f"Incompatible champion comparison: {key}")
            if (
                ap < previous["metrics"]["average_precision"]
                or recall < previous["metrics"]["recall_yes"]
            ):
                raise ValueError("Candidate regresses against champion")
        return {
            "eligible": True,
            "version": str(model_version),
            "champion": champion,
            "average_precision": ap,
            "recall_yes": recall,
            "deployed": False,
        }

    def challenger(self, model_version: str) -> None:
        """Assign a verified candidate alias without changing champion."""
        with self._writer():
            self.metadata(model_version)
            self.client.set_registered_model_alias(self.name, "challenger", str(model_version))

    def promote(self, model_version: str, *, expected: str | None, approved: bool = False) -> dict:
        """Change academic champion only with explicit approval and expected version."""
        if not approved:
            raise PermissionError("Explicit approval is required for champion changes")
        with self._writer():
            decision = self.check(model_version)
            if decision["champion"] != expected:
                raise ValueError("Champion changed since review")
            if self.aliases().get("challenger") != str(model_version):
                raise ValueError("Promote the reviewed challenger only")
            return self._transition(str(model_version), expected, "promote")

    def _transition(self, target: str | None, previous: str | None, action: str) -> dict:
        event = {"action": action, "previous": previous, "target": target, "status": "pending"}
        path = self.directory / f"transition-{uuid4().hex}.json"
        write_json(path, event)
        if target is None:
            self.client.delete_registered_model_alias(self.name, "champion")
        else:
            self.client.set_registered_model_alias(self.name, "champion", target)
        event["status"] = "applied"
        write_json(path, event)
        return {**event, "event": path.name}

    def rollback(self, event_name: str, *, expected: str, approved: bool = False) -> dict:
        """Restore the prior champion from a completed local promotion receipt."""
        if not approved:
            raise PermissionError("Explicit approval is required for rollback")
        with self._writer():
            if Path(event_name).name != event_name or not event_name.startswith("transition-"):
                raise ValueError("Invalid transition receipt")
            event = read_json(self.directory / event_name)
            if (
                event["status"] != "applied"
                or event["action"] != "promote"
                or event["target"] != expected
                or self.aliases().get("champion") != expected
            ):
                raise ValueError("Stale or incomplete rollback receipt")
            if event["previous"] is not None:
                self.metadata(event["previous"])
            return self._transition(event["previous"], expected, "rollback")
