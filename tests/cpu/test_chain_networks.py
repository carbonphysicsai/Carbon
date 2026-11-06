"""F4: the network binding (testnet 567 / finney 116), one exact row per network, fail closed (Chain Auditor 5 Nov).

Real code throughout: `carbon.chain.networks`, the operator profile's `load_config`, and `validator_setup`'s weights
config and runtime read. No network and no wallet.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from carbon.chain import networks
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK


def test_the_default_row_is_the_testnet_constants_byte_for_byte():
    assert networks.DEFAULT is networks.NETWORKS[CARBON_NETWORK]
    assert (networks.DEFAULT.network, networks.DEFAULT.netuid) == ("testnet", 567)
    assert (CARBON_NETWORK, CARBON_NETUID) == ("testnet", 567)


def test_the_two_rows_are_the_public_reads():
    testnet, finney = networks.NETWORKS["testnet"], networks.NETWORKS["finney"]
    assert (testnet.netuid, finney.netuid) == (567, 116)
    assert testnet.genesis_hash == networks.TESTNET_GENESIS
    assert finney.genesis_hash == (
        "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"
    )
    assert set(networks.NETWORKS) == {"testnet", "finney"}


def test_each_rows_stage_is_the_winner_publications_own():
    from carbon.rewards.testnet_winner_publication import STAGES

    for name, bound in networks.NETWORKS.items():
        assert bound.stage == STAGES[name][1]


def test_the_operator_profiles_testnet_names_are_the_rows():
    from carbon.development_testnet import operator

    assert operator.STAGE == networks.NETWORKS["testnet"].stage
    assert operator.DEFAULT_ENDPOINT == networks.NETWORKS["testnet"].endpoints[0]
    assert operator.TESTNET_GENESIS == networks.TESTNET_GENESIS


@pytest.mark.parametrize(
    "fields,code",
    [
        ({"network": "mainnet"}, "network_unregistered"),
        ({"network": "localnet"}, "network_unregistered"),
        ({"network": None}, "network_unregistered"),
        (
            {"network": "finney", "genesis_hash": networks.TESTNET_GENESIS},
            "network_genesis_differs",
        ),
        (
            {"network": "testnet", "genesis_hash": networks.FINNEY_GENESIS},
            "network_genesis_differs",
        ),
        ({"network": "finney", "netuid": 567}, "network_netuid_differs"),
        ({"network": "testnet", "netuid": 116}, "network_netuid_differs"),
        ({"network": "finney", "netuid": True}, "network_netuid_differs"),
        (
            {"network": "finney", "chain_id": "bittensor-official-test"},
            "network_chain_id_differs",
        ),
        (
            {"network": "finney", "endpoint": "wss://test.finney.opentensor.ai:443"},
            "network_endpoint_unregistered",
        ),
        (
            {"network": "testnet", "endpoint": "wss://10.0.0.5:9944"},
            "network_endpoint_unregistered",
        ),
        (
            {"network": "testnet", "endpoint": "ws://127.0.0.1"},
            "network_endpoint_unregistered",
        ),
        (
            {"network": "finney", "endpoint": "ws://user:pw@127.0.0.1:9944"},
            "network_endpoint_unregistered",
        ),
    ],
)
def test_a_mixed_or_unknown_context_is_refused_by_name(fields, code):
    with pytest.raises(networks.NetworkRefused) as refused:
        networks.check_context(**fields)
    assert refused.value.code == code


@pytest.mark.parametrize("name", ["testnet", "finney"])
def test_each_row_accepts_exactly_itself_and_its_own_node(name):
    bound = networks.NETWORKS[name]
    for endpoint in (*bound.endpoints, "ws://127.0.0.1:9944", "ws://localhost:9945"):
        assert (
            networks.check_context(
                network=name,
                chain_id=bound.chain_id,
                genesis_hash=bound.genesis_hash,
                netuid=bound.netuid,
                endpoint=endpoint,
            )
            is bound
        )
    networks.check_genesis_at_connect(bound, bound.genesis_hash)
    other = networks.NETWORKS[{"testnet": "finney", "finney": "testnet"}[name]]
    with pytest.raises(networks.NetworkRefused, match="mismatch_at_connect"):
        networks.check_genesis_at_connect(bound, other.genesis_hash)
    assert networks.row_of_netuid(bound.netuid) is bound


def test_an_unregistered_netuid_has_no_row():
    for netuid in (0, 77, 568, "116", None):
        with pytest.raises(networks.NetworkRefused, match="netuid_unregistered"):
            networks.row_of_netuid(netuid)


# --- the operator profile's config (`development_testnet.operator.load_config`) -------------------------------------


def _document(network, *, netuid=None, authorization=None, **context):
    from test_cw1_development_testnet_operator import document

    raw = document(netuid=netuid, authorization=authorization)
    bound = networks.NETWORKS[network]
    raw["stage"] = bound.stage
    raw["context"].update(
        network=network,
        endpoint=bound.endpoints[0],
        chain_id=bound.chain_id,
        genesis_hash=bound.genesis_hash,
    )
    raw["context"].update(context)
    return raw


def _load(tmp_path, raw):
    from carbon.development_testnet.operator import load_config

    path = tmp_path / "operator.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_config(path)


def _refused(tmp_path, raw):
    from carbon.development_testnet.model import DevelopmentTestnetFailure

    with pytest.raises(DevelopmentTestnetFailure) as refused:
        _load(tmp_path, raw)
    return str(refused.value)


def test_a_finney_operator_config_binds_116_and_its_context_names_finney(tmp_path):
    config = _load(tmp_path, _document("finney", netuid=116))
    assert config.network == "finney"
    assert (config.context.network, config.context.netuid) == ("finney", 116)
    assert config.context.genesis_hash == networks.FINNEY_GENESIS
    own = _load(
        tmp_path, _document("finney", netuid=116, endpoint="ws://127.0.0.1:9944")
    )
    assert own.endpoint == "ws://127.0.0.1:9944"
    assert _load(tmp_path, _document("finney")).context is None  # netuid not set yet


def test_the_testnet_operator_config_is_unchanged(tmp_path):
    config = _load(tmp_path, _document("testnet", netuid=77))
    assert config.network == "testnet"
    assert (config.context.network, config.context.netuid) == ("testnet", 77)


@pytest.mark.parametrize(
    "network,change,code",
    [
        ("finney", {"netuid": 567}, "INVALID_OPERATOR_CONFIG"),
        (
            "finney",
            {"genesis_hash": networks.TESTNET_GENESIS},
            "NETWORK_GENESIS_DIFFERS",
        ),
        (
            "testnet",
            {"genesis_hash": networks.FINNEY_GENESIS},
            "NETWORK_GENESIS_DIFFERS",
        ),
        (
            "finney",
            {"endpoint": "wss://test.finney.opentensor.ai:443"},
            "NETWORK_ENDPOINT_UNREGISTERED",
        ),
        ("finney", {"chain_id": "bittensor-official-test"}, "NETWORK_CHAIN_ID_DIFFERS"),
        ("testnet", {"network": "mainnet"}, "NETWORK_UNREGISTERED"),
    ],
)
def test_an_operator_config_outside_its_row_is_refused(tmp_path, network, change, code):
    raw = _document(network, netuid=116 if network == "finney" else 77)
    raw["context"].update(change)
    assert code in _refused(tmp_path, raw)


def test_an_operator_config_with_the_other_rows_stage_is_refused(tmp_path):
    raw = _document("finney", netuid=116)
    raw["stage"] = networks.NETWORKS["testnet"].stage
    assert "INVALID_OPERATOR_CONFIG" in _refused(tmp_path, raw)


def test_the_development_authorization_stays_testnet_only(tmp_path):
    raw = _document("finney", netuid=116, authorization={"authorization_id": "x"})
    assert "DEVELOPMENT_AUTHORIZATION_TESTNET_ONLY" in _refused(tmp_path, raw)


def test_a_finney_operator_never_runs_the_development_online_check(
    tmp_path, monkeypatch
):
    from carbon.development_testnet import operator

    # host facts only (not the claim): the online branch is what is tested
    monkeypatch.setattr(operator, "_host_memory", lambda: 8 * 1024**3)
    monkeypatch.setattr(operator, "_docker", lambda: (True, True))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a finney config reached the development chain backend")

    monkeypatch.setattr(operator, "BittensorPublicationBackend", forbidden)
    config = _load(tmp_path, _document("finney", netuid=116))
    report = asyncio.run(operator.doctor(config, online=True))
    assert report["chain"]["reason"] == "ONLINE_CHECK_TESTNET_ONLY"
    assert report["chain"]["checked"] is False


# --- validator_setup: weights config and runtime read ---------------------------------------------------------------


def _weights(tmp_path, network, **context):
    from test_validator_setup_weights import config

    path, raw = config(tmp_path, network)
    raw["context"].update(context)
    path.write_text(json.dumps(raw), encoding="utf-8")
    path.chmod(0o600)
    return path


@pytest.mark.parametrize(
    "network,change",
    [
        ("finney", {"netuid": 567}),
        ("testnet", {"netuid": 116}),
        ("finney", {"genesis_hash": networks.TESTNET_GENESIS}),
        ("testnet", {"genesis_hash": networks.FINNEY_GENESIS}),
    ],
)
def test_validator_setup_refuses_a_mixed_weights_context(tmp_path, network, change):
    from carbon.validator_setup import weights
    from carbon.validator_setup.bundle import SetupRefused

    with pytest.raises(SetupRefused, match="OPERATOR_CONTEXT_OR_IDENTITY_REFUSED"):
        weights.load_config(_weights(tmp_path, network, **change))


@pytest.mark.parametrize(
    "network,genesis",
    [("finney", networks.TESTNET_GENESIS), ("testnet", networks.FINNEY_GENESIS)],
)
def test_validator_setup_runtime_read_refuses_the_other_chains_genesis(
    monkeypatch, network, genesis
):
    from carbon.chain import runtime_probe
    from carbon.validator_setup import runtime
    from carbon.validator_setup.bundle import SetupRefused

    async def forbidden(*_args):
        pytest.fail("must not query")

    monkeypatch.setattr(runtime_probe, "probe", forbidden)
    with pytest.raises(SetupRefused, match="EXPLICIT_RUNTIME_CONTEXT_REQUIRED"):
        asyncio.run(runtime.observe(network, "wss://fixture.invalid", genesis, 450))
