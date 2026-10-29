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
