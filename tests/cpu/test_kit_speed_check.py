"""The kit speed check (owner pick 3, 15 Nov 2026): a fixed public workload, timed by the grade's own inference program,
compared with a registered grading-worker row only for the exact same workload."""

import copy
import hashlib
import itertools
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from carbon.development_session import speed_workload
from scripts.dev import speed_reference_measure
from scripts.dev.miner_launchpad import speed_check

GOOD_DIGEST = "sha256:" + "1" * 64


def _row(**changes):
    row = {
        "worker_class": "EPYC 7402P, 4 pinned vCPU (grading worker)",
        "image_id": "sha256:" + "a" * 64,
        "per_call_median_seconds": 0.02,
        "startup_seconds": 1.5,
        "runs": 5,
        "measured_utc": "2026-11-15",
        "evidence_sha256": "sha256:" + "b" * 64,
    }
    row.update(changes)
    return row


def _here(**changes):
    here = {
        "schema": speed_workload.RESULT_SCHEMA,
        "workload_digest": GOOD_DIGEST,
        "image_id": "sha256:" + "a" * 64,
        "per_call_median_seconds": 0.01,
        "per_call_max_seconds": 0.02,
        "per_call_rows": speed_workload.BATCH,
        "cold_query_seconds": 1.0,
        "startup_seconds": 0.99,
    }
    here.update(changes)
    return here


def _reference_file(tmp_path, rows, schema=speed_check.REFERENCE_SCHEMA):
    path = tmp_path / "speed_reference.json"
    path.write_text(json.dumps({"schema": schema, "rows": rows}))
    return path


# -- the workload ----------------------------------------------------------------------------------------------------


def test_the_workload_is_fixed_public_and_exact():
    from carbon.challenge_kit import physical_material

    public = physical_material.bundle_material(
        speed_workload.CHALLENGE, speed_workload.VERSION
    )
    first, second = speed_workload.build(public), speed_workload.build(public)
    assert first["workload_digest"] == second["workload_digest"]
    assert first["state"] == second["state"]
    # The PUBLIC practice rows, nothing else.
    np.testing.assert_array_equal(
        first["inputs"], np.asarray(public["practice_inputs"])
    )
    assert first["expected_output_shape"] == tuple(public["expected_output_shape"])
    assert set(first["identity"]) == {
        "schema",
        "challenge",
        "graph_digest",
        "parameters_digest",
        "inputs_digest",
        "allowlist_digest",
        "program_digest",
        "staged_digests",
        "input_name",
        "batch",
    }
    assert first["binding"]["challenge_version"] == speed_workload.VERSION
    assert speed_workload.inference_wall_seconds(public) == 648


def test_the_workload_times_the_doors_own_program_for_the_version(monkeypatch):
    """The program, input name and staged modules are the door's own choice for the version
    (`registered_inference_contract` -> `v2_infer_query`), so a switch of that choice (the compiled forward) is followed,
    and it names a different workload: a reference measured on one program is never compared with another.
    """
    from carbon.development_session import direct_graph_construction_worker as worker
    from carbon.development_session.bundle_construction_worker import timed_program

    work = speed_workload.build()
    door = worker.v2_infer_query(speed_workload.CHALLENGE, speed_workload.VERSION)
    assert work["query"]["program"] == door["program"]
    assert work["query"]["input_name"] == door["input_name"] == "inputs/features"
    assert work["query"]["staged_files"] == door["staged_files"]
    assert work["query"]["provenance"] == worker.INFERENCE_PROVENANCE
    # The timed child derives its per-call program from it (the anchors are intact).
    assert timed_program(door["program"]) != door["program"]
    original = worker.v2_infer_query

    def switched(challenge_id, version):
        # Any change of the door's program for the version (eager -> compiled, or a later one): independent of which
        # program the door serves today.
        query = dict(original(challenge_id, version))
        query["program"] = query["program"] + "\n# the door's program changed\n"
        return query

    monkeypatch.setattr(worker, "v2_infer_query", switched)
    after = speed_workload.build()
    assert after["query"]["program"] != work["query"]["program"]
    assert after["workload_digest"] != work["workload_digest"]


def test_the_graph_uses_only_plain_allowlisted_ops_and_public_seeded_parameters():
    doc = speed_workload.graph_document(8, 240, "level4-allowlist-v8")
    nodes = doc["graphs"]["main"]["nodes"]
    assert {node["op"] for node in nodes} == {
        "convert_element_type",
        "dot_general",
        "broadcast_in_dim",
        "add",
        "tanh",
    }
    assert sum(node["op"] == "tanh" for node in nodes) == speed_workload.HIDDEN_LAYERS
    assert doc["graphs"]["main"]["inputs"][-1] == {
        "value": 2 * (speed_workload.HIDDEN_LAYERS + 1),
        "name": "inputs/features",
        "dtype": "float64",
        "shape": [speed_workload.BATCH, 8],
    }
    params = speed_workload.parameters(8, 240)
    again = speed_workload.parameters(8, 240)
    assert len(params) == 2 * (speed_workload.HIDDEN_LAYERS + 1)
    assert all(a.dtype == np.float32 for a in params)
    assert all(np.array_equal(a, b) for a, b in zip(params, again))


def test_a_changed_input_row_is_a_different_workload():
    from carbon.challenge_kit import physical_material

    public = physical_material.bundle_material(
        speed_workload.CHALLENGE, speed_workload.VERSION
    )
    changed = dict(public)
    changed["practice_inputs"] = np.array(public["practice_inputs"], copy=True)
    changed["practice_inputs"][0, 0] += 1.0
    assert (
        speed_workload.build(changed)["workload_digest"]
        != speed_workload.build(public)["workload_digest"]
    )


def test_summarize_needs_the_per_call_figure():
    receipt = {
        "measurement": {
            "timing_s": {"preprocess": 0.1, "inference": 0.8, "postprocess": 0.1},
            "per_call_s": [0.03, 0.01, 0.02],
        }
    }
    result = speed_workload.summarize(
        receipt, workload_digest=GOOD_DIGEST, image_id="sha256:" + "a" * 64
    )
    assert result["per_call_median_seconds"] == 0.02
    assert result["per_call_max_seconds"] == 0.03
    assert result["per_call_rows"] == 3
    assert result["startup_seconds"] == pytest.approx(0.98)
    for broken in ([], [0.0], [float("nan")], None):
        bad = copy.deepcopy(receipt)
        bad["measurement"]["per_call_s"] = broken
        with pytest.raises(ValueError, match="timing missing"):
            speed_workload.summarize(bad, workload_digest=GOOD_DIGEST, image_id="x")


def _local_runner(seen):
    count = itertools.count()

    def runner(ledger, *, source, files, output_validator, **kwargs):
        seen.append({"source": source, **kwargs})
        name = f"operation-{next(count):064x}"
        home = ledger.root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        done = subprocess.run(
            [sys.executable, "-c", source],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-4000:]
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        return {
            "operation": name,
            "files": {
                path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in snapshot.iterdir()
            },
        }

    return runner


def test_the_workload_runs_the_grades_own_timed_program_and_reports_per_call(
    tmp_path,
):
    pytest.importorskip("jax")
    from carbon.development_session.bundle_construction_worker import timed_program
    from carbon.development_session.direct_graph_construction_worker import (
        v2_infer_query,
    )
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    image = WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8))
    seen = []
    ledger = speed_workload.open_ledger(tmp_path / "ledger")
    result = speed_workload.measure(
        ledger,
        owner=speed_workload.OWNER,
        identity="speed-test-0",
        inference_image=image,
        runner=_local_runner(seen),
    )
    door = v2_infer_query(speed_workload.CHALLENGE, speed_workload.VERSION)
    assert seen[0]["source"] == timed_program(door["program"])
    assert seen[0]["provenance"] == "DIRECT_GRAPH_PUBLIC_INFERENCE"
    assert seen[0]["rebuild_wall_seconds"] == 648
    assert result["schema"] == speed_workload.RESULT_SCHEMA
    assert result["workload_digest"] == speed_workload.build()["workload_digest"]
    assert result["image_id"] == image.image_id
    assert result["per_call_rows"] == len(speed_workload.material()["practice_inputs"])
    assert 0 < result["per_call_median_seconds"] <= result["per_call_max_seconds"]
    # The ledger reopens frozen (a second kit run reuses it).
    assert speed_workload.open_ledger(tmp_path / "ledger").root == ledger.root


# -- the registered row ----------------------------------------------------------------------------------------------


def test_a_registered_row_is_read_only_for_the_exact_workload(tmp_path):
    path = _reference_file(tmp_path, {GOOD_DIGEST: _row()})
    assert speed_check.reference(GOOD_DIGEST, path) == _row()
    assert speed_check.reference("sha256:" + "2" * 64, path) is None
    assert speed_check.reference(GOOD_DIGEST, tmp_path / "absent.json") is None
    assert (
        speed_check.reference(
            GOOD_DIGEST, _reference_file(tmp_path, {GOOD_DIGEST: _row()}, "other")
        )
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"per_call_median_seconds": 0},
        {"per_call_median_seconds": float("inf")},
        {"per_call_median_seconds": True},
        {"startup_seconds": -1},
        {"runs": 0},
        {"evidence_sha256": "abc"},
        {"worker_class": ""},
        {"extra": 1},
    ],
)
def test_a_malformed_row_is_never_used(tmp_path, changes):
    path = _reference_file(tmp_path, {GOOD_DIGEST: _row(**changes)})
    assert speed_check.reference(GOOD_DIGEST, path) is None


def test_the_shipped_reference_file_is_well_formed():
    document = json.loads(speed_check.REFERENCE_PATH.read_bytes())
    assert document["schema"] == speed_check.REFERENCE_SCHEMA
    assert type(document["rows"]) is dict
    for digest, row in document["rows"].items():
        # Every registered row is one the kit would read: no row that silently reads as "not registered".
        assert speed_check.reference(digest) == row


# -- the words -------------------------------------------------------------------------------------------------------


def test_with_no_registered_row_the_kit_shows_this_machine_alone():
    lines = speed_check.report(_here(), None, 648)
    text = "\n".join(lines)
    assert "this machine:    10.0 ms per call" in text
    assert "not registered yet" in text
    assert "ratio:" not in text and "limit:" not in text
    assert speed_check.CAVEAT in text


def test_the_ratio_and_the_wall_line():
    text = "\n".join(speed_check.report(_here(), _row(), 648))
    assert "grading worker:  20.0 ms per call" in text
    assert "the grading worker is 2.00x slower than this machine" in text
    assert (
        "a graded inference pass that takes about 324 s on this machine would take about 648 s on the grading worker"
        in text
    )
    assert "image differs" not in text
    faster = "\n".join(
        speed_check.report(_here(per_call_median_seconds=0.04), _row(), 648)
    )
    assert "the grading worker is 2.00x faster than this machine" in faster
    assert "takes about 1296 s on this machine" in faster


def test_a_different_worker_image_is_said():
    text = "\n".join(
        speed_check.report(_here(image_id="sha256:" + "c" * 64), _row(), 648)
    )
    assert "your worker image differs" in text


# -- the measurement -------------------------------------------------------------------------------------------------


def test_the_candidate_row_is_the_median_and_one_workload():
    results = [
        _here(per_call_median_seconds=s, startup_seconds=s * 100)
        for s in (0.03, 0.01, 0.02)
    ]
    digest, row = speed_reference_measure.candidate_row(
        results,
        worker_class="class",
        evidence_sha256="sha256:" + "b" * 64,
        measured_utc="2026-11-15",
    )
    assert digest == GOOD_DIGEST
    assert row["per_call_median_seconds"] == 0.02
    assert row["startup_seconds"] == 2.0
    assert row["runs"] == 3
    assert set(row) == speed_check._ROW_KEYS
    with pytest.raises(ValueError, match="differ"):
        speed_reference_measure.candidate_row(
            [*results, _here(workload_digest="sha256:" + "9" * 64)],
            worker_class="class",
            evidence_sha256="sha256:" + "b" * 64,
            measured_utc="2026-11-15",
        )
