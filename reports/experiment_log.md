# Experiment log
One line per run. Date | what changed | result | keep?

- 2026-07-04 | Set up `.venv`, installed core pipeline deps (rasterio, geopandas, esda, libpysal, etc.) | jupyter/jupyterlab/geemap/earthengine-api/shap failed due to a Windows long-path limit (project path + jupyterlab's bundled asset filenames exceed 260 chars) | keep — not needed until notebooks are actually used; revisit by enabling Windows long-path support when Week 1 notebook work starts
- 2026-07-04 | Fixed `config/config.yaml`: CRS EPSG:5234 -> EPSG:32644, relabeled AOI from "Colombo Municipal Council" to bounding-box AOI (geometry in `cmc_boundary.geojson` was already correct) | `pytest` still passes (2 passed) | keep
- 2026-07-04 | Wrote `src/check_raw_data.py`, ran raw-data audit on all 7 rasters | all checks passed, numbers match the student's own manual audit exactly (MODIS 69/135 valid cells, GHSL 0-8130 m2/cell in Mollweide, WorldCover ~10m native res, etc.) | keep — outputs/tables/raw_data_audit.csv is the gate for preprocess.py

