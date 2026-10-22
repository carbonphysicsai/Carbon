"""The per-hotkey evaluation-pack route (E4): a hotkey is served only its own signed
copy, under its own signing domain, and the fetch log binds hotkey -> copy digest."""

from __future__ import annotations

import json

import pytest

from carbon.chain.auth import AuthCode, AuthenticatedHotkey, AuthFailure
from carbon.chain.permits import PermitUnavailable
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import copy_route as route
from carbon.challenge_validator import distribution as dist
from carbon.challenge_validator import sealed_pack_import as spi

RECEIVER = "5Distribution"
ONE, TWO, OUTSIDER = "5ValidatorOne", "5ValidatorTwo", "5Outsider"
CHALLENGE, VERSION = "electric-motor-magnetics", "1.1"


class Verifier:
    def verify(self, headers, body, *, method, path, receiver, now_ns, nonce_store):
        assert (method, path, receiver) == ("POST", route.PACK_PATH, RECEIVER)
        hotkey = headers.get("X-Hotkey")
        if hotkey is None:
            raise AuthFailure(AuthCode.SIGNATURE)
        if not nonce_store.check_and_store(hotkey, int(headers["X-Nonce"])):
            raise AuthFailure(AuthCode.REPLAY)
        return AuthenticatedHotkey(hotkey, int(headers["X-Nonce"]))


class Permits:
    def __init__(self, table):
        self.table = table

    def read(self, hotkey):
        found = self.table.get(hotkey, "unregistered")
        if found == "down":
            raise PermitUnavailable("permit_read_failed")
        if found == "unregistered":
            return None
        return {"permit": found, "block": 1234}


def _commitment(tag):
    return spi.commitment_for(
        CHALLENGE, VERSION, b"manifest-" + tag, {"f": b"x"}, {"retire_block": 10**9}
    )


def _package(key, hotkey, tag):
    return route.copy_package(
        key,
        _commitment(tag),
        {"manifest": tag.decode(), "files": {}},
        hotkey=hotkey,
        copy_digest="sha256:" + tag.hex().ljust(64, "0")[:64],
        canonical_digest="sha256:" + "c" * 64,
    )


def _drop(folder, name, package):
    path = folder / name
    path.write_text(json.dumps(package))
    path.chmod(0o600)


@pytest.fixture
def world(tmp_path):
    key = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    inbox = tmp_path / "copies"
    inbox.mkdir(mode=0o700)
    packages = {}
    for hotkey, tag in ((ONE, b"one"), (TWO, b"two")):
        folder = inbox / hotkey
        folder.mkdir(mode=0o700)
        packages[hotkey] = _package(key, hotkey, tag)
        _drop(folder, "pack.json", packages[hotkey])
    base = dist.DistributionService(
        dist.Inbox(tmp_path, key.public_key),
        receiver=RECEIVER,
        verifier=Verifier(),
        permits=Permits({ONE: True, TWO: True, OUTSIDER: False}),
        nonces=dist.NonceStore(tmp_path / "nonces.sqlite3"),
        log=dist.FetchLog(tmp_path / "fetch.jsonl"),
    )
    pack = route.attach(base, inbox, key.public_key)
    return {
        "key": key,
        "service": pack,
        "packages": packages,
        "log": tmp_path / "fetch.jsonl",
        "inbox": inbox,
    }


def fetcher(service, hotkey):
    counter = iter(range(1, 10**6))

    def sign(body, *, receiver, nonce_ns, path):
        assert path == route.PACK_PATH
        return {"X-Hotkey": hotkey, "X-Nonce": str(next(counter))}

    def post(url, body, headers):
        return service.handle(headers, body)

    return route.PackFetcher("http://127.0.0.1:1", None, RECEIVER, post=post, sign=sign)


def entries(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_each_hotkey_lists_and_fetches_only_its_own_copy(world):
    for hotkey in (ONE, TWO):
        asker = fetcher(world["service"], hotkey)
        listed = asker.ask(CHALLENGE)["packages"]
        assert len(listed) == 1
        commitment, copy = route.verify_manifest(listed[0], world["key"].public_key)
        assert copy["validator_hotkey"] == hotkey
        package = asker.ask(CHALLENGE, commitment["fingerprint"])["package"]
        assert package == world["packages"][hotkey]


def test_a_hotkey_cannot_fetch_another_hotkeys_fingerprint(world):
    theirs = world["packages"][TWO]["manifest"]["commitment"]["fingerprint"]
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_unknown_batch"):
        fetcher(world["service"], ONE).ask(CHALLENGE, theirs)


def test_a_misfiled_package_is_never_served(world):
    # The package for TWO dropped into ONE's directory names TWO: ONE is not served it.
    _drop(world["inbox"] / ONE, "stray.json", world["packages"][TWO])
    listed = fetcher(world["service"], ONE).ask(CHALLENGE)["packages"]
    assert len(listed) == 1
    copy = route.verify_manifest(listed[0], world["key"].public_key)[1]
    assert copy["validator_hotkey"] == ONE


def test_the_fetch_log_binds_hotkey_to_copy_digest(world):
    asker = fetcher(world["service"], ONE)
    fingerprint = world["packages"][ONE]["manifest"]["commitment"]["fingerprint"]
    asker.ask(CHALLENGE)
    asker.ask(CHALLENGE, fingerprint)
    served = [e for e in entries(world["log"]) if e["verdict"] == "SERVED"]
    assert len(served) == 1
    assert served[0]["hotkey"] == ONE
    wanted = world["packages"][ONE]["manifest"]["copy"]["copy_digest"]
    assert served[0]["copy_digest"] == wanted
    assert served[0]["route"] == "evaluation-pack"


def test_no_permit_and_no_copy_are_typed_outcomes(world):
    with pytest.raises(ak.AnswerKeyRefused, match="answer_key_no_validator_permit"):
        fetcher(world["service"], OUTSIDER).ask(CHALLENGE)
    world["service"].permits = Permits({"5NoCopy": True})
    assert fetcher(world["service"], "5NoCopy").ask(CHALLENGE)["packages"] == []


def test_the_pack_domain_is_separate_from_the_answer_key_domain(world):
    package = world["packages"][ONE]
    manifest = package["manifest"]
    public_key = world["key"].public_key
    assert ak.verify_in(route.PACK_DOMAIN, manifest, package["signature"], public_key)
    assert not ak.verify_in(ak.DOMAIN, manifest, package["signature"], public_key)
    with pytest.raises(ak.AnswerKeyRefused):
        route.verify_package(
            {"schema": ak.PACKAGE_SCHEMA, "manifest": manifest}, public_key
        )


def test_a_tampered_or_foreign_package_is_not_served(world, tmp_path):
    other = ak.ProducerKey.create(str(tmp_path / "other.key"))
    _drop(world["inbox"] / TWO, "forged.json", _package(other, TWO, b"forged"))
    tampered = json.loads(json.dumps(world["packages"][TWO]))
    tampered["payload"]["manifest"] = "changed"
    _drop(world["inbox"] / TWO, "tampered.json", tampered)
    listed = fetcher(world["service"], TWO).ask(CHALLENGE)["packages"]
    assert len(listed) == 1


def test_a_withdrawn_copy_is_not_served(world):
    gone = world["packages"][ONE]["manifest"]["copy"]["copy_digest"]
    world["service"].inbox = route.CopyInbox(
        world["inbox"], world["key"].public_key, withdrawn=lambda challenge: {gone}
    )
    assert fetcher(world["service"], ONE).ask(CHALLENGE)["packages"] == []
    assert len(fetcher(world["service"], TWO).ask(CHALLENGE)["packages"]) == 1


def test_the_first_route_keeps_its_own_path_and_schema(world):
    assert dist.DistributionService.route == ak.PATH
    assert dist.DistributionService.request_schema == ak.REQUEST_SCHEMA
    assert world["service"].route == route.PACK_PATH
    assert world["service"].request_schema == route.PACK_REQUEST_SCHEMA
