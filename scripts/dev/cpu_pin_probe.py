"""Print what NumPy and OpenBLAS dispatch on THIS host, and whether a candidate CPU pin takes effect.

    python scripts/dev/cpu_pin_probe.py [--disable NAME,NAME,...] [--coretype Haswell]

Prints one JSON document: the numpy version, its build baseline and dispatch targets, the features this CPU has, and
(for the candidate pin) the same facts from a child process started with the pin in its environment, plus the child's
stderr (NumPy warns or refuses on a feature name it does not know). Public facts about the host's CPU only.
Run it on every host that must agree (the Targon VM, runner2, the validator) and compare the `pinned` blocks.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_REPORT = r"""
import json, os
import numpy as np
from numpy._core._multiarray_umath import __cpu_baseline__, __cpu_dispatch__, __cpu_features__
import numpy.linalg
info = {
    "numpy": np.__version__,
    "baseline": list(__cpu_baseline__),
    "dispatch": list(__cpu_dispatch__),
    "features_on": sorted(k for k, v in __cpu_features__.items() if v),
    "features_avx512_known": sorted(k for k in __cpu_features__ if k.startswith("AVX512")),
    "dispatch_targets_on": sorted(t for t in __cpu_dispatch__ if __cpu_features__.get(t)),
    "env": {k: os.environ.get(k) for k in ("OPENBLAS_CORETYPE", "NPY_DISABLE_CPU_FEATURES", "OPENBLAS_NUM_THREADS")},
}
try:
    from numpy.__config__ import CONFIG
    info["blas"] = CONFIG.get("Build Dependencies", {}).get("blas", {})
except Exception as error:  # report, never fail the probe
    info["blas_error"] = type(error).__name__
print(json.dumps(info, sort_keys=True))
"""


def _run(extra_env, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in extra_env and k not in drop}
    env.update(extra_env)
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    done = subprocess.run(
        [sys.executable, "-c", _REPORT],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    try:
        report = json.loads(done.stdout)
    except ValueError:
        report = None
    return {"rc": done.returncode, "report": report, "stderr": done.stderr[-600:]}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--disable", default="")
    parser.add_argument("--coretype", default="Haswell")
    args = parser.parse_args(argv)
    # the unpinned child has the pin variables REMOVED even when this process (e.g. canonical.sh) exports them
    out = {"unpinned": _run({}, drop=("OPENBLAS_CORETYPE", "NPY_DISABLE_CPU_FEATURES"))}
    pin = {"OPENBLAS_CORETYPE": args.coretype}
    if args.disable:
        pin["NPY_DISABLE_CPU_FEATURES"] = args.disable
    out["pinned"] = _run(pin)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
