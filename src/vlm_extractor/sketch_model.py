"""The sketch model: one dict that describes a yard's grid.

It is the same shape the VLM already returns (see ``schema.py``):
``rows``, ``ncols_per_row``, ``max_cols``, ``row_gap_below``, ``cells``
plus notes/confidence. The new Site Builder keeps exactly ONE of these
per yard in session state. The VLM creates it, the correction loop
edits it, and ``to_form_vars`` hands it to the unchanged Compute step.

Everything here is pure Python (no Streamlit) so it can be unit-tested.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from .geometry import fmt_ft, label, layout, resolve_slants, row_heights
from .schema import normalize_extraction, validate_extraction


# ════════════════════════════════════════════════════════════════
#  Parsing helpers
# ════════════════════════════════════════════════════════════════

_FT_IN = re.compile(
    r"""^\s*
        (?:(?P<ft>\d+(?:\.\d+)?)\s*(?:'|ft|feet|foot)?)?\s*
        (?:(?P<inch>\d+(?:\.\d+)?)\s*(?:"|''|in|inch|inches))?\s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_length(value: Any) -> float:
    """Accept 10.5, "10.5", "10' 6\"", "10 ft 6 in", "6in" → decimal feet."""
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        raise ValueError("missing length")
    text = str(value).strip().replace("’", "'").replace("”", '"').replace("″", '"').replace("′", "'")
    try:
        return float(text)
    except ValueError:
        pass
    loose = re.fullmatch(r"(\d+(?:\.\d+)?)\s*'\s*(\d+(?:\.\d+)?)", text)   # 10'6
    if loose:
        return round(float(loose.group(1)) + float(loose.group(2)) / 12.0, 4)
    m = _FT_IN.match(text)
    if not m or (m.group("ft") is None and m.group("inch") is None):
        raise ValueError(f"can't read length '{value}'")
    ft = float(m.group("ft") or 0)
    inch = float(m.group("inch") or 0)
    return round(ft + inch / 12.0, 4)


def resolve_cell_id(ref: str) -> str:
    """'1A', 'A1', 'a1', ' 3f ' → internal row-first id 'A1' / 'F3'.

    Field workers write column-first ('3F'); the app stores row-first
    ('F3'). Both mean the same cell, so we accept either.
    """
    s = str(ref).strip().upper().replace(" ", "")
    m = re.fullmatch(r"([A-Z])(\d+)", s) or re.fullmatch(r"(\d+)([A-Z])", s)
    if not m:
        raise ValueError(f"'{ref}' is not a cell label like 2B or B2")
    a, b = m.group(1), m.group(2)
    row, col = (a, b) if a.isalpha() else (b, a)
    return f"{row}{int(col)}"


# ════════════════════════════════════════════════════════════════
#  Model bookkeeping
# ════════════════════════════════════════════════════════════════

def empty_model() -> dict[str, Any]:
    return {
        "rows": [], "ncols_per_row": {}, "max_cols": 1, "row_gap_below": {},
        "cells": {}, "global_notes": "", "overall_confidence": "high",
        "questions": [],
    }


def refresh_counts(model: dict[str, Any]) -> None:
    """Recompute ncols_per_row / max_cols / row order after edits.

    ncols_per_row is the HIGHEST column a row reaches (sparse extension
    rows count up to their rightmost cell), matching the prompt contract.
    Rows are kept in alphabetical order (A is always farthest from the
    house) and rows with no cells are kept — an empty row can still be
    a deliberate gap the user is about to fill.
    """
    cells = model.setdefault("cells", {})
    rows = set(model.get("rows") or [])
    rows.update(c["row"] for c in cells.values())
    model["rows"] = sorted(rows)
    ncols = {}
    for r in model["rows"]:
        cols = [int(c["col"]) for c in cells.values() if c["row"] == r]
        ncols[r] = max(cols) if cols else 1
    model["ncols_per_row"] = ncols
    model["max_cols"] = max(ncols.values()) if ncols else 1
    gaps = model.setdefault("row_gap_below", {})
    for r in list(gaps):
        if r not in model["rows"]:
            gaps.pop(r)
    for r in model["rows"]:
        gaps.setdefault(r, 0.0)


def prepare(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalise a fresh VLM extraction into a clean model.

    Returns (model, structural_problems). Also resolves written slant
    lengths into insets so the first preview is already correct.
    """
    # Which way round does THIS sketch write labels ("B1" or "1B")? The
    # SampleID pattern is built from the label, so cells the VLM left
    # unlabelled must follow the same style as the ones it did label.
    raw_cells = (raw or {}).get("cells") or {}
    given = [str(c.get("sketch_label") or "") for c in raw_cells.values()]
    row_first = sum(1 for g in given if re.fullmatch(r"[A-Z]\d+", g))
    col_first = sum(1 for g in given if re.fullmatch(r"\d+[A-Z]", g))
    unlabelled = {k for k, c in raw_cells.items() if not c.get("sketch_label")}
    model = normalize_extraction(copy.deepcopy(raw))
    if row_first > col_first:
        for k in unlabelled:
            c = model["cells"].get(k)
            if c and isinstance(c.get("col"), int):
                c["sketch_label"] = f"{c['row']}{c['col']}"
    model.setdefault("questions", [])
    ok, problems = validate_extraction(model)
    for cid, cell in model.get("cells", {}).items():
        for key in ("width", "height"):
            try:
                cell[key] = parse_length(cell.get(key))
            except ValueError:
                problems.append(f"{label(cid, cell)}: {key} '{cell.get(key)}' unreadable")
                cell[key] = 0.0
    refresh_counts(model)
    problems += resolve_slants(model)
    return model, problems


# ════════════════════════════════════════════════════════════════
#  Checks — what the user should look at before saving
# ════════════════════════════════════════════════════════════════

def check(model: dict[str, Any]) -> list[dict[str, str]]:
    """Return a list of ``{"level", "cell", "msg"}`` findings.

    level "error"  → Compute would produce something wrong; fix first.
    level "warn"   → probably a misread; worth a look.
    level "ask"    → the VLM asked a question / was unsure.
    """
    out: list[dict[str, str]] = []
    cells = model.get("cells") or {}
    rows = model.get("rows") or []

    def add(level: str, cid: str, msg: str) -> None:
        out.append({"level": level, "cell": cid, "msg": msg})

    if not cells:
        add("error", "", "No cells yet — upload a sketch or describe the grid.")
        return out

    for cid, c in sorted(cells.items()):
        name = label(cid, c)
        w, h = float(c.get("width", 0) or 0), float(c.get("height", 0) or 0)
        if w <= 0 or h <= 0:
            add("error", cid, f"{name} has no size yet ({fmt_ft(w)} × {fmt_ft(h)}).")
        kind = c.get("shape_kind", "rect")
        p = c.get("shape_params") or {}
        if kind == "angle":
            near, far = float(p.get("inset_near", 0) or 0), float(p.get("inset_far", 0) or 0)
            if near == 0 and far == 0:
                add("error", cid, f"{name} is marked as slanted but the slant has no "
                                  f"measurement. Tell me the diagonal length, e.g. "
                                  f"\"{name} left edge slants, diagonal 16 ft\".")
            span = w if p.get("side", "L") in ("L", "R") else h
            # inset == span is a triangle (fine — staircase diagonals);
            # more than that means the slant runs past the cell.
            if max(near, far) > span + 0.05 and span > 0:
                add("error", cid, f"{name}'s slant ({fmt_ft(max(near, far))}) is wider "
                                  f"than the cell itself ({fmt_ft(span)}).")
        if kind == "notch":
            if float(p.get("notch_w", 0) or 0) >= w or float(p.get("notch_h", 0) or 0) >= h:
                add("warn", cid, f"{name}'s cut-out is as big as the cell itself.")
        if c.get("confidence") == "low" and not c.get("_verified"):
            note = c.get("notes") or "the reading was unclear"
            add("ask", cid, f"{name}: {note}")

    # Outliers: a cell far bigger than a typical cell is usually a number
    # read off the wrong edge (e.g. a neighbour's label taken as this
    # cell's top width).
    import statistics
    for dim in ("width", "height"):
        vals = [float(c[dim]) for c in cells.values() if float(c.get(dim, 0) or 0) > 0]
        if len(vals) >= 4:
            med = statistics.median(vals)
            for cid, c in sorted(cells.items()):
                v = float(c.get(dim, 0) or 0)
                if v > 1.6 * med and v - med > 4:
                    add("warn", cid, f"{label(cid, c)} comes out {fmt_ft(v)} {('wide' if dim == 'width' else 'tall')}"
                                     f" — much bigger than a typical cell ({fmt_ft(med)}). "
                                     f"Probably a number read from the wrong edge.")

    # Cells in one row with different heights — Compute uses the first
    # cell's height for the whole row and pins the rest to the house side.
    rh = row_heights(model)
    for r in rows:
        hs = {cid: float(c["height"]) for cid, c in cells.items() if c["row"] == r}
        if hs and max(hs.values()) - min(hs.values()) > 0.05:
            tall = [label(k, cells[k]) for k, v in hs.items() if v > rh.get(r, 0) + 0.05]
            if tall:
                add("warn", "", f"Row {r}: {', '.join(tall)} is taller than the row "
                                f"({fmt_ft(rh[r])}) and will overlap the next row.")

    # Rows with the same number of full columns should usually be equally wide.
    lay = layout(model)
    totals: dict[str, float] = {}
    for r in rows:
        xs = [lay[cid]["x1"] for cid, c in cells.items() if c["row"] == r and cid in lay]
        dense = all(f"{r}{k}" in cells for k in range(1, (model["ncols_per_row"].get(r) or 1) + 1))
        if xs and dense:
            totals[r] = max(xs)
    by_n: dict[int, list[str]] = {}
    for r in totals:
        by_n.setdefault(model["ncols_per_row"][r], []).append(r)
    for n, rs in by_n.items():
        if len(rs) > 1:
            lo, hi = min(totals[r] for r in rs), max(totals[r] for r in rs)
            if hi - lo > 0.5:
                detail = ", ".join(f"{r}: {fmt_ft(totals[r])}" for r in rs)
                add("warn", "", f"Rows with {n} cells have different total widths "
                                f"({detail}). Fine if the yard really narrows; "
                                f"otherwise a width was misread.")

    # Medium-confidence cells: one grouped line instead of one per cell.
    unsure = [label(k, c) for k, c in sorted(cells.items())
              if c.get("confidence") == "medium" and not c.get("_verified")]
    if unsure:
        add("ask", "", f"Not fully sure about {', '.join(unsure)} — check them against the "
                       f"sketch, then correct them or say \"those look right\".")

    for q in model.get("questions") or []:
        add("ask", "", str(q))
    return out


# ════════════════════════════════════════════════════════════════
#  Hand-off to site_builder's Compute step
# ════════════════════════════════════════════════════════════════

def to_form_vars(model: dict[str, Any], yard_choice: str) -> dict[str, Any]:
    """Produce exactly the variables steps ⑥–⑦ used to build.

    Keys: rows, max_cols, ncols_per_row, row_gap_below, cell_data.
    Walkway cells keep their pattern (Compute drops it for walkways).
    """
    from .schema import to_cell_data

    m = copy.deepcopy(model)
    refresh_counts(m)
    resolve_slants(m)
    cell_data = to_cell_data(m, yard_choice)
    for cid, cd in cell_data.items():
        pattern = (m["cells"][cid].get("pattern") or "").strip()
        if pattern:
            cd["pattern"] = pattern
        # Compute only needs inset_near/inset_far; drop helper keys.
        if cd["shape_kind"] == "angle":
            sp = cd["shape_params"]
            cd["shape_params"] = {
                "side": sp.get("side", "L"),
                "inset_near": float(sp.get("inset_near", 0) or 0),
                "inset_far": float(sp.get("inset_far", 0) or 0),
            }
    return {
        "rows": list(m["rows"]),
        "max_cols": int(m["max_cols"]),
        "ncols_per_row": dict(m["ncols_per_row"]),
        "row_gap_below": {r: float(m["row_gap_below"].get(r, 0.0) or 0.0) for r in m["rows"]},
        "cell_data": cell_data,
    }
