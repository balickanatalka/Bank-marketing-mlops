"""Render the validation model card from verified registry lineage."""


def render_model_card(metadata: dict) -> str:
    """Return a public-safe card using recorded validation metrics and error counts."""
    metrics = metadata["metrics"]
    matrix = metadata["error_analysis"]["confusion_matrix"]
    positives = sum(matrix[1])
    groups = metadata["error_analysis"]["subgroups"]
    rows = "\n".join(
        f"| {name} | {group['support']} | {group['positive_support']} | "
        f"{group['confusion_matrix'][1][1]} |"
        for name, group in groups.items()
    )
    return f"""---
title: Validation model card
updated: 2026-11-11
---

# {metadata["parameters"]["algorithm"]} validation experiment

Generated from verified registry lineage by `src/model_card.py`.
Status: validation candidate, not deployed. Registration does not imply promotion.
No champion is assigned by the preparation command. No production readiness claim.

## Purpose and data

Academic investigation of pre-contact ranking for UCI Bank Marketing, target y=yes.
Pinned additional-full data SHA-256: `{metadata["raw_sha256"]}`.
Chronological split {metadata["split"]}; train {metadata["rows"]["train"]:,} rows,
validation {metadata["rows"]["validation"]:,} rows ({positives} positive).
{len(metadata["schema"])} pre-contact features: {", ".join(metadata["schema"])}.
Duration and target excluded. Complete fitted Pipeline
contains scaling, one-hot encoding and pdays=999 history transformation.
Unknown categories remain explicit; real null values are rejected.

## Validation metrics

Threshold: {metadata["parameters"]["decision_threshold"]}; evaluation: validation only.

| Metric | Value |
| --- | ---: |
| Average Precision | {metrics["average_precision"]:.9f} |
| Dummy Average Precision | {metadata["dummy_ap"]:.9f} |
| Recall yes | {metrics["recall_yes"]:.9f} |
| Precision yes | {metrics["precision_yes"]:.9f} |
| F1 yes | {metrics["f1_yes"]:.9f} |

Detected {matrix[1][1]} of {positives} positives; missed {matrix[1][0]}.
The academic recall floor is {metadata["recall_floor"]:.9f}
(ordinary Logistic Regression in the same batch).
This very low recall is insufficient evidence for operational use.
No threshold tuning, final-test scoring or replay scoring was performed.

## Descriptive subgroups

| Subgroup | Support | Positive support | True positives |
| --- | ---: | ---: | ---: |
{rows}

These aggregates do not establish fairness or statistical significance and do not
influence selection or promotion.

## Lineage and registry

Original MLflow run: `{metadata["source_run_id"]}`.
Training Git SHA: `{metadata["git_sha"]}`; dirty tree: {metadata["working_tree_dirty"]}.
Preprocessing version: `{metadata["preprocessing_sha256"]}`.
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
"""
