#!/usr/bin/env python3
"""Deterministically render the Carbon Development Hub from JSON source data.

The tool intentionally uses only the Python standard library. ``index.html``
is a complete static page; ``interactive.html`` is an optional generated app.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "hub_data_v2.json"
EVENTS_PATH = ROOT / "data" / "change_events.json"
TEMPLATE_PATH = ROOT / "tools" / "templates" / "interactive_template.html"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return value


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def ticket_filename(ticket_id: str) -> str:
    return ticket_id.lower().replace("-", "_") + ".md"


def list_html(values: Iterable[object], *, ordered: bool = False) -> str:
    values = list(values)
    if not values:
        return '<p class="muted">None captured.</p>'
    tag = "ol" if ordered else "ul"
    return (
        f"<{tag}>" + "".join(f"<li>{esc(value)}</li>" for value in values) + f"</{tag}>"
    )


def badges(values: Iterable[object], prefix: str = "") -> str:
    rendered = "".join(
        f'<span class="badge">{esc(prefix)}{esc(value)}</span>' for value in values
    )
    return rendered or '<span class="badge muted">None captured</span>'


def links_html(items: Iterable[dict[str, str]]) -> str:
    rows = []
    for item in items:
        label, url = item.get("label", "Repository detail"), item.get("url", "")
        extra = (
            ' target="_blank" rel="noopener noreferrer"'
            if url.startswith(("http://", "https://"))
            else ""
        )
        rows.append(f'<li><a href="{esc(url)}"{extra}>{esc(label)}</a></li>')
    return (
        '<ul class="links">' + "".join(rows) + "</ul>"
        if rows
        else '<p class="muted">No repository link captured.</p>'
    )


def links_markdown(items: Iterable[dict[str, str]]) -> str:
    rows = [f"- [{item['label']}]({item['url']})" for item in items]
    return "\n".join(rows) if rows else "- No repository link captured."


def ceiling(data: dict[str, Any], record: dict[str, Any], kind: str) -> str:
    if record.get("maturity_ceiling"):
        return str(record["maturity_ceiling"])
    return str(
        data["authority_ceilings"][f"{kind}_status"].get(
            record.get("status"), "No ceiling captured."
        )
    )


def artifact_coverage(ticket: dict[str, Any]) -> str:
    labels = " ".join(
        str(item.get("label", "")).lower() for item in ticket.get("repo_links", [])
    )
    kinds = {
        "Ticket": ("ticket",),
        "Plan": ("plan",),
        "Contract/specification": ("contract", "spec"),
        "Decision record": ("decision",),
        "Pull request": ("pr #", "pull request"),
        "Evidence record": ("evidence",),
    }
    rows = []
    for label, needles in kinds.items():
        state = (
            "linked above"
            if any(needle in labels for needle in needles)
            else "missing or future in the captured state"
        )
        rows.append(f"<li><strong>{esc(label)}:</strong> {esc(state)}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def ordered_unique(values: Iterable[object]) -> list[str]:
    """Return source-ordered, stringified values without duplicates."""
    return list(dict.fromkeys(str(value) for value in values))


def ticket_wave_ids(data: dict[str, Any]) -> list[str]:
    """Return only waves represented by the captured ticket inventory."""
    return ordered_unique(ticket["wave"] for ticket in data["tickets"])


def human_join(values: Iterable[object]) -> str:
    rendered = [str(value) for value in values]
    if not rendered:
        return "none"
    if len(rendered) == 1:
        return rendered[0]
    if len(rendered) == 2:
        return f"{rendered[0]} and {rendered[1]}"
    return f"{', '.join(rendered[:-1])}, and {rendered[-1]}"


def ticket_inventory_label(data: dict[str, Any]) -> str:
    return human_join(f"Wave {wave_id}" for wave_id in ticket_wave_ids(data))


def wave_status_summary(data: dict[str, Any]) -> str:
    current_wave = data["current"]["wave"]
    return (
        "Closed waves remain closed only in their recorded bounded scopes. "
        f"Wave {current_wave} is active only through its controlling board and "
        "selected ticket. Planned waves remain planning context, not implementation "
        "permission."
    )


CSS = r"""
:root{--ink:#182326;--muted:#586a70;--paper:#f4f6f5;--panel:#fff;--line:#ccd6d9;--dark:#101a1e;--blue:#155f88;--blue-soft:#e7f2f8;--green:#176847;--green-soft:#e5f3eb;--amber:#8b4d00;--amber-soft:#fff0d6;--red:#943838;--shadow:0 10px 30px rgba(16,29,35,.08);--radius:18px}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}a{color:#075c89;text-decoration-thickness:.09em;text-underline-offset:.16em;overflow-wrap:anywhere}:focus-visible{outline:3px solid #f0a236;outline-offset:3px;border-radius:4px}.skip{position:absolute;top:-5rem;left:1rem;background:#fff;color:#000;padding:.8rem 1rem;z-index:100}.skip:focus{top:1rem}.hero{background:var(--dark);color:#fff;padding:2.5rem max(1.2rem,calc((100vw - 1420px)/2))}.hero h1{font-size:clamp(2.2rem,6vw,4.7rem);line-height:1;letter-spacing:-.045em;margin:.5rem 0 1rem}.hero p{max-width:1000px;color:#cfdbdf}.eyebrow{font-size:.75rem;font-weight:850;letter-spacing:.14em;text-transform:uppercase;color:#a9d8f3}.nav{position:sticky;top:0;z-index:20;background:#fff;border-bottom:1px solid var(--line)}.nav ul{max-width:1420px;margin:0 auto;padding:.7rem 1.2rem;display:flex;gap:.35rem;overflow-x:auto;list-style:none}.nav a{display:block;padding:.5rem .65rem;border-radius:8px;color:var(--ink);font-weight:700;text-decoration:none;white-space:nowrap}.nav a:hover{background:var(--blue-soft)}main{max-width:1420px;margin:auto;padding:1.4rem 1.2rem 5rem}.section{scroll-margin-top:5rem;margin:1.5rem 0;padding:clamp(1rem,3vw,2rem);background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow)}.section>h2{font-size:clamp(1.7rem,3vw,2.5rem);line-height:1.1;margin:.2rem 0 .5rem}.lede{font-size:1.08rem;color:var(--muted);max-width:1100px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:1rem}.card{min-width:0;padding:1.1rem;border:1px solid var(--line);border-radius:14px;background:#fff}.card h3{line-height:1.2;margin:.15rem 0 .5rem}.card h4{margin:1rem 0 .25rem}.current{background:linear-gradient(135deg,var(--dark),#1c333c);color:#fff}.current a{color:#abe0ff}.current .card{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.2)}.current .muted{color:#c7d4d8}.status{display:inline-block;padding:.18rem .55rem;border-radius:999px;background:#e9edef;color:#34464c;text-transform:uppercase;letter-spacing:.06em;font-size:.72rem;font-weight:850}.status.closed,.status.done{background:var(--green-soft);color:var(--green)}.status.active,.status.in_progress{background:var(--amber-soft);color:var(--amber)}.badge{display:inline-block;padding:.18rem .5rem;margin:.12rem;border:1px solid var(--line);border-radius:999px;background:#f7f9f9;font-size:.82rem}.muted{color:var(--muted)}.boundary{border-left:4px solid var(--amber);background:var(--amber-soft);padding:.8rem 1rem;border-radius:0 10px 10px 0}.fail{border-left:4px solid var(--red);background:#fae9e9;color:var(--ink);padding:.8rem 1rem;border-radius:0 10px 10px 0}.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.55rem;margin:.8rem 0}.meta div{padding:.55rem .7rem;border-radius:9px;background:#eef3f4}.current .meta div{background:rgba(255,255,255,.1)}.meta strong{display:block;text-transform:uppercase;letter-spacing:.05em;font-size:.72rem;color:var(--muted)}.current .meta strong{color:#bfd0d6}.wave{border-top:5px solid #96a5aa}.wave.closed{border-top-color:var(--green)}.wave.active{border-top-color:#d7871a}.ticket{border-left:5px solid #96a5aa}.ticket.done{border-left-color:var(--green)}.ticket.in_progress{border-left-color:#d7871a}.links{padding-left:1.1rem}.links li{margin:.25rem 0}code{padding:.08rem .28rem;background:#edf1f2;border-radius:5px;overflow-wrap:anywhere}.current code{background:rgba(255,255,255,.13)}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:.65rem;border-bottom:1px solid var(--line)}th{background:#eef3f4}.footer{padding:2rem max(1.2rem,calc((100vw - 1420px)/2));background:var(--dark);color:#d6e0e3}.footer a{color:#abe0ff}@media(max-width:700px){.nav{position:static}.nav ul{flex-wrap:wrap}.hero{padding:1.6rem 1rem}.hero h1{font-size:2.45rem}.section{padding:1rem;border-radius:12px}.grid,.meta{grid-template-columns:1fr}th,td{min-width:10rem}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}@media print{.nav{position:static}.section{box-shadow:none}.hero{background:#fff;color:#000}.hero p{color:#333}}
"""


def render_static(data: dict[str, Any], events: list[dict[str, Any]]) -> str:
    meta, current = data["meta"], data["current"]
    ticket_waves = ticket_inventory_label(data)
    wave_summary = wave_status_summary(data)
    snapshot_commit = str(meta["authority_snapshot_commit"])
    snapshot_short = snapshot_commit[:8]
    nav_items = (
        ("start", "Start here"),
        ("current", "Current"),
        ("waves", "Waves"),
        ("tickets", "Tickets"),
        ("changes", "Change routes"),
        ("decisions", "Decisions"),
        ("events", "Events"),
        ("maturity", "Maturity"),
        ("glossary", "Glossary"),
        ("sources", "Sources"),
        ("publication", "Publication"),
    )
    nav = "".join(
        f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in nav_items
    )

    orientation = (
        (
            "What is Carbon?",
            "An incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.",
        ),
        (
            "Why separate authorities?",
            "Science owns scientific meaning; specifications own exact semantics; boards and tickets authorize bounded work; implementation, review, and evidence prove only recorded scope; business and publications remain separate planes.",
        ),
        (
            "What is a wave?",
            "A bounded development stage with a system outcome, predecessor and successor relationships, an authority ceiling, and a closeout gate.",
        ),
        (
            "What is a ticket?",
            "The smallest selected unit of authorized work. It owns scope, dependencies, reviewers, non-goals, and definition of done.",
        ),
        (
            "What is a decision record?",
            "A durable choice with rationale, alternatives, downstream effects, reversibility, and an exact change or supersession path.",
        ),
        (
            "What does a PR prove?",
            "The exact implementation, review, repairs, tests, and merge identity. It does not itself prove science, security, or production qualification.",
        ),
        (
            "What does evidence prove?",
            "Only what passed, at which identity, in which bounded scope, and under which maturity ceiling.",
        ),
        (
            "Where should I begin?",
            "Read this orientation, the current position, and the active ticket explainer; then follow the repository links before implementing anything.",
        ),
    )
    orientation_html = "".join(
        f'<article class="card"><h3>{esc(title)}</h3><p>{esc(body)}</p></article>'
        for title, body in orientation
    )

    wave_cards = []
    waves = data["waves"]
    for wave in waves:
        predecessor = wave.get("predecessor")
        successor = wave.get("successor")
        before = (
            f"Wave {predecessor}"
            if predecessor
            else "Constitution and repository orientation"
        )
        after = (
            f"Wave {successor}"
            if successor
            else "Only a prospectively authorized successor"
        )
        wave_cards.append(
            f"""<article class="card wave {esc(wave["status"])}" id="wave-{esc(wave["id"])}"><span class="status {esc(wave["status"])}">{esc(wave["status"])}</span><h3>Wave {esc(wave["id"])}: {esc(wave["title"])}</h3><p><strong>Purpose:</strong> {esc(wave["one_line"])}</p><p><strong>What:</strong> {esc(wave["what"])}</p><p><strong>Why:</strong> {esc(wave["why"])}</p><p><strong>Success and unlocks:</strong> {esc(wave["success"])} {esc(wave["unlocks"])}</p><p class="boundary"><strong>Still unavailable:</strong> {esc(wave["does_not"])}</p><p><strong>Authority ceiling:</strong> {esc(ceiling(data, wave, "wave"))}</p><div class="meta"><div><strong>Predecessor</strong>{esc(before)}</div><div><strong>Successor</strong>{esc(after)}</div><div><strong>Map ref</strong><code>WAVE-{esc(wave["id"])}</code></div></div><p><strong>Key objects:</strong> {badges(wave.get("objects", []))}</p><p><strong>Captured tickets:</strong> {badges(wave.get("ticket_ids", []))}</p><h4>Repository detail</h4>{links_html(wave.get("repo_links", []))}</article>"""
        )

    ticket_cards = []
    for ticket in data["tickets"]:
        dependencies = list(ticket.get("depends_on", [])) + list(
            ticket.get("depends_on_context", [])
        )
        downstream = list(ticket.get("unlocks", [])) + list(
            ticket.get("unlocks_context", [])
        )
        stage = (
            ticket.get("current_stage")
            or "No more specific current stage is supported; use the captured status and repository evidence."
        )
        ticket_cards.append(
            f"""<article class="card ticket {esc(ticket["status"])}" id="ticket-{esc(ticket["id"])}"><span class="status {esc(ticket["status"])}">{esc(ticket["status"])}</span><h3>{esc(ticket["id"])}: {esc(ticket["title"])}</h3><p><strong>Purpose:</strong> {esc(ticket["one_line"])}</p><p><strong>What it adds:</strong> {esc(ticket["adds"])}</p><p><strong>Why now:</strong> {esc(ticket["why"])}</p><p class="boundary"><strong>Explicit non-goals:</strong> {esc(ticket["does_not"])}</p><div class="meta"><div><strong>Map ref</strong><code>WAVE-{esc(ticket["wave"])}/{esc(ticket["id"])}</code></div><div><strong>Driver</strong>{esc(ticket["owner"])}</div><div><strong>Reviewer route</strong>{esc(ticket["reviewer"])}</div><div><strong>Target</strong>{esc(ticket["target"])}</div></div><p><strong>Dependencies:</strong> {badges(dependencies)}</p><p><strong>Downstream consumers:</strong> {badges(downstream)}</p><p><strong>Current stage:</strong> {esc(stage)}</p><p><strong>Maturity ceiling:</strong> {esc(ceiling(data, ticket, "ticket"))}</p><h4>Repository detail</h4>{links_html(ticket.get("repo_links", []))}<h4>Artifact coverage</h4>{artifact_coverage(ticket)}</article>"""
        )

    route_cards = []
    for route in data["change_paths"]:
        route_cards.append(
            f"""<article class="card" id="change-{esc(route["id"])}"><h3>{esc(route["title"])}</h3><p>{esc(route["summary"])}</p><p><strong>Start:</strong> {esc(route["start"])}</p><p><strong>Why this route:</strong> {esc(route["why_route"])}</p><p><strong>Waves:</strong> {badges(route["waves"], "Wave ")}</p><p><strong>Ticket anchors:</strong> {badges(route["tickets"])}</p><h4>Decisions to name</h4>{list_html(route["decisions"])}<h4>Human-owned or approved inputs</h4>{list_html(route["human_reserved"])}<h4>Repository handoff</h4>{list_html(route["repo_flow"], ordered=True)}<h4>Repository authority</h4>{links_html(route.get("repo_links", []))}<p class="boundary"><strong>Boundary:</strong> {esc(route["warning"])}</p></article>"""
        )

    event_cards = []
    for event in events:
        detail = str(event["primary_detail"])
        detail_html = (
            f'<a href="{esc(detail)}" target="_blank" rel="noopener noreferrer">{esc(detail)}</a>'
            if detail.startswith(("http://", "https://"))
            else f"<code>{esc(detail)}</code>"
        )
        event_cards.append(
            f"""<article class="card" id="event-{esc(event["event_id"])}"><span class="status {esc(event["status"])}">{esc(event["event_type"])} · {esc(event["status"])}</span><h3>{esc(event["event_id"])}</h3><p>{esc(event["summary"])}</p><div class="meta"><div><strong>Primary map ref</strong><code>{esc(event["map_ref"])}</code></div><div><strong>Owner lane</strong>{esc(event["owner_lane"])}</div><div><strong>Supersedes</strong>{esc(event.get("supersedes") or "None")}</div></div><p><strong>Affects:</strong> {badges(event.get("affects", []))}</p><p><strong>Primary detail:</strong> {detail_html}</p></article>"""
        )

    maturity_rows = "".join(
        f'<tr><th scope="row">{esc(item["label"])}</th><td>{esc(item["meaning"])}</td><td>{esc(item["proof"])}</td><td>{esc(item["not_implied"])}</td></tr>'
        for item in data["maturity"]
    )
    glossary = "".join(
        f'<article class="card"><h3>{esc(item["term"])}</h3><p>{esc(item["definition"])}</p></article>'
        for item in data["glossary"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><meta name="description" content="Carbon Development Hub: static-first orientation, map, router, and repository handoff."><title>Carbon Development Hub v{esc(meta["version"])}</title><style>{CSS}</style></head><body><a class="skip" href="#main-content">Skip to main content</a><header class="hero"><p class="eyebrow">Orientation layer · repository authority remains controlling</p><h1>Carbon Development Hub</h1><p>{esc(meta["purpose"])}</p><p>Version {esc(meta["version"])} · authority snapshot <strong>{esc(snapshot_short)}</strong> on <strong>{esc(meta["branch"])}</strong> · captured {esc(meta["captured_at_utc"])}</p></header><nav class="nav" aria-label="Development Hub sections"><ul>{nav}</ul></nav><main id="main-content">
<section class="section" id="start"><p class="eyebrow">New to Carbon</p><h2>Understand the layers before changing the system</h2><p class="lede">The hub answers what, why, where, status, dependency, and handoff. The repository owns how, exact semantics, code, review, tests, evidence, and implementation authority.</p><div class="grid">{orientation_html}</div><p class="boundary"><strong>Core rule:</strong> Carbon may widen what participants and agents can discover without changing who controls the official grade. The exam must be qualified before it may qualify candidates.</p></section>
<section class="section current" id="current"><p class="eyebrow">Captured repository position</p><h2>Wave {esc(current["wave"])} · {esc(current["ticket"])}</h2><p class="lede">{esc(current["stage"])}</p><div class="grid"><article class="card"><h3>Current authority</h3><p><strong>{esc(current["wave_title"])}</strong></p><p>{esc(current["wave_status"])}; ticket <strong>{esc(current["ticket_status"])}</strong>.</p><p class="muted">{esc(current["maturity_summary"])}</p></article><article class="card"><h3>Completed direct dependency</h3>{list_html(current["recent_dependencies"])}<p class="muted">Other completed Wave {esc(current["wave"])} context: {badges(current["other_completed_wave_context"])}</p></article><article class="card"><h3>Downstream handoffs</h3>{list_html(current["downstream_handoffs"])}<p class="muted">Every handoff retains its own dependencies and gate.</p></article><article class="card"><h3>Parallel context</h3>{list_html(current["parallel_context"])}<p class="muted">Next selected ticket: {esc(current["next_selected_ticket"] or "none captured")}</p></article><article class="card"><h3>Decision lanes</h3><p><a href="{esc(current["technical_decision_route"])}" target="_blank" rel="noopener noreferrer">SciML / Technical Lead inbox #42</a></p><p><a href="{esc(current["owner_decision_route"])}" target="_blank" rel="noopener noreferrer">Owner inbox #41</a></p><p class="muted">Notification provides visibility; silence does not grant reserved authority.</p></article><article class="card"><h3>Decision-series status</h3><p>{esc(current["decision_series_status"])}</p></article></div><div class="fail"><strong>Still fail closed</strong>{list_html(current["fail_closed"])}</div></section>
<section class="section" id="waves"><p class="eyebrow">Development sequence</p><h2>Wave {esc(waves[0]["id"])} through Wave {esc(waves[-1]["id"])}</h2><p class="lede">{esc(wave_summary)}</p><div class="grid">{"".join(wave_cards)}</div></section>
<section class="section" id="tickets"><p class="eyebrow">Captured ticket map</p><h2>Captured tickets across {esc(ticket_waves)}</h2><p class="lede">Each explainer shows placement and purpose. Repository records remain authoritative; unsupported artifact links are marked missing or future.</p><div class="grid">{"".join(ticket_cards)}</div></section>
<section class="section" id="changes"><p class="eyebrow">Protocol-change router</p><h2>Place the change before implementing it</h2><p class="lede">Choose the layer that owns the meaning. Routing does not activate a later wave or authorize work outside the selected ticket.</p><div class="grid">{"".join(route_cards)}</div></section>
<section class="section" id="decisions"><p class="eyebrow">Asynchronous oversight</p><h2>Decision routing and supersession</h2><p class="lede"><a href="decisions.html#needs-me">Open Decisions → Needs Me</a></p><div class="grid"><article class="card"><h3>SciML and technical lane</h3><p>Material SciML and technical decisions route to <a href="{esc(data["sources"]["harsh_inbox"]["url"])}" target="_blank" rel="noopener noreferrer">issue #42</a> and mention <code>@harshaa765</code>.</p></article><article class="card"><h3>Owner lane</h3><p>Owner-reserved choices and decisions explicitly deferred by a lead route to <a href="{esc(data["sources"]["owner_inbox"]["url"])}" target="_blank" rel="noopener noreferrer">issue #41</a>.</p></article><article class="card"><h3>Complete notification</h3><p>Include recommendation, rationale, implementation location, rejected alternatives, downstream effects, reversibility, unresolved reserved inputs, and exact change path.</p></article><article class="card"><h3>Preserve history</h3><p>Notification gives visibility, not authority. Silence does not grant scientific, security, legal, economic, launch, LIVE, or production authority. Later changes supersede; current merged authority controls.</p></article></div></section>
<section class="section" id="events"><p class="eyebrow">Concise map history</p><h2>Change events</h2><p class="lede">Events capture material changes to team understanding, placement, status, dependency, boundaries, maturity, risk, or primary links. Detailed discussion stays in repository records.</p><div class="grid">{"".join(event_cards)}</div></section>
<section class="section" id="maturity"><p class="eyebrow">Independent states</p><h2>Eight maturity dimensions</h2><p class="lede">Never infer a later state from an earlier one.</p><div class="table-wrap"><table><thead><tr><th>State</th><th>Meaning</th><th>Required proof</th><th>Does not imply</th></tr></thead><tbody>{maturity_rows}</tbody></table></div></section>
<section class="section" id="glossary"><p class="eyebrow">Plain-language reference</p><h2>Glossary</h2><div class="grid">{glossary}</div></section>
<section class="section" id="sources"><p class="eyebrow">Repository handoff</p><h2>Where authority lives</h2><p class="lede">These links are pinned to the captured commit where possible. They load only when deliberately opened; this primary page requests no remote resource.</p>{links_html(data["sources"].values())}<p><a href="interactive.html">Open the optional interactive hub</a>.</p></section>
<section class="section" id="publication"><p class="eyebrow">Maintainer-controlled publication</p><h2>Hosting boundary</h2><p>Open <code>index.html</code> through <code>file://</code>, or run <code>python tools/serve_hub.py</code>. Manual GitHub Pages publication is available to authorized repository maintainers. The workflow does not itself enforce owner approval; if desired, a required reviewer on the <code>github-pages</code> environment is a separate human-controlled repository setting. Automatic publication remains disabled unless <code>CARBON_HUB_PUBLISH=true</code>. This Hub integration neither enables Pages nor changes repository settings. Enabling Pages publishes the Hub publicly.</p></section>
</main><footer class="footer"><p><strong>Authority ceiling:</strong> {esc(meta["authority_notice"])}</p><p>Generated from the two JSON source records. Authority snapshot <a href="{esc(meta["repository"])}/commit/{esc(snapshot_commit)}" target="_blank" rel="noopener noreferrer">{esc(snapshot_short)}</a>.</p></footer></body></html>
"""


def render_interactive(data: dict[str, Any], events: list[dict[str, Any]]) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count("__HUB_DATA__") != 1:
        raise SystemExit(
            "Interactive template must contain exactly one __HUB_DATA__ marker"
        )
    for marker in ("__CURRENT_POSITION__", "__CURRENT_STAGE__"):
        if template.count(marker) != 1:
            raise SystemExit(
                f"Interactive template must contain exactly one {marker} marker"
            )
    current = data["current"]
    template = template.replace(
        "__CURRENT_POSITION__",
        f"Wave {esc(current['wave'])} / {esc(current['ticket'])}",
    ).replace("__CURRENT_STAGE__", esc(current["stage"]))
    interactive_data = {**data, "change_events": events}
    payload = json.dumps(
        interactive_data, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    result = template.replace("__HUB_DATA__", payload)
    result = result.replace("<head>", '<head><link rel="icon" href="data:,">', 1)
    result = re.sub(
        r"<title>.*?</title>",
        f"<title>Carbon Development Hub v{esc(data['meta']['version'])} — interactive</title>",
        result,
        count=1,
        flags=re.DOTALL,
    )
    captured = (
        str(data["meta"]["captured_at_utc"]).replace("T", " ").replace("Z", " UTC")
    )
    snapshot_commit = str(data["meta"]["authority_snapshot_commit"])
    snapshot = f'<div class="snapshot"><strong>Authority snapshot {esc(snapshot_commit[:8])}</strong>{esc(data["meta"]["branch"])} · {esc(captured)}</div>'
    result, count = re.subn(
        r'<div class="snapshot">.*?</div>', snapshot, result, count=1, flags=re.DOTALL
    )
    if count != 1:
        raise SystemExit("Interactive template is missing its snapshot label")
    extra_css = ".skip-link{position:absolute;left:1rem;top:-5rem;background:#fff;color:#111;padding:.7rem 1rem;z-index:100}.skip-link:focus{top:1rem}:focus-visible{outline:3px solid #f0a236;outline-offset:3px}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}\n"
    result = result.replace("</style>", extra_css + "</style>", 1)
    fallback = '<body><a class="skip-link" href="#view">Skip to interactive content</a><noscript><div class="callout"><strong>JavaScript is disabled.</strong><p><a href="index.html">Open the complete static hub.</a></p></div></noscript>'
    result = result.replace("<body>", fallback, 1)
    return result.replace(
        "Carbon Development Hub v2.1 · orientation layer",
        "Carbon Development Hub v2.1 · optional interactive layer",
    )


def render_wave(data: dict[str, Any], wave: dict[str, Any]) -> str:
    tickets = {ticket["id"]: ticket for ticket in data["tickets"]}
    rows = []
    for ticket_id in wave.get("ticket_ids", []):
        ticket = tickets.get(ticket_id)
        rows.append(
            f"- [{ticket_id}](../tickets/{ticket_filename(ticket_id)}): {ticket['title']} [{ticket['status']}]"
            if ticket
            else f"- `{ticket_id}`: missing from captured ticket data"
        )
    return f"""# Wave {wave["id"]}: {wave["title"]}

**Status:** {wave["status"].upper()}

**Map ref:** `WAVE-{wave["id"]}`

**Purpose:** {wave["one_line"]}

## Sequence

- **Predecessor:** {f"Wave {wave['predecessor']}" if wave.get("predecessor") else "Constitution and repository orientation"}
- **Successor:** {f"Wave {wave['successor']}" if wave.get("successor") else "Only a prospectively authorized successor"}

## What and why

{wave["what"]}

{wave["why"]}

## Success and unlocks

{wave["success"]}

{wave["unlocks"]}

## Authority ceiling

{ceiling(data, wave, "wave")}

## Still unavailable

{wave["does_not"]}

## Key objects

{chr(10).join(f"- `{item}`" for item in wave.get("objects", [])) or "- None captured."}

## Tickets

{chr(10).join(rows) or "No controlling ticket board is captured for this planned wave."}

## Repository detail

{links_markdown(wave.get("repo_links", []))}

> Orientation boundary: repository authority owns exact semantics, implementation, review, evidence, and activation.
"""


def render_ticket(data: dict[str, Any], ticket: dict[str, Any]) -> str:
    dependencies = list(ticket.get("depends_on", [])) + list(
        ticket.get("depends_on_context", [])
    )
    downstream = list(ticket.get("unlocks", [])) + list(
        ticket.get("unlocks_context", [])
    )
    stage = (
        ticket.get("current_stage")
        or "No more specific stage is supported; use the captured status and repository evidence."
    )
    return f"""# {ticket["id"]}: {ticket["title"]}

**Wave:** {ticket["wave"]}

**Map ref:** `WAVE-{ticket["wave"]}/{ticket["id"]}`

**Status:** {ticket["status"].upper()}

**Target phase:** {ticket["target"]}

## What and why

{ticket["what"]}

{ticket["why"]}

## What it adds

{ticket["adds"]}

## Placement and handoff

- **Depends on:** {", ".join(dependencies) or "No prior ticket dependency captured."}
- **Feeds:** {", ".join(downstream) or "No downstream ticket captured."}
- **Driver:** {ticket["owner"]}
- **Review route:** {ticket["reviewer"]}
- **Master questions:** {", ".join(ticket.get("master_questions", [])) or "None captured."}

## Explicit non-goals

{ticket["does_not"]}

## Current stage

{stage}

## Maturity ceiling

{ceiling(data, ticket, "ticket")}

## Repository detail

{links_markdown(ticket.get("repo_links", []))}

> {ticket["orientation_note"]}
"""


def render_start_here(data: dict[str, Any]) -> str:
    current = data["current"]
    return f"""# Start Here: Carbon Development Hub

## Carbon in one minute

Carbon is building an incentivized experimental system for discovering,
independently testing, learning from, and qualifying methods for constructing
fast physical models.

```text
prove the judge
then prove the portfolio
then deepen the physics
then widen the search
bring industry in throughout
```

Carbon uses **waves** and **tickets** so capability can widen without silently
widening authority. A wave states the system outcome and authority ceiling. A
ticket owns one bounded unit of authorized work. Decisions record why; PRs own
the exact change and review; evidence states what the result proves and what it
does not prove.

## Where Carbon is now

- **Current wave:** Wave {current["wave"]} — {current["wave_title"]}
- **Current ticket:** {current["ticket"]} — {current["ticket_title"]}
- **Current stage:** {current["stage"]}
- **Captured maturity:** {current["maturity_summary"]}

## How to use the hub

1. Open the wave to understand the system outcome and authority ceiling.
2. Open the ticket to understand purpose, dependencies, and handoff.
3. Follow pinned repository links for exact scope, implementation, decisions,
   tests, review, and evidence.
4. Place each material change on one primary map reference before implementation.
5. Reconcile source data and append an immutable event only when a material map
   trigger applies.

## The boundary

**Hub:** what, why, where, status, dependency, maturity ceiling, and navigation.

**Repository:** how, exact semantics, implementation, review, tests, evidence,
and authority.

The hub cannot promote a design, fixture, implementation, or test into a
scientific, security, network, commercial, production, LIVE, frontier,
settlement, weight, or emission claim.

## Repository sources

{links_markdown(data["sources"].values())}

Authority snapshot: `{data["meta"]["authority_snapshot_commit"][:8]}` on `{data["meta"]["branch"]}`,
captured {data["meta"]["captured_at_utc"]}.
"""


def render_change_routing(data: dict[str, Any]) -> str:
    sections = [
        "# Protocol Change Routing",
        "",
        "These stable routes explain placement. The active wave board and selected ticket control implementation authorization.",
    ]
    for route in data["change_paths"]:
        tickets = (
            ", ".join(route["tickets"])
            or f"No current Wave {data['current']['wave']} ticket anchor is captured."
        )
        sections += [
            "",
            f"## {route['title']}",
            "",
            route["summary"],
            "",
            f"**Stable route ID:** `{route['id']}`",
            "",
            f"**Start:** {route['start']}",
            "",
            f"**Waves:** {', '.join(f'Wave {wave}' for wave in route['waves'])}",
            "",
            f"**Current ticket anchors:** {tickets}",
            "",
            f"**Why this route:** {route['why_route']}",
            "",
            "### Decisions to name",
            "",
            *(f"- {item}" for item in route["decisions"]),
            "",
            "### Human-owned or human-approved inputs",
            "",
            *(f"- {item}" for item in route["human_reserved"]),
            "",
            "### Repository flow",
            "",
            *(f"{index}. {item}" for index, item in enumerate(route["repo_flow"], 1)),
            "",
            "### Repository authority",
            "",
            links_markdown(route.get("repo_links", [])),
            "",
            f"> {route['warning']}",
        ]
    return "\n".join(sections) + "\n"


def render_glossary(data: dict[str, Any]) -> str:
    lines = [
        "# Carbon Hub Glossary",
        "",
        "These plain-language definitions orient readers; pinned repository sources own normative meaning.",
    ]
    for item in data["glossary"]:
        lines += ["", f"## {item['term']}", "", item["definition"]]
    return "\n".join(lines) + "\n"


def render_compact(data: dict[str, Any], events: list[dict[str, Any]]) -> str:
    meta, current = data["meta"], data["current"]
    lines = [
        "# Carbon Development Hub v2.1",
        "",
        f"**Purpose:** {meta['purpose']}",
        "",
        f"**Authority snapshot:** `{meta['authority_snapshot_commit']}` on `{meta['branch']}`, captured {meta['captured_at_utc']}.",
        f"**Current:** Wave {current['wave']}, ticket {current['ticket']}. {current['stage']}",
        "",
        "## Wave spine",
        "",
        "| Wave | Purpose | Status |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| [{wave['id']}](explainers/waves/wave_{wave['id'].lower()}.md) | {wave['one_line']} | {wave['status']} |"
        for wave in data["waves"]
    )
    lines += [
        "",
        "## Captured tickets",
        "",
        "| Ticket | Purpose | Status |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| [{ticket['id']}](explainers/tickets/{ticket_filename(ticket['id'])}) | {ticket['one_line']} | {ticket['status']} |"
        for ticket in data["tickets"]
    )
    lines += ["", "## Change routes", ""]
    lines.extend(
        f"- **{route['title']}** (`{route['id']}`): {route['summary']}"
        for route in data["change_paths"]
    )
    lines += ["", "## Map events", ""]
    lines.extend(
        f"- `{event['event_id']}` — `{event['map_ref']}` — {event['summary']}"
        for event in events
    )
    lines += ["", "## Authority boundary", "", meta["authority_notice"], ""]
    return "\n".join(lines)


def render_readme(data: dict[str, Any], events: list[dict[str, Any]]) -> str:
    current = data["current"]
    waves = data["waves"]
    ticket_waves = ticket_inventory_label(data)
    return f"""# Carbon Development Hub v2.1

Carbon's static-first, non-repository orientation and navigation layer.

When browsing on GitHub, start with **`orientation/START_HERE.md`**. It is the primary repository-readable orientation entry.

**`index.html`** is the complete local or hosted static Hub build after cloning or through a configured static host. GitHub's file view is not a hosted Hub application. The page has no script element or automatic remote resource and works through `file://` or a basic static server. `interactive.html` is optional.

## Inventory

- {len(waves)} waves ({waves[0]["id"]}-{waves[-1]["id"]})
- {len(data["tickets"])} captured tickets across {ticket_waves}
- {len(data["change_paths"])} protocol-change routes
- {len(events)} map-level change events
- {len(data["maturity"])} independent maturity states

## Captured current position

Wave **{current["wave"]}**, ticket **{current["ticket"]}** (`{current["ticket_status"]}`). {current["stage"]}

## Maintain

Read `orientation/AGENT_MAINTENANCE_CONTRACT.md`. Semantic map updates use
`data/hub_data_v2.json` and `data/change_events.json`; the event template,
renderer, and interactive template are maintained sources for their respective
schema or presentation behavior. Never hand-edit generated outputs. Then run:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
```

The hub explains and routes; repository authority controls implementation and evidence. Manual Pages publication is available to authorized maintainers, but the workflow does not itself enforce owner approval. A required reviewer on the `github-pages` environment, if desired, is a separate human-controlled repository setting. Pages is public when enabled; this integration does not enable it or change settings.
"""


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def yaml_dump(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        rows = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                rows += [f"{pad}{key}:", yaml_dump(child, indent + 2)]
            else:
                rows.append(f"{pad}{key}: {yaml_scalar(child)}")
        return "\n".join(rows)
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        rows = []
        for child in value:
            if isinstance(child, (dict, list)):
                rows += [f"{pad}-", yaml_dump(child, indent + 2)]
            else:
                rows.append(f"{pad}- {yaml_scalar(child)}")
        return "\n".join(rows)
    return f"{pad}{yaml_scalar(value)}"


def collect_outputs(
    data: dict[str, Any], events: list[dict[str, Any]]
) -> dict[Path, str]:
    index_data = {
        "meta": data["meta"],
        "current": data["current"],
        "waves": [
            {
                "id": wave["id"],
                "title": wave["title"],
                "status": wave["status"],
                "explainer": f"explainers/waves/wave_{wave['id'].lower()}.md",
                "tickets": wave.get("ticket_ids", []),
            }
            for wave in data["waves"]
        ],
        "tickets": [
            {
                "id": ticket["id"],
                "wave": ticket["wave"],
                "title": ticket["title"],
                "status": ticket["status"],
                "explainer": f"explainers/tickets/{ticket_filename(ticket['id'])}",
                "repo_path": ticket.get("repo_path"),
                "depends_on": ticket.get("depends_on", []),
                "depends_on_context": ticket.get("depends_on_context", []),
                "unlocks": ticket.get("unlocks", []),
                "unlocks_context": ticket.get("unlocks_context", []),
            }
            for ticket in data["tickets"]
        ],
        "change_paths": [
            {
                "id": route["id"],
                "title": route["title"],
                "waves": route["waves"],
                "tickets": route["tickets"],
            }
            for route in data["change_paths"]
        ],
        "events": events,
        "event_schema": data.get("event_schema", {}),
    }
    outputs = {
        ROOT / "index.html": render_static(data, events),
        ROOT / "interactive.html": render_interactive(data, events),
        ROOT / "Carbon_Development_Hub_v2.md": render_compact(data, events),
        ROOT / "README.md": render_readme(data, events),
        ROOT / "data" / "hub_index_v2.yaml": yaml_dump(index_data) + "\n",
        ROOT / "orientation" / "START_HERE.md": render_start_here(data),
        ROOT / "orientation" / "CHANGE_ROUTING.md": render_change_routing(data),
        ROOT / "orientation" / "GLOSSARY.md": render_glossary(data),
    }
    for wave in data["waves"]:
        outputs[ROOT / "explainers" / "waves" / f"wave_{wave['id'].lower()}.md"] = (
            render_wave(data, wave)
        )
    for ticket in data["tickets"]:
        outputs[ROOT / "explainers" / "tickets" / ticket_filename(ticket["id"])] = (
            render_ticket(data, ticket)
        )
    return outputs


def generated_extras(expected: set[Path]) -> list[Path]:
    actual = set((ROOT / "explainers" / "waves").glob("*.md")) | set(
        (ROOT / "explainers" / "tickets").glob("*.md")
    )
    return sorted(actual - expected)


def run(*, check: bool, data_path: Path, events_path: Path) -> int:
    data = load_json(data_path)
    event_bundle = load_json(events_path)
    required = (
        "meta",
        "current",
        "sources",
        "authority_ceilings",
        "waves",
        "tickets",
        "maturity",
        "change_paths",
        "glossary",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit(f"Missing hub-data keys: {', '.join(missing)}")
    events = event_bundle.get("events")
    if not isinstance(events, list):
        raise SystemExit("change_events.json must contain an events array")
    outputs = collect_outputs(data, events)
    extras = generated_extras(set(outputs))
    if check:
        drift = []
        for path, expected in outputs.items():
            actual = path.read_text(encoding="utf-8") if path.exists() else None
            if actual != expected:
                drift.append(path.relative_to(ROOT).as_posix())
        drift += [path.relative_to(ROOT).as_posix() for path in extras]
        if drift:
            print("Generated-output drift detected:")
            for name in sorted(set(drift)):
                print(f"  - {name}")
            print("Run tools/render_hub.py and commit the results.")
            return 1
        print(
            f"Generated outputs are current: {len(outputs)} files; no stale explainers."
        )
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    for path in extras:
        path.unlink()
    print(
        f"Rendered {len(data['waves'])} waves, {len(data['tickets'])} tickets, {len(data['change_paths'])} routes, and {len(events)} events into {len(outputs)} generated files."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when committed generated output differs",
    )
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--events", type=Path, default=EVENTS_PATH)
    args = parser.parse_args()
    return run(
        check=args.check,
        data_path=args.data.resolve(),
        events_path=args.events.resolve(),
    )


if __name__ == "__main__":
    sys.exit(main())
