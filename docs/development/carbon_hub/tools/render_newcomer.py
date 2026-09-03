#!/usr/bin/env python3
"""Generate the newcomer-first Carbon Hub overview.

The page is a non-authoritative presentation projection. Canonical Hub data and
repository records remain authoritative for status, maturity, implementation,
and evidence.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HUB_DATA = ROOT / "data" / "hub_data_v2.json"
WAVE_COPY = ROOT / "data" / "newcomer_projection_v1.json"
TICKET_COPY = (
    ROOT / "data" / "newcomer_tickets_wave_a_v1.json",
    ROOT / "data" / "newcomer_tickets_wave_b_v1.json",
)
OVERVIEW = ROOT / "newcomer.html"
TECHNICAL = ROOT / "technical.html"

STATUS = {
    "closed": "Built in bounded scope",
    "done": "Built in bounded scope",
    "active": "Building",
    "in_progress": "Building",
    "planned": "Planned",
    "todo": "Planned",
    "blocked": "Blocked",
}

CSS = """
:root{--ink:#172225;--muted:#5d6d72;--paper:#f3f5f4;--panel:#fff;--line:#cdd7da;--dark:#111b1f;--blue:#0d608d;--soft:#e7f3f9;--green:#176847;--green-soft:#e5f3eb;--amber:#8a4c00;--amber-soft:#fff0d6;--shadow:0 10px 28px rgba(16,29,35,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.55}a{color:#075c89;text-underline-offset:.16em}.hero{background:var(--dark);color:#fff;padding:clamp(1.5rem,5vw,3.5rem) max(1rem,calc((100vw - 1240px)/2))}.hero h1{font-size:clamp(2.2rem,6vw,4.7rem);line-height:1;letter-spacing:-.045em;margin:.4rem 0 1rem}.hero p{max-width:900px;color:#d3dee2}.eyebrow{font-size:.75rem;font-weight:850;letter-spacing:.13em;text-transform:uppercase;color:#a9d8f3}.buttons{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.2rem}.button{padding:.65rem .85rem;border-radius:10px;background:#fff;color:#102126;text-decoration:none;font-weight:800}.button.alt{background:transparent;color:#fff;border:1px solid #6e858d}.nav{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--line)}.nav div{max-width:1240px;margin:auto;display:flex;gap:.9rem;padding:.7rem 1rem;overflow-x:auto}.nav a{font-weight:750;color:var(--ink);text-decoration:none;white-space:nowrap}main{max-width:1240px;margin:auto;padding:1rem 1rem 5rem}.section{margin:1.2rem 0;background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:clamp(1rem,3vw,2rem);scroll-margin-top:4rem}.section h2{font-size:clamp(1.7rem,3vw,2.5rem);line-height:1.1;margin:.1rem 0 .6rem}.lede{font-size:1.08rem;color:var(--muted);max-width:950px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:1rem}.card{border:1px solid var(--line);border-radius:15px;padding:1.1rem;background:#fff}.card h3{margin:.25rem 0 .7rem;line-height:1.2}.card p{margin:.55rem 0}.status{display:inline-block;border-radius:999px;padding:.2rem .58rem;font-size:.73rem;font-weight:850;text-transform:uppercase;background:#edf1f2}.status.done,.status.closed{background:var(--green-soft);color:var(--green)}.status.active,.status.in_progress{background:var(--amber-soft);color:var(--amber)}.status.planned,.status.todo{background:var(--soft);color:var(--blue)}.label{font-weight:850}.boundary{border-left:4px solid var(--amber);background:var(--amber-soft);padding:.75rem .85rem;border-radius:0 9px 9px 0}.current{background:linear-gradient(135deg,#102026,#1a3843);color:#fff}.current .card{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.22)}.current .lede{color:#ccdade}.current a{color:#ade0ff}details{margin-top:.8rem;border-top:1px solid var(--line);padding-top:.75rem}summary{cursor:pointer;font-weight:850;color:#174b63}.current summary{color:#d2e5ec}.technical{font-size:.94rem;color:var(--muted)}.current .technical{color:#d2e5ec}.wave{border-top:5px solid #9ba8ad}.wave.closed{border-top-color:var(--green)}.wave.active{border-top-color:#d6871b}.ticket{border-left:5px solid #9ba8ad}.ticket.done{border-left-color:var(--green)}.ticket.in_progress{border-left-color:#d6871b}.groups>details{border:1px solid var(--line);border-radius:14px;padding:1rem;background:#fafcfc;margin:.8rem 0}.groups>details>summary{font-size:1.15rem;color:var(--ink)}footer{background:var(--dark);color:#d7e1e4;padding:2rem max(1rem,calc((100vw - 1240px)/2))}footer a{color:#ade0ff}@media(max-width:650px){.nav{position:static}.nav div{flex-wrap:wrap}.grid{grid-template-columns:1fr}.hero h1{font-size:2.5rem}.section{border-radius:12px}}@media print{.nav{display:none}.section{box-shadow:none}.hero{background:#fff;color:#000}.hero p{color:#333}}
"""


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return value


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_projection() -> dict[str, Any]:
    result = load(WAVE_COPY)
    tickets: dict[str, Any] = {}
    for path in TICKET_COPY:
        bundle = load(path)
        for key in ("schema_version", "map_ref", "product_decision"):
            if bundle.get(key) != result.get(key):
                raise SystemExit(f"{path}: {key} does not match Wave projection")
        records = bundle.get("tickets")
        if not isinstance(records, dict):
            raise SystemExit(f"{path}: tickets must be an object")
        overlap = set(records) & set(tickets)
        if overlap:
            raise SystemExit(f"Duplicate newcomer tickets: {sorted(overlap)}")
        tickets.update(records)
    result["tickets"] = tickets
    return result


def validate(hub: dict[str, Any], copy: dict[str, Any]) -> None:
    if copy.get("schema_version") != "1.0":
        raise SystemExit("newcomer projection schema_version must be 1.0")
    if copy.get("map_ref") != "SYSTEM/DEVELOPMENT-HUB":
        raise SystemExit("newcomer projection must bind to SYSTEM/DEVELOPMENT-HUB")
    waves = {str(item["id"]): item for item in hub["waves"]}
    tickets = {str(item["id"]): item for item in hub["tickets"]}
    if set(copy["waves"]) != set(waves):
        raise SystemExit("Newcomer Wave coverage does not match canonical Hub")
    if set(copy["tickets"]) != set(tickets):
        raise SystemExit("Newcomer ticket coverage does not match canonical Hub")
    for wave_id, item in copy["waves"].items():
        if item.get("map_ref") != f"WAVE-{wave_id}":
            raise SystemExit(f"{wave_id}: wrong newcomer map_ref")
        for field in ("title", "what", "why", "done_when", "not_yet"):
            if not str(item.get(field, "")).strip():
                raise SystemExit(f"{wave_id}: missing newcomer field {field}")
    for ticket_id, item in copy["tickets"].items():
        expected = f"WAVE-{tickets[ticket_id]['wave']}/{ticket_id}"
        if item.get("map_ref") != expected:
            raise SystemExit(f"{ticket_id}: wrong newcomer map_ref")
        for field in ("title", "what", "why", "changes", "not_yet"):
            if not str(item.get(field, "")).strip():
                raise SystemExit(f"{ticket_id}: missing newcomer field {field}")


def detail(item: dict[str, Any], map_ref: str, href: str) -> str:
    ceiling = (
        item.get("authority_ceiling")
        or item.get("maturity_ceiling")
        or "See exact Hub record."
    )
    return (
        '<details><summary>Technical Detail</summary><div class="technical">'
        f'<p><span class="label">Canonical title:</span> {esc(item["title"])}</p>'
        f'<p><span class="label">Exact status:</span> {esc(item["status"])}</p>'
        f'<p><span class="label">Map ref:</span> <code>{esc(map_ref)}</code></p>'
        f'<p><span class="label">Maturity / authority ceiling:</span> {esc(ceiling)}</p>'
        f'<p><a href="{esc(href)}">Open the full technical Hub record</a></p>'
        "</div></details>"
    )


def render(hub: dict[str, Any], copy: dict[str, Any]) -> str:
    waves = {str(item["id"]): item for item in hub["waves"]}
    tickets = {str(item["id"]): item for item in hub["tickets"]}
    current = hub["current"]
    current_wave, current_ticket = str(current["wave"]), str(current["ticket"])
    current_wave_copy = copy["waves"][current_wave]
    current_ticket_copy = copy["tickets"][current_ticket]

    wave_cards: list[str] = []
    for wave_id, canonical in waves.items():
        plain = copy["waves"][wave_id]
        status = str(canonical["status"])
        wave_cards.append(
            f'<article class="card wave {esc(status)}" id="overview-wave-{esc(wave_id)}">'
            f'<span class="status {esc(status)}">{esc(STATUS.get(status, status))}</span>'
            f'<h3>Wave {esc(wave_id)} — {esc(plain["title"])}</h3>'
            f'<p><span class="label">What are we building?</span> {esc(plain["what"])}</p>'
            f'<p><span class="label">Why does Carbon need it?</span> {esc(plain["why"])}</p>'
            f'<p><span class="label">Done when:</span> {esc(plain["done_when"])}</p>'
            f'<p class="boundary"><span class="label">Still not true:</span> {esc(plain["not_yet"])}</p>'
            + detail(canonical, plain["map_ref"], f"index.html#wave-{wave_id}")
            + "</article>"
        )

    ticket_groups: list[str] = []
    for wave_id in dict.fromkeys(str(item["wave"]) for item in hub["tickets"]):
        cards: list[str] = []
        for canonical in hub["tickets"]:
            if str(canonical["wave"]) != wave_id:
                continue
            ticket_id = str(canonical["id"])
            plain = copy["tickets"][ticket_id]
            status = str(canonical["status"])
            cards.append(
                f'<article class="card ticket {esc(status)}" id="overview-ticket-{esc(ticket_id)}">'
                f'<span class="status {esc(status)}">{esc(STATUS.get(status, status))}</span>'
                f'<h3>{esc(ticket_id)} — {esc(plain["title"])}</h3>'
                f'<p><span class="label">What are we doing?</span> {esc(plain["what"])}</p>'
                f'<p><span class="label">Why does it matter?</span> {esc(plain["why"])}</p>'
                f'<p><span class="label">What changes when finished?</span> {esc(plain["changes"])}</p>'
                f'<p class="boundary"><span class="label">What it does not do:</span> {esc(plain["not_yet"])}</p>'
                + detail(canonical, plain["map_ref"], f"index.html#ticket-{ticket_id}")
                + "</article>"
            )
        open_attr = " open" if wave_id == current_wave else ""
        ticket_groups.append(
            f"<details{open_attr}><summary>Wave {esc(wave_id)} tickets</summary>"
            f'<div class="grid">{"".join(cards)}</div></details>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(copy["summary"])}"><title>{esc(copy["title"])}</title><style>{CSS}</style></head>
<body><header class="hero"><p class="eyebrow">Carbon Hub · Overview</p><h1>Understand Carbon before reading the repository.</h1><p>{esc(copy["summary"])}</p><div class="buttons"><a class="button" href="#current">Start with where Carbon is now</a><a class="button alt" href="index.html">Open Technical Detail</a></div></header>
<nav class="nav" aria-label="Overview sections"><div><a href="#current">Current</a><a href="#roadmap">Roadmap</a><a href="#tickets">Tickets</a><a href="#status">Status</a></div></nav><main>
<section class="section current" id="current"><p class="eyebrow">Where Carbon is now</p><h2>Wave {esc(current_wave)} · {esc(current_ticket)}</h2><p class="lede">Carbon is in <strong>Wave {esc(current_wave)} — {esc(current_wave_copy["title"])}</strong>. The selected ticket is <strong>{esc(current_ticket)} — {esc(current_ticket_copy["title"])}</strong>.</p><div class="grid">
<article class="card"><h3>Current Wave</h3><p>{esc(current_wave_copy["what"])}</p><p class="boundary"><strong>Still not true:</strong> {esc(current_wave_copy["not_yet"])}</p>{detail(waves[current_wave], current_wave_copy["map_ref"], f"index.html#wave-{current_wave}")}</article>
<article class="card"><h3>Current Ticket</h3><p>{esc(current_ticket_copy["what"])}</p><p><strong>Why it matters:</strong> {esc(current_ticket_copy["why"])}</p><p class="boundary"><strong>Still not true:</strong> {esc(current_ticket_copy["not_yet"])}</p>{detail(tickets[current_ticket], current_ticket_copy["map_ref"], f"index.html#ticket-{current_ticket}")}</article></div></section>
<section class="section" id="roadmap"><p class="eyebrow">Development roadmap</p><h2>What each Wave is trying to make true</h2><p class="lede">Read the idea first. Open Technical Detail for canonical names, maturity, dependencies, specifications, and evidence.</p><div class="grid">{"".join(wave_cards)}</div></section>
<section class="section" id="tickets"><p class="eyebrow">Work map</p><h2>What the captured tickets mean</h2><p class="lede">Tickets are bounded pieces of work. Their technical records remain the repository handoff.</p><div class="groups">{"".join(ticket_groups)}</div></section>
<section class="section" id="status"><p class="eyebrow">Status discipline</p><h2>Simple words, exact maturity</h2><div class="grid"><article class="card"><h3>Built in bounded scope</h3><p>The recorded engineering work is complete in its stated scope. Scientific, security, network, commercial, and production qualification remain separate.</p></article><article class="card"><h3>Building</h3><p>The controlling board selected bounded work. Completion and later maturity remain unearned until their own evidence exists.</p></article><article class="card"><h3>Planned</h3><p>The repository describes the future capability. Roadmap presence does not create implementation authority.</p></article></div><p class="boundary"><strong>One truth, two levels of detail:</strong> Overview and Technical Detail describe the same stable records. Overview cannot activate work, change scientific meaning, or grant maturity.</p></section>
</main><footer><p><strong>Authority boundary:</strong> This is a newcomer projection of the Carbon Development Hub. Repository authority, tickets, contracts, decisions, review, tests, and evidence remain controlling.</p><p><a href="index.html">Open Technical Detail</a> · <code>SYSTEM/DEVELOPMENT-HUB</code> · <code>{esc(copy["product_decision"])}</code></p></footer></body></html>"""


def render_technical() -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>Carbon Hub — Technical Detail</title></head><body><main>"
        "<h1>Carbon Hub — Technical Detail</h1>"
        '<p><a href="index.html">Open the complete technical Hub.</a></p>'
        "</main></body></html>"
    )


def collect_outputs() -> dict[Path, str]:
    """Return this module's generated artifacts, keyed by absolute path.

    Shared by this module's own CLI and by ``render_hub.py``, so a single
    generation/check pass covers both the technical Hub and the newcomer
    Overview.
    """
    hub, copy = load(HUB_DATA), load_projection()
    validate(hub, copy)
    return {
        OVERVIEW: render(hub, copy).rstrip() + "\n",
        TECHNICAL: render_technical().rstrip() + "\n",
    }


def write(path: Path, content: str, check: bool) -> None:
    content = content.rstrip() + "\n"
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Generated newcomer output is stale: {path}")
    else:
        path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in collect_outputs().items():
        write(path, content, args.check)


if __name__ == "__main__":
    main()
