"""The go-live path: `python -m carbon.dashboard live` and carbon/dashboard/go_live.sh.

The launch Challenges' signed boards are fetched from each validator door; a door that
answers 404 has nothing published yet and its Challenge shows "Launching soon" (the Worker
skips the URL, `live` reports NOT_PUBLISHED). Any other failed fetch, a refused board, or a
build with no accepted board exits 1, so a chained deploy stops. No network: urlopen is
replaced, and the Worker runs in Node over a stubbed fetch.
"""

from __future__ import annotations

import datetime
import io
import json
import os
import shutil
import subprocess
import urllib.error
from pathlib import Path

import pytest

from carbon.challenge_validator import launch_board as lb
from carbon.dashboard import __main__ as cli
from tests.cpu import test_dashboard_worker as base

REPOSITORY = Path(__file__).resolve().parents[2]
NAMES_FILE = REPOSITORY / "carbon" / "dashboard" / "names.launch.json"
KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
DOOR = "https://door.example/carbon/v1/feed/"
CHALLENGES = [
    "electric-motor-magnetics",
    "chip-cold-plate",
    "f08-ribbed-bracket",
    "f02",
]
URLS = [DOOR + c for c in CHALLENGES]


def _ladder(status, total):
    return {
        "schema": "carbon.private-exam.ladder-feedback.v2",
        "exam_version": "x",
        "status": status,
        "total": total,
        "gate_names": [],
    }


def _board(signer, challenge, version=1):
    king = {
        "schema": "carbon.koth.public.v1",
        "challenge_id": challenge,
        "challenge_version": "1.0",
        "exam_version_label": "exam-1",
        "king": {"hotkey": KING, "total": 0.64, "since_epoch": 7},
        "margin": 0.02,
        "to_beat": 0.66,
        "baseline_total": None,
    }
    rows = [
        (KING, _ladder("IMPROVED", 0.64), _ladder("IMPROVED", 0.64)),
        (OTHER, _ladder("IMPROVED", 0.5), _ladder("NO_IMPROVEMENT", 0.5)),
    ]
    return lb.build(
        king_document=king,
        rows=rows,
        network="testnet",
        key=signer,
        version=version,
        now=NOW,
    )


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _door(monkeypatch, answers):
    """urlopen answering each URL with a document, an HTTP status, or an exception."""

    def fake(request, timeout):
        answer = answers[request.full_url]
        if isinstance(answer, int):
            raise urllib.error.HTTPError(
                request.full_url, answer, "x", {}, io.BytesIO()
            )
        if isinstance(answer, Exception):
            raise answer
        return _Answer(json.dumps(answer).encode())

    monkeypatch.setattr(cli.urllib.request, "urlopen", fake)


def _live(tmp_path, key, *extra):
    out = tmp_path / "site"
    code = cli.main(
        ["live", "--trust-key", key, "--names", str(NAMES_FILE), "--out", str(out)]
        + [a for url in URLS for a in ("--url", url)]
        + list(extra)
    )
    return code, out


def _index(out):
    return json.loads((out / "data" / "index.json").read_text(encoding="utf-8"))


def test_the_launch_names_are_plain_labels_for_the_four_challenges():
    names = json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    assert names == {
        "electric-motor-magnetics": "Motor",
        "chip-cold-plate": "Cooling",
        "f08-ribbed-bracket": "Ribbed Bracket",
        "f02": "Burst Thermal",
    }


def test_two_published_boards_build_and_the_rest_wait(tmp_path, monkeypatch, capsys):
    signer = lb.LaunchBoardKey(os.urandom(32))
    _door(
        monkeypatch,
        {
            URLS[0]: _board(signer, CHALLENGES[0]),
            URLS[1]: 404,
            URLS[2]: 404,
            URLS[3]: _board(signer, CHALLENGES[3]),
        },
    )
    code, out = _live(tmp_path, signer.public_key)
    said = capsys.readouterr().out
    assert code == 0
    assert "NOT_PUBLISHED " + URLS[1] in said
    assert "2 accepted, 0 refused, 0 not fetched, 2 not published yet" in said
    index = _index(out)
    assert index["fixture"] is False and index["showcase"] is False
    assert [b["state"] for b in index["boards"]] == ["ACCEPTED", "ACCEPTED"]
    assert [b["challenge"]["id"] for b in index["boards"]] == [
        "electric-motor-magnetics",
        "f02",
    ]
    assert not (out / "showcase").exists()
    names = json.loads((out / "data" / "names.json").read_text(encoding="utf-8"))[
        "names"
    ]
    assert names["chip-cold-plate"] == "Cooling"


@pytest.mark.parametrize(
    "unavailable",
    [503, urllib.error.URLError("name not resolved"), TimeoutError("timed out")],
)
def test_a_failed_fetch_stops_the_deploy(tmp_path, monkeypatch, capsys, unavailable):
    signer = lb.LaunchBoardKey(os.urandom(32))
    _door(
        monkeypatch,
        {
            URLS[0]: _board(signer, CHALLENGES[0]),
            URLS[1]: unavailable,
            URLS[2]: 404,
            URLS[3]: 404,
        },
    )
    code, _ = _live(tmp_path, signer.public_key)
    captured = capsys.readouterr()
    assert code == 1
    assert "FETCH_FAILED " + URLS[1] in captured.out
    assert "Not safe to deploy" in captured.err


def test_a_board_the_pinned_key_does_not_verify_stops_the_deploy(
    tmp_path, monkeypatch, capsys
):
    signer = lb.LaunchBoardKey(os.urandom(32))
    stranger = lb.LaunchBoardKey(os.urandom(32))
    _door(
        monkeypatch,
        {
            URLS[0]: _board(stranger, CHALLENGES[0]),
            URLS[1]: 404,
            URLS[2]: 404,
            URLS[3]: _board(signer, CHALLENGES[3]),
        },
    )
    code, _ = _live(tmp_path, signer.public_key)
    said = capsys.readouterr().out
    assert code == 1
    assert "REFUSED" in said and "signature_invalid" in said


def test_nothing_published_keeps_the_launching_soon_site(tmp_path, monkeypatch, capsys):
    signer = lb.LaunchBoardKey(os.urandom(32))
    _door(monkeypatch, {url: 404 for url in URLS})
    code, out = _live(tmp_path, signer.public_key)
    captured = capsys.readouterr()
    assert code == 1
    assert "0 accepted, 0 refused, 0 not fetched, 4 not published yet" in captured.out
    assert "Launching soon" in captured.err
    assert _index(out)["boards"] == []


def test_the_command_refuses_unsafe_arguments(tmp_path, monkeypatch):
    signer = lb.LaunchBoardKey(os.urandom(32))
    _door(monkeypatch, {url: 404 for url in URLS})
    key = signer.public_key
    bad = [
        ["--url", "http://door.example/f", "--trust-key", key],
        ["--url", URLS[0], "--trust-key", "abc"],
        ["--url", URLS[0]],
        ["--trust-key", key],
    ]
    for arguments in bad:
        with pytest.raises(SystemExit) as stop:
            cli.main(["live", "--out", str(tmp_path / "x"), *arguments])
        assert stop.value.code == 2
    full = tmp_path / "full"
    full.mkdir()
    (full / "old").write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as stop:
        cli.main(["live", "--out", str(full), "--url", URLS[0], "--trust-key", key])
    assert stop.value.code == 2


def test_settings_come_from_one_line_files(tmp_path, monkeypatch, capsys):
    signer = lb.LaunchBoardKey(os.urandom(32))
    urls = tmp_path / "dashboard-feed-urls"
    urls.write_text(",".join(URLS) + "\n", encoding="utf-8")
    keys = tmp_path / "dashboard-feed-keys"
    keys.write_text(signer.public_key + "\n", encoding="utf-8")
    _door(
        monkeypatch,
        {
            URLS[0]: _board(signer, CHALLENGES[0]),
            URLS[1]: 404,
            URLS[2]: 404,
            URLS[3]: 404,
        },
    )
    out = tmp_path / "site"
    code = cli.main(
        [
            "live",
            "--urls-file",
            str(urls),
            "--keys-file",
            str(keys),
            "--names",
            str(NAMES_FILE),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    assert (
        "1 accepted, 0 refused, 0 not fetched, 3 not published yet"
        in capsys.readouterr().out
    )


def test_the_worker_shows_unpublished_challenges_as_launching_soon(
    tmp_path, monkeypatch
):
    """All four launch URLs are set from day one. A 404 adds no board (the page's named
    "Launching soon" card takes its place); a failure other than 404 is a visible refusal.
    """
    pytest.importorskip("cryptography")
    if shutil.which("node") is None:
        pytest.skip("node is not installed here")
    signer = lb.LaunchBoardKey(os.urandom(32))
    key = signer.public_key
    published = {
        URLS[0]: _board(signer, CHALLENGES[0]),
        URLS[3]: _board(signer, CHALLENGES[3]),
    }
    _door(monkeypatch, {**published, URLS[1]: 404, URLS[2]: 404})
    code, out = _live(tmp_path, key)
    assert code == 0
    env = {"FEED_URLS": ",".join(URLS), "FEED_KEYS": key, "CACHE_SECONDS": "0"}
    feeds = {url: json.dumps(doc) for url, doc in published.items()}

    def serve(missing, feeds=feeds):
        spec = {
            "mode": "worker",
            "site": str(out),
            "env": env,
            "feeds": feeds,
            "missing": missing,
            "requests": ["/data/index.json", "/data/names.json"],
        }
        return base._node(spec, tmp_path)

    index, names = serve([URLS[1], URLS[2]])
    boards = json.loads(index["body"])["boards"]
    assert [(b["challenge"]["id"], b["state"]) for b in boards] == [
        ("electric-motor-magnetics", "ACCEPTED"),
        ("f02", "ACCEPTED"),
    ]
    assert json.loads(names["body"])["names"]["chip-cold-plate"] == "Cooling"
    # one of those doors is down (502, not 404): shown as refused, never hidden
    index, _ = serve([URLS[2]])
    boards = json.loads(index["body"])["boards"]
    assert sorted(b["state"] for b in boards) == ["ACCEPTED", "ACCEPTED", "REFUSED"]
    assert [b["code"] for b in boards if b["state"] == "REFUSED"] == [
        "feed_unavailable"
    ]


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python") is None,
    reason="bash and python are needed to run the script",
)
def test_go_live_dry_run_builds_and_changes_nothing(tmp_path):
    """The whole script up to its wrangler dry run: fetch, build, and a stubbed wrangler.
    A stand-in `urlopen` (sitecustomize on PYTHONPATH) serves the signed boards."""
    signer = lb.LaunchBoardKey(os.urandom(32))
    config = tmp_path / "config"
    config.mkdir()
    (config / "dashboard-feed-urls").write_text(",".join(URLS) + "\n", encoding="utf-8")
    (config / "dashboard-feed-keys").write_text(
        signer.public_key + "\n", encoding="utf-8"
    )
    served = {
        URLS[0]: _board(signer, CHALLENGES[0]),
        URLS[1]: None,
        URLS[2]: None,
        URLS[3]: _board(signer, CHALLENGES[3]),
    }
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "doors.json").write_text(json.dumps(served), encoding="utf-8")
    (stub / "sitecustomize.py").write_text(
        "import io, json, pathlib, urllib.error, urllib.request\n"
        "doors = json.loads((pathlib.Path(__file__).with_name('doors.json')).read_text())\n"
        "class A(io.BytesIO):\n"
        "    def __enter__(self): return self\n"
        "    def __exit__(self, *e): return False\n"
        "def urlopen(request, timeout=0):\n"
        "    body = doors[request.full_url]\n"
        "    if body is None:\n"
        "        raise urllib.error.HTTPError(request.full_url, 404, 'x', {}, io.BytesIO())\n"
        "    return A(json.dumps(body).encode())\n"
        "urllib.request.urlopen = urlopen\n",
        encoding="utf-8",
    )
    wrangler = tmp_path / "fake-wrangler.sh"
    calls = tmp_path / "calls.txt"
    wrangler.write_text(
        f'#!/usr/bin/env bash\necho "$@" >> "{calls.as_posix()}"\n',
        encoding="utf-8",
        newline="\n",
    )
    site = tmp_path / "site"
    env = {
        **os.environ,
        "CARBON_CONFIG_DIR": config.as_posix(),
        "CARBON_DASHBOARD_SITE": site.as_posix(),
        "WRANGLER": f"bash {wrangler.as_posix()}",
        "PYTHONPATH": os.pathsep.join([str(stub), str(REPOSITORY)]),
    }
    run = subprocess.run(
        ["bash", str(REPOSITORY / "carbon" / "dashboard" / "go_live.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=tmp_path,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "2 accepted, 0 refused, 0 not fetched, 2 not published yet" in run.stdout
    assert "Dry run only" in run.stdout
    (line,) = calls.read_text(encoding="utf-8").splitlines()
    assert line.startswith(
        "deploy --dry-run --config carbon/dashboard/wrangler.dashboard.toml --assets"
    )
    assert (site / "data" / "names.json").is_file()
    assert not (config / "dashboard-secrets.json").exists()
    # a refused board stops the script before wrangler is called at all
    calls.unlink()
    (config / "dashboard-feed-keys").write_text(
        lb.LaunchBoardKey(os.urandom(32)).public_key + "\n", encoding="utf-8"
    )
    env["CARBON_DASHBOARD_SITE"] = (tmp_path / "site2").as_posix()
    run = subprocess.run(
        ["bash", str(REPOSITORY / "carbon" / "dashboard" / "go_live.sh"), "--deploy"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=tmp_path,
    )
    assert run.returncode == 1 and not calls.exists()
