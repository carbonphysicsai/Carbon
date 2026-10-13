"""D2 final panel (Validator spec via Test Lead, 2026-10-13) from the public EV4
references RES-12 binned (sha256 72ea300b...): all FEASIBLE candidates at
2-4 mV, about 10 positive FEASIBLE at 4-8 mV stratified c1 low/high x T_amb
cold/warm with the 9 C / SOC 0.06 corner included, and the 4 negative pairs."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # a main checkout
from carbon.battery.value import contract as ev  # noqa: E402
from carbon.battery.value import decision as d  # noqa: E402

REF = Path(sys.argv[2])
REF_SHA = "72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf"
CONTRACT = (
    Path(sys.argv[1])
    / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
)
SALT = "PLATING-CONVERGENCE-02/D2-final"
NEGATIVE = (
    ("V-T9-S0.06", 1.25, 0.6),
    ("V-T9-S0.06", 1.5, 0.6),
    ("V-T9-S0.06", 1.0, 0.6),
    ("V-T9-S0.22", 1.0, 0.6),
)

raw = REF.read_bytes()
assert hashlib.sha256(raw).hexdigest() == REF_SHA, "EV4 public reference copy changed"
contract = json.loads(CONTRACT.read_text())
by_inputs = {}
for line in raw.decode().splitlines():
    if line.strip():
        r = json.loads(line)
        i = r["inputs"]
        by_inputs[(i["c1"], i["c2"], i["t_amb_c"], i["soc0"])] = r
cands = ev.candidates(contract)
rows = []
for split in ("development", "verification"):
    for s in ev.scenarios(contract, split):
        refs = {}
        for c in cands:
            for k, (t, soc) in enumerate(s["conditions"]):
                r = by_inputs.get((c["c1"], c["c2"], float(t), float(soc)))
                if r is not None:
                    refs[(c["id"], k)] = r
        out = d.assess_reference(contract, s, cands, refs)
        for c in cands:
            v = out[c["id"]]
            if "quantities" not in v:
                continue
            t, soc = s["conditions"][0]
            rows.append({
                "case_id": f"ev4:{s['id']}:{c['id']}:0", "question": s["id"], "split": split,
                "candidate": c["id"], "c1": c["c1"], "c2": c["c2"], "t_amb_c": float(t), "soc0": float(soc),
                "reference_margin_v": v["quantities"][0]["plating_margin_v"], "reference_status": v["status"],
                "reference_rung": "standard",
            })  # fmt: skip

order = lambda r: hashlib.sha256(
    f"{SALT}:{r['case_id']}".encode()
).hexdigest()  # noqa: E731
mv = lambda r: r["reference_margin_v"] * 1e3  # noqa: E731
tier1 = [r for r in rows if r["reference_status"] == "FEASIBLE" and 2 < mv(r) <= 4]
pool = [r for r in rows if r["reference_status"] == "FEASIBLE" and 4 < mv(r) <= 8]
tier2 = []
corner = [r for r in pool if r["t_amb_c"] == 9.0 and r["soc0"] == 0.06]
if corner:
    tier2.append(sorted(corner, key=order)[0])
for high in (False, True):
    for cold in (True, False):
        stratum = sorted(
            (r for r in pool if (r["c1"] >= 1.25) == high and (r["t_amb_c"] < 20) == cold and r not in tier2),
            key=order,
        )  # fmt: skip
        tier2 += stratum[: 3 if cold else 2]
tier2 = tier2[:10]
tier3 = [
    next(r for r in rows if r["question"] == q and r["c1"] == c1 and r["c2"] == c2)
    for q, c1, c2 in NEGATIVE
]
for tag, tier in (
    ("feasible_2_4mV", tier1),
    ("feasible_4_8mV", tier2),
    ("negative_pair", tier3),
):
    for r in tier:
        r["panel_tier"] = tag
cases = tier1 + tier2 + tier3
doc = {
    "schema": "carbon.battery.plating-convergence-cases.v1",
    "ladder": "panel",
    "rule": "D2 final (Validator spec via Test Lead 2026-10-13), public EV4 references sha256 "
    f"{REF_SHA}: every FEASIBLE candidate with standard margin in (2,4] mV; up to 10 FEASIBLE in (4,8] mV, "
    "the 9 C / SOC 0.06 corner first, then c1 low/high x T_amb cold (<20 C, 3 each) / warm (2 each) in "
    f"sha256('{SALT}:'+case_id) order; the 4 named negative pairs",
    "source": {"ev4_references_sha256": REF_SHA,
               "contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest()},
    "counts": {"feasible_2_4mV": len(tier1), "feasible_4_8mV": len(tier2), "negative_pair": len(tier3)},
    "cases": cases,
}  # fmt: skip
print(json.dumps(doc, indent=1, sort_keys=True))
