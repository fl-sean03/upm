"""Canonical table schemas + normalization utilities (v0.1).

UPM represents forcefield parameters as canonical pandas DataFrames. The goal of
this module is to provide a single source of truth for:

- required columns / canonical column order
- pragmatic dtype normalization (string/float extension dtypes)
- deterministic canonicalization rules (key ordering) and stable sorting

This enables:
1) safe construction from imported sources (eg `.frc` parsing later),
2) schema + semantic validation (see `upm.core.validate`),
3) deterministic equality in tests (roundtrip comparisons).

v0.1 minimal scope:
- `atom_types` and `bonds` are supported.
- `pair_overrides` schema is defined as a skeleton for later nonbonded support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from upm.core.model import canonicalize_angle_key, canonicalize_bond_key

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd


# ----------------------------
# Canonical schema descriptors
# ----------------------------

# Schema values are *logical dtypes*; normalization casts to these pragmatically.
# We use pandas extension dtypes where appropriate to preserve missing values.
TABLE_SCHEMAS: dict[str, dict[str, str]] = {
    "atom_types": {
        "atom_type": "string",
        "element": "string",
        "mass_amu": "Float32",
        "vdw_style": "string",
        "lj_a": "Float64",
        "lj_b": "Float64",
        "notes": "string",
    },
    "bonds": {
        "t1": "string",
        "t2": "string",
        "style": "string",
        "k": "Float64",
        "r0": "Float64",
        "source": "string",
    },
    "angles": {
        "t1": "string",
        "t2": "string",
        "t3": "string",
        "style": "string",
        "k": "Float64",
        "theta0_deg": "Float64",
        "source": "string",
    },
    "pair_overrides": {
        "t1": "string",
        "t2": "string",
        "lj_a": "Float64",
        "lj_b": "Float64",
    },
}

# Deterministic key columns used for sorting.
TABLE_KEYS: dict[str, list[str]] = {
    "atom_types": ["atom_type"],
    "bonds": ["t1", "t2", "style"],
    "angles": ["t1", "t2", "t3", "style"],
    "pair_overrides": ["t1", "t2"],
}

# Canonical column order for stable CSV export and equality tests.
TABLE_COLUMN_ORDER: dict[str, list[str]] = {
    name: list(schema.keys()) for name, schema in TABLE_SCHEMAS.items()
}


# ----------------------------
# Internal helpers
# ----------------------------


def _require_columns(df: "pd.DataFrame", *, required: list[str], table: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{table}: missing required columns: {missing}")


def _reject_extra_columns(df: "pd.DataFrame", *, allowed: list[str], table: str) -> None:
    extras = [c for c in df.columns if c not in allowed]
    if extras:
        raise ValueError(f"{table}: unexpected extra columns: {extras}")


def _astype_safe(series: "pd.Series", dtype: str) -> "pd.Series":
    # Use pandas' nullable extension dtypes where specified.
    # This keeps missing values as <NA> instead of converting to numpy nan in some cases.
    return series.astype(dtype)


def _normalize_string_col(series: "pd.Series") -> "pd.Series":
    # Ensure string dtype, then strip whitespace on non-null values.
    s = _astype_safe(series, "string")
    # Pandas string dtype supports .str methods; it leaves <NA> untouched.
    return s.str.strip()


def _normalize_df_strings(df: "pd.DataFrame", *, string_cols: list[str]) -> "pd.DataFrame":
    for c in string_cols:
        if c in df.columns:
            df[c] = _normalize_string_col(df[c])
    return df


def _cast_to_schema(df: "pd.DataFrame", *, schema: dict[str, str]) -> "pd.DataFrame":
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        if dtype == "string":
            df[col] = _normalize_string_col(df[col])
        else:
            df[col] = _astype_safe(df[col], dtype)
    return df


def _sort_canonical(df: "pd.DataFrame", *, keys: list[str]) -> "pd.DataFrame":
    # stable sort ensures deterministic ordering if keys tie
    return df.sort_values(keys, kind="mergesort", na_position="last").reset_index(drop=True)


def _reorder_columns(df: "pd.DataFrame", *, column_order: list[str]) -> "pd.DataFrame":
    return df.loc[:, column_order]


# ----------------------------
# Public normalizers
# ----------------------------


def normalize_atom_types(df: "pd.DataFrame") -> "pd.DataFrame":
    """Return a canonicalized `atom_types` table.

    Post-conditions (guarantees of this function):
    - required columns are present and no extra columns exist (strict v0.1)
    - string columns are pandas string dtype and stripped
    - float columns are cast to Float32/Float64 extension dtypes
    - rows are sorted deterministically by (`atom_type`)
    - index is reset to RangeIndex

    Note: semantic validation (eg uniqueness, allowed `vdw_style`) is handled by
    `upm.core.validate.validate_atom_types`.
    """
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"atom_types: expected pandas.DataFrame, got {type(df).__name__}")

    table = "atom_types"
    schema = TABLE_SCHEMAS[table]
    required_cols = list(schema.keys())

    _require_columns(df, required=required_cols, table=table)
    _reject_extra_columns(df, allowed=required_cols, table=table)

    out = df.copy(deep=True)
    out = _cast_to_schema(out, schema=schema)
    out = _reorder_columns(out, column_order=TABLE_COLUMN_ORDER[table])
    out = _sort_canonical(out, keys=TABLE_KEYS[table])
    return out


def normalize_bonds(df: "pd.DataFrame") -> "pd.DataFrame":
    """Return a canonicalized `bonds` table.

    Canonicalization rules (v0.1):
    - bond endpoint types are sorted so that `t1 <= t2` lexicographically
      (using `upm.core.model.canonicalize_bond_key`)

    Post-conditions (guarantees of this function):
    - required columns are present and no extra columns exist (strict v0.1)
    - string columns are pandas string dtype and stripped
    - `(t1,t2)` is canonicalized for every row
    - numeric columns are cast to Float64 extension dtype
    - rows are sorted deterministically by (`t1`,`t2`,`style`)
    - index is reset to RangeIndex

    Note: semantic validation (eg style allowed, non-null numeric values, uniqueness)
    is handled by `upm.core.validate.validate_bonds`.
    """
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"bonds: expected pandas.DataFrame, got {type(df).__name__}")

    table = "bonds"
    schema = TABLE_SCHEMAS[table]
    required_cols = list(schema.keys())

    _require_columns(df, required=required_cols, table=table)
    _reject_extra_columns(df, allowed=required_cols, table=table)

    out = df.copy(deep=True)

    # Normalize dtypes/strings first so canonicalization sees stripped strings.
    out = _cast_to_schema(out, schema=schema)

    # Canonicalize endpoints per-row.
    # Use tolist iteration to avoid per-row pandas apply overhead while staying simple.
    t1_vals = out["t1"].tolist()
    t2_vals = out["t2"].tolist()
    new_t1: list[str | Any] = []
    new_t2: list[str | Any] = []
    for a, b in zip(t1_vals, t2_vals):
        # Preserve <NA> as-is; validation will reject nulls.
        if a is pd.NA or b is pd.NA:
            new_t1.append(a)
            new_t2.append(b)
            continue
        k1, k2 = canonicalize_bond_key(str(a), str(b))
        new_t1.append(k1)
        new_t2.append(k2)

    out["t1"] = pd.Series(new_t1, dtype="string")
    out["t2"] = pd.Series(new_t2, dtype="string")

    out = _reorder_columns(out, column_order=TABLE_COLUMN_ORDER[table])
    out = _sort_canonical(out, keys=TABLE_KEYS[table])
    return out


def normalize_angles(df: "pd.DataFrame") -> "pd.DataFrame":
    """Return a canonicalized `angles` table.

    Canonicalization rules (v0.1.1):
    - angle endpoints are canonicalized so that `t1 <= t3` lexicographically
      (using `upm.core.model.canonicalize_angle_key`)

    Post-conditions:
    - required columns are present and no extra columns exist (strict)
    - string columns are pandas string dtype and stripped
    - `(t1,t2,t3)` is canonicalized for every row
    - numeric columns are cast to Float64 extension dtype
    - rows are sorted deterministically by (`t1`,`t2`,`t3`,`style`)
    - index is reset to RangeIndex

    Note: semantic validation (eg style allowed, non-null numeric values, uniqueness)
    is handled by `upm.core.validate.validate_angles`.
    """
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"angles: expected pandas.DataFrame, got {type(df).__name__}")

    table = "angles"
    schema = TABLE_SCHEMAS[table]
    required_cols = list(schema.keys())

    _require_columns(df, required=required_cols, table=table)
    _reject_extra_columns(df, allowed=required_cols, table=table)

    out = df.copy(deep=True)

    # Normalize dtypes/strings first so canonicalization sees stripped strings.
    out = _cast_to_schema(out, schema=schema)

    t1_vals = out["t1"].tolist()
    t2_vals = out["t2"].tolist()
    t3_vals = out["t3"].tolist()

    new_t1: list[str | Any] = []
    new_t2: list[str | Any] = []
    new_t3: list[str | Any] = []

    for a, b, c in zip(t1_vals, t2_vals, t3_vals):
        if a is pd.NA or b is pd.NA or c is pd.NA:
            new_t1.append(a)
            new_t2.append(b)
            new_t3.append(c)
            continue
        k1, k2, k3 = canonicalize_angle_key(str(a), str(b), str(c))
        new_t1.append(k1)
        new_t2.append(k2)
        new_t3.append(k3)

    out["t1"] = pd.Series(new_t1, dtype="string")
    out["t2"] = pd.Series(new_t2, dtype="string")
    out["t3"] = pd.Series(new_t3, dtype="string")

    out = _reorder_columns(out, column_order=TABLE_COLUMN_ORDER[table])
    out = _sort_canonical(out, keys=TABLE_KEYS[table])
    return out


def normalize_tables(tables: dict[str, "pd.DataFrame"]) -> dict[str, "pd.DataFrame"]:
    """Normalize any recognized tables in `tables` and return a new dict.

    Unknown table names are passed through unchanged.
    """
    import pandas as pd

    if not isinstance(tables, dict):
        raise TypeError(f"tables: expected dict[str, DataFrame], got {type(tables).__name__}")

    out: dict[str, pd.DataFrame] = {}
    for name, df in tables.items():
        if name == "atom_types":
            out[name] = normalize_atom_types(df)
        elif name == "bonds":
            out[name] = normalize_bonds(df)
        elif name == "angles":
            out[name] = normalize_angles(df)
        else:
            out[name] = df
    return out