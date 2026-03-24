"""Backward-compatible wrappers for deprecated FRC builder functions.

These functions wrap the new FRCBuilder API to maintain compatibility
with existing code. They delegate to FRCBuilder internally.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .frc_builder import FRCBuilder, FRCBuilderConfig
from .parameter_sources import ChainedSource, ParameterSetSource, PlaceholderSource, ExistingFRCSource
from .validators import MissingTypesError


def build_frc_cvff_with_generic_bonded(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    out_path: str | Path,
    msi2lmp_max_atom_type_len: int = 5,
    expand_aliases: bool = False,
) -> str:
    """Build minimal CVFF .frc with generic bonded params.

    RECOMMENDED: This builder produces msi2lmp-compatible .frc files
    with placeholder bonded parameters.

    Internally uses FRCBuilder with ChainedSource.

    Args:
        termset: Dictionary containing atom_types, bond_types, angle_types,
            dihedral_types, and improper_types lists.
        parameterset: Dictionary containing atom_types with mass, LJ parameters,
            and element information.
        out_path: Output file path for the .frc file.
        msi2lmp_max_atom_type_len: Maximum atom type name length for msi2lmp
            compatibility.
        expand_aliases: Whether to expand long atom type names into aliases.

    Returns:
        Output path as string.
    """
    # Build element map for PlaceholderSource
    ps_map = parameterset.get("atom_types", {})
    element_map = {
        at: ps_map.get(at, {}).get("element", "X")
        for at in termset.get("atom_types", [])
    }

    source = ChainedSource([
        ParameterSetSource(parameterset),
        PlaceholderSource(element_map),
    ])

    config = FRCBuilderConfig(
        msi2lmp_max_type_len=msi2lmp_max_atom_type_len,
        expand_aliases=expand_aliases,
        strict=True,
    )

    builder = FRCBuilder(termset, source, config)
    return builder.write(out_path)


def build_frc_from_existing(
    termset: dict[str, Any],
    source_frc_path: str | Path,
    *,
    out_path: str | Path,
    parameterset: dict[str, Any] | None = None,
    strict: bool = True,
) -> str:
    """Build minimal FRC by extracting real params from existing FRC.

    Internally uses FRCBuilder with ExistingFRCSource.

    Args:
        termset: Dictionary containing atom_types, bond_types, angle_types,
            dihedral_types, and improper_types lists.
        source_frc_path: Path to existing .frc file to extract parameters from.
        out_path: Output file path for the new .frc file.
        parameterset: Optional parameterset for additional parameters.
        strict: If True, raise MissingTypesError for missing parameters.

    Returns:
        Output path as string.
    """
    source = ExistingFRCSource(Path(source_frc_path), termset)

    config = FRCBuilderConfig(
        strict=strict,
        expand_aliases=False,
    )

    builder = FRCBuilder(termset, source, config)
    return builder.write(out_path)


__all__ = [
    "MissingTypesError",
    "build_frc_cvff_with_generic_bonded",
    "build_frc_from_existing",
]
