"""Week 3 - spatial clustering of LST.
Global Moran's I (is clustering real?) + Getis-Ord Gi* (where).
in : features.parquet + grid.gpkg ; out: outputs/tables/hotspots.csv + Gi*
     column, outputs/maps/hotspots.gpkg

Weights: Queen contiguity built directly on the land+valid-LST cell
polygons (not a distance band). The analysis unit is a genuine regular
100m grid, not irregular points, so contiguity captures the natural
raster adjacency (up to 8 neighbours: 4 edge + 4 corner) without needing
an arbitrary distance threshold - a ~150m fixed-distance band would give
almost the same structure here anyway, since the diagonal neighbour
distance is exactly 100*sqrt(2)=141.4m. Building weights straight from
the land-only polygon subset also guarantees water cells never enter the
weights matrix, by construction, rather than needing to filter a
centroid-distance matrix afterwards.

Gi* uses star=True (include the focal cell, i.e. Getis-Ord Gi* not Gi)
and a permutation-based, two-sided p-value (esda's own recommendation
over the 'directed' default). FDR correction (esda.fdr) is reported
alongside the naive uncorrected count so the multiple-testing inflation
is visible, not just corrected away silently.
"""
import sys
import warnings
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import numpy as np
import pandas as pd
import geopandas as gpd
from libpysal.weights import Queen
from esda.moran import Moran
from esda.getisord import G_Local
from esda import fdr as esda_fdr

import utils

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUTS_TABLES = ROOT / "outputs" / "tables"
OUTPUTS_MAPS = ROOT / "outputs" / "maps"
FEATURES_PARQUET = PROCESSED_DIR / "features.parquet"
GRID_GPKG = PROCESSED_DIR / "grid.gpkg"

ALPHA = 0.05
PERMUTATIONS = 999
SEED = 12345


def load_analysis_universe():
    """Land cells with valid LST only - the universe for Moran's I / Gi*."""
    df = pd.read_parquet(FEATURES_PARQUET)
    grid = gpd.read_file(GRID_GPKG)[["cell_id", "geometry"]]
    gdf = grid.merge(df, on="cell_id", how="left")
    analysis = gdf[gdf["land_mask"] & gdf["valid_lst"]].reset_index(drop=True)
    return gdf, analysis


def build_weights(analysis, logger):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w = Queen.from_dataframe(analysis, use_index=False)
        for warning in caught:
            logger.info(f"  (libpysal) {warning.message}")

    logger.info(
        f"Queen weights on {w.n} land+valid-LST cells: "
        f"{len(w.islands)} islands (zero-neighbour cells), "
        f"{w.n_components} connected component(s)"
    )
    if w.islands:
        logger.info(f"  island cell_ids (no neighbours): {analysis.loc[w.islands, 'cell_id'].tolist()}")
    return w


def run_moran(y, w, logger):
    moran = Moran(y, w, permutations=PERMUTATIONS)
    logger.info(f"Global Moran's I = {moran.I:.4f} (expected under null = {moran.EI:.6f}), p_sim = {moran.p_sim:.4f}")
    return moran


def run_gi_star(y, w, logger):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # same disconnected-components warning as build_weights, already logged there
        gi = G_Local(y, w, transform="B", star=True, permutations=PERMUTATIONS, seed=SEED, alternative="two-sided")

    label_raw = np.full(len(y), "ns", dtype=object)
    label_raw[(gi.Zs > 0) & (gi.p_sim < ALPHA)] = "hot"
    label_raw[(gi.Zs < 0) & (gi.p_sim < ALPHA)] = "cold"

    fdr_cutoff = esda_fdr(gi.p_sim, ALPHA)
    label_fdr = np.full(len(y), "ns", dtype=object)
    label_fdr[(gi.Zs > 0) & (gi.p_sim < fdr_cutoff)] = "hot"
    label_fdr[(gi.Zs < 0) & (gi.p_sim < fdr_cutoff)] = "cold"

    logger.info(
        f"Gi* uncorrected (p<{ALPHA}): hot={(label_raw == 'hot').sum()} "
        f"cold={(label_raw == 'cold').sum()} ns={(label_raw == 'ns').sum()}"
    )
    logger.info(
        f"Gi* FDR-corrected (p<{fdr_cutoff:.5f}): hot={(label_fdr == 'hot').sum()} "
        f"cold={(label_fdr == 'cold').sum()} ns={(label_fdr == 'ns').sum()}"
    )
    return gi, label_raw, label_fdr, fdr_cutoff


def main():
    logger = utils.setup_logging()
    gdf, analysis = load_analysis_universe()
    logger.info(f"Analysis universe (land_mask & valid_lst): {len(analysis)} / {len(gdf)} cells")

    w = build_weights(analysis, logger)
    y = analysis["lst"].to_numpy()

    moran = run_moran(y, w, logger)
    gi, label_raw, label_fdr, fdr_cutoff = run_gi_star(y, w, logger)

    analysis["gi_z"] = gi.Zs
    analysis["p"] = gi.p_sim
    analysis["label_raw"] = label_raw
    analysis["label"] = label_fdr

    out_cols = ["cell_id", "gi_z", "p", "label_raw", "label"]
    result = gdf.merge(analysis[out_cols], on="cell_id", how="left")

    OUTPUTS_TABLES.mkdir(parents=True, exist_ok=True)
    hotspots_csv = OUTPUTS_TABLES / "hotspots.csv"
    result[["cell_id", "x", "y", "lst", "gi_z", "p", "label_raw", "label"]].to_csv(hotspots_csv, index=False)
    logger.info(f"Wrote {hotspots_csv} ({len(result)} rows)")

    OUTPUTS_MAPS.mkdir(parents=True, exist_ok=True)
    hotspots_gpkg = OUTPUTS_MAPS / "hotspots.gpkg"
    result[["cell_id", "geometry", "gi_z", "p", "label_raw", "label"]].to_file(hotspots_gpkg, driver="GPKG")
    logger.info(f"Wrote {hotspots_gpkg}")

    return moran, gi, result


if __name__ == "__main__":
    main()
