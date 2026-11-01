"""Cooling 1.7's published record states what its A_gen slice is (Validator ruling E6); 1.6's record is unchanged."""

from carbon.challenge_registry import published_exam as pe

COOLING = "chip-cold-plate"


def _a_gen(version):
    legs = pe._BY_VERSION[(COOLING, version)]["score"]["legs"]
    return next(leg["measures"] for leg in legs if leg["id"] == "A_gen")


def test_cooling_1_7_says_a_gen_is_in_range_only_until_1_8():
    assert (
        "A_gen is measured in-range only (no out-of-range cases until 1.8)"
        in _a_gen("1.7")
    )


def test_cooling_1_6_and_1_5_keep_their_a_gen_text_and_the_other_legs_of_1_7_are_1_6s():
    for version in ("1.5", "1.6"):
        assert "extended validity region" in _a_gen(version)
    seven = pe._BY_VERSION[(COOLING, "1.7")]["score"]["legs"]
    six = pe._BY_VERSION[(COOLING, "1.6")]["score"]["legs"]
    assert [leg for leg in seven if leg["id"] != "A_gen"] == [
        leg for leg in six if leg["id"] != "A_gen"
    ]
    assert (
        pe._BY_VERSION[(COOLING, "1.7")]["score"]["formula"]
        == pe._BY_VERSION[(COOLING, "1.6")]["score"]["formula"]
    )
