"""Suite-wide isolation from the host's own operator state.

LANE-RESOURCE-BOUND-01: Carbon's operator host installs the miner lane's
resource profile at `~/.config/carbon/research-resource-profile.json`, and
tests on that host run as the same user. No test reads the installed file:
each sees an empty home for the fallback, and a test that needs a profile
names its own.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def _empty_profile_home(tmp_path_factory):
    return str(tmp_path_factory.mktemp("no-installed-profile-home"))


@pytest.fixture(autouse=True)
def _no_installed_research_resource_profile(monkeypatch, _empty_profile_home):
    monkeypatch.setattr(
        "carbon.development_session.miner_container._process_home",
        lambda: _empty_profile_home,
    )


@pytest.fixture(autouse=True)
def _fresh_once_per_process_caches():
    """The cold-read caches (manifest, served digests, allowlist v8, bundle context seals) are keyed on what they
    read and so never stale; they are still cleared around every test so no test leaves another a kept value.
    """
    import sys

    def clear():
        for module, name in (
            ("carbon.backbone_catalog.listing", "clear_cache"),
            ("carbon.backbone_catalog.served", "clear_cache"),
            ("carbon.level4.allowlist", "clear_cache"),
            ("carbon.development_session.library_bundles", "clear_cache"),
        ):
            loaded = sys.modules.get(module)
            if loaded is not None:
                getattr(loaded, name)()

    clear()
    yield
    clear()


@pytest.fixture(autouse=True, scope="module")
def _fresh_direct_contract_caches():
    """The direct-campaign contracts are cached per (spec, version) for speed (hundreds of clauses bind one
    profile). A test module that patches a fact or the registered catalog while one is built must not leave the
    built value to the modules after it (the F08 1.4 clause digest read a stale profile inside a full shard), so
    they are cleared when a test module starts and when it ends."""
    import sys

    def clear():
        loaded = sys.modules.get("carbon.direct_campaign.contracts")
        if loaded is not None:
            loaded.clear_caches()

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _no_served_registry_version():
    """The version a receiver serves (`registry_version.serve`, set at receiver start) is process state: no test leaves
    one for the next, so a registry lookup reads the Challenge id unless the test names a version.
    """
    import sys

    def clear():
        loaded = sys.modules.get("carbon.challenge_validator.registry_version")
        if loaded is not None:
            loaded.serve(None, None)

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _no_installed_crown_rule():
    """The crown rule a receiver installs at start (`crown_official.install`: since 17 Nov ON for every version, its
    margin unset where the version has no row) is process state: no test leaves it for the next (Runner gate-96: a
    receiver-start test left ``margin_unset`` and three KOTH tests later in the shard read their crowns as waiting).
    """
    import sys

    def clear():
        loaded = sys.modules.get("carbon.challenge_validator.crown_official")
        if loaded is not None:
            loaded.ACTIVE = None

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _no_chain_crown_hold_or_sweep_memory():
    """Process state a receiver sets at start that crown tests read (release 21 Nov 19:15:13Z: 25 order-dependent
    failures in test_operator_pause / test_pool_consider / test_king_upkeep inside one shard, all passing alone):
    `operator_pause.hold_crowns_until_fresh` (over-broad audit #10: `serve` installs a chain-freshness hold that makes
    `crowns_paused` True once its window goes stale), the crown sweep's in-process memory (`crown_pause_sweep`:
    first-seen, king-changed and queued-behind marks) and the stale-snapshot counter (`battery.intake._STALE`). No test
    leaves any of them to the next.
    """
    import sys

    def clear():
        pause = sys.modules.get("carbon.challenge_validator.operator_pause")
        if pause is not None and hasattr(pause, "hold_crowns_until_fresh"):
            pause.hold_crowns_until_fresh(None)
        sweep = sys.modules.get("carbon.challenge_validator.crown_pause_sweep")
        if sweep is not None:
            for name in ("_FIRST_SEEN", "_KING_CHANGED", "_QUEUED"):
                memo = getattr(sweep, name, None)
                if isinstance(memo, dict):
                    memo.clear()
        intake = sys.modules.get("carbon.battery.intake")
        stale = getattr(intake, "_STALE", None) if intake is not None else None
        if isinstance(stale, dict):
            stale.update({"uses": 0, "since": None})

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _no_receiver_stop_or_adoption():
    """A receiver stop (`research_carrier.door_stopping`) and a start's adoptions are process state: no test leaves
    them for the next (a stopped process starts no remote GPU build)."""
    import sys

    def clear():
        loaded = sys.modules.get("carbon.development_session.research_carrier")
        if loaded is not None and hasattr(loaded, "clear_process_state"):
            loaded.clear_process_state()

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _no_snapshot_compression_left_on():
    """A receiver's start turns on compression of verified inference snapshots' predictions.json
    (`bundle_construction_worker.compress_snapshot_predictions`), process state: no test leaves it on for the next
    (release 21 Nov 2026: a receiver test's switch made later tests' snapshots compressed, order-dependently).
    """
    import sys

    def clear():
        loaded = sys.modules.get(
            "carbon.development_session.bundle_construction_worker"
        )
        if loaded is not None and hasattr(loaded, "compress_snapshot_predictions"):
            loaded.compress_snapshot_predictions(False)

    clear()
    yield
    clear()


#: Tools a canonical run must have. A test that skips because one is missing is a
#: FAILURE there (a gate that skipped the browser-page tests silently proved nothing);
#: elsewhere the skip stands. `CARBON_CANONICAL_DEV_ENV` is set only by the canonical
#: development image.
CANONICAL_REQUIRED_TOOLS = ("node",)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    import os

    outcome = yield
    report = outcome.get_result()
    if not report.skipped or not os.environ.get("CARBON_CANONICAL_DEV_ENV"):
        return
    reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else ""
    for tool in CANONICAL_REQUIRED_TOOLS:
        if f"{tool} is not installed" in str(reason):
            report.outcome = "failed"
            report.longrepr = (
                f"required tool missing in the canonical environment: {tool} "
                f"(skip reason: {reason})"
            )
            return
