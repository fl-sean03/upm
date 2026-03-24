# Migration Guide: UPM v0.1 → v2.0

## Breaking Changes

### MissingTypesError field name
**v0.1:** `error.missing_atom_types` (tuple)
**v2.0:** `error.missing_types` (tuple)

The canonical `MissingTypesError` is now in `upm.build.validators`. The old
version in `upm.build.frc_helpers` re-exports the new one.

```python
# v0.1
except MissingTypesError as e:
    print(e.missing_atom_types)

# v2.0
except MissingTypesError as e:
    print(e.missing_types)
```

### CHARMM .prm codec
**v0.1:** `read_prm()` and `write_prm()` raised `NotImplementedError`
**v2.0:** Both work. `read_prm()` returns `(tables, raw_sections)`.

### frc_minimal_base deleted
**v0.1:** `build_frc_cvff_with_minimal_base()` available (deprecated)
**v2.0:** Deleted. Use `FRCBuilder` or `build_frc_cvff_with_generic_bonded()`.

## Deprecated APIs (still work, use FRCBuilder instead)

| v0.1 API | v2.0 Replacement |
|----------|-----------------|
| `build_frc_cvff_with_generic_bonded()` | `FRCBuilder` with `ChainedSource` |
| `build_frc_from_existing()` | `FRCBuilder` with `ExistingFRCSource` |
| `build_minimal_cvff_frc()` | `FRCBuilder` |
| `build_frc_nonbond_only()` | `FRCBuilder` (nonbond source only) |

All legacy APIs now delegate to `FRCBuilder` internally via `_legacy.py`.

## New Capabilities

### New table types
- `torsions`: `#torsion_1` section support in .frc
- `out_of_plane`: `#out_of_plane` section support in .frc
- `equivalences`: `#equivalence` section support in .frc

### CHARMM .prm codec
```python
from upm.codecs.charmm_prm import read_prm, write_prm
tables, raw = read_prm("charmm36.prm")
write_prm("output.prm", tables=tables, raw_sections=raw)
```

### Parameter registry
```python
from upm.registry import discover_packages, PackageIndex, diff_tables
packages = discover_packages()
index = PackageIndex(packages)
diff = diff_tables(old_tables, new_tables)
```

### New CLI commands
- `upm import-prm`: Parse CHARMM .prm files
- `upm search`: Cross-package atom type search
- `upm diff`: Compare two force field files
