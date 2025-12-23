"""ParameterSet JSON I/O (UPM v0.1.2 bridge).

Schema contract: `upm.parameterset.v0.1.2`.

UPM policy:
- This reader is *validation-only*: it enforces required fields and basic numeric
  constraints, and raises if the input violates them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParameterSetValidationError(ValueError):
    """Deterministic validation error for ParameterSet JSON."""

    message: str

    def __str__(self) -> str:
        return self.message


_MISSING = object()


def _require_dict(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ParameterSetValidationError(f"{where}: expected JSON object, got {type(value).__name__}")
    return value


def _norm_str(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise ParameterSetValidationError(f"{where}: expected str, got {type(value).__name__}")
    s = value.strip()
    if not s:
        raise ParameterSetValidationError(f"{where}: must be a non-empty string")
    return s


def _require_key(obj: dict[str, Any], key: str, *, where: str) -> Any:
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        raise ParameterSetValidationError(f"{where}: missing required key '{key}'")
    if v is None:
        raise ParameterSetValidationError(f"{where}.{key}: must not be null")
    return v


def _require_finite_float(value: Any, *, where: str) -> float:
    if value is None:
        raise ParameterSetValidationError(f"{where}: expected number, got null")
    try:
        x = float(value)
    except Exception as e:
        raise ParameterSetValidationError(f"{where}: expected number") from e
    if not math.isfinite(x):
        raise ParameterSetValidationError(f"{where}: must be finite")
    return x


def read_parameterset_json(path: str | Path) -> dict[str, Any]:
    """Read a ParameterSet JSON file and validate v0.1.2 constraints."""

    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    obj = _require_dict(data, where="parameterset.json")
    schema = _norm_str(_require_key(obj, "schema", where="parameterset.json"), where="parameterset.json.schema")
    if schema != "upm.parameterset.v0.1.2":
        raise ParameterSetValidationError(
            f"parameterset.json.schema: expected 'upm.parameterset.v0.1.2', got {schema!r}"
        )

    atom_types_raw = _require_key(obj, "atom_types", where="parameterset.json")
    atom_types_obj = _require_dict(atom_types_raw, where="parameterset.json.atom_types")

    # Validate and normalize each atom_type entry.
    # Determinism: we return a mapping ordered by sorted atom_type keys.
    keys = list(atom_types_obj.keys())
    norm_keys = [_norm_str(k, where="parameterset.json.atom_types keys") for k in keys]
    if len(norm_keys) != len(set(norm_keys)):
        raise ParameterSetValidationError("parameterset.json.atom_types: duplicate atom_type keys after stripping")

    out_map: dict[str, dict[str, Any]] = {}
    # Use original dict to fetch values, but emit sorted keys.
    norm_to_raw: dict[str, str] = {nk: rk for nk, rk in zip(norm_keys, keys)}
    for at in sorted(norm_keys):
        entry = atom_types_obj.get(norm_to_raw[at])
        eobj = _require_dict(entry, where=f"parameterset.json.atom_types[{at}]")

        allowed = {"mass_amu", "lj_sigma_angstrom", "lj_epsilon_kcal_mol", "element"}
        extras = sorted([k for k in eobj.keys() if k not in allowed])
        if extras:
            raise ParameterSetValidationError(f"parameterset.json.atom_types[{at}]: unexpected keys: {extras}")

        mass = _require_finite_float(eobj.get("mass_amu", None), where=f"parameterset.json.atom_types[{at}].mass_amu")
        sigma = _require_finite_float(
            eobj.get("lj_sigma_angstrom", None), where=f"parameterset.json.atom_types[{at}].lj_sigma_angstrom"
        )
        eps = _require_finite_float(
            eobj.get("lj_epsilon_kcal_mol", None), where=f"parameterset.json.atom_types[{at}].lj_epsilon_kcal_mol"
        )

        if mass <= 0.0:
            raise ParameterSetValidationError(f"parameterset.json.atom_types[{at}].mass_amu: must be > 0")
        if sigma <= 0.0:
            raise ParameterSetValidationError(f"parameterset.json.atom_types[{at}].lj_sigma_angstrom: must be > 0")
        if eps < 0.0:
            raise ParameterSetValidationError(f"parameterset.json.atom_types[{at}].lj_epsilon_kcal_mol: must be >= 0")

        rec: dict[str, Any] = {
            "mass_amu": mass,
            "lj_sigma_angstrom": sigma,
            "lj_epsilon_kcal_mol": eps,
        }

        if "element" in eobj and eobj["element"] is not None:
            rec["element"] = _norm_str(eobj["element"], where=f"parameterset.json.atom_types[{at}].element")

        out_map[at] = rec

    return {
        "schema": schema,
        "atom_types": out_map,
        # pass-through optional keys
        "provenance": obj.get("provenance"),
        "units": obj.get("units"),
    }


__all__ = [
    "ParameterSetValidationError",
    "read_parameterset_json",
]
