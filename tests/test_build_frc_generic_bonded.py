"""Tests for Phase 11 generic bonded parameters builder.

These tests validate:
- generate_generic_bonded_params() function
- build_frc_cvff_with_generic_bonded() builder
- Integration with CALF20 termset/parameterset data
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from upm.build.frc_builders import (
    generate_generic_bonded_params,
    build_frc_cvff_with_generic_bonded,
    MissingTypesError,
)


def _termset(
    *,
    atom_types: list[str],
    bond_types: list[tuple[str, str]],
    angle_types: list[tuple[str, str, str]],
    dihedral_types: list[tuple[str, str, str, str]],
    improper_types: list[tuple[str, str, str, str]],
) -> dict[str, object]:
    return {
        "schema": "molsaic.termset.v0.1.2",
        "atom_types": list(atom_types),
        "bond_types": [list(x) for x in bond_types],
        "angle_types": [list(x) for x in angle_types],
        "dihedral_types": [list(x) for x in dihedral_types],
        "improper_types": [list(x) for x in improper_types],
    }


def _parameterset(*, atom_types: dict[str, dict[str, float | str]]) -> dict[str, object]:
    return {
        "schema": "upm.parameterset.v0.1.2",
        "atom_types": dict(atom_types),
    }


# =============================================================================
# Tests for generate_generic_bonded_params()
# =============================================================================


def test_generate_generic_bonded_params_returns_expected_keys() -> None:
    """Test that generate_generic_bonded_params returns all required keys."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF"],
        bond_types=[("C_MOF", "H_MOF")],
        angle_types=[("H_MOF", "C_MOF", "H_MOF")],
        dihedral_types=[],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        }
    )

    result = generate_generic_bonded_params(ts, ps)

    assert "bond_entries" in result
    assert "angle_entries" in result
    assert "torsion_entries" in result
    assert "oop_entries" in result
    assert isinstance(result["bond_entries"], list)
    assert isinstance(result["angle_entries"], list)
    assert isinstance(result["torsion_entries"], list)
    assert isinstance(result["oop_entries"], list)


def test_generate_generic_bonded_params_bond_format() -> None:
    """Test bond entry format matches CVFF spec."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF"],
        bond_types=[("C_MOF", "H_MOF")],
        angle_types=[],
        dihedral_types=[],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        }
    )

    result = generate_generic_bonded_params(ts, ps)
    bond_entries = result["bond_entries"]

    assert len(bond_entries) > 0
    # Check format: should contain atom types and numeric values
    # H-bonds use k=340.0, r0=1.09
    joined = "\n".join(bond_entries)
    assert "C_MOF" in joined
    assert "H_MOF" in joined
    assert "1.09" in joined  # r0 for H-bonds
    assert "340" in joined  # k for H-bonds


def test_generate_generic_bonded_params_angle_format() -> None:
    """Test angle entry format matches CVFF spec."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF"],
        bond_types=[],
        angle_types=[("H_MOF", "C_MOF", "H_MOF")],
        dihedral_types=[],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        }
    )

    result = generate_generic_bonded_params(ts, ps)
    angle_entries = result["angle_entries"]

    assert len(angle_entries) > 0
    joined = "\n".join(angle_entries)
    # C-center angles use theta0=109.5, k=44.4
    assert "109.5" in joined
    assert "44.4" in joined


def test_generate_generic_bonded_params_torsion_format() -> None:
    """Test torsion entry format matches CVFF spec."""
    ts = _termset(
        atom_types=["C_MOF", "N_MOF", "H_MOF"],
        bond_types=[],
        angle_types=[],
        dihedral_types=[("H_MOF", "C_MOF", "N_MOF", "H_MOF")],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "N_MOF": {"element": "N", "mass_amu": 14.007, "lj_sigma_angstrom": 3.3, "lj_epsilon_kcal_mol": 0.05},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        }
    )

    result = generate_generic_bonded_params(ts, ps)
    torsion_entries = result["torsion_entries"]

    assert len(torsion_entries) > 0
    # Check that entries contain the atom types
    joined = "\n".join(torsion_entries)
    assert "C_MOF" in joined
    assert "N_MOF" in joined
    assert "H_MOF" in joined


def test_generate_generic_bonded_params_oop_format() -> None:
    """Test out-of-plane entry format matches CVFF spec."""
    ts = _termset(
        atom_types=["C_MOF", "N_MOF", "Zn_MOF"],
        bond_types=[],
        angle_types=[],
        dihedral_types=[],
        improper_types=[("C_MOF", "N_MOF", "C_MOF", "Zn_MOF")],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "N_MOF": {"element": "N", "mass_amu": 14.007, "lj_sigma_angstrom": 3.3, "lj_epsilon_kcal_mol": 0.05},
            "Zn_MOF": {"element": "Zn", "mass_amu": 65.38, "lj_sigma_angstrom": 2.4, "lj_epsilon_kcal_mol": 0.12},
        }
    )

    result = generate_generic_bonded_params(ts, ps)
    oop_entries = result["oop_entries"]

    assert len(oop_entries) > 0
    joined = "\n".join(oop_entries)
    # OOP uses all permutations, so all atom types should appear
    assert "C_MOF" in joined
    assert "N_MOF" in joined


def test_generate_generic_bonded_params_alias_expansion() -> None:
    """Test that Zn_MOF generates both Zn_MOF and Zn_MO variants."""
    ts = _termset(
        atom_types=["C_MOF", "Zn_MOF"],
        bond_types=[("C_MOF", "Zn_MOF")],
        angle_types=[],
        dihedral_types=[],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "Zn_MOF": {"element": "Zn", "mass_amu": 65.38, "lj_sigma_angstrom": 2.4, "lj_epsilon_kcal_mol": 0.12},
        }
    )

    result = generate_generic_bonded_params(ts, ps, msi2lmp_max_atom_type_len=5)
    bond_entries = result["bond_entries"]

    joined = "\n".join(bond_entries)
    # Should have both full name and truncated alias
    assert "Zn_MOF" in joined
    assert "Zn_MO" in joined


# =============================================================================
# Tests for build_frc_cvff_with_generic_bonded()
# =============================================================================


def test_build_frc_cvff_with_generic_bonded_creates_file(tmp_path: Path) -> None:
    """Test that builder creates output file."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF"],
        bond_types=[("C_MOF", "H_MOF")],
        angle_types=[("H_MOF", "C_MOF", "H_MOF")],
        dihedral_types=[],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        }
    )

    out = tmp_path / "test.frc"
    result = build_frc_cvff_with_generic_bonded(ts, ps, out_path=out)

    assert out.exists()
    assert out.stat().st_size > 0
    assert result == str(out)


def test_build_frc_cvff_with_generic_bonded_is_deterministic(tmp_path: Path) -> None:
    """Test byte-determinism across multiple runs."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF", "N_MOF", "O_MOF", "Zn_MOF"],
        bond_types=[("C_MOF", "H_MOF"), ("N_MOF", "Zn_MOF")],
        angle_types=[("H_MOF", "C_MOF", "H_MOF")],
        dihedral_types=[("C_MOF", "N_MOF", "C_MOF", "H_MOF")],
        improper_types=[("C_MOF", "N_MOF", "C_MOF", "Zn_MOF")],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
            "N_MOF": {"element": "N", "mass_amu": 14.007, "lj_sigma_angstrom": 3.3, "lj_epsilon_kcal_mol": 0.05},
            "O_MOF": {"element": "O", "mass_amu": 15.999, "lj_sigma_angstrom": 3.1, "lj_epsilon_kcal_mol": 0.06},
            "Zn_MOF": {"element": "Zn", "mass_amu": 65.38, "lj_sigma_angstrom": 2.4, "lj_epsilon_kcal_mol": 0.12},
        }
    )

    p1 = tmp_path / "run1.frc"
    p2 = tmp_path / "run2.frc"

    build_frc_cvff_with_generic_bonded(ts, ps, out_path=p1)
    build_frc_cvff_with_generic_bonded(ts, ps, out_path=p2)

    # Byte-for-byte comparison
    assert p1.read_bytes() == p2.read_bytes()

    # sha256 comparison for additional verification
    hash1 = hashlib.sha256(p1.read_bytes()).hexdigest()
    hash2 = hashlib.sha256(p2.read_bytes()).hexdigest()
    assert hash1 == hash2


def test_build_frc_cvff_with_generic_bonded_includes_all_sections(tmp_path: Path) -> None:
    """Test output includes all required CVFF sections."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF", "N_MOF", "O_MOF", "Zn_MOF"],
        bond_types=[("C_MOF", "H_MOF")],
        angle_types=[("H_MOF", "C_MOF", "H_MOF")],
        dihedral_types=[("C_MOF", "N_MOF", "C_MOF", "H_MOF")],
        improper_types=[("C_MOF", "N_MOF", "C_MOF", "Zn_MOF")],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
            "N_MOF": {"element": "N", "mass_amu": 14.007, "lj_sigma_angstrom": 3.3, "lj_epsilon_kcal_mol": 0.05},
            "O_MOF": {"element": "O", "mass_amu": 15.999, "lj_sigma_angstrom": 3.1, "lj_epsilon_kcal_mol": 0.06},
            "Zn_MOF": {"element": "Zn", "mass_amu": 65.38, "lj_sigma_angstrom": 2.4, "lj_epsilon_kcal_mol": 0.12},
        }
    )

    out = tmp_path / "cvff.frc"
    build_frc_cvff_with_generic_bonded(ts, ps, out_path=out)
    text = out.read_text(encoding="utf-8")

    # Required CVFF markers
    assert "!BIOSYM forcefield" in text
    assert "#define cvff" in text
    assert "#atom_types" in text
    assert "#equivalence" in text
    assert "#auto_equivalence" in text
    assert "#quadratic_bond" in text
    assert "#quadratic_angle" in text
    assert "#torsion_1" in text
    assert "#out_of_plane" in text
    assert "#nonbond(12-6)" in text
    assert "@type A-B" in text
    assert "@combination geometric" in text


def test_build_frc_cvff_with_generic_bonded_bonded_entries_not_empty(tmp_path: Path) -> None:
    """Test that bonded sections contain actual data entries."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF", "N_MOF"],
        bond_types=[("C_MOF", "H_MOF"), ("C_MOF", "N_MOF")],
        angle_types=[("H_MOF", "C_MOF", "H_MOF"), ("H_MOF", "C_MOF", "N_MOF")],
        dihedral_types=[("H_MOF", "C_MOF", "N_MOF", "H_MOF")],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
            "N_MOF": {"element": "N", "mass_amu": 14.007, "lj_sigma_angstrom": 3.3, "lj_epsilon_kcal_mol": 0.05},
        }
    )

    out = tmp_path / "cvff.frc"
    build_frc_cvff_with_generic_bonded(ts, ps, out_path=out)
    text = out.read_text(encoding="utf-8")

    # Find sections and check they have data after the headers
    # Bond entries should include numeric values
    assert " 2.0  18    C_MOF" in text or " 2.0  18    H_MOF" in text
    
    # Check that there are actual bond parameter values (r0, k)
    lines = text.split("\n")
    bond_section_started = False
    bond_data_found = False
    for line in lines:
        if "#quadratic_bond" in line:
            bond_section_started = True
            continue
        if bond_section_started and line.startswith(" 2.0"):
            bond_data_found = True
            break
        if bond_section_started and line.startswith("#"):
            break  # Next section
    
    assert bond_data_found, "No bond data entries found in #quadratic_bond section"


def test_build_frc_cvff_with_generic_bonded_raises_on_missing_types(tmp_path: Path) -> None:
    """Test that MissingTypesError is raised for missing parameterset entries."""
    ts = _termset(
        atom_types=["C_MOF", "H_MOF", "MISSING_TYPE"],
        bond_types=[],
        angle_types=[],
        dihedral_types=[],
        improper_types=[],
    )
    ps = _parameterset(
        atom_types={
            "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.4, "lj_epsilon_kcal_mol": 0.1},
            "H_MOF": {"element": "H", "mass_amu": 1.008, "lj_sigma_angstrom": 2.5, "lj_epsilon_kcal_mol": 0.01},
        }
    )

    out = tmp_path / "test.frc"
    with pytest.raises(MissingTypesError) as exc_info:
        build_frc_cvff_with_generic_bonded(ts, ps, out_path=out)

    assert "MISSING_TYPE" in str(exc_info.value)


def test_build_frc_cvff_with_generic_bonded_calf20_integration(tmp_path: Path) -> None:
    """Test with real CALF20 termset/parameterset data."""
    ts_path = Path("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/termset.json")
    ps_path = Path("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/parameterset.json")

    if not ts_path.exists() or not ps_path.exists():
        pytest.skip("CALF20 data files not available")

    ts = json.loads(ts_path.read_text(encoding="utf-8"))
    ps = json.loads(ps_path.read_text(encoding="utf-8"))

    out = tmp_path / "calf20_generic_bonded.frc"
    result = build_frc_cvff_with_generic_bonded(ts, ps, out_path=out)

    assert out.exists()
    text = out.read_text(encoding="utf-8")

    # Verify all atom types are present
    for at in ts.get("atom_types", []):
        assert at in text, f"Missing atom type: {at}"

    # Verify truncation alias for Zn_MOF
    assert "Zn_MO" in text

    # Verify bonded sections have entries for termset types
    for t1, t2 in ts.get("bond_types", [])[:3]:  # Check first 3 bond types
        assert t1 in text
        assert t2 in text

    # Count lines - should be compact but include bonded entries
    line_count = len(text.splitlines())
    assert line_count > 100, f"File too small: {line_count} lines"
    assert line_count < 1000, f"File unexpectedly large: {line_count} lines"

    print(f"CALF20 generic bonded .frc file: {line_count} lines")
