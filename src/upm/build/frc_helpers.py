"""FRC builder helper functions and utilities.

This module contains:
- Exception classes for FRC builders
- Helper functions for parameter conversion
- Section parsing utilities
- Skeleton template formatting functions

These are used by the main builder functions in frc_builders.py.
"""

from __future__ import annotations

import re
from typing import Any


# =============================================================================
# Exception Classes (canonical source: validators.py)
# =============================================================================

from upm.build.validators import MissingTypesError  # noqa: E402 — re-export for compat


# =============================================================================
# Parameter Conversion Functions
# =============================================================================


def lj_sigma_eps_to_ab(*, sigma: float, epsilon: float) -> tuple[float, float]:
    """Convert LJ sigma/epsilon to A/B coefficients for MSI 12-6 form.
    
    A = 4*eps*sigma^12
    B = 4*eps*sigma^6
    
    Args:
        sigma: LJ sigma parameter in Angstroms.
        epsilon: LJ epsilon parameter in kcal/mol.
    
    Returns:
        Tuple of (A, B) coefficients.
    """
    s6 = sigma**6
    a = 4.0 * epsilon * (s6**2)
    b = 4.0 * epsilon * s6
    return a, b


def placeholder_bond_params(*, t1_el: str, t2_el: str) -> tuple[float, float]:
    """Deterministic placeholder (k, r0) for #quadratic_bond.

    This is *tool-satisfying, not physical*. It exists to prevent msi2lmp.exe
    from stalling during parameter lookup when a bonded key is absent.

    Policy:
    - any bond involving H: (k=340.0, r0=1.09)
    - any bond involving Zn: (k=150.0, r0=2.05)
    - otherwise: (k=300.0, r0=1.50)
    
    Args:
        t1_el: Element symbol for first atom type.
        t2_el: Element symbol for second atom type.
    
    Returns:
        Tuple of (k, r0) parameters.
    """
    els = {t1_el.strip().upper(), t2_el.strip().upper()}
    if "H" in els:
        return (340.0, 1.09)
    if "ZN" in els:
        return (150.0, 2.05)
    return (300.0, 1.50)


def placeholder_angle_params(*, center_el: str) -> tuple[float, float]:
    """Deterministic placeholder (theta0_deg, k) for #quadratic_angle.

    Tool-satisfying defaults (not physical).

    Policy (updated for msi2lmp.exe v3.9.6 compatibility):
    - center Zn: (90.0, 50.0) - tetrahedral-like coordination
    - center O:  (109.5, 50.0) - tetrahedral
    - center N:  (120.0, 50.0) - trigonal planar
    - center C:  (109.5, 50.0) - tetrahedral
    - otherwise: (120.0, 50.0)
    
    Note: K2=50.0 is used consistently for all angles to match validated
    working .frc files. Variable K2 values can cause msi2lmp.exe segfaults.
    
    Args:
        center_el: Element symbol for center (apex) atom.
    
    Returns:
        Tuple of (theta0_deg, k) parameters.
    """
    el = (center_el or "X").strip().upper()
    if el == "ZN":
        return (90.0, 50.0)
    if el == "O":
        return (109.5, 50.0)
    if el == "N":
        return (120.0, 50.0)
    if el == "C":
        return (109.5, 50.0)
    return (120.0, 50.0)


# =============================================================================
# Section Parser for CVFF Minimal Base
# =============================================================================


def parse_embedded_base_sections(content: str) -> dict[str, tuple[int, int, list[str]]]:
    """Parse embedded base into section name -> (start_line, end_line, lines) mapping.
    
    Section boundaries are identified by lines starting with # (except #version, #define, ##).
    The preamble (lines before first data section) is treated as a special "preamble" section.
    
    Args:
        content: The embedded base content string
        
    Returns:
        Dict mapping section identifier to (start_idx, end_idx, lines) tuple.
        - start_idx: 0-based line index where section starts
        - end_idx: 0-based line index where section ends (inclusive)
        - lines: list of lines in this section (including header)
        
        Special keys:
        - "preamble": lines before first data section (BIOSYM, #define blocks, etc.)
        - Section keys are normalized: "#section_name\\tlabel" → "section_name label"
    """
    all_lines = content.splitlines(keepends=False)
    sections: dict[str, tuple[int, int, list[str]]] = {}
    
    # Find preamble end (first # that is not #version, #define, ##)
    preamble_end = 0
    for i, line in enumerate(all_lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            if stripped.startswith("#version") or stripped.startswith("#define") or stripped.startswith("##"):
                continue
            # This is a data section header
            preamble_end = i
            break
    else:
        # No data sections found - entire content is preamble
        preamble_end = len(all_lines)
    
    # Store preamble
    if preamble_end > 0:
        sections["preamble"] = (0, preamble_end - 1, all_lines[:preamble_end])
    
    # Parse data sections
    current_section: str | None = None
    current_start: int = 0
    current_lines: list[str] = []
    
    for i in range(preamble_end, len(all_lines)):
        line = all_lines[i]
        stripped = line.strip()
        
        # Check if this is a new section header
        if stripped.startswith("#") and not stripped.startswith("##"):
            # Normalize header: "#section_name\tlabel" → "section_name label"
            header_content = stripped[1:]  # Remove leading #
            # Replace tabs with spaces and collapse multiple spaces for consistent matching
            normalized = re.sub(r'\s+', ' ', header_content).strip()
            
            # Save previous section if any
            if current_section is not None and current_lines:
                sections[current_section] = (current_start, i - 1, current_lines)
            
            # Start new section
            current_section = normalized
            current_start = i
            current_lines = [line]
        else:
            # Continue current section
            if current_section is not None:
                current_lines.append(line)
    
    # Save final section
    if current_section is not None and current_lines:
        sections[current_section] = (current_start, len(all_lines) - 1, current_lines)
    
    return sections


# =============================================================================
# Skeleton Template Formatting (re-exports from formatters.py for compat)
# =============================================================================

from upm.build.formatters import (  # noqa: E402
    format_atom_type_entry as format_skeleton_atom_type_entry,
    format_equivalence_entry as format_skeleton_equivalence_entry,
    format_auto_equivalence_entry as format_skeleton_auto_equivalence_entry,
    format_nonbond_entry as format_skeleton_nonbond_entry,
    format_bond_entry as format_skeleton_bond_entry,
    format_angle_entry as format_skeleton_angle_entry,
    format_torsion_entry as format_skeleton_torsion_entry,
    format_oop_entry as format_skeleton_oop_entry,
    format_bond_increment_entry as format_skeleton_bond_increment_entry,
)


# =============================================================================
# Utility Functions
# =============================================================================


def skeleton_element_to_connects(element: str) -> int:
    """Map element symbol to typical connectivity count."""
    connects_map = {
        "H": 1, "C": 4, "N": 3, "O": 2, "S": 2,
        "P": 3, "F": 1, "Cl": 1, "Br": 1, "I": 1, "Zn": 6,
    }
    return connects_map.get(element, 0)


def build_skeleton_alias_map(
    atom_types: list[str],
    max_len: int,
) -> tuple[dict[str, str], list[str]]:
    """Build alias mapping and expanded type list for msi2lmp compatibility.
    
    msi2lmp.exe v3.9.6 truncates atom type names to 5 characters during
    parameter lookup.
    
    Args:
        atom_types: List of atom type names.
        max_len: Maximum allowed length for type names.
    
    Returns:
        Tuple of (alias_to_source_map, expanded_types_sorted)
    
    Raises:
        ValueError: If two different types would have the same alias.
    """
    alias_to_source: dict[str, str] = {}
    inv_alias: dict[str, str] = {}
    
    for at in atom_types:
        at_s = str(at)
        if len(at_s) > max_len:
            alias = at_s[:max_len]
            if alias in inv_alias and inv_alias[alias] != at_s:
                raise ValueError(
                    f"Atom type alias collision: {at_s!r} and {inv_alias[alias]!r} "
                    f"both map to {alias!r} (max_len={max_len})"
                )
            alias_to_source[alias] = at_s
            inv_alias[alias] = at_s
    
    expanded = set(atom_types)
    expanded.update(alias_to_source.keys())
    return alias_to_source, sorted(expanded)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exception
    "MissingTypesError",
    # Parameter conversion
    "lj_sigma_eps_to_ab",
    "placeholder_bond_params",
    "placeholder_angle_params",
    # Section parsing
    "parse_embedded_base_sections",
    # Skeleton formatting
    "format_skeleton_atom_type_entry",
    "format_skeleton_equivalence_entry",
    "format_skeleton_auto_equivalence_entry",
    "format_skeleton_nonbond_entry",
    "format_skeleton_bond_entry",
    "format_skeleton_angle_entry",
    "format_skeleton_torsion_entry",
    "format_skeleton_oop_entry",
    "format_skeleton_bond_increment_entry",
    # Utilities
    "skeleton_element_to_connects",
    "build_skeleton_alias_map",
]
