# Colombo UHI & Heat Exposure

Code for *Urban Heat Island Mapping and Heat Vulnerability Assessment for Colombo Using
Remote Sensing and GIS*. A compact, ~36-working-hour GIS + remote sensing pipeline that
turns Landsat/MODIS imagery and open geospatial datasets into a heat-exposure index and
hotspot map for Colombo, Sri Lanka.

## Overview

The project quantifies the Urban Heat Island (UHI) effect in Colombo and links it to
population exposure. It follows a linear, reproducible pipeline:

1. Collect satellite imagery and auxiliary layers via Google Earth Engine.
2. Build a fixed 100 m analysis grid over the Colombo AOI and align every raster to it.
3. Assemble a single per-cell feature table (LST, NDVI, NDBI, built-up, land cover,
   population).
4. Run spatial statistics (Moran's I, Getis-Ord Gi*) to find statistically significant
   heat hotspots.
5. Build and classify a Heat-Exposure Index (HEI) combining temperature, vegetation, and
   population density.
6. Validate Landsat-derived LST against independent MODIS observations.
7. Produce publication-ready maps, figures, and tables.
8. *(Optional stretch)* Attribute what drives LST using a Random Forest model and SHAP.

**Why this scope:** all Heat-Exposure/Risk Index outputs describe *exposure*, not full
vulnerability — adaptive capacity indicators (e.g. income, healthcare access) are not
included and would need to be added for a true vulnerability index.

## Features

- **Automated raster collection** from Google Earth Engine (Landsat 8/9, MODIS,
  WorldCover, WorldPop, SRTM, GHS-BUILT-S) via standalone JavaScript scripts.
- **Cloud-masked, dry-season composites** built from Landsat Collection 2 Level 2
  surface reflectance and thermal bands (`QA_PIXEL` bit masking, official scale factors).
- **Consistent 100 m analysis grid** (`EPSG:32644`) that every input raster is
  reprojected and aligned to, so every downstream computation operates on the same cells.
- **Spatial hotspot analysis** — Global Moran's I for clustering significance, Getis-Ord
  Gi* for hotspot/coldspot location, using Queen contiguity weights built directly from
  the land-only grid cells.
- **Heat-Exposure Index (HEI)** — `minmax(lst_z * pop_density * (1 - ndvi))`,
  quantile-classified into 5 risk classes.
- **Independent validation** of Landsat LST against MODIS MOD11A2 (land-only, area-
  weighted aggregation to avoid sea-surface bias).
- **Publication-ready visualization** — consistent, colour-blind-safe (viridis /
  RdBu) maps and figures sized for a two-column academic paper (300 dpi).
- **Optional ML driver-attribution layer** — Random Forest regression on LST with SHAP
  explainability, evaluated on a spatially blocked train/test split to avoid spatial
  leakage.
- **Raw-data audit gate** (`src/check_raw_data.py`) — validates every exported raster
  (value ranges, CRS, resolution) before it enters the pipeline.
- **Lightweight smoke tests** (`pytest`) as a sanity safety net, not a full test suite.

## Tech Stack

- **Language:** Python 3.x (pipeline), JavaScript (Google Earth Engine Code Editor)
- **Earth observation / data collection:** `earthengine-api`, `geemap`
- **Geospatial processing:** `geopandas`, `rasterio`, `rioxarray`, `xarray`, `shapely`,
  `pyproj`
- **Spatial statistics:** `esda`, `libpysal` (Moran's I, Getis-Ord Gi*)
- **Data handling:** `numpy`, `pandas`, `pyarrow` (Parquet feature store)
- **Machine learning / explainability (optional layer):** `scikit-learn`, `shap`
- **Visualization:** `matplotlib`, `contextily`
- **Configuration:** `pyyaml`
- **Notebooks & reproducibility:** `jupyter`, `nbformat`, `nbclient`, `ipykernel`,
  `papermill`
- **Testing:** `pytest`
- **Desktop GIS (map authoring):** QGIS (`outputs/maps/colombo_uhi_project.qgz`)

## Dataset & Data Collection

All raw raster inputs are collected from **Google Earth Engine** via the scripts in
[`gee/`](gee) and exported to Google Drive, then downloaded into `data/raw/`.

| Source | Dataset | Used for |
|---|---|---|
| Landsat 8/9 Collection 2 L2 | `LANDSAT/LC08\|LC09/C02/T1_L2` | Surface reflectance composite, LST, NDVI, NDBI |
| MODIS | `MODIS/061/MOD11A2` | Day + night LST — independent validation layer |
| ESA WorldCover | `ESA/WorldCover/v200` | Land use / land cover classification |
| WorldPop | `WorldPop/GP/100m/pop` | Population density |
| USGS SRTM | `USGS/SRTMGL1_003` | Elevation |
| JRC GHSL | `JRC/GHSL/P2023A/GHS_BUILT_S` | Built-up surface fraction |
| `data/external/cmc_boundary.geojson` | — | Fixed Colombo AOI bounding box (**not** an administrative boundary) |

**Study area:** Colombo bounding box — `W 79.8189, S 6.8618, E 79.8910, N 6.9821`.
**Study period:** Dry season, January–March, 2023 & 2024 (two years merged into one
median composite to fill cloud-cover gaps).
**Target CRS / resolution:** `EPSG:32644` (WGS 84 / UTM zone 44N), 100 m analysis grid.

See [`gee/`](gee) below for how to run the collection scripts, and
`config/config.yaml` for the single source of truth on AOI, CRS, dates, and dataset IDs.

`data/`, `outputs/models/`, and `outputs/presentations/` are not version-controlled
(see `.gitignore`) — raw and derived data must be regenerated locally by running the
pipeline.

## File Structure

```
colombo-uhi/
├── gee/                          # Google Earth Engine scripts (JavaScript, run in Code Editor)
│   ├── 01_composite.js           # Landsat 8/9 dry-season composite (preview only)
│   ├── 02_lst.js                 # Land Surface Temperature export
│   ├── 03_ndvi_ndbi.js           # NDVI + NDBI export
│   └── 04_aux_layers.js          # WorldCover, WorldPop, SRTM, GHS-BUILT-S, MODIS LST
│
├── config/
│   ├── config.yaml               # Single source of truth: CRS, AOI, dates, dataset IDs
│   └── logging.yaml              # Logging configuration
│
├── src/                          # Python pipeline (run in order)
│   ├── grid.py                   # Build the 100 m analysis grid
│   ├── preprocess.py             # Align every raw raster to the grid
│   ├── features.py               # Assemble the per-cell feature table
│   ├── hotspots.py               # Moran's I + Getis-Ord Gi*
│   ├── hvi.py                    # Heat-Exposure Index build + classification
│   ├── validation.py             # Landsat vs MODIS validation
│   ├── viz.py                    # Final maps, figures, tables
│   ├── check_raw_data.py         # Raw-data audit gate
│   ├── model.py                  # (optional) Random Forest LST driver attribution
│   ├── shap_analysis.py          # (optional) SHAP explainability
│   ├── utils.py                  # Shared helpers (logging, minmax, etc.)
│   └── config.py                 # Config loader
│
├── notebooks/                    # Exploratory / write-up notebooks (mirror src/ stages)
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_analysis.ipynb
│   ├── 03_hvi_experiments.ipynb
│   ├── 04_final_figures.ipynb
│   └── 05_ml_xai.ipynb
│
├── data/                         # Not version-controlled — generated locally
│   ├── external/                 # AOI boundary, external inputs
│   ├── raw/                      # GEE exports
│   ├── interim/                  # Grid-aligned rasters
│   └── processed/                # features.parquet, grid.gpkg
│
├── outputs/
│   ├── figures/                  # Charts (correlation heatmap, SHAP plots, etc.)
│   ├── maps/                     # LST/NDVI/HEI/hotspot maps, QGIS project
│   ├── tables/                   # CSV outputs (hotspots, validation, metrics)
│   ├── models/                   # Trained model artifacts (not version-controlled)
│   └── run.log
│
├── reports/                      # Methodology notes, experiment log, results summary
├── tests/
│   └── test_pipeline.py          # Smoke tests (pytest)
├── requirements.txt
└── README.md
```

## Prerequisites

- **Python** 3.9+ (a virtual environment is strongly recommended)
- **A Google Earth Engine account** with API access enabled, for running the `gee/`
  collection scripts
- **QGIS** (optional) — only needed to open `outputs/maps/colombo_uhi_project.qgz`
- Sufficient local disk space for raw/interim/processed rasters (not version-controlled)

## Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/AkithaPasandul/colombo-uhi-heat-risk.git
   cd colombo-uhi
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Authenticate Google Earth Engine**
   ```bash
   earthengine authenticate
   ```

5. **Configure the project**
   Edit `config/config.yaml` first — it is the single source of truth for CRS, AOI,
   dates, and dataset IDs that every script downstream depends on.

6. **Add the AOI boundary**
   Place the AOI boundary file at `data/external/cmc_boundary.geojson` (the geometry is
   a fixed bounding box, not an administrative polygon).

## Usage

### 1. Collect raw data (Google Earth Engine)

Open each script in [`gee/`](gee) in the
[Earth Engine Code Editor](https://code.earthengine.google.com/) and run in order:

```
01_composite.js   # preview only — confirm the composite before trusting 02/03
02_lst.js         # export LST
03_ndvi_ndbi.js   # export NDVI + NDBI
04_aux_layers.js  # export WorldCover, WorldPop, SRTM, GHS-BUILT-S, MODIS LST (standalone)
```

Each export queues a task in the Code Editor's **Tasks** tab — click **Run** on each one.
Download the results from Google Drive into `data/raw/` using the exact filenames the
scripts export (see [`gee/`](gee) for the full list) — `src/check_raw_data.py` matches
files by name.

### 2. Run the processing pipeline

Run the pipeline stages **in order** from the project root:

```bash
python src/check_raw_data.py   # audit raw rasters before anything else touches them
python src/grid.py             # build the 100 m analysis grid
python src/preprocess.py       # align every raster to the grid
python src/features.py         # assemble the feature table
python src/hotspots.py         # Moran's I + Getis-Ord Gi*
python src/hvi.py              # build & classify the Heat-Exposure Index
python src/validation.py       # Landsat vs MODIS validation
python src/viz.py              # final maps, figures, tables
```

### 3. (Optional) ML driver attribution

Only after the core GIS pipeline above is complete:

```bash
python src/model.py            # Random Forest LST regression
python src/shap_analysis.py    # SHAP feature attribution
```

### 4. Explore via notebooks

The notebooks in `notebooks/` mirror the pipeline stages for exploratory analysis and
figure drafting and can be run with Jupyter or `papermill`.

### 5. Run tests

```bash
pytest -q
```

## License

[Insert license here — e.g. MIT, Apache 2.0, or "All rights reserved" if unpublished]
