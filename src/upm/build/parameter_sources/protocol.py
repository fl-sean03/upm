"""Protocol definition for FRC parameter sources.

This module defines the ParameterSource protocol that all parameter
providers must implement, and the ChainedSource composite that enables
fallback behavior across multiple sources.

The Protocol pattern allows different parameter sources (e.g., from
ParameterSet, from embedded base, from skeleton templates) to be
used interchangeably and composed into lookup chains.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..entries import (
    AngleParams,
    AtomTypeInfo,
    BondIncrementParams,
    BondParams,
    NonbondParams,
    OOPParams,
    TorsionParams,
)


@runtime_checkable
class ParameterSource(Protocol):
    """Protocol for FRC parameter sources.

    Implementations provide lookup methods for each parameter type.
    All methods return Optional values - None indicates the parameter
    is not available from this source.

    The @runtime_checkable decorator allows isinstance() checks
    against this protocol.
    """

    def get_atom_type_info(self, atom_type: str) -> Optional[AtomTypeInfo]:
        """Look up atom type information.

        Args:
            atom_type: The atom type name.

        Returns:
            AtomTypeInfo if found, None otherwise.
        """
        ...

    def get_nonbond_params(self, atom_type: str) -> Optional[NonbondParams]:
        """Look up nonbond (LJ 12-6) parameters.

        Args:
            atom_type: The atom type name.

        Returns:
            NonbondParams if found, None otherwise.
        """
        ...

    def get_bond_params(self, t1: str, t2: str) -> Optional[BondParams]:
        """Look up bond parameters.

        Args:
            t1: First atom type in the bond.
            t2: Second atom type in the bond.

        Returns:
            BondParams if found, None otherwise.
        """
        ...

    def get_angle_params(self, t1: str, t2: str, t3: str) -> Optional[AngleParams]:
        """Look up angle parameters.

        Args:
            t1: First atom type (end atom).
            t2: Center atom type (apex).
            t3: Third atom type (other end atom).

        Returns:
            AngleParams if found, None otherwise.
        """
        ...

    def get_torsion_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[TorsionParams]:
        """Look up torsion (dihedral) parameters.

        Args:
            t1: First atom type.
            t2: Second atom type (central bond start).
            t3: Third atom type (central bond end).
            t4: Fourth atom type.

        Returns:
            TorsionParams if found, None otherwise.
        """
        ...

    def get_oop_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[OOPParams]:
        """Look up out-of-plane (improper) parameters.

        Args:
            t1: Central atom type.
            t2: First bonded atom type.
            t3: Second bonded atom type.
            t4: Third bonded atom type.

        Returns:
            OOPParams if found, None otherwise.
        """
        ...

    def get_bond_increment_params(self, t1: str, t2: str) -> Optional[BondIncrementParams]:
        """Look up bond increment parameters.

        Args:
            t1: First atom type in the bond.
            t2: Second atom type in the bond.

        Returns:
            BondIncrementParams if found, None otherwise.
        """
        ...


class ChainedSource:
    """Composite source that chains multiple sources with fallback.

    When looking up a parameter, tries each source in order until
    one returns a non-None result. This enables layered parameter
    resolution (e.g., try ParameterSet first, fall back to defaults).

    Example:
        >>> source = ChainedSource([param_set_source, default_source])
        >>> params = source.get_bond_params("c", "o")  # tries each in order
    """

    def __init__(self, sources: list[ParameterSource]) -> None:
        """Initialize with ordered list of sources.

        Args:
            sources: List of ParameterSource implementations to chain.
                     Earlier sources have higher priority.
        """
        self._sources = sources

    def get_atom_type_info(self, atom_type: str) -> Optional[AtomTypeInfo]:
        """Look up atom type info, trying each source in order."""
        for source in self._sources:
            result = source.get_atom_type_info(atom_type)
            if result is not None:
                return result
        return None

    def get_nonbond_params(self, atom_type: str) -> Optional[NonbondParams]:
        """Look up nonbond params, trying each source in order."""
        for source in self._sources:
            result = source.get_nonbond_params(atom_type)
            if result is not None:
                return result
        return None

    def get_bond_params(self, t1: str, t2: str) -> Optional[BondParams]:
        """Look up bond params, trying each source in order."""
        for source in self._sources:
            result = source.get_bond_params(t1, t2)
            if result is not None:
                return result
        return None

    def get_angle_params(self, t1: str, t2: str, t3: str) -> Optional[AngleParams]:
        """Look up angle params, trying each source in order."""
        for source in self._sources:
            result = source.get_angle_params(t1, t2, t3)
            if result is not None:
                return result
        return None

    def get_torsion_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[TorsionParams]:
        """Look up torsion params, trying each source in order."""
        for source in self._sources:
            result = source.get_torsion_params(t1, t2, t3, t4)
            if result is not None:
                return result
        return None

    def get_oop_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[OOPParams]:
        """Look up out-of-plane params, trying each source in order."""
        for source in self._sources:
            result = source.get_oop_params(t1, t2, t3, t4)
            if result is not None:
                return result
        return None

    def get_bond_increment_params(self, t1: str, t2: str) -> Optional[BondIncrementParams]:
        """Look up bond increment params, trying each source in order."""
        for source in self._sources:
            if hasattr(source, "get_bond_increment_params"):
                result = source.get_bond_increment_params(t1, t2)
                if result is not None:
                    return result
        return None


__all__ = [
    "ParameterSource",
    "ChainedSource",
]
