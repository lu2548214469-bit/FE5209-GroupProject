"""Load the strategy configuration (config/strategy.yaml)."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "strategy.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def override(cfg: dict, **changes) -> dict:
    """Copy of cfg with dotted keys replaced, e.g. override(cfg, **{"selection.top_k": 3})."""
    out = copy.deepcopy(cfg)
    for key, value in changes.items():
        node = out
        *parents, leaf = key.split(".")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return out


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
