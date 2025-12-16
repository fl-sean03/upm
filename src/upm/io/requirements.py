"""Requirements JSON I/O (v0.1).

Scope (v0.1 minimal):
- Read Requirements JSON schema only (no writer, no toy structure format).

Dev guide schema example:
{
  "atom_types": ["c3", "o", "h"],
  "bond_types": [["c3","o"], ["c3","h"]],
  "angle_types": [],
  "dihedral_types": []
}

Rules:
- Missing arrays default to empty.
- Canonicalization happens on read (delegated to `upm.core.model.Requirements`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upm.core.model import Requirements


_MISSING = object()


def _require_dict(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected JSON object, got {type(value).__name__}")
    return value


def _get_array(data: dict[str, Any], key: str) -> Any:
    """Return array value for key; default [] if key missing; error if explicitly null."""
    v = data.get(key, _MISSING)
    if v is _MISSING:
        return []
    if v is None:
        raise ValueError(f"{key}: must be an array; got null")
    return v


def read_requirements_json(path: str | Path) -> Requirements:
    """Read v0.1 Requirements JSON and return canonical `Requirements`.

    Hard errors:
    - top-level must be a JSON object
    - if a field is present, it must be an array (null is rejected)
    - tuple entries must be correct length and strings (enforced by Requirements)
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    obj = _require_dict(data, where="requirements.json")

    atom_types = _get_array(obj, "atom_types")
    bond_types = _get_array(obj, "bond_types")
    angle_types = _get_array(obj, "angle_types")
    dihedral_types = _get_array(obj, "dihedral_types")

    # Canonicalization + validation occurs in Requirements.__post_init__.
    return Requirements(
        atom_types=atom_types,
        bond_types=bond_types,
        angle_types=angle_types,
        dihedral_types=dihedral_types,
    )