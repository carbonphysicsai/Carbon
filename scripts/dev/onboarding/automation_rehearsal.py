"""Bounded motor command-consolidation trial; tool clocks are not human labour."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from carbon.challenge_pipeline.onboarding import metrics, packet, timeline

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/development/challenge_pipeline/automation-rehearsal/report.json"
SOURCE = "docs/development/challenge_pipeline/automation-rehearsal/README.md"
HEADS = {
    "packet": "481f2e64ac5925013d1e1a06c6a53336fd75249d",
    "law": "3651720553a7c167e9c71819c87da98c37230b55",
    "panel": "a410c386f104dc2a1ad4935ddf9ac8be48c2e797",
    "timer": "b1cc1e8bf0a4fde38cc8c21b0de7c9e8d04380fb",
}
STAGES = {
    "packet": ("S1_packet", "packet"),
    "law": ("S4_question_law", "question_law"),
    "panel": ("S3_feasibility_value_panel", "panel"),
}
MANIFESTS = {
    "packet": "docs/development/challenge_pipeline/packet-reconcile/motor-manifest.json",
    "law": "docs/development/challenge_pipeline/law-consistency/motor-bindings.json",
}
DRIVERS = {
    "packet": "from carbon.challenge_pipeline.onboarding import packet,reconcile as mod; import json,sys; from pathlib import Path; root=Path('.'); spec=packet.read_json(root/sys.argv[1]); spec['checks']=[spec['checks'][int(sys.argv[2])]] if sys.argv[2]!='all' else spec['checks']; print(json.dumps(mod.reconcile(root,spec)['checks']))",
    "law": "from carbon.challenge_pipeline.onboarding import packet,law_consistency as mod; import json,sys; from pathlib import Path; root=Path('.'); spec=packet.read_json(root/sys.argv[1]); spec['checks']=[spec['checks'][int(sys.argv[2])]] if sys.argv[2]!='all' else spec['checks']; print(json.dumps(mod.check(root,spec)['checks']))",
    "panel": "from carbon.challenge_pipeline.onboarding import packet,panel_diff; import json; from pathlib import Path; root=Path('.'); brief=packet.read_json(root/'docs/development/challenge_pipeline/onboarding-automation/motor-brief.json'); print(json.dumps(panel_diff.generate(packet.generate(brief,root))))",
}


def run(root, args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    if len(result.stdout) > 2_000_000:
        raise packet.DraftError("bounded rehearsal output required")
    return json.loads(result.stdout)


def timer(root, command, **values):
    args = [
        "-m",
        "carbon.challenge_pipeline.onboarding.telemetry",
        "--root",
        str(ROOT),
        command,
        "--challenge",
        "motor",
    ]
    for key, value in values.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    return run(root, args)


def summarize(phases):
    baseline = sum(p["per_clause_wall_s"] for p in phases)
    batch = sum(p["batched_wall_s"] for p in phases)
    return {
        "control": "SAME_CHECKER_PER_CLAUSE_NOT_HISTORICAL_MANUAL_REVIEW",
        "baseline_invocations": sum(p["baseline_invocations"] for p in phases),
        "batched_invocations": len(phases),
        "per_clause_wall_s": baseline,
        "batched_wall_s": batch,
        "observed_command_consolidation_ratio": baseline / batch if batch > 0 else None,
        "human_labour_speedup": None,
        "human_labour_basis": "NOT_DEMONSTRATED_NO_MEASURED_HUMAN_BASELINE",
        "all_compared_outputs_equal": all(p["outputs_equal"] for p in phases),
        "trial_n": 1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in HEADS:
        parser.add_argument("--" + name + "-root", type=Path, required=True)
    args = parser.parse_args()
    if OUT.exists():
        parser.exit(
            2,
            "Retained timing report exists; make a new versioned trial, never overwrite history\n",
        )
    roots = {name: getattr(args, name + "_root").resolve() for name in HEADS}
    for name, root in roots.items():
        if timeline.git(root, "rev-parse", "HEAD") != HEADS[name] or timeline.git(
            root, "diff", "--name-only", "HEAD"
        ):
            parser.exit(2, "Candidate tool head/tree changed: " + name + "\n")
    phases, event_ids = [], []
    for name, root in roots.items():
        if name == "timer":
            continue
        stage, milestone = STAGES[name]
        data = packet.read_json(root / MANIFESTS[name]) if name in MANIFESTS else None
        count = len(data["checks"]) if data else 1
        observations = {}
        for mode in ("per_clause", "batched"):
            cycle = "motor-command-trial-" + name + "-" + mode.replace("_", "-")
            entry = timer(
                roots["timer"],
                "entry",
                cycle=cycle,
                stage=stage,
                actor="checker-" + name,
                actor_kind="TOOL",
                source=SOURCE,
            )
            start = timer(
                roots["timer"],
                "start",
                cycle=cycle,
                stage=stage,
                actor="checker-" + name,
                actor_kind="TOOL",
                source=SOURCE,
                milestone=milestone,
            )
            then = perf_counter()
            if name == "panel":
                result = run(root, ["-c", DRIVERS[name]])
            elif mode == "batched":
                result = run(root, ["-c", DRIVERS[name], MANIFESTS[name], "all"])
            else:
                result = [
                    r
                    for i in range(count)
                    for r in run(root, ["-c", DRIVERS[name], MANIFESTS[name], str(i)])
                ]
            elapsed = perf_counter() - then
            end = timer(roots["timer"], "finish", ref_id=start["id"])
            exit_ = timer(
                roots["timer"], "exit", ref_id=entry["id"], disposition="PREPARED"
            )
            event_ids.extend(e["id"] for e in (entry, start, end, exit_))
            observations[mode] = (result, elapsed)
        phases.append(
            {
                "phase": name,
                "baseline_invocations": count,
                "per_clause_wall_s": observations["per_clause"][1],
                "batched_wall_s": observations["batched"][1],
                "outputs_equal": observations["per_clause"][0]
                == observations["batched"][0],
                "compared_output_digest": packet.digest(
                    json.dumps(observations["batched"][0], sort_keys=True).encode()
                ),
                "full_checklist_claim": False,
            }
        )
    process = timer(roots["timer"], "view")
    sources = packet.read_json(
        ROOT / "docs/development/challenge_pipeline/onboarding-metrics/sources.json"
    )
    historical = packet.read_json(
        ROOT / "docs/development/challenge_pipeline/onboarding-metrics/report.json"
    )
    prs = packet.read_json(
        ROOT
        / "docs/development/challenge_pipeline/onboarding-metrics/pull-requests.json"
    )
    observations = {
        (r["challenge"], r["stage"]): r["source"] for r in historical["rows"]
    }
    refreshed = metrics.summarize(
        observations,
        sources,
        prs["prs"],
        captured_at=prs["captured_at"],
        effort_events=process["metrics_effort_events"],
    )
    motor = [
        {
            "stage": r["stage"],
            "historical_arrival_gap_s": r["previous_artifact_arrival_gap_s"],
            "human_team_effort_hours": r["team_effort_hours"],
            "accepted_stage_elapsed_s": r["stage_elapsed_s"],
        }
        for r in refreshed["rows"]
        if r["challenge"] == "motor"
    ]
    report = {
        "schema": "carbon.onboarding.motor-command-rehearsal.v1",
        "scope": "PUBLIC_DEVELOPMENT_PREPARATION_ONLY",
        "authority_main": timeline.git(ROOT, "rev-parse", "HEAD"),
        "candidate_tool_heads": HEADS,
        "phases": phases,
        "comparison": summarize(phases),
        "process_view": process,
        "event_ids": event_ids,
        "metrics_replay": {
            "basis": "RETAINED_HISTORICAL_GIT_PR_CAPTURE_PLUS_NEW_TOOL_CLOCKS_NOT_FRESH_GIT_CAPTURE",
            "historical_capture_utc": prs["captured_at"],
            "historical_sources_sha256": packet.digest(
                (
                    ROOT
                    / "docs/development/challenge_pipeline/onboarding-metrics/sources.json"
                ).read_bytes()
            ),
            "motor_rows": motor,
        },
        "solver_runs": 0,
        "spend": 0,
        "stage_acceptance": False,
        "limits": "One unblinded command-consolidation trial; not total onboarding, human labour savings, V4 model value or scientific qualification. Missing panel seed/pins/index and unbound buyer/law fields remain open.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report["comparison"], indent=2))


if __name__ == "__main__":
    main()
