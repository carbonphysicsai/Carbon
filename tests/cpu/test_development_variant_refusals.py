"""Every miner-facing door refuses a development-only variant by name.

OWNER-GRAPHITE-TEST-WAVE-03 §1: only Carbon's development runners read a
development-only contract variant. The miner MCP server, the Launchpad, the
validator, the intake and any miner-facing registry path never do, and tests
prove each refusal (GRAPHITE-DEV-VARIANTS-01). Each door is driven here with a
registered fixture variant's digest (or its version name) and must answer
`development_variant_not_served`. Each door's check is also switched off once
(`MUTATIONS`) and its test shown to fail, because the generic refusal behind
it would otherwise hide a missing check.

The daemon and the intake, which need the battery references and a signed
gateway, are in `test_development_variant_daemon_intake.py`.

Synthetic fixture variants only; nothing here is security acceptance.
"""

from __future__ import annotations

import asyncio
import json

import pytest
import test_challenge_validator_contract as tvc
from test_development_variants import BATTERY, FIXTURE_DIGESTS, install

from carbon.challenge_validator import Adapters, AttemptLedger, Validator, dispatch
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import challenge_contracts as cc

NOT_SERVED = "development_variant_not_served"
VARIANT = FIXTURE_DIGESTS[1]
VERSION_NAME = "fixture-battery-level-1-v1"


@pytest.fixture(autouse=True)
def _registry(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)


def _strategy():
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "knn",
        "parameters": {"neighbours": 8},
    }


def _codes(result):
    return {(i.code, i.path) for i in result.errors}


# --- the capability registry: contract() and public_registry -----------------------------


def door_public_registry(tmp_path):
    for name in (VARIANT, VERSION_NAME):
        # Still an UnknownChallenge to every existing caller, under its own code.
        for call in (cr.public_registry, cr.contract, cr.catalog_surfaces):
            with pytest.raises(cr.UnknownChallenge) as refused:
                call(name)
            assert type(refused.value) is cr.DevelopmentVariantNotServed
            assert refused.value.code == NOT_SERVED
    # A Challenge that is neither stays an ordinary unknown.
    with pytest.raises(cr.UnknownChallenge) as unknown:
        cr.contract("no-such-challenge")
    assert type(unknown.value) is cr.UnknownChallenge


def test_public_registry_refuses_a_variant(tmp_path):
    door_public_registry(tmp_path)


# --- reconstruction/challenge_contracts ----------------------------------------------------


def door_validate_for_challenge(tmp_path):
    result = cc.validate_for_challenge(_strategy(), contract_digest=VARIANT)
    assert (NOT_SERVED, "/contract_digest") in _codes(result)
    assert not result.ok
    named = dict(_strategy(), challenge_id=VERSION_NAME)
    assert (NOT_SERVED, "/challenge_id") in _codes(cc.validate_for_challenge(named))
    # Level 0 is unchanged: the live digest and no digest both validate.
    assert cc.validate_for_challenge(_strategy()).ok
    live = cr.contract(BATTERY).digest
    assert cc.validate_for_challenge(_strategy(), contract_digest=live).ok


def test_validate_for_challenge_refuses_a_variant(tmp_path):
    door_validate_for_challenge(tmp_path)


def door_check_contract_digest(tmp_path):
    with pytest.raises(cc.SubmissionRefused) as refused:
        cc.check_contract_digest(BATTERY, VARIANT)
    assert [(i.code, i.path) for i in refused.value.issues] == [
        (NOT_SERVED, "/contract_digest")
    ]


def test_check_contract_digest_refuses_a_variant(tmp_path):
    door_check_contract_digest(tmp_path)


def door_compile_submission(tmp_path):
    with pytest.raises(cc.SubmissionRefused) as refused:
        cc.compile_submission(_strategy(), contract_digest=VARIANT)
    assert (NOT_SERVED, "/contract_digest") in {
        (i.code, i.path) for i in refused.value.issues
    }


def test_compile_submission_refuses_a_variant(tmp_path):
    door_compile_submission(tmp_path)


# --- the validator (challenge_validator/dispatch) ----------------------------------------


def _validator(tmp_path):
    folder = tmp_path / "validator"
    folder.mkdir(mode=0o700)
    ledger = AttemptLedger(folder / "ledger.sqlite3")
    return Validator(Adapters([tvc.Fake()]), ledger), ledger


def door_validator_evaluate(tmp_path):
    validator, ledger = _validator(tmp_path)
    result = validator.evaluate(tvc.sub(contract_digest=VARIANT))
    assert result["kind"] == "REFUSED" and result["code"] == NOT_SERVED
    assert result["outcome"] is None and result["pinned"] is None
    # Recorded as a refusal, never scored.
    counts = ledger.attempt_counts("hk-owner")
    assert counts["total"] == 1 and counts["by_kind"]["REFUSED"] == 1


def test_the_validator_refuses_a_variant_submission(tmp_path):
    door_validator_evaluate(tmp_path)


def door_validator_outcome(tmp_path):
    validator, _ledger = _validator(tmp_path)
    result = validator.outcome(VARIANT, "sub-1", "hk-owner")
    assert result["kind"] == "REFUSED" and result["code"] == NOT_SERVED


def test_the_validator_refuses_a_variant_outcome_request(tmp_path):
    door_validator_outcome(tmp_path)


class VariantAdapter(tvc.Fake):
    """An adapter that tries to serve a development variant's digest."""

    challenge_id = BATTERY
    challenge_version = "1.0"
    contract_digest = VARIANT

    def identities(self):
        return {**super().identities(), "contract_digest": VARIANT}


def door_adapter_registration(tmp_path):
    with pytest.raises(ValueError) as refused:
        Adapters([VariantAdapter()])
    assert str(refused.value) == NOT_SERVED


def test_no_validator_adapter_may_serve_a_variant(tmp_path):
    door_adapter_registration(tmp_path)


# --- the miner MCP door and the Challenge registry ---------------------------------------


def door_registry(tmp_path):
    from carbon import challenge_registry as challenges

    for challenge_id, version in (
        (VARIANT, None),
        (VERSION_NAME, "1.0"),
        (BATTERY, VERSION_NAME),
    ):
        for call, arguments in (
            (challenges.describe, (challenge_id, version)),
            (challenges.resolve, (challenge_id, version, "cpu_research")),
        ):
            with pytest.raises(challenges.ResolutionError) as refused:
                call(*arguments)
            assert refused.value.code == NOT_SERVED


def test_the_challenge_registry_refuses_a_variant(tmp_path):
    door_registry(tmp_path)


def door_miner_mcp(tmp_path):
    pytest.importorskip("mcp")
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon import challenge_registry as challenges
    from carbon.miner_mcp.mcp_challenges import PREFIX
    from carbon.miner_mcp.open_tier import create_open_tier_server

    server = create_open_tier_server(
        host_facts=lambda: challenges.HostFacts(frozenset())
    )
    for arguments in (
        {"challenge_id": VARIANT, "version": None},
        {"challenge_id": BATTERY, "version": VERSION_NAME},
    ):
        with pytest.raises(ToolError, match=": " + NOT_SERVED + "; next_action="):
            asyncio.run(server.call_tool(PREFIX + "describe", arguments))
    listed = asyncio.run(server.call_tool(PREFIX + "list", {}))
    text = json.dumps(listed.structured_content)
    assert VARIANT not in text and VERSION_NAME not in text


def test_the_miner_mcp_refuses_a_variant(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    door_miner_mcp(tmp_path)


# --- the Launchpad -------------------------------------------------------------------


def door_launchpad_launch(tmp_path):
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    for request in (
        {"challenge": VARIANT, "challenge_version": None},
        {"challenge": BATTERY, "challenge_version": VERSION_NAME},
    ):
        with pytest.raises(Rejected) as refused:
            RunnerAdapter._challenge(request)
        assert refused.value.code == NOT_SERVED


def test_the_launchpad_refuses_to_launch_a_variant(tmp_path):
    door_launchpad_launch(tmp_path)


def door_launchpad_submit(tmp_path):
    from carbon.battery import campaign
    from carbon.battery import remote_submission as rs

    def never(*args, **kwargs):
        raise AssertionError("nothing is sent for a development variant")

    with pytest.raises(rs.IntakeRefusal) as refused:
        campaign.submit_through_intake(
            "https://intake.invalid",
            object(),
            root=tmp_path,
            epoch=1,
            strategy=_strategy(),
            contract_digest=VARIANT,
            read=never,
            post=never,
        )
    assert refused.value.code == NOT_SERVED
    # The code is a closed intake code with its plain explanation.
    assert campaign.intake_code(NOT_SERVED) == NOT_SERVED
    assert campaign.intake_outcome(NOT_SERVED) == "REFUSED"


def test_the_launchpad_never_submits_a_variant(tmp_path):
    door_launchpad_submit(tmp_path)


def test_the_launchpad_offers_no_variant():
    """The launch options list each Challenge's families from CONTRACTS, where
    no variant ever is; the contract view refuses one."""
    from scripts.dev.miner_launchpad import campaign_view

    assert not set(FIXTURE_DIGESTS.values()) & {c.digest for c in cr.CONTRACTS.values()}
    assert VERSION_NAME not in cr.CONTRACTS
    assert campaign_view.contract_section({"id": VARIANT, "version": None}, "FULL") == {
        "status": "UNAVAILABLE",
        "challenge": {"id": VARIANT, "version": None},
    }


# --- switching each door's check off fails its test ----------------------------------


def _off(target, name):
    return lambda m: m.setattr(target, name, lambda *args, **kwargs: False)


def _contracts_off(m):
    m.setattr(cc, "is_development_variant", lambda *args, **kwargs: False)


def _registry_off(m):
    from carbon.challenge_registry import registry

    m.setattr(registry, "is_development_variant", lambda *args, **kwargs: False)


def _contract_off(m):
    real = cr.contract

    def contract(challenge=cr.BURGERS_CHALLENGE):
        if challenge in cr.CONTRACTS:
            return real(challenge)
        raise cr.UnknownChallenge("no construction contract for this challenge")

    m.setattr(cr, "contract", contract)


def _adapter_registration_off(m):
    real = cr.is_development_variant
    m.setattr(
        cr,
        "is_development_variant",
        lambda value, directory=None: (
            False if value == VARIANT else real(value, directory)
        ),
    )


def _launchpad_submit_off(m):
    m.setattr(cr, "is_development_variant", lambda *args, **kwargs: False)


MUTATIONS = {
    "public_registry": (_contract_off, door_public_registry),
    "validate_for_challenge": (_contracts_off, door_validate_for_challenge),
    "check_contract_digest": (_contracts_off, door_check_contract_digest),
    "compile_submission": (_contracts_off, door_compile_submission),
    "validator_evaluate": (
        _off(dispatch, "_development_variant"),
        door_validator_evaluate,
    ),
    "validator_outcome": (
        _off(dispatch, "_development_variant"),
        door_validator_outcome,
    ),
    "adapter_registration": (_adapter_registration_off, door_adapter_registration),
    "challenge_registry": (_registry_off, door_registry),
    "launchpad_launch": (_registry_off, door_launchpad_launch),
    "launchpad_submit": (_launchpad_submit_off, door_launchpad_submit),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_doors_check_off_fails_its_test(name, tmp_path, monkeypatch):
    disable, door = MUTATIONS[name]
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    door(intact)  # holds with the check in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        door(mutated)
