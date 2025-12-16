"""Schema + semantic validators for canonical tables (v0.1).

This module validates canonical pandas DataFrames for UPM v0.1. Validation is
split from normalization:

- `upm.core.tables` handles deterministic canonicalization (dtypes, key ordering,
  sorting).
- This module enforces schema presence and semantic invariants.

Validation should be explicit and deterministic so that failures are easy to
debug and tests can assert error messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from upm.core.tables import TABLE_COLUMN_ORDER

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd


@dataclass(frozen=True)
class Violation:
    table: str
    message: str

    def __str__(self) -> str:  # pragma: no cover (covered indirectly by exception message)
        return f"{self.table}: {self.message}"


class TableValidationError(ValueError):
    """Aggregates multiple table validation failures.

    The message is stable and suitable for test assertions.
    """

    def __init__(self, violations: Iterable[Violation]):
        v = list(violations)
        if not v:
            super().__init__("table validation failed (no details)")
            self.violations = []
            return
        # Deterministic ordering for stable exception messages.
        v_sorted = sorted(v, key=lambda x: (x.table, x.message))
        msg = "table validation failed:\n" + "\n".join(f"  - {item}" for item in v_sorted)
        super().__init__(msg)
        self.violations = v_sorted




def _require_dataframe(df: object, *, table: str) -> "pd.DataFrame":
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{table}: expected pandas.DataFrame, got {type(df).__name__}")
    return df


def _required_columns(table: str) -> list[str]:
    return list(TABLE_COLUMN_ORDER[table])


def _check_required_columns(df: "pd.DataFrame", *, table: str, violations: list[Violation]) -> None:
    required = _required_columns(table)
    missing = [c for c in required if c not in df.columns]
    if missing:
        violations.append(Violation(table, f"missing required columns: {missing}"))


def _check_no_extra_columns(df: "pd.DataFrame", *, table: str, violations: list[Violation]) -> None:
    allowed = set(_required_columns(table))
    extras = [c for c in df.columns if c not in allowed]
    if extras:
        violations.append(Violation(table, f"unexpected extra columns: {extras}"))


def _check_non_empty_strings(
    df: "pd.DataFrame",
    *,
    table: str,
    col: str,
    violations: list[Violation],
) -> None:
    if col not in df.columns:
        return
    s = df[col]
    # nulls
    null_mask = s.isna()
    if null_mask.any():
        violations.append(Violation(table, f"{col}: contains nulls"))
    # empty/whitespace
    # Use astype(str) carefully; nulls already handled above.
    stripped = s.astype("string").str.strip()
    empty_mask = stripped == ""
    if empty_mask.any():
        violations.append(Violation(table, f"{col}: contains empty/whitespace-only strings"))


def _check_unique_key(
    df: "pd.DataFrame",
    *,
    table: str,
    cols: list[str],
    violations: list[Violation],
) -> None:
    if any(c not in df.columns for c in cols):
        return
    dup_mask = df.duplicated(subset=cols, keep=False)
    if dup_mask.any():
        violations.append(Violation(table, f"duplicate key rows for {cols}"))


def _check_numeric_non_null_finite(
    df: "pd.DataFrame",
    *,
    table: str,
    col: str,
    violations: list[Violation],
) -> None:
    import numpy as np
    import pandas as pd

    if col not in df.columns:
        return

    s = df[col]

    if s.isna().any():
        violations.append(Violation(table, f"{col}: contains nulls"))
        return

    # Convert to numeric to catch non-numeric types; coerce errors to NaN then detect.
    numeric = pd.to_numeric(s, errors="coerce")
    if numeric.isna().any():
        violations.append(Violation(table, f"{col}: contains non-numeric values"))
        return

    # Finite check: reject +/-inf and NaN (NaN would already be caught above, but keep explicit).
    arr = numeric.to_numpy(dtype="float64", copy=False)
    if not np.isfinite(arr).all():
        violations.append(Violation(table, f"{col}: contains non-finite values"))


def validate_atom_types(df: "pd.DataFrame") -> None:
    """Validate `atom_types` schema + v0.1 invariants.

    Raises:
        TableValidationError: when any violation is found.
    """
    df = _require_dataframe(df, table="atom_types")

    violations: list[Violation] = []
    _check_required_columns(df, table="atom_types", violations=violations)
    _check_no_extra_columns(df, table="atom_types", violations=violations)

    # Stop early if schema is broken to avoid noisy follow-on errors.
    if violations:
        raise TableValidationError(violations)

    # invariants
    _check_non_empty_strings(df, table="atom_types", col="atom_type", violations=violations)
    _check_unique_key(df, table="atom_types", cols=["atom_type"], violations=violations)
    _check_non_empty_strings(df, table="atom_types", col="vdw_style", violations=violations)

    # v0.1 `.frc` style must be lj_ab_12_6 (per dev guide).
    bad_style_mask = df["vdw_style"].astype("string").str.strip() != "lj_ab_12_6"
    if bad_style_mask.any():
        violations.append(Violation("atom_types", "vdw_style: only 'lj_ab_12_6' supported in v0.1"))

    # When lj_ab_12_6, LJ parameters must be present and finite.
    # (We check globally because v0.1 enforces this style for all rows.)
    _check_numeric_non_null_finite(df, table="atom_types", col="lj_a", violations=violations)
    _check_numeric_non_null_finite(df, table="atom_types", col="lj_b", violations=violations)

    if violations:
        raise TableValidationError(violations)


def validate_bonds(df: "pd.DataFrame") -> None:
    """Validate `bonds` schema + v0.1 invariants.

    Raises:
        TableValidationError: when any violation is found.
    """
    df = _require_dataframe(df, table="bonds")

    violations: list[Violation] = []
    _check_required_columns(df, table="bonds", violations=violations)
    _check_no_extra_columns(df, table="bonds", violations=violations)

    if violations:
        raise TableValidationError(violations)

    _check_non_empty_strings(df, table="bonds", col="t1", violations=violations)
    _check_non_empty_strings(df, table="bonds", col="t2", violations=violations)
    _check_non_empty_strings(df, table="bonds", col="style", violations=violations)

    # invariant: t1 <= t2
    t1 = df["t1"].astype("string").str.strip()
    t2 = df["t2"].astype("string").str.strip()
    bad_order = t1 > t2
    if bad_order.any():
        violations.append(Violation("bonds", "bond keys must satisfy t1 <= t2 (canonicalize before validate)"))

    # v0.1 supports quadratic only
    bad_style = df["style"].astype("string").str.strip() != "quadratic"
    if bad_style.any():
        violations.append(Violation("bonds", "style: only 'quadratic' supported in v0.1"))

    _check_numeric_non_null_finite(df, table="bonds", col="k", violations=violations)
    _check_numeric_non_null_finite(df, table="bonds", col="r0", violations=violations)
    _check_unique_key(df, table="bonds", cols=["t1", "t2", "style"], violations=violations)

    if violations:
        raise TableValidationError(violations)


def validate_angles(df: "pd.DataFrame") -> None:
    """Validate `angles` schema + v0.1.1 invariants.

    Canonical invariants:
    - endpoints must satisfy t1 <= t3 (canonicalize before validate)

    Style support (v0.1.1):
    - only quadratic angles are supported (from `#quadratic_angle`)
    """
    df = _require_dataframe(df, table="angles")

    violations: list[Violation] = []
    _check_required_columns(df, table="angles", violations=violations)
    _check_no_extra_columns(df, table="angles", violations=violations)

    if violations:
        raise TableValidationError(violations)

    _check_non_empty_strings(df, table="angles", col="t1", violations=violations)
    _check_non_empty_strings(df, table="angles", col="t2", violations=violations)
    _check_non_empty_strings(df, table="angles", col="t3", violations=violations)
    _check_non_empty_strings(df, table="angles", col="style", violations=violations)

    # invariant: t1 <= t3
    t1 = df["t1"].astype("string").str.strip()
    t3 = df["t3"].astype("string").str.strip()
    bad_order = t1 > t3
    if bad_order.any():
        violations.append(Violation("angles", "angle keys must satisfy t1 <= t3 (canonicalize before validate)"))

    bad_style = df["style"].astype("string").str.strip() != "quadratic"
    if bad_style.any():
        violations.append(Violation("angles", "style: only 'quadratic' supported in v0.1.1"))

    _check_numeric_non_null_finite(df, table="angles", col="k", violations=violations)
    _check_numeric_non_null_finite(df, table="angles", col="theta0_deg", violations=violations)
    _check_unique_key(df, table="angles", cols=["t1", "t2", "t3", "style"], violations=violations)

    if violations:
        raise TableValidationError(violations)


def validate_tables(tables: dict[str, "pd.DataFrame"]) -> None:
    """Validate a tables dict for v0.1.

    Required:
    - `atom_types`

    Optional (validated if present):
    - `bonds`
    - `angles`
    - `pair_overrides` (schema defined, but semantic validation not yet enforced in v0.1 minimal)
    """
    if not isinstance(tables, dict):
        raise TypeError(f"tables: expected dict[str, DataFrame], got {type(tables).__name__}")

    violations: list[Violation] = []

    # Required table
    if "atom_types" not in tables or tables["atom_types"] is None:
        violations.append(Violation("tables", "missing required table 'atom_types'"))
    else:
        try:
            validate_atom_types(tables["atom_types"])
        except TableValidationError as e:
            violations.extend(e.violations)

    # Optional tables
    if "bonds" in tables and tables["bonds"] is not None:
        try:
            validate_bonds(tables["bonds"])
        except TableValidationError as e:
            violations.extend(e.violations)

    if "angles" in tables and tables["angles"] is not None:
        try:
            validate_angles(tables["angles"])
        except TableValidationError as e:
            violations.extend(e.violations)

    # `pair_overrides` intentionally not validated semantically in v0.1 minimal,
    # but if present we still enforce schema strictness to preserve determinism.
    if "pair_overrides" in tables and tables["pair_overrides"] is not None:
        df = _require_dataframe(tables["pair_overrides"], table="pair_overrides")
        local: list[Violation] = []
        _check_required_columns(df, table="pair_overrides", violations=local)
        _check_no_extra_columns(df, table="pair_overrides", violations=local)
        violations.extend(local)

    if violations:
        raise TableValidationError(violations)