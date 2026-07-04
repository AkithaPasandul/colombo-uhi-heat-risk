"""Week 2 - assemble the feature stack (one row per grid cell).
in : data/interim/*_aligned.tif + land_mask.tif
out: data/processed/features.parquet with columns cell_id, x, y, lst, ndvi,
     ndbi, built_up, lulc_class, pop_count, pop_density, valid_lst,
     pop_valid, land_mask. Everything downstream reads this table.

No elevation/dist_water columns - no SRTM raster was ever exported, and
they were only ever needed for the deferred ML stretch goal (see
src/_MODEL_LAYER_NOTE.md).

Each aligned raster's nodata sentinel (-9999.0 for continuous/count
layers, 255 for WorldCover) is converted back to real NaN here - the
sentinel is a GeoTIFF-file necessity, not something later pandas code
should have to remember to filter out.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import numpy as np
import pandas as pd
import rasterio

import utils

INTERIM_DIR = ROOT / "data" / "interim"
PROCESSED_DIR = ROOT / "data" / "processed"
FEATURES_PARQUET = PROCESSED_DIR / "features.parquet"


def read_band(path):
    with rasterio.open(path) as src:
        return src.read(1), src.nodata


def to_nan(arr, nodata):
    """Replace the raster's nodata sentinel with real NaN for the tabular feature layer."""
    arr = arr.astype("float64")
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    return arr


def build_features():
    with rasterio.open(INTERIM_DIR / "grid_reference.tif") as ref:
        transform = ref.transform
        height, width = ref.height, ref.width

    rows, cols = np.indices((height, width))
    rows = rows.ravel()
    cols = cols.ravel()
    cell_id = np.arange(height * width)

    # Cell-centroid coordinates in the project CRS (EPSG:32644)
    x = transform.c + (cols + 0.5) * transform.a
    y = transform.f + (rows + 0.5) * transform.e

    lst_arr, lst_nodata = read_band(INTERIM_DIR / "lst_aligned.tif")
    ndvi_arr, ndvi_nodata = read_band(INTERIM_DIR / "ndvi_aligned.tif")
    ndbi_arr, ndbi_nodata = read_band(INTERIM_DIR / "ndbi_aligned.tif")
    built_arr, built_nodata = read_band(INTERIM_DIR / "ghsl_built_aligned.tif")
    lulc_arr, lulc_nodata = read_band(INTERIM_DIR / "worldcover_aligned.tif")
    pop_arr, pop_nodata = read_band(INTERIM_DIR / "worldpop_aligned.tif")
    land_arr, _ = read_band(INTERIM_DIR / "land_mask.tif")

    lst = to_nan(lst_arr, lst_nodata).ravel()
    ndvi = to_nan(ndvi_arr, ndvi_nodata).ravel()
    ndbi = to_nan(ndbi_arr, ndbi_nodata).ravel()
    built_up = to_nan(built_arr, built_nodata).ravel()
    lulc_class = to_nan(lulc_arr, lulc_nodata).ravel()
    pop_count = to_nan(pop_arr, pop_nodata).ravel()
    pop_density = pop_count.copy()  # each cell is exactly 100m x 100m = 1 hectare
    land_mask = land_arr.ravel().astype(bool)

    valid_lst = ~np.isnan(lst)
    pop_valid = ~np.isnan(pop_count)

    return pd.DataFrame({
        "cell_id": cell_id,
        "x": x,
        "y": y,
        "lst": lst,
        "ndvi": ndvi,
        "ndbi": ndbi,
        "built_up": built_up,
        "lulc_class": lulc_class,
        "pop_count": pop_count,
        "pop_density": pop_density,
        "valid_lst": valid_lst,
        "pop_valid": pop_valid,
        "land_mask": land_mask,
    })


def main():
    logger = utils.setup_logging()
    df = build_features()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(FEATURES_PARQUET, index=False)
    logger.info(f"Wrote {FEATURES_PARQUET} ({len(df)} rows, {len(df.columns)} columns)")

    return df


if __name__ == "__main__":
    main()
