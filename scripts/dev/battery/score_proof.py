"""The one-command battery score proof (SCORE-PROOF-01), off chain.

    python -m scripts.dev.battery.score_proof --phase selection --work TUNING_DIR \
        --dev-results RESULTS --q3-regret Q3 --out PROOF_DIR
    python -m scripts.dev.battery.score_proof --phase confirmation --rule ID ...
    python -m scripts.dev.battery.score_proof --phase selection --public-standin \
        --ev4 DIR --run5 DIR --attack DIR --dev-results ... --out DIR

Selection is kept apart from proof (`proof-split-v1.json`, registered before
any run). Every rule and cutoff is compared on the selection fold of the
scoring cases (and of the members, where a level has enough), and the owner
picks there. The confirmation phase reports the proof criteria for the
picked rule only, against the rule in force, on the held-apart fold, and
gives a PROVEN or UNPROVEN verdict naming each failed criterion.

It uses the same panel as `tuning_rescore` (`assemble`: stored predictions,
sealed references, development decision values, registry-v4's candidates
with its commit check). It adds levels and roles from the members manifest
(`proof-members-v1.json`) and the per-case-fold legs, and writes
`carbon.battery.value.score_proof`'s report.

Outputs go to `--out`, owner-only: `<phase>.json` and `<phase>.md`, aggregates
only, with no case, input, output or reference. `--public-standin` runs on
the public scoring set as a plumbing check, and its numbers are not proof.
The real run is on the sealed tuning set, operator host only
(`SCORE_PROOF_OWNER_SHEET.md`). No rule is adopted and no cutoff is chosen:
both stay the owner's.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.battery import tuning_rescore as tr

MEMBERS = ROOT / "docs/development/evidence/battery-score-tuning/proof-members-v1.json"
REGISTRY = ROOT / "docs/development/evidence/battery-score-tuning/registry-v5.json"
#: The rule in force (OWNER-BATTERY-SCORE-RULE-01): A-Q with the G-FEAS gate at
#: 0.05, recorded as "exceeds" (registry v5's `G-FEAS/A-Q>@0.05`).
RULE_IN_FORCE = "G-FEAS/A-Q>@0.05"
MEMBERS_SCHEMA = "carbon.battery.score-proof-members.v1"
SPLIT = ROOT / "docs/development/evidence/battery-score-tuning/proof-split-v1.json"


def load_members(path=MEMBERS):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema") != MEMBERS_SCHEMA:
        raise SystemExit("refused: unknown members manifest schema")
    return document


def level_of(name, rules):
    """The first matching rule's level (None for a level-agnostic anchor);
    a member no rule names is refused."""
    for rule in rules:
        if re.search(rule["pattern"], name):
            return rule["level"]
    raise SystemExit(f"refused: no level rule names a member ({len(name)} chars)")


def load_split(path=SPLIT):
    from carbon.battery.value import score_proof as sp

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema") != sp.SPLIT_SCHEMA:
        raise SystemExit("refused: unknown split schema")
    return document


def phase_panel(panel, members, split, phase):
    """The panel restricted to one phase: its members (the registered split),
    with decision values recomputed on exactly those members. The caller has
    already computed the legs on the phase's scoring cases."""
    from carbon.battery.value import score_proof as sp
    from carbon.battery.value import score_tuning as st

    roles = members["roles"]
    levels = {m: level_of(m, members["levels"]) for m in panel["names"]}
    anchors = {m for m in panel["names"] if levels[m] is None} | {
        m
        for key in ("known_bad", "benign", "adversarial", "unsafe")
        for m in roles[key]
    }
    names, split_levels = sp.split_members(
        split, panel["names"], panel["recipe_of"], levels, anchors, phase
    )
    values, mask, outcomes = st.decision_values(panel["results"], names)
    return {
        **panel,
        "names": names,
        "legs": {m: panel["legs"][m] for m in names},
        "values": values,
        "mask": mask,
        "outcomes": outcomes,
        "split_levels": split_levels,
    }


def fold_legs(panel, folds):
    """Each member's legs on each of `folds` folds of the scoring cases."""
    from carbon.battery.value import score_tuning as st

    ids = list(panel["ids"])
    out = []
    for k in range(folds):
        subset = ids[k::folds]
        out.append(
            {
                m: st.member_legs(
                    panel["contract"],
                    panel["predictions"][m],
                    panel["store"],
                    subset,
                    panel["q3_regret"].get(m),
                )
                for m in panel["names"]
            }
        )
    return out


def proof(
    panel,
    members,
    *,
    folds,
    n_bootstrap,
    candidates=None,
    registry_path=REGISTRY,
    baseline=RULE_IN_FORCE,
):
    from carbon.battery.value import score_proof as sp
    from carbon.battery.value import score_tuning as st

    names = panel["names"]
    levels = {m: level_of(m, members["levels"]) for m in names}
    roles = members["roles"]
    registry = st.load_registry(registry_path, repository=ROOT)
    legs = {m: panel["legs"][m] for m in names}
    report = sp.prove(
        registry,
        legs,
        panel["values"],
        panel["recipe_of"],
        levels,
        results=panel["results"],
        known_bad=[m for m in roles["known_bad"] if m in names],
        adversarial=[m for m in roles["adversarial"] if m in names],
        unsafe=[m for m in roles["unsafe"] if m in names],
        fold_legs=fold_legs(panel, folds) if folds > 1 else (),
        ids=candidates,
        baseline=baseline,
        folds=folds,
        n_bootstrap=n_bootstrap,
    )
    report["benign_controls_ranks"] = _benign(report, panel, roles, registry)
    report["panel"] = {
        "members": len(names),
        "dev_mask": len(panel["mask"]),
        "missing_from_decisions": len(panel["missing_from_decisions"]),
        "missing_by_level": members["missing"],
    }
    return report


def _benign(report, panel, roles, registry):
    """Where the benign controls (the oracle, the rank-preserving delay)
    rank in the pooled panel, per candidate: they should stay high."""
    from carbon.battery.value import score_tuning as st

    candidates, _ = registry
    names = panel["names"]
    benign = [m for m in roles["benign"] if m in names]
    out = {}
    for cid in report["candidates"]:
        scores, _ = st.candidate_scores(
            candidates[cid], panel["legs"], panel["recipe_of"]
        )
        ranked = sorted(
            (m for m in names if scores.get(m) is not None),
            key=lambda m: (-scores[m], m),
        )
        out[cid] = {
            m: (ranked.index(m) + 1, len(ranked)) for m in benign if m in ranked
        }
    return out


def _f(x):
    return "—" if x is None else f"{x:.3f}"


def _ci(x):
    return "—" if x is None else f"[{x[0]:.3f}, {x[1]:.3f}]"


def gate_lines(report):
    """The pre-registered gate-recall check: every gated rule that misses an
    unsafe member, with the cutoff range that would catch it (not picked)."""
    out = ["\n## Gate recall on the unsafe members (pre-registered)\n"]
    for cid, check in report["gate_recall_check"].items():
        if check["status"] == "FAIL":
            catch = check["catching_cutoff"]
            bound = ", ".join(f"{k} {v}" for k, v in catch.items())
            out.append(
                f"- **{cid}: FAIL.** It misses {len(check['missed'])} unsafe "
                f"member(s) at cutoff {check['cutoff_in_force']}; every one fails "
                f"at {bound}. The cutoff stays the owner's."
            )
    if len(out) == 1:
        out.append("- Every gated rule fails every unsafe member (PASS).")
    return "\n".join(out) + "\n"


def table(report):
    """One table per level, the rule in force first."""
    base = report["rule_in_force"]
    order = [base] + [c for c in report["candidates"] if c != base]
    out = []
    for level in report["levels"]:
        out.append(f"\n## {level} ({report['levels'][level]} members)\n")
        out.append(
            "| candidate | τ | τ 95 % CI | Δτ vs rule in force | known-bad in top half "
            "| top-1 regret | gate recall (unsafe) | fold τ sd (scenario / case) "
            "| adversarial divergent |"
        )
        out.append("|" + "---|" * 9)
        for cid in order:
            r = report["candidates"][cid][level]
            if r["status"] != "COMPLETE":
                out.append(
                    f"| {cid}{' (in force)' if cid == base else ''} "
                    f"| {r['status']}: {r['unscored']} members unscored | — | — | — "
                    f"| — | {_f(r['gate_recall_unsafe'])} | — | — |"
                )
                continue
            folds = r["fold_stability"]
            sd = "/".join(
                "—" if folds[k] is None else f"{folds[k]['sd']:.3f}"
                for k in ("scenario_folds", "case_folds")
            )
            out.append(
                f"| {cid}{' (in force)' if cid == base else ''} | {_f(r['tau'])} "
                f"| {_ci(r['tau_ci95'])} | {_ci(r['delta_tau_vs_rule_in_force_ci95'])} "
                f"| {len(r['known_bad_in_top_half']) + len(r['adversarial_in_top_half'])} "
                f"| {_f(r['top1_regret'])} | {_f(r['gate_recall_unsafe'])} | {sd} "
                f"| {len(r['adversarial_divergence'])} |"
            )
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="score_proof")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--public-standin", action="store_true")
    parser.add_argument("--ev4", type=Path)
    parser.add_argument("--run5", type=Path)
    parser.add_argument("--attack", type=Path)
    parser.add_argument("--dev-results", type=Path, required=True)
    parser.add_argument("--q3-regret", type=Path)
    parser.add_argument("--members", type=Path, default=MEMBERS)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--baseline", default=RULE_IN_FORCE)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument(
        "--candidates", help="comma-separated registered ids; default all"
    )
    parser.add_argument("--split", type=Path, default=SPLIT)
    parser.add_argument(
        "--phase",
        choices=("selection", "confirmation"),
        required=True,
        help="selection: compare every rule (the owner picks); confirmation: "
        "the proof criteria for --rule only, on the held-apart fold",
    )
    parser.add_argument("--rule", help="confirmation: the rule the owner picked")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    from carbon.battery.value import score_proof as sp

    if args.phase == "confirmation" and not args.rule:
        raise SystemExit("refused: confirmation needs --rule (the owner's pick)")
    if args.phase == "selection" and args.rule:
        raise SystemExit("refused: --rule is for confirmation only")
    if args.public_standin:
        store, ids, predictions = tr._standin([args.ev4, args.run5, args.attack])
    else:
        store, ids, predictions = tr._tuning(args.work)
    split = load_split(args.split)
    members = load_members(args.members)
    q3 = json.loads(args.q3_regret.read_text()) if args.q3_regret else None
    cases = sp.split_cases(split, ids, args.phase)
    panel = phase_panel(
        tr.assemble(store, cases, predictions, args.dev_results, q3),
        members,
        split,
        args.phase,
    )
    if args.phase == "confirmation":
        # Candidates locked: the owner's pick and the rule in force only.
        candidates = sorted({args.rule, args.baseline})
    else:
        candidates = args.candidates.split(",") if args.candidates else None
    report = proof(
        panel,
        members,
        folds=args.folds,
        n_bootstrap=args.bootstrap,
        candidates=candidates,
        registry_path=args.registry,
        baseline=args.baseline,
    )
    report["phase"] = {
        "phase": args.phase,
        "split": split["salt"],
        "cases": len(cases),
        "member_split_levels": panel["split_levels"],
    }
    if args.phase == "confirmation":
        report["verdict"] = sp.verdict(
            report, args.rule, split["minimum_level_members"]
        )
    report["source"] = (
        "PUBLIC_STANDIN (plumbing only; not proof)"
        if args.public_standin
        else "graphite-tuning-v1 (sealed)"
    )
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.phase == "selection":
        lead = (
            "**SELECTION fold.** Compare the rules and pick one here; nothing on "
            "this page is proof. Then run the confirmation phase with --rule."
        )
    else:
        v = report["verdict"]
        lead = f"**CONFIRMATION fold, {v['rule']}: {v['verdict']}.**" + "".join(
            f"\n- {f}" for f in v["failed"]
        )
    phase = report["phase"]
    header = (
        f"# Score proof ({report['source']})\n\n{lead}\n\n"
        f"{phase['cases']} scoring cases; member split at levels "
        f"{phase['member_split_levels'] or 'none'}.\n\n{report['threshold']}\n"
    )
    for name, text in (
        (
            f"{args.phase}.json",
            json.dumps(report, indent=1, sort_keys=True, default=str) + "\n",
        ),
        (f"{args.phase}.md", header + gate_lines(report) + table(report)),
    ):
        path = args.out / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
    print(json.dumps({"written": str(args.out), "levels": report["levels"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
