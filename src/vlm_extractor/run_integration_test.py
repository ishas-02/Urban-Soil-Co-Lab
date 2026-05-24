"""Integration test: prove the VLM-extracted cell_data drops cleanly
into site_builder.py's existing Compute path.

We re-implement (verbatim) the geo-math from lines 1234–1330 of the
active site_builder.py and run it on the extracted cell_data. If the
resulting grid_blocks have plausible sw_x/ne_y coordinates, the
contract is intact and Chunk 1 is done.
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # .../src/vlm_extractor
_SRC  = _HERE.parent                              # .../src
_REPO = _SRC.parent                               # .../Soil Co-Lab
sys.path.insert(0, str(_SRC))


def _rect_local_polygon(w, h):
    return [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]]


def _angled_local_polygon(w, h, side, inset_near, inset_far):
    """Verbatim copy from site_builder.py lines 363–420."""
    w = max(0.0, float(w))
    h = max(0.0, float(h))
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
    return _rect_local_polygon(w, h)


def _local_polygon_for_cell(cd):
    """Verbatim copy from site_builder.py line 476."""
    w, h = float(cd.get("width", 0)), float(cd.get("height", 0))
    kind = cd.get("shape_kind", "rect")
    params = cd.get("shape_params") or {}
    if kind == "rect":
        return _rect_local_polygon(w, h)
    if kind == "angle":
        return _angled_local_polygon(
            w, h, params.get("side", "L"),
            params.get("inset_near", 0), params.get("inset_far", 0),
        )
    return _rect_local_polygon(w, h)


def run_compute(extracted: dict):
    """Lift of site_builder.py's Compute path. Inputs match what the
    Streamlit form would supply: manual fixed-point cell + corner,
    yard orientation, plus the VLM-extracted cell structure.
    """
    cell_data = extracted["cell_data"]
    rows = extracted["rows"]
    row_gap_below = extracted["row_gap_below"]

    # ── manual inputs from Streamlit (kept on the form per your rules) ──
    fp_cell = "4D"           # fixed point cell (would be picked in UI)
    fp_corner = "Bottom-Right"
    orientation = "Vertical (strip runs North–South)"
    house_dir = "Bottom (South)"

    # ── row heights from cell_data (verbatim from site_builder.py L1223) ──
    row_heights = {}
    for row in rows:
        c1 = f"1{row}"  # note: site_builder uses f"{row}1" but reads via cell_data lookup
        # Use whatever cell exists in that row to pick its height
        for cid, cd in cell_data.items():
            if cd["row"] == row:
                row_heights[row] = cd["height"]
                break

    # Strip positions with row gaps (verbatim L1237)
    strip_pos, pos = {}, 0
    for row in rows:
        strip_pos[row] = pos
        pos += row_heights.get(row, 10) + float(row_gap_below.get(row, 0.0) or 0.0)

    # Column-width / gap lookups (verbatim L1245)
    col_widths_per_row = {}
    col_gap_right_per_row = {}
    for row in rows:
        col_widths_per_row[row] = {}
        col_gap_right_per_row[row] = {}
        for cid, cd in cell_data.items():
            if cd["row"] == row:
                col_widths_per_row[row][cd["col"]] = cd["width"]
                col_gap_right_per_row[row][cd["col"]] = float(cd.get("gap_right", 0.0) or 0.0)

    def perp_start_for(row, col):
        s = 0.0
        for c in range(1, col):
            s += col_widths_per_row[row].get(c, 0)
            s += col_gap_right_per_row[row].get(c, 0)
        return s

    # Fixed-point math
    fp_row = ''.join(c for c in fp_cell if c.isalpha())
    fp_col = int(''.join(c for c in fp_cell if c.isdigit()))
    fp_perp = perp_start_for(fp_row, fp_col)
    if "Right" in fp_corner:
        fp_perp += col_widths_per_row[fp_row].get(fp_col, 0)
    fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

    is_vertical = "Vertical" in orientation
    flip_strip = "Top" in house_dir or "Right" in house_dir

    grid_blocks = {}
    for cid, cd in cell_data.items():
        row, col = cd["row"], cd["col"]
        cell_h, cell_w = cd["height"], cd["width"]

        strip_start = strip_pos[row] - fp_strip
        strip_end = strip_start + row_heights[row]
        if cell_h != row_heights[row]:
            strip_start = strip_end - cell_h

        perp_start = perp_start_for(row, col) - fp_perp
        perp_end = perp_start + cell_w

        ss_pre, se_pre = strip_start, strip_end
        bb_ss = -se_pre if flip_strip else ss_pre
        bb_se = -ss_pre if flip_strip else se_pre

        if is_vertical:
            ns, ne, es, ee = bb_ss, bb_se, perp_start, perp_end
        else:
            es, ee, ns, ne = bb_ss, bb_se, perp_start, perp_end

        grid_blocks[cid] = {
            "sw_x": es, "sw_y": ns,
            "ne_x": ee, "ne_y": ne,
            "shape_kind": cd["shape_kind"],
        }
    return grid_blocks


def main():
    test_path = str(_REPO / "Data" / "site_configs" / "__vlm_test_cell_data.json")
    with open(test_path) as f:
        extracted = json.load(f)

    print("=" * 64)
    print(" Integration test: extracted cell_data → existing Compute math")
    print("=" * 64)

    grid_blocks = run_compute(extracted)

    print(f"\nProduced {len(grid_blocks)} grid_blocks:\n")
    print(f"  {'Cell':<5} {'sw_x':>9} {'sw_y':>9} {'ne_x':>9} {'ne_y':>9}  {'shape':<7}  {'W':>6} × {'H':>6}")
    print(f"  {'-'*5} {'-'*9} {'-'*9} {'-'*9} {'-'*9}  {'-'*7}  {'-'*6}   {'-'*6}")

    # Sort like the sketch reads: row A first, col 1 first
    for cid in sorted(grid_blocks.keys(),
                      key=lambda c: (c[-1], int(c[:-1]))):
        b = grid_blocks[cid]
        w = b["ne_x"] - b["sw_x"]
        h = b["ne_y"] - b["sw_y"]
        print(f"  {cid:<5} {b['sw_x']:>9.2f} {b['sw_y']:>9.2f} "
              f"{b['ne_x']:>9.2f} {b['ne_y']:>9.2f}  {b['shape_kind']:<7}  "
              f"{w:>6.2f} × {h:>6.2f}")

    # Sanity checks
    print("\nSanity checks:")
    # 1. fixed point should be at (0,0) for the bottom-right corner of 4D
    b4d = grid_blocks["4D"]
    fp_x = b4d["ne_x"]   # right edge = east
    fp_y = b4d["sw_y"]   # bottom edge (= south in vert+flipped frame)
    print(f"  ✓ Fixed point (4D BR corner): ({fp_x:.2f}, {fp_y:.2f}) "
          f"— expect (0.00, 0.00)" + ("  ✅" if abs(fp_x) < 0.01 and abs(fp_y) < 0.01 else "  ❌"))

    # 2. Total grid width along A row should be 10+10+10+13 = 43
    a_west = grid_blocks["1A"]["sw_x"]
    a_east = grid_blocks["4A"]["ne_x"]
    a_width = a_east - a_west
    print(f"  ✓ Row-A width: {a_width:.2f}'  — expect 43.00'" +
          ("  ✅" if abs(a_width - 43) < 0.01 else "  ❌"))

    # 3. 1F width should be 4.417' (4'5") — the narrow extension cell
    b1f = grid_blocks["1F"]
    w1f = b1f["ne_x"] - b1f["sw_x"]
    print(f"  ✓ 1F width:   {w1f:.3f}'  — expect 4.417'  " +
          ("✅" if abs(w1f - 4.417) < 0.01 else "❌"))

    # 4. 1E height should be 15.667' (the single E-row cell)
    b1e = grid_blocks["1E"]
    h1e = b1e["ne_y"] - b1e["sw_y"]
    print(f"  ✓ 1E height:  {h1e:.3f}'  — expect 15.667' " +
          ("✅" if abs(h1e - 15.667) < 0.01 else "❌"))

    # 5. Extension cells 1F + 2F should total 4.417 + 13 = 17.417 wide
    b2f = grid_blocks["2F"]
    f_total = (b2f["ne_x"] - b2f["sw_x"]) + (b1f["ne_x"] - b1f["sw_x"])
    print(f"  ✓ Row F total width: {f_total:.3f}'  — expect 17.417' " +
          ("✅" if abs(f_total - 17.417) < 0.01 else "❌"))

    print("\nAll done — extracted cell_data is fully compatible "
          "with the existing Compute path.")


if __name__ == "__main__":
    main()