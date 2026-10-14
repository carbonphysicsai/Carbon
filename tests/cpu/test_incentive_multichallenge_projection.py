"""Product observer aide: registered multi-Challenge targets, synthetic only.

Real ledger/projector/compiler arithmetic; no backend, provider, key, signer,
network or payment. Complete expectations are bound to the SAME synthetic
projection/snapshot, not inferred from a later live king clock. Without that
publication basis, a live mismatch is unverified/attention, not payment proof.
"""

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from carbon.chain.models import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.publication import (
    PublicationFailure,
    RuntimeCapabilities,
    compile_targets,
)
from carbon.challenge_validator.canary import CANARY_HOTKEYS
from carbon.rewards import testnet_winner_publication as publication
from carbon.rewards import winner_decay as decay
from carbon.rewards import winner_eligibility as eligibility
from carbon.rewards.core import DAY_MS, Q12, RewardFailure
from carbon.transport.store import ReceiptJournal
from scripts.dev.canary import incentive as observer

POLICY = decay.load_policy("testnet-winner-v1")
BATTERY, COOLING, MOTOR = POLICY.challenges
NOW = 10 * DAY_MS
SHARED, OTHER, PUBLISHER = "fixture-shared", "fixture-other", "fixture-publisher"
SPEC = 477  # Existing adopted testnet spec; no runtime is contacted or certified.


def fixture_projection(tmp_path, ages=(0, 1)):
    """Each age is a distinct Challenge clock for the SAME synthetic hotkey.

    Cooling has no source or ledger record. First-incumbent eligibility uses
    the actual policy's null baselines; it makes no scientific winner claim.
    """
    context = ChainContext(
        "testnet", "wss://127.0.0.1:1", "fixture", "0x" + "1" * 64, 567
    )
    state = MetagraphSnapshot(
        context,
        1080,
        "0x" + "2" * 64,
        NOW,
        (
            Participant(0, "fixture-burn", "fixture-owner-cold", 1),
            Participant(1, SHARED, "fixture-shared-cold", 2),
            Participant(2, OTHER, "fixture-other-cold", 3),
            Participant(3, PUBLISHER, "fixture-publisher-cold", 4),
        ),
    )
    authorization = publication.StandingAuthorization(
        "e" * 64,  # Synthetic record identity, never a live authorization file.
        POLICY.digest,
        context,
        PUBLISHER,
        SPEC,
        0,
        2000,
    )
    ledger = eligibility.WinnerLedger(tmp_path / "fixture-winners.jsonl")
    coldkeys = {member.hotkey: member.coldkey for member in state.participants}
    sources, winners = {}, {}
    for challenge, age in zip((BATTERY, MOTOR), ages, strict=False):
        promotion = {
            "model_id": "fixture-" + challenge,
            "hotkey": SHARED,
            "previous": None,
            "kind": eligibility.FIRST,
        }
        clock = NOW - age * DAY_MS
        record = ledger.observe(POLICY, challenge, promotion, coldkeys, clock)
        assert record["eligible"] and record["clock_ms"] == clock
        sources[challenge] = lambda promotion=promotion: promotion
        winners[challenge] = decay.Winner(SHARED, clock)
    issuer = publication.TestnetWinnerIntentIssuer(
        ReceiptJournal(tmp_path / "fixture-receipts.sqlite3", context),
        authorization,
        POLICY,
        ledger,
        sources,
    )
    capabilities = RuntimeCapabilities(
        snapshot_id=state.snapshot_id,
        spec_version=SPEC,
        mechanism_count=1,
        maximum_mechanisms=2,
        burn_mode="Burn",
        owner_coldkey="fixture-owner-cold",
        owner_hotkey="fixture-burn",
        owner_hotkeys=("fixture-burn",),
        min_weights=1,
        max_weight=65535,
        version_key=0,
        rate_limit=0,
        last_update=0,
        commit_reveal=False,
        validator_permit=True,
        sufficient_stake=True,
    )
    resolved = issuer.resolve(issuer.issue(state), state)
    return issuer, state, capabilities, resolved, winners


def compile_fixture(state, capabilities, resolved):
    return compile_targets(
        resolved,
        state,
        capabilities,
        PUBLISHER,
        network=POLICY.network,
        spec_version=SPEC,
    )


def observe(state, row, winners, hotkeys=None, *, expected_targets=None):
    options = {} if expected_targets is None else {"expected_targets": expected_targets}
    return observer.verify_epoch(
        row,
        hotkeys or {member.uid: member.hotkey for member in state.participants},
        {challenge: winner.hotkey for challenge, winner in winners.items()},
        len(POLICY.challenges),
        frozenset(CANARY_HOTKEYS),
        burn_uid=POLICY.burn_uid,
        **options,
    )


def expected_fixture_vector(state, resolved, winners):
    """Bind the pure expectation to the exact fixture's resolved projection.

    This basis exists only inside these fixtures. A signed current king alone
    does not establish when a stored row was computed, published or finalized.
    """
    intent, projection = resolved["intent"], resolved["projection"]
    assert intent["policy_digest"] == POLICY.digest
    assert intent["context"] == asdict(state.context)
    assert intent["epoch"] == state.finalized_block // POLICY.cadence_blocks
    assert intent["targets"] == projection["targets"]
    targets = projection["targets"]
    assert len(targets["challenges"]) == len(POLICY.challenges)
    expected = decay.epoch_targets(POLICY, winners, state.timestamp_ms)
    assert expected == {
        "winners": {holder["hotkey"]: amount for holder, amount in targets["winners"]},
        "burn": targets["burn"],
    }
    assert sum(expected["winners"].values()) + expected["burn"] == Q12
    return expected


def test_full_plus_half_same_hotkey_has_exact_complete_q12_and_u16_vector(tmp_path):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path)
    assert POLICY.challenges == (
        "battery-fastcharge-ageing-development-v1",
        "chip-cold-plate",
        "electric-motor-magnetics",
    )
    assert POLICY.share == 333333333333
    expected_paid, expected_burn = 499999999999, 500000000001
    assert decay.epoch_targets(POLICY, winners, NOW) == {
        "winners": {SHARED: expected_paid},
        "burn": expected_burn,
    }
    targets = resolved["projection"]["targets"]
    assert len(targets["challenges"]) == len(POLICY.challenges) == 3
    holder = {"hotkey": SHARED, "coldkey": "fixture-shared-cold", "registered_at": 2}
    assert targets["winners"] == [[holder, expected_paid]]
    assert targets["burn"] == expected_burn
    assert [
        (row["allocated"], row["earned"], row["unearned"], row["holder"])
        for row in targets["challenges"]
    ] == [
        (333333333333, 333333333333, 0, holder),
        (333333333333, 0, 333333333333, None),
        (333333333333, 166666666666, 166666666667, holder),
    ]
    # Missing cooling + motor decay + the 1-unit allocation remainder all burn.
    assert expected_burn == 333333333333 + 166666666667 + 1
    assert expected_paid + expected_burn == Q12
    plan = compile_fixture(state, capabilities, resolved)
    assert plan.q12 == ((0, expected_burn), (1, expected_paid))
    assert sum(value for _, value in plan.q12) == Q12
    # u16 uses max-normalization, so a valid row need not sum to 65535.
    assert plan.integers == ((0, 65535), (1, 65535))


@pytest.mark.parametrize("ages", [(0, 1), (0, 2), (1, 2), (0, 0)])
def test_without_clocks_shared_hotkey_is_unverified_instead_of_false_blocker(
    tmp_path, ages
):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path, ages)
    plan = compile_fixture(state, capabilities, resolved)
    result = observe(state, [list(pair) for pair in plan.integers], winners)
    assert result["state"] == observer.UNVERIFIED, result
    assert not any(
        finding["level"] == observer.BLOCKER for finding in result["findings"]
    )


@pytest.mark.parametrize("ages", [(0, 1), (0, 2), (1, 2), (0, 0)])
def test_complete_expected_vector_accepts_registered_shared_hotkey_aggregate(
    tmp_path, ages
):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path, ages)
    plan = compile_fixture(state, capabilities, resolved)
    expected = expected_fixture_vector(state, resolved, winners)
    assert sum(expected["winners"].values()) + expected["burn"] == Q12
    result = observe(state, list(plan.integers), winners, expected_targets=expected)
    assert result["state"] == observer.PASS, result
    assert result[
        "findings"
    ], "A complete-vector verdict must report a comparison basis"


@pytest.mark.parametrize(
    "row",
    [
        [[0, 43690], [1, 21845]],  # One share instead of full + half.
        [[0, 65535]],  # The eligible aggregate was burned too.
        [[1, 65535]],  # Missing cooling and decayed remainder were not burned.
    ],
)
def test_complete_vector_rejects_wrong_aggregate_or_burn_even_if_a_decay_level(
    tmp_path, row
):
    _, state, _, resolved, winners = fixture_projection(tmp_path)
    result = observe(
        state,
        row,
        winners,
        expected_targets=expected_fixture_vector(state, resolved, winners),
    )
    assert result["state"] == observer.BLOCKER, result


@pytest.mark.parametrize("defect", ["missing_burn", "not_conserved", "wrong_holder"])
def test_incomplete_or_conflicting_expected_evidence_is_unverified(tmp_path, defect):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path)
    plan = compile_fixture(state, capabilities, resolved)
    expected = expected_fixture_vector(state, resolved, winners)
    if defect == "missing_burn":
        del expected["burn"]
    elif defect == "not_conserved":
        expected["burn"] -= 1
    else:
        expected["winners"] = {OTHER: expected["winners"][SHARED]}
    result = observe(state, list(plan.integers), winners, expected_targets=expected)
    assert result["state"] == observer.UNVERIFIED, result


@pytest.mark.parametrize("ages", [(), (0,), (1,), (2,)])
def test_no_source_and_missing_winners_burn_without_earned_only_normalization(
    tmp_path, ages
):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path, ages)
    expected_paid = sum(POLICY.share // 2**age for age in ages)
    targets = resolved["projection"]["targets"]
    assert targets["burn"] == Q12 - expected_paid
    assert sum(row["earned"] for row in targets["challenges"]) == expected_paid
    assert sum(row["allocated"] for row in targets["challenges"]) == Q12 - 1
    plan = compile_fixture(state, capabilities, resolved)
    assert dict(plan.q12).get(1, 0) == expected_paid
    assert dict(plan.q12)[0] == Q12 - expected_paid
    assert sum(dict(plan.q12).values()) == Q12
    result = observe(
        state,
        list(plan.integers),
        winners,
        expected_targets=expected_fixture_vector(state, resolved, winners),
    )
    assert result["state"] == observer.PASS, result


def test_later_clock_does_not_rewrite_original_publication_fixture_basis(tmp_path):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path)
    plan = compile_fixture(state, capabilities, resolved)
    original = expected_fixture_vector(state, resolved, winners)
    later = decay.epoch_targets(POLICY, winners, state.timestamp_ms + DAY_MS)
    assert later == {"winners": {SHARED: 249999999999}, "burn": 750000000001}
    assert original != later
    # The old row belongs to the old fixture projection. A later current king
    # clock is not evidence of a new 360-block publication/finalized receipt.
    result = observe(state, list(plan.integers), winners, expected_targets=original)
    assert result["state"] == observer.PASS, result


def test_compiler_refuses_single_challenge_amount_mislabeled_as_shared_total(tmp_path):
    _, state, capabilities, resolved, _ = fixture_projection(tmp_path)
    compile_fixture(
        state, capabilities, resolved
    )  # Same real path accepts the good vector.
    wrong = deepcopy(resolved)
    wrong["projection"]["targets"]["winners"][0][1] = POLICY.share
    with pytest.raises(PublicationFailure, match="^CONFLICTING_WINNER_AGGREGATION$"):
        compile_fixture(state, capabilities, wrong)


def test_compiler_refuses_missing_challenge_and_decay_burn(tmp_path):
    _, state, capabilities, resolved, _ = fixture_projection(tmp_path)
    compile_fixture(state, capabilities, resolved)
    wrong = deepcopy(resolved)
    wrong["projection"]["targets"]["burn"] -= POLICY.share
    with pytest.raises(PublicationFailure, match="^INCOMPLETE_BURN_VECTOR$"):
        compile_fixture(state, capabilities, wrong)


@pytest.mark.parametrize(
    "changes",
    [
        {"hotkey": "fixture-recycled-uid"},
        {"coldkey": "fixture-changed-cold"},
        {"registered_at": 22},
    ],
)
def test_compiler_refuses_recycled_uid_or_changed_holder_identity(tmp_path, changes):
    _, state, capabilities, resolved, _ = fixture_projection(tmp_path)
    compile_fixture(state, capabilities, resolved)
    members = list(state.participants)
    members[1] = replace(members[1], **changes)
    changed = replace(state, participants=tuple(members))
    # Refresh capabilities too: refusal must be holder identity, not stale capabilities.
    capabilities = replace(capabilities, snapshot_id=changed.snapshot_id)
    with pytest.raises(
        PublicationFailure, match="^WINNER_IDENTITY_CHANGED_REFRESH_TO_BURN$"
    ):
        compile_fixture(changed, capabilities, resolved)


def test_without_bound_targets_observer_does_not_guess_decay_from_a_fraction(tmp_path):
    _, state, _, _, winners = fixture_projection(tmp_path)
    # Unknown publication/clock basis: do not infer a payment defect by guessing
    # a sum of binary decay levels from just this observed aggregate fraction.
    result = observe(state, [[0, 52428], [1, 13107]], winners)
    assert result["state"] == observer.UNVERIFIED, result


@pytest.mark.parametrize("recipient", [OTHER, CANARY_HOTKEYS[0]])
def test_observer_rejects_nonwinner_or_canary_despite_conserved_row(
    tmp_path, recipient
):
    _, state, _, _, winners = fixture_projection(tmp_path)
    hotkeys = {member.uid: member.hotkey for member in state.participants}
    hotkeys[2] = recipient
    result = observe(state, [[0, 31767], [1, 32768], [2, 1000]], winners, hotkeys)
    expected = (
        "canary_weighted" if recipient in CANARY_HOTKEYS else "weight_to_non_incumbent"
    )
    assert any(
        finding["level"] == observer.BLOCKER and finding["code"] == expected
        for finding in result["findings"]
    ), result


def test_unobserved_challenge_is_not_certified_by_a_compatible_row(tmp_path):
    _, state, capabilities, resolved, winners = fixture_projection(tmp_path, (0,))
    plan = compile_fixture(state, capabilities, resolved)
    result = observer.verify_epoch(
        list(plan.integers),
        {member.uid: member.hotkey for member in state.participants},
        {BATTERY: SHARED, COOLING: None},
        len(POLICY.challenges),
        frozenset(CANARY_HOTKEYS),
    )
    assert winners.keys() == {BATTERY}
    assert result["state"] == observer.UNVERIFIED, result
    assert any(
        finding["level"] == observer.UNVERIFIED and finding["challenge"] == COOLING
        for finding in result["findings"]
    ), result


def test_an_unregistered_challenge_source_is_refused_not_added_to_allocation(tmp_path):
    issuer, _, _, _, _ = fixture_projection(tmp_path)
    with pytest.raises(
        publication.WinnerPublicationRefused, match="^SOURCE_OUTSIDE_POLICY$"
    ):
        publication.TestnetWinnerIntentIssuer(
            issuer.receipts,
            issuer.authorization,
            POLICY,
            issuer.ledger,
            {"fixture-unregistered-challenge": lambda: None},
        )


def test_a_future_clock_is_refused_before_a_conserved_vector_can_be_created():
    with pytest.raises(RewardFailure, match="^CLOCK_BEFORE_PROMOTION$"):
        decay.epoch_targets(POLICY, {BATTERY: decay.Winner(SHARED, NOW + 1)}, NOW)
