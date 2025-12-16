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

