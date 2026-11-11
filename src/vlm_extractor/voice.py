"""Voice → text for the correction box.

Voice is just another way to type: the transcript goes through the exact
same correction loop as a typed instruction. We transcribe with Gemini
(the lab already has a key for it) and bias it toward grid vocabulary so
"two B" comes out as "2B" and "four feet six" as 4' 6".
"""

from __future__ import annotations

import base64
import os

TRANSCRIBE_PROMPT = (
    "Transcribe this short voice note word for word. It is a field worker "
    "correcting a soil-sampling grid map. Cell labels are a number followed "
    "by a letter (write them like 2B, 3F, 1A). Lengths are in feet and "
    "inches (write them like 4', 10' 6\"). Return ONLY the transcript."
)


def transcribe(audio_bytes: bytes, mime: str = "audio/wav", *,
               model: str = "gemini-2.5-flash", timeout: int = 60) -> str:
    import requests

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Voice needs GEMINI_API_KEY (or GOOGLE_API_KEY) to transcribe.")
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        json={
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": mime,
                                 "data": base64.standard_b64encode(audio_bytes).decode("ascii")}},
                {"text": TRANSCRIBE_PROMPT},
            ]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1024},
        },
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Transcription failed ({resp.status_code}): {resp.text[:300]}")
    cands = resp.json().get("candidates") or []
    if not cands:
        raise RuntimeError("Transcription returned nothing — try again a bit louder.")
    text = "".join(p.get("text", "") for p in cands[0]["content"].get("parts", []))
    return text.strip()
