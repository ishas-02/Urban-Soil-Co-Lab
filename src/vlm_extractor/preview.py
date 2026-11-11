"""Draw the sketch model as a clean, labelled map (PNG bytes).

Uses ``geometry.layout`` — the same placement rules as Compute — so what
the user sees here is what gets saved. Colours:

  blue    normal sampling cell
  grey    walkway cell (no XRF sampling)
  amber   the VLM was unsure / an open question mentions the cell
  red     a check found an error (e.g. slant with no measurement)
"""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

from .geometry import fmt_ft, label, layout  # noqa: E402
from .sketch_model import check  # noqa: E402

COL = {
    "ok": ("#e3eefc", "#2f6db5"),
    "walk": ("#eeeeee", "#8a8a8a"),
    "ask": ("#fff3d6", "#c98a00"),
    "error": ("#fde4e1", "#c62828"),
}


def render_png(model: dict[str, Any], *, width_in: float = 6.5, dpi: int = 130) -> bytes:
    cells = model.get("cells") or {}
    lay = layout(model)
    findings = check(model)
    err_cells = {f["cell"] for f in findings if f["level"] == "error" and f["cell"]}
    ask_cells = {f["cell"] for f in findings if f["level"] == "ask" and f["cell"]}

    if not lay:
        fig, ax = plt.subplots(figsize=(width_in, 2.2), dpi=dpi)
        ax.text(0.5, 0.5, "No cells yet", ha="center", va="center", color="#888")
        ax.axis("off")
        return _to_png(fig)

    xs = [p[0] for c in lay.values() for p in c["polygon"]] + [c["x1"] for c in lay.values()]
    ys = [p[1] for c in lay.values() for p in c["polygon"]] + [c["y1"] for c in lay.values()]
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    height_in = max(2.5, min(11.0, width_in * span_y / max(span_x, 1e-6)))
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=dpi)

    # Font scales with cell size so labels stay inside small cells.
    min_dim = min(min(float(c["width"]), float(c["height"])) for c in cells.values())
    fs = max(7.0, min(11.0, 11.0 * min_dim / max(span_x, span_y) * 4))

    for cid, box in lay.items():
        c = cells[cid]
        state = ("error" if cid in err_cells else "ask" if cid in ask_cells
                 else "walk" if c.get("is_walkway") else "ok")
        face, edge = COL[state]
        # faint dashed bounding box shows the full cell the shape lives in
        if c.get("shape_kind", "rect") != "rect":
            ax.add_patch(Rectangle((box["x0"], box["y0"]), box["x1"] - box["x0"],
                                   box["y1"] - box["y0"], fill=False, ls=":",
                                   lw=0.6, ec="#b0b0b0"))
        ax.add_patch(Polygon(box["polygon"], closed=True, fc=face, ec=edge, lw=1.4,
                             hatch="///" if c.get("is_walkway") else None))
        px, py = _centroid(box["polygon"])
        dims = f"{fmt_ft(c['width'])} × {fmt_ft(c['height'])}"
        ax.text(px, py, f"{label(cid, c)}\n{dims}", ha="center", va="center",
                fontsize=fs, color="#1a1a1a", fontweight="bold" if state != "ok" else None)

        gap = float(c.get("gap_right", 0) or 0)
        if gap > 0:
            ax.add_patch(Rectangle((box["x1"], box["y0"]), gap, box["y1"] - box["y0"],
                                   fc="#fff8e1", ec="#c8a060", ls="--", lw=0.8))
            ax.text(box["x1"] + gap / 2, (box["y0"] + box["y1"]) / 2, f"path\n{fmt_ft(gap)}",
                    ha="center", va="center", fontsize=fs * 0.8, color="#a07a20", rotation=90)

    # Row walkways
    rows = model.get("rows") or []
    for r in rows:
        g = float((model.get("row_gap_below") or {}).get(r, 0) or 0)
        row_boxes = [lay[k] for k, c in cells.items() if c["row"] == r and k in lay]
        if g <= 0 or not row_boxes or r == rows[-1]:
            continue
        y_top = min(b["y0"] for b in row_boxes)
        ax.add_patch(Rectangle((min(xs), y_top - g), span_x, g, fc="#fff8e1",
                               ec="#c8a060", ls="--", lw=0.8))
        ax.text(min(xs) + span_x / 2, y_top - g / 2, f"walkway {fmt_ft(g)}",
                ha="center", va="center", fontsize=fs * 0.85, color="#a07a20")

    pad = max(span_x, span_y) * 0.04 + 0.5
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad * 2.2)
    ax.text(min(xs), max(ys) + pad * 1.2, "↑ far from house", fontsize=7, color="#777")
    ax.text(min(xs), min(ys) - pad * 0.8, "↓ house side", fontsize=7, color="#777", va="top")
    ax.set_aspect("equal")
    ax.axis("off")
    return _to_png(fig)


def _centroid(pts: list[list[float]]) -> tuple[float, float]:
    """Area centroid (label sits inside triangles, not on their edge)."""
    a = cx = cy = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-9:
        return sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    return cx / (3 * a), cy / (3 * a)


def _to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
