"""Unified FRC file builder.

This module provides the FRCBuilder class, which is the recommended entry point
for all FRC generation. It orchestrates: validate → collect → format → write.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .frc_templates import CVFF_CANONICAL_TEMPLATE
from .parameter_sources import ParameterSource
from .formatters import (
    format_atom_type_entry,
    format_equivalence_entry,
    format_nonbond_entry,
    format_bond_entry,
    format_angle_entry,
    format_torsion_entry,
    format_oop_entry,
    format_bond_increment_entry,
    join_entries_with_trailing_newline,
)
from .validators import MissingTypesError
from .alias_manager import build_alias_map


@dataclass
class FRCBuilderConfig:
    """Configuration for FRCBuilder."""

    msi2lmp_max_type_len: int = 5
    expand_aliases: bool = False
    strict: bool = True
    forcefield_label: str = "cvff"


class FRCBuilder:
    """Unified FRC file builder.

    This is the recommended entry point for all FRC generation.

    Example:
        >>> from upm.build import FRCBuilder
        >>> from upm.build.parameter_sources import ChainedSource, ParameterSetSource, PlaceholderSource
        >>>
        >>> element_map = {at: ps["atom_types"][at].get("element", "X") for at in termset["atom_types"]}
        >>> source = ChainedSource([
        ...     ParameterSetSource(parameterset),
        ...     PlaceholderSource(element_map),
        ... ])
        >>> builder = FRCBuilder(termset, source)
        >>> builder.write("output.frc")
    """

    def __init__(
        self,
        termset: dict[str, Any],
        parameter_source: ParameterSource,
        config: Optional[FRCBuilderConfig] = None,
    ) -> None:
        self._termset = termset
        self._source = parameter_source
        self._config = config or FRCBuilderConfig()

    def validate(self) -> list[str]:
        """Validate parameter coverage.

        Returns:
            List of missing type descriptions (empty if all covered).
        """
        missing: list[str] = []

        # Check atom types
        for at in self._termset.get("atom_types", []):
            if self._source.get_atom_type_info(at) is None:
                missing.append(f"atom_type:{at}")
            if self._source.get_nonbond_params(at) is None:
                missing.append(f"nonbond:{at}")

        # Check bond types
        for bond in self._termset.get("bond_types", []):
            t1, t2 = bond[0], bond[1]
            if self._source.get_bond_params(t1, t2) is None:
                missing.append(f"bond:{t1}-{t2}")

        # Check angle types
        for angle in self._termset.get("angle_types", []):
            t1, t2, t3 = angle[0], angle[1], angle[2]
            if self._source.get_angle_params(t1, t2, t3) is None:
                missing.append(f"angle:{t1}-{t2}-{t3}")

        # Check dihedral types
        for dihedral in self._termset.get("dihedral_types", []):
            t1, t2, t3, t4 = dihedral[0], dihedral[1], dihedral[2], dihedral[3]
            if self._source.get_torsion_params(t1, t2, t3, t4) is None:
                missing.append(f"torsion:{t1}-{t2}-{t3}-{t4}")

        # Check improper types
        for improper in self._termset.get("improper_types", []):
            t1, t2, t3, t4 = improper[0], improper[1], improper[2], improper[3]
            if self._source.get_oop_params(t1, t2, t3, t4) is None:
                missing.append(f"oop:{t1}-{t2}-{t3}-{t4}")

        return missing

    def build(self) -> str:
        """Build FRC content string.

        Returns:
            Complete FRC file content as string.

        Raises:
            MissingTypesError: If strict=True and parameters are missing.
        """
        # 1. Validate (if strict)
        if self._config.strict:
            missing = self.validate()
            if missing:
                raise MissingTypesError(tuple(missing))

        # 2. Build alias map (if expanding)
        atom_types = list(self._termset.get("atom_types", []))
        alias_map: dict[str, str] = {}
        expanded_types = sorted(atom_types)

        if self._config.expand_aliases:
            alias_map, expanded_types = build_alias_map(
                atom_types, self._config.msi2lmp_max_type_len
            )

        # Build reverse map: emitted_type -> source_type
        emitted_to_source: dict[str, str] = {}
        for at in atom_types:
            emitted_to_source[at] = at
        for alias, source in alias_map.items():
            emitted_to_source[alias] = source

        # 3. Collect and format entries
        atom_types_entries = self._collect_atom_types(expanded_types, emitted_to_source)
        equivalence_entries = self._collect_equivalences(expanded_types, emitted_to_source)
        auto_equivalence_entries: list[str] = []  # Must be empty per FINDINGS.md
        bond_entries = self._collect_bonds()
        angle_entries = self._collect_angles()
        torsion_entries = self._collect_torsions()
        oop_entries = self._collect_oops()
        nonbond_entries = self._collect_nonbonds(expanded_types, emitted_to_source)
        bond_increment_entries = self._collect_bond_increments()

        # 4. Format and populate template
        return CVFF_CANONICAL_TEMPLATE.format(
            atom_types_entries="\n".join(atom_types_entries),
            equivalence_entries="\n".join(equivalence_entries),
            auto_equivalence_entries=join_entries_with_trailing_newline(auto_equivalence_entries),
            bond_entries="\n".join(bond_entries),
            angle_entries="\n".join(angle_entries),
            torsion_entries=join_entries_with_trailing_newline(torsion_entries),
            oop_entries=join_entries_with_trailing_newline(oop_entries),
            nonbond_entries="\n".join(nonbond_entries),
            bond_increments_entries="\n".join(bond_increment_entries),
        )

    def write(self, path: Path | str) -> str:
        """Build and write FRC to file.

        Args:
            path: Output file path.

        Returns:
            Output path as string.
        """
        content = self.build()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return str(out)

    # Collection methods (private)
    def _collect_atom_types(
        self, expanded_types: list[str], emitted_to_source: dict[str, str]
    ) -> list[str]:
        entries: list[str] = []
        for at in expanded_types:
            src = emitted_to_source[at]
            info = self._source.get_atom_type_info(src)
            if info is not None:
                entries.append(
                    format_atom_type_entry(
                        atom_type=at,
                        mass=info.mass_amu,
                        element=info.element,
                        connects=info.connects,
                    )
                )
        return entries

    def _collect_equivalences(
        self, expanded_types: list[str], emitted_to_source: dict[str, str]
    ) -> list[str]:
        entries: list[str] = []
        for at in expanded_types:
            src = emitted_to_source[at]
            entries.append(
                format_equivalence_entry(
                    atom_type=at,
                    nonb=src,
                    bond=src,
                    angle=src,
                    torsion=src,
                    oop=src,
                )
            )
        return entries

    def _collect_nonbonds(
        self, expanded_types: list[str], emitted_to_source: dict[str, str]
    ) -> list[str]:
        entries: list[str] = []
        for at in expanded_types:
            src = emitted_to_source[at]
            params = self._source.get_nonbond_params(src)
            if params is not None:
                entries.append(
                    format_nonbond_entry(
                        atom_type=at,
                        a_coeff=params.lj_a,
                        b_coeff=params.lj_b,
                    )
                )
        return entries

    def _collect_bonds(self) -> list[str]:
        entries: list[str] = []
        seen: set[tuple[str, str]] = set()
        for bond in self._termset.get("bond_types", []):
            t1, t2 = bond[0], bond[1]
            key = (t1, t2) if t1 <= t2 else (t2, t1)
            if key in seen:
                continue
            seen.add(key)
            params = self._source.get_bond_params(t1, t2)
            if params is not None:
                entries.append(format_bond_entry(t1, t2, params.r0, params.k))
        return sorted(entries)

    def _collect_angles(self) -> list[str]:
        entries: list[str] = []
        seen: set[tuple[str, str, str]] = set()
        for angle in self._termset.get("angle_types", []):
            t1, t2, t3 = angle[0], angle[1], angle[2]
            key = (t1, t2, t3) if t1 <= t3 else (t3, t2, t1)
            if key in seen:
                continue
            seen.add(key)
            params = self._source.get_angle_params(t1, t2, t3)
            if params is not None:
                entries.append(format_angle_entry(t1, t2, t3, params.theta0_deg, params.k))
        return sorted(entries)

    def _collect_torsions(self) -> list[str]:
        entries: list[str] = []
        for dihedral in self._termset.get("dihedral_types", []):
            t1, t2, t3, t4 = dihedral[0], dihedral[1], dihedral[2], dihedral[3]
            params = self._source.get_torsion_params(t1, t2, t3, t4)
            if params is not None:
                entries.append(
                    format_torsion_entry(t1, t2, t3, t4, params.kphi, params.n, params.phi0)
                )
        return sorted(entries)

    def _collect_oops(self) -> list[str]:
        entries: list[str] = []
        for improper in self._termset.get("improper_types", []):
            t1, t2, t3, t4 = improper[0], improper[1], improper[2], improper[3]
            params = self._source.get_oop_params(t1, t2, t3, t4)
            if params is not None:
                entries.append(
                    format_oop_entry(t1, t2, t3, t4, params.kchi, params.n, params.chi0)
                )
        return sorted(entries)

    def _collect_bond_increments(self) -> list[str]:
        entries: list[str] = []
        seen: set[tuple[str, str]] = set()
        for bond in self._termset.get("bond_types", []):
            t1, t2 = bond[0], bond[1]
            key = (t1, t2) if t1 <= t2 else (t2, t1)
            if key in seen:
                continue
            seen.add(key)
            # Try to get actual bond increment values from source
            delta_ij, delta_ji = 0.0, 0.0
            if hasattr(self._source, "get_bond_increment_params"):
                params = self._source.get_bond_increment_params(t1, t2)
                if params is not None:
                    delta_ij = params.delta_ij
                    delta_ji = params.delta_ji
            entries.append(format_bond_increment_entry(t1, t2, delta_ij, delta_ji))
        return sorted(entries)


__all__ = ["FRCBuilder", "FRCBuilderConfig"]
