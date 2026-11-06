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
    # this test process sets no CARBON_CHAIN_NETWORK: the binding is testnet, as before F4
    assert networks.BOUND is networks.DEFAULT is networks.NETWORKS["testnet"]
    assert (networks.DEFAULT.network, networks.DEFAULT.netuid) == ("testnet", 567)
    assert (CARBON_NETWORK, CARBON_NETUID) == ("testnet", 567)


_PROBE = """
import json
from carbon.chain import networks
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
from carbon.development_session.chain_onboarding import carbon_testnet_context
from carbon.development_session import miner_network
context = carbon_testnet_context()
print(json.dumps({
    "constants": [CARBON_NETWORK, CARBON_NETUID],
    "bound": networks.BOUND.network,
    "context": [context.network, context.endpoint, context.provider, context.genesis_hash, context.netuid],
    "miner_context": miner_network._context().netuid,
}))
"""


def _bound(value):
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {k: v for k, v in os.environ.items() if k != "CARBON_CHAIN_NETWORK"}
    if value is not None:
        env["CARBON_CHAIN_NETWORK"] = value
    root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = str(root)
    return subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        check=False,
        text=True,
        env=env,
        cwd=root,
        timeout=120,
    )


@pytest.mark.parametrize("value", [None, "", "testnet"])
def test_an_unset_or_testnet_binding_is_testnet_567(value):
    done = _bound(value)
    assert done.returncode == 0, done.stderr[-400:]
    out = json.loads(done.stdout)
    testnet = networks.NETWORKS["testnet"]
    assert out["constants"] == ["testnet", 567]
    assert out["context"] == [
        "testnet",
        testnet.endpoints[0],
        testnet.chain_id,
        testnet.genesis_hash,
        567,
    ]
    assert out["miner_context"] == 567


def test_a_finney_binding_moves_every_guard_and_the_context_together():
    done = _bound("finney")
    assert done.returncode == 0, done.stderr[-400:]
    out = json.loads(done.stdout)
    finney = networks.NETWORKS["finney"]
    assert out["constants"] == ["finney", 116]
    assert out["bound"] == "finney"
    assert out["context"] == [
        "finney",
        finney.endpoints[0],
        finney.chain_id,
        finney.genesis_hash,
        116,
    ]
    assert out["miner_context"] == 116


@pytest.mark.parametrize("value", ["mainnet", "Finney", "Localnet", "567"])
def test_an_unregistered_binding_refuses_at_import(value):
    done = _bound(value)
    assert done.returncode != 0
    assert "CARBON_CHAIN_NETWORK names no registered network" in done.stderr


def test_the_commitment_cli_stays_testnet_only_under_a_finney_binding():
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "CARBON_CHAIN_NETWORK": "finney", "PYTHONPATH": str(root)}
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.chain.commitment_poster",
            "--hotkey",
            "x",
            "--digest",
            "y",
            "--plan",
        ],
        capture_output=True,
        check=False,
        text=True,
        env=env,
        cwd=root,
        timeout=120,
    )
    assert done.returncode == 2
    assert "testnet only (D5)" in done.stderr


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


# --- H8 part 3: the STAGING-only localnet row (owner-accepted 6 Nov via the Lead; Validator-2 09:22) ------------------

LOCAL_GENESIS = "0x" + "4c" * 32
LOCAL_ENDPOINT = "ws://127.0.0.1:19944"

_LOCAL_PROBE = """
import json
from carbon.chain import networks
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext, ChainFailure
from carbon.development_session.chain_onboarding import carbon_testnet_context
context = carbon_testnet_context()
out = {
    "constants": [CARBON_NETWORK, CARBON_NETUID],
    "rows": sorted(networks.NETWORKS),
    "row": [networks.BOUND.network, networks.BOUND.chain_id, networks.BOUND.genesis_hash, networks.BOUND.netuid,
            list(networks.BOUND.endpoints), networks.BOUND.stage],
    "context": [context.network, context.endpoint, context.provider, context.genesis_hash, context.netuid],
}
try:
    networks.check_context(network="localnet", endpoint="wss://chain.example.org:443")
    out["remote"] = "accepted"
except networks.NetworkRefused as refused:
    out["remote"] = refused.code
try:
    ChainContext("localnet", "wss://chain.example.org:443", "disposable-localnet", context.genesis_hash, 2)
    out["remote_context"] = "accepted"
except ChainFailure:
    out["remote_context"] = "refused"
try:
    networks.check_genesis_at_connect(networks.BOUND, "0x" + "5d" * 32)
    out["other_genesis"] = "accepted"
except networks.NetworkRefused as refused:
    out["other_genesis"] = refused.code
print(json.dumps(out))
"""


def _local(env_changes, probe=_LOCAL_PROBE):
    import os
    import subprocess
    import sys
    from pathlib import Path

    names = (
        "CARBON_CHAIN_NETWORK",
        "CARBON_LOCALNET_GENESIS",
        "CARBON_LOCALNET_ENDPOINT",
    )
    env = {k: v for k, v in os.environ.items() if k not in names}
    env.update(env_changes)
    root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = str(root)
    return subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        check=False,
        text=True,
        env=env,
        cwd=root,
        timeout=120,
    )


def test_a_localnet_binding_is_the_staging_row_on_the_hosts_own_node():
    done = _local(
        {
            "CARBON_CHAIN_NETWORK": "localnet",
            "CARBON_LOCALNET_GENESIS": LOCAL_GENESIS,
            "CARBON_LOCALNET_ENDPOINT": LOCAL_ENDPOINT,
        }
    )
    assert done.returncode == 0, done.stderr[-400:]
    out = json.loads(done.stdout)
    assert out["constants"] == ["localnet", 2]
    assert out["rows"] == ["finney", "localnet", "testnet"]
    # no stage: no publication profile accepts it (no weights authority)
    assert out["row"] == [
        "localnet",
        "disposable-localnet",
        LOCAL_GENESIS,
        2,
        [LOCAL_ENDPOINT],
        None,
    ]
    assert out["context"] == [
        "localnet",
        LOCAL_ENDPOINT,
        "disposable-localnet",
        LOCAL_GENESIS,
        2,
    ]
    # only ever the host's own node, whatever a config names; the genesis stays exact at connect
    assert out["remote"] == "network_endpoint_unregistered"
    assert out["remote_context"] == "refused"
    assert out["other_genesis"] == "network_genesis_mismatch_at_connect"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({}, "CARBON_LOCALNET_GENESIS must name"),
        ({"CARBON_LOCALNET_GENESIS": "0x1234"}, "CARBON_LOCALNET_GENESIS must name"),
        (
            {"CARBON_LOCALNET_GENESIS": LOCAL_GENESIS},
            "CARBON_LOCALNET_ENDPOINT must be",
        ),
        (
            {
                "CARBON_LOCALNET_GENESIS": LOCAL_GENESIS,
                "CARBON_LOCALNET_ENDPOINT": "wss://chain.example.org:443",
            },
            "CARBON_LOCALNET_ENDPOINT must be",
        ),
        (
            {
                "CARBON_LOCALNET_GENESIS": LOCAL_GENESIS,
                "CARBON_LOCALNET_ENDPOINT": "ws://127.0.0.1",
            },
            "CARBON_LOCALNET_ENDPOINT must be",
        ),
    ],
)
def test_a_localnet_binding_without_its_genesis_and_own_node_refuses_at_import(
    changes, message
):
    done = _local({"CARBON_CHAIN_NETWORK": "localnet", **changes})
    assert done.returncode != 0
    assert message in done.stderr


@pytest.mark.parametrize("value", [None, "testnet", "finney"])
def test_no_other_binding_can_name_the_localnet_even_with_its_variables_set(value):
    probe = """
import json
from carbon.chain import networks
try:
    networks.row("localnet")
    named = "accepted"
except networks.NetworkRefused as refused:
    named = refused.code
print(json.dumps({"rows": sorted(networks.NETWORKS), "named": named}))
"""
    changes = {
        "CARBON_LOCALNET_GENESIS": LOCAL_GENESIS,
        "CARBON_LOCALNET_ENDPOINT": LOCAL_ENDPOINT,
    }
    if value is not None:
        changes["CARBON_CHAIN_NETWORK"] = value
    done = _local(changes, probe)
    assert done.returncode == 0, done.stderr[-400:]
    assert json.loads(done.stdout) == {
        "rows": ["finney", "testnet"],
        "named": "network_unregistered",
    }


def test_a_localnet_process_prepares_only_a_staging_root(tmp_path):
    from pathlib import Path

    probe = """
import json, sys
from pathlib import Path
from carbon.challenge_validator import receiver_setup
out = {}
for name in ("live", "staging"):
    root = Path(sys.argv[1]) / name
    try:
        receiver_setup._require_live_chain_or_staging(root)
        out[name] = "allowed"
    except receiver_setup.SetupRefused as refused:
        out[name] = refused.code
print(json.dumps(out))
"""
    (tmp_path / "staging" / "receiver").mkdir(parents=True)
    (tmp_path / "staging" / "receiver" / "STAGING").write_text("", encoding="utf-8")
    (tmp_path / "live" / "receiver").mkdir(parents=True)
    import subprocess
    import sys

    def run(changes):
        import os

        names = (
            "CARBON_CHAIN_NETWORK",
            "CARBON_LOCALNET_GENESIS",
            "CARBON_LOCALNET_ENDPOINT",
        )
        env = {k: v for k, v in os.environ.items() if k not in names}
        env.update(changes)
        root = Path(__file__).resolve().parents[2]
        env["PYTHONPATH"] = str(root)
        done = subprocess.run(
            [sys.executable, "-c", probe, str(tmp_path)],
            capture_output=True, check=False, text=True, env=env, cwd=root, timeout=120,
        )  # fmt: skip
        assert done.returncode == 0, done.stderr[-400:]
        return json.loads(done.stdout)

    bound = {
        "CARBON_CHAIN_NETWORK": "localnet",
        "CARBON_LOCALNET_GENESIS": LOCAL_GENESIS,
        "CARBON_LOCALNET_ENDPOINT": LOCAL_ENDPOINT,
    }
    assert run(bound) == {
        "live": "localnet_requires_staging_root",
        "staging": "allowed",
    }
    assert run({}) == {
        "live": "allowed",
        "staging": "allowed",
    }  # a live binding is unchanged


def test_no_miner_facing_surface_names_the_localnet():
    """The staging row never reaches a miner: the feed, board, KOTH view, dashboard, kit and MCP sources never name it
    (a source check: in a live process the row does not exist at all)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    surfaces = [
        root / "carbon/challenge_validator/score_feed.py",
        root / "carbon/challenge_validator/launch_board.py",
        root / "carbon/challenge_validator/koth_public.py",
        root / "carbon/dashboard/launch.py",
        *sorted((root / "carbon/miner_mcp").rglob("*.py")),
        *sorted((root / "carbon/mcp").rglob("*.py")),
        *sorted((root / "carbon/challenge_kit").rglob("*.py")),
    ]
    assert len(surfaces) > 6
    named = [
        str(p.relative_to(root))
        for p in surfaces
        if "localnet" in p.read_text(encoding="utf-8").lower()
    ]
    assert named == []
