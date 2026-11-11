"""Pure-Python geometry for the sketch model.

Why this module exists
----------------------
The VLM is good at *reading* a sketch (labels, numbers, which edge is
slanted) and bad at *computing* coordinates. So the model only reports
what is written on the page, and everything numeric is derived here.

Two jobs:

1. ``resolve_slants`` — turn a written diagonal length (e.g. the 16' on a
   slanted edge) into the ``inset_near`` / ``inset_far`` values that
   site_builder's Compute step expects. Pythagoras, not the model.
2. ``layout`` — place every cell in sketch space (x → right, y ↑ away
   from the house) using the SAME rules as site_builder's Compute step
   (row heights from the row's first cell, row gaps, sparse extension
   rows right-aligned under the main-grid column). The preview drawn
   from this layout therefore matches what Compute will save.

The polygon helpers are copied verbatim from site_builder.py (which is a
Streamlit script and can't be imported without running the UI). If you
change the shape maths in one place, change it in both; the test
``test_geometry.py::test_polygons_match_site_builder`` guards this.
"""

from __future__ import annotations

import math
from typing import Any


# ════════════════════════════════════════════════════════════════
#  Shape templates (cell-local feet, origin = sketch bottom-left)
#  Kept identical to site_builder.py.
# ════════════════════════════════════════════════════════════════

def rect_local_polygon(cell_w: float, cell_h: float):
    return [[0.0, 0.0], [cell_w, 0.0], [cell_w, cell_h], [0.0, cell_h]]


def notch_local_polygon(cell_w, cell_h, corner, notch_w, notch_h):
    w = max(0.0, float(cell_w))
    h = max(0.0, float(cell_h))
    nw = max(0.0, min(float(notch_w), w))
    nh = max(0.0, min(float(notch_h), h))
    if nw == 0 or nh == 0:
        return rect_local_polygon(w, h)
    if corner == "BL":
        return [[nw, 0.0], [w, 0.0], [w, h], [0.0, h], [0.0, nh], [nw, nh]]
    if corner == "BR":
        return [[0.0, 0.0], [w - nw, 0.0], [w - nw, nh], [w, nh], [w, h], [0.0, h]]
    if corner == "TL":
        return [[0.0, 0.0], [w, 0.0], [w, h], [nw, h], [nw, h - nh], [0.0, h - nh]]
    if corner == "TR":
        return [[0.0, 0.0], [w, 0.0], [w, h - nh], [w - nw, h - nh], [w - nw, h], [0.0, h]]
    return rect_local_polygon(w, h)


def angled_local_polygon(cell_w, cell_h, side, inset_near, inset_far):
    w = max(0.0, float(cell_w))
    h = max(0.0, float(cell_h))
    if side in ("L", "R"):
        a = max(0.0, min(float(inset_near), w))
        b = max(0.0, min(float(inset_far), w))
    else:
        a = max(0.0, min(float(inset_near), h))
        b = max(0.0, min(float(inset_far), h))
    if side == "L":
        return [[a, 0.0], [w, 0.0], [w, h], [b, h]]
    if side == "R":
        return [[0.0, 0.0], [w - a, 0.0], [w - b, h], [0.0, h]]
    if side == "B":
        return [[0.0, a], [w, b], [w, h], [0.0, h]]
    if side == "T":
        return [[0.0, 0.0], [w, 0.0], [w, h - b], [0.0, h - a]]
    return rect_local_polygon(w, h)


def local_polygon_for_cell(cd: dict) -> list[list[float]]:
    w, h = float(cd.get("width", 0)), float(cd.get("height", 0))
    kind = cd.get("shape_kind", "rect")
    p = cd.get("shape_params", {}) or {}
    if kind == "notch":
        return notch_local_polygon(w, h, p.get("corner", "TL"),
                                   p.get("notch_w", 0), p.get("notch_h", 0))
    if kind == "angle":
        return angled_local_polygon(w, h, p.get("side", "L"),
                                    p.get("inset_near", 0), p.get("inset_far", 0))
    if kind == "custom":
        pts = cd.get("local_polygon")
        if pts and len(pts) >= 3:
            return [list(map(float, q)) for q in pts]
    return rect_local_polygon(w, h)


# ════════════════════════════════════════════════════════════════
#  Slant resolution: written diagonal length → insets
# ════════════════════════════════════════════════════════════════

def slant_edge_span(cell: dict) -> float:
    """Length of the straight edge the slant replaces.

    A slanted LEFT/RIGHT edge spans the cell's height; a slanted
    TOP/BOTTOM edge spans its width.
    """
    side = (cell.get("shape_params") or {}).get("side", "L")
    return float(cell.get("height" if side in ("L", "R") else "width", 0) or 0)


def resolve_slants(model: dict[str, Any]) -> list[str]:
    """Fill ``inset_near``/``inset_far`` for angled cells from ``slant_len``.

    ``shape_params`` for an angled cell may carry:
      • ``slant_len``  — the diagonal length written on the sketch (ft)
      • ``slant_end``  — which end of the edge is pushed in: "near"
        (bottom for L/R, left for T/B) or "far" (top for L/R, right for
        T/B). Defaults to "far".

    Python computes ``offset = sqrt(slant_len² − span²)`` and writes it
    to the chosen end (the other end stays 0). Mutates ``model`` in place
    and returns human-readable problems (e.g. a diagonal shorter than
    the edge it replaces, which is physically impossible).
    """
    problems: list[str] = []
    for cid, cell in (model.get("cells") or {}).items():
        if cell.get("shape_kind") != "angle":
            continue
        p = cell.setdefault("shape_params", {})
        side = p.get("side", "L")
        end = "near" if p.get("slant_end") == "near" else "far"
        # The cell's size ACROSS the slant (width for L/R, height for T/B)
        # at each end of the slanted edge, when written on the sketch.
        # e.g. a staircase cell with "4'" written along its top edge has
        # top_width=4; a pointed (triangle) cell has top_width=0.
        if side in ("L", "R"):
            at = {"near": p.get("bottom_width"), "far": p.get("top_width")}
            size_key = "width"
        else:
            at = {"near": p.get("left_height"), "far": p.get("right_height")}
            size_key = "height"
        try:
            at = {k: (None if v in (None, "") else float(v)) for k, v in at.items()}
            slant = p.get("slant_len")
            slant = None if slant in (None, "", 0) else float(slant)
        except (TypeError, ValueError):
            problems.append(f"{label(cid, cell)}: a slant measurement is not a number")
            continue
        pushed, full = at[end], at["far" if end == "near" else "near"]

        if pushed is not None and full is not None:
            # Both ends written: the slant follows from them.
            offset = max(0.0, full - pushed)
            if slant is not None:
                implied = math.hypot(offset, slant_edge_span(cell))
                if abs(implied - slant) > 1.0:
                    problems.append(
                        f"{label(cid, cell)}: the written ends ({fmt_ft(pushed)} and "
                        f"{fmt_ft(full)}) and the diagonal ({fmt_ft(slant)}) don't agree "
                        f"(they imply a {fmt_ft(implied)} diagonal) — one is misread."
                    )
            cell[size_key] = full
        elif slant is not None:
            span = slant_edge_span(cell)
            if slant + 1e-6 < span:
                problems.append(
                    f"{label(cid, cell)}: slanted edge {fmt_ft(slant)} is shorter than "
                    f"the straight edge it replaces ({fmt_ft(span)}) — one of the two "
                    f"numbers is misread."
                )
                continue
            offset = math.sqrt(max(0.0, slant * slant - span * span))
            if pushed is not None:
                cell[size_key] = round(pushed + offset, 3)   # wide end = short end + run
            elif full is not None:
                cell[size_key] = full
        else:
            continue
        offset = round(offset, 3)
        p["inset_near"] = offset if end == "near" else 0.0
        p["inset_far"] = offset if end == "far" else 0.0
    return problems


# ════════════════════════════════════════════════════════════════
#  Layout — mirrors site_builder.py's Compute step
# ════════════════════════════════════════════════════════════════

def row_heights(model: dict[str, Any]) -> dict[str, float]:
    """Row height = height of the row's col-1 cell, else its first cell."""
    cells = model.get("cells") or {}
    out: dict[str, float] = {}
    for row in model.get("rows") or []:
        c1 = cells.get(f"{row}1")
        if c1 is not None:
            out[row] = float(c1["height"])
            continue
        for _cid, cd in sorted(cells.items(), key=lambda kv: kv[1].get("col", 0)):
            if cd.get("row") == row:
                out[row] = float(cd["height"])
                break
    return out


def layout(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Place every cell in sketch space.

    Returns ``{cell_id: {"x0", "x1", "y0", "y1", "polygon"}}`` in feet,
    where x grows to the right (higher column) and y grows UP the page
    (away from the house). Row A therefore has the largest y.
    """
    rows = list(model.get("rows") or [])
    cells = model.get("cells") or {}
    gaps = model.get("row_gap_below") or {}
    rh = row_heights(model)

    strip_pos: dict[str, float] = {}
    pos = 0.0
    for row in rows:
        strip_pos[row] = pos
        pos += rh.get(row, 10.0) + float(gaps.get(row, 0.0) or 0.0)

    widths: dict[str, dict[int, float]] = {r: {} for r in rows}
    gapr: dict[str, dict[int, float]] = {r: {} for r in rows}
    for cd in cells.values():
        r = cd.get("row")
        if r in widths:
            widths[r][int(cd["col"])] = float(cd["width"])
            gapr[r][int(cd["col"])] = float(cd.get("gap_right", 0.0) or 0.0)

    def main_right_edge(col: int):
        for r in rows:
            w = widths.get(r, {})
            if all(c in w for c in range(1, col + 1)):
                total = 0.0
                for c in range(1, col + 1):
                    total += w[c]
                    if c < col:
                        total += gapr[r].get(c, 0.0)
                return total
        return None

    def perp_start(row: str, col: int) -> float:
        w = widths.get(row, {})
        if all(c in w for c in range(1, col)):
            return sum(w[c] + gapr[row].get(c, 0.0) for c in range(1, col))
        edge = main_right_edge(col)
        if edge is not None:
            return edge - w.get(col, 0.0)
        return sum(w.get(c, 0.0) + gapr[row].get(c, 0.0) for c in range(1, col))

    out: dict[str, dict[str, Any]] = {}
    for cid, cd in cells.items():
        row, col = cd.get("row"), int(cd.get("col", 1))
        if row not in strip_pos:
            continue
        strip_end = strip_pos[row] + rh.get(row, float(cd["height"]))
        x0 = perp_start(row, col)
        y_near = -strip_end                     # near-house edge, sketch y
        poly = [[x0 + lx, y_near + ly] for lx, ly in local_polygon_for_cell(cd)]
        out[cid] = {
            "x0": x0, "x1": x0 + float(cd["width"]),
            "y0": y_near, "y1": y_near + float(cd["height"]),
            "polygon": poly,
        }
    return out


# ════════════════════════════════════════════════════════════════
#  Small formatting helpers shared by checks + UI
# ════════════════════════════════════════════════════════════════

def fmt_ft(decimal_ft: float) -> str:
    """10.5 → 10' 6\" ; 12.0 → 12'."""
    try:
        v = float(decimal_ft)
    except (TypeError, ValueError):
        return str(decimal_ft)
    neg = v < 0
    v = abs(v)
    ft = int(v)
    inches = round((v - ft) * 12)
    if inches == 12:
        ft, inches = ft + 1, 0
    s = f"{ft}'" + (f" {inches}\"" if inches else "")
    return f"-{s}" if neg else s


def label(cid: str, cell: dict | None = None) -> str:
    """User-facing name: the label written on the sketch (e.g. '3F')."""
    if cell and cell.get("sketch_label"):
        return str(cell["sketch_label"])
    return cid
