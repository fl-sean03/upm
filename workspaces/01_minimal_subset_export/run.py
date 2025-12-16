"""Workspace 01: minimal subset export (v0.1).

This workspace is self-contained (no repo-level assets required). It:
1) builds a synthetic demo package bundle under outputs/packages/<name>/<version>
2) loads requirements.json
3) resolves a minimal subset via upm.core.resolve.resolve_minimal()
4) exports outputs/minimal.frc
5) re-imports outputs/minimal.frc and asserts it contains only required rows

On hard missing-term failure, it writes outputs/missing.json and exits non-zero.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from upm.bundle.io import load_package, save_package
from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc
from upm.core.resolve import MissingTermsError, resolve_minimal
from upm.io.requirements import read_requirements_json


def _fixture_frc_text() -> str:
    # Include extra terms so the resolver can meaningfully subset.
    return "\n".join(
        [
            "#atom_types",
            "  c3  C  12.011  carbon sp3",
            "  o   O  15.999  oxygen",
            "  h   H  1.008   hydrogen",
            "#quadratic_bond",
            "  o  c3  100.0  1.23",
            "  c3 h   250.0  1.09",
            "#nonbond(12-6)",
            "  @type A-B",
            "  @combination geometric",
            "  c3  1.0   2.0",
            "  o   10.0  20.0",
            "  h   0.1   0.2",
            "#unsupported_section",
            "kept",
        ]
    ) + "\n"


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    here = Path(__file__).resolve().parent
    outputs = here / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    pkg_name = "demo-ff"
    pkg_version = "v0"
    pkg_root = outputs / "packages" / pkg_name / pkg_version

    src_text = _fixture_frc_text()
    tables_full, unknown_full = parse_frc_text(src_text)

    save_package(
        pkg_root,
        name=pkg_name,
        version=pkg_version,
        tables=tables_full,
        source_text=src_text,
        unknown_sections=unknown_full,
    )

    req_path = here / "requirements.json"
    req = read_requirements_json(req_path)

    bundle = load_package(pkg_root)

    try:
        resolved = resolve_minimal(bundle.tables, req)
    except MissingTermsError as e:
        _write_json(outputs / "missing.json", {"error": str(e), "missing_atom_types": list(e.missing_atom_types), "missing_bond_types": list(e.missing_bond_types)})
        raise SystemExit(str(e))

    minimal_tables: dict[str, object] = {"atom_types": resolved.atom_types}
    if resolved.bonds is not None:
        minimal_tables["bonds"] = resolved.bonds

    out_frc = outputs / "minimal.frc"
    write_frc(out_frc, tables=minimal_tables, unknown_sections=bundle.raw["unknown_sections"], mode="minimal")

    # Reimport and assert only required terms exist
    tables_min, unknown_min = read_frc(out_frc)

    # Atom types: exact set match
    got_atoms = set(tables_min["atom_types"]["atom_type"].astype("string").tolist())
    want_atoms = set(req.atom_types)
    if got_atoms != want_atoms:
        raise SystemExit(f"atom_types mismatch: got={sorted(got_atoms)!r} want={sorted(want_atoms)!r}")

    # Bonds: exact set match (if any)
    if req.bond_types:
        keys = list(zip(tables_min["bonds"]["t1"].astype("string").tolist(), tables_min["bonds"]["t2"].astype("string").tolist()))
        got_bonds = set(keys)
        want_bonds = set(req.bond_types)
        if got_bonds != want_bonds:
            raise SystemExit(f"bond_types mismatch: got={sorted(got_bonds)!r} want={sorted(want_bonds)!r}")
    else:
        if "bonds" in tables_min and len(tables_min["bonds"]) > 0:
            raise SystemExit("expected zero bonds in minimal export")

    # Unknowns preserved
    if unknown_min.get("#unsupported_section") != unknown_full.get("#unsupported_section"):
        raise SystemExit("unknown section did not roundtrip")

    # Deterministic empty/no missing file: remove if exists
    missing_path = outputs / "missing.json"
    if missing_path.exists():
        missing_path.unlink()

    _write_json(outputs / "report.json", {"minimal_frc": str(out_frc), "atom_types": sorted(list(want_atoms)), "bond_types": [list(x) for x in sorted(list(want_bonds))]})

    # Basic sanity for deterministic dataframes
    pd.testing.assert_frame_equal(
        tables_min["atom_types"].sort_values(["atom_type"]).reset_index(drop=True),
        tables_min["atom_types"],
        check_like=False,
    )


if __name__ == "__main__":
    main()