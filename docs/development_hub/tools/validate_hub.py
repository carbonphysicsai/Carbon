#!/usr/bin/env python3
"""Validate the static-first Carbon Development Hub and generated outputs.

The validator uses the Python standard library only. Pass ``--repo-root`` when
running inside the Carbon repository to validate repository-facing links and
snapshot metadata against the checked-out tree.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

HUB_ROOT = Path(__file__).resolve().parents[1]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.text: list[str] = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if attr.get("id"):
            self.ids.add(str(attr["id"]))
        if tag == "a" and attr.get("href"):
            self.links.append(str(attr["href"]))
        self.in_script = self.in_script or tag == "script"
        self.in_style = self.in_style or tag == "style"

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if not self.in_script and not self.in_style and data.strip():
            self.text.append(data.strip())


def relative_target(source: Path, href: str) -> Path | None:
    if href.startswith(("#", "http://", "https://", "mailto:", "javascript:")):
        return None
    clean = urllib.parse.unquote(href.split("#", 1)[0].split("?", 1)[0])
    if not clean:
        return None
    return (source.parent / clean).resolve()


def duplicate_values(values: Iterable[str]) -> list[str]:
    values = list(values)
    return sorted({value for value in values if values.count(value) > 1})


def git_output(repo_root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    def fail(message: str) -> None:
        errors.append(message)

    data_path = HUB_ROOT / "data" / "hub_data_v2.json"
    events_path = HUB_ROOT / "data" / "change_events.json"
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"JSON parse failed for {data_path.name}: {exc}")
        data = {}
    try:
        events = json.loads(events_path.read_text(encoding="utf-8"))
        if not isinstance(events, list):
            fail("change_events.json must contain a list")
            events = []
    except Exception as exc:
        fail(f"JSON parse failed for {events_path.name}: {exc}")
        events = []

    waves = data.get("waves", [])
    tickets = data.get("tickets", [])
    routes = data.get("change_paths", [])
    maturity = data.get("maturity", [])
    wave_ids = [str(wave.get("id")) for wave in waves]
    ticket_ids = [str(ticket.get("id")) for ticket in tickets]

    if duplicate_values(wave_ids):
        fail(f"Duplicate wave IDs: {duplicate_values(wave_ids)}")
    if duplicate_values(ticket_ids):
        fail(f"Duplicate ticket IDs: {duplicate_values(ticket_ids)}")
    if wave_ids != list("ABCDEFGHIJKLMN"):
        fail(f"Expected Wave A-N order; found {wave_ids}")
    if len(maturity) != 8:
        fail(f"Expected eight maturity states; found {len(maturity)}")

    known = set(ticket_ids)
    for ticket in tickets:
        for field in ("depends_on", "unlocks"):
            for related in ticket.get(field, []):
                if related not in known and re.fullmatch(r"[A-Z]+-[A-Z0-9]+", str(related)):
                    warnings.append(f"{ticket['id']} {field} uncaptured ticket {related}")
        explainer = HUB_ROOT / "explainers" / "tickets" / (ticket["id"].lower().replace("-", "_") + ".md")
        if not explainer.exists():
            fail(f"Missing ticket explainer: {explainer.relative_to(HUB_ROOT)}")
    for wave in waves:
        explainer = HUB_ROOT / "explainers" / "waves" / f"wave_{wave['id'].lower()}.md"
        if not explainer.exists():
            fail(f"Missing wave explainer: {explainer.relative_to(HUB_ROOT)}")

    required_event_fields = {"event_id", "map_ref", "event_type", "status", "summary", "primary_detail"}
    allowed_event_types = {"decision", "adjustment", "bug", "blocker", "risk", "evidence"}
    allowed_event_statuses = {"proposed", "active", "blocked", "implemented", "superseded", "closed"}
    map_refs = {f"WAVE-{wave_id}" for wave_id in wave_ids}
    map_refs.update(f"WAVE-{ticket['wave']}/{ticket['id']}" for ticket in tickets)
    map_refs.add("SYSTEM/DEVELOPMENT-HUB")
    event_ids: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            fail("Each change event must be an object")
            continue
        missing = sorted(required_event_fields - set(event))
        if missing:
            fail(f"Event {event.get('event_id','<unknown>')} is missing {missing}")
        event_id = str(event.get("event_id"))
        event_ids.append(event_id)
        if event.get("map_ref") not in map_refs:
            fail(f"Event {event_id} has unknown map_ref {event.get('map_ref')}")
        if event.get("event_type") not in allowed_event_types:
            fail(f"Event {event_id} has invalid event_type {event.get('event_type')}")
        if event.get("status") not in allowed_event_statuses:
            fail(f"Event {event_id} has invalid status {event.get('status')}")
        summary = str(event.get("summary", ""))
        if not summary or len(summary) > 220:
            fail(f"Event {event_id} summary must contain 1-220 characters")
    if duplicate_values(event_ids):
        fail(f"Duplicate event IDs: {duplicate_values(event_ids)}")

    yaml_path = HUB_ROOT / "data" / "hub_index_v2.yaml"
    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
        for heading in ("meta:", "current:", "waves:", "tickets:", "change_paths:"):
            if heading not in yaml_text:
                fail(f"YAML index is missing {heading}")
        if "\t" in yaml_text:
            fail("YAML index contains tab indentation")
    except Exception as exc:
        fail(f"YAML index read failed: {exc}")

    for html_path in HUB_ROOT.rglob("*.html"):
        html_text = html_path.read_text(encoding="utf-8")
        parsed = LinkParser()
        try:
            parsed.feed(html_text)
        except Exception as exc:
            fail(f"{html_path.relative_to(HUB_ROOT)} HTML parse failed: {exc}")
            continue
        for href in parsed.links:
            target = relative_target(html_path, href)
            if target is not None and not target.exists():
                fail(f"{html_path.relative_to(HUB_ROOT)} has missing link {href}")

    markdown_link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for md_path in HUB_ROOT.rglob("*.md"):
        for href in markdown_link.findall(md_path.read_text(encoding="utf-8")):
            target = relative_target(md_path, href)
            if target is not None and not target.exists():
                fail(f"{md_path.relative_to(HUB_ROOT)} has missing link {href}")

    index_path = HUB_ROOT / "index.html"
    if not index_path.exists():
        fail("index.html is missing")
    else:
        index_text = index_path.read_text(encoding="utf-8")
        parsed = LinkParser()
        parsed.feed(index_text)
        required_ids = {"home", "hub-content", "start", "waves", "tickets", "routes", "events", "maturity", "glossary", "sources"}
        missing_ids = sorted(required_ids - parsed.ids)
        if missing_ids:
            fail(f"index.html is missing static sections: {missing_ids}")
        visible = " ".join(parsed.text)
        for phrase in (
            "Understand what is changing and why.",
            "New to Carbon",
            "Waves A through N",
            "Ticket index",
            "Recent map-level changes",
            data.get("current", {}).get("ticket_title", ""),
        ):
            if phrase and phrase not in visible:
                fail(f"index.html static content is missing: {phrase}")
        if len(visible) < 12000:
            fail("index.html contains too little static content; it may regress to a script-only shell")
        if "<script" in index_text.lower():
            warnings.append("index.html contains script content; the primary hub should remain usable without it")
        if index_text.count('class="card wave-card') != len(waves):
            fail("index.html wave card count does not match hub data")
        if index_text.count('class="card ticket-card') != len(tickets):
            fail("index.html ticket card count does not match hub data")
        if index_text.count('class="card route-card') != len(routes):
            fail("index.html change-route count does not match hub data")
        if index_text.count('class="event-card"') != len(events):
            fail("index.html event count does not match change_events.json")

    interactive_path = HUB_ROOT / "interactive.html"
    if interactive_path.exists():
        interactive_text = interactive_path.read_text(encoding="utf-8")
        match = re.search(r"const DATA = (.*?);\nconst \$ =", interactive_text, re.DOTALL)
        if not match:
            fail("interactive.html embedded DATA object was not found")
        else:
            try:
                embedded = json.loads(match.group(1))
                if embedded != data:
                    fail("interactive.html embedded DATA does not match hub_data_v2.json")
            except Exception as exc:
                fail(f"interactive.html embedded DATA parse failed: {exc}")

    if args.repo_root:
        repo_root = args.repo_root.resolve()
        if not (repo_root / ".git").exists():
            warnings.append(f"Repository root {repo_root} has no .git directory; Git SHA reconciliation skipped")
        else:
            head = git_output(repo_root, "rev-parse", "HEAD")
            if head and data.get("meta", {}).get("commit") != head:
                warnings.append(
                    f"Hub source snapshot {data.get('meta', {}).get('commit')} differs from checked-out HEAD {head}. "
                    "This is expected for the hub commit itself; reconcile on the next map-visible repository change."
                )

        active_wave = repo_root / ".agent" / "WAVE.md"
        if not active_wave.exists():
            fail("Repository root is missing .agent/WAVE.md")
        else:
            wave_text = active_wave.read_text(encoding="utf-8")
            wave_match = re.search(r"\*\*Current wave:\*\*\s*([A-Z])", wave_text)
            ticket_match = re.search(r"\*\*Selected ticket:\*\*\s*([^\s—]+)\s*—\s*`?([a-z_]+)`?", wave_text)
            if not wave_match:
                fail("Could not parse current wave from .agent/WAVE.md")
            elif wave_match.group(1) != data.get("current", {}).get("wave"):
                fail(f"Hub current wave {data.get('current',{}).get('wave')} != repository current wave {wave_match.group(1)}")
            if not ticket_match:
                fail("Could not parse selected ticket from .agent/WAVE.md")
            else:
                repo_ticket, repo_status = ticket_match.groups()
                if repo_ticket != data.get("current", {}).get("ticket"):
                    fail(f"Hub current ticket {data.get('current',{}).get('ticket')} != repository selected ticket {repo_ticket}")
                if repo_status != data.get("current", {}).get("ticket_status"):
                    fail(f"Hub current ticket status {data.get('current',{}).get('ticket_status')} != repository status {repo_status}")

        active_wave_id = data.get("current", {}).get("wave")
        board_path = repo_root / ".agent" / f"WAVE_{active_wave_id}.md"
        if not board_path.exists():
            fail(f"Repository root is missing active board .agent/WAVE_{active_wave_id}.md")
        else:
            board_status: dict[str, str] = {}
            for line in board_path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("|"):
                    continue
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if len(cells) >= 3 and re.fullmatch(r"[A-Z]+-[A-Z0-9]+", cells[0]) and cells[2] in {"todo", "in_progress", "done", "blocked"}:
                    board_status[cells[0]] = cells[2]
            hub_status = {ticket["id"]: ticket["status"] for ticket in tickets if ticket["wave"] == active_wave_id}
            if set(board_status) != set(hub_status):
                missing = sorted(set(board_status) - set(hub_status))
                extra = sorted(set(hub_status) - set(board_status))
                if missing:
                    fail(f"Hub is missing active-board tickets: {missing}")
                if extra:
                    fail(f"Hub has active-wave tickets absent from board: {extra}")
            for ticket_id in sorted(set(board_status) & set(hub_status)):
                if board_status[ticket_id] != hub_status[ticket_id]:
                    fail(f"Hub status {ticket_id}={hub_status[ticket_id]} != board status {board_status[ticket_id]}")

        for ticket in tickets:
            repo_path = ticket.get("repo_path")
            if repo_path and not (repo_root / repo_path).exists():
                fail(f"Missing ticket source path for {ticket['id']}: {repo_path}")

    print(f"Waves: {len(waves)}")
    print(f"Tickets: {len(tickets)}")
    print(f"Change routes: {len(routes)}")
    print(f"Events: {len(events)}")
    print(f"Maturity states: {len(maturity)}")
    print(f"Warnings: {len(warnings)}")
    for warning in warnings:
        print(f"WARN: {warning}")
    print(f"Errors: {len(errors)}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        raise SystemExit(1)
    print("Validation passed.")


if __name__ == "__main__":
    main()
