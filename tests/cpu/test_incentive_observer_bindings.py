"""Synthetic signed public feeds only; no real key, chain, payment or operator."""

import io
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from carbon.chain.models import ChainContext, MetagraphSnapshot, Participant
from carbon.challenge_validator.feed_file import FEED_DOMAIN, FEED_SCHEMA, canonical
from carbon.rewards.winner_decay import load_policy
from scripts.dev.canary import incentive as inc
from scripts.dev.canary import incentive_observation as obs

KEY = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
PUBLIC_KEY = (
    KEY.public_key()
    .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    .hex()
)


def signed(**changes):
    feed = {
        "schema": FEED_SCHEMA,
        "validator": {"hotkey": "5Validator", "feed_key": PUBLIC_KEY},
        "challenge": {"id": inc.BATTERY},
        "leaderboard": {"incumbent": None, "standing": []},
        "king": {"hotkey": "5CurrentWinner", "eligible": True},
        **changes,
    }
    return {**feed, "signature": KEY.sign(FEED_DOMAIN + canonical(feed).encode()).hex()}


def opener(feed):
    def read(_url, *, timeout):
        assert timeout == 10
        return io.BytesIO(json.dumps(feed).encode())

    return read


def test_current_winner_does_not_wait_for_released_leaderboard():
    feed = signed()
    assert feed["leaderboard"]["incumbent"] is None
    assert (
        inc.read_incumbent("https://example.invalid", PUBLIC_KEY, opener=opener(feed))
        == "5CurrentWinner"
    )


@pytest.mark.parametrize(
    "changes", [{"schema": "wrong.schema"}, {"challenge": {"id": "other"}}]
)
def test_correctly_signed_wrong_schema_or_challenge_is_unverified(changes):
    feed = signed(**changes)
    with pytest.raises(inc.Unverified):
        inc.read_incumbent("https://example.invalid", PUBLIC_KEY, opener=opener(feed))


POLICY = load_policy("testnet-winner-v1")
NOW = 1_800_000_000_000
CONTEXT = ChainContext(
    "testnet", "wss://example.invalid", "fixture", "0x" + "1" * 64, 567
)
SNAPSHOT = MetagraphSnapshot(
    CONTEXT,
    10,
    "0x" + "2" * 64,
    NOW,
    (
        Participant(0, "5Burn", "5Owner", 0),
        Participant(1, "5CurrentWinner", "5MinerCold", 1),
        Participant(2, "5Validator", "5ValidatorCold", 2),
    ),
)
FRESH = {
    "authority": "SYNTHETIC_FIXTURE_ONLY",
    "max_feed_age_ms": 60_000,
    "max_block_lag": 2,
}


def sign_body(feed):
    body = {k: v for k, v in feed.items() if k != "signature"}
    return {**body, "signature": KEY.sign(FEED_DOMAIN + canonical(body).encode()).hex()}


def bound_feed(challenge=inc.BATTERY, *, winner=True, snapshot=SNAPSHOT):
    network = {
        "name": snapshot.context.network,
        "netuid": snapshot.context.netuid,
        "genesis_hash": snapshot.context.genesis_hash,
    }
    return sign_body(
        {
            "schema": FEED_SCHEMA,
            "labels": ["DEVELOPMENT"]
            + (["TESTNET"] if snapshot.context.network == "testnet" else []),
            "validator": {"hotkey": "5Validator", "feed_key": PUBLIC_KEY},
            "challenge": {
                "id": challenge,
                "version": "fixture-v1",
                "rule_digest": "sha256:" + "a" * 64,
            },
            "network": network,
            "as_of_block": {
                "number": snapshot.finalized_block,
                "hash": snapshot.block_hash,
                "timestamp_ms": snapshot.timestamp_ms,
            },
            "generated_at": datetime.fromtimestamp(
                snapshot.timestamp_ms / 1000, UTC
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": 2,
            "leaderboard": {"incumbent": None, "standing": []},
            "king": (
                {
                    "hotkey": "5CurrentWinner",
                    "submission_id": "fixture-model",
                    "eligible": True,
                    "crowned_utc_ms": NOW - 1000,
                    "policy_digest": POLICY.digest,
                    "uid": 1,
                    "coldkey": "5MinerCold",
                }
                if winner
                else None
            ),
            "winner_observation": {
                "schema": "carbon.validator.winner-observation.v1",
                "source": "WINNER_LEDGER_AND_LIVE_DEPLOYMENT",
                "state": "CURRENT" if winner else "NO_PAYABLE_WINNER",
                "policy_digest": POLICY.digest,
            },
        }
    )


def config(root, *, all_challenges=True):
    first = bound_feed()["challenge"]
    return {
        "schema": inc.SCHEMA,
        "validator_hotkey": "5Validator",
        "intake_url": "https://example.invalid",
        "feed_key": PUBLIC_KEY,
        "policy": POLICY.version,
        "challenge": first,
        "network": bound_feed()["network"],
        "chain_endpoint": CONTEXT.endpoint,
        "cursor": str(root / "observer.jsonl"),
        "additional_challenges": (
            [{**first, "id": c} for c in POLICY.challenges[1:]]
            if all_challenges
            else []
        ),
    }


def reading(snapshot=SNAPSHOT, *, row=((0, 43690), (1, 21845))):
    return obs.WeightObservation(
        snapshot,
        row,
        (43690, 21845, 0),
        publication={
            "number": snapshot.finalized_block,
            "hash": snapshot.block_hash,
            "timestamp_ms": snapshot.timestamp_ms,
        },
    )


def scope():
    return {
        "challenge": bound_feed()["challenge"],
        "network": bound_feed()["network"],
        "validator_hotkey": "5Validator",
        "feed_key": PUBLIC_KEY,
        "policy_digest": POLICY.digest,
    }


def validate(feed, *, view=None, now=NOW):
    return obs.validate_feed(
        feed, scope(), reading() if view is None else view, now_ms=now, freshness=FRESH
    )


def test_real_signature_context_and_current_king_are_bound():
    value = validate(bound_feed())
    assert value["winner"]["hotkey"] == "5CurrentWinner"
    assert value["registration"] == {
        "uid": 1,
        "coldkey": "5MinerCold",
        "registered_at": 1,
    }
    assert value["block"]["hash"] == SNAPSHOT.block_hash


@pytest.mark.parametrize(
    "path,value,code",
    [
        (("schema",), "wrong", "feed_schema_mismatch"),
        (("validator", "hotkey"), "5OtherValidator", "feed_validator_mismatch"),
        (("challenge", "id"), "other", "feed_challenge_mismatch"),
        (("challenge", "rule_digest"), "sha256:" + "b" * 64, "feed_challenge_mismatch"),
        (("challenge", "version"), "old", "feed_challenge_mismatch"),
        (("network", "name"), "finney", "feed_network_mismatch"),
        (("network", "netuid"), 568, "feed_network_mismatch"),
        (("network", "genesis_hash"), "0x" + "3" * 64, "feed_network_mismatch"),
        (("as_of_block", "hash"), "0x" + "3" * 64, "feed_finalized_anchor_conflict"),
        (("as_of_block", "number"), 11, "feed_block_stale_or_future"),
        (("as_of_block", "number"), 7, "feed_block_stale_or_future"),
        (("version",), True, "feed_version_malformed"),
        (("king", "policy_digest"), None, "winner_policy_unbound"),
        (("king", "uid"), 2, "winner_registration_drift"),
        (("king", "coldkey"), "5Different", "winner_registration_drift"),
        (("king", "eligible"), False, "winner_not_payable"),
        (
            ("winner_observation", "state"),
            "UNAVAILABLE",
            "winner_ledger_observation_missing",
        ),
        (
            ("winner_observation", "policy_digest"),
            "sha256:" + "b" * 64,
            "winner_policy_unbound",
        ),
        (("winner_observation", "schema"), "old", "winner_ledger_observation_missing"),
    ],
)
def test_signed_wrong_context_identity_or_source_never_passes(path, value, code):
    feed = bound_feed()
    target = feed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(obs.Unverified, match=code):
        validate(sign_body(feed))


def test_signature_is_not_mocked_and_marker_payload_is_not_reported():
    feed = bound_feed()
    marker = "synthetic-untrusted-provider-marker"
    feed["untrusted_payload"] = marker
    feed["signature"] = "00" * 64
    with pytest.raises(obs.Unverified, match="feed_signature_invalid") as caught:
        validate(feed)
    assert str(caught.value) == "feed_signature_invalid"
    assert marker not in str(caught.value)


@pytest.mark.parametrize("offset", [-1, 60_001])
def test_future_or_stale_observation_is_unverified(offset):
    with pytest.raises(obs.Unverified, match="time_stale_or_future"):
        validate(bound_feed(), now=NOW + offset)


def test_owner_freshness_gap_prevents_network_or_fixture_read(tmp_path):
    assert obs.FRESHNESS == {
        "authority": "HUMAN_INPUT",
        "max_feed_age_ms": None,
        "max_block_lag": None,
    }

    def never(*_args, **_kwargs):
        raise AssertionError("missing owner input dispatched a reader")

    result = inc.check(
        config(tmp_path), context=CONTEXT, feed_reader=never, weights_reader=never
    )
    assert result == {
        "state": inc.UNVERIFIED,
        "findings": [{"code": "feed_freshness_human_input"}],
    }


def current_check(configured, monkeypatch, *, snapshot=SNAPSHOT, feeds=None, row=None):
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)
    feeds = feeds or {
        c: bound_feed(c, winner=c == inc.BATTERY, snapshot=snapshot)
        for c in POLICY.challenges
    }

    async def weights(context, validator, *, feed_block):
        assert context == snapshot.context and validator == "5Validator"
        assert len(feed_block) == len(configured["additional_challenges"]) + 1
        return reading(snapshot, row=((0, 43690), (1, 21845)) if row is None else row)

    return inc.check(
        configured,
        context=snapshot.context,
        feed_reader=lambda url, key, c: feeds[c],
        weights_reader=weights,
        clock=lambda: snapshot.timestamp_ms / 1000,
    )


def test_full_check_uses_live_king_complete_registered_vector_and_labels_limits(
    tmp_path, monkeypatch
):
    result = current_check(config(tmp_path), monkeypatch)
    assert result["state"] == inc.PASS, result
    assert (
        result["observation"]["challenges"][inc.BATTERY]["winner"]["hotkey"]
        == "5CurrentWinner"
    )
    assert result["observation"]["source"] == "INJECTED_TEST_READERS"
    assert (
        result["observation"]["payment_claim"]
        == "INCENTIVE_ONLY_NOT_ALPHA_RECEIPT_OR_SETTLEMENT"
    )
    assert len((tmp_path / "observer.jsonl").read_bytes().splitlines()) == 1
    assert current_check(config(tmp_path), monkeypatch)["state"] == inc.PASS
    assert len((tmp_path / "observer.jsonl").read_bytes().splitlines()) == 1


def test_missing_challenge_source_does_not_mean_no_winner_or_all_burn(
    tmp_path, monkeypatch
):
    result = current_check(config(tmp_path, all_challenges=False), monkeypatch)
    assert result["state"] == inc.UNVERIFIED, result
    assert result["findings"][0]["code"] == "challenge_observations_incomplete"
    assert result["observation"]["coverage"] == "PARTIAL_UNVERIFIED"


def test_null_king_without_explicit_bound_none_state_is_unverified():
    feed = bound_feed(winner=False)
    feed.pop("winner_observation")
    with pytest.raises(obs.Unverified, match="winner_ledger_observation_missing"):
        validate(sign_body(feed))
    assert validate(bound_feed(winner=False))["winner"] is None


def test_equal_version_newer_finalized_block_is_allowed_and_watermark_advances(
    tmp_path, monkeypatch
):
    configured = config(tmp_path)
    assert current_check(configured, monkeypatch)["state"] == inc.PASS
    later = replace(
        SNAPSHOT,
        finalized_block=11,
        block_hash="0x" + "3" * 64,
        timestamp_ms=NOW + 1000,
    )
    assert current_check(configured, monkeypatch, snapshot=later)["state"] == inc.PASS
    assert len((tmp_path / "observer.jsonl").read_bytes().splitlines()) == 2
    result = current_check(configured, monkeypatch)
    assert (
        result["state"] == inc.UNVERIFIED
        and result["findings"][0]["code"] == "feed_observation_rollback"
    )


@pytest.mark.parametrize(
    "defect,code",
    [
        ("version", "feed_observation_rollback"),
        ("hash", "feed_block_conflict"),
        ("winner", "feed_version_winner_conflict"),
        ("registration", "winner_registration_changed_since_observation"),
    ],
)
def test_cursor_rejects_rollback_conflicts_and_recycled_holder(tmp_path, defect, code):
    path = tmp_path / "cursor.jsonl"
    first = validate(bound_feed())
    obs.record_observation(path, scope(), first)
    before = path.read_bytes()
    next_value = deepcopy(first)
    if defect == "version":
        next_value["feed_version"] = 1
    elif defect == "hash":
        next_value["block"]["hash"] = "0x" + "3" * 64
    elif defect == "winner":
        next_value["winner"]["submission_id"] = "other-model"
    else:
        next_value["feed_version"] = 3
        next_value["registration"]["registered_at"] = 2
    with pytest.raises(obs.Unverified, match=code):
        obs.record_observation(path, scope(), next_value)
    assert path.read_bytes() == before


def test_foreign_cursor_and_corrupt_middle_history_refuse(tmp_path):
    path = tmp_path / "cursor.jsonl"
    value = validate(bound_feed())
    obs.record_observation(path, scope(), value)
    with pytest.raises(obs.Unverified, match="scope_mismatch"):
        obs.record_observation(path, {**scope(), "validator_hotkey": "5Other"}, value)
    with path.open("ab") as stream:
        stream.write(b'{"scope":"wrong","observations":{}}\n')
    with pytest.raises(obs.Unverified, match="scope_mismatch"):
        obs.record_observation(path, scope(), value)


def test_existing_empty_or_permissive_cursor_cannot_be_adopted(tmp_path):
    path = tmp_path / "unknown-empty.jsonl"
    path.write_bytes(b"")
    path.chmod(0o600)
    with pytest.raises(obs.Unverified, match="cursor_unavailable"):
        obs.record_observation(path, scope(), validate(bound_feed()))
    path.chmod(0o644)
    with pytest.raises(obs.Unverified, match="not_owner_only"):
        obs.record_observation(path, scope(), validate(bound_feed()))


def test_duplicate_signed_document_fields_refuse_without_last_value_fallback():
    body = json.dumps(bound_feed())
    duplicate = body.replace(
        '"schema": "carbon.validator.score-feed.v1"',
        '"schema":"wrong","schema":"carbon.validator.score-feed.v1"',
        1,
    )
    assert duplicate != body
    with pytest.raises(inc.Unverified, match="feed_unavailable"):
        inc.read_feed(
            "https://example.invalid",
            PUBLIC_KEY,
            opener=lambda *a, **k: io.BytesIO(duplicate.encode()),
        )


def test_provider_failure_does_not_echo_marker_and_the_reader_really_executes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)
    marker = "synthetic-private-provider-error-marker"
    called = []

    async def failed(*_args, **_kwargs):
        called.append(True)
        raise RuntimeError(marker)

    result = inc.check(
        config(tmp_path),
        context=CONTEXT,
        weights_reader=failed,
        feed_reader=lambda url, key, c: bound_feed(c, winner=c == inc.BATTERY),
        clock=lambda: NOW / 1000,
    )
    assert called == [True]
    assert result == {
        "state": inc.UNVERIFIED,
        "findings": [{"code": "read_failed", "type": "RuntimeError"}],
    }
    assert marker not in json.dumps(result)


@pytest.mark.parametrize("version", ["absent-mainnet-policy", "unregistered-policy"])
def test_unregistered_policy_cannot_use_testnet_or_fixture_fallback(tmp_path, version):
    configured = {**config(tmp_path), "policy": version}
    result = inc.check(configured, context=CONTEXT)
    assert result == {
        "state": inc.UNVERIFIED,
        "findings": [{"code": "weight_policy_unavailable"}],
    }


def test_legacy_config_and_scalar_readers_do_not_certify_current_observation(
    tmp_path, monkeypatch
):
    configured = config(tmp_path)
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)
    old = {**configured, "schema": "carbon.incentive-canary.config.v1"}
    assert inc.check(old, context=CONTEXT)["findings"] == [
        {"code": "observer_config_upgrade_required"}
    ]
    assert inc.check(
        configured, context=CONTEXT, incumbent_reader=lambda *_: "5CurrentWinner"
    )["findings"] == [{"code": "legacy_reader_unbound"}]


def test_same_guards_apply_to_a_synthetic_mainnet_policy_without_authorizing_it(
    tmp_path, monkeypatch
):
    import carbon.rewards.winner_decay as decay

    fixture_policy = replace(
        POLICY,
        version="fixture-finney",
        network="finney",
        netuid=42,
        authority=decay.MAINNET_AUTHORITY,
    )
    fixture_context = replace(CONTEXT, network="finney", netuid=42)
    snapshot = replace(SNAPSHOT, context=fixture_context)
    configured = config(tmp_path)
    configured["policy"] = fixture_policy.version
    configured["network"] = {**configured["network"], "name": "finney", "netuid": 42}
    monkeypatch.setattr(decay, "load_policy", lambda version: fixture_policy)
    result = current_check(configured, monkeypatch, snapshot=snapshot)
    assert (
        result["state"] == inc.PASS
        and result["observation"]["source"] == "INJECTED_TEST_READERS"
    )
    wrong = replace(snapshot, context=CONTEXT)
    result = current_check(configured, monkeypatch, snapshot=wrong)
    assert (
        result["state"] == inc.UNVERIFIED
        and result["findings"][0]["code"] == "chain_context_mismatch"
    )


def test_unknown_publication_epoch_is_unverified_and_readback_is_still_labelled(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)

    async def weights(*_args, **_kwargs):
        return obs.WeightObservation(
            SNAPSHOT, ((0, 43690), (1, 21845)), (43690, 21845, 0)
        )

    result = inc.check(
        config(tmp_path),
        context=CONTEXT,
        weights_reader=weights,
        feed_reader=lambda url, key, c: bound_feed(c, winner=c == inc.BATTERY),
        clock=lambda: NOW / 1000,
    )
    assert result["state"] == inc.UNVERIFIED, result
    assert result["findings"][0]["code"] == "publication_epoch_context_unavailable"
    assert result["observation"]["publication"] is None


def test_row_from_before_takeover_stays_unverified_not_false_payment_blocker(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)

    async def weights(*_args, **_kwargs):
        return obs.WeightObservation(
            SNAPSHOT,
            ((0, 65535),),
            (65535, 0, 0),
            publication={
                "number": 8,
                "hash": "0x" + "8" * 64,
                "timestamp_ms": NOW - 2000,
            },
        )

    result = inc.check(
        config(tmp_path),
        context=CONTEXT,
        weights_reader=weights,
        feed_reader=lambda url, key, c: bound_feed(c, winner=c == inc.BATTERY),
        clock=lambda: NOW / 1000,
    )
    assert result["state"] == inc.UNVERIFIED, result
    assert result["findings"][0]["code"] == "winner_clock_after_publication"


def test_current_vector_drift_with_publication_context_is_attention_not_payment_failure(
    tmp_path, monkeypatch
):
    result = current_check(config(tmp_path), monkeypatch, row=((0, 65535),))
    assert result["state"] == inc.ATTENTION, result
    assert any(
        f["code"] == "observed_row_not_current_target" for f in result["findings"]
    )
    assert not any(f["level"] == inc.BLOCKER for f in result["findings"])


def test_sybil_pair_winning_distinct_challenges_is_not_false_primary_split(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)
    monkeypatch.setattr(
        inc,
        "_sybil_scenarios",
        lambda: {"fixture-sybil": {"of": "5CurrentWinner", "hotkey": "5Other"}},
    )
    snapshot = replace(
        SNAPSHOT,
        participants=(
            *SNAPSHOT.participants,
            Participant(3, "5Other", "5OtherCold", 3),
        ),
    )
    configured = {**config(tmp_path), "sybil": "fixture-sybil"}
    feeds = {
        c: bound_feed(c, winner=c != POLICY.challenges[2], snapshot=snapshot)
        for c in POLICY.challenges
    }
    second = feeds[POLICY.challenges[1]]
    second["king"].update(hotkey="5Other", uid=3, coldkey="5OtherCold")
    feeds[POLICY.challenges[1]] = sign_body(second)

    async def weights(*_args, **_kwargs):
        return obs.WeightObservation(
            snapshot,
            ((0, 65535), (1, 65535), (3, 65535)),
            (21845, 21845, 0, 21845),
            publication={
                "number": snapshot.finalized_block,
                "hash": snapshot.block_hash,
                "timestamp_ms": snapshot.timestamp_ms,
            },
        )

    result = inc.check(
        configured,
        context=CONTEXT,
        weights_reader=weights,
        feed_reader=lambda url, key, c: feeds[c],
        clock=lambda: NOW / 1000,
    )
    assert result["state"] == inc.UNVERIFIED, result
    assert any(
        f["code"] == "sybil_row_not_challenge_specific" for f in result["findings"]
    )
    assert not any(f["code"] == "sybil_split" for f in result["findings"])
    assert "shares" not in result
    assert inc.summarize([result], 1 / 3)["observed"] is None
