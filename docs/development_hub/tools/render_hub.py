#!/usr/bin/env python3
"""Render the static-first Carbon Development Hub from JSON source data.

The generated ``index.html`` contains real HTML content and remains useful when
JavaScript is blocked. The optional ``interactive.html`` is retained as a
secondary app view, but it is never the only route to the hub's content.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "hub_data_v2.json"
EVENTS_PATH = ROOT / "data" / "change_events.json"
INTERACTIVE_PATH = ROOT / "interactive.html"


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def ticket_filename(ticket_id: str) -> str:
    return ticket_id.lower().replace("-", "_") + ".md"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def required_data(data: dict[str, Any]) -> None:
    for key in ("meta", "current", "sources", "waves", "tickets", "maturity", "change_paths", "glossary"):
        if key not in data:
            raise ValueError(f"Missing required top-level key: {key}")


def external_buttons(items: Iterable[dict[str, str]]) -> str:
    parts = []
    for item in items:
        parts.append(
            f'<a class="button secondary" href="{h(item["url"])}" target="_blank" rel="noopener">'
            f'{h(item["label"])} ↗</a>'
        )
    return "".join(parts)


def status_badge(status: str) -> str:
    css = slug(status)
    return f'<span class="status {css}">{h(status.replace("_", " "))}</span>'


def ticket_anchor(ticket_id: str) -> str:
    return f"ticket-{slug(ticket_id)}"


def wave_anchor(wave_id: str) -> str:
    return f"wave-{slug(wave_id)}"


def internal_ticket_links(ids: list[str], known: set[str]) -> str:
    if not ids:
        return '<span class="muted">None listed</span>'
    chunks = []
    for item in ids:
        if item in known:
            chunks.append(f'<a class="chip" href="#{ticket_anchor(item)}">{h(item)}</a>')
        else:
            chunks.append(f'<span class="chip">{h(item)}</span>')
    return "".join(chunks)


def wave_card(wave: dict[str, Any], ticket_by_id: dict[str, dict[str, Any]]) -> str:
    tickets = []
    for ticket_id in wave.get("ticket_ids", []):
        ticket = ticket_by_id.get(ticket_id)
        if ticket:
            tickets.append(
                f'<a class="chip" href="#{ticket_anchor(ticket_id)}">{h(ticket_id)} · {h(ticket["title"])}</a>'
            )
        else:
            tickets.append(f'<span class="chip">{h(ticket_id)}</span>')
    objects = "".join(f"<li><code>{h(item)}</code></li>" for item in wave.get("objects", []))
    ticket_html = "".join(tickets) or '<span class="muted">No active ticket board in this snapshot.</span>'
    next_wave = wave.get("next_wave")
    next_link = f'<a href="#{wave_anchor(next_wave)}">Wave {h(next_wave)}</a>' if next_wave else "End of current plan"
    return f"""
<details class="card wave-card" id="{wave_anchor(wave['id'])}" {'open' if wave['id'] in ('A','B') else ''}>
  <summary>
    <span class="wave-letter">{h(wave['id'])}</span>
    <span><strong>Wave {h(wave['id'])}: {h(wave['title'])}</strong><small>{h(wave['one_line'])}</small></span>
    {status_badge(wave['status'])}
  </summary>
  <div class="detail-body">
    <div class="two-col">
      <section><div class="label">What</div><h3>What this wave is</h3><p>{h(wave['what'])}</p></section>
      <section><div class="label">Why</div><h3>Why Carbon needs it</h3><p>{h(wave['why'])}</p></section>
      <section><div class="label">Success</div><h3>What success means</h3><p>{h(wave['success'])}</p></section>
      <section><div class="label">Boundary</div><h3>What it still does not mean</h3><p>{h(wave['does_not'])}</p></section>
    </div>
    <div class="callout"><strong>Unlocks</strong><p>{h(wave['unlocks'])}</p><span class="muted">Next map stage: {next_link}</span></div>
    <div class="two-col compact">
      <section><h3>Key objects</h3><ul class="object-list">{objects}</ul></section>
      <section><h3>Tickets</h3><div class="chips">{ticket_html}</div></section>
    </div>
    <div class="buttons">{external_buttons(wave.get('repo_links', []))}<a class="button" href="explainers/waves/wave_{h(wave['id'].lower())}.md">Standalone explainer</a></div>
  </div>
</details>"""


def ticket_card(ticket: dict[str, Any], known: set[str], current_ticket: str) -> str:
    current = ticket["id"] == current_ticket
    stage = ticket.get("current_stage") or "Open the repository records below for the captured stage."
    questions = ticket.get("master_questions", [])
    q_html = "".join(f'<span class="chip">{h(q)}</span>' for q in questions) or '<span class="muted">None listed</span>'
    return f"""
<details class="card ticket-card {'current' if current else ''}" id="{ticket_anchor(ticket['id'])}" {'open' if current else ''} data-wave="{h(ticket['wave'])}" data-status="{h(ticket['status'])}">
  <summary>
    <span class="ticket-code">{h(ticket['id'])}</span>
    <span><strong>{h(ticket['title'])}</strong><small>{h(ticket['one_line'])}</small></span>
    {status_badge(ticket['status'])}
  </summary>
  <div class="detail-body">
    <div class="fact-grid">
      <div><span>Wave</span><strong><a href="#{wave_anchor(ticket['wave'])}">{h(ticket['wave'])}</a></strong></div>
      <div><span>Target</span><strong>{h(ticket.get('target','Not listed'))}</strong></div>
      <div><span>Driver</span><strong>{h(ticket.get('owner','Not listed'))}</strong></div>
      <div><span>Review route</span><strong>{h(ticket.get('reviewer','Not listed'))}</strong></div>
    </div>
    <div class="two-col">
      <section><div class="label">What</div><h3>What this ticket is</h3><p>{h(ticket['what'])}</p></section>
      <section><div class="label">Why</div><h3>Why it exists</h3><p>{h(ticket['why'])}</p></section>
      <section><div class="label">Adds</div><h3>What it adds to Carbon</h3><p>{h(ticket['adds'])}</p></section>
      <section><div class="label">Boundary</div><h3>What it does not do</h3><p>{h(ticket['does_not'])}</p></section>
    </div>
    <div class="two-col compact">
      <section><h3>Depends on</h3><div class="chips">{internal_ticket_links(ticket.get('depends_on', []), known)}</div></section>
      <section><h3>Feeds or unlocks</h3><div class="chips">{internal_ticket_links(ticket.get('unlocks', []), known)}</div></section>
    </div>
    <div class="two-col compact">
      <section><h3>Current stage</h3><p>{h(stage)}</p></section>
      <section><h3>Master questions</h3><div class="chips">{q_html}</div></section>
    </div>
    <div class="note">{h(ticket['orientation_note'])}</div>
    <div class="buttons">{external_buttons(ticket.get('repo_links', []))}<a class="button" href="explainers/tickets/{ticket_filename(ticket['id'])}">Standalone explainer</a></div>
  </div>
</details>"""


def change_route(route: dict[str, Any]) -> str:
    waves = "".join(f'<a class="chip" href="#{wave_anchor(w)}">Wave {h(w)}</a>' for w in route.get("waves", []))
    tickets = "".join(f'<a class="chip" href="#{ticket_anchor(t)}">{h(t)}</a>' for t in route.get("tickets", [])) or '<span class="muted">No current ticket anchor</span>'
    decisions = "".join(f"<li>{h(item)}</li>" for item in route.get("decisions", []))
    humans = "".join(f"<li>{h(item)}</li>" for item in route.get("human_reserved", []))
    flow = "".join(f"<li>{h(item)}</li>" for item in route.get("repo_flow", []))
    return f"""
<details class="card route-card" id="change-{slug(route['id'])}">
  <summary><span class="route-icon">{h(route['icon'])}</span><span><strong>{h(route['title'])}</strong><small>{h(route['summary'])}</small></span></summary>
  <div class="detail-body">
    <div class="callout"><strong>Start here</strong><p>{h(route['start'])}</p></div>
    <p>{h(route['why_route'])}</p>
    <div class="two-col compact"><section><h3>Likely waves</h3><div class="chips">{waves}</div></section><section><h3>Current ticket anchors</h3><div class="chips">{tickets}</div></section></div>
    <div class="two-col"><section><h3>Name these decisions</h3><ul>{decisions}</ul></section><section><h3>Human-owned inputs</h3><ul>{humans}</ul></section></div>
    <section><h3>Repository handoff</h3><ol>{flow}</ol></section>
    <div class="warning"><strong>Authority note</strong><p>{h(route['warning'])}</p></div>
  </div>
</details>"""


def event_card(event: dict[str, Any]) -> str:
    primary = event.get("primary_detail", "")
    if primary.startswith(("http://", "https://")):
        link = f'<a href="{h(primary)}" target="_blank" rel="noopener">Open detail ↗</a>'
    else:
        link = f'<code>{h(primary)}</code>'
    affects = "".join(f'<span class="chip">{h(item)}</span>' for item in event.get("affects", []))
    return f"""
<article class="event-card">
  <div class="event-top"><span class="ticket-code">{h(event['event_id'])}</span>{status_badge(event['status'])}</div>
  <h3>{h(event['summary'])}</h3>
  <p><strong>{h(event['event_type'])}</strong> · {h(event.get('date',''))} · {h(event['map_ref'])}</p>
  <div class="chips">{affects}</div>
  <div class="event-link">{link}</div>
</article>"""


def render_index(data: dict[str, Any], events: list[dict[str, Any]]) -> str:
    meta, current = data["meta"], data["current"]
    ticket_by_id = {t["id"]: t for t in data["tickets"]}
    known_tickets = set(ticket_by_id)
    wave_html = "".join(wave_card(w, ticket_by_id) for w in data["waves"])
    ticket_html = "".join(ticket_card(t, known_tickets, current["ticket"]) for t in data["tickets"])
    route_html = "".join(change_route(r) for r in data["change_paths"])
    event_html = "".join(event_card(e) for e in sorted(events, key=lambda x: x.get("date", ""), reverse=True))
    maturity_html = "".join(
        f'<article class="maturity"><span>{i:02d}</span><h3>{h(m["label"])}</h3><p>{h(m["meaning"])}</p><strong>Proof</strong><p>{h(m["proof"])}</p><strong>Does not imply</strong><p>{h(m["not_implied"])}</p></article>'
        for i, m in enumerate(data["maturity"], 1)
    )
    glossary_html = "".join(f'<article class="gloss"><h3>{h(g["term"])}</h3><p>{h(g["definition"])}</p></article>' for g in data["glossary"])
    source_html = "".join(
        f'<a class="source" href="{h(item["url"])}" target="_blank" rel="noopener"><strong>{h(item["label"])}</strong><span>Open repository record ↗</span></a>'
        for item in data["sources"].values()
    )
    completed = ", ".join(current.get("completed_b_tickets", []))
    decision_series = "".join(f'<span class="chip">{h(item)}</span>' for item in current.get("decision_series", []))
    captured = str(meta["captured_at_utc"]).replace("T", " ").replace("Z", " UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Carbon Development Hub: what Carbon is building, why it exists, where changes belong, and which repository record owns implementation detail.">
<title>Carbon Development Hub v2</title>
<style>
:root{{--ink:#162025;--muted:#607078;--paper:#f2f5f4;--panel:#fff;--line:#d4dcde;--dark:#11191d;--blue:#1d638c;--blue-soft:#e8f3f9;--green:#1c7653;--green-soft:#e7f4ed;--amber:#9b5800;--amber-soft:#fff0d7;--red:#a33d3d;--red-soft:#fae8e8;--slate:#5d6b71;--slate-soft:#eef2f3;--purple:#675197;--purple-soft:#f0ebfa;--shadow:0 14px 44px rgba(19,31,37,.08);--radius:20px}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}}a{{color:var(--blue)}}code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}.layout{{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}}aside{{position:sticky;top:0;height:100vh;overflow:auto;background:var(--dark);color:white;padding:26px 20px}}.brand{{padding:4px 9px 23px}}.mark{{width:44px;height:44px;border-radius:14px;background:white;color:var(--dark);display:grid;place-items:center;font-weight:950;font-size:22px;margin-bottom:14px}}.brand strong{{display:block;font-size:20px}}.brand span{{display:block;color:#aebbc1;font-size:13px;margin-top:4px}}nav h2{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#82959e;margin:20px 10px 7px}}nav a{{display:block;color:#dce5e8;text-decoration:none;padding:10px 12px;border-radius:11px;font-weight:700;font-size:14px}}nav a:hover{{background:rgba(255,255,255,.1);color:white}}.side-note{{margin-top:28px;border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.07);border-radius:16px;padding:15px;font-size:13px;color:#bac7cc}}.side-note strong{{display:block;color:white;font-size:17px;margin:4px 0}}main{{min-width:0}}.top{{position:sticky;top:0;z-index:2;background:rgba(242,245,244,.94);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:14px 34px;display:flex;justify-content:space-between;gap:20px;font-size:13px;color:var(--muted)}}.content{{max-width:1550px;margin:auto;padding:34px 38px 80px}}.hero{{background:var(--dark);color:white;border-radius:30px;padding:46px;box-shadow:var(--shadow)}}.hero-grid{{display:grid;grid-template-columns:1.4fr .8fr;gap:32px}}.eyebrow,.label{{font-size:11px;text-transform:uppercase;letter-spacing:.13em;font-weight:900;color:#77b9dc}}h1{{font-size:clamp(36px,5vw,68px);line-height:1.02;letter-spacing:-.04em;margin:12px 0 18px}}h2{{font-size:30px;letter-spacing:-.025em;margin:0 0 10px}}h3{{font-size:18px;margin:8px 0 7px}}p{{margin:0 0 13px}}.hero p{{color:#c7d3d8;font-size:18px;max-width:850px}}.hero-card{{background:white;color:var(--ink);border-radius:22px;padding:24px}}.hero-card p{{color:var(--muted);font-size:14px}}.current-path{{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}}.current-path span{{padding:8px 10px;border-radius:10px;background:var(--amber-soft);color:var(--amber);font-weight:850}}.buttons{{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}}.button{{display:inline-block;text-decoration:none;border:1px solid var(--line);background:white;color:var(--ink);padding:9px 12px;border-radius:10px;font-weight:800;font-size:13px}}.button.primary{{background:white;color:var(--dark);border-color:white}}.button.secondary{{background:var(--blue-soft);border-color:#c8e0ed;color:var(--blue)}}.section{{padding-top:58px;scroll-margin-top:65px}}.section-head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:18px}}.section-head p{{color:var(--muted);max-width:720px}}.grid-2,.two-col{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.grid-3{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}.grid-4{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}}.compact{{margin-top:16px}}.panel,.card,.maturity,.gloss,.event-card{{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow)}}.panel{{padding:25px}}.card{{margin-bottom:13px;scroll-margin-top:75px}}details summary{{list-style:none;cursor:pointer;padding:20px 22px;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:14px;align-items:center}}details summary::-webkit-details-marker{{display:none}}details summary:after{{content:"+";grid-column:4;font-weight:900;color:var(--muted)}}details[open] summary:after{{content:"−"}}details[open] summary{{border-bottom:1px solid var(--line)}}summary strong{{display:block;font-size:17px}}summary small{{display:block;color:var(--muted);margin-top:4px}}.detail-body{{padding:22px}}.wave-letter,.ticket-code,.route-icon{{display:grid;place-items:center;min-width:45px;height:45px;border-radius:13px;background:var(--blue-soft);color:var(--blue);font-weight:950}}.ticket-code{{padding:0 10px;min-width:66px;background:var(--slate-soft);color:var(--ink)}}.route-icon{{background:var(--purple-soft);color:var(--purple)}}.current{{border:2px solid #d79a43}}.status{{justify-self:end;white-space:nowrap;padding:5px 9px;border-radius:999px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:900;background:var(--slate-soft);color:var(--slate)}}.status.done,.status.closed{{background:var(--green-soft);color:var(--green)}}.status.active,.status.in-progress,.status.in_progress{{background:var(--amber-soft);color:var(--amber)}}.status.blocked{{background:var(--red-soft);color:var(--red)}}.two-col section{{background:#f8faf9;border:1px solid #e5eaeb;border-radius:15px;padding:18px}}.two-col p,.detail-body li{{color:#45545b}}.callout,.warning,.note{{border-radius:15px;padding:17px;margin:16px 0}}.callout{{background:var(--blue-soft);border:1px solid #cae0ec}}.warning{{background:var(--amber-soft);border:1px solid #ecd09d}}.note{{background:var(--slate-soft);color:#435159}}.chips{{display:flex;flex-wrap:wrap;gap:7px}}.chip{{display:inline-block;text-decoration:none;border:1px solid var(--line);background:white;color:var(--ink);border-radius:999px;padding:5px 9px;font-size:12px;font-weight:750}}.fact-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:18px}}.fact-grid div{{background:var(--slate-soft);padding:13px;border-radius:12px}}.fact-grid span{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}.fact-grid strong{{display:block;margin-top:4px;font-size:13px}}.object-list{{columns:2;margin-bottom:0}}.event-card,.maturity,.gloss{{padding:20px}}.event-top{{display:flex;justify-content:space-between;gap:8px}}.event-card h3{{font-size:16px}}.event-card p,.maturity p,.gloss p{{color:var(--muted);font-size:14px}}.event-link{{margin-top:12px}}.maturity>span{{font-weight:950;color:var(--blue)}}.source-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.source{{display:flex;flex-direction:column;gap:5px;text-decoration:none;background:white;border:1px solid var(--line);border-radius:14px;padding:16px;color:var(--ink)}}.source span{{font-size:12px;color:var(--blue)}}.muted{{color:var(--muted)}}.footer{{margin-top:60px;border-top:1px solid var(--line);padding-top:20px;display:flex;justify-content:space-between;color:var(--muted);font-size:12px}}ol,ul{{padding-left:22px}}@media(max-width:1050px){{.layout{{display:block}}aside{{position:relative;height:auto}}nav{{columns:2}}.top{{position:relative}}.hero-grid,.grid-4,.grid-3,.fact-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:700px){{.content{{padding:20px 16px 50px}}.hero{{padding:28px 22px;border-radius:22px}}.hero-grid,.grid-2,.grid-3,.grid-4,.two-col,.fact-grid,.source-grid{{grid-template-columns:1fr}}.section-head,.footer{{display:block}}details summary{{grid-template-columns:auto minmax(0,1fr)}}details summary .status{{grid-column:2;justify-self:start}}details summary:after{{grid-column:1;grid-row:2}}nav{{columns:1}}.top{{padding:12px 17px}}}}
</style>
</head>
<body>
<div class="layout">
<aside>
  <div class="brand"><div class="mark">C</div><strong>Carbon Development Hub</strong><span>Orientation, placement, and navigation</span></div>
  <nav>
    <h2>Understand</h2><a href="#home">Home</a><a href="#start">New to Carbon</a><a href="#waves">Waves A–N</a><a href="#tickets">Ticket index</a>
    <h2>Change Carbon</h2><a href="#routes">Change routes</a><a href="#events">Change log</a><a href="#maturity">Maturity ladder</a>
    <h2>Reference</h2><a href="#glossary">Glossary</a><a href="#sources">Authority and sources</a>
  </nav>
  <div class="side-note"><span>Current position</span><strong>Wave {h(current['wave'])} / {h(current['ticket'])}</strong>{h(current['stage'])}</div>
</aside>
<main id="home">
  <div class="top"><span>Static-first: readable with scripts blocked</span><span>Source snapshot <strong>{h(meta['commit_short'])}</strong> · {h(captured)}</span></div>
  <div class="content" id="hub-content">
    <header class="hero">
      <div class="hero-grid">
        <div><div class="eyebrow">Carbon team development system</div><h1>Understand what is changing and why.</h1><p>The hub explains what Carbon is building, where work belongs, what maturity it has earned, and which repository record owns the implementation detail.</p><div class="buttons"><a class="button primary" href="#start">New to Carbon</a><a class="button primary" href="#routes">Place a protocol change</a></div></div>
        <div class="hero-card"><div class="label">Current position</div><h2>Wave {h(current['wave'])}</h2><h3>{h(current['ticket'])}: {h(current['ticket_title'])}</h3><div class="current-path"><span>Wave A closed</span><span>Wave B active</span><span>{h(current['ticket'])} selected</span></div><p>{h(current['stage'])}</p><p><strong>Completed in Wave B:</strong> {h(completed)}</p><div class="chips">{decision_series}</div></div>
      </div>
    </header>

    <section class="section" id="start"><div class="section-head"><div><div class="label">Start here</div><h2>New to Carbon</h2></div><p>Read this before opening a ticket or PR. The hub supplies context. Repository authority supplies exact meaning.</p></div>
      <div class="grid-2"><article class="panel"><h3>What Carbon is building</h3><p>Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.</p><h3>Why waves exist</h3><p>Each wave earns one bounded system capability. Later architecture cannot be treated as implemented merely because the plan describes it.</p></article><article class="panel"><h3>How to read the work</h3><p><strong>Wave:</strong> the system outcome being earned. <strong>Ticket:</strong> the bounded authorized change. <strong>Decision:</strong> the recorded choice and change path. <strong>PR:</strong> implementation and review. <strong>Evidence:</strong> what passed and what remains unearned.</p><h3>Where detail lives</h3><p>Use the hub for what, why, where, status, dependency, and orientation. Use the repository for how, exact semantics, code, tests, review, and evidence.</p></article></div>
      <div class="buttons"><a class="button secondary" href="orientation/START_HERE.md">Standalone Start Here</a><a class="button" href="orientation/GLOSSARY.md">Glossary</a><a class="button" href="#maturity">Maturity ladder</a></div>
    </section>

    <section class="section"><div class="section-head"><div><div class="label">Layer contract</div><h2>One map, several authorities</h2></div><p>The hub never becomes scientific or protocol authority.</p></div><div class="grid-4"><article class="panel"><h3>Hub</h3><p>What, why, where, status, dependency.</p></article><article class="panel"><h3>Wave board</h3><p>Ticket inventory, sequence, drivers, and closeout.</p></article><article class="panel"><h3>Ticket and PR</h3><p>Scope, exact implementation, review, bugs, and repairs.</p></article><article class="panel"><h3>Evidence</h3><p>What passed, at which identity, and under which maturity ceiling.</p></article></div></section>

    <section class="section" id="waves"><div class="section-head"><div><div class="label">Development plan</div><h2>Waves A through N</h2></div><p>Open a wave for its what, why, success condition, boundary, objects, tickets, and repository handoff.</p></div>{wave_html}</section>

    <section class="section" id="tickets"><div class="section-head"><div><div class="label">Bounded work</div><h2>Ticket index</h2></div><p>Use browser Find (Ctrl/Cmd+F) for a ticket ID, object, owner, or protocol term.</p></div>{ticket_html}</section>

    <section class="section" id="routes"><div class="section-head"><div><div class="label">Implementation routing</div><h2>Place a change before implementing it</h2></div><p>These routes cover new Challenges, model architecture, miner priors, truth and measurement, protocol contracts, bugs, and commercial/private modes.</p></div>{route_html}<div class="buttons"><a class="button secondary" href="orientation/CHANGE_ROUTING.md">Standalone routing guide</a></div></section>

    <section class="section" id="events"><div class="section-head"><div><div class="label">Living trace</div><h2>Recent map-level changes</h2></div><p>Events stay concise. The linked ticket, decision, PR, or evidence record carries the detail.</p></div><div class="grid-3">{event_html}</div><div class="buttons"><a class="button" href="data/change_event_template.yaml">Event template</a><a class="button" href="orientation/HUB_UPDATE_PLAYBOOK.md">Update playbook</a><a class="button" href="orientation/AGENT_MAINTENANCE_CONTRACT.md">Agent maintenance contract</a><a class="button" href="orientation/REPOSITORY_INTEGRATION.md">Repository integration</a></div></section>

    <section class="section" id="maturity"><div class="section-head"><div><div class="label">Claim discipline</div><h2>Eight independent maturity states</h2></div><p>Carbon does not infer a later state from an earlier one.</p></div><div class="grid-4">{maturity_html}</div></section>

    <section class="section" id="glossary"><div class="section-head"><div><div class="label">Plain language</div><h2>Glossary</h2></div><p>Use these definitions for orientation, then follow the source links for normative detail.</p></div><div class="grid-3">{glossary_html}</div></section>

    <section class="section" id="sources"><div class="section-head"><div><div class="label">Authority</div><h2>Repository source set</h2></div><p>The hub summarizes. These records control the system.</p></div><div class="source-grid">{source_html}</div></section>

    <footer class="footer"><span>Carbon Development Hub v2 · static-first orientation layer</span><span>Source snapshot {h(meta['commit_short'])} · current hub data must be reconciled before merge</span></footer>
  </div>
</main>
</div>
</body>
</html>
"""


def md_links(items: list[dict[str, str]]) -> str:
    return "\n".join(f"- [{item['label']}]({item['url']})" for item in items)


def render_wave_md(wave: dict[str, Any], ticket_by_id: dict[str, dict[str, Any]]) -> str:
    tickets = []
    for tid in wave.get("ticket_ids", []):
        t = ticket_by_id.get(tid)
        tickets.append(f"- [{tid}](../tickets/{ticket_filename(tid)}): {t['title']} [{t['status']}]" if t else f"- `{tid}`: no captured ticket explainer")
    objects = "\n".join(f"- `{item}`" for item in wave.get("objects", []))
    return f"""# Wave {wave['id']}: {wave['title']}

**Status:** {wave['status'].upper()}  
**Purpose:** {wave['one_line']}

## What this wave is

{wave['what']}

## Why Carbon needs it

{wave['why']}

## What success means

{wave['success']}

## What it unlocks

{wave['unlocks']}

## What it still does not mean

{wave['does_not']}

## Key objects

{objects}

## Tickets

{chr(10).join(tickets) or 'No active ticket board exists in this snapshot.'}

## Repository detail

{md_links(wave.get('repo_links', []))}

> Orientation boundary: this page explains what and why. The linked repository authority owns exact implementation scope and evidence.
"""


def render_ticket_md(ticket: dict[str, Any]) -> str:
    dependencies = ", ".join(ticket.get("depends_on", [])) or "No prior ticket listed in this orientation view."
    unlocks = ", ".join(ticket.get("unlocks", [])) or "No downstream ticket listed in the captured A/B board."
    questions = ", ".join(ticket.get("master_questions", [])) or "None listed in this orientation view."
    stage = ticket.get("current_stage") or "Use the status and evidence links below for the captured state."
    return f"""# {ticket['id']}: {ticket['title']}

**Wave:** {ticket['wave']}  
**Status:** {ticket['status'].upper()}  
**Target phase:** {ticket['target']}

## What this ticket is

{ticket['what']}

## Why it exists

{ticket['why']}

## What it adds to Carbon

{ticket['adds']}

## Where it fits

- **Depends on:** {dependencies}
- **Unlocks or feeds:** {unlocks}
- **Driver:** {ticket['owner']}
- **Accountable review route:** {ticket['reviewer']}
- **Master questions:** {questions}

## What it does not do

{ticket['does_not']}

## Current stage

{stage}

## Repository detail

{md_links(ticket.get('repo_links', []))}

> {ticket['orientation_note']}
"""


def render_compact_md(data: dict[str, Any]) -> str:
    meta, current = data["meta"], data["current"]
    rows = [
        "# Carbon Development Hub v2", "", f"**Purpose:** {meta['purpose']}  ",
        f"**Source snapshot:** `{meta['commit']}` on `{meta['branch']}`, captured {meta['captured_at_utc']}.  ",
        f"**Current:** Wave {current['wave']}, ticket {current['ticket']}. {current['stage']}", "",
        "## Layer contract", "", "| Layer | Answers | Detail owner |", "|---|---|---|",
        "| Hub | What, why, where, status, dependency | This package |",
        "| Wave board | Ticket inventory, sequence, drivers, closeout | `.agent/WAVE*.md` |",
        "| Ticket / contract | Bounded scope, exact semantics, non-goals, DoD | `.agent/tickets/*` and domain specs |",
        "| Decision / PR | Rationale, implementation, review, repairs, tests | `.agent/DECISIONS.md` and GitHub PR |",
        "| Evidence | Exact proof and maturity ceiling | `.agent/evidence/*` and wave reports |", "", "## Wave spine", "",
        "| Wave | What and why | Status |", "|---|---|---|",
    ]
    for wave in data["waves"]:
        rows.append(f"| [{wave['id']}](explainers/waves/wave_{wave['id'].lower()}.md) | **{wave['title']}**: {wave['one_line']} | {wave['status']} |")
    rows += ["", "## Captured ticket map", "", "| Ticket | Purpose | Status |", "|---|---|---|"]
    for ticket in data["tickets"]:
        rows.append(f"| [{ticket['id']}](explainers/tickets/{ticket_filename(ticket['id'])}) | {ticket['one_line']} | {ticket['status']} |")
    rows += ["", "## Change routes", ""]
    rows.extend(f"- **{route['title']}**: {route['summary']}" for route in data["change_paths"])
    rows += ["", "## Repository authority", "", md_links([data["sources"]["constitution"], data["sources"]["current_wave"], data["sources"]["wave_b_board"], data["sources"]["master_plan"], data["sources"]["decision_log"]]), ""]
    return "\n".join(rows)


def render_readme(data: dict[str, Any]) -> str:
    meta, current = data["meta"], data["current"]
    return f"""# Carbon Development Hub v2

This directory is Carbon's orientation and protocol-change navigation layer.

Open **`index.html`** first. It contains the complete hub and remains readable when a preview blocks JavaScript.

## Included

- New to Carbon orientation;
- full Wave A-N what-and-why map;
- explainers for captured Wave A and Wave B tickets;
- protocol-change routes for new Challenges, model architecture, miner priors, reference and measurement changes, protocol changes, defects, and commercial/private modes;
- map-level change event registry;
- maturity ladder and authority map;
- source JSON, renderer, validators, and maintenance playbook.

## Authority boundary

The hub explains what, why, where, status, and dependency. The repository owns how, exact semantics, code, decisions, tests, review, evidence, and authority.

## Source snapshot

- Repository: {meta['repository']}
- Branch: `{meta['branch']}`
- Commit reconciled: `{meta['commit']}`
- Captured: {meta['captured_at_utc']}
- Current wave: {current['wave']}
- Current ticket: {current['ticket']}

## Required development use

Read `AGENTS.md` in this directory, `orientation/AGENT_MAINTENANCE_CONTRACT.md`, and the repository root instructions. Material ticket work must place itself in the hub, update map-visible state and links, append a concise change event, regenerate outputs, and pass validation before merge.

Repository wiring and publication notes live in `orientation/REPOSITORY_INTEGRATION.md`.

## Update path

1. Read `.agent/WAVE.md`, the active wave board, and the active ticket.
2. Edit `data/hub_data_v2.json` and `data/change_events.json`.
3. Run `python tools/render_hub.py`.
4. Run `python tools/validate_hub.py --repo-root ../../..` from this directory, or pass the repository root explicitly.
5. Run `python tools/check_change_coverage.py --repo-root ../../.. --base <base> --head <head>` in PR validation.
"""


def simple_yaml(data: dict[str, Any]) -> str:
    # The JSON source is authoritative for generation. This compact YAML index is
    # for navigation, so a small dedicated emitter keeps rendering dependency-free.
    def scalar(value: object) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        text = str(value)
        if not text or re.search(r"[:#\[\]{},&*!|>'\"%@`]|^[-?]|\n", text):
            return json.dumps(text, ensure_ascii=False)
        return text

    def emit(value: object, indent: int = 0) -> list[str]:
        pad = " " * indent
        if isinstance(value, dict):
            out: list[str] = []
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    out.append(f"{pad}{key}:")
                    out.extend(emit(item, indent + 2))
                else:
                    out.append(f"{pad}{key}: {scalar(item)}")
            return out
        if isinstance(value, list):
            out = []
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for key, val in item.items():
                        prefix = f"{pad}- " if first else f"{pad}  "
                        if isinstance(val, (dict, list)):
                            out.append(f"{prefix}{key}:")
                            out.extend(emit(val, indent + 4))
                        else:
                            out.append(f"{prefix}{key}: {scalar(val)}")
                        first = False
                elif isinstance(item, list):
                    out.append(f"{pad}-")
                    out.extend(emit(item, indent + 2))
                else:
                    out.append(f"{pad}- {scalar(item)}")
            return out
        return [f"{pad}{scalar(value)}"]

    return "\n".join(emit(data)) + "\n"


def render_yaml_index(data: dict[str, Any]) -> str:
    index = {
        "meta": data["meta"],
        "current": data["current"],
        "waves": [{"id": w["id"], "title": w["title"], "status": w["status"], "explainer": f"explainers/waves/wave_{w['id'].lower()}.md", "tickets": w.get("ticket_ids", [])} for w in data["waves"]],
        "tickets": [{"id": t["id"], "wave": t["wave"], "title": t["title"], "status": t["status"], "explainer": f"explainers/tickets/{ticket_filename(t['id'])}", "repo_path": t.get("repo_path"), "depends_on": t.get("depends_on", []), "unlocks": t.get("unlocks", [])} for t in data["tickets"]],
        "change_paths": [{"id": r["id"], "title": r["title"], "waves": r["waves"], "tickets": r["tickets"]} for r in data["change_paths"]],
        "event_schema": data.get("event_schema", {}),
    }
    return simple_yaml(index)


def render_interactive_shell(data: dict[str, Any]) -> str:
    """Refresh the optional JavaScript app without making it the primary view."""
    if not INTERACTIVE_PATH.exists():
        return ""
    source = INTERACTIVE_PATH.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    source, count = re.subn(
        r"const DATA = .*?;\nconst \$ =",
        f"const DATA = {payload};\nconst $ =",
        source,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("Could not refresh embedded DATA in interactive.html")
    captured = str(data["meta"]["captured_at_utc"]).replace("T", " ").replace("Z", " UTC")
    snapshot = (
        f'<div class="snapshot"><strong>Snapshot {h(data["meta"]["commit_short"])}</strong>'
        f'{h(data["meta"]["branch"])} · {h(captured)}</div>'
    )
    source, count = re.subn(r'<div class="snapshot">.*?</div>', snapshot, source, count=1)
    if count != 1:
        raise RuntimeError("Could not refresh snapshot label in interactive.html")
    return source


def expected_outputs(data: dict[str, Any], events: list[dict[str, Any]]) -> dict[Path, str]:
    ticket_by_id = {t["id"]: t for t in data["tickets"]}
    outputs: dict[Path, str] = {
        ROOT / "index.html": render_index(data, events),
        ROOT / "README.md": render_readme(data),
        ROOT / "Carbon_Development_Hub_v2.md": render_compact_md(data),
        ROOT / "data" / "hub_index_v2.yaml": render_yaml_index(data),
    }
    if INTERACTIVE_PATH.exists():
        outputs[INTERACTIVE_PATH] = render_interactive_shell(data)
    for wave in data["waves"]:
        outputs[ROOT / "explainers" / "waves" / f"wave_{wave['id'].lower()}.md"] = render_wave_md(wave, ticket_by_id)
    for ticket in data["tickets"]:
        outputs[ROOT / "explainers" / "tickets" / ticket_filename(ticket["id"])] = render_ticket_md(ticket)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--events", type=Path, default=EVENTS_PATH)
    parser.add_argument("--check", action="store_true", help="Fail when generated files differ from source data")
    args = parser.parse_args()
    data = load_json(args.data.resolve())
    events = load_json(args.events.resolve()) if args.events.exists() else []
    required_data(data)
    outputs = expected_outputs(data, events)
    stale: list[str] = []
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if stale:
        raise SystemExit("Generated hub files are stale:\n- " + "\n- ".join(stale) + "\nRun: python tools/render_hub.py")
    action = "Checked" if args.check else "Rendered"
    print(f"{action} {len(data['waves'])} waves, {len(data['tickets'])} tickets, {len(data['change_paths'])} change routes, and {len(events)} events.")


if __name__ == "__main__":
    main()
