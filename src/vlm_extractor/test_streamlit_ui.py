# # """Smoke test for streamlit_ui._apply_to_session_state.

# # Bypasses the Streamlit dependency by mocking st.session_state as a
# # plain dict, so we can verify the session-state write contract
# # without needing to launch Streamlit.

# # What this proves:
# #   - All the keys site_builder.py expects DO get written
# #   - Feet/inches split is correct (e.g. 15.667 → ft=15, in=8.0)
# #   - Shape-specific params (notch corner, angle side, custom polygon)
# #     are routed to the right keys
# #   - L-extension rows with missing cells don't error
# # """

# # import sys
# # from pathlib import Path
# # from types import ModuleType

# # # ── Mock the `streamlit` module so streamlit_ui can be imported ──
# # class _MockStreamlit(ModuleType):
# #     """Minimal Streamlit stand-in for offline import."""
# #     def __init__(self):
# #         super().__init__("streamlit")
# #         self.session_state: dict = {}
# #     def __getattr__(self, name):
# #         # Any other attribute (st.button, st.markdown, etc.) becomes a no-op
# #         def _noop(*a, **kw):
# #             return None
# #         return _noop


# # _st = _MockStreamlit()
# # sys.modules["streamlit"] = _st

# # # Now we can import streamlit_ui normally.
# # _HERE = Path(__file__).resolve().parent
# # _SRC = _HERE.parent
# # sys.path.insert(0, str(_SRC))

# # from vlm_extractor.schema import normalize_extraction  # noqa: E402
# # from vlm_extractor.streamlit_ui import _apply_to_session_state  # noqa: E402


# # def main():
# #     print("=" * 60)
# #     print(" Smoke test: _apply_to_session_state")
# #     print("=" * 60)

# #     # Build a representative extraction — the same shape Chunk 1
# #     # produces from the example sketch.
# #     extraction = normalize_extraction({
# #         "rows": ["A", "B", "C", "D", "E", "F", "G"],
# #         "ncols_per_row": {"A": 4, "B": 4, "C": 4, "D": 4,
# #                           "E": 1, "F": 2, "G": 2},
# #         "row_gap_below": {"D": 0.5},
# #         "max_cols": 4,
# #         "cells": {
# #             # Main grid (just two cells of A row, for brevity)
# #             "1A": {"width": 10.0, "height": 10.0,
# #                    "row": "A", "col": 1, "shape_kind": "rect"},
# #             "4D": {"width": 13.0, "height": 13.0,
# #                    "row": "D", "col": 4, "shape_kind": "rect"},
# #             # Single extension cell with the trickier 15'8" dimension
# #             "1E": {"width": 13.0, "height": 15.0 + 8/12,
# #                    "row": "E", "col": 1, "shape_kind": "rect",
# #                    "confidence": "high"},
# #             # Angle shape on extension's narrow cell
# #             "1F": {"width": 4.0 + 5/12, "height": 14.0,
# #                    "row": "F", "col": 1,
# #                    "shape_kind": "angle",
# #                    "shape_params": {"side": "T",
# #                                     "inset_near": 0.0,
# #                                     "inset_far": 6.0}},
# #             # Notch shape (synthetic, not in the example sketch)
# #             "2F": {"width": 13.0, "height": 14.0,
# #                    "row": "F", "col": 2,
# #                    "shape_kind": "notch",
# #                    "shape_params": {"corner": "BR",
# #                                     "notch_w": 2.0,
# #                                     "notch_h": 1.5}},
# #             # Custom polygon (synthetic)
# #             "1G": {"width": 4.0 + 5/12, "height": 13.0 + 8/12,
# #                    "row": "G", "col": 1,
# #                    "shape_kind": "custom",
# #                    "local_polygon": [[0, 0], [4.42, 0], [4.42, 13.67],
# #                                      [2, 13.67], [0, 10]]},
# #             "2G": {"width": 13.0, "height": 13.0 + 8/12,
# #                    "row": "G", "col": 2, "shape_kind": "rect",
# #                    "is_walkway": True, "gap_right": 1.5},
# #         },
# #     })

# #     yard_key = "back"
# #     _st.session_state.clear()
# #     n_written, warnings = _apply_to_session_state(extraction, yard_key)

# #     print(f"\n[1] Wrote {n_written} keys, {len(warnings)} warnings")
# #     if warnings:
# #         for w in warnings:
# #             print(f"    ⚠️  {w}")

# #     ss = _st.session_state

# #     def _check(key, expected, label):
# #         actual = ss.get(key)
# #         ok = actual == expected
# #         emoji = "✅" if ok else "❌"
# #         print(f"    {emoji} {label:.<40} {key} = {actual!r}  (expected {expected!r})")
# #         return ok

# #     print("\n[2] Top-level grid keys:")
# #     _check("rows_back", "A, B, C, D, E, F, G", "rows comma-string")
# #     _check("max_cols_back", 4, "max_cols")
# #     _check("ncols_A_back", 4, "ncols for row A")
# #     _check("ncols_F_back", 2, "ncols for row F (L-extension)")

# #     print("\n[3] Feet/inches split for 15'8\" extension cell (1E height):")
# #     _check("h_1E_back__ft", 15, "1E height feet part")
# #     _check("h_1E_back__in", 8.0, "1E height inches part")

# #     print("\n[4] Feet/inches split for 4'5\" narrow cell (1F width):")
# #     _check("w_1F_back__ft", 4, "1F width feet part")
# #     _check("w_1F_back__in", 5.0, "1F width inches part")

# #     print("\n[5] Shape kind + params for angle cell (1F):")
# #     _check("shapekind_1F_back", "angle", "1F shape_kind")
# #     _check("angle_side_1F_back", "T", "1F angle side")
# #     _check("angle_near_1F_back__ft", 0, "1F angle inset_near feet")
# #     _check("angle_far_1F_back__ft", 6, "1F angle inset_far feet")
# #     _check("angle_far_1F_back__in", 0.0, "1F angle inset_far inches")

# #     print("\n[6] Shape kind + params for notch cell (2F):")
# #     _check("shapekind_2F_back", "notch", "2F shape_kind")
# #     _check("notch_corner_2F_back", "BR", "2F notch corner")
# #     _check("notch_w_2F_back__ft", 2, "2F notch_w feet")
# #     _check("notch_h_2F_back__ft", 1, "2F notch_h feet")
# #     _check("notch_h_2F_back__in", 6.0, "2F notch_h inches (0.5 = 6\")")

# #     print("\n[7] Custom polygon (1G):")
# #     _check("shapekind_1G_back", "custom", "1G shape_kind")
# #     poly_text = ss.get("poly_1G_back", "")
# #     has_all_pts = (
# #         "0.00,0.00" in poly_text and "4.42,0.00" in poly_text
# #         and "0.00,10.00" in poly_text
# #     )
# #     print(f"    {'✅' if has_all_pts else '❌'} 1G polygon text contains all vertices")
# #     print(f"        poly_1G_back = {poly_text!r}")

# #     print("\n[8] Walkway flag and gap_right (2G):")
# #     _check("walkway_2G_back", True, "2G is_walkway flag")
# #     _check("gapr_2G_back__ft", 1, "2G gap_right feet")
# #     _check("gapr_2G_back__in", 6.0, "2G gap_right inches (0.5 = 6\")")

# #     print("\n[9] Row gap below D (0.5 feet):")
# #     _check("rowgap_D_back__ft", 0, "row gap D feet part")
# #     _check("rowgap_D_back__in", 6.0, "row gap D inches part (0.5 = 6\")")

# #     print("\n[10] Sample-ID pattern uses yard prefix:")
# #     _check("pat_1A_back", "Back_1A_", "1A pattern")
# #     _check("pat_1F_back", "Back_1F_", "1F pattern")

# #     print("\n[11] Front and back share key namespace properly (front keys absent):")
# #     _check("rows_front", None, "no rows_front (we only wrote back)")
# #     _check("w_1A_front__ft", None, "no w_1A_front (we only wrote back)")

# #     print("\n✓ Smoke test complete.")


# # if __name__ == "__main__":
# #     main()

# """Smoke test for streamlit_ui._apply_to_session_state.

# Bypasses the Streamlit dependency by mocking st.session_state as a
# plain dict, so we can verify the session-state write contract
# without needing to launch Streamlit.

# What this proves:
#   - All the keys site_builder.py expects DO get written
#   - Feet/inches split is correct (e.g. 15.667 → ft=15, in=8.0)
#   - Shape-specific params (notch corner, angle side, custom polygon)
#     are routed to the right keys
#   - L-extension rows with missing cells don't error
# """

# import sys
# from pathlib import Path
# from types import ModuleType

# # ── Mock the `streamlit` module so streamlit_ui can be imported ──
# class _MockStreamlit(ModuleType):
#     """Minimal Streamlit stand-in for offline import."""
#     def __init__(self):
#         super().__init__("streamlit")
#         self.session_state: dict = {}
#     def __getattr__(self, name):
#         # Any other attribute (st.button, st.markdown, etc.) becomes a no-op
#         def _noop(*a, **kw):
#             return None
#         return _noop


# _st = _MockStreamlit()
# sys.modules["streamlit"] = _st

# # Now we can import streamlit_ui normally.
# _HERE = Path(__file__).resolve().parent
# _SRC = _HERE.parent
# sys.path.insert(0, str(_SRC))

# from vlm_extractor.schema import normalize_extraction  # noqa: E402
# from vlm_extractor.streamlit_ui import _apply_to_session_state  # noqa: E402


# def main():
#     print("=" * 60)
#     print(" Smoke test: _apply_to_session_state")
#     print("=" * 60)

#     # Build a representative extraction — the same shape Chunk 1
#     # produces from the example sketch.
#     extraction = normalize_extraction({
#         "rows": ["A", "B", "C", "D", "E", "F", "G"],
#         "ncols_per_row": {"A": 4, "B": 4, "C": 4, "D": 4,
#                           "E": 1, "F": 2, "G": 2},
#         "row_gap_below": {"D": 0.5},
#         "max_cols": 4,
#         "cells": {
#             # Main grid (just two cells of A row, for brevity)
#             "A1": {"width": 10.0, "height": 10.0,
#                    "row": "A", "col": 1, "shape_kind": "rect",
#                    "sketch_label": "1A"},
#             "D4": {"width": 13.0, "height": 13.0,
#                    "row": "D", "col": 4, "shape_kind": "rect",
#                    "sketch_label": "4D"},
#             # Single extension cell with the trickier 15'8" dimension
#             "E1": {"width": 13.0, "height": 15.0 + 8/12,
#                    "row": "E", "col": 1, "shape_kind": "rect",
#                    "confidence": "high", "sketch_label": "4E"},
#             # Angle shape on extension's narrow cell
#             "F1": {"width": 4.0 + 5/12, "height": 14.0,
#                    "row": "F", "col": 1,
#                    "shape_kind": "angle",
#                    "shape_params": {"side": "T",
#                                     "inset_near": 0.0,
#                                     "inset_far": 6.0},
#                    "sketch_label": "3F"},
#             # Notch shape (synthetic, not in the example sketch)
#             "F2": {"width": 13.0, "height": 14.0,
#                    "row": "F", "col": 2,
#                    "shape_kind": "notch",
#                    "shape_params": {"corner": "BR",
#                                     "notch_w": 2.0,
#                                     "notch_h": 1.5},
#                    "sketch_label": "4F"},
#             # Custom polygon (synthetic)
#             "G1": {"width": 4.0 + 5/12, "height": 13.0 + 8/12,
#                    "row": "G", "col": 1,
#                    "shape_kind": "custom",
#                    "local_polygon": [[0, 0], [4.42, 0], [4.42, 13.67],
#                                      [2, 13.67], [0, 10]],
#                    "sketch_label": "3G"},
#             "G2": {"width": 13.0, "height": 13.0 + 8/12,
#                    "row": "G", "col": 2, "shape_kind": "rect",
#                    "is_walkway": True, "gap_right": 1.5,
#                    "sketch_label": "4G"},
#         },
#     })

#     yard_key = "back"
#     _st.session_state.clear()
#     n_written, warnings = _apply_to_session_state(extraction, yard_key)

#     print(f"\n[1] Wrote {n_written} keys, {len(warnings)} warnings")
#     if warnings:
#         for w in warnings:
#             print(f"    ⚠️  {w}")

#     ss = _st.session_state

#     def _check(key, expected, label):
#         actual = ss.get(key)
#         ok = actual == expected
#         emoji = "✅" if ok else "❌"
#         print(f"    {emoji} {label:.<40} {key} = {actual!r}  (expected {expected!r})")
#         return ok

#     print("\n[2] Top-level grid keys:")
#     _check("rows_back", "A, B, C, D, E, F, G", "rows comma-string")
#     _check("max_cols_back", 4, "max_cols")
#     _check("ncols_A_back", 4, "ncols for row A")
#     _check("ncols_F_back", 2, "ncols for row F (L-extension)")

#     print("\n[3] Feet/inches split for 15'8\" extension cell (E1 height):")
#     _check("h_E1_back__ft", 15, "E1 height feet part")
#     _check("h_E1_back__in", 8.0, "E1 height inches part")

#     print("\n[4] Feet/inches split for 4'5\" narrow cell (F1 width):")
#     _check("w_F1_back__ft", 4, "F1 width feet part")
#     _check("w_F1_back__in", 5.0, "F1 width inches part")

#     print("\n[5] Shape kind + params for angle cell (F1):")
#     _check("shapekind_F1_back", "angle", "F1 shape_kind")
#     _check("angle_side_F1_back", "T", "F1 angle side")
#     _check("angle_near_F1_back__ft", 0, "F1 angle inset_near feet")
#     _check("angle_far_F1_back__ft", 6, "F1 angle inset_far feet")
#     _check("angle_far_F1_back__in", 0.0, "F1 angle inset_far inches")

#     print("\n[6] Shape kind + params for notch cell (F2):")
#     _check("shapekind_F2_back", "notch", "F2 shape_kind")
#     _check("notch_corner_F2_back", "BR", "F2 notch corner")
#     _check("notch_w_F2_back__ft", 2, "F2 notch_w feet")
#     _check("notch_h_F2_back__ft", 1, "F2 notch_h feet")
#     _check("notch_h_F2_back__in", 6.0, "F2 notch_h inches (0.5 = 6\")")

#     print("\n[7] Custom polygon (G1):")
#     _check("shapekind_G1_back", "custom", "G1 shape_kind")
#     poly_text = ss.get("poly_G1_back", "")
#     has_all_pts = (
#         "0.00,0.00" in poly_text and "4.42,0.00" in poly_text
#         and "0.00,10.00" in poly_text
#     )
#     print(f"    {'✅' if has_all_pts else '❌'} G1 polygon text contains all vertices")
#     print(f"        poly_G1_back = {poly_text!r}")

#     print("\n[8] Walkway flag and gap_right (G2):")
#     _check("walkway_G2_back", True, "G2 is_walkway flag")
#     _check("gapr_G2_back__ft", 1, "G2 gap_right feet")
#     _check("gapr_G2_back__in", 6.0, "G2 gap_right inches (0.5 = 6\")")

#     print("\n[9] Row gap below D (0.5 feet):")
#     _check("rowgap_D_back__ft", 0, "row gap D feet part")
#     _check("rowgap_D_back__in", 6.0, "row gap D inches part (0.5 = 6\")")

#     print("\n[10] Sample-ID pattern uses SKETCH LABEL (not internal ID):")
#     _check("pat_A1_back", "Back_1A_", "A1 pattern uses '1A' from sketch")
#     _check("pat_F1_back", "Back_3F_", "F1 pattern uses '3F' from sketch")
#     _check("pat_E1_back", "Back_4E_", "E1 pattern uses '4E' from sketch")
#     _check("pat_G1_back", "Back_3G_", "G1 pattern uses '3G' from sketch")

#     print("\n[11] Front and back share key namespace properly (front keys absent):")
#     _check("rows_front", None, "no rows_front (we only wrote back)")
#     _check("w_A1_front__ft", None, "no w_A1_front (we only wrote back)")

#     print("\n✓ Smoke test complete.")


# if __name__ == "__main__":
#     main()

"""Smoke test for streamlit_ui._apply_to_session_state.

Bypasses the Streamlit dependency by mocking st.session_state as a
plain dict, so we can verify the session-state write contract
without needing to launch Streamlit.

What this proves:
  - All the keys site_builder.py expects DO get written
  - Feet/inches split is correct (e.g. 15.667 → ft=15, in=8.0)
  - Shape-specific params (notch corner, angle side, custom polygon)
    are routed to the right keys
  - L-extension rows with missing cells don't error
"""

import sys
from pathlib import Path
from types import ModuleType

# ── Mock the `streamlit` module so streamlit_ui can be imported ──
class _MockStreamlit(ModuleType):
    """Minimal Streamlit stand-in for offline import."""
    def __init__(self):
        super().__init__("streamlit")
        self.session_state: dict = {}
    def __getattr__(self, name):
        # Any other attribute (st.button, st.markdown, etc.) becomes a no-op
        def _noop(*a, **kw):
            return None
        return _noop


_st = _MockStreamlit()
sys.modules["streamlit"] = _st

# Now we can import streamlit_ui normally.
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent
sys.path.insert(0, str(_SRC))

from vlm_extractor.schema import normalize_extraction  # noqa: E402
from vlm_extractor.streamlit_ui import _apply_to_session_state  # noqa: E402


def main():
    print("=" * 60)
    print(" Smoke test: _apply_to_session_state")
    print("=" * 60)

    # Build a representative extraction — the same shape Chunk 1
    # produces from the example sketch.
    extraction = normalize_extraction({
        "rows": ["A", "B", "C", "D", "E", "F", "G"],
        "ncols_per_row": {"A": 4, "B": 4, "C": 4, "D": 4,
                          "E": 4, "F": 4, "G": 4},
        "row_gap_below": {"D": 0.5},
        "max_cols": 4,
        "cells": {
            # Main grid (just two cells of A row, for brevity)
            "A1": {"width": 10.0, "height": 10.0,
                   "row": "A", "col": 1, "shape_kind": "rect",
                   "sketch_label": "1A"},
            "D4": {"width": 13.0, "height": 13.0,
                   "row": "D", "col": 4, "shape_kind": "rect",
                   "sketch_label": "4D"},
            # Single extension cell with the trickier 15'8" dimension
            "E4": {"width": 13.0, "height": 15.0 + 8/12,
                   "row": "E", "col": 4, "shape_kind": "rect",
                   "confidence": "high", "sketch_label": "4E"},
            # Angle shape on extension's narrow cell
            "F3": {"width": 4.0 + 5/12, "height": 14.0,
                   "row": "F", "col": 3,
                   "shape_kind": "angle",
                   "shape_params": {"side": "T",
                                    "inset_near": 0.0,
                                    "inset_far": 6.0},
                   "sketch_label": "3F"},
            # Notch shape (synthetic, not in the example sketch)
            "F4": {"width": 13.0, "height": 14.0,
                   "row": "F", "col": 4,
                   "shape_kind": "notch",
                   "shape_params": {"corner": "BR",
                                    "notch_w": 2.0,
                                    "notch_h": 1.5},
                   "sketch_label": "4F"},
            # Custom polygon (synthetic)
            "G3": {"width": 4.0 + 5/12, "height": 13.0 + 8/12,
                   "row": "G", "col": 3,
                   "shape_kind": "custom",
                   "local_polygon": [[0, 0], [4.42, 0], [4.42, 13.67],
                                     [2, 13.67], [0, 10]],
                   "sketch_label": "3G"},
            "G4": {"width": 13.0, "height": 13.0 + 8/12,
                   "row": "G", "col": 4, "shape_kind": "rect",
                   "is_walkway": True, "gap_right": 1.5,
                   "sketch_label": "4G"},
        },
    })

    yard_key = "back"
    _st.session_state.clear()
    n_written, warnings = _apply_to_session_state(extraction, yard_key)

    print(f"\n[1] Wrote {n_written} keys, {len(warnings)} warnings")
    if warnings:
        for w in warnings:
            print(f"    ⚠️  {w}")

    ss = _st.session_state

    def _check(key, expected, label):
        actual = ss.get(key)
        ok = actual == expected
        emoji = "✅" if ok else "❌"
        print(f"    {emoji} {label:.<40} {key} = {actual!r}  (expected {expected!r})")
        return ok

    print("\n[2] Top-level grid keys:")
    _check("rows_back", "A, B, C, D, E, F, G", "rows comma-string")
    _check("max_cols_back", 4, "max_cols")
    _check("ncols_A_back", 4, "ncols for row A")
    _check("ncols_F_back", 4, "ncols for row F (reaches col 4)")

    print("\n[3] Feet/inches split for 15'8\" extension cell (E4 height):")
    _check("h_E4_back__ft", 15, "E4 height feet part")
    _check("h_E4_back__in", 8.0, "E4 height inches part")

    print("\n[4] Feet/inches split for 4'5\" narrow cell (F3 width):")
    _check("w_F3_back__ft", 4, "F3 width feet part")
    _check("w_F3_back__in", 5.0, "F3 width inches part")

    print("\n[5] Shape kind + params for angle cell (F3):")
    _check("shapekind_F3_back", "angle", "F3 shape_kind")
    _check("angle_side_F3_back", "T", "F3 angle side")
    _check("angle_near_F3_back__ft", 0, "F3 angle inset_near feet")
    _check("angle_far_F3_back__ft", 6, "F3 angle inset_far feet")
    _check("angle_far_F3_back__in", 0.0, "F3 angle inset_far inches")

    print("\n[6] Shape kind + params for notch cell (F4):")
    _check("shapekind_F4_back", "notch", "F4 shape_kind")
    _check("notch_corner_F4_back", "BR", "F4 notch corner")
    _check("notch_w_F4_back__ft", 2, "F4 notch_w feet")
    _check("notch_h_F4_back__ft", 1, "F4 notch_h feet")
    _check("notch_h_F4_back__in", 6.0, "F4 notch_h inches (0.5 = 6\")")

    print("\n[7] Custom polygon (G3):")
    _check("shapekind_G3_back", "custom", "G3 shape_kind")
    poly_text = ss.get("poly_G3_back", "")
    has_all_pts = (
        "0.00,0.00" in poly_text and "4.42,0.00" in poly_text
        and "0.00,10.00" in poly_text
    )
    print(f"    {'✅' if has_all_pts else '❌'} G3 polygon text contains all vertices")
    print(f"        poly_G3_back = {poly_text!r}")

    print("\n[8] Walkway flag and gap_right (G4):")
    _check("walkway_G4_back", True, "G4 is_walkway flag")
    _check("gapr_G4_back__ft", 1, "G4 gap_right feet")
    _check("gapr_G4_back__in", 6.0, "G4 gap_right inches (0.5 = 6\")")

    print("\n[9] Row gap below D (0.5 feet):")
    _check("rowgap_D_back__ft", 0, "row gap D feet part")
    _check("rowgap_D_back__in", 6.0, "row gap D inches part (0.5 = 6\")")

    print("\n[10] Sample-ID pattern uses SKETCH LABEL (not internal ID):")
    _check("pat_A1_back", "Back_1A_", "A1 pattern uses '1A' from sketch")
    _check("pat_F3_back", "Back_3F_", "F3 pattern uses '3F' from sketch")
    _check("pat_E4_back", "Back_4E_", "E4 pattern uses '4E' from sketch")
    _check("pat_G3_back", "Back_3G_", "G3 pattern uses '3G' from sketch")

    print("\n[11] Front and back share key namespace properly (front keys absent):")
    _check("rows_front", None, "no rows_front (we only wrote back)")
    _check("w_A1_front__ft", None, "no w_A1_front (we only wrote back)")

    print("\n✓ Smoke test complete.")


if __name__ == "__main__":
    main()