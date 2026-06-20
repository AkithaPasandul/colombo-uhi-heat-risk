"""Load locked project settings from config/config.yaml."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load(path: str | None = None) -> dict:
    path = path or (ROOT / "config" / "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)
