"""Submission terms at the door (owner G-LEAD-50, OWNER_LINES block 47; v2 scope read row 4781; wire row 4815).

Claims: only the Challenge versions named in the terms table require terms (stand-in versions here; owner G-LEAD-122
keeps the real ones off the public tree), and the live Motor 1.8 door is
unchanged (no ``terms`` in discovery, the strict two submit fields); a terms door advertises {version, sha256, path} and
serves the text only when it is the pinned published one; a ``construction_submit`` there must carry the door's current
``terms_version`` + ``terms_sha256`` inside the hotkey-signed body, else it is refused (``terms_not_accepted`` /
``terms_mismatch``, 400, the door's terms in the answer) before anything is admitted; while the sha is unpinned or the
text is not the pinned one, every submission is refused ``terms_unavailable`` (503, refuse-without); an admitted one
first leaves an append-only acceptance row holding the signed request (body + ``x-bittensor-*`` headers only).
Synthetic text and hotkeys only; the real text's sha is pinned by a later values head.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from test_c08_authenticated_miner_mcp import CONTEXT, NOW, _snapshot, _Verifier
from test_direct_recipe_intake import _signed
from test_direct_v3_durable_tasks import _fixture

from carbon.battery.intake import SnapshotWindow
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator import submission_terms as st
from carbon.challenge_validator.direct_intake import (
    INFO_PATH,
    SUBMIT_PATH,
    SUBMIT_TOOL,
    DirectRecipeIntake,
)
from carbon.transport.store import ReceiptJournal

TEXT = b"Synthetic submission terms for a test door.\nNot the published text.\n"
SHA = hashlib.sha256(TEXT).hexdigest()
VERSION = "carbon-submission-terms-v0"
#: The published text's sha (miner-ux 4825), verified by v2 (row 4828) against the owner-approved wording.
PUBLISHED_SHA = "946244f64b9c8580010595822ad997eb22e7184dd4074dfca808868c30232faa"
ROOT = Path(__file__).resolve().parents[2]
#: Two stand-in versions that require the terms (the public table names none, owner G-LEAD-122).
TERMS_A = ("zz-terms-family", "1.0")
TERMS_B = ("zz-terms-family", "2.0")


@pytest.fixture(autouse=True)
def _terms_table(monkeypatch):
    monkeypatch.setattr(st, "TERMS_BY_VERSION", {TERMS_A: VERSION, TERMS_B: VERSION})


# --- the per-version table (v2 4781 (1): per version, never the live 1.8 door) ---


def test_only_the_named_next_opens_require_terms():
    assert st.required_version(*TERMS_A) == VERSION
    assert st.required_version(*TERMS_B) == VERSION
    for live in (
        ("electric-motor-magnetics", "1.8"),
        ("f08-ribbed-bracket", "1.7"),
        ("f02", "2.5"),
        ("chip-cold-plate", "1.6"),
    ):
        assert st.required_version(*live) is None
        assert st.for_door(*live, "/nowhere/terms.md") is None
    # the PUBLISHED text's sha, pinned after v2's byte check; a door whose text file is missing refuses everything
    assert st.PINNED_SHA256[VERSION] == PUBLISHED_SHA
    terms = st.for_door(*TERMS_A, "/nowhere/terms.md")
    assert terms.version == VERSION and not terms.ready


def test_the_pin_is_the_checkouts_published_file_once_it_is_there():
    published = ROOT / "docs" / "terms" / (VERSION + ".md")
    if not published.is_file():
        pytest.skip(
            "docs/terms lands with the client + publication head (miner-ux 4825)"
        )
    assert hashlib.sha256(published.read_bytes()).hexdigest() == PUBLISHED_SHA
    terms = st.for_door(*TERMS_A, str(published))
    assert terms.ready and terms.text == published.read_bytes()


def test_the_text_is_served_only_when_it_is_the_pinned_one(tmp_path, monkeypatch):
    path = tmp_path / "terms.md"
    path.write_bytes(TEXT)
    assert st.read_text(path, SHA) == TEXT
    assert st.read_text(path, "0" * 64) is None
    assert st.read_text(path, None) is None
    assert st.read_text(tmp_path / "missing.md", SHA) is None
    big = tmp_path / "big.md"
    big.write_bytes(b"a" * (st.MAX_TEXT_BYTES + 1))
    assert st.read_text(big, hashlib.sha256(big.read_bytes()).hexdigest()) is None
    latin = tmp_path / "latin.md"
    latin.write_bytes(b"\xe9t\xe9")
    assert st.read_text(latin, hashlib.sha256(b"\xe9t\xe9").hexdigest()) is None
    monkeypatch.setitem(st.PINNED_SHA256, VERSION, SHA)
    terms = st.for_door(*TERMS_B, str(path))
    assert terms.ready and terms.text == path.read_bytes()
    assert terms.facts() == {
        "version": VERSION,
        "sha256": SHA,
        "path": "/carbon/v1/terms/" + VERSION,
    }


def test_the_submit_fields_of_a_terms_door_and_of_a_door_without_terms():
    terms = st.Terms(VERSION, SHA, TEXT)
    recipe = {"strategy_json": "{}", "contract_digest": "sha256:" + "a" * 64}
    accepted = {**recipe, "terms_version": VERSION, "terms_sha256": SHA}
    assert st.check_fields(None, recipe) == (None, recipe)
    assert st.check_fields(None, accepted) == ("submission_fields", None)
    assert st.check_fields(terms, recipe) == (st.NOT_ACCEPTED, None)
    assert st.check_fields(terms, accepted) == (None, recipe)
    assert st.check_fields(terms, {**accepted, "terms_sha256": "0" * 64}) == (
        st.MISMATCH,
        None,
    )
    assert st.check_fields(terms, {**accepted, "terms_version": "v-old"}) == (
        st.MISMATCH,
        None,
    )
    assert st.check_fields(terms, {**recipe, "terms_version": VERSION}) == (
        "submission_fields",
        None,
    )


# --- the acceptance record: append-only, the signed request, signature headers only ---


class _Challenge:
    challenge_id, version = TERMS_A


def test_the_acceptance_record_is_append_only_and_keeps_the_signed_request(tmp_path):
    store = st.AcceptanceStore(tmp_path / st.RECORD_NAME)
    terms = st.Terms(VERSION, SHA, TEXT)
    headers = {
        "X-Bittensor-Signature": "0x" + "ab" * 64,
        "x-bittensor-hotkey": "5" + "F" * 47,
        "X-Forwarded-For": "198.51.100.7",
        "Cookie": "c=1",
    }
    receipt = {"sequence": 7, "digest": "sha256:" + "1" * 64, "block": 100}
    kwargs = {
        "receipt": receipt,
        "hotkey": "5" + "F" * 47,
        "challenge": _Challenge,
        "terms": terms,
        "body": b'{"signed":"body"}',
        "headers": headers,
    }
    store.record(**kwargs)
    store.record(**kwargs)  # the same receipt again: one row
    (row,) = store.rows()
    assert row["request_body"] == b'{"signed":"body"}'
    assert row["request_sha256"] == hashlib.sha256(b'{"signed":"body"}').hexdigest()
    assert json.loads(row["auth_headers"]) == {
        "x-bittensor-hotkey": "5" + "F" * 47,
        "x-bittensor-signature": "0x" + "ab" * 64,
    }
    assert (row["terms_version"], row["terms_sha256"]) == (VERSION, SHA)
    # another acceptance claiming the same receipt is not silently merged
    with pytest.raises(st.TermsUnavailable):
        store.record(**{**kwargs, "hotkey": "5" + "G" * 47})
    with sqlite3.connect(tmp_path / st.RECORD_NAME) as connection:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("UPDATE acceptance SET terms_sha256 = 'x'")
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("DELETE FROM acceptance")
    assert len(store.rows()) == 1


def test_an_unwritable_record_is_terms_unavailable(tmp_path):
    store = st.AcceptanceStore(tmp_path / "no-such-dir" / st.RECORD_NAME)
    with pytest.raises(st.TermsUnavailable):
        store.record(
            receipt={"sequence": 1, "digest": "d", "block": 1},
            hotkey="h",
            challenge=_Challenge,
            terms=st.Terms(VERSION, SHA, TEXT),
            body=b"{}",
            headers={},
        )


# --- the real intake, end to end on a synthetic door ---


@pytest.fixture
def door(tmp_path, monkeypatch):
    request, provider_factory, discovery = _fixture(
        tmp_path / "direct", monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    state = _snapshot()
    window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
    window.add(state)
    intake = DirectRecipeIntake(
        context=CONTEXT,
        receiver="validator",
        journal=ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
        verifier=_Verifier(),
        window=window,
        discovery=discovery,
        provider_for=lambda owner: provider if owner == "miner" else None,
        attempt_ledger=AttemptLedger(root / "ledger.sqlite3"),
        clock_ns=lambda: NOW,
    )
    try:
        yield intake, request, state, provider, root
    finally:
        provider.close()


def _submit(intake, request, state, n, **terms_fields):
    fields = {
        "strategy_json": json.dumps(request.recipe, sort_keys=True),
        "contract_digest": intake.adapter.contract_digest,
        **terms_fields,
    }
    body, headers = _signed(
        state,
        request.challenge_key,
        SUBMIT_TOOL,
        fields,
        request=f"terms-submit-{n:04d}",
        nonce=NOW + n,
    )
    headers["X-Bittensor-Signature"] = "sig-" + str(n)
    headers["X-Forwarded-For"] = "198.51.100.7"
    return intake.handle("POST", SUBMIT_PATH, headers, body, "127.0.0.1"), body


def test_a_door_without_terms_is_unchanged(door):
    intake, request, state, provider, _root = door
    assert "terms" not in intake.handle("GET", INFO_PATH, {}, b"", "127.0.0.1").body
    answer, _ = _submit(
        intake, request, state, 1, terms_version=VERSION, terms_sha256=SHA
    )
    assert (answer.status, answer.body) == (400, {"refused": "submission_fields"})
    answer, _ = _submit(intake, request, state, 2)
    assert answer.status == 202 and len(provider.queued_tasks()) == 1


def test_a_terms_door_refuses_without_the_signed_acceptance_and_keeps_the_one_it_admits(
    door,
):
    intake, request, state, provider, root = door
    intake.submission_terms = st.Terms(VERSION, SHA, TEXT)
    intake.terms_store = st.AcceptanceStore(root / st.RECORD_NAME)
    facts = intake.handle("GET", INFO_PATH, {}, b"", "127.0.0.1").body["terms"]
    assert facts == {"version": VERSION, "sha256": SHA, "path": st.path_of(VERSION)}
    text = intake.handle("GET", facts["path"], {}, b"", "127.0.0.1")
    # the exact bytes, served as they are (the client hashes them against the facts)
    assert (text.status, text.body) == (200, TEXT)

    for n, fields, code in (
        (1, {}, st.NOT_ACCEPTED),
        (2, {"terms_version": VERSION, "terms_sha256": "0" * 64}, st.MISMATCH),
    ):
        answer, _ = _submit(intake, request, state, n, **fields)
        assert answer.status == 400
        assert answer.body == {"refused": code, "terms": facts}
    assert len(provider.queued_tasks()) == 0 and intake.terms_store.rows() == []

    answer, body = _submit(
        intake, request, state, 3, terms_version=VERSION, terms_sha256=SHA
    )
    assert answer.status == 202 and answer.body["outcome"]["state"] == "ADMITTED"
    (row,) = intake.terms_store.rows()
    assert row["request_body"] == body and row["hotkey"] == "miner"
    assert json.loads(row["auth_headers"]) == {"x-bittensor-signature": "sig-3"}
    assert (row["terms_version"], row["terms_sha256"]) == (VERSION, SHA)


def test_an_unpinned_or_unready_terms_door_admits_nothing(door):
    intake, request, state, provider, root = door
    intake.submission_terms = st.Terms(
        VERSION, None, None
    )  # published sha not pinned yet
    intake.terms_store = st.AcceptanceStore(root / st.RECORD_NAME)
    facts = intake.handle("GET", INFO_PATH, {}, b"", "127.0.0.1").body["terms"]
    assert facts["sha256"] is None
    assert intake.handle("GET", facts["path"], {}, b"", "127.0.0.1").status == 503
    answer, _ = _submit(
        intake, request, state, 1, terms_version=VERSION, terms_sha256=None
    )
    assert answer.status == 503 and answer.body["refused"] == st.UNAVAILABLE
    # a pinned sha whose text file is missing on the host: still nothing admitted
    intake.submission_terms = st.Terms(VERSION, SHA, None)
    answer, _ = _submit(
        intake, request, state, 2, terms_version=VERSION, terms_sha256=SHA
    )
    assert answer.status == 503 and answer.body["refused"] == st.UNAVAILABLE
    assert len(provider.queued_tasks()) == 0 and intake.terms_store.rows() == []


# --- the receiver config key ---


def test_the_receiver_reads_the_terms_text_path_as_an_absolute_operator_file(
    tmp_path, monkeypatch
):
    from test_direct_receiver import _config

    from carbon.challenge_validator import direct_receiver as receiver

    cfg = {**_config(tmp_path), "submission_terms_text": str(tmp_path / "terms.md")}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
    cfg = {**_config(tmp_path), "submission_terms_text": "terms.md"}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    with pytest.raises(ValueError):
        receiver.load_config(tmp_path / "config.json")


# --- the listener writes the text byte for byte (never JSON-encoded), and every other answer as before ---


def _written(answer):
    import io

    from carbon.battery.intake import _handler

    handler = object.__new__(_handler(object()))
    handler.wfile = io.BytesIO()
    handler.request_version, handler.requestline, handler.command = (
        "HTTP/1.1",
        "GET / HTTP/1.1",
        "GET",
    )
    handler.client_address = ("127.0.0.1", 0)
    handler._answer(answer)
    head, _, payload = handler.wfile.getvalue().partition(b"\r\n\r\n")
    return head.decode("latin-1"), payload


def test_the_listener_serves_the_text_bytes_as_markdown_and_json_as_before():
    from carbon.battery.intake import Answer

    head, payload = _written(Answer(200, TEXT))
    assert payload == TEXT
    assert "Content-Type: text/markdown; charset=utf-8" in head
    assert f"Content-Length: {len(TEXT)}" in head
    head, payload = _written(Answer(400, {"refused": st.NOT_ACCEPTED}))
    assert json.loads(payload) == {"refused": st.NOT_ACCEPTED}
    assert "Content-Type: application/json" in head
