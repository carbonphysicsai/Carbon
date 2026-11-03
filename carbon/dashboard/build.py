"""Write the static dashboard: the web app plus one board file per feed.

`build(out, documents, trust)` checks each feed document with `feed.project`
and writes:

- `data/index.json`: one entry per board (Challenge, device class, labels,
  feed state);
- `data/boards/<slug>.json`: the verified board model (board.v1);
- `data/v2/<slug>.json`: the same board as `carbon.dashboard.board.v2`
  (`board_v2.project`), whose phase is computed at `now`. The pages draw
  this file only (DASHBOARD-02 S2);
- `updates.json`: the Updates page's text (`write_updates`), from
  carbon/dashboard/updates.json.

A refused document never overwrites an accepted board. When an accepted board
for the same Challenge and device class is already in `out`, it stays, marked
`REFUSED` with the reason code, so the page shows the last good version and
why the newer one was not drawn. A refusal is never replaced by fixture data.

The brand fonts and wordmark are copied from the Launchpad's copies of the
verified website asset set, and their digests are checked against the website's
production baseline manifest values pinned here. The Carbon favicons (dark
mark for light browser chrome, light mark for dark) are the owner's brand files
from the Carbon Google Drive "Favicons" folder, kept in `brand/` beside this
module and pinned here the same way. Nothing loads from the internet at runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from carbon.dashboard import board_v2, feed

INDEX_SCHEMA = "carbon.dashboard.index.v1"
WEB = Path(__file__).with_name("web")
REPOSITORY = Path(__file__).resolve().parents[2]
# Path in the repository -> (published path, sha256 from
# website/ask-carbon/production-baseline.manifest.json).
BRAND_ASSETS = {
    "scripts/dev/miner_launchpad/fonts/neue-0.otf": (
        "fonts/neue-0.otf",
        "69bcecee993d4564980d8e082d4f15a461fd1f7e8ebbc36e8533d9e95f0131f8",
    ),
    "scripts/dev/miner_launchpad/fonts/neue-1.otf": (
        "fonts/neue-1.otf",
        "437ad49efdf9812ec50df7440fab56f66f1c8311ce9f276c1473919b63a1050d",
    ),
    "scripts/dev/miner_launchpad/brand/brand-2.svg": (
        "brand/brand-2.svg",
        "98cd406e21141304bee9085918dd7d6d41383a70d2c929964d64717c2655f276",
    ),
}
BRAND = Path(__file__).with_name("brand")
# File in brand/ -> sha256 of the owner's Drive original. Published as brand/<name>.
FAVICONS = {
    "favicon-dark.svg": "39f7e21a32ee0d4fceaf218b97caaeaa1663ae5c55283701ca1880c4319e657a",
    "favicon-light.svg": "fc3ca1fd565e0b1a4e119008dc522a2cc397be501a3583f36e5af463e3985892",
    "favicon-dark-32.png": "c6f5d352ce67ee8b15409522ed995f6545d398f25d8c6e44e235baa3362b07b8",
    "favicon-light-32.png": "e80d5d98f380164219fe8caa54b9f03d209b1f32566673b1f11cb5e96f588bd6",
}


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy_web(out):
    for source in sorted(WEB.rglob("*")):
        if source.is_file():
            target = out / source.relative_to(WEB)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    copied = []
    for relative, (published, expected) in BRAND_ASSETS.items():
        source = REPOSITORY / relative
        if not source.is_file():
            continue
        body = source.read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError(f"brand asset digest mismatch: {relative}")
        target = out / published
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        copied.append(published)
    for name, expected in FAVICONS.items():
        body = (BRAND / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError(f"favicon digest mismatch: {name}")
        target = out / "brand" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        copied.append(f"brand/{name}")
    return copied


def _previous(out, slug):
    path = out / "data" / "boards" / f"{slug}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _previous_v2(out, slug):
    path = out / "data" / "v2" / f"{slug}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _slug_of(document):
    """Where a refused document would have gone, when that much is readable."""
    try:
        device = document.get("device_class") or (
            document["submissions"][0]["device_class"]
            if document.get("submissions")
            else "no-class"
        )
        return feed.board_slug(document["challenge"]["id"], device)
    except (AttributeError, IndexError, KeyError, TypeError):
        return None


def build(out, documents, trust, *, showcase=False, now=None):
    """Build the site into `out`; return the index written. With `showcase`,
    also write the design showcase replays (public EV4 material only). `now`
    (whole seconds since the epoch, default the clock) sets the v2 phase."""
    now = int(time.time()) if now is None else now
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    brand = _copy_web(out)
    write_updates(out)
    entries = {}
    leaders = []
    for document in documents:
        try:
            board = feed.project(document, trust)
        except feed.FeedRefused as refusal:
            slug = _slug_of(document)
            previous = _previous(out, slug) if slug else None
            if previous is None:
                key = slug or f"unreadable-{len(entries)}"
                entries[key] = {"slug": None, "state": "REFUSED", "code": refusal.code}
                continue
            previous["feed_state"] = {"state": "REFUSED", "code": refusal.code}
            _write_json(out / "data" / "boards" / f"{slug}.json", previous)
            entries[slug] = _entry(previous)
            kept = _previous_v2(out, slug)
            if kept is not None:
                kept = board_v2.restamp(kept, now)
                kept["feed_state"] = previous["feed_state"]
                _write_json(out / "data" / "v2" / f"{slug}.json", kept)
            continue
        board["feed_state"] = {"state": "ACCEPTED", "code": None}
        if board["showcase_panel"] is not None:
            leaders.append((board, board["showcase_panel"]))
        # The panel's predictions go to the showcase replays, not the board.
        board = {**board, "showcase_panel": _panel_summary(board["showcase_panel"])}
        if board["slug"] in entries and entries[board["slug"]]["state"] == "ACCEPTED":
            raise ValueError(f"two feeds for one board: {board['slug']}")
        _write_json(out / "data" / "boards" / f"{board['slug']}.json", board)
        v2 = board_v2.project(board, now)
        v2["feed_state"] = board["feed_state"]
        _write_json(out / "data" / "v2" / f"{board['slug']}.json", v2)
        entries[board["slug"]] = _entry(board)
    if showcase:
        from carbon.dashboard import showcase as replays

        replays.build_all(out / "showcase", leaders)
    index = {
        "schema": INDEX_SCHEMA,
        "fixture": trust.fixture,
        "brand_assets": brand,
        # S3's signed network snapshot: the page fetches it only when present.
        "network": (out / "data" / "network.json").is_file(),
        # The page offers the design showcase only when this build carries one.
        "showcase": (out / "showcase" / "index.json").is_file(),
        "boards": [entries[k] for k in sorted(entries)],
    }
    _write_json(out / "data" / "index.json", index)
    return index


#: The Worker's security headers (worker/index.mjs SECURITY_HEADERS) for a static-only deploy.
STATIC_HEADERS = """/*
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=()
/data/*
  Cache-Control: no-cache
"""


def write_static_headers(out):
    (Path(out) / "_headers").write_text(STATIC_HEADERS, encoding="utf-8", newline="\n")


NAMES_SCHEMA = "carbon.dashboard.names.v1"
#: A plain label: no markup, at most 40 characters (the page and the Worker check the same).
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._&'+-]{0,39}$")
#: An entry may be {"name", "status", "door"}: a status line and an https door link for the
#: Challenge's card while it has no board (the page and the Worker check the same patterns).
STATUS_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._&'+:,-]{0,59}$")
ABOUT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._&'+:,()/-]{0,89}$")
DOOR_PATTERN = re.compile(r"^https://[A-Za-z0-9.-]+(:\d{1,5})?(/[A-Za-z0-9._~/-]*)?$")


def write_names(out, names):
    """Write `data/names.json`: display names keyed by Challenge id. The page shows a
    name in place of the id and falls back to the id in title case. Public labels
    only; a name that is not a plain label refuses the build."""
    if not isinstance(names, dict) or not names:
        raise ValueError("names must be a non-empty object of id to name")
    for challenge_id, value in names.items():
        if not isinstance(challenge_id, str) or not challenge_id:
            raise ValueError("a name needs a Challenge id")
        name = value.get("name") if isinstance(value, dict) else value
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            raise ValueError(f"not a plain display name for {challenge_id}")
        if isinstance(value, dict):
            if set(value) - {"name", "status", "door", "about", "order"}:
                raise ValueError(f"unknown field in the entry for {challenge_id}")
            status, door = value.get("status"), value.get("door")
            if status is not None and not (
                isinstance(status, str) and STATUS_PATTERN.fullmatch(status)
            ):
                raise ValueError(f"not a plain status for {challenge_id}")
            about, order = value.get("about"), value.get("order")
            if about is not None and not (
                isinstance(about, str) and ABOUT_PATTERN.fullmatch(about)
            ):
                raise ValueError(f"not a plain description for {challenge_id}")
            if order is not None and not (type(order) is int and 1 <= order <= 99):
                raise ValueError(f"not a place from 1 to 99 for {challenge_id}")
            if door is not None and not (
                isinstance(door, str) and DOOR_PATTERN.fullmatch(door)
            ):
                raise ValueError(f"not an https door address for {challenge_id}")
    _write_json(
        Path(out) / "data" / "names.json",
        {"schema": NAMES_SCHEMA, "names": dict(sorted(names.items()))},
    )


UPDATES = Path(__file__).with_name("updates.json")
UPDATES_SCHEMA = "carbon.dashboard.updates.v1"
UPDATES_FIELDS = {
    "schema",
    "intro",
    "next_label",
    "challenges",
    "every_version",
    "fixes",
    "known_issues",
    "faq",
}
#: One line of the Updates page: plain text, no markup, at most 400 characters.
UPDATE_LINE = re.compile(r"^[^<>\x00-\x1f]{1,400}$")
VERSION_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){1,2}$")
CHALLENGE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _lines(value, where, *, empty=True):
    if not isinstance(value, list) or not (value or empty):
        raise ValueError(f"updates: {where} is not a list of lines")
    if not all(isinstance(v, str) and UPDATE_LINE.fullmatch(v) for v in value):
        raise ValueError(f"updates: a line in {where} is not plain text")


def write_updates(out, updates=None):
    """Write `updates.json`, the Updates page's text, from carbon/dashboard/updates.json
    (the one file to edit). Plain lines only, or the build is refused. The page reads
    each Challenge's live version from the index, never from this file."""
    doc = updates
    if doc is None:
        doc = json.loads(UPDATES.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or set(doc) != UPDATES_FIELDS:
        raise ValueError("updates: not the Updates page's fields")
    if doc["schema"] != UPDATES_SCHEMA:
        raise ValueError("updates: unknown schema")
    _lines([doc["intro"]], "intro")
    _lines([doc["next_label"]], "next_label")
    for name in ("every_version", "fixes", "known_issues"):
        _lines(doc[name], name)
    if not isinstance(doc["challenges"], list) or not doc["challenges"]:
        raise ValueError("updates: no Challenge")
    for challenge in doc["challenges"]:
        if (
            not isinstance(challenge, dict)
            or set(challenge) != {"id", "next"}
            or not isinstance(challenge["id"], str)
            or not CHALLENGE_ID.fullmatch(challenge["id"])
            or not isinstance(challenge["next"], list)
        ):
            raise ValueError("updates: a Challenge needs exactly an id and a list next")
        for step in challenge["next"]:
            if (
                not isinstance(step, dict)
                or set(step) != {"version", "changes"}
                or not isinstance(step["version"], str)
                or not VERSION_PATTERN.fullmatch(step["version"])
            ):
                raise ValueError(f"updates: not a next version for {challenge['id']}")
            _lines(step["changes"], challenge["id"], empty=False)
    if not isinstance(doc["faq"], list) or not all(
        isinstance(item, dict) and set(item) == {"q", "a"} for item in doc["faq"]
    ):
        raise ValueError("updates: a question needs exactly q and a")
    for item in doc["faq"]:
        _lines([item["q"]], "faq")
        _lines(item["a"], "faq", empty=False)
    _write_json(Path(out) / "updates.json", doc)


def _panel_summary(panel):
    if panel is None:
        return None
    return {
        "state": panel["state"],
        "code": panel["code"],
        "cases": len(panel["predictions"]),
    }


def _entry(board):
    incumbent = board["incumbent"]
    return {
        "slug": board["slug"],
        "state": board["feed_state"]["state"],
        "code": board["feed_state"]["code"],
        "challenge": board["challenge"],
        "device_class": board["device_class"],
        "labels": board["labels"],
        "fixture": board["fixture"],
        "version": board["version"],
        "released_through_block": board["released_through_block"],
        "incumbent": None if incumbent is None else incumbent["hotkey"],
        "miners": len(board["miners"]),
    }
