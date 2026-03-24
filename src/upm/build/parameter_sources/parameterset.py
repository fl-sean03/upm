"""ParameterSet parameter source for FRC builder.

This module provides the ParameterSetSource class that extracts parameters
from a USM-derived ParameterSet dictionary. It provides atom type info and
nonbond parameters, but not bonded parameters (those should come from
ChainedSource with PlaceholderSource fallback).
"""

from __future__ import annotations

from typing import Any, Optional

from ..alias_manager import element_to_connects
from ..frc_helpers import lj_sigma_eps_to_ab as _lj_sigma_eps_to_ab
from ..entries import (
    AngleParams,
    AtomTypeInfo,
    BondParams,
    NonbondParams,
    OOPParams,
    TorsionParams,
)


class ParameterSetSource:
    """Provides parameters from USM-derived ParameterSet dict.

    **DOES provide**:
        - get_atom_type_info() - mass, element, connects from parameterset
        - get_nonbond_params() - LJ σ/ε → A/B conversion

    **DOES NOT provide** (returns None):
        - get_bond_params() - use ChainedSource with PlaceholderSource fallback
        - get_angle_params() - use ChainedSource with PlaceholderSource fallback
        - get_torsion_params() - use ChainedSource with PlaceholderSource fallback
        - get_oop_params() - use ChainedSource with PlaceholderSource fallback

    Example:
        >>> parameterset = {
        ...     "atom_types": {
        ...         "C_MOF": {
        ...             "mass_amu": 12.0,
        ...             "lj_sigma_angstrom": 3.4,
        ...             "lj_epsilon_kcal_mol": 0.1,
        ...             "element": "C"
        ...         }
        ...     }
        ... }
        >>> source = ParameterSetSource(parameterset)
        >>> info = source.get_atom_type_info("C_MOF")
        >>> info.mass_amu
        12.0
        >>> info.element
        'C'
    """

    def __init__(self, parameterset: dict[str, Any]) -> None:
        """Initialize with USM-derived parameterset dictionary.

        Args:
            parameterset: Dict with "atom_types" key containing a mapping
                          of atom type names to their parameters.
        """
        self._ps = parameterset.get("atom_types", {})

    def get_atom_type_info(self, atom_type: str) -> Optional[AtomTypeInfo]:
        """Get atom type information (mass, element, connects).

        Args:
            atom_type: The atom type name.

        Returns:
            AtomTypeInfo if found in parameterset, None otherwise.
        """
        rec = self._ps.get(atom_type)
        if rec is None:
            return None
        element = str(rec.get("element", "X"))
        return AtomTypeInfo(
            mass_amu=float(rec["mass_amu"]),
            element=element,
            connects=element_to_connects(element),
        )

    def get_nonbond_params(self, atom_type: str) -> Optional[NonbondParams]:
        """Get nonbond (LJ 12-6) parameters with σ/ε → A/B conversion.

        Converts from σ/ε form to A/B form:
            A = 4 * ε * σ^12
            B = 4 * ε * σ^6

        Args:
            atom_type: The atom type name.

        Returns:
            NonbondParams with A/B coefficients if found, None otherwise.
        """
        rec = self._ps.get(atom_type)
        if rec is None:
            return None
        sigma = float(rec["lj_sigma_angstrom"])
        epsilon = float(rec["lj_epsilon_kcal_mol"])
        a, b = _lj_sigma_eps_to_ab(sigma=sigma, epsilon=epsilon)
        return NonbondParams(lj_a=a, lj_b=b)

    def get_bond_params(self, t1: str, t2: str) -> Optional[BondParams]:
        """Return None - bond params should come from PlaceholderSource fallback.

        Args:
            t1: First atom type in the bond.
            t2: Second atom type in the bond.

        Returns:
            None (always).
        """
        return None

    def get_angle_params(self, t1: str, t2: str, t3: str) -> Optional[AngleParams]:
        """Return None - angle params should come from PlaceholderSource fallback.

        Args:
            t1: First atom type (end atom).
            t2: Center atom type (apex).
            t3: Third atom type (other end atom).

        Returns:
            None (always).
        """
        return None

    def get_torsion_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[TorsionParams]:
        """Return None - torsion params should come from PlaceholderSource fallback.

        Args:
            t1: First atom type.
            t2: Second atom type (central bond start).
            t3: Third atom type (central bond end).
            t4: Fourth atom type.

        Returns:
            None (always).
        """
        return None

    def get_oop_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[OOPParams]:
        """Return None - OOP params should come from PlaceholderSource fallback.

        Args:
            t1: Central atom type.
            t2: First bonded atom type.
            t3: Second bonded atom type.
            t4: Third bonded atom type.

        Returns:
            None (always).
        """
        return None


__all__ = [
    "ParameterSetSource",
]
