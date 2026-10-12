"""CONTROL-VARIATE-PREDICT-01, METHOD-ONLY: leave-one-out fits on the public
two-rung pairs themselves.

    python loco_fit_on_pairs.py --pairs-dir DIR --out DIR

THIS IS NOT A MEMBER. No qualified member can predict the v3 battery or the
10p/12s motor cases (their TRAIN sets are unsolved), so, on the Test Lead's
decision, each case is predicted by a small fixed model fitted on the OTHER
pair cases' registered-rung values. The predictions give a first estimate of
rho (the correlation of a case's paired difference judged against the coarse
and against the fine reference). They are evidence about nothing else: not a
member, not a Carbon arm, not a value claim.

Data: Data Collection's PUBLIC_DEVELOPMENT two-rung pairs; each file is
checked against MANIFEST.json before use. No sealed, hidden or tuning data.

Fit target: the registered rung only (battery `standard`, motor `rung1_49`),
so a prediction does not depend on the rung it is later judged against.

Methods (hyperparameters fixed here, before any result was seen):
- krr:   RBF kernel ridge, length 0.5 on [0,1]-scaled inputs, lambda 1e-3
- knn:   3 nearest, inverse-distance weights
- ridge: quadratic features, ridge alpha 1e-2
Hold-outs: `loco` leaves out one case; motor also has `lodo`, which leaves
out every case of the held-out case's design (the stricter test).

Rho (reported in meta.json): for each challenge and metric, error e = |pred -
reference| against the coarse (registered) rung and against the fine rung
(battery rung 2; motor rung 2). For each method pair (leader = lower mean
error against the fine reference), d = (e_L - e_c) / mean(e_L); rho is the
Pearson correlation over cases of d judged against coarse vs fine. A metric
whose reference is constant (relative spread < 1e-9) is skipped.
"""

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

PAIRS_HOME = "~carbon/shared/evidence/two-rung-pairs"
LABEL = (
    "METHOD-ONLY: leave-one-out fit on the two-rung pairs themselves; not a "
    "member, not a Carbon arm, not evidence about any member"
)
BATTERY_METRICS = (
    "charging_t_max_c",
    "minutes",
    "plating_min_v",
    "q30_over_q1",
    "v_max_v",
)
MOTOR_METRICS = ("mean_nm", "pk_pk_nm")
GRAMMAR = (
    "airgap_mm",
    "coverage",
    "magnet_mm",
    "opening_frac",
    "slot_bottom_mm",
    "tooth_frac",
)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load(pairs_dir):
    pairs_dir = Path(pairs_dir)
    manifest = json.loads((pairs_dir / "MANIFEST.json").read_bytes())
    assert manifest["schema"] == "carbon.two-rung-pairs.v1"
    assert manifest["scope"].startswith("PUBLIC_DEVELOPMENT")
    out = {}
    for name in ("battery-pairs.jsonl", "motor-pairs.jsonl"):
        data = (pairs_dir / name).read_bytes()
        want = manifest["files"][name]
        if sha(data) != want["sha256"]:
            raise SystemExit(f"DIGEST MISMATCH {name}")
        rows = [json.loads(x) for x in data.decode().splitlines() if x]
        assert len(rows) == want["rows"]
        out[name] = (sha(data), rows)
    return out


# -- features -------------------------------------------------------------------------------
def battery_features(rows):
    inp = [r["inputs"] for r in rows]
    c1 = np.log([i["c1"] for i in inp])
    c2 = np.log([i["c2"] for i in inp])
    sv = np.array([i["switch_v"] for i in inp])
    amb = np.array([i["ambient_c"] for i in inp])
    cool = np.array([i["cooling"] for i in inp])

    def mm(v):  # scaling uses inputs only, never targets
        return (v - v.min()) / (v.max() - v.min())

    cols = [mm(amb), mm(c1), mm(c2), mm(sv)]
    cols += [0.5 * (cool == c).astype(float) for c in (1.0, 2.0, 3.0, 4.0)]
    return np.stack(cols, 1)


def motor_features(rows):
    cols = []
    for g in GRAMMAR:
        v = np.array([r["design"][g] for r in rows])
        cols.append((v - v.min()) / (v.max() - v.min()))
    j = np.array([r["j_a_mm2"] for r in rows]) / 10.0
    gm = np.array([r["gamma_deg"] for r in rows]) / 10.0
    return np.stack(cols + [j, 0.5 * gm, 0.5 * np.abs(gm)], 1)


def battery_targets(rows, rung):
    return np.array([[r[rung]["values"][m] for m in BATTERY_METRICS] for r in rows])


def motor_targets(rows, rung):
    return np.array([[r[rung][m] for m in ("mean_nm", "pk_pk_nm")] for r in rows])


# -- models ---------------------------------------------------------------------------------
def d2(a, b):
    return ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)


def fit_predict(method, xtr, ytr, xte):
    mu, sd = ytr.mean(0), ytr.std(0) + 1e-12
    z = (ytr - mu) / sd
    if method == "krr":
        k = np.exp(-d2(xtr, xtr) / (2 * 0.5**2))
        alpha = np.linalg.solve(k + 1e-3 * np.eye(len(xtr)), z)
        pred = np.exp(-d2(xte, xtr) / (2 * 0.5**2)) @ alpha
    elif method == "knn":
        dist = np.sqrt(d2(xte, xtr))
        idx = np.argsort(dist, axis=1, kind="stable")[:, :3]
        w = 1.0 / (np.take_along_axis(dist, idx, 1) + 1e-9)
        pred = (w[:, :, None] * z[idx]).sum(1) / w.sum(1)[:, None]
    elif method == "ridge":

        def quad(x):
            n, p = x.shape
            cross = [
                x[:, i] * x[:, j]
                for i, j in itertools.combinations_with_replacement(range(p), 2)
            ]
            return np.concatenate([np.ones((n, 1)), x, np.stack(cross, 1)], 1)

        a, b = quad(xtr), quad(xte)
        reg = 1e-2 * np.eye(a.shape[1])
        reg[0, 0] = 0
        pred = b @ np.linalg.solve(a.T @ a + reg, a.T @ z)
    else:
        raise ValueError(method)
    return pred * sd + mu


def holdout(method, x, y, groups):
    """Predict every row from a fit on the rows outside its group."""
    out = np.empty_like(y)
    for g in sorted(set(groups)):
        te = np.array([i for i, h in enumerate(groups) if h == g])
        tr = np.array([i for i, h in enumerate(groups) if h != g])
        out[te] = fit_predict(method, x[tr], y[tr], x[te])
    return out


# -- rho ------------------------------------------------------------------------------------
def rho_report(preds, coarse, fine, names):
    """`{metric: {"rho_median", "pairs": [...]}}` for one challenge."""
    rep = {}
    for k, name in enumerate(names):
        ref = fine[:, k]
        if np.ptp(ref) < 1e-9 * (abs(ref).mean() + 1e-12):
            rep[name] = {"rho": None, "note": "reference constant: skipped"}
            continue
        err_c = {m: abs(p[:, k] - coarse[:, k]) for m, p in preds.items()}
        err_f = {m: abs(p[:, k] - fine[:, k]) for m, p in preds.items()}
        leader = min(err_f, key=lambda m: err_f[m].mean())
        pairs = []
        for m in sorted(err_f):
            if m == leader:
                continue
            dc = (err_c[leader] - err_c[m]) / err_c[leader].mean()
            df = (err_f[leader] - err_f[m]) / err_f[leader].mean()
            pairs.append(
                {
                    "leader": leader,
                    "challenger": m,
                    "rho": float(np.corrcoef(dc, df)[0, 1]),
                }
            )
        rep[name] = {"rho": float(np.median([p["rho"] for p in pairs])), "pairs": pairs}
    return rep


def write_member(out, member, case_ids, names, pred, case_file, digest):
    rows = [
        {
            "member": member,
            "case_id": cid,
            "status": "PREDICTED",
            "outputs": {n: float(v) for n, v in zip(names, p)},
            "label": LABEL,
            "case_file": f"{PAIRS_HOME}/{case_file}",
            "case_file_digest": "sha256:" + digest,
        }
        for cid, p in zip(case_ids, pred)
    ]
    path = Path(out) / "predictions" / (member.replace("/", "-") + ".jsonl.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(path, "wb", mtime=0) as f:
        f.write("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode())
    return path.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = load(a.pairs_dir)
    meta = {
        "label": LABEL,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "challenges": {},
    }
    methods = ("krr", "knn", "ridge")

    bd, br = files["battery-pairs.jsonl"]
    xb, yb = battery_features(br), battery_targets(br, "standard")
    gb = list(range(len(br)))
    ids = [r["standard"]["source"] for r in br]
    preds = {}
    for m in methods:
        p = holdout(m, xb, yb, gb)
        member = f"loco-fit-on-pairs-battery/{m}"
        write_member(a.out, member, ids, BATTERY_METRICS, p, "battery-pairs.jsonl", bd)
        preds[member] = p
    r2 = battery_targets(br, "rung2")
    meta["challenges"]["battery"] = {
        "cases": len(br),
        "fit_target": "standard rung",
        "judged": "coarse = standard, fine = rung2",
        "rho": rho_report(preds, yb, r2, BATTERY_METRICS),
    }
    three = [i for i, r in enumerate(br) if "rung3" in r]
    r3 = battery_targets([br[i] for i in three], "rung3")
    meta["challenges"]["battery"]["rho_rung3_subset"] = {
        "cases": len(three),
        "judged": "coarse = standard, fine = rung3",
        "rho": rho_report(
            {m: p[three] for m, p in preds.items()}, yb[three], r3, BATTERY_METRICS
        ),
    }

    md, mr = files["motor-pairs.jsonl"]
    xm, ym = motor_features(mr), motor_targets(mr, "rung1_49")
    ids = [r["rung1_49"]["source"] for r in mr]
    design = [json.dumps(r["design"], sort_keys=True) for r in mr]
    meta["challenges"]["motor"] = {
        "cases": len(mr),
        "fit_target": "rung1 (49-position) reduction",
        "judged": "coarse = rung1, fine = rung2 (97-position)",
    }
    r2 = motor_targets(mr, "rung2_97")
    for hold, groups in (("loco", list(range(len(mr)))), ("lodo", design)):
        preds = {}
        for m in methods:
            p = holdout(m, xm, ym, groups)
            member = f"{hold}-fit-on-pairs-motor/{m}"
            write_member(a.out, member, ids, MOTOR_METRICS, p, "motor-pairs.jsonl", md)
            preds[member] = p
        meta["challenges"]["motor"][f"rho_{hold}"] = rho_report(
            preds, ym, r2, MOTOR_METRICS
        )
    # battery members are named loco-*; motor loco-* and lodo-* share a folder
    meta["case_files"] = {
        "battery-pairs.jsonl": "sha256:" + bd,
        "motor-pairs.jsonl": "sha256:" + md,
    }
    (Path(a.out) / "meta-loco.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in meta["challenges"].items()}, indent=1, sort_keys=True
        )[:6000]
    )


if __name__ == "__main__":
    main()
