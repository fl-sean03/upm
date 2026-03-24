"""UPM Build module - minimal CVFF .frc file generation.

NEW API (Recommended):
    from upm.build import FRCBuilder, FRCBuilderConfig
    from upm.build.parameter_sources import ChainedSource, ParameterSetSource, PlaceholderSource

    source = ChainedSource([ParameterSetSource(ps), PlaceholderSource(elem_map)])
    builder = FRCBuilder(termset, source)
    builder.write("output.frc")

LEGACY API (Still supported):
    from upm.build import build_frc_cvff_with_generic_bonded
    build_frc_cvff_with_generic_bonded(termset, parameterset, out_path="output.frc")
"""

from pathlib import Path
from typing import Union

# New unified API
from .frc_builder import FRCBuilder, FRCBuilderConfig
from .parameter_sources import (
    ParameterSource,
    ChainedSource,
    PlaceholderSource,
    ParameterSetSource,
    ExistingFRCSource,
)
from .entries import (
    AtomTypeInfo,
    NonbondParams,
    BondParams,
    AngleParams,
    TorsionParams,
    OOPParams,
)
from .validators import MissingTypesError
from .formatters import (
    format_atom_type_entry,
    format_equivalence_entry,
    format_bond_entry,
    format_angle_entry,
    format_nonbond_entry,
)
from .alias_manager import AliasConfig, build_alias_map

# Templates (unchanged)
from .frc_templates import CVFF_CANONICAL_TEMPLATE, CVFF_SKELETON, CVFF_MINIMAL_SKELETON

# Legacy API (backward compatible)
from ._legacy import (
    build_frc_cvff_with_generic_bonded,
    build_frc_from_existing,
)

# Keep existing exports for full backward compatibility
from .frc_builders import (
    build_frc_nonbond_only,
    generate_generic_bonded_params,
    filter_frc_tables,
)
from .frc_input import (
    AtomTypeEntry,
    BondEntry,
    AngleEntry,
    TorsionEntry,
    OOPEntry,
    NonbondEntry,
    FRCInput,
    build_frc_input,
)
from .frc_writer import write_cvff_frc


def build_minimal_cvff_frc(
    termset: dict,
    parameterset: dict,
    out_path: Union[str, Path],
) -> str:
    """Build minimal CVFF .frc from USM-derived data.

    This is a LEGACY API. For new code, prefer FRCBuilder.

    Args:
        termset: Output of derive_termset_v0_1_2() with keys:
            - atom_types, bond_types, angle_types, dihedral_types, improper_types
        parameterset: Output of derive_parameterset_v0_1_2() with:
            - atom_types mapping with mass, LJ params, element
        out_path: Where to write the .frc file.

    Returns:
        The output path as a string.

    Example:
        >>> from upm.build import build_minimal_cvff_frc
        >>> build_minimal_cvff_frc(termset, parameterset, "cvff.frc")
        'cvff.frc'
    """
    frc_input = build_frc_input(termset, parameterset)
    return write_cvff_frc(frc_input, out_path)


__all__ = [
    # New unified API (RECOMMENDED)
    "FRCBuilder",
    "FRCBuilderConfig",
    "ParameterSource",
    "ChainedSource",
    "PlaceholderSource",
    "ParameterSetSource",
    "ExistingFRCSource",
    # Entry types
    "AtomTypeInfo",
    "NonbondParams",
    "BondParams",
    "AngleParams",
    "TorsionParams",
    "OOPParams",
    # Validators
    "MissingTypesError",
    # Formatters
    "format_atom_type_entry",
    "format_equivalence_entry",
    "format_bond_entry",
    "format_angle_entry",
    "format_nonbond_entry",
    # Alias management
    "AliasConfig",
    "build_alias_map",
    # Templates
    "CVFF_CANONICAL_TEMPLATE",
    "CVFF_SKELETON",
    "CVFF_MINIMAL_SKELETON",
    # Legacy API (backward compatible)
    "build_frc_cvff_with_generic_bonded",
    "build_frc_from_existing",
    "build_frc_nonbond_only",
    "generate_generic_bonded_params",
    "filter_frc_tables",
    # Old FRCInput API (backward compatible)
    "AtomTypeEntry",
    "BondEntry",
    "AngleEntry",
    "TorsionEntry",
    "OOPEntry",
    "NonbondEntry",
    "FRCInput",
    "build_frc_input",
    "write_cvff_frc",
    # High-level legacy API
    "build_minimal_cvff_frc",
]
