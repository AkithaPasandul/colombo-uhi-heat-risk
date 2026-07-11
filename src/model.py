"""Optional ML layer - Random Forest LST prediction (driver attribution).
in : data/processed/features.parquet
out: outputs/models/rf_lst.joblib, outputs/tables/ml_metrics.csv,
     outputs/figures/ml_pred_vs_obs.png

Predicts Landsat LST (degC) per 100m land cell from surface/population
covariates. The point is driver attribution (SHAP follows in
shap_analysis.py), not an operational LST product - the headline result
is the ranking, not the R^2.

Two feature sets are evaluated on IDENTICAL splits (same seed, same
block assignment), so the comparison is clean:
- 'base':     ndvi, ndbi, built_up, pop_density, one-hot lulc_class.
- 'extended': base + physically-motivated spatial context - 3x3 focal
  means (300m neighbourhood) of the four continuous predictors, because
  100m LST responds to the surrounding surface (source-area effect),
  not just the cell itself; plus dist_water_m (distance to the nearest
  non-land cell via a distance transform of land_mask - sea/lagoon
  breeze proximity). dist_water was in config.yaml's original
  optional_model predictor list; it is finally derived here, from
  processed data only. Raw x/y remain excluded from features
  (coordinate leakage; used only to build the 1km split blocks).

Design decisions (see the approved ML plan / reports/methodology_notes.md):
- Analysis universe = the exact HEI universe (land_mask & valid_lst &
  complete-case base features, n=5,391).
- Both a naive random 80/20 cell split AND a spatial block split are
  evaluated; the gap quantifies spatial-leakage inflation. Honest
  headline metrics are the spatial split's.
- NDBI is quasi-circular (same 2024 Landsat composite as LST), so an
  RF without it is fit as an ablation.
- Fixed modest hyperparameters, no tuning. HistGradientBoosting is
  included as a one-row model-class comparison (still no deep learning).
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
from scipy.ndimage import distance_transform_edt, uniform_filter
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

import preprocess
import utils

FEATURES_PARQUET = ROOT / "data" / "processed" / "features.parquet"
OUTPUTS_MODELS = ROOT / "outputs" / "models"
OUTPUTS_TABLES = ROOT / "outputs" / "tables"
OUTPUTS_FIGURES = ROOT / "outputs" / "figures"

TARGET = "lst"
CONTINUOUS_FEATURES = ["ndvi", "ndbi", "built_up", "pop_density"]
CATEGORICAL_FEATURE = "lulc_class"
FOCAL_SIZE = 3          # 3x3 cells = 300m neighbourhood
BLOCK_SIZE_M = 1000     # 1km x 1km spatial blocks (10x10 cells)
TEST_FRACTION = 0.2
SEED = 42
CV_FOLDS = 5

RF_PARAMS = dict(
    n_estimators=500,
    min_samples_leaf=5,
    max_features="sqrt",
    random_state=SEED,
    n_jobs=-1,
)


def add_spatial_context_features(df):
    """3x3 focal means + distance-to-water, computed on the FULL grid before any filtering.

    Focal means are NaN-aware (mean of valid neighbours only) and never NaN where the
    centre cell is valid, so the complete-case universe is unchanged (n=5,391). These use
    only predictor rasters, never the LST target, so they cannot leak the target across
    the train/test block boundary.
    """
    ref = preprocess.load_reference()
    height, width = ref["height"], ref["width"]
    df = df.sort_values("cell_id").reset_index(drop=True)
    out = df.copy()

    for col in CONTINUOUS_FEATURES:
        arr = df[col].to_numpy().reshape(height, width)
        valid = np.isfinite(arr)
        summed = uniform_filter(np.where(valid, arr, 0.0), size=FOCAL_SIZE, mode="constant", cval=0.0)
        count = uniform_filter(valid.astype(float), size=FOCAL_SIZE, mode="constant", cval=0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            focal = np.where(count > 0, summed / count, np.nan)
        out[f"{col}_foc3"] = focal.ravel()

    land = df["land_mask"].to_numpy().reshape(height, width)
    # distance (in cells) from each land cell to the nearest non-land (water/excluded) cell
    out["dist_water_m"] = distance_transform_edt(land).ravel() * 100.0
    return out


def build_dataset(feature_set="extended"):
    """The exact HEI analysis universe: land, valid LST, complete-case base features (n=5,391)."""
    df = pd.read_parquet(FEATURES_PARQUET)
    df = add_spatial_context_features(df)

    base_needed = [TARGET] + CONTINUOUS_FEATURES + [CATEGORICAL_FEATURE]
    valid = df["land_mask"] & df["valid_lst"] & df[base_needed].notna().all(axis=1)

    extended_cols = [f"{c}_foc3" for c in CONTINUOUS_FEATURES] + ["dist_water_m"]
    keep = ["cell_id", "x", "y"] + base_needed + extended_cols
    data = df.loc[valid, keep].reset_index(drop=True)

    dummies = pd.get_dummies(data[CATEGORICAL_FEATURE].astype(int), prefix="lulc")
    X = pd.concat([data[CONTINUOUS_FEATURES], dummies], axis=1)
    if feature_set == "extended":
        X = pd.concat([X, data[extended_cols]], axis=1)
    elif feature_set != "base":
        raise ValueError(f"unknown feature_set {feature_set!r}")
    y = data[TARGET]

    # 1km blocks from cell centroids - used ONLY for the spatial split, never as features
    block_col = (data["x"] // BLOCK_SIZE_M).astype(int)
    block_row = (data["y"] // BLOCK_SIZE_M).astype(int)
    blocks = block_row * 10_000 + block_col

    return data, X, y, blocks


def random_split(n, rng):
    idx = rng.permutation(n)
    n_test = int(round(n * TEST_FRACTION))
    return idx[n_test:], idx[:n_test]


def spatial_block_split(blocks, rng):
    """Assign whole 1km blocks to train/test so test cells never sit beside training cells."""
    unique_blocks = np.array(sorted(blocks.unique()))
    shuffled = rng.permutation(unique_blocks)
    n_test_blocks = int(round(len(unique_blocks) * TEST_FRACTION))
    test_blocks = set(shuffled[:n_test_blocks].tolist())
    is_test = blocks.isin(test_blocks).to_numpy()
    return np.where(~is_test)[0], np.where(is_test)[0], len(unique_blocks), n_test_blocks


def evaluate(y_true, y_pred):
    return {
        "r2": r2_score(y_true, y_pred),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": mean_absolute_error(y_true, y_pred),
    }


def fit_and_score(X, y, train_idx, test_idx, feature_cols=None, with_baselines=True):
    """Fit mean-baseline / linear / RF on one split; returns metrics rows + the RF and its test predictions."""
    cols = feature_cols if feature_cols is not None else list(X.columns)
    X_train, X_test = X.iloc[train_idx][cols], X.iloc[test_idx][cols]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    rows = {}
    if with_baselines:
        rows["baseline_mean"] = evaluate(y_test, np.full(len(y_test), y_train.mean()))
        linear = LinearRegression().fit(X_train, y_train)
        rows["linear_regression"] = evaluate(y_test, linear.predict(X_test))

    rf = RandomForestRegressor(**RF_PARAMS).fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rows["random_forest"] = evaluate(y_test, rf_pred)

    return rows, rf, rf_pred


def block_group_cv(X, y, blocks, logger, tag):
    gkf = GroupKFold(n_splits=CV_FOLDS)
    scores = []
    for train_idx, test_idx in gkf.split(X, y, groups=blocks):
        rf = RandomForestRegressor(**RF_PARAMS).fit(X.iloc[train_idx], y.iloc[train_idx])
        scores.append(r2_score(y.iloc[test_idx], rf.predict(X.iloc[test_idx])))
    logger.info(f"Block GroupKFold ({CV_FOLDS} folds, {tag}) RF R^2: mean={np.mean(scores):.3f} sd={np.std(scores):.3f}")
    return float(np.mean(scores)), float(np.std(scores))


def plot_pred_vs_obs(y_test, rf_pred, r2, out_path):
    fig, ax = plt.subplots(figsize=(3.35, 3.1))
    ax.scatter(y_test, rf_pred, s=4, alpha=0.4, color="#4c72b0", edgecolors="none")
    lims = [min(y_test.min(), rf_pred.min()) - 0.5, max(y_test.max(), rf_pred.max()) + 0.5]
    ax.plot(lims, lims, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlim(lims); ax.set_ylim(lims)
    ax.set_xlabel("Observed LST (°C)", fontsize=8.5)
    ax.set_ylabel("Predicted LST (°C)", fontsize=8.5)
    ax.set_title(f"RF (extended), spatial-block test set (R²={r2:.2f})", fontsize=9.5)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    logger = utils.setup_logging()

    data, X_ext, y, blocks = build_dataset("extended")
    base_cols = [c for c in X_ext.columns if not c.endswith("_foc3") and c != "dist_water_m"]
    logger.info(f"ML dataset: n={len(data)} cells")
    logger.info(f"  base features ({len(base_cols)}): {base_cols}")
    ext_only = [c for c in X_ext.columns if c not in base_cols]
    logger.info(f"  extended adds ({len(ext_only)}): {ext_only}")

    # rng consumed in the same order as the baseline run -> identical splits (determinism check)
    rng = np.random.default_rng(SEED)
    train_r, test_r = random_split(len(data), rng)
    train_s, test_s, n_blocks, n_test_blocks = spatial_block_split(blocks, rng)
    logger.info(
        f"Spatial split: {n_blocks} blocks total, {n_test_blocks} test blocks "
        f"({len(test_s)} test cells / {len(train_s)} train cells)"
    )

    metrics_rows = []

    def record(split, feature_set, rows):
        for model_name, m in rows.items():
            metrics_rows.append({"split": split, "feature_set": feature_set, "model": model_name, **m})

    # --- base feature set (must reproduce the recorded baseline exactly) ---
    rows_random, _, _ = fit_and_score(X_ext, y, train_r, test_r, feature_cols=base_cols)
    record("random", "base", rows_random)
    rows_spatial, _, _ = fit_and_score(X_ext, y, train_s, test_s, feature_cols=base_cols)
    record("spatial_block", "base", rows_spatial)

    base_no_ndbi = [c for c in base_cols if c != "ndbi"]
    rows_ab, _, _ = fit_and_score(X_ext, y, train_s, test_s, feature_cols=base_no_ndbi, with_baselines=False)
    metrics_rows.append({"split": "spatial_block", "feature_set": "base",
                         "model": "random_forest_no_ndbi", **rows_ab["random_forest"]})

    cv_mean_b, cv_sd_b = block_group_cv(X_ext[base_cols], y, blocks, logger, "base")
    metrics_rows.append({"split": f"block_groupkfold_{CV_FOLDS}fold", "feature_set": "base",
                         "model": "random_forest", "r2": cv_mean_b, "rmse": np.nan, "mae": np.nan})

    # --- extended feature set (the improvement candidate), identical splits ---
    rows_random_e, _, _ = fit_and_score(X_ext, y, train_r, test_r)
    record("random", "extended", {"random_forest": rows_random_e["random_forest"],
                                  "linear_regression": rows_random_e["linear_regression"]})
    rows_spatial_e, rf_ext, rf_pred_ext = fit_and_score(X_ext, y, train_s, test_s)
    record("spatial_block", "extended", {"random_forest": rows_spatial_e["random_forest"],
                                         "linear_regression": rows_spatial_e["linear_regression"]})

    ext_no_ndbi = [c for c in X_ext.columns if c != "ndbi" and c != "ndbi_foc3"]
    rows_ab_e, _, _ = fit_and_score(X_ext, y, train_s, test_s, feature_cols=ext_no_ndbi, with_baselines=False)
    metrics_rows.append({"split": "spatial_block", "feature_set": "extended",
                         "model": "random_forest_no_ndbi", **rows_ab_e["random_forest"]})

    hgb = HistGradientBoostingRegressor(random_state=SEED)
    hgb.fit(X_ext.iloc[train_s], y.iloc[train_s])
    metrics_rows.append({"split": "spatial_block", "feature_set": "extended",
                         "model": "hist_gradient_boosting", **evaluate(y.iloc[test_s], hgb.predict(X_ext.iloc[test_s]))})

    cv_mean_e, cv_sd_e = block_group_cv(X_ext, y, blocks, logger, "extended")
    metrics_rows.append({"split": f"block_groupkfold_{CV_FOLDS}fold", "feature_set": "extended",
                         "model": "random_forest", "r2": cv_mean_e, "rmse": np.nan, "mae": np.nan})

    metrics = pd.DataFrame(metrics_rows)
    OUTPUTS_TABLES.mkdir(parents=True, exist_ok=True)
    metrics_csv = OUTPUTS_TABLES / "ml_metrics.csv"
    metrics.to_csv(metrics_csv, index=False)

    OUTPUTS_MODELS.mkdir(parents=True, exist_ok=True)
    model_path = OUTPUTS_MODELS / "rf_lst.joblib"
    joblib.dump({
        "model": rf_ext,
        "feature_set": "extended",
        "feature_columns": list(X_ext.columns),
        "train_index_cell_ids": data.loc[train_s, "cell_id"].tolist(),
        "test_index_cell_ids": data.loc[test_s, "cell_id"].tolist(),
        "rf_params": RF_PARAMS,
        "seed": SEED,
        "block_size_m": BLOCK_SIZE_M,
        "groupkfold_r2": {"base": (cv_mean_b, cv_sd_b), "extended": (cv_mean_e, cv_sd_e)},
    }, model_path)

    OUTPUTS_FIGURES.mkdir(parents=True, exist_ok=True)
    fig_path = OUTPUTS_FIGURES / "ml_pred_vs_obs.png"
    plot_pred_vs_obs(y.iloc[test_s], rf_pred_ext, rows_spatial_e["random_forest"]["r2"], fig_path)

    # verification convention: re-read the written table from disk before trusting it
    reread = pd.read_csv(metrics_csv)
    logger.info(f"Wrote {metrics_csv} ({len(reread)} rows), {model_path}, {fig_path}")
    logger.info("\n" + reread.round(4).to_string(index=False))

    return metrics


if __name__ == "__main__":
    main()
