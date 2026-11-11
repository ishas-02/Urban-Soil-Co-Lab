"""Correction loop: plain-English instruction → small edit operations.

This is the "talk to it like you'd talk to Claude in chat" part. The
user types (or says) "2B–3B has a 4 ft walkway" or "1A's left edge
slants, diagonal 16 ft". We send the LLM:

  • the sketch photo (so it can re-read the page when asked to),
  • the CURRENT model as compact JSON,
  • the open checks/questions,
  • the last few chat turns (so "make it 5 instead" works),
  • the new instruction,

and ask for ``{"ops": [...], "reply": "...", "questions": [...]}``.
``edits.apply_ops`` applies the ops; nothing else in the map changes.

The LLM call is injectable (``call_fn``) so tests and offline demos
can run without an API key.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Callable, Optional

from .edits import apply_ops
from .geometry import label
from .sketch_model import check

CORRECTION_SYSTEM_PROMPT = """\
You help a soil-lab field worker turn a hand-drawn yard sketch into an
exact digital grid. The app has ALREADY read the sketch into a model
(given to you as JSON). The user now tells you what is wrong or missing,
in plain English, sometimes transcribed from voice (expect typos like
"to be" for "2B", "for feet" for "4 ft").

Your ONLY job: translate the user's message into a list of edit
operations on the model. Python applies them and redraws the map.

## Grid conventions
- Rows are letters, A = farthest from the house (top of the sketch).
- Columns are numbers, 1 = left of the sketch.
- Field workers write cells column-first ("2B" = column 2, row B).
  Either order is fine in ops ("2B" or "B2" mean the same cell).
- Lengths: decimal feet (10.5) or strings like "10' 6\\"" — both accepted.
- "width" runs left↔right on the sketch, "height" runs top↔bottom.

## Operations (return any number, in order)
{"op":"set_cell","cell":"2B","width":10.5,"height":8,"gap_right":0,"is_walkway":false}
    (include only the fields being changed)
{"op":"set_shape","cell":"1A","shape_kind":"angle","side":"L","slant_len":16,"slant_end":"far"}
    side = the slanted edge: L, R, T (far from house) or B (near house).
    slant_len = diagonal length the user gives. slant_end = which end of
    that edge is pushed INTO the cell: for L/R "near"=bottom "far"=top;
    for T/B "near"=left "far"=right. If the user gives an offset instead
    of a diagonal, use "inset_near"/"inset_far" (feet) and omit slant_len.
    Optional: "top_width"/"bottom_width" (L/R) or "left_height"/"right_height"
    (T/B) = the cell's size at that end of the slant ("4 ft across the top
    of 2B" → top_width 4; a pointed end → 0). The app computes the rest.
    For a slanted cell, a width the user gives for its top or bottom goes
    in top_width / bottom_width inside set_shape — not in set_cell width.
    set_shape REPLACES the cell's whole shape: repeat every measurement
    that should stay, and leave out any the user says is wrong or absent.
{"op":"set_shape","cell":"3C","shape_kind":"notch","corner":"TR","notch_w":3,"notch_h":2}
{"op":"set_shape","cell":"3C","shape_kind":"rect"}
{"op":"set_shape","cell":"4D","shape_kind":"custom","polygon":[[0,0],[8,0],[8,6],[0,10]]}
    (cell-local feet, origin = cell's bottom-left on the sketch, y up)
{"op":"walkway_between","a":"2B","b":"3B","width":4}
    the app decides whether that is a column gap or a row gap.
{"op":"set_row_gap","row":"C","gap":3}     walkway below row C
{"op":"set_col_gap","col":2,"width":2}      walkway between columns 2 and 3 in
    EVERY row (add "rows":["A","B"] to limit it). walkway_between only
    touches the one pair of cells you name.
{"op":"align_slant","cells":["B2","C3","D4","E5"]}
    the slanted cells form ONE continuous line: each cell WITHOUT a top
    width starts where the one above it ends (measured top widths are
    kept). Use when the user says the diagonal is one line or a cell's
    top "lines up with" the cell above. List cells top to bottom; every
    listed cell must already be slanted.
{"op":"set_row_height","row":"C","height":12}
{"op":"set_col_width","col":2,"width":9.5}           (optional "rows":["A","B"])
{"op":"add_cell","cell":"5E","width":10,"height":10}
{"op":"remove_cell","cell":"4D"}
{"op":"add_row","row":"F","ncols":4,"width":10,"height":10}
{"op":"remove_row","row":"F"}
{"op":"set_cell","cell":"2C","is_walkway":true}      cell itself is a path
{"op":"confirm","cells":["all"]}   or a list — the user says these look right
    (use this instead of re-setting values that don't change)

## Rules
1. Change ONLY what the user asked about. Never "tidy up" other cells.
2. If the message is ambiguous (which cell? which edge? what length?),
   return NO ops for that part and ask ONE short question instead.
3. If the user asks you to look at the sketch again ("re-read row C"),
   use the image and return ops for what you now read.
4. If the user is just answering one of the open questions, apply it.
5. "reply" = one short, plain sentence saying what YOUR OPS change —
   nothing more — using the user's cell labels (e.g. "Set 2B to 10' 6\\" wide.").
6. When the user points at rows/cells by position on the paper ("the
   bottom two rows", "the cell by the stairs"), identify them from the
   IMAGE and the measurements they quote (the model lists each row's
   height), not from the word "bottom" alone — photos may be upside
   down relative to the map (map: row A = far from house = top).
   Name the rows/cells you picked in the reply so the user can check.
7. "questions" = every question that is STILL open after this turn:
   earlier questions the user hasn't answered yet, plus any new one.
   Drop questions this message answered. Empty list when nothing is open.

Return ONLY this JSON object, no prose, no code fences:
{"ops": [...], "reply": "...", "questions": ["..."]}
"""


def compact_model(model: dict[str, Any]) -> dict[str, Any]:
    """The model as the LLM needs to see it — small and readable."""
    cells = []
    for cid, c in sorted((model.get("cells") or {}).items(),
                         key=lambda kv: (kv[1]["row"], kv[1]["col"])):
        item: dict[str, Any] = {
            "label": label(cid, c), "row": c["row"], "col": c["col"],
            "width": round(float(c["width"]), 3), "height": round(float(c["height"]), 3),
        }
        if c.get("shape_kind", "rect") != "rect":
            item["shape"] = c["shape_kind"]
            sp = dict(c.get("shape_params") or {})
            if sp.get("slant_len") not in (None, ""):
                # insets are computed from the measurements — showing them
                # only invites the model to "fix" derived numbers.
                sp.pop("inset_near", None)
                sp.pop("inset_far", None)
            item["shape_params"] = sp
            if c.get("local_polygon"):
                item["polygon"] = c["local_polygon"]
        if c.get("gap_right"):
            item["gap_right"] = c["gap_right"]
        if c.get("is_walkway"):
            item["is_walkway"] = True
        cells.append(item)
    gaps = {r: g for r, g in (model.get("row_gap_below") or {}).items() if g}
    from .geometry import row_heights
    rh = row_heights(model)
    rows = model.get("rows", [])
    row_info = [{"row": r, "height": round(rh.get(r, 0), 3),
                 "cells": sum(1 for c in (model.get("cells") or {}).values() if c["row"] == r),
                 "position": ("farthest from house" if i == 0 else
                              "nearest the house" if i == len(rows) - 1 else "")}
                for i, r in enumerate(rows)]
    return {"rows": row_info, "row_gap_below": gaps, "cells": cells}


def build_user_text(model: dict, instruction: str, chat: list[dict] | None = None) -> str:
    findings = [f["msg"] for f in check(model) if f["level"] in ("error", "warn", "ask")]
    recent = (chat or [])[-6:]
    parts = [
        "CURRENT MODEL:\n" + json.dumps(compact_model(model), separators=(",", ":")),
        "OPEN CHECKS / QUESTIONS:\n" + ("\n".join(f"- {m}" for m in findings) or "(none)"),
    ]
    if recent:
        parts.append("RECENT CHAT:\n" + "\n".join(f"{t['role']}: {t['text']}" for t in recent))
    parts.append("USER SAYS:\n" + instruction.strip())
    return "\n\n".join(parts)


# ════════════════════════════════════════════════════════════════
#  Provider calls (same HTTP style as providers.py)
# ════════════════════════════════════════════════════════════════

def _claude_body(model: str, system: str, content: list) -> dict:
    """Request body; uses a small thinking budget so the model checks
    which cell/edge the user means before answering."""
    budget = int(os.environ.get("VLM_FIX_THINKING_BUDGET", "2500") or 0)
    body = {"model": model, "max_tokens": 2048, "temperature": 0.0,
            "system": system, "messages": [{"role": "user", "content": content}]}
    if budget > 0:
        body.update(thinking={"type": "enabled", "budget_tokens": budget},
                    max_tokens=budget + 2048)
        body.pop("temperature")
    return body


def _post_claude(system: str, text: str, image: Optional[tuple[bytes, str]],
                 model: str, api_key: str, timeout: int) -> str:
    import requests
    content: list[dict] = []
    if image:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": image[1],
            "data": base64.standard_b64encode(image[0]).decode("ascii")}})
    content.append({"type": "text", "text": text})
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"},
        json=_claude_body(model, system, content),
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Claude API {resp.status_code}: {resp.text[:400]}")
    blocks = resp.json().get("content") or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def _post_gemini(system: str, text: str, image: Optional[tuple[bytes, str]],
                 model: str, api_key: str, timeout: int) -> str:
    import requests
    parts: list[dict] = []
    if image:
        parts.append({"inline_data": {"mime_type": image[1],
                                      "data": base64.standard_b64encode(image[0]).decode("ascii")}})
    parts.append({"text": text})
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={"systemInstruction": {"parts": [{"text": system}]},
              "contents": [{"role": "user", "parts": parts}],
              "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4096,
                                   "responseMimeType": "application/json"}},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:400]}")
    cands = resp.json().get("candidates") or []
    if not cands:
        raise RuntimeError("Gemini returned no answer")
    return "".join(p.get("text", "") for p in cands[0]["content"].get("parts", []))


def default_call(backend: str, model_name: Optional[str] = None, timeout: int = 90) -> Callable:
    """Return ``call(system, text, image) -> raw_text`` for a backend."""
    from .providers import _call_with_retry
    backend = backend.lower()
    if backend == "claude":
        key = os.environ.get("ANTHROPIC_API_KEY")
        mdl = model_name or "claude-sonnet-4-6"
        post = _post_claude
    else:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        mdl = model_name or "gemini-2.5-flash"
        post = _post_gemini
    if not key:
        raise RuntimeError(f"No API key set for {backend}.")

    def call(system: str, text: str, image):
        return _call_with_retry(post, system, text, image, mdl, key, timeout)
    return call


# ════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════

def correct(
    model: dict[str, Any],
    instruction: str,
    *,
    image: Optional[tuple[bytes, str]] = None,
    chat: list[dict] | None = None,
    call_fn: Callable[[str, str, Any], str],
) -> dict[str, Any]:
    """Run one correction turn.

    Returns ``{"model", "ops", "done", "errors", "reply", "questions"}``.
    ``model`` is a NEW dict (the input is not mutated) — the caller
    pushes the old one on the undo stack.
    """
    from .providers import _parse_json_response

    raw = call_fn(CORRECTION_SYSTEM_PROMPT, build_user_text(model, instruction, chat), image)
    try:
        payload = _parse_json_response(raw)
    except Exception as exc:  # malformed JSON from the model
        return {"model": model, "ops": [], "done": [], "errors": [f"Couldn't understand the "
                f"model's answer ({exc}). Try rephrasing."], "reply": "", "questions": []}
    ops = payload.get("ops") or []
    new_model, done, errors = apply_ops(model, ops)
    questions = [str(q) for q in (payload.get("questions") or []) if str(q).strip()]
    new_model["questions"] = questions
    return {"model": new_model, "ops": ops, "done": done, "errors": errors,
            "reply": str(payload.get("reply") or ""), "questions": questions}
