"""Correction-loop tests with a fake LLM (no API key needed)."""

from __future__ import annotations

import json

import pytest

from vlm_extractor.corrector import CORRECTION_SYSTEM_PROMPT, build_user_text, correct
from vlm_extractor.test_sketch_model import grid


def fake_llm(answer: dict | str):
    seen = {}

    def call(system, text, image):
        seen.update(system=system, text=text, image=image)
        return answer if isinstance(answer, str) else json.dumps(answer)
    return call, seen


def test_correct_applies_ops_and_keeps_original():
    m = grid()
    call, seen = fake_llm({"ops": [{"op": "walkway_between", "a": "2B", "b": "3B", "width": 4}],
                           "reply": "Added a 4 ft walkway between 2B and 3B.", "questions": []})
    out = correct(m, "between 2B and 3B there's a 4 foot walkway", call_fn=call)
    assert out["model"]["cells"]["B2"]["gap_right"] == 4
    assert m["cells"]["B2"].get("gap_right", 0) == 0
    assert out["reply"].startswith("Added")
    assert "USER SAYS:\nbetween 2B and 3B" in seen["text"]
    assert seen["system"] == CORRECTION_SYSTEM_PROMPT


def test_correct_passes_image_and_history():
    call, seen = fake_llm({"ops": [], "reply": "ok", "questions": []})
    correct(grid(), "make it 5 instead", image=(b"img", "image/png"),
            chat=[{"role": "user", "text": "2B is 4 ft wide"}], call_fn=call)
    assert seen["image"] == (b"img", "image/png")
    assert "user: 2B is 4 ft wide" in seen["text"]


def test_correct_question_only_changes_nothing():
    m = grid()
    call, _ = fake_llm({"ops": [], "reply": "", "questions": ["Which edge of 1A slants?"]})
    out = correct(m, "1A is slanted", call_fn=call)
    assert out["model"]["cells"] == m["cells"]
    assert out["model"]["questions"] == ["Which edge of 1A slants?"]


def test_correct_survives_bad_json_and_bad_ops():
    call, _ = fake_llm("sorry, I can't")
    out = correct(grid(), "x", call_fn=call)
    assert out["errors"] and out["model"]["cells"] == grid()["cells"]

    call, _ = fake_llm({"ops": [{"op": "set_cell", "cell": "Q7", "width": 1},
                                {"op": "set_row_height", "row": "B", "height": "8'"}],
                        "reply": "done"})
    out = correct(grid(), "x", call_fn=call)
    assert len(out["errors"]) == 1
    assert out["model"]["cells"]["B1"]["height"] == 8


def test_user_text_lists_open_checks():
    m = grid("A", 2)
    m["cells"]["A1"].update(shape_kind="angle", shape_params={"side": "L"})
    assert "slanted but the slant has no measurement" in build_user_text(m, "hi")
