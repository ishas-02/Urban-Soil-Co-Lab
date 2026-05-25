# """Unit tests for the schema validator.

# Covers the kinds of malformed responses a VLM might produce so we can
# catch them BEFORE they hit Streamlit.
# """

# import sys
# from pathlib import Path

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# from vlm_extractor.schema import (
#     normalize_extraction,
#     to_cell_data,
#     validate_extraction,
# )


# def _expect(ok_expected: bool, problems_should_contain: list[str],
#             data: dict, label: str):
#     ok, problems = validate_extraction(data)
#     status = "✅" if ok == ok_expected else "❌"
#     print(f"  {status} {label}")
#     print(f"      expected ok={ok_expected}, got ok={ok}")
#     if problems:
#         print(f"      problems ({len(problems)}):")
#         for p in problems[:5]:
#             print(f"        • {p}")
#         if len(problems) > 5:
#             print(f"        … {len(problems) - 5} more")
#     for needle in problems_should_contain:
#         if not any(needle.lower() in p.lower() for p in problems):
#             print(f"      ❌ expected '{needle}' in problems but didn't find it")


# def good_minimal():
#     return normalize_extraction({
#         "rows": ["A"],
#         "ncols_per_row": {"A": 1},
#         "max_cols": 1,
#         "cells": {
#             "1A": {"width": 10.0, "height": 10.0, "row": "A", "col": 1},
#         },
#     })


# def main():
#     print("=" * 60)
#     print(" Schema validator unit tests")
#     print("=" * 60)

#     print("\n[good cases]")
#     _expect(True, [], good_minimal(), "minimal valid extraction (1×1)")

#     # L-extension with non-contiguous cells
#     l_ext = normalize_extraction({
#         "rows": ["A", "B"],
#         "ncols_per_row": {"A": 3, "B": 1},
#         "max_cols": 3,
#         "cells": {
#             "1A": {"width": 10, "height": 10, "row": "A", "col": 1},
#             "2A": {"width": 10, "height": 10, "row": "A", "col": 2},
#             "3A": {"width": 10, "height": 10, "row": "A", "col": 3},
#             "1B": {"width": 10, "height": 10, "row": "B", "col": 1},
#         },
#     })
#     _expect(True, [], l_ext, "L-extension (row B has only col 1)")

#     # Cell with shape_kind=custom + valid polygon
#     custom_poly = normalize_extraction({
#         "rows": ["A"],
#         "ncols_per_row": {"A": 1},
#         "max_cols": 1,
#         "cells": {
#             "1A": {
#                 "width": 10, "height": 10, "row": "A", "col": 1,
#                 "shape_kind": "custom",
#                 "local_polygon": [[0, 0], [10, 0], [10, 5], [5, 5], [5, 10], [0, 10]],
#             },
#         },
#     })
#     _expect(True, [], custom_poly, "custom polygon (L-shape) on a single cell")

#     print("\n[bad cases the validator must catch]")

#     # Missing top-level keys
#     _expect(False, ["missing"], {}, "completely empty extraction")
#     _expect(False, ["missing"], {"rows": ["A"]}, "missing ncols/cells/max_cols")

#     # row letter wrong format
#     bad_row_letter = normalize_extraction({
#         "rows": ["AA"], "ncols_per_row": {"AA": 1}, "max_cols": 1,
#         "cells": {"1AA": {"width": 10, "height": 10, "row": "AA", "col": 1}},
#     })
#     _expect(False, ["single uppercase letter"], bad_row_letter,
#             "multi-letter row name 'AA' (should be single letter)")

#     # cell key/col mismatch
#     mismatch = normalize_extraction({
#         "rows": ["A"], "ncols_per_row": {"A": 2}, "max_cols": 2,
#         "cells": {
#             "1A": {"width": 10, "height": 10, "row": "A", "col": 2},   # bad!
#         },
#     })
#     _expect(False, ["key says col=1 but"], mismatch,
#             "cell key '1A' but col=2 in body")

#     # col exceeds ncols_per_row
#     overflow = normalize_extraction({
#         "rows": ["A"], "ncols_per_row": {"A": 2}, "max_cols": 2,
#         "cells": {
#             "5A": {"width": 10, "height": 10, "row": "A", "col": 5},
#         },
#     })
#     _expect(False, ["exceeds"], overflow,
#             "cell '5A' with ncols_per_row['A']=2")

#     # max_cols too small
#     max_cols_wrong = normalize_extraction({
#         "rows": ["A"], "ncols_per_row": {"A": 5}, "max_cols": 2,
#         "cells": {
#             "1A": {"width": 10, "height": 10, "row": "A", "col": 1},
#             "2A": {"width": 10, "height": 10, "row": "A", "col": 2},
#             "3A": {"width": 10, "height": 10, "row": "A", "col": 3},
#             "4A": {"width": 10, "height": 10, "row": "A", "col": 4},
#             "5A": {"width": 10, "height": 10, "row": "A", "col": 5},
#         },
#     })
#     _expect(False, ["max_cols"], max_cols_wrong,
#             "max_cols=2 but ncols_per_row says 5")

#     # custom shape missing polygon
#     no_poly = normalize_extraction({
#         "rows": ["A"], "ncols_per_row": {"A": 1}, "max_cols": 1,
#         "cells": {
#             "1A": {
#                 "width": 10, "height": 10, "row": "A", "col": 1,
#                 "shape_kind": "custom",   # but no local_polygon set
#             },
#         },
#     })
#     _expect(False, ["local_polygon"], no_poly,
#             "shape_kind=custom without local_polygon")

#     # bogus shape_kind
#     bad_shape = normalize_extraction({
#         "rows": ["A"], "ncols_per_row": {"A": 1}, "max_cols": 1,
#         "cells": {
#             "1A": {
#                 "width": 10, "height": 10, "row": "A", "col": 1,
#                 "shape_kind": "circle",   # not supported
#             },
#         },
#     })
#     _expect(False, ["unknown shape_kind"], bad_shape,
#             "shape_kind='circle' (unsupported)")

#     print("\n[to_cell_data smoke test]")
#     cd = to_cell_data(l_ext, yard_choice="Front")
#     expected_keys = {"1A", "2A", "3A", "1B"}
#     if set(cd.keys()) == expected_keys:
#         print(f"  ✅ to_cell_data produced exactly the expected cells: {sorted(cd.keys())}")
#     else:
#         print(f"  ❌ unexpected cells: {sorted(cd.keys())}")
#     for cid, cell in cd.items():
#         if cell["pattern"] != f"Front_{cid}_":
#             print(f"  ❌ {cid}: pattern is '{cell['pattern']}', expected 'Front_{cid}_'")
#             break
#     else:
#         print(f"  ✅ All cells got correct default 'Front_<id>_' pattern")

#     print("\nDone.")


# if __name__ == "__main__":
#     main()

"""Unit tests for the schema validator.

Covers the kinds of malformed responses a VLM might produce so we can
catch them BEFORE they hit Streamlit.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlm_extractor.schema import (
    normalize_extraction,
    to_cell_data,
    validate_extraction,
)


def _expect(ok_expected: bool, problems_should_contain: list[str],
            data: dict, label: str):
    ok, problems = validate_extraction(data)
    status = "✅" if ok == ok_expected else "❌"
    print(f"  {status} {label}")
    print(f"      expected ok={ok_expected}, got ok={ok}")
    if problems:
        print(f"      problems ({len(problems)}):")
        for p in problems[:5]:
            print(f"        • {p}")
        if len(problems) > 5:
            print(f"        … {len(problems) - 5} more")
    for needle in problems_should_contain:
        if not any(needle.lower() in p.lower() for p in problems):
            print(f"      ❌ expected '{needle}' in problems but didn't find it")


def good_minimal():
    return normalize_extraction({
        "rows": ["A"],
        "ncols_per_row": {"A": 1},
        "max_cols": 1,
        "cells": {
            "A1": {"width": 10.0, "height": 10.0, "row": "A", "col": 1},
        },
    })


def main():
    print("=" * 60)
    print(" Schema validator unit tests")
    print("=" * 60)

    print("\n[good cases]")
    _expect(True, [], good_minimal(), "minimal valid extraction (1×1)")

    # L-extension with non-contiguous cells
    l_ext = normalize_extraction({
        "rows": ["A", "B"],
        "ncols_per_row": {"A": 3, "B": 1},
        "max_cols": 3,
        "cells": {
            "A1": {"width": 10, "height": 10, "row": "A", "col": 1},
            "A2": {"width": 10, "height": 10, "row": "A", "col": 2},
            "A3": {"width": 10, "height": 10, "row": "A", "col": 3},
            "B1": {"width": 10, "height": 10, "row": "B", "col": 1},
        },
    })
    _expect(True, [], l_ext, "L-extension (row B has only col 1)")

    # Cell with shape_kind=custom + valid polygon
    custom_poly = normalize_extraction({
        "rows": ["A"],
        "ncols_per_row": {"A": 1},
        "max_cols": 1,
        "cells": {
            "A1": {
                "width": 10, "height": 10, "row": "A", "col": 1,
                "shape_kind": "custom",
                "local_polygon": [[0, 0], [10, 0], [10, 5], [5, 5], [5, 10], [0, 10]],
            },
        },
    })
    _expect(True, [], custom_poly, "custom polygon (L-shape) on a single cell")

    print("\n[bad cases the validator must catch]")

    # Missing top-level keys
    _expect(False, ["missing"], {}, "completely empty extraction")
    _expect(False, ["missing"], {"rows": ["A"]}, "missing ncols/cells/max_cols")

    # row letter wrong format
    bad_row_letter = normalize_extraction({
        "rows": ["AA"], "ncols_per_row": {"AA": 1}, "max_cols": 1,
        "cells": {"AA1": {"width": 10, "height": 10, "row": "AA", "col": 1}},
    })
    _expect(False, ["single uppercase letter"], bad_row_letter,
            "multi-letter row name 'AA' (should be single letter)")

    # cell key/col mismatch
    mismatch = normalize_extraction({
        "rows": ["A"], "ncols_per_row": {"A": 2}, "max_cols": 2,
        "cells": {
            "A1": {"width": 10, "height": 10, "row": "A", "col": 2},   # bad!
        },
    })
    _expect(False, ["key says col=1 but"], mismatch,
            "cell key 'A1' but col=2 in body")

    # col exceeds ncols_per_row
    overflow = normalize_extraction({
        "rows": ["A"], "ncols_per_row": {"A": 2}, "max_cols": 2,
        "cells": {
            "A5": {"width": 10, "height": 10, "row": "A", "col": 5},
        },
    })
    _expect(False, ["exceeds"], overflow,
            "cell 'A5' with ncols_per_row['A']=2")

    # max_cols too small
    max_cols_wrong = normalize_extraction({
        "rows": ["A"], "ncols_per_row": {"A": 5}, "max_cols": 2,
        "cells": {
            "A1": {"width": 10, "height": 10, "row": "A", "col": 1},
            "A2": {"width": 10, "height": 10, "row": "A", "col": 2},
            "A3": {"width": 10, "height": 10, "row": "A", "col": 3},
            "A4": {"width": 10, "height": 10, "row": "A", "col": 4},
            "A5": {"width": 10, "height": 10, "row": "A", "col": 5},
        },
    })
    _expect(False, ["max_cols"], max_cols_wrong,
            "max_cols=2 but ncols_per_row says 5")

    # custom shape missing polygon
    no_poly = normalize_extraction({
        "rows": ["A"], "ncols_per_row": {"A": 1}, "max_cols": 1,
        "cells": {
            "A1": {
                "width": 10, "height": 10, "row": "A", "col": 1,
                "shape_kind": "custom",   # but no local_polygon set
            },
        },
    })
    _expect(False, ["local_polygon"], no_poly,
            "shape_kind=custom without local_polygon")

    # bogus shape_kind
    bad_shape = normalize_extraction({
        "rows": ["A"], "ncols_per_row": {"A": 1}, "max_cols": 1,
        "cells": {
            "A1": {
                "width": 10, "height": 10, "row": "A", "col": 1,
                "shape_kind": "circle",   # not supported
            },
        },
    })
    _expect(False, ["unknown shape_kind"], bad_shape,
            "shape_kind='circle' (unsupported)")

    print("\n[to_cell_data smoke test]")
    cd = to_cell_data(l_ext, yard_choice="Front")
    expected_keys = {"A1", "A2", "A3", "B1"}
    if set(cd.keys()) == expected_keys:
        print(f"  ✅ to_cell_data produced exactly the expected cells: {sorted(cd.keys())}")
    else:
        print(f"  ❌ unexpected cells: {sorted(cd.keys())}")
    # Pattern should use sketch_label (defaulting to col-first)
    expected_a1_pat = "Front_1A_"   # sketch_label defaults to '1A' for cell 'A1'
    if cd["A1"]["pattern"] == expected_a1_pat:
        print(f"  ✅ pattern uses sketch_label: {cd['A1']['pattern']!r}")
    else:
        print(f"  ❌ A1 pattern is {cd['A1']['pattern']!r}, expected {expected_a1_pat!r}")

    print("\nDone.")


if __name__ == "__main__":
    main()