from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - fallback for bootstrapping without dependencies
    yaml = None


def load_metadata(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if yaml is not None:
        loaded = yaml.safe_load(raw)
    else:
        loaded = json.loads(raw)

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded
