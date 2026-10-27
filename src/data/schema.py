"""Pinned UCI additional-full data contract, independent of model selection.

Unknown values are explicit categories; nulls and undocumented categories fail.
Bounds express domain constraints, not extrema fitted on validation or holdouts.
"""

CATEGORIES = {
    "job": {
        "admin.",
        "blue-collar",
        "entrepreneur",
        "housemaid",
        "management",
        "retired",
        "self-employed",
        "services",
        "student",
        "technician",
        "unemployed",
        "unknown",
    },
    "marital": {"divorced", "married", "single", "unknown"},
    "education": {
        "basic.4y",
        "basic.6y",
        "basic.9y",
        "high.school",
        "illiterate",
        "professional.course",
        "university.degree",
        "unknown",
    },
    "default": {"no", "yes", "unknown"},
    "housing": {"no", "yes", "unknown"},
    "loan": {"no", "yes", "unknown"},
    "contact": {"cellular", "telephone"},
    "month": {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"},
    "day_of_week": {"mon", "tue", "wed", "thu", "fri"},
    "poutcome": {"failure", "nonexistent", "success"},
    "y": {"no", "yes"},
}

INTEGER_BOUNDS = {
    "age": (1, 120),
    "duration": (0, None),
    "campaign": (1, None),
    "pdays": (0, 999),
    "previous": (0, None),
}

POSITIVE_COLUMNS = ("cons.price.idx", "euribor3m", "nr.employed")
