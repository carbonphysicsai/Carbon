"""Battery's development-only Level 4 variant: graph-only (LEVEL4-DEV-VARIANT-01).

Claims tested:

1. `battery-l4-graph-v1` is registered, pinned by digest and recorded; the
   shipped policy is exactly what `level4.variant_document` builds (no drift),
   and it pins allowlist v1 and graph-only admission.
2. A strategy naming a submission digest compiles under it to a Level 4
   graph record; anything else in the graph slot is refused by name.
3. The shared dispatch (`development_rebuild`) routes the record to Level 4,
   never to Level 0 or Level 1, and every rebuild fails closed as Carbon's
   environment (never the candidate's) until the submission's documents
   reach the rebuild worker. G5 itself is accepted for development and
   testnet (OWNER-L4-G5-COMPILE-ISOLATION-01), so D3 is no longer the blocker.
4. The miner-facing contract still refuses the graph slot, and the variant's
   digest is refused at miner doors.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("jax")

from carbon.battery import development_rebuild, level4, level4_worker, worker
from carbon.battery.worker import DirectBackend, WorkerFailure
from carbon.level4 import allowlist as allowlist_module
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
DIGEST = "sha256:" + "ab" * 32


def strategy(value=DIGEST):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {"width": 16, "depth": 1, "steps": 16, level4.FIELD: value},
    }


def test_registered_pinned_and_free_of_drift():
    variant = dv.variant(BATTERY, 4)
    assert variant.version == level4.VERSION and variant.level == 4
    shipped = json.loads(
        (Path(dv.SHIPPED_DIR) / f"{level4.VERSION}.json").read_text(encoding="utf-8")
    )
    assert shipped == level4.variant_document(base=shipped["base_contract"])
    bounds = shipped["widened"][0]["bounds"]
    allowlist = allowlist_module.load()
    assert bounds["admission"] == "graph_only"
    assert bounds["allowlist"] == {
        "version": allowlist.version,
        "digest": allowlist.digest,
    }
    assert set(bounds["caps"].values()) == {allowlist_module.HUMAN_INPUT}
    assert shipped["participant_code"] is False
    assert dv.recorded_variant(variant) is not None


def test_compiles_to_a_level4_graph_record():
    found = dv.compile_development(strategy(), dv.variant(BATTERY, 4))
    record = development_rebuild.record(found.reconstruction)
    assert record == level4_worker.graph_record(found.reconstruction)
    assert record["submission"] == DIGEST and record["lane"] == level4_worker.BLOCKED
    assert level4_worker.BLOCKED == "level4_submission_documents_not_staged"
    assert development_rebuild.kind(record) == development_rebuild.LEVEL4
    assert development_rebuild.rebuild_label(record) == level4_worker.REBUILD_LABEL
    for value in ("not-a-digest", "sha256:" + "z" * 64, 7):
        with pytest.raises(dv.VariantRefused) as refused:
            dv.compile_development(strategy(value), dv.variant(BATTERY, 4))
        assert refused.value.code == dv.PARAMETER_REFUSED
        assert refused.value.issues[0][0] == "development.level4.submission_digest"


def test_every_rebuild_fails_closed_as_carbons_environment():
    found = dv.compile_development(strategy(), dv.variant(BATTERY, 4))
    record = development_rebuild.record(found.reconstruction)
    base = worker.RECONSTRUCT_PROGRAM
    program, files, trainer = development_rebuild.stage(
        record, base, {"recipe.json": b"{}"}, level1_program=lambda: "x"
    )
    assert trainer == development_rebuild.LEVEL4 and level4_worker.STAGED in files
    # The raise replaces the build line inside the program's `try:`, so the
    # program's own `except ImportError` records stage `environment`.
    raise_line = f"    raise ImportError({level4_worker.BLOCKED!r})\n"
    assert level4_worker._BUILD not in program and program.count(raise_line) == 1
    start = program.index(raise_line)
    assert program.rfind("try:", 0, start) > program.rfind("except", 0, start)
    assert program.index("except ImportError", start) > start
    with pytest.raises(RuntimeError):
        level4_worker.program("print('no build line')\n")
    with pytest.raises(ImportError):
        development_rebuild.build_in_process(found.construction, record)
    with pytest.raises(WorkerFailure) as failure:
        DirectBackend(REPOSITORY).reconstruct(None, found.construction, 7, record)
    assert failure.value.candidate is False


def test_miner_doors_still_refuse_the_graph_slot():
    with pytest.raises(SubmissionRefused):
        compile_submission(strategy())
    assert cr.is_development_variant(dv.variant(BATTERY, 4).digest)
