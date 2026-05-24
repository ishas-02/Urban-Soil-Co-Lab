"""Test harness: run the VLM extractor against the example sketch.

This bypasses the Streamlit UI entirely — it's the smallest possible
end-to-end test that proves the prompt + schema + parsing path work.
"""

import json
import os
import sys
from pathlib import Path

# Make the vlm_extractor package importable from its sibling location.
_HERE = Path(__file__).resolve().parent          # .../src/vlm_extractor
_SRC  = _HERE.parent                              # .../src
_REPO = _SRC.parent                               # .../Soil Co-Lab
sys.path.insert(0, str(_SRC))

from vlm_extractor import extract_from_image, to_cell_data
from vlm_extractor.schema import validate_extraction


def main():
    # Point this at any sketch image on your machine. CLI override:
    #   python3 run_test.py /path/to/sketch.jpg
    if len(sys.argv) > 1:
        sketch = sys.argv[1]
    else:
        # Default: look in the repo root for a sketch named like the
        # field worker's example. Adjust this for your local layout.
        sketch = str(_REPO / "Data" / "sample_sketches" / "example_sketch.jpeg")
    assert Path(sketch).exists(), f"sketch missing: {sketch}"

    # Use the Anthropic key already available in this environment.
    # In production: GEMINI_API_KEY would be the default cheaper path.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set; cannot run test")

    print("─" * 60)
    print(f"Extracting sketch: {sketch}")
    print("─" * 60)

    result = extract_from_image(
        sketch,
        backend="claude",
        # Use the model string that maps to Sonnet 4.6 on the API.
        model="claude-sonnet-4-5",   # closest available; will swap to 4.6 in prod
        extra_hints=(
            "Site code at the bottom right of the page is 'PITT' "
            "(written upside-down). The sampling date is 2026-05-15. "
            "This sketch shows ONE yard. The house side is the bottom "
            "of the page."
        ),
    )

    print(f"\nBackend: {result.backend} ({result.model})")
    print(f"Usage:   {result.usage}")
    print(f"Valid:   {result.ok}")
    if result.problems:
        print("\nVALIDATION PROBLEMS:")
        for p in result.problems:
            print(f"  • {p}")

    print("\n─── Extracted data ───")
    print(json.dumps(result.data, indent=2))

    print("\n─── Converted to cell_data (back yard) ───")
    cell_data = to_cell_data(result.data, yard_choice="Back")
    for cid in sorted(cell_data.keys()):
        cd = cell_data[cid]
        shape = cd["shape_kind"]
        extra = ""
        if shape == "notch":
            extra = f"  notch={cd['shape_params']}"
        elif shape == "angle":
            extra = f"  angle={cd['shape_params']}"
        elif shape == "custom":
            n = len(cd["local_polygon"] or [])
            extra = f"  custom_poly={n}pts"
        gap = f"  gap_r={cd['gap_right']:.2f}" if cd["gap_right"] else ""
        wlk = "  [WALKWAY]" if cd["is_walkway"] else ""
        print(
            f"  {cid:>4}  W={cd['width']:5.2f}'  H={cd['height']:5.2f}'  "
            f"row={cd['row']} col={cd['col']}{extra}{gap}{wlk}"
        )

    # Show confidence breakdown
    print("\n─── Confidence ───")
    conf_counts = {"high": 0, "medium": 0, "low": 0}
    low_cells = []
    for cid, cell in result.data.get("cells", {}).items():
        c = cell.get("confidence", "medium")
        conf_counts[c] = conf_counts.get(c, 0) + 1
        if c == "low":
            low_cells.append((cid, cell.get("notes", "")))
    print(f"  high:   {conf_counts.get('high', 0)}")
    print(f"  medium: {conf_counts.get('medium', 0)}")
    print(f"  low:    {conf_counts.get('low', 0)}")
    if low_cells:
        print("  Low-confidence cells (need review):")
        for cid, note in low_cells:
            print(f"    {cid}: {note}")
    print(f"\n  Overall: {result.data.get('overall_confidence')}")
    if result.data.get("global_notes"):
        print(f"  Notes:   {result.data['global_notes']}")


if __name__ == "__main__":
    main()