"""The mining-identity helper: a separate process that alone handles the recovery phrase and password.

Ship gate (owner, 2026-10-21): a sentinel password and a sentinel phrase are searched for in every log line,
every response, the process's output and every file the flow writes; the phrase may appear only in the one
response that shows it, and the password nowhere.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
import stat
import threading
from pathlib import Path

import pytest

from carbon_miner_identity.backend import FakeBackend, IdentityRefused, SdkBackend
from carbon_miner_identity.core import Identity
from carbon_miner_identity.page import HELPER_JS, INDEX_HTML
from carbon_miner_identity.server import Server

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "SENTINEL-pw-7Hq2-never-anywhere"
WORDS = [
    "zephyr0",
    "quokka1",
    "marzipan2",
    "lattice3",
    "ostrich4",
    "plinth5",
    "vellum6",
    "tundra7",
    "walrus8",
    "xylem9",
    "yonder10",
    "zinnia11",
]
PHRASE = " ".join(WORDS)


class Running:
    def __init__(self, backend):
        self.identity = Identity(backend)
        self.server = Server(self.identity)
        self.port = self.server.server_address[1]
        self.token = self.server.token
        self.responses = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, body=None, token="default", host=None, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if token == "default":
            token = self.token
        if token:
            headers["X-Identity-Token"] = token
        if origin:
            headers["Origin"] = origin
        raw = json.dumps(body).encode() if body is not None else None
        if raw is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=raw, headers=headers)
        response = connection.getresponse()
        data = response.read()
        self.responses.append(
            (path, response.status, data, dict(response.getheaders()))
        )
        connection.close()
        return response.status, data, dict(response.getheaders())

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def helper():
    running = Running(FakeBackend(PHRASE))
    yield running
    running.stop()


def flow(running, password=PASSWORD, name="mine"):
    status, data, _ = running.call("POST", "/api/create", {"name": name})
    assert status == 200, data
    made = json.loads(data)
    answers = [made["words"][position - 1] for position in made["ask"]]
    assert running.call("POST", "/api/confirm", {"words": answers})[0] == 200
    status, data, _ = running.call(
        "POST", "/api/save", {"password": password, "again": password}
    )
    return status, json.loads(data)


# ---- the state machine --------------------------------------------------------------------------
def test_the_steps_run_in_order_and_end_with_public_addresses_only():
    identity = Identity(FakeBackend(PHRASE))
    with pytest.raises(IdentityRefused):
        identity.confirm(["a", "b", "c"])
    with pytest.raises(IdentityRefused):
        identity.save(PASSWORD, PASSWORD)
    made = identity.create("mine")
    assert (
        made["words"] == WORDS
        and len(made["ask"]) == 3
        and made["ask"] == sorted(made["ask"])
    )
    with pytest.raises(IdentityRefused):
        identity.save(PASSWORD, PASSWORD)  # not before the words are given back
    identity.confirm([WORDS[position - 1] for position in made["ask"]])
    saved = identity.save(PASSWORD, PASSWORD)
    assert set(saved) == {"wallet", "hotkey", "coldkey_address", "hotkey_address"}
    assert PASSWORD not in json.dumps(saved) and not any(
        word in json.dumps(saved) for word in WORDS
    )
    assert identity._phrase is None, "the phrase is dropped once saved"


def test_wrong_words_are_refused_and_too_many_start_over():
    identity = Identity(FakeBackend(PHRASE))
    identity.create("mine")
    for _ in range(4):
        with pytest.raises(IdentityRefused, match="do not match"):
            identity.confirm(["no", "no", "no"])
    with pytest.raises(IdentityRefused, match="Too many"):
        identity.confirm(["no", "no", "no"])
    assert identity.stage == "idle" and identity._phrase is None


@pytest.mark.parametrize("name", ["", "../x", "a b", "-lead", "x" * 33, None, 7])
def test_a_wallet_name_must_be_short_and_plain(name):
    with pytest.raises(IdentityRefused):
        Identity(FakeBackend(PHRASE)).create(name)


@pytest.mark.parametrize(
    "password, again",
    [
        ("short", "short"),
        (PASSWORD, PASSWORD + "x"),
        ("x" * 300, "x" * 300),
        (None, None),
    ],
)
def test_a_weak_or_mismatched_password_is_refused_and_nothing_is_saved(password, again):
    backend = FakeBackend(PHRASE)
    identity = Identity(backend)
    made = identity.create("mine")
    identity.confirm([WORDS[position - 1] for position in made["ask"]])
    with pytest.raises(IdentityRefused):
        identity.save(password, again)
    assert backend.saved == []


def test_an_existing_wallet_is_never_overwritten():
    backend = FakeBackend(PHRASE)
    backend.names.add("taken")
    with pytest.raises(IdentityRefused, match="already exists"):
        Identity(backend).create("taken")


# ---- the server -----------------------------------------------------------------------------------
def test_every_call_needs_the_one_time_token_the_right_host_and_origin(helper):
    assert helper.call("POST", "/api/create", {"name": "x"}, token=None)[0] == 401
    assert (
        helper.call("POST", "/api/create", {"name": "x"}, token="wrong" * 8)[0] == 401
    )
    assert (
        helper.call("POST", "/api/create", {"name": "x"}, host="evil.example:80")[0]
        == 403
    )
    assert helper.call("GET", "/", host="evil.example:80")[0] == 403
    assert (
        helper.call("POST", "/api/create", {"name": "x"}, origin="http://evil.example")[
            0
        ]
        == 403
    )
    assert helper.identity.stage == "idle"


def test_the_page_is_self_contained_with_no_storage_no_copy_and_strict_headers(helper):
    status, data, headers = helper.call("GET", "/", token=None)
    assert status == 200
    assert (
        "default-src 'none'" in headers["Content-Security-Policy"]
        and "script-src 'self'" in headers["Content-Security-Policy"]
    )
    assert (
        headers["Cache-Control"] == "no-store"
        and headers["Referrer-Policy"] == "no-referrer"
    )
    html = data.decode()
    assert not re.search(
        r"https?://", html + HELPER_JS
    ), "nothing is loaded from, or sent to, anywhere else"
    for banned in (
        "localStorage",
        "sessionStorage",
        "clipboard",
        "document.cookie",
        "indexedDB",
    ):
        assert banned not in HELPER_JS + INDEX_HTML
    assert "copy" not in INDEX_HTML.lower().replace(
        "copy it into the control center", ""
    )  # no copy button for the phrase
    assert (
        "location.search" not in HELPER_JS and "?token" not in HELPER_JS
    ), "the token is never in a query string"
    assert (
        "history.replaceState" in HELPER_JS
    ), "the fragment is removed from the address bar"


def test_the_link_carries_the_token_in_the_fragment_only(helper):
    assert (
        helper.server.link.endswith("/#t=" + helper.token)
        and "?" not in helper.server.link
    )


def test_oversized_and_malformed_bodies_are_refused(helper):
    connection = http.client.HTTPConnection("127.0.0.1", helper.port, timeout=10)
    connection.request(
        "POST",
        "/api/create",
        body=b"x" * 9000,
        headers={
            "Host": f"127.0.0.1:{helper.port}",
            "X-Identity-Token": helper.token,
            "Content-Length": "9000",
        },
    )
    assert connection.getresponse().status == 400
    assert helper.call("POST", "/api/create", [1, 2])[0] in (400, 422)


def test_the_helper_listens_on_loopback_only(helper):
    assert helper.server.server_address[0] == "127.0.0.1"


# ---- the ship gate ----------------------------------------------------------------------------------
def test_sentinels_appear_nowhere_but_the_one_response_that_shows_the_phrase(
    tmp_path, capfd, caplog
):
    caplog.set_level(logging.DEBUG)
    running = Running(FakeBackend(PHRASE))
    try:
        status, saved = flow(running)
        assert status == 200, saved
        assert running.call("POST", "/api/done", {})[0] == 200
    finally:
        running.stop()
    output = capfd.readouterr()
    everything_but_create = [
        (path, data)
        for path, _status, data, _headers in running.responses
        if path != "/api/create"
    ]
    create = [
        data
        for path, _status, data, _headers in running.responses
        if path == "/api/create"
    ]
    assert len(create) == 1 and all(
        word.encode() in create[0] for word in WORDS
    ), "the phrase is shown, once"
    haystacks = {
        "stdout": output.out,
        "stderr": output.err,
        "log": caplog.text,
        "files": "".join(
            p.read_text(errors="ignore") for p in tmp_path.rglob("*") if p.is_file()
        ),
        **{
            f"response {path}": data.decode("utf-8", "ignore")
            for path, data in everything_but_create
        },
    }
    for place, text in haystacks.items():
        assert PASSWORD not in text, "the password is in " + place
        assert not any(word in text for word in WORDS), "a phrase word is in " + place
    # The password reaches the key tool and nothing else.
    assert running.identity.backend.saved == [("mine", "default", len(PASSWORD))]
    for _path, _status, data, headers in running.responses:
        assert PASSWORD.encode() not in data and PASSWORD not in json.dumps(headers)


def test_a_failing_key_tool_says_nothing_it_was_told(monkeypatch):
    class Leaky(FakeBackend):
        def save(self, name, hotkey, coldkey_phrase, password):
            raise RuntimeError(
                "could not write with " + password + " and " + coldkey_phrase
            )

    running = Running(Leaky(PHRASE))
    try:
        status, data, _ = running.call("POST", "/api/create", {"name": "mine"})
        made = json.loads(data)
        running.call(
            "POST",
            "/api/confirm",
            {"words": [made["words"][p - 1] for p in made["ask"]]},
        )
        status, data, _ = running.call(
            "POST", "/api/save", {"password": PASSWORD, "again": PASSWORD}
        )
        assert status == 500
        assert PASSWORD.encode() not in data and not any(
            word.encode() in data for word in WORDS
        )
        assert running.identity.stage == "idle" and running.identity._phrase is None
    finally:
        running.stop()


# ---- the real SDK ------------------------------------------------------------------------------------
def test_the_sdk_writes_encrypted_owner_only_keys_and_prints_no_phrase(tmp_path, capfd):
    pytest.importorskip("bittensor")
    backend = SdkBackend(wallet_path=str(tmp_path))
    identity = Identity(backend)
    made = identity.create("realwallet")
    words = made["words"]
    identity.confirm([words[position - 1] for position in made["ask"]])
    saved = identity.save(PASSWORD, PASSWORD)
    assert saved["coldkey_address"].startswith("5") and saved[
        "hotkey_address"
    ].startswith("5")
    files = [p for p in (tmp_path / "realwallet").rglob("*") if p.is_file()]
    assert any(p.name == "coldkey" for p in files) and any(
        p.parent.name == "hotkeys" for p in files
    )
    for path in files:
        text = path.read_bytes().decode("latin-1")
        assert PASSWORD not in text
        assert not any(word in text for word in words if len(word) > 3), (
            "no phrase in the clear in " + path.name
        )
        if os.name == "posix" and path.name in ("coldkey", "default"):
            assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, (
                path.name + " is readable by others"
            )
    # What the miner's own signer does: unlock the hotkey with the password, and it is the address shown.
    from bittensor.keyfiles import Keyfile

    hotkey_file = Keyfile(str(tmp_path / "realwallet" / "hotkeys" / "default"))
    assert (
        hotkey_file.is_encrypted()
        and Keyfile(str(tmp_path / "realwallet" / "coldkey")).is_encrypted()
    )
    assert (
        hotkey_file.get_keypair(password=PASSWORD).ss58_address
        == saved["hotkey_address"]
    )
    captured = capfd.readouterr()
    assert not any(
        word in captured.out + captured.err for word in words
    ), "the SDK printed the phrase"
    assert PASSWORD not in captured.out + captured.err
    with pytest.raises(IdentityRefused, match="already exists"):
        Identity(backend).create("realwallet")


# ---- the boundary ------------------------------------------------------------------------------------
def test_nothing_in_carbons_product_process_mentions_the_helper_and_the_helper_imports_no_carbon():
    for entry in (
        ROOT / "scripts" / "dev" / "miner_launchpad",
        ROOT / "carbon" / "miner_mcp",
    ):
        for path in entry.rglob("*.py"):
            assert "carbon_miner_identity" not in path.read_text(
                encoding="utf-8", errors="ignore"
            ), str(path)
    for path in (ROOT / "carbon_miner_identity").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"^\s*(from|import)\s+carbon(\.|\s|$)", text, re.MULTILINE
        ), (path.name + " imports carbon")
