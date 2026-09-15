"""Read-only, secret-free C-W1-D1 operator preflight."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

from carbon.chain import MetagraphSnapshot, Participant
from carbon.chain.publication import RuntimeCapabilities
from carbon.development_testnet.operator import (
    DEFAULT_ENDPOINT,
    TESTNET_GENESIS,
    doctor,
    load_config,
    main,
)

DIGEST = "sha256:" + "1" * 64
HOTKEY = "5E48fhGnyi4C94bsAc64s2bgshyJb7bfP59pRbidghc1pAyQ"
COLDKEY = "5CmGx8PFzfL7EvrvqFgV2Sv2HGok53YkGUsBw1atTD5hw7N8"


def document(*, netuid=None, authorization=None):
    return {
        "schema": "carbon.development-testnet.operator.v1",
        "profile_id": "carbon.public-synthetic-testnet.development.v1",
        "stage": "PUBLIC_TESTNET_DEVELOPMENT",
        "context": {
            "network": "testnet",
            "endpoint": DEFAULT_ENDPOINT,
            "chain_id": "bittensor-official-test",
            "genesis_hash": TESTNET_GENESIS,
            "netuid": netuid,
        },
        "expected_runtime_spec": 458,
        "publisher": {"hotkey": HOTKEY, "coldkey": COLDKEY},
        "wallet": {"name": "miner1", "hotkey_name": "default"},
        "execution": {
            "worker_profile": "carbon.c03.linux-x86_64-cpu.development.v1",
            "worker_image_digest": DIGEST,
            "resource_policy_digest": DIGEST,
        },
        "retention": {
            "root": "evidence",
            "export_root": "export",
            "max_retained_bytes": 1024,
            "host_loss_recoverable": False,
        },
        "transaction_authorization": authorization,
    }


def write(tmp_path: Path, value):
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_shipped_example_is_valid_and_deliberately_not_transaction_ready(capsys):
    path = (
        Path(__file__).parents[2]
        / "docs/development/CW1_DEVELOPMENT_TESTNET_OPERATOR.example.json"
    ).absolute()
    config = load_config(path)
    assert config.netuid is None
    assert config.transaction_authorization is None
    assert main(["validate", "--config", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["configuration"] == "VALID_WITH_MISSING_EXTERNAL_INPUTS"
    assert report["wallet_or_secret_read"] is False
    assert report["writes_performed"] is False


def test_draft_doctor_reports_host_facts_without_chain_or_wallet_access(tmp_path):
    config = load_config(write(tmp_path, document()))
    report = asyncio.run(doctor(config, online=False))
    assert report["chain"]["checked"] is False
    assert report["missing_external_inputs"] == [
        "context.netuid",
        "transaction_authorization",
    ]
    assert report["transaction_ready"] is False
    assert report["writes_performed"] is False
    assert report["protected_or_official_eligible"] is False


def test_exact_authorization_and_observed_runtime_enable_only_readiness(
    tmp_path, monkeypatch
):
    authorization = {
        "authorization_id": "owner-testnet-demo-1",
        "authority_record_digest": DIGEST,
        "publisher_hotkey": HOTKEY,
        "expected_runtime_spec": 458,
        "valid_from_block": 100,
        "valid_through_block": 120,
    }
    config = load_config(
        write(tmp_path, document(netuid=77, authorization=authorization))
    )
    context = config.context
    snapshot = MetagraphSnapshot(
        context,
        101,
        "0x" + "2" * 64,
        1,
        (
            Participant(0, "owner-hotkey", "owner-coldkey", 1),
            Participant(1, HOTKEY, COLDKEY, 2),
        ),
    )
    capabilities = RuntimeCapabilities(
        snapshot.snapshot_id,
        458,
        1,
        2,
        "Burn",
        "owner-coldkey",
        "owner-hotkey",
        ("owner-hotkey",),
        1,
        65535,
        0,
        0,
        0,
        False,
        True,
        True,
    )

    class Backend:
        def __init__(self, *args, **kwargs):
            pass

        async def observe(self):
            return snapshot, replace(capabilities)

        async def close(self):
            pass

    monkeypatch.setattr(
        "carbon.development_testnet.operator.BittensorPublicationBackend", Backend
    )
    monkeypatch.setattr(
        "carbon.development_testnet.operator.version", lambda name: "11.1.0"
    )
    report = asyncio.run(doctor(config, online=True))
    assert report["chain"]["checked"] is True
    assert report["chain"]["uid"] == 1
    assert report["transaction_ready"] is True
    assert report["writes_performed"] is False


def test_main_fails_closed_without_echoing_invalid_input(tmp_path, capsys):
    path = write(tmp_path, {"secret": "do-not-echo"})
    assert main(["doctor", "--config", str(path)]) == 2
    assert "do-not-echo" not in capsys.readouterr().out
