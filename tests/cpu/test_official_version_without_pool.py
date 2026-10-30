"""No OFFICIAL submission is admitted on a Challenge version without a registered pool exam
(Validator WIRING_CHANNEL_AND_LOOKUP_P0_RULING_20261030, item b). The older allowlist-v7 versions
grade nothing; practice is not routed through the official door."""

from __future__ import annotations

import pytest

from carbon.challenge_kit import version_registry
from carbon.challenge_registry import published_exam
from carbon.challenge_validator import lean_recipe
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

V7_ONLY = [
    ("f08-ribbed-bracket", "1.3"),
    ("f08-ribbed-bracket", "1.4"),
    ("f02", "2.2"),
    ("f02", "2.3"),
    ("chip-cold-plate", "1.2"),
    ("electric-motor-magnetics", "1.3"),
]
LAUNCH = [
    ("chip-cold-plate", "1.6"),
    ("electric-motor-magnetics", "1.5"),
    ("f08-ribbed-bracket", "1.7"),
    ("f02", "2.5"),
]


def _adapter_stub(key):
    class Stub:
        _kit = {"id": key[0], "version": key[1]}

    return Stub()


def _check(key):
    LeanRecipeAdapter.require_registered_pool(_adapter_stub(key))


@pytest.mark.parametrize("key", V7_ONLY)
def test_an_official_submission_on_an_older_version_is_refused(key):
    assert key in version_registry.VERSIONS
    assert version_registry.VERSIONS[key].allowlist == "v7"
    assert published_exam.registered_pool(*key) is None
    with pytest.raises(lean_recipe.Unavailable) as refused:
        _check(key)
    assert "official_version_without_pool" in str(refused.value.args)


@pytest.mark.parametrize("key", LAUNCH)
def test_the_launch_versions_have_a_registered_pool_and_pass(key):
    assert published_exam.registered_pool(*key) is not None
    _check(key)


def test_every_registered_version_without_a_pool_is_refused():
    """Not only the six named: any registry version with no pool grades nothing officially."""
    for key in version_registry.VERSIONS:
        if published_exam.registered_pool(*key) is None:
            with pytest.raises(lean_recipe.Unavailable):
                _check(key)


def test_a_version_the_registry_does_not_know_is_left_to_its_own_door():
    _check(("not-a-challenge", "9.9"))
