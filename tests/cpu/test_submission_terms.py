"""The Carbon submission terms on the miner's side (owner G-LEAD-50): read, show, accept, send; refuse without."""

from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.error
from pathlib import Path

import pytest

from carbon.development_session import direct_submission as client
from carbon.development_session import submission_terms as terms
from scripts.dev.miner_launchpad import supervisor
from tests.cpu import test_direct_submission as fixture

TEXT = "**Carbon submission terms, version v0**\n\nA test text, not the published one.\n".encode("utf-8")
SHA = hashlib.sha256(TEXT).hexdigest()
VERSION = "carbon-submission-terms-v0"
FACT = {"version": VERSION, "sha256": SHA, "path": terms.PATH_PREFIX + VERSION}


def _facts(**changes):
    return {**fixture._facts(), "terms": {**FACT, **changes}}


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(body=TEXT, seen=None):
    def opener(request, timeout):
        if seen is not None:
            seen.append(request.full_url)
        return _Response(body)

    return opener


def test_no_terms_in_the_facts_means_none_required_and_nothing_is_added():
    assert terms.required(fixture._facts()) is None
    assert terms.submission_fields(fixture._facts()) == {}


def test_the_facts_name_one_version_sha_and_the_door_path_of_its_text():
    assert terms.required(_facts()) == terms.Terms(VERSION, SHA, terms.PATH_PREFIX + VERSION)


@pytest.mark.parametrize(
    "value",
    [
        "carbon-submission-terms-v0",
        {**FACT, "url": "https://example.invalid"},
        {"version": VERSION, "sha256": SHA},
        {**FACT, "sha256": SHA.upper()},
        {**FACT, "sha256": "sha256:" + SHA},
        {**FACT, "version": "terms-v0", "path": terms.PATH_PREFIX + "terms-v0"},
        {**FACT, "path": "/elsewhere/" + VERSION},
    ],
)
def test_malformed_terms_facts_refuse_rather_than_guess(value):
    with pytest.raises(terms.TermsRefused) as refused:
        terms.required({**fixture._facts(), "terms": value})
    assert refused.value.code == terms.FACTS_INVALID


def test_the_text_is_read_from_the_door_path_and_only_with_the_named_sha():
    seen = []
    text = terms.fetch_text(fixture._URL, terms.required(_facts()), opener=_opener(seen=seen))
    assert text == TEXT
    assert seen == [fixture._URL + terms.PATH_PREFIX + VERSION]
    for body, code in (
        (TEXT + b" ", terms.TEXT_DIGEST_MISMATCH),
        (b"x" * (terms.MAX_TEXT_BYTES + 1), terms.TEXT_OVERSIZED),
    ):
        with pytest.raises(terms.TermsRefused) as refused:
            terms.fetch_text(fixture._URL, terms.required(_facts()), opener=_opener(body))
        assert refused.value.code == code


def test_an_unreachable_text_is_a_typed_refusal():
    def opener(request, timeout):
        raise urllib.error.URLError("down")

    with pytest.raises(terms.TermsRefused) as refused:
        terms.fetch_text(fixture._URL, terms.required(_facts()), opener=opener)
    assert refused.value.code == terms.TEXT_UNAVAILABLE


def test_only_the_text_shown_can_be_accepted_and_the_record_binds_version_and_sha(tmp_path):
    required = terms.required(_facts())
    with pytest.raises(terms.TermsRefused) as refused:
        terms.accept(required, TEXT + b"edited", home=tmp_path)
    assert refused.value.code == terms.TEXT_DIGEST_MISMATCH
    assert not terms.accepted(required, home=tmp_path)
    path = terms.accept(required, TEXT, home=tmp_path, clock=lambda: 0.0)
    assert path == tmp_path / f"{VERSION}.{SHA}.json"
    assert json.loads(path.read_bytes()) == {
        "schema": terms.SCHEMA,
        "version": VERSION,
        "sha256": SHA,
        "accepted_utc": "1970-01-01T00:00:00Z",
    }
    assert terms.accepted(required, home=tmp_path)
    assert terms.accept(required, TEXT, home=tmp_path, clock=lambda: 99.0) == path  # kept as it is
    other = terms.required(_facts(sha256="0" * 64))
    assert not terms.accepted(other, home=tmp_path)


def test_an_edited_or_foreign_record_is_not_an_acceptance(tmp_path):
    required = terms.required(_facts())
    path = terms.record_path(required, home=tmp_path)
    tmp_path.mkdir(exist_ok=True)
    path.write_text(json.dumps({"schema": terms.SCHEMA, "version": VERSION, "sha256": "0" * 64, "accepted_utc": "x"}))
    assert not terms.accepted(required, home=tmp_path)
    path.write_text("not json")
    assert not terms.accepted(required, home=tmp_path)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_a_symlinked_record_is_not_an_acceptance(tmp_path):
    required = terms.required(_facts())
    real = tmp_path / "real.json"
    terms.accept(required, TEXT, home=tmp_path / "a")
    real.write_bytes(terms.record_path(required, home=tmp_path / "a").read_bytes())
    link = terms.record_path(required, home=tmp_path / "b")
    link.parent.mkdir()
    os.symlink(real, link)
    assert not terms.accepted(required, home=tmp_path / "b")


def test_submission_fields_refuse_without_acceptance_and_carry_version_and_sha_after(tmp_path):
    with pytest.raises(terms.TermsRefused) as refused:
        terms.submission_fields(_facts(), home=tmp_path)
    assert refused.value.code == terms.NOT_ACCEPTED
    terms.accept(terms.required(_facts()), TEXT, home=tmp_path)
    assert terms.submission_fields(_facts(), home=tmp_path) == {"terms_version": VERSION, "terms_sha256": SHA}
    assert tuple(terms.submission_fields(_facts(), home=tmp_path)) == terms.SUBMIT_FIELDS


def _submit(tmp_path, monkeypatch, facts):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    signed, sent = [], []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            signed.append(json.loads(body))
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        request = json.loads(body)
        sent.append(request)
        if request["tool"] == client.SUBMIT_TOOL:
            return 202, fixture._answer("ADMITTED")
        return 200, fixture._answer("RECONSTRUCTED")

    run = lambda: client.submit_and_wait(  # noqa: E731
        fixture._URL,
        "external-signer",
        root=tmp_path / "campaign",
        epoch=1,
        recipe=fixture._recipe(),
        contract_digest=fixture._CONTRACT,
        receiver=fixture._RECEIVER,
        context=fixture._CONTEXT,
        read=lambda url: facts,
        send=send,
    )
    (tmp_path / "campaign").mkdir()
    return run, signed, sent


def test_a_door_that_requires_terms_is_refused_before_signing_until_the_miner_accepts(tmp_path, monkeypatch):
    run, signed, sent = _submit(tmp_path, monkeypatch, _facts())
    with pytest.raises(client.DirectIntakeRefusal) as refused:
        run()
    assert refused.value.code == terms.NOT_ACCEPTED
    assert signed == [] and sent == []
    terms.accept(terms.required(_facts()), TEXT)  # the default store, under the patched home
    assert run()["state"] == "RECONSTRUCTED"
    fields = sent[0]["fields"]
    assert sent[0]["tool"] == client.SUBMIT_TOOL
    assert (fields["terms_version"], fields["terms_sha256"]) == (VERSION, SHA)
    assert signed[0]["fields"] == fields  # inside the hotkey-signed body


def test_a_door_that_requires_no_terms_gets_exactly_todays_submission_fields(tmp_path, monkeypatch):
    run, signed, sent = _submit(tmp_path, monkeypatch, fixture._facts())
    assert run()["state"] == "RECONSTRUCTED"
    assert set(sent[0]["fields"]) == {"strategy_json", "contract_digest"}


def test_the_command_shows_the_text_and_records_only_an_explicit_accept(tmp_path):
    out = io.StringIO()
    read = lambda url: _facts()  # noqa: E731
    fetch = lambda url, required: TEXT  # noqa: E731
    assert terms.main(["--door", fixture._URL], read=read, fetch=fetch, ask=lambda _: "no", out=out, home=tmp_path) == 1
    assert TEXT.decode() in out.getvalue() and SHA in out.getvalue()
    assert not terms.accepted(terms.required(_facts()), home=tmp_path)
    args = ["--door", fixture._URL, "--accept", "0" * 64]
    assert terms.main(args, read=read, fetch=fetch, out=io.StringIO(), home=tmp_path) == 2
    assert not terms.accepted(terms.required(_facts()), home=tmp_path)
    assert terms.main(["--door", fixture._URL], read=read, fetch=fetch, ask=lambda _: "ACCEPT", out=io.StringIO(), home=tmp_path) == 0
    assert terms.accepted(terms.required(_facts()), home=tmp_path)


def test_every_terms_refusal_has_its_next_step_for_the_miner():
    literal = (
        "terms_not_accepted",
        "terms_facts_invalid",
        "terms_text_unavailable",
        "terms_text_oversized",
        "terms_text_digest_mismatch",
    )
    assert literal == terms.CODES
    for code in literal:
        assert supervisor.NEXT_ACTIONS[code]
        assert "nothing was" in supervisor.NEXT_ACTIONS[code].lower()  # says nothing was charged
    assert "submission_terms --door" in supervisor.NEXT_ACTIONS["terms_not_accepted"]


# --- the Launchpad card (scripts/dev/miner_launchpad/terms_card.py) ---

from scripts.dev.miner_launchpad import terms_card  # noqa: E402
from scripts.dev.miner_launchpad.controller import Rejected  # noqa: E402

URLS = {"electric-motor-magnetics": fixture._URL, "f08-ribbed-bracket": "http://127.0.0.1:9081"}


def _read(url):
    return _facts() if url == fixture._URL else fixture._facts()


def _fetch(url, required):
    return TEXT


def test_the_card_shows_the_full_text_only_where_a_validator_requires_terms(tmp_path):
    rows = terms_card.card(URLS, read=_read, fetch=_fetch, home=tmp_path)["challenges"]
    assert rows == [
        {
            "challenge_id": "electric-motor-magnetics",
            "required": True,
            "version": VERSION,
            "sha256": SHA,
            "text": TEXT.decode(),
            "accepted": False,
        },
        {"challenge_id": "f08-ribbed-bracket", "required": False},
    ]


def test_a_text_that_does_not_match_is_a_row_with_its_reason_not_a_shown_text(tmp_path):
    def fetch(url, required):
        raise terms.TermsRefused("terms_text_digest_mismatch")

    row = terms_card.card(URLS, read=_read, fetch=fetch, home=tmp_path)["challenges"][0]
    assert row["code"] == "terms_text_digest_mismatch" and "text" not in row
    assert row["words"] == supervisor.NEXT_ACTIONS["terms_text_digest_mismatch"]


def test_the_page_accept_records_exactly_the_text_shown(tmp_path):
    value = {"challenge_id": "electric-motor-magnetics", "sha256": SHA}
    row = terms_card.accept(URLS, value, read=_read, fetch=_fetch, home=tmp_path)
    assert row["accepted"] is True
    assert terms.accepted(terms.required(_facts()), home=tmp_path)


@pytest.mark.parametrize(
    "value, code",
    [
        ({"challenge_id": "electric-motor-magnetics"}, "closed_terms_accept_required"),
        ({"challenge_id": "electric-motor-magnetics", "sha256": SHA, "extra": 1}, "closed_terms_accept_required"),
        ({"challenge_id": "electric-motor-magnetics", "sha256": "sha256:" + SHA}, "closed_terms_accept_required"),
        ({"challenge_id": "chip-cold-plate", "sha256": SHA}, "terms_challenge_not_in_profile"),
        ({"challenge_id": "f08-ribbed-bracket", "sha256": SHA}, "terms_not_required"),
        ({"challenge_id": "electric-motor-magnetics", "sha256": "0" * 64}, "terms_changed_since_shown"),
    ],
)
def test_the_page_accept_refuses_anything_but_the_shown_version(tmp_path, value, code):
    with pytest.raises(Rejected) as refused:
        terms_card.accept(URLS, value, read=_read, fetch=_fetch, home=tmp_path)
    assert refused.value.code == code
    assert not terms.accepted(terms.required(_facts()), home=tmp_path)


def test_accepting_is_not_an_operation_an_agent_door_can_call():
    from scripts.dev.miner_launchpad import operations, setup_operations

    for table in (operations.OPERATIONS, setup_operations.SETUP_OPERATIONS):
        assert not any("terms" in str(name) for name in table)


def test_the_page_has_the_card_and_both_routes_go_to_the_terms_card():
    root = Path(terms_card.__file__).parent
    from scripts.dev.miner_launchpad import controller

    assert controller.TERMS_ROUTE == "/api/v1/page/terms"
    assert 'id="overview-terms"' in (root / "index.html").read_text(encoding="utf-8")
    script = (root / "app.js").read_text(encoding="utf-8")
    assert script.count('"/api/v1/page/terms"') == 2  # the read and the accept
    source = (root / "controller.py").read_text(encoding="utf-8")
    assert source.count("elif self.path == TERMS_ROUTE:") == 2
    assert "terms_card.accept_for_profile(" in source and "terms_card.for_profile(" in source
