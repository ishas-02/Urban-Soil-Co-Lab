# """Streamlit review UI for VLM-extracted site sketches.

# Designed to drop into `site_builder.py` between section ⑤ (Grid
# Layout) and section ⑥ (Define Grid Rows). One public function:
# ``render_vlm_section(yard_key, yard_choice)``. When the user clicks
# **Accept & Pre-fill Form**, the relevant ``st.session_state`` keys
# are populated so the existing widgets in sections ⑥ and ⑦ pick up
# the values automatically on the next rerun.

# All session_state writes use the EXACT key names site_builder.py's
# existing widgets read from — see the comment block at the top of
# ``_apply_to_session_state`` for the canonical list.
# """

# from __future__ import annotations

# import io
# import os
# import tempfile
# import traceback
# from typing import Any, Optional

# import streamlit as st

# from .providers import extract_from_image
# from .schema import normalize_extraction, to_cell_data, validate_extraction


# # ════════════════════════════════════════════════════════════════
# #  Configuration
# # ════════════════════════════════════════════════════════════════

# # Which API providers to expose in the UI. Order matters — first is
# # the default. Each tuple is (label, backend, default_model, blurb).
# PROVIDERS: list[tuple[str, str, str, str]] = [
#     ("Gemini 2.5 Flash-Lite (default — cheapest)",
#      "gemini",
#      "gemini-2.5-flash-lite",       # ← was "gemini-2.5-flash"
#      "Highest free-tier throughput. Strong enough for clean sketches."),
#     ("Claude Sonnet 4.6 (fallback — better on messy sketches)",
#      "claude",
#      "claude-sonnet-4-6",
#      "~$0.01 per sketch. Best for shadowed, unclear, or complex sketches."),
# ]


# # ════════════════════════════════════════════════════════════════
# #  Session-state helpers
# # ════════════════════════════════════════════════════════════════

# def _ss_key(yard_key: str, suffix: str) -> str:
#     """Build a yard-scoped session-state key used internally by the
#     VLM section (e.g. to remember the last upload + extraction).
#     """
#     return f"vlm_{yard_key}_{suffix}"


# def _clear_extraction(yard_key: str) -> None:
#     """Forget the in-progress VLM extraction for this yard."""
#     for suffix in ("extraction", "raw_response", "image_bytes",
#                    "image_name", "problems", "backend_used", "model_used"):
#         st.session_state.pop(_ss_key(yard_key, suffix), None)


# def _apply_to_session_state(
#     extraction: dict[str, Any],
#     yard_key: str,
# ) -> tuple[int, list[str]]:
#     """Push the VLM-extracted values into the session_state keys that
#     site_builder.py's existing widgets already use.

#     Returns (n_keys_written, warnings).

#     Canonical key list (must stay in sync with site_builder.py):

#       • rows_{yard_key}              — text input (comma-separated)
#       • max_cols_{yard_key}          — number input (int)
#       • ncols_{row}_{yard_key}       — number input per row
#       • rowgap_{row}_{yard_key}__ft  — feet part of row-gap-below
#       • rowgap_{row}_{yard_key}__in  — inches part
#       • w_{cell_id}_{yard_key}__ft   — width feet
#       • w_{cell_id}_{yard_key}__in   — width inches
#       • h_{cell_id}_{yard_key}__ft   — height feet
#       • h_{cell_id}_{yard_key}__in   — height inches
#       • pat_{cell_id}_{yard_key}     — sample-ID pattern
#       • walkway_{cell_id}_{yard_key} — walkway checkbox
#       • gapr_{cell_id}_{yard_key}__ft, __in — gap to the right
#       • shapekind_{cell_id}_{yard_key} — shape selectbox
#       • notch_corner_{cell_id}_{yard_key}, notch_w_, notch_h_ (+__ft/__in)
#       • angle_side_, angle_near_, angle_far_ (+__ft/__in)
#       • poly_{cell_id}_{yard_key}    — custom polygon text area
#     """
#     warnings: list[str] = []
#     n_written = 0

#     def _set(key: str, value: Any) -> None:
#         nonlocal n_written
#         st.session_state[key] = value
#         n_written += 1

#     def _set_ft_in(key_base: str, decimal_feet: float) -> None:
#         ft = int(decimal_feet)
#         inches = round((decimal_feet - ft) * 12 * 2) / 2  # nearest 0.5"
#         if inches >= 12:
#             ft += 1
#             inches = 0.0
#         _set(f"{key_base}__ft", ft)
#         _set(f"{key_base}__in", float(inches))

#     # ── 1. Rows + grid layout ──
#     rows = extraction.get("rows", [])
#     if rows:
#         _set(f"rows_{yard_key}", ", ".join(rows))

#     ncols_per_row = extraction.get("ncols_per_row", {})
#     if ncols_per_row:
#         max_cols = extraction.get("max_cols") or max(ncols_per_row.values())
#         _set(f"max_cols_{yard_key}", int(max_cols))
#         for row, n in ncols_per_row.items():
#             _set(f"ncols_{row}_{yard_key}", int(n))

#     # ── 2. Row gaps below ──
#     for row, gap in (extraction.get("row_gap_below") or {}).items():
#         _set_ft_in(f"rowgap_{row}_{yard_key}", float(gap or 0.0))

#     # ── 3. Per-cell dimensions, shape, and metadata ──
#     cells = extraction.get("cells") or {}
#     yard_choice_titlecase = "Front" if yard_key == "front" else "Back"

#     for cid, cell in cells.items():
#         try:
#             _set_ft_in(f"w_{cid}_{yard_key}", float(cell["width"]))
#             _set_ft_in(f"h_{cid}_{yard_key}", float(cell["height"]))
#             _set(f"pat_{cid}_{yard_key}", f"{yard_choice_titlecase}_{cid}_")
#             _set(f"walkway_{cid}_{yard_key}",
#                  bool(cell.get("is_walkway", False)))
#             _set_ft_in(f"gapr_{cid}_{yard_key}",
#                        float(cell.get("gap_right", 0.0) or 0.0))

#             shape_kind = cell.get("shape_kind", "rect")
#             _set(f"shapekind_{cid}_{yard_key}", shape_kind)

#             params = cell.get("shape_params") or {}
#             if shape_kind == "notch":
#                 _set(f"notch_corner_{cid}_{yard_key}",
#                      params.get("corner", "TL"))
#                 _set_ft_in(f"notch_w_{cid}_{yard_key}",
#                            float(params.get("notch_w", 0)))
#                 _set_ft_in(f"notch_h_{cid}_{yard_key}",
#                            float(params.get("notch_h", 0)))
#             elif shape_kind == "angle":
#                 _set(f"angle_side_{cid}_{yard_key}",
#                      params.get("side", "L"))
#                 _set_ft_in(f"angle_near_{cid}_{yard_key}",
#                            float(params.get("inset_near", 0)))
#                 _set_ft_in(f"angle_far_{cid}_{yard_key}",
#                            float(params.get("inset_far", 0)))
#             elif shape_kind == "custom":
#                 pts = cell.get("local_polygon") or []
#                 if pts:
#                     poly_text = "; ".join(
#                         f"{p[0]:.2f},{p[1]:.2f}" for p in pts
#                     )
#                     _set(f"poly_{cid}_{yard_key}", poly_text)
#         except (KeyError, ValueError, TypeError) as exc:
#             warnings.append(f"cell '{cid}': could not pre-fill ({exc})")

#     return n_written, warnings


# # ════════════════════════════════════════════════════════════════
# #  UI rendering — the public function
# # ════════════════════════════════════════════════════════════════

# def render_vlm_section(yard_key: str, yard_choice: str) -> None:
#     """Render the VLM-upload-and-extract section for one yard.

#     Call this from ``site_builder.py`` between section ⑤ and section ⑥.
#     All state is scoped to ``yard_key`` so Front and Back never collide.

#     Parameters
#     ----------
#     yard_key:
#         Internal yard key, ``"front"`` or ``"back"``.
#     yard_choice:
#         Display label, ``"Front"`` or ``"Back"``.
#     """
#     st.subheader(f"📷 Auto-extract from sketch — {yard_choice} Yard  _(optional)_")
#     st.caption(
#         "Upload a photo or scan of the hand-drawn site sketch. The VLM will "
#         "read the grid structure, dimensions, and irregular shapes, then "
#         "pre-fill sections ⑥ and ⑦ below for you to review and accept. "
#         "**You can skip this entirely** and fill in sections ⑥–⑦ manually "
#         "as before — this is an accelerator, not a replacement."
#     )

#     # ── Provider selection + advanced options ──
#     with st.expander("⚙️ Extraction settings", expanded=False):
#         col_prov, col_check = st.columns([2, 1])
#         with col_prov:
#             label_to_idx = {p[0]: i for i, p in enumerate(PROVIDERS)}
#             chosen_label = st.selectbox(
#                 "Provider",
#                 options=list(label_to_idx.keys()),
#                 index=0,
#                 key=_ss_key(yard_key, "provider_label"),
#                 help="Pick a VLM provider. Gemini is cheaper and usually "
#                      "enough; Claude is better for messy/shadowed sketches.",
#             )
#             backend = PROVIDERS[label_to_idx[chosen_label]][1]
#             model = PROVIDERS[label_to_idx[chosen_label]][2]
#             st.caption(PROVIDERS[label_to_idx[chosen_label]][3])
#         with col_check:
#             messy = st.checkbox(
#                 "This sketch is messy",
#                 value=False,
#                 key=_ss_key(yard_key, "messy_flag"),
#                 help="If checked, auto-uses Claude regardless of the "
#                      "provider dropdown above. Use for shadowed, unclear, "
#                      "or unusually complex sketches.",
#             )
#             if messy and backend != "claude":
#                 backend = "claude"
#                 model = "claude-sonnet-4-6"
#                 st.info("→ Switched to Claude (messy flag set).")

#         # API-key availability hint (we don't show the keys, just whether
#         # they're configured).
#         key_env = "GEMINI_API_KEY" if backend == "gemini" else "ANTHROPIC_API_KEY"
#         if not os.environ.get(key_env):
#             # GEMINI_API_KEY can also be GOOGLE_API_KEY for Gemini.
#             if backend == "gemini" and os.environ.get("GOOGLE_API_KEY"):
#                 pass
#             else:
#                 st.warning(
#                     f"`{key_env}` is not set in this environment. Add it "
#                     f"to your `.env` file at the project root and restart "
#                     f"Streamlit."
#                 )

#         extra_hints = st.text_area(
#             "Field-worker hints _(optional)_",
#             value="",
#             placeholder=(
#                 "Any extra context you'd give a human reading this sketch. "
#                 "Examples: 'house is at the bottom of the page', 'all "
#                 "dimensions in feet', 'the cell at top-right is partially "
#                 "cut off by the page edge'."
#             ),
#             key=_ss_key(yard_key, "extra_hints"),
#             height=80,
#         )

#     # ── Upload ──
#     uploaded = st.file_uploader(
#         f"Upload {yard_choice.lower()}-yard sketch",
#         type=["jpg", "jpeg", "png", "heic", "webp"],
#         key=_ss_key(yard_key, "uploader"),
#         help="One sketch per yard. If your site has both Front and Back "
#              "yards on separate pages, upload them one at a time and "
#              "switch the yard dropdown above between extractions.",
#     )

#     col_run, col_clear = st.columns([2, 1])
#     with col_run:
#         run_clicked = st.button(
#             f"🔎 Extract grid from sketch — {yard_choice}",
#             type="primary",
#             disabled=(uploaded is None),
#             use_container_width=True,
#             key=_ss_key(yard_key, "run_btn"),
#         )
#     with col_clear:
#         clear_clicked = st.button(
#             "🗑️ Clear extraction",
#             disabled=(_ss_key(yard_key, "extraction") not in st.session_state),
#             use_container_width=True,
#             key=_ss_key(yard_key, "clear_btn"),
#         )
#     if clear_clicked:
#         _clear_extraction(yard_key)
#         st.success(f"Cleared VLM extraction for {yard_choice} yard.")
#         st.rerun()

#     # ── Run the VLM call ──
#     if run_clicked and uploaded is not None:
#         # Save the upload to a temp file the providers module can read.
#         suffix = os.path.splitext(uploaded.name)[1].lower() or ".jpg"
#         with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
#             tmp.write(uploaded.getbuffer())
#             tmp_path = tmp.name

#         with st.spinner(
#             f"Calling {PROVIDERS[0 if backend == 'gemini' else 1][0]} "
#             f"on {uploaded.name}…"
#         ):
#             try:
#                 result = extract_from_image(
#                     tmp_path,
#                     backend=backend,
#                     model=model,
#                     extra_hints=extra_hints or None,
#                 )
#             except Exception as exc:
#                 st.error(
#                     f"VLM call failed: **{type(exc).__name__}** — {exc}\n\n"
#                     f"Common causes: API key not set, network blocked, or "
#                     f"the image format isn't supported by the provider."
#                 )
#                 with st.expander("Full traceback", expanded=False):
#                     st.code(traceback.format_exc())
#                 return
#             finally:
#                 try:
#                     os.unlink(tmp_path)
#                 except OSError:
#                     pass

#         # Stash everything so the rerun renders the review panel.
#         st.session_state[_ss_key(yard_key, "extraction")]  = result.data
#         st.session_state[_ss_key(yard_key, "raw_response")] = result.raw_response
#         st.session_state[_ss_key(yard_key, "problems")]    = result.problems
#         st.session_state[_ss_key(yard_key, "backend_used")] = result.backend
#         st.session_state[_ss_key(yard_key, "model_used")]   = result.model
#         # Keep a snapshot of the image bytes so we can re-render the
#         # preview after rerun (Streamlit's uploader resets each rerun).
#         st.session_state[_ss_key(yard_key, "image_bytes")] = uploaded.getvalue()
#         st.session_state[_ss_key(yard_key, "image_name")]  = uploaded.name
#         st.rerun()

#     # ── Render the review panel if we have an extraction ──
#     extraction = st.session_state.get(_ss_key(yard_key, "extraction"))
#     if extraction:
#         _render_review_panel(yard_key, yard_choice, extraction)

#     st.markdown("---")


# # ════════════════════════════════════════════════════════════════
# #  Review panel — shown after a successful extraction
# # ════════════════════════════════════════════════════════════════

# def _render_review_panel(
#     yard_key: str,
#     yard_choice: str,
#     extraction: dict[str, Any],
# ) -> None:
#     """Side-by-side review: sketch on the left, extracted grid on the right."""
#     problems = st.session_state.get(_ss_key(yard_key, "problems"), [])
#     backend_used = st.session_state.get(_ss_key(yard_key, "backend_used"), "?")
#     model_used = st.session_state.get(_ss_key(yard_key, "model_used"), "?")
#     image_bytes = st.session_state.get(_ss_key(yard_key, "image_bytes"))
#     image_name = st.session_state.get(_ss_key(yard_key, "image_name"), "")

#     # ── Status banner ──
#     n_cells = len(extraction.get("cells", {}))
#     n_rows = len(extraction.get("rows", []))
#     overall_conf = extraction.get("overall_confidence", "?")
#     conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(overall_conf, "⚪")
#     st.success(
#         f"Extracted **{n_cells} cells** across **{n_rows} rows** "
#         f"({conf_emoji} overall confidence: **{overall_conf}**)  · "
#         f"_provider: {backend_used} · model: {model_used}_"
#     )

#     if problems:
#         with st.expander(f"⚠️ {len(problems)} validation problem(s) — please review", expanded=True):
#             for p in problems:
#                 st.warning(p)
#             st.caption(
#                 "These are issues with the VLM's response shape — accepting "
#                 "anyway may produce a partially-correct pre-fill, or you "
#                 "can adjust and re-extract."
#             )

#     if extraction.get("global_notes"):
#         st.info(f"📝 VLM notes: {extraction['global_notes']}")

#     # ── Side-by-side panel ──
#     col_img, col_table = st.columns([1, 1])

#     with col_img:
#         st.markdown(f"**Original sketch**  ·  _{image_name}_")
#         if image_bytes:
#             st.image(image_bytes, use_container_width=True)
#         else:
#             st.caption("_(sketch image not available — re-upload to see preview)_")

#     with col_table:
#         st.markdown("**Extracted grid**")
#         _render_extraction_table(extraction)

#     # ── Per-cell review (low/medium confidence only) ──
#     cells = extraction.get("cells", {})
#     flagged = [
#         (cid, c) for cid, c in cells.items()
#         if c.get("confidence", "high") in ("medium", "low")
#     ]
#     if flagged:
#         st.markdown(
#             f"#### 🟡 {len(flagged)} cell(s) flagged for review"
#         )
#         st.caption(
#             "The VLM was unsure about these. Skim them before accepting — "
#             "you can override anything later in sections ⑥–⑦, but a sanity "
#             "check now saves time."
#         )
#         for cid, cell in sorted(flagged):
#             conf = cell.get("confidence", "?")
#             emoji = "🟡" if conf == "medium" else "🔴"
#             note = cell.get("notes") or "(no note from VLM)"
#             with st.expander(
#                 f"{emoji} **{cid}** — {conf} confidence — {note[:80]}",
#                 expanded=False,
#             ):
#                 col_a, col_b, col_c = st.columns(3)
#                 with col_a:
#                     st.metric("Width (ft)", f"{cell['width']:.2f}")
#                 with col_b:
#                     st.metric("Height (ft)", f"{cell['height']:.2f}")
#                 with col_c:
#                     st.metric("Shape", cell.get("shape_kind", "rect"))
#                 if cell.get("shape_params"):
#                     st.json(cell["shape_params"])
#                 st.caption(f"Full note: {note}")
#     else:
#         st.success("🟢 All cells extracted with high confidence — looks clean.")

#     # ── Accept / Reject ──
#     st.markdown("")
#     col_accept, col_reject = st.columns([2, 1])
#     with col_accept:
#         accept_clicked = st.button(
#             f"✅ Accept & pre-fill sections ⑥–⑦ — {yard_choice}",
#             type="primary",
#             use_container_width=True,
#             key=_ss_key(yard_key, "accept_btn"),
#             help="Writes the extracted values into the form widgets below. "
#                  "You can still edit individual cells before clicking "
#                  "'Compute {yard} Yard'.",
#         )
#     with col_reject:
#         reject_clicked = st.button(
#             "❌ Reject & try again",
#             use_container_width=True,
#             key=_ss_key(yard_key, "reject_btn"),
#         )

#     if reject_clicked:
#         _clear_extraction(yard_key)
#         st.rerun()

#     if accept_clicked:
#         try:
#             n_written, warnings = _apply_to_session_state(extraction, yard_key)
#         except Exception as exc:
#             st.error(
#                 f"Could not apply extraction to form: {type(exc).__name__} — {exc}"
#             )
#             with st.expander("Traceback"):
#                 st.code(traceback.format_exc())
#             return

#         if warnings:
#             for w in warnings:
#                 st.warning(w)
#         st.success(
#             f"✅ Pre-filled **{n_written}** form fields. Scroll down to "
#             f"sections ⑥ and ⑦ to review, edit, and click **Compute "
#             f"{yard_choice} Yard**."
#         )
#         # Mark as applied so the user knows on subsequent renders.
#         st.session_state[_ss_key(yard_key, "applied")] = True
#         st.rerun()

#     if st.session_state.get(_ss_key(yard_key, "applied")):
#         st.info(
#             f"☑️ Form already pre-filled from this extraction. Re-click "
#             f"Accept to overwrite again, or scroll down to ⑥–⑦ to edit."
#         )


# # ════════════════════════════════════════════════════════════════
# #  Extracted-grid table renderer
# # ════════════════════════════════════════════════════════════════

# def _render_extraction_table(extraction: dict[str, Any]) -> None:
#     """Pretty-print the extracted grid as a compact HTML table.

#     Each cell shows its dimensions and a confidence badge. Uses
#     inline-styled HTML rather than a DataFrame so the L-shape of the
#     grid is visually obvious (placeholder dashes for missing cells).
#     """
#     rows = extraction.get("rows", [])
#     ncols_per_row = extraction.get("ncols_per_row", {})
#     cells = extraction.get("cells", {})
#     if not rows or not ncols_per_row:
#         st.write("_(no grid to display)_")
#         return
#     max_cols = extraction.get("max_cols") or max(ncols_per_row.values())

#     conf_bg = {
#         "high":   "#e8f5e9",
#         "medium": "#fff8e1",
#         "low":    "#ffebee",
#     }
#     conf_border = {
#         "high":   "#66bb6a",
#         "medium": "#ffb300",
#         "low":    "#e53935",
#     }

#     html = ["<table style='width:100%;border-collapse:collapse;font-size:0.85em;'>"]
#     for row in rows:
#         html.append("<tr>")
#         n_in_row = ncols_per_row.get(row, 0)
#         for c in range(1, max_cols + 1):
#             cid = f"{c}{row}"
#             if c <= n_in_row and cid in cells:
#                 cell = cells[cid]
#                 conf = cell.get("confidence", "high")
#                 bg = conf_bg.get(conf, "#fafafa")
#                 br = conf_border.get(conf, "#bbb")
#                 shape = cell.get("shape_kind", "rect")
#                 shape_badge = "" if shape == "rect" else f" ·{shape}"
#                 walkway_badge = " 🚶" if cell.get("is_walkway") else ""
#                 gap_r_badge = (" →" if (cell.get("gap_right") or 0) > 0 else "")
#                 html.append(
#                     f"<td style='background:{bg};border:1.5px solid {br};"
#                     f"border-radius:6px;padding:6px 8px;text-align:center;"
#                     f"vertical-align:top;'>"
#                     f"<div style='font-weight:600;'>{cid}{walkway_badge}{gap_r_badge}</div>"
#                     f"<div style='font-size:0.85em;color:#555;'>"
#                     f"{cell['width']:.1f}' × {cell['height']:.1f}'"
#                     f"<span style='color:#888;'>{shape_badge}</span>"
#                     f"</div>"
#                     f"</td>"
#                 )
#             else:
#                 html.append(
#                     "<td style='background:#fafafa;border:1px dashed #ddd;"
#                     "border-radius:6px;padding:6px 8px;text-align:center;"
#                     "color:#bbb;font-size:0.85em;'>—</td>"
#                 )
#         html.append("</tr>")
#     html.append("</table>")
#     st.markdown("".join(html), unsafe_allow_html=True)

#     # Row-gap-below display
#     row_gaps = extraction.get("row_gap_below", {})
#     nonzero_gaps = {r: g for r, g in row_gaps.items() if g}
#     if nonzero_gaps:
#         st.caption(
#             "**Row gaps (walkways between rows):** "
#             + ", ".join(f"below {r}: {g:.2f}'" for r, g in nonzero_gaps.items())
#         )

"""Streamlit review UI for VLM-extracted site sketches.

Designed to drop into `site_builder.py` between section ⑤ (Grid
Layout) and section ⑥ (Define Grid Rows). One public function:
``render_vlm_section(yard_key, yard_choice)``. When the user clicks
**Accept & Pre-fill Form**, the relevant ``st.session_state`` keys
are populated so the existing widgets in sections ⑥ and ⑦ pick up
the values automatically on the next rerun.

All session_state writes use the EXACT key names site_builder.py's
existing widgets read from — see the comment block at the top of
``_apply_to_session_state`` for the canonical list.
"""

from __future__ import annotations

import io
import os
import tempfile
import traceback
from typing import Any, Optional

import streamlit as st

from .providers import extract_from_image
from .schema import normalize_extraction, to_cell_data, validate_extraction


# ════════════════════════════════════════════════════════════════
#  Configuration
# ════════════════════════════════════════════════════════════════

# Which API providers to expose in the UI. Order matters — first is
# the default. Each tuple is (label, backend, default_model, blurb).
PROVIDERS: list[tuple[str, str, str, str]] = [
    ("Gemini 2.5 Flash (default — cheapest)",
     "gemini",
     "gemini-2.5-flash",
     "Free tier covers typical lab volume. Strong on clean sketches."),
    ("Claude Sonnet 4.6 (fallback — better on messy sketches)",
     "claude",
     "claude-sonnet-4-6",
     "~$0.01 per sketch. Best for shadowed, unclear, or complex sketches."),
]


# ════════════════════════════════════════════════════════════════
#  Session-state helpers
# ════════════════════════════════════════════════════════════════

def _ss_key(yard_key: str, suffix: str) -> str:
    """Build a yard-scoped session-state key used internally by the
    VLM section (e.g. to remember the last upload + extraction).
    """
    return f"vlm_{yard_key}_{suffix}"


def _clear_extraction(yard_key: str) -> None:
    """Forget the in-progress VLM extraction for this yard."""
    for suffix in ("extraction", "raw_response", "image_bytes",
                   "image_name", "problems", "backend_used", "model_used"):
        st.session_state.pop(_ss_key(yard_key, suffix), None)


def _apply_to_session_state(
    extraction: dict[str, Any],
    yard_key: str,
) -> tuple[int, list[str]]:
    """Push the VLM-extracted values into the session_state keys that
    site_builder.py's existing widgets already use.

    Returns (n_keys_written, warnings).

    Canonical key list (must stay in sync with site_builder.py):

      • rows_{yard_key}              — text input (comma-separated)
      • max_cols_{yard_key}          — number input (int)
      • ncols_{row}_{yard_key}       — number input per row
      • rowgap_{row}_{yard_key}__ft  — feet part of row-gap-below
      • rowgap_{row}_{yard_key}__in  — inches part
      • w_{cell_id}_{yard_key}__ft   — width feet
      • w_{cell_id}_{yard_key}__in   — width inches
      • h_{cell_id}_{yard_key}__ft   — height feet
      • h_{cell_id}_{yard_key}__in   — height inches
      • pat_{cell_id}_{yard_key}     — sample-ID pattern
      • walkway_{cell_id}_{yard_key} — walkway checkbox
      • gapr_{cell_id}_{yard_key}__ft, __in — gap to the right
      • shapekind_{cell_id}_{yard_key} — shape selectbox
      • notch_corner_{cell_id}_{yard_key}, notch_w_, notch_h_ (+__ft/__in)
      • angle_side_, angle_near_, angle_far_ (+__ft/__in)
      • poly_{cell_id}_{yard_key}    — custom polygon text area
    """
    warnings: list[str] = []
    n_written = 0

    def _set(key: str, value: Any) -> None:
        nonlocal n_written
        st.session_state[key] = value
        n_written += 1

    def _set_ft_in(key_base: str, decimal_feet: float) -> None:
        ft = int(decimal_feet)
        inches = round((decimal_feet - ft) * 12 * 2) / 2  # nearest 0.5"
        if inches >= 12:
            ft += 1
            inches = 0.0
        _set(f"{key_base}__ft", ft)
        _set(f"{key_base}__in", float(inches))

    # ── 1. Rows + grid layout ──
    rows = extraction.get("rows", [])
    if rows:
        _set(f"rows_{yard_key}", ", ".join(rows))

    ncols_per_row = extraction.get("ncols_per_row", {})
    if ncols_per_row:
        max_cols = extraction.get("max_cols") or max(ncols_per_row.values())
        _set(f"max_cols_{yard_key}", int(max_cols))
        for row, n in ncols_per_row.items():
            _set(f"ncols_{row}_{yard_key}", int(n))

    # ── 2. Row gaps below ──
    for row, gap in (extraction.get("row_gap_below") or {}).items():
        _set_ft_in(f"rowgap_{row}_{yard_key}", float(gap or 0.0))

    # ── 3. Per-cell dimensions, shape, and metadata ──
    cells = extraction.get("cells") or {}
    yard_choice_titlecase = "Front" if yard_key == "front" else "Back"

    for cid, cell in cells.items():
        try:
            _set_ft_in(f"w_{cid}_{yard_key}", float(cell["width"]))
            _set_ft_in(f"h_{cid}_{yard_key}", float(cell["height"]))
            _set(f"pat_{cid}_{yard_key}", f"{yard_choice_titlecase}_{cid}_")
            _set(f"walkway_{cid}_{yard_key}",
                 bool(cell.get("is_walkway", False)))
            _set_ft_in(f"gapr_{cid}_{yard_key}",
                       float(cell.get("gap_right", 0.0) or 0.0))

            shape_kind = cell.get("shape_kind", "rect")
            _set(f"shapekind_{cid}_{yard_key}", shape_kind)

            params = cell.get("shape_params") or {}
            if shape_kind == "notch":
                _set(f"notch_corner_{cid}_{yard_key}",
                     params.get("corner", "TL"))
                _set_ft_in(f"notch_w_{cid}_{yard_key}",
                           float(params.get("notch_w", 0)))
                _set_ft_in(f"notch_h_{cid}_{yard_key}",
                           float(params.get("notch_h", 0)))
            elif shape_kind == "angle":
                _set(f"angle_side_{cid}_{yard_key}",
                     params.get("side", "L"))
                _set_ft_in(f"angle_near_{cid}_{yard_key}",
                           float(params.get("inset_near", 0)))
                _set_ft_in(f"angle_far_{cid}_{yard_key}",
                           float(params.get("inset_far", 0)))
            elif shape_kind == "custom":
                pts = cell.get("local_polygon") or []
                if pts:
                    poly_text = "; ".join(
                        f"{p[0]:.2f},{p[1]:.2f}" for p in pts
                    )
                    _set(f"poly_{cid}_{yard_key}", poly_text)
        except (KeyError, ValueError, TypeError) as exc:
            warnings.append(f"cell '{cid}': could not pre-fill ({exc})")

    return n_written, warnings


# ════════════════════════════════════════════════════════════════
#  UI rendering — the public function
# ════════════════════════════════════════════════════════════════

def render_vlm_section(yard_key: str, yard_choice: str) -> None:
    """Render the VLM-upload-and-extract section for one yard.

    Call this from ``site_builder.py`` between section ⑤ and section ⑥.
    All state is scoped to ``yard_key`` so Front and Back never collide.

    Parameters
    ----------
    yard_key:
        Internal yard key, ``"front"`` or ``"back"``.
    yard_choice:
        Display label, ``"Front"`` or ``"Back"``.
    """
    st.subheader(f"📷 Auto-extract from sketch — {yard_choice} Yard  _(optional)_")
    st.caption(
        "Upload a photo or scan of the hand-drawn site sketch. The VLM will "
        "read the grid structure, dimensions, and irregular shapes, then "
        "pre-fill sections ⑥ and ⑦ below for you to review and accept. "
        "**You can skip this entirely** and fill in sections ⑥–⑦ manually "
        "as before — this is an accelerator, not a replacement."
    )

    # ── Provider selection + advanced options ──
    with st.expander("⚙️ Extraction settings", expanded=False):
        col_prov, col_check = st.columns([2, 1])
        with col_prov:
            label_to_idx = {p[0]: i for i, p in enumerate(PROVIDERS)}
            chosen_label = st.selectbox(
                "Provider",
                options=list(label_to_idx.keys()),
                index=0,
                key=_ss_key(yard_key, "provider_label"),
                help="Pick a VLM provider. Gemini is cheaper and usually "
                     "enough; Claude is better for messy/shadowed sketches.",
            )
            backend = PROVIDERS[label_to_idx[chosen_label]][1]
            model = PROVIDERS[label_to_idx[chosen_label]][2]
            st.caption(PROVIDERS[label_to_idx[chosen_label]][3])
        with col_check:
            messy = st.checkbox(
                "This sketch is messy",
                value=False,
                key=_ss_key(yard_key, "messy_flag"),
                help="If checked, auto-uses Claude regardless of the "
                     "provider dropdown above. Use for shadowed, unclear, "
                     "or unusually complex sketches.",
            )
            if messy and backend != "claude":
                backend = "claude"
                model = "claude-sonnet-4-6"
                st.info("→ Switched to Claude (messy flag set).")

        # API-key availability hint (we don't show the keys, just whether
        # they're configured).
        key_env = "GEMINI_API_KEY" if backend == "gemini" else "ANTHROPIC_API_KEY"
        if not os.environ.get(key_env):
            # GEMINI_API_KEY can also be GOOGLE_API_KEY for Gemini.
            if backend == "gemini" and os.environ.get("GOOGLE_API_KEY"):
                pass
            else:
                st.warning(
                    f"`{key_env}` is not set in this environment. Add it "
                    f"to your `.env` file at the project root and restart "
                    f"Streamlit."
                )

        extra_hints = st.text_area(
            "Field-worker hints _(optional)_",
            value="",
            placeholder=(
                "Any extra context you'd give a human reading this sketch. "
                "Examples: 'house is at the bottom of the page', 'all "
                "dimensions in feet', 'the cell at top-right is partially "
                "cut off by the page edge'."
            ),
            key=_ss_key(yard_key, "extra_hints"),
            height=80,
        )

    # ── Upload ──
    uploaded = st.file_uploader(
        f"Upload {yard_choice.lower()}-yard sketch",
        type=["jpg", "jpeg", "png", "heic", "webp"],
        key=_ss_key(yard_key, "uploader"),
        help="One sketch per yard. If your site has both Front and Back "
             "yards on separate pages, upload them one at a time and "
             "switch the yard dropdown above between extractions.",
    )

    col_run, col_clear = st.columns([2, 1])
    with col_run:
        run_clicked = st.button(
            f"🔎 Extract grid from sketch — {yard_choice}",
            type="primary",
            disabled=(uploaded is None),
            use_container_width=True,
            key=_ss_key(yard_key, "run_btn"),
        )
    with col_clear:
        clear_clicked = st.button(
            "🗑️ Clear extraction",
            disabled=(_ss_key(yard_key, "extraction") not in st.session_state),
            use_container_width=True,
            key=_ss_key(yard_key, "clear_btn"),
        )
    if clear_clicked:
        _clear_extraction(yard_key)
        st.success(f"Cleared VLM extraction for {yard_choice} yard.")
        st.rerun()

    # ── Run the VLM call ──
    if run_clicked and uploaded is not None:
        # Save the upload to a temp file the providers module can read.
        suffix = os.path.splitext(uploaded.name)[1].lower() or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = tmp.name

        with st.spinner(
            f"Calling {PROVIDERS[0 if backend == 'gemini' else 1][0]} "
            f"on {uploaded.name}…"
        ):
            try:
                result = extract_from_image(
                    tmp_path,
                    backend=backend,
                    model=model,
                    extra_hints=extra_hints or None,
                )
            except Exception as exc:
                err_str = str(exc)
                is_rate_limit = ("429" in err_str
                                 or "rate limit" in err_str.lower()
                                 or "quota" in err_str.lower())
                if is_rate_limit:
                    st.error(
                        f"**Rate-limited by the API** (after auto-retry).\n\n"
                        f"```\n{exc}\n```\n\n"
                        f"**What to try:**\n"
                        f"- Wait 60 seconds and click Extract again — "
                        f"per-minute quotas clear automatically.\n"
                        f"- If this keeps happening, you've hit a per-DAY "
                        f"limit. Check your usage at "
                        f"https://aistudio.google.com/app/apikey\n"
                        f"- Switch provider to **Claude** in the settings "
                        f"expander above (uses a different quota pool).\n"
                        f"- Or: pick **Gemini 2.5 Flash-Lite** for the "
                        f"highest free-tier throughput.\n"
                    )
                else:
                    st.error(
                        f"VLM call failed: **{type(exc).__name__}**\n\n"
                        f"```\n{exc}\n```\n\n"
                        f"Common causes: API key not set, network blocked, "
                        f"or the image format isn't supported by the provider."
                    )
                with st.expander("Full traceback", expanded=False):
                    st.code(traceback.format_exc())
                return
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # Stash everything so the rerun renders the review panel.
        st.session_state[_ss_key(yard_key, "extraction")]  = result.data
        st.session_state[_ss_key(yard_key, "raw_response")] = result.raw_response
        st.session_state[_ss_key(yard_key, "problems")]    = result.problems
        st.session_state[_ss_key(yard_key, "backend_used")] = result.backend
        st.session_state[_ss_key(yard_key, "model_used")]   = result.model
        # Keep a snapshot of the image bytes so we can re-render the
        # preview after rerun (Streamlit's uploader resets each rerun).
        st.session_state[_ss_key(yard_key, "image_bytes")] = uploaded.getvalue()
        st.session_state[_ss_key(yard_key, "image_name")]  = uploaded.name
        st.rerun()

    # ── Render the review panel if we have an extraction ──
    extraction = st.session_state.get(_ss_key(yard_key, "extraction"))
    if extraction:
        _render_review_panel(yard_key, yard_choice, extraction)

    st.markdown("---")


# ════════════════════════════════════════════════════════════════
#  Review panel — shown after a successful extraction
# ════════════════════════════════════════════════════════════════

def _render_review_panel(
    yard_key: str,
    yard_choice: str,
    extraction: dict[str, Any],
) -> None:
    """Side-by-side review: sketch on the left, extracted grid on the right."""
    problems = st.session_state.get(_ss_key(yard_key, "problems"), [])
    backend_used = st.session_state.get(_ss_key(yard_key, "backend_used"), "?")
    model_used = st.session_state.get(_ss_key(yard_key, "model_used"), "?")
    image_bytes = st.session_state.get(_ss_key(yard_key, "image_bytes"))
    image_name = st.session_state.get(_ss_key(yard_key, "image_name"), "")

    # ── Status banner ──
    n_cells = len(extraction.get("cells", {}))
    n_rows = len(extraction.get("rows", []))
    overall_conf = extraction.get("overall_confidence", "?")
    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(overall_conf, "⚪")
    st.success(
        f"Extracted **{n_cells} cells** across **{n_rows} rows** "
        f"({conf_emoji} overall confidence: **{overall_conf}**)  · "
        f"_provider: {backend_used} · model: {model_used}_"
    )

    if problems:
        with st.expander(f"⚠️ {len(problems)} validation problem(s) — please review", expanded=True):
            for p in problems:
                st.warning(p)
            st.caption(
                "These are issues with the VLM's response shape — accepting "
                "anyway may produce a partially-correct pre-fill, or you "
                "can adjust and re-extract."
            )

    if extraction.get("global_notes"):
        st.info(f"📝 VLM notes: {extraction['global_notes']}")

    # ── Side-by-side panel ──
    col_img, col_table = st.columns([1, 1])

    with col_img:
        st.markdown(f"**Original sketch**  ·  _{image_name}_")
        if image_bytes:
            st.image(image_bytes, use_container_width=True)
        else:
            st.caption("_(sketch image not available — re-upload to see preview)_")

    with col_table:
        st.markdown("**Extracted grid**")
        _render_extraction_table(extraction)

    # ── Per-cell review (low/medium confidence only) ──
    cells = extraction.get("cells", {})
    flagged = [
        (cid, c) for cid, c in cells.items()
        if c.get("confidence", "high") in ("medium", "low")
    ]
    if flagged:
        st.markdown(
            f"#### 🟡 {len(flagged)} cell(s) flagged for review"
        )
        st.caption(
            "The VLM was unsure about these. Skim them before accepting — "
            "you can override anything later in sections ⑥–⑦, but a sanity "
            "check now saves time."
        )
        for cid, cell in sorted(flagged):
            conf = cell.get("confidence", "?")
            emoji = "🟡" if conf == "medium" else "🔴"
            note = cell.get("notes") or "(no note from VLM)"
            with st.expander(
                f"{emoji} **{cid}** — {conf} confidence — {note[:80]}",
                expanded=False,
            ):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Width (ft)", f"{cell['width']:.2f}")
                with col_b:
                    st.metric("Height (ft)", f"{cell['height']:.2f}")
                with col_c:
                    st.metric("Shape", cell.get("shape_kind", "rect"))
                if cell.get("shape_params"):
                    st.json(cell["shape_params"])
                st.caption(f"Full note: {note}")
    else:
        st.success("🟢 All cells extracted with high confidence — looks clean.")

    # ── Accept / Reject ──
    st.markdown("")
    col_accept, col_reject = st.columns([2, 1])
    with col_accept:
        accept_clicked = st.button(
            f"✅ Accept & pre-fill sections ⑥–⑦ — {yard_choice}",
            type="primary",
            use_container_width=True,
            key=_ss_key(yard_key, "accept_btn"),
            help="Writes the extracted values into the form widgets below. "
                 "You can still edit individual cells before clicking "
                 "'Compute {yard} Yard'.",
        )
    with col_reject:
        reject_clicked = st.button(
            "❌ Reject & try again",
            use_container_width=True,
            key=_ss_key(yard_key, "reject_btn"),
        )

    if reject_clicked:
        _clear_extraction(yard_key)
        st.rerun()

    if accept_clicked:
        try:
            n_written, warnings = _apply_to_session_state(extraction, yard_key)
        except Exception as exc:
            st.error(
                f"Could not apply extraction to form: {type(exc).__name__} — {exc}"
            )
            with st.expander("Traceback"):
                st.code(traceback.format_exc())
            return

        if warnings:
            for w in warnings:
                st.warning(w)
        st.success(
            f"✅ Pre-filled **{n_written}** form fields. Scroll down to "
            f"sections ⑥ and ⑦ to review, edit, and click **Compute "
            f"{yard_choice} Yard**."
        )
        # Mark as applied so the user knows on subsequent renders.
        st.session_state[_ss_key(yard_key, "applied")] = True
        st.rerun()

    if st.session_state.get(_ss_key(yard_key, "applied")):
        st.info(
            f"☑️ Form already pre-filled from this extraction. Re-click "
            f"Accept to overwrite again, or scroll down to ⑥–⑦ to edit."
        )


# ════════════════════════════════════════════════════════════════
#  Extracted-grid table renderer
# ════════════════════════════════════════════════════════════════

def _render_extraction_table(extraction: dict[str, Any]) -> None:
    """Pretty-print the extracted grid as a compact HTML table.

    Each cell shows its dimensions and a confidence badge. Uses
    inline-styled HTML rather than a DataFrame so the L-shape of the
    grid is visually obvious (placeholder dashes for missing cells).
    """
    rows = extraction.get("rows", [])
    ncols_per_row = extraction.get("ncols_per_row", {})
    cells = extraction.get("cells", {})
    if not rows or not ncols_per_row:
        st.write("_(no grid to display)_")
        return
    max_cols = extraction.get("max_cols") or max(ncols_per_row.values())

    conf_bg = {
        "high":   "#e8f5e9",
        "medium": "#fff8e1",
        "low":    "#ffebee",
    }
    conf_border = {
        "high":   "#66bb6a",
        "medium": "#ffb300",
        "low":    "#e53935",
    }

    html = ["<table style='width:100%;border-collapse:collapse;font-size:0.85em;'>"]
    for row in rows:
        html.append("<tr>")
        n_in_row = ncols_per_row.get(row, 0)
        for c in range(1, max_cols + 1):
            cid = f"{c}{row}"
            if c <= n_in_row and cid in cells:
                cell = cells[cid]
                conf = cell.get("confidence", "high")
                bg = conf_bg.get(conf, "#fafafa")
                br = conf_border.get(conf, "#bbb")
                shape = cell.get("shape_kind", "rect")
                shape_badge = "" if shape == "rect" else f" ·{shape}"
                walkway_badge = " 🚶" if cell.get("is_walkway") else ""
                gap_r_badge = (" →" if (cell.get("gap_right") or 0) > 0 else "")
                html.append(
                    f"<td style='background:{bg};border:1.5px solid {br};"
                    f"border-radius:6px;padding:6px 8px;text-align:center;"
                    f"vertical-align:top;'>"
                    f"<div style='font-weight:600;'>{cid}{walkway_badge}{gap_r_badge}</div>"
                    f"<div style='font-size:0.85em;color:#555;'>"
                    f"{cell['width']:.1f}' × {cell['height']:.1f}'"
                    f"<span style='color:#888;'>{shape_badge}</span>"
                    f"</div>"
                    f"</td>"
                )
            else:
                html.append(
                    "<td style='background:#fafafa;border:1px dashed #ddd;"
                    "border-radius:6px;padding:6px 8px;text-align:center;"
                    "color:#bbb;font-size:0.85em;'>—</td>"
                )
        html.append("</tr>")
    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)

    # Row-gap-below display
    row_gaps = extraction.get("row_gap_below", {})
    nonzero_gaps = {r: g for r, g in row_gaps.items() if g}
    if nonzero_gaps:
        st.caption(
            "**Row gaps (walkways between rows):** "
            + ", ".join(f"below {r}: {g:.2f}'" for r, g in nonzero_gaps.items())
        )