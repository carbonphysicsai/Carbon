"""LAUNCHPAD-ACCEPT-04: a testnet submit target through a tunnel, and readback.

A validator that binds its own loopback is reached from the miner's machine
as a loopback intake through a tunnel (rehearsal 3a's valV2, as
`http://127.0.0.1:18467`). Nothing publishes it: the miner names it at
Review as their own intake, with its receiver hotkey (LAUNCHPAD-ACCEPT-03).
These tests hold:
- Review's preflight of a loopback intake reads its public facts and refuses
  another network, subnet or Challenge, saying what to do;
- an intake that does not answer is `intake_unreachable`, whose next step
  names a tunnel or validator that is not running (Carbon cannot tell
  which), and the submit-time next step says so too;
- `published_endpoints.json` stays empty (OWNER-AX42-DOOR-PRIVATE-01);
- readback: a submit refusal from an intake trip carries its outcome class
  (QUEUED, UNAVAILABLE or REFUSED) on observe and on the campaign view, and a
  sealed outcome shows its public identity, never a hidden score.

The intakes are loopback fixtures; no chain, tunnel or validator is reached.
"""

from __future__ import annotations

import json
import socket

import pytest
from test_battery_remote_submission import Answering

from carbon.challenge_registry.campaigns import campaign_for_id
from scripts.dev.miner_launchpad import environment_setup as environment
from scripts.dev.miner_launchpad.environment_setup import LiveChecks, SetupRefused

BATTERY = "battery-fastcharge-ageing-development-v1"
RECEIVER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


def public_facts(**changes):
    """The battery intake's public facts for Carbon's testnet, as served."""
    from carbon.battery.challenge import CHALLENGE
    from carbon.battery.intake import PUBLIC_SCHEMA
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    context = carbon_testnet_context()
    value = {
        "schema": PUBLIC_SCHEMA,
        "network": context.network,
        "genesis": context.genesis_hash,
        "netuid": context.netuid,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "receiver": RECEIVER,
        "snapshot": {"id": "fixture-snapshot"},
    }
    return json.dumps({**value, **changes}).encode()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def check(url):
    return LiveChecks().intake(url, campaign=campaign_for_id(BATTERY))


def test_a_loopback_intake_is_read_for_its_testnet_facts_and_receiver():
    server = Answering((200, "application/json", public_facts()))
    try:
        assert check(server.url)["receiver"] == RECEIVER
    finally:
        server.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"netuid": 1},
        {"network": "finney"},
        {"challenge": {"id": "another-challenge", "version": "1"}},
    ],
)
def test_another_subnet_network_or_challenge_is_refused_with_a_step(changes):
    server = Answering((200, "application/json", public_facts(**changes)))
    try:
        with pytest.raises(SetupRefused) as refused:
            check(server.url)
    finally:
        server.close()
    assert (refused.value.field, refused.value.code) == (
        "intakes",
        "intake_serves_another_chain_or_challenge",
    )
    assert refused.value.next_step == environment.INTAKE_MISMATCH_STEP
    assert "netuid 567" in refused.value.next_step


def test_a_loopback_intake_that_does_not_answer_names_the_tunnel_or_validator():
    with pytest.raises(SetupRefused) as refused:
        check(f"http://127.0.0.1:{free_port()}")
    assert (refused.value.field, refused.value.code) == (
        "intakes",
        "intake_unreachable",
    )
    step = refused.value.next_step
    assert step == environment.LOOPBACK_UNREACHABLE_STEP
    assert "tunnel" in step and "validator" in step
    assert "cannot tell which" in step


def test_localhost_is_a_tunnel_end_and_a_remote_intake_is_told_otherwise():
    server = Answering((502, "text/html", b"<html>Bad Gateway</html>"))
    url = server.url.replace("127.0.0.1", "localhost")
    try:
        with pytest.raises(SetupRefused) as loopback:
            check(url)
    finally:
        server.close()
    # `localhost` is loopback too: a tunnel's near end.
    assert loopback.value.next_step == environment.LOOPBACK_UNREACHABLE_STEP
    assert environment._loopback("https://intake.example.org") is False
    assert "tunnel" not in environment.INTAKE_UNREACHABLE_STEP


def test_the_submit_time_step_names_the_tunnel_or_validator_too():
    from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

    step = NEXT_ACTIONS["intake_unreachable"]
    assert "tunnel" in step and "validator" in step and "cannot" in step


def test_the_tunnel_target_is_not_published():
    """OWNER-AX42-DOOR-PRIVATE-01: the loopback-through-tunnel address works
    only where the tunnel key is held, so nothing publishes it."""
    document = json.loads(environment.PUBLISHED_ENDPOINTS.read_bytes())
    assert document["endpoints"] == []
    assert environment.published_endpoints()["endpoints"] == {}


# --- readback: the intake outcome and the sealed outcome --------------------------


@pytest.mark.parametrize(
    ("code", "outcome"),
    [
        ("evaluation_queued", "QUEUED"),
        ("intake_unreachable", "UNAVAILABLE"),
        ("commitment_reader_unavailable", "UNAVAILABLE"),
        ("commitment_required", "REFUSED"),
        ("intake_receiver_mismatch", "REFUSED"),
        ("AUTH_WRONG_RECEIVER", "REFUSED"),
        ("evaluation_unavailable", None),  # no intake was configured
        ("campaign_busy", None),
    ],
)
def test_the_battery_campaign_classifies_only_its_intakes_codes(code, outcome):
    from carbon.battery import campaign

    classify = campaign_for_id(BATTERY).intake_outcome
    assert classify(code) == outcome
    if outcome is not None:
        assert campaign.intake_outcome(code) == outcome


def test_a_submit_refusal_carries_its_intake_outcome_only_for_submit(tmp_path):
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad import campaign_view
    from scripts.dev.miner_launchpad import supervisor as supervision
    from scripts.dev.miner_launchpad.runner import _intake_outcome

    (tmp_path / "campaign-manifest.json").write_text(
        json.dumps({"challenge": challenge_ref(BATTERY)})
    )
    refused = supervision.refusal("commitment_required", operation="submit")
    assert _intake_outcome(refused, tmp_path) == "REFUSED"
    practice = supervision.refusal("commitment_required", operation="practice")
    assert _intake_outcome(practice, tmp_path) is None
    assert _intake_outcome(None, tmp_path) is None
    # A campaign whose manifest cannot be read shows nothing, never a guess.
    assert _intake_outcome(refused, tmp_path / "missing") is None
    shown = campaign_view.last_refusal(
        {"last_refusal": {**refused, "intake_outcome": "REFUSED"}}
    )
    assert shown["intake_outcome"] == "REFUSED"
    odd = campaign_view.last_refusal(
        {"last_refusal": {**refused, "intake_outcome": "SCORED"}}
    )
    assert "intake_outcome" not in odd


SEALED = {
    "schema": "carbon.battery.validator-outcome.v1",
    "submission_id": "sub-fixture-0001",
    "challenge": {"id": BATTERY, "version": "1"},
    "state": "SCORED",
    "evidence": "DEVELOPMENT_SHADOW",
    "rule": "DEVELOPMENT",
    "qualification": False,
    "reward": False,
    "recipe_digest": "sha256:" + "a" * 64,
    "contract_digest": "sha256:" + "b" * 64,
    "reconstruction": {"backend": "jax", "validator_path": True},
}


def feedback(tmp_path, outcome):
    path = tmp_path / "permitted-final-feedback.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.permitted-feedback.v1",
                "epoch": 1,
                "outcome": outcome,
                "official_eligible": False,
                "reward": False,
            }
        )
    )
    return path


def test_a_sealed_outcome_reads_back_its_public_identity_only(tmp_path):
    from scripts.dev.miner_launchpad.projection import _validator_outcome

    shown = _validator_outcome(1, feedback(tmp_path, SEALED))
    result = shown["result"]
    assert shown["status"] == "VALIDATOR_OUTCOME"
    assert result["sealed"] is True and result["screening"] is None
    assert result["submission_id"] == "sub-fixture-0001"
    for key in ("rule", "recipe_digest", "contract_digest"):
        assert result[key] == SEALED[key]
    assert result["reconstruction"] == {"backend": "jax", "validator_path": True}
    assert (result["qualification"], result["reward"]) == (False, False)
    # A field in any other shape is left out, never echoed.
    odd = {**SEALED, "recipe_digest": "not a digest", "rule": {"x": 1}}
    result = _validator_outcome(1, feedback(tmp_path, odd))["result"]
    assert "recipe_digest" not in result and "rule" not in result


def test_a_screened_outcome_is_not_sealed_and_a_refusal_shows_its_reason(tmp_path):
    from scripts.dev.miner_launchpad.projection import _validator_outcome

    screened = {**SEALED, "screening": {"eligible": True, "score": 0.5}}
    assert (
        _validator_outcome(1, feedback(tmp_path, screened))["result"]["sealed"] is False
    )
    invalid = {
        **SEALED,
        "state": "INVALID_CONSTRUCTION",
        "failure": {
            "code": "recipe_refused",
            "issues": [{"code": "unknown_field", "path": ["parameters", "x"]}],
        },
    }
    result = _validator_outcome(1, feedback(tmp_path, invalid))["result"]
    assert result["sealed"] is False
    assert result["failure"] == {
        "code": "recipe_refused",
        "issues": [{"code": "unknown_field", "path": ["parameters", "x"]}],
    }
