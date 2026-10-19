"""CI exposes only closed exit/status/deadline values from private evidence."""

import json

import pytest
from closed_export_failure_fixture import closed_export_failure


def record(tmp_path, **changes):
    operation = tmp_path / ("operation-" + "1" * 64)
    operation.mkdir(exist_ok=True)
    value = {
        "schema": "carbon.autoresearch.export-failure-evidence.v1",
        "launch_digest": "sha256:" + "1" * 64,
        "observed_exec_exit": 7,
        "export_deadline_reached": False,
        "observation": {"status": "OBSERVED", "memory": {"peak_bytes": 123456}},
        "stderr": "SECRET_TOKEN /private/path",
    }
    value.update(changes)
    path = operation / "private-export-failure-evidence.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return operation, path


def test_closed_projection_omits_private_text_identity_and_counters(tmp_path):
    operation, _ = record(tmp_path)
    result = closed_export_failure(operation)
    assert result == {
        "observed_exec_exit": 7,
        "observation_status": "OBSERVED",
        "export_deadline_reached": False,
    }
    assert all(
        text not in json.dumps(result)
        for text in (
            "SECRET_TOKEN",
            "/private/path",
            "peak_bytes",
            "123456",
            "launch_digest",
        )
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"observed_exec_exit": True},
        {"observed_exec_exit": -1},
        {"observed_exec_exit": 256},
        {"observed_exec_exit": "SECRET"},
        {"export_deadline_reached": "SECRET"},
        {"observation": {"status": "SECRET"}},
        {"observation": []},
        {"schema": "other"},
        {"launch_digest": "sha256:" + "2" * 64},
    ],
)
def test_malformed_or_other_launch_is_unknown(tmp_path, changes):
    operation, _ = record(tmp_path, **changes)
    assert closed_export_failure(operation) == {
        "observed_exec_exit": None,
        "observation_status": "UNKNOWN",
        "export_deadline_reached": None,
    }


@pytest.mark.parametrize("raw", [b"{", b"\xff", b"SECRET" * 1024])
def test_unreadable_or_oversized_record_never_becomes_diagnostic_text(tmp_path, raw):
    operation, path = record(tmp_path)
    path.write_bytes(raw)
    assert closed_export_failure(operation)["observation_status"] == "UNKNOWN"


def test_missing_record_and_explicit_null_exit_remain_unknown(tmp_path):
    operation, path = record(
        tmp_path,
        observed_exec_exit=None,
        observation={"status": "UNKNOWN"},
        export_deadline_reached=True,
    )
    assert closed_export_failure(operation) == {
        "observed_exec_exit": None,
        "observation_status": "UNKNOWN",
        "export_deadline_reached": True,
    }
    path.unlink()
    assert closed_export_failure(operation)["export_deadline_reached"] is None
