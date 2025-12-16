"""Requirements JSON I/O (v0.1 / v0.1.1).

This module provides:
- v0.1 Requirements JSON reader (`read_requirements_json`)
- v0.1 Requirements JSON writer (`write_requirements_json`)
- v0.1.1 toy structure JSON -> Requirements derivation (`requirements_from_structure_json`)

Dev guide Requirements schema example:
{
  "atom_types": ["c3", "o", "h"],
  "bond_types": [["c3","o"], ["c3","h"]],
  "angle_types": [],
  "dihedral_types": []
}

Toy structure schema (UPM-only standalone helper; no USM dependency):
{
  "atoms": [{"aid": 0, "atom_type": "c3"}, ...],
  "bonds": [{"a1": 0, "a2": 1}, ...]   # optional
}

Rules:
- Requirements canonicalization happens via `upm.core.model.Requirements`.
- Writer is stable: UTF-8, `indent=2`, `sort_keys=True`, newline-terminated.
- Toy structure derivation is deterministic and aligns with v0.1.1 DevGuide:
  - bond_types keys canonicalized so t1 <= t2
  - angle_types keys canonicalized so endpoints satisfy t1 <= t3
  - derived angles are enumerated deterministically from the bond adjacency graph
  - dihedral_types is always empty for v0.1.1
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upm.core.model import Requirements, canonicalize_angle_key, canonicalize_bond_key


_MISSING = object()


def _require_dict(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected JSON object, got {type(value).__name__}")
    return value


def _require_list(value: Any, *, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{where}: expected JSON array, got {type(value).__name__}")
    return value


def _require_int(value: Any, *, where: str) -> int:
    if value is None:
        raise ValueError(f"{where}: expected int, got null")
    try:
        # Explicitly reject booleans (Python bool is a subclass of int).
        if isinstance(value, bool):
            raise TypeError("bool is not an int")
        return int(value)
    except Exception as e:
        raise ValueError(f"{where}: expected int, got {type(value).__name__}") from e


def _norm_str(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where}: expected str, got {type(value).__name__}")
    s = value.strip()
    if not s:
        raise ValueError(f"{where}: must be a non-empty string")
    return s


def _get_array(data: dict[str, Any], key: str) -> Any:
    """Return array value for key; default [] if key missing; error if explicitly null."""
    v = data.get(key, _MISSING)
    if v is _MISSING:
        return []
    if v is None:
        raise ValueError(f"{key}: must be an array; got null")
    return v


def read_requirements_json(path: str | Path) -> Requirements:
    """Read v0.1 Requirements JSON and return canonical `Requirements`.

    Hard errors:
    - top-level must be a JSON object
    - if a field is present, it must be an array (null is rejected)
    - tuple entries must be correct length and strings (enforced by Requirements)
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    obj = _require_dict(data, where="requirements.json")

    atom_types = _get_array(obj, "atom_types")
    bond_types = _get_array(obj, "bond_types")
    angle_types = _get_array(obj, "angle_types")
    dihedral_types = _get_array(obj, "dihedral_types")

    # Canonicalization + validation occurs in Requirements.__post_init__.
    return Requirements(
        atom_types=atom_types,
        bond_types=bond_types,
        angle_types=angle_types,
        dihedral_types=dihedral_types,
    )


def requirements_to_json_dict(req: Requirements) -> dict[str, Any]:
    """Convert canonical `Requirements` to a JSON-ready dict (lists, not tuples)."""
    return {
        "atom_types": list(req.atom_types),
        "bond_types": [list(x) for x in req.bond_types],
        "angle_types": [list(x) for x in req.angle_types],
        "dihedral_types": [list(x) for x in req.dihedral_types],
    }


def write_requirements_json(req: Requirements, path: str | Path) -> None:
    """Write canonical Requirements JSON (v0.1 schema) deterministically."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(requirements_to_json_dict(req), indent=2, sort_keys=True)
    if not text.endswith("\n"):
        text += "\n"
    p.write_text(text, encoding="utf-8")


def _extract_atom_types_by_aid(structure_obj: dict[str, Any]) -> list[str]:
    atoms_raw = structure_obj.get("atoms", _MISSING)
    if atoms_raw is _MISSING:
        raise ValueError("structure.json: missing required key 'atoms'")
    if atoms_raw is None:
        raise ValueError("structure.json.atoms: must be an array; got null")

    atoms = _require_list(atoms_raw, where="structure.json.atoms")
    n = len(atoms)
    by_aid: list[str | None] = [None] * n

    seen: set[int] = set()
    for i, atom in enumerate(atoms):
        aobj = _require_dict(atom, where=f"structure.json.atoms[{i}]")
        aid = _require_int(aobj.get("aid", None), where=f"structure.json.atoms[{i}].aid")
        if aid < 0 or aid >= n:
            raise ValueError(f"structure.json.atoms[{i}].aid: out of range: {aid} (n_atoms={n})")
        if aid in seen:
            raise ValueError(f"structure.json.atoms[{i}].aid: duplicate aid {aid}")
        seen.add(aid)

        at = _norm_str(aobj.get("atom_type", None), where=f"structure.json.atoms[{i}].atom_type")
        by_aid[aid] = at

    if any(v is None for v in by_aid):
        raise ValueError("structure.json.atoms: aid mapping must cover a contiguous 0..n-1 range")

    return [v for v in by_aid if v is not None]


def _normalized_unique_bond_pairs(structure_obj: dict[str, Any], *, n_atoms: int) -> list[tuple[int, int]]:
    bonds_raw = structure_obj.get("bonds", _MISSING)
    if bonds_raw is _MISSING:
        return []
    if bonds_raw is None:
        raise ValueError("structure.json.bonds: must be an array; got null")

    bonds = _require_list(bonds_raw, where="structure.json.bonds")
    if not bonds:
        return []

    pairs: set[tuple[int, int]] = set()
    for i, bond in enumerate(bonds):
        bobj = _require_dict(bond, where=f"structure.json.bonds[{i}]")
        a1 = _require_int(bobj.get("a1", None), where=f"structure.json.bonds[{i}].a1")
        a2 = _require_int(bobj.get("a2", None), where=f"structure.json.bonds[{i}].a2")

        if a1 < 0 or a1 >= n_atoms or a2 < 0 or a2 >= n_atoms:
            raise ValueError(
                f"structure.json.bonds[{i}]: a1/a2 out of range: ({a1},{a2}) (n_atoms={n_atoms})"
            )
        if a1 == a2:
            raise ValueError(f"structure.json.bonds[{i}]: self-bond not allowed (aid={a1})")

        a, b = (a1, a2) if a1 <= a2 else (a2, a1)
        pairs.add((a, b))

    return sorted(pairs)


def requirements_from_structure_json(path: str | Path) -> Requirements:
    """Derive canonical v0.1 Requirements from a toy `structure.json` (v0.1.1).

    Determinism:
    - bond pairs are canonicalized as undirected unique edges, then sorted
    - neighbors are deduped, then sorted before enumerating angle pairs
    - derived (bond_types, angle_types) are deduped as sets, then sorted
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    obj = _require_dict(data, where="structure.json")

    atom_types_by_aid = _extract_atom_types_by_aid(obj)
    n_atoms = len(atom_types_by_aid)

    bond_pairs = _normalized_unique_bond_pairs(obj, n_atoms=n_atoms)

    # Build bond types + adjacency.
    bond_types_set: set[tuple[str, str]] = set()
    neighbors: list[list[int]] = [[] for _ in range(n_atoms)]
    for a1, a2 in bond_pairs:
        t1 = atom_types_by_aid[a1]
        t2 = atom_types_by_aid[a2]
        bond_types_set.add(canonicalize_bond_key(t1, t2))
        neighbors[a1].append(a2)
        neighbors[a2].append(a1)

    angle_types_set: set[tuple[str, str, str]] = set()
    for j in range(n_atoms):
        nbrs = sorted(set(neighbors[j]))
        if len(nbrs) < 2:
            continue
        tj = atom_types_by_aid[j]
        for p_i in range(len(nbrs) - 1):
            i = nbrs[p_i]
            ti = atom_types_by_aid[i]
            for p_k in range(p_i + 1, len(nbrs)):
                k = nbrs[p_k]
                tk = atom_types_by_aid[k]
                angle_types_set.add(canonicalize_angle_key(ti, tj, tk))

    # Use Requirements to validate/canonicalize atom_types and the derived type keys.
    return Requirements(
        atom_types=sorted(set(atom_types_by_aid)),
        bond_types=[list(x) for x in sorted(bond_types_set)],
        angle_types=[list(x) for x in sorted(angle_types_set)],
        dihedral_types=[],
    )


__all__ = [
    "read_requirements_json",
    "requirements_from_structure_json",
    "requirements_to_json_dict",
    "write_requirements_json",
]