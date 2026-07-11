"""Optional ML layer - SHAP attribution for the trained RF (post-hoc only).
in : outputs/models/rf_lst.joblib + data/processed/features.parquet
out: outputs/tables/shap_importance.csv,
     outputs/figures/shap_summary.png, outputs/figures/shap_bar.png

Strictly post-hoc: loads the model model.py saved and never retrains.
Feature preprocessing is not reimplemented here - it reuses
model.build_dataset() so the two files cannot drift apart, and the
spatial test set is reselected by the exact cell_ids saved in the
joblib (not re-derived from the seed).

SHAP is computed on the spatial-block TEST set only (~1,100 cells,
TreeExplainer, no sampling needed at this size) - attribution on cells
the model never saw in training, consistent with the honest-evaluation
convention. One-hot LULC columns are aggregated back into a single
"land cover" importance (sum of member mean-|SHAP|) for the headline
ranking; the per-class breakdown stays in the CSV.

Interpretation guardrail (repeat in any write-up): SHAP ranks what the
MODEL attributes its predictions to - not physical causality. NDBI's
rank additionally carries the quasi-circularity caveat (same 2024
Landsat composite as LST itself; see model.py's ablation).
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap

import model
import utils

MODEL_PATH = ROOT / "outputs" / "models" / "rf_lst.joblib"
OUTPUTS_TABLES = ROOT / "outputs" / "tables"
OUTPUTS_FIGURES = ROOT / "outputs" / "figures"

SINGLE_COL_WIDTH_IN = 3.35
DPI = 300


def load_test_set():
    """Rebuild the dataset via model.build_dataset() and reselect the saved spatial test cells."""
    bundle = joblib.load(MODEL_PATH)
    data, X, y, _blocks = model.build_dataset()

    if list(X.columns) != bundle["feature_columns"]:
        raise RuntimeError(
            "Feature columns differ from those the model was trained on - "
            f"expected {bundle['feature_columns']}, got {list(X.columns)}. "
            "Re-run src/model.py before shap_analysis.py."
        )

    test_ids = set(bundle["test_index_cell_ids"])
    test_mask = data["cell_id"].isin(test_ids).to_numpy()
    return bundle["model"], X.loc[test_mask], y.loc[test_mask]


def aggregate_lulc(importance):
    """Collapse one-hot lulc_* rows into a single 'lulc_class (all)' row for the headline ranking."""
    is_lulc = importance["feature"].str.startswith("lulc_")
    lulc_total = importance.loc[is_lulc, "mean_abs_shap"].sum()
    headline = importance[~is_lulc].copy()
    headline = pd.concat([
        headline,
        pd.DataFrame([{"feature": "lulc_class (all)", "mean_abs_shap": lulc_total}]),
    ], ignore_index=True)
    return headline.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)


def plot_beeswarm(shap_values, X_test, out_path):
    fig = plt.figure(figsize=(SINGLE_COL_WIDTH_IN * 1.6, SINGLE_COL_WIDTH_IN * 1.3))
    shap.summary_plot(shap_values, X_test, show=False, plot_size=None)
    plt.gcf().set_size_inches(SINGLE_COL_WIDTH_IN * 1.6, SINGLE_COL_WIDTH_IN * 1.3)
    for ax in plt.gcf().axes:
        ax.tick_params(labelsize=8)
        ax.xaxis.label.set_size(8.5)
    plt.tight_layout()
    plt.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close("all")


def plot_bar(headline, out_path):
    fig, ax = plt.subplots(figsize=(SINGLE_COL_WIDTH_IN, SINGLE_COL_WIDTH_IN * 0.75))
    ordered = headline.sort_values("mean_abs_shap")
    ax.barh(ordered["feature"], ordered["mean_abs_shap"], color="#4c72b0", edgecolor="black", linewidth=0.4)
    ax.set_xlabel("mean |SHAP| (°C)", fontsize=8.5)
    ax.set_title("RF feature attribution (spatial test set)", fontsize=9.5)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def main():
    logger = utils.setup_logging()

    rf, X_test, y_test = load_test_set()
    logger.info(f"SHAP on spatial test set: {len(X_test)} cells, {X_test.shape[1]} features")

    explainer = shap.TreeExplainer(rf)
    shap_values = explainer.shap_values(X_test)

    importance = pd.DataFrame({
        "feature": X_test.columns,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0),
    }).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)

    headline = aggregate_lulc(importance)

    OUTPUTS_TABLES.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUTS_TABLES / "shap_importance.csv"
    # full per-column table (incl. each one-hot lulc class), plus the aggregated headline rows
    importance["level"] = "per_column"
    headline["level"] = "headline_aggregated"
    pd.concat([headline, importance], ignore_index=True).to_csv(csv_path, index=False)

    OUTPUTS_FIGURES.mkdir(parents=True, exist_ok=True)
    plot_beeswarm(shap_values, X_test, OUTPUTS_FIGURES / "shap_summary.png")
    plot_bar(headline, OUTPUTS_FIGURES / "shap_bar.png")

    # verification convention: re-read the written table before trusting it
    reread = pd.read_csv(csv_path)
    logger.info(f"Wrote {csv_path} ({len(reread)} rows) + shap_summary.png + shap_bar.png")
    logger.info("\nHeadline ranking (one-hot LULC aggregated):\n"
                + headline.round(4).to_string(index=False))

    return headline, importance


if __name__ == "__main__":
    main()
