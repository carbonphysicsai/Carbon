"""miner_lookup (scripts/dev/miner_lookup.py): the read-only tool Miner X answers miners with (V2 ruling
MINER_LOOKUP_DISCLOSURE_20261120). Its replies can reach a public channel, so every test seeds the stores with CANARY
text in each hidden place and asserts the canary never reaches the output."""

from __future__ import annotations

import json
import re
import sqlite3
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import ledger as attempt_ledger
from scripts.dev import miner_lookup as ml
from scripts.dev.miner_launchpad import projection, supervisor

CANARY = "CANARY-HIDDEN-9f3a"
HOTKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
SAME_ENDS = "5FHn" + "A" * 40 + "94ty"
OTHER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
TASK = "rtsk_" + "ab" * 32
TASK_B = "rtsk_" + "cd" * 32
TASK_C = "rtsk_" + "ef" * 32
TASK_NEW = "rtsk_" + "34" * 32
TASK_D = "rtsk_" + "d1" * 32
TASK_E = "rtsk_" + "e2" * 32
T0 = 1_763_600_000


def _ns(seconds):
    return int(seconds * 1e9)


def _seed(path, rows, withdrawals=(), slots=()):
    db = sqlite3.connect(path)
    db.executescript(attempt_ledger.DDL)
    db.executescript(
        exam_cap._DDL
    )  # the receiver's own exam_graded / exam_requeues schema
    for at, kind, code, hotkey, task, state in rows:
        db.execute(
            "INSERT INTO attempts(at_ns,kind,code,hotkey,contract_digest,receipt,submission_sha256,submission_id,state)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (
                _ns(at),
                kind,
                code,
                hotkey,
                "d" * 8,
                CANARY,
                "sha256:" + CANARY,
                task,
                state,
            ),
        )
    for task, hotkey in withdrawals:
        db.execute(
            "INSERT INTO miner_withdrawals VALUES(?,?,?,?)",
            ("d" * 8, task, hotkey, _ns(T0)),
        )
    for task, hotkey, state, status in slots:
        db.execute(
            "INSERT INTO exam_graded(hotkey,challenge_id,challenge_version,exam_key,kind,epoch,submission_id,state,status,"
            "reserved_ns) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (hotkey, "c", "1.8", "k", "GRADED", 1, task, state, status, _ns(T0)),
        )
    db.commit()
    db.close()


def _marker(store, task, **body):
    (store / "markers").mkdir(exist_ok=True)
    (store / "markers" / (task + ".json")).write_text(json.dumps(body))


@pytest.fixture
def store(tmp_path):
    _seed(
        tmp_path / "attempts.sqlite3",
        [
            (T0, "RECEIVED", None, HOTKEY, TASK, None),
            (T0 + 600, "OUTCOME", None, HOTKEY, TASK, "ADMITTED"),
            (T0 + 10, "RECEIVED", None, HOTKEY, TASK_B, None),
            (T0 + 900, "OUTCOME", None, HOTKEY, TASK_B, "ADMITTED"),
            (T0 + 50, "OUTCOME", None, HOTKEY, TASK_D, "ADMITTED"),
            (T0 + 60, "OUTCOME", None, HOTKEY, TASK_E, "ADMITTED"),
            (T0 + 20, "RECEIVED", None, HOTKEY, TASK_C, None),
            (T0 + 30, "RECEIVED", None, HOTKEY, "entry-" + "7", None),
            (T0 + 40, "RECEIVED", None, SAME_ENDS, "rtsk_" + "12" * 32, None),
        ],
        slots=[
            (TASK, HOTKEY, "COUNTED", "WORKER_WALL_LIMIT_REACHED"),
            (TASK_B, HOTKEY, "RELEASED", "FAILED_INFRA"),
            (TASK_D, HOTKEY, "COUNTED", "MANDATORY_GATE_FAILED"),
        ],
    )
    _marker(tmp_path, TASK, state="CANDIDATE_FAILED", code="WORKER_WALL_LIMIT_REACHED")
    _marker(tmp_path, TASK_B, state="FAILED", code="WorkerFailure", detail=CANARY)
    _marker(tmp_path, TASK_D, state="GRADED", code=None)
    markers = tmp_path / "markers"
    markers.mkdir(exist_ok=True)
    (markers / (TASK_C + ".json")).write_text(
        json.dumps(
            {
                "state": "FAILED",
                "code": "cancelled_by_carbon_stop",
                "traceback": CANARY,
                "lane": CANARY + "-FSN1-10.0.0.1",
            }
        )
    )
    (tmp_path / "owed.tsv").write_text(
        "owed_id\ttask_id\tstate\tnew_task_id\n"
        f"V2-OWED-1\t{TASK_B}\tre-running\t{TASK_NEW}\n"
        f"V2-OWED-2\t{TASK_B}\tqueued\t-\n"
        f"BAD STATE\t{TASK}\tqueued\t-\n"
        f"V2-OWED-3\t{TASK}\tsecret ruling text {CANARY}\t-\n"
        f"V2-OWED-4\tnot-a-task\tdone\t-\n"
    )
    (tmp_path / "board.json").write_text(
        json.dumps(
            {
                "ladder": [
                    {
                        "rank": 1,
                        "hotkey": HOTKEY,
                        "total": 0.123456,
                        "status": "SCORED",
                        "gate_names": [CANARY],
                    },
                    {
                        "rank": 2,
                        "hotkey": OTHER,
                        "total": 0.1,
                        "status": "SCORED",
                        "gate_names": [],
                    },
                    {"rank": 3, "hotkey": "short", "total": 0.1, "status": "SCORED"},
                ]
            }
        )
    )
    return tmp_path


def _root(store, **extra):
    return ml.Root(
        store / "attempts.sqlite3",
        store / "markers",
        store / "owed.tsv",
        board=store / "board.json",
        **extra,
    )


def _ask(store, name, argument=None, **extra):
    text = ml.finish(ml.lookup(_root(store, **extra), name, argument))
    assert CANARY not in text
    return json.loads(text), text


def test_a_task_comes_out_as_the_allow_listed_fields_only(store):
    document, text = _ask(store, "task", TASK)
    task = document["task"]
    assert set(task) <= ml.ALLOWED_FIELDS["task"]
    assert task["task_id"] == TASK
    assert task["state"] == "CANDIDATE_FAILED"
    assert task["outcome_code"] == "CANDIDATE_FAILED"
    assert task["reason"].startswith("Grade state: ")
    assert task["charged"] == "yes"
    assert (
        task["owed"] == []
    )  # a row with an unlisted state or a bad id is dropped, never shown
    assert document["board"] == {"rank": 1, "total": 0.123, "status": "SCORED"}
    assert "FSN1" not in text and "traceback" not in text and "gate_names" not in text
    assert document["not_available"] == list(ml.NOT_AVAILABLE)


def test_an_infrastructure_failure_is_failed_infra_uncharged_with_the_slot_given_back(
    store,
):
    task = _ask(store, "task", TASK_B)[0]["task"]
    assert task["state"] == "FAILED_INFRA"
    assert task["charged"] == "no" and task["slot_given_back"] == "yes"
    assert task["outcome_code"] == "FAILED_INFRA"
    # V2's own owed ids and their state, never the ruling text
    assert task["owed"] == [
        {"owed_id": "V2-OWED-1", "state": "re-running", "rerun_task_id": TASK_NEW},
        {"owed_id": "V2-OWED-2", "state": "queued"},
    ]


def test_a_stop_cancelled_task_is_cancelled_in_the_validators_words_not_the_markers(
    store,
):
    task = _ask(store, "task", TASK_C)[0]["task"]
    assert task["state"] == "CANCELLED"
    assert task["outcome_code"] == "direct_task_cancelled"
    assert task["reason"] == supervisor.NEXT_ACTIONS["direct_task_cancelled"]


def test_a_code_outside_the_closed_tables_is_never_printed(tmp_path):
    odd = "rtsk_" + "99" * 32
    _seed(
        tmp_path / "attempts.sqlite3",
        [(T0, "REFUSED", CANARY + "_code", HOTKEY, odd, CANARY)],
    )
    task = _ask(tmp_path, "task", odd)[0]["task"]
    assert (
        task["outcome_code"] is None
        and task["reason"] is None
        and task["state"] == "REFUSED"
    )


def test_an_ambiguous_prefix_and_suffix_refuses_and_lists_nothing(store):
    with pytest.raises(ml.Refused) as refused:
        ml.lookup(_root(store), "hotkey", HOTKEY[:4] + "..." + HOTKEY[-4:])
    assert refused.value.code == "hotkey_ambiguous_send_more_characters"
    assert HOTKEY not in str(refused.value) and SAME_ENDS not in str(refused.value)


def test_a_full_hotkey_lists_only_its_own_tasks_without_the_long_reason(store):
    document, text = _ask(store, "hotkey", HOTKEY)
    ids = [t.get("task_id") for t in document["tasks"]]
    assert set(ids) == {TASK, TASK_B, TASK_C, TASK_D, TASK_E}
    assert all("reason" not in t for t in document["tasks"])
    assert (
        "rtsk_" + "12" * 32 not in text
        and SAME_ENDS not in text
        and "entry-7" not in text
    )


def test_a_withdrawn_task_is_cancelled_and_says_withdrawn(tmp_path):
    _seed(
        tmp_path / "attempts.sqlite3",
        [(T0, "RECEIVED", None, HOTKEY, TASK, None)],
        withdrawals=[(TASK, HOTKEY)],
    )
    task = _ask(tmp_path, "task", TASK)[0]["task"]
    assert task["state"] == "CANCELLED" and task["withdrawn"] is True


def test_a_short_task_prefix_resolves_and_an_unknown_or_malformed_one_is_refused(store):
    assert _ask(store, "task", "abababab")[0]["task"]["task_id"] == TASK
    for argument in ("12345678", "not-hex!", None):
        with pytest.raises(ml.Refused):
            ml.lookup(_root(store), "task", argument)


def test_an_entry_id_that_is_not_a_task_is_echoed_as_an_entry(store):
    task = _ask(store, "entry", "entry-7")[0]["task"]
    assert task["entry_id"] == "entry-7" and "task_id" not in task
    for argument in ("bad id!", "x" * 65, None):
        with pytest.raises(ml.Refused):
            ml.lookup(_root(store), "entry", argument)
    with pytest.raises(ml.Refused) as refused:
        ml.lookup(_root(store), "entry", "nothing-here")
    assert refused.value.code == "entry_not_found"


class _Feed(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(
            {
                "door_state": "grading",
                "waiting_to_build": 3,
                "building_now": 1,
                "waiting_to_grade": 2,
                "grading_now": 1,
                "wait_24h": {
                    "verdicts": 9,
                    "median_s": 7200,
                    "p90_s": 9000,
                    "reason": CANARY,
                },
                "as_of": "2026-11-20T12:00:00Z",
                "internal_reason": CANARY,
                "rows": [
                    {
                        "position": 1,
                        "hotkey": HOTKEY[:4] + "…" + HOTKEY[-4:],
                        "state": "grading",
                        "in_queue_s": 600,
                        "x": CANARY,
                    },
                    {
                        "position": 2,
                        "hotkey": OTHER,
                        "state": "waiting to grade",
                        "in_queue_s": 300,
                    },
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def feed():
    server = HTTPServer(("127.0.0.1", 0), _Feed)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/carbon/v1/queue/motor"
    server.shutdown()


def test_the_public_queue_is_rebuilt_field_by_field(store, feed):
    document, text = _ask(store, "public", "queue", queue_url=feed)
    queue = document["queue"]
    assert set(queue) <= ml.ALLOWED_FIELDS["queue"]
    assert queue["wait_24h"] == {"verdicts": 9, "median_s": 7200, "p90_s": 9000}
    # a full address in a row is not the feed's short form: it is dropped, never printed
    assert queue["rows"][1]["hotkey"] is None and OTHER not in text
    assert queue["rows"][0]["hotkey"] == HOTKEY[:4] + "…" + HOTKEY[-4:]


def test_a_hotkeys_own_queue_rows_are_the_only_rows_in_its_answer(store, feed):
    document, _ = _ask(store, "hotkey", HOTKEY, queue_url=feed)
    assert [r["position"] for r in document["queue_rows"]] == [1]


def test_the_public_board_shows_short_hotkeys_and_only_rank_total_status(store):
    board = _ask(store, "public", "board")[0]["board"]
    assert [row["rank"] for row in board] == [1, 2]
    assert board[0] == {
        "rank": 1,
        "total": 0.123,
        "status": "SCORED",
        "hotkey": HOTKEY[:4] + "…" + HOTKEY[-4:],
    }
    assert HOTKEY not in json.dumps(board)


def test_the_one_switch_turns_every_own_subcommand_off_and_leaves_public_working(
    store, monkeypatch
):
    monkeypatch.setattr(ml, "OWN_READ", "off")
    for name, argument in (("hotkey", HOTKEY), ("task", TASK), ("entry", "entry-7")):
        with pytest.raises(ml.Refused) as refused:
            ml.lookup(_root(store), name, argument)
        assert refused.value.code == "own_fields_off"
    assert _ask(store, "public", "board")[0]["board"]


def test_verify_is_a_refusal_in_this_head(store):
    assert ml.parse_words(["verify", HOTKEY, "nonce", "sig"]) == ("verify", None)
    with pytest.raises(ml.Refused) as refused:
        ml.lookup(_root(store), "verify")
    assert refused.value.code == "verify_not_built"


def test_the_ledger_is_opened_read_only_and_query_only(store):
    db = _root(store).db()
    try:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("INSERT INTO meta VALUES('k','v')")
    finally:
        db.close()


def test_finish_refuses_a_document_with_anything_off_the_list(store):
    document = ml.lookup(_root(store), "task", TASK)
    document["task"]["receipt"] = CANARY
    with pytest.raises(ml.Refused):
        ml.finish(document)
    with pytest.raises(ml.Refused):
        ml.finish({"asked": "task", "secret": 1})


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", "a" * 40),
        ("reason", "deadbeef" * 5),
        ("state", "0123456789abcdef0123456789abcdef"),
        ("task_id", "rtsk_" + "ab" * 31),
        ("outcome_code", "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0+/"),
    ],
)
def test_finish_refuses_secret_shaped_text_outside_the_named_id_fields(
    store, field, value
):
    document = ml.lookup(_root(store), "task", TASK)
    document["task"][field] = value
    with pytest.raises(ml.Refused) as refused:
        ml.finish(document)
    assert refused.value.code == "secret_shaped_text"


def test_an_oversized_answer_is_refused_not_cut(store):
    document = ml.lookup(_root(store), "task", TASK)
    document["task"]["owed"] = [{"owed_id": "X", "state": "queued"}] * 20000
    with pytest.raises(ml.Refused) as refused:
        ml.finish(document)
    assert refused.value.code == "answer_too_large"


@pytest.mark.parametrize(
    "command",
    [
        "ls",
        "bash -c id",
        "hotkey",
        "hotkey a b",
        "hotkey --config /etc/passwd",
        "public queue; cat /etc/passwd",
        "verify a b",
        "miner_lookup",
        "miner_lookup hotkey a b c d",
        "task 'x",
        "",
    ],
)
def test_a_forced_command_accepts_one_subcommand_and_nothing_else(command):
    with pytest.raises(ml.Refused):
        ml.parse_ssh_command(command)


def test_a_forced_command_with_one_subcommand_parses():
    assert ml.parse_ssh_command("task " + TASK) == ("task", TASK)
    assert ml.parse_ssh_command("miner_lookup public queue") == ("public", "queue")
    assert ml.parse_ssh_command("hotkey " + HOTKEY) == ("hotkey", HOTKEY)


def _config(store, **extra):
    body = {
        "ledger": str(store / "attempts.sqlite3"),
        "markers": str(store / "markers"),
        "owed_tasks": str(store / "owed.tsv"),
        "board": str(store / "board.json"),
        "audit": str(store / "audit.tsv"),
        **extra,
    }
    path = store / "config.json"
    path.write_text(json.dumps(body))
    return str(path)


def test_main_prints_json_and_audits_subcommand_asked_and_bytes_but_no_output(
    store, capsys
):
    config = _config(store)
    assert ml.main(["--config", config, "hotkey", HOTKEY]) == 0
    out = capsys.readouterr().out
    assert CANARY not in out and json.loads(out)["tasks"]
    audit = store / "audit.tsv"
    fields = audit.read_text().splitlines()[-1].split("\t")
    assert fields[1:3] == ["hotkey", HOTKEY] and int(fields[3]) == len(
        out.rstrip("\n").encode("utf-8")
    )
    assert stat.S_IMODE(audit.stat().st_mode) == 0o600
    assert TASK not in audit.read_text()
    assert ml.main(["--config", config, "hotkey", "x"]) == 2
    assert json.loads(capsys.readouterr().out) == {"refused": "hotkey_form"}


def test_the_audit_never_takes_a_forged_argument_with_a_newline_or_tab(store, capsys):
    config = _config(store)
    ml.main(["--config", config, "entry", "a\nb\tc"])
    capsys.readouterr()
    lines = (store / "audit.tsv").read_text().splitlines()
    assert len(lines) == 1 and lines[0].split("\t")[2] == "-"


def test_the_ssh_mode_takes_only_the_asker_words_from_the_environment(store, capsys):
    config = _config(store)
    ok = {"SSH_ORIGINAL_COMMAND": "task " + TASK}
    assert ml.main(["--config", config, "ssh"], ok) == 0
    assert json.loads(capsys.readouterr().out)["task"]["task_id"] == TASK
    for command in ("bash -c id", "hotkey --config /etc/passwd", None):
        env = {} if command is None else {"SSH_ORIGINAL_COMMAND": command}
        assert ml.main(["--config", config, "ssh"], env) == 2
        assert json.loads(capsys.readouterr().out) == {"refused": "command_form"}


def test_a_missing_or_wrong_config_is_a_refusal_not_a_traceback(store, capsys):
    assert ml.main(["--config", str(store / "nope.json"), "public", "queue"]) == 2
    assert json.loads(capsys.readouterr().out) == {"refused": "config_unreadable"}
    bad = store / "bad.json"
    bad.write_text(json.dumps({"ledger": "x", "shell": "rm -rf /"}))
    assert ml.main(["--config", str(bad), "public", "queue"]) == 2
    assert json.loads(capsys.readouterr().out) == {"refused": "config_invalid"}


def test_the_word_tables_are_the_launchpads_own_words():
    assert ml.WORDS_NEXT == supervisor.NEXT_ACTIONS
    assert ml.WORDS_GRADE == projection.GRADE_STATE_WORDS
    source = Path(ml.__file__).read_text(encoding="utf-8")
    start, end = source.index(ml.START), source.index(ml.END) + len(ml.END)
    assert (
        source[start:end] == ml.words_block()
    ), "run: python -m scripts.dev.miner_lookup --write-words"


def test_the_tool_is_one_self_contained_file_that_imports_no_repository_code():
    source = Path(ml.__file__).read_text(encoding="utf-8")
    before_generator = source[: source.index("# --- generator")]
    assert not re.search(
        r"^\s*(from|import)\s+(carbon|scripts)\b", before_generator, re.MULTILINE
    )


def test_a_task_that_was_only_admitted_is_queued_never_succeeded(store):
    # sre's 22:44Z check on the live ledger: an ADMITTED attempt row said SUCCEEDED, whatever happened after.
    task = _ask(store, "task", TASK_E)[0]["task"]
    assert task["state"] == "QUEUED" and task["charged"] == "not stated"
    assert task["outcome_code"] == "QUEUED"


def test_a_graded_task_that_failed_its_gate_is_graded_and_counted_not_succeeded(store):
    task = _ask(store, "task", TASK_D)[0]["task"]
    assert task["state"] == "GRADED" and task["charged"] == "yes"


def test_the_state_follows_the_receivers_own_rule_for_every_marker_and_slot(tmp_path):
    cases = [
        # marker, slot (state, status), expected state, charged, slot given back
        (
            {"state": "GRADED", "code": None},
            ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE"),
            "GRADED",
            "yes",
            "not stated",
        ),
        (
            {"state": "GRADED", "code": None},
            ("RESERVED", None),
            "GRADED",
            "yes",
            "not stated",
        ),
        (
            {"state": "GRADED", "code": None},
            ("RELEASED", "SLOT_RETURNED"),
            "GRADED",
            "no",
            "yes",
        ),
        ({"state": "GRADED", "code": None}, (None, None), "NOT_GRADED", "no", "yes"),
        (
            {"state": "GRADED", "code": None},
            ("RELEASED", "FAILED_INFRA"),
            "NOT_GRADED",
            "no",
            "yes",
        ),
        (
            {"state": "GRADED", "code": "epoch_limit_reached"},
            (None, None),
            "ROUND_LIMIT_REACHED",
            "no",
            "not stated",
        ),
        (
            {"state": "GRADED", "code": "exam_daily_allowance_reached"},
            (None, None),
            "ROUND_LIMIT_REACHED",
            "no",
            "not stated",
        ),
        (
            {"state": "DUPLICATE"},
            ("COUNTED", "DUPLICATE_OF_EARLIER"),
            "GRADED",
            "yes",
            "not stated",
        ),
        (
            {"state": "CANDIDATE_FAILED"},
            ("COUNTED", "WORKER_WALL_LIMIT_REACHED"),
            "CANDIDATE_FAILED",
            "yes",
            "not stated",
        ),
        (
            {"state": "FAILED", "code": "WorkerFailure"},
            ("RELEASED", "FAILED_INFRA"),
            "FAILED_INFRA",
            "no",
            "yes",
        ),
        ({"state": "VERSION_CLOSED"}, (None, None), "NOT_GRADED", "no", "yes"),
    ]
    for number, (marker, slot, state, charged, given_back) in enumerate(cases):
        folder = tmp_path / f"c{number}"
        folder.mkdir()
        task = "rtsk_" + f"{number:02x}" * 32
        _seed(
            folder / "attempts.sqlite3",
            [(T0, "OUTCOME", None, HOTKEY, task, "ADMITTED")],
            slots=[(task, HOTKEY) + slot] if slot[0] else [],
        )
        _marker(folder, task, **marker)
        shown = _ask(folder, "task", task)[0]["task"]
        assert (shown["state"], shown["charged"], shown["slot_given_back"]) == (
            state,
            charged,
            given_back,
        ), (number, marker, slot, shown)
        assert shown["outcome_code"] is not None and shown["reason"] is not None


def test_a_ledger_without_the_slot_table_still_answers_and_says_not_stated(tmp_path):
    db = sqlite3.connect(tmp_path / "attempts.sqlite3")
    db.executescript(attempt_ledger.DDL)
    db.execute(
        "INSERT INTO attempts(at_ns,kind,hotkey,contract_digest,submission_sha256,submission_id,state) VALUES(?,?,?,?,?,?,?)",
        (_ns(T0), "OUTCOME", HOTKEY, "d" * 8, "s", TASK, "ADMITTED"),
    )
    db.commit()
    db.close()
    _marker(tmp_path, TASK, state="GRADED", code=None)
    task = _ask(tmp_path, "task", TASK)[0]["task"]
    assert task["state"] == "NOT_GRADED"
