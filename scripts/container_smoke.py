"""Exercise a built API image, always removing only this test's container."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from src.serving_contract import PredictResponse, example_request


def check_image(image: str, bundle: Path | None = None, receipt_hash: str | None = None) -> dict:
    """Check HTTP readiness/prediction and non-root identity with a read-only mount."""
    name = "bank-marketing-smoke-" + uuid4().hex
    command = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=134217728,mode=1777",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--publish",
        "127.0.0.1::8000",
    ]
    if bundle is not None:
        if not bundle.is_dir() or not receipt_hash:
            raise ValueError("An existing bundle and external receipt hash are required")
        command += [
            "--mount",
            f"type=bind,source={bundle.resolve()},target=/model,readonly",
            "--env",
            "BANK_MARKETING_SERVING_BUNDLE=/model",
            "--env",
            f"BANK_MARKETING_SERVING_RECEIPT_SHA256={receipt_hash}",
        ]
    command.append(image)

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            base + path, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
        binding = subprocess.check_output(
            ["docker", "port", name, "8000/tcp"], text=True, timeout=15
        ).strip()
        base = "http://" + binding
        deadline = time.monotonic() + 90
        while True:
            try:
                if request("/health/live")[0] == 200:
                    break
            except (OSError, ValueError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("Container did not become live within 90 seconds")
            time.sleep(0.5)
        expected = 200 if bundle is not None else 503
        if request("/health/ready")[0] != expected:
            raise RuntimeError("Incorrect container readiness")
        status, payload = request("/v1/predict", example_request())
        if status != expected:
            raise RuntimeError("Incorrect prediction status")
        if bundle is not None:
            PredictResponse.model_validate(payload)
        elif payload["error"] != "model_unavailable":
            raise RuntimeError("Missing model was not reported")
        user = subprocess.check_output(
            ["docker", "inspect", "--format", "{{.Config.User}}", name],
            text=True,
            timeout=15,
        ).strip()
        if user != "10001:10001":
            raise RuntimeError("Unexpected container runtime user")
        subprocess.run(
            [
                "docker",
                "exec",
                name,
                "python",
                "-c",
                "import importlib.util, shutil; "
                "assert importlib.util.find_spec('diskcache') is None; "
                "assert importlib.util.find_spec('dvc') is None; "
                "assert shutil.which('mount') is None; "
                "assert shutil.which('umount') is None",
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return {
            "status": "PASS",
            "with_model": bundle is not None,
            "runtime_user": user,
            "development_tools_present": False,
            "mount_tools_present": False,
        }
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)


def main() -> None:
    """Test the missing-model case or a pinned bundle without rebuilding an image."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--receipt-sha256")
    args = parser.parse_args()
    print(json.dumps(check_image(args.image, args.bundle, args.receipt_sha256)))


if __name__ == "__main__":
    main()
