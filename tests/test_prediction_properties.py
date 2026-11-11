import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.features.build import build_preprocessor


@pytest.fixture(scope="module")
def model():
    train = pd.DataFrame(
        {
            "age": [24, 34, 44, 54],
            "job": ["admin.", "unknown", "admin.", "unknown"],
            "pdays": [999, 1, 999, 12],
        }
    )
    return Pipeline(
        [
            ("preprocessing", build_preprocessor(list(train))),
            ("model", LogisticRegression(random_state=42)),
        ]
    ).fit(train, [0, 1, 0, 1])


batches = st.lists(
    st.fixed_dictionaries(
        {
            "age": st.integers(min_value=1, max_value=120),
            "job": st.sampled_from(["admin.", "unknown", "unseen"]),
            "pdays": st.one_of(st.integers(min_value=0, max_value=998), st.just(999)),
        }
    ),
    min_size=1,
    max_size=20,
)


@settings(max_examples=40, derandomize=True, deadline=None)
@given(records=batches)
def test_generated_probabilities_are_normalized_and_bounded(model, records):
    probabilities = model.predict_proba(pd.DataFrame.from_records(records))

    assert np.isfinite(probabilities).all()
    assert ((0 <= probabilities) & (probabilities <= 1)).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), 1)


@settings(max_examples=40, derandomize=True, deadline=None)
@given(records=batches)
def test_generated_batch_preserves_row_count_and_feature_width(model, records):
    batch = pd.DataFrame.from_records(records)
    transformed = model["preprocessing"].transform(batch)

    assert transformed.shape == (len(records), model["model"].n_features_in_)
    assert model.predict(batch).shape == (len(records),)
    assert model.predict_proba(batch).shape == (len(records), len(model.classes_))
