# Results summary
Headline numbers for the paper. All statistics are land-cells-only ("within study bbox",
never "within CMC") — see methodology_notes.md for the land-masking rationale.

> **Paper status (2026-07-25)**: both 6-page ICTAR versions are drafted and citation-aligned
> (Paper A = core/no-ML, 20 refs, fallback; Paper B = +ML/XAI, 21 refs, preferred if it fits
> 6 pages). Every number below is the source of truth for both drafts. See
> `reports/paper_writing_status.md` for the assembly checklist and standing guardrails.

## Core pipeline (the paper's contribution)

- **LST (land cells, 2024 dry season)**: range 31.66–47.34 °C, mean 41.08 °C (n=5,777).
  For contrast: water-only mean 30.29 °C, combined land+water 36.13 °C — the ~11 °C
  land/water gap is the empirical justification for mandatory land masking.
- **MODIS consistency check**: r = 0.234 (p = 0.055), RMSE = 7.29 °C, n = 68 one-km blocks
  (land-only block aggregation, ≥50% land). Framed as an illustrative pattern check, not
  validation — MODIS's 1 km resolution smooths away the variability Landsat resolves at
  100 m in this compact AOI.
- **Spatial structure**: global Moran's I = 0.7978 (p = 0.001). Getis-Ord Gi*
  (FDR-corrected): 873 hot / 434 cold / 4,470 n.s. cells. Hot core in central-north
  Colombo; cold spots at the eastern wetland/park cluster (likely Diyasaru/Beddagana) and
  a small western coastal strip.
- **Correlations (land only)**: LST–NDBI +0.72, LST–NDVI −0.49, LST–built-up (GHSL) +0.36.
- **LST by land cover**: built-up 41.4 °C and bare/sparse 41.5 °C hottest; tree cover
  38.6 °C, grassland 39.3 °C; wetland 34.8 °C coolest (n=3, unreliable).
- **HEI (5-class quantile, n=5,391 valid cells)**: top class covers 20.0% of valid area
  *by construction*, but holds **37.1% of the resident population** (204,689 of 551,036
  people) — the population-weighted exposure headline. Top-10 HEI cells cluster at
  ~79.868E, 6.940N (Maradana/Kotahena area) and are all FDR-significant Gi* hot spots.
- **HEI robustness** (notebook 03): top-cell ranking stable under robust-vs-standard
  z-scoring (Spearman 0.997, 10/10 top-10 overlap); class membership (not ranking) depends
  on the quantile-vs-equal-interval classification choice — quantile is correct for a
  right-skewed prioritisation index; one-line caveat in methods.

## Optional ML + XAI extension (does NOT replace the HEI/hotspot methodology)

Optional driver-attribution experiment (`src/model.py`, `src/shap_analysis.py`,
notebook 05 — intentionally untracked). RF predicts land-cell LST; honest evaluation on a
spatial block split (whole 1 km blocks held out; naive random split reported only to
quantify leakage). n = 5,391 (the exact HEI universe). x/y never used as features.

- **Baseline RF** (cell-level features: NDVI, NDBI, GHSL built-up, pop density, LULC):
  spatial-block R² = 0.656, RMSE = 1.274 °C, MAE = 0.976 °C.
- **Extended RF — the best optional ML model** (adds 300 m focal means of the four
  continuous predictors + distance-to-water): spatial-block **R² = 0.765,
  RMSE = 1.054 °C, MAE = 0.792 °C**; block 5-fold GroupKFold **R² = 0.686 ± 0.095**.
  The extended model replaces the original RF as the best model; the original is retained
  in `ml_metrics.csv` as the frozen baseline comparison (identical splits, same seed).
- **NDBI ablation**: extended RF without NDBI (cell + focal) still reaches R² = 0.682 —
  above the full baseline — so the gain does not ride on the quasi-circular predictor.
- **Model class barely matters**: HistGradientBoosting 0.760 ≈ RF 0.765; extended linear
  regression 0.727. The improvement is the 300 m spatial context, not the algorithm.
- **Top drivers (SHAP, mean |SHAP| on the spatial test set)**: ndbi_foc3 (0.360 °C) >
  ndbi (0.355) > ndvi_foc3 (0.197) > dist_water_m (0.151) > ndvi (0.135). Neighbourhood
  versions of the drivers outrank their cell-level values; coastal proximity carries real
  attribution.
- **Caveats (mandatory wherever these results appear)**: SHAP ranks model attributions,
  not physical causes — no causal claims. NDBI (and ndbi_foc3) are quasi-circular (same
  2024 Landsat composite as the LST target), bounded by the ablation. Spatial leakage is
  controlled by the block split / block CV and quantified by the random-vs-spatial gap
  (0.783 vs 0.765 extended). Predictor years span 2020–2024 (accepted limitation).
