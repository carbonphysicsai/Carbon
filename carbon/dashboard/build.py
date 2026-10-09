"""Write the static dashboard: the web app plus one board file per feed.

`build(out, documents, trust)` checks each feed document with `feed.project`
and writes:

- `data/index.json`: one entry per board (Challenge, device class, labels,
  feed state);
- `data/boards/<slug>.json`: the board model the pages draw.

A refused document never overwrites an accepted board. When an accepted board
for the same Challenge and device class is already in `out`, it stays, marked
`REFUSED` with the reason code, so the page shows the last good version and
why the newer one was not drawn. A refusal is never replaced by fixture data.

The brand fonts and wordmark are copied from the Launchpad's copies of the
verified website asset set, and their digests are checked against the website's
production baseline manifest values pinned here. Nothing loads from the
internet at runtime.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from carbon.dashboard import feed

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
    return copied


def _previous(out, slug):
    path = out / "data" / "boards" / f"{slug}.json"
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


def build(out, documents, trust, *, showcase=False):
    """Build the site into `out`; return the index written. With `showcase`,
    also write the design showcase replays (public EV4 material only)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    brand = _copy_web(out)
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
            continue
        board["feed_state"] = {"state": "ACCEPTED", "code": None}
        if board["showcase_panel"] is not None:
            leaders.append((board, board["showcase_panel"]))
        # The panel's predictions go to the showcase replays, not the board.
        board = {**board, "showcase_panel": _panel_summary(board["showcase_panel"])}
        if board["slug"] in entries and entries[board["slug"]]["state"] == "ACCEPTED":
            raise ValueError(f"two feeds for one board: {board['slug']}")
        _write_json(out / "data" / "boards" / f"{board['slug']}.json", board)
        entries[board["slug"]] = _entry(board)
    if showcase:
        from carbon.dashboard import showcase as replays

        replays.build_all(out / "showcase", leaders)
    index = {
        "schema": INDEX_SCHEMA,
        "fixture": trust.fixture,
        "brand_assets": brand,
        "boards": [entries[k] for k in sorted(entries)],
    }
    _write_json(out / "data" / "index.json", index)
    return index


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
