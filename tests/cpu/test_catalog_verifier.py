"""The display-only catalog readiness snapshot (Validator ruling 2026-10-29): fast reads, progressive status,
generation discard, and no decision path reading it."""

from pathlib import Path

from scripts.dev.miner_launchpad import capabilities, catalog_generation
from scripts.dev.miner_launchpad.catalog_verifier import (
    FAILED_CODE,
    STALE_SECONDS,
    CatalogVerifier,
)

CFG = {"campaigns_root": "x"}


class Harness:
    """A verifier whose runs are held until the test releases them."""

    def __init__(self, compute=None):
        self.pending, self.calls, self.now = [], 0, 1000.0

        def default(cfg, progress):
            self.calls += 1
            progress(1, 3)
            progress(3, 3)
            return {"a": True, "b": False}

        self.verifier = CatalogVerifier(
            compute=compute or default,
            clock=lambda: self.now,
            spawn=self.pending.append,
        )

    def run_all(self):
        while self.pending:
            self.pending.pop(0)()


def test_a_read_never_blocks_and_ready_comes_only_from_a_completed_run():
    h = Harness()
    first = h.verifier.read(CFG)
    assert first["status"] == "verifying" and first["found"] is None
    assert h.calls == 0 and len(h.pending) == 1
    h.run_all()
    done = h.verifier.read(CFG)
    assert done["status"] == "ready" and done["found"] == {"a": True, "b": False}
    assert "stale" not in done and not h.pending


def test_one_run_at_a_time_and_progress_is_shown_while_it_runs():
    seen = []
    h = Harness()

    def compute(cfg, progress):
        progress(2, 5)
        seen.append(h.verifier.read(CFG))
        return {}

    h = Harness(compute)
    h.verifier.read(CFG)
    h.verifier.read(CFG)
    assert len(h.pending) == 1
    h.run_all()
    assert seen[0]["status"] == "verifying" and (
        seen[0]["checked"],
        seen[0]["total"],
    ) == (2, 5)
    assert len(h.pending) == 0


def test_a_run_begun_before_an_invalidating_event_is_discarded_never_shown():
    h = Harness()
    h.verifier.read(CFG)
    catalog_generation.bump()  # an install started while the run was in flight
    h.run_all()
    after = h.verifier.read(CFG)
    assert after["status"] == "verifying" and after["found"] is None
    assert len(h.pending) == 1  # a fresh run, under the current generation
    h.run_all()
    assert h.verifier.read(CFG)["status"] == "ready"
    h.verifier.read(CFG)
    h.verifier.invalidate()
    assert h.verifier.read(CFG)["found"] is None


def test_a_changed_config_invalidates():
    h = Harness()
    h.verifier.read(CFG)
    h.run_all()
    assert h.verifier.read(CFG)["status"] == "ready"
    changed = h.verifier.read({"campaigns_root": "y"})
    assert changed["status"] == "verifying" and changed["found"] is None


def test_an_older_result_is_kept_marked_stale_and_replaced_on_demand_only():
    h = Harness()
    h.verifier.read(CFG)
    h.run_all()
    h.now += STALE_SECONDS - 1
    assert "stale" not in h.verifier.read(CFG) and not h.pending
    h.now += 2
    stale = h.verifier.read(CFG)
    assert stale["status"] == "ready" and stale["stale"] is True
    assert stale["found"] == {"a": True, "b": False} and stale["checked_at"] == 1000.0
    assert len(h.pending) == 1  # re-run on that read, no timer
    h.verifier.read(CFG)
    assert len(h.pending) == 1
    h.run_all()
    assert "stale" not in h.verifier.read(CFG)


def test_a_failed_run_is_failed_with_a_stable_code_and_no_message():
    def compute(cfg, progress):
        raise OSError("/home/miner/.carbon/secret at 10.1.2.3:2376")

    h = Harness(compute)
    h.verifier.read(CFG)
    h.run_all()
    failed = h.verifier.read(CFG)
    assert failed["status"] == "failed" and failed["found"] is None
    assert failed["code"] == FAILED_CODE and failed["detail"] == "OSError"
    assert "/home" not in str(failed) and "10.1.2.3" not in str(failed)


def test_a_restart_starts_at_verifying():
    first = Harness()
    first.verifier.read(CFG)
    first.run_all()
    assert first.verifier.read(CFG)["status"] == "ready"
    assert Harness().verifier.read(CFG)["status"] == "verifying"


def test_the_capabilities_view_never_counts_unknown_as_installed_or_zero():
    entries = [{"catalog_id": "a"}, {"catalog_id": "b"}]
    verifying = capabilities._progressive(
        entries, {"status": "verifying", "found": None, "checked": 2, "total": 5}
    )
    assert verifying == {
        "entries": 2,
        "installed": None,
        "status": "verifying",
        "checked": 2,
        "total": 5,
    }
    ready = capabilities._progressive(
        entries, {"status": "ready", "found": {"a": True}, "checked": 3, "total": 3}
    )
    assert ready["installed"] == 1 and ready["status"] == "ready"
    failed = capabilities._progressive(
        entries,
        {
            "status": "failed",
            "found": None,
            "checked": 1,
            "total": 5,
            "code": "c",
            "detail": "d",
        },
    )
    assert failed["installed"] is None and failed["status"] == "failed"


def test_no_practice_submission_rebuild_or_install_path_reads_the_snapshot():
    """The snapshot is display only: nothing but the capabilities answer imports it."""
    root = Path(__file__).resolve().parents[2]
    allowed = {
        root / "scripts/dev/miner_launchpad/capabilities.py",
        root / "scripts/dev/miner_launchpad/catalog_verifier.py",
    }
    found = set()
    for base in ("carbon", "scripts"):
        for path in (root / base).rglob("*.py"):
            if "catalog_verifier" in path.read_text(encoding="utf-8", errors="ignore"):
                found.add(path)
    assert found <= allowed, sorted(str(path) for path in found - allowed)
    install_side = (
        "scripts/dev/catalog_install.py",
        "scripts/dev/miner_launchpad/catalog_build.py",
        "scripts/dev/library_bundle.py",
        "carbon/development_session/library_environment_cache.py",
    )
    for name in install_side:
        assert "catalog_verifier" not in (root / name).read_text(encoding="utf-8")
