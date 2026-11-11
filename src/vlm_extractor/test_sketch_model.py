"""Tests for the sketch model, geometry and edit operations.

Run from src/:   python -m pytest vlm_extractor/test_sketch_model.py -q
"""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path

import pytest

from vlm_extractor import geometry
from vlm_extractor.edits import EditError, History, apply_op, apply_ops
from vlm_extractor.sketch_model import (
    check, empty_model, parse_length, prepare, resolve_cell_id, to_form_vars,
)


# ── fixtures ────────────────────────────────────────────────────

def _cell(row, col, w=10.0, h=10.0, **kw):
    c = {"row": row, "col": col, "width": w, "height": h,
         "sketch_label": f"{col}{row}", "confidence": "high"}
    c.update(kw)
    return c


def grid(rows="ABC", ncols=3, w=10.0, h=10.0):
    cells = {f"{r}{k}": _cell(r, k, w, h) for r in rows for k in range(1, ncols + 1)}
    model, problems = prepare({"rows": list(rows), "ncols_per_row": {r: ncols for r in rows},
                               "max_cols": ncols, "cells": cells})
    assert not problems, problems
    return model


@pytest.fixture
def staircase():
    """The July sketch: A has 1 cell … E has 5; the diagonal cells slant."""
    cells = {}
    for i, r in enumerate("ABCDE", start=1):
        for k in range(1, i + 1):
            cells[f"{r}{k}"] = _cell(r, k)
    raw = {"rows": list("ABCDE"), "ncols_per_row": {r: i for i, r in enumerate("ABCDE", 1)},
           "max_cols": 5, "cells": cells}
    # VLM says the right edge of each diagonal cell is slanted and reads
    # the diagonal length but (as before) gives no insets.
    for i, r in enumerate("ABCDE", start=1):
        raw["cells"][f"{r}{i}"].update(shape_kind="angle",
                                        shape_params={"side": "R", "slant_len": 14.142})
    model, problems = prepare(raw)
    assert not problems, problems
    return model


# ── parsing ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text,ft", [
    (10, 10.0), ("10.5", 10.5), ("10' 6\"", 10.5), ("10'6", 10.5),
    ("10 ft 6 in", 10.5), ("6in", 0.5), ("14' 2\"", 14 + 2 / 12), ("12’ 2”", 12 + 2 / 12),
])
def test_parse_length(text, ft):
    assert parse_length(text) == pytest.approx(ft, abs=1e-3)


def test_parse_length_rejects_garbage():
    with pytest.raises(ValueError):
        parse_length("ten feet")


@pytest.mark.parametrize("ref,cid", [("1A", "A1"), ("A1", "A1"), (" 3f ", "F3"), ("b12", "B12")])
def test_resolve_cell_id(ref, cid):
    assert resolve_cell_id(ref) == cid


# ── geometry ────────────────────────────────────────────────────

def test_slant_length_becomes_inset(staircase):
    # diagonal 14.142 over a 10 ft edge → 10 ft offset (√(14.142² − 10²))
    p = staircase["cells"]["C3"]["shape_params"]
    assert p["inset_far"] == pytest.approx(10.0, abs=0.01)
    assert p["inset_near"] == 0.0


def test_slant_shorter_than_edge_is_reported():
    raw = copy.deepcopy(grid("A", 1))
    raw["cells"]["A1"].update(shape_kind="angle", shape_params={"side": "L", "slant_len": 8})
    _, problems = prepare(raw)
    assert any("shorter than" in p for p in problems)


def test_layout_rows_stack_far_to_near():
    m = grid("AB", 2, w=10, h=8)
    lay = geometry.layout(m)
    assert lay["A1"]["y1"] == pytest.approx(0)          # row A on top
    assert lay["B1"]["y1"] == pytest.approx(-8)
    assert lay["A2"]["x0"] == pytest.approx(10)


def test_layout_row_gap_and_gap_right():
    m = grid("AB", 2)
    m["row_gap_below"]["A"] = 4
    m["cells"]["A1"]["gap_right"] = 3
    lay = geometry.layout(m)
    assert lay["B1"]["y1"] == pytest.approx(-14)        # 10 ft row + 4 ft walkway
    assert lay["A2"]["x0"] == pytest.approx(13)


def test_sparse_extension_row_right_aligns():
    m = grid("AB", 4)
    m["cells"]["C4"] = _cell("C", 4, w=6)
    m, _ = prepare(m)
    lay = geometry.layout(m)
    assert lay["C4"]["x1"] == pytest.approx(lay["A4"]["x1"])


def _site_builder_funcs():
    """Load the polygon helpers straight out of site_builder.py."""
    src = (Path(__file__).resolve().parent.parent / "site_builder.py").read_text()
    tree = ast.parse(src)
    wanted = {"_rect_local_polygon", "_notch_local_polygon", "_angled_local_polygon"}
    mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                           and n.name in wanted], type_ignores=[])
    ns: dict = {}
    exec(compile(mod, "site_builder_helpers", "exec"), ns)
    return ns


def test_polygons_match_site_builder():
    sb = _site_builder_funcs()
    for corner in ("TL", "TR", "BL", "BR"):
        assert geometry.notch_local_polygon(10, 8, corner, 3, 2) == \
            sb["_notch_local_polygon"](10, 8, corner, 3, 2)
    for side in "LRTB":
        assert geometry.angled_local_polygon(10, 8, side, 1, 4) == \
            sb["_angled_local_polygon"](10, 8, side, 1, 4)


# ── checks ──────────────────────────────────────────────────────

def test_check_flags_unmeasured_slant():
    m = grid("A", 2)
    m["cells"]["A1"].update(shape_kind="angle", shape_params={"side": "L"})
    findings = check(m)
    assert any(f["level"] == "error" and f["cell"] == "A1" for f in findings)


def test_check_flags_width_mismatch():
    m = grid("AB", 2)
    m["cells"]["B2"]["width"] = 14
    assert any("different total widths" in f["msg"] for f in check(m))


def test_check_clean_grid_has_no_errors(staircase):
    assert not [f for f in check(staircase) if f["level"] == "error"]


# ── edits ───────────────────────────────────────────────────────

def test_set_cell_accepts_written_lengths_and_either_label_order():
    m = grid()
    m2, done, errs = apply_ops(m, [{"op": "set_cell", "cell": "2B", "width": "10' 6\""}])
    assert not errs and m2["cells"]["B2"]["width"] == pytest.approx(10.5)
    assert m["cells"]["B2"]["width"] == 10           # original untouched


def test_set_shape_angle_from_diagonal():
    m2, _, errs = apply_ops(grid(), [{"op": "set_shape", "cell": "1A", "shape_kind": "angle",
                                      "side": "L", "slant_len": "16'", "slant_end": "far"}])
    assert not errs
    assert m2["cells"]["A1"]["shape_params"]["inset_far"] == pytest.approx(math.sqrt(256 - 100), abs=0.01)


def test_walkway_between_columns_and_rows():
    m2, _, errs = apply_ops(grid(), [
        {"op": "walkway_between", "a": "B2", "b": "B3", "width": 4},
        {"op": "walkway_between", "a": "A1", "b": "B1", "width": "2' 6\""},
    ])
    assert not errs
    assert m2["cells"]["B2"]["gap_right"] == 4
    assert m2["row_gap_below"]["A"] == pytest.approx(2.5)


def test_walkway_between_non_neighbours_fails():
    _, _, errs = apply_ops(grid(), [{"op": "walkway_between", "a": "A1", "b": "C3", "width": 4}])
    assert errs


def test_add_and_remove_cells_and_rows_keep_counts_right():
    m2, _, errs = apply_ops(grid("AB", 3), [
        {"op": "add_row", "row": "C", "ncols": 2, "width": 10, "height": 6},
        {"op": "add_cell", "cell": "4A", "width": 5, "height": 10},
        {"op": "remove_cell", "cell": "B3"},
    ])
    assert not errs
    assert m2["rows"] == ["A", "B", "C"]
    assert m2["ncols_per_row"] == {"A": 4, "B": 2, "C": 2}
    assert m2["max_cols"] == 4


def test_bad_op_is_reported_but_good_ones_apply():
    m2, done, errs = apply_ops(grid(), [
        {"op": "set_cell", "cell": "Z9", "width": 3},
        {"op": "set_row_height", "row": "A", "height": 12},
    ])
    assert len(errs) == 1 and len(done) == 1
    assert m2["cells"]["A3"]["height"] == 12


def test_edited_cell_is_marked_verified():
    m = grid()
    m["cells"]["A1"]["confidence"] = "low"
    assert any(f["level"] == "ask" for f in check(m))
    m2, _, _ = apply_ops(m, [{"op": "set_cell", "cell": "A1", "width": 10}])
    assert not any(f["level"] == "ask" for f in check(m2))


def test_history_undo():
    h = History([])
    m = grid()
    h.push(m)
    m2, _, _ = apply_ops(m, [{"op": "remove_row", "row": "C"}])
    assert h.undo()["rows"] == ["A", "B", "C"]
    assert len(h) == 0


# ── hand-off to Compute ─────────────────────────────────────────

def test_form_vars_match_compute_contract(staircase):
    fv = to_form_vars(staircase, "Back")
    assert fv["rows"] == list("ABCDE")
    assert fv["max_cols"] == 5
    cd = fv["cell_data"]["C3"]
    assert set(cd) >= {"width", "height", "col", "row", "pattern", "gap_right",
                       "is_walkway", "shape_kind", "shape_params", "local_polygon"}
    assert cd["pattern"] == "Back_3C_"
    assert set(cd["shape_params"]) == {"side", "inset_near", "inset_far"}


def test_empty_model_reports_error():
    assert check(empty_model())[0]["level"] == "error"


# ── slanted cells with a written end width (staircase yards) ────

def test_top_width_plus_diagonal_gives_full_width():
    # B2 on the July sketch: 4' across the top, 13' diagonal, 10' tall
    raw = copy.deepcopy(grid("A", 1))
    raw["cells"]["A1"].update(shape_kind="angle", shape_params={
        "side": "R", "slant_len": 13, "slant_end": "far", "top_width": 4})
    m, problems = prepare(raw)
    assert not problems
    c = m["cells"]["A1"]
    assert c["width"] == pytest.approx(4 + math.sqrt(169 - 100), abs=0.01)
    assert c["shape_params"]["inset_far"] == pytest.approx(math.sqrt(69), abs=0.01)
    top = geometry.local_polygon_for_cell(c)
    assert top[2][0] - top[3][0] == pytest.approx(4, abs=0.01)   # top edge is 4 ft


def test_pointed_triangle_cell():
    raw = copy.deepcopy(grid("A", 1, h=12))
    raw["cells"]["A1"].update(shape_kind="angle", shape_params={
        "side": "R", "slant_len": 16, "slant_end": "far", "top_width": 0})
    m, _ = prepare(raw)
    assert m["cells"]["A1"]["width"] == pytest.approx(math.sqrt(256 - 144), abs=0.01)
    assert not [f for f in check(m) if f["level"] == "error"]


def test_both_ends_written_disagreeing_with_diagonal_is_flagged():
    raw = copy.deepcopy(grid("A", 1))
    raw["cells"]["A1"].update(shape_kind="angle", shape_params={
        "side": "R", "slant_len": 20, "top_width": 4, "bottom_width": 12})
    _, problems = prepare(raw)
    assert any("don't agree" in p for p in problems)


def test_explicit_width_overrides_end_measurements():
    m2, _, errs = apply_ops(grid("A", 1), [
        {"op": "set_shape", "cell": "1A", "shape_kind": "angle", "side": "R",
         "slant_len": 13, "top_width": 4},
        {"op": "set_cell", "cell": "1A", "width": 11}])
    assert not errs and m2["cells"]["A1"]["width"] == 11


def test_align_slant_makes_one_continuous_line():
    raw = {"rows": ["A", "B"], "ncols_per_row": {}, "max_cols": 2, "cells": {
        "A1": _cell("A", 1, shape_kind="angle",
                    shape_params={"side": "R", "slant_len": 13, "top_width": 4}),
        "B1": _cell("B", 1), "B2": _cell("B", 2, shape_kind="angle",
                                         shape_params={"side": "R", "slant_len": 15})}}
    m, _ = prepare(raw)
    m2, done, errs = apply_ops(m, [{"op": "align_slant", "cells": ["1A", "2B"]}])
    assert not errs, errs
    lay = geometry.layout(m2)
    a_bottom_right = max(p[0] for p in lay["A1"]["polygon"] if abs(p[1] - lay["A1"]["y0"]) < 1e-6)
    b_top_right = max(p[0] for p in lay["B2"]["polygon"] if abs(p[1] - lay["B2"]["y1"]) < 1e-6)
    assert b_top_right == pytest.approx(a_bottom_right, abs=0.01)


def test_medium_cells_grouped_and_confirm_clears_them():
    m = grid("A", 3)
    for c in m["cells"].values():
        c["confidence"] = "medium"
    asks = [f for f in check(m) if f["level"] == "ask"]
    assert len(asks) == 1 and "3A" in asks[0]["msg"]
    m2, _, errs = apply_ops(m, [{"op": "confirm", "cells": ["all"]}])
    assert not errs and not [f for f in check(m2) if f["level"] == "ask"]


def test_failed_op_leaves_no_partial_change():
    raw = {"rows": ["A", "B"], "ncols_per_row": {}, "max_cols": 2, "cells": {
        "A1": _cell("A", 1, shape_kind="angle", shape_params={"side": "R", "slant_len": 13}),
        "B1": _cell("B", 1), "B2": _cell("B", 2)}}           # B2 not slanted
    m, _ = prepare(raw)
    m2, done, errs = apply_ops(m, [{"op": "align_slant", "cells": ["A1", "B2"]}])
    assert errs and not done
    assert m2["cells"] == m["cells"]


def test_align_slant_keeps_measured_top_width():
    raw = {"rows": ["A", "B"], "ncols_per_row": {}, "max_cols": 2, "cells": {
        "A1": _cell("A", 1, shape_kind="angle", shape_params={"side": "R", "slant_len": 13}),
        "B1": _cell("B", 1), "B2": _cell("B", 2, shape_kind="angle",
                                         shape_params={"side": "R", "slant_len": 15, "top_width": 2})}}
    m, _ = prepare(raw)
    m2, done, errs = apply_ops(m, [{"op": "align_slant", "cells": ["A1", "B2"]}])
    assert not errs and m2["cells"]["B2"]["shape_params"]["top_width"] == 2
    assert "as measured" in done[0]


def test_missing_labels_follow_the_sketch_style():
    raw = {"rows": ["A", "B"], "ncols_per_row": {}, "max_cols": 1, "cells": {
        "A1": {"row": "A", "col": 1, "width": 10, "height": 10, "sketch_label": "A1"},
        "B1": {"row": "B", "col": 1, "width": 10, "height": 10}}}
    m, _ = prepare(raw)
    assert m["cells"]["B1"]["sketch_label"] == "B1"
    assert to_form_vars(m, "Front")["cell_data"]["B1"]["pattern"] == "Front_B1_"
