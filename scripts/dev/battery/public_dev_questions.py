"""Public development decision questions for battery (PUBLIC-DEV-DECISIONS-01).

    python -m scripts.dev.battery.public_dev_questions draw --work W [--questions 110]
    python -m scripts.dev.battery.public_dev_questions refine --work W
    python -m scripts.dev.battery.public_dev_questions evaluate --work W --workers N

Test Lead 2026-10-11, from SCORE-CEILING-01's cost table. The public τ ceiling
is capped by the 7 resolved development questions. About 110 new public
questions, solved and refined, target >= 64 resolved and a ceiling near 0.8.

These are SCORE-PROOF-01's sealed `draw`, `refine` and `evaluate` with three
differences, and everything here is public:
- **Seed.** The seed is public and fixed: sha256 of `SEED_LABEL`. Anyone
  regenerates the same questions from this commit.
- **Grid.** Conditions lie on a 0.5 degC grid offset by 0.25 degC
  (5.25 ... 39.75 C) x 0.01 SOC0, inside EV4's envelope. By construction no
  public question equals any condition on the 0.5 degC grid, which is the
  sealed confirmation's grid and holds EV4's public conditions. The sealed
  set was never read.
- **Contract.** It is EV4's decision contract (`ev4-dev-proof-v1`: candidate
  grid, constraints, bands, panel) with these conditions as its development
  scenarios, `contract_id` = `public-dev-decisions-v1`.

The jobs (35 per question) are solved by the truth service in the pinned truth
image (`python -m carbon.battery.truth_env solve`). `refine` appends
REF-RESOLVE-01's refined jobs. `evaluate` rebuilds the panel members on host
CPU and evaluates.

DEVELOPMENT only. No hidden material and no rule adoption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.battery import score_proof_questions as spq

CONTRACT_ID = "public-dev-decisions-v1"
SEED_LABEL = b"PUBLIC-DEV-DECISIONS-01"
T_OFFSET, T_STEP, SOC_STEP = 0.25, 0.5, 0.01


def draw_conditions(count, envelope, excluded):
    import numpy as np

    rng = np.random.default_rng(
        int.from_bytes(hashlib.sha256(SEED_LABEL).digest(), "big")
    )
    t_lo, t_hi = envelope["t_amb_c"]
    s_lo, s_hi = envelope["soc0"]
    t_grid = np.round(np.arange(t_lo + T_OFFSET, t_hi, T_STEP), 3)
    s_grid = np.round(np.arange(s_lo, s_hi + SOC_STEP / 2, SOC_STEP), 3)
    out, seen = [], set(excluded)
    while len(out) < count:
        point = (float(rng.choice(t_grid)), float(rng.choice(s_grid)))
        if point not in seen:
            seen.add(point)
            out.append(point)
    return out


def public_contract(base, conditions):
    contract = json.loads(json.dumps(base))
    contract["contract_id"] = CONTRACT_ID
    contract["scenarios"] = {
        **contract["scenarios"],
        "development": [{"id": f"D-{k:04d}", "conditions": [list(c)]} for k, c in enumerate(conditions)],
        "verification": [],
        "rule": (
            "drawn from the public seed sha256('PUBLIC-DEV-DECISIONS-01') on the 0.25-degC-offset 0.5 degC x 0.01 "
            "grid inside the envelope: disjoint by construction from every 0.5 degC grid condition"
        ),
    }  # fmt: skip
    contract["intended_use"] = (
        "PUBLIC-DEV-DECISIONS-01 public development decision questions: EV4's decision contract with "
        "publicly drawn operating conditions; DEVELOPMENT"
    )
    return contract


def draw(work, questions):
    from carbon.battery.value import contract as ev
    from carbon.battery.value.experiment import Experiment

    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    if (work / "contract.json").exists():
        raise SystemExit("refused: this work directory already holds its questions")
    base, _ = ev.load(spq.BASE_CONTRACT)
    conditions = draw_conditions(
        questions, base["operating_conditions"]["envelope"], spq.public_conditions(base)
    )
    if any(
        round((t - 5.0) / T_STEP, 6) == round((t - 5.0) / T_STEP) for t, _ in conditions
    ):
        raise SystemExit("refused: a condition sits on the 0.5 degC grid")
    contract = public_contract(base, conditions)
    (work / "contract.json").write_text(json.dumps(contract, indent=1) + "\n")
    _document, digest = ev.load(work / "contract.json")
    Experiment(work / "experiment", repository=ROOT).freeze(str(work / "contract.json"))
    jobs = [
        {k: job[k] for k in ("case_id", "c1", "c2", "t_amb_c", "soc0")}
        for job in ev.decision_cases(contract)
    ]
    body = spq._canonical({"fingerprint": digest, "jobs": jobs})
    (work / "jobs.json").write_bytes(body)
    (work / "records.jsonl").touch(mode=0o600)  # the truth service needs owner-only
    return {"questions": questions, "jobs": len(jobs), "contract_digest": digest,
            "jobs_sha256": hashlib.sha256(body).hexdigest()}  # fmt: skip


def refine(work):
    work = Path(work)
    contract = json.loads((work / "contract.json").read_bytes())
    jobs_file = json.loads((work / "jobs.json").read_bytes())
    added = spq.refine_jobs(contract, spq._records(work), jobs_file["jobs"])
    jobs_file["jobs"] = jobs_file["jobs"] + added
    (work / "jobs.json").write_bytes(spq._canonical(jobs_file))
    (work / "refine-jobs.json").write_bytes(
        spq._canonical({"fingerprint": jobs_file["fingerprint"], "jobs": added})
    )
    return {"refine_jobs": len(added)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="public_dev_questions")
    sub = parser.add_subparsers(dest="command", required=True)
    drawn = sub.add_parser("draw")
    drawn.add_argument("--work", type=Path, required=True)
    drawn.add_argument("--questions", type=int, default=110)
    refined = sub.add_parser("refine")
    refined.add_argument("--work", type=Path, required=True)
    evaluated = sub.add_parser("evaluate")
    evaluated.add_argument("--work", type=Path, required=True)
    evaluated.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    if args.command == "draw":
        result = draw(args.work, args.questions)
    elif args.command == "refine":
        result = refine(args.work)
    else:
        result = spq.evaluate(args.work, args.workers)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
