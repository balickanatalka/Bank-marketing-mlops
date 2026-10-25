"""Run local quality checks and record command output."""

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Save actual command output; stop on the first failed check."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required")
    files = [
        str(p.relative_to(ROOT))
        for directory in ["src", "tests", "scripts", "notebooks"]
        for p in (ROOT / directory).rglob("*")
        if p.suffix in {".py", ".ipynb"}
    ]
    commands = [
        ["ruff", "check", "src", "tests", "scripts", "notebooks"],
        ["ruff", "format", "--check", "src", "tests", "scripts", "notebooks"],
        ["pytest", "-q", "-p", "no:cacheprovider", f"--basetemp=artifacts/checks-{uuid4().hex}"],
        ["pre-commit", "run", "--files", *files],
    ]
    records = []
    for arguments in commands:
        result = subprocess.run(
            [uv, "run", "--locked", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        records.append(
            {
                "command": ["uv", "run", "--locked", *arguments],
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        print(result.stdout, result.stderr, end="")
        if result.returncode:
            break
    path = ROOT / "reports/evidence/checks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"timestamp_utc": datetime.now(UTC).isoformat(), "checks": records},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    if any(record["exit_code"] for record in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
