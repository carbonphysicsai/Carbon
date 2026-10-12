"""The screening ladder's per-coldkey noise floor (SCREENING-GRAIN-01 v2):
the registered minimum, the max() both ways, no cross-coldkey read, and the
fail-closed lookup."""

import math

import pytest

from carbon.challenge_validator import screening_grain as sg

V2 = {"rule": "v2-bank-sched", "score_section": "accuracy",
      "rule_digest": "sha256:c6fc92b3afbbdd40452fbd52fb822e5cff26867da9caf21b3d8a18719da24f67"}  # fmt: skip
V3 = {"rule": "v3-bank-sched", "score_section": "registered",
      "score_candidate": "G-FEAS/A-Q>@0.05",
      "registry_sha256": "70f2943814db0531429613e6ca5e2bd1c0b656673c6ee74de08e98f540758277"}  # fmt: skip


@pytest.fixture
def doc():
    return sg.load()


def test_the_lookup_reads_the_latest_version_and_fails_closed(doc):
    assert doc["version"] == 2
    assert sg.entry_for(doc, V2)["grain"] == 0.035
    assert sg.entry_for(doc, V3)["grain"] == 0.025
    assert sg.entry_for(doc, {**V2, "rule_digest": "sha256:" + "0" * 64}) is None
    assert (
        sg.entry_for(doc, {"rule": "v9-something", "score_section": "registered"})
        is None
    )
    assert sg.entry_for(None, V2) is None
    assert sg.update(doc, None, None, 0.1, 0.01, 10_000)[0] == sg.SEALED


def test_below_the_minimum_it_is_no_update_never_an_update_at_the_grain(doc):
    """(1) The minimum is pinned, and below it nothing moves."""
    nf = doc["noise_floor"]
    assert (nf["min_cases"], nf["min_design_questions"]) == (294, 24)
    v2, v3 = sg.entry_for(doc, V2), sg.entry_for(doc, V3)
    huge = 0.01  # a 10x better error than the best below: far beyond any step
    assert sg.update(doc, v2, 0.1, huge, 0.001, 293) == (sg.NO_UPDATE, 0.1)
    assert sg.update(doc, v2, None, huge, 0.001, 293) == (sg.NO_UPDATE, None)
    assert sg.update(doc, v2, 0.1, huge, 0.001, 294)[0] == sg.UPDATE
    # v3 also needs its design questions.
    assert sg.update(doc, v3, 0.5, 0.9, 0.001, 294, 23) == (sg.NO_UPDATE, 0.5)
    assert sg.update(doc, v3, 0.5, 0.9, 0.001, 294, 24)[0] == sg.UPDATE


def test_the_step_is_the_larger_of_the_grain_and_the_own_se(doc):
    """(2) A precise coldkey is floored at the grain; a noisy one at its own SE."""
    v2 = sg.entry_for(doc, V2)
    g = v2["grain"]
    best = (1 + g) ** -60  # a displayed (grid) value
    # 5 % better (over one grid step): beyond the grain (3.5 %), within a 6 % own SE.
    score = best / 1.05
    precise = sg.update(doc, v2, best, score, 0.001, 294)
    noisy = sg.update(doc, v2, best, score, 0.06, 294)
    assert precise[0] == sg.UPDATE and noisy == (sg.NO_UPDATE, best)
    # The noisy one moves once it beats its own SE (6 %), by a grid step too.
    assert sg.update(doc, v2, best, best / 1.08, 0.06, 294)[0] == sg.UPDATE
    # Exactly at the grain is not "more than" it.
    assert sg.update(doc, v2, best, best / (1 + g), 0.001, 294)[0] == sg.NO_UPDATE
    assert sg.round_up(0.0001) == 0.005 and sg.round_up(0.0251) == 0.03
    # The display never overstates (lower is better: shown >= score).
    _state, shown = precise
    assert shown >= score * (1 - 1e-12)


def test_the_own_se_reads_only_that_coldkeys_cases():
    """(3) No other coldkey's cases are read, even when present."""

    class Poison(dict):
        def __getitem__(self, key):
            raise AssertionError("another coldkey's record was read: " + key)

        def get(self, key, default=None):
            if key == "coldkey":
                return dict.get(self, key)
            raise AssertionError("another coldkey's record was read: " + key)

    mine = [{"coldkey": "ck-A", "errors": [0.10, 0.12, 0.08, 0.11]},
            {"coldkey": "ck-A", "errors": [0.09, 0.10]}]  # fmt: skip
    other = Poison(coldkey="ck-B", errors=[9.0, 0.0])
    se, n, m = sg.coldkey_own_se("v2-bank-sched", [mine[0], other, mine[1]], "ck-A")
    alone, _, _ = sg.coldkey_own_se("v2-bank-sched", mine, "ck-A")
    assert (n, m) == (6, 0) and se == alone
    errors = [0.10, 0.12, 0.08, 0.11, 0.09, 0.10]
    expected = (
        (sum((x - sum(errors) / 6) ** 2 for x in errors) / 5) ** 0.5
        / math.sqrt(6)
        / (sum(errors) / 6)
    )
    assert se == pytest.approx(expected)
