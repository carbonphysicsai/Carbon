"""Nominal local authority tests; fixture doubles confer no scientific evidence."""

from dataclasses import replace

import pytest
from test_reward_ledger import accepted_batch, advance, initialized, run

from carbon.rewards.core import Q12, RewardFailure, WinnerStatus
from carbon.rewards.intents import (
    POLICY,
    VALIDITY_MS,
    LocalnetIntentIssuer,
    StructuralLocalnetWeightIntent,
    TreasuryRoutingWeightIntent,
)
from carbon.rewards.intents import (
    TestnetWinnerWeightIntent as PublicTestnetIntent,
)


def test_no_winner_issues_complete_burn_with_exact_context_and_restart(tmp_path):
    ledger, _, gate, terms = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)
    ref = run(issuer.issue("opening"))
    result = issuer.resolve(ref, gate.adapter.state)
    body, projection = result["intent"], result["projection"]
    assert body["no_winner"] is True
    assert body["stage"] == "DISPOSABLE_LOCALNET"
    assert body["policy"] == POLICY
    assert body["valid_until_ms"] == terms.opens_ms + VALIDITY_MS
    assert body["context"]["genesis_hash"] == gate.context.genesis_hash
    assert body["snapshot"] == gate.adapter.state.snapshot_id
    assert projection["targets"]["winners"] == []
    assert projection["targets"]["burn"] == Q12
    restarted = LocalnetIntentIssuer(ledger)
    assert run(restarted.issue("opening")) == ref
    assert restarted.resolve(ref, gate.adapter.state) == result


def test_winner_target_comes_only_from_resolved_accepted_projection(tmp_path):
    ledger, journal, gate, _ = initialized(tmp_path)
    accepted_batch(ledger, journal, gate)
    issuer = LocalnetIntentIssuer(ledger)
    result = issuer.resolve(run(issuer.issue("winner")), gate.adapter.state)
    assert result["intent"]["no_winner"] is False
    assert result["projection"]["targets"]["winners"][0][1] == 950000000000
    assert result["projection"]["targets"]["burn"] == 50000000000
    with pytest.raises(RewardFailure, match="FIXTURE_LEDGER"):
        LocalnetIntentIssuer(result["projection"])
    with pytest.raises(RewardFailure, match="LOCALNET_INTENT"):
        issuer.resolve(result["intent"], gate.adapter.state)


@pytest.mark.parametrize("family", [PublicTestnetIntent, TreasuryRoutingWeightIntent])
def test_fixture_cannot_construct_reserved_public_or_treasury_authority(
    family, tmp_path
):
    ledger, _, _, _ = initialized(tmp_path)
    ref = run(LocalnetIntentIssuer(ledger).issue("fixture"))
    with pytest.raises(RewardFailure, match="ISSUER_UNAVAILABLE"):
        family(ref, accepted=True, stage="LIVE")
    assert family is not StructuralLocalnetWeightIntent


def test_new_issuance_supersedes_old_but_replay_does_not_reactivate(tmp_path):
    ledger, _, gate, _ = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)
    old = run(issuer.issue("old"))
    advance(gate, 1000)
    new = run(issuer.issue("new"))
    assert run(issuer.issue("old")) == old
    with pytest.raises(RewardFailure, match="SUPERSEDED_INTENT"):
        issuer.resolve(old, gate.adapter.state)
    assert issuer.resolve(new, gate.adapter.state)


def test_new_acceptance_and_quarantine_invalidate_existing_targets(tmp_path):
    ledger, journal, gate, _ = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)
    old = run(issuer.issue("opening"))
    accepted, _, _ = accepted_batch(ledger, journal, gate)
    with pytest.raises(RewardFailure, match="SUPERSEDED_SCIENTIFIC"):
        issuer.resolve(old, gate.adapter.state)
    new = run(issuer.issue("winner"))
    ledger.hold(accepted, WinnerStatus.CONTESTED, "local-fixture-contest")
    with pytest.raises(RewardFailure, match="QUARANTINED"):
        issuer.resolve(new, gate.adapter.state)
    burn = issuer.resolve(run(issuer.issue("quarantine")), gate.adapter.state)
    assert burn["projection"]["targets"]["burn"] == Q12


@pytest.mark.parametrize("delta", [-1, VALIDITY_MS, VALIDITY_MS + 1])
def test_stale_or_expired_intent_is_not_execution_authority(tmp_path, delta):
    ledger, _, gate, _ = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)
    ref = run(issuer.issue("window"))
    advance(gate, delta)
    with pytest.raises(RewardFailure, match="STALE_OR_EXPIRED"):
        issuer.resolve(ref, gate.adapter.state)


def test_wrong_chain_and_same_block_conflict_fail(tmp_path):
    ledger, _, gate, _ = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)
    ref = run(issuer.issue("bound"))
    bad = replace(gate.adapter.state, context=replace(gate.context, netuid=2))
    with pytest.raises(RewardFailure, match="CONTEXT_OR_STAGE"):
        issuer.resolve(ref, bad)
    bad = replace(gate.adapter.state, timestamp_ms=gate.adapter.state.timestamp_ms + 1)
    with pytest.raises(RewardFailure, match="STALE_OR_EXPIRED"):
        issuer.resolve(ref, bad)


def test_funding_boundary_shortens_intent_and_next_projection_is_all_burn(tmp_path):
    ledger, journal, gate, terms = initialized(tmp_path)
    accepted_batch(ledger, journal, gate)
    advance(gate, terms.funded_until_ms - gate.adapter.state.timestamp_ms - 1000)
    issuer = LocalnetIntentIssuer(ledger)
    ref = run(issuer.issue("before-funding-end"))
    assert (
        issuer.resolve(ref, gate.adapter.state)["intent"]["valid_until_ms"]
        == terms.funded_until_ms
    )
    advance(gate, 1000)
    with pytest.raises(RewardFailure, match="EXPIRED"):
        issuer.resolve(ref, gate.adapter.state)
    fresh = issuer.resolve(run(issuer.issue("after-funding-end")), gate.adapter.state)
    assert fresh["projection"]["targets"]["burn"] == Q12


def test_tampering_unknown_reference_and_malformed_inputs_fail(tmp_path):
    ledger, _, gate, _ = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)
    ref = run(issuer.issue("immutable"))
    for identity in (None, True, {}, "", "x" * 129):
        with pytest.raises(RewardFailure):
            run(issuer.issue(identity))
    with pytest.raises(RewardFailure, match="UNKNOWN_OR_CONFLICTING"):
        issuer.resolve(replace(ref, digest="f" * 64), gate.adapter.state)
    with ledger.receipts.transaction() as db:
        db.execute("UPDATE localnet_intent_v1 SET body='{}'")
    with pytest.raises(RewardFailure, match="CONFLICTING_INTENT"):
        run(issuer.issue("immutable"))


def test_reference_subclass_and_unregistered_nominal_reference_are_rejected(tmp_path):
    ledger, _, gate, _ = initialized(tmp_path)
    issuer = LocalnetIntentIssuer(ledger)

    class Forged(StructuralLocalnetWeightIntent):
        pass

    with pytest.raises(RewardFailure, match="LOCALNET_INTENT"):
        issuer.resolve(Forged("forged", "a" * 64), gate.adapter.state)
    with pytest.raises(RewardFailure, match="UNKNOWN"):
        issuer.resolve(
            StructuralLocalnetWeightIntent("unknown", "a" * 64), gate.adapter.state
        )
