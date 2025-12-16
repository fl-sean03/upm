"""UPM core: data model and core logic primitives.

This package is intentionally standalone and must not import CLI/codecs/bundle
to avoid circular dependencies.
"""

from __future__ import annotations

from .model import (
    AngleKey,
    BondKey,
    DihedralKey,
    PackageRef,
    Requirements,
    ResolvedFF,
    canonicalize_angle_key,
    canonicalize_bond_key,
    canonicalize_dihedral_key,
)
from .tables import TABLE_COLUMN_ORDER, TABLE_KEYS, TABLE_SCHEMAS, normalize_atom_types, normalize_bonds, normalize_tables
from .validate import TableValidationError, validate_atom_types, validate_bonds, validate_tables

__all__ = [
    "AngleKey",
    "BondKey",
    "DihedralKey",
    "Requirements",
    "PackageRef",
    "ResolvedFF",
    "canonicalize_bond_key",
    "canonicalize_angle_key",
    "canonicalize_dihedral_key",
    "TABLE_SCHEMAS",
    "TABLE_KEYS",
    "TABLE_COLUMN_ORDER",
    "normalize_atom_types",
    "normalize_bonds",
    "normalize_tables",
    "TableValidationError",
    "validate_atom_types",
    "validate_bonds",
    "validate_tables",
]