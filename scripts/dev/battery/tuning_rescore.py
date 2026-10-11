"""Re-score the registered candidates on the sealed tuning set (step 1 of
GRAPHITE_PLAN_2026-10-06). No retraining: legs come from the stored predictions.

    python -m scripts.dev.battery.tuning_rescore --work TUNING_DIR \
        --dev-results ev4-dev-tuning-v1/results.json --out CURVES_DIR
    python -m scripts.dev.battery.tuning_rescore --public-standin \
        --ev4 DIR --run5 DIR --attack DIR --dev-results ... --out DIR

- Legs (`score_tuning.member_legs`) come from each member's stored tuning-set
  predictions and the sealed references (`challenge_validator.tuning`'s
  `references` and `case_store`). Controls are derived from the references.
- Decision value comes from ev4-dev-tuning-v1's development results (#671).
- Candidates come from registry-v2 (#674), loaded with its commit check.

Outputs go to `--out`, owner-only: `curves.json` and `curves.md`, one row
per candidate and cutoff, with the rule in force (`CE`) first. Aggregates
only: no case, input, output or reference leaves the work directory.
`--public-standin` runs the same pipeline on the public scoring set, as a
plumbing check, and its numbers are not tuning results.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "docs/development/evidence/battery-score-tuning/registry-v4.json"
CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
UNSAFE = ("graphite-run5-p-1d4aaff5d292-s3718551111",)
#: EV5's adversarial FAIL (conditions.json, #661): the 8 top-half infeasible
#: Track A constructions and the 2 Mode X violators.
ADVERSARIAL = (
    "attack_rebuild_identity_backbone_a-s0",
    "attack_rebuild_identity_backbone_b-s0",
    "attack_rebuild_identity_optimizer_a-s0",
    "attack_rebuild_identity_steps_a-s0",
    "attack_rebuild_identity_steps_b-s0",
    "attack_rebuild_identity_train_fraction_a-s0",
    "attack_rebuild_identity_width_a-s0",
    "attack_rebuild_identity_width_b-s0",
    "mlp_t6000_w256_d3_ens2-s0",
    "mlp_t6000_w512_d3-s1",
)


def _tuning(work):
    from carbon.challenge_validator import tuning

    work = Path(work)
    batch, refs = tuning.references(work)
    store = tuning.case_store(batch, refs, ROOT)
    predictions = {}
    for path in sorted((work / "predictions").glob("*.json")):
        if not path.name.endswith(".failure.json"):
            bundle = json.loads(path.read_bytes())
            predictions[bundle["member"]] = bundle["predictions"]
    return store, sorted(refs), predictions


def _standin(dirs):
    from carbon.battery.value import scoring as sc

    store, ids, _ = sc.scoring_set(ROOT)
    predictions = {}
    for directory in dirs:
        for path in sorted(Path(directory).glob("*.json.gz")):
            bundle = json.loads(gzip.decompress(path.read_bytes()))
            predictions[bundle["member"]] = bundle["predictions"]
    return store, ids, predictions


def assemble(store, ids, predictions, dev_results, q3_regret=None):
    """The panel the rescore and the score proof (SCORE-PROOF-01) share: each
    decided member's legs, decision value and outcomes, recipe and seed
    grouping, and what the legs were computed from."""
    from carbon.battery.value import panel as pn
    from carbon.battery.value import score_tuning as st
    from carbon.battery.value.contract import load

    contract, _ = load(CONTRACT)
    members = dict(predictions)
    for kind in pn.CONTROLS:
        members["control-" + kind] = pn.control_predictions(kind, store.refs)
    results = json.loads(Path(dev_results).read_text())
    decided = set(results["decisions"])
    names = sorted(m for m in members if m in decided)
    q3_regret = q3_regret or {}
    legs = {
        m: st.member_legs(contract, members[m], store, ids, q3_regret.get(m))
        for m in names
    }
    values, mask, outcomes = st.decision_values(results, names)
    recipe_of = {
        m: (m if m.startswith("control-") else m.rsplit("-s", 1)[0]) for m in names
    }
    first = {
        label: seeds[0]
        for panel in ("ev4", "graphite-run5")
        for label, _s, seeds in pn.PANELS[panel]
    }
    one_seed = [
        m
        for m in names
        if m.startswith(("control-", "attack_"))
        or int(m.rsplit("-s", 1)[1]) == first.get(recipe_of[m])
    ]
    return {
        "contract": contract,
        "store": store,
        "ids": ids,
        "predictions": members,
        "q3_regret": q3_regret,
        "results": results,
        "names": names,
        "legs": legs,
        "values": values,
        "mask": mask,
        "outcomes": outcomes,
        "recipe_of": recipe_of,
        "one_seed": one_seed,
        "missing_from_decisions": sorted(set(members) - decided),
    }


def rescore(
    store, ids, predictions, dev_results, registry_path=REGISTRY, q3_regret=None
):
    from carbon.battery.value import score_tuning as st

    p = assemble(store, ids, predictions, dev_results, q3_regret)
    names = p["names"]
    registry = st.load_registry(registry_path, repository=ROOT)
    out = st.evaluate_all(
        registry,
        p["legs"],
        p["values"],
        p["outcomes"],
        p["recipe_of"],
        names,
        p["one_seed"],
        unsafe=[u for u in UNSAFE if u in names],
        adversarial=[a for a in ADVERSARIAL if a in names],
    )
    out["panel"] = {
        "members": len(names),
        "one_seed": len(p["one_seed"]),
        "dev_mask": len(p["mask"]),
        "missing_from_decisions": p["missing_from_decisions"],
    }
    return out


def table(out):
    """One row per candidate (and cutoff), the rule in force first."""
    rows = []
    order = ["CE"] + [c for c in out["candidates"] if c != "CE"]
    header = (
        "| candidate | τ all | τ seed band | ρ | regret | top-1 false-feasible "
        "| gate failures | adversarial in top half | Δτ vs CE |"
    )
    rows.append(header)
    rows.append("|" + "---|" * 9)
    for cid in order:
        r = out["candidates"][cid]

        def f(x):
            return "—" if x is None else f"{x:.3f}"

        band = r["tau_seed_band"]
        delta = r["delta_tau_vs_baseline"]
        rows.append(
            f"| {cid}{' (rule in force)' if cid == 'CE' else ''} | {f(r['tau_all'])} "
            f"| {'—' if band is None else f'[{band[0]:.3f}, {band[1]:.3f}]'} "
            f"| {f(r['rho_all'])} | {f(r['regret'])} | {f(r['top1_false_feasible_rate'])} "
            f"| {len(r['gate_failures'])} | {len(r['adversarial_in_top_half'])} "
            f"| {'—' if delta is None else f'[{delta[0]:.3f}, {delta[1]:.3f}]'} |"
        )
    return "\n".join(rows) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tuning_rescore")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--public-standin", action="store_true")
    parser.add_argument("--ev4", type=Path)
    parser.add_argument("--run5", type=Path)
    parser.add_argument("--attack", type=Path)
    parser.add_argument("--dev-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--q3-regret",
        type=Path,
        help="member -> mean Q3 decision regret (the quiz producer's aggregate); leg q",
    )
    args = parser.parse_args(argv)
    if args.public_standin:
        store, ids, predictions = _standin([args.ev4, args.run5, args.attack])
    else:
        store, ids, predictions = _tuning(args.work)
    q3 = json.loads(args.q3_regret.read_text()) if args.q3_regret else None
    out = rescore(store, ids, predictions, args.dev_results, q3_regret=q3)
    out["source"] = (
        "PUBLIC_STANDIN (plumbing only)"
        if args.public_standin
        else "graphite-tuning-v1 (sealed)"
    )
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, text in (
        ("curves.json", json.dumps(out, indent=1, sort_keys=True, default=str) + "\n"),
        ("curves.md", f"# Score-tuning curves ({out['source']})\n\n" + table(out)),
    ):
        path = args.out / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
    print(json.dumps({"written": str(args.out), **out["panel"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
