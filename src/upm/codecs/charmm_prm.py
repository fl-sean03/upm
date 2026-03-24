"""CHARMM `.prm` codec.

Read/write CHARMM/NAMD parameter files. Supports BONDS, ANGLES,
DIHEDRALS, IMPROPER, NONBONDED, NBFIX sections. CMAP is preserved
as raw data (not parsed into tables).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from upm.codecs._charmm_parser import parse_prm_text
from upm.codecs._charmm_writer import write_prm_text
from upm.core.tables import normalize_tables


def read_prm(
    path: str | Path,
    *,
    validate: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read a CHARMM .prm file into UPM tables.

    Args:
        path: Path to .prm file.
        validate: If True, validate tables after normalization.

    Returns:
        (tables, raw_sections) where tables is a dict of DataFrames
        and raw_sections preserves TITLE, CMAP, HBOND data.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    tables, raw_sections = parse_prm_text(text)
    tables = normalize_tables(tables)

    if validate:
        from upm.core.validate import validate_tables
        validate_tables(tables)

    return tables, raw_sections


def write_prm(
    path: str | Path,
    *,
    tables: dict[str, Any],
    raw_sections: list[dict[str, Any]] | None = None,
) -> str:
    """Write UPM tables to a CHARMM .prm file.

    Args:
        path: Output file path.
        tables: Dict of DataFrames (atom_types, bonds, angles, etc.)
        raw_sections: Optional preserved raw sections (TITLE, CMAP, HBOND).

    Returns:
        Output path as string.
    """
    p = Path(path)
    text = write_prm_text(tables, raw_sections=raw_sections)
    p.write_text(text, encoding="utf-8")
    return str(p)


__all__ = [
    "read_prm",
    "write_prm",
]
