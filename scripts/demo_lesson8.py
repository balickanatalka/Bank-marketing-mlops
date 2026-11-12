"""Run a real localhost HTTP demonstration without training or registry writes."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import numpy as np

from src.config import ROOT
from src.experiments import sha256
from src.registry import read_json
from src.serving_contract import PredictResponse, example_request


def fingerprint(directory: Path) -> dict:
    """Compare identities and bytes of the entire evidence/package/registry tree."""
    return {
        p.relative_to(directory).as_posix(): sha256(p) for p in directory.rglob("*") if p.is_file()
    }


@contextmanager
def running_service(
    evidence: Path, output: Path, *, version: str | None = None, alias: str | None = "challenger"
):
    """Start a local child process and always stop it, including on client failure."""
    output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith("BANK_MARKETING_SERVING_")
    }
    environment.update(
        BANK_MARKETING_SERVING_EVIDENCE=str(evidence.resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        MLFLOW_ENABLE_TELEMETRY="false",
        MLFLOW_DISABLE_AGENT_HINT="1",
    )
    if version is not None:
        environment["BANK_MARKETING_SERVING_VERSION"] = version
    elif alias is not None:
        environment["BANK_MARKETING_SERVING_ALIAS"] = alias
    command = [
        sys.executable,
        "-B",
        "-m",
        "uvicorn",
        "src.serving:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
        "--log-config",
        str(ROOT / "configs/serving-logging.json"),
    ]
    with (
        (output / "server.stdout.log").open("xb") as stdout,
        (output / "server.stderr.log").open("xb") as stderr,
    ):
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False
            ) as client:
                for _ in range(300):
                    if process.poll() is not None:
                        raise RuntimeError("Local API exited; inspect server logs")
                    try:
                        if client.get("/health/live").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.2)
                else:
                    raise TimeoutError("Local API startup timed out")
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
            (output / "process.json").write_text(
                json.dumps(
                    {
                        "started": True,
                        "stopped": process.poll() is not None,
                        "exit_code": process.returncode,
                        "host": "127.0.0.1",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )


def demonstrate(evidence: Path, output: Path, *, version: str | None = None) -> dict:
    """Record real responses, contract validation, latency and unchanged registry."""
    evidence = evidence.resolve()
    read_json(evidence)
    before = fingerprint(evidence.parent)
    with running_service(evidence, output, version=version) as client:
        live, ready = client.get("/health/live"), client.get("/health/ready")
        assert live.status_code == ready.status_code == 200
        body = example_request()
        response = client.post("/v1/predict", json=body)
        assert response.status_code == 200
        PredictResponse.model_validate(response.json())
        invalid = {"records": [{**body["records"][0], "duration": 42}]}
        rejected = client.post("/v1/predict", json=invalid)
        assert rejected.status_code == 422
        measurements = {}
        for size in (1, 50):
            durations = []
            for _ in range(30):
                started = time.perf_counter()
                measured = client.post("/v1/predict", json={"records": body["records"] * size})
                durations.append((time.perf_counter() - started) * 1000)
                assert measured.status_code == 200
                PredictResponse.model_validate(measured.json())
            measurements[str(size)] = {
                "requests": len(durations),
                "records_per_request": size,
                "p50_ms": float(np.percentile(durations, 50)),
                "p95_ms": float(np.percentile(durations, 95)),
                "p99_ms": float(np.percentile(durations, 99)),
                "median_ms_per_record": float(np.median(durations) / size),
            }
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        expected = read_json(ROOT / "docs/api/openapi-v1.json")
        assert openapi.json() == expected
        result = {
            "status": "PASS",
            "transport": "real localhost HTTP",
            "mode": "demonstration",
            "live_status": live.status_code,
            "ready_status": ready.status_code,
            "valid_status": response.status_code,
            "invalid_status": rejected.status_code,
            "synthetic_request": body,
            "response": response.json(),
            "invalid_response": rejected.json(),
            "latency": measurements,
            "latency_scope": "30 warmed requests per size; no load/SLO claim",
            "registry_unchanged": False,
        }
    assert fingerprint(evidence.parent) == before
    result["registry_unchanged"] = True
    result["server_stopped"] = read_json(output / "process.json")["stopped"]
    (output / "evidence.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    return result


def main() -> None:
    """Require explicit lesson-7 evidence; never discover a workstation registry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version")
    args = parser.parse_args()
    result = demonstrate(args.evidence, args.output, version=args.version)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
