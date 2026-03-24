"""ExistingFRC parameter source for FRC builder.

This module provides the ExistingFRCSource class that extracts real parameters
from an existing .frc file. It parses the source file, filters entries to match
the termset, and provides O(1) lookups for all parameter types.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from upm.codecs.msi_frc import read_frc
from upm.core.model import canonicalize_angle_key, canonicalize_bond_key

from ..alias_manager import element_to_connects
from ..entries import (
    AngleParams,
    AtomTypeInfo,
    BondIncrementParams,
    BondParams,
    NonbondParams,
    OOPParams,
    TorsionParams,
)


class ExistingFRCSource:
    """Provides parameters extracted from an existing .frc file.

    This source parses an existing FRC file, filters entries to match the
    termset atom types, and provides O(1) lookups via pre-built indices.

    **DOES provide** (all parameter types):
        - get_atom_type_info() - mass, element, connects from FRC
        - get_nonbond_params() - LJ A/B from FRC
        - get_bond_params() - k, r0 from FRC bonds table
        - get_angle_params() - theta0, k from FRC angles table
        - get_torsion_params() - kphi, n, phi0 from FRC torsions table (if present)
        - get_oop_params() - kchi, n, chi0 from FRC oop table (if present)

    Example:
        >>> termset = {"atom_types": ["cdc", "cdo"], "bond_types": [["cdc", "cdo"]]}
        >>> source = ExistingFRCSource(Path("large.frc"), termset)
        >>> info = source.get_atom_type_info("cdc")
        >>> bond = source.get_bond_params("cdc", "cdo")
    """

    def __init__(self, frc_path: Path, termset: dict[str, Any]) -> None:
        """Load and filter FRC tables for termset atom types.

        Args:
            frc_path: Path to the source .frc file.
            termset: TermSet dict with keys 'atom_types', 'bond_types',
                     'angle_types', etc. to filter the source FRC.
        """
        tables, _ = read_frc(frc_path, validate=False)
        self._tables = _filter_frc_tables(tables, termset)
        self._build_lookup_indices()

    def _build_lookup_indices(self) -> None:
        """Build dict lookups for O(1) parameter access."""
        # Atom type index: atom_type → row dict
        self._atom_type_index: dict[str, dict[str, Any]] = {}
        if "atom_types" in self._tables:
            for _, row in self._tables["atom_types"].iterrows():
                at = str(row["atom_type"])
                self._atom_type_index[at] = row.to_dict()

        # Bond index: (t1, t2) canonicalized → row dict
        self._bond_index: dict[tuple[str, str], dict[str, Any]] = {}
        if "bonds" in self._tables:
            for _, row in self._tables["bonds"].iterrows():
                t1, t2 = str(row["t1"]), str(row["t2"])
                canon = canonicalize_bond_key(t1, t2)
                self._bond_index[canon] = row.to_dict()

        # Angle index: (t1, t2, t3) canonicalized → row dict
        self._angle_index: dict[tuple[str, str, str], dict[str, Any]] = {}
        if "angles" in self._tables:
            for _, row in self._tables["angles"].iterrows():
                t1, t2, t3 = str(row["t1"]), str(row["t2"]), str(row["t3"])
                canon = canonicalize_angle_key(t1, t2, t3)
                self._angle_index[canon] = row.to_dict()

        # Torsion index: (t1, t2, t3, t4) → row dict
        # Note: torsion canonicalization is more complex; we store both orderings
        self._torsion_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        if "torsions" in self._tables:
            for _, row in self._tables["torsions"].iterrows():
                t1 = str(row["t1"])
                t2 = str(row["t2"])
                t3 = str(row["t3"])
                t4 = str(row["t4"])
                self._torsion_index[(t1, t2, t3, t4)] = row.to_dict()
                # Also store reverse
                self._torsion_index[(t4, t3, t2, t1)] = row.to_dict()

        # OOP index: (t1, t2, t3, t4) → row dict
        self._oop_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        if "oop" in self._tables:
            for _, row in self._tables["oop"].iterrows():
                t1 = str(row["t1"])
                t2 = str(row["t2"])
                t3 = str(row["t3"])
                t4 = str(row["t4"])
                self._oop_index[(t1, t2, t3, t4)] = row.to_dict()

        # Bond increment index: (t1, t2) canonicalized → row dict
        self._bond_increment_index: dict[tuple[str, str], dict[str, Any]] = {}
        if "bond_increments" in self._tables:
            for _, row in self._tables["bond_increments"].iterrows():
                t1, t2 = str(row["t1"]), str(row["t2"])
                canon = canonicalize_bond_key(t1, t2)
                self._bond_increment_index[canon] = row.to_dict()

    def get_atom_type_info(self, atom_type: str) -> Optional[AtomTypeInfo]:
        """Get atom type information from parsed FRC.

        Args:
            atom_type: The atom type name.

        Returns:
            AtomTypeInfo if found in FRC, None otherwise.
        """
        rec = self._atom_type_index.get(atom_type)
        if rec is None:
            return None
        element = str(rec.get("element", "X"))
        mass = float(rec.get("mass_amu", 0.0))
        return AtomTypeInfo(
            mass_amu=mass,
            element=element,
            connects=element_to_connects(element),
        )

    def get_nonbond_params(self, atom_type: str) -> Optional[NonbondParams]:
        """Get nonbond (LJ 12-6) parameters from parsed FRC.

        Args:
            atom_type: The atom type name.

        Returns:
            NonbondParams with A/B coefficients if found, None otherwise.
        """
        rec = self._atom_type_index.get(atom_type)
        if rec is None:
            return None
        lj_a = rec.get("lj_a")
        lj_b = rec.get("lj_b")
        if lj_a is None or lj_b is None or pd.isna(lj_a) or pd.isna(lj_b):
            return None
        return NonbondParams(lj_a=float(lj_a), lj_b=float(lj_b))

    def get_bond_params(self, t1: str, t2: str) -> Optional[BondParams]:
        """Get bond parameters from parsed FRC.

        Args:
            t1: First atom type in the bond.
            t2: Second atom type in the bond.

        Returns:
            BondParams if found in FRC bonds table, None otherwise.
        """
        canon = canonicalize_bond_key(t1, t2)
        rec = self._bond_index.get(canon)
        if rec is None:
            return None
        r0 = rec.get("r0")
        # Try both "k" (msi_frc parser) and "k2" (older format) for compatibility
        k_val = rec.get("k") if rec.get("k") is not None else rec.get("k2")
        if r0 is None or k_val is None or pd.isna(r0) or pd.isna(k_val):
            return None
        return BondParams(r0=float(r0), k=float(k_val))

    def get_angle_params(self, t1: str, t2: str, t3: str) -> Optional[AngleParams]:
        """Get angle parameters from parsed FRC.

        Args:
            t1: First atom type (end atom).
            t2: Center atom type (apex).
            t3: Third atom type (other end atom).

        Returns:
            AngleParams if found in FRC angles table, None otherwise.
        """
        canon = canonicalize_angle_key(t1, t2, t3)
        rec = self._angle_index.get(canon)
        if rec is None:
            return None
        # Try both "theta0_deg" (msi_frc parser) and "theta0" (older format)
        theta0 = rec.get("theta0_deg") if rec.get("theta0_deg") is not None else rec.get("theta0")
        # Try both "k" (msi_frc parser) and "k2" (older format) for compatibility
        k_val = rec.get("k") if rec.get("k") is not None else rec.get("k2")
        if theta0 is None or k_val is None or pd.isna(theta0) or pd.isna(k_val):
            return None
        return AngleParams(theta0_deg=float(theta0), k=float(k_val))

    def get_torsion_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[TorsionParams]:
        """Get torsion (dihedral) parameters from parsed FRC.

        Args:
            t1: First atom type.
            t2: Second atom type (central bond start).
            t3: Third atom type (central bond end).
            t4: Fourth atom type.

        Returns:
            TorsionParams if found in FRC torsions table, None otherwise.
        """
        rec = self._torsion_index.get((t1, t2, t3, t4))
        if rec is None:
            return None
        kphi = rec.get("kphi")
        n = rec.get("n")
        phi0 = rec.get("phi0")
        if kphi is None or n is None or phi0 is None:
            return None
        if pd.isna(kphi) or pd.isna(n) or pd.isna(phi0):
            return None
        return TorsionParams(kphi=float(kphi), n=int(n), phi0=float(phi0))

    def get_oop_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[OOPParams]:
        """Get out-of-plane (improper) parameters from parsed FRC.

        Args:
            t1: Central atom type.
            t2: First bonded atom type.
            t3: Second bonded atom type.
            t4: Third bonded atom type.

        Returns:
            OOPParams if found in FRC oop table, None otherwise.
        """
        rec = self._oop_index.get((t1, t2, t3, t4))
        if rec is None:
            return None
        kchi = rec.get("kchi")
        n = rec.get("n")
        chi0 = rec.get("chi0")
        if kchi is None or n is None or chi0 is None:
            return None
        if pd.isna(kchi) or pd.isna(n) or pd.isna(chi0):
            return None
        return OOPParams(kchi=float(kchi), n=int(n), chi0=float(chi0))

    def get_bond_increment_params(self, t1: str, t2: str) -> Optional[BondIncrementParams]:
        """Get bond increment parameters from parsed FRC.

        Args:
            t1: First atom type in the bond.
            t2: Second atom type in the bond.

        Returns:
            BondIncrementParams if found in FRC bond_increments table, None otherwise.
        """
        canon = canonicalize_bond_key(t1, t2)
        rec = self._bond_increment_index.get(canon)
        if rec is None:
            return None
        delta_ij = rec.get("delta_ij")
        delta_ji = rec.get("delta_ji")
        if delta_ij is None or delta_ji is None:
            return None
        if pd.isna(delta_ij) or pd.isna(delta_ji):
            return None
        return BondIncrementParams(delta_ij=float(delta_ij), delta_ji=float(delta_ji))


# =============================================================================
# Table Filtering Utility
# =============================================================================


def _filter_frc_tables(
    tables: dict[str, pd.DataFrame],
    termset: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Filter FRC tables to only include entries for required atom types.

    This function extracts only the entries from parsed FRC tables that match
    the types specified in the termset. It handles canonicalization of bond
    and angle types to ensure matching regardless of atom type ordering.

    Additionally, this function deduplicates entries when the source FRC file
    contains multiple entries for the same type (e.g., different versions).
    For deduplication:
    - atom_types: prefer entries with lj_a/lj_b populated; otherwise keep last
    - bonds: keep last entry for each (t1, t2, style) key
    - angles: keep last entry for each (t1, t2, t3, style) key

    Args:
        tables: Parsed FRC tables from read_frc() with keys like 'atom_types',
            'bonds', 'angles', etc. Each value is a pandas DataFrame.
        termset: TermSet dict with keys 'atom_types', 'bond_types', 'angle_types',
            etc. The types are used to filter matching entries from tables.

    Returns:
        Filtered tables dict with only matching entries. Tables that have no
        matching entries are omitted from the result. All duplicates are removed.
    """
    result: dict[str, pd.DataFrame] = {}

    # 1. Filter atom_types by exact match on atom_type column
    required_atom_types = set(termset.get("atom_types") or [])
    if "atom_types" in tables and not tables["atom_types"].empty:
        at_df = tables["atom_types"]
        mask = at_df["atom_type"].isin(required_atom_types)
        filtered_at = at_df[mask].copy()

        if not filtered_at.empty:
            # Deduplicate: prefer entries with lj_a/lj_b populated
            # Group by atom_type and select best entry
            deduplicated_rows = []
            for atom_type in filtered_at["atom_type"].unique():
                candidates = filtered_at[filtered_at["atom_type"] == atom_type]
                if len(candidates) == 1:
                    deduplicated_rows.append(candidates.iloc[0])
                else:
                    # Prefer entry with lj_a and lj_b populated (not null)
                    has_lj = candidates["lj_a"].notna() & candidates["lj_b"].notna()
                    with_lj = candidates[has_lj]
                    if not with_lj.empty:
                        # Take last entry with LJ params (later versions typically better)
                        deduplicated_rows.append(with_lj.iloc[-1])
                    else:
                        # No entries have LJ params - take last entry
                        deduplicated_rows.append(candidates.iloc[-1])

            result["atom_types"] = pd.DataFrame(deduplicated_rows).reset_index(
                drop=True
            )

    # 2. Filter bonds by canonicalized (t1, t2) matching
    raw_bond_types = termset.get("bond_types") or []
    required_bonds: set[tuple[str, str]] = set()
    for bt in raw_bond_types:
        if len(bt) >= 2:
            # Canonicalize: t1 <= t2 lexicographically
            canon = canonicalize_bond_key(str(bt[0]), str(bt[1]))
            required_bonds.add(canon)

    if "bonds" in tables and not tables["bonds"].empty and required_bonds:
        bonds_df = tables["bonds"]

        def _bond_matches(row: pd.Series) -> bool:
            t1, t2 = str(row["t1"]), str(row["t2"])
            canon = canonicalize_bond_key(t1, t2)
            return canon in required_bonds

        mask = bonds_df.apply(_bond_matches, axis=1)
        filtered_bonds = bonds_df[mask].copy()

        if not filtered_bonds.empty:
            # Deduplicate: keep last entry for each (t1, t2, style) key

            def _get_canon_bond_key(row: pd.Series) -> str:
                t1, t2 = canonicalize_bond_key(str(row["t1"]), str(row["t2"]))
                style = str(row["style"]) if pd.notna(row["style"]) else ""
                return f"{t1}|{t2}|{style}"

            filtered_bonds["_canon_key"] = filtered_bonds.apply(
                _get_canon_bond_key, axis=1
            )
            # Keep last occurrence of each key
            filtered_bonds = filtered_bonds.drop_duplicates(
                subset=["_canon_key"], keep="last"
            )
            filtered_bonds = filtered_bonds.drop(columns=["_canon_key"]).reset_index(
                drop=True
            )
            result["bonds"] = filtered_bonds

    # 3. Filter angles by canonicalized (t1, t2, t3) matching
    raw_angle_types = termset.get("angle_types") or []
    required_angles: set[tuple[str, str, str]] = set()
    for at in raw_angle_types:
        if len(at) >= 3:
            # Canonicalize: t1 <= t3 lexicographically (center stays in place)
            canon = canonicalize_angle_key(str(at[0]), str(at[1]), str(at[2]))
            required_angles.add(canon)

    if "angles" in tables and not tables["angles"].empty and required_angles:
        angles_df = tables["angles"]

        def _angle_matches(row: pd.Series) -> bool:
            t1, t2, t3 = str(row["t1"]), str(row["t2"]), str(row["t3"])
            canon = canonicalize_angle_key(t1, t2, t3)
            return canon in required_angles

        mask = angles_df.apply(_angle_matches, axis=1)
        filtered_angles = angles_df[mask].copy()

        if not filtered_angles.empty:
            # Deduplicate: keep last entry for each (t1, t2, t3, style) key

            def _get_canon_angle_key(row: pd.Series) -> str:
                t1, t2, t3 = canonicalize_angle_key(
                    str(row["t1"]), str(row["t2"]), str(row["t3"])
                )
                style = str(row["style"]) if pd.notna(row["style"]) else ""
                return f"{t1}|{t2}|{t3}|{style}"

            filtered_angles["_canon_key"] = filtered_angles.apply(
                _get_canon_angle_key, axis=1
            )
            # Keep last occurrence of each key
            filtered_angles = filtered_angles.drop_duplicates(
                subset=["_canon_key"], keep="last"
            )
            filtered_angles = filtered_angles.drop(columns=["_canon_key"]).reset_index(
                drop=True
            )
            result["angles"] = filtered_angles

    # 4. Filter bond_increments by canonicalized (t1, t2) matching (same as bonds)
    if "bond_increments" in tables and not tables["bond_increments"].empty and required_bonds:
        bi_df = tables["bond_increments"]

        def _bi_matches(row: pd.Series) -> bool:
            t1, t2 = str(row["t1"]), str(row["t2"])
            canon = canonicalize_bond_key(t1, t2)
            return canon in required_bonds

        mask = bi_df.apply(_bi_matches, axis=1)
        filtered_bi = bi_df[mask].copy()

        if not filtered_bi.empty:
            # Deduplicate: keep last entry for each (t1, t2) key

            def _get_canon_bi_key(row: pd.Series) -> str:
                t1, t2 = canonicalize_bond_key(str(row["t1"]), str(row["t2"]))
                return f"{t1}|{t2}"

            filtered_bi["_canon_key"] = filtered_bi.apply(_get_canon_bi_key, axis=1)
            # Keep last occurrence of each key
            filtered_bi = filtered_bi.drop_duplicates(subset=["_canon_key"], keep="last")
            filtered_bi = filtered_bi.drop(columns=["_canon_key"]).reset_index(drop=True)
            result["bond_increments"] = filtered_bi

    return result


__all__ = [
    "ExistingFRCSource",
]
