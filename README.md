# Colombo UHI & Heat Exposure

Code for *Urban Heat Island Mapping and Heat Vulnerability Assessment for Colombo
Using Remote Sensing and GIS*. Scoped to ~36 working hours (weekends, 6 weeks).

## Pipeline (folders map to methodology stages)
1. `gee/`         – Earth Engine: composites + raster exports
2. `src/grid`     – fix CRS + build the 100 m analysis grid
3. `src/preprocess` – align every raster to the grid
4. `src/features`   – assemble the feature stack (everything reads this table)
5. `src/hotspots`   – Moran's I + Getis-Ord Gi*
6. Optional stretch: ML driver attribution — RF + SHAP, only after the core GIS pipeline is complete
7. `src/hvi`        – build & classify the heat-exposure index
8. `src/validation` – MODIS cross-comparison
9. `src/viz`        – final maps, figures, tables

## Data flow
data/raw (GEE exports) -> data/interim (aligned) -> data/processed (feature stack)
External inputs (boundary, OSM, census) live in data/external.
Nothing in data/ or outputs/ is version-controlled.

## Quick start
1. Edit `config/config.yaml` (CRS, AOI path, dates) — first thing.
2. Drop the AOI boundary into `data/external/`.
3. Run GEE scripts, export to `data/raw/`.
4. Work through `src/` in pipeline order, or the notebooks.

## Week map
W1 grid+LST/NDVI · W2 predictor stack · W3 hotspots · W4 HEI/HVI draft · W5 validation · W6 maps+buffer

## Optional ML stretch
Keep ML out of the main workflow until the required GIS/remote-sensing outputs are finished.
If extra time remains, add `src/model.py` and `src/shap_analysis.py` locally for Random
Forest driver attribution and SHAP ranking. These files are ignored by Git by default.
