"""The F02 3.0 leakage deck's rented smoke (Validator order: lumped control, zero-law, then one powered exponential case).

    python3 f02_leakage_smoke.py fixtures OUT            # the TEST_ONLY synthetic coefficient files (prints their sha256)
    python3 f02_leakage_smoke.py build OUT               # the decks of steps 1 and 2 (and 3 when --case-json is given)
    CARBON_F02_IMAGE=<pinned image id> python3 f02_leakage_smoke.py solve OUT [--only NAME ...]
    python3 f02_leakage_smoke.py check OUT               # the pass checks, printed as JSON; rc 0 = every step PASS, 3 = a STOP

``solve`` runs ElmerSolver in the pinned Elmer image exactly as `f02_readiness.run` does (one CPU, no network, read-only,
the case directory mounted at /case; the image must be `f02_readiness.IMAGE`). Every coefficient here is SYNTHETIC test
data: nothing is registered and every deck is labelled TEST_ONLY.

Steps (decks named ``s1-lumped``, ``s2-off``, ``s2-zero``, ``s3-exp``):

1. ``s1-lumped``  STEADY deck, constant leakage 5e6 W/m^3: the heat balance (heat in = BASE_W + q V_die, carried out by the
   Robin underside) and the mean underside temperature match the closed form (`f02_deck_v3.lumped_control`).
2. ``s2-off`` / ``s2-zero``  the same powered TRANSIENT deck with TEST_ONLY tables (so both run the nonlinear iteration), one
   without leakage and one with the constant-ZERO law: ``scalars.dat`` columns time and boundary max temperature are
   textually identical (the peak to the last printed digit).
3. ``s3-exp``  one powered exponential-law case (``--case-json``: a v3 case dict, e.g. DC's C3 corner): it must converge
   (``thermal_runaway`` and ``out_of_property_range`` are STOP), and its peak must exceed the leakage-off peak of the same case.

The pass tolerance of step 1 (``--tol``, default 1e-6 relative on the heat balance) is a PROPOSAL for the Validator to rule on;
the measured residual is always printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for path in (str(ROOT), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import f02_deck_v3 as v3
import f02_readiness as readiness

CONSTANT = {
    "schema": v3.LEAKAGE_SCHEMA,
    "decision": v3.LEAKAGE_TEST_ONLY,
    "source": "synthetic smoke fixture (constant)",
    "form": "constant",
    "range_k": [250.0, 500.0],
    "q_w_per_m3": 5000000.0,
}
ZERO = {**CONSTANT, "source": "synthetic smoke fixture (zero)", "q_w_per_m3": 0.0}
EXPONENTIAL = {
    "schema": v3.LEAKAGE_SCHEMA,
    "decision": v3.LEAKAGE_TEST_ONLY,
    "source": "synthetic smoke fixture (exponential)",
    "form": "exponential",
    "range_k": [250.0, 500.0],
    "q_ref_w_per_m3": 4000000.0,
    "t_ref_k": 300.0,
    "beta_per_k": 0.02,
}
FIXTURES = {
    "leak-constant.json": CONSTANT,
    "leak-zero.json": ZERO,
    "leak-exponential.json": EXPONENTIAL,
}
#: A powered v3 case (a stand-in until DC's C3 corner is given): the rectangle of the TEST tables' pins.
CASE = {
    "peak_w": 120.0,
    "on_time_s": 10.0,
    "ramp_fraction": 0.0,
    "pulses": 1,
    "h_w_m2_k": 4000.0,
    "coolant_c": 25.0,
    "start_offset_c": 5.0,
    "left_source_fraction": 0.6,
}
#: Synthetic TEST_ONLY property tables (both decks of step 2 run the nonlinear iteration on them).
TABLES = {
    "copper": {
        "k": [(250.0, 400.0), (500.0, 380.0)],
        "cp": [(250.0, 380.0), (500.0, 400.0)],
    },
    "die": {"k": [(250.0, 160.0), (500.0, 90.0)], "cp": 420.0},
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixtures(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    shas = {}
    for name, doc in FIXTURES.items():
        body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
        (out / name).write_bytes(body.encode())  # LF on every host
        shas[name] = _sha(out / name)
    return shas


def _leak(out, name):
    return v3.load_leakage(Path(out) / name, test_mode=True)


def build(out, case_json=None):
    out = Path(out)
    shas = fixtures(out)
    decks = out / "decks"
    v3.write_case(
        CASE, decks / "s1-lumped", steady=True, leakage=_leak(out, "leak-constant.json")
    )
    v3.write_case(CASE, decks / "s2-off", tables=TABLES, test_mode=True)
    v3.write_case(
        CASE,
        decks / "s2-zero",
        tables=TABLES,
        test_mode=True,
        leakage=_leak(out, "leak-zero.json"),
    )
    names = ["s1-lumped", "s2-off", "s2-zero"]
    if case_json is not None:
        case = json.loads(Path(case_json).read_text())
        v3.write_case(case, decks / "s3-off", tables=TABLES, test_mode=True)
        v3.write_case(
            case,
            decks / "s3-exp",
            tables=TABLES,
            test_mode=True,
            leakage=_leak(out, "leak-exponential.json"),
        )
        names += ["s3-off", "s3-exp"]
    manifest = {
        "schema": "carbon.f02.leakage-smoke.v1",
        "fixtures_sha256": shas,
        "decks": {
            n: {f: _sha(decks / n / f) for f in ("case.sif", "deck.json")}
            for n in names
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    )
    return manifest


def solve(out, only=None):
    image = os.environ.get("CARBON_F02_IMAGE")
    if image != readiness.IMAGE:
        raise SystemExit("CARBON_F02_IMAGE must be the pinned F02 image")
    decks = Path(out) / "decks"
    manifest = json.loads((Path(out) / "manifest.json").read_text())
    results = {}
    for name, files in manifest[
        "decks"
    ].items():  # every deck is checked before any container starts
        for f, digest in files.items():
            if _sha(decks / name / f) != digest:
                raise SystemExit(f"{name}/{f} differs from the built manifest")
    for name in manifest["decks"]:
        if only and name not in only:
            continue
        d = decks / name
        steady = name == "s1-lumped"
        memory = "1g"
        cmd = ["docker", "run", "--rm", "--name", f"carbon-f02leak-{name}", "--network", "none",
               "--read-only", "--tmpfs", "/tmp", "--cpus", "1", "--memory", memory,
               "--memory-swap", memory, "--pids-limit", "16",
               "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case",
               "-w", "/case", image, "bash", "-c", f"{readiness.SOLVE}; {readiness.ACCOUNT}"]  # fmt: skip
        started = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        results[name] = {
            "exit": proc.returncode,
            "wall_s": time.monotonic() - started,
            "steady": steady,
        }
        print(json.dumps({name: results[name]}), flush=True)
    (Path(out) / "solve-results.json").write_text(
        json.dumps(results, indent=1, sort_keys=True) + "\n"
    )
    return results


def _series(directory):
    """The printed (time, boundary max) columns of scalars.dat, as the text the solver wrote."""
    cols, rows = v3.read_scalars(directory)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    lines = Path(directory, "scalars.dat").read_text().splitlines()
    return [(x.split()[0], x.split()[i_top]) for x in lines if x.strip()], max(
        r[i_top] for r in rows
    )


def _status(directory):
    log = Path(directory, "solver.log")
    return v3.reference_status(directory, log if log.is_file() else None)


def check(out, tol=1e-6):
    decks = Path(out) / "decks"
    report = {"steps": {}, "tolerance_status": "PROPOSAL_PENDING_VALIDATOR", "tol": tol}
    stop = False
    # 1. the lumped control
    try:
        lumped = v3.lumped_control(decks / "s1-lumped")
        status = _status(decks / "s1-lumped")
        ok = (
            status["status"] == "OK"
            and abs(lumped["residual_rel"]) < tol
            and abs(
                lumped["mean_underside_k"] / lumped["expected_mean_underside_k"] - 1.0
            )
            < tol
        )
        report["steps"]["1_lumped"] = {"pass": bool(ok), **lumped, "reference": status}
    except (OSError, v3.DeckRefused, StopIteration, IndexError) as error:
        report["steps"]["1_lumped"] = {"pass": False, "error": str(error)}
    # 2. the zero-law equals leakage-off to the last printed digit
    try:
        off, peak_off = _series(decks / "s2-off")
        zero, peak_zero = _series(decks / "s2-zero")
        status_off, status_zero = _status(decks / "s2-off"), _status(decks / "s2-zero")
        report["steps"]["2_zero_law"] = {
            "pass": off == zero
            and len(off) > 0
            and status_off["status"] == status_zero["status"] == "OK",
            "rows": len(off),
            "peak_off_k": peak_off,
            "peak_zero_k": peak_zero,
            "rows_differing": sum(a != b for a, b in zip(off, zero)),
            "reference_off": status_off,
            "reference_zero": status_zero,
        }
    except (OSError, StopIteration, IndexError) as error:
        report["steps"]["2_zero_law"] = {"pass": False, "error": str(error)}
    # 3. the powered exponential case (only when it was built)
    if (decks / "s3-exp").is_dir():
        try:
            status = _status(decks / "s3-exp")
            _off, peak_off = _series(decks / "s3-off")
            _exp, peak_exp = _series(decks / "s3-exp")
            window = json.loads((decks / "s3-exp" / "deck.json").read_text())[
                "property_range_k"
            ]
            report["steps"]["3_exponential"] = {
                "pass": status["status"] == "OK"
                and peak_exp > peak_off
                and peak_exp <= window[1],
                "peak_off_k": peak_off,
                "peak_exp_k": peak_exp,
                "window_k": window,
                "reference": status,
            }
        except (OSError, StopIteration, IndexError, v3.DeckRefused) as error:
            report["steps"]["3_exponential"] = {"pass": False, "error": str(error)}
    stop = any(not step["pass"] for step in report["steps"].values())
    report["verdict"] = "STOP" if stop else "PASS"
    (Path(out) / "smoke-report.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=1, sort_keys=True))
    return 3 if stop else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("fixtures", "build", "solve", "check"):
        p = sub.add_parser(name)
        p.add_argument("out", type=Path)
        if name == "build":
            p.add_argument("--case-json", type=Path)
        if name == "solve":
            p.add_argument("--only", nargs="*")
        if name == "check":
            p.add_argument("--tol", type=float, default=1e-6)
    args = parser.parse_args(argv)
    if args.cmd == "fixtures":
        print(json.dumps(fixtures(args.out), indent=1, sort_keys=True))
        return 0
    if args.cmd == "build":
        print(json.dumps(build(args.out, args.case_json), indent=1, sort_keys=True))
        return 0
    if args.cmd == "solve":
        results = solve(args.out, args.only)
        return 0 if all(r["exit"] == 0 for r in results.values()) else 2
    return check(args.out, args.tol)


if __name__ == "__main__":
    sys.exit(main())
