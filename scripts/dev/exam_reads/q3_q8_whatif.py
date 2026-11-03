"""Custody reads of the current exams: Q3 (A_bank vs A_gen ranking), Q8 (near-gate margins) and the NEW-RULES what-if.

    python3 q3_q8_whatif.py q3     CONFIG.json --out OUT.json
    python3 q3_q8_whatif.py q8     CONFIG.json --out OUT.json
    python3 q3_q8_whatif.py whatif CONFIG.json --out OUT.json

READ-ONLY and scratch: nothing is written to the receiver's store (the pool store is opened ``mode=ro``), no score is official, nothing
is rescored in any record. Only AGGREGATES leave custody: hotkeys may appear, exact totals, per-target values and case ids never do
(the what-if reports gaps and spreads, not totals). Pause during any door grade; run under the leak attack's bounds (CPUQuota 200 %,
MemoryMax 4G, nice 19, no GPU).

Re-grade route (the Validator's): each current-exam entry's retained ``inference-pair.json`` is graded through
``calibration_grade.grade`` -> the version's ``PoolVariant.measure`` -> ``pool_exam.measure_pool`` on the SEALED pack read in the
validator's copy form (`pool_binding._load_set`, the leak attack's loader), and ``measure_pool``'s own ``capture`` hands back
A_bank, the per-target d and A_gen, and C. Nothing of the scoring is re-implemented: the what-if changes only the OWNER-registered
policies handed to the same functions (top-k pick rule, ``balanced_region_mean``, s_h, A_gen scales), and wraps the model in the
proof suite's own ``biased`` control. Every recomputed total is checked against the graded one (a mismatch STOPS the run).

Q8's margins (the gate-margin card, `gate_slack`): physics_pool's m is read beside the live gate from the pool answers it received
(the min over the entry's laws and answers; a parity STOP on any answer whose slack sign disagrees with the live verdict),
with a per-law block (raw slack always; m only for a law with a REGISTERED scale, today Motor's allowance) and the pool's
near-limit design counts (per limit x region class, +-U and +-3U). The sealed grader's native gates expose no margin.

CONFIG (every key required; nothing is defaulted):
  challenge, version, evaluation_version   the live version and its CURRENT exam key
  copy_hotkey, pack_root                   the sealed pack in the validator's copy form (as the leak attack)
  baseline_predictions                     the baseline's retained inference pair (the 'baseline' row of the what-if), or null for a
                                           Challenge with no registered baseline pair: then q8 runs, and q3 and the what-if refuse
  store                                    the pool store (sqlite file, opened read-only)
  task_roots                               directories searched for ``<submission_id>.evaluation/inference-pair.json``
  margin_n                                 the version's registered margin_N (printed beside the bootstrap spreads)
  top                                      how many top entries (5)
  gaming                                   the suite's accuracy-matched `biased` controls, a list of {"mode": "feasible_bias", "k", "seed"}
                                           or {"mode": "wrong_near", "k", "radius", "seed"} (the pool proof grid's registered ones)
  records                                  {"koth_rebuild_noise_sha256", "proof_grid_sha256", "proof_grid_seed"}: the files margin_n and gaming
                                           were read from, and the grid's OWN seed (20261025), recorded beside the controls' seed (20261101)
  agen_factors                             A_gen scale multipliers to try, relative to the registered scale (e.g. [1.0, 0.3333333333333333])
  s_h_fraction                             0.25 (s_h = fraction x the baseline's median per-target pick error)
  pick_k                                   3
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import dataclasses
import hashlib
import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for path in (str(ROOT), str(HERE), str(HERE.parent / "part_feedback_attack")):
    if path not in sys.path:
        sys.path.insert(0, path)

SEED = 20261101
#: The pool physics gate (`pool_exam.PHYSICS_GATE`) and the Q8 near-gate band on m.
PHYSICS_POOL = "physics_pool"
NEAR_GATE = 0.10
RESAMPLES = 2000
PLACEHOLDER_S_H = 1.0  # a pick error e does not depend on s_h: any positive value gives the same e list
CONFIG_KEYS = frozenset(
    {
        "challenge",
        "version",
        "evaluation_version",
        "copy_hotkey",
        "pack_root",
        "baseline_predictions",
        "store",
        "task_roots",
        "margin_n",
        "top",
        "gaming",
        "records",
        "agen_factors",
        "s_h_fraction",
        "pick_k",
    }
)


class ReadRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise ReadRefused(code)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_config(path):
    document = json.loads(Path(path).read_bytes())
    _need(type(document) is dict, "config_shape")
    unknown = sorted(set(document) - CONFIG_KEYS)
    _need(not unknown, f"config_unknown_key:{unknown[0] if unknown else ''}")
    missing = sorted(CONFIG_KEYS - set(document))
    _need(not missing, f"config_missing_key:{missing[0] if missing else ''}")
    for key in (
        "challenge",
        "version",
        "evaluation_version",
        "copy_hotkey",
        "pack_root",
        "store",
    ):
        _need(type(document[key]) is str and document[key], f"config_{key}")
    # null only for a Challenge with no registered baseline pair; the reads that need it refuse it (`_needs_baseline`)
    _need(
        document["baseline_predictions"] is None
        or (
            type(document["baseline_predictions"]) is str
            and document["baseline_predictions"]
        ),
        "config_baseline_predictions",
    )
    roots = document["task_roots"]
    _need(
        type(roots) is list and roots and all(type(r) is str and r for r in roots),
        "config_task_roots",
    )
    for key in ("margin_n", "s_h_fraction"):
        _need(
            type(document[key]) in (int, float)
            and math.isfinite(document[key])
            and document[key] > 0,
            f"config_{key}",
        )
    _need(type(document["top"]) is int and document["top"] >= 2, "config_top")
    _need(type(document["pick_k"]) is int and document["pick_k"] >= 1, "config_pick_k")
    gaming = document["gaming"]
    _need(type(gaming) is list and gaming, "config_gaming")
    for control in gaming:
        _need(
            type(control) is dict
            and control.get("mode") in ("feasible_bias", "wrong_near")
            and set(control)
            == (
                {"mode", "k", "seed"}
                if control["mode"] == "feasible_bias"
                else {"mode", "k", "radius", "seed"}
            )
            and type(control["seed"]) is int
            and all(
                type(control[key]) in (int, float)
                and math.isfinite(control[key])
                and control[key] > 0
                for key in ("k", "radius")
                if key in control
            ),
            "config_gaming",
        )
    records = document["records"]
    _need(
        type(records) is dict
        and set(records)
        == {"koth_rebuild_noise_sha256", "proof_grid_sha256", "proof_grid_seed"}
        and all(
            type(records[k]) is str and len(records[k]) == 64
            for k in ("koth_rebuild_noise_sha256", "proof_grid_sha256")
        )
        and type(records["proof_grid_seed"]) is int,
        "config_records",
    )
    factors = document["agen_factors"]
    _need(
        type(factors) is list
        and factors
        and all(type(f) in (int, float) and math.isfinite(f) and f > 0 for f in factors)
        and 1.0 in factors,
        "config_agen_factors",
    )
    return document


# ---------------------------------------------------------------- the statistics (pure)


def ranks(values):
    """Average ranks (ties share their mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return out


def pearson(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / (sx * sy)


def spearman(x, y):
    """Spearman's rho (Pearson of the average ranks), or None when either side is constant."""
    _need(len(x) == len(y) and len(x) >= 2, "spearman_needs_two_paired_entries")
    return pearson(ranks(x), ranks(y))


def bootstrap_rho(x, y, *, resamples=RESAMPLES, seed=SEED):
    """``(rho, (low, high))``: the 95 % percentile interval of rho over ``resamples`` resamples of ENTRIES (a resample with a
    constant side contributes nothing). The interval is None when no resample had a defined rho.
    """
    import numpy as np

    rho = spearman(x, y)
    generator = np.random.Generator(np.random.PCG64(seed))
    n = len(x)
    draws = []
    for _ in range(resamples):
        index = generator.integers(0, n, size=n)
        value = spearman([x[i] for i in index], [y[i] for i in index])
        if value is not None:
            draws.append(value)
    if not draws:
        return rho, None
    low, high = np.percentile(np.asarray(draws), [2.5, 97.5])
    return rho, (float(low), float(high))


def flipped_pairs(rows, key_a, key_b):
    """``(flipped, pairs)`` over every pair of ``rows``: a pair is flipped when its order by ``key_a`` alone is STRICTLY opposite
    to its order by ``key_b`` alone (a tie on either side is not a flip)."""
    flipped = pairs = 0
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            pairs += 1
            da = rows[i][key_a] - rows[j][key_a]
            db = rows[i][key_b] - rows[j][key_b]
            if da * db < 0:
                flipped += 1
    return flipped, pairs


# ---------------------------------------------------------------- one entry's decomposition


def pack_total(combo, a, d):
    """The pack's own combination of the two legs (`dual_score.score`'s formula): ``combo`` is the pack's
    ``{"combination", "value_weight"}``. Checked against every graded total before use (a drifted composition STOPS).
    """
    w = combo["value_weight"]
    if combo["combination"] == "weighted_arithmetic_mean":
        return (1 - w) * a + w * d
    return (
        0.0
        if a == 0 or d == 0
        else min(a, d) * math.exp((1 - w) * math.log(a) + w * math.log(d))
    )


def decompose(basis, combo):
    """A record's numbers from ``measure_pool``'s ``capture["se_basis"]``: A_bank, C, A_gen per set (mean over its targets that
    have one), D per set (plain mean of d), and the total recomputed by the exam's own composition
    (`pool_exam.total_of_targets`). ``classes`` (per set, per target) is carried for the balanced composition.
    """
    from carbon.scoring import pool_exam

    _need(type(basis) is dict and basis.get("gated") is False, "entry_gated")
    gens = []
    d_sets = []
    for targets in basis["sets"]:
        have = [t["agen"] for t in targets if t["agen"] is not None]
        gens.append(statistics.fmean(have) if have else None)
        d_sets.append(statistics.fmean(t["d"] for t in targets))
    total = pool_exam.total_of_targets(basis, basis["sets"])
    return {
        "a_bank": basis["a_bank"],
        "c": basis["c"],
        "a_rule": dict(basis["a_rule"]),
        "a_gen_sets": gens,
        "d_sets": d_sets,
        "basis_total": basis["total"],
        "plain_total": total,
        "combo": dict(combo),
    }


def a_total(record, *, mode="both"):
    """A as the pack combines it: per set ``combine_a(A_bank, A_gen)``, averaged over the sets (``mode`` 'both'); 'bank' uses A_bank
    alone, 'gen' the A_gen per set alone (every other leg unchanged)."""
    from carbon.scoring import pool_grader

    values = []
    for gen in record["a_gen_sets"]:
        if mode == "bank":
            values.append(record["a_bank"])
        elif mode == "gen":
            values.append(gen if gen is not None else record["a_bank"])
        else:
            values.append(
                pool_grader.combine_a(record["a_bank"], gen, record["a_rule"])
            )
    return statistics.fmean(values)


def d_total(record):
    return statistics.fmean(min(d, record["c"]) for d in record["d_sets"])


def total_with(record, *, mode="both"):
    return pack_total(record["combo"], a_total(record, mode=mode), d_total(record))


def crown(rows, *, mode="both"):
    """The index of the highest total (ties keep the first, the incumbent order of ``rows``)."""
    best = 0
    for i, row in enumerate(rows):
        if total_with(row, mode=mode) > total_with(rows[best], mode=mode):
            best = i
    return best


# ---------------------------------------------------------------- Q3 and Q8 (pure on records)


def q3(records, *, top=5):
    """Q3 for one Challenge from its scored entries' decompositions (each ``{"hotkey", "record"}``)."""
    _need(len(records) >= 2, "q3_needs_two_entries")
    bank = [r["record"]["a_bank"] for r in records]
    gen = [a_total(r["record"], mode="gen") for r in records]
    rho, interval = bootstrap_rho(bank, gen)
    ranked = sorted(records, key=lambda r: total_with(r["record"]), reverse=True)
    leaders = [
        {
            "hotkey": r["hotkey"],
            "bank": r["record"]["a_bank"],
            "gen": a_total(r["record"], mode="gen"),
        }
        for r in ranked[:top]
    ]
    flips, pairs = flipped_pairs(leaders, "bank", "gen")
    rows = [r["record"] for r in ranked]
    king = crown(rows)
    return {
        "n": len(records),
        "rho": rho,
        "ci": interval,
        "flipped_pairs": flips,
        "pairs": pairs,
        "king": ranked[king]["hotkey"],
        "crown_flip_bank_only": ranked[crown(rows, mode="bank")]["hotkey"]
        != ranked[king]["hotkey"],
        "crown_flip_gen_only": ranked[crown(rows, mode="gen")]["hotkey"]
        != ranked[king]["hotkey"],
        "crown_if_bank_only": ranked[crown(rows, mode="bank")]["hotkey"],
        "crown_if_gen_only": ranked[crown(rows, mode="gen")]["hotkey"],
    }


def quantile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def two_sig(value):
    return None if value is None else float(f"{value:.1e}")


def q8(entries, slack, *, top=5):
    """Q8 for one Challenge. ``entries`` are ``{"hotkey", "total", "gates": {name: bool}}`` (SCORED and GATED alike);
    ``slack(entry, gate)`` is the gate's own signed pass margin m (m >= 0 passes) or None when the gate exposes none. Per gate:
    quantiles of m over all entries and over the top entries, the near-gate and failing counts, the king's m rounded to 2
    significant figures. A gate with no exposed margin reports ``slack_exposed: false`` and its pass/fail counts only.
    """
    names = sorted({g for e in entries for g in e["gates"]})
    ranked = sorted(
        (e for e in entries if e["total"] is not None),
        key=lambda e: e["total"],
        reverse=True,
    )
    leaders = ranked[:top]
    king = ranked[0] if ranked else None
    out = {}
    for name in names:
        margins = {e["hotkey"]: slack(e, name) for e in entries if name in e["gates"]}
        exposed = any(m is not None for m in margins.values())
        failing = sum(1 for e in entries if e["gates"].get(name) is False)
        row = {"slack_exposed": exposed, "fail_count": failing}
        if exposed:
            values = [m for m in margins.values() if m is not None]
            top_values = [
                margins[e["hotkey"]]
                for e in leaders
                if margins.get(e["hotkey"]) is not None
            ]
            row.update(
                {
                    "q05": quantile(values, 0.05),
                    "q25": quantile(values, 0.25),
                    "q50": quantile(values, 0.50),
                    "top5_q05": quantile(top_values, 0.05),
                    "near_count": sum(1 for m in values if 0 <= m < 0.10),
                    "fail_count": sum(1 for m in values if m < 0),
                    "king_m": two_sig(margins.get(king["hotkey"])) if king else None,
                }
            )
        row["king_passes"] = king["gates"].get(name) if king else None
        out[name] = row
    return out


# ---------------------------------------------------------------- the what-if (pure on decompositions)


def balanced_d_sets(record):
    """D per set under ``balanced_region_mean`` from the per-target d and the per-target region classes the record carries."""
    out = []
    for targets in record["targets"]:
        by = {}
        for t in targets:
            by.setdefault(t["cls"], []).append(t["d"])
        out.append(statistics.fmean(statistics.fmean(v) for v in by.values()))
    return out


def total_from_targets(record, *, balanced):
    """The exam's composition from per-target values: per set A = combine_a(A_bank, mean A_gen), D = plain mean d or the balanced
    class mean, D capped by C; total = the pack's combination of mean(A) and mean(D)."""
    from carbon.scoring import pool_grader

    a_values, d_values = [], []
    d_balanced = balanced_d_sets(record) if balanced else None
    for index, targets in enumerate(record["targets"]):
        gens = [t["agen"] for t in targets if t["agen"] is not None]
        gen = statistics.fmean(gens) if gens else None
        a_values.append(pool_grader.combine_a(record["a_bank"], gen, record["a_rule"]))
        d = d_balanced[index] if balanced else statistics.fmean(t["d"] for t in targets)
        d_values.append(min(d, record["c"]))
    return pack_total(
        record["combo"], statistics.fmean(a_values), statistics.fmean(d_values)
    )


def class_bootstrap(record, *, resamples=RESAMPLES, seed=SEED):
    """The spread (standard deviation) of each class mean of d and of the balanced total under a bootstrap of TARGETS within each
    class of each set (the set structure kept), ``resamples`` resamples, the registered seed. Aggregates only.

    A set with NO targets (every target of it dropped, e.g. at a DV-CURVE budget where none is anchored) has no balanced total, so
    nothing is resampled: the result says ``unresolved: set_without_targets`` with the per-set counts and no spread (TL 3 Nov 09:46:
    the dvcurve crashed on the empty mean). Never a zero spread.
    """
    import numpy as np

    if not record["targets"] or any(not targets for targets in record["targets"]):
        return {
            "resamples": 0,
            "seed": seed,
            "targets_per_set": [len(targets) for targets in record["targets"]],
            "targets_per_class": {},
            "class_mean_sd": None,
            "total_sd": None,
            "unresolved": "set_without_targets",
        }
    generator = np.random.Generator(np.random.PCG64(seed))
    classes = sorted({t["cls"] for targets in record["targets"] for t in targets})
    means = {c: [] for c in classes}
    totals = []
    for _ in range(resamples):
        drawn = []
        for targets in record["targets"]:
            resampled = []
            for c in classes:
                members = [t for t in targets if t["cls"] == c]
                if not members:
                    continue
                order = generator.choice(len(members), size=len(members), replace=True)
                resampled += [members[int(i)] for i in order]
            drawn.append(resampled)
        sample = {**record, "targets": drawn}
        for c in classes:
            ds = [t["d"] for targets in drawn for t in targets if t["cls"] == c]
            means[c].append(statistics.fmean(ds))
        totals.append(total_from_targets(sample, balanced=True))
    return {
        "resamples": resamples,
        "seed": seed,
        "targets_per_class": {
            c: [
                sum(1 for t in targets if t["cls"] == c)
                for targets in record["targets"]
            ]
            for c in classes
        },
        "class_mean_sd": {
            c: float(np.std(np.asarray(v), ddof=1)) for c, v in means.items()
        },
        "total_sd": float(np.std(np.asarray(totals), ddof=1)),
    }


def gap(king_total, baseline_total):
    return king_total - baseline_total


def paired_gaming(entry_total, control_total):
    """The suite's rule: a control built from the entry's own predictions plus a bias gains nothing (control <= entry)."""
    return {"gain": control_total - entry_total, "holds": control_total <= entry_total}


# ---------------------------------------------------------------- the re-grade route (custody only)


def read_bodies(store_path):
    """Every stored private evaluation body, oldest first, from a READ-ONLY connection to the pool store."""
    connection = sqlite3.connect(
        f"file:{Path(store_path).as_posix()}?mode=ro", uri=True
    )
    try:
        rows = connection.execute(
            "SELECT body FROM operations WHERE kind='private_evaluation.v1' "
            "AND state='BOUND_DEVELOPMENT_ONLY' ORDER BY rowid"
        ).fetchall()
    finally:
        connection.close()
    out = []
    for (raw,) in rows:
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def _hotkey(owner):
    if type(owner) is dict:
        owner = owner.get("hotkey")
    return owner if type(owner) is str and owner else None


def _pairs_by_sha(task_roots):
    """``{"sha256:<hex>": path}`` of every retained ``<task>.evaluation/inference-pair.json`` directly under ``task_roots``. A
    re-prepare re-grades an entry under a NEW task id (`lean_recipe_retention`, regrade-provenance), so its pair is found by the
    sha256 its stored body binds (``evidence.inference_pair_sha256``), never by a guessed path.
    """
    found = {}
    for root in task_roots:
        for path in sorted(Path(root).glob("*.evaluation/inference-pair.json")):
            if path.is_file():
                found.setdefault("sha256:" + _sha(path.read_bytes()), path)
    return found


def _pair_of(evidence, sid, task_roots, by_sha):
    """The entry's retained pair: the file its body binds by sha256 when it binds one (the ``<sid>.evaluation`` file only when
    its bytes are those), else the ``<sid>.evaluation`` file. ``(path_or_None, found_by_sha)``.
    """
    bound = evidence.get("inference_pair_sha256")
    direct = None
    for root in task_roots:
        candidate = Path(root) / f"{sid}.evaluation" / "inference-pair.json"
        if candidate.is_file():
            direct = candidate
            break
    if type(bound) is not str:
        return direct, False
    if direct is not None and "sha256:" + _sha(direct.read_bytes()) == bound:
        return direct, False
    found = by_sha.get(bound)
    return found, found is not None


def enumerate_entries(bodies, config, task_roots):
    """The current exam's entries: one per (hotkey, submission), the LATEST per hotkey x recipe digest once the retained pair names
    the recipe; ``scored`` for SCORED_DEVELOPMENT_CANDIDATE, ``gated`` for the others. Each carries the retained pair's path when
    one exists under ``task_roots`` (`_pair_of`: by the sha256 the body binds, so a re-graded entry's pair under its regrade task
    id is found). Returns ``(entries, coverage)`` (counts only)."""
    by_sha = None
    latest = {}
    for body in bodies:
        evidence = body.get("evidence")
        model = evidence.get("model_p") if type(evidence) is dict else None
        if (
            type(model) is not dict
            or evidence.get("challenge") != config["challenge"]
            or evidence.get("evaluation_version") != config["evaluation_version"]
        ):
            continue
        hotkey, sid = _hotkey(body.get("owner")), body.get("submission_id")
        if hotkey is None or type(sid) is not str:
            continue
        if by_sha is None and type(evidence.get("inference_pair_sha256")) is str:
            by_sha = _pairs_by_sha(task_roots)
        pair, via_sha = _pair_of(evidence, sid, task_roots, by_sha)
        recipe = None
        if pair is not None:
            try:
                recipe = json.loads(pair.read_bytes()).get("recipe_digest")
            except (OSError, ValueError):
                recipe = None
        latest[(hotkey, recipe if recipe is not None else sid)] = {
            "hotkey": hotkey,
            "submission_id": sid,
            "recipe_digest": recipe,
            "status": model.get("score_status"),
            "total": (
                model.get("total_score")
                if type(model.get("total_score")) is float
                else None
            ),
            "pair": pair,
            "pair_by_sha": via_sha,
        }
    entries = list(latest.values())
    coverage = {
        "entries": len(entries),
        "with_pair": sum(1 for e in entries if e["pair"] is not None),
        "without_pair": sum(1 for e in entries if e["pair"] is None),
        "pair_found_by_bound_sha": sum(1 for e in entries if e["pair_by_sha"]),
        "scored": sum(
            1 for e in entries if e["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
        ),
    }
    return entries, coverage


@contextlib.contextmanager
def _patched_item(mapping, key, value):
    original = mapping[key]
    mapping[key] = value
    try:
        yield
    finally:
        mapping[key] = original


@contextlib.contextmanager
def _patched(owner, name, value):
    original = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, original)


#: The reads that grade the baseline (q3 ranks against it; the what-if's gap, s_h and controls use it). q8 does not.
NEEDS_BASELINE = ("q3", "whatif", "dvcurve")


def _needs_baseline(config, read):
    """A read that uses the baseline refuses a config whose baseline is null, by name."""
    _need(
        read not in NEEDS_BASELINE or config["baseline_predictions"] is not None,
        f"baseline_predictions_null_refused_for_{read}",
    )


class Regrader:
    """Grades rows through the receiver's own route with optional overrides; holds one sealed set (`pool_binding._load_set`)."""

    def __init__(self, config, loader=None):
        import pool_binding

        self.config = config
        self.binding = pool_binding
        spec = {
            "pack_root": config["pack_root"],
            "baseline_predictions": config["baseline_predictions"],
        }
        real = loader is None
        loader = loader or pool_binding._load_set
        with contextlib.ExitStack() as stack:
            if config["baseline_predictions"] is None:
                # no baseline pair (a q8-only read): the set loads without one; nothing reads `base_rows`
                stack.enter_context(
                    _patched(
                        pool_binding, "read_baseline", lambda *a, **k: (None, None)
                    )
                )
            self.graded, self.inputs, _snapshot = loader(
                spec,
                {
                    "challenge": config["challenge"],
                    "version": config["version"],
                    "copy_hotkey": config["copy_hotkey"],
                },
            )
        self.no_baseline_width = None
        if self.graded.base_rows is None:
            from carbon.challenge_kit import physical_material

            # the width the loader reads the baseline at (the interface's output shape)
            self.no_baseline_width = tuple(
                physical_material.bundle_material(
                    config["challenge"], config["version"]
                )["expected_output_shape"]
            )[1]
        if real:
            # the receiver's retained query is in the practice inputs' dtype (as the leak attack's loader reads it)
            from carbon.challenge_kit import physical_material

            self.input_dtype = physical_material.bundle_material(
                config["challenge"], config["version"]
            )["practice_inputs"].dtype
        else:
            import numpy as np

            self.input_dtype = np.asarray(self.graded.bank["inputs"]).dtype
        self.pack = self.graded.roles["score_pack"]
        self.combo = {
            "combination": self.pack["combination"],
            "value_weight": self.pack["value_weight"],
        }
        from carbon.scoring import pool_grader, pool_version

        material = self.graded.bank[pool_version.POOL_KEY]
        self.all_specs = tuple(
            pool_grader.load_pool(document)
            for group in material["sets"]
            for document in group
        )

    def rows_of(self, pair_path):
        """The entry's retained primary predictions for this set's bank (the pair reader checks the inputs digest, the
        primary == repeat bytes, and that it is a pair), as the receiver hands them to ``measure``: lists of Python floats
        (its ``predictions.json`` decoded), never numpy rows. A gate that types its answer (Motor's ``schema_finite``
        takes ``int``/``float`` only) fails every numpy scalar, so numpy rows would gate every entry on ``physics_pool``.
        """
        import numpy as np

        graded = self.graded
        if graded.base_rows is not None:
            width, dtype = len(graded.base_rows[0]), graded.base_rows.dtype
        else:  # no baseline (q8 only): a pair's rows are read as floats whatever the dtype
            width, dtype = self.no_baseline_width, np.dtype(float)
        return self.binding.read_baseline(
            pair_path,
            len(graded.bank["inputs"]),
            width,
            dtype,
            inputs_digest=self.binding.inputs_digest(
                graded.bank["inputs"], self.input_dtype
            ),
        )[0].tolist()

    def grade(
        self,
        rows,
        entry_id,
        *,
        policies=None,
        classes=None,
        errors=None,
        agen_points=None,
        bias=None,
        slacks=False,
        minimums=None,
        anchors=None,
    ):
        """One regrade. Returns ``{"status", "gates", "basis", "total"}``; ``basis`` is ``measure_pool``'s capture (None when the
        entry is gated). ``policies`` replaces the registered ones; ``classes`` maps a target id to its region class; ``errors`` (a
        list) receives each graded target's pick error e in order; ``agen_points`` (a list) receives each A_gen point as
        {target_id, conditions, design, atom} (ACC-NOISE-01: the atom is the grader's own benefit, averaged over the outputs, of
        the very predictions `pool_grader.agen_accuracy` scored, the grade unchanged); ``bias`` wraps the model in the suite's ``biased`` control.
        ``anchors`` ({target_id: s_low}) replaces those targets' D zero point for this grade only (DV-CURVE-01: the shortcut's
        anchor; the grader's own q formula is unchanged). ``minimums`` ({leg: value or None}) replaces the score pack's leg minimums for this grade only (R26 / E8: under a candidate
        rule set they are the baseline's own legs under that set; None lifts a minimum). ``slacks`` adds ``"physics_slack"``: `gate_slack.entry_summary` of the pool answers exactly as the physics_pool gate
        received them (the live `pool_gates.failed_gates` still decides the verdict; the summary only reads beside it).
        """
        from carbon.scoring import (
            pool_exam,
            pool_gates,
            pool_grader,
            pool_plugin,
            pool_version,
        )
        from carbon.scoring import pool_proof_suite as suite

        capture = {}
        adapter = self.graded.adapter
        original_measure = adapter.measure

        def measure(**kwargs):
            return original_measure(capture=capture, **kwargs)

        stack = contextlib.ExitStack()
        with stack:
            stack.enter_context(_patched(adapter, "measure", measure))
            if policies is not None:
                stack.enter_context(
                    _patched(
                        pool_version, "registered_policies", lambda *a, **k: policies
                    )
                )
            if classes is not None:
                stack.enter_context(
                    _patched(
                        pool_grader,
                        "region_class",
                        lambda spec, plan=None: classes[spec.target_id],
                    )
                )
            if errors is not None:
                real = pool_grader.grade_set

                def recording(specs, predict, optimizer, honesty):
                    grade = real(specs, predict, optimizer, honesty)
                    errors.extend(t.e for t in grade.targets)
                    return grade

                stack.enter_context(_patched(pool_grader, "grade_set", recording))
            if agen_points is not None:
                stack.enter_context(
                    _patched(
                        pool_grader,
                        "agen_accuracy",
                        _recording_agen(pool_grader, agen_points),
                    )
                )
            if bias is not None:
                real_predictor = pool_plugin.pool_predictor

                def biased(submitted, serve):
                    honest = real_predictor(submitted, serve)
                    shell = type("Shell", (), {"good_model": staticmethod(honest)})
                    return suite.pool_predictor(
                        shell,
                        {
                            "kind": "biased",
                            "base": {"kind": "good"},
                            "bias": dict(bias),
                        },
                        self.all_specs,
                    )

                stack.enter_context(
                    _patched(pool_exam.pool_plugin, "pool_predictor", biased)
                )
            if anchors:
                real_load = pool_grader.load_pool

                def anchored(document):
                    spec = real_load(document)
                    value = anchors.get(spec.target_id)
                    return (
                        spec
                        if value is None
                        else dataclasses.replace(spec, s_low=value)
                    )

                stack.enter_context(_patched(pool_grader, "load_pool", anchored))
            if minimums is not None:
                pack = candidate_score_pack(self.graded.roles["score_pack"], minimums)
                stack.enter_context(
                    _patched_item(self.graded.roles, "score_pack", pack)
                )
            gated_answers = []
            if slacks:
                real_failed = pool_gates.failed_gates

                def recording_gates(binding, pool_rows, raw_rows):
                    gated_answers.append((binding.physics_gates, pool_rows, raw_rows))
                    return real_failed(binding, pool_rows, raw_rows)

                stack.enter_context(
                    _patched(pool_gates, "failed_gates", recording_gates)
                )
            aggregates = self.graded.graded(
                infer=lambda _inputs: rows, entry_id=entry_id
            )
        status, total, legs, gates, _reason = self.binding._status_and_values(
            aggregates, self.pack
        )
        result = {
            "status": status,
            "gates": gates,
            "total": total,
            "legs": legs,
            "basis": capture.get("se_basis"),
        }
        if slacks:
            import gate_slack

            # one measure per grade: the graded run's answers, never a repeat's
            _need(len(gated_answers) == 1, "slack_capture_count")
            result["physics_slack"] = gate_slack.entry_summary(*gated_answers[0])
        return result

    def sets_and_classes(self):
        """The pool's targets in order, per set, with their REGISTERED region class (`pool_grader.region_class`: an
        extended target, the one with an OOD shell, is ``extended_shell``, every other ``in_train``):
        ``({target_id: class}, [[target_id...]...])``. Read from the pack's pool material, never printed; nothing is assumed
        about how many targets a set has or where its extended ones sit."""
        from carbon.scoring import pool_grader, pool_version

        material = self.graded.bank[pool_version.POOL_KEY]
        classes, order = {}, []
        for group in material["sets"]:
            ids = []
            for document in group:
                spec = pool_grader.load_pool(document)
                classes[spec.target_id] = pool_grader.region_class(spec)
                ids.append(spec.target_id)
            order.append(ids)
        return classes, order


def with_targets(basis, record, order, classes):
    """Attach per-target (d, agen, class) to a decomposition from the capture's per-set target lists (same order as the pool
    material's targets)."""
    targets = []
    for ids, sets in zip(order, basis["sets"], strict=True):
        _need(len(ids) == len(sets), "targets_differ_from_the_pool_material")
        targets.append(
            [
                {"d": t["d"], "agen": t["agen"], "cls": classes[tid]}
                for tid, t in zip(ids, sets, strict=True)
            ]
        )
    return {**record, "targets": targets}


def scaled_policies(registered, *, pick_k, s_h, agen_factor):
    optimizer = dataclasses.replace(
        registered.optimizer,
        pick_rule={"kind": "top_k", "k": pick_k},
        d_aggregate="balanced_region_mean",
    )
    honesty = dataclasses.replace(registered.honesty, scale=s_h)
    agen = {k: v * agen_factor for k, v in registered.agen_scales.items()}
    return dataclasses.replace(
        registered, optimizer=optimizer, honesty=honesty, agen_scales=agen
    )


def candidate_score_pack(registered, minimums):
    """The registered score pack with ``minimums`` ({leg: value or None}) as its leg minimums, RE-PINNED by the pack writer's own
    `dual_score.register_pack` (Validator 11-01): ``pack_digest`` is the candidate body's, so `dual_score.score`'s own pack-digest
    check holds, unweakened. The registered pack is verified first (it must be exactly its own registration), so only a
    verified pack is ever substituted. Raises `dual_score.DualScoreRefused` when the candidate body is not a registrable pack
    (for example minimums whose total is above the pack's registered ``baseline_floor_total``).
    """
    from carbon.scoring import dual_score

    body = {k: v for k, v in registered.items() if k != "pack_digest"}
    _need(
        type(registered) is dict and dual_score.register_pack(body) == registered,
        "registered_score_pack_is_not_its_own_registration",
    )
    body = copy.deepcopy(body)
    for leg, value in minimums.items():
        _need(leg in body["legs"], f"minimum_for_an_unknown_leg:{leg}")
        body["legs"][leg]["minimum"] = value
    return dual_score.register_pack(body)


def _recording_agen(pool_grader, sink):
    """`pool_grader.agen_accuracy` unchanged, recording each A_gen point's atom from the predictions it scored (one predict call
    per target with a slice, in spec order, as the grader makes them). measure_pool scores A_gen per SET and then calls it again per
    target for its capture: each (target, point) is kept ONCE, and a repeat that scores it differently STOPS.
    """
    import statistics

    real = pool_grader.agen_accuracy
    seen = {}

    def recording(specs, predict, scales, **kwargs):
        calls = []

        def tap(conditions, designs):
            batch = predict(conditions, designs)
            calls.append(batch)
            return batch

        value = real(specs, tap, scales, **kwargs)
        with_slice = [spec for spec in specs if spec.agen]
        _need(len(calls) == len(with_slice), "agen_predict_calls_differ")
        for spec, batch in zip(with_slice, calls, strict=True):
            for index, prediction in zip(spec.agen, batch, strict=True):
                atoms = [
                    pool_grader.benefit(
                        abs(prediction[k] - spec.truths[index][k]) / scales[k]
                    )
                    for k in spec.outputs
                ]
                atom = statistics.fmean(atoms)
                key = (spec.target_id, index)
                if key in seen:
                    _need(seen[key] == atom, "agen_point_scored_twice_differently")
                    continue
                seen[key] = atom
                sink.append(
                    {
                        "target_id": spec.target_id,
                        "conditions": spec.conditions,
                        "design": list(spec.designs[index]),
                        "atom": atom,
                    }
                )
        return value

    return recording


def baseline_minimums(regrader, base_rows, policies, classes):
    """R26 / E8 (Validator 11-01): under a candidate rule set the leg minimums ARE the baseline's own legs measured under that set.
    Grades the baseline with every minimum lifted; returns ``(minimums, None)``, or ``(None, failure)`` when the baseline itself is
    not scored under the set (its failed gate names: then the set cannot be graded consistently, and the report says why).
    """
    lifted = {leg: None for leg in regrader.pack["legs"]}
    result = regrader.grade(
        base_rows,
        "sha256:" + _sha(b"baseline-legs"),
        policies=policies,
        classes=classes,
        minimums=lifted,
    )
    if result["status"] != "SCORED":
        failed = sorted(name for name, ok in (result["gates"] or {}).items() if not ok)
        return None, {"status": result["status"], "failed_gates": failed}
    minimums = {leg: float(result["legs"][leg]) for leg in lifted}
    from carbon.scoring import dual_score

    try:
        candidate_score_pack(regrader.graded.roles["score_pack"], minimums)
    except dual_score.DualScoreRefused as refused:
        # the rule set's own minimums do not make a registrable pack: a typed failure of THIS set, never a crash
        return None, {"status": "PACK_REFUSED", "code": str(refused)}
    return minimums, None


def measured_entries(
    regrader,
    entries,
    *,
    policies=None,
    classes=None,
    order=None,
    slacks=False,
    minimums=None,
):
    """Regrade every entry that has a retained pair; returns ``[{"hotkey", "record" | None, "gates", "status", "total"}]`` and the
    count graded."""
    out = []
    for e in entries:
        if e["pair"] is None:
            continue
        result = regrader.grade(
            regrader.rows_of(e["pair"]),
            "sha256:"
            + _sha(_canonical([e["hotkey"], e["recipe_digest"], e["submission_id"]])),
            policies=policies,
            classes=classes,
            slacks=slacks,
            minimums=minimums,
        )
        record = None
        if result["basis"] is not None and result["basis"].get("gated") is False:
            record = decompose(result["basis"], regrader.combo)
            if classes is not None:
                record = with_targets(result["basis"], record, order, classes)
        out.append({"hotkey": e["hotkey"], "recipe": e["recipe_digest"], "regraded_total": result["total"],
                    "gates": result["gates"], "status": result["status"], "record": record,
                    "stored_total": e["total"], "stored_status": e["status"],
                    "physics_slack": result.get("physics_slack")})  # fmt: skip
    return out


def run_digest(output, config_path, script_path):
    return "sha256:" + _sha(
        _canonical(
            {
                "output": output,
                "config_sha256": _sha(Path(config_path).read_bytes()),
                "script_sha256": _sha(Path(script_path).read_bytes()),
            }
        )
    )


def _check_regrade_matches(graded, tolerance=1e-9):
    """The regrade of an entry must reproduce its stored status and total (so the route is the receiver's own); a
    mismatch STOPS. A stored SCORED entry regraded as gated (or the reverse) is a mismatch even though one side has no
    total: the code names the regraded status and its failed gates (names only)."""
    for g in graded:
        stored_scored = g["stored_status"] == "SCORED_DEVELOPMENT_CANDIDATE"
        if stored_scored != (g["status"] == "SCORED"):
            failed = sorted(name for name, ok in (g["gates"] or {}).items() if not ok)
            raise ReadRefused(
                "regrade_does_not_reproduce_the_stored_status:"
                f"{g['stored_status']}->{g['status']}:{','.join(failed)}"
            )
        if g["stored_total"] is None or g["regraded_total"] is None:
            continue
        _need(
            abs(g["stored_total"] - g["regraded_total"]) <= tolerance,
            "regrade_does_not_reproduce_the_stored_total",
        )


def _check_composition(graded, tolerance=1e-9):
    """The recomposed total (the pack's own combination of the legs) must reproduce the graded total of every scored entry."""
    for g in graded:
        if g["record"] is not None and g["status"] == "SCORED":
            _need(
                abs(total_with(g["record"]) - g["regraded_total"]) <= tolerance,
                "recomposed_total_differs_from_the_graded_total",
            )


def run_q3(config, config_path):
    _needs_baseline(config, "q3")
    regrader = Regrader(config)
    bodies = read_bodies(config["store"])
    entries, coverage = enumerate_entries(bodies, config, config["task_roots"])
    graded = measured_entries(regrader, entries)
    _check_regrade_matches(graded)
    _check_composition(graded)
    scored = [g for g in graded if g["record"] is not None and g["status"] == "SCORED"]
    result = {
        "challenge": config["challenge"],
        "coverage": coverage,
        "q3": q3(scored, top=config["top"]),
    }
    return {**result, "run_digest": run_digest(result, config_path, __file__)}


def physics_laws(graded, top=5):
    """Per physics_pool law, over the entries' `gate_slack.entry_summary`: quantiles of each entry's minimum m (where the
    law has a registered scale) and of its minimum RAW slack, the near-gate and failing entry counts, and the answer
    counts per band summed over entries and for the king. Aggregates only."""
    ranked = sorted(
        (g for g in graded if g["status"] == "SCORED"),
        key=lambda g: g["regraded_total"],
        reverse=True,
    )
    king = ranked[0] if ranked else None
    leaders = {g["hotkey"] for g in ranked[:top]}
    names = sorted(
        {n for g in graded if g["physics_slack"] for n in g["physics_slack"]["laws"]}
    )
    out = {}
    for name in names:
        held = [
            (g, g["physics_slack"]["laws"][name])
            for g in graded
            if g["physics_slack"] and g["physics_slack"]["laws"].get(name)
        ]
        scaled = [(g, h["m_min"]) for g, h in held if h["m_min"] is not None]
        unscaled = any(h["unscaled"] for _g, h in held)
        raw = [h["slack_min"] for _g, h in held]
        row = {
            "entries": len(held),
            "scale": "no registered scale" if unscaled else "registered",
            "raw_slack_q05": quantile(raw, 0.05),
            "raw_slack_q50": quantile(raw, 0.50),
            "fail_count": sum(1 for _g, h in held if h["fail"]),
            "answers": {
                band: sum(h[band] for _g, h in held)
                for band in ("answers", "fail", "near", "unscaled")
            },
        }
        if scaled and not unscaled:
            values = [m for _g, m in scaled]
            row.update(
                {
                    "q05": quantile(values, 0.05),
                    "q25": quantile(values, 0.25),
                    "q50": quantile(values, 0.50),
                    "top5_q05": quantile(
                        [m for g, m in scaled if g["hotkey"] in leaders], 0.05
                    ),
                    "near_count": sum(1 for m in values if 0 <= m < NEAR_GATE),
                }
            )
        mine = (
            king and king["physics_slack"] and king["physics_slack"]["laws"].get(name)
        )
        row["king"] = (
            None
            if not mine
            else {
                "m": two_sig(mine["m_min"]) if mine["m_min"] is not None else None,
                "fail": mine["fail"],
                "near": mine["near"],
                "answers": mine["answers"],
            }
        )
        out[name] = row
    return out


def run_q8(config, config_path):
    import gate_slack

    from carbon.scoring import pool_grader

    regrader = Regrader(config)
    bodies = read_bodies(config["store"])
    entries, coverage = enumerate_entries(bodies, config, config["task_roots"])
    graded = measured_entries(regrader, entries, slacks=True)
    _check_regrade_matches(graded)
    rows = [
        {
            "hotkey": g["hotkey"],
            "total": g["regraded_total"] if g["status"] == "SCORED" else None,
            "gates": g["gates"],
            "physics_slack": g["physics_slack"],
        }
        for g in graded
    ]

    # physics_pool exposes its slack through `gate_slack` (the min m over its laws and answers, where every law it answered
    # has a registered scale); the sealed grader's native gates and the boolean/coverage gates expose none.
    def slack(entry, gate):
        if gate != PHYSICS_POOL or entry["physics_slack"] is None:
            return None
        return gate_slack.physics_pool_m(entry["physics_slack"])

    result = {
        "challenge": config["challenge"],
        "coverage": coverage,
        "q8": q8(rows, slack, top=config["top"]),
        "physics_pool_laws": physics_laws(graded, top=config["top"]),
        "near_limit_designs": gate_slack.near_limit_counts(
            regrader.all_specs, pool_grader.region_class
        ),
    }
    return {**result, "run_digest": run_digest(result, config_path, __file__)}


def run_whatif(config, config_path):
    from carbon.scoring import pool_version

    _needs_baseline(config, "whatif")
    regrader = Regrader(config)
    classes, order = regrader.sets_and_classes()
    bodies = read_bodies(config["store"])
    entries, coverage = enumerate_entries(bodies, config, config["task_roots"])
    registered = pool_version.registered_policies(
        config["challenge"], config["version"]
    )
    old = measured_entries(regrader, entries, classes=classes, order=order)
    _check_regrade_matches(old)
    _check_composition(old)
    scored = sorted(
        (g for g in old if g["record"] is not None and g["status"] == "SCORED"),
        key=lambda g: g["regraded_total"],
        reverse=True,
    )
    _need(scored, "no_scored_entries_with_a_retained_pair")
    leaders = scored[: config["top"]]
    king = scored[0]
    # the baseline's rows as the receiver hands rows to `measure` (Python floats; see `Regrader.rows_of`)
    base_rows = regrader.graded.base_rows.tolist()
    # s_h: the baseline's median per-target pick error e under the new pick rule (e does not depend on s_h)
    errors = []
    probe = scaled_policies(
        registered, pick_k=config["pick_k"], s_h=PLACEHOLDER_S_H, agen_factor=1.0
    )
    regrader.grade(
        base_rows,
        "sha256:" + _sha(b"baseline-e"),
        policies=probe,
        classes=classes,
        errors=errors,
    )
    _need(errors and all(math.isfinite(e) for e in errors), "baseline_errors_unusable")
    median_e = statistics.median(errors)
    s_h = config["s_h_fraction"] * median_e
    report = {
        "challenge": config["challenge"],
        "version": config["version"],
        "coverage": coverage,
        "s_h": {"fraction": config["s_h_fraction"], "baseline_median_e": median_e, "value": s_h,
                "e_list_sha256": _sha(json.dumps([repr(float(e)) for e in errors]).encode()), "targets": len(errors)},
        "margin_n": config["margin_n"],
        # the material's registered region classes, as counts only (which targets: never)
        "region_classes": {c: sum(1 for v in classes.values() if v == c) for c in sorted(set(classes.values()))},
        "records": config["records"],
        "old_rules": {},
        "new_rules": {},
    }  # fmt: skip

    def summarise(label, graded_rows, policies, *, balanced, minimums=None):
        """gap, paired gaming for the king and the top entries, class bootstrap for the king."""
        base = regrader.grade(
            base_rows,
            "sha256:" + _sha(b"baseline"),
            policies=policies,
            classes=classes,
            minimums=minimums,
        )
        _need(base["status"] == "SCORED", "baseline_not_scored")
        gap_value = gap(graded_rows[0]["regraded_total"], base["total"])
        gaming = []
        for g in graded_rows:
            for control_spec in config["gaming"]:
                control = regrader.grade(
                    regrader.rows_of(pair_of[g["hotkey"], g["recipe"]]),
                    "sha256:"
                    + _sha(
                        b"biased" + _canonical([g["hotkey"], g["recipe"], control_spec])
                    ),
                    policies=policies,
                    classes=classes,
                    bias=control_spec,
                    minimums=minimums,
                )
                row = {"hotkey": g["hotkey"], "control": control_spec["mode"]}
                if control["status"] != "SCORED":
                    # a control that fails a gate or is not scored gains nothing
                    gaming.append(
                        {
                            **row,
                            "status": control["status"],
                            "holds": True,
                            "gain": None,
                        }
                    )
                else:
                    gaming.append(
                        {**row, **paired_gaming(g["regraded_total"], control["total"])}
                    )
        out = {
            "crown_minus_baseline": gap_value,
            "king": graded_rows[0]["hotkey"],
            "paired_gaming": gaming,
            "paired_gaming_holds": all(x["holds"] for x in gaming),
        }
        if balanced:
            out["class_bootstrap"] = class_bootstrap(graded_rows[0]["record"])
            out["class_bootstrap"]["margin_n"] = config["margin_n"]
        return out

    pair_of = {
        (e["hotkey"], e["recipe_digest"]): e["pair"]
        for e in entries
        if e["pair"] is not None
    }
    report["old_rules"] = summarise("old", leaders, registered, balanced=False)
    for factor in config["agen_factors"]:
        policies = scaled_policies(
            registered, pick_k=config["pick_k"], s_h=s_h, agen_factor=factor
        )
        key = f"agen_x{factor:g}"
        # R26 / E8: the minimums of THIS rule set are the baseline's legs under it (the old registered ones would be inconsistent)
        minimums, failure = baseline_minimums(regrader, base_rows, policies, classes)
        if failure is not None:
            reason = (
                "candidate_score_pack_refused"
                if failure["status"] == "PACK_REFUSED"
                else "baseline_not_scored_under_these_rules"
            )
            report["new_rules"][key] = {reason: failure}
            continue
        new = measured_entries(
            regrader,
            entries,
            policies=policies,
            classes=classes,
            order=order,
            minimums=minimums,
        )
        usable = sorted(
            (g for g in new if g["record"] is not None and g["status"] == "SCORED"),
            key=lambda g: g["regraded_total"],
            reverse=True,
        )
        _need(usable, "no_scored_entries_under_the_new_rules")
        # the recomposed balanced total must equal the registered grader's: the guard against a drifted composition
        for g in usable:
            _need(
                abs(
                    total_from_targets(g["record"], balanced=True) - g["regraded_total"]
                )
                <= 1e-9,
                "balanced_composition_differs_from_the_grader",
            )
        report["new_rules"][key] = summarise(
            "new", usable[: config["top"]], policies, balanced=True, minimums=minimums
        )
        report["new_rules"][key]["king_old_rules_was"] = king["hotkey"]
        report["new_rules"][key]["leg_minimums_rederived"] = minimums
        report["new_rules"][key]["score_pack_digest"] = {
            "registered": regrader.pack["pack_digest"],
            "candidate": candidate_score_pack(regrader.pack, minimums)["pack_digest"],
        }
    return {**report, "run_digest": run_digest(report, config_path, __file__)}


CURVE_KEYS = frozenset(
    {"budgets", "walls", "coarse", "seed", "class_floor_n", "contenders"}
)


def load_curve(path):
    """The DV-CURVE inputs (every key required; nothing defaulted): ``budgets`` (the candidate B list; B itself stays HUMAN_INPUT),
    ``walls`` {"t_ref", "t_coarse", "rung_records_sha256"} (the MEASURED rung-record medians and the records they came from),
    ``coarse`` (the custody h3 rung outputs per target and design: {target_id: {design_index: {output: value}}}), ``seed`` (the
    shortcut's draw seed, recorded), ``class_floor_n`` (the registered N), ``contenders`` ({name: {"rows_npy", "sha256"}}: extra
    models' raw rows in bank order, e.g. the TRAIN-kernel's)."""
    document = json.loads(Path(path).read_bytes())
    _need(type(document) is dict and set(document) == CURVE_KEYS, "curve_shape")
    budgets = document["budgets"]
    _need(
        type(budgets) is list
        and budgets
        and all(type(b) is int and b >= 1 for b in budgets),
        "curve_budgets",
    )
    walls = document["walls"]
    _need(
        type(walls) is dict
        and set(walls) == {"t_ref", "t_coarse", "rung_records_sha256"}
        and all(
            type(walls[k]) in (int, float) and walls[k] > 0
            for k in ("t_ref", "t_coarse")
        ),
        "curve_walls",
    )
    _need(type(document["seed"]) is int, "curve_seed")
    _need(
        type(document["class_floor_n"]) is int and document["class_floor_n"] >= 1,
        "curve_class_floor_n",
    )
    _need(type(document["contenders"]) is dict, "curve_contenders")
    raw = Path(document["coarse"]).read_bytes()
    coarse = json.loads(raw)
    _need(type(coarse) is dict, "curve_coarse")
    document["coarse_by_target"] = {
        tid: {int(i): row for i, row in rows.items()} for tid, rows in coarse.items()
    }
    document["coarse_sha256"] = _sha(raw)
    return document


def _contender_rows(spec, n_rows):
    import io

    import numpy as np

    _need(type(spec) is dict and set(spec) == {"rows_npy", "sha256"}, "contender_shape")
    raw = Path(spec["rows_npy"]).read_bytes()
    _need(_sha(raw) == spec["sha256"].removeprefix("sha256:"), "contender_rows_changed")
    rows = np.load(io.BytesIO(raw), allow_pickle=False)
    _need(
        rows.ndim == 2 and len(rows) == n_rows and np.isfinite(rows).all(),
        "contender_rows_shape",
    )
    return rows.astype(float).tolist()


def d_dropping(basis, order, dropped, c):
    """D with the dropped (degenerate) targets left out of each set's mean (ruling 4: dropped, never 0); a set left empty is
    skipped. The plain per-set mean and the C cap are `decompose` / `d_total`'s (checked against the grader by _check_composition).
    """
    values = []
    for ids, targets in zip(order, basis["sets"], strict=True):
        kept = [
            t["d"] for tid, t in zip(ids, targets, strict=True) if tid not in dropped
        ]
        if kept:
            values.append(min(statistics.fmean(kept), c))
    return statistics.fmean(values) if values else None


def run_dvcurve(config, config_path, curve_path):
    """DV-CURVE-01 step 1: per candidate B, the shortcut's anchor per target (`dv_curve`), and D for the leaders, the baseline and
    the contenders under the MEDIAN anchor and the SHORTCUT anchor; the crown - baseline gap; paired gaming; the class bootstrap
    spread vs margin_N; per-class counts of shortcut-anchored, no-verified-feasible and degenerate targets; classes below N; and the
    shortcut's own q under the median anchor. Aggregates only."""
    import random

    import dv_curve

    from carbon.scoring import pool_grader

    _needs_baseline(config, "dvcurve")
    curve = load_curve(curve_path)
    regrader = Regrader(config)
    classes, order = regrader.sets_and_classes()
    bodies = read_bodies(config["store"])
    entries, coverage = enumerate_entries(bodies, config, config["task_roots"])
    old = measured_entries(regrader, entries, classes=classes, order=order)
    _check_regrade_matches(old)
    _check_composition(old)
    scored = sorted(
        (g for g in old if g["record"] is not None and g["status"] == "SCORED"),
        key=lambda g: g["regraded_total"],
        reverse=True,
    )
    _need(scored, "no_scored_entries_with_a_retained_pair")
    leaders = scored[: config["top"]]
    pair_of = {
        (e["hotkey"], e["recipe_digest"]): e["pair"]
        for e in entries
        if e["pair"] is not None
    }
    rows_of = {
        f"entry:{g['hotkey']}": regrader.rows_of(pair_of[g["hotkey"], g["recipe"]])
        for g in leaders
    }
    rows_of["baseline"] = regrader.graded.base_rows.tolist()
    n_rows = len(rows_of["baseline"])
    for name, spec in sorted(curve["contenders"].items()):
        rows_of[f"contender:{name}"] = _contender_rows(spec, n_rows)
    specs = regrader.all_specs
    c_of = {}

    def graded(name, anchors=None, bias=None):
        result = regrader.grade(
            rows_of[name],
            "sha256:"
            + _sha(
                _canonical(["dvcurve", name, sorted((anchors or {}).items()), bias])
            ),
            classes=classes,
            anchors=anchors,
            bias=bias,
        )
        return result

    def d_of(result, dropped):
        basis = result["basis"]
        if basis is None or basis.get("gated") is not False:
            return None
        return d_dropping(basis, order, dropped, basis["c"])

    median = {}
    for name in sorted(rows_of):
        result = graded(name)
        median[name] = {"status": result["status"], "D": d_of(result, set())}
        if result["basis"] is not None and result["basis"].get("gated") is False:
            c_of[name] = result["basis"]["c"]
    rng = random.Random(curve["seed"])
    report = {
        "challenge": config["challenge"],
        "version": config["version"],
        "coverage": coverage,
        "margin_n": config["margin_n"],
        "region_classes": {
            c: sum(1 for v in classes.values() if v == c)
            for c in sorted(set(classes.values()))
        },
        "walls": curve["walls"],
        "coarse_sha256": curve["coarse_sha256"],
        "seed": curve["seed"],
        "class_floor_n": curve["class_floor_n"],
        "median_anchor": median,
        "curve": {},
    }
    king = f"entry:{leaders[0]['hotkey']}"
    for budget in curve["budgets"]:
        replace, counts = dv_curve.anchors(
            (config["challenge"], config["version"]), specs, curve["coarse_by_target"], budget,
            curve["walls"]["t_ref"], curve["walls"]["t_coarse"], rng, pool_grader.region_class,
        )  # fmt: skip
        anchored = {tid: value for tid, value in replace.items() if value is not None}
        dropped = {tid for tid, value in replace.items() if value is None}
        point = {
            "targets_by_class": counts,
            "classes_below_n": dv_curve.classes_below_floor(
                counts, curve["class_floor_n"]
            ),
            # why a budget point may have nothing to bootstrap: how many targets it anchored and how many it dropped
            "anchored_n": len(anchored),
            "dropped_n": len(dropped),
        }
        models = {}
        for name in sorted(rows_of):
            result = graded(name, anchors=anchored)
            models[name] = {"status": result["status"], "D": d_of(result, dropped)}
        point["models"] = models
        king_d, base_d = models[king]["D"], models["baseline"]["D"]
        point["crown_minus_baseline_D"] = (
            None if king_d is None or base_d is None else king_d - base_d
        )
        gaming = []
        for control_spec in config["gaming"]:
            control = graded(king, anchors=anchored, bias=control_spec)
            control_d = d_of(control, dropped)
            gaming.append(
                {"control": control_spec["mode"], "holds": True, "gain": None}
                if control_d is None or king_d is None
                else {
                    "control": control_spec["mode"],
                    **paired_gaming(king_d, control_d),
                }
            )
        point["paired_gaming"] = gaming
        king_result = graded(king, anchors=anchored)
        if (
            king_result["basis"] is not None
            and king_result["basis"].get("gated") is False
        ):
            record = with_targets(
                king_result["basis"],
                decompose(king_result["basis"], regrader.combo),
                order,
                classes,
            )
            record["targets"] = [
                [t for tid, t in zip(ids, targets, strict=True) if tid not in dropped]
                for ids, targets in zip(order, record["targets"], strict=True)
            ]
            point["class_bootstrap"] = {
                **class_bootstrap(record),
                "margin_n": config["margin_n"],
            }
        shortcut_q = {}
        for spec in specs:
            value = dv_curve.shortcut_s_low(
                (config["challenge"], config["version"]), spec, curve["coarse_by_target"].get(spec.target_id, {}), budget,
                curve["walls"]["t_ref"], curve["walls"]["t_coarse"], random.Random(curve["seed"]),
            )["s_low"]  # fmt: skip
            q = dv_curve.shortcut_q_under_median(spec, value)
            if q is not None:
                shortcut_q.setdefault(pool_grader.region_class(spec), []).append(q)
        point["shortcut_q_under_median_anchor"] = {
            cls: {"n": len(v), "mean": statistics.fmean(v)}
            for cls, v in sorted(shortcut_q.items())
        }
        report["curve"][str(budget)] = point
    return {**report, "run_digest": run_digest(report, config_path, __file__)}


ACCNOISE_KEYS = frozenset(
    {"contenders", "class_source", "class_floor_n", "other_ood_enters", "seed"}
)
CLASS_SOURCE_KEYS = frozenset(
    {
        "rule_path",
        "rule_sha256",
        "region_path",
        "region_sha256",
        "plan_params_path",
        "plan_params_sha256",
    }
)


def load_accnoise(path):
    """The ACC-NOISE-01 inputs (every key required; nothing defaulted): ``contenders`` {"train_kernel": {"rows_npy", "sha256"},
    "operator": {...} | null, "down_formula": {...} | null} (each model's raw rows in bank order, as DV-CURVE's contenders; a null
    is "not available", never improvised), ``class_source`` (the receipted geometric-v1 rule file, the signed region and the
    registered coverage-plan params, each by its sha256), ``class_floor_n`` (the registered accuracy-case floor N),
    ``other_ood_enters`` (bool, as ruled), ``seed`` (the bootstrap seed, recorded)."""
    document = json.loads(Path(path).read_bytes())
    _need(type(document) is dict and set(document) == ACCNOISE_KEYS, "accnoise_shape")
    contenders = document["contenders"]
    _need(
        type(contenders) is dict
        and set(contenders) == {"train_kernel", "operator", "down_formula"}
        and contenders["train_kernel"] is not None,
        "accnoise_contenders",
    )
    source = document["class_source"]
    _need(
        type(source) is dict and set(source) == CLASS_SOURCE_KEYS,
        "accnoise_class_source",
    )
    _need(
        type(document["class_floor_n"]) is int and document["class_floor_n"] >= 1,
        "accnoise_class_floor_n",
    )
    _need(type(document["other_ood_enters"]) is bool, "accnoise_other_ood_enters")
    _need(type(document["seed"]) is int, "accnoise_seed")
    return document


def _class_source(source):
    """``(klass, region, plan classes, identities)``: the receipted rule by its sha, the signed region read by pool_common (the
    rule's own module) under its canonical sha, the registered coverage plan's class names from its params file by sha.
    """
    import acc_noise

    try:
        klass = acc_noise.load_rule(source["rule_path"], source["rule_sha256"])
    except acc_noise.AccNoiseRefused as refused:
        raise ReadRefused(refused.code) from refused
    try:
        region = klass.__globals__["pc"].load_region(
            source["region_path"], source["region_sha256"].removeprefix("sha256:")
        )
    except SystemExit:
        raise ReadRefused("accnoise_region_sha256_mismatch") from None
    raw = Path(source["plan_params_path"]).read_bytes()
    _need(
        _sha(raw) == source["plan_params_sha256"].removeprefix("sha256:"),
        "accnoise_plan_params_changed",
    )
    try:
        allowed = acc_noise.plan_class_names(json.loads(raw))
    except acc_noise.AccNoiseRefused as refused:
        raise ReadRefused(refused.code) from refused
    identities = {
        k: source[k] for k in ("rule_sha256", "region_sha256", "plan_params_sha256")
    }
    return klass, region, allowed, identities


def run_accnoise(config, config_path, accnoise_path):
    """ACC-NOISE-01 (the S2 noise dry run, CUSTODY scratch, never official): every contender is regraded through the receipted
    route with the A_gen recorder (each point's atom from the predictions the grader scored), A_in = its grade's own a_bank, each
    point's class by the receipted geometric-v1 rule inside the registered coverage plan, and the `acc_noise.report` table with the
    ruled verdict. The crown is the top regraded leader; the baseline the pack's; the TRAIN-kernel, operator and DOWN formula their
    rows by sha. Aggregates only."""
    import acc_noise

    from carbon.scoring import pool_version

    _needs_baseline(config, "accnoise")
    doc = load_accnoise(accnoise_path)
    klass, region, allowed, identities = _class_source(doc["class_source"])
    regrader = Regrader(config)
    classes, order = regrader.sets_and_classes()
    set_of = {tid: i for i, ids in enumerate(order) for tid in ids}
    bodies = read_bodies(config["store"])
    entries, _coverage = enumerate_entries(bodies, config, config["task_roots"])
    old = measured_entries(regrader, entries, classes=classes, order=order)
    _check_regrade_matches(old)
    _check_composition(old)
    scored = sorted(
        (g for g in old if g["record"] is not None and g["status"] == "SCORED"),
        key=lambda g: g["regraded_total"],
        reverse=True,
    )
    _need(scored, "no_scored_entries_with_a_retained_pair")
    crown = scored[0]
    pair_of = {
        (e["hotkey"], e["recipe_digest"]): e["pair"]
        for e in entries
        if e["pair"] is not None
    }
    base_rows = regrader.graded.base_rows.tolist()
    rows_of = {
        "crown": regrader.rows_of(pair_of[crown["hotkey"], crown["recipe"]]),
        "baseline": base_rows,
    }
    for role, spec in doc["contenders"].items():
        if spec is not None:
            rows_of[role] = _contender_rows(spec, len(base_rows))
    material = regrader.graded.bank[pool_version.POOL_KEY]
    design_names = list(material["design_names"])
    names = sorted(region["base"])
    contenders = {role: None for role in acc_noise.ROLES}
    rule = None
    for role, rows in rows_of.items():
        sink = []
        result = regrader.grade(
            rows, f"accnoise:{role}", classes=classes, agen_points=sink
        )
        _need(result["basis"] is not None, f"accnoise_contender_gated:{role}")
        rule = result["basis"]["a_rule"] if role == "crown" else rule
        inputs = [
            {
                **p["conditions"]["fixed"],
                **dict(zip(design_names, p["design"], strict=True)),
            }
            for p in sink
        ]
        try:
            point_class = acc_noise.point_classes(
                inputs, klass=klass, region=region, names=names, allowed=allowed
            )
        except acc_noise.AccNoiseRefused as refused:
            raise ReadRefused(refused.code) from refused
        contenders[role] = {
            "a_in": result["basis"]["a_bank"],
            "points": [
                (c, p["target_id"], p["atom"])
                for c, p in zip(point_class, sink, strict=True)
            ],
        }
    try:
        table = acc_noise.report(
            contenders,
            set_of=set_of,
            floor_n=doc["class_floor_n"],
            other_ood_enters=doc["other_ood_enters"],
            registered_rule=rule,
            seed=doc["seed"],
            margin_n=config["margin_n"],
        )
    except acc_noise.AccNoiseRefused as refused:
        raise ReadRefused(refused.code) from refused
    report = {
        "schema": "carbon.exam-reads.acc-noise.v1",
        "challenge": config["challenge"],
        "version": config["version"],
        "scratch_only": True,
        "crown_hotkey": crown["hotkey"],
        "class_source": identities,
        "contender_rows_sha256": {
            role: spec["sha256"]
            for role, spec in doc["contenders"].items()
            if spec is not None
        },
        **table,
    }
    return {**report, "run_digest": run_digest(report, config_path, __file__)}


STRONG_KEYS = frozenset({"panel", "default_model", "ceiling"})
#: The strong-checks panel kinds (the strong-checks spec, check (1)): the version's engineer shortcut, the generic fits and the
#: physics-feature sparse regression (`shortcut_panel.py`, TRAIN only), and the previous version's kings / best ladder entries.
PANEL_KINDS = (
    "engineer_shortcut",
    "generic_fit",
    "physics_regression",
    "previous_king",
)


def load_strong(path):
    """The STRONG-CHECKS inputs (every key required): ``panel`` [{"name", "kind", "rows_npy", "sha256"}, ...] (raw rows in bank
    order, each trained on the version's TRAIN only), ``default_model`` {"name", "rows_npy", "sha256"} (the published default
    recipe, one standard-seed training, no tuning), ``ceiling`` {"draws", "seed"} (the Monte-Carlo noise ceiling).
    """
    document = json.loads(Path(path).read_bytes())
    _need(type(document) is dict and set(document) == STRONG_KEYS, "strong_shape")
    panel = document["panel"]
    _need(type(panel) is list and panel, "strong_panel")
    names = set()
    for entry in panel:
        _need(
            type(entry) is dict
            and set(entry) == {"name", "kind", "rows_npy", "sha256"}
            and entry["kind"] in PANEL_KINDS
            and type(entry["name"]) is str
            and entry["name"]
            and entry["name"] not in names,
            "strong_panel_entry",
        )
        names.add(entry["name"])
    default = document["default_model"]
    _need(
        type(default) is dict
        and set(default) == {"name", "rows_npy", "sha256"}
        and default["name"] not in names,
        "strong_default_model",
    )
    ceiling = document["ceiling"]
    _need(
        type(ceiling) is dict
        and set(ceiling) == {"draws", "seed"}
        and type(ceiling["draws"]) is int
        and ceiling["draws"] >= 1
        and type(ceiling["seed"]) is int,
        "strong_ceiling",
    )
    return document


def class_means(basis, order, classes):
    """Per region class: the mean over its targets of the grader's own d and A_gen (``agen`` None where a target has no slice)."""
    by = {}
    for ids, targets in zip(order, basis["sets"], strict=True):
        _need(len(ids) == len(targets), "targets_differ_from_the_pool_material")
        for tid, target in zip(ids, targets, strict=True):
            row = by.setdefault(classes[tid], {"d": [], "agen": []})
            row["d"].append(target["d"])
            if target.get("agen") is not None:
                row["agen"].append(target["agen"])
    return {
        cls: {
            "targets": len(row["d"]),
            "d": statistics.fmean(row["d"]),
            "agen": statistics.fmean(row["agen"]) if row["agen"] else None,
        }
        for cls, row in sorted(by.items())
    }


def noise_ceiling(specs, policies, classes, *, draws, seed):
    """The strong-checks noise ceiling per region class: the pool's own decision-output truths, each output perturbed uniformly
    within its registered U (`pool_grader.u_value`), scored by the grader's own `grade_target` (d) and `agen_accuracy` (A_gen),
    averaged over ``draws`` Monte-Carlo draws (``seed`` recorded)."""
    import random

    from carbon.scoring import pool_grader

    per_target = {}
    for spec in specs:
        index_of = {tuple(design): i for i, design in enumerate(spec.designs)}
        d_values, agen_values = [], []
        for draw in range(draws):
            rng = random.Random(f"{seed}:{draw}:{spec.target_id}")
            noise = [
                {
                    k: rng.uniform(-1.0, 1.0) * pool_grader.u_value(spec.u[k], truth[k])
                    for k in spec.outputs
                }
                for truth in spec.truths
            ]

            def predict(
                _conditions, designs, spec=spec, noise=noise, index_of=index_of
            ):
                out = []
                for design in designs:
                    i = index_of[tuple(design)]
                    out.append(
                        {k: spec.truths[i][k] + noise[i][k] for k in spec.outputs}
                    )
                return out

            d_values.append(
                pool_grader.grade_target(
                    spec, predict, policies.optimizer, policies.honesty
                ).d
            )
            if spec.agen:
                agen_values.append(
                    pool_grader.agen_accuracy([spec], predict, policies.agen_scales)
                )
        per_target[spec.target_id] = (
            statistics.fmean(d_values),
            statistics.fmean(agen_values) if agen_values else None,
        )
    by = {}
    for tid, (d, agen) in per_target.items():
        row = by.setdefault(classes[tid], {"d": [], "agen": []})
        row["d"].append(d)
        if agen is not None:
            row["agen"].append(agen)
    return {
        cls: {
            "d": statistics.fmean(row["d"]),
            "agen": statistics.fmean(row["agen"]) if row["agen"] else None,
        }
        for cls, row in sorted(by.items())
    }


def run_strong(config, config_path, strong_path):
    """STRONG-CHECKS (the strong-checks spec, checks (1)-(3)), CUSTODY scratch, never official. Every panel member, the default
    model and the noise ceiling are scored by the version's own grader per region class (A_gen and D, the receipted Regrader);
    the gaps are reported in score steps, max(eta, the registered rebuild noise). No bar is applied: the owner picks each one.
    """
    from carbon.scoring import grade_feedback, pool_version

    doc = load_strong(strong_path)
    regrader = Regrader(config)
    classes, order = regrader.sets_and_classes()
    n_rows = len(regrader.graded.bank["inputs"])
    step = grade_feedback.step(config["margin_n"])
    graded = {}
    for entry in [*doc["panel"], {**doc["default_model"], "kind": "default_model"}]:
        rows = _contender_rows(
            {"rows_npy": entry["rows_npy"], "sha256": entry["sha256"]}, n_rows
        )
        result = regrader.grade(rows, f"strong:{entry['name']}", classes=classes)
        gated = result["basis"] is None or result["basis"].get("gated") is not False
        graded[entry["name"]] = {
            "kind": entry["kind"],
            "status": result["status"],
            "gates": result["gates"],
            "classes": None if gated else class_means(result["basis"], order, classes),
        }
    policies = pool_version.registered_policies(config["challenge"], config["version"])
    ceiling = noise_ceiling(
        regrader.all_specs,
        policies,
        classes,
        draws=doc["ceiling"]["draws"],
        seed=doc["ceiling"]["seed"],
    )
    panel = [
        e["name"] for e in doc["panel"] if graded[e["name"]]["classes"] is not None
    ]
    default = doc["default_model"]["name"]
    in_range = "in_train"

    def best(cls, metric):
        values = [
            (graded[n]["classes"][cls][metric], n)
            for n in panel
            if cls in graded[n]["classes"]
            and graded[n]["classes"][cls][metric] is not None
        ]
        return max(values) if values else (None, None)

    def steps(value):
        return None if value is None else value / step

    checks = {}
    for cls in sorted(ceiling):
        row = {}
        for metric in ("agen", "d"):
            top, who = best(cls, metric)
            ceil = ceiling[cls][metric]
            dflt = (
                None
                if graded[default]["classes"] is None
                else graded[default]["classes"].get(cls, {}).get(metric)
            )
            row[metric] = {
                "best_shortcut": top,
                "best_shortcut_member": who,
                "noise_ceiling": ceil,
                "ceiling_minus_best_in_steps": (
                    None if ceil is None or top is None else steps(ceil - top)
                ),
                "default_model": dflt,
                "default_minus_best_in_steps": (
                    None if dflt is None or top is None else steps(dflt - top)
                ),
            }
            if cls == in_range:
                row[metric]["default_beats_best_by_more_than_rebuild_noise"] = (
                    None
                    if dflt is None or top is None
                    else (dflt - top) > config["margin_n"]
                )
        checks[cls] = row
    report = {
        "schema": "carbon.exam-reads.strong-checks.v1",
        "challenge": config["challenge"],
        "version": config["version"],
        "scratch_only": True,
        "score_step": step,
        "margin_n": config["margin_n"],
        "bars": "owner values (the shortcut bar, K steps): measured gaps only, never judged here",
        "predictors": graded,
        "noise_ceiling": {"by_class": ceiling, **doc["ceiling"]},
        "checks_by_class": checks,
        "panel_rows_sha256": {e["name"]: e["sha256"] for e in doc["panel"]},
        "default_model_rows_sha256": doc["default_model"]["sha256"],
    }
    return {**report, "run_digest": run_digest(report, config_path, __file__)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "cmd", choices=("q3", "q8", "whatif", "dvcurve", "accnoise", "strong")
    )
    parser.add_argument("config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--curve", type=Path, help="dvcurve: the DV-CURVE inputs (`load_curve`)"
    )
    parser.add_argument(
        "--accnoise",
        type=Path,
        help="accnoise: the ACC-NOISE-01 inputs (`load_accnoise`)",
    )
    parser.add_argument(
        "--strong", type=Path, help="strong: the STRONG-CHECKS inputs (`load_strong`)"
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite")
    if args.cmd == "dvcurve" and args.curve is None:
        raise SystemExit("dvcurve needs --curve")
    if args.cmd == "accnoise" and args.accnoise is None:
        raise SystemExit("accnoise needs --accnoise")
    if args.cmd == "strong" and args.strong is None:
        raise SystemExit("strong needs --strong")
    run = {
        "q3": run_q3,
        "q8": run_q8,
        "whatif": run_whatif,
        "dvcurve": lambda c, p: run_dvcurve(c, p, args.curve),
        "accnoise": lambda c, p: run_accnoise(c, p, args.accnoise),
        "strong": lambda c, p: run_strong(c, p, args.strong),
    }[args.cmd]
    try:
        result = run(config, args.config)
    except ReadRefused as refused:
        print(f"STOP: {refused.code}", file=sys.stderr)
        return 3
    args.out.write_bytes((json.dumps(result, indent=1, sort_keys=True) + "\n").encode())
    print(json.dumps({"out": str(args.out), "run_digest": result["run_digest"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
