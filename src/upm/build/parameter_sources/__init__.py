"""Parameter sources package for FRC builder.

This package provides the ParameterSource protocol and implementations
for resolving force field parameters from various sources.

The protocol-based design allows:
- Different sources (ParameterSet, embedded base, defaults) to be used interchangeably
- Composition via ChainedSource for fallback behavior
- Easy testing via mock sources

Available Sources:
    - ParameterSource: Protocol defining the parameter lookup interface
    - ChainedSource: Composite source that chains multiple sources with fallback
    - PlaceholderSource: Provides generic/placeholder parameters based on element types
    - ParameterSetSource: Provides parameters from USM-derived ParameterSet dict
    - ExistingFRCSource: Provides parameters extracted from an existing .frc file

Example:
    >>> from upm.build.parameter_sources import (
    ...     ChainedSource, PlaceholderSource, ParameterSetSource
    ... )
    >>> element_map = {"C_MOF": "C", "H_MOF": "H"}
    >>> parameterset = {"atom_types": {"C_MOF": {"mass_amu": 12.0, ...}}}
    >>> 
    >>> # Create a chained source: try ParameterSetSource first, fallback to placeholder
    >>> source = ChainedSource([
    ...     ParameterSetSource(parameterset),
    ...     PlaceholderSource(element_map),
    ... ])
    >>> 
    >>> # Atom type info comes from ParameterSetSource
    >>> info = source.get_atom_type_info("C_MOF")
    >>> # Bond params fall back to PlaceholderSource (not in ParameterSetSource)
    >>> bond = source.get_bond_params("C_MOF", "H_MOF")
"""

from .existing_frc import ExistingFRCSource
from .parameterset import ParameterSetSource
from .placeholder import PlaceholderSource
from .protocol import ChainedSource, ParameterSource

__all__ = [
    "ParameterSource",
    "ChainedSource",
    "PlaceholderSource",
    "ParameterSetSource",
    "ExistingFRCSource",
]
