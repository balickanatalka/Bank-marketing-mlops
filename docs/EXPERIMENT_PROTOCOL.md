---
title: Controlled validation experiments
updated: 2026-11-02
---

# Experiment protocol

The fixed candidate parameters are in `configs/experiments.yaml`. This protocol
is defined before comparing candidates. Each batch trains six pipelines on the
same chronological train window and evaluates the same validation window.
Final test and replay are excluded from model fitting, selection and evaluation.

Choose the greatest scikit-learn Average Precision among non-Dummy candidates
with AP strictly greater than Dummy and positive-class recall at least equal to
ordinary Logistic Regression. All classification metrics use the fixed threshold
0.5. The baseline determines the recall floor before candidate comparison. Exact
AP ties follow the predefined order in configuration, preferring the simpler
logistic model. If no candidate qualifies, report no selection. Do not change the
threshold or candidate parameters in response to these results.

The six runs are Dummy, ordinary Logistic Regression, balanced Logistic
Regression, balanced Random Forest, balanced HistGradientBoosting and XGBoost.
XGBoost's scale_pos_weight equals negative/positive label counts from train only.
Use one CPU thread, fixed seeds and the shared preprocessing factory. Persist
the complete fitted Pipeline. Encoding is dense for all candidates to support
HistGradientBoosting without a separate feature implementation.

SQLite metadata and model artifacts stay under a fresh ignored
`artifacts/lesson5/<batch>/` directory. No tracking URI from the environment is
used. Log parameters, metrics, model files, plots, configuration, dependency
versions, source hashes, Git SHA and dirty state, pinned data hash, split hashes,
seed, batch ID and run IDs. Do not log client rows or raw validation predictions
to public reports. Error analysis uses aggregate confusion counts, probability
bins and documented subgroups; subgroup statistics are descriptive and do not
determine model selection.

The selected model is a validation experiment winner, not a production model.
There is no registry promotion, deployment, final-test score or RAG execution.
Repeated validation comparisons limit certainty and may overfit this window;
low support, temporal shift and missing client identifiers remain limitations.
