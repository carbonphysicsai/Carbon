"""R89: the direct door's request buckets per verified funder group (Validator-2 6 Nov 09:16 option b;
Release Architect 11:31 + Validator-2 11:32). Values here are TEST values only; the real ones are the owner's.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest
from test_c08_authenticated_miner_mcp import CONTEXT, NOW, _Verifier
from test_direct_recipe_intake import _signed
from test_direct_v3_durable_tasks import _fixture

from carbon.battery.intake import SnapshotWindow
from carbon.chain.models import MetagraphSnapshot, Participant
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import (
    AttemptLedger,
    direct_intake,
    direct_receiver,
    funder_map,
    request_buckets,
)
from carbon.challenge_validator.direct_intake import (
    RESEARCH_NAMESPACE,
    STATUS_TOOL,
    SUBMIT_PATH,
    DirectRecipeIntake,
)
from carbon.challenge_validator.request_buckets import (
    RequestBuckets,
    RequestBucketsUnset,
    claimed_hotkey,
)
from carbon.development_session.profile import digest
from carbon.transport.store import ReceiptJournal

TEST_VALUES = {
    "guard": {"rate_per_s": 0.001, "burst": 3},
    "group": {"rate_per_s": 0.001, "burst": 2},
    "chunks": {"rate_per_s": 0.001, "burst": 2},
}
GROUP_ID = "a" * 64


def _frozen():
    return RequestBuckets(TEST_VALUES, clock=lambda: 0.0)


# --- values: none defaulted, every gap refuses ------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "HUMAN_INPUT",
        0,
        -1,
        True,
        math.nan,
        math.inf,
        "1",
    ],
)
@pytest.mark.parametrize("kind", ["guard", "group", "chunks"])
@pytest.mark.parametrize("field", ["rate_per_s", "burst"])
def test_an_unset_or_invalid_value_refuses(kind, field, bad):
    block = json.loads(json.dumps(TEST_VALUES))
    block[kind][field] = bad
    with pytest.raises(RequestBucketsUnset) as refused:
        request_buckets.values(block)
    assert refused.value.code == "direct_intake_request_buckets_unset"


def test_a_missing_kind_or_extra_key_refuses():
    for block in (
        {k: v for k, v in TEST_VALUES.items() if k != "chunks"},
        {**TEST_VALUES, "peer": {"rate_per_s": 1, "burst": 1}},
        {**TEST_VALUES, "group": {"rate_per_s": 1}},
        {**TEST_VALUES, "group": {"rate_per_s": 1, "burst": 1, "extra": 0}},
        [],
    ):
        with pytest.raises(RequestBucketsUnset):
            request_buckets.values(block)
    with pytest.raises(RequestBucketsUnset):
        direct_receiver._request_buckets(
            {"request_buckets": {**TEST_VALUES, "guard": "HUMAN_INPUT"}}
        )


def test_no_block_means_no_request_buckets():
    assert direct_receiver._request_buckets({}) is None


def test_claimed_hotkey_is_one_well_formed_header_or_none():
    assert claimed_hotkey({"X-Bittensor-Hotkey": "miner"}) == "miner"
    assert claimed_hotkey({"x-bittensor-hotkey": "miner"}) == "miner"
    assert claimed_hotkey({}) is None
    assert claimed_hotkey({"X-Bittensor-Hotkey": "a b"}) is None
    assert claimed_hotkey({"X-Bittensor-Hotkey": "m" * 65}) is None
    assert (
        claimed_hotkey({"X-Bittensor-Hotkey": "a", "x-bittensor-hotkey": "b"}) is None
    )
    assert claimed_hotkey(None) is None


# --- the funder map ----------------------------------------------------------------------


def _map_bytes(groups, block=7):
    return json.dumps(
        {"schema": funder_map.SCHEMA, "block": block, "groups": groups}
    ).encode()


def test_unmapped_coldkeys_are_their_own_groups_and_never_show_the_ss58():
    empty = funder_map.FunderMap.empty()
    assert empty.group("cold") == empty.group("cold")
    assert empty.group("cold") != empty.group("cold3")
    assert "cold" not in empty.group("cold")


def test_a_map_joins_coldkeys_of_one_funder():
    loaded = funder_map.parse(_map_bytes({"cold": GROUP_ID, "cold3": GROUP_ID}))
    assert loaded.problem is None and loaded.block == 7
    assert loaded.group("cold") == loaded.group("cold3") == "f:" + GROUP_ID
    assert loaded.group("other") == funder_map.FunderMap.empty().group("other")


@pytest.mark.parametrize(
    "raw, problem",
    [
        (b"{", "funder_map_malformed"),
        (
            json.dumps({"schema": "x", "block": 1, "groups": {}}).encode(),
            "funder_map_schema",
        ),
        (_map_bytes({"cold": "not-hex"}), "funder_map_malformed"),
        (_map_bytes({"cold": GROUP_ID}, block=-1), "funder_map_malformed"),
        (_map_bytes({"bad key": GROUP_ID}), "funder_map_malformed"),
    ],
)
def test_a_bad_map_is_no_map_with_a_problem_never_a_refusal(raw, problem):
    loaded = funder_map.parse(raw)
    assert loaded.problem == problem
    assert loaded.group("cold") == funder_map.FunderMap.empty().group("cold")


def test_an_unreadable_map_file_is_no_map(tmp_path):
    assert funder_map.load(None).problem is None
    assert funder_map.load(tmp_path / "absent.json").problem == "funder_map_unreadable"


# --- the door ----------------------------------------------------------------------------


def _state():
    return MetagraphSnapshot(
        CONTEXT,
        10,
        "0x" + "2" * 64,
        NOW // 1_000_000,
        (
            Participant(0, "validator", "owner", 1),
            Participant(1, "miner", "cold", 2),
            Participant(2, "miner2", "cold", 3),
            Participant(3, "miner3", "cold3", 4),
        ),
    )


@pytest.fixture
def door(tmp_path, monkeypatch):
    request, provider_factory, discovery = _fixture(
        tmp_path / "direct", monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    state = _state()
    window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
    window.add(state)

    def build(buckets, groups=None):
        return DirectRecipeIntake(
            context=CONTEXT,
            receiver="validator",
            journal=ReceiptJournal(
                tmp_path / f"transport-{id(buckets)}.sqlite3", CONTEXT
            ),
            verifier=_Verifier(),
            window=window,
            discovery=discovery,
            provider_for=lambda owner: provider,
            attempt_ledger=AttemptLedger(root / f"ledger-{id(buckets)}.sqlite3"),
            request_buckets=buckets,
            funder_map=None if groups is None else funder_map.parse(_map_bytes(groups)),
            clock_ns=lambda: NOW,
        )

    counter = iter(range(1, 10_000))

    def post(intake, hotkey, *, forged=False, claimed=True, replay_of=None):
        if replay_of is not None:
            body, headers = replay_of
        else:
            n = next(counter)
            body, headers = _signed(
                state,
                request.challenge_key,
                STATUS_TOOL,
                {"submission_id": f"none-{n}"},
                request=f"r89-status-{n:04d}",
                nonce=NOW + n,
            )
            headers["hotkey"] = hotkey
            if claimed:
                headers["X-Bittensor-Hotkey"] = hotkey
            if forged:
                headers["body"] = digest(b"something else")
        answer = intake.handle("POST", SUBMIT_PATH, headers, body, "127.0.0.1")
        return answer, (body, headers)

    yield SimpleNamespace(build=build, post=post)
    provider.close()


def _rate_refused(answer):
    return answer.status == 429 and answer.body["refused"] == "rate"


def test_a_forged_flood_naming_a_member_cannot_429_the_real_hotkey(door):
    intake = door.build(_frozen())
    for _ in range(10):
        forged, _ = door.post(intake, "miner", forged=True)
        assert forged.status == 401 and forged.body["refused"] == "AUTH_BAD_SIGNATURE"
    real, _ = door.post(intake, "miner")
    assert not _rate_refused(real)
    # The flood went to the guard: an unattributable POST is now refused before its body.
    unattributed, _ = door.post(intake, "miner", claimed=False)
    assert _rate_refused(unattributed)


def test_a_replayed_request_charges_the_guard_not_the_victims_group(door):
    intake = door.build(_frozen())
    first, captured = door.post(intake, "miner")
    assert not _rate_refused(first)
    for _ in range(5):
        replay, _ = door.post(intake, "miner", replay_of=captured)
        assert replay.status == 401 and replay.body["refused"] == "AUTH_REPLAY"
    second, _ = door.post(intake, "miner")
    assert not _rate_refused(second)  # group burst 2: the replays took none of it
    third, _ = door.post(intake, "miner")
    assert _rate_refused(third)


def test_hotkeys_of_one_coldkey_share_a_group_and_another_funder_does_not(door):
    intake = door.build(_frozen())
    assert not _rate_refused(door.post(intake, "miner")[0])
    assert not _rate_refused(door.post(intake, "miner2")[0])
    assert _rate_refused(door.post(intake, "miner")[0])
    assert _rate_refused(door.post(intake, "miner2")[0])
    assert not _rate_refused(door.post(intake, "miner3")[0])


def test_the_funder_map_joins_two_coldkeys_into_one_bucket(door):
    intake = door.build(_frozen(), groups={"cold": GROUP_ID, "cold3": GROUP_ID})
    assert not _rate_refused(door.post(intake, "miner")[0])
    assert not _rate_refused(door.post(intake, "miner3")[0])
    assert _rate_refused(door.post(intake, "miner2")[0])


def test_a_map_reload_keeps_the_buckets(door):
    intake = door.build(_frozen())
    door.post(intake, "miner")
    door.post(intake, "miner")
    intake.funder_map = funder_map.parse(_map_bytes({}))
    assert _rate_refused(door.post(intake, "miner")[0])


def test_the_pre_body_peek_charges_nothing(door):
    buckets = _frozen()
    intake = door.build(buckets)
    group = intake.funder_map.group("cold")
    headers = {"X-Bittensor-Hotkey": "miner"}
    for _ in range(20):
        assert intake.admit_before_body("POST", "127.0.0.1", headers)
    assert buckets.charge_group(group, chunk=False)
    assert buckets.charge_group(group, chunk=False)
    assert not buckets.charge_group(group, chunk=False)
    assert buckets.charge_group(
        group, chunk=True
    )  # chunks still have tokens: the peek still admits
    assert intake.admit_before_body("POST", "127.0.0.1", headers)
    assert buckets.charge_group(group, chunk=True)
    assert not intake.admit_before_body("POST", "127.0.0.1", headers)
    # An unregistered claim is the guard's, not anyone's group.
    assert intake.admit_before_body(
        "POST", "127.0.0.1", {"X-Bittensor-Hotkey": "stranger"}
    )


def test_continuation_chunks_never_take_a_submits_tokens(door, monkeypatch):
    buckets = _frozen()
    intake = door.build(buckets)
    chunk_call = SimpleNamespace(
        operation="stage_research_source", request=SimpleNamespace(offset=8192)
    )
    monkeypatch.setattr(
        intake, "_continues_upload", lambda hotkey, request: request.offset > 0
    )
    first_call = SimpleNamespace(
        operation="stage_research_source", request=SimpleNamespace(offset=0)
    )
    calls = iter([chunk_call, chunk_call, chunk_call, first_call])
    monkeypatch.setattr(direct_intake, "decode_research_call", lambda call: next(calls))
    staged = SimpleNamespace(
        call=SimpleNamespace(tool=RESEARCH_NAMESPACE),
        receipt=SimpleNamespace(hotkey="miner", coldkey="cold"),
    )
    assert intake._verified_charge(staged)
    assert intake._verified_charge(staged)
    assert not intake._verified_charge(staged)  # this group's chunk bucket is empty
    assert intake._verified_charge(staged)  # a first chunk (offset 0) is a request
    assert not _rate_refused(
        door.post(intake, "miner")[0]
    )  # and a submit still has one


def test_gets_are_not_charged(door):
    buckets = _frozen()
    intake = door.build(buckets)
    # In-process GETs fall to the peer bucket as before (over HTTP a local-hop GET is charged nothing);
    # none touches the R89 buckets.
    for _ in range(5):
        assert intake.admit_before_body(
            "GET", "127.0.0.1", {"X-Bittensor-Hotkey": "miner"}
        )
    assert all(buckets.charge_guard("unattributed") for _ in range(3))
    group = intake.funder_map.group("cold")
    assert all(buckets.charge_group(group, chunk=False) for _ in range(2))


def test_without_request_buckets_the_door_keeps_the_shared_peer_bucket(door):
    intake = door.build(None)
    answers = [door.post(intake, f"miner{'' if i % 2 else '3'}")[0] for i in range(12)]
    assert [
        a for a in answers if _rate_refused(a)
    ]  # today's one shared bucket (burst 10)
    assert not any(_rate_refused(a) for a in answers[:10])


# --- a continuation is this owner's own upload at its current length (Validator-2B 7 Nov) ----------------------------


def _campaign(tmp_path):
    from test_direct_source_staging import _ledger

    return _ledger(tmp_path)


def test_only_a_chunk_at_the_owners_current_length_is_a_continuation(tmp_path):
    from test_direct_source_staging import _request

    from carbon.development_session.direct_source_staging import (
        continuation_at,
        stage_source,
    )
    from carbon.level4 import staging

    ledger = _campaign(tmp_path)
    body = b'{"documents":{}}'
    first = _request(staging.WORKSPACE_MANIFEST, body, 0, body[:8])
    assert not continuation_at(ledger, "alice", first)  # offset 0: a request
    second = _request(staging.WORKSPACE_MANIFEST, body, 8, body[8:12])
    assert not continuation_at(ledger, "alice", second)  # nothing staged yet
    stage_source(ledger, "alice", first)
    assert continuation_at(ledger, "alice", second)
    assert not continuation_at(ledger, "bob", second)  # another owner's upload
    replayed = _request(staging.WORKSPACE_MANIFEST, body, 4, body[4:8])
    assert not continuation_at(ledger, "alice", replayed)  # below the current length
    ahead = _request(staging.WORKSPACE_MANIFEST, body, 12, body[12:])
    assert not continuation_at(ledger, "alice", ahead)
    assert not continuation_at(ledger, "alice", SimpleNamespace(offset=8))


def test_an_empty_guard_and_a_forged_registered_flood_leave_the_real_hotkey_at_worst_503(
    door,
):
    # Validator-2B 7 Nov: with the guard empty, a forger naming registered hotkeys can contend for in-flight
    # slots (503 capacity) but never 429 the real hotkey.
    intake = door.build(_frozen())
    for _ in range(3):
        door.post(intake, "nobody", claimed=False)
    assert _rate_refused(door.post(intake, "nobody", claimed=False)[0])  # guard empty
    for hotkey in ("miner", "miner2", "miner3") * 4:
        forged, _ = door.post(intake, hotkey, forged=True)
        assert forged.status == 401
    real, _ = door.post(intake, "miner")
    assert real.status != 429
    # The in-flight cap is the only bound left on verified-looking traffic: full, it answers 503, never 429.
    from carbon.battery.intake import IN_FLIGHT

    for _ in range(IN_FLIGHT):
        assert intake.limits._flight.acquire(blocking=False)
    try:
        crowded, _ = door.post(intake, "miner")
        assert crowded.status == 503 and crowded.body["refused"] == "capacity"
    finally:
        for _ in range(IN_FLIGHT):
            intake.limits._flight.release()


def test_the_peek_writes_nothing():
    buckets = _frozen()
    group = funder_map.FunderMap.empty().group("cold")
    before = {k: dict(b._buckets) for k, b in buckets._kinds.items()}
    for _ in range(5):
        assert buckets.peek_group(group)
    assert {k: dict(b._buckets) for k, b in buckets._kinds.items()} == before


def test_the_hourly_line_carries_counts_only():
    now = [0.0]
    lines = []
    buckets = RequestBuckets(
        TEST_VALUES,
        clock=lambda: now[0],
        emit=lambda event, **f: lines.append((event, f)),
    )
    group = funder_map.FunderMap.empty().group("cold")
    for _ in range(4):
        buckets.charge_guard("unattributed")  # burst 3: the 4th is refused
    buckets.charge_guard("verify_failed")
    buckets.charge_group(group, chunk=False)
    buckets.charge_group(group, chunk=False)
    buckets.charge_group(group, chunk=False)
    buckets.note("capacity_503")
    assert lines == []
    now[0] = request_buckets.COUNTS_PERIOD_S
    buckets.note("capacity_503")
    ((event, fields),) = lines
    assert event == request_buckets.COUNTS_EVENT
    assert fields == {
        "period_s": 3600,
        "guard_unattributed": 4,
        "guard_verify_failed": 1,
        "guard_429": 2,
        "peek_429": 0,
        "group_429": 1,
        "chunk_429": 0,
        "capacity_503": 2,
    }
    assert "cold" not in repr(lines) and group not in repr(lines)


def test_a_full_in_flight_cap_is_counted(door):
    from carbon.battery.intake import IN_FLIGHT

    buckets = _frozen()
    intake = door.build(buckets)
    for _ in range(IN_FLIGHT):
        assert intake.limits._flight.acquire(blocking=False)
    try:
        assert door.post(intake, "miner")[0].status == 503
    finally:
        for _ in range(IN_FLIGHT):
            intake.limits._flight.release()
    assert buckets._counts["capacity_503"] == 1
