"""Week 1 - raw-data audit, the reproducibility gate for the whole pipeline.

Reads all 7 raw rasters directly via rasterio (not the cached .aux.xml
stats, which can go stale after a re-export) and checks each against the
value ranges already confirmed by hand: LST/MODIS Celsius range, NDVI/NDBI
bounds, WorldCover class codes + native resolution, WorldPop non-negativity,
and GHSL's CRS (it's the only raw raster in Mollweide, not EPSG:4326).
None of the 7 files carry a GDAL nodata tag - they use bare NaN - so every
stat here is computed NaN-aware.

Run:  python src/check_raw_data.py
Out:  outputs/tables/raw_data_audit.csv
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

RAW_DIR = ROOT / "data" / "raw"
OUT_CSV = ROOT / "outputs" / "tables" / "raw_data_audit.csv"

# filename -> short key used to pick which checks apply below
RASTERS = {
    "colombo_lst_2024_dry_season.tif": "lst",
    "colombo_modis_lst_2024_dry_season.tif": "modis_lst",
    "colombo_ndvi_2024_dry_season.tif": "ndvi",
    "colombo_ndbi_2024_dry_season.tif": "ndbi",
    "colombo_worldcover_2021.tif": "worldcover",
    "colombo_worldpop_2020.tif": "worldpop",
    "colombo_ghsl_built_2020.tif": "ghsl_built",
}

KNOWN_WORLDCOVER_CODES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}


def read_stats(path):
    """Open one raster and compute NaN-aware summary stats (no GDAL nodata tag is set on any raw file)."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        valid = arr[~np.isnan(arr)]
        n_total = arr.size
        return {
            "file": path.name,
            "crs": str(src.crs),
            "res_x": src.res[0],
            "res_y": src.res[1],
            "width": src.width,
            "height": src.height,
            "bounds": str(tuple(round(b, 6) for b in src.bounds)),
            "nodata_tag": src.nodata,
            "dtype": src.dtypes[0],
            "valid_percent": round(100 * valid.size / n_total, 2) if n_total else 0.0,
            "min": float(valid.min()) if valid.size else float("nan"),
            "max": float(valid.max()) if valid.size else float("nan"),
            "mean": float(valid.mean()) if valid.size else float("nan"),
            "std": float(valid.std()) if valid.size else float("nan"),
        }


def check(logger, label, condition, detail, failures):
    status = "PASS" if condition else "FAIL"
    logger.info(f"  [{status}] {label}: {detail}")
    if not condition:
        failures.append(f"{label}: {detail}")


def run_checks(logger, key, path, stats, failures):
    check(logger, f"{key}: not entirely nodata/constant",
          stats["valid_percent"] > 0 and stats["min"] != stats["max"],
          f"valid%={stats['valid_percent']}, min={stats['min']}, max={stats['max']}", failures)

    if key in ("lst", "modis_lst"):
        check(logger, f"{key}: plausible Celsius range (20-55)",
              20 <= stats["min"] and stats["max"] <= 55,
              f"min={stats['min']:.2f} max={stats['max']:.2f}", failures)

    if key in ("ndvi", "ndbi"):
        check(logger, f"{key}: within [-1, 1]",
              stats["min"] >= -1.01 and stats["max"] <= 1.01,
              f"min={stats['min']:.3f} max={stats['max']:.3f}", failures)

    if key == "worldcover":
        with rasterio.open(path) as src:
            arr = src.read(1).astype("float64")
        uniq = set(np.unique(arr[~np.isnan(arr)]).astype(int).tolist())
        check(logger, "worldcover: values are known ESA codes",
              uniq.issubset(KNOWN_WORLDCOVER_CODES), f"unique values={sorted(uniq)}", failures)
        check(logger, "worldcover: native resolution ~10m (~0.00009 deg)",
              abs(stats["res_x"] - 0.00009) < 0.00002, f"res_x={stats['res_x']:.6f}", failures)

    if key == "worldpop":
        check(logger, "worldpop: non-negative", stats["min"] >= 0, f"min={stats['min']:.3f}", failures)

    if key == "ghsl_built":
        check(logger, "ghsl_built: in Mollweide (ESRI:54009), not EPSG:4326 like the others",
              "54009" in stats["crs"], f"crs={stats['crs']}", failures)
        check(logger, "ghsl_built: complete raster (no nodata)",
              stats["valid_percent"] >= 99.9, f"valid%={stats['valid_percent']}", failures)
    else:
        check(logger, f"{key}: CRS is EPSG:4326", stats["crs"] == "EPSG:4326", f"crs={stats['crs']}", failures)


def main():
    logger = utils.setup_logging()
    failures = []
    rows = []

    for filename, key in RASTERS.items():
        path = RAW_DIR / filename
        if not path.exists():
            failures.append(f"missing raw file: {filename}")
            logger.error(f"[FAIL] {filename} not found in data/raw/")
            continue

        stats = read_stats(path)
        rows.append(stats)

        logger.info(f"\n{filename}")
        logger.info(
            f"  crs={stats['crs']} res=({stats['res_x']:.6f}, {stats['res_y']:.6f}) "
            f"shape={stats['width']}x{stats['height']} valid%={stats['valid_percent']}"
        )
        logger.info(
            f"  min={stats['min']:.3f} max={stats['max']:.3f} "
            f"mean={stats['mean']:.3f} std={stats['std']:.3f}"
        )
        run_checks(logger, key, path, stats, failures)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    logger.info(f"\nWrote {OUT_CSV}")

    logger.info("=" * 60)
    if failures:
        logger.error(f"RAW DATA AUDIT: FAILED ({len(failures)} issue(s))")
        for f in failures:
            logger.error(f"  - {f}")
        return 1

    logger.info("RAW DATA AUDIT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
