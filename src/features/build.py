"""One unfitted preprocessing factory shared by training and future serving."""

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.config import SAFE_FEATURES


def history_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Encode UCI's no-contact sentinel without changing the input frame."""
    frame = frame.copy()
    frame["not_previously_contacted"] = (frame.pdays == 999).astype(int)
    frame["pdays"] = frame.pdays.mask(frame.pdays == 999, 0)
    return frame


def build_preprocessor(features: list[str]) -> Pipeline:
    """Return unfitted transforms; preserve unknown/nonexistent as categories.

    Raw validation rejects nulls, so no imputer is necessary. Fit this pipeline
    only on train, then persist it with the classifier for batch/online inference.
    """
    if not features or len(set(features)) != len(features) or not set(features) <= SAFE_FEATURES:
        raise ValueError("Unsafe or duplicate features in preprocessing.")
    numeric = [c for c in features if c in {"age", "pdays", "previous"}]
    categorical = [c for c in features if c not in {"age", "pdays", "previous"}]
    steps = []
    if "pdays" in features:
        numeric.append("not_previously_contacted")
        steps.append(("history", FunctionTransformer(history_features)))
    steps.append(
        (
            "columns",
            ColumnTransformer(
                [
                    ("numeric", StandardScaler(), numeric),
                    ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
                ]
            ),
        )
    )
    return Pipeline(steps)
