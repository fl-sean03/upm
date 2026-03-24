"""Placeholder parameter source for FRC builder.

This module provides the PlaceholderSource class that generates generic/placeholder
parameters based on element types. It is used as a fallback when real parameters
aren't available from other sources.

The placeholder parameters are tool-satisfying (not physical) - they exist to
enable msi2lmp.exe to run without the -ignore flag.
"""

from __future__ import annotations

from typing import Optional

from ..frc_helpers import (
    placeholder_bond_params as _placeholder_bond_params,
    placeholder_angle_params as _placeholder_angle_params,
)
from ..entries import (
    AngleParams,
    BondParams,
    OOPParams,
    TorsionParams,
)


class PlaceholderSource:
    """Provides generic/placeholder parameters based on element types.

    This source generates tool-satisfying (not physical) parameters
    to enable msi2lmp.exe to run without the -ignore flag.

    **DOES NOT provide** (returns None):
        - get_atom_type_info() - mass/element must come from external source
        - get_nonbond_params() - LJ A/B must come from external source

    **DOES provide**:
        - get_bond_params() - based on element pair (k, r0)
        - get_angle_params() - based on center element (theta0, k)
        - get_torsion_params() - zero-barrier defaults
        - get_oop_params() - minimal defaults (kchi=0.1, n=2, chi0=180)

    Example:
        >>> element_map = {"C_MOF": "C", "H_MOF": "H", "Zn_MOF": "Zn"}
        >>> source = PlaceholderSource(element_map)
        >>> bond = source.get_bond_params("H_MOF", "C_MOF")
        >>> bond.k, bond.r0  # H bond defaults
        (340.0, 1.09)
    """

    def __init__(self, element_map: dict[str, str]) -> None:
        """Initialize with atom_type → element mapping.

        Args:
            element_map: Mapping from atom type names to element symbols.
                         Example: {"C_MOF": "C", "H_MOF": "H", "Zn_MOF": "Zn"}
        """
        self._element_map = element_map

    def get_atom_type_info(self, atom_type: str) -> None:
        """Return None - mass/element must come from external source.

        Args:
            atom_type: The atom type name (unused).

        Returns:
            None (always).
        """
        return None

    def get_nonbond_params(self, atom_type: str) -> None:
        """Return None - LJ A/B must come from external source.

        Args:
            atom_type: The atom type name (unused).

        Returns:
            None (always).
        """
        return None

    def get_bond_params(self, t1: str, t2: str) -> Optional[BondParams]:
        """Get placeholder bond parameters based on element pair.

        Uses element-based logic:
        - Any bond involving H: (k=340.0, r0=1.09)
        - Any bond involving Zn: (k=150.0, r0=2.05)
        - Otherwise: (k=300.0, r0=1.50)

        Args:
            t1: First atom type in the bond.
            t2: Second atom type in the bond.

        Returns:
            BondParams with placeholder values.
        """
        el1 = self._element_map.get(t1, "X").upper()
        el2 = self._element_map.get(t2, "X").upper()
        k, r0 = _placeholder_bond_params(t1_el=el1, t2_el=el2)
        return BondParams(r0=r0, k=k)

    def get_angle_params(self, t1: str, t2: str, t3: str) -> Optional[AngleParams]:
        """Get placeholder angle parameters based on center element.

        Uses center element-based logic:
        - Center Zn: (90.0°, k=50.0)
        - Center O: (109.5°, k=50.0)
        - Center N: (120.0°, k=50.0)
        - Center C: (109.5°, k=50.0)
        - Otherwise: (120.0°, k=50.0)

        Args:
            t1: First atom type (end atom).
            t2: Center atom type (apex).
            t3: Third atom type (other end atom).

        Returns:
            AngleParams with placeholder values.
        """
        center_el = self._element_map.get(t2, "X")
        theta0, k = _placeholder_angle_params(center_el=center_el)
        return AngleParams(theta0_deg=theta0, k=k)

    def get_torsion_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[TorsionParams]:
        """Get placeholder torsion parameters (zero-barrier defaults).

        Args:
            t1: First atom type.
            t2: Second atom type (central bond start).
            t3: Third atom type (central bond end).
            t4: Fourth atom type.

        Returns:
            TorsionParams with zero-barrier defaults (kphi=0.0, n=1, phi0=0.0).
        """
        return TorsionParams(kphi=0.0, n=1, phi0=0.0)

    def get_oop_params(
        self, t1: str, t2: str, t3: str, t4: str
    ) -> Optional[OOPParams]:
        """Get placeholder out-of-plane parameters (minimal defaults).

        Note: msi2lmp.exe v3.9.6 requires non-zero OOP parameters
        (0.1/2/180) to avoid segfaults. Zero values cause undefined behavior.

        Args:
            t1: Central atom type.
            t2: First bonded atom type.
            t3: Second bonded atom type.
            t4: Third bonded atom type.

        Returns:
            OOPParams with minimal defaults (kchi=0.1, n=2, chi0=180.0).
        """
        return OOPParams(kchi=0.1, n=2, chi0=180.0)


__all__ = [
    "PlaceholderSource",
]
