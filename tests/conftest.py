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
