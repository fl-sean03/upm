"""Core data model for UPM (Unified Parameter Model).

v0.1 minimal acceptance scope:
- Standalone dataclasses with stable fields and no circular imports.
- Requirements canonicalization for deterministic minimal resolving.
- Does NOT implement parsing/export/bundling.

This module must not import codecs/bundle/cli.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd


# Keep these as plain assignments for Python 3.9 compatibility (no typing.TypeAlias).
BondKey = tuple[str, str]
AngleKey = tuple[str, str, str]
DihedralKey = tuple[str, str, str, str]


def _norm_str(value: Any, *, where: str) -> str:
    """Normalize a required string: strip and reject empty/whitespace."""
    if not isinstance(value, str):
        raise ValueError(f"{where}: expected str, got {type(value).__name__}")
    s = value.strip()
    if not s:
        raise ValueError(f"{where}: must be a non-empty string")
    return s


def canonicalize_bond_key(t1: str, t2: str) -> BondKey:
    """Canonicalize a bond key so that t1 <= t2 lexicographically."""
    a = _norm_str(t1, where="bond_types[*][0]")
    b = _norm_str(t2, where="bond_types[*][1]")
    return (a, b) if a <= b else (b, a)


def canonicalize_angle_key(t1: str, t2: str, t3: str) -> AngleKey:
    """Canonicalize an angle key so that endpoint types satisfy t1 <= t3."""
    a = _norm_str(t1, where="angle_types[*][0]")
    b = _norm_str(t2, where="angle_types[*][1]")
    c = _norm_str(t3, where="angle_types[*][2]")
    return (a, b, c) if a <= c else (c, b, a)


def canonicalize_dihedral_key(t1: str, t2: str, t3: str, t4: str) -> DihedralKey:
    """Canonicalize by reversal: choose lexicographically smaller of forward vs reversed."""
    a = _norm_str(t1, where="dihedral_types[*][0]")
    b = _norm_str(t2, where="dihedral_types[*][1]")
    c = _norm_str(t3, where="dihedral_types[*][2]")
    d = _norm_str(t4, where="dihedral_types[*][3]")
    fwd: DihedralKey = (a, b, c, d)
    rev: DihedralKey = (d, c, b, a)
    return fwd if fwd <= rev else rev


def _ensure_iterable_not_string(value: Any, *, where: str) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{where}: expected a list/tuple, got {type(value).__name__}")
    try:
        iter(value)
    except TypeError as e:
        raise ValueError(f"{where}: expected an iterable") from e
    return value


def _unique_sorted_strs(values: Iterable[str], *, where: str) -> tuple[str, ...]:
    normed = [_norm_str(v, where=f"{where}[*]") for v in values]
    return tuple(sorted(set(normed)))


def _unique_sorted_keys(values: Iterable[Any], *, where: str) -> tuple[Any, ...]:
    # Values must be hashable (tuples) by design.
    return tuple(sorted(set(values)))


def _normalize_bond_types(raw: Any) -> tuple[BondKey, ...]:
    items = _ensure_iterable_not_string(raw, where="bond_types")
    keys: list[BondKey] = []
    for i, item in enumerate(items):
        if not isinstance(item, (list, tuple)):
            raise ValueError(f"bond_types[{i}]: expected [t1,t2] array")
        if len(item) != 2:
            raise ValueError(f"bond_types[{i}]: expected 2 items, got {len(item)}")
        keys.append(canonicalize_bond_key(item[0], item[1]))
    return _unique_sorted_keys(keys, where="bond_types")


def _normalize_angle_types(raw: Any) -> tuple[AngleKey, ...]:
    items = _ensure_iterable_not_string(raw, where="angle_types")
    keys: list[AngleKey] = []
    for i, item in enumerate(items):
        if not isinstance(item, (list, tuple)):
            raise ValueError(f"angle_types[{i}]: expected [t1,t2,t3] array")
        if len(item) != 3:
            raise ValueError(f"angle_types[{i}]: expected 3 items, got {len(item)}")
        keys.append(canonicalize_angle_key(item[0], item[1], item[2]))
    return _unique_sorted_keys(keys, where="angle_types")


def _normalize_dihedral_types(raw: Any) -> tuple[DihedralKey, ...]:
    items = _ensure_iterable_not_string(raw, where="dihedral_types")
    keys: list[DihedralKey] = []
    for i, item in enumerate(items):
        if not isinstance(item, (list, tuple)):
            raise ValueError(f"dihedral_types[{i}]: expected [t1,t2,t3,t4] array")
        if len(item) != 4:
            raise ValueError(f"dihedral_types[{i}]: expected 4 items, got {len(item)}")
        keys.append(canonicalize_dihedral_key(item[0], item[1], item[2], item[3]))
    return _unique_sorted_keys(keys, where="dihedral_types")


@dataclass(frozen=True)
class Requirements:
    """Canonical Requirements for minimal resolving.

    JSON schema fields (v0.1):
      - atom_types: [str]
      - bond_types: [[str,str]]
      - angle_types: [[str,str,str]] (optional in v0.1)
      - dihedral_types: [[str,str,str,str]] (optional in v0.1)

    Canonicalization:
      - Strings are stripped; empty strings hard-error.
      - atom_types: unique + sorted
      - bond_types: each (t1,t2) sorted so t1 <= t2; then unique + sorted
      - angle_types: endpoints canonicalized so t1 <= t3; then unique + sorted
      - dihedral_types: reversal canonicalization; then unique + sorted
    """

    atom_types: tuple[str, ...] = ()
    bond_types: tuple[BondKey, ...] = ()
    angle_types: tuple[AngleKey, ...] = ()
    dihedral_types: tuple[DihedralKey, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "atom_types",
            _unique_sorted_strs(
                _ensure_iterable_not_string(self.atom_types, where="atom_types"),
                where="atom_types",
            ),
        )
        object.__setattr__(self, "bond_types", _normalize_bond_types(self.bond_types))
        object.__setattr__(self, "angle_types", _normalize_angle_types(self.angle_types))
        object.__setattr__(self, "dihedral_types", _normalize_dihedral_types(self.dihedral_types))


@dataclass(frozen=True)
class PackageRef:
    """Minimal identity/reference for a UPM package (no bundle/manifest semantics)."""

    name: str
    version: str
    root: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _norm_str(self.name, where="PackageRef.name"))
        object.__setattr__(self, "version", _norm_str(self.version, where="PackageRef.version"))


@dataclass(frozen=True)
class ResolvedFF:
    """Minimal resolver output container for downstream export.

    Tables are carried as pandas DataFrames but this core model avoids importing
    pandas at runtime to reduce import surfaces and prevent cycles.
    """

    requirements: Requirements
    atom_types: "pd.DataFrame"
    bonds: "pd.DataFrame | None" = None
    angles: "pd.DataFrame | None" = None
    pair_overrides: "pd.DataFrame | None" = None

    source: PackageRef | None = None
    raw_unknown_sections: dict[str, list[str]] | None = None