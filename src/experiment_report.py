"""Build shareable aggregate experiment reports without loading model artifacts."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT


def comparison_table(summary: dict) -> pd.DataFrame:
    """Return comparable validation metrics and stable MLflow run identifiers."""
    return pd.DataFrame(
        [
            {"model": name, "run_id": result["run_id"], **result["metrics"]}
            for name, result in summary["results"].items()
        ]
    ).set_index("model")


def export_comparison(batch: Path, reports: Path | None = None) -> dict:
    """Exclusively create an aggregate JSON snapshot and comparison Markdown.

    PR curves are sampled to at most 200 display points per model. AP metrics
    remain those computed from every validation prediction in the original run.
    No source rows, model files, SQLite paths or host identifiers are exported.
    """
    reports = reports or ROOT / "reports"
    json_path = reports / "lesson5_experiments.json"
    markdown_path = reports / "experiment_comparison.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError("Experiment comparison exists; choose a fresh report directory")
    summary = json.loads((batch / "summary.json").read_text(encoding="utf-8"))
    summary["protocol"] = json.loads((batch / "protocol.json").read_text(encoding="utf-8"))
    summary["display_curves"] = {}
    summary["error_analysis"] = {}
    for name in summary["results"]:
        curve = json.loads((batch / name / "precision_recall.json").read_text(encoding="utf-8"))
        indices = np.unique(
            np.linspace(
                0, len(curve["precision"]) - 1, min(200, len(curve["precision"])), dtype=int
            )
        )
        summary["display_curves"][name] = {
            key: [curve[key][int(index)] for index in indices] for key in ["precision", "recall"]
        }
        summary["error_analysis"][name] = json.loads(
            (batch / name / "errors.json").read_text(encoding="utf-8")
        )
    summary["display_curves_sampled"] = True
    table = comparison_table(summary)
    columns = ["average_precision", "precision_yes", "recall_yes", "f1_yes", "macro_f1"]
    lines = [
        "# Validation experiment comparison",
        "",
        "All six models use the same chronological train and validation windows.",
        "Threshold: 0.5. No final test or replay evaluation, registry promotion or deployment.",
        "",
        "| Model | AP | Precision yes | Recall yes | F1 yes | Macro F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in table.iterrows():
        lines.append("| " + name + " | " + " | ".join(f"{row[key]:.6f}" for key in columns) + " |")
    selection = summary["selection"]
    lines.extend(
        [
            "",
            f"Validation winner: **{selection['winner']}**.",
            "The predefined rule maximizes AP among candidates above Dummy AP and at least",
            f"ordinary LR recall ({selection['recall_floor']:.6f}).",
            "Exact ties prefer the recorded order.",
            "",
            "Run identifiers:",
            "",
            "| Model | MLflow run |",
            "|---|---|",
        ]
    )
    for name, result in summary["results"].items():
        lines.append(f"| {name} | `{result['run_id']}` |")
    lines.extend(
        [
            "",
            "The aggregate JSON includes parameters, provenance, confusion counts and subgroup",
            "errors. PR display curves are sampled; AP uses all predictions. Full curves, plots,",
            "fitted pipelines and SQLite metadata remain in ignored local artifacts.",
            "",
            "Class weighting changes the threshold trade-off and can increase false positives.",
            "Inspect false negatives as well as AP. Small subgroups do not support causal",
            "or fairness claims. One historical validation window limits certainty.",
            "This is a validation winner, not an approved production model.",
            "",
        ]
    )
    reports.mkdir(parents=True, exist_ok=True)
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    with markdown_path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return summary


def main() -> None:
    """Export one existing batch; do not fit models or modify prior reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--reports", type=Path)
    args = parser.parse_args()
    export_comparison(args.batch, args.reports)


if __name__ == "__main__":
    main()
