import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.pipeline import build_preprocessor, chronological_split, history_features


def test_chronological_partition():
    df = pd.DataFrame({"row": range(101)})
    parts = chronological_split(df, dict(train=0.6, validation=0.15, final_test=0.1, replay=0.15))
    assert [len(p) for p in parts.values()] == [60, 15, 10, 16]
    assert pd.concat(parts.values()).equals(df)
    assert max(parts["train"].index) < min(parts["validation"].index)
    assert max(parts["validation"].index) < min(parts["final_test"].index)


def test_fit_train_only_unknown_and_roundtrip(tmp_path):
    train = pd.DataFrame({"age": [20, 30, 40, 50], "job": ["a", "b", "a", "b"]})
    valid = pd.DataFrame({"age": [1000], "job": ["never_seen"]})
    model = Pipeline(
        [("preprocessing", build_preprocessor(["age", "job"])), ("model", LogisticRegression())]
    )
    model.fit(train, [0, 1, 0, 1])
    columns = model["preprocessing"]["columns"]
    assert columns.named_transformers_["numeric"].mean_[0] == 35
    assert "never_seen" not in columns.named_transformers_["categorical"].categories_[0]
    probabilities = model.predict_proba(valid)
    assert probabilities.shape == (1, 2)
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    path = tmp_path / "model.joblib"
    joblib.dump(model, path)
    np.testing.assert_allclose(joblib.load(path).predict_proba(valid), probabilities)


def test_pdays_semantics():
    df = pd.DataFrame({"pdays": [999, 5]})
    transformed = history_features(df)
    assert transformed.pdays.tolist() == [0, 5]
    assert transformed.not_previously_contacted.tolist() == [1, 0]
    assert df.pdays.tolist() == [999, 5]
