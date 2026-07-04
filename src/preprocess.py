"""Week 1-2 - align every exported raster to the grid CRS/resolution.
in : data/raw/*.tif ; out: data/interim/*_aligned.tif

One rasterio.warp.reproject() call per raster, all targeting the transform/
shape/CRS of data/interim/grid_reference.tif (built by grid.py). WorldCover
uses Resampling.mode (mode-aggregate + reproject in a single warp - GDAL's
mode kernel picks the dominant class among the source pixels overlapping
each destination cell, which is the same result as aggregating then
nearest-reprojecting, done in one pass since this GDAL build supports it).
WorldPop uses Resampling.sum to conserve population mass rather than
averaging it away. MODIS stays at native 1km/EPSG:4326 - copied over with
an explicit nodata tag, never resampled onto the 100m grid. None of the raw
rasters carry a GDAL nodata tag (bare NaN), so NaN is passed explicitly as
src_nodata wherever a raster actually has gaps.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

import utils

RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
REFERENCE_TIF = INTERIM_DIR / "grid_reference.tif"

FLOAT_NODATA = -9999.0
WORLDCOVER_NODATA = 255
WATER_CLASS = 80
KNOWN_WORLDCOVER_CLASSES = {10, 20, 30, 40, 50, 60, 80, 90}

# key -> (raw filename, resampling method, src has NaN gaps?, output dtype, output nodata)
RASTER_SPECS = {
    "lst": ("colombo_lst_2024_dry_season.tif", Resampling.bilinear, True, "float32", FLOAT_NODATA),
    "ndvi": ("colombo_ndvi_2024_dry_season.tif", Resampling.bilinear, True, "float32", FLOAT_NODATA),
    "ndbi": ("colombo_ndbi_2024_dry_season.tif", Resampling.bilinear, True, "float32", FLOAT_NODATA),
    "worldcover": ("colombo_worldcover_2021.tif", Resampling.mode, False, "uint8", WORLDCOVER_NODATA),
    "worldpop": ("colombo_worldpop_2020.tif", Resampling.sum, True, "float32", FLOAT_NODATA),
    "ghsl_built": ("colombo_ghsl_built_2020.tif", Resampling.bilinear, False, "float32", FLOAT_NODATA),
}


def load_reference():
    with rasterio.open(REFERENCE_TIF) as ref:
        return {"crs": ref.crs, "transform": ref.transform, "width": ref.width, "height": ref.height}


def align(src_path, dst_path, ref, resampling, has_nan, out_dtype, out_nodata):
    """Read src_path, warp it onto ref's transform/shape/CRS in one reproject() call, write dst_path."""
    with rasterio.open(src_path) as src:
        src_arr = src.read(1)
        src_transform, src_crs = src.transform, src.crs

    src_nodata = np.nan if has_nan else None
    dst_arr = np.full((ref["height"], ref["width"]), out_nodata, dtype=out_dtype)

    reproject(
        source=src_arr,
        destination=dst_arr,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=ref["transform"],
        dst_crs=ref["crs"],
        dst_nodata=out_nodata,
        resampling=resampling,
    )

    profile = {
        "driver": "GTiff", "dtype": out_dtype, "count": 1,
        "width": ref["width"], "height": ref["height"],
        "crs": ref["crs"], "transform": ref["transform"], "nodata": out_nodata,
    }
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(dst_arr, 1)

    return dst_arr


def copy_modis_native(logger):
    """MODIS stays at native 1km/EPSG:4326 - just clean up the nodata tag, no resampling onto the grid."""
    src_path = RAW_DIR / "colombo_modis_lst_2024_dry_season.tif"
    dst_path = INTERIM_DIR / "modis_lst_native.tif"

    with rasterio.open(src_path) as src:
        arr = src.read(1).astype("float32")
        profile = src.profile.copy()

    arr = np.where(np.isnan(arr), FLOAT_NODATA, arr)
    profile.update(dtype="float32", nodata=FLOAT_NODATA)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(arr, 1)

    logger.info(f"Copied MODIS LST natively (no resample) -> {dst_path}")


def write_land_mask(worldcover_arr, ref, logger):
    """land_mask = True where WorldCover is valid land (not water, not nodata). Every cell gets a definitive value."""
    land_mask = (worldcover_arr != WATER_CLASS) & (worldcover_arr != WORLDCOVER_NODATA)
    path = INTERIM_DIR / "land_mask.tif"
    profile = {
        "driver": "GTiff", "dtype": "uint8", "count": 1,
        "width": ref["width"], "height": ref["height"],
        "crs": ref["crs"], "transform": ref["transform"],
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(land_mask.astype("uint8"), 1)
    logger.info(f"Wrote {path} (land fraction={100 * land_mask.mean():.2f}%)")
    return land_mask


def verify(logger):
    """Re-open every written file from disk (not the in-memory arrays) and check the five numbers requested."""
    checks = []

    def record(label, ok, detail):
        logger.info(f"  [{'PASS' if ok else 'FAIL'}] {label}: {detail}")
        checks.append((label, ok))

    logger.info("\n--- Check 1: shapes + nodata, read back from disk ---")
    aligned_paths = {k: INTERIM_DIR / f"{k}_aligned.tif" for k in RASTER_SPECS}
    aligned_paths["land_mask"] = INTERIM_DIR / "land_mask.tif"
    for key, path in aligned_paths.items():
        with rasterio.open(path) as src:
            shape = (src.height, src.width)
            record(f"shape[{key}]", shape == (134, 81), f"shape={shape[0]}x{shape[1]} nodata={src.nodata}")

    logger.info("\n--- Check 2: land fraction from land_mask ---")
    with rasterio.open(INTERIM_DIR / "land_mask.tif") as src:
        land_mask = src.read(1).astype(bool)
    land_pct = 100 * land_mask.sum() / land_mask.size
    record("land_fraction", 45 <= land_pct <= 65,
           f"land={land_pct:.2f}% water={100 - land_pct:.2f}% (expected ~55% land / ~45% water)")

    logger.info("\n--- Check 3: WorldPop mass conservation (raw sum vs aligned sum) ---")
    with rasterio.open(RAW_DIR / "colombo_worldpop_2020.tif") as src:
        raw_sum = np.nansum(src.read(1).astype("float64"))
    with rasterio.open(INTERIM_DIR / "worldpop_aligned.tif") as src:
        aligned = src.read(1).astype("float64")
        aligned_sum = aligned[aligned != src.nodata].sum()
    pct_diff = 100 * abs(aligned_sum - raw_sum) / raw_sum
    record("worldpop_mass", pct_diff <= 2.0,
           f"raw_sum={raw_sum:.1f} aligned_sum={aligned_sum:.1f} diff={pct_diff:.2f}% (expected <=2%)")

    logger.info("\n--- Check 4: aligned LST range over land cells only ---")
    with rasterio.open(INTERIM_DIR / "lst_aligned.tif") as src:
        lst = src.read(1)
        lst_nodata = src.nodata
    land_lst = lst[land_mask & (lst != lst_nodata)]
    lst_min, lst_max = float(land_lst.min()), float(land_lst.max())
    record("lst_range_land_only", 28 <= lst_min and lst_max <= 50,
           f"min={lst_min:.2f} max={lst_max:.2f} (expected ~28-50 degC)")

    logger.info("\n--- Check 5: WorldCover unique values (excluding nodata sentinel) ---")
    with rasterio.open(INTERIM_DIR / "worldcover_aligned.tif") as src:
        wc = src.read(1)
        wc_nodata = src.nodata
    uniq = set(np.unique(wc[wc != wc_nodata]).tolist())
    extra = uniq - KNOWN_WORLDCOVER_CLASSES
    record("worldcover_classes", not extra,
           f"unique={sorted(uniq)} unexpected={sorted(extra) if extra else 'none'}")

    return checks


def main():
    logger = utils.setup_logging()
    ref = load_reference()
    logger.info(f"Reference grid: {ref['width']}x{ref['height']} in {ref['crs']}")

    worldcover_arr = None
    for key, (filename, resampling, has_nan, out_dtype, out_nodata) in RASTER_SPECS.items():
        arr = align(RAW_DIR / filename, INTERIM_DIR / f"{key}_aligned.tif", ref,
                    resampling, has_nan, out_dtype, out_nodata)
        logger.info(f"Aligned {key} ({resampling.name}) -> data/interim/{key}_aligned.tif, shape={arr.shape}")
        if key == "worldcover":
            worldcover_arr = arr

    copy_modis_native(logger)
    write_land_mask(worldcover_arr, ref, logger)

    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION")
    checks = verify(logger)

    failures = [label for label, ok in checks if not ok]
    logger.info("\n" + "=" * 60)
    if failures:
        logger.error(f"PREPROCESS VERIFICATION FAILED ({len(failures)}): {failures}")
        return 1
    logger.info("PREPROCESS VERIFICATION: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
