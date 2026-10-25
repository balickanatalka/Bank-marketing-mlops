"""Rebuild from an allowlisted source copy without local data or environment.

This is a same-machine check, not an independent person's fresh Git clone.
Run: uv run --locked python scripts/verify_reproduction.py
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sanitize_output(text: str) -> str:
    """Replace local project and home paths without changing experiment results."""
    for path, marker in [(ROOT, "PROJECT_ROOT"), (Path.home(), "<USER_HOME>")]:
        text = text.replace(str(path), marker).replace(path.as_posix(), marker)
    return text


def main() -> None:
    """Leave the isolated copy in ignored artifacts for inspection; delete nothing."""
    base = ROOT / "artifacts"
    base.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="reproduction-", dir=base))
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(destination)],
        check=True,
    )
    for directory in ["src", "configs", "metadata", "tests"]:
        shutil.copytree(
            ROOT / directory, destination / directory, ignore=shutil.ignore_patterns("__pycache__")
        )
    for filename in ["pyproject.toml", "uv.lock", ".python-version"]:
        shutil.copy2(ROOT / filename, destination / filename)
    environment = os.environ.copy()
    for key in ["VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PROJEKT_SEED", "PYTHONPATH"]:
        environment.pop(key, None)
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv nie jest dostępny w PATH.")
    steps = []

    def run(arguments: list[str]) -> None:
        completed = subprocess.run(
            [uv, *arguments],
            cwd=destination,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        steps.append(
            {
                "command": ["uv", *arguments],
                "exit_code": completed.returncode,
                "stdout": sanitize_output(completed.stdout),
                "stderr": sanitize_output(completed.stderr),
            }
        )
        if completed.returncode:
            print(completed.stdout, completed.stderr)
            raise RuntimeError(f"Nieudane polecenie: {arguments}")

    run(["sync", "--locked"])
    run(["run", "--locked", "python", "--version"])
    run(["run", "--locked", "python", "-m", "src.cli", "all"])
    original = json.loads((ROOT / "artifacts/reports/metrics.json").read_text(encoding="utf-8"))
    reproduced = json.loads((destination / "artifacts/reports/metrics.json").read_text("utf-8"))
    if original["models"] != reproduced["models"]:
        raise RuntimeError("Metryki czystej kopii różnią się od oryginału.")
    run(["run", "--locked", "pytest", "-q", "--basetemp=artifacts/pytest-fresh-copy"])
    run(["run", "--locked", "python", "-m", "src.cli", "all"])
    repeated = json.loads((destination / "artifacts/reports/metrics.json").read_text("utf-8"))
    if repeated["models"] != reproduced["models"]:
        raise RuntimeError("Powtórzony przebieg zmienił metryki.")
    environment["PROJEKT_SEED"] = "123"
    run(["run", "--locked", "python", "-m", "src.cli", "all"])
    seeded = json.loads((destination / "artifacts/reports/metrics.json").read_text("utf-8"))
    if seeded["training"]["config"]["seed"] != 123:
        raise RuntimeError("PROJEKT_SEED nie został zastosowany.")
    evidence = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "local_clone_with_uncommitted_source_overlay": True,
        "remote_clone_verified": False,
        "python_version": reproduced["training"]["python"],
        "pinned_python_version": (destination / ".python-version").read_text().strip(),
        "same_machine_only": True,
        "independent_review": False,
        "clean_copy_metrics_equal": True,
        "repeat_metrics_equal": True,
        "seed_123_metrics_equal": seeded["models"] == reproduced["models"],
        "models": reproduced["models"],
        "steps": steps,
    }
    if evidence["python_version"] != evidence["pinned_python_version"]:
        raise RuntimeError("Rzeczywisty Python różni się od .python-version.")
    target = ROOT / "reports/evidence/reproduction.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(sanitize_output(f"PASS: {target}; isolated copy: {destination}"))


if __name__ == "__main__":
    main()
