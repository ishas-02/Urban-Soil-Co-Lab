"""
password_gate.py — the one lab password screen shared by all five apps.

    from password_gate import require_password
    require_password("Field Entry")      # right after st.set_page_config / badge

Same behaviour as the original XRF Tech login:
  * One shared password: `lab_password` in the app's Streamlit secrets
    (the OpenShift Secret `streamlit-secrets`, mounted at .streamlit/).
    The LAB_PASSWORD environment variable is accepted as a fallback.
  * Once entered, it stays unlocked for that browser tab's session.
  * Changing the password = update the Secret, restart the apps.

Safety:
  * Fails CLOSED: if no password is configured, the app shows an error and
    does not open — it never silently lets everyone in.
  * Constant-time comparison (hmac.compare_digest).
"""
from __future__ import annotations

import hmac
import os

import streamlit as st

_KEY_OK = "password_correct"      # same session key the XRF Tech app always used
_KEY_INPUT = "password"


def _configured_password() -> str | None:
    try:
        pw = st.secrets.get("lab_password")
    except Exception:              # no secrets.toml at all
        pw = None
    pw = pw or os.environ.get("LAB_PASSWORD")
    return str(pw) if pw else None


def _check() -> None:
    expected = _configured_password()
    given = st.session_state.get(_KEY_INPUT, "")
    ok = bool(expected) and hmac.compare_digest(str(given).encode(), expected.encode())
    st.session_state[_KEY_OK] = ok
    if ok:
        del st.session_state[_KEY_INPUT]      # don't keep the password in memory


def require_password(app_name: str = "") -> None:
    """Show the login screen and stop the page until the right password is entered."""
    if st.session_state.get(_KEY_OK) is True:
        return

    title = "### 🔒 GroundSense Tech Portal Login"
    if app_name:
        title += f"\n#### {app_name}"
    st.markdown(title)

    if not _configured_password():
        st.error("🚫 This app's password is not configured yet, so it is locked. "
                 "Please contact the platform administrator.")
        st.stop()

    st.text_input("Enter Lab Password", type="password", on_change=_check, key=_KEY_INPUT)
    if st.session_state.get(_KEY_OK) is False:
        st.error("🚫 Incorrect password. Please try again.")
    st.stop()
