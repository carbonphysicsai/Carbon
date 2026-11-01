"""OWNER-EXAM-VALUE-PICKS-01, option B: a score pack may carry ``baseline_floor_total``, the crown floor kept separate
from the leg minimums. Present: the floor is used and the minimums are untouched. Absent: bit-identical to before. A floor
below the minimums-derived total is refused."""

from __future__ import annotations

import copy

import pytest

from carbon.challenge_validator import koth_registry as kr
from carbon.scoring import dual_score

SHA = "sha256:" + "a" * 64


def _pack(a=0.4, d=0.6, weight=0.5, combination="weighted_arithmetic_mean", **extra):
    leg = {
        "components": [
            {
                "metric": "m",
                "unit": "1",
                "transform": "unit_benefit",
                "scale": None,
                "weight": 1.0,
            }
        ],
    }
    body = {
        "schema": dual_score.PACK_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": "chip-cold-plate",
        "physics_contract_digest": SHA,
        "measurement_contract_digest": SHA,
        "hard_gates": ["g"],
        "legs": {
            "A": {
                "components": [{**leg["components"][0], "metric": "a_metric"}],
                "minimum": a,
            },
            "D": {
                "components": [{**leg["components"][0], "metric": "d_metric"}],
                "minimum": d,
            },
        },
        "value_weight": weight,
        "combination": combination,
        "decision_policy": {
            "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
            "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
            "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
        },
        **extra,
    }
    return body


#: The pack_digest of `_pack()` registered by origin/main (f5f5509d0f) BEFORE this change.
MAIN_DIGEST = "sha256:2858ef11ee34afef7289b3112c0c302def5dcfc4ff6fa509e83afc0622d95d96"


def test_an_absent_floor_is_bit_identical_to_the_pack_as_it_always_was():
    registered = dual_score.register_pack(_pack())
    assert "baseline_floor_total" not in registered
    # the same body registers to the SAME digest main registered before the field existed
    assert registered["pack_digest"] == MAIN_DIGEST
    assert kr.baseline_total(registered) == pytest.approx(0.5 * 0.4 + 0.5 * 0.6)
    # the geometric combination too
    geometric = dual_score.register_pack(
        _pack(a=0.5, d=0.8, weight=0.3, combination="bottleneck_capped_geometric")
    )
    assert kr.baseline_total(geometric) == kr.minimums_total(geometric)
    assert kr.baseline_total(geometric) == dual_score.minimums_total(geometric)


def test_a_present_floor_is_used_and_the_minimums_are_untouched():
    plain = dual_score.register_pack(_pack())
    with_floor = dual_score.register_pack(_pack(baseline_floor_total=0.62))
    assert with_floor["baseline_floor_total"] == 0.62
    assert with_floor["legs"] == plain["legs"]  # the leg minimums are what they were
    assert (
        kr.baseline_total(with_floor) == 0.62
    )  # the crown floor is the separate figure
    assert kr.minimums_total(with_floor) == pytest.approx(0.5)
    # a floor is part of the pack's identity: another floor is another pack
    other = dual_score.register_pack(_pack(baseline_floor_total=0.63))
    assert (
        len({plain["pack_digest"], with_floor["pack_digest"], other["pack_digest"]})
        == 3
    )


def test_the_floor_equal_to_the_minimums_total_is_allowed_and_one_below_is_refused():
    kept = dual_score.register_pack(_pack(baseline_floor_total=0.5))
    assert kr.baseline_total(kept) == 0.5
    with pytest.raises(
        dual_score.DualScoreRefused, match="pack_baseline_floor_below_minimums"
    ):
        dual_score.register_pack(_pack(baseline_floor_total=0.49))
    # the registry refuses it too (a pack assembled without register_pack)
    forged = copy.deepcopy(kept)
    forged["baseline_floor_total"] = 0.49
    with pytest.raises(kr.RegistryInvalid, match="baseline_floor_invalid"):
        kr.baseline_total(forged)


@pytest.mark.parametrize(
    "bad", [-0.1, 1.5, float("nan"), float("inf"), "0.6", True, None]
)
def test_a_malformed_floor_is_refused(bad):
    with pytest.raises(dual_score.DualScoreRefused, match="pack_baseline_floor"):
        dual_score.register_pack(_pack(baseline_floor_total=bad))


def test_a_pack_with_no_minimums_takes_the_floor_as_given():
    pack = dual_score.register_pack(_pack(a=None, d=None, baseline_floor_total=0.3))
    assert kr.minimums_total(pack) is None and kr.baseline_total(pack) == 0.3
    assert kr.baseline_total(dual_score.register_pack(_pack(a=None, d=None))) is None


def test_the_registry_uses_each_packs_own_crown_floor():
    packs = [
        dual_score.register_pack(_pack(baseline_floor_total=0.60)),
        dual_score.register_pack(_pack(baseline_floor_total=0.70)),
    ]
    assert kr.baseline_total(packs[0]) == 0.60
    totals = [kr.baseline_total(p) for p in packs]
    assert sum(totals) / 2 == pytest.approx(0.65)
    # a mixed set (one pack with a floor, one without) averages each pack's own crown floor
    mixed = [packs[0], dual_score.register_pack(_pack())]
    assert [kr.baseline_total(p) for p in mixed] == [0.60, pytest.approx(0.5)]
