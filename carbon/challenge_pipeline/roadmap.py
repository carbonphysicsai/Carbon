"""The Challenge Roadmap's arithmetic: priority queue, false-feasible bound and
deployment leaderboard.

The authority is `Design_Specs/Challenge_Roadmap.md` (rev 2.0), adopted by
OWNER-CHALLENGE-ROADMAP-01. This module is a port of the roadmap page's
script, kept line for line where it can be:
- `speed_score` and `rank_all` are its §04 queue (`speedScore`, `rankAll`);
- `ff_upper` is the §03 false-feasible bound (`ffUpper`);
- `board_rows` is the §05 leaderboard (`boardRows`).

The family data are in `families.json`, transcribed from the same page. The
frequency and value labels are the owners' planning judgments, and the solve
times are engineering estimates for each v1 scope until Design measures them.
Nothing here sets or changes any of them.
"""

from __future__ import annotations

import functools
import json
import math
from pathlib import Path

FAMILIES = Path(__file__).with_name("families.json")

#: The roadmap's equal weighting of frequency, value and solve time (§04).
EQUAL_WEIGHTS = {"F": 1, "V": 1, "S": 1}


def load_families(path=FAMILIES):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def speed_score(seconds):
    """1 under 1 s, 2 for 1-10 s, 3 for 10-60 s, 4 for 1-10 min, 5 above."""
    for score, bound in enumerate((1, 10, 60, 600), start=1):
        if seconds < bound:
            return score
    return 5


def rank_all(doc, times=None, weights=None):
    """The queue, one row per family in the order they enter the pipeline.

    `times` maps a family id to its measured p50 in seconds. A family without
    one is ranked on its v1-scope estimate. Ties go to solve time, then value,
    then the v1.0 priority, as in §04.
    """
    w = weights or EQUAL_WEIGHTS
    wf, wv, ws = (max(0.0, float(w.get(key) or 0)) for key in ("F", "V", "S"))
    if wf + wv + ws == 0:
        wf = wv = ws = 1.0
    times = times or {}
    rows = []
    for family in doc["families"]:
        f = doc["frequency_scores"][family["fL"]]
        v = doc["value_scores"][family["vL"]]
        measured = times.get(family["id"])
        t = measured if measured is not None else family["est"]["typ"]
        s = speed_score(t)
        rows.append(
            {
                "family": family,
                "F": f,
                "V": v,
                "S": s,
                "t": t,
                "source": "measured" if measured is not None else "estimate",
                "composite": (wf * f + wv * v + ws * s) / (wf + wv + ws),
            }
        )
    rows.sort(key=lambda r: (-r["composite"], -r["S"], -r["V"], r["family"]["n"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        row["move"] = row["family"]["n"] - rank
    return rows


def prerequisites_later(rows, stage_of):
    """Each family's prerequisites that rank below it and are still queued:
    pull them forward or build them inside the challenge (§04)."""
    rank = {row["family"]["id"]: row["rank"] for row in rows}
    return {
        row["family"]["id"]: [
            need
            for need in row["family"]["needs"]
            if rank[need] > row["rank"] and stage_of(need) == "queued"
        ]
        for row in rows
    }


def _binomial_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    lp, lq, base = math.log(p), math.log1p(-p), math.lgamma(n + 1)
    total = sum(
        math.exp(
            base - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq
        )
        for i in range(k + 1)
    )
    return min(1.0, total)


def ff_upper(k, n):
    """One-sided 95 % upper bound on the false-feasible rate from `k` events in
    `n` independent scenarios (Clopper-Pearson). With no events it is
    1 - 0.05**(1/n). None when the counts are not a valid pair."""
    if not (isinstance(n, int) and n >= 1 and isinstance(k, int) and 0 <= k <= n):
        return None
    if k == 0:
        return 1 - math.pow(0.05, 1 / n)
    if k == n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _binomial_cdf(k, n, mid) > 0.05:
            lo = mid
        else:
            hi = mid
    return hi


def has_results(record):
    return record is not None and any(
        record.get(key) is not None for key in ("rho", "attC", "attH")
    )


def board_rows(records, rubric, composites):
    """The leaderboard: eligible challenges first, by closest score-to-value
    match, then the rest with the reasons they are not eligible (§05).

    `records` maps a family id to its pipeline record, `rubric` holds the
    thresholds (None until set), and `composites` maps a family id to its
    queue composite. Only records with Track A or B results appear.
    """
    rubric = rubric or {}
    rubric_set = all(rubric.get(key) is not None for key in ("minRho", "maxFF", "minN"))
    max_c = rubric.get("maxC") if rubric.get("maxC") is not None else 0
    max_h = rubric.get("maxH") if rubric.get("maxH") is not None else 0
    rows = []
    for fid, r in records.items():
        if not has_results(r):
            continue
        ff = (
            ff_upper(r["k"], r["n"])
            if r.get("n") is not None and r.get("k") is not None
            else None
        )
        why = []
        if r["stage"] not in ("ready", "deployed"):
            why.append(
                "Still in test" if r["stage"] in ("test", "protocol") else "Not ready"
            )
        if r.get("attC") is None or r.get("attH") is None:
            why.append("No attack results")
        else:
            if r["attC"] > max_c:
                why.append("Open critical findings")
            if r["attH"] > max_h:
                why.append("Open high findings")
        if r.get("rho") is None:
            why.append("No rank agreement")
        if not rubric_set:
            why.append("Rubric not set")
        else:
            if r.get("rho") is not None and r["rho"] < rubric["minRho"]:
                why.append("Rank agreement below threshold")
            if r.get("n") is None or r["n"] < rubric["minN"]:
                why.append("Too few scenarios")
            if ff is None or ff * 100 > rubric["maxFF"]:
                why.append("False-feasible bound above threshold")
            if rubric.get("maxReg") is not None and (
                r.get("regret") is None or r["regret"] > rubric["maxReg"]
            ):
                why.append("Regret above threshold")
        rows.append(
            {
                "fid": fid,
                "record": r,
                "ff": ff,
                "why": why,
                "ok": not why,
                "minor": (r.get("attM") or 0) + (r.get("attL") or 0),
                "composite": composites.get(fid, 0),
            }
        )

    def order(a, b):
        ra = -2 if a["record"].get("rho") is None else a["record"]["rho"]
        rb = -2 if b["record"].get("rho") is None else b["record"]["rho"]
        if rb != ra:
            return -1 if rb < ra else 1
        fa = 2 if a["ff"] is None else a["ff"]
        fb = 2 if b["ff"] is None else b["ff"]
        if fa != fb:
            return -1 if fa < fb else 1
        ga = 1e9 if a["record"].get("regret") is None else a["record"]["regret"]
        gb = 1e9 if b["record"].get("regret") is None else b["record"]["regret"]
        if ga != gb:
            return -1 if ga < gb else 1
        if a["minor"] != b["minor"]:
            return -1 if a["minor"] < b["minor"] else 1
        if a["composite"] != b["composite"]:
            return -1 if b["composite"] < a["composite"] else 1
        return 0

    key = functools.cmp_to_key(order)
    eligible = sorted((row for row in rows if row["ok"]), key=key)
    others = sorted((row for row in rows if not row["ok"]), key=key)
    for position, row in enumerate(eligible, start=1):
        row["position"] = position
    return eligible + others
