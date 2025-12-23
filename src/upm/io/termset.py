"""TermSet JSON I/O (MolSAIC v0.1.2 bridge).

Schema contract: `molsaic.termset.v0.1.2`.

UPM policy:
- This reader is *validation-only*: it enforces canonicalization invariants and
  raises if the input violates them (it does not silently re-canonicalize).
- Returned object is a plain dict with deterministic, normalized strings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TermSetValidationError(ValueError):
    """Deterministic validation error for TermSet JSON."""

    message: str

    def __str__(self) -> str:
        return self.message


_MISSING = object()


def _require_dict(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TermSetValidationError(f"{where}: expected JSON object, got {type(value).__name__}")
    return value


def _require_list(value: Any, *, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise TermSetValidationError(f"{where}: expected JSON array, got {type(value).__name__}")
    return value


def _norm_str(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise TermSetValidationError(f"{where}: expected str, got {type(value).__name__}")
    s = value.strip()
    if not s:
        raise TermSetValidationError(f"{where}: must be a non-empty string")
    return s


def _require_key(obj: dict[str, Any], key: str, *, where: str) -> Any:
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        raise TermSetValidationError(f"{where}: missing required key '{key}'")
    if v is None:
        raise TermSetValidationError(f"{where}.{key}: must not be null")
    return v


def _ensure_sorted_unique_str_list(values: list[Any], *, where: str) -> list[str]:
    out = [_norm_str(v, where=f"{where}[{i}]") for i, v in enumerate(values)]
    if out != sorted(out):
        raise TermSetValidationError(f"{where}: must be sorted")
    if len(out) != len(set(out)):
        raise TermSetValidationError(f"{where}: must contain unique entries")
    return out


def _ensure_sorted_unique_key_list(values: list[Any], *, where: str, n: int) -> list[list[str]]:
    keys: list[list[str]] = []
    for i, item in enumerate(values):
        if not isinstance(item, list):
            raise TermSetValidationError(f"{where}[{i}]: expected array of length {n}")
        if len(item) != n:
            raise TermSetValidationError(f"{where}[{i}]: expected {n} items, got {len(item)}")
        keys.append([_norm_str(item[j], where=f"{where}[{i}][{j}]") for j in range(n)])

    # Validate sortedness + uniqueness using tuple comparison.
    tuples = [tuple(k) for k in keys]
    if tuples != sorted(tuples):
        raise TermSetValidationError(f"{where}: must be sorted lexicographically")
    if len(tuples) != len(set(tuples)):
        raise TermSetValidationError(f"{where}: must contain unique entries")
    return keys


def _check_bond_key(key: list[str], *, where: str) -> None:
    t1, t2 = key
    if t1 > t2:
        raise TermSetValidationError(f"{where}: bond key must satisfy t1 <= t2")


def _check_angle_key(key: list[str], *, where: str) -> None:
    t1, _t2, t3 = key
    if t1 > t3:
        raise TermSetValidationError(f"{where}: angle key must satisfy t1 <= t3 (endpoints canonicalized)")


def _check_dihedral_key(key: list[str], *, where: str) -> None:
    fwd = tuple(key)
    rev = (key[3], key[2], key[1], key[0])
    if fwd != min(fwd, rev):
        raise TermSetValidationError(f"{where}: dihedral key must be lexicographic min of forward vs reverse")


def _check_improper_key(key: list[str], *, where: str) -> None:
    # key = (p1, center, p2, p3) with p1 <= p2 <= p3.
    p1, _center, p2, p3 = key
    if not (p1 <= p2 <= p3):
        raise TermSetValidationError(f"{where}: improper key peripherals must satisfy t1 <= t3 <= t4")


def read_termset_json(path: str | Path) -> dict[str, Any]:
    """Read a TermSet JSON file and validate v0.1.2 invariants.

    Returns a dict with required keys:
      - schema
      - atom_types
      - bond_types
      - angle_types
      - dihedral_types
      - improper_types
    """

    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    obj = _require_dict(data, where="termset.json")
    schema = _require_key(obj, "schema", where="termset.json")
    schema = _norm_str(schema, where="termset.json.schema")
    if schema != "molsaic.termset.v0.1.2":
        raise TermSetValidationError(
            f"termset.json.schema: expected 'molsaic.termset.v0.1.2', got {schema!r}"
        )

    atom_types_raw = _require_list(_require_key(obj, "atom_types", where="termset.json"), where="termset.json.atom_types")
    bond_types_raw = _require_list(_require_key(obj, "bond_types", where="termset.json"), where="termset.json.bond_types")
    angle_types_raw = _require_list(_require_key(obj, "angle_types", where="termset.json"), where="termset.json.angle_types")
    dihedral_types_raw = _require_list(
        _require_key(obj, "dihedral_types", where="termset.json"), where="termset.json.dihedral_types"
    )
    improper_types_raw = _require_list(
        _require_key(obj, "improper_types", where="termset.json"), where="termset.json.improper_types"
    )

    atom_types = _ensure_sorted_unique_str_list(atom_types_raw, where="termset.json.atom_types")

    bond_types = _ensure_sorted_unique_key_list(bond_types_raw, where="termset.json.bond_types", n=2)
    for i, k in enumerate(bond_types):
        _check_bond_key(k, where=f"termset.json.bond_types[{i}]")

    angle_types = _ensure_sorted_unique_key_list(angle_types_raw, where="termset.json.angle_types", n=3)
    for i, k in enumerate(angle_types):
        _check_angle_key(k, where=f"termset.json.angle_types[{i}]")

    dihedral_types = _ensure_sorted_unique_key_list(dihedral_types_raw, where="termset.json.dihedral_types", n=4)
    for i, k in enumerate(dihedral_types):
        _check_dihedral_key(k, where=f"termset.json.dihedral_types[{i}]")

    improper_types = _ensure_sorted_unique_key_list(improper_types_raw, where="termset.json.improper_types", n=4)
    for i, k in enumerate(improper_types):
        _check_improper_key(k, where=f"termset.json.improper_types[{i}]")

    return {
        "schema": schema,
        "atom_types": atom_types,
        "bond_types": bond_types,
        "angle_types": angle_types,
        "dihedral_types": dihedral_types,
        "improper_types": improper_types,
        # pass-through optional keys if present (no validation in v0.1.2 reader)
        "counts": obj.get("counts"),
        "provenance": obj.get("provenance"),
    }


__all__ = [
    "TermSetValidationError",
    "read_termset_json",
]

