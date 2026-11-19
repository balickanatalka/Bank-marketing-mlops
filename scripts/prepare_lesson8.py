"""Prepare public-data serving artifacts in a fresh local clone and environment."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.reproduce_lesson7 import source_read_guard
from scripts.verify_lesson7 import fresh_id
from src.config import ROOT
from src.experiments import sha256

OVERLAY = (
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".gitignore",
    "src/serving.py",
    "src/serving_bundle.py",
    "src/serving_contract.py",
    "scripts/demo_lesson8.py",
    "scripts/prepare_lesson8.py",
    "configs/serving-logging.json",
    "docs/api/openapi-v1.json",
    "notebooks/04_model_serving.ipynb",
    "tests/test_serving.py",
)


def prepare(output: Path | None = None) -> dict:
    """Reuse lesson-7 rebuild only inside a new clone; copy no old models or data."""
    output = (output or ROOT / "artifacts/lesson8" / ("preparation-" + fresh_id())).resolve()
    if not output.is_relative_to((ROOT / "artifacts/lesson8").resolve()):
        raise ValueError("Preparation must stay under artifacts/lesson8")
    output.mkdir(parents=True, exist_ok=False)
    checkout = output / "checkout"
    bootstrap = output / "bootstrap"
    bootstrap.mkdir()
    (bootstrap / "sitecustomize.py").write_text(source_read_guard(ROOT, output), encoding="utf-8")
    for name in ("tmp", "matplotlib"):
        (output / name).mkdir()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("UV_", "MLFLOW_", "DVC_", "BANK_MARKETING_"))
        and k not in {"PYTHONPATH", "PROJEKT_SEED"}
    }
    env.update(
        PYTHONPATH=os.pathsep.join((str(bootstrap), str(checkout))),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        UV_NO_CACHE="1",
        UV_CACHE_DIR=str(output / "cache"),
        UV_PYTHON_DOWNLOADS="never",
        MLFLOW_ENABLE_TELEMETRY="false",
        MLFLOW_DISABLE_AGENT_HINT="1",
        MPLCONFIGDIR=str(output / "matplotlib"),
        TEMP=str(output / "tmp"),
        TMP=str(output / "tmp"),
    )
    steps = []
    result = {
        "status": "FAIL",
        "same_machine_only": True,
        "working_tree_overlay": True,
        "remote_clone_verified": False,
        "old_data_models_or_databases_copied": False,
        "steps": steps,
        "overlay_sha256": {p: sha256(ROOT / p) for p in OVERLAY},
    }

    def run(label, command, cwd):
        process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=1800)
        for stream in ("stdout", "stderr"):
            (output / f"{label}.{stream}.log").write_bytes(getattr(process, stream))
        steps.append({"step": label, "exit_code": process.returncode})
        print(label, process.returncode, flush=True)
        if process.returncode:
            raise RuntimeError(
                f"Preparation failed at {label}; inspect logs in the output directory"
            )
        return process.stdout.decode("utf-8")

    try:
        run("clone", ["git", "clone", "--no-hardlinks", str(ROOT), str(checkout)], ROOT)
        for name in OVERLAY:
            destination = checkout / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        assert not any(
            (checkout / p).exists() for p in ["data", "artifacts", ".venv", ".dvc/cache"]
        )
        assert not any(
            (checkout / "docs" / p).exists() for p in ["AI_USAGE.pl.md", "MOODLE_COMPLIANCE.pl.md"]
        )
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv is required")
        interpreter = Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python3")
        run("sync", [uv, "sync", "--locked", "--no-cache", "--python", str(interpreter)], checkout)
        python = checkout / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
        run(
            "guard",
            [
                str(python),
                "-B",
                "-c",
                "import sitecustomize; assert sitecustomize.guard_self_test()==7",
            ],
            checkout,
        )
        run(
            "rebuild",
            [
                str(python),
                "-B",
                "-m",
                "scripts.verify_lesson7",
                "--rebuild",
                "--output",
                "artifacts/lesson7/serving-demo",
            ],
            checkout,
        )
        evidence = checkout / "artifacts/lesson7/serving-demo/evidence.json"
        run(
            "http-demo",
            [
                str(python),
                "-B",
                "-m",
                "scripts.demo_lesson8",
                "--evidence",
                str(evidence),
                "--output",
                str(output / "http-demo"),
            ],
            checkout,
        )
        run(
            "api-tests",
            [
                str(python),
                "-B",
                "-m",
                "pytest",
                "tests/test_serving.py",
                "-q",
                "--basetemp",
                str(output / "pytest-api"),
                "--junitxml",
                str(output / "api-tests.xml"),
            ],
            checkout,
        )
        result.update(status="PASS", evidence=str(evidence), environment=str(python))
    finally:
        (output / "preparation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    """Print the explicit evidence path to pass to the API or notebook."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))


if __name__ == "__main__":
    main()
