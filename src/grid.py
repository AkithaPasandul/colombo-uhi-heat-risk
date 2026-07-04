"""Week 1 - build the 100 m analysis grid in the project CRS.
in : AOI boundary (data/external/cmc_boundary.geojson - its geometry is the
     fixed bbox, despite the filename) ; out: data/processed/grid.gpkg (the
     spine) + data/interim/grid_reference.tif (the transform/shape every
     other raster's reproject call in preprocess.py targets).
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import math

import geopandas as gpd
import numpy as np
import rasterio
from affine import Affine
from shapely.geometry import box

import config
import utils

AOI_PATH = ROOT / "data" / "external" / "cmc_boundary.geojson"
GRID_GPKG = ROOT / "data" / "processed" / "grid.gpkg"
GRID_REFERENCE_TIF = ROOT / "data" / "interim" / "grid_reference.tif"


def snap(value, res, direction):
    """Snap a coordinate outward to the nearest multiple of `res` so the grid fully covers the AOI."""
    if direction == "down":
        return math.floor(value / res) * res
    return math.ceil(value / res) * res


def build_reference_grid(cfg):
    """Reproject the AOI bbox to the project CRS and derive a clean, 100m-aligned grid transform/shape."""
    crs = cfg["project"]["crs"]
    res = cfg["project"]["grid_resolution_m"]

    aoi = gpd.read_file(AOI_PATH)
    if aoi.crs is None:
        aoi = aoi.set_crs("EPSG:4326")
    aoi_proj = aoi.to_crs(crs)

    xmin, ymin, xmax, ymax = aoi_proj.total_bounds
    xmin = snap(xmin, res, "down")
    ymin = snap(ymin, res, "down")
    xmax = snap(xmax, res, "up")
    ymax = snap(ymax, res, "up")

    width = int(round((xmax - xmin) / res))
    height = int(round((ymax - ymin) / res))
    transform = Affine(res, 0, xmin, 0, -res, ymax)

    return {
        "crs": crs,
        "res": res,
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "width": width,
        "height": height,
        "transform": transform,
    }


def build_grid_polygons(grid_def):
    """One square polygon per 100m cell, row/col indexed to match the reference raster's pixel grid."""
    res = grid_def["res"]
    xmin, ymax = grid_def["xmin"], grid_def["ymax"]
    width, height = grid_def["width"], grid_def["height"]

    rows, cols, geoms = [], [], []
    for row in range(height):
        cell_ymax = ymax - row * res
        cell_ymin = cell_ymax - res
        for col in range(width):
            cell_xmin = xmin + col * res
            cell_xmax = cell_xmin + res
            geoms.append(box(cell_xmin, cell_ymin, cell_xmax, cell_ymax))
            rows.append(row)
            cols.append(col)

    return gpd.GeoDataFrame(
        {"cell_id": range(len(geoms)), "row": rows, "col": cols, "geometry": geoms},
        crs=grid_def["crs"],
    )


def write_reference_raster(grid_def):
    """A minimal single-band raster whose transform/shape/CRS every preprocess.py reproject() call targets."""
    GRID_REFERENCE_TIF.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "count": 1,
        "width": grid_def["width"],
        "height": grid_def["height"],
        "crs": grid_def["crs"],
        "transform": grid_def["transform"],
        "nodata": 255,
    }
    with rasterio.open(GRID_REFERENCE_TIF, "w", **profile) as dst:
        dst.write(np.zeros((grid_def["height"], grid_def["width"]), dtype="uint8"), 1)


def main():
    logger = utils.setup_logging()
    cfg = config.load()

    grid_def = build_reference_grid(cfg)
    logger.info(
        f"Reference grid: {grid_def['width']} x {grid_def['height']} cells "
        f"({grid_def['width'] * grid_def['height']} total) at {grid_def['res']}m in {grid_def['crs']}"
    )
    logger.info(
        f"Bounds (snapped to {grid_def['res']}m): "
        f"xmin={grid_def['xmin']:.1f} ymin={grid_def['ymin']:.1f} "
        f"xmax={grid_def['xmax']:.1f} ymax={grid_def['ymax']:.1f}"
    )

    gdf = build_grid_polygons(grid_def)
    GRID_GPKG.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(GRID_GPKG, driver="GPKG")
    logger.info(f"Wrote {GRID_GPKG} ({len(gdf)} cells)")

    write_reference_raster(grid_def)
    logger.info(f"Wrote {GRID_REFERENCE_TIF} (reference transform/shape for preprocess.py)")

    return grid_def


if __name__ == "__main__":
    main()
