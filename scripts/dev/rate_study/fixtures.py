"""SUBMISSION-RATE-STUDY-01 dry-run FIXTURES: synthetic operator records.

Every record is stamped `provenance: "FIXTURE"`. Nothing here touches a bank,
a pool, a validator, a host or a seed that gates anything: values come from a
public string seed, and the analysis refuses to write a FIXTURE report into the
committed evidence tree. The numbers mean nothing scientifically; they exist so
the analysis and its tests can be exercised with a known answer (an honest arm
with no drift, an adversary whose drift grows with probes).
"""

from __future__ import annotations

import hashlib

import numpy as np

FIXTURE_SEED = "SUBMISSION-RATE-STUDY-01/fixture/"
WINDOWS = 12


def _generator(*parts):
    digest = hashlib.sha256(
        (FIXTURE_SEED + "/".join(map(str, parts))).encode()
    ).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def run_records(
    arm, rate, replicate, *, drift_per_probe=0.0, noise=0.01, windows=WINDOWS
):
    """One synthetic run: `3 * rate` scored submissions per window. `D` is noise
    plus `drift_per_probe` per case-probe; the case-probe count rises by one per
    submission (the plan's `P = E x k`, simplified for a fixture)."""
    generator = _generator(arm, rate, replicate)
    records, t = [], 0
    for window in range(1, windows + 1):
        for _ in range(3 * rate):
            t += 1
            probes = t
            d = float(drift_per_probe * probes + generator.normal(0.0, noise))
            s_current = 1.0
            s_fresh = s_current + d
            records.append(
                {
                    "arm": arm,
                    "rate": rate,
                    "replicate": replicate,
                    "window": window,
                    "t": t,
                    "probes_batch": probes,
                    "probes_case_max": probes,
                    "d_index": d,
                    "s_current": s_current,
                    "s_fresh": s_fresh,
                    "state": "SCORED",
                    "wall_s": float(1.0 + 0.1 * generator.random()),
                    "provenance": "FIXTURE",
                }
            )
    return records


def study(arms_drift, *, replicates=4, windows=WINDOWS, noise=0.01, first_replicate=1):
    """Records for several arms at rates 1, 2, 4. `arms_drift` maps arm to a
    function of the rate giving that arm's drift per probe."""
    records = []
    for arm, drift in arms_drift.items():
        for rate in (1, 2, 4):
            for replicate in range(first_replicate, first_replicate + replicates):
                records.extend(
                    run_records(
                        arm,
                        rate,
                        replicate,
                        drift_per_probe=drift(rate),
                        noise=noise,
                        windows=windows,
                    )
                )
    return records
