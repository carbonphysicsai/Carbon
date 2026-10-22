"""The distribution host's signed per-fetch delivery record (tracing ruling).

With a delivery key configured, every SERVED fetch logs a signed record of what
was served to which hotkey at which finalized block, in its own signing domain: a
leaked exam narrows to the hotkeys that fetched it with evidence the host cannot
later deny. The host holds its own key, never the producer's."""

# ruff: noqa: F811  (the imported fixtures are received as test arguments)
import pytest
from test_challenge_validator_answer_key import (  # noqa: F401
    OUTSIDER,
    VALIDATOR,
    entries,
    fetcher,
    host,
    published,
)

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import distribution as dist


@pytest.fixture
def signer(tmp_path):
    return ak.ProducerKey.create(str(tmp_path / "delivery.key"))


def _fetch(host, published):
    challenge = published["source"].challenge_id
    asker = fetcher(host["service"], VALIDATOR)
    listed = asker.ask(challenge)["packages"]
    fingerprint = listed[0]["manifest"]["commitment"]["fingerprint"]
    return challenge, fingerprint, asker.ask(challenge, fingerprint)["package"]


def test_a_served_fetch_logs_a_signed_record_naming_the_hotkey_and_the_package(
    host, published, signer
):
    host["service"].signer = signer
    challenge, fingerprint, package = _fetch(host, published)
    served = [e for e in entries(host["log"]) if e["verdict"] == "SERVED"]
    (record,) = [e["delivery"] for e in served]
    manifest = dist.verify_delivery(record, signer.public_key)
    assert manifest is not None
    assert manifest["schema"] == dist.DELIVERY_SCHEMA
    assert (
        manifest["challenge_id"],
        manifest["fingerprint"],
        manifest["hotkey"],
    ) == (challenge, fingerprint, VALIDATOR)
    assert manifest["package_digest"] == ak._digest(package)
    assert type(manifest["block"]) is int and manifest["time_ns"] > 0
    # A listing is not a delivery: it carries no record.
    assert all(
        "delivery" not in e for e in entries(host["log"]) if e["verdict"] != "SERVED"
    )


def test_a_tampered_or_foreign_record_does_not_verify(
    host, published, signer, tmp_path
):
    host["service"].signer = signer
    _fetch(host, published)
    (record,) = [
        e["delivery"] for e in entries(host["log"]) if e["verdict"] == "SERVED"
    ]
    forged = {**record, "manifest": {**record["manifest"], "hotkey": OUTSIDER}}
    assert dist.verify_delivery(forged, signer.public_key) is None
    other = ak.ProducerKey.create(str(tmp_path / "other.key"))
    assert dist.verify_delivery(record, other.public_key) is None
    assert dist.verify_delivery({}, signer.public_key) is None


def test_a_record_is_not_a_package_signature(signer):
    """The delivery domain is separate: a delivery signature never verifies as a
    package manifest signature, and the package domain cannot be requested."""
    manifest = {"schema": dist.DELIVERY_SCHEMA, "x": 1}
    signature = signer.sign_in(dist.DELIVERY_DOMAIN, manifest)
    assert ak.verify_in(dist.DELIVERY_DOMAIN, manifest, signature, signer.public_key)
    assert not ak.verify_in(ak.DOMAIN, manifest, signature, signer.public_key)
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_domain_invalid"):
        signer.sign_in(ak.DOMAIN, manifest)
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_domain_invalid"):
        signer.sign_in(b"no-terminator", manifest)


def test_without_a_delivery_key_the_log_is_as_before(host, published):
    _fetch(host, published)
    served = [e for e in entries(host["log"]) if e["verdict"] == "SERVED"]
    assert served and all("delivery" not in e for e in served)


def test_the_service_takes_only_a_producer_key_as_its_signer(tmp_path, published):
    with pytest.raises(TypeError):
        dist.DistributionService(
            dist.Inbox(tmp_path, published["key"].public_key),
            receiver="r",
            verifier=None,
            permits=None,
            nonces=None,
            log=None,
            signer="a string",
        )
