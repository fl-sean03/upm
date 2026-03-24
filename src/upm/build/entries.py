"""Parameter type dataclasses for FRC builder.

This module defines frozen dataclasses representing parameter entries
for various FRC sections. These are the canonical representations used
by ParameterSource implementations to return lookup results.

All dataclasses are frozen (immutable) to ensure parameter data
integrity throughout the build pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AtomTypeInfo:
    """Parameters for #atom_types section.

    Attributes:
        mass_amu: Atomic mass in atomic mass units.
        element: Element symbol (e.g., 'C', 'N', 'O').
        connects: Typical connectivity/valence count.
    """

    mass_amu: float
    element: str
    connects: int


@dataclass(frozen=True)
class NonbondParams:
    """Parameters for #nonbond(12-6) section.

    Uses A/B form of Lennard-Jones 12-6 potential:
        U = A/r^12 - B/r^6

    Attributes:
        lj_a: A coefficient (repulsive term).
        lj_b: B coefficient (attractive term).
    """

    lj_a: float
    lj_b: float


@dataclass(frozen=True)
class BondParams:
    """Parameters for #quadratic_bond section.

    Quadratic bond potential:
        U = k * (r - r0)^2

    Attributes:
        r0: Equilibrium bond length in Angstroms.
        k: Force constant in kcal/(mol·Å²).
    """

    r0: float
    k: float


@dataclass(frozen=True)
class AngleParams:
    """Parameters for #quadratic_angle section.

    Quadratic angle potential:
        U = k * (theta - theta0)^2

    Attributes:
        theta0_deg: Equilibrium angle in degrees.
        k: Force constant in kcal/(mol·rad²).
    """

    theta0_deg: float
    k: float


@dataclass(frozen=True)
class TorsionParams:
    """Parameters for #torsion_1 section.

    Cosine torsion potential:
        U = kphi * (1 + cos(n*phi - phi0))

    Attributes:
        kphi: Torsional barrier height in kcal/mol.
        n: Periodicity (integer, typically 1-6).
        phi0: Phase angle in degrees.
    """

    kphi: float
    n: int
    phi0: float


@dataclass(frozen=True)
class OOPParams:
    """Parameters for #out_of_plane section.

    Out-of-plane (improper torsion) potential:
        U = kchi * (1 + cos(n*chi - chi0))

    Attributes:
        kchi: Out-of-plane force constant in kcal/mol.
        n: Periodicity (integer, typically 2).
        chi0: Equilibrium angle in degrees (typically 0 or 180).
    """

    kchi: float
    n: int
    chi0: float


@dataclass(frozen=True)
class BondIncrementParams:
    """Parameters for #bond_increments section.

    Bond increment charges for partial charge assignment.

    Attributes:
        delta_ij: Charge increment for atom i in i-j bond.
        delta_ji: Charge increment for atom j in i-j bond.
    """

    delta_ij: float
    delta_ji: float


__all__ = [
    "AtomTypeInfo",
    "NonbondParams",
    "BondParams",
    "AngleParams",
    "TorsionParams",
    "OOPParams",
    "BondIncrementParams",
]
