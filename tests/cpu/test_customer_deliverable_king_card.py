"""Per-king Motor card: synthetic boards and facts only (no door, no custody, no hidden value)."""

from __future__ import annotations

import copy
import datetime
import json

import pytest

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb
from carbon.motor import domain
from scripts.dev.customer_deliverable import king_card as kc

KING = "5" + "K" * 47
OTHER = "5" + "C" * 47
MARGIN = 0.0129
NOISE = {"value": MARGIN, "measurement_digest": "sha256:" + "a" * 64}
KING_EXACT = 0.77951
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
SIGNER = lb.LaunchBoardKey(bytes(range(32)))
OTHER_SIGNER = lb.LaunchBoardKey(bytes(range(1, 33)))
CHALLENGE = "electric-motor-magnetics"


def _board(*, king=True, v6=True, signer=SIGNER):
    make = kp.document_v3 if v6 else kp.document_v2
    document = make(
        challenge_id=CHALLENGE,
        challenge_version="1.8",
        exam_version_label="motor-exam",
        king={"hotkey": KING, "total": KING_EXACT, "since_epoch": 12} if king else None,
        rebuild_noise=NOISE,
        baseline_total=None if king else 0.5,
    )
    rows = (
        [(KING, {"total": lb.floor9(0.77)}, {"status": "IMPROVED", "gate_names": []})]
        if king
        else []
    )
    return lb.build(
        king_document=document,
        rows=rows,
        network="mainnet",
        key=signer,
        version=3,
        now=NOW,
        crown_changes=[],
        exact_totals={KING: KING_EXACT} if king else {},
        rebuild_noise=NOISE,
        stability="STABLE" if king else None,
        crowned_utc="2027-01-15T08:00:00Z" if king else None,
        v6=v6,
    )


def _aggregate(output="mean_torque", n=24, unit="relative"):
    return {
        "output": output,
        "n": n,
        "median": 0.01,
        "p90": 0.03,
        "ci95": [0.008, 0.012],
        "unit": unit,
    }


def _facts(**changes):
    facts = {
        "schema": kc.FACTS_SCHEMA,
        "task_id": "rtsk_0123abcd",
        "uid": 7,
        "hotkey": KING,
        "model": {
            "class": "physics-solver graph",
            "parameter_count": 240,
            "state_digest": None,
            "recipe_hash": None,
        },
        "build": {
            "image": "img-fixture",
            "gpu_class": "A100 40GB",
            "build_seconds": None,
            "cpu_fallback": False,
        },
        "judge": {"image": "judge-fixture", "receiver_commit": "abcdef1234"},
        "gates": [
            {
                "name": "speed",
                "result": "PASS",
                "limit": 3.3,
                "measured": 0.2,
                "unit": "s/design",
            },
        ],
        "accuracy": {
            "in_envelope": {"receipt": "V2-fixture-1", "outputs": [_aggregate()]}
        },
        "reference": {
            "solver": "GetDP (fixture)",
            "cross_checks": [
                {
                    "solver": "FEMM 4.2",
                    "public_designs": 18,
                    "report": "reports/fixture",
                }
            ],
        },
    }
    facts.update(changes)
    return facts


def _refused(board, facts, code, key=None):
    with pytest.raises(kc.CardRefused) as raised:
        kc.build_card(board, key or SIGNER.public_key, facts)
    assert raised.value.code == code


def test_card_takes_identity_and_score_only_from_the_signed_board():
    board = _board()
    card = kc.build_card(board, SIGNER.public_key, _facts())
    king = board["king"]
    assert card["labels"] == ["DEVELOPMENT", "NOT_QUALIFIED"]
    assert card["identity"]["hotkey"] == KING
    assert card["identity"]["crowned_utc"] == king["crowned_utc"]
    assert card["score"]["total_shown"] == king["king"]["total"] == 0.78
    assert card["score"]["to_beat"] == king["to_beat"]
    assert card["score"]["to_beat_rule"] == kp.TO_BEAT_RULE_EXACT
    # the exact total never reaches the card
    assert str(KING_EXACT) not in kc.canonical(card)
    assert card["envelope"] == {k: list(v) for k, v in domain.INPUT_BOUNDS.items()}
    assert card["status"] == {
        "client_use": "NOT_QUALIFIED",
        "basis": "EXAM_RESULT_ONLY",
        "rights": "UNDECIDED",
    }


def test_missing_sections_render_not_yet_measured():
    facts = {k: v for k, v in _facts().items() if k in kc.REQUIRED_FACTS}
    card = kc.build_card(_board(), SIGNER.public_key, facts)
    assert card["model"] is None and card["gates"] is None and card["reference"] is None
    assert card["accuracy"] == {
        "in_envelope": None,
        "beyond_envelope": None,
        "vs_classical": None,
    }
    text = kc.render_markdown(card, "0" * 64)
    assert text.count(kc.NOT_MEASURED) >= 7
    assert "DEVELOPMENT / NOT_QUALIFIED" in text


def test_board_must_verify_be_v6_and_have_a_king():
    _refused(_board(signer=OTHER_SIGNER), _facts(), "board_signature")
    tampered = copy.deepcopy(_board())
    tampered["king"]["king"]["total"] = 0.9
    _refused(tampered, _facts(), "board_signature")
    _refused(_board(v6=False), _facts(), "card_board_version")
    _refused(_board(king=False), _facts(), "card_no_king")


def test_facts_hotkey_must_be_the_boards_king():
    _refused(_board(), _facts(hotkey=OTHER), "card_hotkey_mismatch")


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"schema": "other"}, "card_facts_schema"),
        ({"seed": 1}, "card_facts"),
        ({"task_id": "task-1"}, "card_task"),
        ({"uid": -1}, "card_uid"),
        ({"uid": True}, "card_uid"),
        (
            {
                "model": {
                    "class": "x",
                    "parameter_count": 0,
                    "state_digest": None,
                    "recipe_hash": None,
                }
            },
            "card_model",
        ),
        (
            {
                "model": {
                    "class": "x",
                    "parameter_count": 5,
                    "state_digest": "abc",
                    "recipe_hash": None,
                }
            },
            "card_model",
        ),
        (
            {"model": {"class": "x", "parameter_count": 5, "state_digest": None}},
            "card_model",
        ),
        (
            {
                "build": {
                    "image": "i",
                    "gpu_class": None,
                    "build_seconds": float("nan"),
                    "cpu_fallback": False,
                }
            },
            "card_build",
        ),
        (
            {
                "build": {
                    "image": "i",
                    "gpu_class": None,
                    "build_seconds": 1,
                    "cpu_fallback": "no",
                }
            },
            "card_build",
        ),
        ({"judge": {"image": "j", "receiver_commit": "XYZ"}}, "card_judge"),
        (
            {
                "gates": [
                    {
                        "name": "speed",
                        "result": "OK",
                        "limit": 1,
                        "measured": 1,
                        "unit": "s",
                    }
                ]
            },
            "card_gates",
        ),
        (
            {
                "gates": [
                    {
                        "name": "speed",
                        "result": "PASS",
                        "limit": 1,
                        "measured": 1,
                        "unit": "U",
                    }
                ]
            },
            "card_gates",
        ),
        (
            {
                "reference": {
                    "solver": "s",
                    "cross_checks": [
                        {"solver": "f", "public_designs": 0, "report": "r"}
                    ],
                }
            },
            "card_reference",
        ),
    ],
)
def test_facts_shape_is_closed(changes, code):
    _refused(_board(), _facts(**changes), code)


@pytest.mark.parametrize(
    "block",
    [
        {"receipt": "r", "outputs": [_aggregate(n=kc.MIN_AGGREGATE_N - 1)]},
        {"receipt": "r", "outputs": [_aggregate(unit="U")]},
        {"receipt": "r", "outputs": [_aggregate(output="case_0001")]},
        {"receipt": "r", "outputs": [_aggregate(), _aggregate()]},
        {"receipt": "r", "outputs": [{**_aggregate(), "per_case": [0.1]}]},
        {"receipt": "r", "outputs": [{**_aggregate(), "median": 0.05}]},
        {"receipt": "r", "outputs": [{**_aggregate(), "ci95": [0.02, 0.03]}]},
        {"receipt": "r", "outputs": []},
        {"outputs": [_aggregate()]},
    ],
)
def test_accuracy_is_aggregates_only(block):
    _refused(_board(), _facts(accuracy={"in_envelope": block}), "card_accuracy")
    _refused(_board(), _facts(accuracy={"hidden_cases": None}), "card_accuracy")


def test_write_is_deterministic_and_refuses_overwrite(tmp_path):
    card = kc.build_card(_board(), SIGNER.public_key, _facts())
    digest = kc.write_card(card, tmp_path / "a")
    assert (
        kc.write_card(
            kc.build_card(_board(), SIGNER.public_key, _facts()), tmp_path / "b"
        )
        == digest
    )
    body = (tmp_path / "a" / "card.json").read_bytes()
    assert (tmp_path / "a" / "card.json.sha256").read_text() == f"{digest}  card.json\n"
    assert json.loads(body) == card
    assert digest in (tmp_path / "a" / "card.md").read_text(encoding="utf-8")
    with pytest.raises(kc.CardRefused) as raised:
        kc.write_card(card, tmp_path / "a")
    assert raised.value.code == "card_output_exists"


def test_cli_prints_digest_or_refusal(tmp_path, capsys):
    board, facts = tmp_path / "board.json", tmp_path / "facts.json"
    board.write_text(json.dumps(_board()), encoding="utf-8")
    facts.write_text(json.dumps(_facts()), encoding="utf-8")
    args = [
        "--board",
        str(board),
        "--pinned-key",
        SIGNER.public_key,
        "--facts",
        str(facts),
    ]
    assert kc.main([*args, "--out-dir", str(tmp_path / "out")]) == 0
    assert len(capsys.readouterr().out.strip()) == 64
    assert (
        kc.main(
            [
                *args[:3],
                OTHER_SIGNER.public_key,
                *args[4:],
                "--out-dir",
                str(tmp_path / "o2"),
            ]
        )
        == 2
    )
    assert "REFUSED board_signature" in capsys.readouterr().err
    assert not (tmp_path / "o2").exists()
