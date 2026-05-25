"""Unit tests for shape_editor.classify_polygon.

Verifies that arbitrary polygons returned by the JS drag editor are
correctly classified into rect/angle/notch/custom.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Skip the streamlit import by stubbing the module.
from types import ModuleType
class _Stub(ModuleType):
    def __getattr__(self, name):
        if name == "components":
            mod = ModuleType("components")
            mod.v1 = ModuleType("v1")
            mod.v1.html = lambda *a, **kw: None
            return mod
        return lambda *a, **kw: None
sys.modules["streamlit"] = _Stub("streamlit")
sys.modules["streamlit.components.v1"] = sys.modules["streamlit"].components.v1

from vlm_extractor.shape_editor import classify_polygon  # noqa: E402


def test(label, expected_kind, expected_params, width, height, points,
         extra_check=None):
    result = classify_polygon(width, height, points)
    ok = result["shape_kind"] == expected_kind
    msg = f"  {'✅' if ok else '❌'} {label}: got {result['shape_kind']!r}"
    if not ok:
        msg += f" (expected {expected_kind!r})"
    print(msg)
    if expected_kind != "custom" and expected_params and result["shape_kind"] == expected_kind:
        for k, v in expected_params.items():
            actual = result["shape_params"].get(k)
            if isinstance(v, (int, float)) and isinstance(actual, (int, float)):
                close = abs(float(actual) - float(v)) < 0.05
            else:
                close = actual == v
            sub_ok = close
            sub_msg = f"      {'✅' if sub_ok else '❌'} {k}: got {actual!r}"
            if not sub_ok:
                sub_msg += f" (expected {v!r})"
            print(sub_msg)
    if extra_check:
        extra_check(result)


def main():
    print("─" * 60)
    print(" classify_polygon — rect cases")
    print("─" * 60)
    test("plain 10×10 rect", "rect", None,
         10, 10,
         [[0,0],[10,0],[10,10],[0,10]])
    test("plain 13×14 rect (extension cell sized)", "rect", None,
         13, 14,
         [[0,0],[13,0],[13,14],[0,14]])

    print("\n─── classify_polygon — single-corner angle cases ───")
    test("TL moved right along top edge → angle L, inset_far=6",
         "angle", {"side": "L", "inset_near": 0, "inset_far": 6.0},
         10, 14,
         [[0,0],[10,0],[10,14],[6,14]])
    test("TR moved left along top edge → angle R, inset_far=6",
         "angle", {"side": "R", "inset_near": 0, "inset_far": 6.0},
         10, 14,
         [[0,0],[10,0],[4,14],[0,14]])
    test("BL moved up along left edge → angle B, inset_near=3",
         "angle", {"side": "B", "inset_near": 3.0, "inset_far": 0},
         10, 14,
         [[0,3],[10,0],[10,14],[0,14]])
    test("TL moved down along left edge → angle T, inset_near=3",
         "angle", {"side": "T", "inset_near": 3.0, "inset_far": 0},
         10, 14,
         [[0,0],[10,0],[10,14],[0,11]])

    print("\n─── classify_polygon — two-corner angle (full edge slant) ───")
    test("Top edge slanted (TL and TR both pulled down) → angle T",
         "angle", {"side": "T", "inset_near": 2.0, "inset_far": 5.0},
         13, 14,
         [[0,0],[13,0],[13,9],[0,12]])
    test("Bottom edge slanted (BL and BR pulled up) → angle B",
         "angle", {"side": "B", "inset_near": 1.5, "inset_far": 3.0},
         10, 14,
         [[0,1.5],[10,3],[10,14],[0,14]])

    print("\n─── classify_polygon — notch cases ───")
    test("TL notch 2×1.5 → notch corner=TL",
         "notch", {"corner": "TL", "notch_w": 2.0, "notch_h": 1.5},
         10, 14,
         [[0,0],[10,0],[10,14],[2,12.5]])
    test("BR notch 3×2 → notch corner=BR",
         "notch", {"corner": "BR", "notch_w": 3.0, "notch_h": 2.0},
         10, 14,
         [[0,0],[7,2],[10,14],[0,14]])

    print("\n─── classify_polygon — custom (no parametric match) ───")
    test("3 corners moved → custom",
         "custom", None,
         10, 14,
         [[1,1],[9,1],[10,14],[0,14]],
         extra_check=lambda r: print(
             f"      {'✅' if r.get('local_polygon') else '❌'} "
             f"local_polygon present: {bool(r.get('local_polygon'))}"
         ))

    print("\n─── classify_polygon — the 3F case from your sketch ───")
    # 3F: 4.417' × 14', angle on top edge, inset_far=6.0 on the right
    # i.e. TL stays at (0,14), TR pulled down to (4.417, 14-6) = (4.417, 8)
    test("3F: top edge slanted, TR pulled down by 6'",
         "angle", {"side": "T", "inset_near": 0, "inset_far": 6.0},
         4.417, 14,
         [[0,0],[4.417,0],[4.417,8],[0,14]])

    print("\n✓ Done.")


if __name__ == "__main__":
    main()