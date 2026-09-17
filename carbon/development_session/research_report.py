"""Local owner view of actual campaign ledger state, without model inference."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from .research_ledger import ELAPSED_SECONDS, CampaignLedger


def render_status(ledger, *, owner):
    value = ledger.status(owner=owner)
    value["report_schema"] = "carbon.autoresearch.owner-status.v1"
    value["status"] = (
        "NOT_DISPATCHED"
        if value["started_unix"] is None
        else (
            "RECONCILIATION_REQUIRED"
            if any(op["state"] == "RESERVED" for op in value["operations"])
            else "IDLE"
        )
    )
    if (ledger.root / "campaign-complete.json").exists():
        value["status"] = "FINITE_CAMPAIGN_STOPPED"
    elif value["status"] == "RECONCILIATION_REQUIRED":
        value["status"] = "ACTIVE_OR_RECONCILIATION_REQUIRED"
    value["retained_physical_bytes"] = ledger.check_storage()
    value["elapsed_seconds"] = (
        max(0, ledger.clock() - value["started_unix"])
        if value["started_unix"] is not None
        else 0
    )
    value["remaining_elapsed_seconds"] = max(
        0, ELAPSED_SECONDS - value["elapsed_seconds"]
    )
    value["active_operations"] = [
        op["id"] for op in value["operations"] if op["state"] == "RESERVED"
    ]
    value["current_hypothesis"] = next(
        (n["body"] for n in reversed(value["notes"]) if n["kind"] == "hypothesis"), None
    )
    value["phase_accounting"] = {}
    for op in value["operations"]:
        total = value["phase_accounting"].setdefault(op["phase"], {})
        for key, amount in (
            op["actual"] if op["actual"] is not None else op["reservation"]
        ).items():
            total[key] = total.get(key, 0) + amount
    value["epoch_outcomes"] = [
        json.loads(p.read_bytes())
        for p in sorted(ledger.root.glob("epoch-*/outcome.json"))
    ]
    value["trials"] = []
    with ledger.db() as db:
        if db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='research_results'"
        ).fetchone():
            from .profile import digest

            for body, fingerprint in db.execute(
                "SELECT body,digest FROM research_results WHERE owner=?", (owner,)
            ):
                if digest(body) != fingerprint:
                    raise ValueError("changed report source")
                item = json.loads(body)
                if item.get("provenance") == "REAL_JAX_PUBLIC_PRACTICE":
                    value["trials"].append(item)
    value["epoch_results"] = [
        json.loads(path.read_bytes())
        for path in sorted(ledger.root.glob("epoch-*/permitted-final-feedback.json"))
    ]
    value["chain_transactions"] = 0
    value["eligibility"] = "DEVELOPMENT_ONLY; no scientific qualification or payment"
    value["remaining"] = {k: value["ceilings"][k] - v for k, v in value["used"].items()}
    return value


def report(ledger, *, owner):
    value = render_status(ledger, owner=owner)

    def esc(v):
        return html.escape(str(v))

    budgets = "".join(
        f"<tr><th>{esc(k)}</th><td>{v}</td><td>{value['remaining'][k]}</td></tr>"
        for k, v in value["used"].items()
    )
    operations = "".join(
        f"<tr><td>{esc(op['id'])}</td><td>{esc(op['phase'])}</td><td>{esc(op['state'])}</td><td><pre>{esc(json.dumps(op['result'],indent=2))}</pre></td></tr>"
        for op in value["operations"]
    )
    notes = "".join(
        f"<details><summary>{esc(n['kind'])} #{n['sequence']}</summary><pre>{esc(json.dumps(n['body'],indent=2))}</pre></details>"
        for n in value["notes"]
    )
    trials = "".join(
        f"<tr><td>{index+1}</td><td><pre>{esc(json.dumps(t['recipe'],sort_keys=True))}</pre></td><td>{esc(t.get('completed_steps'))}</td><td>{esc(t.get('worker_seconds'))}</td><td><pre>{esc(json.dumps(t.get('diagnostics'),indent=2))}</pre></td></tr>"
        for index, t in enumerate(value["trials"])
    )
    finals = "".join(
        f"<pre>{esc(json.dumps(item,indent=2))}</pre>"
        for item in value["epoch_results"]
    )
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Carbon miner research status</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:2em auto;padding:1em;color:#182329;background:#f6f7f5}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;border-bottom:1px solid #ccd4d0;padding:.6em}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}details{{margin:1em 0}}h1,h2{{color:#174b3b}}</style>
<h1>Carbon miner research</h1><p>Status: <strong>{esc(value['status'])}</strong></p>
<p>This view shows retained operations only. It does not imply a provider call, training run or accepted improvement.</p>
<p>Campaign digest: {esc(value['campaign_digest'])}<br>First operation (Unix UTC): {esc(value['started_unix'])}</p>
<h2>Current operation</h2><p>Elapsed seconds: {esc(round(value["elapsed_seconds"],1))}; remaining: {esc(round(value["remaining_elapsed_seconds"],1))}</p><pre>{esc(json.dumps({"active_operations":value["active_operations"],"hypothesis":value["current_hypothesis"]},indent=2))}</pre><h2>Research versus final work</h2><pre>{esc(json.dumps(value["phase_accounting"],indent=2))}</pre><h2>Cumulative accounting</h2><p>Unresolved operations keep their full reservations. Repository CI is separate.</p><table><tr><th>Resource</th><th>Used or reserved</th><th>Remaining ceiling</th></tr>{budgets}</table>
<h2>Real research trials</h2><p>These single-replica practice observations are adaptively seen, with primary-only references. Full curves and diagnostics remain in miner-owned files and worker snapshots.</p><table><tr><th>Trial</th><th>Recipe</th><th>Completed updates</th><th>Worker seconds</th><th>Permitted diagnostics</th></tr>{trials}</table>
<h2>Independent final comparisons</h2>{finals}<p>Fresh final EVAL and STRESS cases are withheld until recipe freeze. Three construction replicas do not establish a population confidence interval. Chain state, model quality, and payment remain separate.</p>
<h2>Retained operations</h2><table><tr><th>Identity</th><th>Phase</th><th>Disposition</th><th>Result</th></tr>{operations}</table>
<h2>Hypotheses, decisions and capability requests</h2>{notes}<p>{esc(value['eligibility'])}. Chain transactions: zero.</p></html>"""
    for name, data in (
        ("research-report.html", document),
        ("research-report.json", json.dumps(value, indent=2, allow_nan=False)),
        ("agent-report.json", json.dumps(value, indent=2, allow_nan=False)),
    ):
        path = ledger.root / name
        if path.is_symlink():
            raise ValueError("report symlink rejected")
        ledger.check_storage(
            max(
                0,
                len(data.encode("utf-8"))
                - (path.stat().st_size if path.exists() else 0),
            )
        )
        path.write_text(data, encoding="utf-8")
        path.chmod(0o600)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "report"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    args = parser.parse_args()
    ledger = CampaignLedger(args.root)
    value = (report if args.command == "report" else render_status)(
        ledger, owner=args.owner
    )
    print(json.dumps(value, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
