import io

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.features.build import build_preprocessor


def dense(value):
    return value.toarray() if hasattr(value, "toarray") else value


def test_batch_single_record_determinism_and_serialization():
    frame = pd.DataFrame(
        {
            "age": [20, 30, 40, 50],
            "education": ["unknown", "basic.4y"] * 2,
            "poutcome": ["nonexistent", "success"] * 2,
            "pdays": [999, 4, 999, 8],
        }
    )
    original = frame.copy(deep=True)
    models = []
    for _ in range(2):
        model = Pipeline(
            [
                ("features", build_preprocessor(list(frame))),
                ("classifier", LogisticRegression(random_state=42)),
            ]
        )
        model.fit(frame, [0, 1, 0, 1])
        models.append(model)
    batch = models[0]["features"].transform(frame)
    # Simulate an API record reconstructed from a JSON object, without fitting.
    serving = pd.DataFrame([frame.iloc[0].to_dict()])
    np.testing.assert_allclose(dense(batch)[0], dense(models[0]["features"].transform(serving))[0])
    np.testing.assert_allclose(models[0].predict_proba(frame)[:1], models[0].predict_proba(serving))
    np.testing.assert_allclose(models[0].predict_proba(frame), models[1].predict_proba(frame))
    stream = io.BytesIO()
    joblib.dump(models[0], stream)
    stream.seek(0)
    restored = joblib.load(stream)
    np.testing.assert_array_equal(restored.predict(frame), models[0].predict(frame))
    np.testing.assert_allclose(restored.predict_proba(frame), models[0].predict_proba(frame))
    pd.testing.assert_frame_equal(frame, original)
    columns = restored["features"]["columns"]
    assert "unknown" in columns.named_transformers_["categorical"].categories_[0]
    assert "nonexistent" in columns.named_transformers_["categorical"].categories_[1]
    np.testing.assert_allclose(columns.named_transformers_["numeric"].mean_, [35, 3, 0.5])
    restored.predict_proba(
        pd.DataFrame([dict(age=1000, education="unseen", poutcome="unseen", pdays=999)])
    )
    np.testing.assert_allclose(columns.named_transformers_["numeric"].mean_, [35, 3, 0.5])
    assert "unseen" not in columns.named_transformers_["categorical"].categories_[0]


@pytest.mark.parametrize("features", [["duration"], ["y"], ["age", "age"], []])
def test_factory_rejects_leakage(features):
    with pytest.raises(ValueError):
        build_preprocessor(features)
