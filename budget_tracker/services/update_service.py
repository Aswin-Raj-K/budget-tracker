from __future__ import annotations

import json
import urllib.error
import urllib.request

from budget_tracker import __version__

_OWNER   = "Aswin-Raj-K"
_REPO    = "budget-tracker"
_API_URL = f"https://api.github.com/repos/{_OWNER}/{_REPO}/releases/latest"
_TIMEOUT = 8


def _parse_version(tag: str) -> tuple[int, ...]:
    """Convert 'v1.2.3' or '1.2.3-beta' to (1, 2, 3)."""
    tag = tag.lstrip("v").split("-")[0]
    return tuple(int("".join(c for c in p if c.isdigit()) or "0") for p in tag.split("."))


def check_for_update() -> tuple[bool, str, str]:
    """Query GitHub Releases and compare against the running version.

    Returns:
        (has_update, latest_version_str, html_url)

    Raises:
        urllib.error.URLError — network unreachable
        ValueError            — unexpected JSON structure
    """
    req = urllib.request.Request(
        _API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"BudgetTracker/{__version__}",
        },
    )
    try:
        resp_ctx = urllib.request.urlopen(req, timeout=_TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # No releases published yet — treat as "you're up to date".
            return False, __version__, ""
        raise

    with resp_ctx as resp:
        body = json.loads(resp.read().decode("utf-8"))

    tag_name = body.get("tag_name", "")
    html_url = body.get("html_url", _API_URL)
    if not tag_name:
        raise ValueError("GitHub API response missing 'tag_name'")

    has_update = _parse_version(tag_name) > _parse_version(__version__)
    return has_update, tag_name.lstrip("v"), html_url
