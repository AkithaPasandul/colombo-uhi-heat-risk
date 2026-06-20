"""Light smoke tests. Optional for a 36-hour project — a safety net, not a suite.
Run: pytest -q
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

def test_config_loads():
    import config
    cfg = config.load()
    assert cfg["project"]["grid_resolution_m"] == 100
    assert cfg["project"]["crs"].startswith("EPSG")

def test_expected_dirs_exist():
    root = Path(__file__).resolve().parents[1]
    for d in ["data/raw", "data/processed", "outputs/figures", "src"]:
        assert (root / d).exists(), f"missing {d}"
