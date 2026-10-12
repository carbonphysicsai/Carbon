"""SCORE-PROOF-POSTMORTEM-01: aggregates only, from the score proof's own
inputs on the operator host (or the public stand-in for the dry run).

    python pm.py --work T --dev-results RESULTS --q3-regret Q3 \
        --rule RULE [--public-standin --ev4 D --run5 D --attack D] --out FILE

Prints and writes (owner-only):
1. member accounting: evaluated -> decided -> each fold (recipe split,
   anchors in both);
2. on the confirmation fold, for the pick and the rule in force: which
   known-bad / adversarial members rank in the top half, their rank on the
   score, on each leg and on value, and their decision outcomes (counts);
3. which legs track value: Kendall tau of every leg and gate measure with
   decision value over the primary members, and of the value's components;
4. selection optimism: the bootstrap optimism of picking the best of every
   registered rule on the selection fold (members and questions resampled),
   against the pick's observed drop from selection to confirmation.
No case, input, output or reference is printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from carbon.battery.value import score_proof as sp  # noqa: E402
from carbon.battery.value import score_tuning as st  # noqa: E402
from scripts.dev.battery import score_proof as script  # noqa: E402
from scripts.dev.battery import tuning_rescore as tr  # noqa: E402

LEGS = ("a", "r", "g", "m", "n", "p", "q")
GATES = ("feasibility", "plating_fa", "envelope", "near", "error")
rng = np.random.default_rng(20261012)


def panel_for(args, phase, store, ids, predictions, members, split, q3):
    cases = sp.split_cases(split, ids, phase)
    full = tr.assemble(store, cases, predictions, args.dev_results, q3)
    return full, script.phase_panel(full, members, split, phase), cases


def roles_of(members):
    roles = members["roles"]
    return {k: set(roles.get(k, ())) for k in ("known_bad", "benign", "adversarial", "unsafe")}


def tau(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    t = sp.tau_b(x[ok], y[ok]) if ok.sum() > 3 else None
    return None if t is None else round(float(t), 3)


def rank_desc(values, names):
    order = sorted(names, key=lambda m: (-(values[m] if values[m] is not None else -1e18), m))
    return {m: i + 1 for i, m in enumerate(order)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path)
    ap.add_argument("--dev-results", type=Path, required=True)
    ap.add_argument("--q3-regret", type=Path)
    ap.add_argument("--rule", required=True)
    ap.add_argument("--baseline", default="G-FEAS/A-Q>@0.05")
    ap.add_argument("--registry", type=Path, default=script.REGISTRY)
    ap.add_argument("--public-standin", action="store_true")
    ap.add_argument("--ev4", type=Path)
    ap.add_argument("--run5", type=Path)
    ap.add_argument("--attack", type=Path)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.public_standin:
        store, ids, predictions = tr._standin([args.ev4, args.run5, args.attack])
    else:
        store, ids, predictions = tr._tuning(args.work)
    q3 = json.loads(args.q3_regret.read_text()) if args.q3_regret else None
    split = script.load_split()
    members = script.load_members()
    roles = roles_of(members)
    candidates, _identity = st.load_registry(args.registry, repository=ROOT)
    out = {"rule": args.rule, "baseline": args.baseline}

    # 1. Member accounting.
    full_c, conf, conf_cases = panel_for(args, "confirmation", store, ids, predictions, members, split, q3)
    full_s, sel, sel_cases = panel_for(args, "selection", store, ids, predictions, members, split, q3)
    anchors = {m for m in full_c["names"] if script.level_of(m, members["levels"]) is None}
    anchors |= set().union(*roles.values())
    real = [m for m in full_c["names"] if m not in anchors]
    out["accounting"] = {
        "predicted_members": len(predictions),
        "with_decisions (incl. controls)": len(full_c["names"]),
        "missing_from_decisions": len(full_c["missing_from_decisions"]),
        "anchors_in_both_folds": len([m for m in full_c["names"] if m in anchors]),
        "real_members": len(real),
        "real_recipes": len({full_c["recipe_of"][m] for m in real}),
        "split_levels": conf["split_levels"],
        "confirmation_members": len(conf["names"]),
        "selection_members": len(sel["names"]),
        "confirmation_cases": len(conf_cases),
        "selection_cases": len(sel_cases),
        "confirmation_questions": len(conf["mask"]),
        "selection_questions": len(sel["mask"]),
    }

    # 2. and 3. On the confirmation fold.
    names = [m for m in conf["names"] if conf["values"].get(m) is not None]
    primary = [m for m in names if m not in anchors]
    value = {m: -conf["values"][m] for m in names}  # higher is better
    legs = conf["legs"]
    report = {}
    for rule in (args.rule, args.baseline):
        scores, verdicts = st.candidate_scores(candidates[rule], legs, conf["recipe_of"])
        ranked = [m for m in sorted(names, key=lambda m: (-(scores[m] if scores[m] is not None else -1e18), m))]
        half = set(ranked[: len(ranked) // 2])
        flagged = sorted((roles["known_bad"] | roles["adversarial"]) & half)
        vrank = rank_desc(value, names)
        leg_rank = {
            leg: rank_desc({m: legs[m]["legs"].get(leg) for m in names}, names) for leg in ("a", "q", "n", "g")
        }
        rows = []
        for m in flagged:
            kinds = {}
            for s in conf["mask"]:
                k = conf["outcomes"][m][s]
                kinds[k] = kinds.get(k, 0) + 1
            rows.append(
                {
                    "member": m,
                    "role": "known_bad" if m in roles["known_bad"] else "adversarial",
                    "score_rank": ranked.index(m) + 1,
                    "value_rank": vrank[m],
                    "rank_on_accuracy_a": leg_rank["a"][m],
                    "rank_on_q3_regret_q": leg_rank["q"][m],
                    "rank_on_near_limit_n": leg_rank["n"][m],
                    "gate": verdicts.get(m),
                    "feasibility": legs[m]["gates"].get("feasibility"),
                    "envelope": legs[m]["gates"].get("envelope"),
                    "decision_outcomes": kinds,
                }
            )
        report[rule] = {
            "members_ranked": len(ranked),
            "flagged_in_top_half": rows,
            "tau_primary": tau([scores[m] if scores[m] is not None else np.nan for m in primary], [value[m] for m in primary]),
        }
    out["confirmation_fold"] = report
    track = {}
    for leg in LEGS:
        track[f"leg {leg}"] = tau([legs[m]["legs"].get(leg) if legs[m]["legs"].get(leg) is not None else np.nan for m in primary], [value[m] for m in primary])
    for g in GATES:
        track[f"gate {g} (lower better)"] = tau(
            [-legs[m]["gates"][g] if legs[m]["gates"].get(g) is not None else np.nan for m in primary],
            [value[m] for m in primary],
        )
    for kind in ("SELECTED_INFEASIBLE", "MISSED_OPPORTUNITY", "SELECTED_FEASIBLE"):
        track[f"share {kind} (fewer better unless feasible)"] = tau(
            [
                (1 if kind == "SELECTED_FEASIBLE" else -1)
                * np.mean([conf["outcomes"][m][s] == kind for s in conf["mask"]])
                for m in primary
            ],
            [value[m] for m in primary],
        )
    out["what_tracks_value_on_confirmation (tau over primary members)"] = track

    # 4. Selection optimism (bootstrap over members and questions).
    sel_names = [m for m in sel["names"] if sel["values"].get(m) is not None and m not in anchors]
    losses = np.array(
        [[sel["results"]["decisions"][m][s]["outcome"]["decision_loss"] for s in sel["mask"]] for m in sel_names],
        float,
    )
    rule_ids = sorted(candidates)
    S = []
    for rid in rule_ids:
        sc, _v = st.candidate_scores(candidates[rid], sel["legs"], sel["recipe_of"])
        S.append([sc[m] if sc.get(m) is not None else np.nan for m in sel_names])
    S = np.array(S, float)
    usable = ~np.isnan(S).any(axis=1)
    S, rule_ids = S[usable], [r for r, u in zip(rule_ids, usable) if u]
    v0 = -losses.mean(axis=1)
    tau0 = np.array([sp.tau_b(s, v0) or 0.0 for s in S])
    opt = []
    for _ in range(args.boot):
        mi = rng.integers(len(sel_names), size=len(sel_names))
        qi = rng.integers(losses.shape[1], size=losses.shape[1])
        vb = -losses[mi][:, qi].mean(axis=1)
        tb = np.array([sp.tau_b(s[mi], vb) or 0.0 for s in S])
        best = int(np.argmax(tb))
        opt.append(tb[best] - tau0[best])
    pick_sel = tau0[rule_ids.index(args.rule)] if args.rule in rule_ids else None
    out["selection_optimism"] = {
        "rules_compared": len(rule_ids),
        "selection_members_primary": len(sel_names),
        "selection_questions": int(losses.shape[1]),
        "best_selection_tau": round(float(tau0.max()), 3),
        "pick_selection_tau_primary": None if pick_sel is None else round(float(pick_sel), 3),
        "pick_confirmation_tau_primary": report[args.rule]["tau_primary"],
        "bootstrap_optimism_of_the_max_mean": round(float(np.mean(opt)), 3),
        "bootstrap_optimism_p90": round(float(np.quantile(opt, 0.9)), 3),
    }
    text = json.dumps(out, indent=1, default=str)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
