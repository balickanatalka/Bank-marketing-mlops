---
title: Validation model card
updated: 2026-11-02
---

# Logistic Regression validation experiment

Status: selected by the predefined validation protocol, not deployed or promoted.
Exact run IDs, parameters, source hashes and dependency versions are recorded in
`reports/lesson5_experiments.json` and the local MLflow batch.

Data: pinned UCI Bank Marketing additional-full; chronological 60/15/10/15 split.
Train: 24,712 rows; validation: 6,178 rows (794 positive). No final-test/replay scoring.
Ten pre-contact features; duration is excluded. Unknown categories remain explicit;
pdays=999 is encoded as no prior contact. The complete fitted Pipeline is persisted.

Validation AP is 0.185046 versus Dummy 0.128521. At threshold 0.5, precision is
0.368421, recall 0.008816 and positive-class F1 0.017220. This detects only 7 of
794 positives, missing 787. Class-weighted candidates raise recall at the cost of
more false positives but do not exceed this candidate's AP in the fixed comparison.

Use: academic investigation of ranking and reproducible MLOps. The result does
not establish production readiness or justify decisions about real bank clients.
Limitations: one historical validation period, repeated model comparison, missing
client identifiers, assumed feature availability and uncalibrated weighted scores.
Model selection does not optimize an operational cost function or fairness goal.

No model registry alias, production version, final-test result or deployment exists.
Microsoft RAG remains future work over documented evidence.
