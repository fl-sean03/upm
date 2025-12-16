# DevGuide_v0.1.0 — UPM (Unified Parameter Model)

Status target: **UPM v0.1.0 working end-to-end** from a fresh repo  
Starting state: fresh empty repo + this dev guide + `assets/` containing the provided `.frc` and `.prm`

---

## 0) What you’re building

UPM is a **standalone, versioned, testable parameter-package system** for force fields used in Heinz-lab workflows (e.g., INTERFACE/IFF variants), with **import/export** and a **resolver** to generate engine-specific parameter files (v0.1 focuses on **MSI `.frc`**).

UPM is intentionally independent: it **does not require USM** or any other repo to function. Later, it can be integrated with USM (structures) via a small adapter that produces a `Requirements` object.

**Charges are NOT stored in UPM.** Charges live in whatever structure representation you use (USM later, or any other).

---

## 1) v0.1.0 deliverable (what must work)

From a fresh repo, you must be able to:

1. Import a `.frc` in `assets/` into a canonical UPM package:
   - parse supported sections into tables
   - preserve unsupported sections as raw text blobs (so we don’t lose info)
2. Validate the package (schema + invariants).
3. Export:
   - full `.frc` from canonical tables (supported sections)
   - minimal subset `.frc` given a **Requirements** file (JSON)
4. Run reproducible demos via `workspaces/` that exercise the end-to-end flow.

**No USM dependency in v0.1.0.** Requirements come from a JSON file or a toy structure JSON (inside a workspace).

---

## 2) What’s in `assets/` (inputs you have)

You have two long files in `assets/` (names may vary by copy):

- A CVFF/IFF-style `.frc` (e.g., `cvff_IFF_metal_oxides_v2.frc`)
- A CHARMM-style `.prm` (e.g., `IFF_CHARMM36_metal_and_alumina_phases_V8.prm`)

In v0.1.0:
- `.frc` is fully in-scope (subset parse + export).
- `.prm` is **stub-only** (we keep it in assets for future versions; implement a codec stub that clearly errors).

---

## 3) Non-goals (do NOT implement in v0.1.0)

- Do not attempt to “convert physics” between CVFF/PCFF and CHARMM.
- Do not implement CMAP, NBFIX, or full CHARMM `.prm` parsing.
- Do not implement a database server.
- Do not implement atom-typing or charge models.
- Do not try to represent every `.frc` section as normalized tables. Preserve unknown sections as raw.

---

## 4) Core concept: packages vs requirements

### A) UPM Package (definition)
A package is a versioned folder containing:
- canonical tables (atom types, bonds, angles, torsions, nonbonded)
- a manifest with provenance + hashes
- raw copies of original source files and unsupported sections

### B) Requirements (what you need for *this* system/molecule)
A Requirements object is a compact description of what parameters are needed:

- atom types used (strings)
- bond type tuples used
- angle type tuples used (optional in v0.1)
- dihedral tuples used (optional in v0.1)

**In v0.1.0, requirements come from a JSON file.**  
Later, USM will produce the same Requirements object.

---

## 5) Repository layout (must match)

```
upm/
  README.md
  pyproject.toml
  assets/
    cvff_IFF_metal_oxides_v2.frc
    IFF_CHARMM36_metal_and_alumina_phases_V8.prm
  src/upm/
    __init__.py
    core/
      model.py          # dataclasses for Requirements, Package, ResolvedFF
      tables.py         # canonical table schemas + normalization
      validate.py       # schema + semantic validators
      resolve.py        # minimal subset selection + missing-term handling
    bundle/
      io.py             # save/load package bundles (parquet/csv)
      manifest.py       # manifest read/write + hashing
    codecs/
      msi_frc.py        # import/export .frc (v0.1)
      charmm_prm.py     # stub (v0.1)
    io/
      requirements.py   # read/write Requirements JSON; optional toy structure JSON -> Requirements
    cli/
      main.py           # `upm ...`
      commands/
        import_frc.py
        export_frc.py
        validate_pkg.py
  workspaces/
    00_quickcheck_import_export/
      run.py
      outputs/
    01_minimal_subset_export/
      run.py
      requirements.json
      outputs/
    (nested dirs allowed, e.g., workspaces/cvff/demos/<slug>/run.py)
  tests/
    test_bundle_roundtrip.py
    test_frc_import_export_roundtrip.py
    test_resolve_minimal_subset.py
    test_requirements_io.py
  docs/
    DATA_MODEL.md
    WORKFLOWS.md
    FORMAT_SUPPORT.md
    GOVERNANCE.md
  .gitignore
```

### Workspace contract
Every runnable workspace has:
- `run.py` as the entrypoint
- optionally `config.py` or `config.json`
- an `outputs/` directory (created at runtime if missing)

Workspaces may be nested arbitrarily under `workspaces/`. The runner should not assume flat structure.

---

## 6) Canonical data model (v0.1.0)

UPM stores tables as Pandas DataFrames with enforced dtypes and deterministic sorting.

### 6.1 Tables

#### `atom_types` (required)
Columns:
- `atom_type` (string) — primary key
- `element` (string, nullable)
- `mass_amu` (float32, nullable)
- `vdw_style` (string) — for v0.1 `.frc`: `"lj_ab_12_6"`
- `lj_a` (float64, nullable)
- `lj_b` (float64, nullable)
- `notes` (string, nullable)

#### `bonds` (optional but recommended)
- `t1` (string)
- `t2` (string) with invariant `t1 <= t2`
- `style` (string) — `"quadratic"` (v0.1: support quadratic only)
- `k` (float64)
- `r0` (float64)
- `source` (string, nullable)

#### `angles` (optional in v0.1)
- `t1,t2,t3` with invariant `t1 <= t3` around central `t2`
- `style` = `"quadratic"`
- `k`, `theta0_deg`

#### `dihedrals` (optional in v0.1)
- `t1,t2,t3,t4` with reversal canonicalization
- `style` = `"torsion_1"` (if supported)
- coefficient fields as required by your torsion_1 interpretation

#### `pair_overrides` (optional)
- `t1,t2` canonicalized
- `lj_a`, `lj_b`

### 6.2 Raw preservation
Store unsupported `.frc` sections as raw text blobs in:
- `raw/unknown_sections.json` mapping `section_name -> [lines...]`

---

## 7) Bundle format (packages on disk)

Each package is stored as:

```
packages/<name>/<version>/
  manifest.json
  tables/
    atom_types.(parquet|csv)
    bonds.(parquet|csv)
    angles.(parquet|csv)
    dihedrals.(parquet|csv)
    pair_overrides.(parquet|csv)
  raw/
    source.frc
    unknown_sections.json
```

### 7.1 `manifest.json` required fields
- `schema_version`: `"upm-1.0"`
- `name`, `version`
- `created_utc`
- `units`: length/energy/mass/angle
- `nonbonded`: style/form/mixing (for v0.1 `.frc`: `A-B`, `12-6`, `geometric`)
- `features`: list of strings
- `sources`: list of `{path, sha256}`
- `tables`: map table_name → `{path, rows, sha256, dtypes}`

---

## 8) Requirements I/O (standalone v0.1)

UPM must include `upm.io.requirements` for loading Requirements JSON.

### 8.1 Requirements JSON schema (v0.1)

Minimal file:

```json
{
  "atom_types": ["c3", "o", "h"],
  "bond_types": [["c3","o"], ["c3","h"]],
  "angle_types": [],
  "dihedral_types": []
}
```

Rules:
- Each tuple list is canonicalized on read (bonds sorted; angles endpoints sorted; dihedral reversal canonicalized).
- Any missing arrays default to empty.

### 8.2 Optional “toy structure” JSON -> Requirements (nice-to-have)
Support a second format to make demos easier:

```json
{
  "atoms": [
    {"aid": 0, "atom_type": "c3"},
    {"aid": 1, "atom_type": "o"},
    {"aid": 2, "atom_type": "h"}
  ],
  "bonds": [
    {"a1": 0, "a2": 1},
    {"a1": 0, "a2": 2}
  ]
}
```

UPM can compute:
- `atom_types` from atoms
- `bond_types` from bonds + atom_type lookup
Angles/dihedrals are optional in v0.1.

This is the bridge: later, USM is just another “structure source” that produces Requirements.

---

## 9) `.frc` codec requirements (v0.1)

### 9.1 Parse these sections into tables
- `#atom_types`
- `#quadratic_bond`
- `#quadratic_angle` (optional in v0.1; implement if you can quickly)
- `#torsion_1` (optional in v0.1)
- `#nonbond(12-6)` with:
  - `@type A-B`
  - `@combination geometric`

### 9.2 Preserve everything else
Any other `#section` is stored in `unknown_sections.json`.

### 9.3 Export behavior
- `export-fc` full: emits all supported tables
- minimal: emits only the rows required by Requirements

---

## 10) Resolver rules (core correctness)

Implement `resolve_minimal(tables, requirements) -> ResolvedFF`:

- Select subset rows matching Requirements keys.
- Default: error if any required atom type or tuple is missing.
- Optional debug: `--allow-missing` continues, but must:
  - print warnings
  - write `outputs/missing.json`
  - exit non-zero unless `--force` is specified.

**v0.1 recommendation:** require only `atom_types` + `bond_types`. Angles/dihedrals can be empty for initial acceptance.

---

## 11) CLI spec (standalone v0.1)

Use `typer`.

### 11.1 Commands

#### `upm import-frc`
- `upm import-frc assets/cvff_IFF_metal_oxides_v2.frc --name cvff-iff --version v2`
- Creates `packages/cvff-iff/v2/` with manifest + tables + raw blobs.

#### `upm validate`
- `upm validate --package cvff-iff@v2`
- Or `upm validate --path packages/cvff-iff/v2`

#### `upm export-frc`
- Full export:
  - `upm export-frc --package cvff-iff@v2 --out outputs/full.frc --mode full`
- Minimal export:
  - `upm export-frc --package cvff-iff@v2 --requirements workspaces/01_minimal_subset_export/requirements.json --out outputs/min.frc --mode minimal`

---

## 12) Canonicalization rules (MUST implement exactly)

- Atom types: unique `atom_type`, sorted.
- Bonds: `(t1,t2)` sorted so `t1 <= t2`.
- Angles: endpoints sorted so `t1 <= t3` around central `t2`.
- Dihedrals: store lexicographically smaller of forward and reversed.
- Tables sorted by key columns.
- Export float formatting stable across runs.

---

## 13) Implementation plan (short, self-contained thrusts)

Each thrust:
- updates code
- adds tests
- has a clear local validation command

### Thrust 0 — Repo bootstrap
Goal: package installs, CLI runs, tests scaffold.

Validate:
```bash
pip install -e .[dev]
upm --help
pytest -q
ruff check .
```

### Thrust 1 — Core models: Requirements + ResolvedFF
- `upm.core.model.Requirements`
- `upm.io.requirements.read_requirements_json(path)`
- Tests: `test_requirements_io.py`

### Thrust 2 — Table schemas + validation
- `upm.core.tables` defines expected columns/dtypes
- `upm.core.validate.validate_tables(tables)`
- Tests: schema enforcement + canonicalization

### Thrust 3 — Bundle I/O + manifest hashing
- `save_package(folder)` / `load_package(folder)`
- parquet preferred, CSV fallback
- Tests: roundtrip

### Thrust 4 — `.frc` import (supported subset) + raw preservation
- Parse `assets/*.frc` into tables + unknown sections
- Tests: parse doesn’t crash; known sections produce non-empty tables where present

### Thrust 5 — `.frc` export (full)
- Export supported tables to `.frc`
- Tests: import → export(full) → import yields identical supported tables

### Thrust 6 — Resolver + minimal export
- Resolve subset from Requirements
- Export minimal `.frc`
- Tests: minimal contains only required types/tuples; missing triggers explicit errors

### Thrust 7 — CLI commands
- `import-frc`, `validate`, `export-frc`
- Tests can call underlying functions; CLI smoke tests optional.

### Thrust 8 — Workspaces (seed demos)
Create two seed workspaces:

#### `workspaces/00_quickcheck_import_export/run.py`
Does:
1) import `assets/*.frc` into a temp package under `workspaces/.../outputs/packages/`
2) export full `.frc`
3) re-import exported `.frc`
4) validate tables match
Outputs:
- `outputs/full_export.frc`
- `outputs/roundtrip_report.json`

#### `workspaces/01_minimal_subset_export/run.py`
Does:
1) load package from `packages/` (assumes user ran `upm import-frc ...`)
2) load `requirements.json`
3) resolve + export minimal `.frc`
Outputs:
- `outputs/minimal.frc`
- `outputs/missing.json` (empty or absent on success)

Validation:
```bash
python workspaces/00_quickcheck_import_export/run.py
upm import-frc assets/cvff_IFF_metal_oxides_v2.frc --name cvff-iff --version v2
python workspaces/01_minimal_subset_export/run.py
```

---

## 14) Governance (version sprawl killer)

- Every curated package version must live at `packages/<name>/<version>/`.
- Manifest includes sha256 of the source `.frc`.
- Any changes require:
  - table diff output (future: `upm diff`)
  - tests updated if needed
- Default `.gitignore` should ignore `packages/` unless you’re curating and committing.

---

## 15) Acceptance tests (must pass)

- AT1: `.frc` supported-subset round-trip equality
- AT2: minimal subset export matches Requirements exactly
- AT3: missing-term errors are explicit and list missing keys

---

## 16) Future integration with USM (do NOT implement now)

When USM exists, integration is a thin adapter:

- `requirements_from_usm(usm)` produces the same `Requirements` object used today.
- Keep this as a separate module later (e.g., `upm.integrations.usm`) so UPM stays standalone.

UPM’s public API should already make this easy:
- “whatever you have” → `Requirements` → `resolve_minimal` → `export`.

---

End of DevGuide_v0.1.0
