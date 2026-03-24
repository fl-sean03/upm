# UPM — Unified Parameter Model

UPM is a **standalone** Python library + CLI for managing, validating, and exporting **force-field parameter packages**. It supports both MSI/BIOSYM `.frc` (for LAMMPS via `msi2lmp`) and CHARMM `.prm` (for NAMD/CHARMM/OpenMM) formats.

It is designed to:
- Eliminate parameter file sprawl (dozens of `.frc`/`.prm` copies across projects)
- Make parameter sets **versioned, reproducible, and diffable**
- Export **minimal** parameter files for a specific set of required atom types
- Provide **cross-package search and comparison** via the registry module
- Stay independent of any particular structure library

UPM does **not** store charges. Charges belong to the structure representation.

---

## What's in v2.0.0

### Codecs
- **MSI `.frc`** (BIOSYM format): Full read/write for `#atom_types`, `#quadratic_bond`, `#quadratic_angle`, `#torsion_1`, `#out_of_plane`, `#equivalence`, `#nonbond(12-6)`, `#bond_increments`. Unknown sections preserved losslessly.
- **CHARMM `.prm`**: Full read/write for BONDS, ANGLES, DIHEDRALS, IMPROPER, NONBONDED, NBFIX. CMAP preserved as raw passthrough. LJ conversion (epsilon/Rmin ↔ A/B) roundtrip-verified.

### Core
- Table schemas for 7 parameter types: `atom_types`, `bonds`, `angles`, `torsions`, `out_of_plane`, `equivalences`, `pair_overrides`
- Deterministic canonicalization (bond/angle/dihedral key ordering)
- SHA256-verified package bundles with manifest provenance

### Build
- `FRCBuilder` with protocol-based `ParameterSource` and `ChainedSource` fallback
- Built-in sources: `ParameterSetSource`, `PlaceholderSource`, `ExistingFRCSource`

### Registry
- Discover parameter packages via pip entry points (`upm.data_packages` group) or local directories
- Cross-package search by atom type or bond type
- Structured diffs between parameter sets (added/removed types, changed values)

### CLI (9 commands)
```
upm version         Print version
upm import-frc      Import .frc into versioned package
upm import-prm      Import CHARMM .prm and display summary
upm export-frc      Export .frc from package
upm build-frc       Build .frc from termset + parameterset
upm validate        Validate package bundle
upm derive-req      Derive requirements from structure
upm search          Search atom types across packages
upm diff            Compare two force field files (.frc or .prm)
```

---

## Install

```bash
pip install -e .[dev]
```

Run tests:

```bash
pytest -q
```

---

## Quickstart

### Import and roundtrip a force field

```python
from upm.codecs.msi_frc import read_frc, write_frc
from upm.codecs.charmm_prm import read_prm, write_prm

# Read .frc
tables, unknown = read_frc("cvff_interface_v1_5.frc", validate=False)
write_frc("output.frc", tables=tables, mode="full")

# Read .prm
tables, raw = read_prm("charmm27_interface_v1_5.prm")
write_prm("output.prm", tables=tables, raw_sections=raw)
```

### Search and diff

```python
from upm.registry import discover_local_packages, PackageIndex, diff_tables

packages = discover_local_packages(Path("./packages"))
index = PackageIndex(packages)
results = index.search_atom_type("Au")

diff = diff_tables(old_tables, new_tables)
print(diff.summary())
```

### Build minimal .frc for a structure

```python
from upm.build import FRCBuilder, ChainedSource, ParameterSetSource, PlaceholderSource

source = ChainedSource([ParameterSetSource(ps), PlaceholderSource(elem_map)])
builder = FRCBuilder(termset, source)
builder.write("minimal.frc")
```

---

## Repo layout

```
src/upm/         # Library code
  core/          # Data model, tables, validation, resolver
  codecs/        # .frc and .prm parsers/writers
  build/         # FRCBuilder and parameter sources
  registry/      # Package discovery, search, diff
  bundle/        # Versioned package storage
  io/            # JSON I/O for requirements, termsets
  cli/           # Typer-based CLI
assets/          # Reference .prm file
tests/           # 170 pytest tests
docs/            # API reference, migration guide, data package spec
workspaces/      # Runnable demos
```

---

## Documentation

- [API Reference](docs/API.md)
- [Migration Guide (v0.1 → v2.0)](docs/MIGRATION_v1_to_v2.md)
- [Creating a Data Package](docs/DATA_PACKAGE.md)

---

## Design Principles

- **Standalone:** No dependency on USM or any orchestrator
- **Deterministic:** Canonical ordering, stable exports, SHA256 manifests
- **No silent physics changes:** Missing required terms fail by default
- **Provenance-first:** Every package records hashes of sources and tables
- **Multi-format:** .frc and .prm codecs with verified roundtrips
- **Extensible:** Registry discovers data packages via pip entry points (OpenFF model)
