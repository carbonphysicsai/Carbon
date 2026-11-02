"""Write the per-Challenge configs of `q3_q8_whatif.py` from the REGISTERED records (nothing typed by hand).

    python3 make_configs.py OUTDIR --noise scripts/validator_host_classes/koth_rebuild_noise.json \\
        --proof-grid POOL_PROOF_GRID_FULL_B60_20261030.json --seed 20261101 \\
        --host HOST.json            # {challenge: {version, evaluation_version, copy_hotkey, pack_root, baseline_predictions,
                                    #              store, task_roots}}  (paths and the CURRENT exam key: the host's, not mine)

margin_n is the Challenge's value in the koth rebuild-noise registry; the gaming controls are the pool proof grid's `biased`
controls (its ``optimism_k`` as a feasible_bias, its ``wrong_k`` and ``wrong_radius`` as a wrong_near; the seed is the one
given, 20261101). No class split is written: the what-if reads each target's region class from the sealed pool material
(an extended target with an OOD shell is extended_shell) and reports the counts. The sha256 of both record files is written
into every config and echoed in the what-if report. A Challenge with no host record or no registered margin_N is refused by name; nothing is filled. A host
record's null ``baseline_predictions`` (no baseline pair) is written as null: that config serves q8 only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CHALLENGES = (
    "f08-ribbed-bracket",
    "electric-motor-magnetics",
    "f02",
    "chip-cold-plate",
)
HOST_KEYS = {
    "version",
    "evaluation_version",
    "copy_hotkey",
    "pack_root",
    "baseline_predictions",
    "store",
    "task_roots",
}


def build(noise_path, grid_path, host_path, seed):
    noise_raw, grid_raw = Path(noise_path).read_bytes(), Path(grid_path).read_bytes()
    noise, grid = json.loads(noise_raw), json.loads(grid_raw)
    host = json.loads(Path(host_path).read_bytes())
    records = {
        "koth_rebuild_noise_sha256": hashlib.sha256(noise_raw).hexdigest(),
        "proof_grid_sha256": hashlib.sha256(grid_raw).hexdigest(),
        "proof_grid_seed": grid["seed"],
    }
    gaming = [
        {"mode": "feasible_bias", "k": grid["optimism_k"], "seed": seed},
        {
            "mode": "wrong_near",
            "k": grid["wrong_k"],
            "radius": grid["wrong_radius"],
            "seed": seed,
        },
    ]
    if type(host) is not dict or not host:
        raise SystemExit("the host record names no Challenge")
    unknown = sorted(set(host) - set(CHALLENGES))
    if unknown:
        raise SystemExit(f"no config rule for {unknown[0]}")
    configs = {}
    # the Challenges the host record names (its paths and current exam keys), each built only from the records
    for challenge in (c for c in CHALLENGES if c in host):
        entry = host[challenge]
        if type(entry) is not dict or set(entry) != HOST_KEYS:
            raise SystemExit(
                f"host record for {challenge} needs exactly {sorted(HOST_KEYS)}"
            )
        # null only where the host record holds no baseline pair (Cooling 1.6: its judge baseline is a refit); the config
        # then serves q8 only, and q3 / the what-if refuse it
        baseline = entry["baseline_predictions"]
        if baseline is not None and (type(baseline) is not str or not baseline):
            raise SystemExit(f"host record for {challenge}: baseline_predictions")
        try:
            margin = noise["challenges"][challenge]["value"]
        except KeyError:
            raise SystemExit(f"no registered margin_N for {challenge}") from None
        configs[challenge] = {
            "challenge": challenge,
            **entry,
            "margin_n": margin,
            "top": 5,
            "gaming": gaming,
            "records": records,
            "agen_factors": (
                [1.0, 1.0 / 3.0] if challenge == "f08-ribbed-bracket" else [1.0]
            ),
            "s_h_fraction": 0.25,
            "pick_k": 3,
        }
    return configs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--noise", type=Path, required=True)
    parser.add_argument("--proof-grid", type=Path, required=True)
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261101)
    args = parser.parse_args(argv)
    configs = build(args.noise, args.proof_grid, args.host, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for challenge, config in configs.items():
        path = args.out / f"{challenge}.json"
        if path.exists():
            raise SystemExit(f"{path} exists; refusing to overwrite")
        path.write_bytes((json.dumps(config, indent=1, sort_keys=True) + "\n").encode())
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
