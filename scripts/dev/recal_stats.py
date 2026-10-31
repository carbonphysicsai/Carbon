#!/usr/bin/env python3
"""Rebuild-noise statistics for the launch recalibration (GPUYARD_GPU4_REPEAT_EVIDENCE_RULING_20261030, item 4).

Reads the measured totals and state digests, writes one measurement document, and prints its sha256, which becomes the
registered `measurement_digest`. It registers nothing: writing koth_rebuild_noise.json is a reviewed change of its own.

Input (JSON), schema "carbon.recal-stats.input.v1":
  {"schema": ..., "challenges": {<name>: {
      "pack_digest": <64 hex>, "class_record_digest": <64 hex>,
      "control_basis_bit_identical": "<text>", "control_basis_within_noise": "<text>",
      "panel": [<entry_id>, ...],                       # panel order; the control search runs in this order
      "members": {<entry_id>: {
          "reference_fingerprint": <64 hex>,
          "seed0_totals": [10 numbers],                  # 10 rebuilds at the official seed 0
          "state_digests": [10 x 64 hex],                # one per rebuild
          "within_noise": true|false,                    # only read when no member is bit-identical
          "seed0_legs": [10 x {"A", "D", "decision_outcome"}]}},   # only with --judge-pack
      "control_seed_totals": {<entry_id>: [10 numbers]},  # the control rebuilt with seed=0..9
      "control_seed_legs": {<entry_id>: [10 x {"A", "D", "decision_outcome"}]}   # only with --judge-pack
  }}}

--judge-pack CHALLENGE=SCORE_PACK.json (repeatable). The recalibration runs on CALIBRATION packs (leg minimums null).
Minimums only change a row's status, never its legs or total (dual_score.score), so a rebuild that fails the judge
minimums has a VALID total and is a valid rebuild-noise measurement: it stays in sigma and the seed spread (Validator
ruling, 2026-10-31, reversing 2026-10-30). Every non-gated rebuild is still re-judged by `dual_score.score` itself; one that
comes out REQUIRED_LEG_MINIMUM_FAILED is counted and reported (`minimum_failed`, per member and for the control seeds) and
its recorded total must equal what the same legs give with the minimums removed. The minimums, the sha256 of the judge
pack file and the pack's digest are in the output (`judge_minimums`) and printed as a header. The judge pack file carries
a top-level `pack_digest`: it is checked for form, taken off before the pack is registered, compared with the digest the
registration computes, and both are recorded.

The margin (OWNER-CROWN-MARGIN-2SD-01) is value = max(5 x sigma, 2 x seed_sd), where seed_sd is the SAMPLE standard
deviation (n - 1, `statistics.stdev`) of the control's kept per-seed totals; `seed_spread` (max - min) is still reported for
reference and `spread_rule` is "2sd". If 5 x sigma and 2 x seed_sd are both 0 the run is refused (no resolution floor).

A rebuild whose total is null because a hard gate failed has no total (A and D may still be numbers). With --judge-pack
its legs entry shows the failure (`gate_failed`: a decision_outcome or status of GATE_FAILED / MANDATORY_GATE_FAILED, or a
`gates` map with a value that is not PASS / true) and the rebuild is GATED: excluded from sigma and the seed spread,
counted separately (`gated`: by member and for the control seeds). A null total WITHOUT a gate failure is a refusal:
missing data is not gated. At least 2 kept (non-gated) rebuilds are needed for any sigma or spread, else a refusal.

The control is the first panel member that is bit-identical AND whose official seed-0 rebuild is not gated (else the
within-noise rule, with the same seed-0 condition). Failing the judge minimums no longer disqualifies a control; whether
the chosen control's official seed-0 row fails them is reported as `control_fails_judge_minimums`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

SCHEMA_IN = "carbon.recal-stats.input.v1"
SCHEMA_OUT = "carbon.recal-stats.measurement.v1"
N = 10
#: OWNER-CROWN-MARGIN-2SD-01: the margin is max(5 x sigma, 2 x the sample sd of the control's kept per-seed totals).
SEED_SD_MULTIPLE = 2
SPREAD_RULE = "2sd"
_HEX = re.compile(r"[0-9a-f]{64}")


class StatsError(ValueError):
    pass


def _digest(value, where):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise StatsError(f"{where}: not a full 64-hex digest")
    return value


def _totals(value, where, allow_null=False):
    """The N totals as floats. ``allow_null`` (only with a judge pack, which carries the legs that can show a gate
    failure) lets a null stand for a gated rebuild; `keep` then refuses any null the legs do not explain.
    """
    if not isinstance(value, list) or len(value) != N:
        raise StatsError(f"{where}: need exactly {N} totals")
    out = []
    for x in value:
        if x is None and allow_null:
            out.append(None)
            continue
        if (
            isinstance(x, bool)
            or not isinstance(x, (int, float))
            or not math.isfinite(x)
        ):
            raise StatsError(f"{where}: totals must be finite numbers")
        out.append(float(x))
    return out


#: A legs entry shows a hard-gate failure by its decision outcome or status, or by a gates map with a non-PASS value.
GATE_FAILURES = frozenset({"GATE_FAILED", "MANDATORY_GATE_FAILED"})


def gate_failed(legs):
    """True when this rebuild's legs entry shows that a hard gate failed (so it has no total)."""
    if not isinstance(legs, dict):
        return False
    if (
        legs.get("decision_outcome") in GATE_FAILURES
        or legs.get("status") in GATE_FAILURES
    ):
        return True
    gates = legs.get("gates")
    return isinstance(gates, dict) and any(
        v not in (True, "PASS") for v in gates.values()
    )


def canonical(doc):
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def rejudge(legs, score_pack, where):
    """(status, total) of one rebuild's legs scored on the judge pack by `dual_score.score`, as the receiver would.

    The measurements are the grade's own A and D, every hard gate PASS (a rebuild with a failed gate has no total and
    never reaches this), the grade's decision outcome; nothing else can move the status here.
    """
    from carbon.scoring import dual_score

    if not isinstance(legs, dict) or any(
        not isinstance(legs.get(k), (int, float)) or isinstance(legs.get(k), bool)
        for k in ("A", "D")
    ):
        raise StatsError(
            f"{where}: numeric A and D legs are required with --judge-pack"
        )
    measurements = {}
    for leg, body in score_pack["legs"].items():
        if len(body["components"]) != 1:
            raise StatsError(f"{where}: judge pack leg {leg} must have one component")
        measurements[body["components"][0]["metric"]] = {
            "status": "RESOLVED",
            "value": float(legs[leg]),
            "unit": body["components"][0]["unit"],
        }
    benchmark = {
        "schema": dual_score.INPUT_SCHEMA,
        **{
            k: score_pack[k]
            for k in (
                "scope",
                "challenge",
                "physics_contract_digest",
                "measurement_contract_digest",
            )
        },
        "population_role": "P",
        "common_mask_digest": "sha256:" + "0" * 64,
        "models": [
            {
                "artifact_digest": "sha256:" + "0" * 64,
                "gates": {g: "PASS" for g in score_pack["hard_gates"]},
                "measurements": measurements,
                "decision_outcome": legs.get("decision_outcome", "POOL_GRADED"),
            }
        ],
    }
    row = dual_score.score(benchmark, score_pack)["models"][0]
    return row["status"], row["score"]


def load_judge_pack(path):
    """(registered score pack, sha256 of the file) of a judge pack's score_pack JSON."""
    from carbon.scoring import dual_score

    raw = Path(path).read_bytes()
    try:
        body = json.loads(raw)
        declared = None
        if isinstance(body, dict) and "pack_digest" in body:
            # A real judge pack file carries its own digest; `register_pack` takes the body without it.
            declared = _declared_digest(body.pop("pack_digest"), Path(path).name)
        pack = dual_score.register_pack(body)
    except (ValueError, dual_score.DualScoreRefused) as exc:
        raise StatsError(f"judge pack {Path(path).name}: {exc}") from exc
    sha = "sha256:" + hashlib.sha256(raw).hexdigest()
    # The declared digest is recorded, never relied on: the digest the registration computes is the pack's identity.
    return (pack, sha) if declared is None else (pack, sha, declared)


def _declared_digest(value, name):
    """A judge pack file's own `pack_digest` as `sha256:<64 hex>`: 64 hex, with or without the prefix."""
    text = value.removeprefix("sha256:") if isinstance(value, str) else None
    if text is None or not _HEX.fullmatch(text):
        raise StatsError(f"judge pack {name}: pack_digest is not a sha256 digest")
    return "sha256:" + text


def without_minimums(pack):
    """The same pack with every leg minimum removed: what the calibration run scored a rebuild on."""
    from carbon.scoring import dual_score

    body = {k: v for k, v in pack.items() if k != "pack_digest"}
    body["legs"] = {
        leg: {**spec, "minimum": None} for leg, spec in pack["legs"].items()
    }
    return dual_score.register_pack(body)


def _challenge(name, spec, judge=None):
    pack = _digest(spec.get("pack_digest"), f"{name}.pack_digest")
    klass = _digest(spec.get("class_record_digest"), f"{name}.class_record_digest")
    panel, members = spec.get("panel"), spec.get("members")
    if (
        not panel
        or not isinstance(members, dict)
        or set(panel) != set(members)
        or len(set(panel)) != len(panel)
    ):
        raise StatsError(f"{name}: panel must list each member exactly once")

    unbounded = None if judge is None else without_minimums(judge)

    def keep(totals, legs, where):
        """(kept totals, count failing the judge minimums, count gated, whether rebuild 0 is not gated, whether
        rebuild 0 fails the minimums). A gated rebuild (null total, legs show a hard-gate failure) is excluded and counted
        apart; a null total the legs do not explain is a refusal. A rebuild that fails only the judge minimums KEEPS its
        total (minimums change a row's status, never its total) and is counted."""
        if judge is None:
            return totals, 0, 0, True, False
        if not isinstance(legs, list) or len(legs) != N:
            raise StatsError(
                f"{where}: need exactly {N} legs entries with --judge-pack"
            )
        kept, failed, gated, first_ok, first_failed = [], 0, 0, False, False
        for index, (total, leg) in enumerate(zip(totals, legs, strict=True)):
            if total is None:
                if not gate_failed(leg):
                    raise StatsError(
                        f"{where}[{index}]: the total is null and the legs show no hard-gate failure; missing data is not gated"
                    )
                gated += 1
                continue
            status, rescored = rejudge(leg, judge, f"{where}[{index}]")
            if status == "REQUIRED_LEG_MINIMUM_FAILED":
                failed += 1
                # The status is all the minimums change: the total is what the same legs give without them.
                _, rescored = rejudge(leg, unbounded, f"{where}[{index}]")
                if index == 0:
                    first_failed = True
            elif status != "SCORED_DEVELOPMENT_CANDIDATE":
                raise StatsError(
                    f"{where}[{index}]: the judge pack gives {status}, not a scored row"
                )
            if rescored is None or abs(rescored - total) > 1e-9:
                raise StatsError(
                    f"{where}[{index}]: the judge pack gives {status} / total {rescored}, not the recorded {total}"
                )
            kept.append(total)
            if index == 0:
                first_ok = True
        if len(kept) < 2:
            raise StatsError(
                f"{where}: only {len(kept)} non-gated rebuild(s); sigma needs at least 2"
            )
        return kept, failed, gated, first_ok, first_failed

    stats = {}
    for eid in panel:
        m = members[eid]
        totals = _totals(
            m.get("seed0_totals"), f"{name}.{eid}.seed0_totals", judge is not None
        )
        digests = m.get("state_digests")
        if not isinstance(digests, list) or len(digests) != N:
            raise StatsError(f"{name}.{eid}: need exactly {N} state digests")
        digests = [_digest(d, f"{name}.{eid}.state_digests") for d in digests]
        kept, failed, gated, seed0_ok, seed0_failed = keep(
            totals, m.get("seed0_legs"), f"{name}.{eid}.seed0_legs"
        )
        stats[eid] = {
            "sigma": statistics.stdev(kept),
            "bit_identical": len(set(digests)) == 1,
            "fingerprint": _digest(
                m.get("reference_fingerprint"), f"{name}.{eid}.reference_fingerprint"
            ),
            "within_noise": m.get("within_noise") is True,
            "seed0_total": totals[0],
            "seed0_ok": seed0_ok,
            "seed0_failed_minimums": seed0_failed,
            "minimum_failed": failed,
            "gated": gated,
        }
    sigma = max(s["sigma"] for s in stats.values())
    control = next(
        (e for e in panel if stats[e]["bit_identical"] and stats[e]["seed0_ok"]), None
    )
    basis = spec.get("control_basis_bit_identical")
    if control is None:
        pool = [e for e in panel if stats[e]["within_noise"] and stats[e]["seed0_ok"]]
        if not pool:
            raise StatsError(
                f"{name}: no bit-identical member and none marked within_noise; no control can be chosen"
            )
        control = min(pool, key=lambda e: (stats[e]["sigma"], panel.index(e)))
        basis = spec.get("control_basis_within_noise")
    if not isinstance(basis, str) or not basis:
        raise StatsError(
            f"{name}: the control_basis text for the chosen case is missing"
        )
    seeds = _totals(
        (spec.get("control_seed_totals") or {}).get(control),
        f"{name}.control_seed_totals[{control}]",
        judge is not None,
    )
    seed_kept, seed_failed, seed_gated, _ok, _failed = keep(
        seeds,
        (spec.get("control_seed_legs") or {}).get(control),
        f"{name}.control_seed_legs[{control}]",
    )
    spread = max(seed_kept) - min(seed_kept)
    # OWNER-CROWN-MARGIN-2SD-01: the seed term is 2 x the SAMPLE standard deviation (n - 1) of the control's kept per-seed
    # totals; the max - min range stays in the output for reference.
    seed_sd = statistics.stdev(seed_kept)
    value = max(5 * sigma, SEED_SD_MULTIPLE * seed_sd)
    if value == 0:
        raise StatsError(
            f"{name}: sigma and 2 x the seed sd are both 0; stop and report (no resolution floor is registered)"
        )
    result = {
        "bit_identical": {e: stats[e]["bit_identical"] for e in panel},
        "control": {
            "entry_id": control,
            "reference_fingerprint": stats[control]["fingerprint"],
            "reference_total": stats[control]["seed0_total"],
            "control_basis": basis,
            "pack_digest": pack,
            "class_record_digest": klass,
        },
        "seed_sd": seed_sd,
        "seed_spread": spread,
        "spread_rule": SPREAD_RULE,
        "sigma": sigma,
        "sigma_by_member": {e: stats[e]["sigma"] for e in panel},
        "value": value,
    }
    if judge is not None:
        result["minimum_failed"] = {
            "by_member": {e: stats[e]["minimum_failed"] for e in panel},
            "control_seeds": seed_failed,
        }
        result["control_fails_judge_minimums"] = stats[control]["seed0_failed_minimums"]
        result["gated"] = {
            "by_member": {e: stats[e]["gated"] for e in panel},
            "control_seeds": seed_gated,
        }
    return result


def measure(doc, judge_packs=None):
    """The measurement document; ``judge_packs`` is {challenge: (registered score pack, file sha256)}."""
    if (
        not isinstance(doc, dict)
        or doc.get("schema") != SCHEMA_IN
        or not isinstance(doc.get("challenges"), dict)
    ):
        raise StatsError(f"input must carry schema {SCHEMA_IN} and a challenges object")
    judge_packs = judge_packs or {}
    unknown = sorted(set(judge_packs) - set(doc["challenges"]))
    if unknown:
        raise StatsError(f"--judge-pack names a Challenge not in the input: {unknown}")
    body = {
        "challenges": {
            n: _challenge(n, s, judge_packs[n][0] if n in judge_packs else None)
            for n, s in sorted(doc["challenges"].items())
        },
        "schema": SCHEMA_OUT,
    }
    if judge_packs:
        body["judge_minimums"] = {
            n: {
                "source_sha256": sha,
                "score_pack_digest": pack["pack_digest"],
                **(
                    {
                        "declared_pack_digest": declared[0],
                        "declared_pack_digest_matches": declared[0]
                        == pack["pack_digest"],
                    }
                    if declared
                    else {}
                ),
                "minimums": {
                    leg: spec["minimum"] for leg, spec in sorted(pack["legs"].items())
                },
            }
            for n, (pack, sha, *declared) in sorted(judge_packs.items())
        }
    return {**body, "measurement_digest": hashlib.sha256(canonical(body)).hexdigest()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument(
        "--out", help="write the measurement document here (default: stdout)"
    )
    ap.add_argument(
        "--judge-pack",
        action="append",
        default=[],
        metavar="CHALLENGE=SCORE_PACK.json",
        help="apply this judge pack's leg minimums to that Challenge's rebuilds (repeatable)",
    )
    args = ap.parse_args(argv)
    try:
        judge_packs = {}
        for item in args.judge_pack:
            challenge, _, path = item.partition("=")
            if not challenge or not path or challenge in judge_packs:
                raise StatsError(
                    f"--judge-pack wants CHALLENGE=PATH once each: {item!r}"
                )
            judge_packs[challenge] = load_judge_pack(path)
        with open(args.input, encoding="utf-8") as f:
            result = measure(json.load(f), judge_packs)
        for challenge, (pack, sha, *_declared) in sorted(judge_packs.items()):
            minimums = {leg: s["minimum"] for leg, s in sorted(pack["legs"].items())}
            print(
                f"recal_stats: {challenge}: judge-pack minimums {minimums} from {sha}",
                file=sys.stderr,
            )
    except (StatsError, OSError, json.JSONDecodeError) as exc:
        print(f"recal_stats: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(result["measurement_digest"])
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
