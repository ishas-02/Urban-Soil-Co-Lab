"""Prompt for VLM-based site sketch extraction.

The prompt is split into a system message (rules, schema, conventions)
and a user message (the actual sketch image + per-call hints). Hints
can override sketchy defaults — e.g., "this row is in feet" or "the
house is at the bottom of the page".
"""

from __future__ import annotations

import json
from typing import Optional

from .schema import SITE_SKETCH_SCHEMA


SYSTEM_PROMPT = """\
You are an expert at reading hand-drawn field sketches of soil-sampling
grids. Your job is to extract the grid structure and per-cell
dimensions into a strict JSON object. You do NOT speculate about
anything not on the page. You do NOT fill in unknown values — when
unsure, mark the cell's confidence as "low" and leave a short note.

## What's on a sketch

Each sketch shows ONE yard divided into a rectangular grid of cells
plus, sometimes, an irregular extension hanging off one side. Every
cell has a label like `1A`, `2B`, `3F` — the LETTER is the row and the
NUMBER is the column. Cells in the same row share the same letter.
Cells in the same column share the same number.

Around the outside of the grid, the field worker writes dimensions in
imperial form, e.g.:
  - `10'`         = 10 feet  0 inches
  - `10' 6"`      = 10 feet  6 inches
  - `15' 8"`      = 15 feet  8 inches
  - `4' 5"`       = 4 feet  5 inches

Dimensions written across the TOP or BOTTOM of the grid are COLUMN
WIDTHS (perpendicular to the strip). Dimensions written on the LEFT
or RIGHT of the grid are ROW HEIGHTS (along the strip). Sometimes the
right-edge dimensions vary per row — that means the rows have
different heights.

## Conventions you MUST follow

1. The sketch's TOP is the far-from-house side. The sketch's BOTTOM is
   near the house. Row letters are listed FAR→NEAR (A is at the top of
   the sketch, the last row is at the bottom).
2. Column 1 is on the LEFT of the sketch, column N is on the RIGHT.
3. Cell-local coordinates have origin at the cell's BOTTOM-LEFT in
   sketch space, with x going RIGHT and y going UP. All distances are
   in DECIMAL FEET (e.g. 10' 6" → 10.5).
4. "Width" is perpendicular to the strip (horizontal on a typical
   vertical-strip sketch). "Height" is along the strip (vertical).
5. The cell ID format you OUTPUT is `<col><row>` — e.g. `1A`, `2B`,
   `3F`. Even if the sketch writes it `A1`, normalize to `1A`. This
   matches the downstream pipeline convention.

## Shape vocabulary

Most cells are plain rectangles. For irregular ones, pick the
SIMPLEST shape_kind that describes the cell:

- `rect` — plain rectangle, the default. shape_params = {}.

- `notch` — rectangle with one CORNER bitten out (L-shape). Use when a
  single corner of the cell is missing. shape_params:
    {"corner": "TL"|"TR"|"BL"|"BR",
     "notch_w": <feet>, "notch_h": <feet>}
  TL = top-left corner of the cell in SKETCH space (top = far from
  house, left = lower column number). Same convention for TR/BL/BR.

- `angle` — rectangle with ONE slanted edge (pentagon). Use when a
  single side of the cell is not perpendicular to the others.
  shape_params:
    {"side": "L"|"R"|"T"|"B",
     "inset_near": <feet>, "inset_far": <feet>}
  L/R: inset_near is at the BOTTOM end of that edge, inset_far at the
  TOP. T/B: inset_near is at the LEFT end of that edge, inset_far at
  the RIGHT. Both insets push that edge endpoint INWARD into the cell.

- `custom` — anything else (two angled sides, curved boundary
  approximated as polygon, etc.). Provide `local_polygon` as a list of
  [x, y] vertices in cell-local feet (origin = sketch bottom-left).
  At least 3 vertices, going around the polygon in order. Do NOT use
  custom when notch or angle would describe the shape — pick the
  simplest one that fits.

## Walkways and gaps

The sketch may show paths between cells:
- A gap BETWEEN two adjacent COLUMNS in the same row: set the
  left cell's `gap_right` to the gap width in feet.
- A gap BETWEEN two adjacent ROWS (a path running across the strip):
  set `row_gap_below["<that row>"]` to the gap width in feet.
- A cell that IS a walkway (paved/planted, no soil sampling): set
  `is_walkway = true`. The cell still occupies grid space.

## L-shapes and extensions

When the sketch shows an extension (e.g. main grid is 4×4 rows A–D but
extra rows E, F, G hang off only one side), the extension rows are
their OWN strip — column numbering RESTARTS at 1 within the extension.
Even though an extension cell may visually sit under main column 3 or
4, name it starting from `1`.

Example: a 4×4 main grid (rows A–D, cols 1–4) with an extension on
the right side that has:
  - one cell in row E (visually under main col 4)
  - two cells in row F (visually under main cols 3 and 4)
  - two cells in row G (visually under main cols 3 and 4)

Output:
  rows = ["A","B","C","D","E","F","G"]
  ncols_per_row = {"A":4,"B":4,"C":4,"D":4,"E":1,"F":2,"G":2}
  max_cols = 4
  cells contains:
    1A, 2A, 3A, 4A,
    1B, 2B, 3B, 4B,
    1C, 2C, 3C, 4C,
    1D, 2D, 3D, 4D,
    1E,           # the one E-row cell (visually under main col 4)
    1F, 2F,       # the two F-row cells (visually under main cols 3-4)
    1G, 2G        # the two G-row cells

The widths you assign to extension cells should reflect what they
look like in the sketch: e.g. if the leftmost F-row cell is narrow
(4'5") and the rightmost is wide (13'), then `1F.width = 4.417` and
`2F.width = 13.0`. The MAP RENDERER aligns the strip's column 1 with
the main grid's column 1 — if the extension visually sits under main
col 3, you can use the `row_gap_below` of the row JUST BEFORE the
extension to push the extension down, but lateral alignment must be
handled by the user during the visual preview/drag step. Don't try to
encode lateral offset in cell widths.

If the extension hangs off a SPECIFIC side (e.g. flush with the RIGHT
edge of the main grid instead of the left), set the leftmost
extension cell's `is_walkway = true` and give it a width equal to the
empty space — this reserves the lateral offset visually. See the
`is_walkway` note below.

## Confidence

Be honest. Per cell:
- "high"   — dimensions clearly legible, shape unambiguous
- "medium" — one dimension or label is partly obscured but inferrable
- "low"    — anything you'd want a human to verify

If you genuinely cannot read a dimension, give your best guess AND
mark confidence "low" with a `notes` string explaining why ("shadow
covers the right edge dimension"). Never invent a clean value to hide
uncertainty.

## Output format

Return ONLY a single JSON object matching this schema. No prose, no
markdown fences, no explanation. The JSON object's keys are described
in the schema below.

SCHEMA:
""" + json.dumps(SITE_SKETCH_SCHEMA, indent=2)


def build_user_message(extra_hints: Optional[str] = None) -> str:
    """Return the per-call user text accompanying the sketch image."""
    base = (
        "Extract the soil-sampling grid from this hand-drawn sketch. "
        "Follow the conventions in the system message exactly. "
        "Return ONLY the JSON object — no prose, no code fences."
    )
    if extra_hints:
        base += "\n\nField worker hints:\n" + extra_hints.strip()
    return base