"""GRAPHITE-PROGRESS-01: append one ledger line per level per batch, render the chart, print the trend.

    python -m scripts.dev.graphite_progress batch --manifest M.json --root DIR --ledger L.jsonl [--chart OUT.svg] [--history history.jsonl]
    python -m scripts.dev.graphite_progress chart --ledger L.jsonl --out OUT.svg
    python -m scripts.dev.graphite_progress trend --ledger L.jsonl

The manifest names, for one batch, the run output files (basenames under --root) with their role and
level, optional chain logs, and optional triage, refusal-class and finding-to-fix records. The ledger
and the chart live OUTSIDE the repository; a sealed or private path is refused; appending is idempotent
per (batch, level). Opt-in tooling: no run, no spend, no host write except the two output files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import chart, extract, improvement, ledger
from .model import UNMEASURED, ProgressError, refuse_sealed


def _json(path):
    path = refuse_sealed(path)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProgressError(f"manifest_unreadable: {Path(path).name}") from error


def load_runs(manifest, root):
    root = Path(root)
    chain_cache = {}
    runs = []
    for entry in manifest["runs"]:
        source = entry["file"]
        document = extract.read_document(root / source)
        wall = None
        if entry.get("chain_log"):
            log = entry["chain_log"]
            if log not in chain_cache:
                chain_cache[log] = refuse_sealed(root / log).read_text(
                    encoding="utf-8", errors="replace"
                )
            wall = extract.wall_seconds(chain_cache[log], entry.get("chain_label", ""))
        common = {
            "level": entry["level"],
            "source": source,
            "batch": manifest["batch"],
            "wall": wall,
        }
        if entry["role"] == "constructor":
            record = None
            if entry.get("public_improvement_file"):
                record = improvement.validate(
                    extract.read_document(root / entry["public_improvement_file"])
                )
                if (record.get("level") or 0) != entry["level"]:
                    raise ProgressError(
                        f"public_improvement_level_mismatch: {entry['public_improvement_file']}"
                    )
                old = record.get("supersedes")
                if old:
                    # a record that supersedes another must name that file's real digest, and the old
                    # file must still be there beside it (history is kept, never deleted)
                    kept = root / old["file"]
                    if (
                        Path(old["file"]).name != old["file"]
                        or not kept.is_file()
                        or improvement.file_sha256(kept) != old["sha256"]
                    ):
                        raise ProgressError(
                            "public_improvement_supersedes_digest_differs: "
                            f"{entry['public_improvement_file']}"
                        )
            common["public_improvement"] = record
            runs.append(
                extract.constructor_run(
                    document, practice_scores=entry.get("practice_scores"), **common
                )
            )
        elif entry["role"] == "attacker":
            runs.append(extract.attacker_run(document, **common))
        else:
            raise ProgressError(f"unknown_role: {entry['role']}")
    return runs


def load_history(path):
    if not path:
        return []
    return [
        json.loads(line)
        for line in refuse_sealed(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def command_batch(args):
    manifest = _json(args.manifest)
    runs = load_runs(manifest, args.root)
    classes = manifest.get("refusal_classes", {})
    triage = manifest.get("triage", {})
    fixes = manifest.get("finding_fixes")
    history = load_history(args.history)
    outcome = {}
    for level in sorted({r["level"] for r in runs}):
        line = ledger.build_line(
            batch_id=manifest["batch"],
            level=level,
            challenge=manifest["challenge"],
            date=manifest["date"],
            runs=runs,
            classes=classes,
            triage=triage,
            fixes=fixes,
            history=history,
            excluded=manifest.get("excluded", []),
        )
        outcome[f"L{level}"] = ledger.append_line(args.ledger, line)
    if args.chart:
        Path(args.chart).write_text(
            chart.render_svg(ledger.read_ledger(args.ledger)),
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps({"batch": manifest["batch"], "levels": outcome}, sort_keys=True))
    return 0


def command_chart(args):
    Path(args.out).write_text(
        chart.render_svg(ledger.read_ledger(args.ledger)),
        encoding="utf-8",
        newline="\n",
    )
    return 0


def _value(line, path):
    return chart._dig(line, path)


def trend_lines(lines):
    """A few plain lines per level: first and last measured value of each headline metric, with n."""
    out = []
    names = (
        ("bundled share", ("constructor", "bundled_share")),
        ("USD per BUNDLED", ("constructor", "usd_per_bundled")),
        ("refusal rate", ("constructor", "refusals", "rate")),
        (
            "median public-dev decision-loss improvement",
            ("constructor", "improvement", "public_dev", "decision_loss"),
        ),
        ("real findings per attacker run", ("attacker", "real_findings_per_run")),
        ("NOT_BUILT items", ("gate", "last", "NOT_BUILT")),
    )
    for level in sorted({l["level"] for l in lines}):
        mine = sorted(
            (l for l in lines if l["level"] == level),
            key=lambda l: (l["date"], l["batch"]),
        )
        for label, path in names:
            points = [(l["batch"],) + _value(l, path) for l in mine]
            measured = [p for p in points if chart._number(p[1]) is not None]
            if not measured:
                out.append(f"L{level} {label}: {UNMEASURED}")
            elif len(measured) == 1:
                out.append(
                    f"L{level} {label}: {measured[0][1]} (n={measured[0][2]}, one point)"
                )
            else:
                first, last = measured[0], measured[-1]
                a, b = chart._number(first[1]), chart._number(last[1])
                word = "flat" if a == b else ("up" if b > a else "down")
                out.append(
                    f"L{level} {label}: {first[1]} (n={first[2]}) -> {last[1]} (n={last[2]}), {word}, {len(measured)} points"
                )
    return out


def command_trend(args):
    for line in trend_lines(ledger.read_ledger(args.ledger)):
        print(line)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.dev.graphite_progress")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("batch")
    b.add_argument("--manifest", required=True)
    b.add_argument("--root", required=True)
    b.add_argument("--ledger", required=True)
    b.add_argument("--chart")
    b.add_argument(
        "--history",
        help="a readiness history.jsonl (committed), for the gate burn-down",
    )
    c = sub.add_parser("chart")
    c.add_argument("--ledger", required=True)
    c.add_argument("--out", required=True)
    t = sub.add_parser("trend")
    t.add_argument("--ledger", required=True)
    args = parser.parse_args(argv)
    try:
        return {"batch": command_batch, "chart": command_chart, "trend": command_trend}[
            args.command
        ](args)
    except ProgressError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
