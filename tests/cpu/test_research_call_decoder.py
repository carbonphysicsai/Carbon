"""The shared research envelope decoder changes no existing wire contract."""

import base64
from dataclasses import replace

import pytest

from carbon import research
from carbon.mcp.model import McpCall, McpField
from carbon.miner_mcp.research import decode_research_call


def _call():
    return research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(
            research.ChallengeKey("synthetic-linear-field-2d", "1.3")
        ),
    )


def _wire():
    payload = base64.b64encode(research.canonical_bytes(_call())).decode("ascii")
    return McpCall(
        "1.0", research.RESEARCH_NAMESPACE, (McpField("call_base64", payload),)
    )


def test_shared_decoder_retains_existing_canonical_wire():
    assert decode_research_call(_wire()) == _call()


@pytest.mark.parametrize(
    "payload",
    ["not-base64", "é", "AA==", 1, "x" * (1024**2 + 1)],
    ids=["invalid-base64", "non-ascii", "invalid-canonical", "wrong-type", "oversize"],
)
def test_shared_decoder_refuses_bad_payload(payload):
    with pytest.raises(ValueError):
        decode_research_call(
            replace(_wire(), fields=(McpField("call_base64", payload),))
        )


@pytest.mark.parametrize(
    "tool,fields",
    [
        ("construction_submit", ()),
        (research.RESEARCH_NAMESPACE, ()),
        (
            research.RESEARCH_NAMESPACE,
            (McpField("call_base64", ""), McpField("owner", "other")),
        ),
        (research.RESEARCH_NAMESPACE, (McpField("wrong_field", ""),)),
    ],
)
def test_shared_decoder_refuses_another_namespace_or_added_owner(tool, fields):
    with pytest.raises(ValueError):
        decode_research_call(replace(_wire(), tool=tool, fields=fields))


def test_shared_decoder_refuses_nested_namespace_mismatch():
    call = replace(_call(), namespace="carbon_protocol_v1")
    payload = base64.b64encode(research.canonical_bytes(call)).decode("ascii")
    with pytest.raises(ValueError, match="research namespace mismatch"):
        decode_research_call(
            replace(_wire(), fields=(McpField("call_base64", payload),))
        )
