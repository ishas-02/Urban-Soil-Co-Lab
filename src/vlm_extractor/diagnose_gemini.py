"""Gemini API diagnostic — figures out why you're getting 429s.

Run this OUTSIDE Streamlit to see the raw API behavior:

    cd src/vlm_extractor
    python3 diagnose_gemini.py

It does five checks:
  1. API key is loaded (from env or .env)
  2. The key works for a 1-token text-only call (cheapest possible)
  3. List the models the key has access to
  4. Make a tiny image call (proves vision endpoint works for your key)
  5. Read back the rate-limit headers from a real call

Use this when the Streamlit extract button returns a 429 and you want
to know which quota was actually hit.
"""

import base64
import json
import os
import sys
from pathlib import Path

import requests


# ── Load .env so we can read GEMINI_API_KEY without Streamlit ──
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO / ".env")
except ImportError:
    pass


def _color(s, c):
    """Tiny ANSI helper."""
    codes = {"red": 31, "green": 32, "yellow": 33, "cyan": 36, "dim": 2}
    return f"\033[{codes.get(c, 0)}m{s}\033[0m"


def banner(s):
    print()
    print(_color("═" * 64, "cyan"))
    print(_color(f" {s}", "cyan"))
    print(_color("═" * 64, "cyan"))


def check_1_key():
    banner("[1] API key check")
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print(_color("  ✗ No GEMINI_API_KEY or GOOGLE_API_KEY in environment.", "red"))
        print(f"    Looked for .env at: {_REPO / '.env'}")
        print(f"    .env exists: {(_REPO / '.env').exists()}")
        sys.exit(1)
    # Show partial key only — never reveal in full.
    masked = key[:6] + "…" + key[-4:] if len(key) > 12 else "***"
    print(_color(f"  ✓ Key found: {masked}", "green"))
    return key


def check_2_text_call(key):
    banner("[2] Tiny text-only call (proves the key works at all)")
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": "Say hi in one word."}]}],
        "generationConfig": {"maxOutputTokens": 10, "temperature": 0.0},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    print(f"  HTTP status: {resp.status_code}")
    print(f"  Useful headers:")
    for h in ["x-goog-quota-remaining", "x-goog-quota-used", "retry-after",
              "x-ratelimit-limit", "x-ratelimit-remaining"]:
        if h in resp.headers:
            print(f"    {h}: {resp.headers[h]}")
    if resp.status_code == 200:
        out = resp.json()
        text = out.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        print(_color(f"  ✓ Key works. Response: {text!r}", "green"))
        if "usageMetadata" in out:
            print(f"  Token usage: {out['usageMetadata']}")
        return True
    elif resp.status_code == 429:
        print(_color("  ✗ 429 even on a 10-token text call — your key is hard-throttled.", "red"))
        try:
            err = resp.json().get("error", {})
            print(f"  Message: {err.get('message', '?')}")
            for d in err.get("details", []):
                print(f"  Detail: {json.dumps(d, indent=4)}")
        except Exception:
            print(f"  Body: {resp.text[:500]}")
        return False
    else:
        print(_color(f"  ✗ Non-200 response. Body:", "red"))
        try:
            print(json.dumps(resp.json(), indent=2)[:800])
        except Exception:
            print(resp.text[:800])
        return False


def check_3_list_models(key):
    banner("[3] What models can this key access?")
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    resp = requests.get(url, headers={"x-goog-api-key": key}, timeout=30)
    print(f"  HTTP status: {resp.status_code}")
    if resp.status_code != 200:
        print(_color("  ✗ Cannot list models. Key may be restricted.", "red"))
        try:
            print(json.dumps(resp.json(), indent=2)[:800])
        except Exception:
            print(resp.text[:500])
        return
    models = resp.json().get("models", [])
    relevant = [m for m in models if "gemini" in m.get("name", "").lower()]
    print(_color(f"  ✓ {len(relevant)} Gemini models visible:", "green"))
    for m in relevant[:15]:
        name = m.get("name", "?").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        has_gen = "generateContent" in methods
        print(f"    {'✓' if has_gen else ' '} {name}"
              f" — methods: {', '.join(methods[:3])}"
              + ("…" if len(methods) > 3 else ""))


def check_4_tiny_image_call(key):
    banner("[4] Tiny image call (proves vision endpoint works for your key)")
    # Smallest possible valid PNG — a 1x1 transparent pixel.
    pixel_png = base64.standard_b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
    )
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png",
                                 "data": base64.standard_b64encode(pixel_png).decode("ascii")}},
                {"text": "What color is this 1x1 image? One word."},
            ],
        }],
        "generationConfig": {"maxOutputTokens": 20, "temperature": 0.0},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    print(f"  HTTP status: {resp.status_code}")
    if resp.status_code == 200:
        out = resp.json()
        text = out.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        print(_color(f"  ✓ Vision endpoint works. Response: {text!r}", "green"))
        if "usageMetadata" in out:
            print(f"  Token usage: {out['usageMetadata']}")
    elif resp.status_code == 429:
        print(_color("  ✗ 429 on the smallest possible vision call.", "red"))
        try:
            err = resp.json().get("error", {})
            print(f"  Message: {err.get('message', '?')}")
            for d in err.get("details", []):
                print(f"  Detail: {json.dumps(d, indent=4)}")
        except Exception:
            print(f"  Body: {resp.text[:500]}")
    else:
        print(_color(f"  ✗ Non-200 response:", "red"))
        try:
            print(json.dumps(resp.json(), indent=2)[:800])
        except Exception:
            print(resp.text[:500])


def main():
    print(_color("Gemini API diagnostic", "cyan"))
    print(_color(f"Repo root: {_REPO}", "dim"))
    key = check_1_key()
    check_2_text_call(key)
    check_3_list_models(key)
    check_4_tiny_image_call(key)
    print()
    print(_color("Done.", "cyan"))
    print()
    print("If checks 2 and 4 returned 200, your key works and the 429s in")
    print("Streamlit are transient per-minute throttles — they'll clear on")
    print("their own. The new retry logic in providers.py handles those")
    print("automatically.")
    print()
    print("If checks 2 or 4 returned 429, you've hit a hard quota cap. See")
    print("usage at https://aistudio.google.com/app/apikey and consider")
    print("either waiting for the daily reset (00:00 Pacific) or enabling")
    print("billing for higher limits.")


if __name__ == "__main__":
    main()