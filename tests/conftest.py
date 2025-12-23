"""Pytest configuration.

This repo follows the `src/` layout. Some environments may invoke a `pytest`
entrypoint from a different Python install than the one used for
`python -m pip install -e ...`, which can cause `import upm` to fail.

To keep the skeleton robust, we ensure `src/` is on `sys.path` during tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd


def pytest_configure() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    sys.path.insert(0, str(src_dir))


# =============================================================================
# Shared Test Helpers for FRC Tests
# =============================================================================


def make_termset(
    atom_types: list[str],
    bond_types: list[list[str]] | None = None,
    angle_types: list[list[str]] | None = None,
) -> dict[str, Any]:
    """Create a minimal validated termset dict."""
    return {
        "schema": "molsaic.termset.v0.1.2",
        "atom_types": list(atom_types),
        "bond_types": bond_types or [],
        "angle_types": angle_types or [],
        "dihedral_types": [],
        "improper_types": [],
    }


def make_atom_types_df(
    rows: list[dict[str, Any]],
) -> pd.DataFrame:
    """Create an atom_types DataFrame from row dicts."""
    df = pd.DataFrame(rows)
    # Ensure all expected columns exist
    for col in ["atom_type", "element", "mass_amu", "vdw_style", "lj_a", "lj_b", "notes"]:
        if col not in df.columns:
            df[col] = None
    return df


def make_bonds_df(
    rows: list[dict[str, Any]],
) -> pd.DataFrame:
    """Create a bonds DataFrame from row dicts."""
    df = pd.DataFrame(rows)
    for col in ["t1", "t2", "style", "r0", "k"]:
        if col not in df.columns:
            df[col] = None
    return df


def make_angles_df(
    rows: list[dict[str, Any]],
) -> pd.DataFrame:
    """Create an angles DataFrame from row dicts."""
    df = pd.DataFrame(rows)
    for col in ["t1", "t2", "t3", "style", "theta0_deg", "k"]:
        if col not in df.columns:
            df[col] = None
    return df