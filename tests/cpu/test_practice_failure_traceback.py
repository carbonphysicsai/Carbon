"""Test Runner 10:58Z/11:13Z: Cooling 1.4's '-timed' run ends FAILED_INFRA with only the marker
PYTHON_TRACEBACK recorded, and the cause is unrecoverable from the record. A failed program's
failure file now also names the exception class and its last frames (file:line:function), never
the message."""

from __future__ import annotations

import json

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

TRACE = b"""some log line
Traceback (most recent call last):
  File "/work/entry.py", line 12, in <module>
    run()
  File "/work/carbon/development_session/bundle_construction_worker.py", line 341, in run
    outputs = forward(*parameter_arrays, input_array)
  File "/opt/venv/lib/python3.11/site-packages/jax/_src/core.py", line 99, in bind
    raise KeyError(secret_value_0.123)
KeyError: 'private/path /scratch/x and 0.123456'
"""


def test_the_summary_names_the_class_and_the_frames_and_not_the_message():
    found = carrier._traceback_summary(TRACE)
    assert found["worker_exception_class"] == "KeyError"
    assert found["worker_traceback_frames"] == [
        "entry.py:12:<module>",
        "bundle_construction_worker.py:341:run",
        "core.py:99:bind",
    ]
    assert "private" not in json.dumps(found) and "0.123" not in json.dumps(found)


def test_no_traceback_no_summary():
    assert carrier._traceback_summary(b"nothing here") == {}
    assert carrier._traceback_summary(b"") == {}


def test_a_chained_exception_reports_the_last_one():
    chained = TRACE + b"\nDuring handling of the above exception, another exception occurred:\n" + (
        b'Traceback (most recent call last):\n  File "/w/a.py", line 3, in f\n    g()\n'
        b"ValueError: boom\n"
    )
    found = carrier._traceback_summary(chained)
    assert found["worker_exception_class"] == "ValueError"
    assert found["worker_traceback_frames"] == ["a.py:3:f"]


def test_the_failure_file_carries_it(tmp_path):
    error = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=TRACE)
    carrier._retain_practice_failure(tmp_path, "PROGRAM", error)
    written = json.loads((tmp_path / "failure-PROGRAM.json").read_text())
    assert written["diagnostic_markers"] == ["PYTHON_TRACEBACK"] or "PYTHON_TRACEBACK" in written[
        "diagnostic_markers"
    ]
    assert written["worker_exception_class"] == "KeyError"
    assert written["worker_traceback_frames"][-1] == "core.py:99:bind"
    assert "private/path" not in json.dumps(written)
