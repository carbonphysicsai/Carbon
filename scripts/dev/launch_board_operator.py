"""Build, sign and upload the dashboard's launch boards on the validator host
(OWNER-DASHBOARD-01; the Test Engineer's valV3 step 6).

One run, for every launch Challenge in the config:

1. fetch the receiver's own public king document (`GET /carbon/v1/koth/<id>`; an
   unpublished or unreachable one is handled below);
2. read the receiver's Ladder from its attempt-ledger file, read-only;
3. build the closed launch board (`carbon.challenge_validator.launch_board`) and sign it
   with the validator's feed key (loaded here, on the validator host, never printed,
   never copied);
4. write `<out>/<slug>.json` atomically, check it with the dashboard's own reader and
   the PUBLIC key, and upload it.

Before the first graded hotkey the board is the empty one (`PRE_FIRST_RELEASE`); the
moment a result is recorded the next run shows it. A receiver that cannot be reached
leaves the last written board in place (the dashboard marks a stale board STALE by its
own age) and the run says so; nothing finer than the receiver's own king document and
the Ladder's rounded totals ever enters a board.

    python scripts/dev/launch_board_operator.py run --config BOARDS.json
    python scripts/dev/launch_board_operator.py run --config BOARDS.json --every 300
    python scripts/dev/launch_board_operator.py systemd --config BOARDS.json

Config (`carbon.launch-board.operator.config.v1`, mode 600, never committed):

    {"schema": "carbon.launch-board.operator.config.v1",
     "network": "testnet",
     "ledger": "<the receiver's attempt-ledger file>",
     "receiver_url": "http://127.0.0.1:<receiver port>",
     "key": "<the validator's feed key file>",
     "out": "<directory the boards are written to>",
     "upload_command": ["npx", "wrangler@4", "r2", "object", "put",
                        "<bucket>/valv3/{name}", "--file", "{file}",
                        "--content-type", "application/json", "--remote"],
     "challenges": [
       {"id": "electric-motor-magnetics", "version": "1.4", "exam_version_label": "<label>"},
       {"id": "chip-cold-plate", "version": "1.4", "exam_version_label": "<label>"},
       {"id": "f08-ribbed-bracket", "version": "1.5", "exam_version_label": "<label>"},
       {"id": "f02", "version": "2.4", "exam_version_label": "<label>"}]}

`exam_version_label` is only used while the receiver publishes no king document yet (a
404); `exam_key` is optional per Challenge (default "latest": the exam of the most
recent graded result). `upload_command` is optional; `{file}` and `{name}` are
replaced, and nothing else is ever put on the command line.

`"board": "v2"` (optional; default "v1") builds the v2 board instead
(`launch_board.SCHEMA_V2`: the true rank order, the king's ``to_beat_rule`` and the last
``crown_changes``). Each Challenge then also names its receiver's pool store and its
contract digest:

     {"id": "chip-cold-plate", "version": "1.4", "exam_version_label": "<label>",
      "pool_store": "<the receiver's pool store file>",
      "contract_digest": "sha256:<64 hex>"}

and a v2 run (a) fetches the receiver's v2 king document (`GET /carbon/v1/koth/<id>/v2`),
(b) opens the pool store READ-ONLY (never created, never written) for the crown changes
(`koth_public.PoolKingView.crown_changes`, the receiver's own reader, with the epochs of
the ledger's signed receipts) and the exact best totals (`launch_board.exact_best_totals`,
the rank source as ruled, on the same exam key the board's rows are read under, resolved
once per run; the board uses an exact total only where it floors, at the Challenge's
registered rebuild noise, to its row's published total), and (c) checks the written
board with `launch_board.verify` under the PUBLIC key. The exact totals stay in this process: they set the order and are
never written, printed, uploaded or served. Without ``"board"`` (or with "v1") the run
is exactly the v1 run: same requests, same reads, same bytes.

Turn v2 on for a door only after the dashboard Worker that reads launch-board.v2 is
deployed; until then a v2 board would be refused there and the last good board kept.

`"board": "v6"` (owner 16 Nov: "Show scores to 3 decimals, so a lead smaller than the
margin is visible. Make the posted bar match the real rule.") is the v5 run built from
the receiver's v3 king document (`GET /carbon/v1/koth/<id>/v3`): totals at 3 decimals
(half up) and the bar `koth_public.TO_BEAT_RULE_EXACT`. A receiver that serves v1 but
no v3 yet is refused (`receiver_no_v3`), never shown as kingless. The same rule holds:
turn v6 on only after the Worker that reads launch-board.v6 and the door that serves
v3 are deployed; v1-v5 runs are unchanged.

`"board": "v7"` (owner DASHBOARD-ALL-TIME-SUBMISSIONS, pick "unique model designs"; definition v2 5744) is the v6 run
plus ONE signed count, ``designs.unique_submitted``: the distinct recipe digests among this door's admitted submissions,
all time (`unique_designs`, the ledger read-only). Order: the Worker that reads launch-board.v7 first, then the door
that serves it (`launch_board_file`), then this config; v1-v6 runs are unchanged.

Exit codes: 0 every board written and uploaded; 2 a board could not be built, checked
or uploaded (the run names which and why).

DEVELOPMENT / TESTNET only: display data, no score, weight or reward authority.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator import koth_public, koth_registry, launch_board
from carbon.challenge_validator.feed_file import write_feed
from carbon.challenge_validator.ladder_store import latest_exam_key
from carbon.challenge_validator.score_feed import FeedRefused
from carbon.dashboard import feed as dashboard_feed

CONFIG_SCHEMA = "carbon.launch-board.operator.config.v1"
NAMES = {"schema", "network", "ledger", "receiver_url", "key", "out", "challenges"}
OPTIONAL = {"upload_command", "fetch_timeout_seconds", "board"}
BOARDS = ("v1", "v2", "v3", "v4", "v5", "v6", "v7")
CHALLENGE_NAMES = {"id", "version", "exam_version_label"}
CHALLENGE_OPTIONAL = {"exam_key"}
#: What a v2 Challenge must also name; a v1 config never carries them.
CHALLENGE_V2 = {"pool_store", "contract_digest"}
MAX_KOTH_BYTES = koth_public.MAX_BYTES
_PLACEHOLDER = re.compile(r"\{(file|name)\}")
_CONTRACT = re.compile(r"sha256:[0-9a-f]{64}")


class OperatorRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def load_config(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        type(raw) is not dict
        or raw.get("schema") != CONFIG_SCHEMA
        or not NAMES <= set(raw)
        or set(raw) - NAMES - OPTIONAL
        or raw["network"] not in launch_board.NETWORKS
        or type(raw["challenges"]) is not list
        or not raw["challenges"]
    ):
        raise OperatorRefused("operator_config")
    if raw.get("board", "v1") not in BOARDS:
        raise OperatorRefused("operator_config_board")
    v2 = raw.get("board") in (
        "v2",
        "v3",
        "v4",
        "v5",
        "v6",
        "v7",
    )  # v3 is v2 plus the king's stability; v4 adds measure + checks; v5 is v3 plus crown time + row reasons; v6 is
    # v5's shape with totals to 3 decimals; v7 is v6 plus the signed unique-designs count
    for item in raw["challenges"]:
        required = CHALLENGE_NAMES | (CHALLENGE_V2 if v2 else set())
        if (
            type(item) is not dict
            or not required <= set(item)
            or set(item) - required - CHALLENGE_OPTIONAL
        ):
            raise OperatorRefused("operator_config_challenge")
        if v2 and (
            type(item["pool_store"]) is not str
            or not Path(item["pool_store"]).is_absolute()
            or type(item["contract_digest"]) is not str
            or not _CONTRACT.fullmatch(item["contract_digest"])
        ):
            raise OperatorRefused("operator_config_challenge")
    command = raw.get("upload_command")
    if command is not None and (
        type(command) is not list or not all(type(part) is str for part in command)
    ):
        raise OperatorRefused("operator_config_upload")
    if not re.fullmatch(r"https?://[^/\s]+", raw["receiver_url"]):
        raise OperatorRefused("operator_config_receiver")
    return raw


def fetch_king(receiver_url, challenge, timeout, *, v2=False, v3=False):
    """The receiver's king document for ``challenge`` (its v2 document at its own path
    when ``v2``, its v3 one when ``v3``), or None when it publishes none yet (404); an
    unreachable or malformed answer is `OperatorRefused`. With ``v3``, a 404 is "none
    yet" only when the v1 route is 404 too: a receiver serving v1 but no v3 (a door
    before 16 Nov) is `OperatorRefused` ("receiver_no_v3"), never a kingless board."""
    url = f"{receiver_url}{koth_public.PATH}{challenge['id']}"
    if v3:
        found = _fetch_king(url + koth_public.V3_SUFFIX, challenge, timeout)
        if found is None and _fetch_king(url, challenge, timeout) is not None:
            raise OperatorRefused("receiver_no_v3")
        return found
    if v2:
        url += koth_public.V2_SUFFIX
    return _fetch_king(url, challenge, timeout)


def _fetch_king(url, challenge, timeout):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(MAX_KOTH_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise OperatorRefused("receiver_unavailable") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise OperatorRefused("receiver_unavailable") from None
    if len(body) > MAX_KOTH_BYTES:
        raise OperatorRefused("receiver_answer_too_large")
    try:
        document = json.loads(body)
    except ValueError:
        raise OperatorRefused("receiver_answer_malformed") from None
    if type(document) is not dict or document.get("challenge_id") != challenge["id"]:
        raise OperatorRefused("receiver_answer_other_challenge")
    return document


def unpublished_king(challenge, *, v2=False, v3=False):
    """The king document of a receiver that publishes none yet: no king, no margin."""
    build = (
        koth_public.document_v3
        if v3
        else koth_public.document_v2 if v2 else koth_public.document
    )
    return build(
        challenge_id=challenge["id"],
        challenge_version=challenge["version"],
        exam_version_label=challenge["exam_version_label"],
        king=None,
        rebuild_noise=None,
        baseline_total=None,
    )


def _readonly(path):
    """A read-only connection to an existing owner-only database file (a symlink is
    refused). It never creates the database, never changes its journal mode and cannot
    write it (``mode=ro`` and ``query_only``); on a WAL database whose receiver is
    stopped, SQLite may leave the empty -wal/-shm sidecars a reader needs."""
    path = Path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise OperatorRefused("pool_store_not_owner_only")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


class ReadOnlyPoolStore:
    """The receiver's pool store, read-only: exactly the four `PoolStore` readers the v2
    sources call, over `_readonly` connections. It has no writer."""

    def __init__(self, path):
        self.path = Path(path)

    @contextlib.contextmanager
    def db(self):
        with contextlib.closing(_readonly(self.path)) as connection:
            yield connection

    events = PoolStore.events
    incumbent = PoolStore.incumbent
    incumbent_standing = PoolStore.incumbent_standing
    private_evaluation_bodies = PoolStore.private_evaluation_bodies
    crown_average_unstable = PoolStore.crown_average_unstable
    crown_mean = PoolStore.crown_mean
    incumbent_evaluation_key = PoolStore.incumbent_evaluation_key
    kept_crown_rebuilds = PoolStore.kept_crown_rebuilds
    crown_decisions = PoolStore.crown_decisions
    crown_decided_by = PoolStore.crown_decided_by
    submission_hotkey = PoolStore.submission_hotkey


class _ReadOnlyLedger:
    """The receiver's attempt ledger, read-only, for `exam_cap.submission_block`."""

    def __init__(self, path):
        self.path = Path(path)

    @contextlib.contextmanager
    def _db(self):
        with contextlib.closing(_readonly(self.path)) as connection:
            yield connection


def v2_sources(config, item, king_document, exam_key, *, v3=False):
    """``(crown_changes, exact_totals)`` for a v2 board, read here, on the validator host,
    from the receiver's pool store and ledger (both read-only). The crown changes are the
    receiver's own `PoolKingView.crown_changes`; the exact totals are
    `launch_board.exact_best_totals` on ``exam_key`` (the sealed pack digest the board's
    rows are read under), with the king's entry its standing. They are returned to
    `run_once` only, which hands them to `launch_board.build`: nothing here writes, prints or keeps them. No pool store yet is
    no change of king and no exact total. With ``v3`` (a v6 board) the crown changes show
    each total as the v3 king page does (3 decimals, half up)."""
    from carbon.challenge_validator import exam_cap

    if not os.path.lexists(item["pool_store"]):
        return [], {}
    store = ReadOnlyPoolStore(item["pool_store"])
    ledger = _ReadOnlyLedger(config["ledger"])

    def epoch_of(submission_id):
        if not os.path.lexists(ledger.path):
            return None
        block = exam_cap.submission_block(
            ledger, item["contract_digest"], submission_id
        )
        return None if block is None else exam_cap.epoch_of(block)

    ranked = ranked_by(item)
    view = koth_public.PoolKingView(
        open_store=lambda: store,
        epoch_of=epoch_of,
        exam_version_label=king_document["exam_version_label"],
        rebuild_noise_of=lambda: koth_registry.rebuild_noise(
            item["id"], version=item["version"]
        ),
        value=ranked,
        decimals=shown_decimals(item),
    )
    changes = view.crown_changes(limit=launch_board.MAX_CROWN_CHANGES, v3=v3)
    king_model_id = None
    if king_document["king"] is not None:
        # The king row's exact entry is the standing of the king the document names; a
        # crown that moved between the two reads is refused (the next run is consistent).
        incumbent = store.incumbent()
        standing = (
            None
            if incumbent is None
            else store.incumbent_standing(incumbent["model_id"])
        )
        if standing is None or (
            koth_public._owner_hotkey(standing["owner"])
            != king_document["king"]["hotkey"]
        ):
            raise OperatorRefused("king_moved_during_run")
        king_model_id = incumbent["model_id"]
    exact = launch_board.exact_best_totals(
        store,
        challenge_id=item["id"],
        exam_key=exam_key,
        king_model_id=king_model_id,
        value=ranked,
    )
    return changes, exact


def shown_decimals(item):
    """The decimals ``item``'s version shows its number at (`crown_official.shown_decimals`), or None as before."""
    from carbon.challenge_validator import crown_official

    try:
        return crown_official.shown_decimals(item["id"], item["version"])
    except crown_official.CrownOfficialInvalid:
        raise OperatorRefused("crown_official_invalid") from None


def shown_king(king, exact, decimals):
    """The v3 king document at ``decimals`` whatever the door shows: the king's number and the score to beat are taken from
    his own exact standing (``exact``, the board's source), so the signed board never carries a finer one than the rule.
    """
    if decimals is None or king["king"] is None:
        return king
    own = exact.get(king["king"]["hotkey"])
    if type(own) is not float:
        raise OperatorRefused("king_moved_during_run")
    return {
        **king,
        "king": {**king["king"], "total": koth_public.shown_total(own, decimals)},
        "to_beat": (
            None
            if king["margin"] is None
            else koth_public.to_beat_exact(own, king["margin"], decimals)
        ),
    }


def ranked_by(item):
    """The reader of the number ``item``'s version is ranked by (`crown_official.reader`), None for its total; a malformed
    registry refuses (``crown_official_invalid``)."""
    from carbon.challenge_validator import crown_official

    try:
        return crown_official.reader(item["id"], item["version"])
    except crown_official.CrownOfficialInvalid:
        raise OperatorRefused("crown_official_invalid") from None


def king_stability(config, item, king_document):
    """The v3 board's ``stability`` for the king ``king_document`` names (Validator 3 Nov 07:56): None with no king.
    The store's incumbent must BE that king (`king_mismatch` otherwise: the standing's owner hotkey is the document's).
    "UNSTABLE" when the king's latest crown-average record is seed-fragile (`PoolStore.crown_average_unstable`);
    "STABLE" ONLY when a measurement is filed for him (`PoolStore.crown_mean` is a number: KING_MEASURED), so STABLE is
    earned; a king with no filed measurement refuses (`king_unmeasured`), it is never defaulted. It reads two booleans; no
    seed, mean or per-seed status leaves this function (OWNER-CROWN-AVG-UNSTABLE-KING-01).
    """
    if king_document["king"] is None:
        return None
    if not os.path.lexists(item["pool_store"]):
        raise OperatorRefused(
            "king_mismatch"
        )  # a king on the document, no store to hold him
    store = ReadOnlyPoolStore(item["pool_store"])
    incumbent = store.incumbent()
    standing = (
        None if incumbent is None else store.incumbent_standing(incumbent["model_id"])
    )
    if (
        standing is None
        or koth_public._owner_hotkey(standing["owner"])
        != king_document["king"]["hotkey"]
    ):
        raise OperatorRefused("king_mismatch")
    if official_score(item):
        # Official-score crowns (owner 14 Nov; `crown_official`): the king's score IS his official grade, compared with
        # no rebuild, so there is no rebuild mean to file and no rebuild spread to flag. His registered score stands as
        # shown: STABLE (the page's UNSTABLE line, "moved between rebuilds", does not apply to this rule).
        return "STABLE"
    if store.crown_average_unstable(incumbent["model_id"]):
        return "UNSTABLE"
    if store.crown_mean(incumbent["model_id"]) is None:
        raise OperatorRefused("king_unmeasured")
    return "STABLE"


def official_rule(item, king):
    """The v2 king document with the bar's rule NAMED as it decides: for a version that registers official-score crowns
    (`official_score`), a door whose king page still says the averaged id (`koth_public.TO_BEAT_RULE_AVERAGED`, a receiver
    before the official bar's id) is shown under the single-grade id (`koth_public.TO_BEAT_RULE`), the rule that decides
    its crowns. Only the name: the score to beat is the door's own number (for this rule both ids give the same
    guaranteed bound, floor + step + margin, rounded up). Any other document is returned as it is.
    """
    if (
        type(king) is dict
        and king.get("to_beat_rule") == koth_public.TO_BEAT_RULE_AVERAGED
        and official_score(item)
    ):
        return {**king, "to_beat_rule": koth_public.TO_BEAT_RULE}
    return king


def official_score(item):
    """True when ``item``'s Challenge version registers official-score crowns (`crown_official.registered`, the same
    registry file the receiver reads at start); a malformed registry refuses (``crown_official_invalid``).
    """
    from carbon.challenge_validator import crown_official

    try:
        return crown_official.registered(item["id"], item["version"]) is not None
    except crown_official.CrownOfficialInvalid:
        raise OperatorRefused("crown_official_invalid") from None


def crowned_utc(config, item, king_document):
    """The v5 board's ``crowned_utc``: when the store's incumbent, who must BE the king the document names
    (`king_mismatch`), was DECIDED (the incumbent row's ``since``, written by the crown decision itself: never the
    submission's arrival), as UTC to the second; None with no king or no recorded decision time.
    """
    import datetime

    if king_document["king"] is None:
        return None
    if not os.path.lexists(item["pool_store"]):
        raise OperatorRefused("king_mismatch")
    store = ReadOnlyPoolStore(item["pool_store"])
    incumbent = store.incumbent()
    standing = (
        None if incumbent is None else store.incumbent_standing(incumbent["model_id"])
    )
    if (
        standing is None
        or koth_public._owner_hotkey(standing["owner"])
        != king_document["king"]["hotkey"]
    ):
        raise OperatorRefused("king_mismatch")
    with store.db() as db:
        row = db.execute("SELECT since FROM incumbent WHERE id=1").fetchone()
    since = None if row is None else row[0]
    if type(since) not in (int, float) or isinstance(since, bool) or since <= 0:
        return None
    return datetime.datetime.fromtimestamp(int(since), datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


#: The internal UNAVAILABLE reasons with their own public phrase (crown_average.KING_UNMEASURED; bank_promotion.CROWNS_PAUSED
#: and CROWN_QUEUED). Kept here, on the validator side: the miner-surface board module names no internal reason.
_WAIT_KING_REASONS = ("crown_average_king_unmeasured",)
_QUEUED_REASONS = ("crowns_paused", "queued_behind_undecided_crown")


def public_note(outcome, reason):
    """The public phrase (`launch_board.NOTES`) of a crown check's ``outcome`` and internal ``reason``, or None for an
    outcome outside the board's closed set. The reason only picks between the UNAVAILABLE phrases; it is never published.
    """
    if outcome not in launch_board.NOTES:
        return None
    if outcome != "UNAVAILABLE":
        return launch_board.NOTES[outcome][0]
    if reason in _WAIT_KING_REASONS:
        return launch_board.NOTE_WAIT_KING
    if reason in _QUEUED_REASONS:
        return launch_board.NOTE_QUEUED
    return launch_board.NOTE_PENDING


def king_measure(config, item, king_document):
    """The v4 board's ``(stability, measure)`` for the king ``king_document`` names: ``(None, None)`` with no king. The
    store's incumbent must BE that king (`king_mismatch`). On the king's CURRENT key (`incumbent_evaluation_key`, which
    follows a rebuild link): MEASURED when a mean is filed there (stability STABLE), UNSTABLE when his re-measure was
    seed-fragile (UNSTABLE), else IN_PROGRESS with the kept rebuild count, or UNMEASURED (stability None: not yet
    measured, never defaulted). ``n`` is the registered N for the Challenge. Two counts leave this function; no seed or
    mean does."""
    from carbon.challenge_validator import crown_common

    if king_document["king"] is None:
        return None, None
    if not os.path.lexists(item["pool_store"]):
        raise OperatorRefused("king_mismatch")
    store = ReadOnlyPoolStore(item["pool_store"])
    incumbent = store.incumbent()
    standing = (
        None if incumbent is None else store.incumbent_standing(incumbent["model_id"])
    )
    if (
        standing is None
        or koth_public._owner_hotkey(standing["owner"])
        != king_document["king"]["hotkey"]
    ):
        raise OperatorRefused("king_mismatch")
    model = incumbent["model_id"]
    key = store.incumbent_evaluation_key(model)
    n = crown_common.load_rule().n_for(item["id"], item["version"])
    kept = 0 if key is None else min(store.kept_crown_rebuilds(model, key), n)
    if key is not None and store.crown_mean(model, key) is not None:
        return "STABLE", {"state": "MEASURED", "kept": n, "n": n}
    if key is not None and store.crown_average_unstable(model, key):
        return "UNSTABLE", {"state": "UNSTABLE", "kept": kept, "n": n}
    return None, {
        "state": "IN_PROGRESS" if kept else "UNMEASURED",
        "kept": kept,
        "n": n,
    }


def crown_checks(config, item):
    """The v4 board's ``crown_checks``: the latest crown decision per contender, newest first (`PoolStore.crown_decisions`),
    as hotkey + state + outcome + the PUBLIC note (`public_note`; the internal reason code never leaves). A
    contender without an admitted hotkey (a derived, host-owned row) or with an outcome outside the board's closed set is
    left out, never partly shown."""
    if not os.path.lexists(item["pool_store"]):
        return []
    store = ReadOnlyPoolStore(item["pool_store"])
    out, seen = [], set()
    for record in store.crown_decisions(limit=4 * launch_board.MAX_CROWN_CHECKS):
        hotkey = store.submission_hotkey(record["submission_id"])
        outcome = record["outcome"]
        note = public_note(outcome, record["reason"])
        if hotkey is None or hotkey in seen or note is None:
            continue
        seen.add(hotkey)
        out.append(
            {
                "hotkey": hotkey,
                "state": (
                    "DECIDED" if outcome in launch_board.DECIDED_OUTCOMES else "PENDING"
                ),
                "outcome": outcome,
                "note": note,
            }
        )
        if len(out) >= launch_board.MAX_CROWN_CHECKS:
            break
    return out


def unique_designs(config):
    """The v7 board's count (owner DASHBOARD-ALL-TIME-SUBMISSIONS; definition v2 5744): the number of DISTINCT recipe
    digests among this door's ADMITTED submissions, all time, from the receiver's attempt ledger read-only. Every
    admitted submission's digest is written there at admission (`recipe_copies.note_admitted`); a refused-at-intake
    submission never is. One aggregate number: no id, digest or hotkey leaves this function. An unreadable ledger or a
    ledger without the table refuses the run (the last good board is kept), never a 0.
    """
    try:
        with contextlib.closing(_readonly(Path(config["ledger"]))) as db:
            (count,) = db.execute(
                "SELECT COUNT(DISTINCT recipe_digest) FROM recipe_copy_digests"
            ).fetchone()
    except (sqlite3.Error, OSError, TypeError, ValueError):
        raise OperatorRefused("ledger_designs_unavailable") from None
    if type(count) is not int or count < 0:
        raise OperatorRefused("ledger_designs_unavailable")
    return count


def slug_of(challenge):
    return dashboard_feed.board_slug(challenge["id"], "no-class")


def upload(command, path, name):
    """Run the configured upload command with `{file}` and `{name}` filled in."""
    if command is None:
        return None
    argv = [
        _PLACEHOLDER.sub(lambda m: {"file": str(path), "name": name}[m[1]], part)
        for part in command
    ]
    done = subprocess.run(
        argv, capture_output=True, text=True, timeout=300, check=False
    )
    if done.returncode != 0:
        raise OperatorRefused("upload_failed")
    return name


def run_once(config, *, version=None):
    """Build, sign, check and upload every board; the list of result rows."""
    key = launch_board.LaunchBoardKey.load(config["key"])
    trust = dashboard_feed.Trust(keys=frozenset({key.public_key}))
    out = Path(config["out"])
    out.mkdir(parents=True, exist_ok=True)
    version = launch_board.now_version() if version is None else version
    timeout = config.get("fetch_timeout_seconds", 10)
    v2 = config.get("board") in ("v2", "v3", "v4", "v5", "v6", "v7")
    v7 = (
        config.get("board") == "v7"
    )  # v6's run plus the door's unique admitted designs count
    v6 = v7 or config.get("board") == "v6"  # v5's run, from the v3 king document
    v5 = v6 or config.get("board") == "v5"
    three = {"v3": True} if v6 else {}
    v4 = config.get("board") == "v4"
    v3 = v5 or v4 or config.get("board") == "v3"
    rows = []
    for item in config["challenges"]:
        challenge = type(
            "Challenge", (), {"challenge_id": item["id"], "version": item["version"]}
        )()
        name = slug_of(item) + ".json"
        row = {"challenge": item["id"], "version": item["version"], "file": name}
        try:
            # a malformed crown registry refuses this board first, by its own code: the Ladder is read through it too
            ranked_by(item)
            king = fetch_king(config["receiver_url"], item, timeout, v2=v2, **three)
            king = unpublished_king(item, v2=v2, **three) if king is None else king
            exam_key = item.get("exam_key", "latest")
            extra = {"v6": True} if v6 else {}
            if v2:
                if not v6:
                    # a v3 king page never states the averaged id on an official-score door
                    king = official_rule(item, king)
                # The closed v2 king check the build makes, first: the sources read
                # only a king document of exactly that shape.
                launch_board._king(king, v2=True, v6=v6)
                if exam_key == "latest":
                    # one exam for the rows and their exact totals, resolved once
                    exam_key = latest_exam_key(config["ledger"], challenge)
                try:
                    changes, exact = v2_sources(config, item, king, exam_key, **three)
                except (sqlite3.Error, StateError):
                    raise OperatorRefused("pool_store_unavailable") from None
                if v6:
                    decimals = shown_decimals(item)
                    king = shown_king(king, exact, decimals)
                    if decimals is not None:
                        extra["decimals"] = decimals
                extra = {
                    **extra,
                    "crown_changes": changes,
                    "exact_totals": exact,
                    "rebuild_noise": koth_registry.rebuild_noise(
                        item["id"], version=item["version"]
                    ),
                }
                if v4:
                    try:
                        extra["stability"], extra["measure"] = king_measure(
                            config, item, king
                        )
                        extra["crown_checks"] = crown_checks(config, item)
                    except (sqlite3.Error, StateError):
                        raise OperatorRefused("pool_store_unavailable") from None
                elif v3:
                    try:
                        extra["stability"] = king_stability(config, item, king)
                        if v5:
                            extra["crowned_utc"] = crowned_utc(config, item, king)
                    except (sqlite3.Error, StateError):
                        raise OperatorRefused("pool_store_unavailable") from None
                if v7:
                    extra["designs"] = unique_designs(config)
            board = launch_board.build_from_ledger(
                ledger=config["ledger"],
                challenge=challenge,
                exam_key=exam_key,
                king_document=king,
                network=config["network"],
                key=key,
                version=version,
                **extra,
            )
            path = out / name
            write_feed(path, board)
            written = json.loads(path.read_text(encoding="utf-8"))
            if v2:
                # The v2 board's closed shape and signature, under the PUBLIC key (the
                # reader the dashboard Worker's v2 reader is held equal to).
                shown = launch_board.verify(written, key.public_key)["counts"]
            else:
                # The dashboard's own reader, under the PUBLIC key, must accept what
                # was written before it is uploaded.
                shown = dashboard_feed.project(written, trust)["launch"]["counts"]
            row.update(
                state="WROTE",
                graded=board["counts"]["graded"],
                king=board["king"]["king"] is not None,
                shown=shown["graded"],
            )
            if v2:
                row.update(
                    board=(
                        "v7"
                        if v7
                        else (
                            "v6"
                            if v6
                            else "v5" if v5 else "v4" if v4 else "v3" if v3 else "v2"
                        )
                    ),
                    crown_changes=len(board["crown_changes"]),
                )
            if upload(config.get("upload_command"), path, name):
                row["state"] = "UPLOADED"
        except (
            OperatorRefused,
            launch_board.BoardRefused,
            dashboard_feed.FeedRefused,
            ValueError,
            OSError,
            subprocess.SubprocessError,
        ) as error:
            row.update(
                state="REFUSED", code=getattr(error, "code", type(error).__name__)
            )
        rows.append(row)
    return rows


def systemd_units(config_path, *, every=300):
    """A oneshot service and a timer that run this script every ``every`` seconds."""
    script = Path(__file__).resolve()
    return f"""# /etc/systemd/system/carbon-launch-board.service
[Unit]
Description=Carbon launch boards: build, sign and upload the dashboard standing

[Service]
Type=oneshot
ExecStart={sys.executable} {script} run --config {Path(config_path).resolve()}

# /etc/systemd/system/carbon-launch-board.timer
[Unit]
Description=Carbon launch boards every {every} s

[Timer]
OnBootSec=1min
OnUnitActiveSec={every}s

[Install]
WantedBy=timers.target
"""


def main(argv=None):
    parser = argparse.ArgumentParser(prog="launch_board_operator")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument(
        "--every", type=int, default=0, help="repeat every N seconds (0: once)"
    )
    unit = commands.add_parser("systemd")
    unit.add_argument("--config", required=True, type=Path)
    unit.add_argument("--every", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except (OperatorRefused, OSError, ValueError) as error:
        print(json.dumps({"refused": getattr(error, "code", type(error).__name__)}))
        return 2
    if args.command == "systemd":
        print(systemd_units(args.config, every=args.every))
        return 0
    while True:
        try:
            rows = run_once(config)
        except (FeedRefused, OSError) as error:
            print(json.dumps({"refused": getattr(error, "code", type(error).__name__)}))
            return 2
        print(json.dumps({"boards": rows}, sort_keys=True), flush=True)
        failed = any(row["state"] == "REFUSED" for row in rows)
        if args.every <= 0:
            return 2 if failed else 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
