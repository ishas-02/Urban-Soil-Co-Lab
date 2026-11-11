"""Site Builder step ⑥: sketch → digital grid, with a correction chat.

Replaces the old steps ⑥ (row letters) and ⑦ (≈100 width/height boxes
plus per-cell Advanced expanders) and the drag-corner shape editor.

Flow for the user:
  1. Upload the sketch photo → "Read sketch". The VLM fills the model.
  2. Look at the sketch next to the drawn map. Red/amber cells and the
     list under the map say what needs attention.
  3. Type or say corrections ("2B–3B has a 4 ft walkway"). Each one is
     applied, the map redraws, and Undo takes it back.
  4. Scroll on to Compute as before.

``render_sketch_builder`` returns the exact variables Compute used to
read from the old form (rows, cell_data, row_gap_below, …), or None
while there is no grid yet.
"""

from __future__ import annotations

import copy
import hashlib
import json
import mimetypes
import os
import tempfile
import traceback
from typing import Any, Optional

import streamlit as st

from .corrector import correct, default_call
from .edits import History
from .geometry import label
from .preview import render_png
from .sketch_model import check, empty_model, prepare, to_form_vars

PROVIDERS = {
    "Claude Sonnet 4.6 (recommended — most accurate on hand drawings)": ("claude", "claude-sonnet-4-6"),
    "Gemini 2.5 Flash (cheapest)": ("gemini", "gemini-2.5-flash"),
}

EXAMPLES = [
    "Between 2B and 3B there's a 4 ft walkway",
    "1A's left edge slants, the diagonal is 16 ft",
    "Row C is 12' 6\" tall",
    "Column 2 is 9 ft wide in every row",
    "2C is a walkway, no sampling",
    "Add a cell 4E under 4D, 6 ft by 5 ft",
    "Look at the sketch again — what are the widths of row D?",
]


# ════════════════════════════════════════════════════════════════
#  Session state
# ════════════════════════════════════════════════════════════════

def _k(yard_key: str, name: str) -> str:
    return f"sk_{yard_key}_{name}"


def _get(yard_key: str, name: str, default=None):
    return st.session_state.get(_k(yard_key, name), default)


def _set(yard_key: str, name: str, value) -> None:
    st.session_state[_k(yard_key, name)] = value


def _reset(yard_key: str) -> None:
    for name in ("model", "history", "chat", "image", "image_name", "last_audio", "notice"):
        st.session_state.pop(_k(yard_key, name), None)


def _say(yard_key: str, role: str, text: str) -> None:
    chat = _get(yard_key, "chat", [])
    chat.append({"role": role, "text": text})
    _set(yard_key, "chat", chat)


def _commit(yard_key: str, new_model: dict) -> None:
    """Replace the model, keeping the old one on the undo stack."""
    hist = History(_get(yard_key, "history", []))
    old = _get(yard_key, "model")
    if old is not None:
        hist.push(old)
    _set(yard_key, "history", hist.stack)
    _set(yard_key, "model", new_model)


# ════════════════════════════════════════════════════════════════
#  Actions
# ════════════════════════════════════════════════════════════════

def _read_sketch(yard_key: str, backend: str, model_name: str, hints: str) -> None:
    from .providers import extract_from_image

    img, mime = _get(yard_key, "image")
    suffix = mimetypes.guess_extension(mime) or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(img)
        path = tmp.name
    try:
        result = extract_from_image(path, backend=backend, model=model_name,
                                    extra_hints=hints or None)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    model, problems = prepare(result.data)
    model["questions"] = list(model.get("questions") or []) + problems
    _commit(yard_key, model)
    n = len(model["cells"])
    rows = model["rows"]
    findings = check(model)
    todo = [f for f in findings if f["level"] in ("error", "ask")]
    msg = (f"I read **{n} cells** in rows {rows[0]}–{rows[-1]}." if rows
           else "I couldn't find a grid on this page.")
    if todo:
        msg += f" {len(todo)} thing(s) need you — they're listed under the map."
    else:
        msg += " Everything was legible. Compare the map with your sketch."
    _say(yard_key, "assistant", msg)


def _run_correction(yard_key: str, text: str, backend: str, model_name: str) -> None:
    model = _get(yard_key, "model") or empty_model()
    image = _get(yard_key, "image")
    chat = _get(yard_key, "chat", [])
    _say(yard_key, "user", text)
    out = correct(model, text, image=image, chat=chat,
                  call_fn=default_call(backend, model_name))
    if out["done"]:
        _commit(yard_key, out["model"])
    else:
        # Nothing applied — keep the model, but remember the open questions.
        kept = copy.deepcopy(model)
        kept["questions"] = out["questions"]
        _set(yard_key, "model", kept)
    reply = out["reply"] or ("Done." if out["done"] else "I didn't change anything.")
    if out["done"]:
        reply += "\n\n" + "\n".join(f"- {d}" for d in out["done"])
    if out["errors"]:
        reply += "\n\n⚠️ " + "\n⚠️ ".join(out["errors"])
    if out["questions"]:
        reply += "\n\n❓ " + "\n❓ ".join(out["questions"])
    _say(yard_key, "assistant", reply)


# ════════════════════════════════════════════════════════════════
#  UI
# ════════════════════════════════════════════════════════════════

def render_sketch_builder(yard_key: str, yard_choice: str) -> Optional[dict[str, Any]]:
    st.subheader(f"⑥ Grid from sketch — {yard_choice} Yard")
    st.caption(
        "Upload the hand-drawn sketch. The AI reads it into a map; you correct it "
        "in plain words (typed or spoken) until the map matches your drawing. "
        "Every change can be undone."
    )

    with st.expander("⚙️ Settings", expanded=False):
        label_choice = st.selectbox("AI model", list(PROVIDERS), index=0,
                                    key=_k(yard_key, "provider"))
        backend, model_name = PROVIDERS[label_choice]
        env = "ANTHROPIC_API_KEY" if backend == "claude" else "GEMINI_API_KEY"
        if not (os.environ.get(env) or (backend == "gemini" and os.environ.get("GOOGLE_API_KEY"))):
            st.warning(f"`{env}` is not set — reading and corrections won't work.")
        hints = st.text_area(
            "Hints for the first read (optional)", key=_k(yard_key, "hints"), height=70,
            placeholder="e.g. 'house is at the bottom of the page', 'the right column is cut off'",
        )

    model = _get(yard_key, "model")

    # ── 1. Upload / start ───────────────────────────────────────
    up = st.file_uploader(f"{yard_choice}-yard sketch photo",
                          type=["jpg", "jpeg", "png", "webp", "heic"],
                          key=_k(yard_key, "uploader"))
    if up is not None:
        data = up.getvalue()
        if _get(yard_key, "image_name") != (up.name, len(data)):
            _set(yard_key, "image", (data, up.type or "image/jpeg"))
            _set(yard_key, "image_name", (up.name, len(data)))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        read = st.button("🔎 Read sketch" if model is None else "🔁 Re-read sketch",
                         type="primary" if model is None else "secondary",
                         disabled=_get(yard_key, "image") is None,
                         use_container_width=True, key=_k(yard_key, "read_btn"))
    with c2:
        blank = st.button("✏️ Start without photo", disabled=model is not None,
                          use_container_width=True, key=_k(yard_key, "blank_btn"),
                          help="Describe the grid in the box below instead, e.g. "
                               "'5 rows A to E, 4 cells each, 10 by 10 ft'.")
    with c3:
        undo = st.button(f"↩️ Undo ({len(_get(yard_key, 'history', []))})",
                         disabled=not _get(yard_key, "history"),
                         use_container_width=True, key=_k(yard_key, "undo_btn"))
    with c4:
        restart = st.button("🗑️ Start over", disabled=model is None,
                            use_container_width=True, key=_k(yard_key, "reset_btn"))

    if read:
        with st.spinner("Reading the sketch… (up to a minute for big grids)"):
            try:
                _read_sketch(yard_key, backend, model_name, hints)
            except Exception as exc:
                st.error(f"Couldn't read the sketch: **{type(exc).__name__}** — {exc}")
                with st.expander("Details"):
                    st.code(traceback.format_exc())
                return _form_vars_or_none(_get(yard_key, "model"), yard_choice)
        st.rerun()
    if blank:
        _commit(yard_key, empty_model())
        _say(yard_key, "assistant", "Describe the grid, e.g. *“5 rows A to E, 4 cells "
                                    "each, every cell 10 by 10 ft”*.")
        st.rerun()
    if undo:
        prev = History(_get(yard_key, "history", [])).undo()
        if prev is not None:
            _set(yard_key, "model", prev)
            _say(yard_key, "assistant", "↩️ Undid the last change.")
        st.rerun()
    if restart:
        _reset(yard_key)
        st.rerun()

    if model is None:
        st.info("Upload the sketch and press **Read sketch** to begin.")
        return None

    # ── 2. Sketch next to the drawn map ─────────────────────────
    left, right = st.columns(2)
    with left:
        st.markdown("**Your sketch**")
        img = _get(yard_key, "image")
        if img:
            st.image(img[0], use_column_width=True)
        else:
            st.caption("_(no photo)_")
    with right:
        st.markdown("**Digital map** — what will be saved")
        st.image(render_png(model), use_column_width=True)
        st.caption("Blue = sampling cell · grey hatched = walkway · "
                   "amber = please check · red = must fix")

    # ── 3. What needs attention ─────────────────────────────────
    findings = check(model)
    errors = [f for f in findings if f["level"] == "error"]
    warns = [f for f in findings if f["level"] == "warn"]
    asks = [f for f in findings if f["level"] == "ask"]
    if not findings:
        st.success("✅ No open issues. If the map matches your sketch, continue to ⑦.")
    for f in errors:
        st.error(f["msg"])
    for f in warns:
        st.warning(f["msg"])
    for f in asks:
        st.info("❓ " + f["msg"])

    # ── 4. Correction chat ──────────────────────────────────────
    st.markdown("#### 💬 Tell it what to fix")
    for turn in _get(yard_key, "chat", [])[-12:]:
        with st.chat_message("user" if turn["role"] == "user" else "assistant"):
            st.markdown(turn["text"])

    with st.form(_k(yard_key, "fix_form"), clear_on_submit=True):
        text = st.text_area("Correction", key=_k(yard_key, "fix_text"), height=80,
                            label_visibility="collapsed",
                            placeholder="e.g. " + " · ".join(EXAMPLES[:3]))
        send = st.form_submit_button("Apply ➜", type="primary")

    audio = None
    if hasattr(st, "experimental_audio_input"):
        audio = st.experimental_audio_input("🎤 Or say it", key=_k(yard_key, "mic"))
    with st.expander("Examples of what you can say"):
        st.markdown("\n".join(f"- {e}" for e in EXAMPLES))

    instruction = text.strip() if send and text and text.strip() else None
    if audio is not None:
        raw = audio.getvalue()
        digest = hashlib.sha1(raw).hexdigest()
        if digest != _get(yard_key, "last_audio"):
            _set(yard_key, "last_audio", digest)
            try:
                from .voice import transcribe
                with st.spinner("Listening…"):
                    heard = transcribe(raw, audio.type or "audio/wav")
                if heard:
                    instruction = heard
                    _say(yard_key, "assistant", f"🎤 Heard: *“{heard}”*")
            except Exception as exc:
                st.error(f"Voice didn't work: {exc}. You can type the correction instead.")

    if instruction:
        with st.spinner("Applying…"):
            try:
                _run_correction(yard_key, instruction, backend, model_name)
            except Exception as exc:
                _say(yard_key, "assistant", f"⚠️ That didn't go through ({exc}). "
                                            f"Nothing was changed — try again.")
        st.rerun()

    # ── 5. Sample-ID patterns + admin escape hatch ──────────────
    if model.get("cells"):
        _render_patterns(yard_key, yard_choice, model)
    _render_raw_json(yard_key)

    return _form_vars_or_none(_get(yard_key, "model"), yard_choice)


def _form_vars_or_none(model: Optional[dict], yard_choice: str) -> Optional[dict]:
    if not model or not model.get("cells"):
        return None
    return to_form_vars(model, yard_choice)


def _render_patterns(yard_key: str, yard_choice: str, model: dict) -> None:
    with st.expander("🏷️ Sample-ID patterns (matched against XRF readings)", expanded=False):
        st.caption("Defaults to `<Yard>_<label>_`. Change only if the XRF sample "
                   "names for this site use a different pattern.")
        rows = []
        for cid, c in sorted(model["cells"].items(), key=lambda kv: (kv[1]["row"], kv[1]["col"])):
            default = f"{yard_choice}_{label(cid, c)}_"
            rows.append({"cell": label(cid, c), "id": cid,
                         "pattern": c.get("pattern") or default,
                         "walkway": bool(c.get("is_walkway"))})
        edited = st.data_editor(
            rows, key=_k(yard_key, "patterns"), hide_index=True, use_container_width=True,
            disabled=["cell", "id", "walkway"], column_order=["cell", "pattern", "walkway"],
        )
        changed = False
        for r in edited:
            cell = model["cells"].get(r["id"])
            if cell is not None and (r["pattern"] or "") != (cell.get("pattern") or
                                                           f"{yard_choice}_{label(r['id'], cell)}_"):
                cell["pattern"] = (r["pattern"] or "").strip()
                changed = True
        if changed:
            _set(yard_key, "model", model)


def _render_raw_json(yard_key: str) -> None:
    with st.expander("🛠️ Advanced: edit the map as JSON (admins only)", expanded=False):
        st.caption("Escape hatch for anything the chat can't express. "
                   "Applying here also goes on the Undo stack.")
        current = json.dumps(_get(yard_key, "model") or empty_model(), indent=1)
        # No widget key on purpose: the box must refresh whenever the map
        # changes through the chat, and a keyed widget would keep stale text.
        raw = st.text_area("Map JSON", value=current, height=260)
        if st.button("Apply JSON", key=_k(yard_key, "raw_apply")):
            try:
                new, problems = prepare(json.loads(raw))
            except Exception as exc:
                st.error(f"Not valid: {exc}")
                return
            if problems:
                new["questions"] = list(new.get("questions") or []) + problems
            _commit(yard_key, new)
            _say(yard_key, "assistant", "🛠️ Map replaced from JSON.")
            st.rerun()
