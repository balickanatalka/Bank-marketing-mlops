# Validation experiment comparison

All six models use the same chronological train and validation windows.
Threshold: 0.5. No final test or replay evaluation, registry promotion or deployment.

| Model | AP | Precision yes | Recall yes | F1 yes | Macro F1 |
|---|---:|---:|---:|---:|---:|
| dummy | 0.128521 | 0.000000 | 0.000000 | 0.000000 | 0.465663 |
| logistic | 0.185046 | 0.368421 | 0.008816 | 0.017220 | 0.474000 |
| logistic_balanced | 0.182707 | 0.150174 | 0.598237 | 0.240081 | 0.441031 |
| random_forest | 0.182201 | 0.144261 | 0.702771 | 0.239382 | 0.389252 |
| hist_gradient_boosting | 0.165383 | 0.139535 | 0.589421 | 0.225651 | 0.417163 |
| xgboost | 0.172218 | 0.141037 | 0.613350 | 0.229338 | 0.412856 |

Validation winner: **logistic**.
The predefined rule maximizes AP among candidates above Dummy AP and at least
ordinary LR recall (0.008816).
Exact ties prefer the recorded order.

Run identifiers:

| Model | MLflow run |
|---|---|
| dummy | `a3069e9a1683421ba21de7ca8ed4d799` |
| logistic | `1727e138843c4ec8aacc5990124148c6` |
| logistic_balanced | `57d8a3db613a448fb6727344f52142c6` |
| random_forest | `1d92a1c6cd21401f9b69c7a91ae5d12c` |
| hist_gradient_boosting | `7d1516bb6b9941199f35c9112bc83320` |
| xgboost | `02b90a35d34d4751ba4e6a88b5634526` |

The aggregate JSON includes parameters, provenance, confusion counts and subgroup
errors. PR display curves are sampled; AP uses all predictions. Full curves, plots,
fitted pipelines and SQLite metadata remain in ignored local artifacts.

Class weighting changes the threshold trade-off and can increase false positives.
Inspect false negatives as well as AP. Small subgroups do not support causal
or fairness claims. One historical validation window limits certainty.
This is a validation winner, not an approved production model.
