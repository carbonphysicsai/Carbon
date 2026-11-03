"""Crown-average measurement IMPORT (`crown_import`; Validator 06:56, switch-on condition C10): a spare receiver re-measures
the sitting king and writes a measurement record; the live receiver, stopped for seconds, verifies it against its own
configuration, store and K_crown and files the mean through `PoolStore.record_crown_average`.

Claims: a spare's record imports on a live store whose incumbent, key, entry, binding, K_crown and rule all match, the mean
then reads back through `crown_mean`, and a second import is a no-op; every bound field that differs refuses with its own
code and files nothing (incumbent, evaluation key, entry bytes, receiver binding, K_crown, rule, the K_crown MAC over the record,
seeds, mean, record shape);
the receiver's hotkey and chain context are not bound (a spare is not the same door); an unstable king's record imports as
filed; the spare writes nothing unless its re-measure filed, and the record is a new 0600 file; the CLI flags are one of the
two, with --remeasure-king only.
"""

from __future__ import annotations

import json
import math
import os
import stat

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import crown_average, crown_import
from carbon.challenge_validator.interface import digest

KING = "rtsk_" + "a" * 64
OTHER = "rtsk_" + "b" * 64
CHALLENGE = "f08-ribbed-bracket"
KEY = digest(["evaluation", KING])
K_CROWN = b"\x11" * 32
N = 4
BINDING = {
    "schema": "carbon.direct-receiver.v1",
    "implementation": {"revision": "a" * 40, "source_authority": "ACCEPTED"},
    "parent": {"image_id": "sha256:" + "1" * 64},
    "context": {"network": "test", "netuid": 567},
    "receiver_hotkey": "5Freceiver",
    "challenge": {"id": CHALLENGE, "version": "1.7"},
    "measure_query": False,
    "evaluation_pack_digest": "sha256:" + "e" * 64,
}


def _rule(margin=0.002, n=N):
    return crown_average.Rule(
        {
            "rule_version": "crown-average-v1",
            "seed_range": 2**31 - 1,
            "n": n,
            "challenge_n": {},
            "margins": {
                CHALLENGE: {
                    "n": n,
                    "value": margin,
                    "measurement_digest": "sha256:" + "d" * 64,
                }
            },
        }
    )


def _active(key=K_CROWN, **rule):
    return crown_average.Active(_rule(**rule), key)


def _store(path, king=KING):
    path.mkdir(parents=True, exist_ok=True)
    store = PoolStore(path / "pool.sqlite3")
    store.admit(
        KING,
        request_digest=digest(["request", KING]),
        hotkey="5Fking",
        challenge=CHALLENGE,
        strategy={"source": {"kind": "graph"}},
        binding={"challenge": {"id": CHALLENGE}},
    )
    with store.transaction() as db:
        store._set_incumbent(db, king, "fixture", expected=None)
    return store


def _measured(active, totals=(0.85, 0.86, 0.84, 0.85)):
    seeds = crown_average.derive_seeds(
        active._key, CHALLENGE, KING, N, active.rule.seed_range
    )
    totals = list(totals)
    return {
        "seeds": seeds,
        "n": N,
        "margin": active.rule.margin_for(CHALLENGE),
        "totals": totals,
        "mean": math.fsum(totals) / N,
    }


def _entry(path, body=b"state"):
    path.mkdir(parents=True, exist_ok=True)
    (path / "state.npz").write_bytes(body)
    (path / "meta").mkdir(exist_ok=True)
    (path / "meta" / "recipe.json").write_bytes(b"{}")
    return path


def _spare_record(tmp_path, private=None, active=None):
    active = active or _active()
    spare = _store(tmp_path / "spare")
    spare.record_crown_average(KING, KEY, private or _measured(active))
    out = tmp_path / "record.json"
    crown_import.write_record(
        out,
        outcome=crown_average.KING_MEASURED,
        active=active,
        store=spare,
        challenge_id=CHALLENGE,
        submission_id=KING,
        evaluation_key=KEY,
        entry_id="entry-1",
        entry_directory=_entry(tmp_path / "spare-entry"),
        receiver_binding={**BINDING, "receiver_hotkey": "5Fspare"},
    )
    return out


def _import(tmp_path, record, *, store=None, active=None, **overrides):
    args = {
        "active": active or _active(),
        "store": store or _store(tmp_path / "live"),
        "challenge_id": CHALLENGE,
        "evaluation_key": KEY,
        "entry_id": "entry-1",
        "entry_directory": _entry(tmp_path / "live-entry"),
        "receiver_binding": BINDING,
    }
    args.update(overrides)
    return crown_import.import_record(record, **args), args["store"]


def test_a_matching_spare_record_imports_and_the_mean_reads_back(tmp_path):
    record = _spare_record(tmp_path)
    if os.name != "nt":
        assert stat.S_IMODE(record.stat().st_mode) == 0o600
    result, live = _import(tmp_path, record)
    assert result == {
        "state": "CROWN_MEASUREMENT_IMPORTED",
        "submission_id": KING,
        "evaluation_key": KEY,
    }
    assert live.crown_mean(KING) == pytest.approx(0.85)
    assert (
        crown_import.filed_private(live, KING, KEY)
        == json.loads(record.read_text())["private"]
    )
    again, _ = _import(tmp_path, record, store=live)  # idempotent
    assert again == result
    # no seed, total or mean in what the receiver prints
    assert set(result) == {"state", "submission_id", "evaluation_key"}


def _edit(path, change):
    record = json.loads(path.read_text())
    change(record)
    path.write_text(json.dumps(record))
    return path


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        (lambda t: {"store": _store(t / "live", king=OTHER)}, "submission_id"),
        (lambda t: {"evaluation_key": digest(["other"])}, "evaluation_key"),
        (lambda t: {"entry_id": "entry-2"}, "entry"),
        (
            lambda t: {"entry_directory": _entry(t / "changed-entry", b"other")},
            "entry",
        ),
        (
            lambda t: {
                "receiver_binding": {
                    **BINDING,
                    "implementation": {"revision": "b" * 40},
                }
            },
            "implementation",
        ),
        (
            lambda t: {
                "receiver_binding": {
                    **BINDING,
                    "evaluation_pack_digest": "sha256:" + "f" * 64,
                }
            },
            "binding",
        ),
        (lambda t: {"active": _active(key=b"\x22" * 32)}, "key_id"),
        (lambda t: {"active": _active(margin=0.003)}, "rule"),
    ],
)
def test_a_differing_live_fact_refuses_and_files_nothing(tmp_path, setup, code):
    record = _spare_record(tmp_path)
    overrides = setup(tmp_path)
    store = overrides.pop("store", None) or _store(tmp_path / "live")
    with pytest.raises(
        crown_import.ImportRefused, match=f"crown_import_{code}_differs"
    ):
        _import(tmp_path, record, store=store, **overrides)
    assert crown_import.filed_private(store, KING, KEY) is None
    assert store.crown_mean(KING) is None


def _edited_totals(record):
    # Validator 07:28 (1): edited totals WITH a matching mean pass every arithmetic check; only the MAC stops them.
    totals = [t + 0.05 for t in record["private"]["totals"]]
    record["private"].update(totals=totals, mean=math.fsum(totals) / N)


def _remac(change):
    # The same edit, re-signed with the RIGHT K_crown (what only a key holder could do): the content checks still refuse.
    def edit(record):
        change(record)
        record["record_mac"] = crown_import.record_mac(K_CROWN, record)

    return edit


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (_edited_totals, "crown_import_record_mac_differs"),
        (lambda r: r["private"]["seeds"].reverse(), "crown_import_record_mac_differs"),
        (lambda r: r.update(record_mac="0" * 64), "crown_import_record_mac_differs"),
        (lambda r: r.update(record_mac=None), "crown_import_record_mac_differs"),
        (
            _remac(lambda r: r["private"]["seeds"].reverse()),
            "crown_import_seeds_differs",
        ),
        (
            _remac(lambda r: r["private"].update(mean=r["private"]["mean"] + 0.01)),
            "crown_import_mean_differs",
        ),
        (
            _remac(lambda r: r["private"]["totals"].append(0.9)),
            "crown_import_mean_differs",
        ),
        (lambda r: r.update(extra=1), "crown_import_record_invalid"),
        (lambda r: r.pop("record_mac"), "crown_import_record_invalid"),
        (lambda r: r.update(schema="other"), "crown_import_record_invalid"),
    ],
)
def test_a_tampered_record_refuses(tmp_path, change, code):
    record = _edit(_spare_record(tmp_path), change)
    store = _store(tmp_path / "live")
    with pytest.raises(crown_import.ImportRefused, match=code):
        _import(tmp_path, record, store=store)
    assert store.crown_mean(KING) is None


def test_the_hotkey_and_chain_context_are_not_bound(tmp_path):
    record = _spare_record(tmp_path)
    result, _ = _import(
        tmp_path,
        record,
        receiver_binding={
            **BINDING,
            "receiver_hotkey": "5Fanother",
            "context": {"network": "x"},
        },
    )
    assert result["state"] == "CROWN_MEASUREMENT_IMPORTED"


def test_an_unstable_kings_record_imports_as_filed(tmp_path):
    active = _active()
    private = {
        "seeds": crown_average.derive_seeds(K_CROWN, CHALLENGE, KING, N, 2**31 - 1),
        "n": N,
        "margin": 0.002,
        "statuses": ["SCORED", "GATE_FAILED", "SCORED", "SCORED"],
    }
    record = _spare_record(tmp_path, private=private, active=active)
    result, live = _import(tmp_path, record)
    assert result["state"] == "CROWN_MEASUREMENT_IMPORTED"
    assert (
        live.crown_mean(KING) is None
    )  # no mean: the unstable rule reads the statuses
    assert crown_import.filed_private(live, KING, KEY) == private


def test_the_spare_writes_nothing_unless_its_remeasure_filed(tmp_path):
    spare = _store(tmp_path / "spare")
    for outcome in ("UNAVAILABLE", "FAILED_INFRA"):
        with pytest.raises(crown_import.ImportRefused, match="nothing_filed"):
            crown_import.write_record(
                tmp_path / "r.json",
                outcome=outcome,
                active=_active(),
                store=spare,
                challenge_id=CHALLENGE,
                submission_id=KING,
                evaluation_key=KEY,
                entry_id="entry-1",
                entry_directory=_entry(tmp_path / "e"),
                receiver_binding=BINDING,
            )
    with pytest.raises(crown_import.ImportRefused, match="nothing_filed"):
        crown_import.write_record(
            tmp_path / "r.json",
            outcome=crown_average.KING_MEASURED,  # said measured, but nothing was filed
            active=_active(),
            store=spare,
            challenge_id=CHALLENGE,
            submission_id=KING,
            evaluation_key=KEY,
            entry_id="entry-1",
            entry_directory=_entry(tmp_path / "e"),
            receiver_binding=BINDING,
        )
    assert not (tmp_path / "r.json").exists()
    record = _spare_record(tmp_path)
    with pytest.raises(FileExistsError):  # never overwrites a record
        os.open(record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)


def test_an_entry_link_refuses(tmp_path):
    if os.name == "nt":
        pytest.skip("symlinks need privileges on Windows")
    entry = _entry(tmp_path / "e")
    (entry / "link").symlink_to(entry / "state.npz")
    with pytest.raises(crown_import.ImportRefused, match="entry_link"):
        crown_import.entry_digest(entry)


def test_no_rule_installed_refuses(tmp_path):
    record = _spare_record(tmp_path)
    with pytest.raises(crown_import.ImportRefused, match="rule_not_installed"):
        crown_import.import_record(
            record,
            active=None,
            store=_store(tmp_path / "live"),
            challenge_id=CHALLENGE,
            evaluation_key=KEY,
            entry_id="entry-1",
            entry_directory=_entry(tmp_path / "le"),
            receiver_binding=BINDING,
        )


@pytest.mark.parametrize(
    "argv",
    [
        ["--measurement-record", "out.json"],
        ["--import-crown-measurement", "in.json"],
        ["--record-only"],
        ["--accept-measured-revision", "a" * 40],
        [
            "--remeasure-king",
            KING,
            "--evaluation-key",
            KEY,
            "--remeasure-entry",
            "e",
            "--pool-store",
            "p",
            "--measurement-record",
            "out.json",
            "--import-crown-measurement",
            "in.json",
        ],
    ],
)
def test_the_record_flags_are_one_of_the_two_with_remeasure_king_only(
    tmp_path, argv, monkeypatch
):
    from carbon.challenge_validator import cpu_pin, direct_receiver

    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    with pytest.raises(SystemExit) as stopped:
        direct_receiver.main(["--config", str(tmp_path / "c.json"), *argv])
    assert stopped.value.code == 2


def test_a_different_record_already_filed_refuses_and_keeps_the_first(tmp_path):
    record = _spare_record(tmp_path)
    live = _store(tmp_path / "live")
    first = _measured(_active(), totals=(0.80, 0.80, 0.80, 0.80))
    live.record_crown_average(KING, KEY, first)
    with pytest.raises(crown_import.ImportRefused, match="crown_import_record_changed"):
        _import(tmp_path, record, store=live)
    assert crown_import.filed_private(live, KING, KEY) == first


def test_the_write_only_mode_records_what_the_spare_already_filed(tmp_path):
    # F08 (Validator 07:28): the spare re-measured before C10 existed; --record-only writes its record, no rebuild.
    active = _active()
    spare = _store(tmp_path / "spare")
    spare.record_crown_average(KING, KEY, _measured(active))
    out = tmp_path / "f08.json"
    crown_import.write_record(
        out,
        outcome=None,
        active=active,
        store=spare,
        challenge_id=CHALLENGE,
        submission_id=KING,
        evaluation_key=KEY,
        entry_id="entry-1",
        entry_directory=_entry(tmp_path / "spare-entry"),
        receiver_binding=BINDING,
    )
    record = json.loads(out.read_text())
    assert record["record_mac"] == crown_import.record_mac(K_CROWN, record)
    result, live = _import(tmp_path, out)
    assert result["state"] == "CROWN_MEASUREMENT_IMPORTED"
    assert live.crown_mean(KING) == pytest.approx(0.85)
    # with nothing filed, the write-only mode refuses too
    with pytest.raises(crown_import.ImportRefused, match="nothing_filed"):
        crown_import.write_record(
            tmp_path / "none.json",
            outcome=None,
            active=active,
            store=_store(tmp_path / "empty"),
            challenge_id=CHALLENGE,
            submission_id=KING,
            evaluation_key=KEY,
            entry_id="entry-1",
            entry_directory=_entry(tmp_path / "e2"),
            receiver_binding=BINDING,
        )


def test_another_revision_imports_only_with_its_full_sha_named(tmp_path):
    # Validator 07:46: the record keeps the revision it was measured at; another revision imports only under
    # --accept-measured-revision <that full sha>, logged and returned.
    record = _spare_record(tmp_path)
    live_binding = {**BINDING, "implementation": {"revision": "c" * 40}}
    for accept in (None, "b" * 40, "a" * 39, "A" * 40):
        store = _store(tmp_path / f"live-{accept}")
        with pytest.raises(
            crown_import.ImportRefused, match="crown_import_implementation_differs"
        ):
            _import(
                tmp_path,
                record,
                store=store,
                receiver_binding=live_binding,
                accept_measured_revision=accept,
            )
        assert store.crown_mean(KING) is None
    result, live = _import(
        tmp_path,
        record,
        receiver_binding=live_binding,
        accept_measured_revision="a" * 40,
    )
    assert result["accepted_measured_revision"] == "a" * 40
    assert live.crown_mean(KING) == pytest.approx(0.85)
    # the same revision needs no flag, and the result says nothing about one
    same, _ = _import(tmp_path, record, store=_store(tmp_path / "same"))
    assert "accepted_measured_revision" not in same
