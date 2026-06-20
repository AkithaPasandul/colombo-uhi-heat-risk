"""Shared helpers: logging setup, raster<->grid I/O, normalisation."""
import logging, logging.config, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def setup_logging():
    with open(ROOT / "config" / "logging.yaml") as f:
        logging.config.dictConfig(yaml.safe_load(f))
    return logging.getLogger("colombo-uhi")

def minmax(series):
    """Normalise to 0-1; used by the HEI."""
    lo, hi = series.min(), series.max()
    return (series - lo) / (hi - lo)
