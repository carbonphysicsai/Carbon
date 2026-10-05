"""EV5-RUN-01: EV5's pre-registered analysis, its three verdicts, and the
host-only path for the sealed confirmation batch.

EV5 froze on 2026-10-03 (`ev5.FREEZE_MANIFEST`) with its hypotheses fixed in
`docs/development/BATTERY_ENGINEERING_VALUE_EV5.md` §4, but the code that
computes them was never built. This module computes exactly what the manifest
registers, from the pinned helpers, and nothing it does not:

- **H1** (`h1`): Δτ = τ(SR-2 candidate) − τ(deciding) on the verification
  conditions over eligible real members (`hypotheses.paired_bootstrap`), its
  three promotion conditions, else the deciding rule is confirmed;
- **H2** (`h2`): the gate's controls and the FAIL-minus-PASS loss difference
  (`hypotheses.group_difference_bootstrap`);
- **H3** (`h3`): `ev5.h3_report` plus the registered separation check;
- **adversarial score** (`adversarial`): no construction with a reference-
  verified violation in the top half under the deciding rule plus the gate;
- **construction integrity** (`construction_integrity`).

Every pre-data interpretation choice is listed, numbered, in
`.agent/tickets/EV5-RUN-01_analysis_and_confirmation.md`; comments below cite
them as "choice N". Choice 1 (Test Lead ruling): a gate FAIL ranks LAST.
`admissibility.gated` returns 0.0, which under `control-exam-v1` (−E < 0)
would rank a FAIL first, so it is never used for ranking; its literal reading
is reported only as a SENSITIVITY line (choice 2). Gate verdicts come from the
pinned `admissibility.near_optimism` and `admissibility.verdict`, unchanged.

**The run record.** `pin` writes `RUN_RECORD` before the first solve: the
freeze manifest's digest and the SHA-256 of every file under `PINNED_TREES`
(every module any command here can load, including those the freeze manifest
does not pin, such as `admissibility.py`). Every command re-hashes them first
and refuses on any difference, so nothing can drift between pin and result.

**The confirmation batch** (choice 12, OWNER-EV5-Q3-01) never leaves the
operator host. `confirm-jobs` regenerates it from the deployment's committed
root and checks it against the frozen commitment through `SeedJournal.recall`
(which never commits); the validator's pool store is never opened. The solve
runs in the pinned truth image with no network; predictions come from host CPU
rebuilds. Its report is descriptive, owner-only, and enters no verdict.

Public synthetic DEVELOPMENT evidence: no qualification, reward, chain action
or testnet-rule change.

    python -m carbon.battery.value.ev5_run pin
    python -m carbon.battery.value.ev5_run gate --experiment ROOT --out FILE
    python -m carbon.battery.value.ev5_run select --experiment ROOT
    python -m carbon.battery.value.ev5_run analyse --experiment ROOT --out DIR \
        [--pod-failures FILE ...] [--worker-boundary FILE]
    python -m carbon.battery.value.ev5_run confirm-jobs --config DEPLOYMENT --work DIR
    python -m carbon.battery.value.ev5_run confirm-solve --work DIR --overlay DIR
    python -m carbon.battery.value.ev5_run confirm-predict --work DIR
    python -m carbon.battery.value.ev5_run confirm-report --work DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np

from . import admissibility, divergence, ev5, hypotheses, real_divergence
from . import panel as pn

REPOSITORY = ev5.REPOSITORY
RUN_RECORD = f"{ev5.EVIDENCE}/run-record.json"
RECORD_SCHEMA = "carbon.battery.ev5.run-record.v1"
REPORT_SCHEMA = "carbon.battery.ev5.analysis.v1"
GATE_SCHEMA = "carbon.battery.ev5.gate.v1"
CONFIRMATION_SCHEMA = "carbon.battery.ev5.confirmation-report.v1"
TICKET = ".agent/tickets/EV5-RUN-01_analysis_and_confirmation.md"
#: Everything a command here can load: Carbon's package and the pod phases.
PINNED_TREES = ("carbon", "scripts/dev/exam_design")
DECIDING = divergence.DECIDING_RULE
CANDIDATE = "sr2-a0-r0.3-g0.6-m0.1"
SIGN_ERROR = "control-" + ev5.SIGN_ERROR_CONTROL
PROMOTE, CONFIRMED = "PROMOTE_CANDIDATE", "DECIDING_CONFIRMED"
HOLDS, NOT_HOLD, UNDEFINED = "HOLDS", "DOES_NOT_HOLD", "UNDEFINED"
PASS, FAIL, INCOMPLETE = "PASS", "FAIL", "INCOMPLETE"


class RunError(ValueError):
    def __init__(self, code, detail=None):
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code, self.detail = code, detail


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _sha256(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


# --- the run record --------------------------------------------------------------------


def tree_digests(repository=REPOSITORY, trees=PINNED_TREES):
    """SHA-256 of every file under `trees`, by repository-relative path.
    Bytecode caches are not source and are skipped."""
    root = Path(repository)
    out = {}
    for tree in trees:
        if not (root / tree).is_dir():
            continue
        for path in sorted((root / tree).rglob("*")):
            if "__pycache__" in path.parts or not path.is_file():
                continue
            out[path.relative_to(root).as_posix()] = _sha256(path.read_bytes())
    return out


def run_record(repository=REPOSITORY, trees=PINNED_TREES):
    """The record `pin` writes. It holds no private value."""
    root = Path(repository)
    manifest = json.loads((root / ev5.FREEZE_MANIFEST).read_bytes())
    return {
        "schema": RECORD_SCHEMA,
        "study": "EV5",
        "authority": ["OWNER-EV5-GO-01", "OWNER-EV5-FREEZE-01", "OWNER-EV5-CAP-01"],
        "ticket": TICKET,
        "freeze_manifest": {
            "path": ev5.FREEZE_MANIFEST,
            "sha256": _sha256((root / ev5.FREEZE_MANIFEST).read_bytes()),
        },
        "contract_digest": manifest["contract"]["digest"],
        "confirmation_commitment": manifest["confirmation"]["commitment"],
        "trees": list(trees),
        "files": tree_digests(root, trees),
        "rule": (
            "every ev5_run command re-hashes these files and refuses on any "
            "difference; written before the first EV5 solve"
        ),
        "execution": (
            "EV5 runs from a checkout of the exact approved head commit of the "
            "PR that adds this record, never from a later main; every analysis "
            "and confirmation output records that commit (git rev-parse HEAD), "
            "and the worker-boundary CI result counts only at that commit"
        ),
        "deviations": [
            {
                "item": "confirmation reference solves",
                "cost_estimate": 124,
                "planned": 120,
                "reason": (
                    "the 4 hidden duplicates test prediction consistency; they "
                    "reuse their original's reference solve, as the validator does"
                ),
                "ruling": "Test Lead, 2026-10-05, EV5-RUN-01 item 12",
            }
        ],
    }


def pin(repository=REPOSITORY, out=None):
    """Write the run record once; a second pin is refused."""
    from carbon.development_session.data import write_once

    target = Path(repository) / RUN_RECORD if out is None else Path(out)
    if target.exists():
        raise RunError("run_record_exists", str(target))
    record = run_record(repository)
    write_once(target, (json.dumps(record, indent=1, sort_keys=True) + "\n").encode())
    return {"written": str(target), "files": len(record["files"])}


def verify_pins(repository=REPOSITORY, record_path=None):
    """The run record, after checking the tree against it; refused on any
    changed, missing or added file, or a changed freeze manifest."""
    root = Path(repository)
    path = root / RUN_RECORD if record_path is None else Path(record_path)
    if not path.exists():
        raise RunError("run_record_missing", str(path))
    record = json.loads(path.read_bytes())
    if record.get("schema") != RECORD_SCHEMA:
        raise RunError("run_record_schema")
    manifest = root / record["freeze_manifest"]["path"]
    if _sha256(manifest.read_bytes()) != record["freeze_manifest"]["sha256"]:
        raise RunError("manifest_changed")
    now = tree_digests(root, tuple(record["trees"]))
    changed = sorted(p for p, d in record["files"].items() if p in now and now[p] != d)
    if changed:
        raise RunError("module_changed", ",".join(changed))
    missing = sorted(set(record["files"]) - set(now))
    if missing:
        raise RunError("module_missing", ",".join(missing))
    added = sorted(set(now) - set(record["files"]))
    if added:
        raise RunError("module_unpinned", ",".join(added))
    return record


def checkout_head(repository=REPOSITORY):
    """The commit this checkout is at, or None. EV5 runs from the exact
    approved head commit; every output records it."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


# --- shared: the gate, the candidate's scores, ranking --------------------------------


def manifest(repository=REPOSITORY):
    return json.loads((Path(repository) / ev5.FREEZE_MANIFEST).read_bytes())


def gate_verdicts(contract, predictions, controls, case_ids, refs):
    """Each member's and control's near-limit optimism and verdict at the
    pinned cutoff (`admissibility`, unchanged; choice 7: on the scoring set).
    `controls` maps a control member to its predictions."""
    out = {}
    for member, member_predictions in {**predictions, **controls}.items():
        optimism = admissibility.near_optimism(
            contract, member_predictions, case_ids, refs
        )
        out[member] = {
            "near_optimism_bands": optimism,
            "verdict": admissibility.verdict(optimism),
        }
    return out


def ranked_last(scores, verdicts):
    """Scores under a rule plus the gate (choice 1): a FAIL ranks below every
    other member, one less than the lowest numeric score; an unscored member
    stays unscored (also last). Never `admissibility.gated`'s 0.0."""
    finite = [s for s in scores.values() if _numeric(s)]
    floor = (min(finite) if finite else 0.0) - 1.0
    return {
        m: (floor if verdicts.get(m) == admissibility.FAIL else s)
        for m, s in scores.items()
    }


def literal_zero(scores, verdicts):
    """The SENSITIVITY reading (choice 2): `admissibility.gated`'s literal
    0.0 on FAIL. Reported, never entering a verdict."""
    return {
        m: (0.0 if verdicts.get(m) == admissibility.FAIL else s)
        for m, s in scores.items()
    }


def rank_in(score, pool):
    """Competition rank (1 = best) of `score` among `pool`'s numeric scores
    plus itself, and that count. None when unscored (ranked last)."""
    others = [s for s in pool if _numeric(s)]
    n = len(others) + 1
    if not _numeric(score):
        return None, n
    return 1 + sum(1 for s in others if s > score), n


def top_half(rank, n):
    """The frozen `divergence.verified_violation` cut: 2 × rank ≤ n."""
    return rank is not None and 2 * rank <= n


def candidate_rule(repository=REPOSITORY):
    """The SR-2 candidate, checked against the manifest (choice 4)."""
    rule = ev5.candidate_rule(repository)
    frozen = manifest(repository)["rules_compared"]["candidate"]
    if rule["rule"] != CANDIDATE or frozen["rule"] != CANDIDATE:
        raise RunError("candidate_rule_mismatch", rule["rule"])
    if list(rule["weights"]) != list(frozen["weights"]):
        raise RunError("candidate_weights_mismatch")
    return rule


# --- H1 ------------------------------------------------------------------------------


def h1(results, scenarios, *, bootstrap, band=None, verdicts=None):
    """H1 on `results` whose `rule_scores` carry both rules (choice 4).

    `bootstrap` is the manifest's H1 block; `band` is
    `divergence.tau_noise_band(results)`, computed when None (choice 6).
    The primary comparison is ungated (choice 5). With `verdicts`, the gated
    pair (gate failures last) is reported as a secondary line that enters no
    promotion decision (choice 5, Test Lead ruling)."""
    pool = hypotheses.eligible_real(results)
    excluded = sorted(
        m
        for m in pool
        if not (
            _numeric(results["rule_scores"][m].get(CANDIDATE))
            and _numeric(results["rule_scores"][m].get(DECIDING))
        )
    )
    members = [m for m in pool if m not in excluded]
    paired = hypotheses.paired_bootstrap(
        [results["rule_scores"][m][CANDIDATE] for m in members],
        [results["rule_scores"][m][DECIDING] for m in members],
        hypotheses.loss_matrix(results, members, scenarios),
        replicates=bootstrap["replicates"],
        seed=bootstrap["rng_seed"],
        level=bootstrap["level"],
    )
    if band is None:
        band = divergence.tau_noise_band(results)
    counts = {
        rule: real_divergence.classified(results, rule)["counts"]["verification"]
        for rule in (CANDIDATE, DECIDING)
    }
    secondary = None
    if verdicts is not None:
        status = {m: verdicts.get(m, {}).get("verdict") for m in members}
        gated = {
            rule: ranked_last(
                {m: results["rule_scores"][m][rule] for m in members}, status
            )
            for rule in (CANDIDATE, DECIDING)
        }
        secondary = {
            "rules": "both rules plus the gate, failures ranked last",
            "paired_bootstrap": hypotheses.paired_bootstrap(
                [gated[CANDIDATE][m] for m in members],
                [gated[DECIDING][m] for m in members],
                hypotheses.loss_matrix(results, members, scenarios),
                replicates=bootstrap["replicates"],
                seed=bootstrap["rng_seed"],
                level=bootstrap["level"],
            ),
            "enters_promotion": False,
        }
    low, delta = paired["interval"][0], paired["delta_tau"]
    conditions = {
        "interval_lower_bound_above_zero": low is not None and low > 0,
        "delta_tau_exceeds_noise_band": (
            delta is not None and band["band"] is not None and delta > band["band"]
        ),
        "across_family_divergence_not_higher": (
            counts[CANDIDATE]["across_families"] <= counts[DECIDING]["across_families"]
        ),
    }
    return {
        "statistic": f"tau({CANDIDATE}) - tau({DECIDING})",
        "split": "verification",
        "pool": "eligible RECONSTRUCTED members, numeric under both rules",
        "excluded_not_numeric": excluded,
        "paired_bootstrap": paired,
        "tau_noise_band": band,
        "real_divergence_verification": counts,
        "conditions": conditions,
        "outcome": PROMOTE if all(conditions.values()) else CONFIRMED,
        "secondary_gated": secondary,
    }


# --- H2 ------------------------------------------------------------------------------


def h2(results, scenarios, verdicts, *, bootstrap):
    """H2 at the pinned cutoff (choice 7). `verdicts` maps every member and
    control to its gate verdict (`gate_verdicts`)."""
    controls = {}
    for kind in ev5.GATE_MUST_FAIL:
        controls["control-" + kind] = {
            "expected": admissibility.FAIL,
            "verdict": verdicts.get("control-" + kind, {}).get("verdict"),
        }
    for kind in ev5.GATE_MUST_PASS:
        controls["control-" + kind] = {
            "expected": admissibility.PASS,
            "verdict": verdicts.get("control-" + kind, {}).get("verdict"),
        }
    controls_hold = all(c["verdict"] == c["expected"] for c in controls.values())
    real = hypotheses.eligible_real(results)
    failed = [verdicts[m]["verdict"] == admissibility.FAIL for m in real]
    group = hypotheses.group_difference_bootstrap(
        hypotheses.loss_matrix(results, real, scenarios),
        failed,
        replicates=bootstrap["replicates"],
        seed=bootstrap["rng_seed"],
        level=bootstrap["level"],
    )
    difference = group["difference"]
    if difference is None:
        real_members = UNDEFINED
    elif difference > 0 and group["excludes_zero"]:
        real_members = HOLDS
    else:
        real_members = NOT_HOLD
    if not controls_hold:
        outcome = NOT_HOLD
    else:
        outcome = real_members
    n_failed = sum(failed)
    return {
        "cutoff_bands": admissibility.THRESHOLD_BANDS,
        "controls": controls,
        "controls_hold": controls_hold,
        "real_members": len(real),
        "real_members_failed": n_failed,
        "fails_more_than_half": 2 * n_failed > len(real),
        "failed_members": sorted(m for m, f in zip(real, failed, strict=True) if f),
        "group_difference": group,
        "real_member_difference": real_members,
        "outcome": outcome,
    }


# --- H3 ------------------------------------------------------------------------------


def h3(report, results, verdicts):
    """H3 as reported (choice 8): `report` is `ev5.h3_report`'s; plus the
    separation check and the sign-error control's rank under all four rules."""

    def rate(measurement):
        return (
            None if measurement is None else measurement["worst_false_acceptance_rate"]
        )

    control = rate(report["controls"].get(SIGN_ERROR))
    real = hypotheses.eligible_real(results)
    rates = {m: rate(report["members"][m]["measurement"]) for m in real}
    unmeasured = sorted(m for m, r in rates.items() if r is None)
    measured = [r for r in rates.values() if r is not None]
    if control is None:
        separation = UNDEFINED
    else:
        separation = HOLDS if all(control > r for r in measured) else NOT_HOLD
    status = {m: verdicts.get(m, {}).get("verdict") for m in verdicts}
    ranks = {}
    for rule in (DECIDING, CANDIDATE):
        scores = {m: results["rule_scores"][m].get(rule) for m in [*real, SIGN_ERROR]}
        for label, view in (
            ("ungated", scores),
            ("gated_failures_last", ranked_last(scores, status)),
        ):
            rank, n = rank_in(view[SIGN_ERROR], [view[m] for m in real])
            ranks[f"{rule}/{label}"] = {
                "rank": rank,
                "of": n,
                "below_every_eligible_real_member": rank is None or rank == n,
            }
    return {
        "report": report,
        "sign_error_control_rate": control,
        "eligible_real_unmeasured": unmeasured,
        "separation": separation,
        "sign_error_gate": verdicts.get(SIGN_ERROR),
        "sign_error_rank": ranks,
        "caught": {
            "by_gate": verdicts.get(SIGN_ERROR, {}).get("verdict")
            == admissibility.FAIL,
            "by_rule": sorted(
                k for k, v in ranks.items() if v["below_every_eligible_real_member"]
            ),
            "by_measurement": separation == HOLDS,
        },
    }


# --- adversarial score ----------------------------------------------------------------


def adversarial(results, verdicts, findings):
    """The adversarial-score verdict (choice 10). `findings` is the optimizer
    report's {"in_band": [...], "out_of_band": [...]} Mode X findings."""
    members = results["summary"]["members"]
    real = hypotheses.eligible_real(results)
    status = {m: v["verdict"] for m, v in verdicts.items()}
    raw = {m: results["rule_scores"][m].get(DECIDING) for m in members}
    views = {
        "verdict": ranked_last(raw, status),
        "sensitivity_literal_zero": literal_zero(raw, status),
    }
    constructions = []
    for member in sorted(members):
        if members[member]["kind"] != "ATTACK_CONSTRUCTION":
            continue
        infeasible = sorted(
            s
            for s, row in results["decisions"][member].items()
            if row["outcome"]["kind"] == "SELECTED_INFEASIBLE"
        )
        if infeasible:
            constructions.append(
                {"source": "track_a", "member": member, "scenarios": infeasible}
            )
    for side in ("in_band", "out_of_band"):
        for finding in findings.get(side, []):
            constructions.append(
                {
                    "source": f"mode_x/{side}",
                    "member": finding["member"],
                    "design": finding.get("design"),
                    "operating_condition": finding.get("operating_condition"),
                    "violated": finding.get("violated"),
                }
            )
    top = {view: [] for view in views}
    for row in constructions:
        member = row["member"]
        for view, scores in views.items():
            pool = [scores[m] for m in real if m != member]
            rank, n = rank_in(scores.get(member), pool)
            row[view] = {"rank": rank, "of": n, "top_half": top_half(rank, n)}
            if row[view]["top_half"]:
                top[view].append(member)
        row["gate"] = status.get(member)
    return {
        "rule": f"{DECIDING} plus the gate, failures ranked last",
        "cut": "2 x rank <= n (divergence.verified_violation)",
        "constructions": constructions,
        "counted": {
            "track_a": sum(r["source"] == "track_a" for r in constructions),
            "mode_x_in_band": sum(
                r["source"] == "mode_x/in_band" for r in constructions
            ),
            "mode_x_out_of_band": sum(
                r["source"] == "mode_x/out_of_band" for r in constructions
            ),
        },
        "in_top_half": sorted(set(top["verdict"])),
        "sensitivity_literal_zero": {
            "in_top_half": sorted(set(top["sensitivity_literal_zero"])),
            "enters_verdict": False,
            "ruling": "Test Lead 2026-10-05, interpretation choice 2",
        },
        "verdict": FAIL if top["verdict"] else PASS,
    }


# --- construction integrity -----------------------------------------------------------


def construction_integrity(
    track_a_report, refused, frozen, bundles, failures, scan, head=None
):
    """The construction-integrity verdict (choice 11).

    - `track_a_report`: `track_a.run`'s report;
    - `refused`: `panel.attack_constructions()["refused"]`, recomputed now;
    - `frozen`: the manifest's `panel.attack_constructions`;
    - `bundles`: member → (recipe digest, seed) matched (True), mismatched
      (False) or absent (None), for every panel member;
    - `failures`: member → typed pod failure record, for absent members;
    - `scan`: the worker-boundary CI result, or None: {"test", "run_id",
      "head_sha", "conclusion"};
    - `head`: the commit this analysis runs from. The scan counts only when
      it ran at exactly that commit (choice 11); otherwise INCOMPLETE.
    """
    families = track_a_report["families"]
    breaches = list(track_a_report["findings"])
    not_held = sorted(f for f, state in families.items() if state != "IN_PROGRESS")
    # The panel returns a tuple; the manifest holds a JSON list.
    refusals_match = list(refused) == list(frozen["refused"])
    mismatched = sorted(m for m, ok in bundles.items() if ok is False)
    absent = sorted(m for m, ok in bundles.items() if ok is None)
    untyped = sorted(m for m in absent if not (failures.get(m) or {}).get("failure"))
    if (
        scan is None
        or not scan.get("run_id")
        or head is None
        or scan.get("head_sha") != head
    ):
        scan_state = INCOMPLETE
    elif scan.get("conclusion") == "success":
        scan_state = PASS
    else:
        scan_state = FAIL
    failed = bool(breaches or not_held or not refusals_match or mismatched or untyped)
    if failed or scan_state == FAIL:
        verdict = FAIL
    elif scan_state == INCOMPLETE:
        verdict = INCOMPLETE
    else:
        verdict = PASS
    return {
        "families": families,
        "findings": breaches,
        "families_not_in_progress": not_held,
        "refusals_match_freeze": refusals_match,
        "rebuilds_matched": sum(1 for ok in bundles.values() if ok is True),
        "rebuilds_mismatched": mismatched,
        "rebuilds_refused_typed": sorted(set(absent) - set(untyped)),
        "rebuilds_missing_untyped": untyped,
        "worker_boundary_scan": {
            "state": scan_state,
            "evidence": scan,
            "required_head": head,
        },
        "verdict": verdict,
    }


# --- host IO: experiment, predictions, analysis ---------------------------------------


def _experiment(root):
    from . import contract as ev
    from .experiment import Experiment

    experiment = Experiment(root, repository=REPOSITORY)
    contract = experiment.contract()
    if ev.digest(contract) != manifest()["contract"]["digest"]:
        raise RunError("contract_mismatch")
    return experiment, contract


def _results(experiment):
    path = experiment.root / "results" / "results.json"
    if not path.exists():
        raise RunError("not_evaluated", "run `python -m carbon.battery.value evaluate`")
    return json.loads(path.read_bytes())


def _predictions(experiment, members):
    out = {}
    for member in members:
        bundle = experiment._member_predictions(member)
        out[member] = {} if bundle is None else bundle["predictions"]
    return out


def scored(experiment, contract, results):
    """`results` with the SR-2 candidate's scores (choice 4), the gate
    verdicts for every member and control, and the members' predictions."""
    from . import margins
    from . import scoring as sc

    candidate_rule()
    members = results["summary"]["members"]
    real_and_attacks = sorted(
        m for m, row in members.items() if row["kind"] != "SYNTHETIC_CONTROL"
    )
    predictions = _predictions(experiment, real_and_attacks)
    out = margins.with_margins(results, contract, predictions, REPOSITORY)
    store, case_ids, _ = sc.scoring_set(REPOSITORY)
    controls = {
        "control-" + kind: pn.control_predictions(kind, store.refs)
        for kind in pn.CONTROLS
    }
    verdicts = gate_verdicts(contract, predictions, controls, case_ids, store.refs)
    return out, verdicts, predictions


def gate(experiment_root, out):
    """Write the gate verdicts and candidate scores the optimizer's selection
    needs (both are public: scoring-set measurements)."""
    from carbon.development_session.data import write_once

    experiment, contract = _experiment(experiment_root)
    results = _results(experiment)
    out_results, verdicts, _ = scored(experiment, contract, results)
    document = {
        "schema": GATE_SCHEMA,
        "contract_digest": manifest()["contract"]["digest"],
        "results_sha256": _sha256(
            (experiment.root / "results" / "results.json").read_bytes()
        ),
        "cutoff_bands": admissibility.THRESHOLD_BANDS,
        "verdicts": verdicts,
        "candidate_scores": {
            m: out_results["rule_scores"][m].get(CANDIDATE)
            for m in out_results["rule_scores"]
        },
    }
    write_once(
        Path(out), (json.dumps(document, indent=1, sort_keys=True) + "\n").encode()
    )
    return document


def select(experiment_root):
    """EV5's optimizer selection: `best_proposed` from the members the gate
    passes, under the SR-2 candidate (OWNER-EV5-Q2-01)."""
    from . import optimizer as op

    experiment, contract = _experiment(experiment_root)
    results = _results(experiment)
    out_results, verdicts, _ = scored(experiment, contract, results)
    scores = {
        CANDIDATE: {
            m: out_results["rule_scores"][m].get(CANDIDATE)
            for m in out_results["rule_scores"]
        }
    }
    admissible = {m for m, v in verdicts.items() if v["verdict"] == admissibility.PASS}
    with experiment.lock():
        selection = op.run_select(experiment, scores=scores, admissible=admissible)
    return {
        "members": selection["members"],
        "mode_d_solves": selection["mode_d_solves"],
        "mode_x_solves": selection["mode_x_solves"],
        "jobs": len(selection["jobs"]),
        "jobs_file": str(experiment.root / "optimizer" / "jobs.json"),
    }


def _bundle_matches(experiment):
    from ..compile import compile_recipe

    out = {}
    for member, _label, strategy, seed in experiment._members():
        bundle = experiment._member_predictions(member)
        if bundle is None:
            out[member] = None
            continue
        _, recipe = compile_recipe(strategy)
        out[member] = (bundle.get("recipe_digest"), bundle.get("seed")) == (
            recipe.recipe_digest,
            seed,
        )
    return out


def _pod_failures(paths):
    out = {}
    for path in paths or ():
        for line in Path(path).read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                if record.get("candidate"):
                    out[record["member"]] = record
    return out


def analyse(experiment_root, out_dir, *, pod_failures=(), worker_boundary=None):
    """Every EV5 hypothesis and the three verdicts, never blended."""
    from carbon.battery import track_a

    from . import contract as ev

    frozen = manifest()
    head = checkout_head()
    experiment, contract = _experiment(experiment_root)
    results = _results(experiment)
    out_results, verdicts, predictions = scored(experiment, contract, results)
    scenarios = hypotheses.verification_scenarios(contract)
    optimizer_results = experiment.root / "optimizer" / "results.json"
    if not optimizer_results.exists():
        raise RunError("optimizer_not_reported", str(optimizer_results))
    findings = json.loads(optimizer_results.read_bytes())["findings"]
    kinds = {m: row["kind"] for m, row in results["summary"]["members"].items()}
    h3_input = ev5.h3_report(contract, predictions, kinds, REPOSITORY)
    _records, track_report, _divergence = track_a.run(REPOSITORY)
    scan = (
        None
        if worker_boundary is None
        else json.loads(Path(worker_boundary).read_bytes())
    )
    report = {
        "schema": REPORT_SCHEMA,
        "study": "EV5",
        "contract_digest": ev.digest(contract),
        "results_sha256": _sha256(
            (experiment.root / "results" / "results.json").read_bytes()
        ),
        "optimizer_results_sha256": _sha256(optimizer_results.read_bytes()),
        "interpretation": TICKET,
        "checkout_head": head,
        "gate": {"cutoff_bands": admissibility.THRESHOLD_BANDS, "members": verdicts},
        "value": {
            "H1": h1(
                out_results,
                scenarios,
                bootstrap=frozen["hypotheses"]["H1"]["bootstrap"],
                verdicts=verdicts,
            ),
            "H2": h2(
                out_results,
                scenarios,
                verdicts,
                bootstrap=frozen["hypotheses"]["H2"]["bootstrap"],
            ),
            "H3": h3(h3_input, out_results, verdicts),
            "graded": False,
            "rung": "the owner's signed lock decides the rung (OWNER-TRACK-A-L0-02)",
        },
        "adversarial_score": adversarial(out_results, verdicts, findings),
        "construction_integrity": construction_integrity(
            track_report,
            pn.attack_constructions()["refused"],
            frozen["panel"]["attack_constructions"],
            _bundle_matches(experiment),
            _pod_failures(pod_failures),
            scan,
            head,
        ),
        "blended": False,
        "claims": frozen["claims"],
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n"
    )
    return {
        "H1": report["value"]["H1"]["outcome"],
        "H2": report["value"]["H2"]["outcome"],
        "H3_separation": report["value"]["H3"]["separation"],
        "adversarial_score": report["adversarial_score"]["verdict"],
        "construction_integrity": report["construction_integrity"]["verdict"],
    }


# --- the sealed confirmation batch (operator host only) --------------------------------


def _owner_only_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise RunError("work_not_owner_only", str(path))
    return path


def _write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")


def _read_private(path):
    path = Path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise RunError("private_file_not_owner_only", path.name)
    return json.loads(path.read_bytes())


def recall_confirmation(root, pin_value, journal, commitment):
    """The sealed batch, regenerated and recalled (choice 12). Refused unless
    it is exactly the frozen commitment: fingerprint and journal sequence.
    `SeedJournal.recall` never commits."""
    from carbon.battery import seeds

    skeleton = ev5.confirmation()
    batch = seeds.make_batch(
        root,
        pin_value,
        ev5.CONFIRMATION_ROLE,
        skeleton["batch_size"],
        skeleton["hidden_duplicates"],
    )
    if batch.fingerprint != commitment["fingerprint"]:
        raise RunError("confirmation_fingerprint_mismatch")
    committed = journal.recall(batch)
    if committed.sequence != commitment["journal_sequence"]:
        raise RunError("confirmation_sequence_mismatch")
    return committed


def confirm_jobs(config_path, work):
    """Write the batch (owner-only) and its distinct solve jobs. Reads the
    deployment's root and journal only; the pool store is never opened."""
    from carbon.battery import deployment, seeds

    config = deployment.load_config(config_path)
    root = seeds.PrivateRoot.load(deployment._private(config["private_root"]))
    journal = seeds.SeedJournal(config["journal"])
    committed = recall_confirmation(
        root,
        journal.root_pin(root),
        journal,
        manifest()["confirmation"]["commitment"],
    )
    work = _owner_only_dir(work)
    document = committed.batch.document()
    duplicates = set(document["duplicates"])
    jobs = [
        {"case_id": c["case_id"], **c["inputs"]}
        for c in document["cases"]
        if c["case_id"] not in duplicates
    ]
    _write_private(work / "batch.json", document)
    _write_private(
        work / "jobs.json", {"fingerprint": committed.fingerprint, "jobs": jobs}
    )
    return {
        "fingerprint": committed.fingerprint,
        "journal_sequence": committed.sequence,
        "cases": len(document["cases"]),
        "distinct_solves": len(jobs),
    }


def confirm_solve(work, overlay, *, workers=7, timeout_s=1200.0, runner=None):
    """Solve the jobs in the pinned truth image (no network, read-only
    source). Resumable; FAILED_INFRA is retried."""
    import subprocess

    from carbon.battery import truth_env

    work = _owner_only_dir(work)
    if not (work / "records.jsonl").exists():
        (work / "records.jsonl").touch(mode=0o600)
    command = truth_env.solve_command(
        overlay, work, repository=REPOSITORY, workers=workers, timeout_s=timeout_s
    )
    completed = (runner or subprocess.run)(command, check=False)
    return {"returncode": completed.returncode}


def _confirmation_refs(work):
    """Each case's reference record; a hidden duplicate reuses its
    original's solve, as the validator does."""
    batch = _read_private(Path(work) / "batch.json")
    records = {}
    path = Path(work) / "records.jsonl"
    for line in path.read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            if record.get("status") != "FAILED_INFRA":
                records[record["case_id"]] = record
    refs = {}
    for case in batch["cases"]:
        source = batch["duplicates"].get(case["case_id"], case["case_id"])
        if source in records:
            refs[case["case_id"]] = {**records[source], "case_id": case["case_id"]}
    return batch, refs


def confirm_predict(work, *, backend=None):
    """Rebuild every panel member on this host's CPU and predict the batch's
    inputs; owner-only bundles. Resumable."""
    from .experiment import member_bundle

    work = _owner_only_dir(work)
    batch = _read_private(work / "batch.json")
    inputs = {c["case_id"]: dict(c["inputs"]) for c in batch["cases"]}
    if backend is None:
        from carbon.battery.worker import DirectBackend

        backend = DirectBackend(str(REPOSITORY))
    out = _owner_only_dir(work / "predictions")
    done = failed = 0
    for member, _label, strategy, seed in pn.members("ev5"):
        path = out / f"{member}.json"
        if path.exists():
            continue
        try:
            bundle, _state = member_bundle(backend, member, strategy, seed, inputs)
        except Exception as failure:  # noqa: BLE001 - typed, recorded
            _write_private(
                out / f"{member}.failure.json",
                {"member": member, "failure": type(failure).__name__},
            )
            failed += 1
            continue
        _write_private(path, bundle)
        done += 1
    return {"rebuilt": done, "failed": failed}


def confirmation_report(contract, batch, refs, predictions, kinds, verdict_of):
    """The descriptive confirmation report (choice 12): per member, the exam
    components and deciding-rule score on the batch, gate optimism and
    near-limit false acceptance on its important region, and the adversarial
    check repeated on these scores. No case id, input or output."""
    from carbon.battery import exam, seeds

    from ..calibration import SHAPES, frozen_calibration
    from ..challenge import PublicMaterial
    from . import false_acceptance as fa
    from . import scoring as sc
    from .near import near_cases

    material = PublicMaterial.load(REPOSITORY)
    ocv = {
        c: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for c, r in refs.items()
        if r.get("inputs")
    }
    tol, scales = frozen_calibration(REPOSITORY)
    store = exam.CaseStore(refs, ocv, tol, scales, SHAPES, dict(batch["duplicates"]))
    ids = sorted(refs)
    important = near_cases(store, ids)
    members = dict(predictions)
    for kind in pn.CONTROLS:
        members["control-" + kind] = pn.control_predictions(kind, store.refs)
        kinds = {**kinds, "control-" + kind: "SYNTHETIC_CONTROL"}
    rows = {}
    for member, member_predictions in sorted(members.items()):
        component = sc.components(member_predictions, ids, store)
        optimism = admissibility.near_optimism(
            contract, member_predictions, ids, store.refs
        )
        rows[member] = {
            "kind": kinds.get(member, "RECONSTRUCTED"),
            "eligible": component["eligible"],
            "gate_failures": component["gate_failures"],
            "E": component["E"],
            "E_important": component["E_important"],
            DECIDING: sc.rule_scores(contract, component)[DECIDING],
            "near_optimism_bands": optimism,
            "gate_on_batch": admissibility.verdict(optimism),
            "near_false_acceptance": fa.component(
                contract, member_predictions, important, store.refs
            ),
        }
    eligible_real = [
        m for m, r in rows.items() if r["kind"] == "RECONSTRUCTED" and r["eligible"]
    ]
    status = {m: verdict_of.get(m) for m in rows}
    view = ranked_last({m: r[DECIDING] for m, r in rows.items()}, status)
    attacks = {}
    for member, row in rows.items():
        if row["kind"] == "ATTACK_CONSTRUCTION":
            rank, n = rank_in(
                view[member], [view[m] for m in eligible_real if m != member]
            )
            attacks[member] = {"rank": rank, "of": n, "top_half": top_half(rank, n)}
    return {
        "schema": CONFIRMATION_SCHEMA,
        "batch_fingerprint": seeds.PrivateBatch.from_document(batch).fingerprint,
        "cases": len(batch["cases"]),
        "cases_with_reference": len(refs),
        "important_region_cases": len(important),
        "members": rows,
        "attack_constructions_under_deciding_plus_gate": attacks,
        "rebuilds": "host CPU (DirectBackend); not bit-identical to the A40 panel",
        "checkout_head": checkout_head(),
        "state": "DESCRIPTIVE",
        "enters_verdict": False,
        "publication": "held: owner-only until the Test Lead and owner rule (choice 12)",
    }


def confirm_report(work, gate_file):
    """Write the owner-only confirmation report. `gate_file` is `gate`'s
    output (the scoring-set gate verdicts that rank failures last)."""
    from . import contract as ev

    work = _owner_only_dir(work)
    contract, _ = ev.load(REPOSITORY / ev5.CONTRACT)
    batch, refs = _confirmation_refs(work)
    predictions, kinds = {}, pn.kinds("ev5")
    for member, *_ in pn.members("ev5"):
        path = work / "predictions" / f"{member}.json"
        if path.exists():
            predictions[member] = _read_private(path)["predictions"]
    gate_document = json.loads(Path(gate_file).read_bytes())
    verdict_of = {m: v["verdict"] for m, v in gate_document["verdicts"].items()}
    report = confirmation_report(contract, batch, refs, predictions, kinds, verdict_of)
    _write_private(work / "confirmation-report.json", report)
    return {
        "members": len(report["members"]),
        "cases_with_reference": report["cases_with_reference"],
        "attack_constructions_in_top_half": sorted(
            m
            for m, r in report["attack_constructions_under_deciding_plus_gate"].items()
            if r["top_half"]
        ),
    }


# --- CLI -------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value.ev5_run")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pin", help="Write the run record, once, before the first solve")
    sub.add_parser("verify", help="Check the tree against the run record")
    gate_p = sub.add_parser("gate", help="Gate verdicts and candidate scores")
    gate_p.add_argument("--experiment", required=True)
    gate_p.add_argument("--out", required=True)
    select_p = sub.add_parser("select", help="EV5's optimizer selection")
    select_p.add_argument("--experiment", required=True)
    analyse_p = sub.add_parser("analyse", help="H1-H3 and the three verdicts")
    analyse_p.add_argument("--experiment", required=True)
    analyse_p.add_argument("--out", required=True)
    analyse_p.add_argument("--pod-failures", nargs="*", default=())
    analyse_p.add_argument("--worker-boundary")
    jobs_p = sub.add_parser("confirm-jobs", help="Recall the sealed batch (host)")
    jobs_p.add_argument("--config", required=True)
    jobs_p.add_argument("--work", required=True)
    solve_p = sub.add_parser("confirm-solve", help="Solve it in the truth image")
    solve_p.add_argument("--work", required=True)
    solve_p.add_argument("--overlay", required=True)
    solve_p.add_argument("--workers", type=int, default=7)
    predict_p = sub.add_parser("confirm-predict", help="Host CPU rebuilds")
    predict_p.add_argument("--work", required=True)
    report_p = sub.add_parser("confirm-report", help="Owner-only report")
    report_p.add_argument("--work", required=True)
    report_p.add_argument("--gate", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "pin":
            result = pin()
        else:
            record = verify_pins()
            if args.command == "verify":
                result = {"verified_files": len(record["files"])}
            elif args.command == "gate":
                document = gate(args.experiment, args.out)
                result = {
                    "fails": sorted(
                        m
                        for m, v in document["verdicts"].items()
                        if v["verdict"] == admissibility.FAIL
                    )
                }
            elif args.command == "select":
                result = select(args.experiment)
            elif args.command == "analyse":
                result = analyse(
                    args.experiment,
                    args.out,
                    pod_failures=args.pod_failures,
                    worker_boundary=args.worker_boundary,
                )
            elif args.command == "confirm-jobs":
                result = confirm_jobs(args.config, args.work)
            elif args.command == "confirm-solve":
                result = confirm_solve(args.work, args.overlay, workers=args.workers)
            elif args.command == "confirm-predict":
                result = confirm_predict(args.work)
            else:
                result = confirm_report(args.work, args.gate)
            verify_pins()
    except RunError as refused:
        print(json.dumps({"refused": refused.code, "detail": refused.detail}))
        return 2
    print(json.dumps(result, indent=1, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
