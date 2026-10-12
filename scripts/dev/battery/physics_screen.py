"""Screen battery's physics-contract laws (B1-B10) on the public EV4 members
before any is proposed as a gate (PHYSICS-CONTRACT-01 §4).

    python -m scripts.dev.battery.physics_screen --ev4 DIR --run5 DIR \
        --attack DIR --dev-results RESULTS.json --out OUT [--pairs N]

For each law and each candidate tolerance (the verified reference's own
residual quantile, plus margin 0) and gate threshold (the largest violation
rate a member may show):
- **false rejection**: the share of good-value members the gate would make
  ineligible (good value: decision loss at or below the median of the
  reconstructed, non-attack, non-unsafe members);
- **catch rate**: the share of the registered known-bad, adversarial and
  unsafe members it would make ineligible (`proof-members-v1.json` roles);
- **tau effect**: Kendall tau between each computable registry-v9 candidate's
  score and decision value, before and after removing the members the gate
  rejects (invariant 7.3: a gate failure is ineligible, never ranked).

Single-point laws (B1-B4, B9) run on stored predictions over the public
scoring set and are calibrated on the EV4 references (the verified image
carbon-determinism-study@sha256:2d19b261..., OWNER-CODE-VERIFICATION-ACCEPT-01).
Pair laws (B5-B8, B10) need each member to predict at probe pairs, so
`--pairs N` rebuilds members (CPU, DirectBackend, no spend). Their tolerance
needs reference **pairs**, which no record holds yet: they are reported
UNCALIBRATED and are not proposable until Data Collection solves a calibration
panel. The controls are derived from references, so they have no pair-law
reading.

DEVELOPMENT evidence on public data: aggregates only. Nothing here is a
gate, a tolerance or a margin until the owner records it.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "carbon/battery/physics_contract.v1.json"
ROLES = ROOT / "docs/development/evidence/battery-score-tuning/proof-members-v1.json"
REGISTRY = ROOT / "docs/development/evidence/battery-score-tuning/registry-v9.json"
#: Registry-v9 candidates computable on the public EV4 set (no VERIFY-R, no
#: Q3 regret there).
TAU_CANDIDATES = ("A", "ARP", "ENV/ARP")
QUANTILES = (0.99, 1.0)
RATES = (0.0, 0.01, 0.05)


def _ocv():
    import numpy as np

    from carbon.battery.challenge import PublicMaterial

    material = PublicMaterial.load(ROOT)
    return lambda soc: float(np.interp(soc, material.ocv_soc, material.ocv_v))


def _cases(store, ids, predictions=None):
    for cid in ids:
        record = store.refs[cid]
        if record.get("status", "OK") != "OK":
            continue
        outputs = record["outputs"] if predictions is None else predictions.get(cid)
        if outputs is not None:
            yield record["inputs"], outputs


def _taus(panel, names):
    from carbon.battery.value import score_proof as sp
    from carbon.battery.value import score_tuning as st

    candidates, _ = st.load_registry(REGISTRY)
    found = {}
    for cid in TAU_CANDIDATES:
        candidate = candidates.get(cid)
        if candidate is None:
            continue
        legs = {m: panel["legs"][m] for m in names}
        scores, _verdicts = st.candidate_scores(candidate, legs, panel["recipe_of"])
        tau = sp._tau(scores, panel["values"], names)
        found[cid] = None if tau is None else float(tau)
    return found


def screen(panel, roles, contract, *, pair_residuals=None):
    from carbon.challenge_validator import physics_contract as pc

    store, ids = panel["store"], panel["ids"]
    aux = {"ocv": _ocv()}
    reference = pc.check_cases(contract, _cases(store, ids), aux)
    members = panel["names"]
    member_res = {
        m: pc.check_cases(contract, _cases(store, ids, panel["predictions"][m]), aux)
        for m in members
    }
    bad = {m for r in ("known_bad", "adversarial", "unsafe") for m in roles.get(r, ())}
    bad &= set(members)
    pool = [
        m
        for m in members
        if not m.startswith(("control-", "attack_"))
        and m not in bad
        and panel["values"].get(m) is not None
    ]
    cut = statistics.median(panel["values"][m] for m in pool)
    good = {m for m in pool if panel["values"][m] <= cut}
    base_taus = _taus(panel, members)
    laws = {}
    for law in contract["laws"]:
        lid = law["id"]
        if law["type"] in pc.PAIR:
            readings = (pair_residuals or {}).get(lid) or {}
            rows = []
            good_read = [m for m in good if m in readings]
            bad_read = [m for m in bad if m in readings]
            pooled = sorted(r for m in good_read for r in readings[m])
            # Diagnostic tolerances only (no reference pairs yet): 0 and
            # the good members' pooled residual quantiles.
            tols = sorted({0.0} | {pc.quantile(pooled, g) or 0.0 for g in (0.9, 0.99)})
            for tol in tols:
                for rate in RATES:
                    rejected = {
                        m
                        for m, v in readings.items()
                        if (x := pc.violation_rate(v, tol)) is not None and x > rate
                    }
                    rows.append(
                        {
                            "tolerance": tol,
                            "max_violation_rate": rate,
                            "false_rejection": f"{len(rejected & set(good_read))}/{len(good_read)}",
                            "catch": f"{len(rejected & set(bad_read))}/{len(bad_read)}",
                            "caught": sorted(rejected & set(bad_read)),
                        }
                    )
            laws[lid] = {
                "name": law["name"],
                "type": law["type"],
                "calibration": "UNCALIBRATED: no reference pairs yet (diagnostic only)",
                "members_read": len(readings),
                "screen": rows,
            }
            continue
        ref = reference[lid]
        rows = []
        # Margins: 0, then the levels that would admit the good members'
        # own residuals (their pooled p90 / p99 / max), so the screen shows
        # the smallest margin with no false rejection and what it still
        # catches. The registered margin is the owner's (HUMAN_INPUT).
        good_points = sorted(r for m in good for r in member_res[m][lid])
        margins = sorted(
            {0.0}
            | {
                max(
                    0.0,
                    (pc.quantile(good_points, g) or 0.0)
                    - (pc.quantile(ref, 1.0) or 0.0),
                )
                for g in (0.9, 0.99, 1.0)
            }
        )
        for q, margin in [(q, 0.0) for q in QUANTILES] + [
            (1.0, m) for m in margins if m
        ]:
            tol = pc.tolerance(ref, q=q, margin=margin)
            for rate in RATES:
                rejected = {
                    m
                    for m in members
                    if (v := pc.violation_rate(member_res[m][lid], tol)) is not None
                    and v > rate
                }
                kept = [m for m in members if m not in rejected]
                rows.append(
                    {
                        "quantile": q,
                        "margin": margin,
                        "tolerance": tol,
                        "max_violation_rate": rate,
                        "false_rejection": f"{len(rejected & good)}/{len(good)}",
                        "catch": f"{len(rejected & bad)}/{len(bad)}",
                        "caught": sorted(rejected & bad),
                        "rejected_good": sorted(rejected & good),
                        "tau_before": base_taus,
                        "tau_after": _taus(panel, kept),
                    }
                )
        laws[lid] = {
            "name": law["name"],
            "type": law["type"],
            "reference_points": len(ref),
            "reference_residual": {
                "p50": pc.quantile(ref, 0.5),
                "p99": pc.quantile(ref, 0.99),
                "max": pc.quantile(ref, 1.0),
            },
            "screen": rows,
        }
    return {
        "schema": "carbon.battery.physics-screen.v1",
        "contract": contract["version"],
        "members": len(members),
        "good_value": len(good),
        "bad": sorted(bad),
        "laws": laws,
    }


def _pair_readings(panel_names, contract, count, seed):
    """Rebuild the reconstructed and attack members (CPU) and read the pair
    laws at `count` probe pairs per law."""
    from carbon.battery.value import experiment as ex
    from carbon.battery.value import panel as pn
    from carbon.battery.worker import DirectBackend
    from carbon.challenge_validator import physics_contract as pc

    backend = DirectBackend(ROOT)
    wanted = set(panel_names)
    readings = {law["id"]: {} for law in contract["laws"] if law["type"] in pc.PAIR}
    for member, _family, strategy, seed_m in pn.members("ev4-dev-proof"):
        if member not in wanted:
            continue

        def predict(points, member=member, strategy=strategy, seed_m=seed_m):
            inputs = {f"p{i}": dict(p) for i, p in enumerate(points)}
            bundle, _ = ex.member_bundle(backend, member, strategy, seed_m, inputs)
            return [bundle["predictions"][f"p{i}"] for i in range(len(points))]

        found = pc.check_probes(contract, predict, seed=seed, count=count)
        for lid, values in found.items():
            readings[lid][member] = values
    return readings


def main(argv=None):
    from carbon.challenge_validator import physics_contract as pc
    from scripts.dev.battery.tuning_rescore import _standin, assemble

    parser = argparse.ArgumentParser()
    parser.add_argument("--ev4", required=True)
    parser.add_argument("--run5", required=True)
    parser.add_argument("--attack", required=True)
    parser.add_argument("--dev-results", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pairs", type=int, default=0)
    parser.add_argument("--seed", default="physics-screen-v1")
    args = parser.parse_args(argv)
    contract = pc.load(CONTRACT)
    store, ids, predictions = _standin([args.ev4, args.run5, args.attack])
    panel = assemble(store, ids, predictions, args.dev_results)
    roles = json.loads(ROLES.read_text())["roles"]
    pairs = (
        _pair_readings(panel["names"], contract, args.pairs, args.seed)
        if args.pairs
        else None
    )
    result = screen(panel, roles, contract, pair_residuals=pairs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "physics-screen.json").write_text(
        json.dumps(result, indent=1, sort_keys=True)
    )
    print(json.dumps({k: result[k] for k in ("members", "good_value")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
