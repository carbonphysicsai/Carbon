"""Mutation checks for GRAPHITE-ADMISSION-01: disabling each new protection
makes the test that guards it fail.

Each case switches one protection off with monkeypatch and runs its guarding
test. The guarding test must fail; if it passes, it does not exercise the
protection.
"""

from __future__ import annotations

import pytest
import test_agent_campaign_study as tstudy

from carbon.agent_campaign import study

MUTATIONS = {
    "unmapped_capability_is_refused": (
        lambda m: m.setattr(
            study,
            "planning_level",
            lambda s, capability_id: s.ladder.get(capability_id.partition(".")[0], 0),
        ),
        lambda tmp: tstudy.test_an_unmapped_capability_is_refused_not_defaulted(),
    ),
    "adapter_is_checked": (
        lambda m: m.setattr(study, "_checked", lambda s: (s, s.contract())),
        lambda tmp: tstudy.test_a_malformed_adapter_is_refused(
            {"ladder": {"model_family": 6}}, "ladder_map_malformed"
        ),
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
