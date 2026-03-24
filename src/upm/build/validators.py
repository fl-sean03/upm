"""Validation utilities for FRC builder.

This module provides error types and validation functions used
throughout the FRC build pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissingTypesError(ValueError):
    """Raised when builder cannot proceed due to missing required types.

    This error indicates that one or more atom types required for
    FRC generation are not available in the parameter source(s).

    The missing_types tuple is automatically sorted for deterministic
    error messages regardless of iteration order.

    Attributes:
        missing_types: Tuple of atom type names that are missing.

    Example:
        >>> raise MissingTypesError(missing_types=("c3", "o2"))
        MissingTypesError: Missing types: ['c3', 'o2']
    """

    missing_types: tuple[str, ...]

    def __post_init__(self) -> None:
        """Ensure deterministic ordering of missing types."""
        object.__setattr__(self, "missing_types", tuple(sorted(self.missing_types)))

    def __str__(self) -> str:
        """Return human-readable error message."""
        return f"Missing types: {list(self.missing_types)}"


def validate_required_types(
    required: set[str],
    available: set[str],
) -> None:
    """Validate that all required types are available.

    Args:
        required: Set of atom type names that are required.
        available: Set of atom type names that are available.

    Raises:
        MissingTypesError: If any required types are not available.
    """
    missing = required - available
    if missing:
        raise MissingTypesError(missing_types=tuple(missing))


__all__ = [
    "MissingTypesError",
    "validate_required_types",
]
