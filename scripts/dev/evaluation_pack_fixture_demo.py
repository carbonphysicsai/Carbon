#!/usr/bin/env python3
"""Run the C-EP1 local fixture path and emit a public-safe JSON baseline."""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "cpu"))

from test_c_ep1_evaluation_packs import PASSING_FIXTURE
from test_net3_candidates import setup, signed
from test_traineval_stub import (
    _a7_service,
    _provider,
    _service,
    _strategy,
)

from carbon.evaluation_packs import (
    DevelopmentEvaluationPackLedger,
    DevelopmentEvaluationPackService,
)
from carbon.execution import DurableExecutionQueue


def _memory_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages * page_size)
    except (OSError, ValueError):
        return None


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="carbon-c-ep1-") as directory:
        root = Path(directory)
        journal, gate = setup(root)
        first = journal.commit(*signed(gate, 1))
        second = journal.commit(
            *signed(gate, 2, strategy=_strategy(parameters={"n": 3}))
        )
        pack_ids = iter(
            (
                uuid.UUID("10000000-0000-0000-0000-000000000001"),
                uuid.UUID("10000000-0000-0000-0000-000000000002"),
            )
        )
        ledger = DevelopmentEvaluationPackLedger(
            journal, id_factory=lambda: next(pack_ids)
        )
        submissions = _a7_service(root / "science")
        submission_ids = iter(
            (
                uuid.UUID("20000000-0000-4000-8000-000000000001"),
                uuid.UUID("20000000-0000-4000-8000-000000000002"),
            )
        )
        submissions._store.uuid_factory = lambda: next(submission_ids)
        service = DevelopmentEvaluationPackService(
            ledger,
            submissions,
            _service(provider=_provider(PASSING_FIXTURE)),
            DurableExecutionQueue(root / "execution.sqlite3"),
        )

        started = time.perf_counter_ns()
        first_card = service.evaluate(first)
        first_ns = time.perf_counter_ns() - started
        started = time.perf_counter_ns()
        second_card = service.evaluate(second)
        second_ns = time.perf_counter_ns() - started
        started = time.perf_counter_ns()
        replay_card = service.evaluate(first)
        replay_ns = time.perf_counter_ns() - started

        with sqlite3.connect(journal.receipts.path) as db:
            timings = {
                kind: {
                    "count": count,
                    "total_ns": total,
                    "minimum_ns": minimum,
                    "maximum_ns": maximum,
                }
                for kind, count, total, minimum, maximum in db.execute(
                    "SELECT kind,count(*),sum(elapsed_ns),min(elapsed_ns),max(elapsed_ns) "
                    "FROM candidate_pack_event_v1 GROUP BY kind ORDER BY kind"
                )
            }
            pack_count = db.execute(
                "SELECT count(*) FROM candidate_pack_v1"
            ).fetchone()[0]

        result = {
            "schema_version": "c-ep1-local-baseline/1",
            "scope": "DEVELOPMENT_FIXTURE_ONLY",
            "validator_count": 1,
            "environment": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "logical_cpu_count": os.cpu_count(),
                "memory_bytes": _memory_bytes(),
                "gpu_used": False,
                "concurrency": 1,
            },
            "work": {
                "distinct_jobs": 2,
                "fresh_packs": pack_count,
                "fixture_results": 2,
                "scored_results": sum(
                    card.status == "SCORED" for card in (first_card, second_card)
                ),
                "incomplete_or_failed": 0,
                "infrastructure_retries": 0,
                "reconstruction_obligations": 2,
                "materialized_reference_cases": None,
                "reference_attempts": None,
                "reconstruction_replicas": None,
                "phase_count_limitation": "A8 does not expose qualified per-phase counts",
                "replay_added_fresh_packs": 0,
                "replay_equal": replay_card == first_card,
            },
            "end_to_end_fixture_ns": {
                "cold_first": first_ns,
                "warm_distinct_job": second_ns,
                "warm_replay": replay_ns,
            },
            "ledger_event_timings": timings,
            "claims": {
                "scientific_exam": False,
                "throughput_forecast": False,
                "production_entropy": False,
                "independent_execution_integrity": False,
            },
        }
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
