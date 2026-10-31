"""The exam cadence registry written from the recalibration's lane rows (scripts/dev/exam_cadence_from_recal.py)."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from carbon.challenge_validator import exam_cap
from scripts.dev import exam_cadence_from_recal as tool

CLASS_RECORD = b'{"host_class": "fixture"}\n'


def _rebuilds(seconds):
    return [
        {
            "entry_id": f"entry{index % 3}",
            "seed": index,
            "repeat": 0,
            "lane_start_s": 1000.0 * index,
            "lane_release_s": 1000.0 * index + value,
        }
        for index, value in enumerate(seconds)
    ]


def _rows(per_challenge=None):
    seconds = per_challenge or {}
    return {
        "schema": tool.SCHEMA_IN,
        "challenges": {
            name: {"rebuilds": _rebuilds(seconds.get(name, [3600.0] * 10))}
            for name in tool.REQUIRED
        },
    }


def _raw(rows):
    return json.dumps(rows, sort_keys=True).encode()


def test_the_registry_values_follow_the_registered_formula():
    rows = _rows(
        {
            "f02": [1800.0] * 10,
            "chip-cold-plate": [3600.0 + 360.0 * i for i in range(10)],
        }
    )
    raw = _raw(rows)
    document = tool.build(raw, CLASS_RECORD, lanes=4)
    assert document["schema"] == exam_cap.REGISTRY_SCHEMA
    assert document["lanes"] == 4
    assert document["capacity_gpu_lane_hours_per_day"] == pytest.approx(4 * 24 * 0.7)
    hours = document["rebuild_gpu_lane_hours"]
    assert hours["f02"] == pytest.approx(0.5)
    # mean of 3600 + 360 i over i = 0..9 is 3600 + 360 * 4.5 = 5220 s
    assert hours["chip-cold-plate"] == pytest.approx(5220.0 / 3600.0)
    assert hours["electric-motor-magnetics"] == pytest.approx(1.0)
    assert document["measurement_digest"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert (
        document["class_record_digest"]
        == "sha256:" + hashlib.sha256(CLASS_RECORD).hexdigest()
    )
    assert set(document) == exam_cap._V2_KEYS


def test_the_written_file_is_accepted_by_the_registry_and_never_overwritten(tmp_path):
    out = tmp_path / "exam_cadence.json"
    digest = tool.write(tool.build(_raw(_rows()), CLASS_RECORD, lanes=2), out)
    cadence = exam_cap.registered_cadence(out)
    assert cadence["lanes"] == 2
    assert set(cadence["rebuild_gpu_lane_hours"]) == set(tool.REQUIRED)
    assert digest == "sha256:" + hashlib.sha256(out.read_bytes()).hexdigest()
    with pytest.raises(tool.CadenceError, match="overwrite"):
        tool.write(tool.build(_raw(_rows()), CLASS_RECORD, lanes=2), out)


def test_this_tool_never_overwrites_the_committed_registry():
    # The committed file is a reviewed change of its own; the tool writes a candidate beside it and refuses to replace it.
    before = exam_cap.REGISTRY.read_bytes()
    with pytest.raises(tool.CadenceError, match="overwrite"):
        tool.write(tool.build(_raw(_rows()), CLASS_RECORD, lanes=2), exam_cap.REGISTRY)
    assert exam_cap.REGISTRY.read_bytes() == before


@pytest.mark.parametrize("count", [0, 9])
def test_fewer_than_ten_rebuilds_are_refused(count):
    rows = _rows()
    rows["challenges"]["f02"]["rebuilds"] = rows["challenges"]["f02"]["rebuilds"][
        :count
    ]
    with pytest.raises(tool.CadenceError, match="f02: at least 10"):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1)


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda r: r.pop("lane_start_s"), "lane_start_s"),
        (lambda r: r.pop("lane_release_s"), "lane_release_s"),
        (lambda r: r.update(lane_release_s=None), "lane_release_s"),
        (lambda r: r.update(lane_start_s="12"), "lane_start_s"),
        (lambda r: r.update(lane_start_s=True), "lane_start_s"),
        (lambda r: r.update(lane_release_s=r["lane_start_s"]), "after lane_start_s"),
        (
            lambda r: r.update(lane_release_s=r["lane_start_s"] - 1),
            "after lane_start_s",
        ),
        (lambda r: r.pop("entry_id"), "entry_id, seed and repeat"),
        (lambda r: r.pop("seed"), "entry_id, seed and repeat"),
    ],
)
def test_any_missing_or_invalid_timing_field_is_refused(mutate, match):
    rows = _rows()
    mutate(rows["challenges"]["electric-motor-magnetics"]["rebuilds"][3])
    with pytest.raises(tool.CadenceError, match=match):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1)


def test_a_non_finite_timing_is_refused():
    rows = _rows()
    rows["challenges"]["f02"]["rebuilds"][0]["lane_release_s"] = float("nan")
    raw = json.dumps(
        rows
    ).encode()  # Python writes NaN; the reader must still refuse it
    with pytest.raises(tool.CadenceError):
        tool.build(raw, CLASS_RECORD, lanes=1)


def test_a_repeated_rebuild_is_refused():
    rows = _rows()
    rebuilds = rows["challenges"]["f08-ribbed-bracket"]["rebuilds"]
    rebuilds[1] = copy.deepcopy(rebuilds[0])
    with pytest.raises(tool.CadenceError, match="listed twice"):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1)


def test_a_launch_challenge_without_rows_is_refused():
    rows = _rows()
    del rows["challenges"]["chip-cold-plate"]
    with pytest.raises(tool.CadenceError, match="chip-cold-plate"):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1)


@pytest.mark.parametrize("lanes", [0, -1, 1.5, True, "2"])
def test_the_lane_count_is_a_whole_number_of_at_least_one(lanes):
    with pytest.raises(tool.CadenceError, match="lanes"):
        tool.build(_raw(_rows()), CLASS_RECORD, lanes=lanes)


def test_an_empty_class_record_or_wrong_schema_is_refused():
    with pytest.raises(tool.CadenceError, match="class record"):
        tool.build(_raw(_rows()), b"", lanes=1)
    rows = _rows()
    rows["schema"] = "carbon.recal-lane-rows.v0"
    with pytest.raises(tool.CadenceError, match="schema"):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1)
    with pytest.raises(tool.CadenceError, match="not JSON"):
        tool.build(b"{", CLASS_RECORD, lanes=1)


def test_the_command_writes_the_file_and_prints_digests(tmp_path, capsys):
    rows, record, out = (
        tmp_path / "rows.json",
        tmp_path / "class.json",
        tmp_path / "out.json",
    )
    rows.write_bytes(_raw(_rows()))
    record.write_bytes(CLASS_RECORD)
    argv = [
        "--lane-rows",
        str(rows),
        "--class-record",
        str(record),
        "--lanes",
        "3",
        "--out",
        str(out),
    ]
    assert tool.main(argv) == 0
    printed = json.loads(capsys.readouterr().out)
    assert (
        printed["measurement_digest"]
        == "sha256:" + hashlib.sha256(rows.read_bytes()).hexdigest()
    )
    assert exam_cap.registered_cadence(out)["lanes"] == 3
    assert tool.main(argv) == 2  # the output exists: refused, nothing rewritten
    assert "REFUSED" in capsys.readouterr().err


# --- --challenges: a partial registry ------------------------------------------------------------------------------------


def test_named_challenges_alone_are_written_and_named_in_the_source():
    raw = _raw(_rows())  # the rows file carries all four; only the named two are valued
    document = tool.build(
        raw, CLASS_RECORD, lanes=1, challenges=["f08-ribbed-bracket", "f02"]
    )
    assert set(document["rebuild_gpu_lane_hours"]) == {"f08-ribbed-bracket", "f02"}
    assert "Challenges included: f02, f08-ribbed-bracket" in document["source"]
    assert document["measurement_digest"] == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_a_named_challenge_needs_ten_rebuilds_but_an_unnamed_one_need_not_have_rows():
    rows = _rows()
    del rows["challenges"]["chip-cold-plate"]  # not named, so not required
    rows["challenges"]["f02"]["rebuilds"] = rows["challenges"]["f02"]["rebuilds"][:9]
    with pytest.raises(tool.CadenceError, match="f02: at least 10"):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1, challenges=["f02"])
    ok = tool.build(
        _raw(rows), CLASS_RECORD, lanes=1, challenges=["f08-ribbed-bracket"]
    )
    assert set(ok["rebuild_gpu_lane_hours"]) == {"f08-ribbed-bracket"}
    with pytest.raises(tool.CadenceError, match="chip-cold-plate"):
        tool.build(_raw(rows), CLASS_RECORD, lanes=1, challenges=["chip-cold-plate"])


@pytest.mark.parametrize("challenges", [[], [""], ["not-registered"], [3], "f02"])
def test_a_bad_challenge_list_is_refused(challenges):
    with pytest.raises(tool.CadenceError, match="challenges"):
        tool.build(_raw(_rows()), CLASS_RECORD, lanes=1, challenges=challenges)


def test_the_registry_accepts_a_partial_file_and_the_cap_refuses_the_one_left_out(
    tmp_path,
):
    from carbon.challenge_validator.ledger import AttemptLedger

    out = tmp_path / "exam_cadence.json"
    tool.write(
        tool.build(
            _raw(_rows()),
            CLASS_RECORD,
            lanes=2,
            challenges=["f08-ribbed-bracket", "electric-motor-magnetics", "f02"],
        ),
        out,
    )
    cadence = exam_cap.registered_cadence(out)
    assert set(cadence["rebuild_gpu_lane_hours"]) == {
        "f08-ribbed-bracket",
        "electric-motor-magnetics",
        "f02",
    }
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    cap = exam_cap.ExamCap(
        AttemptLedger(directory / "attempts.sqlite3"), cadence=cadence
    )

    def reserve(challenge_id):
        return cap.reserve(
            hotkey="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            challenge_id=challenge_id,
            challenge_version="1.0",
            exam_key="sha256:" + "1" * 64,
            submission_id="rtsk_0",
            block=0,
        )

    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        reserve("chip-cold-plate")  # left out: a typed refusal, no default value
    assert refused.value.code == "exam_cap_unregistered"
    assert reserve("f02")  # a named one still reserves a slot


def test_the_command_takes_a_challenge_list(tmp_path, capsys):
    rows, record = tmp_path / "rows.json", tmp_path / "class.json"
    rows.write_bytes(_raw(_rows()))
    record.write_bytes(CLASS_RECORD)
    argv = ["--lane-rows", str(rows), "--class-record", str(record), "--lanes", "2"]
    listed = ["--challenges", "f02, f08-ribbed-bracket", "--out", str(tmp_path / "a")]
    assert tool.main([*argv, *listed]) == 0
    assert set(json.loads(capsys.readouterr().out)["rebuild_gpu_lane_hours"]) == {
        "f02",
        "f08-ribbed-bracket",
    }
    bad = ["--challenges", "nope", "--out", str(tmp_path / "b")]
    assert tool.main([*argv, *bad]) == 2


# --- --provisional / --min-rebuilds ------------------------------------------------------------------------------------


def _few(count, **per_challenge):
    rows = _rows()
    for name in tool.REQUIRED:
        rows["challenges"][name]["rebuilds"] = _rebuilds(
            [3600.0] * per_challenge.get(name, count)
        )
    return rows


def test_a_provisional_run_at_three_rebuilds_is_accepted_and_marked(tmp_path):
    document = tool.build(
        _raw(_few(3)), CLASS_RECORD, lanes=1, provisional=True, min_rebuilds=3
    )
    assert document["source"].startswith("PROVISIONAL (n=3 rebuilds per Challenge): ")
    assert document["schema"] == exam_cap.REGISTRY_SCHEMA
    assert set(document) == exam_cap._V2_KEYS
    assert ">= 3 rebuilds" in document["source"]
    out = tmp_path / "exam_cadence.json"
    tool.write(document, out)
    assert exam_cap.registered_cadence(out)["rebuild_gpu_lane_hours"]["f02"] == 1.0


def test_the_prefix_names_the_fewest_rebuilds_any_included_challenge_rests_on():
    rows = _few(5, f02=3)
    document = tool.build(
        _raw(rows), CLASS_RECORD, lanes=1, provisional=True, min_rebuilds=3
    )
    assert document["source"].startswith("PROVISIONAL (n=3 rebuilds per Challenge): ")


@pytest.mark.parametrize("floor", [2, 1, 0, -1])
def test_a_provisional_run_below_three_is_refused(floor):
    with pytest.raises(tool.CadenceError, match="at least 3"):
        tool.build(
            _raw(_few(3)), CLASS_RECORD, lanes=1, provisional=True, min_rebuilds=floor
        )


@pytest.mark.parametrize("floor", [3, 5, 9])
def test_fewer_than_ten_without_provisional_is_refused(floor):
    with pytest.raises(tool.CadenceError, match="only with --provisional"):
        tool.build(_raw(_few(floor)), CLASS_RECORD, lanes=1, min_rebuilds=floor)


def test_a_provisional_challenge_below_its_own_minimum_is_refused():
    with pytest.raises(tool.CadenceError, match="f02: at least 3"):
        tool.build(
            _raw(_few(3, f02=2)),
            CLASS_RECORD,
            lanes=1,
            provisional=True,
            min_rebuilds=3,
        )


def test_the_default_is_unchanged_and_not_marked():
    with pytest.raises(tool.CadenceError, match=": at least 10 rebuilds"):
        tool.build(_raw(_few(9)), CLASS_RECORD, lanes=1)
    with pytest.raises(tool.CadenceError, match=": at least 10 rebuilds"):
        tool.build(_raw(_few(9)), CLASS_RECORD, lanes=1, provisional=True)
    plain = tool.build(_raw(_few(10)), CLASS_RECORD, lanes=1)
    assert not plain["source"].startswith("PROVISIONAL")
    assert ">= 10 rebuilds" in plain["source"]
    marked = tool.build(_raw(_few(10)), CLASS_RECORD, lanes=1, provisional=True)
    assert marked["source"].startswith("PROVISIONAL (n=10 rebuilds per Challenge): ")


def test_a_minimum_above_ten_is_honoured_without_provisional():
    with pytest.raises(tool.CadenceError, match="at least 12"):
        tool.build(_raw(_few(10)), CLASS_RECORD, lanes=1, min_rebuilds=12)
    ok = tool.build(_raw(_few(12)), CLASS_RECORD, lanes=1, min_rebuilds=12)
    assert ">= 12 rebuilds" in ok["source"]


@pytest.mark.parametrize("value", [True, 3.0, "3"])
def test_the_minimum_is_a_whole_number(value):
    with pytest.raises(tool.CadenceError, match="min_rebuilds"):
        tool.build(
            _raw(_few(3)), CLASS_RECORD, lanes=1, provisional=True, min_rebuilds=value
        )


@pytest.mark.parametrize("value", [None, 1, "yes"])
def test_provisional_is_true_or_false(value):
    with pytest.raises(tool.CadenceError, match="provisional"):
        tool.build(_raw(_few(10)), CLASS_RECORD, lanes=1, provisional=value)


def test_the_command_takes_both_flags(tmp_path, capsys):
    rows, record = tmp_path / "rows.json", tmp_path / "class.json"
    rows.write_bytes(_raw(_few(3)))
    record.write_bytes(CLASS_RECORD)
    argv = ["--lane-rows", str(rows), "--class-record", str(record), "--lanes", "1"]
    out = tmp_path / "ok.json"
    assert (
        tool.main([*argv, "--provisional", "--min-rebuilds", "3", "--out", str(out)])
        == 0
    )
    capsys.readouterr()
    assert json.loads(out.read_text())["source"].startswith("PROVISIONAL (n=3 ")
    assert tool.main([*argv, "--min-rebuilds", "3", "--out", str(tmp_path / "b")]) == 2
    assert "only with --provisional" in capsys.readouterr().err
    refused = ["--provisional", "--min-rebuilds", "2", "--out", str(tmp_path / "c")]
    assert tool.main([*argv, *refused]) == 2
    assert tool.main([*argv, "--out", str(tmp_path / "d")]) == 2  # default: 3 < 10
