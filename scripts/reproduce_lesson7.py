"""Reproduce the working-tree lesson 7 in a local clone with fresh dependencies/data.

This is not a post-publication remote clone test or independent-machine validation.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.verify_lesson7 import fresh_id
from src.config import ROOT
from src.experiments import sha256
from src.pipeline import write_json

# Exact overlay: public summaries are references, never old data/models/MLflow databases.
WORKING_TREE_FILES = (
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "docs/ARCHITECTURE.md",
    "docs/MODEL_CARD.md",
    "docs/MODEL_REGISTRY.pl.md",
    "docs/TEST_STRATEGY.md",
    "docs/THIRD_PARTY_NOTICES.md",
    "notebooks/03_model_registry.ipynb",
    "scripts/lineage.py",
    "scripts/verify_lesson7.py",
    "scripts/demo_lesson7.py",
    "scripts/reproduce_lesson7.py",
    "src/model_card.py",
    "src/registry.py",
    "tests/test_registry.py",
    "reports/lesson7_registry.pl.md",
    "reports/evidence/lesson7-registry.json",
    "reports/evidence/lesson7-checks.json",
    "reports/evidence/lesson7-integrity.json",
)

PUBLICATION_FILES = WORKING_TREE_FILES + (
    "reports/evidence/lesson7-repair-checks.json",
    "reports/evidence/lesson7-repair-reproduction.json",
    "reports/evidence/lesson7-repair-integrity.json",
)


def source_read_guard(source: Path, workspace: Path) -> str:
    """Build a Python audit hook denying access to original private/project assets.

    The guard is also loaded by child Python processes through sitecustomize.
    This is a regression check for trusted code, not an operating-system sandbox.
    """
    return f"""
import sys
from pathlib import Path
_source = Path({str(source.resolve())!r})
_workspace = Path({str(workspace.resolve())!r})
_blocked = [
    _source / name for name in (
        "data", "artifacts", ".dvc/cache", "private_notes", "docs/PROJECT_PLAN.md",
        "docs/AI_USAGE.pl.md", "docs/MOODLE_COMPLIANCE.pl.md",
    )
]
def _guard(event, arguments):
    if event != "open" or not isinstance(arguments[0], (str, bytes)):
        return
    path = Path(arguments[0].decode() if isinstance(arguments[0], bytes) else arguments[0])
    path = path.resolve()
    if path.is_relative_to(_workspace):
        return
    if any(path == target or path.is_relative_to(target) for target in _blocked):
        raise PermissionError("Source private/project assets are disabled during reproduction")
sys.addaudithook(_guard)
def guard_self_test():
    for target in _blocked:
        try:
            with target.open("rb"):
                raise AssertionError("The source read guard did not block access")
        except PermissionError:
            pass
    return len(_blocked)
"""


def reproduce(output: Path | None = None) -> dict:
    """Clone code, overlay the allowlist, install without cache, download UCI and rebuild."""
    output = (output or ROOT / "artifacts/lesson7" / ("reproduction-" + fresh_id())).resolve()
    if not output.is_relative_to((ROOT / "artifacts/lesson7").resolve()):
        raise ValueError("Reproduction must remain under artifacts/lesson7")
    output.mkdir(parents=True, exist_ok=False)
    checkout = output / "worktree"
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UV_", "MLFLOW_", "DVC_", "BANK_MARKETING_"))
        and key != "PROJEKT_SEED"
    }
    environment.update(
        PYTHONUTF8="1",
        UV_CACHE_DIR=str(output / "uv-cache"),
        MLFLOW_ENABLE_TELEMETRY="false",
        IPYTHONDIR=str(output / "ipython"),
        JUPYTER_RUNTIME_DIR=str(output / "jupyter-runtime"),
    )
    bootstrap = output / "bootstrap"
    bootstrap.mkdir()
    guard_code = source_read_guard(ROOT, output)
    (bootstrap / "sitecustomize.py").write_text(guard_code, encoding="utf-8")
    # Do not inherit PYTHONPATH entries pointing at the original project.
    environment["PYTHONPATH"] = os.pathsep.join((str(bootstrap), str(checkout)))
    guard_namespace = {}
    exec(compile(guard_code, "<lesson7-source-guard>", "exec"), guard_namespace)
    guarded_targets = guard_namespace["guard_self_test"]()
    steps = []
    result = {
        "status": "FAIL",
        "working_tree_overlay": True,
        "remote_clone_verified": False,
        "same_machine_only": True,
        "fresh_venv": True,
        "existing_uv_cache_used": False,
        "old_data_models_or_mlflow_copied": False,
        "workspace_directory": checkout.relative_to(ROOT).as_posix(),
        "logs_directory": output.relative_to(ROOT).as_posix(),
        "private_documents_required": False,
        "source_read_guard_targets": guarded_targets,
        "source_read_guard_self_test": True,
        "steps": steps,
        "overlay_sha256": {name: sha256(ROOT / name) for name in WORKING_TREE_FILES},
    }

    def run(arguments: list[str], label: str, *, cwd: Path) -> str:
        process = subprocess.run(
            arguments,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        log = output / (label + ".log")
        log.write_text(process.stdout + process.stderr, encoding="utf-8")
        steps.append({"step": label, "exit_code": process.returncode, "log_sha256": sha256(log)})
        print(label, process.returncode, flush=True)
        if process.returncode:
            raise RuntimeError(f"Reproduction failed at {label}; inspect the local log")
        return process.stdout

    try:
        run(["git", "clone", "--no-hardlinks", str(ROOT), str(checkout)], "clone", cwd=ROOT)
        for name in WORKING_TREE_FILES:
            target = checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        assert not any(
            (checkout / name).exists() for name in [".venv", "data", "artifacts", ".dvc/cache"]
        )
        assert not any(
            (checkout / "docs" / name).exists()
            for name in ("AI_USAGE.pl.md", "MOODLE_COMPLIANCE.pl.md")
        )
        result["private_documents_absent_in_checkout"] = True
        # Use the existing pinned interpreter, but no old venv, package cache or project data.
        interpreter = Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python3")
        run(
            [uv, "sync", "--locked", "--no-cache", "--python", str(interpreter)],
            "sync",
            cwd=checkout,
        )
        run(
            [
                uv,
                "run",
                "--locked",
                "--no-sync",
                "python",
                "-c",
                "import sitecustomize; assert sitecustomize.guard_self_test() == 7",
            ],
            "child_source_guard",
            cwd=checkout,
        )
        stdout = run(
            [
                uv,
                "run",
                "--locked",
                "--no-sync",
                "python",
                "-m",
                "scripts.verify_lesson7",
                "--rebuild",
                "--output",
                "artifacts/lesson7/rebuilt",
                "--execute-notebook",
            ],
            "rebuild",
            cwd=checkout,
        )
        handoffs = [
            line.removeprefix("EVIDENCE=")
            for line in stdout.splitlines()
            if line.startswith("EVIDENCE=")
        ]
        if len(handoffs) != 1:
            raise ValueError("Rebuild did not provide one explicit evidence handoff")
        evidence_path = checkout / handoffs[0]
        run(
            [
                uv,
                "run",
                "--locked",
                "--no-sync",
                "python",
                "-m",
                "scripts.demo_lesson7",
                "--evidence",
                str(evidence_path),
            ],
            "isolated_demo",
            cwd=checkout,
        )
        rebuilt = json.loads(evidence_path.read_text(encoding="utf-8"))
        config = json.loads(
            (checkout / rebuilt["source_batch_directory"] / "data_config.json").read_text()
        )
        environment["BANK_MARKETING_QUALITY_CSV"] = str(checkout / config["data"]["raw"])
        test_stdout = run(
            [
                uv,
                "run",
                "--locked",
                "--no-sync",
                "pytest",
                "-q",
                "--basetemp",
                "artifacts/lesson7/fresh-pytest",
            ],
            "pytest_with_uci",
            cwd=checkout,
        )
        result["fresh_pytest_summary"] = test_stdout.strip().splitlines()[-1]
        reference = json.loads(
            (checkout / "reports/lesson5_experiments.json").read_text(encoding="utf-8")
        )
        for key in ("average_precision", "recall_yes"):
            if (
                abs(
                    rebuilt["quality_decision"][key]
                    - reference["results"]["logistic"]["metrics"][key]
                )
                > 1e-12
            ):
                raise ValueError("Rebuilt validation metrics differ from the public reference")
        result.update(
            status="PASS",
            public_uci_download_verified=True,
            source_batch=rebuilt["source_batch_directory"],
            validation_metrics_match_reference=True,
            current_evidence_handoff=handoffs[0],
            isolated_demo=json.loads(
                (evidence_path.parent / "isolated-demo/result.json").read_text()
            ),
        )
    except Exception as error:
        result["error_type"] = type(error).__name__
        raise
    finally:
        write_json(output / "result.json", result)
    return result


def main() -> None:
    """Create a new reproduction workspace, never modify the original repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = reproduce(args.output)
    if args.evidence is not None:
        target = args.evidence.resolve()
        if not target.is_relative_to((ROOT / "reports/evidence").resolve()):
            parser.error("Public evidence must remain under reports/evidence")
        write_json(target, result)
    print(result["status"])


if __name__ == "__main__":
    main()
