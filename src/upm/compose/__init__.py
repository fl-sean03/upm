"""UPM Compose — layered force field composition.

Stack a base force field with extension layers and parameter patches,
then export as a monolithic .frc or .prm file.

Usage:
    from upm.compose import ParameterLayer, stack_layers, export_frc

    base = ParameterLayer.from_bundle("cvff-interface-v1-5", "v1.0")
    extension = ParameterLayer.from_bundle("cvff-metal-oxides-v2", "v1.0")
    patch = ParameterLayer.from_dict({"atom_types": {"Au": {"lj_b": 6085.0}}})

    stacked = stack_layers([base, extension, patch])
    export_frc(stacked, "output.frc")
"""

from upm.compose.layers import ParameterLayer, stack_layers
from upm.compose.export import export_frc

__all__ = [
    "ParameterLayer",
    "stack_layers",
    "export_frc",
]
