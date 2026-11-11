"""End-to-end UI test of the new step ⑥ with a fake VLM (no API key).

Uses Streamlit's AppTest to click through: start → describe grid →
correct → undo, and checks the variables handed to Compute.
Run from src/:  python -m pytest vlm_extractor/test_sketch_ui.py -q
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

SCRIPT = '''
import json
import streamlit as st
import vlm_extractor.sketch_ui as ui

SCRIPTED = {
    "make the grid": {"ops": [
        {"op": "add_row", "row": "A", "ncols": 3, "width": 10, "height": 10},
        {"op": "add_row", "row": "B", "ncols": 3, "width": 10, "height": 10}],
        "reply": "Made a 2 x 3 grid.", "questions": []},
    "walkway": {"ops": [{"op": "walkway_between", "a": "2B", "b": "3B", "width": 4}],
                "reply": "Added a 4 ft walkway between 2B and 3B.", "questions": []},
}

def fake_default_call(backend, model_name=None, timeout=90):
    def call(system, text, image):
        said = text.rsplit("USER SAYS:\\n", 1)[1]
        for k, v in SCRIPTED.items():
            if k in said:
                return json.dumps(v)
        return json.dumps({"ops": [], "reply": "", "questions": ["Which cell?"]})
    return call

ui.default_call = fake_default_call
out = ui.render_sketch_builder("back", "Back")
st.session_state["_out"] = out
'''


def _app():
    at = AppTest.from_string(SCRIPT, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def _button(at, text):
    return next(b for b in at.button if text in b.label)


def _say(at, text):
    at.text_area(key="sk_back_fix_text").set_value(text)
    # AppTest can keep a stale copy of the form after st.rerun(); the live
    # submit button is always the last one rendered.
    [b for b in at.button if b.label.startswith("Apply ➜")][-1].click().run()
    assert not at.exception, at.exception


def test_full_flow_without_photo():
    at = _app()
    assert at.session_state["_out"] is None

    _button(at, "Start without photo").click().run()
    _say(at, "make the grid please")
    out = at.session_state["_out"]
    assert out["rows"] == ["A", "B"] and len(out["cell_data"]) == 6
    assert out["cell_data"]["B2"]["pattern"] == "Back_2B_"

    _say(at, "there is a walkway between 2B and 3B")
    assert at.session_state["_out"]["cell_data"]["B2"]["gap_right"] == 4

    _button(at, "Undo").click().run()
    assert at.session_state["_out"]["cell_data"]["B2"]["gap_right"] == 0

    _say(at, "something vague")
    md = " ".join(m.value for m in at.markdown)
    assert "Which cell?" in md
    assert not at.exception


def test_start_over_clears():
    at = _app()
    _button(at, "Start without photo").click().run()
    _say(at, "make the grid")
    _button(at, "Start over").click().run()
    assert at.session_state["_out"] is None
