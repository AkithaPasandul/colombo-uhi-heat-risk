"""Week 6 - final figures/maps with a consistent colour scheme.
LST, NDVI, hotspots, HEI (+ SHAP ranking if the model layer is added).
-> outputs/figures, outputs/maps

Read-only: no computation happens here. Everything is read straight from
data/processed/features.parquet, data/interim/*_aligned.tif, and
outputs/tables/*.csv - all already produced by earlier pipeline stages.

Sized for an ICTAR two-column paper: ~85mm single-column width (3.35in),
>=8pt fonts at final render size, 300 dpi. The four spatial maps share
one extent, a north arrow, a scale bar, and a colour-blind-safe palette
family throughout: viridis (sequential) for LST/NDVI/HEI, RdBu
(diverging) for Gi* and the correlation heatmap. Water/excluded cells
are always shown in neutral grey, never left blank - same convention as
every other output in this pipeline.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))
ROOT = SRC_DIR.parent

import numpy as np
import pandas as pd
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

import preprocess
import utils

PROCESSED_DIR = ROOT / "data" / "processed"
INTERIM_DIR = ROOT / "data" / "interim"
OUTPUTS_TABLES = ROOT / "outputs" / "tables"
OUTPUTS_FIGURES = ROOT / "outputs" / "figures"
OUTPUTS_MAPS = ROOT / "outputs" / "maps"

SINGLE_COL_WIDTH_IN = 3.35  # ~85mm
DPI = 300
WATER_GREY = "#a6a6a6"

WORLDCOVER_LABELS = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare/sparse", 70: "Snow/ice", 80: "Water",
    90: "Wetland", 95: "Mangroves", 100: "Moss/lichen",
}

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 8.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
})


def add_north_arrow(ax):
    # Upper-left sits over open water in this AOI's orientation, so the arrow never overlaps data.
    ax.annotate(
        "N", xy=(0.16, 0.90), xytext=(0.16, 0.78), xycoords="axes fraction",
        textcoords="axes fraction", ha="center", va="center", fontsize=8, fontweight="bold",
        arrowprops=dict(facecolor="black", edgecolor="black", width=2.5, headwidth=7, headlength=7),
    )


def add_scale_bar(ax, length_km=2):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    bar_x0 = x0 + 0.06 * (x1 - x0)
    bar_y = y0 + 0.05 * (y1 - y0)
    ax.plot([bar_x0, bar_x0 + length_km], [bar_y, bar_y], color="black", linewidth=2, solid_capstyle="butt")
    ax.text(bar_x0 + length_km / 2, bar_y + 0.015 * (y1 - y0), f"{length_km} km",
            ha="center", va="bottom", fontsize=8)


def grid_extent_km(ref):
    """Map extent in km (easting/northing), matching every map's shared extent."""
    t = ref["transform"]
    xmin, ymax = t.c, t.f
    xmax = xmin + ref["width"] * t.a
    ymin = ymax + ref["height"] * t.e
    return [xmin / 1000, xmax / 1000, ymin / 1000, ymax / 1000]


def read_aligned(path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    return arr


def plot_map(arr, ref, title, cmap, norm_or_range, cbar_label, out_name, cbar_ticks=None, cbar_ticklabels=None):
    extent = grid_extent_km(ref)
    height_in = SINGLE_COL_WIDTH_IN * (ref["height"] / ref["width"]) + 0.55
    fig, ax = plt.subplots(figsize=(SINGLE_COL_WIDTH_IN, height_in))

    # Grey out wherever this particular map's own data is undefined - not just water, but any
    # cell excluded for this map's own reason (e.g. HEI is also NaN for land cells with no
    # population data, which land_mask alone wouldn't catch).
    excluded_layer = np.where(np.isnan(arr), 1.0, np.nan)
    ax.imshow(excluded_layer, extent=extent, cmap=ListedColormap([WATER_GREY]), vmin=0, vmax=1, zorder=0)

    if isinstance(norm_or_range, BoundaryNorm):
        im = ax.imshow(arr, extent=extent, cmap=cmap, norm=norm_or_range, zorder=1)
    else:
        vmin, vmax = norm_or_range
        im = ax.imshow(arr, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, zorder=1)

    ax.set_title(title)
    ax.set_xlabel("Easting (km)")
    ax.set_ylabel("Northing (km)")
    cbar = fig.colorbar(im, ax=ax, shrink=0.75, pad=0.03)
    cbar.set_label(cbar_label, fontsize=8)
    if cbar_ticks is not None:
        cbar.set_ticks(cbar_ticks)
        cbar.set_ticklabels(cbar_ticklabels)
    cbar.ax.tick_params(labelsize=8)

    add_north_arrow(ax)
    add_scale_bar(ax)

    fig.tight_layout()
    out_path = OUTPUTS_MAPS / out_name
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_lst_map(ref, land_mask):
    lst = read_aligned(INTERIM_DIR / "lst_aligned.tif")
    lst_land = np.where(land_mask, lst, np.nan)
    vmin, vmax = np.nanmin(lst_land), np.nanmax(lst_land)
    return plot_map(lst_land, ref, "Land Surface Temperature", "viridis", (vmin, vmax),
                     "LST (°C)", "lst_map.png")


def make_ndvi_map(ref, land_mask):
    ndvi = read_aligned(INTERIM_DIR / "ndvi_aligned.tif")
    ndvi_land = np.where(land_mask, ndvi, np.nan)
    vmin, vmax = np.nanmin(ndvi_land), np.nanmax(ndvi_land)
    return plot_map(ndvi_land, ref, "NDVI", "viridis", (vmin, vmax),
                     "NDVI", "ndvi_map.png")


def make_gi_map(ref):
    hotspots = pd.read_csv(OUTPUTS_TABLES / "hotspots.csv").sort_values("cell_id")
    code_map = {"cold": 0, "ns": 1, "hot": 2}
    codes = hotspots["label"].map(code_map)
    arr = codes.to_numpy(dtype="float64").reshape((ref["height"], ref["width"]))

    cmap = ListedColormap(["#2166ac", "#f0f0f0", "#b2182b"])  # RdBu-family: cold / ns / hot
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)
    return plot_map(arr, ref, "Getis-Ord Gi* Hot/Cold Spots\n(FDR-corrected)", cmap, norm,
                     "", "hotspots_map.png", cbar_ticks=[0, 1, 2], cbar_ticklabels=["Cold", "Not sig.", "Hot"])


def make_hei_map(ref):
    with rasterio.open(OUTPUTS_MAPS / "hei_classified.tif") as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
    arr = np.where(arr == nodata, np.nan, arr)

    cmap = plt.get_cmap("viridis", 5)
    norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5, 5.5], cmap.N)
    return plot_map(arr, ref, "Heat Exposure Index\n(5-class)", cmap, norm,
                     "", "hei_map.png", cbar_ticks=[1, 2, 3, 4, 5],
                     cbar_ticklabels=["1 (low)", "2", "3", "4", "5 (high)"])


def make_correlation_heatmap():
    corr = pd.read_csv(OUTPUTS_TABLES / "correlation_matrix.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL_WIDTH_IN, SINGLE_COL_WIDTH_IN * 0.85))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index)
    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            val = corr.values[i, j]
            colour = "white" if abs(val) > 0.6 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color=colour)
    ax.set_title("Correlation matrix (land cells)")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.tick_params(labelsize=8)
    fig.tight_layout()
    out_path = OUTPUTS_FIGURES / "correlation_heatmap.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_landcover_boxplot():
    stats_df = pd.read_csv(OUTPUTS_TABLES / "lst_by_landcover.csv")
    stats_df = stats_df.sort_values("mean")

    box_stats = []
    labels = []
    for _, row in stats_df.iterrows():
        cls = int(row["lulc_class"])
        label = WORLDCOVER_LABELS.get(cls, str(cls))
        labels.append(f"{label}\n(n={int(row['count'])})")
        box_stats.append({
            "label": label,
            "whislo": row["min"], "q1": row["q25"], "med": row["median"],
            "q3": row["q75"], "whishi": row["max"], "fliers": [],
        })

    fig, ax = plt.subplots(figsize=(SINGLE_COL_WIDTH_IN, SINGLE_COL_WIDTH_IN * 0.9))
    bp = ax.bxp(box_stats, showfliers=False, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#7fb2d9")
        patch.set_edgecolor("black")
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("LST (°C)")
    ax.set_title("LST by land cover (land cells only)")
    fig.tight_layout()
    out_path = OUTPUTS_FIGURES / "lst_by_landcover_boxplot.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_hei_histogram():
    # A bar chart of per-class counts is tautological under quantile classification (all 5
    # classes are equal-count by construction) - show the continuous distribution instead, with
    # the 4 quantile cut points (20/40/60/80th percentile) that define the class boundaries.
    hei = pd.read_csv(OUTPUTS_TABLES / "hei_by_cell.csv")
    valid = hei["hei"].dropna()
    cut_points = valid.quantile([0.2, 0.4, 0.6, 0.8]).values

    fig, ax = plt.subplots(figsize=(SINGLE_COL_WIDTH_IN, SINGLE_COL_WIDTH_IN * 0.75))
    ax.hist(valid, bins=40, color="#440154", edgecolor="black", linewidth=0.3)
    for cp in cut_points:
        ax.axvline(cp, color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("HEI (continuous, minmax-normalised)")
    ax.set_ylabel("Number of cells")
    ax.set_title(f"HEI distribution (n={len(valid)})")
    fig.tight_layout()
    out_path = OUTPUTS_FIGURES / "hei_distribution_histogram.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    logger = utils.setup_logging()
    OUTPUTS_FIGURES.mkdir(parents=True, exist_ok=True)
    OUTPUTS_MAPS.mkdir(parents=True, exist_ok=True)

    ref = preprocess.load_reference()
    with rasterio.open(INTERIM_DIR / "land_mask.tif") as src:
        land_mask = src.read(1).astype(bool)

    paths = []
    paths.append(make_correlation_heatmap())
    paths.append(make_landcover_boxplot())
    paths.append(make_hei_histogram())
    paths.append(make_lst_map(ref, land_mask))
    paths.append(make_ndvi_map(ref, land_mask))
    paths.append(make_gi_map(ref))
    paths.append(make_hei_map(ref))

    for p in paths:
        logger.info(f"Wrote {p}")

    return paths


if __name__ == "__main__":
    main()
