"""The feedback-leak attack for the v4 per-part feedback (PART_FEEDBACK_GRANULARITY_20261029 section 3; POOL_GRADER_AND_PROOF_SUITE_SPEC
section 3 item 5), as a custody payload. Run it BEFORE a Challenge serves v4; aggregates only.

A simulated miner submits perturbations of a model over many rounds and keeps a perturbation only when the feedback it is SHOWN
says it improved. Three attackers, each seeing exactly what the v4 document shows (through the real `grade_feedback` functions):

(a) **total**: hill-climbs on the Ladder total (rounded down to the step; an improvement shows only when the total reaches the
    best shown total plus one full step: the Ladder rule);
(b) **one attacker per shown part** (A, D, and every registered component), each hill-climbing on that part alone, through the part
    hysteresis (a change shows only after a full part step);
(c) **joint**: uses every part and the gates together (accepts a perturbation whose total improved, or in which some part rose, none
    fell, and every gate passed).

The leak measure is the attacker's final model's gain on the SEALED set beyond its gain on a FRESH set drawn from the same region
(same Challenge, same version): ``gap = (sealed_final - sealed_start) - (fresh_final - fresh_start)``. An honest attacker climbs
only what generalises, so the gap is about zero; a part that leaks the sealed cases lets it climb the sealed set alone.
**Pass rule (unchanged):** the mean gap over the independent attacker runs is within the KOTH margin ``M`` plus 2 standard errors:
``mean_gap <= M + 2 * SE``, and only when the run RESOLVES the margin (``2 * SE <= M``): a wider SE is INCONCLUSIVE (add seeds),
never a pass. A model that scores on the sealed exam but not on the fresh draw FAILS that attacker. ``M`` is the version's
REGISTERED KOTH margin (``--margin-source registered``); the sheet's 0.01 (``provisional_sheet``) only when none is registered; the
output says which was used. This module has no default for either.

If a part FAILS, make it coarser rather than hiding it (the owner's rule), and re-run: ``--part-step 0.10`` for that part's step,
then ``--bands`` for the three-word band (low < 1/3 <= mid < 2/3 <= high). A part that fails even as a band goes to the owner with
these numbers; this tool never decides that.

    python3 attack.py selftest
    python3 attack.py run --binding MODULE:FUNCTION --rounds N --seeds S --margin M --out RESULT.json
                          [--rebuild-noise V] [--part-step P] [--bands] [--sigma0 0.3] [--patience 8] [--shrink 0.7]
    python3 attack.py sums            # the sha256 of this payload's files (compare with SHA256SUMS)

THE BINDING (custody): ``MODULE:FUNCTION`` names a factory returning an object with
    ``dim``                an int, the perturbation dimension;
    ``parts_registry()``   {"A": (metric, ...), "D": (metric, ...)} as the score pack registers them;
    ``gate_names()``       the registered hard gates;
    ``grade(theta, which)`` -> {"status": "SCORED" | other, "total": float, "legs": {"A": float, "D": float},
                            "components": {metric: float}, "gates": {gate: bool}}
                           for ``which`` in ("sealed", "fresh"); theta = zeros(dim) is the unperturbed model.
The binding is the Challenge's real grader on its sealed exam and on a fresh QA-passed draw from the same region. Nothing here
reads a case, a seed or a pool; the output holds no theta and no per-case value.

NUMERICAL settings (the proposal scale, the shrink, the patience, the rounds, the seeds) are recorded in the output and are never
tuned to reach a pass. The rounds are the registered cadence over the 90-day rotation maximum: the owner's rule is
``a = R / (M * sum t)`` graded submissions per miner per day, floor 1 a day, ceiling 1 per epoch; the Test Lead passes the
registered figure. This module invents none.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.scoring import grade_feedback as gf

SCHEMA = "carbon.part-feedback.leak-attack.v1"
#: Which margin M was used: the version's REGISTERED KOTH margin (margin_N from the recal), or the sheet's provisional 0.01 when
#: none is registered. The output says which (Validator, 2026-11-01).
MARGIN_SOURCES = ("registered", "provisional_sheet")
OUTCOMES = ("PASS", "FAIL", "INCONCLUSIVE")
UNSCORED_CASES = (
    "fresh_unscored_while_sealed_scores",
    "sealed_unscored_while_fresh_scores",
    "both_unscored",
)
PAYLOAD_FILES = ("attack.py", "README.md")
BAND_EDGES = (1.0 / 3.0, 2.0 / 3.0)


class AttackRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def band_of(value):
    """The three-word band of a part: 0 low (< 1/3), 1 mid (< 2/3), 2 high."""
    return 0 if value < BAND_EDGES[0] else 1 if value < BAND_EDGES[1] else 2


# ---------------------------------------------------------------- what a miner is shown


class Observer:
    """The v4 feedback for ONE hotkey across rounds, built from the real `grade_feedback` functions: the total through the Ladder
    rule, each part through the hysteresis (or as a band), the gates as pass/fail."""

    def __init__(self, total_step, part_step, bands):
        self.total_step, self.part_step, self.bands = total_step, part_step, bands
        self.best_total = None
        self.parts = {}

    def _part(self, name, value):
        if self.bands:
            shown = band_of(value)
            self.parts[name] = shown
            return shown
        shown = gf.shown_part(value, self.parts.get(name), self.part_step)
        self.parts[name] = shown
        return shown

    def show(self, graded):
        """``{"gate_failed", "improved", "total", "parts"}`` for one graded result. A failed gate shows no numbers."""
        if graded.get("status") != "SCORED":
            return {"gate_failed": False, "scored": False}
        if not all(graded["gates"].values()):
            return {"gate_failed": True, "scored": False}
        total = graded["total"]
        improved = self.best_total is None or total >= self.best_total + self.total_step
        if improved:
            self.best_total = gf._floor(total, self.total_step)
        parts = {
            "A": self._part("A", graded["legs"]["A"]),
            "D": self._part("D", graded["legs"]["D"]),
        }
        for name, value in sorted(graded["components"].items()):
            parts[name] = self._part(name, value)
        return {
            "gate_failed": False,
            "scored": True,
            "improved": improved,
            "total": self.best_total,
            "parts": parts,
        }


# ---------------------------------------------------------------- the attackers


def _accept(kind, before, after):
    """Whether an attacker keeps a perturbation, from what it was shown before and after."""
    if not after["scored"]:
        return False
    if kind == "total":
        return after["improved"]
    if before is None:
        return True
    if kind == "joint":
        rose = [after["parts"][n] > before["parts"][n] for n in after["parts"]]
        fell = [after["parts"][n] < before["parts"][n] for n in after["parts"]]
        return after["improved"] or (any(rose) and not any(fell))
    return after["parts"][kind] > before["parts"][kind]  # one attacker per shown part


def climb(
    binding,
    kind,
    *,
    rounds,
    seed,
    total_step,
    part_step,
    bands,
    sigma0,
    patience,
    shrink,
):
    """One independent attacker run: a (1+1) hill-climb on what the feedback shows. Returns the final theta (kept in memory only)."""
    rng = random.Random(f"{kind}:{seed}")
    dim = binding.dim
    theta = [0.0] * dim
    observer = Observer(total_step, part_step, bands)
    shown = observer.show(binding.grade(theta, "sealed"))
    sigma, stale, accepted = sigma0, 0, 0
    for _ in range(rounds):
        candidate = [t + sigma * rng.gauss(0.0, 1.0) for t in theta]
        # a rejected candidate must not move the hysteresis state of the accepted line: observe on a copy
        trial = Observer(total_step, part_step, bands)
        trial.best_total, trial.parts = observer.best_total, dict(observer.parts)
        after = trial.show(binding.grade(candidate, "sealed"))
        if _accept(kind, shown, after):
            theta, shown, accepted, stale = candidate, after, accepted + 1, 0
            observer.best_total, observer.parts = trial.best_total, trial.parts
        else:
            stale += 1
            if stale >= patience:
                sigma, stale = sigma * shrink, 0
    return theta, accepted


def _mean_se(values):
    mean = statistics.fmean(values)
    se = (
        statistics.stdev(values) / math.sqrt(len(values))
        if len(values) > 1
        else float("nan")
    )
    return mean, se


def _gains(sealed_end, fresh_end, start, counts):
    """``(sealed_gain, fresh_gain)`` of an attacker's final model, counting every case in which one side stops scoring.
    A model that scores on the sealed exam but NOT on the fresh draw is the strongest overfit signal and is never hidden:
    the gain on the sealed side is kept and `_judge` fails the attacker."""
    sealed_ok = sealed_end.get("status") == "SCORED"
    fresh_ok = fresh_end.get("status") == "SCORED"
    if sealed_ok and fresh_ok:
        return (
            sealed_end["total"] - start["sealed"]["total"],
            fresh_end["total"] - start["fresh"]["total"],
        )
    if sealed_ok:
        counts["fresh_unscored_while_sealed_scores"] += 1
        return sealed_end["total"] - start["sealed"]["total"], 0.0
    if fresh_ok:
        counts["sealed_unscored_while_fresh_scores"] += 1  # no sealed gain was made
        return 0.0, 0.0
    counts["both_unscored"] += 1  # a model that no longer scores gained nothing
    return 0.0, 0.0


def _judge(mean_gap, se, margin, counts):
    """``(outcome, reason)`` of one attacker. FAIL when a final model broke on fresh data while the sealed exam still scored it, or
    when mean gap > M + 2 SE; INCONCLUSIVE when the run cannot resolve the margin (2 SE > M: add seeds); else PASS.
    """
    if counts["fresh_unscored_while_sealed_scores"]:
        return "FAIL", "fresh_unscored_while_sealed_scores"
    if mean_gap > margin + 2.0 * se:
        return "FAIL", "gap_above_margin_plus_2_se"
    if 2.0 * se > margin or math.isnan(se):
        return "INCONCLUSIVE", "add_seeds"
    return "PASS", None


def attack(
    binding,
    *,
    rounds,
    seeds,
    margin,
    margin_source,
    rebuild_noise=None,
    part_step=None,
    bands=False,
    sigma0=0.3,
    patience=8,
    shrink=0.7,
):
    """Run every attacker ``seeds`` times and return the aggregates-only result."""
    if type(margin) not in (int, float) or not math.isfinite(margin) or margin < 0:
        raise AttackRefused("margin_required")
    if margin_source not in MARGIN_SOURCES:
        raise AttackRefused("margin_source_required")
    if type(rounds) is not int or rounds < 1 or type(seeds) is not int or seeds < 2:
        raise AttackRefused("rounds_and_two_or_more_seeds_required")
    total_step = gf.step(rebuild_noise)
    p = gf.part_step(rebuild_noise) if part_step is None else float(part_step)
    if p < gf.part_step(rebuild_noise) and part_step is not None:
        raise AttackRefused(
            "part_step_finer_than_registered"
        )  # an attack on a finer step proves nothing about the shipped one
    registry = binding.parts_registry()
    names = ["A", "D", *sorted({n for leg in registry.values() for n in leg})]
    kinds = ["total", *names, "joint"]
    start = {
        "sealed": binding.grade([0.0] * binding.dim, "sealed"),
        "fresh": binding.grade([0.0] * binding.dim, "fresh"),
    }
    for which, graded in start.items():
        if graded.get("status") != "SCORED":
            raise AttackRefused(f"unperturbed_model_not_scored_{which}")
    results = []
    for kind in kinds:
        gaps, sealed_gains, fresh_gains, accepted_counts = [], [], [], []
        counts = dict.fromkeys(UNSCORED_CASES, 0)
        for seed in range(seeds):
            theta, accepted = climb(
                binding, kind, rounds=rounds, seed=seed, total_step=total_step, part_step=p, bands=bands,
                sigma0=sigma0, patience=patience, shrink=shrink,
            )  # fmt: skip
            sealed_end, fresh_end = binding.grade(theta, "sealed"), binding.grade(
                theta, "fresh"
            )
            sealed_gain, fresh_gain = _gains(sealed_end, fresh_end, start, counts)
            sealed_gains.append(sealed_gain)
            fresh_gains.append(fresh_gain)
            gaps.append(sealed_gain - fresh_gain)
            accepted_counts.append(accepted)
        mean_gap, se = _mean_se(gaps)
        bound = margin + 2.0 * se
        outcome, reason = _judge(mean_gap, se, margin, counts)
        results.append(
            {
                "attacker": kind,
                "runs": seeds,
                "mean_accepted_perturbations": statistics.fmean(accepted_counts),
                "mean_sealed_gain": statistics.fmean(sealed_gains),
                "mean_fresh_gain": statistics.fmean(fresh_gains),
                "mean_gap": mean_gap,
                "se_gap": se,
                "bound": bound,
                "unscored": counts,
                "outcome": outcome,
                "reason": reason,
                "pass": outcome == "PASS",
            }
        )
    config = {
        "rounds": rounds,
        "seeds": seeds,
        "margin": margin,
        "margin_source": margin_source,
        "rebuild_noise": rebuild_noise,
        "total_step": total_step,
        "part_step": p,
        "bands": bands,
        "sigma0": sigma0,
        "patience": patience,
        "shrink": shrink,
        "dim": binding.dim,
        "components": names[2:],
        "gates": list(binding.gate_names()),
    }
    body = {
        "schema": SCHEMA,
        "config": config,
        "attackers": results,
        "all_pass": all(r["outcome"] == "PASS" for r in results),
    }
    body["run_digest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                {k: body[k] for k in ("schema", "config", "attackers")},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    return body


# ---------------------------------------------------------------- the fake binding of the selftest


class FakeBinding:
    """A synthetic Challenge: a smooth true landscape shared by both sets, plus a SEALED-only ripple the climber can exploit when the
    feedback is fine enough. Nothing here is physics: it exists to show the instrument sees a leak and does not invent one.
    """

    gates = ("g1", "g2")

    def __init__(self, dim=3, ripple=0.30, noise=0.0):
        self.dim, self.ripple, self.noise = dim, ripple, noise
        self.optimum = [0.15 * (i + 1) for i in range(dim)]

    def parts_registry(self):
        return {"A": ("a_one", "a_two"), "D": ("d_one",)}

    def gate_names(self):
        return self.gates

    def _truth(self, theta):
        return (
            0.5
            - 0.4
            * sum((t - o) ** 2 for t, o in zip(theta, self.optimum, strict=True))
            / self.dim
        )

    def _ripple(self, theta, which):
        if which != "sealed":
            return 0.0
        return (
            self.ripple
            * math.sin(9.0 * sum(theta) + 3.0 * theta[0])
            * math.cos(7.0 * theta[-1])
        )

    def grade(self, theta, which):
        base = self._truth(theta)
        rip = self._ripple(theta, which)
        a = min(1.0, max(0.0, base + 0.6 * rip))
        d = min(1.0, max(0.0, base - 0.2 * rip))
        return {
            "status": "SCORED",
            "total": 0.5 * a + 0.5 * d,
            "legs": {"A": a, "D": d},
            "components": {
                "a_one": a,
                "a_two": min(1.0, max(0.0, a * 0.9)),
                "d_one": d,
            },
            "gates": {g: True for g in self.gates},
        }


def _with_steps(eta, part_floor, function):
    """Run ``function`` with the Ladder step and the part-step floor temporarily set (the selftest's observers only)."""
    original = (gf.ETA, gf.PART_FLOOR)
    gf.ETA, gf.PART_FLOOR = eta, part_floor
    try:
        return function()
    finally:
        gf.ETA, gf.PART_FLOOR = original


def selftest():
    """Show on fake data that the instrument sees a leak when the feedback is fine and reports none when it is coarse. The fake's
    constants are chosen for this demonstration only; they say nothing about any real Challenge or the shipped steps.
    """
    binding = FakeBinding(ripple=0.08)
    common = {
        "rounds": 300,
        "seeds": 6,
        "margin": 0.01,
        "margin_source": "provisional_sheet",
        "sigma0": 0.2,
        "patience": 6,
        "shrink": 0.8,
    }
    leaky = _with_steps(0.0005, 0.0005, lambda: attack(binding, **common))
    coarse = _with_steps(0.15, 0.15, lambda: attack(binding, **common))
    banded = attack(binding, bands=True, **common)
    checks = {
        "fine_feedback_leaks": (not leaky["all_pass"])
        and any(r["mean_gap"] > r["bound"] for r in leaky["attackers"]),
        "coarse_feedback_does_not_leak_the_fake": coarse["all_pass"],
        "bands_do_not_leak_the_fake": banded["all_pass"],
        "deterministic": _with_steps(0.15, 0.15, lambda: attack(binding, **common))[
            "run_digest"
        ]
        == coarse["run_digest"],
        "no_theta_in_output": "theta" not in json.dumps(leaky),
        "a_finer_part_step_than_registered_is_refused": _refused(binding, common),
    }
    return {"selftest": checks, "ok": all(checks.values())}


def _refused(binding, common):
    try:
        attack(binding, part_step=0.001, **common)
    except AttackRefused as refusal:
        return refusal.code == "part_step_finer_than_registered"
    return False


# ---------------------------------------------------------------- command line


def _load(binding):
    module, _, function = binding.partition(":")
    if not module or not function:
        raise AttackRefused("binding_is_module_colon_function")
    return getattr(importlib.import_module(module), function)()


def sums():
    return {
        name: hashlib.sha256(
            (HERE / name).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for name in PAYLOAD_FILES
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    sub.add_parser("sums")
    run = sub.add_parser("run")
    run.add_argument("--binding", required=True)
    run.add_argument("--rounds", type=int, required=True)
    run.add_argument("--seeds", type=int, required=True)
    run.add_argument("--margin", type=float, required=True)
    run.add_argument("--margin-source", required=True, choices=MARGIN_SOURCES)
    run.add_argument("--out", required=True)
    run.add_argument("--rebuild-noise", type=float, default=None)
    run.add_argument("--part-step", type=float, default=None)
    run.add_argument("--bands", action="store_true")
    run.add_argument("--sigma0", type=float, default=0.3)
    run.add_argument("--patience", type=int, default=8)
    run.add_argument("--shrink", type=float, default=0.7)
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        out = selftest()
        print(json.dumps(out, sort_keys=True))
        return 0 if out["ok"] else 1
    if args.cmd == "sums":
        for name, digest in sums().items():
            print(f"{digest}  {name}")
        return 0
    result = attack(
        _load(args.binding), rounds=args.rounds, seeds=args.seeds, margin=args.margin, margin_source=args.margin_source,
        rebuild_noise=args.rebuild_noise,
        part_step=args.part_step, bands=args.bands, sigma0=args.sigma0, patience=args.patience, shrink=args.shrink,
    )  # fmt: skip
    Path(args.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps({"all_pass": result["all_pass"], "run_digest": result["run_digest"]})
    )
    return 0 if result["all_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
