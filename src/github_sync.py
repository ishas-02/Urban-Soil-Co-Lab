import base64
import json
from datetime import datetime, timezone

import requests
import streamlit as st


def github_sync_enabled() -> bool:
    """Return True only when the GitHub token is available in Streamlit secrets."""
    try:
        return bool(st.secrets.get("GITHUB_TOKEN", ""))
    except Exception:
        return False


def _github_headers() -> dict:
    token = st.secrets.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN in Streamlit secrets.")

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def commit_json_to_github(data, commit_message: str | None = None):
    """Commit updated JSON data to GitHub using the GitHub Contents API.

    Required Streamlit secrets:
      GITHUB_TOKEN
      GITHUB_REPO
      GITHUB_BRANCH
      GITHUB_CONFIG_PATH

    For this project, use:
      GITHUB_REPO = "ishas-02/Urban-Soil-Co-Lab"
      GITHUB_BRANCH = "main"
      GITHUB_CONFIG_PATH = "Data/site_configs/site_configs.json"
    """
    repo = st.secrets.get("GITHUB_REPO", "ishas-02/Urban-Soil-Co-Lab")
    branch = st.secrets.get("GITHUB_BRANCH", "main")
    path = st.secrets.get("GITHUB_CONFIG_PATH", "Data/site_configs/site_configs.json")

    if not repo:
        raise RuntimeError("Missing GITHUB_REPO in Streamlit secrets.")
    if not path:
        raise RuntimeError("Missing GITHUB_CONFIG_PATH in Streamlit secrets.")

    headers = _github_headers()
    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # 1) Get the current file SHA. GitHub requires this when updating an
    # existing file; without it, the request will fail for tracked files.
    get_resp = requests.get(
        url,
        headers=headers,
        params={"ref": branch},
        timeout=20,
    )

    sha = None
    if get_resp.status_code == 200:
        sha = get_resp.json().get("sha")
    elif get_resp.status_code == 404:
        # File does not exist yet. The PUT request below will create it.
        sha = None
    else:
        raise RuntimeError(
            f"Could not read current GitHub config file: "
            f"{get_resp.status_code} {get_resp.text}"
        )

    # 2) Encode the JSON file content for the Contents API.
    json_text = json.dumps(data, indent=2, ensure_ascii=False)
    encoded_content = base64.b64encode(json_text.encode("utf-8")).decode("utf-8")

    if commit_message is None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        commit_message = f"Update site configs from Streamlit app - {now}"

    payload = {
        "message": commit_message,
        "content": encoded_content,
        "branch": branch,
    }

    if sha:
        payload["sha"] = sha

    # 3) Create the commit on GitHub.
    put_resp = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=20,
    )

    if put_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Could not commit updated config to GitHub: "
            f"{put_resp.status_code} {put_resp.text}"
        )

    return put_resp.json()
