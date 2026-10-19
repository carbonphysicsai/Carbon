"""Freeze and observe an eight-geometry public f08 near-feasible pilot.

The actions are prospective but chosen near one public TRAIN action, so this
is a local DEVELOPMENT pilot, not a population or hidden-bank claim. The
existing f08 deck, mode ladder, convergence bands and bank-mesh logic decide
the numerical verdicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import f08_bank as bank
import f08_deck as deck
import f08_freeze as freeze_mod

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ACTIONS = (
    ROOT
    / "docs/development/evidence/reference-solvers-2026-10-15/pins/f08-near-feasible-actions.json"
)
DEFAULT_TRAIN = (
    ROOT
    / "docs/development/evidence/reference-solvers-2026-10-15/pins/f08-train-256-h3-manifest.json"
)
H_WITNESS = (2.25, 1.7)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validated_actions(registration, actions_path, train_path):
    selected = json.loads(Path(actions_path).read_text())["actions"]
    train = json.loads(Path(train_path).read_text())["cases"]
    if len(selected) != 8 or len(train) != 256:
        raise ValueError(
            "expected eight pilot actions and complete frozen 256-row TRAIN"
        )
    actions = [bank.s.action(registration, action) for action in selected]
    digests = [bank.s.tasks.digest(action) for action in actions]
    train_digests = {row["action_digest"] for row in train}
    if len(set(digests)) != 8 or train_digests.intersection(digests):
        raise ValueError("pilot action duplicates another pilot action or frozen TRAIN")
    return actions


def freeze(
    out, registration_path, actions_path=DEFAULT_ACTIONS, train_path=DEFAULT_TRAIN
):
    reg = json.loads(Path(registration_path).read_text())
    actions = validated_actions(reg, actions_path, train_path)
    out = Path(out)
    doc = bank.freeze(
        reg,
        0,
        out,
        count=8,
        h_mm=freeze_mod.H_PRIMARY,
        jobs=4,
        public_seed=True,
        role="pilot",
        actions=actions,
    )
    for i, action in enumerate(actions):
        for h in H_WITNESS:
            name = f"pilot-{i:04d}-h{h:g}"
            case_dir = out / "f08" / name
            size = deck.write_case(action, case_dir, h, bank.MODES)
            doc["cases"].append(
                {
                    "family": "f08",
                    "case": name,
                    "reservation": "pilot_witness",
                    "command": deck.BANK_COMMAND,
                    "mesh": size,
                    **deck.estimate(size["nodes"]),
                    "action": action,
                    "action_digest": bank.s.tasks.digest(action),
                    "files": freeze_mod._digest(case_dir),
                }
            )
    doc["counts"] = {"pilot": 8, "pilot_witness": 16}
    doc["pilot"] = {
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "selection": "TRAIN-informed local neighborhood; not independent population",
        "actions_sha256": _sha(actions_path),
        "train_manifest_sha256": _sha(train_path),
        "geometry_count": 8,
        "rungs_h_mm": [3.0, 2.25, 1.7],
    }
    (out / "manifest.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def _nonnegative_metric(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value


def _native_execution(bulk):
    """Read execution evidence once; a parsed case.dat is not a completed run."""
    ledger = Path(bulk) / "ledger.jsonl"
    evidence = {
        "sha256": None,
        "finished": {},
        "native_cases": set(),
        "native_run": False,
    }
    if not ledger.is_file():
        return evidence
    raw = ledger.read_bytes()
    evidence["sha256"] = hashlib.sha256(raw).hexdigest()
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        row = json.loads(line)
        if row.get("event") == "RUN_START":
            evidence["native_run"] = row.get("docker", {}).get("executor") == "native"
        if row.get("family") != "f08" or "case" not in row:
            continue
        if row.get("executor") == "native":
            evidence["native_cases"].add(row["case"])
        if row.get("event") == "FINISHED":
            evidence["finished"][row["case"]] = (row, line_number)
    return evidence


def _native_execution_issue(name, evidence):
    finished = evidence["finished"].get(name)
    if finished is not None and finished[0].get("executor") != "native":
        return None  # Preserve the frozen observer's nonnative behavior.
    if name not in evidence["native_cases"] and not evidence["native_run"]:
        return None
    if finished is None:
        return {"status": "INCOMPLETE_NATIVE_EXECUTION", "execution_outcome": None}
    row, _ = finished
    if row.get("outcome") != "COMPLETED":
        return {"status": "EXECUTION_FAILED", "execution_outcome": row.get("outcome")}
    return None


def _bind_native_costs(summary, evidence):
    """Use case-scoped FINISHED metrics, never a native pod's cgroup.txt.

    The frozen legacy observer remains unchanged. Its cgroup fields are
    cleared for native cases because those counters cover the whole pod.
    Explicit native fields and their ledger provenance carry measured costs;
    missing metrics remain unknown, and an actually measured zero stays zero.
    Failed or unfinished native executions cannot retain a scientific verdict.
    """
    for name in list(summary["cases"]):
        finished = evidence["finished"].get(name)
        if finished is not None:
            row, line_number = finished
            if row.get("executor") != "native":
                continue
        elif name in evidence["native_cases"] or evidence["native_run"]:
            row, line_number = {}, None
        else:
            continue
        cost = summary["cases"][name].setdefault("cost", {})
        cpu = _nonnegative_metric(row.get("rusage_cpu_s"))
        rss = _nonnegative_metric(row.get("rusage_maxrss_bytes"))
        sampled = _nonnegative_metric(row.get("sampled_group_rss_peak_bytes"))
        peaks = [value for value in (rss, sampled) if value is not None]
        peak = max(peaks) if peaks else None
        cost.update(
            {
                "wall_s": row.get("wall_s"),
                "outcome": row.get("outcome"),
                "host_profile": row.get("host_profile"),
                "rusage_cpu_s": cpu,
                "rusage_maxrss_bytes": rss,
                "sampled_group_rss_peak_bytes": sampled,
                "cpu_s": cpu,
                "memory_peak_mib": peak / 2**20 if peak is not None else None,
                "cgroup_cpu_s": None,
                "cgroup_memory_peak_mib": None,
                "metric_provenance": {
                    "executor": "native",
                    "event": "FINISHED" if finished is not None else "MISSING_FINISHED",
                    "case": name,
                    "ledger_sha256": evidence["sha256"],
                    "ledger_line": line_number,
                    "cpu_s": "rusage_cpu_s",
                    "memory_peak_mib": (
                        "max(rusage_maxrss_bytes,sampled_group_rss_peak_bytes)/2**20"
                    ),
                    "cgroup": "POD_SCOPED_COUNTERS_NOT_USED",
                },
            }
        )
        issue = _native_execution_issue(name, evidence)
        if issue is not None:
            summary["cases"][name] = {**issue, "cost": cost}


def observe(bulk, out):
    bulk, out = Path(bulk), Path(out)
    summary = freeze_mod.observe_all(bulk, out)
    execution = _native_execution(bulk)
    _bind_native_costs(summary, execution)
    dirs = freeze_mod._case_dirs(bulk)
    convergence = {}
    for i in range(8):
        stem = f"pilot-{i:04d}"
        names = {3.0: stem, **{h: f"{stem}-h{h:g}" for h in H_WITNESS}}
        issues = {
            name: issue
            for name in names.values()
            if (issue := _native_execution_issue(name, execution)) is not None
        }
        if issues:
            convergence[stem] = {
                "status": (
                    "EXECUTION_FAILED"
                    if any(
                        issue["status"] == "EXECUTION_FAILED"
                        for issue in issues.values()
                    )
                    else "INCOMPLETE_NATIVE_EXECUTION"
                ),
                "execution_issues": issues,
            }
            continue
        if not all(
            name in dirs and (dirs[name] / "case.dat").is_file()
            for name in names.values()
        ):
            convergence[stem] = {"status": "INCOMPLETE_LADDER"}
            continue
        try:
            rungs = {h: deck.observe(dirs[name]) for h, name in names.items()}
            convergence[stem] = deck.convergence(rungs)
        except (KeyError, IndexError, ValueError) as error:
            convergence[stem] = {"status": "OBSERVER_FAILED", "why": repr(error)}
    summary["convergence"] = convergence
    summary["bank_mesh"] = freeze_mod.bank_mesh(convergence)
    summary["scope"] = "PUBLIC_DEVELOPMENT_ONLY"
    summary["selection"] = (
        "TRAIN-informed local neighborhood; not independent population"
    )
    out.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--registration", type=Path, required=True)
    f.add_argument("--actions", type=Path, default=DEFAULT_ACTIONS)
    f.add_argument("--train-manifest", type=Path, default=DEFAULT_TRAIN)
    o = sub.add_parser("observe")
    o.add_argument("--bulk", type=Path, required=True)
    o.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.command == "freeze":
        doc = freeze(args.out, args.registration, args.actions, args.train_manifest)
        print(json.dumps(doc["counts"]))
    else:
        doc = observe(args.bulk, args.out)
        print(json.dumps(doc["bank_mesh"]))


if __name__ == "__main__":
    main()
