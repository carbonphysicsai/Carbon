"""Every miner door refuses a development score variant (VALIDATOR-09).

A development score variant is Carbon's own development scoring rule for
Graphite runs. No miner door may select, describe, launch, submit or score
under one. Each door is driven with a registered FIXTURE score variant's
version name or digest and must refuse it by name
(`development_variant_not_served`), through the same data-only name check
that refuses a development contract variant
(`capability_registry.is_development_variant`, which reads the score variant
registry as data). Each door's test is also run with the score-variant leg
of that check switched off, and must then fail: the generic refusal behind it
would otherwise hide a missing check.

Doors: the capability registry and the contract compiler, the validator's
dispatch, the challenge registry, the miner MCP door, the Launchpad's launch
and submit, the battery daemon and its intake (the public intake), the
research tools' closed request fields, and the Graphite miner path (the
standard door the Constructor attaches through).

Synthetic fixture variants only; nothing here is security acceptance.
"""

from __future__ import annotations

import asyncio

import pytest
import test_development_variant_daemon_intake as dvi
import test_development_variant_refusals as dvr
import test_research_tool_usability as rtu
from graphite_phase3_fixtures import SCORING
from test_battery_validator_daemon import backend, refs  # noqa: F401 - fixtures
from test_graphite_phase3_score_variant import BATTERY, VERSION, document
from test_graphite_phase3_score_variant import write_registry as write

from carbon.agent_campaign.graphite import miner_path
from carbon.development_session import research_tools
from carbon.reconstruction import capability_registry as cr
from carbon.scoring import development_score_variants as dsv

NOT_SERVED = "development_variant_not_served"
DIGEST = dsv.digest(document())


@pytest.fixture(autouse=True)
def _registry(tmp_path, monkeypatch):
    """The fixture score variant registered where every door's name check
    reads it, and the contract-variant door drivers pointed at its names."""
    directory = write(tmp_path / "score-variants", document())
    monkeypatch.setattr(cr, "DEVELOPMENT_SCORE_VARIANT_DIR", directory)
    monkeypatch.setattr(dvr, "VARIANT", DIGEST)
    monkeypatch.setattr(dvr, "VERSION_NAME", VERSION)
    monkeypatch.setattr(dvi, "VARIANT", DIGEST)


def _score_leg_off(m):
    m.setattr(cr, "is_development_score_variant", lambda *args, **kwargs: False)


def test_the_name_check_reads_the_score_variant_registry_as_data():
    assert cr.is_development_score_variant(VERSION)
    assert cr.is_development_score_variant(DIGEST)
    assert cr.is_development_variant(VERSION) and cr.is_development_variant(DIGEST)
    assert not cr.is_development_score_variant(BATTERY)
    assert not cr.is_development_variant(BATTERY)


def test_the_shipped_registry_names_no_score_variant(monkeypatch):
    monkeypatch.undo()
    assert cr.development_score_variant_names() == frozenset()


def test_a_malformed_score_variant_registry_fails_every_door_closed(
    tmp_path, monkeypatch
):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "registry.json").write_text('{"schema": "other"}')
    monkeypatch.setattr(cr, "DEVELOPMENT_SCORE_VARIANT_DIR", tmp_path / "bad")
    with pytest.raises(RuntimeError, match="malformed"):
        cr.is_development_variant(BATTERY)


# --- name-checked doors: each refuses, and fails with the score leg off -------------------

DOORS = {
    "public_registry": dvr.door_public_registry,
    "validate_for_challenge": dvr.door_validate_for_challenge,
    "check_contract_digest": dvr.door_check_contract_digest,
    "compile_submission": dvr.door_compile_submission,
    "validator_evaluate": dvr.door_validator_evaluate,
    "validator_outcome": dvr.door_validator_outcome,
    "challenge_registry": dvr.door_registry,
    "miner_mcp": dvr.door_miner_mcp,
    "launchpad_launch": dvr.door_launchpad_launch,
    "launchpad_submit": dvr.door_launchpad_submit,
}


@pytest.mark.parametrize("name", sorted(DOORS))
def test_a_miner_door_refuses_a_score_variant(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    DOORS[name](tmp_path)


@pytest.mark.parametrize("name", sorted(DOORS))
def test_switching_the_score_leg_off_fails_the_doors_test(name, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    DOORS[name](intact)
    _score_leg_off(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        DOORS[name](mutated)


# --- the battery daemon and the public intake ----------------------------------------------


def test_the_daemon_refuses_a_score_variant(tmp_path, refs, backend):  # noqa: F811
    validator = dvi.tbd.make(tmp_path, refs, backend)
    dvi.check_daemon_admission(validator, "hk-score-variant")
    with pytest.MonkeyPatch.context() as patch:
        _score_leg_off(patch)
        with pytest.raises(AssertionError):
            dvi.check_daemon_admission(validator, "hk-mutated")


def test_the_intake_refuses_a_score_variant(tmp_path, refs, backend):  # noqa: F811
    intake, _target = dvi.tbi.build(tmp_path, refs, backend)
    dvi.check_intake(intake)
    with pytest.MonkeyPatch.context() as patch:
        _score_leg_off(patch)
        with pytest.raises(AssertionError):
            dvi.check_intake(intake)  # queued for the daemon instead


# --- the research tools and the Graphite miner path: no field selects a rule --------------


def test_no_research_tool_takes_a_score_variant_field():
    for operation, fields in research_tools.FIELDS.items():
        assert not {"score_variant", "rule", "scoring_rule"} & set(fields), operation


def _miner_path_call(adapter, arguments):
    tools = miner_path.MinerPathTools(adapter, session="score-variant")
    return asyncio.run(
        tools.call(research_tools.PREFIX + "start_research_task", arguments, "call-1")
    )


def check_research_door(tmp_path, field):
    """A practice request naming a score variant, through the Graphite miner
    path over the standard miner door, is refused before dispatch."""
    adapter, _meter, composition, built = rtu.door_for(tmp_path, rtu.NORMALISING_V2)
    try:
        result = _miner_path_call(adapter, rtu.door_args(**{field: VERSION}))
    finally:
        composition.tasks.close()
    assert result["status"] == "MINER_PATH_REFUSED", result
    assert result["dispatch_may_have_occurred"] is False
    assert result["authority_granted"] is False
    assert built == []  # no request was built, so nothing could be signed


@pytest.mark.parametrize("field", ["score_variant", "rule"])
def test_the_graphite_miner_path_refuses_a_score_variant_field(tmp_path, field):
    check_research_door(tmp_path / "intact", field)


def test_admitting_the_field_fails_the_research_door_test(tmp_path, monkeypatch):
    fields = dict(research_tools.FIELDS)
    fields["start_research_task"] = {
        **dict(fields["start_research_task"]),
        "score_variant": "a field",
    }
    from carbon.miner_mcp import standard

    monkeypatch.setattr(research_tools, "FIELDS", fields)
    monkeypatch.setattr(standard, "FIELDS", fields)
    with pytest.raises(AssertionError):
        check_research_door(tmp_path / "mutated", "score_variant")


def test_the_miner_path_attaches_to_no_campaign_naming_a_score_variant():
    """The Graphite miner path attaches only to the session Challenge's own
    DEVELOPMENT campaign, never one a score variant names."""
    for challenge in (
        {"id": VERSION, "version": None},
        {"id": BATTERY, "version": VERSION},
        {"id": DIGEST, "version": None},
    ):
        with pytest.raises(miner_path.MinerPathRefused) as refused:
            miner_path.check_challenge({"challenge": challenge}, SCORING)
        assert refused.value.code == "miner_campaign_is_not_the_sessions_challenge"
