"""JSON schema for VLM-extracted site sketches.

The VLM produces ONLY what a human would type into the existing
site_builder.py widgets (steps ⑥, ⑦, and per-cell Advanced). All
geo/anchor math stays in Python — the VLM never sees GPS, never
produces sw_x/ne_y, never knows which yard this is. Those come from
the manual entry fields kept on the Streamlit form.

Output contract (one yard per sketch):

{
  "rows": ["A", "B", "C", "D", "E", "F", "G"],
        # ordered far-from-house → near-house, as drawn on the sketch.

  "ncols_per_row": {"A": 4, "B": 4, "C": 4, "D": 4, "E": 1, "F": 2, "G": 2},
        # how many columns each row has. Captures L-shapes and partial
        # extensions. Cells beyond this count don't exist in this row.

  "row_gap_below": {"D": 0.5, ...},
        # decimal feet of walkway between a row and the row that
        # follows it. Default 0. Captures e.g. a footpath between D
        # and the extension rows E/F/G.

  "max_cols": 4,
        # widest row's column count. Drives the visual grid.

  "cells": {
    "1A": {
      "width":        10.0,           # decimal feet, perpendicular to strip
      "height":       10.0,           # decimal feet, along the strip
      "row":          "A",
      "col":          1,              # 1-indexed
      "gap_right":    0.0,            # walkway width to the right of this cell
      "is_walkway":   false,
      "shape_kind":   "rect",         # "rect" | "notch" | "angle" | "custom"
      "shape_params": {},
      "local_polygon": null,          # required only when shape_kind=="custom"
      "confidence":   "high",         # "high" | "medium" | "low"
      "notes":        ""              # short string, e.g. "shadow over right edge"
    },
    ...
  },

  "global_notes": "",                 # any free-text observation about the
                                      # sketch as a whole (e.g. "page edge
                                      # cropped, top-right dimension unclear")
  "overall_confidence": "high"
}

Shape kinds (must match site_builder.py contract exactly):

  - "rect":   default rectangle, no shape_params needed.
  - "notch":  L-shape (corner cut out). shape_params:
              {"corner": "TL"|"TR"|"BL"|"BR", "notch_w": float, "notch_h": float}
              Corners are in sketch space: T=far from house, L=lower col number.
  - "angle":  one slanted edge. shape_params:
              {"side": "L"|"R"|"T"|"B", "inset_near": float, "inset_far": float}
              L/R: inset_near=bottom end, inset_far=top end.
              T/B: inset_near=left end,  inset_far=right end.
              Insets push the corresponding edge endpoint INTO the cell.
  - "custom": arbitrary polygon. local_polygon is a list of [x,y] vertices
              in cell-local feet, origin at sketch bottom-left, x→right, y↑.
              Used for shapes that aren't a rectangle, a corner notch, or a
              single slanted edge — e.g. a cell with two angled sides.

Dimension conventions:

  - All numeric values are decimal feet (10' 6" → 10.5).
  - Cell origin is the cell's sketch BOTTOM-LEFT, with x going RIGHT
    and y going UP. "Bottom" is whichever edge is nearest the house in
    the sketch — but the VLM doesn't need to know which side is the
    house, it just preserves sketch-as-drawn.
  - Width is perpendicular to the strip, height is along it. For a
    typical vertical-strip yard, width=horizontal-on-sketch and
    height=vertical-on-sketch.
"""

from typing import Any, Optional
import re

# JSON Schema (draft-07 style) used to validate VLM output and also passed
# to the provider when structured-output mode is supported.
SITE_SKETCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["rows", "ncols_per_row", "max_cols", "cells"],
    "properties": {
        "rows": {
            "type": "array",
            "items": {"type": "string", "pattern": "^[A-Z]$"},
            "minItems": 1,
            "description": (
                "Row letters in sketch order, far-from-house first. "
                "Single uppercase letters: A, B, C, ..."
            ),
        },
        "ncols_per_row": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 1},
            "description": "Column count per row letter.",
        },
        "row_gap_below": {
            "type": "object",
            "additionalProperties": {"type": "number", "minimum": 0},
            "description": (
                "Walkway gap in feet between this row and the next. "
                "Omit or 0 if rows are flush."
            ),
        },
        "max_cols": {
            "type": "integer",
            "minimum": 1,
            "description": "Widest row's column count.",
        },
        "cells": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["width", "height", "row", "col"],
                "properties": {
                    "width":  {"type": "number", "minimum": 0},
                    "height": {"type": "number", "minimum": 0},
                    "row":    {"type": "string", "pattern": "^[A-Z]$"},
                    "col":    {"type": "integer", "minimum": 1},
                    "gap_right":  {"type": "number", "minimum": 0, "default": 0},
                    "is_walkway": {"type": "boolean", "default": False},
                    "shape_kind": {
                        "type": "string",
                        "enum": ["rect", "notch", "angle", "custom"],
                        "default": "rect",
                    },
                    "shape_params": {"type": "object", "default": {}},
                    "local_polygon": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "default": "high",
                    },
                    "notes": {"type": "string", "default": ""},
                },
            },
        },
        "global_notes": {"type": "string", "default": ""},
        "overall_confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "default": "high",
        },
    },
}


def validate_extraction(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Light structural validation. Returns (ok, list_of_problems).

    We don't use a full jsonschema validator here to keep the dependency
    footprint small — the checks below cover the contract violations
    that would actually break the downstream pipeline.
    """
    problems: list[str] = []

    # ── top-level required keys ──
    for key in ("rows", "ncols_per_row", "max_cols", "cells"):
        if key not in data:
            problems.append(f"missing top-level key: {key}")

    if problems:
        # No point checking nested structure if the skeleton is wrong.
        return False, problems

    rows = data.get("rows") or []
    if not isinstance(rows, list) or not rows:
        problems.append("`rows` must be a non-empty list")
    elif not all(isinstance(r, str) and len(r) == 1 and r.isalpha() and r.isupper()
                 for r in rows):
        problems.append("`rows` entries must each be a single uppercase letter")

    ncols = data.get("ncols_per_row") or {}
    if not isinstance(ncols, dict):
        problems.append("`ncols_per_row` must be a dict")
    else:
        for r in rows:
            if r not in ncols:
                problems.append(f"`ncols_per_row` missing row '{r}'")
            elif not isinstance(ncols[r], int) or ncols[r] < 1:
                problems.append(f"`ncols_per_row['{r}']` must be a positive int")

    max_cols = data.get("max_cols")
    if not isinstance(max_cols, int) or max_cols < 1:
        problems.append("`max_cols` must be a positive int")
    elif isinstance(ncols, dict) and ncols:
        if max_cols < max(ncols.values()):
            problems.append(
                f"`max_cols` ({max_cols}) is less than the widest row "
                f"({max(ncols.values())})"
            )

    cells = data.get("cells") or {}
    if not isinstance(cells, dict) or not cells:
        problems.append("`cells` must be a non-empty dict")
    else:
        # ── Per-cell ID sanity (format + row/col consistency) ──
        # We do NOT require cells to densely fill the rows×ncols box,
        # because L-shaped extensions legitimately have non-contiguous
        # columns (e.g. row F has only cells at columns 3 and 4, not
        # 1 and 2). The cell's own `col` and `row` are the source of
        # truth — we just verify they're consistent with each other
        # and with the row letters declared in `rows`.
        valid_rows = set(rows) if isinstance(rows, list) else set()
        for cid, cell in cells.items():
            if not isinstance(cell, dict):
                continue
            # ID format <col><row>, e.g. "3F"
            m = re.match(r"^(\d+)([A-Z])$", cid)
            if not m:
                problems.append(
                    f"cell key '{cid}' must match `<col><row>` "
                    f"(e.g. '1A', '3F') — letter MUST be uppercase"
                )
                continue
            id_col, id_row = int(m.group(1)), m.group(2)
            cell_col = cell.get("col")
            cell_row = cell.get("row")
            if cell_col != id_col:
                problems.append(
                    f"cell '{cid}': key says col={id_col} but "
                    f"`col` field says {cell_col}"
                )
            if cell_row != id_row:
                problems.append(
                    f"cell '{cid}': key says row='{id_row}' but "
                    f"`row` field says '{cell_row}'"
                )
            if valid_rows and id_row not in valid_rows:
                problems.append(
                    f"cell '{cid}': row '{id_row}' not in declared "
                    f"`rows` list {sorted(valid_rows)}"
                )
            max_col_for_row = ncols.get(id_row) if isinstance(ncols, dict) else None
            if isinstance(max_col_for_row, int) and id_col > max_col_for_row:
                problems.append(
                    f"cell '{cid}': col {id_col} exceeds "
                    f"ncols_per_row['{id_row}']={max_col_for_row}"
                )

        for cid, cell in cells.items():
            if not isinstance(cell, dict):
                problems.append(f"cell '{cid}' must be a dict")
                continue
            for key in ("width", "height", "row", "col"):
                if key not in cell:
                    problems.append(f"cell '{cid}' missing '{key}'")
            kind = cell.get("shape_kind", "rect")
            if kind not in ("rect", "notch", "angle", "custom"):
                problems.append(f"cell '{cid}' has unknown shape_kind '{kind}'")
            if kind == "custom":
                pts = cell.get("local_polygon")
                if not (isinstance(pts, list) and len(pts) >= 3
                        and all(isinstance(p, list) and len(p) == 2 for p in pts)):
                    problems.append(
                        f"cell '{cid}' shape_kind=custom but local_polygon "
                        f"is missing or malformed (need ≥3 [x,y] vertices)"
                    )

    return len(problems) == 0, problems


def normalize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Fill in defaults so the rest of the pipeline can assume completeness.

    Mutates a copy of ``data`` to ensure every cell has the keys
    ``cell_data`` consumers downstream rely on, and every row has a
    ``row_gap_below`` entry.
    """
    out = dict(data)
    out.setdefault("row_gap_below", {})
    out.setdefault("global_notes", "")
    out.setdefault("overall_confidence", "medium")

    rows = out.get("rows", [])
    for r in rows:
        out["row_gap_below"].setdefault(r, 0.0)

    cells_out: dict[str, dict[str, Any]] = {}
    for cid, cell in (out.get("cells") or {}).items():
        c = dict(cell)
        c.setdefault("gap_right", 0.0)
        c.setdefault("is_walkway", False)
        c.setdefault("shape_kind", "rect")
        c.setdefault("shape_params", {})
        c.setdefault("local_polygon", None)
        c.setdefault("confidence", "medium")
        c.setdefault("notes", "")
        cells_out[cid] = c
    out["cells"] = cells_out
    return out


def to_cell_data(extraction: dict[str, Any], yard_choice: str) -> dict[str, dict[str, Any]]:
    """Convert a validated extraction into the ``cell_data`` dict that
    site_builder.py's existing Compute path consumes.

    ``yard_choice`` is "Front" or "Back" — used only to seed the default
    SampleID ``pattern`` so the VLM doesn't have to guess.
    """
    cell_data: dict[str, dict[str, Any]] = {}
    for cid, cell in (extraction.get("cells") or {}).items():
        default_pat = f"{yard_choice}_{cid}_"
        cell_data[cid] = {
            "width":         float(cell["width"]),
            "height":        float(cell["height"]),
            "col":           int(cell["col"]),
            "row":           str(cell["row"]),
            "pattern":       default_pat,
            "gap_right":     float(cell.get("gap_right", 0.0) or 0.0),
            "is_walkway":    bool(cell.get("is_walkway", False)),
            "shape_kind":    cell.get("shape_kind", "rect"),
            "shape_params":  cell.get("shape_params", {}) or {},
            "local_polygon": cell.get("local_polygon"),
        }
    return cell_data