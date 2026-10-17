"""Producer-only measured benchmark command; no battery or legacy lab imports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import solver_benchmark


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = json.loads(args.input.read_text(encoding="utf-8"))
    if type(evidence) is not dict or set(evidence) not in (
        {"registration", "references", "models"},
        {"registration", "references", "models", "score_pack"},
    ):
        raise solver_benchmark.BenchmarkRefused("benchmark_input_shape")
    report = solver_benchmark.compare(
        evidence["registration"],
        evidence["references"],
        evidence["models"],
        score_pack=evidence.get("score_pack"),
    )
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"development benchmark: {len(report['models'])} models; producer output written"
    )
    return 0
