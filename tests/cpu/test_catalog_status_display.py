"""A page poll never re-inspects the daemon, and an unreadable daemon never reads as "nothing installed"
(readiness-latency, Test Runner's GCP diagnosis 2026-10-29)."""

from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import catalog_build, catalog_state
from scripts.dev.miner_launchpad.catalog_verifier import (
    BACKOFF_FACTOR,
    STALE_SECONDS,
    CatalogVerifier,
)

CFG = {"campaigns_root": "x"}


@pytest.fixture
def poll(monkeypatch):
    """`catalog_build.status` with a profile, no running install, and a fresh readiness that must not run."""
    monkeypatch.setattr(catalog_build, "_profile", lambda state_dir: CFG)
    monkeypatch.setattr(catalog_build, "running", lambda state_dir: False)
    monkeypatch.setattr(catalog_build, "_record", lambda state_dir: {})

    def fresh(*args, **kwargs):
        raise AssertionError("a page poll must not inspect the daemon")

    monkeypatch.setattr(catalog_state, "readiness", fresh)
    return lambda display: catalog_build.status("state", display=display)


def test_verifying_shows_no_counts_never_zero(poll):
    shown = poll(
        lambda cfg: {"found": None, "status": "verifying", "checked": 3, "total": 9}
    )
    assert shown["state"] == "VERIFYING"
    assert shown["installed"] is None and shown["total"] is None
    assert shown["readiness"] == {"status": "verifying", "checked": 3, "total": 9}


def test_a_failed_check_is_unknown_not_nothing_installed(poll):
    shown = poll(
        lambda cfg: {
            "found": None,
            "status": "failed",
            "checked": 0,
            "total": 0,
            "code": "catalog.readiness.failed",
            "detail": "ReadinessUnknown",
        }
    )
    assert shown["state"] == "UNKNOWN"
    assert shown["installed"] is None and shown["total"] is None
    assert shown["readiness"]["code"] == "catalog.readiness.failed"


def test_a_ready_snapshot_gives_the_counts_without_a_daemon_call(poll):
    from carbon.backbone_catalog import listing

    ids = [item["catalog_id"] for item in listing.load()["entries"]]
    found = {catalog_id: True for catalog_id in ids}
    shown = poll(
        lambda cfg: {
            "found": found,
            "status": "ready",
            "checked": len(ids),
            "total": len(ids),
        }
    )
    assert shown["state"] == "COMPLETE"
    assert shown["installed"] == shown["total"] == len(ids)


def test_a_running_install_still_measures_its_live_count_fresh(monkeypatch):
    monkeypatch.setattr(catalog_build, "_profile", lambda state_dir: CFG)
    monkeypatch.setattr(catalog_build, "running", lambda state_dir: True)
    monkeypatch.setattr(catalog_build, "_record", lambda state_dir: {})
    calls = []
    monkeypatch.setattr(
        catalog_state,
        "progress",
        lambda cfg, found=None: calls.append(cfg)
        or {"total": 4, "installed": 1, "challenges": []},
    )

    def display(cfg):
        raise AssertionError("the snapshot is discarded while an install runs")

    shown = catalog_build.status("state", display=display)
    assert shown["state"] == "RUNNING" and shown["installed"] == 1 and calls == [CFG]


@pytest.fixture
def daemonless(monkeypatch):
    monkeypatch.setattr(catalog_state, "cache_root", lambda cfg: Path("."))

    def broken(cfg):
        raise OSError("daemon unreachable")

    monkeypatch.setattr(catalog_state, "parents", broken)
    item = {"catalog_id": "a", "bundle_ref": {"runtime_profile_id": "p"}}
    return [item]


def test_an_unreadable_daemon_fails_closed_by_default_and_raises_when_strict(
    daemonless,
):
    assert catalog_state.readiness(CFG, daemonless) == {"a": False}
    with pytest.raises(catalog_state.ReadinessUnknown):
        catalog_state.readiness(CFG, daemonless, strict=True)


def test_the_verifier_reads_an_unreadable_daemon_as_failed_not_ready(
    daemonless, monkeypatch
):
    from scripts.dev.miner_launchpad import catalog_verifier

    monkeypatch.setattr(
        catalog_verifier,
        "_compute",
        lambda cfg, progress: catalog_state.readiness(
            CFG, daemonless, progress=progress, strict=True
        ),
    )
    pending = []
    verifier = CatalogVerifier(compute=catalog_verifier._compute, spawn=pending.append)
    verifier.read(CFG)
    pending.pop()()
    view = verifier.read(CFG)
    assert view["status"] == "failed" and view["found"] is None


def test_a_slow_run_is_not_repeated_until_three_times_its_duration():
    now = [1000.0]
    pending = []

    def slow(cfg, progress):
        now[0] += 65.0  # one pass under a loaded daemon
        return {"a": True}

    verifier = CatalogVerifier(compute=slow, clock=lambda: now[0], spawn=pending.append)
    verifier.read(CFG)
    pending.pop()()
    assert verifier.read(CFG)["status"] == "ready"
    now[0] += STALE_SECONDS + 1  # past the plain staleness, inside 3 x 65 s
    held = verifier.read(CFG)
    assert not pending and "stale" not in held
    now[0] += BACKOFF_FACTOR * 65.0
    assert verifier.read(CFG).get("stale") is True and len(pending) == 1
