"""A signed batch withdrawal (VALIDATOR-24): the producer withdraws a window,
the distribution host lists the notice and never serves the package, and
validators stop scoring on it at once and never import it again. In process,
with the answer-key tests' producer, host and validator. Not a security audit
(AGENTS.md §13)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import producer as pr

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_answer_key import (  # noqa: F401 - fixtures
    VALIDATOR,
    battery_validator,
    fetcher,
    host,
    published,
)

REASON = "leak_suspected"


def withdraw(published, block=2000):  # noqa: F811
    challenge = published["source"].challenge_id
    fingerprint = published["value"]["manifest"]["commitment"]["fingerprint"]
    result = published["producer"].withdraw(challenge, fingerprint, REASON, block=block)
    notice = published["path"].parent / "withdrawals" / result["notice"]
    return fingerprint, notice


def test_a_withdrawn_window_stops_scoring_and_is_never_reimported(
    tmp_path, host, published  # noqa: F811
):
    challenge = published["source"].challenge_id
    key = published["key"].public_key
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    asker = fetcher(host["service"], VALIDATOR)
    assert [
        p["state"] for p in ak.sync(adapter, asker, key, challenge)["packages"]
    ] == ["IMPORTED"]
    fingerprint, notice = withdraw(published)
    assert adapter.target.store.windowed_active(2000) == [fingerprint]
    # The push carries the notice; the stale package is still there too.
    (host["inbox"] / "withdrawals").mkdir(mode=0o700)
    shutil.copy(notice, host["inbox"] / "withdrawals" / notice.name)
    (host["inbox"] / "withdrawals" / notice.name).chmod(0o600)
    result = ak.sync(adapter, asker, key, challenge)
    assert result["packages"] == [{"fingerprint": fingerprint, "state": "WITHDRAWN"}]
    assert adapter.target.store.batch_withdrawn(fingerprint)
    assert adapter.target.store.windowed_active(2000) == []
    # The host never serves it, even with the package still in its inbox.
    listing = asker.ask(challenge)
    assert listing["packages"] == [] and len(listing["withdrawals"]) == 1
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        asker.ask(challenge, fingerprint)
    assert refused.value.code == "answer_key_unknown_batch"
    # And the validator refuses it if it ever arrives another way.
    value = published["value"]
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key(value["manifest"]["commitment"], value["payload"])
    assert refused.value.code == "answer_key_withdrawn"
    # Idempotent.
    assert (
        ak.sync(adapter, asker, key, challenge)["packages"][0]["state"] == "WITHDRAWN"
    )


def test_the_producer_withdraws_once_and_never_republishes(published):  # noqa: F811
    challenge = published["source"].challenge_id
    fingerprint, notice = withdraw(published)
    assert not published["path"].exists() and notice.exists()
    first = notice.read_text()
    again = published["producer"].withdraw(
        challenge, fingerprint, "other_reason", block=9
    )
    assert again["reason"] == REASON and notice.read_text() == first
    with pytest.raises(pr.ProducerRefused) as refused:
        published["producer"].publish(challenge, fingerprint)
    assert refused.value.code == "producer_withdrawn"
    entries = [
        e for e in published["producer"].journal.entries() if e["event"] == "withdrawn"
    ]
    assert [(e["reason"], e["block"]) for e in entries] == [(REASON, 2000)]


def test_a_local_import_applies_withdrawals_first(tmp_path, published):  # noqa: F811
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    _fingerprint, _notice = withdraw(published)
    result = ak.import_local(
        adapter, published["key"].public_key, published["path"].parent
    )
    assert [p["state"] for p in result["packages"]] == ["WITHDRAWN"]


@pytest.mark.parametrize("change", ["reason", "fingerprint", "foreign_key"])
def test_a_tampered_or_foreign_notice_is_refused(
    tmp_path, published, change  # noqa: F811
):
    _fingerprint, notice = withdraw(published)
    value = json.loads(notice.read_text())
    key = published["key"].public_key
    if change == "reason":
        value["manifest"]["reason"] = "nothing_happened"
    elif change == "fingerprint":
        value["manifest"]["fingerprint"] = "sha256:" + "0" * 64
    else:
        key = ak.ProducerKey.create(tmp_path / "other.key").public_key
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        ak.verify_withdrawal(value, key)
    assert refused.value.code in ("answer_key_signature", "answer_key_wrong_producer")


def test_a_withdrawal_before_import_still_refuses_the_batch(
    tmp_path, published  # noqa: F811
):
    adapter = battery_validator(tmp_path / "validator", import_only=True)
    fingerprint, notice = withdraw(published)
    manifest = ak.verify_withdrawal(
        json.loads(notice.read_text()), published["key"].public_key
    )
    assert adapter.withdraw_answer_key(manifest) is True
    assert adapter.withdraw_answer_key(manifest) is False
    changed = dict(manifest, reason="another")
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.withdraw_answer_key(changed)
    assert refused.value.code == "answer_key_withdrawal_changed"
    value = json.loads(
        (
            published["producer"].directory
            / "withdrawn"
            / published["source"].challenge_id
            / (fingerprint.removeprefix("sha256:") + ".json")
        ).read_text()
    )
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key(value["manifest"]["commitment"], value["payload"])
    assert refused.value.code == "answer_key_withdrawn"


# --- slice 2: a withdrawn window's submissions are VOID -----------------------------------


def scored(store, submission_id, hotkey, block, *, nomination=None):
    """Admit one submission at `block` and record a screening score on the
    pool version active then."""
    store.admit(
        submission_id,
        request_digest="r-" + submission_id,
        hotkey=hotkey,
        challenge="battery",
        strategy={"s": submission_id},
        binding={
            "receipt": {"block": block},
            "backend": {"backend": "direct", "validator_path": False},
        },
        window=(block - block % 360, block - block % 360 + 360, 1),
    )
    store.rotate_if_ready()
    version = store.pool()["version"]
    return store.record_score(
        submission_id,
        {"nomination": {"nominated": False}},
        {"score": 0.5},
        expected_version=version,
        nomination=nomination,
    )


def imported(tmp_path, published, name="validator"):  # noqa: F811
    adapter = battery_validator(tmp_path / name, import_only=True)
    value = published["value"]
    adapter.import_answer_key(value["manifest"]["commitment"], value["payload"])
    adapter.target.store.open_pool()
    return adapter


def notice_for(published):  # noqa: F811
    _fingerprint, notice = withdraw(published)
    return ak.verify_withdrawal(
        json.loads(notice.read_text()), published["key"].public_key
    )


def test_a_withdrawn_windows_submissions_are_void_never_failed(
    tmp_path, published  # noqa: F811
):
    adapter = imported(tmp_path, published)
    store = adapter.target.store
    scored(store, "sub-a", "5Miner", 2000)
    assert store.submission("sub-a")["state"] == "SCORED"
    adapter.withdraw_answer_key(notice_for(published))
    row = store.submission("sub-a")
    assert row["state"] == "VOID" and row["failure"] == {"code": "window_withdrawn"}
    # The score stays in the record (invariant 10); the outcome says VOID.
    assert store.score("sub-a")["public"] == {"score": 0.5}
    outcome = adapter.target.outcome("sub-a")
    assert (
        outcome["state"] == "VOID" and outcome["failure"]["code"] == "window_withdrawn"
    )
    assert "screening" not in outcome
    voided = [e["body"] for e in store.events("submission_voided")]
    assert [v["submission_id"] for v in voided] == ["sub-a"]


def test_a_void_submission_does_not_use_the_hotkeys_slot(
    tmp_path, published  # noqa: F811
):
    from carbon.battery.pool_store import HotkeyWindowUsed

    adapter = imported(tmp_path, published)
    store = adapter.target.store
    scored(store, "sub-a", "5Miner", 2000)
    with pytest.raises(HotkeyWindowUsed):
        scored(store, "sub-b", "5Miner", 2001)
    adapter.withdraw_answer_key(notice_for(published))
    store.admit(
        "sub-b",
        request_digest="r-sub-b",
        hotkey="5Miner",
        challenge="battery",
        strategy={"s": "sub-b"},
        binding={
            "receipt": {"block": 2001},
            "backend": {"backend": "direct", "validator_path": False},
        },
        window=(1800, 2160, 1),
    )
    assert store.submission("sub-b")["state"] == "ADMITTED"


def test_every_validator_voids_the_same_window(tmp_path, published):  # noqa: F811
    notice = None
    states = []
    for name in ("first", "second"):
        adapter = imported(tmp_path, published, name)
        scored(adapter.target.store, "sub-a", "5Miner", 2000)
        notice = notice or notice_for(published)
        adapter.withdraw_answer_key(notice)
        states.append(adapter.target.store.submission("sub-a")["state"])
        assert adapter.target.store.windowed_active(2000) == []
    assert states == ["VOID", "VOID"]


def test_a_void_first_incumbent_is_cleared_and_never_weighted(
    tmp_path, published  # noqa: F811
):
    from carbon.rewards.winner_eligibility import battery_promotion

    adapter = imported(tmp_path, published)
    store = adapter.target.store
    scored(
        store,
        "sub-a",
        "5Miner",
        2000,
        nomination={"kind": "first_incumbent", "reason": "first_eligible"},
    )
    assert store.incumbent()["model_id"] == "sub-a"
    adapter.withdraw_answer_key(notice_for(published))
    assert store.incumbent() is None
    assert battery_promotion(adapter.target) is None
