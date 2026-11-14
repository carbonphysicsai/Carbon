"""OWNER-PROBING-COUNTERS-01 (a): the exam allowance shared per funder. Real `AttemptLedger`, `ExamCap`,
`SnapshotWindow` and `funder_map`; every policy value here is a TEST value (the real ones are the owner's).
"""

from __future__ import annotations

import json

import pytest
from test_c08_authenticated_miner_mcp import CONTEXT, NOW

from carbon.battery.intake import SnapshotWindow
from carbon.chain.models import MetagraphSnapshot, Participant
from carbon.challenge_validator import allowance_groups, exam_cap, funder_map
from carbon.challenge_validator.exam_cap import ExamCap, ExamCapRefused
from carbon.challenge_validator.ledger import AttemptLedger

CHALLENGE, VERSION, EXAM = "electric-motor-magnetics", "1.8", "sha256:" + "1" * 64
BLOCK = 10_000  # one epoch for every submission below unless stated
GROUP_ID = "a" * 64
POLICY = {
    "unmapped_coldkey": "per_coldkey",
    "unresolved_hotkey": "per_hotkey",
    "max_map_age_blocks": 7200,
}


def _cadence():
    return {
        "capacity_gpu_lane_hours_per_day": 1000.0,
        "rebuild_gpu_lane_hours": {CHALLENGE: 1.0},
        "lanes": 1,
        "measurement_digest": "sha256:" + "a" * 64,
        "class_record_digest": "sha256:" + "b" * 64,
    }


def _window(block=BLOCK):
    window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
    window.add(
        MetagraphSnapshot(
            CONTEXT,
            block,
            "0x" + "2" * 64,
            NOW // 1_000_000,
            (
                Participant(0, "validator", "owner", 1),
                Participant(1, "hk1", "cold", 2),
                Participant(2, "hk2", "cold", 3),
                Participant(3, "hk3", "cold3", 4),
            ),
        )
    )
    return window


def _map(groups, block=BLOCK):
    return funder_map.parse(
        json.dumps(
            {"schema": funder_map.SCHEMA, "block": block, "groups": groups}
        ).encode()
    )


@pytest.fixture
def cap(tmp_path):
    (tmp_path / "ledger").mkdir(mode=0o700)
    ledger = AttemptLedger(tmp_path / "ledger" / "attempts.sqlite3")
    yield ExamCap(ledger, cadence=_cadence())
    exam_cap.install_grouping(None)


def _install(policy=POLICY, current=None, window=None, emit=None, clock=None):
    kwargs = {"emit": emit} if emit else {}
    if clock:
        kwargs["clock"] = clock
    grouping = allowance_groups.Grouping(
        policy,
        window or _window(),
        lambda: current or funder_map.FunderMap.empty(),
        **kwargs,
    )
    exam_cap.install_grouping(grouping)
    return grouping


_N = iter(range(10_000))


def _grade(cap, hotkey, block=BLOCK):
    """Reserve + count one graded submission; returns the reservation, or raises `ExamCapRefused`."""
    sid = f"rtsk_{next(_N):064x}"
    row = cap.reserve(
        hotkey=hotkey,
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        exam_key=EXAM,
        submission_id=sid,
        block=block,
    )
    cap.settle(row, "SCORED_DEVELOPMENT_CANDIDATE")
    return row


def _refused(cap, hotkey, code, block=BLOCK):
    with pytest.raises(ExamCapRefused) as refused:
        _grade(cap, hotkey, block)
    assert refused.value.code == code


# --- policy: every value the owner's, none defaulted -------------------------------------------------------------


@pytest.mark.parametrize(
    "field, bad",
    [
        ("unmapped_coldkey", "HUMAN_INPUT"),
        ("unmapped_coldkey", None),
        ("unmapped_coldkey", "per_hotkey"),
        ("unresolved_hotkey", "HUMAN_INPUT"),
        ("unresolved_hotkey", "per_coldkey"),
        ("max_map_age_blocks", "HUMAN_INPUT"),
        ("max_map_age_blocks", 0),
        ("max_map_age_blocks", True),
        ("max_map_age_blocks", 1.5),
    ],
)
def test_an_unset_or_invalid_policy_value_refuses(field, bad):
    with pytest.raises(allowance_groups.AllowanceGroupsUnset):
        allowance_groups.policy({**POLICY, field: bad})


def test_a_missing_or_extra_key_refuses_and_no_block_means_no_grouping():
    for block in (
        {k: v for k, v in POLICY.items() if k != "max_map_age_blocks"},
        {**POLICY, "x": 1},
        [],
    ):
        with pytest.raises(allowance_groups.AllowanceGroupsUnset):
            allowance_groups.policy(block)
    assert allowance_groups.from_config({}, _window(), lambda: None) is None


# --- the rule --------------------------------------------------------------------------------------------------------


def test_without_a_grouping_every_hotkey_keeps_its_own_slot(cap):
    _grade(cap, "hk1")
    _grade(cap, "hk2")  # same coldkey, still its own slot: exactly as before
    with cap.ledger._db() as db:
        assert {r[0] for r in db.execute("SELECT group_id FROM exam_graded")} == {None}
    assert exam_cap.plain_text("epoch_limit_reached").startswith(
        "One graded exam per Challenge per round, and this"
    )


def test_hotkeys_of_one_coldkey_share_the_round_and_another_coldkey_does_not(cap):
    _install()
    _grade(cap, "hk1")
    _refused(cap, "hk2", "epoch_limit_reached")
    _grade(cap, "hk3")
    _grade(cap, "hk2", block=BLOCK + 360)  # the next round is open again


def test_the_funder_map_joins_two_coldkeys(cap):
    _install(current=_map({"cold": GROUP_ID, "cold3": GROUP_ID}))
    _grade(cap, "hk3")
    _refused(cap, "hk1", "epoch_limit_reached")


def test_m_counts_groups_not_hotkeys(cap):
    _install()
    _grade(cap, "hk1")
    _grade(cap, "hk2", block=BLOCK + 360)
    assert cap.allowance(hotkey="hk1", block=BLOCK + 360)["active_miners"] == 1
    _grade(cap, "hk3")
    assert cap.allowance(hotkey="hk1", block=BLOCK + 360)["active_miners"] == 2
    _install(current=_map({"cold": GROUP_ID, "cold3": GROUP_ID}))
    assert (
        cap.allowance(hotkey="hk1", block=BLOCK + 360)["active_miners"] == 3
    )  # earlier rows keep their groups


def test_a_stale_or_bad_map_is_per_coldkey_never_a_refusal(cap):
    lines = []
    _install(
        policy={**POLICY, "unmapped_coldkey": "refuse"},
        current=_map({"cold": GROUP_ID, "cold3": GROUP_ID}, block=BLOCK - 7201),
        emit=lambda event, **f: lines.append(f),
    )
    _grade(cap, "hk1")
    _grade(cap, "hk3")  # the stale map does not join them, and nobody is refused
    _install(
        policy={**POLICY, "unmapped_coldkey": "refuse"}, current=funder_map.parse(b"{")
    )
    _grade(cap, "hk3", block=BLOCK + 360)


def test_unmapped_refuse_applies_only_under_a_usable_map(cap):
    strict = {**POLICY, "unmapped_coldkey": "refuse"}
    _install(policy=strict, current=_map({"cold": GROUP_ID}))
    _grade(cap, "hk1")
    _refused(cap, "hk3", "allowance_group_unmapped")
    told = cap.admission_refusal(
        hotkey="hk3",
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        exam_key=EXAM,
        submission_id="rtsk_" + "f" * 64,
        block=BLOCK,
    )
    assert (
        told["code"] == "allowance_group_unmapped"
        and "not yet in the validator's funder map" in told["message"]
    )
    _install(policy=strict)  # no map at all: per coldkey, never everyone refused
    _grade(cap, "hk3")


def test_an_unresolved_hotkey_follows_its_policy(cap):
    _install()
    _grade(cap, "stranger")  # not in the snapshot: its own hotkey, as before
    _install(policy={**POLICY, "unresolved_hotkey": "refuse"})
    _refused(cap, "stranger", "allowance_group_unresolved", block=BLOCK + 360)
    _install(
        window=SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
    )  # no snapshot at all: per hotkey
    _grade(cap, "hk1", block=BLOCK + 720)
    _grade(cap, "hk2", block=BLOCK + 720)


def test_not_retroactive_an_earlier_row_stays_with_its_own_hotkey(cap):
    _grade(cap, "hk1")  # filed before the grouping
    _install()
    _grade(cap, "hk2")  # hk1's earlier row is not its group's
    _refused(cap, "hk1", "epoch_limit_reached")  # but it still counts for hk1 itself


def test_the_admission_check_reads_the_group(cap):
    _install()
    _grade(cap, "hk1")
    told = cap.admission_refusal(
        hotkey="hk2",
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        exam_key=EXAM,
        submission_id="rtsk_" + "e" * 64,
        block=BLOCK,
    )
    assert told["code"] == "epoch_limit_reached"
    assert "same coldkey" in told["message"] and "funder" not in told["message"]


def test_a_regrade_is_never_grouped_or_refused(cap):
    _install(policy={**POLICY, "unresolved_hotkey": "refuse"})
    row = cap.reserve(
        hotkey="stranger",
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        exam_key=EXAM,
        submission_id="rtsk_" + "d" * 64,
        block=None,
        regrade=True,
    )
    assert row


def test_the_hourly_line_carries_counts_only(cap):
    now, lines = [0.0], []
    _install(
        policy={**POLICY, "unmapped_coldkey": "refuse"},
        current=_map({"cold": GROUP_ID}),
        emit=lambda event, **f: lines.append((event, f)),
        clock=lambda: now[0],
    )
    _grade(cap, "hk1")
    _refused(cap, "hk3", "allowance_group_unmapped")
    _grade(cap, "stranger")
    assert lines == []
    now[0] = allowance_groups.COUNTS_PERIOD_S
    _grade(cap, "hk2", block=BLOCK + 360)
    ((event, fields),) = lines
    assert event == allowance_groups.COUNTS_EVENT
    assert fields == {
        "period_s": 3600,
        "funder": 2,
        "coldkey": 0,
        "own_hotkey": 1,
        "map_unusable": 0,
        "refused_unmapped": 1,
        "refused_unresolved": 0,
    }
    assert all(
        s not in repr(lines)
        for s in ("cold3", "hk1", "hk2", "hk3", "stranger", GROUP_ID)
    )


def test_a_map_merge_never_frees_a_slot_for_the_merged_hotkey(cap):
    _install()
    _grade(cap, "hk3")  # filed under cold3's own group
    _install(
        current=_map({"cold": GROUP_ID, "cold3": GROUP_ID})
    )  # the refresh merges cold3 into a funder
    _refused(
        cap, "hk3", "epoch_limit_reached"
    )  # its earlier row still counts for itself
    _grade(
        cap, "hk1"
    )  # its new sibling: the earlier row is not theirs (not retroactive)


def test_the_map_file_is_re_read_when_it_changes(tmp_path):
    import os

    path = tmp_path / "funder-map.json"
    path.write_bytes(
        json.dumps({"schema": funder_map.SCHEMA, "block": 1, "groups": {}}).encode()
    )
    os.chmod(path, 0o600)
    watched = funder_map.Watched(path)
    first = watched.current()
    assert first.groups == {} and watched.current() is first  # unchanged: no re-read
    path.write_bytes(
        json.dumps(
            {"schema": funder_map.SCHEMA, "block": 2, "groups": {"cold": GROUP_ID}}
        ).encode()
    )
    os.utime(path, ns=(10**18, 10**18))
    second = watched.current()
    assert second.block == 2 and second.group("cold") == "f:" + GROUP_ID
    path.write_bytes(b"{")
    os.utime(path, ns=(2 * 10**18, 2 * 10**18))
    assert (
        watched.current().problem == "funder_map_malformed"
    )  # never the old map silently kept
    assert funder_map.Watched(None).current().problem is None


def test_the_grouped_sentences_are_miner_x_b_s_final_wording():
    from carbon.challenge_validator.exam_cap import GROUPED_LIMIT_TEXT, LIMIT_TEXT

    assert set(GROUPED_LIMIT_TEXT) == {
        "epoch_limit_reached",
        "exam_daily_allowance_reached",
        "allowance_group_unmapped",
        "allowance_group_unresolved",
    }
    assert "{when}" in GROUPED_LIMIT_TEXT["epoch_limit_reached"]
    for text in GROUPED_LIMIT_TEXT.values():
        # true at admission AND at grading: a submission refused at grading has used a build, never a grade or a slot
        assert "was not graded" in text and "graded-exam slot" in text
        assert (
            "that build was spent" in text
            or "a build" in text
            or "had been built" in text
        )
        assert "Nothing was built" not in text
        assert (
            "wallet" not in text and "funded from" not in text and "source" not in text
        )
    # the grouped round / day sentences name the same coldkey only
    for code in ("epoch_limit_reached", "exam_daily_allowance_reached"):
        assert "same coldkey" in GROUPED_LIMIT_TEXT[code]
        assert "funder" not in GROUPED_LIMIT_TEXT[code]
    assert set(LIMIT_TEXT) == {
        "epoch_limit_reached",
        "exam_daily_allowance_reached",
    }  # ungrouped text unchanged
