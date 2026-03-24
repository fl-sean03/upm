# Creating a UPM Data Package

UPM separates the **toolkit** (parsing, validation, querying) from the **data**
(actual force field parameters). Data packages are pip-installable Python packages
that UPM discovers via entry points.

## Architecture

```
fl-sean03/upm              hendrikheinz/iff-parameters
(toolkit)                   (data package)
     │                            │
     │  pip install upm[heinz]    │
     │  ────────────────────>     │
     │  entry_points discovery    │
     └────────────────────────────┘
```

## Data Package Structure

```
iff-parameters/
├── pyproject.toml                    # Package metadata + entry points
├── src/iff_parameters/
│   ├── __init__.py                   # get_data_dir(), list_available()
│   └── data/
│       ├── cvff_interface_v1_5/
│       │   ├── manifest.json         # SHA256 provenance
│       │   ├── tables/
│       │   │   ├── atom_types.csv    # Canonical CSV tables
│       │   │   ├── bonds.csv
│       │   │   ├── angles.csv
│       │   │   └── torsions.csv
│       │   └── raw/
│       │       └── source.frc        # Original .frc text
│       ├── pcff_interface_v1_5/
│       │   └── ...
│       └── charmm27_interface_v1_5/
│           ├── manifest.json
│           ├── tables/*.csv
│           └── raw/source.prm
└── tests/
    └── test_roundtrip.py
```

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "iff-parameters"
version = "1.5.0"
description = "INTERFACE Force Field parameters for UPM"
requires-python = ">=3.10"

[project.entry-points."upm.data_packages"]
iff = "iff_parameters:get_data_dir"

[tool.setuptools.package-data]
iff_parameters = ["data/**/*"]
```

## __init__.py

```python
from pathlib import Path
from importlib.resources import files

__version__ = "1.5.0"

def get_data_dir() -> Path:
    """Return path to the data directory (for UPM discovery)."""
    return Path(str(files("iff_parameters").joinpath("data")))

def list_available() -> list[tuple[str, str]]:
    """List available parameter sets as (name, version) tuples."""
    data_dir = get_data_dir()
    results = []
    for pkg_dir in sorted(data_dir.iterdir()):
        if pkg_dir.is_dir():
            manifest = pkg_dir / "manifest.json"
            if manifest.exists():
                import json
                with open(manifest) as f:
                    m = json.load(f)
                results.append((m["name"], m["version"]))
    return results
```

## Creating the Data Package

### Step 1: Import canonical .frc files

```bash
upm import-frc cvff_interface_v1_5.frc --name cvff_interface --version v1.5
upm import-frc pcff_interface_v1_5.frc --name pcff_interface --version v1.5
```

### Step 2: Import CHARMM .prm

```python
from upm.codecs.charmm_prm import read_prm
from upm.bundle.io import save_package

tables, raw = read_prm("charmm27_interface_v1_5.prm")
save_package(
    "data/charmm27_interface_v1_5",
    name="charmm27_interface", version="v1.5",
    tables=tables, source_text=open("charmm27_interface_v1_5.prm").read(),
    unknown_sections=raw,
)
```

### Step 3: Version and release

```bash
git tag v1.5.0
git push origin v1.5.0
pip install -e .  # Local development
# Or publish to PyPI: python -m build && twine upload dist/*
```

## Using with UPM

```python
from upm.registry import discover_packages, PackageIndex

# Automatically discovers installed iff-parameters
packages = discover_packages()
index = PackageIndex(packages)

# Search for Au parameters across all installed packages
results = index.search_atom_type("Au")
for r in results:
    print(f"{r.package_name}@{r.package_version}: lj_a={r.row['lj_a']}")
```

## Versioning

Use semantic versioning for parameter releases:
- **Major** (X.0.0): New fitting strategy or functional form change
- **Minor** (0.Y.0): New materials or refit of existing parameters
- **Patch** (0.0.Z): Bug fixes or corrections
