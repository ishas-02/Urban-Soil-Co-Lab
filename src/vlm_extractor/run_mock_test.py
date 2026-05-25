# # """Mock VLM response for the example sketch.

# # Stand-in for a real Gemini/Claude API call when no API key is
# # available. The JSON below is exactly the shape ``providers.py`` would
# # return after parsing a real response — careful read of the field-
# # worker's sketch.

# # Run with:  python run_mock_test.py
# # """

# # import json
# # import os
# # import sys
# # from pathlib import Path

# # # Make the vlm_extractor package importable from sibling location,
# # # regardless of where the script is invoked from.
# # _HERE = Path(__file__).resolve().parent          # .../src/vlm_extractor
# # _SRC  = _HERE.parent                              # .../src
# # _REPO = _SRC.parent                               # .../Soil Co-Lab
# # sys.path.insert(0, str(_SRC))

# # from vlm_extractor.schema import (
# #     normalize_extraction,
# #     to_cell_data,
# #     validate_extraction,
# # )


# # # This is the exact JSON a well-prompted VLM should produce for the
# # # example sketch in /mnt/user-data/uploads/2025-05-15_SiteMapHanddrawn.jpeg
# # #
# # # Reading from the sketch:
# # #   - Top widths:     10' | 10' | 10' | 13'   (cols 1–4)
# # #   - Left heights:   10' | 10' | 10' | 13'   (rows A–D)
# # #   - Right edge of extension: 15'8" | 14' | 13'8"  (rows E,F,G)
# # #     These are 4E, 4F, 4G heights — but they also visually look like
# # #     the column-4 extension heights. So row heights E,F,G = those.
# # #   - Bottom of extension under col 3: 4'5" wide  (cells 3F, 3G)
# # #   - There's a walkway between D-row and E/F/G with an angled boundary
# # #     that pinches the top of 3F → modelled as `angle` on cell 3F's
# # #     top side (T), or as a row_gap_below["D"] if we treat it as flat.
# # #   - 4E sits only under col 4 (no 3E in the sketch).
# # #   - The bottom-left ramp of the extension (between 4G and main grid)
# # #     is drawn with a notch — handled as an L-shape on 3F via "angle".
# # #
# # # Per cell, cells with shadow or partial occlusion are flagged "medium".

# # MOCK_VLM_RESPONSE = {
# #     "rows": ["A", "B", "C", "D", "E", "F", "G"],
# #     "ncols_per_row": {
# #         # Extension rows restart column numbering at 1 (matches the
# #         # existing site_builder.py convention — each extension row is
# #         # its OWN strip). E has 1 cell, F and G have 2 each.
# #         "A": 4, "B": 4, "C": 4, "D": 4,
# #         "E": 1, "F": 2, "G": 2,
# #     },
# #     "row_gap_below": {
# #         "A": 0.0, "B": 0.0, "C": 0.0,
# #         "D": 0.0, "E": 0.0, "F": 0.0, "G": 0.0,
# #     },
# #     "max_cols": 4,
# #     "cells": {
# #         # ── Main 4×4 grid: rows A,B,C are 10'×10', row D is 13' tall.
# #         #    Column widths 10,10,10,13 — column 4 is the wider one. ──
# #         "1A": {"width": 10.0, "height": 10.0, "row": "A", "col": 1, "shape_kind": "rect", "confidence": "high"},
# #         "2A": {"width": 10.0, "height": 10.0, "row": "A", "col": 2, "shape_kind": "rect", "confidence": "high"},
# #         "3A": {"width": 10.0, "height": 10.0, "row": "A", "col": 3, "shape_kind": "rect", "confidence": "high"},
# #         "4A": {"width": 13.0, "height": 10.0, "row": "A", "col": 4, "shape_kind": "rect", "confidence": "high"},

# #         "1B": {"width": 10.0, "height": 10.0, "row": "B", "col": 1, "shape_kind": "rect", "confidence": "high"},
# #         "2B": {"width": 10.0, "height": 10.0, "row": "B", "col": 2, "shape_kind": "rect", "confidence": "high"},
# #         "3B": {"width": 10.0, "height": 10.0, "row": "B", "col": 3, "shape_kind": "rect", "confidence": "high"},
# #         "4B": {"width": 13.0, "height": 10.0, "row": "B", "col": 4, "shape_kind": "rect", "confidence": "high"},

# #         "1C": {"width": 10.0, "height": 10.0, "row": "C", "col": 1, "shape_kind": "rect", "confidence": "high"},
# #         "2C": {"width": 10.0, "height": 10.0, "row": "C", "col": 2, "shape_kind": "rect", "confidence": "high"},
# #         "3C": {"width": 10.0, "height": 10.0, "row": "C", "col": 3, "shape_kind": "rect", "confidence": "high"},
# #         "4C": {"width": 13.0, "height": 10.0, "row": "C", "col": 4, "shape_kind": "rect", "confidence": "high"},

# #         "1D": {"width": 10.0, "height": 13.0, "row": "D", "col": 1, "shape_kind": "rect", "confidence": "high"},
# #         "2D": {"width": 10.0, "height": 13.0, "row": "D", "col": 2, "shape_kind": "rect", "confidence": "high"},
# #         "3D": {"width": 10.0, "height": 13.0, "row": "D", "col": 3, "shape_kind": "rect", "confidence": "high"},
# #         "4D": {"width": 13.0, "height": 13.0, "row": "D", "col": 4, "shape_kind": "rect", "confidence": "high"},

# #         # ── Extension rows: column numbering restarts at 1. ──
# #         # 1E: the only E-row cell (visually under main col 4 — width 13')
# #         "1E": {
# #             "width": 13.0, "height": 15.0 + 8/12,
# #             "row": "E", "col": 1, "shape_kind": "rect",
# #             "confidence": "high",
# #             "notes": "single E-row cell — width 13' matches col 4 of main grid; height 15'8\""
# #         },

# #         # 1F: narrow cell, 4'5" wide. Angled top edge closes off the
# #         # walkway between D-row and the extension.
# #         "1F": {
# #             "width": 4.0 + 5/12, "height": 14.0,
# #             "row": "F", "col": 1,
# #             "shape_kind": "angle",
# #             "shape_params": {
# #                 "side": "T",                # top edge is slanted
# #                 "inset_near": 0.0,          # left end of top edge — flush
# #                 "inset_far": 6.0,           # right end pulled INTO the cell
# #             },
# #             "confidence": "medium",
# #             "notes": "Top edge angled — closes off walkway between D-row and extension. inset_far is approximate; please verify."
# #         },
# #         "2F": {
# #             "width": 13.0, "height": 14.0,
# #             "row": "F", "col": 2, "shape_kind": "rect",
# #             "confidence": "high",
# #             "notes": "dimension 14' read from right edge"
# #         },

# #         "1G": {
# #             "width": 4.0 + 5/12, "height": 13.0 + 8/12,
# #             "row": "G", "col": 1, "shape_kind": "rect",
# #             "confidence": "medium",
# #             "notes": "narrow extension cell — bottom-left corner of sketch is shadowed"
# #         },
# #         "2G": {
# #             "width": 13.0, "height": 13.0 + 8/12,
# #             "row": "G", "col": 2, "shape_kind": "rect",
# #             "confidence": "high"
# #         },
# #     },
# #     "global_notes": (
# #         "Single yard, 4-col main grid (A–D) with a partial extension "
# #         "(E,F,G) on the right side. The walkway between D-row and "
# #         "the extension is approximated; verify by overlay. Site code "
# #         "'PITT' and date '2026-05-15' visible at bottom of page "
# #         "(written upside-down) — these are NOT extracted into grid."
# #     ),
# #     "overall_confidence": "medium",
# # }


# # def main():
# #     print("=" * 64)
# #     print(" Mock VLM extraction test — example sketch")
# #     print(" (Real Gemini/Claude call would produce this same shape)")
# #     print("=" * 64)

# #     # Step 1: normalize (fill in defaults)
# #     print("\n[1] Normalizing extraction (filling in default keys)…")
# #     normalized = normalize_extraction(MOCK_VLM_RESPONSE)
# #     print(f"    ✓ Normalized {len(normalized['cells'])} cells")

# #     # Step 2: validate against schema
# #     print("\n[2] Validating against schema…")
# #     ok, problems = validate_extraction(normalized)
# #     if ok:
# #         print("    ✓ All structural checks pass")
# #     else:
# #         print(f"    ✗ {len(problems)} problems:")
# #         for p in problems:
# #             print(f"        • {p}")
# #         sys.exit(1)

# #     # Step 3: convert to cell_data shape that site_builder.py consumes
# #     print("\n[3] Converting to site_builder.py `cell_data` format…")
# #     yard_choice = "Back"   # would come from the Streamlit dropdown
# #     cell_data = to_cell_data(normalized, yard_choice=yard_choice)
# #     print(f"    ✓ Produced cell_data for yard '{yard_choice}'")

# #     # Step 4: pretty-print the cell_data so we can eyeball it
# #     print("\n[4] Per-cell breakdown:")
# #     print()
# #     print(f"    {'Cell':<5} {'Width':>8} {'Height':>8} {'Shape':<7} "
# #           f"{'Conf':<7} Pattern")
# #     print(f"    {'-'*5} {'-'*8} {'-'*8} {'-'*7} {'-'*7} {'-'*30}")
# #     for cid in sorted(cell_data.keys(),
# #                       key=lambda x: (normalized["cells"][x]["row"],
# #                                      normalized["cells"][x]["col"])):
# #         cd = cell_data[cid]
# #         conf = normalized["cells"][cid].get("confidence", "?")
# #         w_str = f"{cd['width']:.2f}'"
# #         h_str = f"{cd['height']:.2f}'"
# #         shape = cd["shape_kind"]
# #         if shape == "angle":
# #             params = cd["shape_params"]
# #             shape = f"angle·{params.get('side','?')}"
# #         print(f"    {cid:<5} {w_str:>8} {h_str:>8} {shape:<7} "
# #               f"{conf:<7} {cd['pattern']}")

# #     # Step 5: low-confidence cells the review UI should flag
# #     print("\n[5] Cells to flag for human review:")
# #     low_or_med = [
# #         (cid, c.get("confidence", "?"), c.get("notes", ""))
# #         for cid, c in normalized["cells"].items()
# #         if c.get("confidence") in ("medium", "low")
# #     ]
# #     if not low_or_med:
# #         print("    (none — VLM was confident about everything)")
# #     else:
# #         for cid, conf, note in sorted(low_or_med):
# #             marker = "🟡" if conf == "medium" else "🔴"
# #             print(f"    {marker} {cid} [{conf}]: {note or '(no note)'}")

# #     print(f"\n[6] Overall confidence: {normalized['overall_confidence']}")
# #     print(f"    Global notes: {normalized.get('global_notes', '')[:200]}")

# #     # Step 6: dump the cell_data so the next stage (Chunk 2 UI) can
# #     # consume it.
# #     out_path = str(_REPO / "Data" / "site_configs" / "__vlm_test_cell_data.json")
# #     os.makedirs(os.path.dirname(out_path), exist_ok=True)
# #     with open(out_path, "w") as f:
# #         json.dump({
# #             "yard_choice": yard_choice,
# #             "rows": normalized["rows"],
# #             "ncols_per_row": normalized["ncols_per_row"],
# #             "row_gap_below": normalized["row_gap_below"],
# #             "max_cols": normalized["max_cols"],
# #             "cell_data": cell_data,
# #             "_review_metadata": {
# #                 cid: {
# #                     "confidence": c.get("confidence", "medium"),
# #                     "notes": c.get("notes", ""),
# #                 }
# #                 for cid, c in normalized["cells"].items()
# #             },
# #             "_global": {
# #                 "overall_confidence": normalized["overall_confidence"],
# #                 "global_notes": normalized.get("global_notes", ""),
# #             },
# #         }, f, indent=2)
# #     print(f"\n[7] Wrote intermediate result for Chunk 2 (review UI):")
# #     print(f"    {out_path}")
# #     print(f"\n✓ Pipeline complete — cell_data is ready for site_builder.py")


# # if __name__ == "__main__":
# #     main()

# """Mock VLM response for the example sketch.

# Stand-in for a real Gemini/Claude API call when no API key is
# available. The JSON below is exactly the shape ``providers.py`` would
# return after parsing a real response — careful read of the field-
# worker's sketch.

# Run with:  python run_mock_test.py
# """

# import json
# import os
# import sys
# from pathlib import Path

# # Make the vlm_extractor package importable from sibling location,
# # regardless of where the script is invoked from.
# _HERE = Path(__file__).resolve().parent          # .../src/vlm_extractor
# _SRC  = _HERE.parent                              # .../src
# _REPO = _SRC.parent                               # .../Soil Co-Lab
# sys.path.insert(0, str(_SRC))

# from vlm_extractor.schema import (
#     normalize_extraction,
#     to_cell_data,
#     validate_extraction,
# )


# # This is the exact JSON a well-prompted VLM should produce for the
# # example sketch in /mnt/user-data/uploads/2025-05-15_SiteMapHanddrawn.jpeg
# #
# # Reading from the sketch:
# #   - Top widths:     10' | 10' | 10' | 13'   (cols 1–4)
# #   - Left heights:   10' | 10' | 10' | 13'   (rows A–D)
# #   - Right edge of extension: 15'8" | 14' | 13'8"  (rows E,F,G)
# #     These are 4E, 4F, 4G heights — but they also visually look like
# #     the column-4 extension heights. So row heights E,F,G = those.
# #   - Bottom of extension under col 3: 4'5" wide  (cells 3F, 3G)
# #   - There's a walkway between D-row and E/F/G with an angled boundary
# #     that pinches the top of 3F → modelled as `angle` on cell 3F's
# #     top side (T), or as a row_gap_below["D"] if we treat it as flat.
# #   - 4E sits only under col 4 (no 3E in the sketch).
# #   - The bottom-left ramp of the extension (between 4G and main grid)
# #     is drawn with a notch — handled as an L-shape on 3F via "angle".
# #
# # Per cell, cells with shadow or partial occlusion are flagged "medium".

# MOCK_VLM_RESPONSE = {
#     "rows": ["A", "B", "C", "D", "E", "F", "G"],
#     "ncols_per_row": {
#         # Extension rows restart column numbering at 1 (matches the
#         # existing site_builder.py convention — each extension row is
#         # its OWN strip). E has 1 cell, F and G have 2 each.
#         "A": 4, "B": 4, "C": 4, "D": 4,
#         "E": 1, "F": 2, "G": 2,
#     },
#     "row_gap_below": {
#         "A": 0.0, "B": 0.0, "C": 0.0,
#         "D": 0.0, "E": 0.0, "F": 0.0, "G": 0.0,
#     },
#     "max_cols": 4,
#     "cells": {
#         # ── Main 4×4 grid: rows A,B,C are 10'×10', row D is 13' tall.
#         #    Cell IDs are <row><col> internally. sketch_label preserves
#         #    what the field worker wrote (typically column-first). ──
#         "A1": {"width": 10.0, "height": 10.0, "row": "A", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1A"},
#         "A2": {"width": 10.0, "height": 10.0, "row": "A", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2A"},
#         "A3": {"width": 10.0, "height": 10.0, "row": "A", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3A"},
#         "A4": {"width": 13.0, "height": 10.0, "row": "A", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4A"},

#         "B1": {"width": 10.0, "height": 10.0, "row": "B", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1B"},
#         "B2": {"width": 10.0, "height": 10.0, "row": "B", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2B"},
#         "B3": {"width": 10.0, "height": 10.0, "row": "B", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3B"},
#         "B4": {"width": 13.0, "height": 10.0, "row": "B", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4B"},

#         "C1": {"width": 10.0, "height": 10.0, "row": "C", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1C"},
#         "C2": {"width": 10.0, "height": 10.0, "row": "C", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2C"},
#         "C3": {"width": 10.0, "height": 10.0, "row": "C", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3C"},
#         "C4": {"width": 13.0, "height": 10.0, "row": "C", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4C"},

#         "D1": {"width": 10.0, "height": 13.0, "row": "D", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1D"},
#         "D2": {"width": 10.0, "height": 13.0, "row": "D", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2D"},
#         "D3": {"width": 10.0, "height": 13.0, "row": "D", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3D"},
#         "D4": {"width": 13.0, "height": 13.0, "row": "D", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4D"},

#         # ── Extension rows: column numbering restarts at 1 internally,
#         #    but sketch_label preserves the original col-3/col-4 labels. ──
#         "E1": {
#             "width": 13.0, "height": 15.0 + 8/12,
#             "row": "E", "col": 1, "shape_kind": "rect",
#             "confidence": "high",
#             "sketch_label": "4E",
#             "notes": "single E-row cell — height 15'8\""
#         },

#         # F1: narrow cell, 4'5" wide. Angled top edge.
#         "F1": {
#             "width": 4.0 + 5/12, "height": 14.0,
#             "row": "F", "col": 1,
#             "shape_kind": "angle",
#             "shape_params": {
#                 "side": "T",                # top edge is slanted
#                 "inset_near": 0.0,
#                 "inset_far": 6.0,
#             },
#             "confidence": "medium",
#             "sketch_label": "3F",
#             "notes": "Top edge angled — closes off walkway between D-row and extension."
#         },
#         "F2": {
#             "width": 13.0, "height": 14.0,
#             "row": "F", "col": 2, "shape_kind": "rect",
#             "confidence": "high",
#             "sketch_label": "4F",
#         },

#         "G1": {
#             "width": 4.0 + 5/12, "height": 13.0 + 8/12,
#             "row": "G", "col": 1, "shape_kind": "rect",
#             "confidence": "medium",
#             "sketch_label": "3G",
#             "notes": "narrow extension cell — bottom-left corner shadowed"
#         },
#         "G2": {
#             "width": 13.0, "height": 13.0 + 8/12,
#             "row": "G", "col": 2, "shape_kind": "rect",
#             "confidence": "high",
#             "sketch_label": "4G",
#         },
#     },
#     "global_notes": (
#         "Single yard, 4-col main grid (A–D) with a partial extension "
#         "(E,F,G) on the right side. The walkway between D-row and "
#         "the extension is approximated; verify by overlay. Site code "
#         "'PITT' and date '2026-05-15' visible at bottom of page "
#         "(written upside-down) — these are NOT extracted into grid."
#     ),
#     "overall_confidence": "medium",
# }


# def main():
#     print("=" * 64)
#     print(" Mock VLM extraction test — example sketch")
#     print(" (Real Gemini/Claude call would produce this same shape)")
#     print("=" * 64)

#     # Step 1: normalize (fill in defaults)
#     print("\n[1] Normalizing extraction (filling in default keys)…")
#     normalized = normalize_extraction(MOCK_VLM_RESPONSE)
#     print(f"    ✓ Normalized {len(normalized['cells'])} cells")

#     # Step 2: validate against schema
#     print("\n[2] Validating against schema…")
#     ok, problems = validate_extraction(normalized)
#     if ok:
#         print("    ✓ All structural checks pass")
#     else:
#         print(f"    ✗ {len(problems)} problems:")
#         for p in problems:
#             print(f"        • {p}")
#         sys.exit(1)

#     # Step 3: convert to cell_data shape that site_builder.py consumes
#     print("\n[3] Converting to site_builder.py `cell_data` format…")
#     yard_choice = "Back"   # would come from the Streamlit dropdown
#     cell_data = to_cell_data(normalized, yard_choice=yard_choice)
#     print(f"    ✓ Produced cell_data for yard '{yard_choice}'")

#     # Step 4: pretty-print the cell_data so we can eyeball it
#     print("\n[4] Per-cell breakdown:")
#     print()
#     print(f"    {'Cell':<5} {'Width':>8} {'Height':>8} {'Shape':<7} "
#           f"{'Conf':<7} Pattern")
#     print(f"    {'-'*5} {'-'*8} {'-'*8} {'-'*7} {'-'*7} {'-'*30}")
#     for cid in sorted(cell_data.keys(),
#                       key=lambda x: (normalized["cells"][x]["row"],
#                                      normalized["cells"][x]["col"])):
#         cd = cell_data[cid]
#         conf = normalized["cells"][cid].get("confidence", "?")
#         w_str = f"{cd['width']:.2f}'"
#         h_str = f"{cd['height']:.2f}'"
#         shape = cd["shape_kind"]
#         if shape == "angle":
#             params = cd["shape_params"]
#             shape = f"angle·{params.get('side','?')}"
#         print(f"    {cid:<5} {w_str:>8} {h_str:>8} {shape:<7} "
#               f"{conf:<7} {cd['pattern']}")

#     # Step 5: low-confidence cells the review UI should flag
#     print("\n[5] Cells to flag for human review:")
#     low_or_med = [
#         (cid, c.get("confidence", "?"), c.get("notes", ""))
#         for cid, c in normalized["cells"].items()
#         if c.get("confidence") in ("medium", "low")
#     ]
#     if not low_or_med:
#         print("    (none — VLM was confident about everything)")
#     else:
#         for cid, conf, note in sorted(low_or_med):
#             marker = "🟡" if conf == "medium" else "🔴"
#             print(f"    {marker} {cid} [{conf}]: {note or '(no note)'}")

#     print(f"\n[6] Overall confidence: {normalized['overall_confidence']}")
#     print(f"    Global notes: {normalized.get('global_notes', '')[:200]}")

#     # Step 6: dump the cell_data so the next stage (Chunk 2 UI) can
#     # consume it.
#     out_path = str(_REPO / "Data" / "site_configs" / "__vlm_test_cell_data.json")
#     os.makedirs(os.path.dirname(out_path), exist_ok=True)
#     with open(out_path, "w") as f:
#         json.dump({
#             "yard_choice": yard_choice,
#             "rows": normalized["rows"],
#             "ncols_per_row": normalized["ncols_per_row"],
#             "row_gap_below": normalized["row_gap_below"],
#             "max_cols": normalized["max_cols"],
#             "cell_data": cell_data,
#             "_review_metadata": {
#                 cid: {
#                     "confidence": c.get("confidence", "medium"),
#                     "notes": c.get("notes", ""),
#                 }
#                 for cid, c in normalized["cells"].items()
#             },
#             "_global": {
#                 "overall_confidence": normalized["overall_confidence"],
#                 "global_notes": normalized.get("global_notes", ""),
#             },
#         }, f, indent=2)
#     print(f"\n[7] Wrote intermediate result for Chunk 2 (review UI):")
#     print(f"    {out_path}")
#     print(f"\n✓ Pipeline complete — cell_data is ready for site_builder.py")


# if __name__ == "__main__":
#     main()

"""Mock VLM response for the example sketch.

Stand-in for a real Gemini/Claude API call when no API key is
available. The JSON below is exactly the shape ``providers.py`` would
return after parsing a real response — careful read of the field-
worker's sketch.

Run with:  python run_mock_test.py
"""

import json
import os
import sys
from pathlib import Path

# Make the vlm_extractor package importable from sibling location,
# regardless of where the script is invoked from.
_HERE = Path(__file__).resolve().parent          # .../src/vlm_extractor
_SRC  = _HERE.parent                              # .../src
_REPO = _SRC.parent                               # .../Soil Co-Lab
sys.path.insert(0, str(_SRC))

from vlm_extractor.schema import (
    normalize_extraction,
    to_cell_data,
    validate_extraction,
)


# This is the exact JSON a well-prompted VLM should produce for the
# example sketch in /mnt/user-data/uploads/2025-05-15_SiteMapHanddrawn.jpeg
#
# Reading from the sketch:
#   - Top widths:     10' | 10' | 10' | 13'   (cols 1–4)
#   - Left heights:   10' | 10' | 10' | 13'   (rows A–D)
#   - Right edge of extension: 15'8" | 14' | 13'8"  (rows E,F,G)
#     These are 4E, 4F, 4G heights — but they also visually look like
#     the column-4 extension heights. So row heights E,F,G = those.
#   - Bottom of extension under col 3: 4'5" wide  (cells 3F, 3G)
#   - There's a walkway between D-row and E/F/G with an angled boundary
#     that pinches the top of 3F → modelled as `angle` on cell 3F's
#     top side (T), or as a row_gap_below["D"] if we treat it as flat.
#   - 4E sits only under col 4 (no 3E in the sketch).
#   - The bottom-left ramp of the extension (between 4G and main grid)
#     is drawn with a notch — handled as an L-shape on 3F via "angle".
#
# Per cell, cells with shadow or partial occlusion are flagged "medium".

MOCK_VLM_RESPONSE = {
    "rows": ["A", "B", "C", "D", "E", "F", "G"],
    "ncols_per_row": {
        # ncols_per_row = the HIGHEST column number that row reaches.
        # Extension rows E/F/G have cells at cols 3 and/or 4 (matching
        # the sketch's "4E", "3F", "4F", etc.) — they all "reach" col 4.
        "A": 4, "B": 4, "C": 4, "D": 4,
        "E": 4, "F": 4, "G": 4,
    },
    "row_gap_below": {
        "A": 0.0, "B": 0.0, "C": 0.0,
        "D": 0.0, "E": 0.0, "F": 0.0, "G": 0.0,
    },
    "max_cols": 4,
    "cells": {
        # ── Main 4×4 grid: rows A,B,C are 10'×10', row D is 13' tall.
        #    Cell keys are <row><col>. sketch_label = col-first form. ──
        "A1": {"width": 10.0, "height": 10.0, "row": "A", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1A"},
        "A2": {"width": 10.0, "height": 10.0, "row": "A", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2A"},
        "A3": {"width": 10.0, "height": 10.0, "row": "A", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3A"},
        "A4": {"width": 13.0, "height": 10.0, "row": "A", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4A"},

        "B1": {"width": 10.0, "height": 10.0, "row": "B", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1B"},
        "B2": {"width": 10.0, "height": 10.0, "row": "B", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2B"},
        "B3": {"width": 10.0, "height": 10.0, "row": "B", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3B"},
        "B4": {"width": 13.0, "height": 10.0, "row": "B", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4B"},

        "C1": {"width": 10.0, "height": 10.0, "row": "C", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1C"},
        "C2": {"width": 10.0, "height": 10.0, "row": "C", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2C"},
        "C3": {"width": 10.0, "height": 10.0, "row": "C", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3C"},
        "C4": {"width": 13.0, "height": 10.0, "row": "C", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4C"},

        "D1": {"width": 10.0, "height": 13.0, "row": "D", "col": 1, "shape_kind": "rect", "confidence": "high", "sketch_label": "1D"},
        "D2": {"width": 10.0, "height": 13.0, "row": "D", "col": 2, "shape_kind": "rect", "confidence": "high", "sketch_label": "2D"},
        "D3": {"width": 10.0, "height": 13.0, "row": "D", "col": 3, "shape_kind": "rect", "confidence": "high", "sketch_label": "3D"},
        "D4": {"width": 13.0, "height": 13.0, "row": "D", "col": 4, "shape_kind": "rect", "confidence": "high", "sketch_label": "4D"},

        # ── Extension rows: column numbers MATCH the sketch.
        #    E has only col 4 ("4E"). F has cols 3 & 4 ("3F", "4F").
        #    G has cols 3 & 4 ("3G", "4G"). ──
        "E4": {
            "width": 13.0, "height": 15.0 + 8/12,
            "row": "E", "col": 4, "shape_kind": "rect",
            "confidence": "high",
            "sketch_label": "4E",
            "notes": "single E-row cell — height 15'8\""
        },

        # F3: narrow cell, 4'5" wide. Angled top edge.
        "F3": {
            "width": 4.0 + 5/12, "height": 14.0,
            "row": "F", "col": 3,
            "shape_kind": "angle",
            "shape_params": {
                "side": "T",
                "inset_near": 0.0,
                "inset_far": 6.0,
            },
            "confidence": "medium",
            "sketch_label": "3F",
            "notes": "Top edge angled — closes off walkway between D-row and extension."
        },
        "F4": {
            "width": 13.0, "height": 14.0,
            "row": "F", "col": 4, "shape_kind": "rect",
            "confidence": "high",
            "sketch_label": "4F",
        },

        "G3": {
            "width": 4.0 + 5/12, "height": 13.0 + 8/12,
            "row": "G", "col": 3, "shape_kind": "rect",
            "confidence": "medium",
            "sketch_label": "3G",
            "notes": "narrow extension cell — bottom-left corner shadowed"
        },
        "G4": {
            "width": 13.0, "height": 13.0 + 8/12,
            "row": "G", "col": 4, "shape_kind": "rect",
            "confidence": "high",
            "sketch_label": "4G",
        },
    },
    "global_notes": (
        "Single yard, 4-col main grid (A–D) with a partial extension "
        "(E,F,G) on the right side. The walkway between D-row and "
        "the extension is approximated; verify by overlay. Site code "
        "'PITT' and date '2026-05-15' visible at bottom of page "
        "(written upside-down) — these are NOT extracted into grid."
    ),
    "overall_confidence": "medium",
}


def main():
    print("=" * 64)
    print(" Mock VLM extraction test — example sketch")
    print(" (Real Gemini/Claude call would produce this same shape)")
    print("=" * 64)

    # Step 1: normalize (fill in defaults)
    print("\n[1] Normalizing extraction (filling in default keys)…")
    normalized = normalize_extraction(MOCK_VLM_RESPONSE)
    print(f"    ✓ Normalized {len(normalized['cells'])} cells")

    # Step 2: validate against schema
    print("\n[2] Validating against schema…")
    ok, problems = validate_extraction(normalized)
    if ok:
        print("    ✓ All structural checks pass")
    else:
        print(f"    ✗ {len(problems)} problems:")
        for p in problems:
            print(f"        • {p}")
        sys.exit(1)

    # Step 3: convert to cell_data shape that site_builder.py consumes
    print("\n[3] Converting to site_builder.py `cell_data` format…")
    yard_choice = "Back"   # would come from the Streamlit dropdown
    cell_data = to_cell_data(normalized, yard_choice=yard_choice)
    print(f"    ✓ Produced cell_data for yard '{yard_choice}'")

    # Step 4: pretty-print the cell_data so we can eyeball it
    print("\n[4] Per-cell breakdown:")
    print()
    print(f"    {'Cell':<5} {'Width':>8} {'Height':>8} {'Shape':<7} "
          f"{'Conf':<7} Pattern")
    print(f"    {'-'*5} {'-'*8} {'-'*8} {'-'*7} {'-'*7} {'-'*30}")
    for cid in sorted(cell_data.keys(),
                      key=lambda x: (normalized["cells"][x]["row"],
                                     normalized["cells"][x]["col"])):
        cd = cell_data[cid]
        conf = normalized["cells"][cid].get("confidence", "?")
        w_str = f"{cd['width']:.2f}'"
        h_str = f"{cd['height']:.2f}'"
        shape = cd["shape_kind"]
        if shape == "angle":
            params = cd["shape_params"]
            shape = f"angle·{params.get('side','?')}"
        print(f"    {cid:<5} {w_str:>8} {h_str:>8} {shape:<7} "
              f"{conf:<7} {cd['pattern']}")

    # Step 5: low-confidence cells the review UI should flag
    print("\n[5] Cells to flag for human review:")
    low_or_med = [
        (cid, c.get("confidence", "?"), c.get("notes", ""))
        for cid, c in normalized["cells"].items()
        if c.get("confidence") in ("medium", "low")
    ]
    if not low_or_med:
        print("    (none — VLM was confident about everything)")
    else:
        for cid, conf, note in sorted(low_or_med):
            marker = "🟡" if conf == "medium" else "🔴"
            print(f"    {marker} {cid} [{conf}]: {note or '(no note)'}")

    print(f"\n[6] Overall confidence: {normalized['overall_confidence']}")
    print(f"    Global notes: {normalized.get('global_notes', '')[:200]}")

    # Step 6: dump the cell_data so the next stage (Chunk 2 UI) can
    # consume it.
    out_path = str(_REPO / "Data" / "site_configs" / "__vlm_test_cell_data.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "yard_choice": yard_choice,
            "rows": normalized["rows"],
            "ncols_per_row": normalized["ncols_per_row"],
            "row_gap_below": normalized["row_gap_below"],
            "max_cols": normalized["max_cols"],
            "cell_data": cell_data,
            "_review_metadata": {
                cid: {
                    "confidence": c.get("confidence", "medium"),
                    "notes": c.get("notes", ""),
                }
                for cid, c in normalized["cells"].items()
            },
            "_global": {
                "overall_confidence": normalized["overall_confidence"],
                "global_notes": normalized.get("global_notes", ""),
            },
        }, f, indent=2)
    print(f"\n[7] Wrote intermediate result for Chunk 2 (review UI):")
    print(f"    {out_path}")
    print(f"\n✓ Pipeline complete — cell_data is ready for site_builder.py")


if __name__ == "__main__":
    main()