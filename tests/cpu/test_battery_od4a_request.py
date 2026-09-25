"""The OD-4a request: one exact, digest-bound all-burn publication to approve.

Offline: the probe report and operator config are fixtures; the intent is
signed with a fresh service key. Nothing here dispatches or opens a wallet.
"""

from __future__ import annotations

import copy
import json

import pytest

from carbon.battery import od4a, signing
from carbon.development_testnet.operator import TESTNET_GENESIS

OPERATOR = {
    "context": {
        "network": "testnet",
        "endpoint": "wss://test.finney.opentensor.ai:443",
        "chain_id": "bittensor-official-test",
        "genesis_hash": TESTNET_GENESIS,
        "netuid": 567,
    },
    "publisher": {"hotkey": "5PublisherHotkeyPublicAddressOnly"},
}
PROBE = {
    "status": "COMPATIBLE_USED_SURFACE",
    "spec_version": 471,
    "surface_digest": "sha256:" + "ab" * 32,
    "context": {
        "genesis_hash": TESTNET_GENESIS,
        "finalized_block": 1_000_000,
        "finalized_hash": "0x" + "cd" * 32,
    },
}


@pytest.fixture
def intent(tmp_path):
    key = signing.ServiceKey.create(tmp_path / "service.key")
    return key.sign(
        "weight_intent", signing.all_burn_intent(pool_version=2, reason="phase A")
    )


def build(intent, **overrides):
    arguments = {
        "operator": OPERATOR,
        "probe": PROBE,
        "intent": intent,
        "sequence": 1,
        "start_after": 20,
        "window": 600,
        "expires_utc": "2026-10-02T00:00:00Z",
        **overrides,
    }
    return od4a.build_request(**arguments)


def test_the_request_is_exactly_one_all_burn_publication(intent):
    request = build(intent)
    assert request["authorization_id"] == "OD4A-BATTERY-0001"
    assert request["weights"] == {"mode": "ALL_BURN", "rows": [[0, 65535]]}
    assert request["publisher"]["uid"] == 0
    assert (request["valid_from_block"], request["valid_through_block"]) == (
        1_000_020,
        1_000_619,
    )
    assert request["max_dispatches"] == 1
    assert request["max_fee_tao"] == 0 and request["max_spend_tao"] == 0
    assert request["expected_runtime_spec"] == 471
    assert request["authorizes_dispatch"] is False
    fragment = request["operator_config_fragment"]["transaction_authorization"]
    assert fragment["authority_record_digest"].startswith("HUMAN_INPUT")
    assert request["request_digest"] in fragment["authority_record_digest"]
    # The digest binds every field: the same inputs give the same digest.
    assert build(intent)["request_digest"] == request["request_digest"]
    assert build(intent, window=601)["request_digest"] != request["request_digest"]


def test_nothing_else_is_prepared(intent):
    winner = copy.deepcopy(intent)
    winner["payload"]["winner_weights"] = True
    incompatible = {**PROBE, "status": "INCOMPATIBLE"}
    other_chain = {**PROBE, "context": {**PROBE["context"], "genesis_hash": "0x00"}}
    mainnet = {**OPERATOR, "context": {**OPERATOR["context"], "network": "finney"}}
    for overrides in (
        {"intent": winner},  # tampered: the signature no longer verifies
        {"probe": incompatible},
        {"probe": other_chain},
        {"operator": mainnet},
        {"window": 0},
        {"start_after": -5},
        {"expires_utc": "next week"},
    ):
        with pytest.raises(od4a.RequestRefused):
            build(**{"intent": intent, **overrides})


def test_the_cli_prints_the_request_and_refuses_by_name(tmp_path, intent, capsys):
    files = {}
    for name, value in (("op", OPERATOR), ("probe", PROBE), ("intent", intent)):
        files[name] = tmp_path / (name + ".json")
        files[name].write_text(json.dumps(value))
    arguments = [
        "request",
        "--operator-config", str(files["op"]),
        "--probe", str(files["probe"]),
        "--intent", str(files["intent"]),
        "--sequence", "2",
        "--start-after", "20",
        "--window", "600",
        "--expires-utc", "2026-10-02T00:00:00Z",
    ]  # fmt: skip
    assert od4a.main(arguments) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["authorization_id"] == "OD4A-BATTERY-0002"
    files["probe"].write_text(json.dumps({**PROBE, "status": "INCOMPATIBLE"}))
    assert od4a.main(arguments) == 2
    assert "refused" in json.loads(capsys.readouterr().out)
