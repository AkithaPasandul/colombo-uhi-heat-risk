"""Week 5 — Heat-Exposure / Risk Index.
HEI = minmax( lst_z * pop_density * (1 - ndvi) ); quantile-classify.
NOTE: exposure/risk, not full vulnerability, unless adaptive capacity is added.
in : features.parquet ; out: outputs/maps/hei + classified raster.
"""
