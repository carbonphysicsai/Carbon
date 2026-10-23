"""Published evaluation endpoints name the Challenge version (published-endpoints
v2, Validator ruling 2026-10-21).

A receiver serves exactly one (Challenge id, version), and one Challenge may
have several intake versions (Motor 1.2 and 1.3). These tests hold:
- the v2 list is closed: each entry names a registered intake version, and a
  duplicate or conflicting (id, version) publishes nothing;
- a v1 list (entries without a version) is still read, for a Challenge with
  exactly one intake version only; one with several is unpublished, and
  Review and setup say so;
- Review writes each endpoint into the profile for exactly its version,
  setup and the prelaunch review report per version, and CONFIGURED_FOR_ALL
  or SOME counts versions;
- each version's submit reads its own version's endpoint, never another's.

No chain, provider, image or intake is contacted.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_miner_launchpad_environment_setup import (
    HOTKEY,
    REVISION,
    Onboarding,
    completed,
)
from test_miner_setup_after_install import (
    Reinstalled,
    entry,
    one_version_challenge,
    profile,
    publish,
)

from carbon.battery import campaign as battery
from carbon.development_session.intake_targets import for_version
from carbon.motor import campaign as motor
from carbon.motor.contracts import key_for, keyed
from scripts.dev.miner_launchpad import environment_setup as environment
from scripts.dev.miner_launchpad import prelaunch, runner
from scripts.dev.miner_launchpad.environment_setup import (
    EnvironmentSetup,
    intake_challenges,
    published_endpoints,
)

MOTOR = "electric-motor-magnetics"
OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
URL_12 = "https://motor-12.example.org"
URL_13 = "https://motor-13.example.org"
UNREADABLE = {
    "endpoints": {},
    "problem": "published_endpoints_unreadable",
    "unversioned": [],
}


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture
def head(monkeypatch):
    monkeypatch.setattr(environment, "checkout_revision", lambda repo=None: REVISION)


def versions_of(challenge_id):
    return [c["version"] for c in intake_challenges() if c["id"] == challenge_id]


def test_motor_has_several_intake_versions():
    # The premise of the ruling, read from the registry, not assumed.
    assert {"1.2", "1.3"} <= set(versions_of(MOTOR))
    # And some Challenge has exactly one, which a v1 entry can still name.
    one = one_version_challenge()
    assert versions_of(one["id"]) == [one["version"]]


# --- the v2 list --------------------------------------------------------------------


def test_a_v2_list_publishes_each_version_its_own_endpoint(tmp_path, monkeypatch):
    path = publish(
        tmp_path,
        monkeypatch,
        [
            entry(MOTOR, version="1.2", intake_url=URL_12),
            entry(MOTOR, version="1.3", intake_url=URL_13, receiver_hotkey=OTHER),
            entry(MOTOR, version="1.2", network="finney", netuid=1),
        ],
        schema="v2",
    )
    found = published_endpoints(path)
    assert found["problem"] is None and found["unversioned"] == []
    assert set(found["endpoints"]) == {MOTOR}
    assert found["endpoints"][MOTOR]["1.2"]["intake_url"] == URL_12
    assert found["endpoints"][MOTOR]["1.3"]["intake_url"] == URL_13
    assert found["endpoints"][MOTOR]["1.3"]["receiver_hotkey"] == OTHER
    # Distinct validators may serve one version, as today.
    path = publish(
        tmp_path,
        monkeypatch,
        [
            entry(MOTOR, version="1.2", intake_url=URL_12),
            entry(MOTOR, version="1.2", intake_url=URL_13, receiver_hotkey=OTHER),
        ],
        schema="v2",
    )
    validators = published_endpoints(path)["endpoints"][MOTOR]["1.2"]["validators"]
    assert [v["intake_url"] for v in validators] == [URL_12, URL_13]


@pytest.mark.parametrize(
    "entries",
    [
        # Closed fields: the version is required, and nothing else is added.
        [entry(MOTOR)],
        [entry(MOTOR, version="1.2", extra=True)],
        # The version is an exact registered intake version of its Challenge.
        [entry(MOTOR, version=1.2)],
        [entry(MOTOR, version="1.2.0")],
        [entry(MOTOR, version="9.9")],
        [entry("no-such-challenge", version="1.2")],
        # The same (id, version) twice, or a conflicting URL or receiver.
        [entry(MOTOR, version="1.2")] * 2,
        [
            entry(MOTOR, version="1.2", receiver_hotkey=OTHER),
            entry(MOTOR, version="1.2", intake_url=URL_12, receiver_hotkey=OTHER),
        ],
        [
            entry(MOTOR, version="1.2", intake_url=URL_12),
            entry(MOTOR, version="1.2", intake_url=URL_12, receiver_hotkey=OTHER),
        ],
    ],
)
def test_a_v2_list_that_breaks_the_schema_publishes_nothing(
    tmp_path, monkeypatch, entries
):
    path = publish(tmp_path, monkeypatch, entries, schema="v2")
    assert published_endpoints(path) == UNREADABLE


def test_another_schema_publishes_nothing(tmp_path, monkeypatch):
    path = publish(tmp_path, monkeypatch, [], schema="v3")
    assert published_endpoints(path) == UNREADABLE


# --- the v1 list: read as before, never as covering several versions ---------------


def test_a_v1_entry_applies_only_where_its_challenge_has_one_intake_version(
    tmp_path, monkeypatch
):
    one = one_version_challenge()
    battery_id, battery_version = one["id"], one["version"]
    path = publish(
        tmp_path, monkeypatch, [entry(battery_id), entry(MOTOR, intake_url=URL_12)]
    )
    found = published_endpoints(path)
    assert found["problem"] is None
    # The one-version Challenge: its one intake version, exactly as v1 read it.
    assert found["endpoints"] == {battery_id: {battery_version: entry(battery_id)}}
    # Motor: several versions, so none; said, never guessed.
    assert found["unversioned"] == [MOTOR]
    # A v1 entry still needs exactly the v1 fields.
    path = publish(tmp_path, monkeypatch, [entry(battery_id, version=battery_version)])
    assert published_endpoints(path) == UNREADABLE


def test_review_and_setup_say_a_v1_entry_for_several_versions_is_written_for_none(
    tmp_path, state, head, monkeypatch
):
    publish(tmp_path, monkeypatch, [entry(MOTOR, intake_url=URL_12)])
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    result = setup.review({"confirm": True})
    assert "version_intakes" not in profile(setup)
    assert "intakes" not in profile(setup)
    unversioned = [
        w for w in result["warnings"] if w["code"] == "published_endpoint_unversioned"
    ]
    assert unversioned == [
        {
            "code": "published_endpoint_unversioned",
            "challenge": MOTOR,
            "message": environment.UNVERSIONED_ENDPOINT.format(challenge=MOTOR),
        }
    ]
    assert "nothing for you to fix" in unversioned[0]["message"]
    missing = {
        (w["challenge"], w["version"])
        for w in result["warnings"]
        if w["code"] == "no_evaluation_endpoint"
    }
    assert {(MOTOR, v) for v in versions_of(MOTOR)} <= missing
    items = [
        item
        for item in result["steps"]["evaluation"]["challenges"]
        if item["id"] == MOTOR
    ]
    assert [item["version"] for item in items] == versions_of(MOTOR)
    for item in items:
        assert item["intake"] is None
        assert item["note"] == environment.NO_ENDPOINT.format(title=item["title"])
        assert item["unversioned_endpoint"] == unversioned[0]["message"]


# --- Review, the profile, setup and the prelaunch review, per version ---------------


def test_review_writes_one_versions_endpoint_and_says_the_other_has_none(
    tmp_path, state, head, monkeypatch
):
    publish(
        tmp_path,
        monkeypatch,
        [entry(MOTOR, version="1.2", intake_url=URL_12)],
        schema="v2",
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    result = setup.review({"confirm": True})
    cfg = profile(setup)
    assert cfg["version_intakes"] == {
        MOTOR: {"1.2": [{"intake_url": URL_12, "receiver_hotkey": HOTKEY}]}
    }
    assert "intakes" not in cfg and "receivers" not in cfg
    warned = {
        (w["challenge"], w.get("version"))
        for w in result["warnings"]
        if w["code"] == "no_evaluation_endpoint"
    }
    assert (MOTOR, "1.3") in warned and (MOTOR, "1.2") not in warned
    items = {
        (item["id"], item["version"]): item
        for item in result["steps"]["evaluation"]["challenges"]
    }
    assert (items[MOTOR, "1.2"]["intake"], items[MOTOR, "1.2"]["source"]) == (
        URL_12,
        "published",
    )
    assert items[MOTOR, "1.2"]["receiver_hotkey"] == HOTKEY
    assert items[MOTOR, "1.3"]["intake"] is None
    assert items[MOTOR, "1.3"]["note"] == environment.NO_ENDPOINT.format(
        title=items[MOTOR, "1.3"]["title"]
    )
    assert result["steps"]["evaluation"]["ready"] is False

    # The prelaunch review, per version.
    review = prelaunch.evaluation(cfg)
    by_version = {(i["challenge_id"], i["version"]): i for i in review["challenges"]}
    assert by_version[MOTOR, "1.2"]["status"] == "INTAKE_CONFIGURED"
    assert by_version[MOTOR, "1.2"]["source"] == "PUBLISHED"
    assert by_version[MOTOR, "1.2"]["intake"] == URL_12
    assert by_version[MOTOR, "1.2"]["receiver_pinned"] is True
    assert by_version[MOTOR, "1.3"]["status"] == "NONE_PUBLISHED"
    assert by_version[MOTOR, "1.3"]["next_step"] == environment.NO_ENDPOINT.format(
        title=by_version[MOTOR, "1.3"]["title"]
    )
    assert review["configured"] == "CONFIGURED_FOR_SOME"


def test_configured_for_all_counts_every_version(tmp_path, state, head, monkeypatch):
    every = intake_challenges()
    publish(
        tmp_path,
        monkeypatch,
        [
            entry(c["id"], version=c["version"], intake_url=f"{URL_12}/{i}")
            for i, c in enumerate(every)
        ],
        schema="v2",
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    cfg = profile(setup)
    assert prelaunch.evaluation(cfg)["configured"] == "CONFIGURED_FOR_ALL"
    # One version's endpoint removed: only that version is unconfigured.
    cfg["version_intakes"][MOTOR].pop("1.3")
    review = prelaunch.evaluation(cfg)
    assert review["configured"] == "CONFIGURED_FOR_SOME"
    statuses = {
        (i["challenge_id"], i["version"]): i["status"] for i in review["challenges"]
    }
    assert statuses[MOTOR, "1.3"] == "PUBLISHED_REVIEW_AGAIN"
    assert statuses[MOTOR, "1.2"] == "INTAKE_CONFIGURED"


def test_a_profile_names_a_challenges_intake_by_id_or_per_version(
    tmp_path, state, head, monkeypatch
):
    publish(
        tmp_path,
        monkeypatch,
        [entry(MOTOR, version="1.2", intake_url=URL_12)],
        schema="v2",
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    cfg = profile(setup)
    pair = [{"intake_url": URL_12, "receiver_hotkey": HOTKEY}]
    for bad in (
        # Named both ways: one version's submit could read the other's.
        {**cfg, "intakes": {MOTOR: URL_12}},
        {**cfg, "intakes": {MOTOR: URL_12}, "receivers": {MOTOR: HOTKEY}},
        # Each (id, version) a registered intake version, each list paired.
        {**cfg, "version_intakes": {MOTOR: {"9.9": pair}}},
        {**cfg, "version_intakes": {"no-such-challenge": {"1.2": pair}}},
        {**cfg, "version_intakes": {MOTOR: {"1.2": []}}},
        {**cfg, "version_intakes": {MOTOR: {"1.2": [{**pair[0], "extra": 1}]}}},
        {**cfg, "version_intakes": {MOTOR: {}}},
        {**cfg, "version_intakes": [pair]},
    ):
        with pytest.raises(ValueError):
            runner.validated_profile(json.loads(json.dumps(bad)))
    # A profile from before, naming intakes by id, validates and reads as before.
    legacy = {k: v for k, v in cfg.items() if k != "version_intakes"}
    legacy = {**legacy, "intakes": {MOTOR: URL_13}, "receivers": {MOTOR: OTHER}}
    assert runner.validated_profile(dict(legacy)) == legacy
    for version in versions_of(MOTOR):
        assert runner.intakes(for_version(legacy, MOTOR, version)) == {MOTOR: URL_13}


def test_an_own_intake_by_id_takes_no_published_version(
    tmp_path, state, head, monkeypatch
):
    from test_miner_setup_after_install import OWN, Intakes

    challenge, version = battery.CHALLENGE.challenge_id, battery.CHALLENGE.version
    publish(
        tmp_path,
        monkeypatch,
        [
            entry(challenge, version=version),
            entry(MOTOR, version="1.2", intake_url=URL_12),
        ],
        schema="v2",
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    setup.review(
        {"confirm": True, "intakes": {challenge: OWN}, "receiver_hotkey": HOTKEY}
    )
    cfg = profile(setup)
    # The miner's own intake, named by id, wins as before; Carbon's endpoint
    # for the other Challenge's version is written beside it.
    assert cfg["intakes"] == {challenge: OWN}
    assert set(cfg["version_intakes"]) == {MOTOR}


# --- each version's submit reads its own version's endpoint -------------------------


def _profile_args(version_intakes, **extra):
    return SimpleNamespace(
        intakes={},
        receivers={},
        intake_targets={},
        version_intakes=version_intakes,
        direct_intake_target=None,
        **extra,
    )


def test_each_motor_version_submits_to_its_own_versions_endpoint():
    args = _profile_args(
        {
            MOTOR: {
                "1.2": [{"intake_url": URL_12, "receiver_hotkey": HOTKEY}],
                "1.3": [{"intake_url": URL_13, "receiver_hotkey": OTHER}],
            }
        }
    )
    with keyed(key_for("1.2")):
        assert motor._direct_target(args) == {
            "intake_url": URL_12,
            "receiver_hotkey": HOTKEY,
        }
    with keyed(key_for("1.3")):
        assert motor._direct_target(args) == {
            "intake_url": URL_13,
            "receiver_hotkey": OTHER,
        }
    # Only 1.2 published: 1.3 has no endpoint, never 1.2's.
    only = _profile_args(
        {MOTOR: {"1.2": [{"intake_url": URL_12, "receiver_hotkey": HOTKEY}]}}
    )
    with keyed(key_for("1.3")):
        assert motor._direct_target(only) is None
    # The arguments the campaign was given are not changed.
    assert only.intakes == {} and only.receivers == {}


def test_the_runner_refuses_a_submit_whose_version_has_no_endpoint():
    cfg = {
        "paths": {},
        "version_intakes": {
            MOTOR: {"1.2": [{"intake_url": URL_12, "receiver_hotkey": HOTKEY}]}
        },
    }

    def manifest(version):
        return {"challenge": {"id": MOTOR, "version": version}}

    assert runner.evaluation_refusal(cfg, manifest("1.2")) is None
    assert runner.evaluation_refusal(cfg, manifest("1.3")) == "evaluation_unavailable"


def test_a_direct_campaign_counts_the_profiles_direct_target():
    # M1 E2E H9b: a direct campaign submits to `direct_intake_target` when the
    # profile names no per-Challenge intake (motor `_direct_target`), so the
    # pre-submit check must not refuse it; a non-direct campaign still is.
    cfg = {
        "paths": {},
        "direct_intake_target": {"intake_url": URL_12, "receiver_hotkey": HOTKEY},
    }
    manifest = {"challenge": {"id": MOTOR, "version": "1.2"}}
    assert runner.evaluation_refusal(cfg, manifest, direct=True) is None
    assert runner.evaluation_refusal(cfg, manifest) == "evaluation_unavailable"
    assert (
        runner.evaluation_refusal({"paths": {}}, manifest, direct=True)
        == "evaluation_unavailable"
    )


def test_setup_status_shows_the_direct_target_where_no_intake_is():
    # M1 E2E H12: a Challenge without an intake submits a direct campaign to
    # the profile's direct target, so the evaluation step names it there.
    target = {"intake_url": URL_12, "receiver_hotkey": HOTKEY}
    record = {"profile": {"intakes": {}}, "direct_intake_target": target}
    host = SimpleNamespace(_own_intakes=lambda record: {})
    items = environment.EnvironmentSetup._evaluation(host, record)["challenges"]
    assert items and all(item["intake"] is None for item in items)
    assert all(item["direct_intake"] == target for item in items)
    assert not any("note" in item for item in items)


def test_battery_reads_its_own_versions_endpoint_only():
    challenge, version = battery.CHALLENGE.challenge_id, battery.CHALLENGE.version
    pair = {"intake_url": URL_12, "receiver_hotkey": HOTKEY}
    args = _profile_args({challenge: {version: [pair]}})
    own = SimpleNamespace(args=battery._own_version(args))
    assert (battery._intake(own), battery._receiver(own)) == (URL_12, HOTKEY)
    elsewhere = _profile_args({challenge: {"0.0-other": [pair]}})
    own = SimpleNamespace(args=battery._own_version(elsewhere))
    assert (battery._intake(own), battery._receiver(own)) == (None, None)
    # Not named per version: the same arguments, read exactly as before.
    legacy = _profile_args({})
    legacy.intakes = {challenge: URL_13}
    assert battery._own_version(legacy) is legacy


def test_the_prelaunch_review_counts_the_direct_target():
    # M1 E2E U19: Review said "Unavailable today" for Motor 1.3 although its
    # direct campaign submits to the profile's direct target.
    cfg = {
        "paths": {},
        "direct_intake_target": {"intake_url": URL_12, "receiver_hotkey": HOTKEY},
    }
    review = prelaunch.evaluation(cfg)
    motor = [i for i in review["challenges"] if i["challenge_id"] == MOTOR]
    assert motor and all(i["status"] == "INTAKE_CONFIGURED" for i in motor)
    assert all(i["direct"] is True and i["intake"] == URL_12 for i in motor)
    plain = prelaunch.evaluation({"paths": {}})
    assert all(i["status"] != "INTAKE_CONFIGURED" for i in plain["challenges"])
