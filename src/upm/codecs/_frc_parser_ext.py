"""Extended section parsers for MSI `.frc` codec (v2.0).

Parsers for torsion_1, out_of_plane, and equivalence sections,
split from _frc_parser.py to keep files under 500 LOC.

Private module; imported by _frc_parser.py.
"""
from __future__ import annotations

from typing import Any

from upm.codecs._frc_parser import _is_ignorable_line, _strip_inline_comment


def _parse_torsion_1(lines: list[str], *, source_default: str | None) -> list[dict[str, Any]]:
    """Parse `#torsion_1` section rows.

    Format: ver ref t1 t2 t3 t4 kphi n phi0
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue

        toks = line.split()
        if len(toks) < 7:
            continue  # skip incomplete lines

        # Find the last three adjacent numeric tokens: kphi, n, phi0
        kphi_i: int | None = None
        for i in range(len(toks) - 3, -1, -1):
            try:
                float(toks[i])      # kphi
                int(float(toks[i + 1]))  # n (integer)
                float(toks[i + 2])  # phi0
            except Exception:
                continue
            kphi_i = i
            break

        if kphi_i is None or kphi_i < 4:
            continue  # can't extract 4 type tokens before kphi

        t1 = toks[kphi_i - 4]
        t2 = toks[kphi_i - 3]
        t3 = toks[kphi_i - 2]
        t4 = toks[kphi_i - 1]
        kphi = float(toks[kphi_i])
        n = int(float(toks[kphi_i + 1]))
        phi0 = float(toks[kphi_i + 2])

        source = source_default
        if source is None:
            tail = " ".join(toks[kphi_i + 3:]).strip()
            source = tail if tail else None

        rows.append({
            "t1": t1, "t2": t2, "t3": t3, "t4": t4,
            "style": "torsion_1",
            "kphi": kphi, "n": n, "phi0": phi0,
            "source": source,
        })

    return rows


def _parse_out_of_plane(lines: list[str], *, source_default: str | None) -> list[dict[str, Any]]:
    """Parse `#out_of_plane` section rows.

    Format: ver ref t1 t2 t3 t4 kchi n chi0
    Same structure as torsion_1.
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue

        toks = line.split()
        if len(toks) < 7:
            continue

        kchi_i: int | None = None
        for i in range(len(toks) - 3, -1, -1):
            try:
                float(toks[i])
                int(float(toks[i + 1]))
                float(toks[i + 2])
            except Exception:
                continue
            kchi_i = i
            break

        if kchi_i is None or kchi_i < 4:
            continue

        t1 = toks[kchi_i - 4]
        t2 = toks[kchi_i - 3]
        t3 = toks[kchi_i - 2]
        t4 = toks[kchi_i - 1]
        kchi = float(toks[kchi_i])
        n = int(float(toks[kchi_i + 1]))
        chi0 = float(toks[kchi_i + 2])

        source = source_default
        if source is None:
            tail = " ".join(toks[kchi_i + 3:]).strip()
            source = tail if tail else None

        rows.append({
            "t1": t1, "t2": t2, "t3": t3, "t4": t4,
            "style": "out_of_plane",
            "kchi": kchi, "n": n, "chi0": chi0,
            "source": source,
        })

    return rows


def _parse_equivalence(lines: list[str]) -> list[dict[str, Any]]:
    """Parse `#equivalence` section rows.

    Format: ver ref atom_type nonb bond angle torsion oop
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue

        toks = line.split()
        if len(toks) < 7:
            continue

        # Try asset-style: ver ref type nonb bond angle torsion oop
        try:
            float(toks[0])
            int(float(toks[1]))
        except Exception:
            # Minimal: type nonb bond angle torsion oop
            if len(toks) >= 6:
                rows.append({
                    "atom_type": toks[0],
                    "nonb": toks[1], "bond": toks[2],
                    "angle": toks[3], "torsion": toks[4], "oop": toks[5],
                })
            continue

        if len(toks) >= 8:
            rows.append({
                "atom_type": toks[2],
                "nonb": toks[3], "bond": toks[4],
                "angle": toks[5], "torsion": toks[6], "oop": toks[7],
            })

    return rows
