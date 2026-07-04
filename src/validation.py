"""Week 5 - validation.
Aggregate Landsat LST to MODIS 1 km; correlation + RMSE vs MOD11A2.
LST-by-landcover stats, LST/NDVI/NDBI/built-up correlation matrix.
out: outputs/tables/validation.csv, correlation_matrix.csv,
     lst_by_landcover.csv

All land-only, same `land_mask` convention as every prior stage. The
Landsat-vs-MODIS aggregation is explicitly a pattern/consistency check,
not ground truth (MODIS is a coarse 1km product with its own missingness
pattern) - each MODIS 1km cell's Landsat-side value is the mean of ONLY
the aligned land pixels that fall inside it, and any MODIS cell whose
100m footprint is less than 50% land is dropped, since a naive mean over
all pixels (including sea-surface) would reintroduce the same land/water
mixing bias `land_mask` exists to prevent everywhere else.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy import stats

import utils

PROCESSED_DIR = ROOT / "data" / "processed"
INTERIM_DIR = ROOT / "data" / "interim"
OUTPUTS_TABLES = ROOT / "outputs" / "tables"
FEATURES_PARQUET = PROCESSED_DIR / "features.parquet"
MODIS_NATIVE_TIF = INTERIM_DIR / "modis_lst_native.tif"

LAND_FRACTION_MIN = 0.5


def validate_modis(df, logger):
    """Block-aggregate Landsat LST (land pixels only) up to the native MODIS 1km grid."""
    with rasterio.open(MODIS_NATIVE_TIF) as src:
        modis = src.read(1)
        modis_nodata = src.nodata
        modis_transform = src.transform

    transformer = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(df["x"].values, df["y"].values)
    inv_transform = ~modis_transform
    cols, rows = inv_transform * (lon, lat)

    work = df.copy()
    work["modis_row"] = np.floor(rows).astype(int)
    work["modis_col"] = np.floor(cols).astype(int)

    summary = work.groupby(["modis_row", "modis_col"]).agg(
        total_count=("cell_id", "count"), land_count=("land_mask", "sum")
    ).reset_index()
    summary["land_fraction"] = summary["land_count"] / summary["total_count"]

    land_lst_mean = (
        work[work["land_mask"] & work["valid_lst"]]
        .groupby(["modis_row", "modis_col"])["lst"]
        .mean()
        .rename("land_lst_mean")
        .reset_index()
    )
    summary = summary.merge(land_lst_mean, on=["modis_row", "modis_col"], how="left")

    summary["modis_lst"] = summary.apply(lambda r: modis[int(r.modis_row), int(r.modis_col)], axis=1)
    summary.loc[summary["modis_lst"] == modis_nodata, "modis_lst"] = np.nan
    summary["residual"] = summary["land_lst_mean"] - summary["modis_lst"]

    summary["used_in_comparison"] = (
        (summary["land_fraction"] >= LAND_FRACTION_MIN)
        & summary["modis_lst"].notna()
        & summary["land_lst_mean"].notna()
    )

    used = summary[summary["used_in_comparison"]]
    n = len(used)
    if n >= 2:
        r, p = stats.pearsonr(used["land_lst_mean"], used["modis_lst"])
        rmse = np.sqrt(np.mean(used["residual"] ** 2))
    else:
        r, p, rmse = np.nan, np.nan, np.nan

    logger.info(
        f"Landsat-vs-MODIS pattern check: n={n} cells (land_fraction>={LAND_FRACTION_MIN}, "
        f"both sides valid), Pearson r={r:.4f} (p={p:.4f}), RMSE={rmse:.3f} degC"
    )
    if n < 30:
        logger.info(f"  n={n} is below 30 - illustrative only, not a statistically powerful result.")

    return summary, (r, p, rmse, n)


def correlation_matrix(land, logger):
    corr = land[["lst", "ndvi", "ndbi", "built_up"]].corr()
    logger.info(f"Correlation matrix (land cells only, n={len(land)}):\n{corr.to_string()}")
    return corr


def lst_by_landcover(land, logger):
    stats_table = land.groupby("lulc_class")["lst"].agg(
        count="count", mean="mean", std="std", min="min",
        q25=lambda s: s.quantile(0.25), median="median", q75=lambda s: s.quantile(0.75),
        max="max",
    ).reset_index()
    logger.info(f"LST by land cover (land cells only):\n{stats_table.to_string(index=False)}")
    return stats_table


def main():
    logger = utils.setup_logging()
    df = pd.read_parquet(FEATURES_PARQUET)
    land = df[df["land_mask"]]

    modis_summary, (r, p, rmse, n) = validate_modis(df, logger)
    corr = correlation_matrix(land, logger)
    landcover_stats = lst_by_landcover(land, logger)

    OUTPUTS_TABLES.mkdir(parents=True, exist_ok=True)
    modis_summary.to_csv(OUTPUTS_TABLES / "validation.csv", index=False)
    corr.to_csv(OUTPUTS_TABLES / "correlation_matrix.csv")
    landcover_stats.to_csv(OUTPUTS_TABLES / "lst_by_landcover.csv", index=False)
    logger.info("Wrote outputs/tables/{validation.csv, correlation_matrix.csv, lst_by_landcover.csv}")

    return modis_summary, corr, landcover_stats


if __name__ == "__main__":
    main()
