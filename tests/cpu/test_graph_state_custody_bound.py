"""Custody's state.npz bound follows the build's (live 116, 22 Nov 2026: two Motor 1.8 grades on allowlist v8, an
uncapped version, were refused ``npz_archive_size`` at the record step after build and inference had accepted them).
"""

from __future__ import annotations

import io
import zipfile

import pytest
from test_graph_route_v2 import MOTOR
from test_graph_state_custody import producer_fixture

from carbon.challenge_kit.served_versions import graph_allowlist_bytes
from carbon.development_session import bundle_graph_state
from carbon.level4 import allowlist as allowlist_module
from carbon.reconstruction.worker import model as worker_model
from scripts.dev.score_lab import public_unbound_custody as custody

MIB = 1024 * 1024


def _stored_zip(size):
    """A stored (uncompressed) zip of one ``size``-byte member: an archive of that size class."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("parameter0000.npy", bytes(size))
    return out.getvalue()


def test_motor_18_allowlist_is_uncapped_and_custody_takes_the_worker_envelope_up_to_the_file_bound():
    motor = graph_allowlist_bytes(MOTOR, "1.8")
    version = allowlist_module.Allowlist(motor).version
    assert version in allowlist_module.UNCAPPED_VERSIONS
    assert bundle_graph_state.state_limit(motor) is None
    expected = min(
        worker_model.worker_resources_for(version)["output_bytes"],
        custody.MAX_GRAPH_FILE_BYTES,
    )
    assert custody._state_archive_bytes(None, motor) == expected
    assert expected > bundle_graph_state.MAX_BYTES
    # an Allowlist object resolves the same as its bytes
    assert (
        custody._state_archive_bytes(None, allowlist_module.Allowlist(motor))
        == expected
    )


@pytest.mark.parametrize("version", sorted(allowlist_module.UNCAPPED_VERSIONS))
def test_uncapped_bound_is_never_wider_than_the_build_or_the_retained_file_bound(
    version,
):
    # the build has no state ceiling of its own on an uncapped allowlist: the worker's output envelope binds; custody
    # then retains the state as one graph file, so its bound is the smaller of the two
    envelope = worker_model.worker_resources_for(version)["output_bytes"]
    bound = min(envelope, custody.MAX_GRAPH_FILE_BYTES)
    assert bundle_graph_state.MAX_BYTES < bound <= envelope
    assert custody.MAX_GRAPH_FILE_BYTES <= custody.MAX_GRAPH_TOTAL_BYTES


def test_capped_allowlist_keeps_the_build_ceiling():
    capped = allowlist_module.PATH.read_bytes()
    assert bundle_graph_state.state_limit(capped) == bundle_graph_state.MAX_BYTES
    assert custody._state_archive_bytes(None, capped) == bundle_graph_state.MAX_BYTES
    # nothing to resolve, or an unreadable recipe: the capped bound, never a wider one
    assert custody._state_archive_bytes(None, None) == bundle_graph_state.MAX_BYTES
    assert (
        custody._state_archive_bytes(b"not a recipe", None)
        == bundle_graph_state.MAX_BYTES
    )


def test_recipe_only_callers_resolve_the_registered_allowlist():
    fixture = producer_fixture(key=(MOTOR, "1.5"))
    registered = graph_allowlist_bytes(MOTOR, "1.5")
    expected = (
        custody.MAX_STATE_BYTES
        if bundle_graph_state.state_limit(registered) is None
        else bundle_graph_state.MAX_BYTES
    )
    assert (
        custody._state_archive_bytes(fixture["recipe"].canonical_bytes, None)
        == expected
    )


def test_a_state_over_64_mib_passes_the_archive_preflight_on_an_uncapped_allowlist():
    archive = _stored_zip(65 * MIB)
    assert len(archive) > 64 * MIB
    # the live refusal, reproduced at the old (capped) bound
    with pytest.raises(custody.CustodyRefused, match="npz_archive_size"):
        custody._preflight_zip_directory(
            archive, max_bytes=bundle_graph_state.MAX_BYTES, allow_graph_header=True
        )
    custody._preflight_zip_directory(
        archive,
        max_bytes=custody._state_archive_bytes(
            None, graph_allowlist_bytes(MOTOR, "1.8")
        ),
        allow_graph_header=True,
    )


def test_bundle_header_passes_the_resolved_bound_to_the_archive_inspection(monkeypatch):
    seen = []
    inspect = custody.inspect_numeric_npz

    def spy(state, **kwargs):
        seen.append(kwargs["max_bytes"])
        return inspect(state, **kwargs)

    monkeypatch.setattr(custody, "inspect_numeric_npz", spy)
    fixture = producer_fixture()
    allowlist = fixture["material"]["allowlist_bytes"]
    custody._bundle_header(
        fixture["state"],
        graph_source=True,
        recipe=fixture["recipe"].canonical_bytes,
        allowlist=allowlist,
    )
    assert seen == [custody._state_archive_bytes(None, allowlist)]
