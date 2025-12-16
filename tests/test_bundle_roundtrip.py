from __future__ import annotations

from pathlib import Path

import pandas as pd

from upm.bundle.io import load_package, save_package
from upm.bundle.manifest import sha256_file
from upm.core.tables import normalize_tables


def test_bundle_roundtrip_csv_and_manifest_hashes(tmp_path: Path) -> None:
    root = tmp_path / "packages" / "demo" / "v0"

    atom_types = pd.DataFrame(
        [
            {
                "atom_type": "c3",
                "element": "C",
                "mass_amu": 12.011,
                "vdw_style": "lj_ab_12_6",
                "lj_a": 1.0,
                "lj_b": 2.0,
                "notes": None,
            },
            {
                "atom_type": "o",
                "element": "O",
                "mass_amu": 15.999,
                "vdw_style": "lj_ab_12_6",
                "lj_a": 10.0,
                "lj_b": 20.0,
                "notes": " oxygen ",
            },
        ]
    )

    # Intentionally swapped endpoints; normalize should canonicalize to (c3,o)
    bonds = pd.DataFrame(
        [
            {"t1": "o", "t2": "c3", "style": "quadratic", "k": 100.0, "r0": 1.23, "source": None},
        ]
    )

    tables_in = {"atom_types": atom_types, "bonds": bonds}
    norm_in = normalize_tables(tables_in)

    source_text = "# demo frc\n#atom_types\n...\n"
    unknown_sections = {"#unsupported_section": ["line1", "line2"]}

    manifest = save_package(
        root,
        name="demo",
        version="v0",
        tables=tables_in,
        source_text=source_text,
        unknown_sections=unknown_sections,
    )

    loaded = load_package(root, validate_hashes=True)

    # Tables should match deterministically after normalization
    pd.testing.assert_frame_equal(loaded.tables["atom_types"], norm_in["atom_types"], check_like=False)
    pd.testing.assert_frame_equal(loaded.tables["bonds"], norm_in["bonds"], check_like=False)

    # Raw blobs should be preserved
    assert loaded.raw["source_text"] == source_text
    assert loaded.raw["unknown_sections"] == unknown_sections

    # Manifest hashes must match recomputed file hashes
    for item in manifest["sources"]:
        rel = item["path"]
        assert item["sha256"] == sha256_file(root / rel)

    for table_name, meta in manifest["tables"].items():
        rel = meta["path"]
        assert meta["sha256"] == sha256_file(root / rel)
        assert meta["rows"] == len(norm_in[table_name])