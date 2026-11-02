"""Exercise DVC in a new isolated workspace, preserving existing resources.

Run: uv run --locked python -m scripts.verify_lesson4
Downloads the pinned CSV from UCI. No remote DVC storage is used.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from scripts.verify_lesson3 import sanitize_payload
from src.config import ROOT


def digest(path: Path) -> str:
    """Fingerprint a file without parsing or evaluating its contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files() -> dict[str, str]:
    """Protect original data, models, reports, notebook, cache and Git index."""
    paths = [ROOT / ".git/index", ROOT / ".dvc/config", ROOT / "metadata/data_manifest.json"]
    for directory in [
        "data",
        "artifacts/models",
        "artifacts/reports",
        "notebooks",
        "private_notes",
        "reports/evidence",
        ".dvc/cache",
    ]:
        paths.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths if p.is_file()}


def main() -> None:
    """Record actual commands, expected rejection, cache and parameter behavior."""
    before = protected_files()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    workspace = Path(tempfile.mkdtemp(prefix=f"bank-lesson4-{stamp}-"))
    report = {
        "status": "FAIL",
        "workspace": workspace.name,
        "commands": [],
        "checks": {},
        "download": "UCI, no original CSV/cache copied",
    }
    environment = os.environ.copy()
    environment.pop("PROJEKT_SEED", None)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
    environment.update(DVC_NO_ANALYTICS="1", MPLBACKEND="Agg", PYTHONUTF8="1")

    def run(*args: str, expected_failure: bool = False) -> str:
        result = subprocess.run(
            [sys.executable, "-m", "dvc", *args],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        report["commands"].append(
            {
                "command": ["python", "-m", "dvc", *args],
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "expected_failure": expected_failure,
            }
        )
        print("dvc", *args, "->", result.returncode, flush=True)
        if (result.returncode != 0) != expected_failure:
            raise RuntimeError(
                f"Unexpected exit code for dvc {' '.join(args)}: {result.stdout}\n{result.stderr}"
            )
        return result.stdout + result.stderr

    try:
        for directory in ["src", "configs", "metadata"]:
            shutil.copytree(
                ROOT / directory,
                workspace / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        for name in ["dvc.yaml", "pyproject.toml", "uv.lock", ".python-version", ".dvcignore"]:
            shutil.copyfile(ROOT / name, workspace / name)
        (workspace / ".dvc").mkdir()
        (workspace / ".dvc/config").write_text(
            "[core]\n    no_scm = true\n    autostage = false\n    analytics = false\n"
            "    check_update = false\n[cache]\n    type = copy\n",
            encoding="utf-8",
        )
        first = run("repro")
        stages = ["download", "validate", "prepare", "train", "evaluate"]
        assert all(f"Running stage '{name}'" in first for name in stages)
        initial_lock = (workspace / "dvc.lock").read_bytes()
        initial = yaml.safe_load(initial_lock)["stages"]
        report["checks"]["first_run_all_stages"] = True
        metrics = json.loads(
            (workspace / "artifacts/lesson4/reports/metrics.json").read_text(encoding="utf-8")
        )
        assert metrics["evaluation_split"] == "validation" and not metrics["final_test_evaluated"]
        report["validation_metrics"] = metrics["models"]
        report["checks"]["validation_only"] = True
        second = run("repro")
        assert "Running stage '" not in second
        assert (workspace / "dvc.lock").read_bytes() == initial_lock
        report["checks"]["second_run_no_execution"] = True
        run("status")
        parameter_path = workspace / "configs/lesson4.yaml"
        config = yaml.safe_load(parameter_path.read_text(encoding="utf-8"))
        config["model"]["max_iter"] += 1
        parameter_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        changed = run("repro")
        after = yaml.safe_load((workspace / "dvc.lock").read_text(encoding="utf-8"))["stages"]
        for name in ["download", "validate", "prepare"]:
            assert initial[name] == after[name]
            assert f"Running stage '{name}'" not in changed
        for name in ["train", "evaluate"]:
            assert f"Running stage '{name}'" in changed
        report["checks"]["model_parameter_only_train_evaluate"] = True
        # Corrupt only the disposable raw file; validate must reject before downstream work.
        model = workspace / "artifacts/lesson4/models/model.joblib"
        model_before = digest(model)
        raw = workspace / config["data"]["raw"]
        with raw.open("r+b") as stream:
            stream.write(b"!")
        rejected = run("repro", "--single-item", "validate", expected_failure=True)
        assert "SHA-256" in rejected
        assert digest(model) == model_before
        assert (
            "Running stage 'train'" not in rejected and "Running stage 'evaluate'" not in rejected
        )
        report["checks"]["corrupt_data_rejected_no_training"] = True
        # Keep the baseline lock separate from the parameter/corruption experiments.
        (workspace / "baseline.lock").write_bytes(initial_lock)
        destination = ROOT / "dvc.lock"
        if not destination.exists():
            with destination.open("xb") as stream:
                stream.write(initial_lock)
        report["root_lock_matches_baseline"] = destination.read_bytes() == initial_lock
        report["lock_sha256"] = hashlib.sha256(initial_lock).hexdigest()
        report["status"] = "PASS"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["protected_files_unchanged"] = all(
            (ROOT / name).is_file() and digest(ROOT / name) == value
            for name, value in before.items()
        )
        report["protected_file_count"] = len(before)
        if not report["protected_files_unchanged"]:
            report["status"] = "FAIL"
        output = ROOT / "reports/evidence" / f"lesson4-dvc-{stamp}.json"
        with output.open("x", encoding="utf-8") as stream:
            json.dump(
                sanitize_payload(report), stream, indent=2, ensure_ascii=False, allow_nan=False
            )
            stream.write("\n")
        print(output.name, report["status"], flush=True)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
