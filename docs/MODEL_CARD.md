---
title: Validation model card
updated: 2026-11-11
---

# logistic validation experiment

Generated from verified registry lineage by `src/model_card.py`.
Status: validation candidate, not deployed. Registration does not imply promotion.
No champion is assigned by the preparation command. No production readiness claim.

## Purpose and data

Academic investigation of pre-contact ranking for UCI Bank Marketing, target y=yes.
Pinned additional-full data SHA-256: `74adfc578bf77a7ff4bb1ba4a9f8709d9e3c6907342959c2c8416847e0afb4d8`.
Chronological split {'train': 0.6, 'validation': 0.15, 'final_test': 0.1, 'replay': 0.15}; train 24,712 rows,
validation 6,178 rows (794 positive).
10 pre-contact features: age, job, marital, education, default, housing, loan, pdays, previous, poutcome.
Duration and target excluded. Complete fitted Pipeline
contains scaling, one-hot encoding and pdays=999 history transformation.
Unknown categories remain explicit; real null values are rejected.

## Validation metrics

Threshold: 0.5; evaluation: validation only.

| Metric | Value |
| --- | ---: |
| Average Precision | 0.185046394 |
| Dummy Average Precision | 0.128520557 |
| Recall yes | 0.008816121 |
| Precision yes | 0.368421053 |
| F1 yes | 0.017220172 |

Detected 7 of 794 positives; missed 787.
The academic recall floor is 0.008816121
(ordinary Logistic Regression in the same batch).
This very low recall is insufficient evidence for operational use.
No threshold tuning, final-test scoring or replay scoring was performed.

## Descriptive subgroups

| Subgroup | Support | Positive support | True positives |
| --- | ---: | ---: | ---: |
| age_under_30 | 598 | 157 | 0 |
| age_30_to_59 | 5409 | 563 | 6 |
| age_60_plus | 171 | 74 | 1 |
| no_previous_contact | 6049 | 739 | 0 |
| previous_contact | 129 | 55 | 7 |

These aggregates do not establish fairness or statistical significance and do not
influence selection or promotion.

## Lineage and registry

Original MLflow run: `1727e138843c4ec8aacc5990124148c6`.
Training Git SHA: `e5dc1b36941098255e87c371cb9b372b797a4932`; dirty tree: True.
Preprocessing version: `72438cd19af8b74f1d8dfe727c2811155ce4c0c11b40dc8bddedb932231694a6`.
The package manifest covers model, signature, synthetic input example, dependencies,
source code and lineage. Registry version metadata anchors the manifest SHA-256.
The packaging run and exact model version are recorded in the execution evidence.
Champion/challenger aliases, quality gates, version loading and rollback:
[registry instructions](MODEL_REGISTRY.pl.md).

## Limitations and known failure modes

One historical validation period, repeated comparisons, severe class imbalance,
missing client identifiers, uncertain feature availability and temporal shift.
Low recall at 0.5 misses most positives; class-weighted models trade false positives
for recall without winning the predefined AP comparison. Selection does not
optimize an operational cost or fairness objective. Weighted scores are uncalibrated.
Changed inputs, schema, dependencies or artifact hashes must block reuse/promotion.
Hashes require a trusted local store; they are not cryptographic signatures.
Only trusted source joblib files may be loaded. The packaged skops model explicitly
trusts the existing history_features function. No arbitrary uploaded models are accepted.

No production version, deployment, final-test result or Microsoft RAG exists.
