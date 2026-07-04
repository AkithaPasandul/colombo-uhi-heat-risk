"""Week 4 - Heat-Exposure / Risk Index.
HEI = minmax( lst_z * pop_density * (1 - ndvi) ); quantile-classify.
NOTE: exposure/risk, not full vulnerability, unless adaptive capacity is added.
in : features.parquet ; out: outputs/tables/hei_by_cell.csv,
     outputs/maps/hei.tif, outputs/maps/hei_classified.tif

lst_z is computed from land cells only (land_mask==True, lst not NaN) -
sea-surface LST would otherwise bias the mean/std used for standardisation.
inv_ndvi = 1 - ndvi is NOT clipped: NDVI can go negative on bare/wet land
surfaces, so inv_ndvi can legitimately exceed 1. HEI is NaN wherever
land_mask is False, pop_valid is False, or any of the three components is
NaN - never computed from the remaining two. minmax (utils.minmax) is
applied once, to the final product, and guards against zero range.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import numpy as np
import pandas as pd
import rasterio

import preprocess
import utils

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUTS_TABLES = ROOT / "outputs" / "tables"
OUTPUTS_MAPS = ROOT / "outputs" / "maps"
FEATURES_PARQUET = PROCESSED_DIR / "features.parquet"

FLOAT_NODATA = -9999.0
CLASS_NODATA = 255
N_CLASSES = 5

OUT_COLUMNS = [
    "cell_id", "x", "y", "land_mask", "pop_valid",
    "lst", "ndvi", "lst_z", "inv_ndvi", "pop_density",
    "hei_raw", "hei", "hei_class",
]


def compute_lst_z(df):
    """z-score LST using land cells only; broadcast to every row (irrelevant for cells excluded later)."""
    land_valid = df["land_mask"] & df["lst"].notna()
    mean = df.loc[land_valid, "lst"].mean()
    std = df.loc[land_valid, "lst"].std()
    return (df["lst"] - mean) / std, mean, std


def build_hvi(df, logger):
    df = df.copy()
    df["lst_z"], lst_mean, lst_std = compute_lst_z(df)
    df["inv_ndvi"] = 1 - df["ndvi"]

    logger.info(f"lst_z computed from land cells only: mean(land)={lst_mean:.4f} std(land)={lst_std:.4f}")

    valid = (
        df["land_mask"]
        & df["pop_valid"]
        & df["lst_z"].notna()
        & df["pop_density"].notna()
        & df["inv_ndvi"].notna()
    )

    df["hei_raw"] = np.nan
    df.loc[valid, "hei_raw"] = (
        df.loc[valid, "lst_z"] * df.loc[valid, "pop_density"] * df.loc[valid, "inv_ndvi"]
    )

    df["hei"] = np.nan
    df.loc[valid, "hei"] = utils.minmax(df.loc[valid, "hei_raw"])

    df["hei_class"] = np.nan
    if valid.sum() > 0:
        df.loc[valid, "hei_class"] = pd.qcut(
            df.loc[valid, "hei"], N_CLASSES, labels=range(1, N_CLASSES + 1)
        ).astype(int)

    return df, valid


def write_raster(path, values_flat, ref, dtype, nodata):
    arr = values_flat.reshape((ref["height"], ref["width"])).astype(dtype)
    profile = {
        "driver": "GTiff", "dtype": dtype, "count": 1,
        "width": ref["width"], "height": ref["height"],
        "crs": ref["crs"], "transform": ref["transform"], "nodata": nodata,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)


def main():
    logger = utils.setup_logging()
    ref = preprocess.load_reference()

    df = pd.read_parquet(FEATURES_PARQUET)
    df, valid = build_hvi(df, logger)
    logger.info(f"Valid HEI cells: {int(valid.sum())} / {len(df)}")

    OUTPUTS_TABLES.mkdir(parents=True, exist_ok=True)
    hei_csv = OUTPUTS_TABLES / "hei_by_cell.csv"
    df[OUT_COLUMNS].to_csv(hei_csv, index=False)
    logger.info(f"Wrote {hei_csv} ({len(df)} rows)")

    hei_flat = df["hei"].fillna(FLOAT_NODATA).to_numpy()
    write_raster(OUTPUTS_MAPS / "hei.tif", hei_flat, ref, "float32", FLOAT_NODATA)

    class_flat = df["hei_class"].fillna(CLASS_NODATA).to_numpy()
    write_raster(OUTPUTS_MAPS / "hei_classified.tif", class_flat, ref, "uint8", CLASS_NODATA)
    logger.info(f"Wrote {OUTPUTS_MAPS / 'hei.tif'} and {OUTPUTS_MAPS / 'hei_classified.tif'}")

    return df, valid


if __name__ == "__main__":
    main()
