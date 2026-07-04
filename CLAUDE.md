# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Undergraduate research project: *Urban Heat Island Mapping and Heat Exposure/Risk Assessment for Colombo* using remote sensing + GIS. Scoped to ~36 working hours (weekends, 6 weeks) — keep additions simple and beginner-friendly, not production-grade. ML/SHAP driver attribution is an explicit stretch goal, out of scope for the core pipeline (see "Optional ML layer" below).

## Commands

```bash
# Environment (venv already created at .venv/ — recreate with `python -m venv .venv` if missing)
./.venv/Scripts/pip.exe install -r requirements.txt   # Git Bash
.venv\Scripts\pip.exe install -r requirements.txt      # PowerShell

# Tests (smoke tests only — a safety net, not a suite)
./.venv/Scripts/python.exe -m pytest -q

# Run any src/ module as a script (no package __init__.py — see Import convention below)
./.venv/Scripts/python.exe src/check_raw_data.py
./.venv/Scripts/python.exe src/grid.py         # must run before preprocess.py (builds grid_reference.tif)
./.venv/Scripts/python.exe src/preprocess.py   # must run after grid.py
./.venv/Scripts/python.exe src/features.py     # must run after preprocess.py
./.venv/Scripts/python.exe src/hvi.py          # must run after features.py
./.venv/Scripts/python.exe src/hotspots.py     # must run after features.py (independent of hvi.py)
./.venv/Scripts/python.exe src/validation.py   # must run after features.py
./.venv/Scripts/python.exe src/viz.py          # must run after hvi.py/hotspots.py/validation.py
```

**Windows long-path note**: `jupyter`/`jupyterlab`/`geemap`/`earthengine-api`/`shap` fail to install as a full `pip install -r requirements.txt` on this machine — the project path plus jupyterlab's bundled JS asset filenames exceed the 260-char Windows path limit. The core pipeline packages (rasterio, geopandas, esda, libpysal, rioxarray, xarray, matplotlib, contextily, scikit-learn, pandas, numpy, pyyaml, pytest) install fine on their own and are sufficient for everything except actually opening a notebook. To use notebooks, enable Windows Long Path support first (Settings > System > For developers, or the `LongPathsEnabled` registry key), then retry the full install.

## Architecture

### Pipeline stages (folders map to methodology stages)

```
gee/ -> src/grid -> src/preprocess -> src/features
  -> src/hotspots -> src/hvi -> src/validation -> src/viz   (all stages implemented)
```

Data flow: `data/raw` (GEE exports, read-only, never modify) -> `data/interim` (aligned rasters) -> `data/processed` (feature table + grid). Tables to `outputs/tables/`, figures to `outputs/figures/`, final maps to `outputs/maps/`. **Nothing under `data/` or `outputs/` is version-controlled** (gitignored except `.gitkeep`) — outputs must be reproducible by re-running the pipeline, not committed.

Current `data/interim/` contents (all produced by `grid.py`/`preprocess.py`, all 134x81): `grid_reference.tif` (the alignment target), `lst_aligned.tif`, `ndvi_aligned.tif`, `ndbi_aligned.tif`, `worldcover_aligned.tif`, `worldpop_aligned.tif`, `ghsl_built_aligned.tif`, `land_mask.tif`, plus `modis_lst_native.tif` (kept at native 1km/EPSG:4326, deliberately *not* aligned to the grid). `data/processed/grid.gpkg` holds the same grid as a row/col-indexed polygon layer; `data/processed/features.parquet` is the row-per-cell feature table built by `features.py` (10,854 rows).

### The reference-grid pattern (established in `grid.py`/`preprocess.py`, follow it for any new raster work)

`grid.py` builds `data/interim/grid_reference.tif` — a minimal single-band raster whose transform/shape/CRS is the canonical target every other raster aligns to. `preprocess.py` then does exactly **one `rasterio.warp.reproject()` call per raster**, always passing `dst_transform`/`dst_crs`/`dst_shape` read from this reference file (never from another aligned raster or hand-computed bounds) — this is what guarantees every aligned layer shares identical pixel corners. Resampling method is chosen per raster type via a spec table (`preprocess.py`'s `RASTER_SPECS`), not a single global default: bilinear for continuous fields (LST/NDVI/NDBI/GHSL), `Resampling.mode` for WorldCover (does mode-aggregation + reproject in one warp — this GDAL build, 3.12.1, supports the mode kernel directly, so a separate two-step aggregate-then-reproject isn't needed), `Resampling.sum` for WorldPop (conserves population mass instead of averaging it away). None of the raw rasters carry a GDAL nodata tag, so every aligned output gets one set explicitly in its profile (-9999.0 for float layers, 255 for WorldCover).

**Verification convention**: both `check_raw_data.py` and `preprocess.py` verify by *re-opening the written file from disk* and reading its actual shape/nodata/values back — never by trusting the in-memory array that was just written. Follow this pattern for `features.py`/`hvi.py` outputs too.

One discovered quirk worth knowing: WorldCover's raw class 20 (shrubland) disappeared entirely after mode-aggregation to 100m — it was never the dominant class in any 10x10 block of 10m source pixels. Don't assume all raw WorldCover classes survive alignment.

### The feature-table pattern (established in `features.py`)

`features.py` flattens every aligned raster with `.ravel()` (row-major/C-order) and builds `cell_id = np.arange(height*width)` the same way — this matches `grid.py`'s polygon grid exactly (`cell_id = row*width + col`), so `cell_id` is a stable join key between `features.parquet` and `grid.gpkg` without needing a spatial join. Cell-centroid `x`/`y` (EPSG:32644) are derived directly from `grid_reference.tif`'s affine transform, not recomputed per-raster. Every aligned raster's nodata sentinel (-9999.0 / 255) is converted back to real NaN in the table (`to_nan()`) — raster nodata sentinels are a GeoTIFF-format necessity, not something pandas code downstream should have to remember to filter. Writing the parquet needs `pyarrow` (added to `requirements.txt`, installed separately from the rest — see Windows long-path note above, this one didn't hit that issue).

Two discovered data quirks worth knowing:
- ~604 cells are WorldCover water (class 80) but carry valid WorldPop population data, tightly clustered along a narrow N-S band — almost certainly a Colombo canal/lagoon feature where WorldPop's disaggregation model attributes population to fringing settlements along water WorldCover classifies as class 80. Genuine disagreement between the two source datasets, not a bug — `land_mask` (not `pop_valid`) is what gates HEI/statistics, so this doesn't need special-casing.
- Land-only mean LST (41.08 degC) is notably warmer than the combined land+water mean (36.13 degC) and much warmer than water-only (30.29 degC) — expected, since ~47% of the AOI is cooler ocean/lagoon surface that would otherwise drag the mean down. This is exactly the effect land-masking is meant to produce.

### The analysis-module pattern (established in `hvi.py`/`hotspots.py`, follow it for `validation.py`)

Both import and reuse rather than reimplement: `hvi.py` does `import preprocess` to call `preprocess.load_reference()` for the grid transform/shape/CRS (needed to write `hei.tif`/`hei_classified.tif`), and reuses `utils.minmax()` rather than a local normalisation function. `utils.minmax()` was updated to guard against zero-range input (returns all-zero instead of NaN/inf) since the HEI plan required it — reuse this guarded version for any other normalisation, don't reimplement minmax locally.

Both also define an explicit **"analysis universe"** subset up front rather than filtering ad hoc throughout: `hvi.py`'s `valid` mask is `land_mask & pop_valid & lst_z.notna() & pop_density.notna() & inv_ndvi.notna()`; `hotspots.py`'s is `land_mask & valid_lst` (5,777 of 10,854 cells — land cells without a valid LST value, e.g. the 24 boundary cells, can't have a spatial statistic either). Output tables keep all 10,854 rows with NaN outside the analysis universe (same convention as `features.parquet`), rather than dropping excluded rows — do this for `validation.py` too.

`hotspots.py` builds Queen contiguity weights (`libpysal.weights.Queen.from_dataframe`) directly on the land+valid-LST polygon subset (joined from `grid.gpkg` by `cell_id`) rather than a distance band or the full grid — this is a regular 100m raster grid, so contiguity captures natural adjacency without an arbitrary distance threshold, and building from the land-only subset keeps water out of the weights matrix by construction. Getis-Ord Gi* uses `star=True` (Gi*, not Gi), binary weights (`transform="B"`), and `alternative="two-sided"` permutation p-values (esda's own recommendation over the legacy `"directed"` default) — both a naive `p<0.05` label and an FDR-corrected label (`esda.fdr`) are kept as separate columns (`label_raw` vs `label`) so multiple-testing inflation stays visible rather than silently corrected away.

Two more discovered quirks worth knowing:
- The HVI top-10 cells are *all* also significant Gi* hot spots (perfect overlap) — checked this isn't the HEI formula just echoing raw LST (it isn't: HEI top-10 only overlaps 7/10 with a pure-`lst_z` ranking, and `lst_z`/`pop_density` are meaningfully anti-correlated across the broader top-200). Explained by very strong global autocorrelation (Moran's I=0.80) plus this specific cluster being simultaneously extreme in heat and density.
- Significant cold spots are dominated by an eastern wetland/park cluster (~79.888E, 6.90-6.92N, likely Diyasaru/Beddagana wetland park in Kotte — WorldCover class 10, NDVI ~0.82-0.84) plus a smaller coastal-strip cluster (class 60 bare/sparse, likely beach sand, at the AOI's western edge).

### The MODIS cross-CRS aggregation pattern (established in `validation.py`)

`data/interim/modis_lst_native.tif` deliberately stays at native 1km/EPSG:4326 (never reprojected onto the 100m grid). To compare it against Landsat LST, `validation.py` goes the other direction: reprojects every 100m cell's centroid (`x`/`y` from `features.parquet`) to lon/lat via `pyproj.Transformer`, then uses the MODIS raster's own affine transform (inverted) to find which MODIS pixel each 100m cell falls into, and groups by that. Each MODIS block's Landsat-side value is the mean of **land-only** pixels in that block (never a naive all-pixel mean, which would reintroduce the same sea-surface mixing `land_mask` exists to prevent everywhere else), and blocks under 50% land are dropped entirely.

Discovered quirk: this land-fraction filter barely reduces the sample (69 -> 68), because MOD11A2 already excludes ocean-dominant blocks at the source (its own valid cells have mean land_fraction 0.94) — the two filters are mostly redundant, not additive. Don't assume a land-fraction filter will meaningfully shrink an already-small remote-sensing validation sample; check first.

### `viz.py` conventions (read-only figures/maps)

Every plotting function reads only from `features.parquet`, `data/interim/*_aligned.tif`, and `outputs/tables/*.csv` — no statistics are computed here that aren't already sitting in a CSV or raster from an earlier stage (e.g. the LST-by-landcover boxplot is built from `lst_by_landcover.csv`'s precomputed quantiles via `ax.bxp()`, not by re-deriving quantiles from `features.parquet`).

The four spatial maps (LST, NDVI, Gi* FDR classes, HEI 5-class) share one `plot_map()` helper for consistent extent/north-arrow/scale-bar/sizing. Its grey "excluded" underlay is keyed off **the plotted array's own NaN pattern** (`np.isnan(arr)`), not `land_mask` — a bug was caught where the HEI map showed white instead of grey over a land-but-no-population area, since `land_mask` alone doesn't know about HEI's other exclusion reasons (no WorldPop data, no valid LST, etc.). Reuse this NaN-based approach for any new map, not a `land_mask`-keyed one, unless the array's exclusions are provably identical to `land_mask`.

Sizing is hard-coded for an ICTAR two-column paper: `SINGLE_COL_WIDTH_IN = 3.35` (~85mm), `DPI = 300`, all `rcParams` font sizes >=8pt, every `savefig` call uses `bbox_inches="tight"` (needed — `fig.tight_layout()` alone left a large blank margin above the maps). If the target venue/column width changes, update these constants rather than hand-tuning individual figures.

One discovered quirk worth knowing: a bar chart of `hei_class` counts is tautological under quantile classification (5 equal-count classes by construction, always ~equal bars regardless of the data) — `hei_distribution_histogram.png` shows the continuous HEI value instead, with the 4 class-boundary quantile cut points as vertical lines. Don't add a per-class count bar chart back without the same caveat in mind.

The Colombo Port City reclamation area (western peninsula, ~79.823-79.845E, 6.924-6.951N) is a confirmed, checkable example of the raster year-mismatch limitation: 73% bare/sparse + 23% built-up land cover, near-zero NDVI, a real Gi* hot-spot concentration (20% of its cells), yet 30% of its cells carry WorldPop-2020 population despite the site's footprint changing substantially through continued reclamation since 2020. Useful concrete illustration if the paper's limitations section needs one.

### Fixed methodological decisions (do not reopen)

Set once in `config/config.yaml` (comment: "Locked project decisions... do not change"):
- CRS: EPSG:32644 (WGS84/UTM44N). 100m analysis grid.
- AOI (`aoi.boundary_path`) is a **rectangular bounding box**, not an administrative boundary, despite the file being named `data/external/cmc_boundary.geojson` and labeled historically after Colombo Municipal Council — its geometry is just the bbox rectangle. Report all stats as "within study bbox," never "within CMC."
- Heat Exposure Index: `HEI = minmax(lst_z * pop_density * (1 - ndvi))`, quantile-classified into 5 classes (`config.yaml`'s `hvi:` block). Called "Heat Exposure/Risk Index," never "Heat Vulnerability Index" — there's no socioeconomic/adaptive-capacity data.
- Raster year mismatch across layers (LST/NDVI/NDBI 2024, WorldCover 2021, WorldPop/GHSL 2020) is an accepted limitation, framed as "most-recent-available composite."

### Land masking is mandatory, not optional

~45% of the AOI bbox is ocean (WorldCover class 80). LST is valid data over water (not nodata), so computing `lst_z`, correlations, LST-by-landcover stats, or Getis-Ord Gi* over all pixels rather than land cells only would let sea-surface temperatures bias every land statistic. `features.parquet`'s `land_mask` column (`worldcover != 80 and != 255`, confirmed correct — excludes both true water and the WorldCover nodata-edge cells) is the single source of truth for this: every module past `features.py` must filter on it before computing statistics or HEI. Water/excluded cells stay in the table and are still rendered (as masked/nodata) on raw LST/hotspot maps — just never enter a statistic.

### Raw raster quirks (confirmed via `src/check_raw_data.py`, see `reports/methodology_notes.md` for full numbers)

- None of the 7 raw rasters carry a GDAL nodata tag — they use bare NaN. Read NaN-aware; when writing aligned outputs in `preprocess.py`, always set nodata explicitly in the raster profile.
- 6 of 7 raw rasters are EPSG:4326. **GHSL built-surface is the exception — natively ESRI:54009 (Mollweide)** — direct reproject to EPSG:32644, no averaging needed (native res already ~100m).
- WorldCover is natively ~10m — needs mode-aggregation to 100m *before* the nearest-neighbour reproject (never bilinear/average — it's categorical).
- WorldPop is a population **count**, not a density — sum-aggregate to 100m cells, never resample/interpolate (a cell is exactly 1 hectare, so the summed count *is* people/hectare).
- MODIS LST stays at native 1km and is only used in `validation.py` as a coarse pattern/consistency check (Landsat aggregated up to meet it) — never as pixel-level ground truth; effective sample is ~69 valid cells over this AOI.

### `src/` module responsibilities

| File | Status | Responsibility |
|---|---|---|
| `config.py` | implemented | Load `config/config.yaml`. Pure loader, no logic. |
| `utils.py` | implemented | `setup_logging()` (wires `config/logging.yaml`, console+file handlers to `outputs/run.log`), `minmax()`. Cross-cutting helpers only — no domain logic. |
| `check_raw_data.py` | implemented | Raw-data audit gate — NaN-aware stats + assertions on all 7 rasters, writes `outputs/tables/raw_data_audit.csv`. Run this before trusting any preprocessing decision. |
| `grid.py` | implemented | Builds the 100m reference grid (EPSG:32644) from `data/external/cmc_boundary.geojson`'s bbox geometry, bounds snapped outward to clean 100m multiples. Outputs `data/processed/grid.gpkg` (polygon grid) + `data/interim/grid_reference.tif` (the reproject target). Current AOI resolves to **81 x 134 cells**. |
| `preprocess.py` | implemented | Aligns all 7 raw rasters onto `grid_reference.tif` (see "reference-grid pattern" above) and derives `land_mask` from aligned WorldCover (`!= 80` and `!= 255`). Never touches `data/raw/`. Verified: land ~53%/water ~47%, WorldPop mass conserved within ~0.7%. |
| `features.py` | implemented | Stacks aligned rasters into `data/processed/features.parquet` (10,854 rows): `cell_id, x, y, lst, ndvi, ndbi, built_up, lulc_class, pop_count, pop_density, valid_lst, pop_valid, land_mask`. No `elevation`/`dist_water` — no SRTM raster was exported, only ever needed for the deferred ML layer. The single contract every downstream module reads. |
| `hotspots.py` | implemented | Global Moran's I (0.7978, p=0.001) + Getis-Ord Gi* on LST, Queen weights on the land+valid-LST subset (5,777 cells). Outputs `outputs/tables/hotspots.csv` + `outputs/maps/hotspots.gpkg` (both/uncorrected and FDR-corrected labels). |
| `hvi.py` | implemented | Combines `lst_z` (land-only z-score), `pop_density`, `inv_ndvi` into HEI per the fixed formula; 5-class quantile classify. 5,391 valid cells. Outputs `outputs/tables/hei_by_cell.csv`, `outputs/maps/hei.tif`, `outputs/maps/hei_classified.tif`. |
| `validation.py` | implemented | Landsat-vs-MODIS pattern check (land-only block aggregation, n=68, r=0.234), LST-by-landcover stats, LST/NDVI/NDBI/built-up correlation matrix — all land-only. Outputs `outputs/tables/{validation,correlation_matrix,lst_by_landcover}.csv`. |
| `viz.py` | implemented | Final maps/figures only, reads from `outputs/tables`/`data/interim`/`features.parquet`. No computation. Sized for an ICTAR two-column paper (~85mm width, >=8pt fonts, 300dpi). Outputs 3 figures + 4 maps (see "viz.py conventions" below). |

### Import convention

There's no `src/__init__.py` — `src` is not an installed/importable package. Scripts and tests add `src/` itself to `sys.path` and use bare imports of sibling modules (`import config`, `import utils`), matching `tests/test_pipeline.py`'s existing pattern. Follow this convention for any new `src/` module rather than introducing `from src import ...`-style imports.

### Notebooks vs `src/`

If code runs more than once or another module depends on its output, it belongs in `src/`. If it's disposable exploration/tuning feeding a one-off judgment call, it belongs in a notebook: `01_data_exploration` (calls `check_raw_data`, eyeballs raw rasters), `02_feature_analysis` (explores `features.parquet` before finalizing `validation.py`), `03_hvi_experiments` (tunes normalisation/class breaks before locking `hvi.py` defaults), `04_final_figures` (calls `viz.py`, does final caption/styling polish).

### Optional ML layer (out of scope until core pipeline is done)

`src/model.py` and `src/shap_analysis.py` are intentionally untracked (gitignored) and don't exist yet — see `src/_MODEL_LAYER_NOTE.md`. `config.yaml`'s `optional_model:` block is disabled by default. Only add these files if the core GIS/remote-sensing pipeline (grid through viz) is complete with time remaining.

### Decision logs

`reports/methodology_notes.md` (why: CRS/AOI/grid choices, date window, index framing, confirmed raster quirks) and `reports/experiment_log.md` (what changed/result/keep per run) are living documents — update them when making or discovering pipeline decisions, don't just leave changes in code/commit messages.
