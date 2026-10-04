"""The miner's Graphite library and plans through both doors (S4).

OWNER-GRAPHITE-MINER-01: a Library (Control Center tab and MCP tools) shows
shared and private cards, search and the plan, and lets the miner pin, ban
and import. Here it is eleven rows of the one operations table - five reads
and six writes gated by replay - reached through the browser's
`/api/v1/library/*` and `/api/v1/plans/*` routes and the generated
`carbon_library_*` / `carbon_plan_*` MCP tools. None admits work, so none
reads registration. Every served card is UNCHECKED with its origin; a banned
card, a card of an unknown origin and a card naming protected material are
never served, whatever the library answers.

DEVELOPMENT FIXTURES, by name: the journey host and an in-memory stand-in for
S2's `MinerLibrary` (`test_launchpad_graphite.FakeLibrary`).
"""

from __future__ import annotations

import asyncio
import json
import threading

import pytest
from test_launchpad_graphite import (
    PACK,
    FakeLibrary,
    card,
    ensure_graphite_agent,
    plan_document,
)
from test_miner_launchpad import auth, request

from carbon.development_session.profile import canonical
from scripts.dev.miner_launchpad.controller import Rejected

KEY = "library-write-key-00001"


@pytest.fixture
def library_host(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad.journey_fixture import journey_host

    root = tmp_path / "home"
    root.mkdir(mode=0o700)
    ensure_graphite_agent(monkeypatch)
    host = journey_host(root, patch=monkeypatch.setattr)
    reads = []

    def registration(cfg):
        reads.append(cfg)
        raise AssertionError("a library operation never reads registration")

    host.registration = registration
    library = FakeLibrary(
        [
            card("arxiv-2101.00001v1"),
            card("own-1", "miner_hunt"),
            card("imported-1", "miner_import"),
            card("stray-1", "somewhere_else"),
            card("leaky-1", abstract="This uses the official seed of the exam."),
            card("internal-1", internal_note="Carbon-only field"),
        ]
    )
    host.library_root = root / "graphite-library"
    opened = []

    def open_library(path):
        opened.append(path)
        return library

    host.open_library = open_library
    host.shared_pack = lambda: PACK
    host.validate_plan = lambda plan, library_, curation: (
        (False, {"code": "cites_banned_card"})
        if {c["card_id"] for h in plan["hypotheses"] for c in h["cites"]}
        & set(curation["bans"])
        else (True, None)
    )
    yield host, library, opened
    host.close()


def run(host, name, body):
    from scripts.dev.miner_launchpad.operations import perform

    return perform(host, name, body)


def search_body(**extra):
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return {"query": "fast charge surrogate", "challenge": BATTERY_CHALLENGE, **extra}


# --- the table -----------------------------------------------------------------


LIBRARY_OPERATIONS = (
    "library_search",
    "library_card",
    "library_list",
    "plan_list",
    "plan_get",
    "library_pin",
    "library_unpin",
    "library_ban",
    "library_unban",
    "library_import",
    "plan_edit",
)


def test_the_library_is_eleven_operations_that_admit_no_work():
    from scripts.dev.miner_launchpad.operations import (
        LIBRARY_READS,
        LIBRARY_WRITES,
        OPERATIONS,
    )

    assert set(LIBRARY_READS) | set(LIBRARY_WRITES) == set(LIBRARY_OPERATIONS)
    for name in LIBRARY_OPERATIONS:
        op = OPERATIONS[name]
        assert op.admits_work is False, name
        # No registration read and no campaign: they start nothing.
        assert "registration" not in op.gates and "campaign" not in op.gates
        assert ("replay" in op.gates) == (name in LIBRARY_WRITES), name
        if name in LIBRARY_WRITES:
            assert "idempotency_key" in op.optional


def test_both_doors_list_the_library_tools():
    from carbon.miner_mcp.mcp_operations import make_operation_tools

    names = {t.name for t in make_operation_tools(object())}
    for name in LIBRARY_OPERATIONS:
        assert "carbon_" + name in names


def test_no_library_operation_reads_registration(library_host):
    host, library, _opened = library_host
    run(host, "library_list", {})
    run(host, "library_search", search_body())
    run(host, "library_pin", {"card_id": "own-1"})
    run(host, "library_import", {"title": "Notes", "text": "My notes."})
    plan = run(host, "plan_edit", {"plan_document": plan_document()})["digest"]
    run(host, "plan_get", {"plan": plan})
    run(host, "plan_list", {})
    assert library.writes  # it wrote, and the stub chain was never asked


# --- reads -------------------------------------------------------------------


def test_search_serves_only_what_a_miner_may_see(library_host):
    host, library, _opened = library_host
    library.pins.append("own-1")
    library.bans.append("arxiv-2101.00001v1")
    found = run(host, "library_search", search_body(card_limit=50))
    ids = [c["card_id"] for c in found["cards"]]
    # The banned card, a card of an unknown origin and one naming protected
    # material are never served, whatever the library answered.
    assert ids == ["own-1", "imported-1", "internal-1"]
    for served in found["cards"]:
        assert served["check_status"] == "UNCHECKED"
        assert served["origin"] in ("shared", "miner_hunt", "miner_import")
        assert "internal_note" not in served  # only the card's own fields
        assert served["score"] == 2.5 and served["reasons"]
    assert [c["pinned"] for c in found["cards"]] == [True, False, False]
    # S2's buildability under the Challenge's contract, served as booleans.
    assert [c["plan_input"] for c in found["cards"]] == [True, True, True]
    assert {c["capability_request_candidate"] for c in found["cards"]} == {False}
    assert found["check_status"] == "UNCHECKED" and found["untrusted"] is True
    (asked,) = library.searches
    assert asked["bans"] == ("arxiv-2101.00001v1",)
    assert asked["challenge"]["version"]  # resolved from the registry


def test_search_limits_and_query_are_bounded(library_host):
    host, _library, _opened = library_host
    assert len(run(host, "library_search", search_body(card_limit=1))["cards"]) == 1
    for body, code in (
        (search_body(card_limit=0), "card_limit_out_of_bounds"),
        (search_body(card_limit=51), "card_limit_out_of_bounds"),
        (search_body(query=""), "library_query_invalid"),
        (search_body(query="x" * 201), "library_query_invalid"),
        (search_body(query="a\x1bb"), "library_query_invalid"),
        (search_body(challenge="no-such-challenge"), "challenge_unknown"),
    ):
        with pytest.raises(Rejected) as refused:
            run(host, "library_search", body)
        assert refused.value.code == code, body


def test_a_card_is_served_unless_banned_unknown_or_protected(library_host):
    host, library, _opened = library_host
    served = run(host, "library_card", {"card_id": "own-1"})["card"]
    assert served["origin"] == "miner_hunt" and served["check_status"] == "UNCHECKED"
    library.bans.append("own-1")
    for card_id, code in (
        ("own-1", "card_banned"),
        ("nope-1", "card_not_found"),
        ("../../etc/passwd", "card_not_found"),
        ("leaky-1", "card_not_found"),
        ("stray-1", "card_not_found"),
    ):
        with pytest.raises(Rejected) as refused:
            run(host, "library_card", {"card_id": card_id})
        assert refused.value.code == code, card_id


def test_the_library_list_shows_the_pack_curation_imports_and_plans(library_host):
    host, library, _opened = library_host
    run(host, "library_import", {"title": "Notes", "text": "secret-ish text"})
    plan = run(host, "plan_edit", {"plan_document": plan_document()})["digest"]
    listed = run(host, "library_list", {})
    assert listed["shared_pack"] == {
        "available": True,
        "digest": PACK.digest,
        "cards": 1,
        "check_status": "UNCHECKED",
    }
    assert listed["curation"]["digest"] == library.curation()["digest"]
    # An import waiting for the Reader is listed by title and size only.
    assert listed["pending_imports"] == [
        {
            "import_id": "imp-1",
            "title": "Notes",
            "characters": 15,
            "origin": "miner_import",
        }
    ]
    assert "secret-ish" not in json.dumps(listed)
    assert [p["digest"] for p in listed["plans"]] == [plan]
    assert listed["plans"][0]["created_by"] == "miner"
    # S2's timestamp text, as the library recorded it.
    assert listed["plans"][0]["created_at"] == "2026-10-03T12:00:00Z"


def test_plans_are_listed_newest_first(library_host):
    host, library, _opened = library_host
    first = library.save_plan(plan_document())
    second = run(host, "plan_edit", {"plan_document": plan_document(parent=first)})
    listed = run(host, "plan_list", {})["plans"]
    # S2 lists them oldest first; the doors show the newest first.
    assert [p["digest"] for p in listed] == [second["digest"], first]
    assert [p["created_at"] for p in listed] == [
        "2026-10-03T12:00:01Z",
        "2026-10-03T12:00:00Z",
    ]
    from scripts.dev.miner_launchpad.runner import _plan_entry

    # A timestamp in any other form is never shown as given.
    assert (
        _plan_entry({"digest": first, "created_at": "yesterday"})["created_at"] is None
    )
    assert _plan_entry({"digest": first, "created_at": 1.5})["created_at"] == 1.5


@pytest.mark.parametrize(
    "code,answered,status",
    [
        ("card_not_found", "card_not_found", 404),
        ("card_banned", "card_banned", 409),
        ("plan_not_found", "plan_not_found", 404),
        ("plan_invalid", "plan_invalid", 409),
        ("import_invalid", "import_invalid", 400),
        ("search_invalid", "library_query_invalid", 400),
        # Any other code of S2's is not one a door names.
        ("evidence_invalid", "library_unavailable", 409),
        ("curation_not_found", "library_unavailable", 409),
    ],
)
def test_s2s_typed_refusals_are_answered_by_their_own_code(code, answered, status):
    from test_launchpad_graphite import LibraryError

    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    def refused():
        raise LibraryError(code, "detail with /a/private/path")

    with pytest.raises(Rejected) as caught:
        RunnerAdapter._library_call(refused)
    assert (caught.value.code, caught.value.status) == (answered, status)
    assert "private" not in str(caught.value)


def test_a_code_on_anything_but_s2s_refusal_is_not_trusted():
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    class Coded(RuntimeError):
        code = "card_not_found"

    def broken():
        raise Coded("not a refusal")

    with pytest.raises(Rejected) as caught:
        RunnerAdapter._library_call(broken)
    assert caught.value.code == "library_unavailable"


def test_s2s_refusals_reach_each_door_by_name(library_host):
    """The library raises S2's `LibraryError`, never a KeyError: an unknown
    card, a pin of one, an unknown plan and a refused import each answer
    their own code and step, not `library_unavailable`."""
    from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

    host, library, _opened = library_host
    library.refused_text = "a text S2 refuses"
    for name, body, code in (
        ("library_card", {"card_id": "nope-1"}, "card_not_found"),
        ("library_pin", {"card_id": "nope-1"}, "card_not_found"),
        ("library_ban", {"card_id": "nope-1"}, "card_not_found"),
        ("plan_get", {"plan": "sha256:" + "d" * 64}, "plan_not_found"),
        (
            "library_import",
            {"title": "Notes", "text": "a text S2 refuses"},
            "import_invalid",
        ),
    ):
        with pytest.raises(Rejected) as refused:
            run(host, name, body)
        assert refused.value.code == code, name
        assert code in NEXT_ACTIONS


def test_a_missing_pack_is_named_in_the_list(library_host):
    host, _library, _opened = library_host

    def missing():
        raise FileNotFoundError("the pack")

    host.shared_pack = missing
    assert run(host, "library_list", {})["shared_pack"] == {
        "available": False,
        "code": "literature_pack_missing",
    }


def test_the_library_lives_in_the_setup_root(tmp_path):
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    profile = tmp_path / "environment" / "runner-profile.json"
    profile.parent.mkdir(mode=0o700)
    profile.write_bytes(canonical({"principal": "alice"}))
    profile.chmod(0o600)
    host = RunnerAdapter(tmp_path / "runner.sqlite3", configuration=profile)
    try:
        assert host.library_root == tmp_path / "environment" / "graphite-library"
    finally:
        host.close()
    bare = RunnerAdapter(tmp_path / "bare.sqlite3", principal="alice")
    try:
        assert bare.library_root is None
        with pytest.raises(Rejected) as refused:
            run(bare, "library_list", {})
        assert refused.value.code == "library_unavailable"
    finally:
        bare.close()


def test_no_host_has_a_relative_library_root(tmp_path, monkeypatch):
    """S2's library refuses any root that is not absolute. A host's profile
    path is absolute and resolved - the profile reader refuses any other, so
    `--profile ./runner-profile.json` is refused before a host exists - and
    the library root is made absolute regardless."""
    from pathlib import Path

    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    profile = tmp_path / "environment" / "runner-profile.json"
    profile.parent.mkdir(mode=0o700)
    profile.write_bytes(canonical({"principal": "alice"}))
    profile.chmod(0o600)
    monkeypatch.chdir(tmp_path / "environment")
    relative = Path("./runner-profile.json")
    with pytest.raises(ValueError):
        RunnerAdapter(tmp_path / "relative.sqlite3", configuration=relative)
    with pytest.raises(ValueError):
        RunnerAdapter.for_profile(relative)
    host = RunnerAdapter(tmp_path / "runner.sqlite3", configuration=profile)
    try:
        assert host.library_root.is_absolute()
    finally:
        host.close()


# --- writes ------------------------------------------------------------------


def test_pins_and_bans_change_the_curation_only(library_host):
    host, library, _opened = library_host
    pinned = run(host, "library_pin", {"card_id": "own-1"})
    assert pinned["curation"]["pins"] == ["own-1"]
    assert pinned["curation_digest"] == library.curation()["digest"]
    banned = run(host, "library_ban", {"card_id": "arxiv-2101.00001v1"})
    assert banned["curation"]["bans"] == ["arxiv-2101.00001v1"]
    # A banned card cannot be pinned until the ban is lifted.
    with pytest.raises(Rejected) as refused:
        run(host, "library_pin", {"card_id": "arxiv-2101.00001v1"})
    assert refused.value.code == "card_banned"
    run(host, "library_unban", {"card_id": "arxiv-2101.00001v1"})
    run(host, "library_unpin", {"card_id": "own-1"})
    assert library.curation()["pins"] == [] and library.curation()["bans"] == []
    with pytest.raises(Rejected) as refused:
        run(host, "library_pin", {"card_id": "nope-1"})
    assert refused.value.code == "card_not_found"
    assert host.recent() == []  # no campaign, nothing started


def test_a_keyed_write_replays_its_answer_and_a_changed_one_conflicts(library_host):
    host, library, _opened = library_host
    first = run(host, "library_pin", {"card_id": "own-1", "idempotency_key": KEY})
    writes = len(library.writes)
    library.pins.clear()  # the library changed since; the answer replays
    assert (
        run(host, "library_pin", {"card_id": "own-1", "idempotency_key": KEY}) == first
    )
    assert len(library.writes) == writes
    with pytest.raises(Rejected) as refused:
        run(host, "library_pin", {"card_id": "imported-1", "idempotency_key": KEY})
    assert refused.value.code == "operation_replay_conflict"
    with pytest.raises(Rejected) as refused:
        run(host, "library_ban", {"card_id": "own-1", "idempotency_key": KEY})
    assert refused.value.code == "operation_replay_conflict"


def test_a_library_write_does_not_hold_the_hosts_lock(library_host):
    """S2's library serialises its own writes; the host's lock, which launches
    and operations take, is held only while a key is claimed and answered."""
    host, library, _opened = library_host
    taken = []
    pin = library.pin

    def watched(card_id):
        def other():
            if host.lock.acquire(timeout=5):
                taken.append(True)
                host.lock.release()

        thread = threading.Thread(target=other)
        thread.start()
        thread.join(timeout=10)
        return pin(card_id)

    library.pin = watched
    run(host, "library_pin", {"card_id": "own-1", "idempotency_key": KEY})
    run(host, "library_pin", {"card_id": "imported-1"})
    assert taken == [True, True]


def test_a_failed_keyed_write_leaves_its_key_free(library_host):
    host, library, _opened = library_host
    with pytest.raises(Rejected):
        run(host, "library_pin", {"card_id": "nope-1", "idempotency_key": KEY})
    library.cards["nope-1"] = card("nope-1")
    assert run(host, "library_pin", {"card_id": "nope-1", "idempotency_key": KEY})[
        "curation"
    ]["pins"] == ["nope-1"]


def test_an_import_is_queued_bounded_and_replayed_once(library_host):
    host, library, _opened = library_host
    body = {
        "title": "My notes",
        "text": "line one\r\nline two\tend",
        "idempotency_key": KEY,
    }
    queued = run(host, "library_import", body)
    assert queued["import_id"] == "imp-1" and queued["origin"] == "miner_import"
    assert run(host, "library_import", body) == queued
    assert len(library.imports) == 1
    for title, text in (
        ("", "text"),
        ("t" * 301, "text"),
        ("title", ""),
        ("title", "x" * 20001),
        ("title", "bidi " + chr(0x202E) + " override"),
        ("title", "nul \x00 byte"),
    ):
        with pytest.raises(Rejected) as refused:
            run(host, "library_import", {"title": title, "text": text})
        assert refused.value.code == "import_invalid"
    assert len(library.imports) == 1


def test_a_plan_edit_is_a_new_miner_plan_checked_by_the_plan_rule(library_host):
    host, library, _opened = library_host
    original = library.save_plan(plan_document())
    edited = run(
        host,
        "plan_edit",
        {"plan_document": json.dumps(plan_document(parent=original))},
    )
    assert edited["parent"] == original and edited["created_by"] == "miner"
    saved = run(host, "plan_get", {"plan": edited["digest"]})
    assert saved["plan"]["created_by"] == "miner"  # stamped by the door
    assert saved["plan"]["parent"] == original
    assert run(host, "plan_get", {"plan": original})["plan"]["created_by"] == "planner"
    assert edited["launch_with"] == {
        "agent": "graphite",
        "graphite_mode": "BUILD",
        "plan": edited["digest"],
    }
    listed = run(host, "plan_list", {})["plans"]
    assert {p["digest"] for p in listed} == {original, edited["digest"]}
    for document, code in (
        ({**plan_document(), "schema": "other"}, "plan_invalid"),
        (plan_document(parent="sha256:" + "c" * 64), "plan_not_found"),
        ("not json", "plan_document_required"),
        ([1, 2], "plan_document_required"),
    ):
        with pytest.raises(Rejected) as refused:
            run(host, "plan_edit", {"plan_document": document})
        assert refused.value.code == code
    library.bans.append("arxiv-2101.00001v1")
    with pytest.raises(Rejected) as refused:
        run(host, "plan_edit", {"plan_document": plan_document(parent=original)})
    assert refused.value.code == "plan_invalid"
    with pytest.raises(Rejected) as refused:
        run(host, "plan_get", {"plan": "sha256:" + "d" * 64})
    assert refused.value.code == "plan_not_found"


def test_plan_edit_runs_s3s_own_plan_rule(library_host):
    """At integration: the door with S3's own plan rule, as a host runs it,
    over this library: a left-out pin and a cite under another origin are
    refused with the rule's reason; the corrected plan is saved."""
    pytest.importorskip("carbon.agent_campaign.graphite.miner.plan")
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    host, library, _opened = library_host
    host.validate_plan = RunnerAdapter.validate_plan
    assert run(host, "plan_edit", {"plan_document": plan_document()})["digest"]
    library.pins.append("own-1")
    with pytest.raises(Rejected) as refused:
        run(host, "plan_edit", {"plan_document": plan_document()})
    assert refused.value.code == "plan_invalid"
    considered = {
        **plan_document(),
        "pins_considered": [{"card_id": "own-1", "consideration": "not for this"}],
    }
    assert run(host, "plan_edit", {"plan_document": considered})["digest"]
    wrong_origin = {**considered}
    wrong_origin["hypotheses"] = [
        {
            **considered["hypotheses"][0],
            "cites": [{"card_id": "own-1", "origin": "shared"}],
        }
    ]
    with pytest.raises(Rejected) as refused:
        run(host, "plan_edit", {"plan_document": wrong_origin})
    assert refused.value.code == "plan_invalid"


# --- the doors -----------------------------------------------------------------


@pytest.fixture
def browser(library_host, tmp_path):
    from scripts.dev.miner_launchpad import controller

    host = library_host[0]
    server = controller.Server(
        controller.Controller(tmp_path / "launchpad.sqlite3"),
        "x" * 40,
        port=0,
        research_runner=host,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def post(server, path, body):
    code, _headers, content = request(server, path, "POST", body, auth())
    return code, json.loads(content)


def test_the_browser_routes_are_the_shared_operations(browser, library_host):
    host, _library, _opened = library_host
    code, found = post(browser, "/api/v1/library/search", search_body())
    assert code == 200 and found == run(host, "library_search", search_body())
    code, listed = request(browser, "/api/v1/library", headers=auth())[::2]
    assert code == 200 and json.loads(listed)["schema"] == "carbon.launchpad.library.v1"
    code, plans = request(browser, "/api/v1/plans", headers=auth())[::2]
    assert code == 200 and json.loads(plans)["plans"] == []
    code, pinned = post(browser, "/api/v1/library/pin", {"card_id": "own-1"})
    assert code == 200 and pinned["curation"]["pins"] == ["own-1"]
    code, refused = post(browser, "/api/v1/library/card", {"card_id": "nope-1"})
    assert (code, refused["error"]) == (404, "card_not_found")
    assert refused["next_step"].startswith("No card")
    code, refused = post(browser, "/api/v1/library/delete", {"card_id": "own-1"})
    assert (code, refused["error"]) == (404, "route_not_found")
    code, refused = post(browser, "/api/v1/library/pin", {"card_id": "own-1", "x": 1})
    assert refused["error"] == "closed_request_required"


def test_the_library_page_script_is_served_when_it_ships(browser):
    """S5's Library tab is a page script the controller serves (S5 handoff);
    a checkout without it answers route_not_found, never a server error."""
    from pathlib import Path

    from scripts.dev.miner_launchpad import controller

    assert controller.STATIC["/library_view.js"][0] == "library_view.js"
    shipped = Path(controller.__file__).parent / "library_view.js"
    code, headers, body = request(browser, "/library_view.js")
    if shipped.is_file():
        assert code == 200 and body == shipped.read_bytes()
        assert headers["Content-Type"].startswith("text/javascript")
    else:
        assert (code, json.loads(body)["error"]) == (404, "route_not_found")


def test_an_import_of_twenty_thousand_characters_fits_its_routes(browser, library_host):
    _host, library, _opened = library_host
    text = "é" * 20000  # escaped as JSON, far beyond the 4 KiB default
    for path in ("/api/v1/library/import", "/api/v1/operations/library_import"):
        code, queued = post(browser, path, {"title": "Long", "text": text})
        assert code == 200, queued
    assert [len(item["text"]) for item in library.imports] == [20000, 20000]
    # Every other route keeps its 4 KiB bound.
    code, refused = post(
        browser, "/api/v1/library/pin", {"card_id": "own-1", "pad": "x" * 5000}
    )
    assert (code, refused["error"]) == (413, "body_size_limit")


def test_the_mcp_tools_reach_the_same_bodies(library_host):
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.mcp_operations import make_operation_tools

    host, _library, _opened = library_host
    tools = {t.name: t for t in make_operation_tools(host)}
    result = asyncio.run(tools["carbon_library_search"].fn(**search_body()))
    assert result.payload == run(host, "library_search", search_body())
    pinned = asyncio.run(
        tools["carbon_library_pin"].fn(card_id="own-1", idempotency_key=KEY)
    )
    assert pinned.payload["curation"]["pins"] == ["own-1"]
    assert pinned.idempotency_key == KEY
    with pytest.raises(ToolError) as refused:
        asyncio.run(tools["carbon_library_card"].fn(card_id="nope-1"))
    text = str(refused.value)
    answer = json.loads(text[text.index("{") :])
    assert (answer["error"], answer["field"]) == ("card_not_found", "card_id")


def test_the_mcp_launch_schema_states_graphites_fields():
    from pydantic import ValidationError

    from carbon.miner_mcp.mcp_operations import make_operation_tools

    launch = {t.name: t for t in make_operation_tools(object())}["carbon_launch"]
    properties = launch.parameters["properties"]
    assert {"graphite_mode", "research_share", "plan", "hunt", "limits"} <= set(
        properties
    )
    modes = json.dumps(properties["graphite_mode"])
    assert all('"' + m + '"' in modes for m in ("RESEARCH", "BUILD", "FULL"))
    agent = json.dumps(properties["agent"])
    for value in ("graphite", "carbon-graphite", "none", "own-agent"):
        assert '"' + value + '"' in agent
    model = launch.fn_metadata.arg_model
    base = {"agent": "graphite", "challenge": "c", "challenge_version": "1"}
    assert model.model_validate({**base, "research_share": 0.25}).research_share == 0.25
    assert model.model_validate({**base, "research_share": 1}).research_share == 1
    with pytest.raises(ValidationError):
        model.model_validate({**base, "research_share": True})
    with pytest.raises(ValidationError):
        model.model_validate({**base, "research_share": "0.1"})
