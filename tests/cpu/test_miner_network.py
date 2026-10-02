"""The network a miner's campaign talks to, without an operator file (C-MLP-04).

The chain context is Carbon's settled testnet constants; the publisher is the
hotkey at UID 0 of a finalized snapshot. These tests hold that the file setup
writes is checked against those constants, that a campaign binds to exactly
one source (an operator configuration or the miner's file), and that a
snapshot without UID 0 is refused rather than guessed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.development_session import miner_network as mn
from carbon.development_session.chain_onboarding import carbon_testnet_context

PUBLISHER = "5" + "P" * 47


class Reader:
    def __init__(self, uids=(0, 1)):
        self.uids = uids

    async def capture(self, context):
        assert context == carbon_testnet_context()
        return SimpleNamespace(
            finalized_block=77,
            participants=tuple(
                SimpleNamespace(
                    uid=uid, hotkey=PUBLISHER if uid == 0 else "5" + "M" * 47
                )
                for uid in self.uids
            ),
        )


def test_the_publisher_is_uid_zero_of_a_finalized_snapshot(tmp_path):
    bound, block = mn.resolve(Reader())
    assert (bound.publisher_hotkey, bound.netuid, block) == (PUBLISHER, 567, 77)
    path = tmp_path / "miner-network.json"
    path.write_text(json.dumps(mn.document(bound, block)))
    assert mn.binding(miner_network=path) == bound


def test_no_uid_zero_is_refused_not_guessed():
    with pytest.raises(mn.NetworkUnavailable) as refused:
        mn.resolve(Reader(uids=(1, 2)))
    assert refused.value.code == "publisher_not_on_chain"


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "x"},
        {"publisher_uid": 3},
        {"publisher_hotkey": "not a hotkey"},
        {"context": {"network": "finney"}},
    ],
)
def test_a_network_file_must_be_carbons_testnet(tmp_path, change):
    bound, block = mn.resolve(Reader())
    document = {**mn.document(bound, block), **change}
    path = tmp_path / "miner-network.json"
    path.write_text(json.dumps(document))
    with pytest.raises(mn.NetworkUnavailable):
        mn.load(path)


def test_a_campaign_binds_to_exactly_one_source(tmp_path):
    with pytest.raises(mn.NetworkUnavailable, match="network_binding_required"):
        mn.binding()
    with pytest.raises(mn.NetworkUnavailable, match="network_binding_required"):
        mn.binding(operator_config=tmp_path / "a", miner_network=tmp_path / "b")


def test_an_operator_configuration_still_binds(monkeypatch, tmp_path):
    from carbon.development_testnet import operator

    monkeypatch.setattr(
        operator,
        "load_config",
        lambda _: SimpleNamespace(
            context="ctx", publisher_hotkey="5Operator", netuid=567
        ),
    )
    bound = mn.binding_for(SimpleNamespace(operator_config=tmp_path / "op.json"))
    assert (bound.context, bound.publisher_hotkey) == ("ctx", "5Operator")
