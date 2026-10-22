"""One validator host: a receiver service per Challenge, its proxy and status.

`receiver_setup.prepare` and `.service` are fixtures here (they have their own
tests); nothing is installed, started or read from the chain.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from carbon.challenge_validator import receiver_setup, validator_host

HOTKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
OTHER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
NETWORK = {"network": "testnet", "netuid": 567}


class Receivers:
    """Records prepare/service calls; a prepared state holds its network file."""

    def __init__(self):
        self.prepared, self.started = [], []

    def prepare(self, **arguments):
        self.prepared.append(arguments)
        environment = arguments["receiver_state"] / "environment"
        environment.mkdir(parents=True)
        (environment / "miner-network.json").write_text(
            json.dumps({"context": NETWORK})
        )
        return {"status": "RECEIVER_PROFILE_READY"}

    def service(self, receiver_state):
        self.started.append(receiver_state)
        return {"unit": receiver_setup.unit_name(receiver_state)}


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "installed"
    path.mkdir(mode=0o700)
    return path


def _packs(state, challenges):
    """A pack directory per Challenge, as fetched exams would leave them."""
    root = state.parent / "packs"
    for challenge in challenges:
        (root / f"{challenge['id']}-{challenge['version']}").mkdir(
            parents=True, exist_ok=True
        )
    return root


def _setup(state, receivers, **extra):
    # Built packs: an explicit development install (condition 2).
    challenges = extra.pop("challenges", validator_host.select("current"))
    return validator_host.setup(
        installed_state=state,
        hotkey=extra.pop("hotkey", HOTKEY),
        challenges=challenges,
        prepare=receivers.prepare,
        service=receivers.service,
        **{
            "packs": _packs(state, challenges),
            "development": lambda _state: True,
            **extra,
        },
    )


def test_current_selects_one_newest_version_of_every_served_challenge():
    current = validator_host.select("current")
    assert current == list(receiver_setup.current())
    assert {c["id"] for c in current} == {c["id"] for c in receiver_setup.served()}
    assert validator_host.select("all") == list(receiver_setup.served())
    named = validator_host.select("f02@2.3, f02@2.3,electric-motor-magnetics@1.3")
    assert named == [
        {"id": "f02", "version": "2.3"},
        {"id": "electric-motor-magnetics", "version": "1.3"},
    ]
    with pytest.raises(receiver_setup.SetupRefused, match="challenge_not_registered"):
        validator_host.select("f02@9.9")


def test_setup_prepares_and_starts_one_receiver_per_challenge_on_its_own_port(
    state,
):
    receivers = Receivers()
    done = _setup(state, receivers)
    current = validator_host.select("current")
    assert [r["challenge"] for r in done["receivers"]] == current
    ports = [r["port"] for r in done["receivers"]]
    assert ports == list(range(8769, 8769 + len(current)))
    assert all(call["hotkey"] == HOTKEY for call in receivers.prepared)
    assert len(receivers.started) == len(current)
    record = state / "validator" / "host.json"
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    assert json.loads(record.read_bytes())["hotkey"] == HOTKEY


def test_setup_again_keeps_what_is_there_and_adds_what_is_new(state):
    receivers = Receivers()
    _setup(state, receivers, challenges=validator_host.select("f02@2.3"))
    again = Receivers()
    done = _setup(
        state,
        again,
        challenges=validator_host.select("f02@2.3,electric-motor-magnetics@1.3"),
    )
    assert [c["challenge"]["id"] for c in again.prepared] == [
        "electric-motor-magnetics"
    ]
    assert [r["port"] for r in done["receivers"]] == [8769, 8770]
    assert len(again.started) == 2  # every service is enabled again


def test_setup_never_changes_a_hosts_hotkey(state):
    _setup(state, Receivers(), challenges=validator_host.select("f02@2.3"))
    with pytest.raises(receiver_setup.SetupRefused, match="validator_hotkey_differs"):
        _setup(state, Receivers(), hotkey=OTHER)


def test_every_new_receiver_needs_its_exam_before_anything_is_prepared(state, tmp_path):
    # Validator, E4 (c): a receiver that cannot grade is never set up.
    packs = tmp_path / "fetched"
    (packs / "f02-2.3").mkdir(parents=True)
    receivers = Receivers()
    with pytest.raises(receiver_setup.SetupRefused, match="evaluation_pack_missing"):
        _setup(
            state,
            receivers,
            challenges=validator_host.select("f02@2.3,f08-ribbed-bracket@1.4"),
            packs=packs,
        )
    assert receivers.prepared == [] and receivers.started == []
    with pytest.raises(receiver_setup.SetupRefused, match="evaluation_pack_missing"):
        _setup(state, receivers, packs=None)
    _setup(state, receivers, challenges=validator_host.select("f02@2.3"), packs=packs)
    assert [c["pack"] for c in receivers.prepared] == [packs / "f02-2.3"]


def test_the_proxy_serves_each_receiver_by_challenge_and_version(state):
    # E6: one HTTPS name; each receiver at /ID/VERSION, still on loopback.
    done = _setup(
        state,
        Receivers(),
        challenges=validator_host.select("f02@2.3,electric-motor-magnetics@1.3"),
        domain="validator.example.org",
    )
    caddy = Path(done["proxy"]["caddyfile"]).read_text()
    assert caddy.startswith("validator.example.org {")
    assert "handle_path /f02/2.3/* {" in caddy
    assert "reverse_proxy 127.0.0.1:8769" in caddy
    assert "reverse_proxy 127.0.0.1:8770" in caddy
    entries = json.loads(Path(done["proxy"]["endpoint_entries"]).read_bytes())
    assert entries["add_to"] == validator_host.PUBLISHED
    assert entries["endpoints"][0] == {
        **NETWORK,
        "challenge": "f02",
        "version": "2.3",
        "intake_url": "https://validator.example.org/f02/2.3",
        "receiver_hotkey": HOTKEY,
    }
    # Every entry has exactly the published list's fields.
    published = json.loads(
        (
            Path(validator_host.__file__).parents[2] / validator_host.PUBLISHED
        ).read_bytes()
    )
    for entry in entries["endpoints"]:
        assert set(entry) == set(published["entry_fields"])


@pytest.mark.parametrize(
    "domain", ["https://v.example.org", "V.Example.org", "v.example.org/f02", "local"]
)
def test_a_proxy_needs_a_plain_dns_name(state, domain):
    _setup(state, Receivers(), challenges=validator_host.select("f02@2.3"))
    with pytest.raises(receiver_setup.SetupRefused, match="domain_invalid"):
        validator_host.write_proxy(state, domain)


def test_status_is_healthy_only_when_every_receiver_is(state):
    _setup(
        state,
        Receivers(),
        challenges=validator_host.select("f02@2.3,electric-motor-magnetics@1.3"),
    )
    healthy = {"status": "RECEIVER_HEALTHY"}
    assert (
        validator_host.status(state, receiver_status=lambda _: healthy)["status"]
        == "VALIDATOR_HEALTHY"
    )
    answers = iter([healthy, {"status": "RECEIVER_NOT_HEALTHY"}])
    found = validator_host.status(state, receiver_status=lambda _: next(answers))
    assert found["status"] == "VALIDATOR_NOT_HEALTHY"

    def broken(_state):
        raise ValueError("invalid DEVELOPMENT receiver configuration")

    unreadable = validator_host.status(state, receiver_status=broken)
    assert {r["intake"] for r in unreadable["receivers"]} == {"UNREADABLE"}


def test_status_before_setup_says_what_to_run(state):
    with pytest.raises(receiver_setup.SetupRefused, match="validator_host_not_set_up"):
        validator_host.status(state)


# --- E4: this hotkey's own signed copy of each exam ----------------------------------

SOURCE = {
    "schema": validator_host.EXAM_SOURCE_SCHEMA,
    "url": "https://exams.example.org",
    "receiver": OTHER,
}


def test_the_exam_source_is_public_facts_only(tmp_path):
    good = tmp_path / "source.json"
    good.write_text(json.dumps(SOURCE))
    assert validator_host.read_exam_source(good) == SOURCE
    for changed in (
        {"url": "http://exams.example.org"},
        # Condition 1: a source file never names the trust root.
        {"producer_public_key": "a" * 64},
        {"receiver": "carbon"},
        {"private_key": "x"},
        {"schema": "other"},
    ):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({**SOURCE, **changed}))
        with pytest.raises(receiver_setup.SetupRefused, match="exam_source_invalid"):
            validator_host.read_exam_source(bad)


def _copy_route(producer, hotkey):
    """A distribution host's per-hotkey route serving one Cooling copy."""
    from test_copy_delivery import _issue

    from carbon.challenge_validator import copy_route

    package, (challenge, version, manifest, _files) = _issue(
        producer, "cooling", hotkey
    )

    class Fetcher:
        def __init__(self):
            self.asked = []

        def ask(self, challenge_id, fingerprint=None):
            self.asked.append((challenge_id, fingerprint))
            if fingerprint is None:
                return {"packages": [copy_route.listing_entry(package)]}
            return {"package": package}

    return Fetcher(), {"id": challenge, "version": version}, manifest


def test_setup_fetches_verifies_and_selects_this_hotkeys_own_copy(state, tmp_path):
    # E4 end to end, in process: the per-hotkey route, the real import, and the
    # receiver prepared with the canonical pack by its digest from the store.
    from test_copy_package import HOTKEYS

    from carbon.challenge_validator import answer_key as ak
    from carbon.challenge_validator import sealed_pack_import as spi

    producer = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    hotkey = HOTKEYS[0]
    fetcher, challenge, _manifest = _copy_route(producer, hotkey)
    source = SOURCE
    receivers = Receivers()
    validator_host.setup(
        installed_state=state,
        hotkey=hotkey,
        challenges=[challenge],
        exam_source=source,
        prepare=receivers.prepare,
        service=receivers.service,
        fetch=lambda *args: validator_host.fetch_exams(
            *args, fetcher=fetcher, producer_public_key=producer.public_key
        ),
    )
    (prepared,) = receivers.prepared
    store = state / "validator" / validator_host.EXAMS_DIRECTORY
    assert prepared["pack_store"] == store and "pack" not in prepared
    digest = prepared["pack_digest"]
    assert spi.SealedPackStore(store).delivered(
        digest, challenge["id"], challenge["version"]
    )
    assert stat.S_IMODE(store.stat().st_mode) == 0o700
    # Running setup again fetches nothing for a receiver it already has.
    fetcher.asked.clear()
    validator_host.setup(
        installed_state=state,
        hotkey=hotkey,
        challenges=[challenge],
        exam_source=source,
        prepare=receivers.prepare,
        service=receivers.service,
        fetch=lambda *args: validator_host.fetch_exams(
            *args, fetcher=fetcher, producer_public_key=producer.public_key
        ),
    )
    assert fetcher.asked == [] and len(receivers.prepared) == 1


def test_another_hotkeys_copy_is_refused_and_nothing_is_prepared(state, tmp_path):
    from test_copy_package import HOTKEYS

    from carbon.challenge_validator import answer_key as ak

    producer = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    fetcher, challenge, _manifest = _copy_route(producer, HOTKEYS[1])
    receivers = Receivers()
    with pytest.raises(receiver_setup.SetupRefused):
        validator_host.setup(
            installed_state=state,
            hotkey=HOTKEYS[0],
            challenges=[challenge],
            exam_source=SOURCE,
            prepare=receivers.prepare,
            service=receivers.service,
            fetch=lambda *args: validator_host.fetch_exams(
                *args, fetcher=fetcher, producer_public_key=producer.public_key
            ),
        )
    assert receivers.prepared == [] and receivers.started == []


def test_no_delivered_exam_or_several_are_refused_before_anything_is_prepared(
    state, monkeypatch
):
    from carbon.challenge_validator import sealed_pack_import as spi

    monkeypatch.setattr(spi.SealedPackStore, "delivered", lambda *args: True)
    challenge = {"id": "f02", "version": "2.3"}
    for rows, code in (
        ([], "evaluation_pack_missing"),
        (
            [{"fingerprint": "sha256:" + "1" * 64, "state": "WITHDRAWN"}],
            "evaluation_pack_missing",
        ),
        (
            [
                {"fingerprint": "sha256:" + "1" * 64, "state": "IMPORTED"},
                {"fingerprint": "sha256:" + "2" * 64, "state": "HELD"},
            ],
            "evaluation_pack_ambiguous",
        ),
    ):
        receivers = Receivers()
        with pytest.raises(receiver_setup.SetupRefused, match=code):
            validator_host.setup(
                installed_state=state,
                hotkey=HOTKEY,
                challenges=[challenge],
                exam_source=SOURCE,
                prepare=receivers.prepare,
                service=receivers.service,
                fetch=lambda *args, rows=rows: validator_host.fetch_exams(
                    *args,
                    fetcher=object(),
                    sync=lambda *a, **k: {"packages": rows},
                    producer_public_key="a" * 64,
                ),
            )
        assert receivers.prepared == []


def test_an_unfetchable_exam_is_a_typed_refusal(state):
    from carbon.challenge_validator.answer_key import AnswerKeyRefused

    def refused(*args, **kwargs):
        raise AnswerKeyRefused("answer_key_no_validator_permit")

    with pytest.raises(
        receiver_setup.SetupRefused, match="answer_key_no_validator_permit"
    ):
        validator_host.fetch_exams(
            state,
            HOTKEY,
            [{"id": "f02", "version": "2.3"}],
            SOURCE,
            fetcher=object(),
            sync=refused,
            producer_public_key="a" * 64,
        )


def test_signed_exams_and_built_packs_are_not_combined(state, tmp_path):
    with pytest.raises(receiver_setup.SetupRefused, match="exam_choice_conflict"):
        _setup(state, Receivers(), exam_source=SOURCE)


def test_exams_are_verified_only_against_the_release_pinned_producer_key(
    state, tmp_path, monkeypatch
):
    # Condition 1: with no key registered, fetching refuses before anything is
    # asked.
    registry = json.loads(validator_host.EXAM_PRODUCER.read_bytes())
    unregistered = tmp_path / "unregistered.json"
    unregistered.write_text(json.dumps({**registry, "producer_public_key": None}))
    monkeypatch.setattr(validator_host, "EXAM_PRODUCER", unregistered)
    asked = []
    with pytest.raises(receiver_setup.SetupRefused, match="exam_producer_unregistered"):
        validator_host.fetch_exams(
            state,
            HOTKEY,
            [{"id": "f02", "version": "2.3"}],
            SOURCE,
            fetcher=object(),
            sync=lambda *a, **k: asked.append(a) or {"packages": []},
        )
    assert asked == []
    pinned = tmp_path / "exam_producer.json"
    pinned.write_text(json.dumps({**registry, "producer_public_key": "b" * 64}))
    monkeypatch.setattr(validator_host, "EXAM_PRODUCER", pinned)
    used = []
    validator_host.fetch_exams(
        state,
        HOTKEY,
        [{"id": "f02", "version": "2.3"}],
        SOURCE,
        fetcher=object(),
        sync=lambda store, fetcher, key, *a, **k: used.append(key) or {"packages": []},
    )
    assert used == ["b" * 64]
    pinned.write_text(json.dumps({**registry, "producer_public_key": "B" * 64}))
    with pytest.raises(
        receiver_setup.SetupRefused, match="exam_producer_registry_invalid"
    ):
        validator_host.pinned_producer_key()


def test_built_packs_need_an_explicit_development_install(state):
    # Condition 2: an operator-built pack never serves as an official exam.
    receivers = Receivers()
    with pytest.raises(
        receiver_setup.SetupRefused, match="built_packs_development_only"
    ):
        _setup(state, receivers, development=lambda _state: False)
    assert receivers.prepared == []
    assert validator_host._development_install(state) is False  # no pin here


def test_the_release_pins_the_testnet_exam_producer_key():
    # OWNER-TESTNET-EXAM-KEYS-01: the testnet producer key created on the
    # custody host; its public half is the trust root (TESTNET 567 only).
    from carbon.challenge_validator.answer_key import key_id

    key = validator_host.pinned_producer_key()
    assert key == "375e792210bf352ae3b331b9f5055414a05480fb9ab0b8a891585c435060ec17"
    assert key_id(key) == "carbon-producer-8d358757cf077562"
