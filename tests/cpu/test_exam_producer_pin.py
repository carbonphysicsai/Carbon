"""The testnet exam producer's public key pin (OWNER-TESTNET-EXAM-KEYS-01): the key id
is derived from the public key, never typed independently. Public data only; the
private key and K_master stay on the custody host."""

import json
from pathlib import Path

from carbon.challenge_validator import answer_key as ak

PIN = Path(ak.__file__).with_name("exam_producer.json")


def test_the_pinned_key_id_is_derived_from_the_pinned_public_key():
    pin = json.loads(PIN.read_text())
    assert set(pin) == {"schema", "scope", "decision", "public_key", "key_id"}
    assert pin["scope"] == "TESTNET_DEVELOPMENT"
    assert len(bytes.fromhex(pin["public_key"])) == 32
    assert pin["key_id"] == ak.key_id(pin["public_key"])


def test_the_pin_is_a_public_key_only():
    text = PIN.read_text().lower()
    assert "private" not in text and "master" not in text and "secret" not in text
