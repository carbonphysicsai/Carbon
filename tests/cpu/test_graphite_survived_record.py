"""The scope record generator (SURVIVED-RECORD-DEFINITION-01): read-only, append-only, fixtures only.

Claims tested: an item is entered once TESTED and needs no attack; the four statuses follow the exact rules (ORACLE_GAP and
FALSE_POSITIVE never remove; an untriaged finding or an unfixed REAL_ESCAPE is open; ATTACKED_HELD needs every mapped
family held at k with a DONE stop); triage is read into the record; empty `finding_states` (no repair attestation) is
handled; a finding's level is derived from its construction and a mismatch is kept; a rerun appends nothing, changed
evidence supersedes; removals come from a REAL_ESCAPE in one step and from nothing else; no spend, no verdict words.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.dev.graphite_progress import survived as sv

NOW = lambda: datetime.datetime(2026, 10, 13, 12, 0, tzinfo=datetime.UTC)
CH = "battery-fastcharge-ageing-development-v1"


def _row(status, attempts=3, held=0, **extra):
    return {
        "status": status,
        "budget_used": attempts,
        "held": held,
        "verified": 0,
        "inconclusive": None,
        "not_run": None,
        **extra,
    }


def _store(tmp_path, name, level, rows, findings=(), repairs=(), stop="DONE"):
    store = tmp_path / name / "attacker"
    report = store / "reports" / "r1"
    report.mkdir(parents=True)
    (report / "coverage.json").write_text(
        json.dumps(
            {
                "construction_level": level,
                "schema": "carbon.graphite.attacker-coverage.v7",
                "stop_rule_outcome": {"status": stop, "k": 3},
                "families": {"families": rows},
            }
        )
    )
    controller = store / "controller"
    (controller / "evidence").mkdir(parents=True)
    db = sqlite3.connect(controller / "campaign.sqlite3")
    db.execute("CREATE TABLE findings(id TEXT, body TEXT, ordinal INTEGER)")
    db.execute(
        "CREATE TABLE finding_states(finding TEXT, seq INTEGER, state TEXT, body TEXT)"
    )
    for number, (fid, family, attempt) in enumerate(findings):
        verdict = {
            "family": family,
            "attempt": attempt,
            "authority": "AUTHORITATIVE",
            "conditions": ["FAILING_TRIGGER"],
            "outcome": "BREACHED",
        }
        (controller / "evidence" / f"{number}.bin").write_text(
            json.dumps({"verdict": verdict})
        )
        db.execute(
            "INSERT INTO findings VALUES(?,?,?)",
            (fid, json.dumps({"evidence": {"path": f"evidence/{number}.bin"}}), number),
        )
    for number, fid in enumerate(repairs):
        db.execute(
            "INSERT INTO finding_states VALUES(?,?,?,?)",
            (
                fid,
                number,
                "REPAIRED",
                json.dumps(
                    {"repair_id": "repair-1", "rerun": ["a"], "code_ref": "c" * 40}
                ),
            ),
        )
    db.commit()
    db.close()
    return store


def _ledger(tmp_path, bundled=0.5):
    path = tmp_path / "progress.jsonl"
    path.write_text(
        json.dumps(
            {
                "batch": "b1",
                "level": 2,
                "constructor": {
                    "runs": 3,
                    "proposals": 30,
                    "bundled_share": {"value": bundled},
                    "booked_usd": "9.99",
                },
            }
        )
        + "\n"
    )
    return path


def _manifest(tmp_path, triage=None, fixes=None, reattack=None):
    directory = tmp_path / "backfill"
    directory.mkdir(exist_ok=True)
    (directory / "attack-test.json").write_text(
        json.dumps(
            {
                "batch": "attack-test",
                "triage": triage or {},
                "triage_source": "fixture",
                "finding_fixes": fixes or {},
                "reattack": reattack or {},
            }
        )
    )
    return directory


def _items(tmp_path, families=("fam_a", "fam_b"), ledger=True):
    path = tmp_path / "items.json"
    path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "item_id": "l2.fixture",
                        "level": 2,
                        "construction_family": "fixture",
                        "challenge": CH,
                        "families": list(families),
                        "scored_ledger": (
                            [{"batch": "b1", "level": 2}] if ledger else []
                        ),
                    }
                ]
            }
        )
    )
    return path


def _run(tmp_path, store, backfill, **kwargs):
    args = SimpleNamespace(
        items=str(kwargs.pop("items", None) or _items(tmp_path)),
        ledger=str(_ledger(tmp_path)),
        backfill=str(backfill),
        attacker_store=[str(store)],
        out_jsonl=str(tmp_path / "survived-record.jsonl"),
        snapshot_out=str(tmp_path / "snapshot.json"),
    )
    return (
        sv.generate(
            args, strategy_of=kwargs.pop("strategy_of", lambda finding: None), now=NOW
        ),
        args,
    )


def _record(tmp_path):
    return json.loads((tmp_path / "snapshot.json").read_text())["records"][0]


#: A plain base-recipe construction: the unified classifier derives Level 0 from it, whatever session recorded it.
LEVEL_ZERO_STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": CH,
    "backbone": "mlp",
    "parameters": {"steps": 48, "width": 16, "depth": 1},
}
HELD_ROWS = {
    "fam_a": _row("ATTEMPTED_COVERAGE", 3, 2),
    "fam_b": _row("ATTEMPTED_COVERAGE", 4, 1),
}


def test_held_needs_every_family_held_at_k_with_a_done_stop(tmp_path):
    result, _ = _run(tmp_path, _store(tmp_path, "r", 2, HELD_ROWS), _manifest(tmp_path))
    assert result["records"] == 1
    record = _record(tmp_path)
    assert record["status"] == sv.HELD and record["open_finding_count"] == 0
    assert record["claims"] == sv.CLAIMS and record["entry"]["state"] == "TESTED"


@pytest.mark.parametrize(
    "rows, stop, status",
    [
        (
            {
                "fam_a": _row("ATTEMPTED_COVERAGE", 3, 2),
                "fam_b": _row("INCONCLUSIVE", 3),
            },
            "DONE",
            sv.TESTED_ONLY,
        ),
        (
            {"fam_a": _row("ATTEMPTED_COVERAGE", 3, 2), "fam_b": _row("NOT_RUN", 0)},
            "DONE",
            sv.TESTED_ONLY,
        ),
        (
            {
                "fam_a": _row("ATTEMPTED_COVERAGE", 2, 2),
                "fam_b": _row("ATTEMPTED_COVERAGE", 3, 1),
            },
            "DONE",
            sv.TESTED_ONLY,
        ),
        (HELD_ROWS, "INCOMPLETE", sv.TESTED_ONLY),
        (
            {"fam_a": _row("INCONCLUSIVE", 0), "fam_b": _row("NOT_RUN", 0)},
            "DONE",
            sv.NOT_ATTACKED,
        ),
    ],
)
def test_a_blocked_or_unattacked_family_keeps_the_item_below_held(
    tmp_path, rows, stop, status
):
    _run(tmp_path, _store(tmp_path, "r", 2, rows, stop=stop), _manifest(tmp_path))
    assert _record(tmp_path)["status"] == status


def test_oracle_gap_and_false_positive_never_open_an_item_and_never_make_it_held(
    tmp_path,
):
    rows = {**HELD_ROWS, "fam_a": _row("FINDING", 5, 0)}
    store = _store(
        tmp_path,
        "r",
        2,
        rows,
        findings=[("f1", "fam_a", "t-1"), ("f2", "fam_b", "t-2")],
    )
    backfill = _manifest(tmp_path, triage={"f1": "ORACLE_GAP", "f2": "FALSE_POSITIVE"})
    _run(tmp_path, store, backfill)
    record = _record(tmp_path)
    assert record["status"] == sv.TESTED_ONLY and record["open_finding_count"] == 0
    assert any("ORACLE_GAP awaiting a re-attack" in r for r in record["status_reason"])
    # Once a fix is recorded and a clean re-attack named, only then the family is judged again.
    backfill = _manifest(
        tmp_path,
        triage={"f1": "ORACLE_GAP", "f2": "FALSE_POSITIVE"},
        fixes={"f1": "PR 1"},
        reattack={"f1": "report-2"},
    )
    _run(
        tmp_path,
        _store(tmp_path, "r2", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")]),
        backfill,
    )
    assert _record(tmp_path)["status"] == sv.HELD


@pytest.mark.parametrize("triage", [None, "REAL_ESCAPE"])
def test_an_untriaged_or_unfixed_real_escape_finding_is_open(tmp_path, triage):
    store = _store(tmp_path, "r", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")])
    backfill = _manifest(tmp_path, triage={"f1": triage} if triage else {})
    _run(tmp_path, store, backfill)
    record = _record(tmp_path)
    assert record["status"] == sv.OPEN_FINDING and record["open_finding_count"] == 1
    assert record["findings"][0]["triage"] == (triage or sv.UNTRIAGED)


def test_a_repair_attestation_or_a_fix_with_a_re_attack_closes_a_real_escape(tmp_path):
    store = _store(
        tmp_path, "r", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")], repairs=["f1"]
    )
    _run(tmp_path, store, _manifest(tmp_path, triage={"f1": "REAL_ESCAPE"}))
    record = _record(tmp_path)
    assert (
        record["open_finding_count"] == 0
        and record["repair_attestations"][0]["repair_id"] == "repair-1"
    )


def test_empty_finding_states_means_no_repair_attestation_and_is_handled(tmp_path):
    _run(tmp_path, _store(tmp_path, "r", 2, HELD_ROWS), _manifest(tmp_path))
    assert _record(tmp_path)["repair_attestations"] == []


def test_the_level_label_is_derived_from_the_construction_and_a_mismatch_is_kept(
    tmp_path,
):
    store = _store(tmp_path, "r", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")])
    backfill = _manifest(tmp_path, triage={"f1": "ORACLE_GAP"})
    _run(tmp_path, store, backfill, strategy_of=lambda finding: LEVEL_ZERO_STRATEGY)
    finding = _record(tmp_path)["findings"][0]
    assert finding["recorded_level"] == 2
    assert finding["derived_level"] == 0 and finding["level_label_mismatch"] is True


def test_an_underivable_construction_keeps_its_recorded_level_unflagged(tmp_path):
    store = _store(tmp_path, "r", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")])
    _run(
        tmp_path,
        store,
        _manifest(tmp_path, triage={"f1": "ORACLE_GAP"}),
        strategy_of=lambda finding: None,
    )
    finding = _record(tmp_path)["findings"][0]
    assert finding["derived_level"] is None and finding["level_label_mismatch"] is False


def test_an_item_that_is_not_tested_is_not_entered(tmp_path):
    result, _ = _run(
        tmp_path,
        _store(tmp_path, "r", 2, HELD_ROWS),
        _manifest(tmp_path),
        items=_items(tmp_path, ledger=False),
    )
    assert result["records"] == 0 and result["not_entered"] == 1
    snap = json.loads((tmp_path / "snapshot.json").read_text())
    assert snap["not_entered"][0]["item_id"] == "l2.fixture" and snap["records"] == []


def test_a_rerun_appends_nothing_and_changed_evidence_supersedes(tmp_path):
    store = _store(tmp_path, "r", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")])
    _run(tmp_path, store, _manifest(tmp_path))
    again, args = _run(tmp_path, store, _manifest(tmp_path))
    assert again["appended"] == 0
    lines = [json.loads(t) for t in Path(args.out_jsonl).read_text().splitlines()]
    assert (
        len(lines) == 1
        and lines[0]["supersedes"] is None
        and lines[0]["evidence_version"] == 1
    )
    changed, _ = _run(
        tmp_path, store, _manifest(tmp_path, triage={"f1": "REAL_ESCAPE"})
    )
    lines = [json.loads(t) for t in Path(args.out_jsonl).read_text().splitlines()]
    assert changed["appended"] == 1 and len(lines) == 2
    assert (
        lines[1]["supersedes"] == lines[0]["record_digest"]
        and lines[1]["evidence_version"] == 2
    )


def test_the_snapshot_is_deterministic_and_carries_no_spend_or_verdict_words(tmp_path):
    store = _store(tmp_path, "r", 2, HELD_ROWS, findings=[("f1", "fam_a", "t-1")])
    backfill = _manifest(tmp_path, triage={"f1": "ORACLE_GAP"})
    _run(tmp_path, store, backfill)
    first = (tmp_path / "snapshot.json").read_text()
    _run(tmp_path, store, backfill)
    assert (tmp_path / "snapshot.json").read_text() == first
    text = first.lower()
    assert "usd" not in text and "booked" not in text and "balance" not in text
    snap = json.loads(first)
    assert snap["claims"] == sv.CLAIMS and any(
        r["id"] == "R5_ATTACKER" for r in snap["known_reds"]
    )
    assert all(
        word not in text
        for word in ('"secure"', '"qualified": true', '"accepted": true')
    )


def test_a_removal_is_proposed_from_a_real_escape_in_one_step_and_from_nothing_else(
    tmp_path,
):
    store = _store(
        tmp_path,
        "r",
        2,
        HELD_ROWS,
        findings=[
            ("f1", "fam_a", "t-1"),
            ("f2", "fam_b", "t-2"),
            ("f3", "fam_b", "t-3"),
        ],
    )
    backfill = _manifest(tmp_path, triage={"f1": "REAL_ESCAPE", "f2": "ORACLE_GAP"})
    _run(tmp_path, store, backfill)
    records = json.loads((tmp_path / "snapshot.json").read_text())["records"]
    removal, refusal = sv.propose_removal(
        "f1", records, proposed_by="graphite-lane", now=NOW
    )
    assert refusal is None and removal["schema"] == sv.REMOVAL_SCHEMA
    assert (
        removal["reason_code"] == "REAL_ESCAPE_UNFIXED"
        and removal["decision"]["state"] == "PROPOSED"
    )
    assert removal["effective_from"] is None and removal["claims"] == sv.CLAIMS
    assert (
        removal["justification"][0]["finding_id"] == "f1"
        and removal["entry_ref"] == records[0]["record_digest"]
    )
    assert (
        sv.propose_removal("f2", records, proposed_by="x", now=NOW)[1]
        == "not_a_removal_reason:ORACLE_GAP"
    )
    assert (
        sv.propose_removal("f3", records, proposed_by="x", now=NOW)[1]
        == "not_a_removal_reason:UNTRIAGED"
    )
    assert (
        sv.propose_removal("nope", records, proposed_by="x", now=NOW)[1]
        == "finding_not_found"
    )
