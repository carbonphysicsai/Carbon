"""116, 17 Nov: weights failed TRANSPORT_MALFORMED at dispatch.prepare: the publication document (intent + plan + the
observed metagraph snapshot + capabilities) crossed the transport meter's 65536-byte cap as registrations grew (64,426
bytes, +~470 per epoch). The journal now encodes it with the same canonical bytes under its own storage bounds.
"""

from __future__ import annotations

import math

import pytest

from carbon.chain.dispatch import journal_encode
from carbon.chain.publication import PublicationFailure
from carbon.rewards.ledger import encode
from carbon.transport.models import TransportFailure


def _document(participants):
    return {
        "intent": {"identity": "i", "digest": "a" * 64},
        "plan": {"q12": [[1, 4095]], "integers": [[1, 65535]]},
        "snapshot": {
            "finalized_block": 1,
            "participants": [
                {
                    "uid": uid,
                    "hotkey": "5" + "H" * 47,
                    "coldkey": "5" + "C" * 47,
                    "registered_at": 1,
                }
                for uid in range(participants)
            ],
        },
        "capabilities": {"spec_version": 1},
    }


def test_the_same_canonical_bytes_as_the_ledger_where_both_accept():
    for participants in (1, 64, 256):
        document = _document(participants)
        assert journal_encode(document) == encode(document)


def test_a_document_over_the_transport_byte_cap_is_journaled():
    big = _document(520)  # the live shape past 65536 bytes
    with pytest.raises(TransportFailure):
        encode(big)
    raw = journal_encode(big)
    assert len(raw) > 65536 and raw.startswith('{"capabilities"')


@pytest.mark.parametrize(
    "bad", [{"x": math.nan}, {"x": math.inf}, {"x": 2**64}, {"x": "\ud800"}]
)
def test_every_other_check_of_the_meter_still_refuses(bad):
    with pytest.raises(PublicationFailure):
        journal_encode(bad)


def test_depth_is_still_bounded():
    deep = node = {}
    for _ in range(20):
        node["a"] = {}
        node = node["a"]
    with pytest.raises(PublicationFailure):
        journal_encode(deep)
