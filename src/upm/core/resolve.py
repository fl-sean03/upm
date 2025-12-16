"""Resolver: minimal subset selection for UPM v0.1.

v0.1 minimal acceptance scope (per DevGuide):
- Require only atom_types + bond_types (angles/dihedrals ignored).
- Hard-error if any required atom type or bond tuple is missing.
- Input tables are expected to already be canonicalized + validated; we re-normalize
  the subset output to ensure deterministic sorting/column order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from upm.core.model import BondKey, Requirements, ResolvedFF, canonicalize_bond_key
from upm.core.tables import normalize_atom_types, normalize_bonds


@dataclass(frozen=True)
class MissingTermsError(ValueError):
    """Raised when required parameter terms are missing from the available tables.

    Attributes are deterministic (unique+sorted).
    """

    missing_atom_types: tuple[str, ...] = ()
    missing_bond_types: tuple[BondKey, ...] = ()

    def __init__(
        self,
        *,
        missing_atom_types: list[str] | tuple[str, ...] = (),
        missing_bond_types: list[BondKey] | tuple[BondKey, ...] = (),
    ) -> None:
        atom = tuple(sorted(set(missing_atom_types)))
        bonds = tuple(sorted(set(missing_bond_types)))

        parts: list[str] = []
        if atom:
            parts.append(f"missing required atom_types: {list(atom)!r}")
        if bonds:
            parts.append(f"missing required bond_types: {list(bonds)!r}")

        msg = "; ".join(parts) if parts else "missing required terms"
        super().__init__(msg)

        object.__setattr__(self, "missing_atom_types", atom)
        object.__setattr__(self, "missing_bond_types", bonds)


def resolve_minimal(tables: Mapping[str, Any], requirements: Requirements) -> ResolvedFF:
    """Resolve a minimal subset of canonical tables needed by `requirements`.

    Args:
        tables: mapping of canonical table name -> pandas.DataFrame. Must include
            "atom_types". "bonds" is required iff requirements.bond_types is non-empty.
        requirements: canonical Requirements.

    Returns:
        ResolvedFF containing subset DataFrames.

    Raises:
        MissingTermsError: if any required atom_types or bond_types are missing.
        TypeError/ValueError: for invalid inputs or missing required tables.
    """
    import pandas as pd

    if not isinstance(tables, Mapping):
        raise TypeError(f"resolve_minimal: tables must be a mapping, got {type(tables).__name__}")
    if not isinstance(requirements, Requirements):
        raise TypeError(f"resolve_minimal: requirements must be Requirements, got {type(requirements).__name__}")

    # ------------------------
    # atom_types (required)
    # ------------------------
    atom_df = tables.get("atom_types")
    if atom_df is None:
        raise ValueError("resolve_minimal: missing required table 'atom_types'")
    if not isinstance(atom_df, pd.DataFrame):
        raise TypeError(f"resolve_minimal: tables['atom_types'] must be a DataFrame, got {type(atom_df).__name__}")

    req_atom_set = set(requirements.atom_types)

    atom_type_col = atom_df["atom_type"].astype("string").str.strip()
    present_atom_types = set(atom_type_col.dropna().tolist())
    missing_atom_types = sorted(req_atom_set - present_atom_types)

    atom_mask = atom_type_col.isin(req_atom_set)
    atom_subset = atom_df.loc[atom_mask].copy(deep=True)

    # Keep stripped values (defensive; tables should already be normalized)
    atom_subset["atom_type"] = atom_type_col.loc[atom_mask].astype("string")

    # Re-normalize to ensure deterministic ordering + canonical dtypes.
    atom_subset = normalize_atom_types(atom_subset)

    # ------------------------
    # bonds (required iff req has any)
    # ------------------------
    bonds_subset = None
    missing_bond_types: list[BondKey] = []

    req_bond_set = set(requirements.bond_types)
    if req_bond_set:
        bonds_df = tables.get("bonds")
        if bonds_df is None:
            # Required terms exist but table absent: all bonds are missing.
            missing_bond_types = sorted(req_bond_set)
        else:
            if not isinstance(bonds_df, pd.DataFrame):
                raise TypeError(f"resolve_minimal: tables['bonds'] must be a DataFrame, got {type(bonds_df).__name__}")

            t1 = bonds_df["t1"].astype("string").str.strip()
            t2 = bonds_df["t2"].astype("string").str.strip()

            bond_keys: list[BondKey] = []
            for a, b in zip(t1.tolist(), t2.tolist()):
                if a is pd.NA or b is pd.NA:
                    # Validation should have rejected this already, but keep safe.
                    continue
                bond_keys.append(canonicalize_bond_key(str(a), str(b)))

            present_bond_set = set(bond_keys)
            missing_bond_types = sorted(req_bond_set - present_bond_set)

            # Filter to required bonds
            keep_mask = [k in req_bond_set for k in bond_keys]
            bonds_subset = bonds_df.loc[keep_mask].copy(deep=True)

            # Ensure canonicalized endpoints in the subset (defensive)
            sub_t1: list[str] = []
            sub_t2: list[str] = []
            for a, b in zip(bonds_subset["t1"].astype("string").str.strip().tolist(), bonds_subset["t2"].astype("string").str.strip().tolist()):
                k1, k2 = canonicalize_bond_key(str(a), str(b))
                sub_t1.append(k1)
                sub_t2.append(k2)
            bonds_subset["t1"] = pd.Series(sub_t1, dtype="string")
            bonds_subset["t2"] = pd.Series(sub_t2, dtype="string")

            bonds_subset = normalize_bonds(bonds_subset)

    # ------------------------
    # Missing-term handling (hard-error)
    # ------------------------
    if missing_atom_types or missing_bond_types:
        raise MissingTermsError(
            missing_atom_types=missing_atom_types,
            missing_bond_types=missing_bond_types,
        )

    return ResolvedFF(
        requirements=requirements,
        atom_types=atom_subset,
        bonds=bonds_subset,
    )