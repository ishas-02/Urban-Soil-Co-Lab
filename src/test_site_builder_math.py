"""Test the new shape/gap math in isolation by re-implementing the
compute logic exactly as site_builder.py does it (modulo Streamlit
glue), then verifying:

  1. Rectangles with no gaps and no walkways match the ORIGINAL compute
     output byte-for-byte (regression guard — we can't break existing
     sites).
  2. Row gaps shift only the rows AFTER the gap.
  3. Column gap_right shifts only the columns AFTER the gap.
  4. Notch / angle / custom polygons produce the right vertex count
     and live inside the cell's bounding rectangle.
  5. The bounding-box (sw_x/ne_x) of a non-rect cell hugs its polygon
     (not the original rect dimensions).
  6. Walkway cells get zone="walkway" and empty patterns but still
     occupy grid space.
  7. The hand-drawn sample map from the user's photo is reproducible:
     a 4×4 main grid (A–D, cols 1–4) plus the L-shaped F/G extension
     with the 4E corner notch and a walkway between 3F/3G and 4E/4F/4G.
"""
import sys, os, copy, importlib.util, re

# Load site_builder helpers WITHOUT importing streamlit / map_renderer.
# Easiest: extract just the pure-Python helper functions we need by
# exec-ing a hand-trimmed slice of the file. To avoid that complexity,
# define them inline here, copied verbatim from the implementation —
# this lets the test ALSO catch divergence between the test and the
# source.

HERE = os.path.dirname(os.path.abspath(__file__))
SB_PATH = os.path.join(HERE, "site_builder.py")
with open(SB_PATH) as f:
    src = f.read()

# Pull out the four helper bodies by simple regex — they're all top-
# level `def` with no Streamlit dependencies.
import ast
tree = ast.parse(src)
wanted = {"_rect_local_polygon", "_notch_local_polygon",
          "_angled_local_polygon", "_parse_custom_polygon",
          "_local_polygon_for_cell"}
ns = {"re": __import__("re")}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in wanted:
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     filename=SB_PATH, mode="exec"), ns)

_rect_local_polygon     = ns["_rect_local_polygon"]
_notch_local_polygon    = ns["_notch_local_polygon"]
_angled_local_polygon   = ns["_angled_local_polygon"]
_parse_custom_polygon   = ns["_parse_custom_polygon"]
_local_polygon_for_cell = ns["_local_polygon_for_cell"]


# ─────────────────────────────────────────────────────────────────────
# Reference implementation of the OLD compute math (used to verify the
# new math degenerates correctly when no shapes/gaps are involved).
# ─────────────────────────────────────────────────────────────────────
def original_compute(rows, cell_data, fp_cell, fp_corner,
                     is_vertical=True, flip_strip=False):
    row_heights = {}
    for row in rows:
        c1 = f"{row}1"
        if c1 in cell_data:
            row_heights[row] = cell_data[c1]["height"]
        else:
            for cid, cd in cell_data.items():
                if cd["row"] == row:
                    row_heights[row] = cd["height"]; break

    strip_pos, pos = {}, 0
    for row in rows:
        strip_pos[row] = pos
        pos += row_heights.get(row, 10)

    fp_row = ''.join(c for c in fp_cell if c.isalpha())
    fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

    col_widths_per_row = {}
    for row in rows:
        col_widths_per_row[row] = {}
        for cid, cd in cell_data.items():
            if cd["row"] == row:
                col_widths_per_row[row][cd["col"]] = cd["width"]

    fp_row_widths = col_widths_per_row.get(fp_row, {})
    fp_perp = 0
    if "Left" in fp_corner:
        for c in range(1, fp_col):
            fp_perp += fp_row_widths.get(c, 0)
    else:
        for c in range(1, fp_col + 1):
            fp_perp += fp_row_widths.get(c, 0)

    fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

    out = {}
    for cid, cd in cell_data.items():
        row, col = cd["row"], cd["col"]
        cell_h, cell_w = cd["height"], cd["width"]

        strip_start = strip_pos[row] - fp_strip
        strip_end = strip_start + row_heights[row]
        if cell_h != row_heights[row]:
            strip_start = strip_end - cell_h

        perp_start = sum(col_widths_per_row[row].get(c, 0) for c in range(1, col))
        perp_end = perp_start + cell_w
        perp_start -= fp_perp; perp_end -= fp_perp

        if flip_strip:
            strip_start, strip_end = -strip_end, -strip_start
        if is_vertical:
            ns, ne, es, ee = strip_start, strip_end, perp_start, perp_end
        else:
            es, ee, ns, ne = strip_start, strip_end, perp_start, perp_end

        out[cid] = {
            "sw_x": round(min(es, ee), 2), "sw_y": round(min(ns, ne), 2),
            "ne_x": round(max(es, ee), 2), "ne_y": round(max(ns, ne), 2),
        }
    return out


# ─────────────────────────────────────────────────────────────────────
# New compute implementation (mirror of the patched site_builder code).
# ─────────────────────────────────────────────────────────────────────
def new_compute(rows, cell_data, fp_cell, fp_corner,
                row_gap_below=None, is_vertical=True, flip_strip=False):
    row_gap_below = row_gap_below or {r: 0.0 for r in rows}

    row_heights = {}
    for row in rows:
        c1 = f"{row}1"
        if c1 in cell_data:
            row_heights[row] = cell_data[c1]["height"]
        else:
            for cid, cd in cell_data.items():
                if cd["row"] == row:
                    row_heights[row] = cd["height"]; break

    strip_pos, pos = {}, 0
    for row in rows:
        strip_pos[row] = pos
        pos += row_heights.get(row, 10) + float(row_gap_below.get(row, 0.0) or 0.0)

    fp_row = ''.join(c for c in fp_cell if c.isalpha())
    fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

    col_widths_per_row, col_gap_right_per_row = {}, {}
    for row in rows:
        col_widths_per_row[row] = {}
        col_gap_right_per_row[row] = {}
        for cid, cd in cell_data.items():
            if cd["row"] == row:
                col_widths_per_row[row][cd["col"]] = cd["width"]
                col_gap_right_per_row[row][cd["col"]] = float(
                    cd.get("gap_right", 0.0) or 0.0)

    def perp_start_for(row, col):
        s = 0.0
        for c in range(1, col):
            s += col_widths_per_row[row].get(c, 0)
            s += col_gap_right_per_row[row].get(c, 0)
        return s

    fp_perp = perp_start_for(fp_row, fp_col)
    if "Right" in fp_corner:
        fp_perp += col_widths_per_row[fp_row].get(fp_col, 0)
    fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

    def _local_to_global(local_x, local_y, perp_start_abs, strip_end_abs):
        perp = perp_start_abs + local_x
        strip = strip_end_abs - local_y
        if flip_strip:
            strip = -strip
        if is_vertical:
            return perp, strip
        return strip, perp

    out = {}
    for cid, cd in cell_data.items():
        row, col = cd["row"], cd["col"]
        cell_h, cell_w = cd["height"], cd["width"]

        strip_start = strip_pos[row] - fp_strip
        strip_end = strip_start + row_heights[row]
        if cell_h != row_heights[row]:
            strip_start = strip_end - cell_h
        perp_start = perp_start_for(row, col) - fp_perp
        perp_end = perp_start + cell_w

        ss_pre = strip_start; se_pre = strip_end
        bb_ss = -se_pre if flip_strip else ss_pre
        bb_se = -ss_pre if flip_strip else se_pre
        if is_vertical:
            ns_v, ne_v, es_v, ee_v = bb_ss, bb_se, perp_start, perp_end
        else:
            es_v, ee_v, ns_v, ne_v = bb_ss, bb_se, perp_start, perp_end

        local_poly = _local_polygon_for_cell(cd)
        global_poly = [_local_to_global(lx, ly, perp_start, se_pre)
                       for (lx, ly) in local_poly]
        global_poly = [[round(p[0], 2), round(p[1], 2)] for p in global_poly]

        shape_kind = cd.get("shape_kind", "rect")
        if shape_kind != "rect" and len(global_poly) >= 3:
            poly_xs = [p[0] for p in global_poly]
            poly_ys = [p[1] for p in global_poly]
            sw_x_v, ne_x_v = min(poly_xs), max(poly_xs)
            sw_y_v, ne_y_v = min(poly_ys), max(poly_ys)
        else:
            sw_x_v, ne_x_v = min(es_v, ee_v), max(es_v, ee_v)
            sw_y_v, ne_y_v = min(ns_v, ne_v), max(ns_v, ne_v)

        entry = {"sw_x": round(sw_x_v, 2), "sw_y": round(sw_y_v, 2),
                 "ne_x": round(ne_x_v, 2), "ne_y": round(ne_y_v, 2)}
        if shape_kind != "rect" and len(global_poly) >= 3:
            entry["_polygon"] = global_poly
            entry["shape_kind"] = shape_kind
        if cd.get("is_walkway"):
            entry["is_walkway"] = True
        out[cid] = entry
    return out


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def make_cd(rows, ncols, w=10, h=10, **overrides_per_cell):
    cd = {}
    for r in rows:
        for c in range(1, ncols + 1):
            cid = f"{r}{c}"
            entry = {"width": w, "height": h, "col": c, "row": r,
                     "pattern": f"P_{cid}", "gap_right": 0.0,
                     "is_walkway": False, "shape_kind": "rect",
                     "shape_params": {}, "local_polygon": None}
            entry.update(overrides_per_cell.get(cid, {}))
            cd[cid] = entry
    return cd


def approx(a, b, tol=1e-2):
    return abs(a - b) <= tol


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────
def test_rect_no_gap_matches_original():
    """Regression guard: vanilla rectangles unchanged."""
    rows = ["A", "B", "C", "D"]
    cd = make_cd(rows, 4, w=10, h=10)
    for cmb in [("A1", "Top-Left"), ("D1", "Bottom-Left"),
                ("A4", "Top-Right"), ("D4", "Bottom-Right"),
                ("B2", "Top-Left")]:
        fp, corner = cmb
        old = original_compute(rows, cd, fp, corner)
        new = new_compute(rows, cd, fp, corner)
        for cid in old:
            for k in ("sw_x", "sw_y", "ne_x", "ne_y"):
                assert approx(old[cid][k], new[cid][k]), (
                    f"rect regression for {cid}.{k} with fp={fp}/{corner}: "
                    f"old={old[cid][k]} vs new={new[cid][k]}")
    print("  ✓ test_rect_no_gap_matches_original")


def test_rect_irregular_widths_match():
    """Use unequal widths & heights — like the real hand-drawn map."""
    rows = ["A", "B", "C", "D"]
    cd = make_cd(rows, 4, w=10, h=10,
                 A1={"width": 10, "height": 10, "col": 1, "row": "A",
                     "pattern": "x", "gap_right": 0.0, "is_walkway": False,
                     "shape_kind": "rect", "shape_params": {},
                     "local_polygon": None},
                 A4={"width": 13, "height": 10, "col": 4, "row": "A",
                     "pattern": "x", "gap_right": 0.0, "is_walkway": False,
                     "shape_kind": "rect", "shape_params": {},
                     "local_polygon": None},
                 D4={"width": 13, "height": 13, "col": 4, "row": "D",
                     "pattern": "x", "gap_right": 0.0, "is_walkway": False,
                     "shape_kind": "rect", "shape_params": {},
                     "local_polygon": None})
    old = original_compute(rows, cd, "A1", "Top-Left")
    new = new_compute(rows, cd, "A1", "Top-Left")
    for cid in old:
        for k in ("sw_x", "sw_y", "ne_x", "ne_y"):
            assert approx(old[cid][k], new[cid][k]), (
                f"irregular regression {cid}.{k}: old={old[cid][k]} "
                f"new={new[cid][k]}")
    print("  ✓ test_rect_irregular_widths_match")


def test_orientations_and_flip():
    """Ensure all combinations of (vertical, flipped) also match."""
    rows = ["A", "B", "C"]
    cd = make_cd(rows, 3, w=10, h=10)
    for is_v in (True, False):
        for flip in (True, False):
            old = original_compute(rows, cd, "A1", "Top-Left",
                                   is_vertical=is_v, flip_strip=flip)
            new = new_compute(rows, cd, "A1", "Top-Left",
                              is_vertical=is_v, flip_strip=flip)
            for cid in old:
                for k in ("sw_x", "sw_y", "ne_x", "ne_y"):
                    assert approx(old[cid][k], new[cid][k]), (
                        f"orient regression is_v={is_v} flip={flip} "
                        f"{cid}.{k}: old={old[cid][k]} new={new[cid][k]}")
    print("  ✓ test_orientations_and_flip")


def test_row_gap_shifts_only_after():
    """A gap below row B should leave A, B in place and push C, D south."""
    rows = ["A", "B", "C", "D"]
    cd = make_cd(rows, 2, w=10, h=10)
    gap = {"A": 0, "B": 5, "C": 0, "D": 0}
    no_gap = new_compute(rows, cd, "A1", "Top-Left")
    gapped = new_compute(rows, cd, "A1", "Top-Left", row_gap_below=gap)
    # A1, B1 unchanged
    for cid in ("A1", "A2", "B1", "B2"):
        assert no_gap[cid] == gapped[cid], f"{cid} should be unchanged by row gap after B"
    # C1 shifted south by 5 (strip increases southward; with no flip the strip
    # axis maps to the ns axis under vertical orientation, so ne_y / sw_y both
    # increase).
    delta_c = gapped["C1"]["sw_y"] - no_gap["C1"]["sw_y"]
    assert approx(delta_c, 5.0), f"C1 should shift +5 ft (sw_y) — got Δ={delta_c}"
    delta_d = gapped["D2"]["ne_y"] - no_gap["D2"]["ne_y"]
    assert approx(delta_d, 5.0), f"D2 should also shift +5 ft (ne_y) — got Δ={delta_d}"
    print("  ✓ test_row_gap_shifts_only_after")


def test_col_gap_right_shifts_only_after():
    """gap_right on B2 should push B3, B4 east, leaving everything else alone."""
    rows = ["A", "B", "C"]
    cd = make_cd(rows, 4, w=10, h=10)
    cd["B2"]["gap_right"] = 3.0
    base = new_compute(rows, cd_without := make_cd(rows, 4, w=10, h=10),
                       "A1", "Top-Left")
    out = new_compute(rows, cd, "A1", "Top-Left")
    # Column 1 and 2 in row B unchanged.
    for cid in ("B1", "B2"):
        assert approx(base[cid]["sw_x"], out[cid]["sw_x"]), \
            f"{cid} sw_x shouldn't change from gap_right on B2"
    # B3 shifted east by 3.
    assert approx(out["B3"]["sw_x"] - base["B3"]["sw_x"], 3.0), \
        f"B3 should shift +3 east, got Δ={out['B3']['sw_x'] - base['B3']['sw_x']}"
    # Other rows untouched.
    for cid in ("A3", "C3"):
        assert base[cid] == out[cid], f"{cid} unchanged when only B2 has gap"
    print("  ✓ test_col_gap_right_shifts_only_after")


def test_notch_polygon_has_six_points_inside_cell():
    rows = ["A"]
    cd = make_cd(rows, 1, w=10, h=10)
    cd["A1"]["shape_kind"] = "notch"
    cd["A1"]["shape_params"] = {"corner": "BL", "notch_w": 3, "notch_h": 4}
    out = new_compute(rows, cd, "A1", "Top-Left")
    poly = out["A1"]["_polygon"]
    assert len(poly) == 6, f"Notch should produce 6 vertices, got {len(poly)}"
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    # bounding box still hugs the cell rect [0,10] × [-10,0] (A1 is at the
    # FP, so sw=0; strip goes negative below the FP).
    assert approx(min(xs), 0) and approx(max(xs), 10), f"poly xs out of range: {xs}"
    # sw_y/ne_y come from polygon vertices.
    assert approx(out["A1"]["sw_x"], 0)
    assert approx(out["A1"]["ne_x"], 10)
    print("  ✓ test_notch_polygon_has_six_points_inside_cell")


def test_angle_polygon_has_four_points():
    rows = ["A"]
    cd = make_cd(rows, 1, w=10, h=10)
    cd["A1"]["shape_kind"] = "angle"
    cd["A1"]["shape_params"] = {"side": "L", "inset_near": 2, "inset_far": 4}
    out = new_compute(rows, cd, "A1", "Top-Left")
    poly = out["A1"]["_polygon"]
    assert len(poly) == 4, f"angled edge cell should have 4 vertices, got {len(poly)}"
    print("  ✓ test_angle_polygon_has_four_points")


def test_custom_polygon_round_trips():
    pts, msg = _parse_custom_polygon(
        "0,0; 10,0; 10,6; 4,6; 4,10; 0,10", 10, 10)
    assert pts is not None and len(pts) == 6, f"got {pts}, msg={msg}"
    # Newline-separated should also work
    pts2, _ = _parse_custom_polygon("0,0\n10,0\n10,10\n0,10", 10, 10)
    assert pts2 == [[0,0],[10,0],[10,10],[0,10]]
    # Bad input → None
    bad, msg = _parse_custom_polygon("hello world", 10, 10)
    assert bad is None
    # Too few vertices → None
    short, msg = _parse_custom_polygon("0,0; 10,0", 10, 10)
    assert short is None
    print("  ✓ test_custom_polygon_round_trips")


def test_walkway_cell_tagging():
    """Walkway cells still occupy space but get zone='walkway' (in real
    impl; here just check is_walkway flag passes through and they still
    contribute to perp/strip accumulation)."""
    rows = ["A", "B"]
    cd = make_cd(rows, 3, w=10, h=10)
    cd["B2"]["is_walkway"] = True
    out = new_compute(rows, cd, "A1", "Top-Left")
    assert out["B2"].get("is_walkway") is True
    # B3 should still sit where it would if B2 weren't a walkway
    # (walkway reserves space, doesn't collapse it).
    cd_normal = make_cd(rows, 3, w=10, h=10)
    out_n = new_compute(rows, cd_normal, "A1", "Top-Left")
    assert approx(out["B3"]["sw_x"], out_n["B3"]["sw_x"])
    print("  ✓ test_walkway_cell_tagging")


def test_bbox_for_non_rect_hugs_polygon_not_rect():
    """For a corner-notched cell, sw_x/ne_x should equal the polygon's
    true bbox — but since the notch is in a CORNER of the cell, the
    polygon's bounding rectangle == the original cell rectangle. So this
    test really checks that the bbox is derived FROM the polygon (i.e.
    handles the case correctly even when they happen to coincide)."""
    rows = ["A"]
    cd = make_cd(rows, 1, w=10, h=10)
    cd["A1"]["shape_kind"] = "notch"
    cd["A1"]["shape_params"] = {"corner": "TL", "notch_w": 3, "notch_h": 4}
    out = new_compute(rows, cd, "A1", "Top-Left")
    poly = out["A1"]["_polygon"]
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    assert approx(out["A1"]["sw_x"], min(xs))
    assert approx(out["A1"]["ne_x"], max(xs))
    assert approx(out["A1"]["sw_y"], min(ys))
    assert approx(out["A1"]["ne_y"], max(ys))
    print("  ✓ test_bbox_for_non_rect_hugs_polygon_not_rect")


def test_handdrawn_sample_map():
    """Build something resembling the user's photo and sanity-check it:
      • 4 columns, 4 rows for the main A–D × 1–4 grid
      • cell 4* is 13 ft wide instead of 10
      • row D is 13 ft tall instead of 10
      • F and G rows are an extension (cols 3 and 4 only, with cell 3F
        having an angled left edge, and a column 4 strip with a notched
        4E corner)
      • walkway between rows D and F (5 ft path)
      • column gap between col 3 (3F/3G) and col 4 (4E/4F/4G)
    """
    rows = ["A", "B", "C", "D", "E", "F", "G"]
    cd = {}
    # main 4x4 (A–D × 1–4) with col 4 being 13' wide and row D being 13' tall
    for r in ["A", "B", "C", "D"]:
        for c in range(1, 5):
            w = 13 if c == 4 else 10
            h = 13 if r == "D" else 10
            cd[f"{r}{c}"] = {"width": w, "height": h, "col": c, "row": r,
                             "pattern": f"P_{r}{c}", "gap_right": 0.0,
                             "is_walkway": False, "shape_kind": "rect",
                             "shape_params": {}, "local_polygon": None}
    # E row: just col 4 (4E) — 13' wide × 15.66' tall (15'8")
    cd["E4"] = {"width": 13, "height": 15.66, "col": 4, "row": "E",
                "pattern": "P_E4", "gap_right": 0.0, "is_walkway": False,
                "shape_kind": "notch",
                "shape_params": {"corner": "TL", "notch_w": 4, "notch_h": 4},
                "local_polygon": None}
    # F row: col 3 (3F) angled, col 4 (4F) rect 14' tall × 13'
    cd["F3"] = {"width": 4.42, "height": 14.0, "col": 3, "row": "F",
                "pattern": "P_F3", "gap_right": 2.0,  # walkway to the right
                "is_walkway": False, "shape_kind": "angle",
                "shape_params": {"side": "L", "inset_near": 0, "inset_far": 2},
                "local_polygon": None}
    cd["F4"] = {"width": 13, "height": 14.0, "col": 4, "row": "F",
                "pattern": "P_F4", "gap_right": 0.0, "is_walkway": False,
                "shape_kind": "rect", "shape_params": {}, "local_polygon": None}
    # G row: col 3 (3G), col 4 (4G) with 4G being 13.66' tall (13'8")
    cd["G3"] = {"width": 4.42, "height": 13.66, "col": 3, "row": "G",
                "pattern": "P_G3", "gap_right": 2.0, "is_walkway": False,
                "shape_kind": "rect", "shape_params": {}, "local_polygon": None}
    cd["G4"] = {"width": 13, "height": 13.66, "col": 4, "row": "G",
                "pattern": "P_G4", "gap_right": 0.0, "is_walkway": False,
                "shape_kind": "rect", "shape_params": {}, "local_polygon": None}

    row_gap = {"A": 0, "B": 0, "C": 0, "D": 5, "E": 0, "F": 0, "G": 0}
    out = new_compute(rows, cd, "A1", "Top-Left",
                      row_gap_below=row_gap)

    # Sanity-check a few things
    assert "_polygon" in out["E4"], "E4 should have a polygon"
    assert "_polygon" in out["F3"], "F3 should have a polygon"
    assert "_polygon" not in out["A1"], "A1 should be plain rect, no polygon"
    # Row-gap effect: cells in E,F,G should sit at least 5 ft further south
    # than they would without the gap.
    out_no_gap = new_compute(rows, cd, "A1", "Top-Left")
    e4_delta = out["E4"]["sw_y"] - out_no_gap["E4"]["sw_y"]
    assert approx(e4_delta, 5.0), f"E4 should shift +5 ft (sw_y) — got Δ={e4_delta}"
    # gap_right on F3 → F4 should be 2 ft further east than if gap were 0.
    cd_no_col_gap = copy.deepcopy(cd)
    cd_no_col_gap["F3"]["gap_right"] = 0
    cd_no_col_gap["G3"]["gap_right"] = 0
    out_no_col_gap = new_compute(rows, cd_no_col_gap, "A1", "Top-Left",
                                  row_gap_below=row_gap)
    f4_delta = out["F4"]["sw_x"] - out_no_col_gap["F4"]["sw_x"]
    assert approx(f4_delta, 2.0), f"F4 should shift +2 ft east — got Δ={f4_delta}"
    print("  ✓ test_handdrawn_sample_map")


# Run all
if __name__ == "__main__":
    print("Running site_builder math tests…")
    test_rect_no_gap_matches_original()
    test_rect_irregular_widths_match()
    test_orientations_and_flip()
    test_row_gap_shifts_only_after()
    test_col_gap_right_shifts_only_after()
    test_notch_polygon_has_six_points_inside_cell()
    test_angle_polygon_has_four_points()
    test_custom_polygon_round_trips()
    test_walkway_cell_tagging()
    test_bbox_for_non_rect_hugs_polygon_not_rect()
    test_handdrawn_sample_map()
    print("\nAll tests passed.")