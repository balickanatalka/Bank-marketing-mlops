"""Local demonstration API over an integrity-checked lesson-7 model package."""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sklearn.pipeline import Pipeline

from src.registry import LocalRegistry, input_schema, validate_input
from src.serving_contract import (
    API_TO_MODEL,
    ErrorResponse,
    HealthResponse,
    Prediction,
    PredictRequest,
    PredictResponse,
)

LOGGER = logging.getLogger("bank_marketing.serving")


@dataclass(frozen=True)
class ServingSettings:
    """An explicit evidence file and exactly one version or challenger selector."""

    evidence: Path
    version: str | None = None
    alias: str | None = None

    @classmethod
    def from_environment(cls):
        """Read configuration at startup; a fresh clone has no default registry."""
        evidence = os.environ.get("BANK_MARKETING_SERVING_EVIDENCE")
        if not evidence:
            raise ValueError("Explicit serving evidence is required")
        return cls(
            Path(evidence),
            os.environ.get("BANK_MARKETING_SERVING_VERSION"),
            os.environ.get("BANK_MARKETING_SERVING_ALIAS"),
        )


@dataclass(frozen=True)
class LoadedModel:
    """Keep the verified complete pipeline in memory; never reload per request."""

    model: Pipeline
    name: str
    version: str
    threshold: float
    schema: dict


def load_model(settings: ServingSettings) -> LoadedModel:
    """Reuse lesson-7 integrity, lineage and quality gates without alias writes."""
    if (settings.version is None) == (settings.alias is None):
        raise ValueError("Choose exactly one model selector")
    if settings.alias is not None and settings.alias != "challenger":
        raise ValueError("Only the demonstration challenger alias is supported")
    if settings.version is not None and (
        not settings.version.isdecimal() or int(settings.version) < 1
    ):
        raise ValueError("Model version must be positive")
    store = LocalRegistry.from_evidence(settings.evidence)
    version = settings.version or store.resolve(settings.alias)
    metadata = store.metadata(version)
    expected = input_schema(list(API_TO_MODEL.values()))
    if list(metadata["schema"].items()) != list(expected.items()):
        raise ValueError("Model does not implement the v1 feature contract")
    store.check(version)
    model = store.load(version)
    if not isinstance(model, Pipeline) or list(model.classes_) != [0, 1]:
        raise ValueError("A complete binary pipeline is required")
    return LoadedModel(
        model, store.name, version, metadata["parameters"]["decision_threshold"], expected
    )


def score(loaded: LoadedModel, request: PredictRequest) -> list[Prediction]:
    """Map the API contract, then call the unchanged fitted preprocessing pipeline."""
    frame = pd.DataFrame.from_records(
        [
            {model: getattr(record, api) for api, model in API_TO_MODEL.items()}
            for record in request.records
        ],
        columns=list(API_TO_MODEL.values()),
    )
    validate_input(frame, loaded.schema)
    probabilities = np.asarray(loaded.model.predict_proba(frame))
    if (
        probabilities.shape != (len(frame), 2)
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
        or not np.allclose(probabilities.sum(axis=1), 1)
    ):
        raise ValueError("Invalid model output")
    return [
        Prediction(probability_yes=float(p), class_label="yes" if p >= loaded.threshold else "no")
        for p in probabilities[:, 1]
    ]


def create_app(settings: ServingSettings | None = None) -> FastAPI:
    """Build a local demo service; startup failure keeps liveness but disables readiness."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.loaded = None
        try:
            app.state.loaded = load_model(settings or ServingSettings.from_environment())
        except Exception:
            LOGGER.error(json.dumps({"event": "model_load_failed"}))
        yield
        app.state.loaded = None

    app = FastAPI(title="Bank Marketing demonstration API", version="v1", lifespan=lifespan)
    app.state.loaded = None

    def error(request: Request, status: int, code: str):
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                contract_version="v1",
                request_id=request.state.request_id,
                error=code,
            ).model_dump(),
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            response = error(request, 500, "prediction_failed")
        response.headers["X-Request-ID"] = request.state.request_id
        loaded = app.state.loaded
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request.state.request_id,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "model_version": loaded.version if loaded else None,
                    "model_name": loaded.name if loaded else None,
                    "records": getattr(request.state, "record_count", None),
                }
            )
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return error(request, 422, "invalid_request")

    @app.get("/health/live", response_model=HealthResponse)
    def live():
        return HealthResponse(contract_version="v1", status="alive")

    @app.get(
        "/health/ready", response_model=HealthResponse, responses={503: {"model": ErrorResponse}}
    )
    def ready(request: Request):
        if app.state.loaded is None:
            return error(request, 503, "model_unavailable")
        return HealthResponse(contract_version="v1", status="ready")

    @app.post(
        "/v1/predict",
        response_model=PredictResponse,
        responses={
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    def predict(body: PredictRequest, request: Request):
        request.state.record_count = len(body.records)
        loaded = app.state.loaded
        if loaded is None:
            return error(request, 503, "model_unavailable")
        try:
            predictions = score(loaded, body)
        except Exception:
            return error(request, 500, "prediction_failed")
        return PredictResponse(
            contract_version="v1",
            mode="demonstration",
            request_id=request.state.request_id,
            model_name=loaded.name,
            model_version=loaded.version,
            decision_threshold=loaded.threshold,
            predictions=predictions,
        )

    return app
