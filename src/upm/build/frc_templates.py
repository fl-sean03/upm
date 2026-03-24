"""FRC skeleton templates for CVFF forcefield files.

This module contains the canonical template used by FRC builders to generate
msi2lmp.exe-compatible forcefield files.

Templates:
    - CVFF_CANONICAL_TEMPLATE: The ONE canonical template with all required sections
    - CVFF_SKELETON: (DEPRECATED) Alias to CVFF_CANONICAL_TEMPLATE for backward compatibility
    - CVFF_MINIMAL_SKELETON: (DEPRECATED) Alias to CVFF_CANONICAL_TEMPLATE for backward compatibility

IMPORTANT: All FRC builders should use CVFF_CANONICAL_TEMPLATE. The deprecated
aliases exist only for backward compatibility during migration.
"""

from __future__ import annotations


# =============================================================================
# CVFF Canonical Template (THE ONE TRUE TEMPLATE)
# =============================================================================
#
# Based on test_U_no_hbond.frc - the proven minimal structure that works with
# msi2lmp.exe. Validated through Phase 7-11 experiments (M25-M31).
#
# CRITICAL REQUIREMENTS (see docs/methods/MSI2LMP_FRC_REQUIREMENTS.md):
# 1. !BIOSYM header is REQUIRED by msi2lmp.exe
# 2. #define section MUST be empty (no entry lists - causes segfault)
# 3. All 12 sections must be present in order
# 4. Column headers are REQUIRED for each section
#
# Sections (in order):
#   1. !BIOSYM forcefield 1
#   2. #version
#   3. #define cvff (empty)
#   4. #atom_types cvff
#   5. #equivalence cvff
#   6. #auto_equivalence cvff_auto
#   7. #morse_bond cvff
#   8. #quadratic_bond cvff
#   9. #quadratic_angle cvff
#  10. #torsion_1 cvff
#  11. #out_of_plane cvff
#  12. #nonbond(12-6) cvff
#  13. #bond_increments cvff
#
# Placeholders:
#   {atom_types_entries}, {equivalence_entries}, {auto_equivalence_entries},
#   {bond_entries}, {angle_entries}, {torsion_entries}, {oop_entries},
#   {nonbond_entries}, {bond_increments_entries}

CVFF_CANONICAL_TEMPLATE: str = """!BIOSYM forcefield          1

#version cvff.frc	1.0	01-Jan-00

#define cvff

> Minimal cvff forcefield

!Ver  Ref 		Function		Label
!---- ---   ---------------------------------	------
#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
{atom_types_entries}
#equivalence	cvff

!Ver  Ref   Type  NonB     Bond    Angle    Torsion    OOP
!---- ---   ----  ----     ----    -----    -------    ----
{equivalence_entries}
#auto_equivalence	cvff_auto

!Ver  Ref   Type  NonB Bond   Bond     Angle    Angle     Torsion   Torsion      OOP      OOP
!---- ---   ----  ---- ------ ----  ---------- --------- --------- -----------  -------- -----------
{auto_equivalence_entries}#morse_bond	cvff

!Ver  Ref     I     J          R0         D           ALPHA
!---- ---    ----  ----     -------    --------      -------
#quadratic_bond	cvff

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
{bond_entries}
#quadratic_angle	cvff

!Ver  Ref     I     J     K       Theta0         K2
!---- ---    ----  ----  ----    --------     -------
{angle_entries}
#torsion_1	cvff

!Ver  Ref     I     J     K     L           Kphi        n           Phi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{torsion_entries}#out_of_plane	cvff

!Ver  Ref     I     J     K     L           Kchi        n           Chi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{oop_entries}#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
{nonbond_entries}
#bond_increments        cvff

!Ver  Ref     I     J       DeltaIJ     DeltaJI
!---- ---    ----  ----     -------     -------
{bond_increments_entries}
"""


# =============================================================================
# DEPRECATED ALIASES (for backward compatibility only)
# =============================================================================
#
# WARNING: These are deprecated. Use CVFF_CANONICAL_TEMPLATE directly.
# These aliases use different placeholder names for compatibility with
# existing code that hasn't been migrated yet.


# CVFF_SKELETON - used by frc_writer.py (different placeholder names)
# This template uses {atom_types}, {equivalences}, etc. instead of {atom_types_entries}
CVFF_SKELETON: str = """!BIOSYM forcefield          1

#version cvff.frc	1.0	01-Jan-00

#define cvff

> Minimal cvff forcefield for msi2lmp compatibility

!Ver  Ref 		Function		Label
!---- ---   ---------------------------------	------
#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
{atom_types}
#equivalence	cvff

!		         	  Equivalences
!                 -----------------------------------------
!Ver  Ref   Type  NonB     Bond    Angle    Torsion    OOP
!---- ---   ----  ----     ----    -----    -------    ----
{equivalences}
#auto_equivalence	cvff_auto

!		         	  Equivalences
!                 -----------------------------------------
!Ver  Ref   Type  NonB Bond   Bond     Angle    Angle     Torsion   Torsion      OOP      OOP
!                      Inct           End atom Apex atom End Atoms Center Atoms End Atom Center Atom
!---- ---   ----  ---- ------ ----  ---------- --------- --------- -----------  -------- -----------
{auto_equivalences}
#morse_bond	cvff

!Ver  Ref     I     J          R0         D           ALPHA
!---- ---    ----  ----     -------    --------      -------
#quadratic_bond	cvff

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
{bonds}
#quadratic_angle	cvff

!Ver  Ref     I     J     K       Theta0         K2
!---- ---    ----  ----  ----    --------     -------
{angles}
#torsion_1	cvff

!Ver  Ref     I     J     K     L           Kphi        n           Phi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{torsions}
#out_of_plane	cvff

!Ver  Ref     I     J     K     L           Kchi        n           Chi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{oops}
#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A               B
!---- ---    ----      ---------       ---------
{nonbonds}
#bond_increments        cvff

!Ver  Ref     I     J       DeltaIJ     DeltaJI
!---- ---    ----  ----     -------     -------
"""


# CVFF_MINIMAL_SKELETON - used by frc_builders.py
# Now points to canonical template which has BIOSYM header and all sections
CVFF_MINIMAL_SKELETON: str = CVFF_CANONICAL_TEMPLATE


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CVFF_CANONICAL_TEMPLATE",
    "CVFF_SKELETON",
    "CVFF_MINIMAL_SKELETON",
]
