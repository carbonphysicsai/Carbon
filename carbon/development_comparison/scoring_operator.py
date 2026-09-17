"""Trusted scoring commands; no model provider, training or chain dispatch."""

from __future__ import annotations

import argparse
import html
import json
import statistics
from pathlib import Path

from carbon.development_session.budget import SessionBudget
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.scoring.development import RULE

from .acceptance import (
    DevelopmentAcceptanceRef,
    create_report,
    register,
    resolve_acceptance,
)
from .sources import read_json


def report_ref(root):
    return DevelopmentAcceptanceRef(
        root,
        (root / "registration-pin.txt").read_text().strip(),
        (root / "report-pin.txt").read_text().strip(),
    )


def owner_report(ref):
    report = resolve_acceptance(ref)
    if (ref.root / "owner-scoring-report.json").exists():
        existing = read_json(ref.root / "owner-scoring-report.json")
        if existing["report_digest"] != ref.report_digest:
            raise ValueError("owner report identity conflict")
        return existing
    d = report["decision"]
    lines = [
        "# Carbon DEVELOPMENT measurement and scoring review",
        "",
        "Rule: " + RULE["id"] + " (`" + report["rule_digest"] + "`).",
        "**Disposition: "
        + d["disposition"]
        + "**. No accepted real improvement, payment or network change is implied.",
        "",
        "Baseline construction: `"
        + json.dumps(report["baseline_strategy"], sort_keys=True)
        + "`.",
        "Challenger construction: `"
        + json.dumps(report["challenger_strategy"], sort_keys=True)
        + "`.",
        "",
        "Both are retained authentic results on the seen 12 TRAIN / 12 EVAL / 12 STRESS development subset. New derived measurements preserve original signed receipts. No fresh training or model calls occurred. Historical agent feedback use is recorded in the prior session; this measurement task ran no new agent.",
        "",
        "| Role | Metric (lower is better) | FNO-40 mean | FNO-48 mean | Difference | Baseline replica SD | Challenger replica SD |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for role in ("EVAL", "STRESS"):
        for name, bvalue in d["baseline"]["roles"][role]["metrics"].items():
            cvalue = d["challenger"]["roles"][role]["metrics"][name]
            spreads = []
            for rows in report["measurements"]["sources"]:
                means = [
                    statistics.mean(
                        row["measurement"]["metrics"][name]
                        for row in rows
                        if row["role"] == role and row["replica"] == k
                    )
                    for k in range(3)
                ]
                spreads.append(statistics.stdev(means))
            lines.append(
                f"| {role} | {name} | {bvalue:.8g} | {cvalue:.8g} | {cvalue-bvalue:+.8g} | {spreads[0]:.5g} | {spreads[1]:.5g} |"
            )
    lines += [
        "",
        "## Decision and limits",
        "",
        f"Descriptive scores: {d['baseline']['score']:.9f} -> {d['challenger']['score']:.9f}. These are inadmissible diagnostic ranks, not accepted winner scores.",
        f"Finite-replica/reference score-difference envelope: {d['difference_interval']}. This is not a confidence interval.",
        "Baseline mandatory failures: "
        + ", ".join(d["baseline"]["failed_mandatory"])
        + ".",
        "Challenger mandatory failures: "
        + ", ".join(d["challenger"]["failed_mandatory"])
        + ".",
        "Reference sensitivity: `"
        + json.dumps(report["reference_indicators"], sort_keys=True)
        + "`.",
        "Three reconstructions and twelve cases per role are separate dependence dimensions. No independent case-by-replica sample count or population superiority is claimed. Shared-method refinement is an empirical indicator, not an independent reference witness or qualified error bound.",
        "",
        "## Why the old scalar diagnostics did not change",
        "",
    ]
    for label, rows in zip(
        ("baseline", "challenger"), report["measurements"]["sources"], strict=True
    ):
        diagnostics = [x["measurement"]["diagnostics"] for x in rows]
        counts = {
            k: sum(x[k] == 0 for x in diagnostics)
            for k in (
                "candidate_compression_time_index",
                "candidate_peak_dissipation_time_index",
            )
        }
        censored = sum(
            x["candidate_half_time"]["status"] == "RIGHT_CENSORED" for x in diagnostics
        )
        lines.append(
            f"{label}: sampled compression maximum at t=0 in {counts['candidate_compression_time_index']}/72; peak dissipation at t=0 in {counts['candidate_peak_dissipation_time_index']}/72; absent half-energy crossing in {censored}/72. Exact artifact associations were checked against signed request hashes. The old fourfold spatial compression differs in spatial interpolation, but shared initial conditions/time-extremum domination and horizon clipping explain the repeated outputs; they do not prove identical trajectories."
        )
    taskroot = (
        ref.root.parent
        if (ref.root.parent / "task-envelope.json").exists()
        else ref.root
    )
    accounting = SessionBudget(taskroot / "numerical-budget.sqlite3").summary()
    resources = []
    for p in taskroot.rglob("resources.json"):
        v = read_json(p)
        resources.append({"operation": str(p.parent.relative_to(taskroot)), **v})
    size = sum(p.stat().st_size for p in taskroot.rglob("*") if p.is_file())
    lines += [
        "",
        "## Execution accounting",
        "",
        "Numerical task ledger: `" + json.dumps(accounting, sort_keys=True) + "`.",
        f"New retained artifacts before this report: {size:,} bytes. Each numerical carrier uses the accepted 2-CPU/4-GiB/no-swap, no-network controls; one worker at a time. Required repository acceptance is separate.",
        "New provider calls: 0. New provider charges: USD 0. Fresh training: 0. Public-network transactions: 0. Synthetic reward checks are software/control evidence, not real winners.",
        "",
        "## Retained evidence",
        "",
        f"Baseline source: {report['baseline_source']}",
        f"Challenger source: {report['challenger_source']}",
        f'Derived signed report: {ref.root / "development-acceptance.json"}',
        f"Report digest: {ref.report_digest}",
        f"Calibration and verification: {taskroot}",
        "",
        "## Next step",
        "",
        "Authorize one complete fresh construction/agent experiment under the frozen rule; see the repository next-experiment request. An admissible finite-cohort accepted comparison is required before a real non-paying reward simulation. Non-burn testnet additionally needs a winner-capable checked publication profile, finalized identity mapping and separate exact transaction authority. Scientific/production qualification remains unearned.",
    ]
    text = "\n".join(lines) + "\n"
    write_once(ref.root / "owner-scoring-report.md", text.encode())
    payload = {
        "schema": "carbon.cw1.scoring-owner-report.v1",
        "report_digest": ref.report_digest,
        "accounting": accounting,
        "resources": resources,
        "retained_bytes_before_report": size,
        "provider_usd": 0,
        "provider_calls": 0,
        "training_runs": 0,
        "public_transactions": 0,
    }
    write_once(ref.root / "owner-scoring-report.json", canonical(payload))
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Carbon development scoring</title><style>body{max-width:1100px;margin:40px auto;padding:0 24px;color:#e8edf5;background:#111820;font:16px/1.55 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{color:#83dfb5}</style><h1>Carbon DEVELOPMENT scoring</h1><pre>'
        + html.escape(text)
        + "</pre></html>"
    )
    write_once(ref.root / "owner-scoring-report.html", page.encode())
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("freeze", "derive", "status", "report", "feedback")
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--challenger", type=Path)
    parser.add_argument("--image-manifest", type=Path)
    parser.add_argument("--resume-completed", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        config = read_json(args.config)
        pin = register(
            args.root,
            template_source=Path(config["template_source"]),
            quarantine_journal=Path(config["quarantine_journal"]),
            reference_root=Path(config["reference_root"]),
            sessions=config["sessions"],
        )
        write_once(args.root / "registration-pin.txt", pin.encode())
        print(json.dumps({"root": str(args.root), "registration_digest": pin}))
        return
    if args.command == "derive":
        ref = create_report(
            args.root,
            (args.root / "registration-pin.txt").read_text().strip(),
            args.baseline,
            args.challenger,
            image=load_image_identity(args.image_manifest),
            resume_completed=args.resume_completed,
        )
        write_once(args.root / "report-pin.txt", ref.report_digest.encode())
        print(json.dumps({"report_digest": ref.report_digest}))
        return
    ref = report_ref(args.root)
    if args.command == "report":
        result = owner_report(ref)
        print(
            json.dumps(
                {
                    "report": str(args.root / "owner-scoring-report.html"),
                    "report_digest": ref.report_digest,
                    "numerical_operations": len(result["accounting"]),
                    "provider_usd": 0,
                    "public_transactions": 0,
                }
            )
        )
        return
    if args.command == "feedback":
        from carbon.orchestration.development_feedback import (
            project_development_acceptance,
        )

        print(json.dumps(project_development_acceptance(ref), indent=2))
        return
    doc = resolve_acceptance(ref)
    print(
        json.dumps(
            {
                "rule_digest": doc["rule_digest"],
                "disposition": doc["decision"]["disposition"],
                "accepted_improvement": doc["decision"]["accepted_improvement"],
                "report": str(args.root / "owner-scoring-report.html"),
                "source_lifecycle": "ACTIVE_C10_ELIGIBLE_AT_READBACK",
                "provider_calls": 0,
                "public_transactions": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
