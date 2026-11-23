"""A regrade reads a task's retained files back under the bound they were retained under (live 116, 23 Nov 2026:
smiley's rtsk_aec3a4b7, state.npz 183,830,989 bytes, retained after head 0dbf587a, then refused
public_measurement_bytes_unavailable by the regrade's fixed 128 MiB read cap)."""

from __future__ import annotations

import inspect

import pytest

from carbon.challenge_kit.served_versions import graph_allowlist_bytes
from carbon.challenge_validator import lean_recipe_retention as retention
from scripts.dev.score_lab import public_unbound_custody as custody

MIB = 1024 * 1024


def test_the_read_back_bound_is_the_custody_inventorys_retained_file_bound():
    assert retention.REGRADE_ORIGIN_FILE_BYTES == custody.MAX_GRAPH_FILE_BYTES
    # every state the record step accepts (Motor 1.8, allowlist v8) reads back
    motor = graph_allowlist_bytes("electric-motor-magnetics", "1.8")
    assert (
        custody._state_archive_bytes(None, motor) <= retention.REGRADE_ORIGIN_FILE_BYTES
    )
    assert "REGRADE_ORIGIN_FILE_BYTES" in inspect.getsource(retention._regrade_origin)


def test_a_retained_file_over_128_mib_reads_back(tmp_path):
    path = tmp_path / "state.npz"
    with path.open("wb") as handle:
        handle.truncate(128 * MIB + 1)  # sparse: one byte over the old cap
    with pytest.raises(
        retention.RetentionUnavailable, match="public_measurement_bytes_unavailable"
    ):
        retention._private_measurement_bytes(path, 128 * MIB)
    body = retention._private_measurement_bytes(
        path, retention.REGRADE_ORIGIN_FILE_BYTES
    )
    assert len(body) == 128 * MIB + 1
