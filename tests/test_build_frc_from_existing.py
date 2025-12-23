"""Tests for build_frc_from_existing builder function.

This module tests the functionality of extracting parameters from existing
FRC files to create minimal FRC files for specific termsets.

Expected CO2 parameters from cvff_iff_ILs.frc:
    - cdc: carbon in CO2 (12.011150 amu, C element)
    - cdo: oxygen in CO2 (15.999400 amu, O element)
    - Bond cdc-cdo: r0=1.162Å, k=1140.0
    - Angle cdo-cdc-cdo: θ0=180.0°, k=100.0
    - Nonbond cdc: A=236919.1, B=217.67820
    - Nonbond cdo: A=207547.3, B=315.63070
"""
from __future__ import annotations

from pathlib import Path

import pytest

from upm.build.frc_builders import (
    MissingTypesError,
    build_frc_from_existing,
)
from upm.codecs.msi_frc import parse_frc_text

from conftest import make_termset


# =============================================================================
# Tests for build_frc_from_existing
# =============================================================================


class TestBuildFrcFromExisting:
    """Tests for build_frc_from_existing builder function."""

    def test_builds_frc_from_co2_source(self, tmp_path: Path) -> None:
        """build_frc_from_existing creates valid FRC with CO2 parameters."""
        # Create a minimal source FRC with CO2 params
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2
 3.6  32    cdo   15.999400    O           1        O in CO2

#quadratic_bond	cvff

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
 3.6  32     cdc   cdo       1.1620   1140.0000

#quadratic_angle	cvff

!Ver  Ref     I     J     K       Theta0         K2
!---- ---    ----  ----  ----    --------     -------
 3.6  32     cdo   cdc   cdo     180.0000    100.0000

#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 3.6  32     cdc     236919.1	     217.67820
 3.6  32     cdo     207547.3        315.63070
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        termset = make_termset(
            ["cdc", "cdo"],
            bond_types=[["cdc", "cdo"]],
            angle_types=[["cdo", "cdc", "cdo"]],
        )

        out_path = tmp_path / "minimal.frc"
        result = build_frc_from_existing(
            termset=termset,
            source_frc_path=source_frc,
            out_path=out_path,
            strict=True,
        )

        assert result == str(out_path)
        assert out_path.exists()

        # Parse and verify contents
        text = out_path.read_text(encoding="utf-8")
        tables, unknown = parse_frc_text(text)

        # Verify atom types
        assert "atom_types" in tables
        at_df = tables["atom_types"]
        assert set(at_df["atom_type"]) == {"cdc", "cdo"}

        cdc_row = at_df[at_df["atom_type"] == "cdc"].iloc[0]
        assert float(cdc_row["mass_amu"]) == pytest.approx(12.011150)
        assert float(cdc_row["lj_a"]) == pytest.approx(236919.1)
        assert float(cdc_row["lj_b"]) == pytest.approx(217.67820)

        cdo_row = at_df[at_df["atom_type"] == "cdo"].iloc[0]
        assert float(cdo_row["mass_amu"]) == pytest.approx(15.999400)
        assert float(cdo_row["lj_a"]) == pytest.approx(207547.3)
        assert float(cdo_row["lj_b"]) == pytest.approx(315.63070)

    def test_raises_missing_types_error_strict_mode(self, tmp_path: Path) -> None:
        """build_frc_from_existing raises MissingTypesError when type not found."""
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        termset = make_termset(["cdc", "missing_type"])

        with pytest.raises(MissingTypesError) as exc_info:
            build_frc_from_existing(
                termset=termset,
                source_frc_path=source_frc,
                out_path=tmp_path / "out.frc",
                strict=True,
            )

        assert "missing_type" in exc_info.value.missing_atom_types

    def test_continues_without_error_non_strict_mode(self, tmp_path: Path) -> None:
        """build_frc_from_existing proceeds with partial types when strict=False."""
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2

#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 3.6  32     cdc     236919.1	     217.67820
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        termset = make_termset(["cdc", "missing_type"])
        out_path = tmp_path / "out.frc"

        # Should not raise
        result = build_frc_from_existing(
            termset=termset,
            source_frc_path=source_frc,
            out_path=out_path,
            strict=False,
        )

        assert out_path.exists()

    def test_raises_file_not_found_for_missing_source(self, tmp_path: Path) -> None:
        """build_frc_from_existing raises FileNotFoundError for missing source."""
        termset = make_termset(["cdc"])
        missing_path = tmp_path / "nonexistent.frc"

        with pytest.raises(FileNotFoundError):
            build_frc_from_existing(
                termset=termset,
                source_frc_path=missing_path,
                out_path=tmp_path / "out.frc",
            )

    def test_raises_missing_types_for_missing_bonds(self, tmp_path: Path) -> None:
        """build_frc_from_existing raises MissingTypesError for missing bond types."""
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2
 3.6  32    cdo   15.999400    O           1        O in CO2

#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 3.6  32     cdc     236919.1	     217.67820
 3.6  32     cdo     207547.3        315.63070
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        # Request a bond that doesn't exist in source
        termset = make_termset(
            ["cdc", "cdo"],
            bond_types=[["cdc", "cdo"]],  # Not in source
        )

        with pytest.raises(MissingTypesError) as exc_info:
            build_frc_from_existing(
                termset=termset,
                source_frc_path=source_frc,
                out_path=tmp_path / "out.frc",
                strict=True,
            )

        # Error should mention the missing bond
        assert "cdc-cdo" in exc_info.value.missing_atom_types

    def test_raises_missing_types_for_missing_angles(self, tmp_path: Path) -> None:
        """build_frc_from_existing raises MissingTypesError for missing angle types."""
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2
 3.6  32    cdo   15.999400    O           1        O in CO2

#quadratic_bond	cvff

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
 3.6  32     cdc   cdo       1.1620   1140.0000

#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 3.6  32     cdc     236919.1	     217.67820
 3.6  32     cdo     207547.3        315.63070
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        # Request an angle that doesn't exist in source
        termset = make_termset(
            ["cdc", "cdo"],
            bond_types=[["cdc", "cdo"]],
            angle_types=[["cdo", "cdc", "cdo"]],  # Not in source
        )

        with pytest.raises(MissingTypesError) as exc_info:
            build_frc_from_existing(
                termset=termset,
                source_frc_path=source_frc,
                out_path=tmp_path / "out.frc",
                strict=True,
            )

        # Error should mention the missing angle
        assert "cdo-cdc-cdo" in exc_info.value.missing_atom_types

    def test_is_byte_deterministic(self, tmp_path: Path) -> None:
        """build_frc_from_existing produces identical output for same input."""
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2
 3.6  32    cdo   15.999400    O           1        O in CO2

#quadratic_bond	cvff

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
 3.6  32     cdc   cdo       1.1620   1140.0000

#quadratic_angle	cvff

!Ver  Ref     I     J     K       Theta0         K2
!---- ---    ----  ----  ----    --------     -------
 3.6  32     cdo   cdc   cdo     180.0000    100.0000

#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 3.6  32     cdc     236919.1	     217.67820
 3.6  32     cdo     207547.3        315.63070
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        termset = make_termset(
            ["cdc", "cdo"],
            bond_types=[["cdc", "cdo"]],
            angle_types=[["cdo", "cdc", "cdo"]],
        )

        out1 = tmp_path / "out1.frc"
        out2 = tmp_path / "out2.frc"

        build_frc_from_existing(termset, source_frc, out_path=out1)
        build_frc_from_existing(termset, source_frc, out_path=out2)

        assert out1.read_bytes() == out2.read_bytes()

    def test_output_contains_required_sections(self, tmp_path: Path) -> None:
        """build_frc_from_existing output has all required FRC sections."""
        source_content = """\
!BIOSYM forcefield          1

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 3.6  32    cdc   12.011150    C           2        C in CO2

#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
 3.6  32     cdc     236919.1	     217.67820
"""
        source_frc = tmp_path / "source.frc"
        source_frc.write_text(source_content, encoding="utf-8")

        termset = make_termset(["cdc"])
        out_path = tmp_path / "out.frc"

        build_frc_from_existing(termset, source_frc, out_path=out_path)

        text = out_path.read_text(encoding="utf-8")

        # Check required sections for msi2lmp compatibility
        assert "#atom_types" in text
        assert "#equivalence" in text
        assert "#auto_equivalence" in text
        assert "#nonbond(12-6)" in text
        assert "@type A-B" in text
        assert "@combination geometric" in text


# =============================================================================
# Integration test with real FRC file (if available)
# =============================================================================


@pytest.fixture
def co2_source_frc() -> Path | None:
    """Return path to CO2 source FRC if available, else None."""
    # Try to find the real source FRC file
    frc_path = Path(__file__).resolve().parents[4] / "assets/NIST/CO2_construct/cvff_iff_ILs.frc"
    if frc_path.exists():
        return frc_path
    return None


class TestBuildFrcFromExistingIntegration:
    """Integration tests using real FRC source file."""

    def test_extracts_correct_co2_params_from_real_source(
        self, tmp_path: Path, co2_source_frc: Path | None
    ) -> None:
        """build_frc_from_existing extracts correct CO2 params from cvff_iff_ILs.frc."""
        if co2_source_frc is None:
            pytest.skip("CO2 source FRC file not available")

        termset = make_termset(
            ["cdc", "cdo"],
            bond_types=[["cdc", "cdo"]],
            angle_types=[["cdo", "cdc", "cdo"]],
        )

        out_path = tmp_path / "co2_minimal.frc"
        build_frc_from_existing(
            termset=termset,
            source_frc_path=co2_source_frc,
            out_path=out_path,
            strict=True,
        )

        text = out_path.read_text(encoding="utf-8")
        tables, _ = parse_frc_text(text)

        # Verify atom types with expected values from source
        at_df = tables["atom_types"]
        cdc_row = at_df[at_df["atom_type"] == "cdc"].iloc[0]
        cdo_row = at_df[at_df["atom_type"] == "cdo"].iloc[0]

        # Expected CO2 parameters
        assert float(cdc_row["mass_amu"]) == pytest.approx(12.011150)
        assert float(cdo_row["mass_amu"]) == pytest.approx(15.999400)
        assert float(cdc_row["lj_a"]) == pytest.approx(236919.1)
        assert float(cdc_row["lj_b"]) == pytest.approx(217.67820)
        assert float(cdo_row["lj_a"]) == pytest.approx(207547.3)
        assert float(cdo_row["lj_b"]) == pytest.approx(315.63070)

        # Verify bond section contains correct parameters
        assert "1.162" in text or "1.1620" in text  # r0
        assert "1140" in text  # k

        # Verify angle section contains correct parameters  
        assert "180.0" in text  # theta0
        assert "100.0" in text  # k
