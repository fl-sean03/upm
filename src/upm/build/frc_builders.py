"""FRC builder facade — re-exports from internal modules.

All builder functions are available here for backward compatibility.
New code should use FRCBuilder directly (from upm.build import FRCBuilder).

Builders:
    - build_frc_nonbond_only: Nonbonded-only .frc for CLI
    - build_frc_cvff_with_generic_bonded: Full builder with generic bonded params
    - build_frc_from_existing: Build from existing source FRC

Utilities:
    - generate_generic_bonded_params: Generate formatted bonded parameter lines
    - filter_frc_tables: Filter parsed FRC tables to required atom types

Exception:
    - MissingTypesError: Raised when atom types are missing
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from upm.codecs.msi_frc import write_frc
from upm.core.tables import TABLE_COLUMN_ORDER, normalize_atom_types
from upm.core.validate import validate_atom_types

# Canonical imports
from upm.build.validators import MissingTypesError
from upm.build.frc_helpers import lj_sigma_eps_to_ab

# Re-export legacy builders (now backed by FRCBuilder)
from upm.build._legacy import (
    build_frc_cvff_with_generic_bonded,
    build_frc_from_existing,
)

# Utilities (still standalone)
from upm.build._frc_filters import filter_frc_tables
from upm.build._frc_generic_bonded import generate_generic_bonded_params


def build_frc_nonbond_only(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    out_path: str | Path,
) -> str:
    """Build a nonbonded-only .frc from validated TermSet + ParameterSet.

    Args:
        termset: output of read_termset_json() or equivalent.
        parameterset: output of read_parameterset_json() or equivalent.
        out_path: where to write .frc.

    Returns:
        The output path as a string.
    """
    ts_types = list(termset.get("atom_types") or [])
    ps_map = dict(parameterset.get("atom_types") or {})

    missing = sorted([t for t in ts_types if t not in ps_map])
    if missing:
        raise MissingTypesError(tuple(missing))

    rows: list[dict[str, Any]] = []
    for at in ts_types:
        rec = ps_map[at]
        mass = float(rec["mass_amu"])
        sigma = float(rec["lj_sigma_angstrom"])
        eps = float(rec["lj_epsilon_kcal_mol"])
        a, b = lj_sigma_eps_to_ab(sigma=sigma, epsilon=eps)
        element = rec.get("element")
        if element is None:
            element = "X"

        rows.append(
            {
                "atom_type": at,
                "element": element,
                "mass_amu": mass,
                "vdw_style": "lj_ab_12_6",
                "lj_a": a,
                "lj_b": b,
                "notes": None,
            }
        )

    df = pd.DataFrame(rows)
    df = df.loc[:, TABLE_COLUMN_ORDER["atom_types"]]
    df = normalize_atom_types(df)
    validate_atom_types(df)

    p = Path(out_path)
    write_frc(p, tables={"atom_types": df}, mode="minimal")
    return str(p)


__all__ = [
    "MissingTypesError",
    "build_frc_nonbond_only",
    "build_frc_cvff_with_generic_bonded",
    "build_frc_from_existing",
    "generate_generic_bonded_params",
    "filter_frc_tables",
]
