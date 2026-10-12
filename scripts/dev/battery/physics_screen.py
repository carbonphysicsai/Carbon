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
Pair laws (B15 first, B16, B5-B8 and B10) use member predictions and the
byte-verified public reference pairs. `--pairs N` rebuilds members locally;
the existing synthetic controls are derived from the same reference records.
An identity-matching cache can reuse these readings without another rebuild.

DEVELOPMENT evidence on public data: aggregates only. Nothing here is a
gate, a tolerance or a margin until the owner records it.
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
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
        yield record["inputs"], {} if outputs is None else outputs


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


def screen(
    panel,
    roles,
    contract,
    *,
    pair_residuals=None,
    reference_pairs=None,
    provenance=None,
):
    from carbon.challenge_validator import physics_contract as pc

    store, ids = panel["store"], panel["ids"]
    aux = {"ocv": _ocv()}
    reference_detail = pc.case_readings(contract, _cases(store, ids), aux)
    reference = {lid: r["residuals"] for lid, r in reference_detail.items()}
    members = panel["names"]
    member_detail = {
        m: pc.case_readings(contract, _cases(store, ids, panel["predictions"][m]), aux)
        for m in members
    }
    member_res = {
        m: {lid: r["residuals"] for lid, r in rows.items()}
        for m, rows in member_detail.items()
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
    cut = statistics.median(panel["values"][m] for m in pool) if pool else None
    good = {m for m in pool if panel["values"][m] <= cut}
    base_taus = _taus(panel, members)
    tau_cache = {tuple(sorted(members)): base_taus}

    def taus(names):
        key = tuple(sorted(names))
        if key not in tau_cache:
            tau_cache[key] = _taus(panel, names)
        return tau_cache[key]

    laws = {}
    for law in contract["laws"]:
        lid = law["id"]
        if law["type"] in pc.PAIR:
            readings = (pair_residuals or {}).get(lid) or {}
            raw_readings = readings
            rows = []
            good_read = [m for m in good if readings.get(m)]
            bad_read = [m for m in bad if readings.get(m)]
            pooled = sorted(r for m in good_read for r in readings[m])
            # Diagnostic tolerances only (no reference pairs yet): 0 and
            # the good members' pooled residual quantiles.
            ref_row = (reference_pairs or {}).get(
                lid, {"residuals": [], "unresolved": 0}
            )
            ref = ref_row["residuals"]
            calibrated = bool(ref) and ref_row["unresolved"] == 0
            if calibrated:
                # A partial member reading cannot look like a passing member.
                readings = {m: v for m, v in readings.items() if len(v) == len(ref)}
                good_read = [m for m in good if readings.get(m)]
                bad_read = [m for m in bad if readings.get(m)]
            tols = (
                [(q, 0.0, pc.tolerance(ref, q=q, margin=0)) for q in QUANTILES]
                if calibrated
                else [
                    (None, None, t)
                    for t in sorted(
                        {0.0} | {pc.quantile(pooled, g) or 0.0 for g in (0.9, 0.99)}
                    )
                ]
            )
            for q, margin, tol in tols:
                for rate in RATES:
                    rejected = {
                        m
                        for m, v in readings.items()
                        if (x := pc.violation_rate(v, tol)) is not None and x > rate
                    }
                    rows.append(
                        {
                            "tolerance": tol,
                            "reference_quantile": q,
                            "margin_candidate": margin,
                            "max_violation_rate": rate,
                            "false_rejection": f"{len(rejected & set(good_read))}/{len(good_read)}",
                            "catch": f"{len(rejected & set(bad_read))}/{len(bad_read)}",
                            "caught": sorted(rejected & set(bad_read)),
                            "rejected_good": sorted(rejected & set(good_read)),
                            "reference_violation_rate": pc.violation_rate(ref, tol),
                            "catch_by_role": _role_catches(
                                rejected, {m for m in readings if readings[m]}, roles
                            ),
                            "tau_before": base_taus,
                            "tau_after": taus(
                                [
                                    m
                                    for m in members
                                    if readings.get(m) and m not in rejected
                                ],
                            ),
                            "tau_before_on_resolved": taus(
                                [m for m in members if readings.get(m)]
                            ),
                        }
                    )
            laws[lid] = {
                "name": law["name"],
                "type": law["type"],
                "role": law.get("role", "UNADOPTED_LAW_PROPOSAL"),
                "calibration": (
                    "REFERENCE_CALIBRATED_DIAGNOSTIC"
                    if calibrated
                    else "UNRESOLVED: verified reference pairs missing or incomplete"
                ),
                "gate_state": "UNRESOLVED",
                "reference_points": len(ref),
                "reference_unresolved": ref_row["unresolved"],
                "reference_residual": _distribution(ref),
                "members_read": len(readings),
                "member_residuals": {
                    m: {
                        **_distribution(raw_readings.get(m, [])),
                        "points": len(raw_readings.get(m, [])),
                        "missing_pairs": (
                            max(0, len(ref) - len(raw_readings.get(m, [])))
                            if calibrated
                            else None
                        ),
                    }
                    for m in members
                },
                "unresolved_members": sorted(m for m in members if not readings.get(m)),
                "screen": rows,
            }
            continue
        ref = reference[lid]
        resolved = {
            m
            for m in members
            if len(member_res[m][lid]) == len(ref)
            and member_detail[m][lid]["unresolved"]
            == reference_detail[lid]["unresolved"]
            and ref
        }
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
        candidates = [(q, 0.0, rate) for q in QUANTILES for rate in RATES] + [
            (1.0, m, rate) for m in margins if m for rate in RATES
        ]
        # Exact descriptive boundary that admits every resolved good member at
        # each rate. This is an unregistered margin candidate, never calibration
        # from models or a recommendation to adopt it.
        for rate in RATES:
            critical = max(
                (
                    sorted(member_res[m][lid])[
                        len(member_res[m][lid])
                        - 1
                        - int(rate * len(member_res[m][lid]))
                    ]
                    for m in resolved & good
                ),
                default=None,
            )
            if critical is not None and ref:
                candidates.append((1.0, max(0.0, critical - max(ref)), rate))
        for q, margin, rate in sorted(set(candidates)):
            tol = pc.tolerance(ref, q=q, margin=margin)
            rejected = {
                m
                for m in resolved
                if (v := pc.violation_rate(member_res[m][lid], tol)) is not None
                and v > rate
            }
            kept = [m for m in members if m in resolved and m not in rejected]
            rows.append(
                {
                    "quantile": q,
                    "margin": margin,
                    "tolerance": tol,
                    "max_violation_rate": rate,
                    "false_rejection": f"{len(rejected & good)}/{len(resolved & good)}",
                    "catch": f"{len(rejected & bad)}/{len(resolved & bad)}",
                    "caught": sorted(rejected & bad),
                    "rejected_good": sorted(rejected & good),
                    "tau_before": base_taus,
                    "tau_after": taus(kept),
                    "reference_violation_rate": pc.violation_rate(ref, tol),
                    "catch_by_role": _role_catches(rejected, resolved, roles),
                    "tau_before_on_resolved": taus(
                        [m for m in members if m in resolved]
                    ),
                }
            )
        laws[lid] = {
            "name": law["name"],
            "type": law["type"],
            "role": law.get("role", "UNADOPTED_LAW_PROPOSAL"),
            "existing_exam_gate": law.get("existing_exam_gate"),
            "reference_points": len(ref),
            "reference_unresolved": reference_detail[lid]["unresolved"],
            "unresolved_members": sorted(set(members) - resolved),
            "gate_state": "UNRESOLVED",
            "member_residuals": {
                m: {
                    **_distribution(member_res[m][lid]),
                    "points": len(member_res[m][lid]),
                    "unresolved": member_detail[m][lid]["unresolved"],
                }
                for m in members
            },
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
        "contract_digest": pc.digest(contract),
        "maturity": "DEVELOPMENT_DIAGNOSTIC",
        "notes": "Gates never substitute for verified decisions. B15 is screened first; B16 and B9 are diagnostic only. B1-B3 reference existing exam gates. No law is adopted here.",
        "validity_status": contract.get("validity_status", "HUMAN_INPUT"),
        "registered_quantile": contract["tolerance"]["quantile"],
        "registered_margin": contract["tolerance"]["margin"],
        "registered_gate_max_violation_rate": contract["tolerance"][
            "gate_max_violation_rate"
        ],
        "reference_pair_provenance": provenance,
        "members": len(members),
        "good_value": len(good),
        "good_members": sorted(good),
        "good_value_cut": cut,
        "bad": sorted(bad),
        "laws": laws,
        "b9_diagnosis": _b9_diagnosis(panel, good, contract),
    }


def _distribution(values):
    from carbon.challenge_validator import physics_contract as pc

    return {
        "p50": pc.quantile(values, 0.5),
        "p99": pc.quantile(values, 0.99),
        "max": pc.quantile(values, 1.0),
    }


def _role_catches(rejected, resolved, roles):
    return {
        role: {
            "caught": len(rejected & set(names)),
            "resolved": len(resolved & set(names)),
            "unresolved": len(set(names) - resolved),
        }
        for role, names in roles.items()
        if role in ("known_bad", "adversarial", "unsafe")
    }


def _b9_diagnosis(panel, good, contract):
    """An independent raw-curve calculation, without the law checker or tolerance."""
    from carbon.challenge_validator import physics_contract as pc

    deficits, reference_deficits, excess, affected = [], [], [], set()
    maxima = {}
    for member in sorted(good):
        for cid in panel["ids"]:
            record = panel["store"].refs[cid]
            predicted = panel["predictions"][member].get(cid)
            if (
                record.get("status", "OK") != "OK"
                or predicted is None
                or not pc.applicable(contract, record["inputs"], record["outputs"])
            ):
                continue
            actual = record["outputs"]["temperature_c"]
            curve = predicted.get("temperature_c", [])
            if len(curve) != len(actual) or not all(
                pc._number(v) for v in curve + actual
            ):
                continue
            ambient = record["inputs"]["t_amb_c"]
            dip = max(0.0, ambient - min(curve))
            ref_dip = max(0.0, ambient - min(actual))
            deficits.append(dip)
            reference_deficits.append(ref_dip)
            excess.append(max(0.0, dip - ref_dip))
            if dip > ref_dip:
                affected.add(member)
            maxima[member] = max(maxima.get(member, 0.0), max(0.0, dip - ref_dip))
    return {
        "basis": "Direct ambient - min(raw temperature curve); paired with the public reference; no quantile or tolerance used",
        "good_members_with_excess_subambient_predictions": len(affected),
        "good_members": len(good),
        "member_case_comparisons": len(deficits),
        "predicted_deficit_c": _distribution(deficits),
        "reference_deficit_c": _distribution(reference_deficits),
        "excess_over_reference_c": _distribution(excess),
        "good_member_maximum_excess_c": _distribution(list(maxima.values())),
        "descriptive_tail_counts": {
            str(level): {
                "member_cases_above": sum(x > level for x in excess),
                "good_members_above": sum(x > level for x in maxima.values()),
            }
            for level in (0.001, 0.01, 0.1, 1.0)
        },
        "tail_count_note": "Descriptive reporting bins in degC; not registered tolerances or gate proposals",
        "interpretation": "Measured model/reference discrepancy if excess is positive; not proof of real-cell physics or a qualified universal temperature-floor law. Scientific interpretation stays with the Validator and owner.",
    }


def markdown(result):
    lines = [
        "# PHYSICS-CONTRACT-01 public EV4 screen",
        "",
        "DEVELOPMENT diagnostics only. All gates remain UNRESOLVED; quantile, margin, gate rate and adoption are HUMAN_INPUT. Pair rows without verified calibration are diagnostics only.",
        "",
        result.get("notes", "Gates never substitute for verified decisions."),
        "",
        f"Panel: {result['members']} members; {result['good_value']} good-value members (loss at or below the benign reconstructed panel median).",
        "",
        "| Law | Calibration | Reference points | Tolerance candidate | Rate candidate | False rejection | Catch | Reference violation rate | Tau before / after |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for lid, law in result["laws"].items():
        lines.append(
            f"| {lid} ({law.get('role', 'UNADOPTED_LAW_PROPOSAL')}) | {law.get('calibration', 'PUBLIC_REFERENCE_DIAGNOSTIC')} | {law['reference_points']} | | | | | | |"
        )
        for row in law["screen"]:
            taus = "; ".join(
                f"{name}: {row['tau_before'].get(name)} / {row['tau_after'].get(name)}"
                for name in TAU_CANDIDATES
            )
            lines.append(
                f"| {lid} | {law.get('calibration', 'PUBLIC_REFERENCE_DIAGNOSTIC')} | {law['reference_points']} | {row['tolerance']} | {row['max_violation_rate']} | {row['false_rejection']} | {row['catch']} | {row['reference_violation_rate']} | {taus} |"
            )
    lines.extend(
        [
            "",
            "Good-value and bad-panel membership are descriptive labels, not scientific qualification. Missing member/pair readings are UNRESOLVED and are reported in JSON. Tau after a pair gate uses resolved members only; compare tau_before_on_resolved to avoid a coverage artefact.",
            "",
            "B9 raw-curve diagnosis:",
            "",
            "```json",
            json.dumps(result["b9_diagnosis"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _pair_readings(
    panel_names,
    contract,
    count,
    seed,
    plan_directory=None,
    reference_records=None,
    initial=None,
    checkpoint=None,
):
    """Rebuild the reconstructed and attack members (CPU) and read the pair
    laws at `count` probe pairs per law."""
    from carbon.battery.value import experiment as ex
    from carbon.battery.value import panel as pn
    from carbon.battery.worker import DirectBackend
    from carbon.challenge_validator import physics_contract as pc

    backend = DirectBackend(ROOT)
    wanted = set(panel_names)
    readings = initial or {
        law["id"]: {} for law in contract["laws"] if law["type"] in pc.PAIR
    }
    plan = jobs = None
    if plan_directory:
        from scripts.dev.battery.physics_calibration import public_plan

        plan, jobs, _identity = public_plan(plan_directory, contract)
    for member, _family, strategy, seed_m in pn.members("ev4-dev-proof"):
        if member not in wanted or all(member in row for row in readings.values()):
            continue

        def predict(points, member=member, strategy=strategy, seed_m=seed_m):
            inputs = {f"p{i}": dict(p) for i, p in enumerate(points)}
            bundle, _ = ex.member_bundle(backend, member, strategy, seed_m, inputs)
            return [bundle["predictions"][f"p{i}"] for i in range(len(points))]

        if plan is None:
            found = pc.probe_readings(contract, predict, seed=seed, count=count)
        else:
            from scripts.dev.battery.physics_calibration import (
                readings as planned_readings,
            )

            points = [{k: job[k] for k in contract["probe_region"]} for job in jobs]
            outputs = predict(points)
            if len(outputs) != len(jobs):
                raise pc.ContractRefused("physics_contract_prediction_count")
            by_id = {
                job["case_id"]: {"status": "OK", "inputs": point, "outputs": output}
                for job, point, output in zip(jobs, points, outputs)
            }
            from scripts.dev.battery.physics_calibration import planned_pairs

            pairs = planned_pairs(plan, by_id, contract)
            found = planned_readings({"pairs": pairs}, contract)
        for lid, values in found.items():
            readings[lid][member] = (
                values["residuals"] if values["unresolved"] == 0 else []
            )
        if checkpoint:
            checkpoint(member, {lid: row[member] for lid, row in readings.items()})
        # Rebuilds need no historical full-panel curves or compiled programs.
        # Clearing compilation caches changes resource use, not model inputs,
        # construction settings, seeds, or law arithmetic.
        runtime = sys.modules.get("jax")
        if runtime is not None:
            runtime.clear_caches()
        gc.collect()
        print(
            json.dumps(
                {
                    "public_pair_member": member,
                    "laws_resolved": sum(
                        bool(row.get(member)) for row in readings.values()
                    ),
                }
            ),
            file=sys.stderr,
            flush=True,
        )
    if reference_records is not None and plan is not None:
        from scripts.dev.battery.physics_calibration import (
            planned_pairs,
        )
        from scripts.dev.battery.physics_calibration import (
            readings as planned_readings,
        )

        for kind in pn.CONTROLS:
            member = "control-" + kind
            if member not in wanted or all(member in row for row in readings.values()):
                continue
            outputs = pn.control_predictions(kind, reference_records)
            records = {
                cid: {**record, "outputs": outputs[cid]}
                for cid, record in reference_records.items()
                if cid in outputs
            }
            found = planned_readings(
                {"pairs": planned_pairs(plan, records, contract)}, contract
            )
            for lid, row in found.items():
                readings[lid][member] = (
                    row["residuals"] if row["unresolved"] == 0 else []
                )
            if checkpoint:
                checkpoint(member, {lid: row[member] for lid, row in readings.items()})
    return readings


def public_member_names(directories, dev_results):
    """Read one public bundle at a time; match assemble's decided membership."""
    from carbon.battery.value.panel import CONTROLS

    names = {"control-" + kind for kind in CONTROLS}
    for directory in directories:
        for path in sorted(Path(directory).glob("*.json.gz")):
            with gzip.open(path, "rt") as handle:
                bundle = json.load(handle)
            member = bundle.get("member")
            if type(member) is not str or not member:
                raise ValueError("physics_public_member_identity")
            names.add(member)
            del bundle
    decided = json.loads(Path(dev_results).read_text())["decisions"]
    return sorted(names & set(decided))


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
    parser.add_argument(
        "--pair-cache-only",
        action="store_true",
        help="Rebuild public pair readings without retaining full-panel historical curves; resume an exact-identity partial cache",
    )
    parser.add_argument(
        "--probe-plan",
        help="PUBLIC calibration plan directory; use the same public pairs for member and reference diagnostics",
    )
    parser.add_argument(
        "--calibration-panel",
        help="PUBLIC directory containing MANIFEST.json, plan.json and hash-bound reference records",
    )
    parser.add_argument(
        "--pair-readings",
        help="Reuse a prior public diagnostic's cached per-member residuals; no probe inputs or predictions",
    )
    args = parser.parse_args(argv)
    contract = pc.load(CONTRACT)
    directories = [args.ev4, args.run5, args.attack]
    if args.pair_cache_only:
        if not args.pairs or not args.calibration_panel:
            raise pc.ContractRefused("physics_contract_cache_requires_calibration")
        panel = {"names": public_member_names(directories, args.dev_results)}
    else:
        store, ids, predictions = _standin(directories)
        panel = assemble(store, ids, predictions, args.dev_results)
    roles = json.loads(ROLES.read_text())["roles"]
    pair_plan = args.probe_plan or args.calibration_panel
    plan_sha = None
    if pair_plan:
        from scripts.dev.battery.physics_calibration import public_plan

        _plan, _jobs, plan_sha = public_plan(pair_plan, contract)
        if args.pairs != _plan.get("bases", args.pairs):
            raise pc.ContractRefused("physics_contract_pair_count")
    reference_pairs, provenance, reference_records = None, None, None
    if args.calibration_panel:
        from scripts.dev.battery.physics_calibration import load_directory

        reference_pairs, provenance, reference_records = load_directory(
            args.calibration_panel, contract, repository=ROOT, include_records=True
        )
    cache_identity = {
        "schema": "carbon.physics-pair-readings.v2",
        "scope": "PUBLIC_DEVELOPMENT",
        "contract_digest": pc.digest(contract),
        "plan_sha256": plan_sha,
        "public_seed": args.seed,
        "pairs_per_base": args.pairs,
        "calibration_sha256": hashlib.sha256(
            (ROOT / "scripts/dev/battery/physics_calibration.py").read_bytes()
        ).hexdigest(),
        "manifest_sha256": provenance["manifest_sha256"] if provenance else None,
        "public_members": sorted(panel["names"]),
        "pair_builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(
            (ROOT / "carbon/challenge_validator/physics_contract.py").read_bytes()
        ).hexdigest(),
    }
    if args.pair_readings:
        cached = json.loads(Path(args.pair_readings).read_text())
        pairs = cached_readings(
            cached, cache_identity, contract, allow_incomplete=args.pair_cache_only
        )
    else:
        pairs = (
            _pair_readings(
                panel["names"],
                contract,
                args.pairs,
                args.seed,
                pair_plan,
                reference_records,
            )
            if args.pairs and not args.pair_cache_only
            else None
        )
    if args.pair_cache_only:

        def checkpoint(member, rows):
            print(
                "PLT01_PAIR_MEMBER_CHECKPOINT "
                + json.dumps(
                    {"identity": cache_identity, "member": member, "readings": rows},
                    sort_keys=True,
                ),
                flush=True,
            )

        pairs = _pair_readings(
            panel["names"],
            contract,
            args.pairs,
            args.seed,
            pair_plan,
            reference_records,
            initial=pairs,
            checkpoint=checkpoint,
        )
        complete = all(set(row) == set(panel["names"]) for row in pairs.values())
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "pair-readings.json").write_text(
            json.dumps(
                {**cache_identity, "complete": complete, "readings": pairs},
                sort_keys=True,
            )
        )
        if not complete:
            raise pc.ContractRefused("physics_contract_pair_cache_incomplete")
        return 0
    result = screen(
        panel,
        roles,
        contract,
        pair_residuals=pairs,
        reference_pairs=reference_pairs,
        provenance=provenance,
    )
    result["public_source_hashes"] = {
        str(Path(p).name): hashlib.sha256(Path(p).read_bytes()).hexdigest()
        for p in [args.dev_results, ROLES, REGISTRY]
    }
    from carbon.battery.value.scoring import SCORING_REFERENCES

    result["public_source_hashes"]["scoring_references"] = hashlib.sha256(
        (ROOT / SCORING_REFERENCES).read_bytes()
    ).hexdigest()
    bundles = {
        str(i): {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(directory).glob("*.json.gz"))
        }
        for i, directory in enumerate([args.ev4, args.run5, args.attack])
    }
    result["public_source_hashes"]["prediction_bundle_manifest"] = hashlib.sha256(
        json.dumps(bundles, sort_keys=True).encode()
    ).hexdigest()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "physics-screen.json").write_text(
        json.dumps(result, indent=1, sort_keys=True)
    )
    (out / "physics-screen.md").write_text(markdown(result))
    if pairs is not None:
        (out / "pair-readings.json").write_text(
            json.dumps(
                {**cache_identity, "complete": True, "readings": pairs}, sort_keys=True
            )
        )
    print(json.dumps({k: result[k] for k in ("members", "good_value")}, sort_keys=True))
    return 0


def cached_readings(cached, identity, contract, *, allow_incomplete=False):
    from carbon.challenge_validator import physics_contract as pc

    if type(cached) is not dict or any(cached.get(k) != v for k, v in identity.items()):
        raise pc.ContractRefused("physics_contract_pair_cache_identity")
    readings = cached.get("readings")
    expected = {law["id"] for law in contract["laws"] if law["type"] in pc.PAIR}
    if type(readings) is not dict or set(readings) != expected:
        raise pc.ContractRefused("physics_contract_pair_cache_shape")
    if type(cached.get("complete")) is not bool:
        raise pc.ContractRefused("physics_contract_pair_cache_shape")
    if not allow_incomplete and cached.get("complete") is not True:
        raise pc.ContractRefused("physics_contract_pair_cache_incomplete")
    for members in readings.values():
        if type(members) is not dict or any(
            m not in identity["public_members"] for m in members
        ):
            raise pc.ContractRefused("physics_contract_pair_cache_shape")
        if cached["complete"] and set(members) != set(identity["public_members"]):
            raise pc.ContractRefused("physics_contract_pair_cache_incomplete")
        if any(
            type(row) is not list or any(not pc._number(v) or v < 0 for v in row)
            for row in members.values()
        ):
            raise pc.ContractRefused("physics_contract_pair_cache_shape")
    return readings


if __name__ == "__main__":
    sys.exit(main())
