"""The battery validator daemon with real containers.

Every reconstruction and inference runs in its own container, created with the
carrier's exact isolation arguments (`battery_container_runner`). What these
tests establish:
- the isolated programs produce the same model state and predictions as the
  in-process backend;
- the daemon's screening outcome is the same through either backend;
- no container remains after a run, and the container has no network;
- a replayed run starts no container;
- a run left unresolved by a crash is reconciled onto a new attempt, never
  dispatched twice.

What they do not establish:
- the host doctor's admission, since this host is not cgroup v2;
- the accepted, digest-pinned worker image;
- GPU execution or truth solves.

Skipped unless `CARBON_BATTERY_TEST_IMAGE` names an available image.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPOSITORY / "tests" / "service"),
    str(REPOSITORY / "tests" / "cpu"),
]

import battery_container_runner as runner
from test_battery_validator_daemon import (
    PIN_G,
    PIN_S,
    batch,
    refs,  # noqa: F401 - fixture
    submission,
)

from carbon.battery import seeds
from carbon.battery.compile import compile_recipe
from carbon.battery.daemon import BatteryValidator
from carbon.battery.pool_store import PoolStore
from carbon.battery.worker import (
    CarrierBackend,
    DirectBackend,
    WorkLedger,
)

pytestmark = pytest.mark.skipif(
    not runner.available(), reason="CARBON_BATTERY_TEST_IMAGE is not available"
)
BATTERY = "battery-fastcharge-ageing-development-v1"


def containers():
    listed = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=carbon-d4-"],
        capture_output=True,
        check=True,
    )
    return listed.stdout.split()


def validator_with(tmp_path, refs, backend_factory):  # noqa: F811
    tmp_path.mkdir(mode=0o700, exist_ok=True)
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, PIN_S))
    store = PoolStore(tmp_path / "state.sqlite3")
    validator = BatteryValidator(
        store=store,
        backend=backend_factory(store),
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=False,
        allow_published_cases=True,
    )
    validator.start()
    for b in range(4):
        fp = validator.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        validator.ingest_references(fp, list(refs.values()))
    validator.open_pool()
    return validator


def carrier(store, tmp_path):
    return CarrierBackend(
        WorkLedger(store, tmp_path / "work"),
        None,
        root=REPOSITORY,
        runner=runner.run,
        identity=runner.IDENTITY,
    )


def test_isolated_programs_match_the_in_process_backend(tmp_path, refs):  # noqa: F811
    store = PoolStore(tmp_path / "state.sqlite3")
    isolated = carrier(store, tmp_path)
    direct = DirectBackend(REPOSITORY)
    inputs = {
        f"q{i}": {"c1": 1.0 + i * 0.01, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
        for i in range(4)
    }
    for backbone, parameters in (
        ("knn", {"neighbours": 5}),
        ("mlp", {"steps": 80, "width": 32, "depth": 2}),
    ):
        _, recipe = compile_recipe(
            {
                "schema_version": "1.0",
                "challenge_id": BATTERY,
                "backbone": backbone,
                "parameters": parameters,
            }
        )
        state, _ = isolated.reconstruct("rec-" + backbone, recipe, 11)
        expected, _ = direct.reconstruct("x", recipe, 11)
        assert state == expected
        assert isolated.infer("inf-" + backbone, state, inputs) == direct.infer(
            "y", expected, inputs
        )
    assert containers() == []
    assert runner.network_denied()


def test_daemon_screening_through_containers(tmp_path, refs):  # noqa: F811
    isolated = validator_with(
        tmp_path / "isolated", refs, lambda store: carrier(store, tmp_path / "isolated")
    )
    direct = validator_with(
        tmp_path / "direct", refs, lambda _: DirectBackend(REPOSITORY)
    )
    for hotkey, k in (("hk1", 8), ("hk2", 3)):
        a = isolated.admit(submission(hotkey, neighbours=k))
        b = direct.admit(submission(hotkey, neighbours=k))
        scored_a = isolated.process(a["submission_id"])
        scored_b = direct.process(b["submission_id"])
        assert scored_a["screening"] == scored_b["screening"]
        assert scored_a["reconstruction"] == {
            "backend": "CONTAINER_ISOLATED_TEST_IMAGE",
            "validator_path": False,
        }
    assert containers() == []
    # A replay is served from the work ledger: no container is started.
    ledger = isolated.backend.ledger
    before = len(ledger.status(owner=None)["operations"])
    isolated.run_pending()
    assert len(ledger.status(owner=None)["operations"]) == before


def test_a_run_left_unresolved_is_reconciled_onto_a_new_attempt(
    tmp_path,
    refs,  # noqa: F811
):
    validator = validator_with(tmp_path, refs, lambda store: carrier(store, tmp_path))
    admitted = validator.admit(submission("hk1"))
    sid = admitted["submission_id"]
    ledger = validator.backend.ledger
    # A crash after the reservation, before any container finished.
    ledger.reserve(
        f"rec-{sid}-a0",
        owner="battery-validator",
        phase="final",
        request={"crashed": True},
        resources={},
    )
    # The unresolved identity is never dispatched again: the attempt fails
    # as infrastructure, counts nothing, and is never a score.
    first = validator.process(sid)
    assert first["state"] == "FAILED_INFRA" and "screening" not in first
    validator.recover()
    assert ledger.unresolved() == []
    states = {op["id"]: op["state"] for op in ledger.status(owner=None)["operations"]}
    assert states[f"rec-{sid}-a0"] == "FAILED_INFRA"
    # The retry runs under the next attempt identity, in a fresh container.
    outcome = validator.process(sid)
    assert outcome["state"] == "SCORED"
    assert validator.store.submission(sid)["binding"]["attempt"] == 1
    assert containers() == []
    assert json.dumps(outcome).count("pscreen") == 0


def test_a_run_killed_at_its_wall_clock_bound_is_infrastructure(
    tmp_path,
    refs,  # noqa: F811
):
    """Cancellation: the container is killed mid-training and removed; its
    partial work is never read, and the retry is a new attempt."""
    validator = validator_with(tmp_path, refs, lambda store: carrier(store, tmp_path))
    validator.backend.seconds = 3  # far shorter than this recipe's training
    sid = validator.admit(
        submission("hk1", backbone="mlp", steps=20000, width=256, depth=4)
    )["submission_id"]
    first = validator.process(sid)
    assert first["state"] == "FAILED_INFRA" and "screening" not in first
    assert first["failure"]["code"].startswith("worker_infrastructure")
    assert containers() == []
    assert validator.store.model_state(sid) is None  # nothing partial retained
    validator.recover()
    assert validator.backend.ledger.unresolved() == []
    assert validator.store.submission(sid)["binding"]["attempt"] == 1


def test_partial_output_is_infrastructure_never_a_candidate_failure(
    tmp_path,
    refs,  # noqa: F811
):
    """A run whose export lacks a declared output is Carbon's failure."""

    def partial(ledger, **kwargs):
        result = runner.run(ledger, **kwargs)
        snapshot = ledger.root / result["operation"] / "snapshot"
        for name in ("fit.json", "predictions.json"):
            if (snapshot / name).exists():
                (snapshot / name).unlink()
        return result

    def backend_for(store):
        return CarrierBackend(
            WorkLedger(store, tmp_path / "work"),
            None,
            root=REPOSITORY,
            runner=partial,
            identity=runner.IDENTITY,
        )

    validator = validator_with(tmp_path, refs, backend_for)
    sid = validator.admit(submission("hk1"))["submission_id"]
    outcome = validator.process(sid)
    assert outcome["state"] == "FAILED_INFRA"
    assert outcome["failure"]["code"] == "output_missing"
    assert containers() == []
