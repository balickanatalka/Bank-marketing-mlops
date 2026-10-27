"""Basic raw-data contract, intentionally independent of training."""

import numpy as np
import pandas as pd

from src.data.schema import CATEGORIES, INTEGER_BOUNDS, POSITIVE_COLUMNS

NUMERIC = [
    "age",
    "duration",
    "campaign",
    "pdays",
    "previous",
    "emp.var.rate",
    "cons.price.idx",
    "cons.conf.idx",
    "euribor3m",
    "nr.employed",
]
CATEGORICAL = [
    "job",
    "marital",
    "education",
    "default",
    "housing",
    "loan",
    "contact",
    "month",
    "day_of_week",
    "poutcome",
    "y",
]


def validate_dataframe(df: pd.DataFrame, expected_rows: int | None = 41188) -> dict:
    """Reject malformed raw data; special strings remain explicit categories."""
    if df.columns.duplicated().any() or set(df.columns) != set(NUMERIC + CATEGORICAL):
        raise ValueError("Niepoprawne kolumny: oczekiwano 20 cech i y, bez duplikatów.")
    if expected_rows is not None and len(df) != expected_rows:
        raise ValueError(f"Oczekiwano {expected_rows} wierszy, otrzymano {len(df)}.")
    if df.empty or df.isna().any().any():
        raise ValueError("Pusty zbiór lub wartości null.")
    if set(df.y.unique()) != {"yes", "no"}:
        raise ValueError("Target musi zawierać klasy yes i no.")
    for column in NUMERIC:
        if not pd.api.types.is_numeric_dtype(df[column]) or not np.isfinite(df[column]).all():
            raise ValueError(f"Niepoprawny typ lub wartość liczbowa: {column}.")
    for column in CATEGORICAL:
        if not df[column].map(lambda value: isinstance(value, str)).all():
            raise ValueError(f"Oczekiwano kategorii tekstowej: {column}.")
        if not df[column].isin(CATEGORIES[column]).all():
            raise ValueError(f"Niedozwolona kategoria: {column}.")
    for column, (lower, upper) in INTEGER_BOUNDS.items():
        values = df[column]
        if pd.api.types.is_bool_dtype(values) or (values % 1 != 0).any():
            raise ValueError(f"Oczekiwano liczby całkowitej: {column}.")
        if (values < lower).any() or (upper is not None and (values > upper).any()):
            raise ValueError(f"Niepoprawny zakres: {column}.")
    for column in POSITIVE_COLUMNS:
        if (df[column] <= 0).any():
            raise ValueError(f"Oczekiwano dodatniej wartości: {column}.")
    if (df.age <= 0).any() or (df[["duration", "pdays", "previous"]] < 0).any().any():
        raise ValueError("Niepoprawny zakres wieku lub liczników.")
    if (df.campaign < 1).any():
        raise ValueError("campaign musi być dodatnie.")
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "class_counts": df.y.value_counts().to_dict(),
        "duplicates": int(df.duplicated().sum()),
        "unknown_counts": {c: int((df[c] == "unknown").sum()) for c in CATEGORICAL},
        "pdays_999": int((df.pdays == 999).sum()),
    }
