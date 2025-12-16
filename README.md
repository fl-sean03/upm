# UPM — Unified Parameter Model

UPM is a **standalone** Python library + CLI for managing, validating, and exporting **force-field parameter packages** (starting with Materials Studio / BIOSYM-style `*.frc` used by `msi2lmp`).

UPM is designed to:
- eliminate “v86 / v93 / random copies” parameter sprawl
- make parameter sets **versioned + reproducible + diffable**
- export **minimal** parameter files for a specific set of required atom types / interactions
- stay independent of any particular structure/geometry library (USM integration can be layered later)

UPM intentionally does **not** store charges. Charges belong to the structure representation.

---

## What’s included in v0.1.0

- Import: `*.frc` → canonical tables + manifest + raw preserved sections
- Validate: schema + canonicalization invariants
- Export: full `*.frc` from canonical tables
- Export: minimal `*.frc` from a `requirements.json` file
- Workspace demos under [`workspaces/`](workspaces:1)

Not included in v0.1.0:
- Full CHARMM `*.prm` parsing/export (stub only)
- Universal conversion between CVFF/PCFF and CHARMM “physics”
- Automated atom typing / charge models
- DB server

---

## Install (editable)

From the UPM repo root (this directory):

```bash
python -m pip install -e .
```

This installs the CLI entrypoint declared in [`pyproject.toml`](pyproject.toml:1).

---

## CLI

UPM exposes a small CLI for common tasks (see [`upm.cli.main:app`](src/upm/cli/main.py:1)).

```bash
upm --help
```

The v0.1.0 commands map to implementations under:
- [`src/upm/cli/commands/import_frc.py`](src/upm/cli/commands/import_frc.py:1)
- [`src/upm/cli/commands/export_frc.py`](src/upm/cli/commands/export_frc.py:1)
- [`src/upm/cli/commands/validate_pkg.py`](src/upm/cli/commands/validate_pkg.py:1)

---

## Repo layout

- Packaging + CLI:
  - [`pyproject.toml`](pyproject.toml:1)
  - [`src/upm/`](src/upm:1)
- Code:
  - Core model + validation: [`src/upm/core/`](src/upm/core:1)
  - Codecs (e.g., MSI `*.frc`): [`src/upm/codecs/`](src/upm/codecs:1)
  - Bundle I/O helpers: [`src/upm/bundle/`](src/upm/bundle:1)
  - CLI: [`src/upm/cli/`](src/upm/cli:1)
- Tests:
  - [`tests/`](tests:1)
- Docs:
  - [`docs/`](docs:1)

---

## Relationship to MolSAIC / USM

UPM is intentionally usable on its own. In the MolSAIC ecosystem:
- USM handles **structures** (atoms/bonds/cell + deterministic structure ops).
- UPM handles **parameter packages** (`*.frc` today; extensible to other formats later).
