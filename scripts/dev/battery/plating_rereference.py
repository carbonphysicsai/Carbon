"""PLATING-REREFERENCE-01 (D3): re-reference near-onset public battery cases at mesh 160.

    python scripts/dev/battery/plating_rereference.py select MAIN_CHECKOUT PDD_DIR EV4_REFERENCES > cases.json
    python -m scripts.dev.battery.plating_convergence run --cases cases.json --out DIR --mid-workers N
    python scripts/dev/battery/plating_rereference.py label MAIN_CHECKOUT cases.json DIR/records.jsonl > labels.json

The owner approved D3 (2026-10-13, "Yes to both") for the public near-onset set
inside the standing test grant; the sealed bank is excluded. The Validator set
the parameters (PLATING_REFERENCE_DECISION_2026-10-13.md, "D3 parameters"):
- the set: every public case (PDD development and EV4 public development and
  verification) whose standard (mesh-20) plating margin lies in
  (-1.97, +3.5) mV;
- one solve per case at mesh 160 (rtol 1e-6), plating margin only, cycle 1;
- the label: FEASIBLE if m160 >= 0.6 mV, INFEASIBLE if m160 < 0, UNRESOLVED
  between; claimed only where |m20| < 15 mV.

`label` records per case the mesh-20 and mesh-160 margins, the old plating
label (the reference's own check with its 1.97 mV band) and the new label, and
counts the FEASIBLE to INFEASIBLE flips. It sets no value: the window, band and
cushion are the Validator's, recorded here as given. DEVELOPMENT.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LOW_V, HIGH_V = -1.97e-3, 3.5e-3
FEASIBLE_AT_V, CLAIM_V = 0.6e-3, 15e-3
OLD_BAND_V = 1.97e-3
#: The Validator's transition rule (decision page, "Transition rule").
VERSION = "battery-plating-ref-v2"
#: The convergence check: a stratified 10 % of the window also solved at mesh
#: 40 and 80; stop before sealing v2 if any m80 - m160 exceeds the D2 residual
#: or a FEASIBLE case lands below the D2 floor (Validator's figures).
CHECK_SHARE, CHECK_RESIDUAL_V, CHECK_FLOOR_V = 0.10, 0.359e-3, 0.73e-3
CHECK_SALT = "PLATING-REREFERENCE-01/check"
#: The band was derived with observed order 0.7 (Test Lead): below it, re-derive.
MIN_ORDER = 0.7
EV4_SHA = "72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf"
EV4_CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"


def _cases(main, name, contract_path, records_path, splits):
    sys.path.insert(0, str(main))
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d

    contract = json.loads(Path(contract_path).read_text())
    jobs = {j["case_id"]: j for s in splits for j in ev.decision_cases(contract, s)}
    out = []
    for line in Path(records_path).read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (
            record.get("refined")
            or record.get("status") != "OK"
            or record["case_id"] not in jobs
        ):
            continue
        margin = d.measure(contract, record["outputs"])["plating_margin_v"]
        if LOW_V < margin < HIGH_V:
            job = jobs[record["case_id"]]
            out.append({
                "case_id": record["case_id"], "source": name, "question": job["scenario"],
                "candidate": job["candidate"], "c1": job["c1"], "c2": job["c2"],
                "t_amb_c": job["t_amb_c"], "soc0": job["soc0"], "reference_margin_v": margin,
                "reference_rung": "standard",
            })  # fmt: skip
    return out


def old_label(margin):
    """The reference's own plating check with its 1.97 mV band."""
    if margin - 0.0 > OLD_BAND_V:
        return "FEASIBLE"
    if 0.0 - margin > OLD_BAND_V:
        return "INFEASIBLE"
    return "UNRESOLVED"


def new_label(m20, m160):
    """D3's label (the Validator's parameters); None where it is not claimed."""
    if abs(m20) >= CLAIM_V:
        return None
    if m160 >= FEASIBLE_AT_V:
        return "FEASIBLE"
    if m160 < 0:
        return "INFEASIBLE"
    return "UNRESOLVED"


def select(main, pdd_dir, ev4_references):
    main, pdd = Path(main), Path(pdd_dir)
    ev4 = Path(ev4_references)
    if hashlib.sha256(ev4.read_bytes()).hexdigest() != EV4_SHA:
        raise SystemExit("refused: the public EV4 reference copy changed")
    cases = _cases(
        main, "pdd", pdd / "contract.json", pdd / "records.jsonl", ["development"]
    )
    cases += _cases(
        main, "ev4", main / EV4_CONTRACT, ev4, ["development", "verification"]
    )
    # The 10 % convergence subsample, stratified by source and by where m20
    # sits in the window (below 0, in the old band, above it).
    strata = {}
    for case in cases:
        m = case["reference_margin_v"]
        where = "below0" if m < 0 else "band" if m <= OLD_BAND_V else "above"
        strata.setdefault((case["source"], where), []).append(case)
    for members in strata.values():
        members.sort(
            key=lambda c: hashlib.sha256(
                f"{CHECK_SALT}:{c['case_id']}".encode()
            ).hexdigest()
        )
        for case in members[: max(1, round(CHECK_SHARE * len(members)))]:
            case["convergence_check"] = True
    return {
        "schema": "carbon.battery.plating-convergence-cases.v1",
        "ladder": "re-reference",
        "rule": "D3: every public PDD development and EV4 public case whose standard plating "
        f"margin is in ({LOW_V * 1e3:g}, {HIGH_V * 1e3:g}) mV",
        "source": {
            "pdd_contract_sha256": hashlib.sha256((pdd / "contract.json").read_bytes()).hexdigest(),
            "pdd_records_sha256": hashlib.sha256((pdd / "records.jsonl").read_bytes()).hexdigest(),
            "ev4_references_sha256": EV4_SHA,
        },
        "counts": {s: sum(c["source"] == s for c in cases) for s in ("pdd", "ev4")},
        "convergence_check_cases": sum(bool(c.get("convergence_check")) for c in cases),
        "cases": cases,
    }  # fmt: skip


def label(cases_path, records_path):
    cases = json.loads(Path(cases_path).read_text())["cases"]
    from scripts.dev.battery import plating_convergence as pc

    solved, rungs = {}, {}
    for line in Path(records_path).read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            if record["mesh"] == 160:
                solved[record["case"]] = record
            if record.get("status") == "OK":
                rungs.setdefault(record["case"], {})[record["mesh"]] = record[
                    "plating_margin_v"
                ]
    rows, flips, checks = [], {}, []
    for i, case in enumerate(cases):
        record = solved.get(i)
        m20 = case["reference_margin_v"]
        m160 = (
            record.get("plating_margin_v")
            if record and record.get("status") == "OK"
            else None
        )
        old = old_label(m20)
        new = None if m160 is None else new_label(m20, m160)
        rows.append({
            "case_id": case["case_id"], "source": case["source"], "question": case["question"],
            "c1": case["c1"], "c2": case["c2"], "t_amb_c": case["t_amb_c"], "soc0": case["soc0"],
            "m20_mv": m20 * 1e3, "m160_mv": None if m160 is None else m160 * 1e3,
            "old_label": old, "new_label": new,
            "plating_reference": {"version": VERSION, "rule": "m160-d3" if m160 is not None else "pending-m160"},
            "solve_status": None if record is None else record.get("status"),
        })  # fmt: skip
        mine = rungs.get(i, {})
        if case.get("convergence_check") and all(m in mine for m in (40, 80, 160)):
            p, extrapolated = pc.richardson(mine[40], mine[80], mine[160])
            checks.append({
                "case_id": case["case_id"], "m40_mv": mine[40] * 1e3, "m80_mv": mine[80] * 1e3,
                "m160_mv": mine[160] * 1e3, "d80_160_mv": (mine[80] - mine[160]) * 1e3,
                "observed_order": p,
                "extrapolated_mv": None if extrapolated is None else extrapolated * 1e3,
            })  # fmt: skip
        if new is not None:
            flips[f"{old}->{new}"] = flips.get(f"{old}->{new}", 0) + 1
    report = {
        "schema": "carbon.battery.plating-rereference.v1",
        "status": "DEVELOPMENT; Validator parameters as given; not a qualified reference version",
        "parameters": {"window_mv": [LOW_V * 1e3, HIGH_V * 1e3], "feasible_at_mv": FEASIBLE_AT_V * 1e3,
                       "infeasible_below_mv": 0.0, "claimed_within_mv": CLAIM_V * 1e3,
                       "old_band_mv": OLD_BAND_V * 1e3},
        "cases": len(rows),
        "solved": sum(r["m160_mv"] is not None for r in rows),
        "transitions": dict(sorted(flips.items())),
        "feasible_to_infeasible": flips.get("FEASIBLE->INFEASIBLE", 0),
        "convergence_check": {
            "cases": len(checks),
            "max_d80_160_mv": max((c["d80_160_mv"] for c in checks), default=None),
            "min_observed_order": min((c["observed_order"] for c in checks if c["observed_order"] is not None), default=None),
            "residual_exceeded": [c["case_id"] for c in checks if c["d80_160_mv"] > CHECK_RESIDUAL_V * 1e3],
            "rows": checks,
        },
        "feasible_below_floor": [r["case_id"] for r in rows if r["new_label"] == "FEASIBLE" and r["m160_mv"] < CHECK_FLOOR_V * 1e3],
        "stop_before_sealing": None,
        "rows": rows,
    }  # fmt: skip
    check = report["convergence_check"]
    reasons = []
    if check["residual_exceeded"]:
        reasons.append("m80 - m160 above the D2 residual")
    if report["feasible_below_floor"]:
        reasons.append("a FEASIBLE label below the D2 floor")
    if (
        check["min_observed_order"] is not None
        and check["min_observed_order"] < MIN_ORDER
    ):
        reasons.append("observed order below the band's assumed order")
    report["stop_before_sealing"] = reasons
    return report


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "select":
        result = select(*sys.argv[2:5])
    elif command == "label":
        sys.path.insert(0, sys.argv[2])
        result = label(*sys.argv[3:5])
    else:
        raise SystemExit("usage: plating_rereference.py select|label ...")
    print(json.dumps(result, indent=1, sort_keys=True))
