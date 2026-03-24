"""Parameter diffing between two sets of tables.

Computes added, removed, and changed parameters between two
parameter table dicts (from different versions or packages).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParamChange:
    """A single parameter that changed between two versions.

    Attributes:
        table: Table name (e.g., 'atom_types').
        key: Identifying key (e.g., atom_type name or bond type tuple).
        field: Changed field name (e.g., 'lj_a').
        old_value: Value in the old/left table.
        new_value: Value in the new/right table.
    """
    table: str
    key: str
    field: str
    old_value: Any
    new_value: Any

    def __str__(self) -> str:
        return f"{self.table}[{self.key}].{self.field}: {self.old_value} → {self.new_value}"


@dataclass
class ParameterDiff:
    """Structured diff between two parameter table dicts.

    Attributes:
        added_types: Atom types present in right but not left.
        removed_types: Atom types present in left but not right.
        changed_params: List of individual parameter changes.
    """
    added_types: list[str] = field(default_factory=list)
    removed_types: list[str] = field(default_factory=list)
    changed_params: list[ParamChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added_types or self.removed_types or self.changed_params)

    def summary(self) -> str:
        """Human-readable diff summary."""
        lines = []
        if self.added_types:
            lines.append(f"Added types ({len(self.added_types)}): {', '.join(sorted(self.added_types))}")
        if self.removed_types:
            lines.append(f"Removed types ({len(self.removed_types)}): {', '.join(sorted(self.removed_types))}")
        if self.changed_params:
            lines.append(f"Changed parameters ({len(self.changed_params)}):")
            for change in self.changed_params[:20]:
                lines.append(f"  {change}")
            if len(self.changed_params) > 20:
                lines.append(f"  ... and {len(self.changed_params) - 20} more")
        if not lines:
            lines.append("No differences found.")
        return "\n".join(lines)


def diff_tables(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    numeric_rtol: float = 1e-6,
) -> ParameterDiff:
    """Compute the diff between two parameter table dicts.

    Args:
        left: First (old/baseline) tables dict.
        right: Second (new/updated) tables dict.
        numeric_rtol: Relative tolerance for numeric comparison.

    Returns:
        ParameterDiff with added, removed, and changed parameters.
    """
    diff = ParameterDiff()

    # Diff atom_types
    left_at = _get_atom_types_set(left)
    right_at = _get_atom_types_set(right)
    diff.added_types = sorted(right_at - left_at)
    diff.removed_types = sorted(left_at - right_at)

    # Diff parameter values for common atom types
    common = left_at & right_at
    if common and "atom_types" in left and "atom_types" in right:
        left_df = left["atom_types"]
        right_df = right["atom_types"]

        numeric_cols = ["lj_a", "lj_b", "mass_amu"]
        for at in sorted(common):
            left_row = left_df[left_df["atom_type"] == at].iloc[0]
            right_row = right_df[right_df["atom_type"] == at].iloc[0]

            for col in numeric_cols:
                if col not in left_df.columns or col not in right_df.columns:
                    continue
                lv = float(left_row[col]) if left_row[col] is not None else 0.0
                rv = float(right_row[col]) if right_row[col] is not None else 0.0
                if abs(lv) < 1e-15 and abs(rv) < 1e-15:
                    continue
                denom = max(abs(lv), abs(rv), 1e-15)
                if abs(lv - rv) / denom > numeric_rtol:
                    diff.changed_params.append(ParamChange(
                        table="atom_types", key=at, field=col,
                        old_value=lv, new_value=rv,
                    ))

    return diff


def _get_atom_types_set(tables: dict[str, Any]) -> set[str]:
    if "atom_types" not in tables:
        return set()
    df = tables["atom_types"]
    return set(df["atom_type"].tolist())


__all__ = [
    "ParamChange",
    "ParameterDiff",
    "diff_tables",
]
