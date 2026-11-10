"""Small, explicit edits to the sketch model.

The correction loop never lets the LLM rewrite the whole map. It asks
the LLM to translate "B2–B3 has a 4 ft walkway" into one or more of the
operations below; Python applies them, re-checks, and re-draws. That
keeps every change visible, reversible (undo), and impossible to
"silently drift" on cells the user didn't mention.

Every operation is a dict with an ``"op"`` key. Lengths may be numbers
(decimal feet) or strings like ``"10' 6\\""``. Cell references may be
written either way round (``"2B"`` or ``"B2"``).

Supported ops
-------------
set_cell        cell, [width], [height], [is_walkway], [gap_right], [sketch_label], [pattern]
set_shape       cell, shape_kind = rect | angle | notch | custom
                  angle : side L|R|T|B, and either slant_len (+ slant_end near|far)
                          or inset_near / inset_far
                  notch : corner TL|TR|BL|BR, notch_w, notch_h
                  custom: polygon [[x,y], ...] (cell-local ft, origin bottom-left)
set_row_height  row, height           (every cell in the row)
set_col_width   col, width, [rows]    (every cell in that column, or only `rows`)
set_row_gap     row, gap              (walkway between `row` and the next row)
walkway_between a, b, width           (two neighbouring cells → gap_right or row gap)
add_cell        cell, width, height, [shape fields as set_shape]
remove_cell     cell
add_row         row, ncols, width, height   (new full row of equal cells)
remove_row      row
"""

from __future__ import annotations

import copy
from typing import Any

from .geometry import label, resolve_slants
from .sketch_model import parse_length, refresh_counts, resolve_cell_id


class EditError(ValueError):
    """An operation that can't be applied (unknown cell, bad value…)."""


def _cell(model: dict, ref: Any) -> tuple[str, dict]:
    try:
        cid = resolve_cell_id(ref)
    except ValueError as exc:
        raise EditError(str(exc)) from exc
    cells = model.get("cells") or {}
    if cid not in cells:
        # Fall back to matching the written sketch label (extension cells).
        for k, c in cells.items():
            if str(c.get("sketch_label", "")).upper() == str(ref).strip().upper():
                return k, c
        raise EditError(f"There's no cell {ref} on this map.")
    return cid, cells[cid]


def _len(value: Any, what: str) -> float:
    try:
        v = parse_length(value)
    except ValueError as exc:
        raise EditError(f"{what}: {exc}") from exc
    if v < 0:
        raise EditError(f"{what} can't be negative")
    return v


def _touch(cell: dict) -> None:
    """A cell the user has spoken about counts as human-verified."""
    cell["confidence"] = "high"
    cell["_verified"] = True


def _apply_shape(cell: dict, op: dict) -> None:
    kind = op.get("shape_kind", "rect")
    if kind == "rect":
        cell["shape_kind"], cell["shape_params"], cell["local_polygon"] = "rect", {}, None
    elif kind == "angle":
        side = str(op.get("side", "L")).upper()[:1]
        if side not in "LRTB":
            raise EditError(f"side must be L, R, T or B (got {op.get('side')})")
        params: dict[str, Any] = {"side": side}
        if op.get("slant_len") not in (None, ""):
            params["slant_len"] = _len(op["slant_len"], "slant length")
            end = str(op.get("slant_end", "far")).lower()
            params["slant_end"] = "near" if end.startswith("n") else "far"
        else:
            params["inset_near"] = _len(op.get("inset_near", 0), "inset_near")
            params["inset_far"] = _len(op.get("inset_far", 0), "inset_far")
        cell["shape_kind"], cell["shape_params"], cell["local_polygon"] = "angle", params, None
    elif kind == "notch":
        corner = str(op.get("corner", "TL")).upper()
        if corner not in ("TL", "TR", "BL", "BR"):
            raise EditError(f"corner must be TL, TR, BL or BR (got {op.get('corner')})")
        cell["shape_kind"] = "notch"
        cell["shape_params"] = {
            "corner": corner,
            "notch_w": _len(op.get("notch_w", 0), "notch width"),
            "notch_h": _len(op.get("notch_h", 0), "notch height"),
        }
        cell["local_polygon"] = None
    elif kind == "custom":
        pts = op.get("polygon") or op.get("local_polygon")
        if not (isinstance(pts, list) and len(pts) >= 3):
            raise EditError("custom shape needs a polygon with at least 3 points")
        cell["shape_kind"], cell["shape_params"] = "custom", {}
        cell["local_polygon"] = [[float(x), float(y)] for x, y in pts]
    else:
        raise EditError(f"unknown shape '{kind}'")


def _new_cell(cid: str, width: float, height: float) -> dict:
    row, col = cid[0], int(cid[1:])
    return {
        "row": row, "col": col, "width": width, "height": height,
        "gap_right": 0.0, "is_walkway": False, "shape_kind": "rect",
        "shape_params": {}, "local_polygon": None, "confidence": "high",
        "notes": "", "sketch_label": f"{col}{row}", "_verified": True,
    }


def apply_op(model: dict, op: dict) -> str:
    """Apply ONE operation in place. Returns a short description."""
    kind = op.get("op")
    cells = model.setdefault("cells", {})

    if kind == "set_cell":
        cid, c = _cell(model, op.get("cell"))
        changed = []
        for key in ("width", "height", "gap_right"):
            if op.get(key) is not None:
                c[key] = _len(op[key], key)
                changed.append(key.replace("_", " "))
        if op.get("is_walkway") is not None:
            c["is_walkway"] = bool(op["is_walkway"])
            changed.append("walkway" if c["is_walkway"] else "not a walkway")
        for key in ("sketch_label", "pattern"):
            if op.get(key):
                c[key] = str(op[key]).strip()
                changed.append(key.replace("_", " "))
        _touch(c)
        return f"{label(cid, c)}: updated {', '.join(changed) or 'nothing'}"

    if kind == "set_shape":
        cid, c = _cell(model, op.get("cell"))
        _apply_shape(c, op)
        _touch(c)
        return f"{label(cid, c)}: shape → {c['shape_kind']}"

    if kind == "set_row_height":
        row = str(op.get("row", "")).upper()
        h = _len(op.get("height"), "height")
        hit = [c for c in cells.values() if c["row"] == row]
        if not hit:
            raise EditError(f"There's no row {row}.")
        for c in hit:
            c["height"] = h
            _touch(c)
        return f"Row {row}: height for {len(hit)} cells"

    if kind == "set_col_width":
        col = int(op.get("col"))
        w = _len(op.get("width"), "width")
        only = {str(r).upper() for r in (op.get("rows") or [])}
        hit = [c for c in cells.values() if int(c["col"]) == col and (not only or c["row"] in only)]
        if not hit:
            raise EditError(f"There's no column {col}.")
        for c in hit:
            c["width"] = w
            _touch(c)
        return f"Column {col}: width for {len(hit)} cells"

    if kind == "set_row_gap":
        row = str(op.get("row", "")).upper()
        if row not in (model.get("rows") or []):
            raise EditError(f"There's no row {row}.")
        model.setdefault("row_gap_below", {})[row] = _len(op.get("gap", 0), "gap")
        return f"Walkway below row {row}"

    if kind == "walkway_between":
        a_id, a = _cell(model, op.get("a"))
        b_id, b = _cell(model, op.get("b"))
        w = _len(op.get("width"), "walkway width")
        if a["row"] == b["row"] and abs(a["col"] - b["col"]) == 1:
            left = a if a["col"] < b["col"] else b
            left["gap_right"] = w
            _touch(left)
            return f"Walkway between {label(a_id, a)} and {label(b_id, b)}"
        rows = model.get("rows") or []
        if a["col"] == b["col"] and a["row"] in rows and b["row"] in rows:
            ia, ib = rows.index(a["row"]), rows.index(b["row"])
            if abs(ia - ib) == 1:
                upper = rows[min(ia, ib)]
                model.setdefault("row_gap_below", {})[upper] = w
                return (f"Walkway between rows {rows[min(ia, ib)]} and {rows[max(ia, ib)]} "
                        f"(the whole row, since rows run edge to edge)")
        raise EditError(f"{op.get('a')} and {op.get('b')} aren't next to each other.")

    if kind == "add_cell":
        try:
            cid = resolve_cell_id(op.get("cell"))
        except ValueError as exc:
            raise EditError(str(exc)) from exc
        if cid in cells:
            raise EditError(f"{op.get('cell')} already exists — use set_cell to change it.")
        c = _new_cell(cid, _len(op.get("width"), "width"), _len(op.get("height"), "height"))
        if op.get("sketch_label"):
            c["sketch_label"] = str(op["sketch_label"]).strip()
        if op.get("shape_kind") and op["shape_kind"] != "rect":
            _apply_shape(c, op)
        if op.get("is_walkway"):
            c["is_walkway"] = True
        cells[cid] = c
        return f"Added {label(cid, c)}"

    if kind == "remove_cell":
        cid, c = _cell(model, op.get("cell"))
        del cells[cid]
        return f"Removed {label(cid, c)}"

    if kind == "add_row":
        row = str(op.get("row", "")).upper()
        if len(row) != 1 or not row.isalpha():
            raise EditError("row must be a single letter")
        if any(c["row"] == row for c in cells.values()):
            raise EditError(f"Row {row} already exists.")
        n = int(op.get("ncols", 1))
        w, h = _len(op.get("width"), "width"), _len(op.get("height"), "height")
        for k in range(1, n + 1):
            cells[f"{row}{k}"] = _new_cell(f"{row}{k}", w, h)
        model.setdefault("rows", []).append(row)
        return f"Added row {row} ({n} cells)"

    if kind == "remove_row":
        row = str(op.get("row", "")).upper()
        gone = [k for k, c in cells.items() if c["row"] == row]
        if not gone and row not in (model.get("rows") or []):
            raise EditError(f"There's no row {row}.")
        for k in gone:
            del cells[k]
        model["rows"] = [r for r in model.get("rows", []) if r != row]
        return f"Removed row {row}"

    raise EditError(f"Unknown operation '{kind}'.")


def apply_ops(model: dict, ops: list[dict]) -> tuple[dict, list[str], list[str]]:
    """Apply a batch atomically-ish on a COPY.

    Returns (new_model, done_messages, errors). Ops that fail are
    skipped and reported; the rest still apply, so one misunderstood
    instruction doesn't throw away three good ones.
    """
    new = copy.deepcopy(model)
    done, errors = [], []
    for op in ops or []:
        if not isinstance(op, dict):
            errors.append(f"ignored malformed edit: {op!r}")
            continue
        try:
            done.append(apply_op(new, op))
        except (EditError, TypeError, ValueError, KeyError) as exc:
            errors.append(str(exc) or f"couldn't apply {op.get('op')}")
    refresh_counts(new)
    errors += resolve_slants(new)
    return new, done, errors


class History:
    """Undo stack of models. Stored in st.session_state as a plain list."""

    def __init__(self, stack: list[dict] | None = None, limit: int = 30):
        self.stack = stack if stack is not None else []
        self.limit = limit

    def push(self, model: dict) -> None:
        self.stack.append(copy.deepcopy(model))
        del self.stack[:-self.limit]

    def undo(self) -> dict | None:
        return self.stack.pop() if self.stack else None

    def __len__(self) -> int:
        return len(self.stack)
