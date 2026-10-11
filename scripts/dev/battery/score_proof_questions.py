"""Sealed confirmation questions for the score proof (SCORE-PROOF-01).

Operator host only (the AX42, as `carbon-producer`). The questions are sealed:
their seed, conditions and contract stay in the private work directory `W`;
only counts and the contract digest are printed. The solves go through the
startup-host procedure (`startup_shard`, STARTUP_HOST_RUNBOOK.md) and are
merged back into `W/records.jsonl`.

    python -m scripts.dev.battery.score_proof_questions draw --work W --questions 150 [--quiz Q]
    (split, push, solve on the startup host, pull, merge: the runbook, with --work W)
    python -m scripts.dev.battery.score_proof_questions refine --work W
    (a second split / solve / merge round for the refine jobs)
    python -m scripts.dev.battery.score_proof_questions evaluate --work W --workers N

- **draw.** The host draws its own 32-byte seed (`W/seed`, owner-only) and,
  from it, `--questions` operating conditions on a 0.5 degC x 0.01 grid
  inside EV4's envelope. These avoid EV4's 24 public conditions and, given
  `--quiz`, the quiz's Q3 conditions. The sealed contract is EV4's decision
  contract (`ev4-dev-proof-v1`: its candidate grid, constraints, bands and
  panel), with these conditions as its development scenarios. It is frozen
  as an experiment under `W/experiment`, and `W/jobs.json` holds its
  35 x N reference jobs, in the shape `startup_shard` splits.
- **refine.** Every standard reference the contract's bands leave
  UNRESOLVED, or that failed, gets a refined job (`refined: true`). That is
  REF-RESOLVE-01's policy, appended to `W/jobs.json` for a second round.
- **evaluate.** It imports the merged references, overlays the settled
  refined ones, rebuilds every panel member on host CPU (`--workers` in
  parallel) predicting the sealed cases, and evaluates. The results
  (`W/experiment/results/results.json`) are the confirmation phase's
  decision values (`score_proof --phase confirmation --dev-results`).

DEVELOPMENT only. Nothing here adopts a rule or sets a threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-dev-proof-v1.json"
CONTRACT_ID = "score-proof-confirmation-sealed-v1"
T_STEP, SOC_STEP = 0.5, 0.01


def _private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def seed(work):
    """The host's own seed for this work directory, made once."""
    path = Path(work) / "seed"
    if not path.exists():
        _write_private(path, secrets.token_bytes(32))
    return path.read_bytes()


def public_conditions(contract):
    return {
        (round(float(t), 3), round(float(s), 3))
        for split in ("development", "verification")
        for scenario in contract["scenarios"][split]
        for t, s in scenario["conditions"]
    }


def quiz_conditions(quiz):
    """The quiz's Q3 conditions (a quiz work directory's `draws.json`)."""
    if quiz is None:
        return set()
    draws = json.loads((Path(quiz) / "draws.json").read_bytes())
    out = set()
    for scenario in draws["q3"]:
        t_amb, soc0 = scenario["condition"]
        out.add((round(float(t_amb), 3), round(float(soc0), 3)))
    return out


def draw_conditions(seed_bytes, count, envelope, excluded):
    """`count` distinct grid conditions inside the envelope, none excluded,
    in the seed's deterministic order."""
    import numpy as np

    rng = np.random.default_rng(
        int.from_bytes(hashlib.sha256(seed_bytes).digest(), "big")
    )
    t_lo, t_hi = envelope["t_amb_c"]
    s_lo, s_hi = envelope["soc0"]
    t_grid = np.round(np.arange(t_lo, t_hi + T_STEP / 2, T_STEP), 3)
    s_grid = np.round(np.arange(s_lo, s_hi + SOC_STEP / 2, SOC_STEP), 3)
    if count > len(t_grid) * len(s_grid) - len(excluded):
        raise SystemExit("refused: more questions than grid conditions")
    out, seen = [], set(excluded)
    while len(out) < count:
        point = (float(rng.choice(t_grid)), float(rng.choice(s_grid)))
        if point not in seen:
            seen.add(point)
            out.append(point)
    return out


def sealed_contract(base, conditions):
    contract = json.loads(json.dumps(base))
    contract["contract_id"] = CONTRACT_ID
    contract["scenarios"] = {
        **contract["scenarios"],
        "development": [
            {"id": f"P-{k:04d}", "conditions": [list(c)]}
            for k, c in enumerate(conditions)
        ],
        "verification": [],
        "rule": (
            "host-drawn from a host-generated seed on a 0.5 degC x 0.01 grid inside the "
            "envelope, disjoint from EV4's public and the quiz's Q3 conditions; sealed"
        ),
    }
    contract["intended_use"] = (
        "SCORE-PROOF-01 sealed confirmation questions: EV4's decision contract with "
        "host-drawn operating conditions; operator host only; DEVELOPMENT"
    )
    return contract


def draw(work, questions, quiz=None):
    from carbon.battery.value import contract as ev
    from carbon.battery.value.experiment import Experiment

    work = _private_dir(work)
    if (work / "contract.json").exists():
        raise SystemExit("refused: this work directory already holds its questions")
    base, _ = ev.load(BASE_CONTRACT)
    excluded = public_conditions(base) | quiz_conditions(quiz)
    conditions = draw_conditions(
        seed(work), questions, base["operating_conditions"]["envelope"], excluded
    )
    contract = sealed_contract(base, conditions)
    _write_private(work / "contract.json", json.dumps(contract, indent=1).encode())
    _document, digest = ev.load(work / "contract.json")
    experiment = Experiment(work / "experiment", repository=ROOT)
    experiment.freeze(str(work / "contract.json"))
    jobs = [
        {k: job[k] for k in ("case_id", "c1", "c2", "t_amb_c", "soc0")}
        for job in ev.decision_cases(contract)
    ]
    _write_private(
        work / "jobs.json",
        _canonical({"fingerprint": digest, "jobs": jobs}),
    )
    (work / "records.jsonl").touch(mode=0o600)
    return {"questions": questions, "jobs": len(jobs), "contract_digest": digest}


def _records(work):
    path = Path(work) / "records.jsonl"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def refine_jobs(contract, records, jobs):
    """The refine jobs REF-RESOLVE-01's policy asks for: every standard
    record that failed, or whose checks the contract's bands leave
    UNRESOLVED."""
    from carbon.battery.value import decision as d

    bands = contract["reference"]["uncertainty"]["bands"]
    by_case = {j["case_id"]: j for j in jobs if not j.get("refined")}
    refined = {j["case_id"] for j in jobs if j.get("refined")}
    out = []
    for record in records:
        case = record.get("case_id")
        if record.get("refined") or case not in by_case or case in refined:
            continue
        unresolved = (
            record.get("status") != "OK"
            or d.UNRESOLVED
            in d.check(contract, d.measure(contract, record["outputs"]), bands).values()
        )
        if unresolved:
            out.append({**by_case[case], "refined": True})
            refined.add(case)
    return out


def refine(work):
    work = Path(work)
    contract = json.loads((work / "contract.json").read_bytes())
    jobs_file = json.loads((work / "jobs.json").read_bytes())
    added = refine_jobs(contract, _records(work), jobs_file["jobs"])
    jobs_file["jobs"] = jobs_file["jobs"] + added
    _write_private(work / "jobs.json", _canonical(jobs_file))
    return {"refine_jobs": len(added)}


def _rebuild_one(args):
    root, member = args
    from carbon.battery.value.experiment import Experiment

    Experiment(Path(root), repository=ROOT).panel(only={member})
    return member


def evaluate(work, workers=1):
    from concurrent.futures import ProcessPoolExecutor

    from carbon.battery.value import reference_policy
    from carbon.battery.value.experiment import Experiment

    work = Path(work)
    experiment = Experiment(work / "experiment", repository=ROOT)
    imported = experiment.import_references(work / "records.jsonl")
    members = [m for m, *_ in experiment._members()]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        rebuilt = list(
            pool.map(_rebuild_one, [(str(experiment.root), m) for m in members])
        )
    settled = reference_policy.settled(work / "records.jsonl")
    references = reference_policy.overlay(experiment.reference_map(), settled)
    results = experiment.evaluate(references)
    return {
        "references_imported": imported["imported"],
        "refined_settled": len(settled),
        "members": len(rebuilt),
        "results": "experiment/results/results.json (sealed; stays here)",
        "summary_members": len(results["summary"]["members"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="score_proof_questions")
    sub = parser.add_subparsers(dest="command", required=True)
    drawn = sub.add_parser("draw")
    drawn.add_argument("--work", type=Path, required=True)
    drawn.add_argument("--questions", type=int, required=True)
    drawn.add_argument("--quiz", type=Path)
    refined = sub.add_parser("refine")
    refined.add_argument("--work", type=Path, required=True)
    evaluated = sub.add_parser("evaluate")
    evaluated.add_argument("--work", type=Path, required=True)
    evaluated.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    if args.command == "draw":
        result = draw(args.work, args.questions, args.quiz)
    elif args.command == "refine":
        result = refine(args.work)
    else:
        result = evaluate(args.work, args.workers)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
