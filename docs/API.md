# UPM v2.0 API Reference

## Core Module (`upm.core`)

### Data Model (`upm.core.model`)
- **`Requirements`**: Frozen dataclass holding atom_types, bond_types, angle_types, dihedral_types
- **`ResolvedFF`**: Container for resolver output (subset DataFrames)
- **`canonicalize_bond_key(t1, t2)`**: Returns `(min, max)` lexicographically
- **`canonicalize_angle_key(t1, t2, t3)`**: Endpoints `t1 <= t3`, center fixed
- **`canonicalize_dihedral_key(t1, t2, t3, t4)`**: Forward vs reversed, pick smaller

### Tables (`upm.core.tables`)

Table schemas (pandas DataFrames with strict column sets):

| Table | Key Columns | Value Columns |
|-------|------------|---------------|
| `atom_types` | atom_type | element, mass_amu, vdw_style, lj_a, lj_b, notes |
| `bonds` | t1, t2, style | k, r0, source |
| `angles` | t1, t2, t3, style | k, theta0_deg, source |
| `torsions` | t1, t2, t3, t4, style | kphi, n, phi0, source |
| `out_of_plane` | t1, t2, t3, t4, style | kchi, n, chi0, source |
| `equivalences` | atom_type | nonb, bond, angle, torsion, oop |
| `pair_overrides` | t1, t2 | lj_a, lj_b |

Normalizers: `normalize_atom_types()`, `normalize_bonds()`, `normalize_angles()`,
`normalize_torsions()`, `normalize_out_of_plane()`, `normalize_equivalences()`,
`normalize_tables()`

### Validation (`upm.core.validate`)
- `validate_atom_types(df)`, `validate_bonds(df)`, `validate_angles(df)`
- `validate_torsions(df)`, `validate_out_of_plane(df)`, `validate_equivalences(df)`
- `validate_tables(tables_dict)` — validates all present tables
- Raises `TableValidationError` with deterministic violation messages

### Resolver (`upm.core.resolve`)
- `resolve_minimal(tables, requirements)` → `ResolvedFF`

## Codecs Module (`upm.codecs`)

### MSI FRC (`upm.codecs.msi_frc`)
```python
from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc

# Parse from string
tables, unknown_sections = parse_frc_text(text, validate=True)

# Read from file
tables, unknown_sections = read_frc("path/to/file.frc")

# Write to file
write_frc("output.frc", tables=tables, unknown_sections=unknown, mode="full")
```

Supported sections: `#atom_types`, `#quadratic_bond`, `#quadratic_angle`,
`#torsion_1`, `#out_of_plane`, `#equivalence`, `#nonbond(12-6)`, `#bond_increments`

### CHARMM PRM (`upm.codecs.charmm_prm`)
```python
from upm.codecs.charmm_prm import read_prm, write_prm

# Read CHARMM .prm
tables, raw_sections = read_prm("path/to/file.prm")

# Write CHARMM .prm
write_prm("output.prm", tables=tables, raw_sections=raw_sections)
```

Supported sections: BONDS, ANGLES, DIHEDRALS, IMPROPER, NONBONDED, NBFIX.
CMAP preserved as raw passthrough.

LJ conversion: CHARMM uses (ε, Rmin/2), UPM uses (A, B). Conversion is automatic
and roundtrip-verified to 6+ decimal places.

## Build Module (`upm.build`)

### FRCBuilder (Recommended API)
```python
from upm.build import FRCBuilder, FRCBuilderConfig, ChainedSource, ParameterSetSource, PlaceholderSource

source = ChainedSource([ParameterSetSource(ps), PlaceholderSource(elem_map)])
builder = FRCBuilder(termset, source, FRCBuilderConfig(strict=True))
builder.write("output.frc")
```

### ParameterSource Protocol
Implement `get_atom_type_info()`, `get_nonbond_params()`, `get_bond_params()`,
`get_angle_params()`, `get_torsion_params()`, `get_oop_params()`.

Built-in sources: `ParameterSetSource`, `PlaceholderSource`, `ExistingFRCSource`, `ChainedSource`.

## Registry Module (`upm.registry`)

### Discovery
```python
from upm.registry import discover_packages, discover_local_packages

# Find pip-installed data packages (entry point group: upm.data_packages)
packages = discover_packages()

# Find local bundles
packages = discover_local_packages(Path("./packages"))
```

### Search
```python
from upm.registry import PackageIndex

index = PackageIndex(packages)
results = index.search_atom_type("Au")
results = index.search_bond("c3", "h")
listing = index.list_atom_types()  # {pkg@ver: [types]}
```

### Diff
```python
from upm.registry import diff_tables

diff = diff_tables(tables_old, tables_new)
print(diff.summary())
# Added types (2): Cu, Pt
# Changed parameters (1):
#   atom_types[Au].lj_a: 100.0 → 200.0
```

## CLI Commands

```bash
upm version              # Print version
upm import-frc FILE      # Import .frc into UPM package
upm import-prm FILE      # Import .prm and display summary
upm export-frc           # Export .frc from package
upm build-frc            # Build .frc from termset + parameterset
upm validate             # Validate package bundle
upm derive-req           # Derive requirements from structure
upm search ATOM_TYPE     # Search across packages
upm diff LEFT RIGHT      # Diff two FF files
```
