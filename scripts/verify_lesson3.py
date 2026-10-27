"""Verify lesson 3 in a disposable workspace, preserving existing project data.

Run with uv run --locked python -m scripts.verify_lesson3.
Only the explicit --download option contacts UCI. No remote storage is contacted.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.config import ROOT, load_config
from src.data.download import verify_manifest
from src.data.validation import validate_dataframe


def digest(path: Path) -> str:
    """Return the SHA-256 of a local file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files() -> dict[str, str]:
    """Fingerprint existing data and baseline outputs without evaluating holdouts."""
    files = [
        ROOT / ".git/index",
        ROOT / ".dvc/config",
        ROOT / "metadata/data_manifest.json",
        ROOT / "metadata/bank-additional-full.csv.dvc",
        ROOT / "notebooks/01_bank_marketing_eda.ipynb",
    ]
    for directory in [
        "data",
        "artifacts/models",
        "artifacts/reports",
        "private_notes",
        "reports/evidence",
    ]:
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in files}


def sanitize_output(value: str) -> str:
    """Redact local paths, including paths returned by external tools on failure."""
    for path, marker in [(ROOT, "PROJECT_ROOT"), (Path.home(), "USER_HOME")]:
        for spelling in [str(path), path.as_posix(), str(path).replace("\\", "\\\\")]:
            value = re.sub(re.escape(spelling), marker, value, flags=re.IGNORECASE)
    value = re.sub(r"(?i)\b[A-Z]:[\\/]+[^\r\n\"'<>|;]*", "LOCAL_PATH", value)
    value = re.sub(r"\\\\[^\\/\s]+[\\/][^\r\n\"'<>|;]*", "LOCAL_PATH", value)
    return re.sub(r"(?<![\w:/\\])/(?!/)[^\r\n\"'<>|;,\])]*", "LOCAL_PATH", value)


def sanitize_payload(value):
    """Sanitize every report string at the serialization boundary."""
    if isinstance(value, str):
        return sanitize_output(value)
    if isinstance(value, dict):
        return {sanitize_output(str(key)): sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def write_evidence(
    evidence: dict,
    before: dict[str, str],
    *,
    checks_complete: bool,
    download_requested: bool,
    output_dir: Path,
) -> Path:
    """Determine final status after integrity checks and exclusively create a report."""
    try:
        unchanged = all(
            (ROOT / path).is_file() and digest(ROOT / path) == checksum
            for path, checksum in before.items()
        )
    except OSError:
        unchanged = False
    evidence["existing_files_unchanged"] = unchanged
    if not unchanged:
        evidence["error"] = "Protected project files changed or could not be verified"
    if not checks_complete or evidence.get("error") or not unchanged:
        evidence["status"] = "FAIL"
    else:
        evidence["status"] = "PASS" if download_requested else "INCOMPLETE_UCI_NOT_RUN"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"lesson3-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid4().hex}.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(sanitize_payload(evidence), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return output


def main() -> None:
    """Record real validation, corruption rejection and local-cache recovery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Also recover from UCI HTTPS")
    args = parser.parse_args()
    config = load_config()
    raw = ROOT / config["data"]["raw"]
    manifest_path = ROOT / config["data"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = protected_files()
    evidence = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "remote_required": False,
        "holdouts_used_for_model_selection": False,
        "training_executed": False,
        "steps": [],
    }
    base = ROOT / "artifacts/lesson3"
    base.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="verification-", dir=base))
    checks_complete = False

    def run(*arguments: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "dvc", *arguments],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "DVC_NO_ANALYTICS": "1"},
        )
        evidence["steps"].append(
            {
                "command": ["python", "-m", "dvc", *arguments],
                "exit_code": result.returncode,
                "stdout": sanitize_output(result.stdout),
                "stderr": sanitize_output(result.stderr),
            }
        )
        if result.returncode:
            raise RuntimeError(sanitize_output(result.stderr))

    try:
        if args.download:
            uci = Path(tempfile.mkdtemp(prefix="uci-", dir=base)).resolve()
            assert not list(uci.iterdir())
            # Copy only the stdlib downloader and manifest, never data or DVC cache.
            shutil.copyfile(ROOT / "src/data/download.py", uci / "download.py")
            shutil.copyfile(manifest_path, uci / "manifest.json")
            code = textwrap.dedent("""
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path.cwd()))
                blocked = [Path(arg).resolve() for arg in sys.argv[1:]]
                def guard(event, args):
                    if event in {'open', 'os.listdir', 'os.scandir'} and args:
                        if isinstance(args[0], (str, bytes)):
                            path = Path(__import__('os').fsdecode(args[0])).resolve()
                            if any(path == p or p in path.parents for p in blocked):
                                raise PermissionError('Original data/cache access forbidden')
                sys.addaudithook(guard)
                for path in blocked:
                    try:
                        list(path.iterdir())
                    except PermissionError:
                        pass
                    else:
                        raise AssertionError('Access guard inactive')
                from download import ensure_data
                ensure_data(Path('raw.csv'), Path('manifest.json'))
            """)
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    code,
                    str(ROOT / "data"),
                    str(ROOT / ".dvc/cache"),
                ],
                cwd=uci,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(sanitize_output(result.stderr))
            verify_manifest(uci / "raw.csv", manifest)
            evidence["uci_contract"] = validate_dataframe(pd.read_csv(uci / "raw.csv", sep=";"))
            evidence["uci_download_without_local_csv_or_cache_verified"] = True
            evidence["original_data_and_cache_access_blocked"] = True
        else:
            evidence["uci_download_without_local_csv_or_cache_verified"] = None
        verify_manifest(raw, manifest)
        evidence["manifest_verified"] = True
        evidence["sha256"] = digest(raw)
        evidence["size_bytes"] = raw.stat().st_size
        evidence["contract"] = validate_dataframe(pd.read_csv(raw, sep=";"))
        corrupt = workspace / "corrupt.csv"
        shutil.copyfile(raw, corrupt)
        with corrupt.open("r+b") as stream:
            stream.write(b"!")
        try:
            verify_manifest(corrupt, manifest)
        except ValueError:
            evidence["corrupted_copy_rejected"] = True
        else:
            raise AssertionError("Corrupted CSV accepted")
        frame = pd.read_csv(raw, sep=";")
        frame.loc[0, "job"] = "invalid-category"
        try:
            validate_dataframe(frame)
        except ValueError:
            evidence["invalid_category_rejected"] = True
        else:
            raise AssertionError("Invalid category accepted")

        # No Git repository or index exists in this disposable DVC workspace.
        dvc_dir = workspace / ".dvc"
        dvc_dir.mkdir()
        (dvc_dir / "config").write_text(
            "[core]\n    no_scm = true\n    analytics = false\n"
            "    check_update = false\n    autostage = false\n[cache]\n    type = copy\n",
            encoding="utf-8",
        )
        pointer = Path("metadata/bank-additional-full.csv.dvc")
        (workspace / pointer).parent.mkdir(parents=True)
        shutil.copyfile(ROOT / pointer, workspace / pointer)
        shutil.copytree(ROOT / ".dvc/cache", dvc_dir / "cache")
        recovered = workspace / config["data"]["raw"]
        assert not recovered.exists()
        run("checkout", pointer.as_posix())
        verify_manifest(recovered, manifest)
        evidence["local_cache_checkout_verified"] = True
        run("status")
        evidence["local_dvc_contract"] = validate_dataframe(pd.read_csv(recovered, sep=";"))
        checks_complete = True
    except Exception as error:
        evidence["error"] = sanitize_output(f"{type(error).__name__}: {error}")
    finally:
        output = write_evidence(
            evidence,
            before,
            checks_complete=checks_complete,
            download_requested=args.download,
            output_dir=ROOT / "reports/evidence",
        )
        print(output.name, evidence["status"])
    if evidence["status"] == "FAIL":
        raise RuntimeError(evidence.get("error", "Verification did not complete"))


def cli() -> None:
    """Keep raw exception tracebacks and setup paths out of terminal output."""
    try:
        main()
    except KeyboardInterrupt:
        print("Verification interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as error:
        print(sanitize_output(f"{type(error).__name__}: {error}"), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    cli()
