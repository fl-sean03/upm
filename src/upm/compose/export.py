"""Export stacked parameter layers as monolithic force field files.

Generates complete .frc or .prm files from a stacked ParameterLayer,
suitable for direct use with msi2lmp or NAMD.
"""
from __future__ import annotations

from pathlib import Path

from upm.compose.layers import ParameterLayer


def export_frc(
    layer: ParameterLayer,
    path: str | Path,
    *,
    label: str = "cvff",
) -> str:
    """Export a ParameterLayer as a monolithic CVFF .frc file.

    The output file is directly usable with msi2lmp.exe.

    Args:
        layer: The (stacked) parameter layer to export.
        path: Output file path.
        label: Force field label (default "cvff").

    Returns:
        Output path as string.
    """
    from upm.codecs.msi_frc import write_frc

    p = Path(path)
    write_frc(p, tables=layer.tables, mode="full")
    return str(p)


def export_prm(
    layer: ParameterLayer,
    path: str | Path,
) -> str:
    """Export a ParameterLayer as a monolithic CHARMM .prm file.

    The output file is directly usable with NAMD/CHARMM.

    Args:
        layer: The (stacked) parameter layer to export.
        path: Output file path.

    Returns:
        Output path as string.
    """
    from upm.codecs.charmm_prm import write_prm

    p = Path(path)
    write_prm(p, tables=layer.tables)
    return str(p)


__all__ = [
    "export_frc",
    "export_prm",
]
