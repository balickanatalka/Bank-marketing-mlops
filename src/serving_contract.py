"""Stable v1 HTTP contract; API names are mapped to the existing model features."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.data.schema import CATEGORIES, INTEGER_BOUNDS

API_TO_MODEL = {
    "age_years": "age",
    "job": "job",
    "marital_status": "marital",
    "education": "education",
    "credit_default": "default",
    "housing_loan": "housing",
    "personal_loan": "loan",
    "days_since_previous_contact": "pdays",
    "previous_contacts": "previous",
    "previous_campaign_outcome": "poutcome",
}


class ContractModel(BaseModel):
    """Reject extra fields and implicit type coercion in both API directions."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class BankRecord(ContractModel):
    """One pre-contact record; bounds and dictionaries come from the UCI schema."""

    age_years: int = Field(ge=INTEGER_BOUNDS["age"][0], le=INTEGER_BOUNDS["age"][1])
    job: str = Field(json_schema_extra={"enum": sorted(CATEGORIES["job"])})
    marital_status: str = Field(json_schema_extra={"enum": sorted(CATEGORIES["marital"])})
    education: str = Field(json_schema_extra={"enum": sorted(CATEGORIES["education"])})
    credit_default: str = Field(json_schema_extra={"enum": sorted(CATEGORIES["default"])})
    housing_loan: str = Field(json_schema_extra={"enum": sorted(CATEGORIES["housing"])})
    personal_loan: str = Field(json_schema_extra={"enum": sorted(CATEGORIES["loan"])})
    days_since_previous_contact: int = Field(
        ge=INTEGER_BOUNDS["pdays"][0], le=INTEGER_BOUNDS["pdays"][1]
    )
    previous_contacts: int = Field(ge=INTEGER_BOUNDS["previous"][0])
    previous_campaign_outcome: str = Field(
        json_schema_extra={"enum": sorted(CATEGORIES["poutcome"])}
    )

    @field_validator(
        "job",
        "marital_status",
        "education",
        "credit_default",
        "housing_loan",
        "personal_loan",
        "previous_campaign_outcome",
    )
    @classmethod
    def known_category(cls, value: str, info) -> str:
        """Use the training contract, including explicit unknown/nonexistent values."""
        if value not in CATEGORIES[API_TO_MODEL[info.field_name]]:
            raise ValueError("Unsupported category")
        return value


class PredictRequest(ContractModel):
    """A bounded batch; no inference-time feature engineering is added here."""

    records: Annotated[list[BankRecord], Field(min_length=1, max_length=100)]


class Prediction(ContractModel):
    """Decision at the model's recorded threshold and probability of y=yes."""

    probability_yes: float = Field(ge=0, le=1)
    class_label: Literal["no", "yes"]


class PredictResponse(ContractModel):
    """Pinned model identity stays stable for the lifetime of one service process."""

    contract_version: Literal["v1"]
    request_id: str
    model_name: str
    model_version: str
    mode: Literal["demonstration"]
    decision_threshold: float = Field(ge=0, le=1)
    predictions: Annotated[list[Prediction], Field(min_length=1, max_length=100)]


class ErrorResponse(ContractModel):
    """Stable errors never echo request values, paths or exception messages."""

    contract_version: Literal["v1"]
    request_id: str
    error: Literal["invalid_request", "model_unavailable", "prediction_failed"]


class HealthResponse(ContractModel):
    """Process liveness is independent of successful model initialization."""

    contract_version: Literal["v1"]
    status: Literal["alive", "ready"]


def example_request() -> dict:
    """Return synthetic, valid data rather than copying any customer record."""
    return {
        "records": [
            {
                "age_years": 30,
                "job": "admin.",
                "marital_status": "single",
                "education": "university.degree",
                "credit_default": "no",
                "housing_loan": "no",
                "personal_loan": "no",
                "days_since_previous_contact": 999,
                "previous_contacts": 0,
                "previous_campaign_outcome": "nonexistent",
            }
        ]
    }
