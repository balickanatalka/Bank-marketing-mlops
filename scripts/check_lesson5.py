"""Run lesson 5 quality checks and exclusively create new, redacted evidence."""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from urllib.request import urlopen
from uuid import uuid4

from scripts.verify_lesson3 import sanitize_payload
from scripts.verify_lesson5 import protected_files
from src.config import ROOT


def main() -> None:
    """Check code, tests, hooks, dependencies and DVC without reproducing baseline."""
    before = protected_files()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required")
    files = [
        p.relative_to(ROOT).as_posix()
        for directory in ["src", "tests", "scripts"]
        for p in sorted((ROOT / directory).rglob("*.py"))
    ]
    files.append("notebooks/02_model_experiments.ipynb")
    (ROOT / "artifacts/lesson5-checks").mkdir(parents=True, exist_ok=True)
    commands = [
        [uv, "run", "--locked", "ruff", "check", "src", "tests", "scripts", "notebooks"],
        [
            uv,
            "run",
            "--locked",
            "ruff",
            "format",
            "--check",
            "src",
            "tests",
            "scripts",
            "notebooks",
        ],
        [
            uv,
            "run",
            "--locked",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            f"artifacts/lesson5-checks/{stamp}",
        ],
        [uv, "run", "--locked", "pre-commit", "run", "--files", *files],
        [uv, "lock", "--check"],
        [uv, "pip", "check"],
        [uv, "run", "--locked", "dvc", "dag", "--dot"],
        [uv, "run", "--locked", "dvc", "status", "--json"],
        ["git", "diff", "--check"],
    ]
    evidence = {
        "status": "FAIL",
        "checks": [],
        "root_dvc_note": "Baseline outputs/cache absent; source/dependency changes require repro. "
        "No root repro or historical lock update performed.",
    }
    environment = {**os.environ, "MLFLOW_ENABLE_TELEMETRY": "false", "PYTHONUTF8": "1"}
    try:
        for command in commands:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            evidence["checks"].append(
                {
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            print(" ".join(command[1:]), "->", result.returncode, flush=True)
            if result.returncode:
                raise RuntimeError("Quality check failed; inspect recorded output")
            if command[-2:] == ["status", "--json"]:
                evidence["root_dvc_status"] = json.loads(result.stdout)
        notebook = json.loads(
            (ROOT / "notebooks/02_model_experiments.ipynb").read_text(encoding="utf-8")
        )
        code = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        assert all(cell["execution_count"] is not None for cell in code)
        assert not any(
            output.get("output_type") == "error" for cell in code for output in cell["outputs"]
        )
        evidence["notebook"] = {"executed_code_cells": len(code), "errors": 0}
        with urlopen("http://127.0.0.1:5005/health", timeout=10) as response:
            assert response.status == 200
        with urlopen("http://127.0.0.1:5005/", timeout=10) as response:
            assert response.status == 200
        evidence["local_MLflow_UI"] = {"url": "http://127.0.0.1:5005", "health": 200, "root": 200}
        evidence["status"] = "PASS"
    except Exception as error:
        evidence["error"] = f"{type(error).__name__}: {error}"
    finally:
        current = protected_files()
        evidence["protected_files_unchanged"] = all(current.get(k) == v for k, v in before.items())
        evidence["protected_file_count"] = len(before)
        if not evidence["protected_files_unchanged"]:
            evidence["status"] = "FAIL"
        output = ROOT / "reports/evidence" / f"lesson5-checks-{stamp}.json"
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
