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
./.venv/Scripts/python.exe src/preprocess.py    # must run after grid.py
```

**Windows long-path note**: `jupyter`/`jupyterlab`/`geemap`/`earthengine-api`/`shap` fail to install as a full `pip install -r requirements.txt` on this machine — the project path plus jupyterlab's bundled JS asset filenames exceed the 260-char Windows path limit. The core pipeline packages (rasterio, geopandas, esda, libpysal, rioxarray, xarray, matplotlib, contextily, scikit-learn, pandas, numpy, pyyaml, pytest) install fine on their own and are sufficient for everything except actually opening a notebook. To use notebooks, enable Windows Long Path support first (Settings > System > For developers, or the `LongPathsEnabled` registry key), then retry the full install.

## Architecture

### Pipeline stages (folders map to methodology stages)

```
gee/ (composites+exports, DONE) -> src/grid -> src/preprocess -> src/features
  -> src/hotspots -> src/hvi -> src/validation -> src/viz
```

Data flow: `data/raw` (GEE exports, read-only, never modify) -> `data/interim` (aligned rasters) -> `data/processed` (feature table + grid). Tables to `outputs/tables/`, figures to `outputs/figures/`, final maps to `outputs/maps/`. **Nothing under `data/` or `outputs/` is version-controlled** (gitignored except `.gitkeep`) — outputs must be reproducible by re-running the pipeline, not committed.

Current `data/interim/` contents (all produced by `grid.py`/`preprocess.py`, all 134x81): `grid_reference.tif` (the alignment target), `lst_aligned.tif`, `ndvi_aligned.tif`, `ndbi_aligned.tif`, `worldcover_aligned.tif`, `worldpop_aligned.tif`, `ghsl_built_aligned.tif`, `land_mask.tif`, plus `modis_lst_native.tif` (kept at native 1km/EPSG:4326, deliberately *not* aligned to the grid). `data/processed/grid.gpkg` holds the same grid as a row/col-indexed polygon layer; `data/processed/features.parquet` is the row-per-cell feature table built by `features.py` (10,854 rows).

### The reference-grid pattern (established in `grid.py`/`preprocess.py`, follow it for any new raster work)

`grid.py` builds `data/interim/grid_reference.tif` — a minimal single-band raster whose transform/shape/CRS is the canonical target every other raster aligns to. `preprocess.py` then does exactly **one `rasterio.warp.reproject()` call per raster**, always passing `dst_transform`/`dst_crs`/`dst_shape` read from this reference file (never from another aligned raster or hand-computed bounds) — this is what guarantees every aligned layer shares identical pixel corners. Resampling method is chosen per raster type via a spec table (`preprocess.py`'s `RASTER_SPECS`), not a single global default: bilinear for continuous fields (LST/NDVI/NDBI/GHSL), `Resampling.mode` for WorldCover (does mode-aggregation + reproject in one warp — this GDAL build, 3.12.1, supports the mode kernel directly, so a separate two-step aggregate-then-reproject isn't needed), `Resampling.sum` for WorldPop (conserves population mass instead of averaging it away). None of the raw rasters carry a GDAL nodata tag, so every aligned output gets one set explicitly in its profile (-9999.0 for float layers, 255 for WorldCover).

**Verification convention**: both `check_raw_data.py` and `preprocess.py` verify by *re-opening the written file from disk* and reading its actual shape/nodata/values back — never by trusting the in-memory array that was just written. Follow this pattern for `features.py`/`hvi.py` outputs too.

One discovered quirk worth knowing: WorldCover's raw class 20 (shrubland) disappeared entirely after mode-aggregation to 100m — it was never the dominant class in any 10x10 block of 10m source pixels. Don't assume all raw WorldCover classes survive alignment.

### The feature-table pattern (established in `features.py`)

`features.py` flattens every aligned raster with `.ravel()` (row-major/C-order) and builds `cell_id = np.arange(height*width)` the same way — this matches `grid.py`'s polygon grid exactly (`cell_id = row*width + col`), so `cell_id` is a stable join key between `features.parquet` and `grid.gpkg` without needing a spatial join. Cell-centroid `x`/`y` (EPSG:32644) are derived directly from `grid_reference.tif`'s affine transform, not recomputed per-raster. Every aligned raster's nodata sentinel (-9999.0 / 255) is converted back to real NaN in the table (`to_nan()`) — raster nodata sentinels are a GeoTIFF-format necessity, not something pandas code downstream should have to remember to filter. Writing the parquet needs `pyarrow` (added to `requirements.txt`, installed separately from the rest — see Windows long-path note above, this one didn't hit that issue).

Two discovered data quirks worth knowing before writing `hvi.py`/`validation.py`:
- ~604 cells are WorldCover water (class 80) but carry valid WorldPop population data, tightly clustered along a narrow N-S band — almost certainly a Colombo canal/lagoon feature where WorldPop's disaggregation model attributes population to fringing settlements along water WorldCover classifies as class 80. Genuine disagreement between the two source datasets, not a bug — `land_mask` (not `pop_valid`) is what gates HEI/statistics, so this doesn't need special-casing.
- Land-only mean LST (41.08 degC) is notably warmer than the combined land+water mean (36.13 degC) and much warmer than water-only (30.29 degC) — expected, since ~47% of the AOI is cooler ocean/lagoon surface that would otherwise drag the mean down. This is exactly the effect land-masking is meant to produce.

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
| `hotspots.py` | stub | Global Moran's I + Getis-Ord Gi* on LST (via `esda`/`libpysal`), computed over land cells only. |
| `hvi.py` | stub | Combine `lst_z` (land-only), `pop_density`, `inv_ndvi` into HEI per the fixed formula; 5-class quantile classify. |
| `validation.py` | stub | Landsat-vs-MODIS aggregation/correlation, LST-by-landcover stats, LST/NDVI/NDBI/built-up correlation matrix — all land-only. |
| `viz.py` | stub | Final maps/figures only, reads from `outputs/tables`/`data/processed`. No computation. |

### Import convention

There's no `src/__init__.py` — `src` is not an installed/importable package. Scripts and tests add `src/` itself to `sys.path` and use bare imports of sibling modules (`import config`, `import utils`), matching `tests/test_pipeline.py`'s existing pattern. Follow this convention for any new `src/` module rather than introducing `from src import ...`-style imports.

### Notebooks vs `src/`

If code runs more than once or another module depends on its output, it belongs in `src/`. If it's disposable exploration/tuning feeding a one-off judgment call, it belongs in a notebook: `01_data_exploration` (calls `check_raw_data`, eyeballs raw rasters), `02_feature_analysis` (explores `features.parquet` before finalizing `validation.py`), `03_hvi_experiments` (tunes normalisation/class breaks before locking `hvi.py` defaults), `04_final_figures` (calls `viz.py`, does final caption/styling polish).

### Optional ML layer (out of scope until core pipeline is done)

`src/model.py` and `src/shap_analysis.py` are intentionally untracked (gitignored) and don't exist yet — see `src/_MODEL_LAYER_NOTE.md`. `config.yaml`'s `optional_model:` block is disabled by default. Only add these files if the core GIS/remote-sensing pipeline (grid through viz) is complete with time remaining.

### Decision logs

`reports/methodology_notes.md` (why: CRS/AOI/grid choices, date window, index framing, confirmed raster quirks) and `reports/experiment_log.md` (what changed/result/keep per run) are living documents — update them when making or discovering pipeline decisions, don't just leave changes in code/commit messages.
