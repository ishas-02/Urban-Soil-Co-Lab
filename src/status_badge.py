"""
status_badge.py — small green / red "is this app healthy?" pill, top-right
of every GroundSense app.

    from status_badge import render_status_badge
    render_status_badge("XRF Tech")      # right after st.set_page_config(...)

HOW IT DECIDES THE COLOUR
-------------------------
Two independent checks, so it catches both kinds of failure:

1. Server-side checks (run inside the app, re-checked every 30 s):
     • the shared data volume is mounted, readable and writable
     • the SharePoint sync has run in the last SYNC_STALE_HOURS hours
   Any failure → red, with the reason in the tooltip.

2. Browser-side heartbeat (JavaScript, every 10 s):
     pings this app's own /_stcore/health endpoint. If the pod has crashed,
     is restarting, or the route is down, the ping fails → red "Offline",
     even though Python can no longer run. When the app comes back it turns
     green again by itself.

Hover (desktop) or tap (tablet) the pill to see what was checked.

SAFETY
------
The badge must never break an app: every part is wrapped so that any error
inside it is swallowed and the app carries on normally.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

import streamlit as st

SYNC_STALE_HOURS = float(os.environ.get("BADGE_SYNC_STALE_HOURS", "3"))
HEARTBEAT_MS = 10_000


def _data_dir() -> str:
    try:
        from safe_io import _data_dir as d
        return str(d())
    except Exception:
        return os.environ.get(
            "SOIL_DATA_DIR",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
        )


@st.cache_data(ttl=15, show_spinner=False)
def _server_checks(_cache_key: int) -> dict:
    """Return {"ok": bool, "problems": [...], "details": [...]}."""
    problems, details = [], []
    d = _data_dir()

    # 1. Data volume
    if not os.path.isdir(d):
        problems.append("Data volume not mounted")
    else:
        try:
            os.listdir(d)
            if os.access(d, os.W_OK):
                details.append("Data volume: OK")
            else:
                problems.append("Data volume is read-only")
        except Exception as e:  # stale NFS handle, permission, …
            problems.append(f"Data volume unreadable ({type(e).__name__})")

    # 2. SharePoint sync freshness (the sync rewrites this file every run)
    state = os.path.join(d, ".sync_state.json")
    if os.path.exists(state):
        age_h = (time.time() - os.path.getmtime(state)) / 3600
        when = datetime.fromtimestamp(os.path.getmtime(state)).strftime("%b %d %H:%M")
        if age_h > SYNC_STALE_HOURS:
            problems.append(f"SharePoint sync has not run for {age_h:.0f} h (last {when} UTC)")
        else:
            details.append(f"SharePoint sync: OK (last {when} UTC)")
    else:
        details.append("SharePoint sync: no record yet")

    return {"ok": not problems, "problems": problems, "details": details}


SERVER_RECHECK_S = 30


def _badge_body(app_name: str) -> None:
    try:
        res = _server_checks(int(time.time() // 15))
    except Exception as e:
        res = {"ok": False, "problems": [f"Health check error ({type(e).__name__})"], "details": []}
    try:
        _render(app_name, res)
    except Exception:
        pass  # never let the badge break the app


def render_status_badge(app_name: str) -> None:
    """Draw the badge. Call once per app, right after st.set_page_config().

    The server checks re-run on their own every SERVER_RECHECK_S seconds
    (a Streamlit fragment — only the badge reruns, never the rest of the
    page, so nothing the user is typing is touched).
    """
    try:
        frag = st.fragment(run_every=SERVER_RECHECK_S)(_badge_body)
        frag(app_name)
    except Exception:
        _badge_body(app_name)


def _render(app_name: str, res: dict) -> None:
    import streamlit.components.v1 as components

    payload = json.dumps({
        "app": app_name,
        "ok": bool(res["ok"]),
        "lines": res["problems"] + res["details"],
        "checked": datetime.now().strftime("%H:%M:%S"),
        "beat": HEARTBEAT_MS,
    })

    # The badge logic is installed ONCE into the main page (its own <script>
    # element), so the pill and the heartbeat timer live in the page itself,
    # not in this component's iframe — Streamlit replaces that iframe on every
    # rerun, and timers owned by a removed iframe stop firing. Each rerun only
    # hands the latest server result to the already-running badge.
    components.html(
        "<script>(function(){var W=window.parent,D=W.document;if(!D)return;"
        "if(!W.__gsBadge){var s=D.createElement('script');s.textContent="
        + json.dumps(_BADGE_JS) +
        ";D.head.appendChild(s);}W.__gsBadge.update(" + payload + ");})();</script>",
        height=0,
    )


_BADGE_JS = r"""
(function () {
  var W = window, D = document;
  var pill = null, cfg = null, offline = false;

  function build() {
    var css = D.createElement("style");
    css.textContent = [
      "#gs-status-badge{position:fixed;top:4.1rem;right:1rem;z-index:999990;display:flex;",
      "align-items:center;gap:.4rem;padding:.22rem .65rem;border-radius:999px;",
      "font:600 12px/1.2 system-ui,-apple-system,sans-serif;background:#fff;",
      "border:1px solid #d0d7de;color:#1f2328;box-shadow:0 1px 2px rgba(0,0,0,.08);",
      "cursor:help;user-select:none}",
      "#gs-status-badge .dot{width:9px;height:9px;border-radius:50%;flex:none}",
      "#gs-status-badge.ok .dot{background:#1a7f37;box-shadow:0 0 0 3px rgba(26,127,55,.18)}",
      "#gs-status-badge.bad .dot{background:#cf222e;box-shadow:0 0 0 3px rgba(207,34,46,.2);",
      "animation:gsPulse 1.2s ease-in-out infinite}",
      "#gs-status-badge.bad{border-color:#cf222e;color:#a40e26}",
      "#gs-status-badge .tip{display:none;position:absolute;top:120%;right:0;min-width:230px;",
      "max-width:320px;padding:.55rem .7rem;border-radius:8px;background:#1f2328;color:#fff;",
      "font-weight:400;line-height:1.45;white-space:normal;box-shadow:0 4px 14px rgba(0,0,0,.2)}",
      "#gs-status-badge:hover .tip,#gs-status-badge.open .tip{display:block}",
      "@keyframes gsPulse{50%{opacity:.35}}",
      "@media (max-width:640px){#gs-status-badge{right:.6rem;top:3.9rem}}"
    ].join("");
    D.head.appendChild(css);
    pill = D.createElement("div");
    pill.id = "gs-status-badge";
    pill.setAttribute("role", "status");
    pill.innerHTML = '<span class="dot"></span><span class="lbl"></span><div class="tip"></div>';
    pill.addEventListener("click", function () { pill.classList.toggle("open"); });
    D.body.appendChild(pill);
  }

  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c];
    });
  }
  function draw(ok, label, lines) {
    if (!pill || !D.body.contains(pill)) build();
    pill.className = ok ? "ok" : "bad";
    pill.querySelector(".lbl").textContent = label;
    pill.setAttribute("aria-label", cfg.app + ": " + label);
    pill.querySelector(".tip").innerHTML =
      "<b>" + esc(cfg.app) + "</b><br>" + lines.map(esc).join("<br>");
  }
  function showServer() {
    draw(cfg.ok, cfg.ok ? "Live" : "Problem",
      [cfg.ok ? "All checks passed" : "Problem detected"].concat(cfg.lines, ["Checked " + cfg.checked]));
  }

  var url = W.location.origin + W.location.pathname.replace(/\/+$/, "") + "/_stcore/health";
  function beat() {
    var ctl = new AbortController();
    var t = setTimeout(function () { ctl.abort(); }, 5000);
    fetch(url, {cache: "no-store", signal: ctl.signal})
      .then(function (r) { return r.ok; }, function () { return false; })
      .then(function (up) {
        clearTimeout(t);
        if (!cfg) return;
        if (!up) {
          offline = true;
          draw(false, "Offline", ["App is not reachable — it may be restarting.",
            "This turns green again by itself when the app is back.",
            "If it restarted, entries you had not saved yet may be lost — check the list before continuing."]);
        } else if (offline) {
          // Back up. The last server result is from before the outage, so show
          // a plain "Live" until the app's own checks report again.
          offline = false;
          var now = new Date().toLocaleTimeString();
          cfg = Object.assign({}, cfg, {ok: true, checked: now,
            lines: ["Back online at " + now, "Detailed checks refresh within 30 s."]});
          showServer();
        }
      });
  }

  W.__gsBadge = {
    update: function (c) {
      cfg = c;
      if (!offline) showServer();
      if (!W.__gsBeat) { W.__gsBeat = setInterval(beat, c.beat); beat(); }
    }
  };
})();
"""
