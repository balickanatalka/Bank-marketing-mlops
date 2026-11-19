"""Validate the checked-in CI publication contract without executing a release."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_JOBS = (
    "functional_checks",
    "functional_image",
    "security_dev",
    "security_runtime",
    "security_history",
    "security_image",
)
PUBLISH_CONDITION = (
    "${{ github.event_name == 'workflow_dispatch' && inputs.publish "
    "&& github.ref == 'refs/heads/main' && "
    + " && ".join(f"needs.{job}.result == 'success'" for job in REQUIRED_JOBS)
    + " }}"
)
SCAN_CONDITION = (
    "${{ always() && inputs.scan-security == 'true' && steps.build.outcome == 'success' }}"
)
IMAGE_ACTION = "./.github/actions/check-image"


def publication_allowed(event: str, ref: str, requested: bool, results: dict) -> bool:
    """Model the exact workflow condition; missing/cancelled/skipped gates deny release."""
    return (
        event == "workflow_dispatch"
        and ref == "refs/heads/main"
        and requested is True
        and all(results.get(job) == "success" for job in REQUIRED_JOBS)
    )


def read_yaml(path: Path) -> dict:
    """Preserve GitHub's `on` key and normalize scalar types for policy checks."""
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def require(condition, message: str) -> None:
    if not condition:
        raise ValueError(message)


def normalize(value: str) -> str:
    return " ".join(value.split())


def check_no_bypasses(value) -> None:
    if isinstance(value, dict):
        require("continue-on-error" not in value, "Error masking is forbidden")
        for key, child in value.items():
            if key == "run":
                require(
                    not re.search(
                        r"\|\|\s*(true|:)|set\s+\+e|--ignore-vuln|--ignore-unfixed", child
                    ),
                    "Scanner errors or findings must not be masked",
                )
            check_no_bypasses(child)
    elif isinstance(value, list):
        for child in value:
            check_no_bypasses(child)


def image_step(job: dict) -> dict:
    steps = [s for s in job["steps"] if s.get("uses") == IMAGE_ACTION]
    require(len(steps) == 1, "Expected exactly one checked image candidate")
    return steps[0]


def validate_policy(workflow: dict, action: dict) -> None:
    """Fail closed when the workflow weakens gates or exports an unapproved image.

    This checks the repository's concrete configuration contract. It is a local
    regression guard, not an evaluation of GitHub's remote runner or arbitrary code.
    """
    check_no_bypasses(workflow)
    check_no_bypasses(action)
    jobs = workflow["jobs"]
    require(set(jobs) == {*REQUIRED_JOBS, "publish"}, "Unexpected CI gate set")
    require(set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}, "Unsafe trigger")
    switch = workflow["on"]["workflow_dispatch"]["inputs"]["publish"]
    require(switch["type"] == "boolean" and switch["default"] == "false", "Publish must be opt-in")
    require(workflow["permissions"] == {"contents": "read"}, "Default token must be read-only")
    publish = jobs["publish"]
    require(set(publish["needs"]) == set(REQUIRED_JOBS), "Publication omits a required gate")
    require(normalize(publish["if"]) == PUBLISH_CONDITION, "Publication condition weakened")
    require(
        publish["permissions"] == {"contents": "read", "packages": "write"},
        "Unexpected publication permissions",
    )
    for name, job in jobs.items():
        if name != "publish":
            require("permissions" not in job, "Only publish may request a writable token")
            require("if" not in job, "Required checks must not be conditionally skipped")
        if name.startswith("security_") or name == "functional_checks":
            require("needs" not in job, "Audit and functional checks must run independently")
        for step in job["steps"]:
            command = step.get("run", "")
            require(step.get("with", {}).get("push") != "true", "Ungated registry push action")
            if "docker push" in command or "docker/login-action@" in step.get("uses", ""):
                require(name == "publish", "Registry publication escaped the gated job")
            if name == "publish":
                require("if" not in step, "Publication steps must retain default success gating")
    require(
        jobs["functional_image"]["needs"] == ["functional_checks"],
        "Functional image is coupled to security",
    )
    for name, mode in [
        ("functional_image", "false"),
        ("security_image", "true"),
        ("publish", "true"),
    ]:
        require(
            image_step(jobs[name])["with"]["scan-security"] == mode, "Incorrect candidate scan mode"
        )

    for name, export_flag, other_flag in [
        ("security_dev", "--all-groups", "--no-dev"),
        ("security_runtime", "--no-dev", "--all-groups"),
    ]:
        steps = jobs[name]["steps"]
        exports = [s for s in steps if "uv export" in s.get("run", "")]
        audits = [s for s in steps if "pip-audit --strict" in s.get("run", "")]
        require(len(exports) == len(audits) == 1, "Missing dependency export or strict audit")
        require("if" not in exports[0] and "if" not in audits[0], "Audit may not be skipped")
        require(
            export_flag in exports[0]["run"] and other_flag not in exports[0]["run"],
            "Wrong dependency profile",
        )
        require("--locked" in exports[0]["run"], "Dependency export must use the lock")
        require("--output" in audits[0]["run"], "Raw dependency audit must be retained")
        directory = "artifacts/ci/" + name.replace("_", "-")
        expected_audit = (
            "uvx --from pip-audit==2.10.1 pip-audit --strict --disable-pip --no-deps "
            f"-r {directory}/requirements.txt --format json --output {directory}/pip-audit.json"
        )
        require(
            normalize(audits[0]["run"]) == expected_audit, "Audit result must propagate directly"
        )
    history = jobs["security_history"]["steps"]
    require(history[0]["with"]["fetch-depth"] == "0", "History scan requires full checkout")
    scans = [s for s in history if "gitleaks" in s.get("run", "")]
    require(len(scans) == 1 and "if" not in scans[0], "Missing unconditional history scan")
    require(
        "--log-opts=--all" in scans[0]["run"] and "--redact=100" in scans[0]["run"],
        "History scope weakened",
    )
    require(
        "--exit-code" not in scans[0]["run"] and "||" not in scans[0]["run"],
        "History scan must retain its default failure status",
    )

    steps = action["runs"]["steps"]
    require(action["runs"]["using"] == "composite", "Expected a local image-check action")
    require(action["inputs"]["scan-security"]["default"] == "true", "Secure default required")
    build = next(s for s in steps if s.get("id") == "build")
    require("if" not in build, "Build may not be skipped")
    for key, expected in {
        "push": "false",
        "load": "true",
        "sbom": "true",
        "provenance": "mode=min",
        "tags": "bank-marketing-api:ci",
    }.items():
        require(build["with"].get(key) == expected, "Candidate build/export contract weakened")
    verifier = next(s for s in steps if "scripts.verify_image_evidence" in s.get("run", ""))
    http = next(s for s in steps if "pytest tests/test_serving.py" in s.get("run", ""))
    require("if" not in verifier and "if" not in http, "Candidate verification may not be skipped")
    require(
        verifier["env"]["EXPECTED_IMAGE_DIGEST"] == "${{ steps.build.outputs.digest }}"
        and "docker image save bank-marketing-api:ci" in verifier["run"],
        "Attestation verification must use the built image",
    )
    require(
        http["env"]["BANK_MARKETING_TEST_IMAGE"] == "bank-marketing-api:ci",
        "Wrong HTTP candidate",
    )
    trivy = next(s for s in steps if s.get("uses", "").startswith("aquasecurity/trivy-action@"))
    require(normalize(trivy["if"]) == SCAN_CONDITION, "Image scan condition weakened")
    for key, expected in {
        "severity": "HIGH,CRITICAL",
        "exit-code": "1",
        "ignore-unfixed": "false",
        "scanners": "vuln",
        "image-ref": "bank-marketing-api:ci",
    }.items():
        require(trivy["with"].get(key) == expected, "Image vulnerability policy weakened")
    syft = next(s for s in steps if s.get("uses", "").startswith("anchore/sbom-action@"))
    require(normalize(syft["if"]) == SCAN_CONDITION, "SBOM generation may not be skipped")
    require(
        syft["with"]["upload-release-assets"] == "false", "Candidate SBOM must not create a release"
    )
    require(syft["with"]["image"] == "bank-marketing-api:ci", "Wrong SBOM candidate")
    uploads = [s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@")]
    require(len(uploads) == 1, "Expected one reports-only upload")
    require(
        normalize(uploads[0]["if"]) == "${{ always() && steps.configure.outcome == 'success' }}",
        "Report paths must be validated before upload",
    )
    require(
        uploads[0]["with"]["path"].splitlines()
        == [
            f"artifacts/ci/${{{{ inputs.artifact-name }}}}/*.{ext}"
            for ext in ["json", "xml", "txt"]
        ],
        "Unapproved image archive upload",
    )
    require(
        not any("docker push" in s.get("run", "") for s in steps), "Image action may never publish"
    )

    candidate = image_step(publish)
    require(candidate.get("id") == "candidate", "Publication must use the checked candidate")
    login = next(
        s for s in publish["steps"] if s.get("uses", "").startswith("docker/login-action@")
    )
    push = next(s for s in publish["steps"] if "docker push" in s.get("run", ""))
    require(
        publish["steps"].index(candidate)
        < publish["steps"].index(login)
        < publish["steps"].index(push),
        "Credentials precede verification",
    )
    require(
        push["env"]["EXPECTED_IMAGE_DIGEST"] == "${{ steps.candidate.outputs.digest }}",
        "Wrong candidate digest",
    )
    require(
        "test " in push["run"] and ".Descriptor.digest" in push["run"],
        "Missing identity assertion before push",
    )
    require("docker build" not in push["run"], "Publication may not rebuild the tested candidate")


def main() -> None:
    """Check local YAML and print PASS only when the publication contract is intact."""
    validate_policy(
        read_yaml(ROOT / ".github/workflows/ci.yml"),
        read_yaml(ROOT / ".github/actions/check-image/action.yml"),
    )
    print(json.dumps({"status": "PASS", "required_publication_gates": REQUIRED_JOBS}))


if __name__ == "__main__":
    main()
