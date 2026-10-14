"""Neutral configuration is not mainnet authorization; no live wallet/chain."""

import argparse
import asyncio
import json

import pytest

from carbon.validator_setup import weights
from carbon.validator_setup.bundle import SetupRefused


def config(tmp_path, network="testnet"):
    value = {
        "schema": weights.SCHEMA,
        "context": {
            "network": network,
            "endpoint": "wss://public-fixture.invalid",
            "chain_id": "fixture",
            "genesis_hash": "0x" + "a" * 64,
            "netuid": 567,
        },
        "expected_runtime_spec": 445,
        "publisher": {"hotkey": "fixture-publisher", "coldkey": "fixture-coldkey"},
        "wallet": {
            "name": "fixture-wallet",
            "hotkey_name": "fixture-hotkey",
            "path": str(tmp_path / "own-wallets"),
        },
    }
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)
    return path, value


@pytest.mark.parametrize("network", ["testnet", "finney"])
def test_exact_context_and_own_identity_are_parsed_without_wallet_or_chain(
    tmp_path, network
):
    path, raw = config(tmp_path, network)
    parsed = weights.load_config(path)
    assert parsed.context.network == network
    assert parsed.context.provider == raw["context"]["chain_id"]
    assert parsed.publisher_hotkey == "fixture-publisher"
    assert parsed.netuid == 567


@pytest.mark.parametrize("change", ["network", "genesis", "extra", "runtime", "mode"])
def test_wrong_context_extra_fields_runtime_and_public_config_refuse(tmp_path, change):
    path, raw = config(tmp_path)
    if change == "network":
        raw["context"]["network"] = "unsupported"
    elif change == "genesis":
        raw["context"]["genesis_hash"] = "synthetic-private-marker"
    elif change == "extra":
        raw["private_key"] = "synthetic-private-marker"
    elif change == "runtime":
        raw["expected_runtime_spec"] = True
    else:
        path.chmod(0o644)
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SetupRefused) as refused:
        weights.load_config(path)
    assert "synthetic-private-marker" not in str(refused.value)


@pytest.mark.parametrize("action", ["preview", "run"])
def test_missing_finney_policy_refuses_before_wallet_reader_or_private_source(
    tmp_path, monkeypatch, action
):
    from carbon.chain import sdk, sdk_weights
    from carbon.rewards.testnet_winner_publication import WinnerPublicationRefused

    path, _ = config(tmp_path, "finney")
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("external-or-private")
        raise AssertionError("not reached")

    monkeypatch.setattr(sdk, "BittensorReader", forbidden)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", forbidden)
    args = argparse.Namespace(
        config=path,
        action=action,
        policy_version=None,
        standing=tmp_path / "absent-standing",
        journal=tmp_path / "absent-journal",
        ledger=tmp_path / "absent-ledger",
        battery_deployment=tmp_path / "absent-private-deployment",
        repository=tmp_path,
    )
    with pytest.raises(WinnerPublicationRefused, match="POLICY_NOT_FOR_THIS_NETWORK"):
        asyncio.run(weights.execute(args))
    assert calls == []
    assert not (tmp_path / "absent-journal").exists()
    assert not (tmp_path / "absent-ledger").exists()


@pytest.mark.parametrize("explicit", [False, True])
def test_wallet_helper_preserves_old_callers_and_uses_explicit_owned_path(
    tmp_path, monkeypatch, explicit
):
    from types import SimpleNamespace

    import bittensor as bt

    from carbon.chain import sdk_weights

    calls = []

    def wallet(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            hotkey=SimpleNamespace(ss58_address="fixture-hotkey"),
            coldkeypub=SimpleNamespace(ss58_address="fixture-coldkey"),
        )

    monkeypatch.setattr(bt, "Wallet", wallet)
    options = {"wallet_path": tmp_path / "owned-wallets"} if explicit else {}
    sdk_weights.open_operator_wallet(
        "fixture-wallet", "fixture-key", "fixture-hotkey", "fixture-coldkey", **options
    )
    assert calls == [
        {
            "name": "fixture-wallet",
            "hotkey": "fixture-key",
            **({"path": str(tmp_path / "owned-wallets")} if explicit else {}),
        }
    ]
