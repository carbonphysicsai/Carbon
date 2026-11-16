"""A drained door answers 503 "updating" at once (A19; miner feedback 16 Nov 2026: requests hung until the miner timed
out during drains and switches; owner's miner-facing words via the Lead). Internal names (the DRAINING flag) stay.
"""

from __future__ import annotations

from carbon.battery import intake as battery_intake


def test_no_flag_no_answer(tmp_path):
    assert battery_intake.updating_answer(None) is None
    assert battery_intake.updating_answer(tmp_path / "draining") is None


def test_the_miner_facing_words_and_the_default_retry(tmp_path):
    flag = tmp_path / "draining"
    flag.touch()
    answer = battery_intake.updating_answer(flag)
    assert answer.status == 503
    assert answer.body == {
        "status": "updating",
        "message": "Carbon is upgrading the validator; please retry shortly",
        "retry_after_s": battery_intake.UPDATING_RETRY_DEFAULT_S,
    }
    assert "drain" not in str(answer.body)


def test_the_operator_sets_the_retry_in_the_flag(tmp_path):
    flag = tmp_path / "draining"
    for text, expected in (
        ("120\n", 120),
        ("0", battery_intake.UPDATING_RETRY_DEFAULT_S),
        ("abc", battery_intake.UPDATING_RETRY_DEFAULT_S),
        ("-5", battery_intake.UPDATING_RETRY_DEFAULT_S),
        (
            str(battery_intake.UPDATING_RETRY_MAX_S + 1),
            battery_intake.UPDATING_RETRY_DEFAULT_S,
        ),
    ):
        flag.write_text(text, encoding="ascii")
        assert battery_intake.updating_answer(flag).body["retry_after_s"] == expected


def test_the_receiver_points_its_intake_at_its_own_draining_flag():
    import inspect

    from carbon.challenge_validator import direct_intake

    source = inspect.getsource(direct_intake.serve_loopback)
    assert "intake.updating_flag = Path(state_dir) / DRAIN_NAME" in source
