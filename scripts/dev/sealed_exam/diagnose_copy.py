#!/usr/bin/env python3
"""Why does a delivered copy not import? Names the role that differs and how (custody or grading host, read-only).

    python scripts/dev/sealed_exam/diagnose_copy.py --copy <signed copy .json> --hotkey <hotkey> \
        [--producer-public-key <hex>]

`copy_delivery.verify_copy` refuses `copy_batch_not_the_pack` when a role file the copy's pack carries (case_bank,
reference_rows, solver_evidence) differs from the same role recomputed here from the batch the copy carries. This runs
the same steps and, for each of the three roles, prints whether they match, both digests and lengths, the first
differing byte, and WHERE and HOW MUCH they differ (a JSON path with the kind of difference, a numeric relative
difference, an array shape or element count): never a value. It also prints the host facts the recomputation depends
on (Python, NumPy, platform, CPU count, BLAS threads), so running it on the host that issued the copy AND on the host
that refuses it tells a host difference from a data difference.

Exit 0 when every role matches (the copy verifies at this step), 3 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROLES = ("case_bank", "reference_rows", "solver_evidence")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def host_facts():
    import numpy

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "thread_env": {
            k: os.environ.get(k)
            for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
    }


def _json_difference(a, b, path="$"):
    """The first place two parsed JSON values differ: ``{"path", "kind", ...}`` (no values), or None."""
    if type(a) is not type(b):
        return {
            "path": path,
            "kind": "type",
            "left": type(a).__name__,
            "right": type(b).__name__,
        }
    if isinstance(a, dict):
        if set(a) != set(b):
            return {
                "path": path,
                "kind": "keys",
                "only_in_pack": sorted(set(a) - set(b)),
                "only_recomputed": sorted(set(b) - set(a)),
            }
        for key in sorted(a):
            found = _json_difference(a[key], b[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return {
                "path": path,
                "kind": "length",
                "pack": len(a),
                "recomputed": len(b),
            }
        for index, (x, y) in enumerate(zip(a, b, strict=True)):
            found = _json_difference(x, y, f"{path}[{index}]")
            if found:
                return found
        return None
    if isinstance(a, float):
        if a == b or (math.isnan(a) and math.isnan(b)):
            return None
        scale = max(abs(a), abs(b)) or 1.0
        return {
            "path": path,
            "kind": "float",
            "relative_difference": abs(a - b) / scale,
        }
    if a != b:
        return {"path": path, "kind": "value"}
    return None


def _array_difference(left, right):
    import io

    import numpy as np

    def load(raw):
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            return {name: archive[name] for name in archive.files}

    a, b = load(left), load(right)
    if sorted(a) != sorted(b):
        return {"kind": "members", "pack": sorted(a), "recomputed": sorted(b)}
    for name in sorted(a):
        x, y = a[name], b[name]
        if x.shape != y.shape or x.dtype != y.dtype:
            return {
                "kind": "array",
                "member": name,
                "pack": [list(x.shape), str(x.dtype)],
                "recomputed": [list(y.shape), str(y.dtype)],
            }
        different = int((x != y).sum()) if x.size else 0
        if different:
            scale = np.maximum(np.abs(x), np.abs(y)).astype(float)
            scale[scale == 0] = 1.0
            return {
                "kind": "elements",
                "member": name,
                "different": different,
                "of": int(x.size),
                "max_relative_difference": float(
                    np.max(np.abs(x.astype(float) - y.astype(float)) / scale)
                ),
            }
    return {"kind": "same_arrays_different_container_bytes"}


def role_report(role, pack_bytes, recomputed):
    """One role's comparison (digests, lengths, first differing byte, where and how much)."""
    report = {
        "match": pack_bytes == recomputed,
        "pack_sha256": _sha(pack_bytes) if pack_bytes is not None else None,
        "recomputed_sha256": _sha(recomputed),
        "pack_bytes": None if pack_bytes is None else len(pack_bytes),
        "recomputed_bytes": len(recomputed),
    }
    if report["match"]:
        return report
    if pack_bytes is None:
        report["difference"] = {"kind": "the pack carries no such file"}
        return report
    report["first_differing_byte"] = next(
        (
            i
            for i, (x, y) in enumerate(zip(pack_bytes, recomputed, strict=False))
            if x != y
        ),
        min(len(pack_bytes), len(recomputed)),
    )
    try:
        if role == "case_bank":
            report["difference"] = _array_difference(pack_bytes, recomputed)
        else:
            report["difference"] = _json_difference(
                json.loads(pack_bytes), json.loads(recomputed)
            ) or {"kind": "same_json_different_bytes"}
    except (ValueError, OSError, KeyError) as error:
        report["difference"] = {"kind": "unreadable", "error": type(error).__name__}
    return report


def diagnose(copy_path, hotkey, producer_public_key=None):
    """The per-role report of one signed copy (see the module docstring)."""
    from carbon.challenge_validator import copy_delivery as cdl
    from carbon.challenge_validator import copy_route
    from carbon.challenge_validator import sealed_pack_import as spi
    from carbon.challenge_validator.validator_host import pinned_producer_key
    from carbon.scoring import sealed_batch_source as source

    package = json.loads(Path(copy_path).read_bytes())
    key = pinned_producer_key() if producer_public_key is None else producer_public_key
    commitment, payload, copy = copy_route.verify_package(package, key)
    own = dict(commitment, fingerprint=commitment["manifest_digest"])
    manifest_h, files, _snapshot = spi.verify_payload(
        own, {"manifest": payload["manifest"], "files": payload["files"]}
    )
    challenge, version = commitment["challenge_id"], commitment["challenge_version"]
    raw_batch = cdl._unb64(payload["copy"]["batch"])
    kit = source._kit(challenge)
    carried = json.loads(raw_batch)
    copy_bank = source._build(
        challenge, kit, carried["document"], carried["records"], version
    )
    recomputed = cdl.expected_roles(challenge, version, kit, copy_bank)
    paths = cdl._role_paths(json.loads(manifest_h))
    roles = {
        role: role_report(role, files.get(paths[role]), recomputed[role])
        for role in ROLES
    }
    return {
        "challenge": challenge,
        "version": version,
        "copy_hotkey_matches": copy["validator_hotkey"] == hotkey,
        "host": host_facts(),
        "roles": roles,
        "all_roles_match": all(r["match"] for r in roles.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--copy", required=True)
    parser.add_argument("--hotkey", required=True)
    parser.add_argument("--producer-public-key")
    args = parser.parse_args(argv)
    try:
        report = diagnose(args.copy, args.hotkey, args.producer_public_key)
    except (ValueError, KeyError, TypeError, OSError) as refused:
        code = getattr(refused, "code", type(refused).__name__)
        print(json.dumps({"refused": code, "host": host_facts()}), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["all_roles_match"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
