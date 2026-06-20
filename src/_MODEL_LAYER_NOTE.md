# Optional ML driver-attribution layer

This structure has no tracked `model.py` / `shap_analysis.py` on purpose. The core
study is GIS + remote sensing first: LST, NDVI/NDBI, hotspot analysis, and the heat
exposure/risk index.

If the required outputs are finished early, add the two files locally for Random
Forest driver attribution and SHAP ranking. They are ignored by Git by default, so
experiments will not distract from the necessary pipeline.
