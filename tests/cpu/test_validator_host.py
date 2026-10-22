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
    challenges = extra.pop("challenges", validator_host.select("current"))
    return validator_host.setup(
        installed_state=state,
        hotkey=extra.pop("hotkey", HOTKEY),
        challenges=challenges,
        prepare=receivers.prepare,
        service=receivers.service,
        **{"packs": _packs(state, challenges), **extra},
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
