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


@pytest.mark.parametrize("refused", [False, True])
def test_preview_uses_private_mounted_journal_parent_and_cleans_on_failure(
    tmp_path, monkeypatch, refused
):
    import stat
    from pathlib import Path
    from types import SimpleNamespace

    from carbon.chain import sdk, sdk_weights
    from carbon.rewards import testnet_winner_publication as publication

    path, _raw = config(tmp_path)
    parent = tmp_path / "mounted-journals"
    parent.mkdir(mode=0o700)
    journal = parent / "existing.sqlite3"
    journal.write_bytes(b"existing-history-unchanged")
    scratch_paths = []

    def forbidden(*args, **kwargs):
        raise AssertionError("preview must not use default tmp or open a wallet")

    monkeypatch.setattr(weights.tempfile, "gettempdir", forbidden)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", forbidden)

    def issuer(_args, _config, preview_journal):
        directory = preview_journal.parent
        scratch_paths.append(directory)
        assert directory.parent == parent
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        preview_journal.write_bytes(b"synthetic-preview-only")
        if refused:
            raise ValueError("synthetic-issuer-refusal")
        return "fixture-issuer"

    class Reader:
        async def capture(self, _context):
            return "fixture-snapshot"

    monkeypatch.setattr(publication, "_issuer", issuer)
    monkeypatch.setattr(sdk, "BittensorReader", Reader)
    monkeypatch.setattr(
        publication, "preview", lambda issuer, snapshot: (issuer, snapshot)
    )
    args = SimpleNamespace(config=path, action="preview", journal=journal)
    if refused:
        with pytest.raises(ValueError, match="synthetic-issuer-refusal"):
            asyncio.run(weights.execute(args))
    else:
        assert asyncio.run(weights.execute(args)) == (
            "fixture-issuer",
            "fixture-snapshot",
        )
    assert len(scratch_paths) == 1
    assert not Path(scratch_paths[0]).exists()
    assert journal.read_bytes() == b"existing-history-unchanged"
    assert list(parent.iterdir()) == [journal]


@pytest.mark.parametrize("bad", ["missing", "public", "symlink", "file"])
def test_preview_refuses_unavailable_or_nonprivate_parent_before_issuer(
    tmp_path, monkeypatch, bad
):
    from types import SimpleNamespace
    from carbon.rewards import testnet_winner_publication as publication

    path, _raw = config(tmp_path)
    parent = tmp_path / "journal-parent"
    if bad == "public":
        parent.mkdir(mode=0o755)
    elif bad == "symlink":
        parent.symlink_to(tmp_path, target_is_directory=True)
    elif bad == "file":
        parent.write_bytes(b"not-a-directory")

    def forbidden(*args):
        raise AssertionError("invalid scratch parent must refuse before issuer")

    monkeypatch.setattr(publication, "_issuer", forbidden)
    args = SimpleNamespace(
        config=path, action="preview", journal=parent / "state.sqlite3"
    )
    with pytest.raises(
        SetupRefused, match="OWNER_ONLY_PREVIEW_JOURNAL_PARENT_REQUIRED"
    ):
        asyncio.run(weights.execute(args))
