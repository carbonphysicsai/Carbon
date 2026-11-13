"""Motor 1.8's retained set fits the custody and grade readers because their ceilings are sized from ITS bank (13 Nov).

The canary grade on 36b7e70b closed FAILED_INFRA ``operator_bank_custody_unavailable``: the custody inventory read every
retained ``.json`` at 4 MiB, but a full-bank regrade of Motor 1.8 (2564 rows x 240 outputs) retains predictions.json at
12,342,243 B and worker-evidence.json (the predictions as base64 plus the origin's evidence) at 16,458,795 B. The same
fixed 4 MiB capped the graded originals' parse (`bundle_benchmark_core._parse_graph_original`). Both now read under the
bound of the graded query's own shape (`pair_read_bound.pair_bytes`) where a grade or regrade sized it, and every other
read keeps its standing cap. Synthetic bytes only: sizes matter here, never content.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.scoring import bundle_benchmark_core as bundle
from carbon.scoring import pair_read_bound
from scripts.dev.score_lab import public_unbound_custody as custody

MOTOR_18_ROWS, MOTOR_18_WIDTH = 2564, 240
PREDICTIONS_BYTES = 12_342_243  # measured on the Motor 1.8 full-bank regrade
WORKER_EVIDENCE_BYTES = 16_458_795
MOTOR_15_ROWS, MOTOR_15_WIDTH = 646, 60
STANDING = 4 * 1024 * 1024


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _retained(root: Path, sizes: dict) -> dict:
    files = {}
    for name, size in sizes.items():
        if name.endswith(".json"):
            raw = b'{"x":"' + b"a" * (size - 8) + b'"}'
        else:
            raw = b"#" * size
        assert len(raw) == size
        (root / name).write_bytes(raw)
        files[name] = _sha(raw)
    return files


def _inventory(root, files):
    return custody._graph_rehash_inventory(
        root, files, frozenset(files), lineage_name=None
    )


def test_the_standing_cap_still_refuses_a_motor_1_8_sized_retained_set(tmp_path):
    files = _retained(tmp_path, {"predictions.json": PREDICTIONS_BYTES})
    with pytest.raises(custody.CustodyRefused, match="graph_artifact_size"):
        _inventory(tmp_path, files)


def test_the_bank_bound_covers_the_motor_1_8_retained_set(tmp_path):
    bound = pair_read_bound.pair_bytes(MOTOR_18_ROWS, MOTOR_18_WIDTH)
    assert bound > WORKER_EVIDENCE_BYTES > PREDICTIONS_BYTES
    files = _retained(
        tmp_path,
        {
            "predictions.json": PREDICTIONS_BYTES,
            "worker-evidence.json": WORKER_EVIDENCE_BYTES,
            "recipe.json": 2048,
        },
    )
    with custody.raised_json_bytes(bound):
        observed, raw = _inventory(tmp_path, files)
    assert observed["worker-evidence.json"]["bytes"] == WORKER_EVIDENCE_BYTES
    assert set(raw) == set(files)
    # restored: the next read is under the standing cap again
    assert custody.GRAPH_JSON_FILE_BYTES == STANDING
    with pytest.raises(custody.CustodyRefused, match="graph_artifact_size"):
        _inventory(tmp_path, files)


def test_a_file_beyond_the_bank_bound_is_still_refused(tmp_path):
    bound = pair_read_bound.pair_bytes(MOTOR_18_ROWS, MOTOR_18_WIDTH)
    files = _retained(tmp_path, {"worker-evidence.json": bound + 1})
    with (
        custody.raised_json_bytes(bound),
        pytest.raises(custody.CustodyRefused, match="graph_artifact_size"),
    ):
        _inventory(tmp_path, files)


def test_a_py_file_keeps_its_cap_inside_the_raised_block(tmp_path):
    bound = pair_read_bound.pair_bytes(MOTOR_18_ROWS, MOTOR_18_WIDTH)
    files = _retained(tmp_path, {"worker.py": 5 * 1024 * 1024})
    with (
        custody.raised_json_bytes(bound),
        pytest.raises(custody.CustodyRefused, match="graph_artifact_size"),
    ):
        _inventory(tmp_path, files)


def test_the_ceiling_is_restored_however_the_block_ends():
    with pytest.raises(RuntimeError), custody.raised_json_bytes(40 * 1024 * 1024):
        assert custody.GRAPH_JSON_FILE_BYTES == 40 * 1024 * 1024
        raise RuntimeError("boom")
    assert custody.GRAPH_JSON_FILE_BYTES == STANDING
    for bad in (0, -1, 1.5, True, None):
        with pytest.raises(ValueError), custody.raised_json_bytes(bad):
            pass


def test_a_raise_below_the_standing_cap_never_lowers_it():
    with custody.raised_json_bytes(1024) as limit:
        assert limit == STANDING


def test_the_regrade_raises_only_for_a_bank_larger_than_every_live_version():
    big = retention._regrade_bank_bound(MOTOR_18_ROWS, (MOTOR_18_ROWS, MOTOR_18_WIDTH))
    assert big == pair_read_bound.pair_bytes(MOTOR_18_ROWS, MOTOR_18_WIDTH)
    assert big > retention.PAIR_READ_BYTES
    with retention._custody_json_ceiling(big):
        assert custody.GRAPH_JSON_FILE_BYTES >= big
    assert custody.GRAPH_JSON_FILE_BYTES == STANDING
    # Motor 1.5's 646 x 60 bank is below PAIR_READ_BYTES: its custody keeps the standing cap
    small = retention._regrade_bank_bound(
        MOTOR_15_ROWS, (MOTOR_15_ROWS, MOTOR_15_WIDTH)
    )
    assert small <= retention.PAIR_READ_BYTES
    with retention._custody_json_ceiling(small):
        assert custody.GRAPH_JSON_FILE_BYTES == STANDING
    with retention._custody_json_ceiling(None):
        assert custody.GRAPH_JSON_FILE_BYTES == STANDING
    # a shape that cannot be read keeps the standing caps
    assert retention._regrade_bank_bound(0, (0, 3)) is None


def _evidence(size):
    return json.dumps({"predictions_raw_base64": "A" * (size - 40)}).encode()


def test_the_graded_originals_parse_under_the_pairs_sized_ceiling():
    raw = _evidence(WORKER_EVIDENCE_BYTES)
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="graph_worker_evidence_bytes"
    ):
        bundle._parse_graph_original(raw, "graph_worker_evidence")
    bound = pair_read_bound.pair_bytes(MOTOR_18_ROWS, MOTOR_18_WIDTH)
    with pair_read_bound.raised(bound):
        parsed = bundle._parse_graph_original(raw, "graph_worker_evidence")
        assert len(parsed["predictions_raw_base64"]) > 16_000_000
        # still bounded: beyond the sized ceiling is refused
        with pytest.raises(bundle.BundleBenchmarkRefused, match="_bytes"):
            bundle._parse_graph_original(
                _evidence(bound + 100), "graph_worker_evidence"
            )
    # restored: the standing cap again, and a small original is read as before
    with pytest.raises(bundle.BundleBenchmarkRefused):
        bundle._parse_graph_original(raw, "graph_worker_evidence")
    assert bundle._parse_graph_original(b'{"a":1}', "graph_inference_receipt") == {
        "a": 1
    }
