"""Exercise release denial and mutations of the actual checked-in workflow."""

import copy

import pytest

from scripts.verify_ci_policy import (
    REQUIRED_JOBS,
    ROOT,
    publication_allowed,
    read_yaml,
    validate_policy,
)


def documents():
    return (
        read_yaml(ROOT / ".github/workflows/ci.yml"),
        read_yaml(ROOT / ".github/actions/check-image/action.yml"),
    )


def successful_results():
    return dict.fromkeys(REQUIRED_JOBS, "success")


def test_checked_in_workflow_preserves_publication_contract():
    validate_policy(*documents())
    assert publication_allowed("workflow_dispatch", "refs/heads/main", True, successful_results())


@pytest.mark.parametrize("gate", REQUIRED_JOBS)
@pytest.mark.parametrize("status", ["failure", "cancelled", "skipped", None])
def test_each_unsuccessful_or_missing_gate_blocks_release(gate, status):
    results = successful_results()
    if status is None:
        del results[gate]
    else:
        results[gate] = status
    assert not publication_allowed("workflow_dispatch", "refs/heads/main", True, results)


@pytest.mark.parametrize(
    "event,ref,requested",
    [
        ("push", "refs/heads/main", True),
        ("pull_request", "refs/heads/main", True),
        ("workflow_run", "refs/heads/main", True),
        ("workflow_dispatch", "refs/heads/feature", True),
        ("workflow_dispatch", "refs/tags/main", True),
        ("workflow_dispatch", "refs/heads/main", False),
        ("workflow_dispatch", "refs/heads/main", "false"),
    ],
)
def test_release_requires_manual_main_branch_opt_in(event, ref, requested):
    assert not publication_allowed(event, ref, requested, successful_results())


@pytest.mark.parametrize("gate", REQUIRED_JOBS)
def test_removing_a_gate_from_publish_dependencies_is_rejected(gate):
    workflow, action = documents()
    workflow["jobs"]["publish"]["needs"].remove(gate)
    with pytest.raises(ValueError, match="omits"):
        validate_policy(workflow, action)


@pytest.mark.parametrize(
    "mutation",
    [
        "condition",
        "mask_errors",
        "skip_dev",
        "disable_image_scan",
        "unfixed",
        "threshold",
        "archive_upload",
        "early_publish",
        "runtime_profile",
        "candidate_rescan",
        "push_after_failure",
        "zero_scan_exit",
        "wrong_scan_image",
        "wrong_sbom_image",
        "masked_audit",
        "history_zero_exit",
    ],
)
def test_unsafe_configuration_changes_are_rejected(mutation):
    workflow, action = copy.deepcopy(documents())
    if mutation == "condition":
        workflow["jobs"]["publish"]["if"] = "${{ always() }}"
    elif mutation == "mask_errors":
        workflow["jobs"]["security_dev"]["continue-on-error"] = "true"
    elif mutation == "skip_dev":
        step = next(
            s
            for s in workflow["jobs"]["security_dev"]["steps"]
            if "pip-audit --strict" in s.get("run", "")
        )
        step["if"] = "false"
    elif mutation == "disable_image_scan":
        workflow["jobs"]["security_image"]["steps"][-1]["with"]["scan-security"] = "false"
    elif mutation in {"unfixed", "threshold"}:
        step = next(
            s for s in action["runs"]["steps"] if s.get("uses", "").startswith("aquasecurity/")
        )
        step["with"]["ignore-unfixed" if mutation == "unfixed" else "severity"] = (
            "true" if mutation == "unfixed" else "CRITICAL"
        )
    elif mutation == "archive_upload":
        action["runs"]["steps"][-1]["with"]["path"] += "\nimage.oci.tar"
    elif mutation == "early_publish":
        action["runs"]["steps"].append({"run": "docker push unverified:latest"})
    elif mutation == "candidate_rescan":
        workflow["jobs"]["publish"]["steps"][1]["with"]["scan-security"] = "false"
    elif mutation == "push_after_failure":
        step = next(
            s for s in workflow["jobs"]["publish"]["steps"] if "docker push" in s.get("run", "")
        )
        step["if"] = "${{ always() }}"
    elif mutation == "zero_scan_exit":
        step = next(
            s for s in action["runs"]["steps"] if s.get("uses", "").startswith("aquasecurity/")
        )
        step["with"]["exit-code"] = "0"
    elif mutation == "wrong_scan_image":
        step = next(
            s for s in action["runs"]["steps"] if s.get("uses", "").startswith("aquasecurity/")
        )
        step["with"]["image-ref"] = "unrelated:latest"
    elif mutation == "wrong_sbom_image":
        step = next(s for s in action["runs"]["steps"] if s.get("uses", "").startswith("anchore/"))
        step["with"]["image"] = "unrelated:latest"
    elif mutation == "masked_audit":
        step = next(
            s
            for s in workflow["jobs"]["security_dev"]["steps"]
            if "pip-audit --strict" in s.get("run", "")
        )
        step["run"] = "if " + step["run"] + "; then echo done; else echo done; fi"
    elif mutation == "history_zero_exit":
        step = next(
            s
            for s in workflow["jobs"]["security_history"]["steps"]
            if "gitleaks" in s.get("run", "")
        )
        step["run"] += " --exit-code 0"
    else:
        step = next(
            s
            for s in workflow["jobs"]["security_runtime"]["steps"]
            if "uv export" in s.get("run", "")
        )
        step["run"] = step["run"].replace("--no-dev", "--all-groups")
    with pytest.raises(ValueError):
        validate_policy(workflow, action)


@pytest.mark.parametrize(
    "mutation",
    [
        "implicit_local_tag",
        "registry",
        "wrong_archive",
        "file_autodetection",
        "wrong_export",
        "wrong_report",
        "missing_binding",
        "skipped_binding",
        "wrong_binding_digest",
        "wrong_binding_archive",
        "binding_before_scan",
        "unverified_archive",
        "syft_version",
        "registry_credentials",
    ],
)
def test_sbom_must_use_verified_oci_bytes_and_block_on_bad_reports(mutation):
    workflow, action = copy.deepcopy(documents())
    steps = action["runs"]["steps"]
    syft = next(s for s in steps if s.get("id") == "syft")
    verifier = next(s for s in steps if s.get("id") == "verify_image")
    binding = next(s for s in steps if "--cyclonedx" in s.get("run", ""))
    if mutation == "implicit_local_tag":
        syft["with"]["image"] = "bank-marketing-api:ci"
    elif mutation == "registry":
        syft["with"]["image"] = "registry:bank-marketing-api:ci"
    elif mutation == "wrong_archive":
        syft["with"]["image"] = "oci-archive:/other/image.tar"
    elif mutation == "file_autodetection":
        syft["with"]["file"] = syft["with"].pop("image")
    elif mutation == "wrong_export":
        verifier["run"] = verifier["run"].replace("image.oci.tar", "other.oci.tar")
    elif mutation == "wrong_report":
        syft["with"]["output-file"] = "other.cdx.json"
    elif mutation == "missing_binding":
        steps.remove(binding)
    elif mutation == "skipped_binding":
        binding["if"] = "false"
    elif mutation == "wrong_binding_digest":
        binding["env"]["EXPECTED_IMAGE_DIGEST"] = "untrusted"
    elif mutation == "wrong_binding_archive":
        binding["run"] = binding["run"].replace("image.oci.tar", "other.oci.tar")
    elif mutation == "binding_before_scan":
        steps.remove(binding)
        steps.insert(steps.index(syft), binding)
    elif mutation == "unverified_archive":
        syft["if"] = syft["if"].replace(" && steps.verify_image.outcome == 'success'", "")
    elif mutation == "syft_version":
        syft["with"]["syft-version"] = "latest"
    elif mutation == "registry_credentials":
        syft["with"]["registry-username"] = "unexpected"
    with pytest.raises(ValueError):
        validate_policy(workflow, action)
