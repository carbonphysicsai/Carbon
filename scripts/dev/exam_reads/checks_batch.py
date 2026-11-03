"""CHECKS BATCH: one custody launch per version for checks (1)-(3) (`checks_report`, FORMAT rev 2) and the G1-G9 reports
(`g_reports`). CUSTODY scratch, never official; the outputs are aggregates.

    checks_batch.py run      --config CONFIG.json --inputs REPORT_INPUTS.json [--g-inputs G_INPUTS.json] --out DIR
    checks_batch.py dry      --config CONFIG.json --inputs REPORT_INPUTS.json [--g-inputs G_INPUTS.json]
    checks_batch.py selftest --out DIR
    checks_batch.py run      --config CONFIG.json --inputs REPORT_INPUTS.json --kit-data KIT_MANIFEST.json [--g-inputs ...] --out DIR
    checks_batch.py dry      --config CONFIG.json --inputs REPORT_INPUTS.json --kit-data KIT_MANIFEST.json [--g-inputs ...]

``run`` writes checks-1-3-report.{json,md}, g-reports.json and SUMS (sha256 of each). ``dry`` loads and checks every input (shapes,
every sha256, the pack loads, the class source resolves) and grades nothing. ``selftest`` runs the whole chain on FAKE pool targets
of the real shapes (two targets, two outputs, A_gen slices, a gated contender) through the real grader functions, and checks the
outputs carry every field; it touches no custody material.

With ``--kit-data`` the launch is check (1K), the kit-data fit (`checks_kit`, STRONG_CHECKS_SPEC_ADDENDUM_KITFIT_20261103): ``run``
writes check-1k-report.{json,md} and SUMS instead (the G inputs, if given, are checked and not used: G1-G9 belong to the checks-1-3
launch); ``dry`` checks the manifest, every sha256, the row counts, the disjointness, both runs of every member and the budget
fields, and grades nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import checks_kit
import checks_report as report
import g_reports
import q3_q8_whatif as reads

OUTPUTS = ("checks-1-3-report.json", "checks-1-3-report.md", "g-reports.json")


def _write(out, checks, g_doc):
    files = {
        "checks-1-3-report.json": json.dumps(checks, indent=2, sort_keys=True) + "\n",
        "checks-1-3-report.md": report.summary(checks),
        "g-reports.json": json.dumps(g_doc, indent=2, sort_keys=True) + "\n",
    }
    return _write_files(out, files, OUTPUTS)


def _write_files(out, files, names):
    out.mkdir(parents=True)
    sums = []
    for name in names:
        raw = files[name].encode()
        (out / name).write_bytes(raw)
        sums.append(f"{hashlib.sha256(raw).hexdigest()}  {name}\n")
    (out / "SUMS").write_bytes("".join(sums).encode())
    return "".join(sums)


def run(config_path, inputs_path, g_inputs_path, out):
    reads._need(not out.exists(), "batch_out_exists")
    g_inputs = g_reports.load_inputs(g_inputs_path)
    config = reads.load_config(config_path)
    sink = {}
    checks = report.run_report(config, config_path, inputs_path, keep=sink)
    return _write(out, checks, g_reports.build(checks, sink, g_inputs))


def run_kit(config_path, inputs_path, kit_path, g_inputs_path, out):
    """Check (1K): check-1k-report.{json,md} and SUMS."""
    reads._need(not out.exists(), "batch_out_exists")
    g_reports.load_inputs(g_inputs_path)
    config = reads.load_config(config_path)
    doc = checks_kit.run_kit(config, config_path, inputs_path, kit_path)
    files = {
        "check-1k-report.json": json.dumps(doc, indent=2, sort_keys=True) + "\n",
        "check-1k-report.md": checks_kit.summary(doc),
    }
    return _write_files(out, files, checks_kit.OUTPUTS)


def dry_kit(config_path, inputs_path, kit_path, g_inputs_path):
    """Check (1K)'s inputs loaded and checked; nothing graded."""
    g_reports.load_inputs(g_inputs_path)
    config = reads.load_config(config_path)
    return checks_kit.dry(config, inputs_path, kit_path)


def dry(config_path, inputs_path, g_inputs_path):
    """Every input loaded and checked; nothing graded."""
    g_reports.load_inputs(g_inputs_path)
    config = reads.load_config(config_path)
    doc = report.load_inputs(inputs_path)
    report.train_matrix(doc["train_inputs"])
    reads._class_source(doc["class_source"])
    regrader = reads.Regrader(config)
    n_rows = len(regrader.graded.bank["inputs"])
    for entry in doc["contenders"]:
        reads._contender_rows(
            {"rows_npy": entry["rows_npy"], "sha256": entry["sha256"]}, n_rows
        )
    return {
        "challenge": config["challenge"],
        "version": config["version"],
        "contenders": [e["role"] for e in doc["contenders"]],
        "bank_rows": n_rows,
        "dry": "OK",
    }


def selftest(out):
    """The chain on fake targets of the real shapes (see the module docstring); returns the SUMS text."""
    from contextlib import ExitStack
    from unittest import mock

    sys.path.insert(0, str(_HERE.parents[2] / "tests" / "cpu"))
    import test_checks_report as fake

    from carbon.scoring import pool_version

    work = out / "_inputs"
    work.mkdir(parents=True)
    config = {"challenge": "selftest", "version": "0", "margin_n": 0.03}
    config_path = work / "config.json"
    config_path.write_text(json.dumps(config))
    inputs = fake._inputs(work / "in")
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(reads, "Regrader", fake._StubRegrader))
        stack.enter_context(
            mock.patch.object(
                pool_version, "registered_policies", lambda *a, **k: fake.POLICIES
            )
        )
        stack.enter_context(
            mock.patch.object(
                reads,
                "_class_source",
                lambda source: (
                    fake._klass,
                    {"base": {"x": 0, "y": 0}},
                    frozenset({report.IN_TRAIN, fake.OUTER}),
                    {
                        "rule_sha256": "r",
                        "region_sha256": "g",
                        "plan_params_sha256": "p",
                    },
                ),
            )
        )
        sink = {}
        checks = report.run_report(config, config_path, inputs, keep=sink)
    g_doc = g_reports.build(
        checks,
        sink,
        {"g2_threshold": 0.1, "g3_floor_n": 3, "g8_practice_inputs": None},
    )
    for key in ("classes", "checks", "status", "bootstrap", "contenders"):
        reads._need(key in checks, f"selftest_report_lacks_{key}")
    for key in (k for k in g_doc if k.startswith("G")):
        reads._need(g_doc[key] is not None, f"selftest_{key}_missing")
    return _write(out / "outputs", checks, g_doc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("run", "dry"):
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path, required=True)
        p.add_argument("--inputs", type=Path, required=True)
        p.add_argument("--g-inputs", type=Path)
        p.add_argument("--kit-data", type=Path)
        if name == "run":
            p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("selftest")
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        kit = getattr(args, "kit_data", None)
        if args.cmd == "run" and kit is not None:
            print(
                run_kit(args.config, args.inputs, kit, args.g_inputs, args.out), end=""
            )
        elif args.cmd == "dry" and kit is not None:
            print(json.dumps(dry_kit(args.config, args.inputs, kit, args.g_inputs)))
        elif args.cmd == "run":
            print(run(args.config, args.inputs, args.g_inputs, args.out), end="")
        elif args.cmd == "dry":
            print(json.dumps(dry(args.config, args.inputs, args.g_inputs)))
        else:
            reads._need(not args.out.exists(), "batch_out_exists")
            print(selftest(args.out), end="")
    except reads.ReadRefused as refused:
        print(f"REFUSED: {refused.code}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
