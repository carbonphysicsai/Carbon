"""Scripted pre-mainnet attacks on grading, gaming, feedback leaks and disclosure (OWNER "Start whatever we can now";
MAINNET_PREP item 5; areas G1, G4, G5 and G6 of POST_LAUNCH_TESTNET_TEST_PLAN_20261024).

Everything here runs offline against the checked-out build's own code (the KOTH comparator, the Ladder feedback, the
public king document, the submission cap). No network, no chain, no key, no sealed exam, no live effect. Every
number a simulation needs is a labelled SYNTHETIC parameter: nothing here sets or measures a production value, and
a verdict never says a Challenge is qualified.

    python -m scripts.dev.mainnet_attack_tests --markdown out.md --json out.json
    python -m scripts.dev.mainnet_attack_tests --scan DIR --sentinel TEXT      # G6 against a live run's captures

Verdicts: PASS (the expected protection held), FAIL (an attack succeeded), RISK (a quantified exposure the owner
has accepted or must decide; not a defect in the code under test), INFO (a recorded measurement).
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import random
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from carbon.battery.pool_store import StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import exam_cap, koth_public
from carbon.challenge_validator.interface import digest
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import grade_feedback as gf

SYNTHETIC = (
    "SYNTHETIC (an attack-simulation parameter, not a registered or measured value)"
)
REFUSALS = (ValueError, TypeError, KeyError, StateError)
CHALLENGE = "electric-motor-magnetics"
PACK = digest("attack score pack")
BASELINE_ENTRY = digest("attack baseline entry")
KEY = digest("attack evaluation key")
GATES = ("native_motor_valid", "complete_fixed_coverage")
SS58_A = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
SS58_B = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


@dataclass
class Result:
    id: str
    area: str
    title: str
    expected: str
    observed: str
    verdict: str
    detail: dict = field(default_factory=dict)


def _body(model, *, status=bp.SCORED, total=1.0, entry=None, extra=None):
    model_p = {"score_status": status, "total_score": total}
    model_p.update(extra or {})
    return {
        "submission_id": model,
        "evidence": {
            "schema": bp.PAIRED_BINDING,
            "challenge": CHALLENGE,
            "score_compatibility": {"score_pack_digest": PACK},
            "entry_id": digest(["entry", model]) if entry is None else entry,
            "model_p": model_p,
        },
    }


def _pair(candidate, incumbent):
    return {
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "evaluation_key": KEY,
        "expected_incumbent": None if incumbent is None else incumbent["submission_id"],
        "candidate": candidate,
        "incumbent": incumbent,
    }


def _rule(noise, baseline=0.5, **changes):
    rule = {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": CHALLENGE,
        "score_pack_digest": PACK,
        "rebuild_noise": (
            None
            if noise is None
            else {"value": noise, "measurement_digest": digest("attack noise record")}
        ),
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": [BASELINE_ENTRY],
        "baseline_total": baseline,
    }
    rule.update(changes)
    return rule


def _decide(candidate_total, king_total, noise, **kw):
    return bp.compare_private_pair(
        _pair(_body("c", total=candidate_total, **kw), _body("k", total=king_total)),
        _rule(noise),
    )["outcome"]


# ----------------------------------------------------------------------------------------------- G1 copying


def g1_copy_never_wins(rng, rounds):
    """An exact copy of the king, and any candidate within the registered margin, never takes the crown."""
    crowned = []
    for _ in range(rounds):
        held = rng.uniform(
            0.05, 0.85
        )  # king + margin stays inside 0..1 (rc42 refuses a total above 1)
        noise = rng.choice([0.005, 0.01, 0.02, 0.05, 0.1])
        # exact copy, and a spread of totals up to and including the margin edge
        for total in (
            held,
            held + noise * rng.random(),
            held + noise,
            held - noise * rng.random(),
        ):
            total = min(1.0, max(0.0, total))  # a total is 0..1 (rc42 refuses others)
            if _decide(total, held, noise) == bp.CHALLENGER:
                crowned.append((held, noise, total))
    return Result(
        "G1a",
        "G1 copying",
        "A copy of the king (equal total) and every total up to king + margin never crowns",
        f"0 crowns in {rounds} x 4 draws",
        f"{len(crowned)} crowns",
        "PASS" if not crowned else "FAIL",
        {"first_failures": crowned[:3]},
    )


def g1_margin_edge(rng):
    """The edge is strict: exactly king + margin keeps the king, the next float above takes it."""
    held, noise = 0.5, 0.0625  # binary-exact so the sum is exact
    at = _decide(held + noise, held, noise)
    above = _decide(math.nextafter(held + noise, 1.0), held, noise)
    return Result(
        "G1b",
        "G1 copying",
        "Strict margin edge (tie keeps the king; one ulp above takes it)",
        "INCUMBENT_KEEPS at the edge, CHALLENGER one ulp above",
        f"{at} at the edge, {above} one ulp above",
        "PASS" if (at, above) == (bp.INCUMBENT_KEEPS, bp.CHALLENGER) else "FAIL",
    )


def g1_baseline_entry_copy():
    """Submitting the baseline run that set the leg minimums never contends."""
    rows = []
    for incumbent in (None, _body("k", total=0.4)):
        candidate = _body("c", total=0.99, entry=BASELINE_ENTRY)
        rows.append(
            bp.compare_private_pair(_pair(candidate, incumbent), _rule(0.05))["outcome"]
        )
    ok = rows == [bp.NO_WINNER, bp.INCUMBENT_KEEPS]
    return Result(
        "G1c",
        "G1 copying",
        "A copy of Carbon's baseline entry (the leg-minimum source) is never a contender",
        "NO_WINNER with no king, INCUMBENT_KEEPS with one",
        ", ".join(rows),
        "PASS" if ok else "FAIL",
    )


def g1_replay_and_cross_hotkey(tmp):
    """Replaying one submission reuses its slot; the same recipe from another hotkey is a new graded
    submission (it spends a slot) but can at most tie."""
    cap = exam_cap.ExamCap(_ledger(tmp, "g1"), cadence=_cadence())
    args = {
        "challenge_id": "chip-cold-plate",
        "challenge_version": "1.0",
        "exam_key": digest("exam"),
        "block": 36_000,
    }
    first = cap.reserve(hotkey=SS58_A, submission_id="sha256:a", **args)
    again = cap.reserve(hotkey=SS58_A, submission_id="sha256:a", **args)
    other = cap.reserve(hotkey=SS58_B, submission_id="sha256:b", **args)
    tie = _decide(0.7, 0.7, 0.02)
    ok = first == again and other != first and tie == bp.INCUMBENT_KEEPS
    return Result(
        "G1d",
        "G1 copying",
        "Replay reuses its slot; the same recipe from a second hotkey spends its own slot and only ties",
        "same reservation id on replay; distinct id for the second hotkey; INCUMBENT_KEEPS on the tie",
        f"replay_same_slot={first == again}, second_hotkey_new_slot={other != first}, tie={tie}",
        "PASS" if ok else "FAIL",
        {
            "note": "a copied recipe costs the validator one rebuild per hotkey (see G4b), never a crown"
        },
    )


def g1_public_numbers_do_not_overpromise(rng, rounds):
    """The public `to_beat` is built from the king's Ladder-stepped (rounded-down) total, so it can only
    under-state the real threshold: a miner who submits at the shown number may fall short, never win by it.
    """
    worst_gap, over = 0.0, 0
    step = 0.02
    for _ in range(rounds):
        true_total = rng.uniform(0.05, 0.95)
        noise = rng.choice([0.0, 0.005, 0.01, 0.03])  # 0 means no margin shown
        noise_rec = None if noise == 0 else {"value": noise, "measurement_digest": KEY}
        doc = koth_public.document(
            challenge_id=CHALLENGE,
            challenge_version="1.0",
            exam_version_label="exam-1",
            king={"hotkey": SS58_A, "total": true_total, "since_epoch": 3},
            rebuild_noise=noise_rec,
            baseline_total=None,
        )
        if doc["to_beat"] is None:
            continue
        real = true_total + noise
        if doc["to_beat"] > real + 1e-12:
            over += 1
        worst_gap = max(worst_gap, real - doc["to_beat"])
    return Result(
        "G1e",
        "G1 copying",
        "The public king document never over-promises the threshold (to_beat <= king + margin)",
        "0 over-promises; shortfall below one Ladder step",
        f"{over} over-promises; largest shortfall {worst_gap:.4f} (step {step})",
        "PASS" if over == 0 and worst_gap < max(step, 0.03) + 1e-9 else "FAIL",
    )


# --------------------------------------------------------------------------------- comparator hostile input


def hostile_comparator_inputs():
    """Malformed or spoofed evidence reaching the KOTH comparator never crowns."""
    cases = {
        "nan total": _body("c", total=float("nan")),
        "inf total": _body("c", total=float("inf")),
        "bool total": _body("c", total=True),
        "string total": _body("c", total="0.99"),
        "unknown status carrying a huge total": _body(
            "c", status="SCORED_OFFICIAL", total=9.0
        ),
        "infra status": _body("c", status="FAILED_INFRA", total=0.99),
        "indeterminate status": _body("c", status="INDETERMINATE_EVIDENCE", total=0.99),
    }
    refused, crowned = [], []
    for name, candidate in cases.items():
        try:
            outcome = bp.compare_private_pair(
                _pair(candidate, _body("k", total=0.4)), _rule(0.05)
            )["outcome"]
        except REFUSALS as error:  # a typed refusal is the expected path
            refused.append(f"{name}: {type(error).__name__}")
            continue
        if outcome in (bp.CHALLENGER, bp.FIRST_INCUMBENT):
            crowned.append(f"{name}: {outcome}")
        else:
            refused.append(f"{name}: {outcome}")
    spoofed = []
    for label, change in (
        ("other Challenge", {"challenge": "chip-cold-plate"}),
        ("other score pack", {"score_pack_digest": digest("other pack")}),
        ("official scope", {"scope": "OFFICIAL"}),
        ("practice-scope document", {"scope": "PUBLIC_PRACTICE_FEEDBACK"}),
    ):
        rule = _rule(0.05)
        candidate = _body("c", total=0.99)
        if "challenge" in change:
            # only the evidence names another Challenge; the rule stays the registered one
            candidate["evidence"]["challenge"] = change["challenge"]
        else:
            rule.update(change)
        try:
            outcome = bp.compare_private_pair(
                _pair(candidate, _body("k", total=0.4)), rule
            )["outcome"]
            spoofed.append(f"{label}: {outcome}")
            if outcome in (bp.CHALLENGER, bp.FIRST_INCUMBENT):
                crowned.append(f"{label}: {outcome}")
        except REFUSALS as error:
            spoofed.append(f"{label}: refused {type(error).__name__}")
    return Result(
        "G1f",
        "G1 copying",
        "Hostile or spoofed evidence (NaN/inf/bool/string totals, unscored statuses, wrong Challenge or pack, "
        "unadopted scope) never crowns",
        "0 crowns; every case refused or not-won",
        f"{len(crowned)} crowns",
        "PASS" if not crowned else "FAIL",
        {"cases": refused + spoofed, "crowned": crowned},
    )


def noise_unregistered_never_crowns():
    """On a build where a Challenge has no registered rebuild noise (the committed registry is empty today), no
    pair can crown: UNAVAILABLE, never zero."""
    outcomes = {
        _decide(0.99, 0.2, None),
        bp.compare_private_pair(_pair(_body("c", total=0.99), None), _rule(None))[
            "outcome"
        ],
    }
    return Result(
        "K0",
        "G1 copying",
        "No registered rebuild noise: no crown can be taken",
        "UNAVAILABLE only",
        ", ".join(sorted(outcomes)),
        "PASS" if outcomes == {bp.UNAVAILABLE} else "FAIL",
        {
            "committed_registry": json.loads(
                (Path(bp.__file__).with_name("koth_rebuild_noise.json")).read_text()
            )["challenges"],
            "note": "while the committed registry is empty the testnet cannot crown anyone; K1-K5 need it registered",
        },
    )


def out_of_range_total_reaches_comparator():
    """The comparator does not range-check a total: a total above 1 would crown. Upstream scoring bounds legs to
    0..1 (dual_score), so this is a defence-in-depth gap, not a reachable attack on its own.
    """
    try:
        outcome = _decide(5.0, 0.4, 0.05)
    except (
        REFUSALS
    ) as error:  # rc42+: the comparator refuses it (private_evaluation_invalid)
        outcome = f"refused: {error}"
    return Result(
        "G1g",
        "G1 copying",
        "A total outside 0..1 handed to the comparator",
        "refused (the 0..1 check, rc42 onward)",
        outcome,
        "RISK" if outcome == bp.CHALLENGER else "PASS",
        {
            "meaning": "compare_private_pair trusts model_p.total_score; dual_score bounds the legs, and koth_public refuses "
            "a king total outside 0..1, so only a bug upstream could deliver one. Suggest a 0..1 check beside the finite check."
        },
    )


# ------------------------------------------------------------------------------------------ G4 multi-hotkey


def _cadence():
    return {
        "capacity_cpu_hours_per_day": 134.4,
        "rebuild_cpu_hours_placeholder": {
            "battery-fastcharge-ageing-development-v1": 2.0,
            "chip-cold-plate": 1.0,
            CHALLENGE: 1.0,
            "f02": 0.2,
            "f08-ribbed-bracket": 0.5,
        },
    }


def _ledger(tmp, name):
    directory = Path(tmp) / name
    directory.mkdir(mode=0o700, exist_ok=True)
    return AttemptLedger(directory / "attempts.sqlite3")


def _hotkey(index):
    return f"5{index:046d}"[:48]


def _day_of_attempts(tmp, name, operator_keys, honest, challenge="chip-cold-plate"):
    """One rolling day on the real cap: every hotkey tries once per epoch for 20 epochs."""
    cap = exam_cap.ExamCap(_ledger(tmp, name), cadence=_cadence())
    keys = [("operator", _hotkey(i)) for i in range(operator_keys)] + [
        ("honest", _hotkey(1000 + i)) for i in range(honest)
    ]
    granted = {"operator": 0, "honest": 0}
    for epoch in range(100, 120):
        for who, key in keys:
            try:
                cap.reserve(
                    hotkey=key,
                    challenge_id=challenge,
                    challenge_version="1.0",
                    exam_key=digest("exam"),
                    submission_id=f"sha256:{key}-{epoch}",
                    block=epoch * exam_cap.EPOCH_BLOCKS,
                )
                granted[who] += 1
            except exam_cap.ExamCapRefused:
                pass
    return granted


def g4_extra_capacity_and_sybil_floor(tmp):
    """What a second (third...) registration buys, on the real cap with the committed cadence (R=134.4 CPU-h/day,
    placeholder sum 4.7). Also where the formula stops protecting capacity."""
    rows = []
    for honest in (0, 10):
        for k in (1, 2, 5):
            granted = _day_of_attempts(tmp, f"g4-{honest}-{k}", k, honest)
            total = granted["operator"] + granted["honest"]
            rows.append(
                {
                    "honest_hotkeys": honest,
                    "operator_hotkeys": k,
                    "operator_slots_per_day": granted["operator"],
                    "operator_slots_per_hotkey": granted["operator"] / k,
                    "honest_slots_per_hotkey": (
                        (granted["honest"] / honest) if honest else None
                    ),
                    "operator_share_of_slots": granted["operator"] / total,
                }
            )
    capacity, per = 134.4, 4.7
    floor_at = capacity / per
    gain2 = next(
        r for r in rows if r["honest_hotkeys"] == 0 and r["operator_hotkeys"] == 2
    )
    busy1, busy2, busy5 = (
        next(
            r for r in rows if r["honest_hotkeys"] == 10 and r["operator_hotkeys"] == k
        )
        for k in (1, 2, 5)
    )
    gain1 = next(
        r for r in rows if r["honest_hotkeys"] == 0 and r["operator_hotkeys"] == 1
    )
    return Result(
        "G4a",
        "G4 multi-hotkey",
        "Grading capacity a second registration buys (the number for the owner's economics)",
        "recorded, not a pass/fail",
        f"alone: 1 hotkey {gain1['operator_slots_per_day']} slots/day (the one-per-epoch limit), 2 hotkeys "
        f"{gain2['operator_slots_per_day']}; among 10 honest hotkeys: 1 hotkey {busy1['operator_share_of_slots']:.0%} of all slots, "
        f"2 hotkeys {busy2['operator_share_of_slots']:.0%}, 5 hotkeys {busy5['operator_share_of_slots']:.0%} (each hotkey's own allowance "
        f"shrinks as active hotkeys grow, but the operator's share grows with its hotkeys)",
        "INFO",
        {
            "rows": rows,
            "formula": "allowance a = max(1, floor(R / (M * sum_t))), R=134.4 CPU-h/day, sum_t=4.7 (placeholders)",
            "allowance_reaches_the_floor_of_1_at_M_hotkeys": math.ceil(floor_at),
            "meaning": "up to about 28 active hotkeys the daily total stays near R (more hotkeys split one pie; an operator with k "
            "hotkeys gets about k/(M) of it). From about 29 active hotkeys every hotkey is at the floor of 1 a day, and total "
            "demand M x sum_t then exceeds R: the formula no longer protects capacity (see G4b).",
        },
    )


def g4_sybil_pushes_everyone_to_the_floor(tmp):
    """One operator registers `k` hotkeys, each submitting once, to push every honest miner's allowance to the floor."""
    cap = exam_cap.ExamCap(_ledger(tmp, "sybil"), cadence=_cadence())
    honest = _hotkey(2000)
    before = cap.allowance(hotkey=honest, block=100 * 360)["allowance"]
    for i in range(40):
        try:
            cap.reserve(
                hotkey=_hotkey(i),
                challenge_id="chip-cold-plate",
                challenge_version="1.0",
                exam_key=digest("exam"),
                submission_id=f"sha256:sybil-{i}",
                block=100 * 360,
            )
        except exam_cap.ExamCapRefused:
            pass
    after = cap.allowance(hotkey=honest, block=100 * 360 + 1)
    return Result(
        "G4b",
        "G4 multi-hotkey",
        "Cheap hotkeys (one submission each) lower every honest miner's daily allowance",
        "allowance for an honest miner should not be removable by outsiders (design question)",
        f"honest allowance {before}/day -> {after['allowance']}/day after 40 one-shot hotkeys "
        f"(active hotkeys {after['active_miners']})",
        "RISK" if after["allowance"] < before else "PASS",
        {
            "cost_to_attacker": "40 registrations plus 40 graded submissions (each costs one rebuild)",
            "dependency": "mainnet registration cost per hotkey and the submission fee (MAINNET_PREP item 3) bound this; the cap alone does not",
        },
    )


def g4_at_most_one_crown(rng, rounds):
    """Two hotkeys of one operator submit near-identical models for many rounds: the Challenge never has two kings,
    and with no merit difference the crown moves only by the margin rule."""
    changes = 0
    king, king_total = None, None
    noise = 0.02
    for _ in range(rounds):
        total = 0.6 + rng.gauss(
            0, 0.002
        )  # near-identical model: tiny spread, no real merit difference
        hotkey = rng.choice(("A", "B"))
        candidate = _body(f"{hotkey}{_}", total=total)
        incumbent = None if king is None else _body(king, total=king_total)
        out = bp.compare_private_pair(
            _pair(candidate, incumbent), _rule(noise, baseline=0.3)
        )
        if out["outcome"] in (bp.FIRST_INCUMBENT, bp.CHALLENGER):
            king, king_total = candidate["submission_id"], total
            changes += 1
    return Result(
        "G4c",
        "G4 multi-hotkey",
        "Near-identical models from two hotkeys: one king, and the crown does not move on a spread far below the margin",
        "1 crown change (the first), then none",
        f"{changes} crown change(s) over {rounds} rounds",
        "PASS" if changes == 1 else "FAIL",
        {"spread": "sd 0.002 against margin 0.02 (fixture values, " + SYNTHETIC + ")"},
    )


def _phi_bar(x):
    return 0.5 * math.erfc(x / math.sqrt(2))


def g4_noise_fishing(rng, trials=20000):
    """The accepted consequence of the margin rule (OWNER-KOTH-MARGIN-AND-PRIVACY-01 amendment): trivially varied
    resubmissions of one model are independent draws of the rebuild jitter. The margin is the largest difference
    among >= 3 rebuilds of a recipe, so it is only a few sigma wide; a fisher gets many tries a day.
    """
    table = []
    for rebuilds in (3, 5, 10):
        # margin = max pairwise |difference| among `rebuilds` independent draws, in units of sigma (sd of one rebuild)
        margins = []
        for _ in range(trials):
            draws = [rng.gauss(0, 1) for _ in range(rebuilds)]
            margins.append(max(draws) - min(draws))
        margins.sort()
        for label, m in (
            ("typical margin (median)", margins[len(margins) // 2]),
            ("small margin (10th percentile)", margins[len(margins) // 10]),
        ):
            p = _phi_bar(
                m / math.sqrt(2.0)
            )  # candidate draw vs king draw, both with sd sigma, equal true quality
            row = {
                "rebuilds_in_margin_measurement": rebuilds,
                "margin_case": label,
                "margin_in_sigma": round(m, 3),
                "p_per_try": round(p, 4),
            }
            for tries in (1, 7, 28, 140):
                row[f"P_false_crown_in_{tries}_tries"] = round(1 - (1 - p) ** tries, 4)
            table.append(row)
    return Result(
        "G5a",
        "G5 overfit/fishing",
        "Noise fishing: resubmitting trivially varied copies of one model to land on a lucky rebuild",
        "recorded for the owner (a known, accepted consequence); the exposure shrinks with margin / jitter",
        "with a margin from 3 rebuilds, a hotkey using its ~28 daily tries has a high chance of a false crown "
        "(table in detail)",
        "RISK",
        {
            "model": "each try = an independent draw with the jitter sd sigma; king's recorded score is itself one draw; "
            "equal true quality; margin = range of n rebuilds (sigma units). "
            + SYNTHETIC,
            "table": table,
            "bound_in_code": "1 graded submission per epoch and a daily allowance of about 28 for one hotkey (G4a)",
            "mitigations_to_discuss": "a margin measured from more rebuilds; a margin in sigma units rather than the sample range; "
            "the weekly fresh-draw regrade of the king; paying only after the crown survives a fresh draw",
        },
    )


def g5_ratchet(rng, trials=300, days=14):
    """A fisher keeps the crown by luck; the recorded king total ratchets up while true quality is flat, so honest
    improvers face a bar above the model's real quality."""
    sigma, margin, tries = 1.0, 2.0, 28  # margin 2 sigma: roughly a 3-rebuild range
    rise = []
    for _ in range(trials):
        king = rng.gauss(0, sigma)
        for _ in range(days):
            for _ in range(tries):
                x = rng.gauss(0, sigma)
                if x > king + margin:
                    king = x
        rise.append(king)
    rise.sort()
    return Result(
        "G5b",
        "G5 overfit/fishing",
        f"Ratchet: the recorded king total after a fisher works for {days} days against a model of unchanged quality",
        "recorded for the owner",
        f"recorded total ends {rise[len(rise)//2]:.2f} sigma above true quality (median), "
        f"{rise[int(0.9 * len(rise))]:.2f} at the 90th percentile",
        "RISK" if rise[len(rise) // 2] > 0 else "INFO",
        {
            "model": f"margin {margin} sigma, {tries} tries/day, equal true quality. "
            + SYNTHETIC,
            "note": "the weekly regrade of the incumbent on a fresh draw is the registered counter-measure; it is not run by this script",
        },
    )


# ------------------------------------------------------------------------------------------ G5 hill-climb


class _Field:
    """A smooth random function of a point in the unit cube: the idiosyncrasy of one set of exam cases."""

    def __init__(self, rng, dim, features=24, scale=1.0):
        self.w = [[rng.gauss(0, 2.0) for _ in range(dim)] for _ in range(features)]
        self.p = [rng.uniform(0, 2 * math.pi) for _ in range(features)]
        self.a = [
            rng.gauss(0, 1) * scale / math.sqrt(features) for _ in range(features)
        ]

    def __call__(self, x):
        return sum(
            a * math.cos(sum(wi * xi for wi, xi in zip(w, x)) + p)
            for a, w, p in zip(self.a, self.w, self.p)
        )


def _climb(rng, mode, rounds, noise_registered, sigma_cases, dim=6):
    """One attacker. `mode` is "ladder" (sees only the Ladder document) or "exact" (sees every unrounded total)."""
    star = [rng.uniform(0.3, 0.7) for _ in range(dim)]

    def base(x):
        return 0.5 + 0.2 * math.exp(-sum((a - b) ** 2 for a, b in zip(x, star)) / 0.5)

    sealed, fresh = _Field(rng, dim, scale=sigma_cases), _Field(
        rng, dim, scale=sigma_cases
    )
    x = [rng.uniform(0, 1) for _ in range(dim)]
    start_sealed, start_fresh = base(x) + sealed(x), base(x) + fresh(x)
    best_doc = None
    current_exact = start_sealed
    # the attacker's first submission establishes the ladder
    for r in range(rounds):
        candidate = [min(1.0, max(0.0, xi + rng.gauss(0, 0.08))) for xi in x]
        total = base(candidate) + sealed(candidate)
        graded = {
            "status": "SCORED_DEVELOPMENT_CANDIDATE",
            "score": min(1.0, max(0.0, total)),
            "legs": {"A": 0.1, "D": 0.2},
            "gates": {g: "PASS" for g in GATES},
        }
        if mode == "exact":
            if total > current_exact:
                x, current_exact = candidate, total
            continue
        doc = gf.ladder_feedback(
            graded,
            best=best_doc,
            exam_version="exam-1",
            gate_registry=GATES,
            rebuild_noise=noise_registered,
        )
        if doc["status"] == "IMPROVED":
            x = candidate
        best_doc = gf.next_best(best_doc, doc)
    end_sealed, end_fresh = base(x) + sealed(x), base(x) + fresh(x)
    return end_sealed - start_sealed, end_fresh - start_fresh


def g5_hill_climb(rng, trials=60):
    """A scripted hill-climb on the Ladder total for N rounds within the allowance, against the same attacker given
    unrounded totals. Reports the gain on the sealed set minus the gain on a fresh set (the overfit).
    """
    rows = []
    for sigma_cases in (0.01, 0.03):
        for rounds in (28, 140, 560):
            for mode, noise in (("exact", None), ("ladder", None), ("ladder", 0.05)):
                gaps = []
                for t in range(trials):
                    sealed_gain, fresh_gain = _climb(
                        random.Random(rng.random()), mode, rounds, noise, sigma_cases
                    )
                    gaps.append(sealed_gain - fresh_gain)
                gaps.sort()
                rows.append(
                    {
                        "case_idiosyncrasy_sd": sigma_cases,
                        "rounds": rounds,
                        "feedback": (
                            "unrounded totals"
                            if mode == "exact"
                            else f"Ladder (step {gf.step(noise)})"
                        ),
                        "mean_overfit": round(sum(gaps) / len(gaps), 4),
                        "p95_overfit": round(gaps[int(0.95 * len(gaps))], 4),
                    }
                )
    ladder = [r for r in rows if r["feedback"].startswith("Ladder")]
    exact = {
        (r["case_idiosyncrasy_sd"], r["rounds"]): r
        for r in rows
        if r["feedback"] == "unrounded totals"
    }
    reduced = sum(
        1
        for r in ladder
        if r["mean_overfit"]
        <= exact[(r["case_idiosyncrasy_sd"], r["rounds"])]["mean_overfit"] + 1e-9
    )
    return Result(
        "G5c",
        "G5 overfit/fishing",
        "Scripted hill-climb on the rounded Ladder total vs. on unrounded totals: sealed gain minus fresh-set gain",
        "recorded: how far the Ladder's rounding limits overfit (the table is the evidence for 'margin + 2 SE')",
        f"Ladder overfit <= exact-total overfit in {reduced} of {len(ladder)} settings: rounding is a disclosure control, "
        "not a material overfit control at these steps (table in detail)",
        "INFO",
        {
            "model": "a smooth random field per case set stands for what the sealed cases reward beyond the population; the "
            "attacker sees only the Ladder document (real grade_feedback code). "
            + SYNTHETIC,
            "table": rows,
            "reading": "compare p95_overfit with the Challenge's margin plus 2 SE once both are registered; the weekly fresh-draw check "
            "measures this on the real king",
        },
    )


# ------------------------------------------------------------------------------- feedback leak and disclosure

SENTINEL = "CARBON-SENTINEL-7f3a91c2e8d44b0a"


def _walk_strings(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, str):
        yield value


def encodings(sentinel):
    """The forms a planted sentinel can take if a field is re-encoded on its way out."""
    raw = sentinel.encode()
    forms = {sentinel, sentinel.lower(), sentinel.upper(), raw.hex(), raw.hex().upper()}
    for pad in range(3):
        shifted = b"\0" * pad + raw
        std = base64.b64encode(shifted).decode().rstrip("=")
        url = base64.urlsafe_b64encode(shifted).decode().rstrip("=")
        # drop the characters that depend on the neighbouring bytes
        forms.add(std[4:-4])
        forms.add(url[4:-4])
    from urllib.parse import quote

    forms.add(quote(sentinel))
    return {f for f in forms if len(f) >= 8}


def scan_text(text, sentinel):
    return sorted(form for form in encodings(sentinel) if form in text)


def g6_offline_sweep(rng):
    """Plant a sentinel in every private field of the inputs of each miner-facing builder; none may reach an output."""
    hits, outputs = [], 0
    graded_variants = []
    base_row = {
        "artifact_digest": digest("a"),
        "legs": {"A": 0.33, "D": 0.41},
        "gates": {g: "PASS" for g in GATES},
        "components": {"x": SENTINEL},
        "decision_outcome": SENTINEL,
        "per_case": [SENTINEL, 0.1],
        "pick": SENTINEL,
        "case_ids": [SENTINEL],
        "seed": SENTINEL,
        "reference": {"path": f"/custody/{SENTINEL}"},
    }
    for status, score in (
        ("SCORED_DEVELOPMENT_CANDIDATE", 0.61),
        ("MANDATORY_GATE_FAILED", None),
        ("REQUIRED_LEG_MINIMUM_FAILED", None),
        ("CANDIDATE_INVALID", None),
        ("FAILED_INFRA", None),
        ("INDETERMINATE_EVIDENCE", None),
    ):
        row = dict(base_row, status=status, score=score)
        if status == "MANDATORY_GATE_FAILED":
            row["gates"] = {GATES[0]: "FAIL", GATES[1]: "PASS"}
        graded_variants.append(row)
    for row in graded_variants:
        for about in (False, True):
            kw = {"recipe_digest": digest("recipe"), "epoch": 7} if about else {}
            doc = gf.ladder_feedback(
                row,
                best=None,
                exam_version="exam-1",
                gate_registry=GATES,
                rebuild_noise=0.01,
                leg_minimums={"A": 0.5, "D": 0.5},
                **kw,
            )
            outputs += 1
            hits += scan_text(json.dumps(doc), SENTINEL)
            if gf.shape(doc) is None:
                hits.append("document_shape_not_allow_listed")
    king = {
        "hotkey": SS58_A,
        "total": 0.77,
        "since_epoch": 4,
        "recipe": SENTINEL,
        "path": SENTINEL,
    }
    doc = koth_public.document(
        challenge_id=CHALLENGE,
        challenge_version="1.0",
        exam_version_label="exam-1",
        king=king,
        rebuild_noise={"value": 0.01, "measurement_digest": KEY, "panel": SENTINEL},
        baseline_total=0.3,
    )
    outputs += 1
    hits += scan_text(json.dumps(doc), SENTINEL)
    decision = bp.compare_private_pair(
        _pair(
            _body("c", total=0.9, extra={"per_case": SENTINEL, "seed": SENTINEL}),
            _body("k", total=0.5, extra={"seed": SENTINEL}),
        ),
        _rule(0.02),
    )
    outputs += 1
    hits += scan_text(json.dumps(decision), SENTINEL)
    # a hostile gate name or exam label carrying the sentinel must be refused, not echoed
    for call in (
        lambda: gf.ladder_feedback(
            dict(
                base_row,
                status="MANDATORY_GATE_FAILED",
                score=None,
                gates={SENTINEL: "FAIL"},
            ),
            best=None,
            exam_version="exam-1",
            gate_registry=GATES,
            rebuild_noise=0.01,
        ),
        lambda: koth_public.document(
            challenge_id=CHALLENGE,
            challenge_version="1.0",
            exam_version_label=SENTINEL + "!!",
            king=None,
            rebuild_noise=None,
            baseline_total=0.3,
        ),
    ):
        try:
            echoed = json.dumps(call())
            hits += scan_text(echoed, SENTINEL) or ["hostile_value_accepted"]
        except REFUSALS as error:
            hits += scan_text(str(error), SENTINEL)
    cap = exam_cap.ExamCap(_ledger(tempfile.mkdtemp(), "g6"), cadence=_cadence())
    try:
        cap.reserve(
            hotkey=SS58_A,
            challenge_id=SENTINEL,
            challenge_version="1.0",
            exam_key=KEY,
            submission_id="x",
            block=1,
        )
    except exam_cap.ExamCapRefused as error:
        outputs += 1
        hits += scan_text(str(error), SENTINEL)
    return Result(
        "G6a",
        "G6 disclosure",
        "Offline sweep: a sentinel planted in every private input of the Ladder, the public king document, the comparator "
        "decision and the cap's refusals appears in no output (raw, case-changed, hex, base64, percent-encoded)",
        "0 hits",
        f"{len(hits)} hits over {outputs} outputs",
        "PASS" if not hits else "FAIL",
        {"hits": hits[:5]},
    )


def g5_feedback_information(rng):
    """The Ladder document is a closed set: what one submission can teach at most."""
    totals = [rng.uniform(0, 1) for _ in range(20000)]
    docs = set()
    over = 0
    for t in totals:
        doc = gf.ladder_feedback(
            {
                "status": "SCORED_DEVELOPMENT_CANDIDATE",
                "score": t,
                "legs": {"A": t, "D": t},
                "gates": {g: "PASS" for g in GATES},
            },
            best=None,
            exam_version="exam-1",
            gate_registry=GATES,
            rebuild_noise=None,
        )
        docs.add(json.dumps(doc, sort_keys=True))
        if (
            doc["total"] is None
            or doc["total"] > t + 1e-12
            or t - doc["total"] >= gf.ETA + 1e-9
        ):
            over += 1
        if set(doc) != gf.FIELDS:
            over += 1
    bits = math.log2(len(docs))
    return Result(
        "G5d",
        "G5 overfit/fishing",
        "Ladder document: rounded down within one step, exactly the allow-listed fields, no leg or case value",
        "0 violations; at most ~log2(1/step) bits of the total per submission",
        f"{over} violations; {len(docs)} distinct documents over 20000 totals (~{bits:.1f} bits)",
        "PASS" if over == 0 else "FAIL",
    )


# -------------------------------------------------------------------------------------------- live G6 scan


def scan_directory(directory, sentinels):
    """G6 against a real run: every file under `directory` (captured miner responses, Ladder documents, receipts,
    public pages, state documents) is searched for each sentinel in all encodings. Returns [(file, form)].
    """
    findings = []
    for path in sorted(Path(directory).rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        for sentinel in sentinels:
            for form in encodings(sentinel):
                if form in text or form.encode() in data:
                    findings.append((str(path), form))
    return findings


# ------------------------------------------------------------------------------------------------- driver


def run(seed=20261025, fast=False):
    rng = random.Random(seed)
    tmp = tempfile.mkdtemp(prefix="attack-")
    rounds = 400 if fast else 4000
    results = [
        g1_copy_never_wins(rng, rounds),
        g1_margin_edge(rng),
        g1_baseline_entry_copy(),
        g1_replay_and_cross_hotkey(tmp),
        g1_public_numbers_do_not_overpromise(rng, rounds),
        hostile_comparator_inputs(),
        noise_unregistered_never_crowns(),
        out_of_range_total_reaches_comparator(),
        g4_extra_capacity_and_sybil_floor(tmp),
        g4_sybil_pushes_everyone_to_the_floor(tmp),
        g4_at_most_one_crown(rng, 200 if fast else 2000),
        g4_noise_fishing(rng, 2000 if fast else 20000),
        g5_ratchet(rng, 60 if fast else 300),
        g5_hill_climb(rng, 6 if fast else 60),
        g5_feedback_information(rng),
        g6_offline_sweep(rng),
    ]
    return results


def markdown(results, seed):
    lines = [
        f"# Pre-mainnet attack tests (seed {seed})",
        "",
        "| id | area | verdict | attack | expected | observed |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.id} | {r.area} | **{r.verdict}** | {r.title} | {r.expected} | {r.observed} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument(
        "--scan",
        type=Path,
        help="G6 against a live run: a directory of captured responses and state",
    )
    parser.add_argument("--sentinel", action="append", default=[])
    parser.add_argument("--sentinel-file", type=Path, help="one sentinel per line")
    args = parser.parse_args(argv)
    if args.scan is not None:
        sentinels = list(args.sentinel)
        if args.sentinel_file is not None:
            sentinels += [
                s for s in args.sentinel_file.read_text().splitlines() if s.strip()
            ]
        if not sentinels:
            parser.error("--scan needs --sentinel or --sentinel-file")
        findings = scan_directory(args.scan, sentinels)
        for path, form in findings:
            print(f"LEAK {path} contains {form[:12]}...")
        print(
            f"G6 live scan: {'FAIL' if findings else 'PASS'} ({len(findings)} findings)"
        )
        return 1 if findings else 0
    results = run(args.seed, args.fast)
    if args.json:
        args.json.write_text(
            json.dumps([r.__dict__ for r in results], indent=1, default=str),
            encoding="utf-8",
        )
    text = markdown(results, args.seed)
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    print(text)
    return 1 if any(r.verdict == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
