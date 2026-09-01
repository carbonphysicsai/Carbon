"""Focused checks for the Development Hub Decision Console."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "decisions.json"
PAGE = ROOT / "decisions.html"
ATTENTION = {
    "NEEDS_REVIEW",
    "HUMAN_REQUIRED",
    "FOR_AWARENESS",
    "OWNER_DEFERRED",
    "RESOLVED",
}
REQUIRED = {
    "decision_id",
    "map_ref",
    "wave",
    "ticket",
    "title",
    "attention",
    "status",
    "audience",
    "question",
    "recommendation",
    "why",
    "if_kept",
    "if_changed",
    "affects",
    "response_url",
    "technical_detail_url",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def valid_github_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and parsed.path.startswith("/carbonphysicsai/Carbon/")
    )


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        fail("decisions.json must contain a decisions list")
    ids: set[str] = set()
    for item in decisions:
        if not isinstance(item, dict):
            fail("every decision must be an object")
        missing = REQUIRED - item.keys()
        if missing:
            fail(
                f"{item.get('decision_id', '<unknown>')} missing fields {sorted(missing)}"
            )
        decision_id = str(item["decision_id"])
        if decision_id in ids:
            fail(f"duplicate decision_id {decision_id}")
        ids.add(decision_id)
        if item["attention"] not in ATTENTION:
            fail(f"{decision_id} has unknown attention state {item['attention']!r}")
        if item["audience"] != "harsh":
            fail(f"{decision_id} must currently target audience 'harsh'")
        map_ref = str(item["map_ref"])
        if not re.fullmatch(
            r"(?:WAVE-[A-N](?:/[A-Z0-9-]+)?|SYSTEM/[A-Z0-9-]+(?:/[A-Z0-9-]+)*)",
            map_ref,
        ):
            fail(f"{decision_id} has invalid primary map_ref")
        if not isinstance(item["affects"], list):
            fail(f"{decision_id}.affects must be a list")
        for field in ("response_url", "technical_detail_url"):
            if not valid_github_url(str(item[field])):
                fail(f"{decision_id}.{field} must be a Carbon GitHub URL")
    page = PAGE.read_text(encoding="utf-8")
    for marker in (
        'id="needs-me"',
        'id="human-required"',
        'id="awareness"',
        'id="owner-deferred"',
        'id="resolved"',
        "KEEP ${d.decision_id}",
        "CHANGE ${d.decision_id}: <direction>",
        "BLOCKED ${d.decision_id}: <reason>",
        "DEFER_TO_OWNER ${d.decision_id}: <question or recommendation>",
        "data/decisions.json",
        "Open response location",
    ):
        if marker not in page:
            fail(f"decisions.html missing marker {marker!r}")
    hub = (ROOT / "index.html").read_text(encoding="utf-8")
    if 'href="decisions.html#needs-me"' not in hub:
        fail("primary Hub must link to Decisions → Needs Me")
    print(
        f"Decision Console: {len(decisions)} decisions, {len(ids)} unique IDs, focused checks passed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
