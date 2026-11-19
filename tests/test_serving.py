"""API tests build their own model/registry; no UCI or workstation assets required."""

import copy
import json
import logging
import os
import shutil

import mlflow.sklearn
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src import experiments, registry, serving
from src.config import ROOT, load_config
from src.pipeline import write_json
from src.serving import ServingSettings, create_app
from src.serving_bundle import export_bundle
from src.serving_contract import API_TO_MODEL, PredictResponse, example_request


def fingerprint(path):
    return {
        p.relative_to(path).as_posix(): experiments.sha256(p)
        for p in path.rglob("*")
        if p.is_file()
    }


@pytest.fixture(scope="module")
def serving_source(tmp_path_factory):
    root = tmp_path_factory.mktemp("serving-source")
    for name in ["uv.lock", "dvc.lock"]:
        shutil.copyfile(ROOT / name, root / name)
    shutil.copytree(ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
    write_json(root / "metadata/data_manifest.json", {"sha256": "synthetic"})
    config = load_config()
    record = example_request()["records"][0]
    rows = [{model: record[api] for api, model in API_TO_MODEL.items()} for _ in range(80)]
    for i, row in enumerate(rows):
        row.update(age=20 if i % 2 else 60, pdays=999 if i % 2 else 5, y="no" if i % 2 else "yes")
    train = pd.DataFrame(rows)
    validation = train.iloc[:20].copy()
    validation.index = range(80, 100)
    validation["age"] += 1
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(experiments, "ROOT", root)
        patch.setattr(registry, "ROOT", root)
        patch.setattr(
            experiments, "training_inputs", lambda cfg: (train, validation, {"sha256": "synthetic"})
        )
        summary = experiments.run_experiments(ROOT / "configs/experiments.yaml", config=config)
        batch = next((root / "artifacts/lesson5").iterdir())
        summary["provenance"]["git_sha"] = "a" * 40
        write_json(batch / "summary.json", summary)
        package = root / "package"
        digest = registry.package_existing(batch, "logistic", package, validation)
    return package, digest


@pytest.fixture
def service(tmp_path, serving_source):
    package, digest = serving_source
    store = registry.LocalRegistry(tmp_path / "registry")
    version = store.register(package, digest)
    store.challenger(version)
    item = store.client.get_model_version(store.name, version)
    evidence = tmp_path / "evidence.json"
    write_json(
        evidence,
        {
            "schema_version": 2,
            "paths_relative_to": "evidence_parent",
            "registry_directory": "registry",
            "model_name": store.name,
            "model_version": version,
            "packaging_run_id": item.run_id,
            "manifest_sha256": digest,
        },
    )
    return ServingSettings(evidence, alias="challenger"), store


def test_api_model_parity_and_registry_unchanged(service):
    settings, store = service
    before = fingerprint(store.directory)
    state = store.snapshot()
    direct = mlflow.sklearn.load_model(str(store.package_path("1") / "model"))
    body = example_request()
    frame = pd.DataFrame([{model: body["records"][0][api] for api, model in API_TO_MODEL.items()}])
    expected = direct.predict_proba(frame)[0, 1]
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/predict", json=body)
        assert response.status_code == 200
        parsed = PredictResponse.model_validate(response.json())
        assert parsed.predictions[0].probability_yes == expected
        assert parsed.predictions[0].class_label == ("yes" if expected >= 0.5 else "no")
        assert parsed.request_id == response.headers["X-Request-ID"]
        assert (parsed.model_name, parsed.model_version, parsed.mode) == (
            store.name,
            "1",
            "demonstration",
        )
        assert client.get("/health/live").json()["status"] == "alive"
        assert client.get("/health/ready").status_code == 200
        assert isinstance(client.app.state.loaded.model, type(direct))
        # Both calls execute the same serialized history/scaling/encoding pipeline.
        np.testing.assert_array_equal(
            client.app.state.loaded.model.predict_proba(frame), direct.predict_proba(frame)
        )
    assert store.snapshot() == state
    assert fingerprint(store.directory) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_years", "30"),
        ("age_years", 30.0),
        ("age_years", True),
        ("age_years", 0),
        ("age_years", 121),
        ("age_years", None),
        ("job", 42),
        ("job", "invalid"),
        ("marital_status", "invalid"),
        ("education", "invalid"),
        ("credit_default", "invalid"),
        ("housing_loan", "invalid"),
        ("personal_loan", "invalid"),
        ("days_since_previous_contact", -1),
        ("days_since_previous_contact", 1000),
        ("previous_contacts", -1),
        ("previous_contacts", False),
        ("previous_campaign_outcome", "invalid"),
    ],
)
def test_strict_record_validation(field, value):
    body = example_request()
    body["records"][0][field] = value
    with TestClient(create_app()) as client:
        response = client.post("/v1/predict", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "input" not in response.text and "Traceback" not in response.text


@pytest.mark.parametrize("field", list(API_TO_MODEL))
def test_each_field_required(field):
    body = example_request()
    del body["records"][0][field]
    with TestClient(create_app()) as client:
        assert client.post("/v1/predict", json=body).status_code == 422


@pytest.mark.parametrize("extra", ["duration", "target", "y", "extra"])
def test_forbidden_fields(extra):
    body = example_request()
    body["records"][0][extra] = 1
    with TestClient(create_app()) as client:
        assert client.post("/v1/predict", json=body).status_code == 422
        assert client.post("/v1/predict", json={**example_request(), extra: 1}).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"records": []},
        {"records": None},
        {"records": "bad"},
        {"records": example_request()["records"] * 101},
    ],
)
def test_request_envelope(body):
    with TestClient(create_app()) as client:
        assert client.post("/v1/predict", json=body).status_code == 422


@pytest.mark.parametrize("version", ["0", "invalid", "9999"])
def test_invalid_model_version(service, version):
    settings, store = service
    before = fingerprint(store.directory)
    with TestClient(create_app(ServingSettings(settings.evidence, version=version))) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        response = client.post("/v1/predict", json=example_request())
        assert response.status_code == 503
        assert str(settings.evidence) not in response.text
    assert fingerprint(store.directory) == before


def test_missing_model_and_malformed_json(tmp_path):
    path = tmp_path / "private-path/evidence.json"
    with TestClient(create_app(ServingSettings(path, version="1"))) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        response = client.post("/v1/predict", json=example_request())
        assert response.json()["error"] == "model_unavailable"
        assert "private-path" not in response.text
        assert (
            client.post(
                "/v1/predict", content="{", headers={"Content-Type": "application/json"}
            ).status_code
            == 422
        )


def test_load_once_and_alias_is_pinned(service, monkeypatch):
    settings, store = service
    calls = []
    real_load = serving.load_model
    monkeypatch.setattr(
        serving, "load_model", lambda config: (calls.append(config), real_load(config))[1]
    )
    with TestClient(create_app(settings)) as client:
        monkeypatch.setattr(
            registry.LocalRegistry, "load", lambda *args: pytest.fail("request reloaded model")
        )
        monkeypatch.setattr(
            registry.LocalRegistry, "resolve", lambda *args: pytest.fail("request resolved alias")
        )
        for _ in range(3):
            assert client.post("/v1/predict", json=example_request()).json()["model_version"] == "1"
    assert len(calls) == 1


def test_output_error_is_private(service, monkeypatch):
    settings, _ = service
    with TestClient(create_app(settings)) as client:

        def broken(frame):
            raise RuntimeError("D:/secret/private/model.db internal traceback")

        monkeypatch.setattr(client.app.state.loaded.model, "predict_proba", broken)
        response = client.post("/v1/predict", json=example_request())
        assert response.status_code == 500
        assert response.json()["error"] == "prediction_failed"
        assert "secret" not in response.text and "traceback" not in response.text


@pytest.mark.parametrize("scores", [[[float("nan"), 0.2]], [[0.5, 1.5]], [[0.2, 0.2]], [[0.5]]])
def test_invalid_probabilities_fail_closed(service, monkeypatch, scores):
    settings, _ = service
    with TestClient(create_app(settings)) as client:
        monkeypatch.setattr(client.app.state.loaded.model, "predict_proba", lambda frame: scores)
        assert client.post("/v1/predict", json=example_request()).status_code == 500


def test_schema_mismatch_not_ready(service, monkeypatch):
    settings, _ = service
    original = registry.LocalRegistry.metadata

    def wrong_schema(self, version):
        metadata = copy.deepcopy(original(self, version))
        metadata["schema"].pop("age")
        return metadata

    monkeypatch.setattr(registry.LocalRegistry, "metadata", wrong_schema)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 503


def test_safe_structured_logs_and_batch(service, caplog):
    settings, _ = service
    with caplog.at_level(logging.INFO, logger="bank_marketing.serving"):
        with TestClient(create_app(settings)) as client:
            body = {"records": example_request()["records"] * 100}
            response = client.post("/v1/predict", json=body)
            assert response.status_code == 200
            assert len(response.json()["predictions"]) == 100
    events = [json.loads(r.message) for r in caplog.records if r.name == "bank_marketing.serving"]
    assert events and events[-1]["request_id"] == response.json()["request_id"]
    assert not any(field in json.dumps(events) for field in API_TO_MODEL)


def test_openapi_snapshot_and_response_contract():
    schema = create_app().openapi()
    expected = json.loads((ROOT / "docs/api/openapi-v1.json").read_text(encoding="utf-8"))
    assert schema == expected
    assert schema["components"]["schemas"]["BankRecord"]["additionalProperties"] is False
    assert (
        schema["components"]["schemas"]["BankRecord"]["properties"]["age_years"]["type"]
        == "integer"
    )
    response = {
        "contract_version": "v1",
        "mode": "demonstration",
        "request_id": "synthetic",
        "model_name": "test",
        "model_version": "1",
        "decision_threshold": 0.5,
        "predictions": [{"class_label": "no", "probability_yes": 0.1}],
    }
    PredictResponse.model_validate(response)
    for required in response:
        broken = {k: v for k, v in response.items() if k != required}
        with pytest.raises(ValidationError):
            PredictResponse.model_validate(broken)


def test_portable_bundle_parity_and_no_registry_dependency(service, tmp_path):
    settings, store = service
    before = fingerprint(store.directory)
    destination = tmp_path / "bundle"
    digest = export_bundle(settings.evidence, "1", destination)
    assert fingerprint(store.directory) == before
    with TestClient(create_app(settings)) as client:
        expected = client.post("/v1/predict", json=example_request()).json()
    # Move the package to simulate a different machine or container mount.
    moved = tmp_path / "elsewhere"
    destination.rename(moved)
    with TestClient(create_app(ServingSettings(bundle=moved, receipt_sha256=digest))) as client:
        assert client.get("/health/ready").status_code == 200
        response = client.post("/v1/predict", json=example_request())
        assert response.status_code == 200
        assert response.json()["predictions"] == expected["predictions"]
        assert response.json()["model_version"] == "1"


@pytest.mark.parametrize("damage", ["anchor", "receipt", "model", "ml_bom", "selector"])
def test_portable_bundle_fails_closed(service, tmp_path, damage, monkeypatch):
    settings, _ = service
    destination = tmp_path / "bundle"
    digest = export_bundle(settings.evidence, "1", destination)
    if damage == "anchor":
        digest = "0" * 64
    elif damage == "receipt":
        (destination / "receipt.json").write_text("{}", encoding="utf-8")
    elif damage == "model":
        model = next(destination.rglob("*.skops"))
        model.write_bytes(b"corrupted")
    elif damage == "ml_bom":
        (destination / "ml-bom.json").write_text("{}", encoding="utf-8")
    else:
        settings = ServingSettings(
            evidence=settings.evidence, bundle=destination, receipt_sha256=digest
        )
    if damage != "selector":
        settings = ServingSettings(bundle=destination, receipt_sha256=digest)

    # Verification must reject corrupt inputs before the deserializer runs.
    def forbidden(*args, **kwargs):
        pytest.fail("Unverified model reached deserialization")

    monkeypatch.setattr(mlflow.sklearn, "load_model", forbidden)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert client.post("/v1/predict", json=example_request()).status_code == 503


def test_bundle_environment_requires_exclusive_source(monkeypatch, tmp_path):
    for name in tuple(os.environ):
        if name.startswith("BANK_MARKETING_SERVING_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("BANK_MARKETING_SERVING_BUNDLE", str(tmp_path))
    monkeypatch.setenv("BANK_MARKETING_SERVING_RECEIPT_SHA256", "a" * 64)
    assert ServingSettings.from_environment().bundle == tmp_path
    monkeypatch.setenv("BANK_MARKETING_SERVING_EVIDENCE", "evidence.json")
    with pytest.raises(ValueError, match="Choose"):
        ServingSettings.from_environment()


@pytest.mark.skipif(
    not os.environ.get("BANK_MARKETING_TEST_IMAGE"), reason="Explicit Docker image required"
)
def test_container_http(service, tmp_path):
    from scripts.container_smoke import check_image

    settings, _ = service
    destination = tmp_path / "bundle"
    digest = export_bundle(settings.evidence, "1", destination)
    image = os.environ["BANK_MARKETING_TEST_IMAGE"]
    assert check_image(image)["status"] == "PASS"
    assert check_image(image, destination, digest)["status"] == "PASS"
