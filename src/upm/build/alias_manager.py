"""Alias management for msi2lmp compatibility.

This module handles atom type aliasing required for msi2lmp.exe
compatibility. The msi2lmp tool truncates atom type names to a
maximum length (typically 5 characters) during parameter lookup,
so we need to generate short aliases for long type names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AliasConfig:
    """Configuration for msi2lmp alias expansion.

    Attributes:
        max_type_len: Maximum allowed length for atom type names.
                      Types longer than this will have aliases generated.
        expand_aliases: Whether to include aliases in FRC output.
                        When True, aliases are added as separate entries.
    """

    max_type_len: int = 5
    expand_aliases: bool = False


def build_alias_map(
    atom_types: list[str],
    max_len: int,
) -> tuple[dict[str, str], list[str]]:
    """Build alias mapping for msi2lmp compatibility.

    msi2lmp.exe v3.9.6 truncates atom type names to max_len characters
    during parameter lookup. This function creates a mapping from
    truncated aliases to their full source names.

    Args:
        atom_types: List of atom type names.
        max_len: Maximum allowed length for type names.

    Returns:
        Tuple of:
        - alias_to_source: Dict mapping truncated alias → full type name.
          Only includes types that exceed max_len.
        - expanded_types: Sorted list of all types including aliases.

    Raises:
        ValueError: If two different types would have the same alias
                    (collision detection).

    Example:
        >>> types = ["carbon_sp3", "c", "hydrogen"]
        >>> alias_map, expanded = build_alias_map(types, max_len=5)
        >>> alias_map
        {'carbo': 'carbon_sp3', 'hydro': 'hydrogen'}
        >>> sorted(expanded)
        ['c', 'carbo', 'carbon_sp3', 'hydro', 'hydrogen']
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


def element_to_connects(element: str) -> int:
    """Map element symbol to typical connectivity count.

    Returns the typical valence/connectivity for common elements.
    Used when generating skeleton FRC entries where connectivity
    is not explicitly provided.

    Args:
        element: Element symbol (e.g., 'C', 'N', 'O', 'Zn').

    Returns:
        Typical connectivity count for the element.
        Returns 0 for unknown elements.

    Example:
        >>> element_to_connects("C")
        4
        >>> element_to_connects("O")
        2
        >>> element_to_connects("Zn")
        6
    """
    connects_map = {
        "H": 1,
        "C": 4,
        "N": 3,
        "O": 2,
        "S": 2,
        "P": 3,
        "F": 1,
        "Cl": 1,
        "Br": 1,
        "I": 1,
        "Zn": 6,
    }
    return connects_map.get(element, 0)


def truncate_type(atom_type: str, max_len: int) -> str:
    """Truncate atom type name to maximum length.

    Args:
        atom_type: The full atom type name.
        max_len: Maximum allowed length.

    Returns:
        Truncated type name (or original if already short enough).

    Example:
        >>> truncate_type("carbon_sp3", 5)
        'carbo'
        >>> truncate_type("c3", 5)
        'c3'
    """
    return atom_type[:max_len] if len(atom_type) > max_len else atom_type


def needs_alias(atom_type: str, max_len: int) -> bool:
    """Check if an atom type needs an alias.

    Args:
        atom_type: The atom type name.
        max_len: Maximum allowed length.

    Returns:
        True if the type name exceeds max_len and needs aliasing.

    Example:
        >>> needs_alias("carbon_sp3", 5)
        True
        >>> needs_alias("c3", 5)
        False
    """
    return len(atom_type) > max_len


__all__ = [
    "AliasConfig",
    "build_alias_map",
    "element_to_connects",
    "truncate_type",
    "needs_alias",
]
