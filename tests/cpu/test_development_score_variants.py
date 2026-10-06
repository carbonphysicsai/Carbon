"""Development score variants (VALIDATOR-09): one candidate definition with
the score-tuning registry (#650), never served to miners.

The parity test is the Test Lead's requirement: a score-tuning candidate
promoted to a variant scores byte-identically under both paths. Fixture
variants live in a test directory; the shipped registry is empty and refuses
a fixture.
"""

import json

import pytest

from carbon.battery.value import score_tuning as st
from carbon.challenge_validator.scoring import scoring_for
from carbon.scoring import development_score_variants as dsv

BATTERY = "battery-fastcharge-ageing-development-v1"
ORIGIN = {"sha256": "a" * 64, "commit": "b" * 40}
#: Battery's pinned practice value contract (EV4's, the Test Lead on #668),
#: read from the pin itself so a re-pin never leaves this fixture stale.
CONTRACT = scoring_for(BATTERY).practice_value_contract
ENTRY = {
    "id": "near-limit-weighted",
    "kind": "geometric",
    "weights": {"a": 0.4, "g": 0.2, "m": 0.2, "p": 0.2},
    "gate": {"measure": "near", "cutoff": 1.0},
    "stable": True,
    "basis": "diagnosis: near-limit optimism",
}


def document(version="battery-v-test-v1", **changes):
    value = {
        "schema": dsv.SCHEMA,
        "version": version,
        "challenge_id": BATTERY,
        "base_rule": "battery-practice-v2",
        "candidate": dict(ENTRY),
        "candidate_registry": dict(ORIGIN),
        "practice_value_contract": CONTRACT,
        "scope": dsv.SCOPE,
        "status": "SURVIVOR",
        "authority": {"promoted_from": "score-tuning registry"},
        "fixture": True,
    }
    value.update(changes)
    return value


def register(tmp_path, *documents):
    tmp_path.mkdir(parents=True, exist_ok=True)
    variants = {}
    for item in documents:
        (tmp_path / f"{item['version']}.json").write_text(json.dumps(item))
        variants[item["version"]] = dsv.digest(item)
    (tmp_path / "registry.json").write_text(
        json.dumps({"schema": dsv.REGISTRY_SCHEMA, "variants": variants})
    )
    return tmp_path


def load(tmp_path, **changes):
    item = document(**changes)
    return dsv.load_variant(item["version"], directory=register(tmp_path, item))


def panel(n=6):
    """The score-tuning tests' panel shape: two seeds of three recipes."""
    legs, recipe_of = {}, {}
    for i in range(n):
        member = f"rec{i // 2}-s{i % 2}"
        legs[member] = {
            "eligible": i != 3,
            "E": 0.1 * (n - i),
            "legs": {
                "a": 1.0 - i / (2 * n),
                "r": 0.5,
                "g": 0.4 + 0.05 * i,
                "m": 0.6,
                "n": 0.5,
                "p": 0.3 + 0.1 * (i % 3),
            },
            "gates": {"near": 0.5 if i < n - 1 else 3.0, "envelope": 0.5},
        }
        recipe_of[member] = f"rec{i // 2}"
    return legs, recipe_of


def test_battery_declares_exactly_the_score_tuning_legs():
    assert scoring_for(BATTERY).declared_score_components == st.LEGS


def test_the_shipped_registry_is_empty_and_refuses_an_unregistered_version():
    assert dsv.registered() == {}
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant("anything")
    assert refused.value.code == "score_variant_unregistered"


def test_a_variant_carries_the_tuning_entry_verbatim(tmp_path):
    variant = load(tmp_path)
    assert variant.entry == ENTRY
    assert variant.candidate == st.parse_candidate(ENTRY)
    identity = variant.identity()
    assert identity["candidate"] == "near-limit-weighted"
    assert identity["candidate_registry"] == ORIGIN
    assert identity["practice_value_contract"] == CONTRACT
    assert identity["label"] == "development_score_result:battery-v-test-v1"


def test_a_promoted_candidate_scores_byte_identically_under_both_paths(tmp_path):
    """The parity the Test Lead requires: panel and single-member scores from
    the variant equal the tuning loop's own, byte for byte."""
    variant = load(tmp_path)
    legs, recipe_of = panel()
    tuning = st.candidate_scores(st.parse_candidate(ENTRY), legs, recipe_of)
    mine = dsv.panel_scores(variant, legs, recipe_of)
    assert json.dumps(mine, sort_keys=True) == json.dumps(tuning, sort_keys=True)
    for row in legs.values():
        single = dsv.score_member(variant, row)
        theirs = (
            st.score_member(st.parse_candidate(ENTRY), row),
            st.gate_verdict(st.parse_candidate(ENTRY), row),
        )
        assert json.dumps((single["score"], single["gate"])) == json.dumps(theirs)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        (
            {"candidate": {**ENTRY, "kind": "deciding"}},
            "score_variant_deciding_is_the_base_rule",
        ),
        (
            {"candidate": {**ENTRY, "weights": {"a": 0.5, "z": 0.5}}},
            "score_variant_candidate_refused:candidate_legs",
        ),
        (
            {"candidate": {**ENTRY, "weights": {"a": 0.5, "m": 0.4}}},
            "score_variant_candidate_refused:candidate_weights_sum",
        ),
        (
            {"candidate": {**ENTRY, "extra": 1}},
            "score_variant_candidate_refused:candidate_fields",
        ),
        (
            {"candidate_registry": {"sha256": "a" * 64, "commit": None}},
            "score_variant_candidate_registry_malformed",
        ),
        ({"challenge_id": "chip-cold-plate"}, "score_variant_challenge_not_served"),
        ({"scope": "SERVED"}, "score_variant_malformed"),
        (
            {"practice_value_contract": "c" * 64},
            "score_variant_practice_value_contract_malformed",
        ),
        ({"status": "ADOPTED"}, "score_variant_malformed"),
    ],
)
def test_every_malformed_or_unserved_variant_is_refused_by_name(
    tmp_path, changes, code
):
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        load(tmp_path, **changes)
    assert refused.value.code == code


def test_an_undeclared_leg_is_refused(tmp_path):
    item = document()
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant(
            item["version"], directory=register(tmp_path, item), declared=("a", "r")
        )
    assert refused.value.code == "score_variant_component_not_declared"


def test_an_altered_document_is_refused(tmp_path):
    item = document()
    directory = register(tmp_path, item)
    item["candidate"]["weights"] = {"a": 1.0}
    (directory / f"{item['version']}.json").write_text(json.dumps(item))
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant(item["version"], directory=directory)
    assert refused.value.code == "score_variant_altered"


def test_a_fixture_is_refused_in_the_shipped_registry(monkeypatch, tmp_path):
    item = document()
    monkeypatch.setattr(dsv, "POLICY_DIR", register(tmp_path, item))
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant(item["version"])
    assert refused.value.code == "score_variant_fixture_in_shipped_registry"


def test_a_contract_other_than_the_challenges_pinned_one_is_refused(
    tmp_path, monkeypatch
):
    scoring = scoring_for(BATTERY)
    monkeypatch.setattr(
        type(scoring), "practice_value_contract", "sha256:" + "d" * 64, raising=False
    )
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        load(tmp_path)
    assert refused.value.code == "score_variant_practice_value_contract_not_pinned"
    monkeypatch.setattr(type(scoring), "practice_value_contract", CONTRACT)
    assert load(tmp_path).practice_value_contract == CONTRACT
