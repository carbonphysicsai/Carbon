"""The published block of a menu-D + headroom version (Motor 1.8): its registered values equal its pool-constants row,
and once registered it states menu D, headroom A and the in-range gate, never the pick-D search (no query budget, first
step, honesty scale, A_gen scale or variant: menu D replaces pick D, OWNER-VARIANT-RULE-NULL-MENU-D-18-01). Until the
row's last HUMAN_INPUT is filled the version is not in `_REGISTERED_POOL` and stays RESERVED.
"""

import json
from pathlib import Path

import pytest

from carbon.challenge_registry import published_exam as pe
from carbon.challenge_registry import registry

ROOT = Path(__file__).resolve().parents[2]
MOTOR_18 = ("electric-motor-magnetics", "1.8")
#: Pick-D words a menu-D + headroom block must never state (its D has no search, budget, step, honesty or variant).
PICK_D_WORDS = (
    "query budget",
    "cma-es",
    "honesty",
    "first step",
    "a_gen",
    "variant",
    "tighter",
    "looser",
)


def _row():
    document = json.loads(
        (ROOT / "scripts/validator_host_classes/pool_constants.json").read_bytes()
    )
    return document["versions"]["electric-motor-magnetics 1.8"]


def _words(value, sources=True):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "source" and not sources:
                continue  # a citation (file names, record ids), not a published claim
            yield str(k)
            yield from _words(v, sources)
    elif isinstance(value, list):
        for v in value:
            yield from _words(v, sources)
    elif isinstance(value, str):
        yield value


@pytest.fixture
def registered(monkeypatch):
    """Motor 1.8 as it will be once its row is complete (the flip is the final registration commit)."""
    monkeypatch.setitem(pe._REGISTERED_POOL, MOTOR_18, pe.MOTOR_18_REGISTRATION)
    return pe.for_version(*MOTOR_18)


def test_the_menu_pick_weights_are_the_graders():
    from carbon.scoring import menu_score

    assert pe.MENU_PICK_WEIGHTS == menu_score.WEIGHTS


def test_motor_18_s_published_registration_equals_its_pool_constants_row():
    own, row = pe.MOTOR_18_REGISTRATION, _row()
    assert own["kind"] == pe.MENU_HEADROOM
    assert own["d"] == {
        "rule": "menu",
        "tasks_per_epoch": row["menu"]["tasks_per_epoch"],
        "aggregate": row["menu"]["aggregate"],
        "rotation_days": row["menu"]["rotation_days"],
    }
    physics = row["physics"]
    assert own["a"] == {
        k: physics[k] for k in ("scoring", "skill_form", "h_min", "h_lo", "n_min")
    }
    assert own["gate"] == {
        "statistic": physics["gate_statistic"],
        "threshold_u": physics["gate_threshold"],
    }
    assert own["total"] == {
        "rule": physics["total_rule"],
        "ad_split": physics["ad_split"],
    }
    assert own["c_rule"] == row["c_rule"]["kind"]
    # menu D replaces pick D: the row registers no variant rule (the record), so the block can state none
    assert "variant_rule" not in row["optimizer"]


def test_motor_18_is_reserved_until_its_row_is_complete():
    complete = "HUMAN_INPUT" not in json.dumps(_row())
    assert (MOTOR_18 in pe._REGISTERED_POOL) == complete
    status = {(e.challenge_id, e.version): e.status for e in registry.entries()}[
        MOTOR_18
    ]
    assert status == (registry.IMPLEMENTED if complete else registry.RESERVED)


def test_registering_motor_18_offers_it(registered):
    status = {(e.challenge_id, e.version): e.status for e in registry.entries()}[
        MOTOR_18
    ]
    assert status == registry.IMPLEMENTED


def test_a_registered_menu_headroom_block_states_menu_d_headroom_a_and_the_gate(
    registered,
):
    block = registered
    rule = block["score"]["rule"]
    assert block["score"]["formula"] == "TOTAL = 0.5 * A + 0.5 * D"
    assert "ln(A_c / E) / ln(A_c)" in rule["A"] and "floored at 1 U" in rule["A"]
    assert rule["D"] == "D = min(menu D, C); see design_search"
    assert (
        "p90" in rule["gate"]
        and "26.79 U" in rule["gate"]
        and "11.44 U" in rule["gate"]
    )
    assert "73.01 U" in rule["gate"] and "gives no score" in rule["gate"]
    assert [leg["id"] for leg in block["score"]["legs"]] == [
        "A_headroom",
        "D_menu",
        "C",
    ]
    search = block["design_search"]
    assert search["menu"] == {
        "tasks_per_epoch": 3,
        "aggregate": "mean",
        "pick_weights": [0.4, 0.25, 0.15, 0.12, 0.08],
    }
    assert "top five picks" in search["what"] and "D = 0" in search["what"]
    # F-1 (Miner X-C FD-1): no code changes the draw on a schedule, so no rotation is stated.
    assert "days" not in search["what"] and "Each epoch" not in search["what"]
    # F-1 (Carbon Validator-Motor-C S1-S4): the 1.6 sections that are not true for 1.8 are cut.
    assert not {"uncertainty", "design_value_scales", "exam_shape"} & set(block)
    assert set(block["limits"]) == {"inputs", "source"}
    lines = {line["id"]: line for line in block["how_you_are_tested"]}
    assert "variants" not in lines
    assert lines["inverse_design"]["title"] == "Design value"
    assert lines["optimizer"]["title"] == "Accuracy beyond the training data"
    assert lines["registered_values"]["text"] == pe._registered_text(
        pe.MOTOR_18_REGISTRATION
    )


#: The sections the menu-D + headroom kind rewrites. The block's other sections are inherited from Motor 1.6's
#: (gates, physics_laws, design_value_scales, limits, uncertainty, exam_shape, population, minimums, rotation, koth):
#: whether each still holds for 1.8 is a science check (Carbon Validator-Motor-C) before the flip.
REWRITTEN = ("score", "design_search", "how_you_are_tested")


def test_a_menu_headroom_block_states_no_pick_d_search(registered):
    words = " ".join(
        _words({k: registered[k] for k in REWRITTEN}, sources=False)
    ).lower()
    for word in PICK_D_WORDS:
        assert word not in words, word
    assert pe.NOT_REGISTERED not in words


def test_a_menu_headroom_block_is_allow_listed_small_and_withholds(registered):
    from tests.cpu.test_published_exam_pool import WITHHELD

    assert set(registered) <= pe.ALLOWED_FIELDS
    assert len(json.dumps(registered, sort_keys=True)) < 16000
    words = " ".join(_words(registered)).lower()
    for word in WITHHELD:
        assert word not in words, word


def test_a_pick_d_version_is_published_exactly_as_before():
    """The new kind changes nothing for an entry without it (Motor 1.5 keeps its pick-D text)."""
    own = pe.registered_pool("electric-motor-magnetics", "1.5")
    assert "kind" not in own
    block = pe.for_version("electric-motor-magnetics", "1.5")
    assert block["design_search"]["search"]["query_budget"] == own["query_budget"]
    assert "variants" in {line["id"] for line in block["how_you_are_tested"]}
