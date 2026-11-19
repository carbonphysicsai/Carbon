"""The public king card (`carbon.challenge_validator.crown_card`) under Validator-2's standing ruling
KING_STATS_DISCLOSURE_20261119: a closed allow-list rendered from the crowning grade's private breakdown, failing closed.
Every value is a SYNTHETIC fixture.
"""

from __future__ import annotations

import json
import os

import pytest

from carbon.challenge_validator import crown_card as kc
from carbon.challenge_validator import koth_public
from carbon.scoring import grade_breakdown as gb

TASK = "rtsk_" + "c" * 64
OTHER = "rtsk_" + "d" * 64
EXAM = "sha256:" + "7" * 64
CALLS = [0.0123 + i * 1e-5 for i in range(20)]
PUBLIC = {
    "public_outputs": ["torque_pkpk", "ke_ll_loaded"],
    "public_classes": ["H-1", "H-2"],
    "lane_classes": {"local": "validator class C03 (EPYC 4-core lane)"},
}


def _document(**change):
    values = {
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.8",
        "submission_id": TASK,
        "exam_key": EXAM,
        "contract_ids": {"physics_contract": "sha256:" + "8" * 64},
        "sets": {"set0": {"A": 0.61234, "D": 0.4321, "rows": 15}},
        "tasks": [{"task": 7, "D": 0.4321, "Z": 0.11, "oracle": 0.97}],
        "rule_flags": {"pool_physics": True, "speed": True, "native_motor_valid": True},
        "halves": {"A": 0.612345, "D": 0.432149},
        "outputs": [
            {
                "class": "H-1",
                "output": "torque_pkpk",
                "range": "in",
                "n": 16,
                "median": 0.012345,
                "p90": 0.0995,
            },
            {
                "class": "H-2",
                "output": "torque_pkpk",
                "range": "in",
                "n": 9,
                "median": 1234.5,
                "p90": 2000.0,
            },
            {
                "class": "H-3",
                "output": "torque_pkpk",
                "range": "out",
                "n": 3,
                "median": 0.5,
                "p90": 0.9,
            },
            {
                "class": "H-1",
                "output": "private_cell",
                "range": "in",
                "n": 4,
                "median": 0.3,
                "p90": 0.4,
            },
            {
                "class": "H-2",
                "output": "ke_ll_loaded",
                "range": "in",
                "n": 0,
                "median": None,
                "p90": None,
            },
        ],
        "speed": {
            "call_seconds": CALLS,
            "median_seconds": 0.0123951,
            "ceiling_seconds": 0.5,
            "passed": True,
            "lane": "local",
        },
        "clock": 1_800_000_000.0,
        **change,
    }
    return gb.breakdown(**values)


def _render(document=None, **change):
    arguments = {
        "crowned_task": TASK,
        "source": kc.OFFICIAL,
        "epoch": "E1",
        "pack_id": "motor-1.8-pack-e1",
        "code_sha": "7b99e87b",
        **PUBLIC,
        **change,
    }
    return kc.render(_document() if document is None else document, **arguments)


def test_the_card_is_the_pinned_allow_list_and_rounds_at_render():
    card = _render()
    assert set(card) == kc.CARD_KEYS
    assert card["halves"] == {
        "A": koth_public.shown_total(0.612345),
        "D": koth_public.shown_total(0.432149),
    }
    assert card["outputs"] == [
        {
            "output": "torque_pkpk",
            "class": "H-1",
            "metric": kc.METRIC,
            "median": 0.012,
            "p90": 0.1,
        },
        {
            "output": "torque_pkpk",
            "class": "H-2",
            "metric": kc.METRIC,
            "median": 1200.0,
            "p90": 2000.0,
        },
    ]
    assert card["speed"] == {
        "median_seconds": 0.012,
        "ceiling_seconds": 0.5,
        "passed": True,
        "class": "validator class C03 (EPYC 4-core lane)",
    }
    assert card["gates"] == dict.fromkeys(
        ["native_motor_valid", "pool_physics", "speed"], "PASS"
    )
    assert card["provenance"] == {
        "label": "official exam, epoch E1",
        "epoch": "E1",
        "pack_id": "motor-1.8-pack-e1",
        "graded_at": "2027-01-15T08:00:00Z",
        "code_sha": "7b99e87b",
    }


def test_nothing_the_ruling_refuses_reaches_the_public_bytes():
    shown = kc.dumps(_render()).decode() + kc.text(_render())
    for refused in (
        "set0",
        "menu/t07",
        "0.97",
        "0.11",
        "oracle",
        "rows",
        '"n"',
        "H-3",
        "private_cell",
        "max",
        "call_seconds",
        "local",
        TASK,
        EXAM,
        "0.0123951",
        "0.01231",
    ):
        assert refused not in shown, refused


@pytest.mark.parametrize(
    "change, code",
    [
        ({"crowned_task": OTHER}, "crown_card_not_the_crowned_grade"),
        ({"source": "remeasured"}, "crown_card_source_invalid"),
        (
            {"source": kc.RECOMPUTED, "graded_at": "2026-11-18T10:00:00Z"},
            "crown_card_recompute_not_self_checked",
        ),
        (
            {"source": kc.RECOMPUTED, "self_check_matched": True},
            "crown_card_graded_at_invalid",
        ),
        ({"graded_at": "2026-11-18T10:00:00Z"}, "crown_card_graded_at_invalid"),
        ({"lane_classes": {}}, "crown_card_speed_class_unnamed"),
        ({"lane_classes": {"local": "bad\nlabel"}}, "crown_card_lane_classes_invalid"),
        ({"public_outputs": ["../x"]}, "crown_card_public_names_invalid"),
        ({"epoch": "E 1"}, "crown_card_epoch_invalid"),
        ({"code_sha": "not-a-sha"}, "crown_card_code_sha_invalid"),
    ],
)
def test_a_render_outside_the_ruling_refuses_the_whole_card(change, code):
    with pytest.raises(kc.KingCardRefused) as refused:
        _render(**change)
    assert refused.value.code == code


def test_a_grade_with_a_failed_gate_or_no_halves_or_no_speed_is_never_a_card():
    for document, code in (
        (_document(rule_flags={"speed": False}), "crown_card_gate_not_passed"),
        (_document(halves={"A": None, "D": 0.0}), "crown_card_halves_missing"),
        (_document(speed=None), "crown_card_speed_missing"),
    ):
        with pytest.raises(kc.KingCardRefused) as refused:
            _render(document)
        assert refused.value.code == code


def test_a_tampered_breakdown_or_card_refuses():
    tampered = {**_document(), "extra": 1}
    with pytest.raises(kc.KingCardRefused) as refused:
        _render(tampered)
    assert refused.value.code == "crown_card_breakdown_invalid"
    unchecked = _document()
    unchecked["halves"] = {"A": float("nan"), "D": 0.1}
    with pytest.raises(kc.KingCardRefused):
        _render(unchecked)
    card = _render()
    for broken in (
        {**card, "sets": {}},
        {**card, "speed": {**card["speed"], "call_seconds": CALLS}},
        {**card, "outputs": [{**card["outputs"][0], "n": 16}]},
        {**card, "gates": {"speed": "FAIL"}},
    ):
        with pytest.raises(kc.KingCardRefused) as refused:
            kc.dumps(broken)
        assert refused.value.code == "crown_card_keys"


def test_a_recomputed_card_says_so_and_carries_the_original_grade_time():
    card = _render(
        source=kc.RECOMPUTED, self_check_matched=True, graded_at="2026-11-18T10:00:00Z"
    )
    assert (
        card["provenance"]["label"]
        == "recomputed from the kept grade, self-check matched"
    )
    assert card["provenance"]["graded_at"] == "2026-11-18T10:00:00Z"


def test_two_significant_digits_half_up():
    assert [kc.significant(v) for v in (0.012345, 0.0995, 1234.5, 0.0, 7.0, 0.015)] == [
        0.012,
        0.1,
        1200.0,
        0.0,
        7.0,
        0.015,
    ]
    assert kc.significant(None) is None


@pytest.mark.skipif(os.name != "posix", reason="owner-only directory modes are POSIX")
def test_the_cli_writes_the_card_its_text_and_the_receipt_naming_the_crowning_file(
    tmp_path,
):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "crown_card_render",
        Path(__file__).resolve().parents[2] / "scripts/dev/king_card_render.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    custody = tmp_path / "custody"
    custody.mkdir(mode=0o700)
    source = gb.write(custody, _document())
    record = tmp_path / "host-class.json"
    record.write_text(
        json.dumps(
            {"schema": kc.HOST_CLASS_SCHEMA, "id": "VALIDATOR-HOST-CLASS-EPYC-TEST-01"}
        )
    )
    out = tmp_path / "out"
    out.mkdir(mode=0o700)
    argv = [
        "--breakdown",
        str(source),
        "--crowned-task",
        TASK,
        "--source",
        "official",
        "--epoch",
        "E1",
        "--pack-id",
        "motor-1.8-pack-e1",
        "--code-sha",
        "7b99e87b",
        "--lane-class",
        f"local={record}",
        "--out",
        str(out),
    ]
    assert cli.main(argv) == 0
    card = json.loads((out / "king-card.json").read_bytes())
    assert kc.check_card(card) == card
    # the speed class is the record's device class name, never the lane's host
    assert card["speed"]["class"] == "VALIDATOR-HOST-CLASS-EPYC-TEST-01"
    receipt = json.loads((out / "king-card-receipt.json").read_bytes())
    assert receipt["breakdown_file"] == str(source.resolve())
    assert receipt["crowned_task"] == TASK
    assert receipt["registration"]["outputs"] == sorted(
        receipt["registration"]["outputs"]
    )
    assert receipt["lane_class_records"]["local"]["sha256"].startswith("sha256:")
    # a lane with no class record refuses (nothing written)
    bare = tmp_path / "out-bare"
    bare.mkdir(mode=0o700)
    argv_bare = [a for a in argv if a not in ("--lane-class", f"local={record}")]
    argv_bare[argv_bare.index(str(out))] = str(bare)
    assert cli.main(argv_bare) == 3
    assert not any(bare.iterdir())
    # a second render into the same directory refuses (nothing overwritten)
    assert cli.main(argv) == 3
    # the repeat grade's own file (its own task id) is never read as the crowning grade's
    repeat = gb.write(custody, _document(submission_id=OTHER))
    other_out = tmp_path / "out2"
    other_out.mkdir(mode=0o700)
    argv_repeat = [a if a != str(source) else str(repeat) for a in argv]
    argv_repeat[argv_repeat.index(str(out))] = str(other_out)
    assert cli.main(argv_repeat) == 3
    assert not any(other_out.iterdir())


def test_the_public_names_come_from_the_served_registration():
    from pathlib import Path

    from carbon.scoring import pool_version

    raw = Path(pool_version.CONSTANTS).read_bytes()
    outputs, classes = kc.public_names(raw, "electric-motor-magnetics", "1.8")
    entry = json.loads(raw)["versions"]["electric-motor-magnetics 1.8"]
    assert outputs == sorted(entry["physics"]["gate_threshold"])
    assert classes == entry["optimizer"]["coverage_class_vocabulary"]
    with pytest.raises(kc.KingCardRefused) as refused:
        kc.public_names(raw, "electric-motor-magnetics", "9.9")
    assert refused.value.code == "crown_card_registration_unreadable"


def test_a_lane_class_is_a_host_class_record_id_never_a_host():
    from pathlib import Path

    from carbon.scoring import pool_version

    record = Path(pool_version.CONSTANTS).parent / "EPYC7402P-VM-01.json"
    assert kc.lane_class(record.read_bytes()) == "VALIDATOR-HOST-CLASS-EPYC7402P-VM-01"
    for bad in (
        b"{}",
        b"not json",
        json.dumps(
            {"schema": kc.HOST_CLASS_SCHEMA, "id": "ssh://root@10.0.0.1"}
        ).encode(),
        json.dumps({"schema": "other", "id": "VALIDATOR-HOST-CLASS-X"}).encode(),
    ):
        with pytest.raises(kc.KingCardRefused) as refused:
            kc.lane_class(bad)
        assert refused.value.code == "crown_card_lane_class_record_invalid"


def test_the_text_says_error_as_a_multiple_of_the_exams_u_and_never_a_raw_error():
    shown = kc.text(_render())
    assert "error as a multiple of the exam's U" in shown
    assert "abs_error_over_u" not in shown


@pytest.mark.skipif(os.name != "posix", reason="owner-only directory modes are POSIX")
def test_a_lane_with_no_class_record_shows_class_not_recorded(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "crown_card_render",
        Path(__file__).resolve().parents[2] / "scripts/dev/king_card_render.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    custody = tmp_path / "custody"
    custody.mkdir(mode=0o700)
    source = gb.write(custody, _document())
    out = tmp_path / "out"
    out.mkdir(mode=0o700)
    argv = [
        "--breakdown",
        str(source),
        "--crowned-task",
        TASK,
        "--source",
        "official",
        "--epoch",
        "E1",
        "--pack-id",
        "motor-1.8-pack-e1",
        "--code-sha",
        "7b99e87b",
        "--lane-unrecorded",
        "local",
        "--out",
        str(out),
    ]
    assert cli.main(argv) == 0
    card = json.loads((out / "king-card.json").read_bytes())
    assert card["speed"]["class"] == kc.UNRECORDED_CLASS == "class not recorded"
    receipt = json.loads((out / "king-card-receipt.json").read_bytes())
    assert receipt["lane_class_records"] == {"local": {"file": None, "sha256": None}}
