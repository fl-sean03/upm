# UPM — Unified Parameter Model

UPM is a **standalone** Python library + CLI for managing, validating, and exporting **force-field parameter packages** (starting with Materials Studio / BIOSYM-style `*.frc` used by `msi2lmp`).

It is designed to:
- eliminate “v86 / v93 / random copies” parameter sprawl
- make parameter sets **versioned + reproducible + diffable**
- export **minimal** parameter files for a specific set of required atom types / interactions
- stay independent of any particular structure library (USM can be integrated later)

UPM does **not** store charges. Charges belong to the structure representation.

---

## What’s included in v0.1.0

- Import: `*.frc` → canonical tables + manifest + raw preserved sections
- Validate: schema + canonicalization invariants
- Export: full `*.frc` from canonical tables
- Export: minimal `*.frc` from a `requirements.json` file
- Workspace demos under `workspaces/`

Not included in v0.1.0:
- Full CHARMM `*.prm` parsing/export (stub only)
- Universal conversion between CVFF/PCFF and CHARMM “physics”
- Automated atom typing / charge models
- DB server

---

## Repo layout

```

assets/          # provided long .frc / .prm inputs for demos + tests
src/upm/         # library code
packages/        # generated packages (gitignored by default)
workspaces/      # runnable demos; each has run.py and outputs/
tests/           # pytest suite
docs/            # data model, workflows, governance

````

Workspaces can be nested arbitrarily under `workspaces/`. Each workspace must have a `run.py` entrypoint and should write outputs to `outputs/`.

---

## Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
````

Run tests:

```bash
pytest -q
```

---

## Quickstart

### 1) Import a force field (`*.frc`) into a versioned package

```bash
upm import-frc assets/cvff_IFF_metal_oxides_v2.frc --name cvff-iff --version v2
```

This creates:

```
packages/cvff-iff/v2/
  manifest.json
  tables/...
  raw/source.frc
  raw/unknown_sections.json
```

### 2) Validate a package

```bash
upm validate --package cvff-iff@v2
# or:
upm validate --path packages/cvff-iff/v2
```

### 3) Export a full `*.frc`

```bash
upm export-frc --package cvff-iff@v2 --mode full --out outputs/full.frc
```

### 4) Export a minimal `*.frc` using `requirements.json`

Create `requirements.json`:

```json
{
  "atom_types": ["c3", "o", "h"],
  "bond_types": [["c3","o"], ["c3","h"]],
  "angle_types": [],
  "dihedral_types": []
}
```

Then:

```bash
upm export-frc \
  --package cvff-iff@v2 \
  --mode minimal \
  --requirements requirements.json \
  --out outputs/minimal.frc
```

By default, missing required parameters cause a hard error. (If an `--allow-missing` debug flag exists in your build, it must warn loudly and write a `missing.json` report.)

---

## Workspaces (runnable demos)

### Workspace: import → export(full) → re-import round-trip

```bash
python workspaces/00_quickcheck_import_export/run.py
```

Outputs:

* `workspaces/00_quickcheck_import_export/outputs/full_export.frc`
* `workspaces/00_quickcheck_import_export/outputs/roundtrip_report.json`

### Workspace: minimal subset export

```bash
# first import a package:
upm import-frc assets/cvff_IFF_metal_oxides_v2.frc --name cvff-iff --version v2

# then run:
python workspaces/01_minimal_subset_export/run.py
```

Outputs:

* `workspaces/01_minimal_subset_export/outputs/minimal.frc`

---

## Supported `.frc` sections (v0.1.0)

UPM v0.1.0 focuses on a subset required for `msi2lmp` workflows. Typically:

* `#atom_types`
* `#quadratic_bond`
* `#quadratic_angle` (if implemented in the current repo state)
* `#torsion_1` (if implemented)
* `#nonbond(12-6)` with `@type A-B` and `@combination geometric`

Everything else is preserved in `raw/unknown_sections.json` and is not lost.

See `docs/FORMAT_SUPPORT.md` for the exact list once implemented.

---

## Design principles

* **Stand-alone:** no dependency on USM or any orchestrator.
* **Deterministic:** canonical ordering + stable exports.
* **No silent physics changes:** missing required terms fail by default.
* **Provenance-first:** manifests record hashes of sources and tables.
* **Extensible:** additional codecs (e.g., CHARMM PRM) can be added later.

---

## Future integration

When USM (structures) is available, integration is an adapter that produces the same `Requirements` object used today. UPM’s core flow remains:

> Structure/Topology (any source) → Requirements → Resolve → Export

---

## License / attribution

TBD (set explicitly before publishing publicly). Ensure any vendored parameter sets in `assets/` or committed `packages/` are compatible with the chosen license.
