#!/usr/bin/env python3
"""Render the newcomer-first Carbon Hub overview from a non-authoritative projection.

The canonical Development Hub data remains the authority-bearing orientation source.
This renderer requires exact Wave/ticket coverage and binds every plain-language
projection to the same stable map_ref before producing static HTML.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HUB_DATA_PATH = ROOT / "data" / "hub_data_v2.json"
PROJECTION_PATH = ROOT / "data" / "newcomer_projection_v1.json"
OUTPUT_PATH = ROOT / "newcomer.html"
TECHNICAL_REDIRECT_PATH = ROOT / "technical.html"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected object in {path}")
    return value


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def status_label(status: str) -> str:
    return {
        "closed": "Built in bounded scope",
        "active": "Building",
        "planned": "Planned",
        "done": "Built in bounded scope",
        "in_progress": "Building",
        "todo": "Planned",
        "blocked": "Blocked",
    }.get(status, status.replace("_", " ").title())


def validate_projection(hub: dict[str, Any], projection: dict[str, Any]) -> None:
    if projection.get("schema_version") != "1.0":
        raise SystemExit("newcomer projection schema_version must be 1.0")
    if projection.get("map_ref") != "SYSTEM/DEVELOPMENT-HUB":
        raise SystemExit("newcomer projection must bind to SYSTEM/DEVELOPMENT-HUB")

    canonical_waves = {str(item["id"]): item for item in hub["waves"]}
    projected_waves = projection.get("waves")
    if not isinstance(projected_waves, dict):
        raise SystemExit("newcomer projection waves must be an object")
    if set(projected_waves) != set(canonical_waves):
        missing = sorted(set(canonical_waves) - set(projected_waves))
        extra = sorted(set(projected_waves) - set(canonical_waves))
        raise SystemExit(f"Wave newcomer coverage mismatch: missing={missing}, extra={extra}")

    canonical_tickets = {str(item["id"]): item for item in hub["tickets"]}
    projected_tickets = projection.get("tickets")
    if not isinstance(projected_tickets, dict):
        raise SystemExit("newcomer projection tickets must be an object")
    if set(projected_tickets) != set(canonical_tickets):
        missing = sorted(set(canonical_tickets) - set(projected_tickets))
        extra = sorted(set(projected_tickets) - set(canonical_tickets))
        raise SystemExit(f"Ticket newcomer coverage mismatch: missing={missing}, extra={extra}")

    required_wave = ("title", "what", "why", "done_when", "not_yet", "map_ref")
    required_ticket = ("title", "what", "why", "changes", "not_yet", "map_ref")
    for wave_id, item in canonical_waves.items():
        projected = projected_waves[wave_id]
        expected_ref = f"WAVE-{wave_id}"
        if projected.get("map_ref") != expected_ref:
            raise SystemExit(f"{wave_id}: newcomer map_ref must be {expected_ref}")
        for field in required_wave:
            if not str(projected.get(field, "")).strip():
                raise SystemExit(f"{wave_id}: missing newcomer field {field}")

    for ticket_id, item in canonical_tickets.items():
        wave_id = str(item["wave"])
        projected = projected_tickets[ticket_id]
        expected_ref = f"WAVE-{wave_id}/{ticket_id}"
        if projected.get("map_ref") != expected_ref:
            raise SystemExit(f"{ticket_id}: newcomer map_ref must be {expected_ref}")
        for field in required_ticket:
            if not str(projected.get(field, "")).strip():
                raise SystemExit(f"{ticket_id}: missing newcomer field {field}")


CSS = r"""
:root{--ink:#172225;--muted:#5d6d72;--paper:#f3f5f4;--panel:#fff;--line:#cdd7da;--dark:#111b1f;--blue:#0d608d;--blue-soft:#e7f3f9;--green:#176847;--green-soft:#e5f3eb;--amber:#8a4c00;--amber-soft:#fff0d6;--shadow:0 10px 28px rgba(16,29,35,.08);--radius:18px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}a{color:#075c89;text-underline-offset:.16em}.hero{background:var(--dark);color:#fff;padding:clamp(1.4rem,5vw,3.5rem) max(1rem,calc((100vw - 1240px)/2))}.eyebrow{font-size:.76rem;font-weight:850;letter-spacing:.13em;text-transform:uppercase;color:#a9d8f3}.hero h1{font-size:clamp(2.2rem,6vw,4.8rem);line-height:1;letter-spacing:-.045em;margin:.4rem 0 1rem}.hero p{max-width:900px;color:#d3dee2}.toplinks{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.2rem}.button{display:inline-block;padding:.65rem .85rem;border-radius:10px;background:#fff;color:#102126;text-decoration:none;font-weight:800}.button.secondary{background:transparent;color:#fff;border:1px solid #6e858d}.nav{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--line)}.nav div{max-width:1240px;margin:auto;display:flex;gap:.8rem;overflow-x:auto;padding:.7rem 1rem}.nav a{font-weight:750;color:var(--ink);text-decoration:none;white-space:nowrap}main{max-width:1240px;margin:auto;padding:1rem 1rem 5rem}.section{margin:1.2rem 0;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:clamp(1rem,3vw,2rem);scroll-margin-top:4rem}.section h2{font-size:clamp(1.7rem,3vw,2.5rem);line-height:1.1;margin:.1rem 0 .6rem}.lede{font-size:1.08rem;color:var(--muted);max-width:950px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:1rem}.card{border:1px solid var(--line);border-radius:15px;padding:1.1rem;background:#fff}.card h3{margin:.25rem 0 .7rem;line-height:1.2}.card p{margin:.55rem 0}.status{display:inline-block;border-radius:999px;padding:.2rem .58rem;font-size:.74rem;font-weight:850;letter-spacing:.04em;text-transform:uppercase;background:#edf1f2}.status.done,.status.closed{background:var(--green-soft);color:var(--green)}.status.active,.status.in_progress{background:var(--amber-soft);color:var(--amber)}.status.planned,.status.todo{background:var(--blue-soft);color:var(--blue)}.label{font-weight:850}.boundary{border-left:4px solid var(--amber);background:var(--amber-soft);padding:.75rem .85rem;border-radius:0 9px 9px 0}.current{background:linear-gradient(135deg,#102026,#1a3843);color:#fff}.current .card{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.22)}.current .lede,.current .muted{color:#ccdade}.current a{color:#ade0ff}details{margin-top:.8rem;border-top:1px solid var(--line);padding-top:.75rem}summary{cursor:pointer;font-weight:850;color:#174b63}details[open] summary{margin-bottom:.5rem}.technical{font-size:.94rem;color:var(--muted)}.current .technical,.current summary{color:#d2e5ec}.wave{border-top:5px solid #9ba8ad}.wave.closed{border-top-color:var(--green)}.wave.active{border-top-color:#d6871b}.ticket{border-left:5px solid #9ba8ad}.ticket.done{border-left-color:var(--green)}.ticket.in_progress{border-left-color:#d6871b}.ticket-groups>details{border:1px solid var(--line);border-radius:14px;padding:1rem;background:#fafcfc;margin:.8rem 0}.ticket-groups>details>summary{font-size:1.15rem;color:var(--ink)}.footer{background:var(--dark);color:#d7e1e4;padding:2rem max(1rem,calc((100vw - 1240px)/2))}.footer a{color:#ade0ff}@media(max-width:650px){.nav{position:static}.nav div{flex-wrap:wrap}.grid{grid-template-columns:1fr}.hero h1{font-size:2.55rem}.section{border-radius:12px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{.nav{display:none}.section{box-shadow:none}.hero{background:#fff;color:#000}.hero p{color:#333}}
"""


def tech_detail(kind: str, item: dict[str, Any], map_ref: str, href: str) -> str:
    label = f"Wave {item['id']}: {item['title']}" if kind == "wave" else f"{item['id']}: {item['title']}"
    ceiling = item.get("authority_ceiling") or item.get("maturity_ceiling") or "See exact Hub record."
    return (
        "<details><summary>Technical Detail</summary>"
        f'<div class="technical"><p><span class="label">Canonical record:</span> {esc(label)}</p>'
        f'<p><span class="label">Exact status:</span> {esc(item["status"])}</p>'
        f'<p><span class="label">Map ref:</span> <code>{esc(map_ref)}</code></p>'
        f'<p><span class="label">Maturity / authority ceiling:</span> {esc(ceiling)}</p>'
        f'<p><a href="{esc(href)}">Open the full technical Hub record</a></p></div></details>'
    )


def render(hub: dict[str, Any], projection: dict[str, Any]) -> str:
    waves = {str(item["id"]): item for item in hub["waves"]}
    tickets = {str(item["id"]): item for item in hub["tickets"]}
    current = hub["current"]
    current_wave = str(current["wave"])
    current_ticket = str(current["ticket"])
    p_wave = projection["waves"][current_wave]
    p_ticket = projection["tickets"][current_ticket]
    current_wave_item = waves[current_wave]
    current_ticket_item = tickets[current_ticket]

    wave_cards = []
    for wave_id, item in waves.items():
        p = projection["waves"][wave_id]
        wave_cards.append(
            f'<article class="card wave {esc(item["status"])}" id="overview-wave-{esc(wave_id)}">'
            f'<span class="status {esc(item["status"])}">{esc(status_label(str(item["status"])))}</span>'
            f'<h3>Wave {esc(wave_id)} — {esc(p["title"])}</h3>'
            f'<p><span class="label">What are we building?</span> {esc(p["what"])}</p>'
            f'<p><span class="label">Why does Carbon need it?</span> {esc(p["why"])}</p>'
            f'<p><span class="label">Done when:</span> {esc(p["done_when"])}</p>'
            f'<p class="boundary"><span class="label">Still not true:</span> {esc(p["not_yet"])}</p>'
            + tech_detail("wave", item, p["map_ref"], f"technical.html#wave-{wave_id}")
            + "</article>"
        )

    ticket_groups = []
    ordered_waves = []
    for ticket in hub["tickets"]:
        wave_id = str(ticket["wave"])
        if wave_id not in ordered_waves:
            ordered_waves.append(wave_id)
    for wave_id in ordered_waves:
        cards = []
        for item in hub["tickets"]:
            if str(item["wave"]) != wave_id:
                continue
            ticket_id = str(item["id"])
            p = projection["tickets"][ticket_id]
            cards.append(
                f'<article class="card ticket {esc(item["status"])}" id="overview-ticket-{esc(ticket_id)}">'
                f'<span class="status {esc(item["status"])}">{esc(status_label(str(item["status"])))}</span>'
                f'<h3>{esc(ticket_id)} — {esc(p["title"])}</h3>'
                f'<p><span class="label">What are we doing?</span> {esc(p["what"])}</p>'
                f'<p><span class="label">Why does it matter?</span> {esc(p["why"])}</p>'
                f'<p><span class="label">What changes when it is finished?</span> {esc(p["changes"])}</p>'
                f'<p class="boundary"><span class="label">What it does not do:</span> {esc(p["not_yet"])}</p>'
                + tech_detail("ticket", item, p["map_ref"], f"technical.html#ticket-{ticket_id}")
                + "</article>"
            )
        ticket_groups.append(
            f'<details {"open" if wave_id == current_wave else ""}><summary>Wave {esc(wave_id)} tickets</summary>'
            f'<div class="grid">{"".join(cards)}</div></details>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(projection["summary"])}"><title>{esc(projection["title"])}</title><style>{CSS}</style></head>
<body><header class="hero"><p class="eyebrow">Carbon Hub · Overview</p><h1>Understand Carbon before reading the repository.</h1>
<p>{esc(projection["summary"])}</p><div class="toplinks"><a class="button" href="#current">Start with where Carbon is now</a>
<a class="button secondary" href="technical.html">Open Technical Detail</a></div></header>
<nav class="nav" aria-label="Overview sections"><div><a href="#current">Current</a><a href="#roadmap">Roadmap</a><a href="#tickets">Tickets</a><a href="#how-to-read">How to read status</a></div></nav>
<main>
<section class="section current" id="current"><p class="eyebrow">Where Carbon is now</p><h2>Wave {esc(current_wave)} · {esc(current_ticket)}</h2>
<p class="lede">Carbon is in <strong>Wave {esc(current_wave)} — {esc(p_wave["title"])}</strong>. The selected ticket is <strong>{esc(current_ticket)} — {esc(p_ticket["title"])}</strong>.</p>
<div class="grid"><article class="card"><h3>Current Wave</h3><p>{esc(p_wave["what"])}</p><p class="boundary"><strong>Still not true:</strong> {esc(p_wave["not_yet"])}</p>
{tech_detail("wave", current_wave_item, p_wave["map_ref"], f"technical.html#wave-{current_wave}")}</article>
<article class="card"><h3>Current Ticket</h3><p>{esc(p_ticket["what"])}</p><p><strong>Why it matters:</strong> {esc(p_ticket["why"])}</p>
<p class="boundary"><strong>Still not true:</strong> {esc(p_ticket["not_yet"])}</p>
{tech_detail("ticket", current_ticket_item, p_ticket["map_ref"], f"technical.html#ticket-{current_ticket}")}</article></div></section>
<section class="section" id="roadmap"><p class="eyebrow">Development roadmap</p><h2>What each Wave is trying to make true</h2>
<p class="lede">Read the plain-English outcome first. Open Technical Detail when you need canonical Carbon names, maturity ceilings, dependencies, tickets, specifications, and evidence.</p>
<div class="grid">{"".join(wave_cards)}</div></section>
<section class="section" id="tickets"><p class="eyebrow">Work map</p><h2>What the captured tickets mean</h2>
<p class="lede">Tickets are the bounded pieces of work inside a Wave. The Overview explains the job each ticket performs; the technical Hub remains the exact repository handoff.</p>
<div class="ticket-groups">{"".join(ticket_groups)}</div></section>
<section class="section" id="how-to-read"><p class="eyebrow">Status discipline</p><h2>Simple words, exact maturity</h2>
<div class="grid"><article class="card"><h3>Built in bounded scope</h3><p>The recorded engineering work is complete in its stated scope. It does not inherit scientific, security, network, commercial, or production qualification.</p></article>
<article class="card"><h3>Building</h3><p>The controlling board has selected bounded work. Completion and every later maturity state remain unearned until their own evidence exists.</p></article>
<article class="card"><h3>Planned</h3><p>The repository describes the future capability, but no active implementation authority follows from the roadmap alone.</p></article></div>
<p class="boundary"><strong>One truth, two levels of detail:</strong> Overview and Technical Detail describe the same stable Wave and ticket records. The Overview cannot activate work, change scientific meaning, or grant maturity.</p></section>
</main><footer class="footer"><p><strong>Authority boundary:</strong> This page is a newcomer projection of the Carbon Development Hub. Repository authority, tickets, contracts, decisions, review, tests, and evidence remain controlling.</p>
<p><a href="technical.html">Open Technical Detail</a> · map owner <code>SYSTEM/DEVELOPMENT-HUB</code> · decision <code>{esc(projection["product_decision"])}</code></p></footer></body></html>
"""


TECHNICAL_REDIRECT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Carbon Hub — Technical Detail</title></head>
<body><main><h1>Carbon Hub — Technical Detail</h1><p>The repository keeps the complete technical Hub at <a href="index.html">index.html</a>.</p></main></body></html>
"""


def write_or_check(path: Path, content: str, *, check: bool) -> None:
    content = content.rstrip() + "\n"
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Generated newcomer output is stale: {path}")
        return
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    hub = load_json(HUB_DATA_PATH)
    projection = load_json(PROJECTION_PATH)
    validate_projection(hub, projection)
    write_or_check(OUTPUT_PATH, render(hub, projection), check=args.check)
    write_or_check(TECHNICAL_REDIRECT_PATH, TECHNICAL_REDIRECT, check=args.check)


if __name__ == "__main__":
    main()
