"""A fixed practice that fails before its program ran keeps a bounded PRIVATE traceback.

A GPU prep on a fresh 4090 VM ended FAILED_INFRA at STAGING with only `worker_code
reconstruction.worker.runtime.failed` and no way to tell which call failed. `failure-<STAGE>.json` stays closed
metadata; the new `private-<stage>-traceback.txt` beside it carries the exception chain with its traceback and
the controller's own private diagnostic. It is the owner's host's private file, never a public result.
"""

from __future__ import annotations

import pytest

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure


def _fail(tmp_path, provenance, stage, error):
    with (
        pytest.raises(type(error)),
        carrier._fixed_practice_stage(tmp_path, provenance, stage),
    ):
        raise error


def _chained():
    try:
        try:
            raise OSError("copy of /uv failed: no space left")
        except OSError as cause:
            raise WorkerFailure(
                WorkerCode.RUNTIME,
                private_diagnostic=b"Error response from daemon: cannot copy",
            ) from cause
    except WorkerFailure as failure:
        return failure


def test_a_staging_failure_keeps_the_chain_the_frames_and_the_controller_diagnostic(
    tmp_path,
):
    _fail(tmp_path, carrier.LIBRARY_PREP_PROVENANCE, "STAGING", _chained())
    text = (tmp_path / "private-staging-traceback.txt").read_text()
    assert "WorkerFailure" in text and "OSError" in text
    assert "copy of /uv failed" in text  # the cause, which the closed record hides
    assert "test_stage_failure_traceback.py" in text  # the frames
    assert "Error response from daemon: cannot copy" in text  # the controller's bytes
    # the closed public-shaped record is unchanged: no text in it
    record = (tmp_path / "failure-STAGING.json").read_text()
    assert "copy of /uv" not in record and "daemon" not in record


def test_it_is_bounded_and_written_once(tmp_path):
    huge = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"x" * 10**6)
    _fail(tmp_path, carrier.LIBRARY_PREP_PROVENANCE, "CREATE", huge)
    assert (tmp_path / "private-create-traceback.txt").stat().st_size <= 32768
    # a second failure at the same stage never replaces or raises over the first
    first = (tmp_path / "private-create-traceback.txt").read_bytes()
    _fail(tmp_path, carrier.LIBRARY_PREP_PROVENANCE, "CREATE", _chained())
    assert (tmp_path / "private-create-traceback.txt").read_bytes() == first


def test_the_program_stages_keep_their_own_diagnostics_and_other_lanes_write_nothing(
    tmp_path,
):
    _fail(tmp_path, carrier.LIBRARY_PREP_PROVENANCE, "PROGRAM", _chained())
    assert not (tmp_path / "private-program-traceback.txt").exists()
    other = tmp_path / "miner"
    other.mkdir()
    _fail(other, "MINER_SELF_REPORTED", "STAGING", _chained())
    assert not list(other.glob("private-*"))


def test_an_unknown_stage_writes_nothing(tmp_path):
    carrier._retain_stage_traceback(tmp_path, "NOT_A_STAGE", _chained())
    assert not list(tmp_path.iterdir())
