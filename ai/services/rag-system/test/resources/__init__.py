"""Test resource loader."""

from __future__ import annotations

import json
from pathlib import Path

_RESOURCES = Path(__file__).parent


def load_json(relative_path: str) -> dict | list:
    """Load a JSON resource file by path relative to resources/."""
    path = _RESOURCES / relative_path
    return json.loads(path.read_text(encoding="utf-8"))
