"""Drag-corner shape editor for VLM-extracted cells.

A small SVG widget rendered via streamlit.components.v1.html. The user
drags any of the four cell corners; the widget snaps to edges when
close, and detects which of the existing shape_kinds (rect / notch /
angle / custom) the resulting polygon best fits. The user clicks
"Save" inside the widget to commit; the new shape_kind and params
are returned to Python via Streamlit.setComponentValue().

Public entry point: ``render_shape_editor(cell_id, cell, key) -> dict | None``.

When the user saves a new shape, returns a dict like:
  {"shape_kind": "angle",
   "shape_params": {"side": "T", "inset_near": 0.0, "inset_far": 6.0},
   "local_polygon": None}

Returns None until the user clicks Save (i.e. on most reruns).

A helper ``classify_polygon(width, height, points)`` does the
rectangle/notch/angle/custom detection. It's pure Python and unit-
testable without Streamlit. The JS side does its own classification
for live preview, then sends both the polygon AND its classification
to Python — Python re-classifies as the source of truth.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import streamlit as st
import streamlit.components.v1 as components


# ════════════════════════════════════════════════════════════════
#  Pure-Python shape classification (called both client-side via
#  embedded copy in JS, and server-side as the source of truth)
# ════════════════════════════════════════════════════════════════

# How close (in feet) a corner has to be to a cell edge to "count
# as on that edge" — used both for snapping and classification.
EDGE_TOLERANCE_FT = 0.25


def _near(a: float, b: float, tol: float = EDGE_TOLERANCE_FT) -> bool:
    return abs(a - b) < tol


def classify_polygon(
    width: float, height: float, points: list[list[float]]
) -> dict[str, Any]:
    """Given a 4-point polygon in cell-local feet (origin = sketch
    bottom-left), return the simplest shape_kind that describes it.

    Inputs:
        width, height : cell dimensions in feet
        points        : 4 (x,y) corners, in order BL, BR, TR, TL
                        (bottom-left, bottom-right, top-right, top-left)

    Returns:
        {"shape_kind": ..., "shape_params": {...}, "local_polygon": ...}
    """
    if len(points) != 4:
        return {
            "shape_kind": "custom",
            "shape_params": {},
            "local_polygon": [list(p) for p in points],
        }

    bl, br, tr, tl = points
    w, h = float(width), float(height)

    # ── Detect plain rectangle ──
    if (_near(bl[0], 0) and _near(bl[1], 0)
            and _near(br[0], w) and _near(br[1], 0)
            and _near(tr[0], w) and _near(tr[1], h)
            and _near(tl[0], 0) and _near(tl[1], h)):
        return {"shape_kind": "rect", "shape_params": {}, "local_polygon": None}

    # ── Detect "angle" (one slanted edge) ──
    # An angle has 3 corners exactly at their canonical positions and
    # 1 corner that's been moved along an edge inward.
    # We check each of the 4 sides L/R/T/B.

    # Helper: are 3 of 4 corners at their canonical rect positions?
    canonical = [[0, 0], [w, 0], [w, h], [0, h]]
    moved_idx = None
    for i, (p, c) in enumerate(zip(points, canonical)):
        if not (_near(p[0], c[0]) and _near(p[1], c[1])):
            if moved_idx is not None:
                # More than one corner moved — try the 2-corner angle case below
                moved_idx = -1
                break
            moved_idx = i

    if moved_idx is not None and moved_idx >= 0:
        # Exactly one corner moved.  Determine where it went.
        mp = points[moved_idx]
        c  = canonical[moved_idx]
        dx, dy = mp[0] - c[0], mp[1] - c[1]
        # If the moved corner stays on one of its adjacent edges, it's
        # really still a corner — that's an angle with one inset=0.
        # If it moved into the interior, it's a notch.
        # We compute as an angle on the appropriate side.
        # Adjacent edges of corner i are: prev edge and next edge.
        # Canonical edges: 0=B (bl->br), 1=R (br->tr), 2=T (tr->tl), 3=L (tl->bl)
        # Corner 0 (bl): edges B and L
        # Corner 1 (br): edges B and R
        # Corner 2 (tr): edges T and R
        # Corner 3 (tl): edges T and L
        on_horiz_edge = _near(mp[1], c[1])   # still on the horizontal edge
        on_vert_edge  = _near(mp[0], c[0])   # still on the vertical edge

        if on_horiz_edge and not on_vert_edge:
            # Moved along the top/bottom edge → angle on L or R side
            side = "L" if moved_idx in (0, 3) else "R"
            if moved_idx == 0:   # bl moved right along B
                return {"shape_kind": "angle",
                        "shape_params": {"side": "L",
                                         "inset_near": float(mp[0]),
                                         "inset_far": 0.0},
                        "local_polygon": None}
            if moved_idx == 1:   # br moved left along B
                return {"shape_kind": "angle",
                        "shape_params": {"side": "R",
                                         "inset_near": float(w - mp[0]),
                                         "inset_far": 0.0},
                        "local_polygon": None}
            if moved_idx == 2:   # tr moved left along T
                return {"shape_kind": "angle",
                        "shape_params": {"side": "R",
                                         "inset_near": 0.0,
                                         "inset_far": float(w - mp[0])},
                        "local_polygon": None}
            if moved_idx == 3:   # tl moved right along T
                return {"shape_kind": "angle",
                        "shape_params": {"side": "L",
                                         "inset_near": 0.0,
                                         "inset_far": float(mp[0])},
                        "local_polygon": None}

        if on_vert_edge and not on_horiz_edge:
            # Moved along the left/right edge → angle on T or B side
            if moved_idx == 0:   # bl moved up along L
                return {"shape_kind": "angle",
                        "shape_params": {"side": "B",
                                         "inset_near": float(mp[1]),
                                         "inset_far": 0.0},
                        "local_polygon": None}
            if moved_idx == 3:   # tl moved down along L
                return {"shape_kind": "angle",
                        "shape_params": {"side": "T",
                                         "inset_near": float(h - mp[1]),
                                         "inset_far": 0.0},
                        "local_polygon": None}
            if moved_idx == 1:   # br moved up along R
                return {"shape_kind": "angle",
                        "shape_params": {"side": "B",
                                         "inset_near": 0.0,
                                         "inset_far": float(mp[1])},
                        "local_polygon": None}
            if moved_idx == 2:   # tr moved down along R
                return {"shape_kind": "angle",
                        "shape_params": {"side": "T",
                                         "inset_near": 0.0,
                                         "inset_far": float(h - mp[1])},
                        "local_polygon": None}

        # Corner moved diagonally into the interior → notch.
        # The "corner" tag uses the existing TL/TR/BL/BR convention
        # (sketch space: T = top of sketch, L = lower col number).
        corner_tag = {0: "BL", 1: "BR", 2: "TR", 3: "TL"}[moved_idx]
        if moved_idx == 0:
            notch_w, notch_h = float(mp[0]), float(mp[1])
        elif moved_idx == 1:
            notch_w, notch_h = float(w - mp[0]), float(mp[1])
        elif moved_idx == 2:
            notch_w, notch_h = float(w - mp[0]), float(h - mp[1])
        else:  # 3
            notch_w, notch_h = float(mp[0]), float(h - mp[1])
        return {"shape_kind": "notch",
                "shape_params": {"corner": corner_tag,
                                 "notch_w": notch_w, "notch_h": notch_h},
                "local_polygon": None}

    # ── Detect "angle" with TWO corners moved (both endpoints of one edge) ──
    # E.g. top edge slanted: TL moved down AND TR moved down → angle side=T.
    # Check each edge to see if both its endpoints moved INWARD along the
    # perpendicular axis, while the other two corners stayed put.
    canonical_at = {0: (0, 0), 1: (w, 0), 2: (w, h), 3: (0, h)}
    moved = {
        i: (points[i][0] - canonical_at[i][0], points[i][1] - canonical_at[i][1])
        for i in range(4)
    }
    still = {i for i in range(4) if _near(moved[i][0], 0) and _near(moved[i][1], 0)}

    # Side T: corners 2 (TR) and 3 (TL) moved DOWN (negative dy), others still
    if 0 in still and 1 in still and 2 not in still and 3 not in still \
            and moved[2][1] < -EDGE_TOLERANCE_FT and moved[3][1] < -EDGE_TOLERANCE_FT \
            and _near(moved[2][0], 0) and _near(moved[3][0], 0):
        return {"shape_kind": "angle",
                "shape_params": {"side": "T",
                                 "inset_near": float(-moved[3][1]),   # TL drop (left end)
                                 "inset_far": float(-moved[2][1])},   # TR drop (right end)
                "local_polygon": None}

    # Side B: corners 0 (BL) and 1 (BR) moved UP
    if 2 in still and 3 in still and 0 not in still and 1 not in still \
            and moved[0][1] > EDGE_TOLERANCE_FT and moved[1][1] > EDGE_TOLERANCE_FT \
            and _near(moved[0][0], 0) and _near(moved[1][0], 0):
        return {"shape_kind": "angle",
                "shape_params": {"side": "B",
                                 "inset_near": float(moved[0][1]),
                                 "inset_far": float(moved[1][1])},
                "local_polygon": None}

    # Side L: corners 0 (BL) and 3 (TL) moved RIGHT
    if 1 in still and 2 in still and 0 not in still and 3 not in still \
            and moved[0][0] > EDGE_TOLERANCE_FT and moved[3][0] > EDGE_TOLERANCE_FT \
            and _near(moved[0][1], 0) and _near(moved[3][1], 0):
        return {"shape_kind": "angle",
                "shape_params": {"side": "L",
                                 "inset_near": float(moved[0][0]),
                                 "inset_far": float(moved[3][0])},
                "local_polygon": None}

    # Side R: corners 1 (BR) and 2 (TR) moved LEFT
    if 0 in still and 3 in still and 1 not in still and 2 not in still \
            and moved[1][0] < -EDGE_TOLERANCE_FT and moved[2][0] < -EDGE_TOLERANCE_FT \
            and _near(moved[1][1], 0) and _near(moved[2][1], 0):
        return {"shape_kind": "angle",
                "shape_params": {"side": "R",
                                 "inset_near": float(-moved[1][0]),
                                 "inset_far": float(-moved[2][0])},
                "local_polygon": None}

    # ── Fallback: custom polygon ──
    return {
        "shape_kind": "custom",
        "shape_params": {},
        "local_polygon": [[round(p[0], 2), round(p[1], 2)] for p in points],
    }


# ════════════════════════════════════════════════════════════════
#  Initial-polygon computation: turn an existing shape_kind/params
#  back into a 4-point polygon, so the editor opens "where the
#  shape already is" rather than always starting from a plain rect.
# ════════════════════════════════════════════════════════════════

def _initial_polygon(width: float, height: float, cell: dict[str, Any]) -> list[list[float]]:
    """Return [BL, BR, TR, TL] in cell-local feet for the cell's
    current shape.  When the cell is a custom polygon with more
    than 4 vertices, we fall back to its bounding box rectangle
    (the editor only supports 4 corners).
    """
    w, h = float(width), float(height)
    kind = cell.get("shape_kind", "rect")
    params = cell.get("shape_params") or {}

    if kind == "rect":
        return [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]]

    if kind == "angle":
        side = params.get("side", "L")
        near = float(params.get("inset_near", 0))
        far  = float(params.get("inset_far", 0))
        if side == "T":
            return [[0.0, 0.0], [w, 0.0], [w, h - far], [0.0, h - near]]
        if side == "B":
            return [[0.0, near], [w, far], [w, h], [0.0, h]]
        if side == "L":
            return [[near, 0.0], [w, 0.0], [w, h], [far, h]]
        if side == "R":
            return [[0.0, 0.0], [w - near, 0.0], [w - far, h], [0.0, h]]

    if kind == "notch":
        corner = params.get("corner", "TL")
        nw = float(params.get("notch_w", 0))
        nh = float(params.get("notch_h", 0))
        # Move the single corresponding corner inward.
        bl, br, tr, tl = [0.0, 0.0], [w, 0.0], [w, h], [0.0, h]
        if corner == "BL":
            bl = [nw, nh]
        elif corner == "BR":
            br = [w - nw, nh]
        elif corner == "TR":
            tr = [w - nw, h - nh]
        elif corner == "TL":
            tl = [nw, h - nh]
        return [bl, br, tr, tl]

    if kind == "custom":
        pts = cell.get("local_polygon") or []
        if len(pts) == 4:
            return [[float(p[0]), float(p[1])] for p in pts]
        # Fallback: bounding box
        return [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]]

    return [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]]


# ════════════════════════════════════════════════════════════════
#  Streamlit widget
# ════════════════════════════════════════════════════════════════

# Visual size of the editor canvas in pixels. The cell is drawn
# at a fixed margin from the SVG edges; corners are HTML SVG circles
# with mouse/touch drag handlers.
_CANVAS_W   = 360
_CANVAS_H   = 360
_MARGIN_PX  = 40
_HANDLE_R   = 9

# Snap to an edge when the cursor is within this many pixels of one.
_SNAP_PX = 12


def render_shape_editor(
    cell_id: str,
    cell: dict[str, Any],
    key: str,
) -> Optional[dict[str, Any]]:
    """Render the drag-corner editor for one cell.

    Parameters
    ----------
    cell_id:
        e.g. "F3". Used for the widget DOM id and the title.
    cell:
        The cell dict from the extraction — must contain width, height,
        shape_kind, shape_params, local_polygon (any).
    key:
        Unique Streamlit key to avoid collisions when multiple editors
        coexist on a page (in practice, one at a time).

    Returns
    -------
    The new shape dict {"shape_kind", "shape_params", "local_polygon"}
    when the user clicks Save inside the widget, else None.
    """
    width  = float(cell.get("width", 10.0))
    height = float(cell.get("height", 10.0))
    sketch_label = cell.get("sketch_label") or cell_id
    initial = _initial_polygon(width, height, cell)

    # Pass everything the embedded JS needs as a JSON blob.
    payload = {
        "cellId":       cell_id,
        "sketchLabel":  sketch_label,
        "width":        width,
        "height":       height,
        "initialPoly":  initial,
        "canvasW":      _CANVAS_W,
        "canvasH":      _CANVAS_H,
        "marginPx":     _MARGIN_PX,
        "handleR":      _HANDLE_R,
        "snapPx":       _SNAP_PX,
    }
    payload_json = json.dumps(payload)

    html = _WIDGET_HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)
    result = components.html(html, height=_CANVAS_H + 180, scrolling=False)

    # When the user clicks Save inside the widget, the JS calls
    # Streamlit.setComponentValue(<the polygon>). On the next rerun,
    # `result` is that value. Re-classify in Python (source of truth)
    # and return the new shape dict.
    if result and isinstance(result, dict) and result.get("__saved__"):
        polygon = result.get("points") or []
        classified = classify_polygon(width, height, polygon)
        return classified
    return None


# ════════════════════════════════════════════════════════════════
#  Embedded HTML/CSS/JS — single template, payload injected as JSON
# ════════════════════════════════════════════════════════════════

_WIDGET_HTML_TEMPLATE = r"""
<!doctype html>
<html><head><style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
         Roboto, sans-serif; font-size: 13px; margin: 0; padding: 8px;
         color: #222; background: transparent; }
  .editor { display: flex; gap: 16px; align-items: flex-start; }
  svg { background: #fafafa; border: 1px solid #ddd; border-radius: 6px;
        touch-action: none; user-select: none; }
  .meta { flex: 1; min-width: 0; }
  .meta h4 { margin: 0 0 6px 0; font-size: 14px; }
  .shape-tag { display: inline-block; padding: 2px 8px; border-radius: 10px;
               background: #eef; color: #336; font-weight: 600;
               font-size: 11px; margin-right: 6px; }
  .params { font-family: ui-monospace, "SF Mono", monospace; font-size: 11px;
            background: #f5f5f5; padding: 6px 8px; border-radius: 4px;
            margin: 8px 0; white-space: pre-wrap; word-break: break-word; }
  .btns { display: flex; gap: 6px; margin-top: 10px; }
  button { padding: 6px 12px; border-radius: 4px; border: 1px solid #bbb;
           background: #fff; cursor: pointer; font-size: 12px; }
  button.primary { background: #1f6feb; border-color: #1f6feb; color: #fff; }
  button.primary:hover { background: #1a5fcc; }
  button:hover { background: #f0f0f0; }
  .hint { color: #666; font-size: 11px; margin-top: 8px; }
  .handle { fill: #1f6feb; stroke: #fff; stroke-width: 2;
            cursor: grab; }
  .handle:hover { fill: #0a4cb8; }
  .handle.dragging { cursor: grabbing; fill: #0a4cb8; }
  .poly { fill: rgba(31, 111, 235, 0.12); stroke: #1f6feb; stroke-width: 2; }
  .ghost { fill: none; stroke: #bbb; stroke-width: 1; stroke-dasharray: 4 4; }
  .axis-label { fill: #888; font-size: 10px; }
</style></head><body>

<div class="editor">
  <svg id="canvas" width="0" height="0"></svg>
  <div class="meta">
    <h4 id="cell-title">Editing —</h4>
    <div><span class="shape-tag" id="shape-tag">rect</span>
         <span id="shape-side"></span></div>
    <div class="params" id="params-out"></div>
    <div class="hint">
      Drag any blue corner. Corners snap to edges when close, so plain
      rectangles, single-edge angles, and corner notches stay clean.
      Custom polygons are saved when no parametric shape fits.
    </div>
    <div class="btns">
      <button class="primary" id="save-btn">💾 Save shape</button>
      <button id="reset-btn">↺ Reset to rect</button>
    </div>
  </div>
</div>

<script>
(function() {
  const P = __PAYLOAD__;
  const svg = document.getElementById("canvas");
  svg.setAttribute("width",  P.canvasW);
  svg.setAttribute("height", P.canvasH);

  document.getElementById("cell-title").textContent =
    "Editing " + P.sketchLabel + "  (" + P.width.toFixed(1) + "' × " +
    P.height.toFixed(1) + "')";

  // ── Coordinate transforms ──
  // Feet space:  x ∈ [0, width], y ∈ [0, height]  (origin = bottom-left)
  // Pixel space: SVG coordinates with origin at top-left
  const innerW = P.canvasW - 2 * P.marginPx;
  const innerH = P.canvasH - 2 * P.marginPx;
  function ftToPx(pt) {
    return [
      P.marginPx + (pt[0] / P.width)  * innerW,
      P.canvasH - P.marginPx - (pt[1] / P.height) * innerH,
    ];
  }
  function pxToFt(px) {
    return [
      ((px[0] - P.marginPx) / innerW) * P.width,
      ((P.canvasH - P.marginPx - px[1]) / innerH) * P.height,
    ];
  }

  // ── State ──
  let points = P.initialPoly.map(p => [p[0], p[1]]);   // BL, BR, TR, TL
  let dragIdx = null;

  // ── SVG node creation ──
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  // Ghost rectangle outlining the cell's full bounding box
  const ghostCorners = [[0,0],[P.width,0],[P.width,P.height],[0,P.height]]
    .map(ftToPx);
  const ghost = el("polygon", {
    class: "ghost",
    points: ghostCorners.map(p => p.join(",")).join(" "),
  });
  svg.appendChild(ghost);

  // Axis labels (width across the bottom, height up the left)
  const labelB = el("text", {
    class: "axis-label",
    x: P.canvasW / 2,
    y: P.canvasH - 8,
    "text-anchor": "middle",
  });
  labelB.textContent = "← " + P.width.toFixed(1) + "' →";
  svg.appendChild(labelB);
  const labelL = el("text", {
    class: "axis-label",
    x: 12, y: P.canvasH / 2,
    "text-anchor": "middle",
    transform: `rotate(-90 12 ${P.canvasH / 2})`,
  });
  labelL.textContent = "↑ " + P.height.toFixed(1) + "' ↑";
  svg.appendChild(labelL);

  // Polygon (the live cell shape)
  const poly = el("polygon", { class: "poly", points: "" });
  svg.appendChild(poly);

  // Corner handles
  const handles = [0,1,2,3].map(i => {
    const c = el("circle", {
      class: "handle",
      r: P.handleR,
      "data-i": i,
    });
    svg.appendChild(c);
    return c;
  });

  // ── Snapping logic ──
  // Snap a point in PIXEL space to the cell edges when within snapPx.
  function snapPx(px, py) {
    const tl = ftToPx([0, P.height]);
    const br = ftToPx([P.width, 0]);
    const left = tl[0], right = br[0], top = tl[1], bot = br[1];
    let nx = px, ny = py;
    if (Math.abs(px - left)  < P.snapPx) nx = left;
    if (Math.abs(px - right) < P.snapPx) nx = right;
    if (Math.abs(py - top)   < P.snapPx) ny = top;
    if (Math.abs(py - bot)   < P.snapPx) ny = bot;
    // Clamp inside the cell box
    nx = Math.max(left,  Math.min(right, nx));
    ny = Math.max(top,   Math.min(bot,   ny));
    return [nx, ny];
  }

  // ── Render loop ──
  function render() {
    const px = points.map(ftToPx);
    poly.setAttribute("points", px.map(p => p.join(",")).join(" "));
    for (let i = 0; i < 4; i++) {
      handles[i].setAttribute("cx", px[i][0]);
      handles[i].setAttribute("cy", px[i][1]);
    }
    classifyAndShow();
  }

  // ── Live classification (mirrors Python classify_polygon) ──
  const TOL = 0.25;
  function near(a, b) { return Math.abs(a - b) < TOL; }
  function classify() {
    const w = P.width, h = P.height;
    const canon = [[0,0],[w,0],[w,h],[0,h]];
    const moved = [], still = new Set();
    for (let i = 0; i < 4; i++) {
      const dx = points[i][0] - canon[i][0];
      const dy = points[i][1] - canon[i][1];
      moved.push([dx, dy]);
      if (near(dx, 0) && near(dy, 0)) still.add(i);
    }
    if (still.size === 4) {
      return { kind: "rect", params: {} };
    }
    // One corner moved cases
    if (still.size === 3) {
      const i = [0,1,2,3].find(j => !still.has(j));
      const mp = points[i], c = canon[i];
      const onH = near(mp[1], c[1]);
      const onV = near(mp[0], c[0]);
      if (onH && !onV) {
        if (i === 0) return {kind:"angle", params:{side:"L", inset_near: mp[0], inset_far: 0}};
        if (i === 1) return {kind:"angle", params:{side:"R", inset_near: w-mp[0], inset_far: 0}};
        if (i === 2) return {kind:"angle", params:{side:"R", inset_near: 0, inset_far: w-mp[0]}};
        if (i === 3) return {kind:"angle", params:{side:"L", inset_near: 0, inset_far: mp[0]}};
      }
      if (onV && !onH) {
        if (i === 0) return {kind:"angle", params:{side:"B", inset_near: mp[1], inset_far: 0}};
        if (i === 3) return {kind:"angle", params:{side:"T", inset_near: h-mp[1], inset_far: 0}};
        if (i === 1) return {kind:"angle", params:{side:"B", inset_near: 0, inset_far: mp[1]}};
        if (i === 2) return {kind:"angle", params:{side:"T", inset_near: 0, inset_far: h-mp[1]}};
      }
      // Diagonal → notch
      const tag = {0:"BL",1:"BR",2:"TR",3:"TL"}[i];
      let nw, nh;
      if (i === 0) { nw = mp[0];     nh = mp[1]; }
      else if (i === 1) { nw = w-mp[0]; nh = mp[1]; }
      else if (i === 2) { nw = w-mp[0]; nh = h-mp[1]; }
      else { nw = mp[0]; nh = h-mp[1]; }
      return {kind:"notch", params:{corner: tag, notch_w: nw, notch_h: nh}};
    }
    // Two-corner angle cases (both endpoints of one edge)
    const m = moved;
    if (still.has(0) && still.has(1) && !still.has(2) && !still.has(3)
        && m[2][1] < -TOL && m[3][1] < -TOL && near(m[2][0],0) && near(m[3][0],0)) {
      return {kind:"angle", params:{side:"T", inset_near:-m[3][1], inset_far:-m[2][1]}};
    }
    if (still.has(2) && still.has(3) && !still.has(0) && !still.has(1)
        && m[0][1] > TOL && m[1][1] > TOL && near(m[0][0],0) && near(m[1][0],0)) {
      return {kind:"angle", params:{side:"B", inset_near:m[0][1], inset_far:m[1][1]}};
    }
    if (still.has(1) && still.has(2) && !still.has(0) && !still.has(3)
        && m[0][0] > TOL && m[3][0] > TOL && near(m[0][1],0) && near(m[3][1],0)) {
      return {kind:"angle", params:{side:"L", inset_near:m[0][0], inset_far:m[3][0]}};
    }
    if (still.has(0) && still.has(3) && !still.has(1) && !still.has(2)
        && m[1][0] < -TOL && m[2][0] < -TOL && near(m[1][1],0) && near(m[2][1],0)) {
      return {kind:"angle", params:{side:"R", inset_near:-m[1][0], inset_far:-m[2][0]}};
    }
    // Fallback: custom
    return {kind:"custom", params:{}};
  }

  function classifyAndShow() {
    const c = classify();
    document.getElementById("shape-tag").textContent = c.kind;
    let side = "";
    if (c.kind === "angle") side = "· side=" + c.params.side;
    if (c.kind === "notch") side = "· " + c.params.corner;
    document.getElementById("shape-side").textContent = side;
    let out = "";
    if (c.kind === "rect") {
      out = "Plain rectangle, no parameters.";
    } else if (c.kind === "angle") {
      out = "side: " + c.params.side + "\n"
          + "inset_near: " + c.params.inset_near.toFixed(2) + "'\n"
          + "inset_far:  " + c.params.inset_far.toFixed(2) + "'";
    } else if (c.kind === "notch") {
      out = "corner:  " + c.params.corner + "\n"
          + "notch_w: " + c.params.notch_w.toFixed(2) + "'\n"
          + "notch_h: " + c.params.notch_h.toFixed(2) + "'";
    } else {
      out = "Custom polygon (" + points.length + " vertices):\n"
          + points.map(p => "  " + p[0].toFixed(2) + ", " + p[1].toFixed(2)).join("\n");
    }
    document.getElementById("params-out").textContent = out;
  }

  // ── Drag handlers ──
  function getSvgPoint(evt) {
    const rect = svg.getBoundingClientRect();
    const x = (evt.clientX ?? evt.touches?.[0]?.clientX) - rect.left;
    const y = (evt.clientY ?? evt.touches?.[0]?.clientY) - rect.top;
    return [x, y];
  }

  function startDrag(evt) {
    evt.preventDefault();
    const t = evt.target;
    if (!t.classList.contains("handle")) return;
    dragIdx = parseInt(t.getAttribute("data-i"), 10);
    t.classList.add("dragging");
  }
  function moveDrag(evt) {
    if (dragIdx === null) return;
    evt.preventDefault();
    const [x, y] = getSvgPoint(evt);
    const [sx, sy] = snapPx(x, y);
    points[dragIdx] = pxToFt([sx, sy]);
    render();
  }
  function endDrag(evt) {
    if (dragIdx === null) return;
    handles[dragIdx].classList.remove("dragging");
    dragIdx = null;
  }

  svg.addEventListener("mousedown", startDrag);
  window.addEventListener("mousemove", moveDrag);
  window.addEventListener("mouseup",   endDrag);
  svg.addEventListener("touchstart", startDrag, {passive: false});
  window.addEventListener("touchmove", moveDrag, {passive: false});
  window.addEventListener("touchend",  endDrag);

  // ── Buttons ──
  document.getElementById("reset-btn").addEventListener("click", () => {
    points = [[0,0],[P.width,0],[P.width,P.height],[0,P.height]];
    render();
  });

  document.getElementById("save-btn").addEventListener("click", () => {
    const payload = {
      __saved__: true,
      points: points.map(p => [Number(p[0].toFixed(3)),
                               Number(p[1].toFixed(3))]),
    };
    // Streamlit component value pipeline
    if (window.Streamlit) {
      window.Streamlit.setComponentValue(payload);
    } else {
      // Fallback (shouldn't happen inside Streamlit but useful for testing)
      window.parent.postMessage({type:"streamlit:setComponentValue",
                                 value: payload}, "*");
    }
  });

  // ── Streamlit component handshake ──
  // The component must signal "I am ready" once, and "I want this height".
  function bootStreamlit() {
    if (!window.Streamlit) return;
    window.Streamlit.setComponentReady();
    window.Streamlit.setFrameHeight(P.canvasH + 180);
  }
  // Streamlit injects its bridge script slightly after our HTML loads.
  // Poll briefly until it's available.
  let tries = 0;
  const boot = setInterval(() => {
    tries++;
    if (window.Streamlit || tries > 20) {
      clearInterval(boot);
      bootStreamlit();
    }
  }, 50);

  render();
})();
</script>
</body></html>
"""