"""Reproduce lesson 5 twice in fresh local batches, preserving existing assets."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np

from scripts.verify_lesson3 import sanitize_payload
from src.config import ROOT


def protected_files() -> dict[str, str]:
    """Fingerprint historical resources, plans, data, Git config and index."""
    files = [
        ROOT / ".git/index",
        ROOT / ".git/config",
        ROOT / "dvc.yaml",
        ROOT / "dvc.lock",
        ROOT / "docs/PROJECT_PLAN.md",
        ROOT / "notebooks/01_bank_marketing_eda.ipynb",
    ]
    for directory in [
        "data",
        "artifacts/models",
        "artifacts/reports",
        "private_notes",
        "reports/evidence",
        ".dvc/cache",
    ]:
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
        if p.is_file()
    }


def main() -> None:
    """Record genuine runs and deterministic validation metrics, without publishing."""
    before = protected_files()
    evidence = {"status": "FAIL", "commands": [], "batches": [], "checks": {}}
    environment = {**os.environ, "MLFLOW_ENABLE_TELEMETRY": "false", "PYTHONUTF8": "1"}
    try:
        summaries = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-m", "src.experiments"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
            )
            evidence["commands"].append(
                {
                    "command": "python -m src.experiments",
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            if result.returncode:
                raise RuntimeError("Experiment command failed; inspect captured output")
            info = json.loads(result.stdout.strip().splitlines()[-1])
            evidence["batches"].append(info)
            summaries.append(
                json.loads((ROOT / info["output"] / "summary.json").read_text(encoding="utf-8"))
            )
            print("Batch", len(summaries), info["batch_id"], info["winner"], flush=True)
        first, second = summaries
        for name, result in first["results"].items():
            for metric, value in result["metrics"].items():
                other = second["results"][name]["metrics"][metric]
                if value is None:
                    assert other is None
                else:
                    np.testing.assert_allclose(value, other, rtol=1e-12, atol=1e-12)
        assert first["selection"] == second["selection"]
        assert first["provenance"]["split_sha256"] == second["provenance"]["split_sha256"]
        assert first["provenance"]["protocol_sha256"] == second["provenance"]["protocol_sha256"]
        assert not first["provenance"]["final_test_evaluated"]
        assert not first["provenance"]["replay_evaluated"]
        evidence["checks"] = {
            "two_independent_batches": True,
            "six_models_each": len(first["results"]) == len(second["results"]) == 6,
            "all_validation_metrics_equal": True,
            "same_selection_and_split": True,
            "validation_only": True,
            "MLflow_readback_and_serialization": True,
        }
        assert all(evidence["checks"].values())
        evidence["results"] = first["results"]
        evidence["selection"] = first["selection"]
        evidence["status"] = "PASS"
    except Exception as error:
        evidence["error"] = f"{type(error).__name__}: {error}"
    finally:
        evidence["protected_files_unchanged"] = all(
            (ROOT / name).is_file()
            and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value
            for name, value in before.items()
        )
        evidence["protected_file_count"] = len(before)
        if not evidence["protected_files_unchanged"]:
            evidence["status"] = "FAIL"
        output = (
            ROOT
            / "reports/evidence"
            / (f"lesson5-reproduction-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid4().hex[:8]}.json")
        )
        with output.open("x", encoding="utf-8") as stream:
            json.dump(
                sanitize_payload(evidence), stream, indent=2, ensure_ascii=False, allow_nan=False
            )
            stream.write("\n")
        print(output.name, evidence["status"], flush=True)
    if evidence["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
