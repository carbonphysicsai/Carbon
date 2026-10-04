"""The miner's private library and the literature a miner campaign serves.

OWNER-GRAPHITE-MINER-01 §3-§5. Two objects:

- `MinerLibrary(root)`: the miner's own library at
  `<profile root>/graphite-library/`, owner-only (directories 0700, files
  0600), content-addressed and append-only where it is a journal. It holds
  the cards the miner's hunts extracted (origin `miner_hunt`, in a
  `method_cards.CardStore`, with the arXiv records they came from), the texts
  the miner imported and their cards (origin `miner_import`), a claims table
  that makes every paid extraction happen at most once per paper, the
  curation journal (pins and bans), the plan store, and the miner's own
  practice outcomes per card. The Library doors (Control Center and MCP) read
  and curate it; none of its operations admits work.
- `MinerLiterature(pack, library, ...)`: the read-only literature one campaign
  serves through `lit_search` and `lit_card`, frozen by digest: the shared
  pack, one private-library snapshot (`MinerLibrary.snapshot`) and one
  curation state. Replaying a campaign serves the same cards in the same
  order, whatever the library holds later.

Every served card carries its `origin` (`shared`, `miner_hunt` or
`miner_import`) and `check_status` `UNCHECKED`. A card that names protected
material (`tools.protected`) is withheld when it is written and again when it
is served. A banned card is never served. A pinned card is flagged so the
Planner must consider it. Card text is data, never instructions.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .. import literature, method_cards
from ..literature_fetch import RawStore
from ..tools import protected
from . import focus, imports
from .pack import (
    MINER_HUNT,
    MINER_IMPORT,
    ORIGINS,
    SHARED,
    UNCHECKED,
    SharedPack,
    card_paper_key,
    load_shared_pack,
    paper_key,
)

CURATION_SCHEMA = "carbon.graphite.miner-curation.v1"
CURATION_ENTRY_SCHEMA = "carbon.graphite.miner-curation-entry.v1"
SNAPSHOT_SCHEMA = "carbon.graphite.miner-library-snapshot.v1"
OUTCOME_SCHEMA = "carbon.graphite.miner-outcome.v1"
PLAN_INDEX_SCHEMA = "carbon.graphite.miner-plan-index.v1"
CLAIM_SCHEMA = "carbon.graphite.miner-claim.v1"
CLAIM_OUTCOME_SCHEMA = "carbon.graphite.miner-claim-outcome.v1"
IMPORT_CARD_SCHEMA = "carbon.graphite.miner-import-card.v1"
LITERATURE_SCHEMA = "carbon.graphite.miner-literature.v1"

CARD_NOT_FOUND = "card_not_found"
CARD_BANNED = "card_banned"
PLAN_NOT_FOUND = "plan_not_found"
PLAN_INVALID = "plan_invalid"
SEARCH_INVALID = "search_invalid"
EVIDENCE_INVALID = "evidence_invalid"
LIBRARY_ROOT_INVALID = "library_root_invalid"

#: The most results one `lit_search` returns, as the phase-1 tool does.
MAX_RESULTS = literature.MAX_RESULTS
MAX_SEARCH_LIMIT = 50
MAX_PLAN_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 16 * 1024
MAX_OUTCOME_CARDS = 64
PLAN_AUTHORS = ("planner", "miner")
UNCHECKED_NOTE = (
    "UNCHECKED: no person has checked this card's extraction. Its claims are "
    "the source's own as a model extracted them, not Carbon's."
)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_KEY = re.compile(r"[a-z0-9][a-z0-9.-]{0,95}\Z")


class LibraryError(ValueError):
    """A typed refusal from the library; nothing was changed."""

    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code, self.detail = code, detail


def _flock(fd):
    try:
        import fcntl
    except ImportError:  # pragma: no cover - the miner stack runs on Linux
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        return
    fcntl.flock(fd, fcntl.LOCK_EX)


@contextlib.contextmanager
def _locked(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _flock(descriptor)
        yield
    finally:
        os.close(descriptor)


def _append(path, payload):
    with path.open("ab") as stream:
        stream.write(payload + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


def _lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def _hex(value):
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise ValueError("a digest is sha256")
    return value[len("sha256:") :]


def curation_digest(pins, bans):
    return digest(
        canonical(
            {"schema": CURATION_SCHEMA, "pins": sorted(pins), "bans": sorted(bans)}
        )
    )


def curation_state(pins=(), bans=()):
    pins, bans = sorted(set(pins)), sorted(set(bans))
    return {"pins": pins, "bans": bans, "digest": curation_digest(pins, bans)}


def checked_curation(curation):
    """A curation state whose digest matches its pins and bans."""
    if curation is None:
        return curation_state()
    if type(curation) is not dict or set(curation) != {"pins", "bans", "digest"}:
        raise ValueError("a curation state is {pins, bans, digest}")
    pins, bans = curation["pins"], curation["bans"]
    if (
        type(pins) is not list
        or type(bans) is not list
        or any(type(i) is not str for i in [*pins, *bans])
        or set(pins) & set(bans)
    ):
        raise ValueError("pins and bans are disjoint lists of card ids")
    state = curation_state(pins, bans)
    if state["digest"] != curation["digest"]:
        raise ValueError("a curation state does not match its digest")
    return state


def _served(card, origin):
    """A served card: the method-card fields, its origin and its status."""
    return {
        **{name: card[name] for name in literature.CARD_FIELDS},
        "origin": origin,
        "check_status": UNCHECKED,
    }


def import_served(card):
    """The served form of an import card."""
    extraction = card["extraction"]
    claims = "; ".join(card["construction_claims"]) or "not stated"
    evidence = "; ".join(card["reported_evidence"]) or "not stated"
    inputs = "; ".join(card["required_inputs"]) or "not stated"
    return {
        "card_id": card["card_id"],
        "title": card["title"],
        "technique": card["method_name"] + "; " + card["family"],
        "claimed_effect": claims + " | reported evidence: " + evidence,
        "data_regime": card["data_regime"] + " | required inputs: " + inputs,
        "cost": card["cost"],
        "code_available": card["code_available"],
        "applicability": card["applicability"],
        "abstract": card["excerpt"],
        "provenance": (
            f"miner import {card['import_id']} (text {card['text_digest']}); "
            f"method card {UNCHECKED}; extracted by {extraction['model']} via "
            f"{extraction['provider_id']}, prompt {extraction['prompt_digest']}; "
            "the claims are the text's own as extracted, not Carbon's"
        ),
        "origin": MINER_IMPORT,
        "check_status": UNCHECKED,
    }


_PACK_SERVED = {}


def _pack_served(pack):
    """The pack's servable cards (copies), withheld ones apart; per digest."""
    found = _PACK_SERVED.get(pack.digest)
    if found is None or found[0] is not pack:
        cards, withheld = [], []
        for card in pack.cards:
            served = _served(card, SHARED)
            (withheld if protected(served) else cards).append(served)
        found = (pack, tuple(cards), tuple(c["card_id"] for c in withheld))
        _PACK_SERVED.clear()
        _PACK_SERVED[pack.digest] = found
    return found[1], found[2]


class _Served:
    """One served view: pack cards, private cards, a curation state, the
    miner's outcome counts and one Challenge's public context."""

    def __init__(self, pack, private, *, curation, evidence, discovery, contract):
        pack_cards, withheld = _pack_served(pack)
        self.withheld = list(withheld)
        self.bans, self.pins = set(curation["bans"]), set(curation["pins"])
        self.cards, self.banned, self.shadowed = {}, {}, []
        for card in pack_cards:
            self._add(card)
        known = pack.paper_keys
        for card in private:
            key = card_paper_key(card["card_id"])
            if card["card_id"] in self.cards or (key is not None and key in known):
                self.shadowed.append(card["card_id"])
                continue
            if protected(card):
                self.withheld.append(card["card_id"])
                continue
            self._add(card)
        self.focus = focus.discovery_focus(discovery)
        self.statuses = focus.contract_statuses(contract)
        self.counts = focus._counts(evidence)
        self._assessed = {}

    def _add(self, card):
        target = self.banned if card["card_id"] in self.bans else self.cards
        target[card["card_id"]] = card

    def assess(self, card):
        cid = card["card_id"]
        if cid not in self._assessed:
            self._assessed[cid] = focus.assess(
                card,
                focus=self.focus,
                statuses=self.statuses,
                counts=self.counts,
                pinned=cid in self.pins,
            )
        return self._assessed[cid]

    def ranked(self, query, limit):
        """`(card, assessment)` best first: by query hits when there is a
        query, then pin, grade and id."""
        rows = []
        for card in self.cards.values():
            hits = focus.query_hits(query, card) if query else 0
            if query and not hits:
                continue
            result = self.assess(card)
            rows.append(((-hits, *result["_order"], card["card_id"]), card, result))
        rows.sort(key=lambda row: row[0])
        return [(card, result) for _, card, result in rows[:limit]]

    def status(self, card_id):
        if card_id in self.cards:
            return "served"
        if card_id in self.banned:
            return "banned"
        return "unknown"

    def pinned(self):
        return [self.cards[cid] for cid in sorted(self.pins) if cid in self.cards]


def _row(card, result, *, full):
    row = (
        dict(card)
        if full
        else {
            "card_id": card["card_id"],
            "title": card["title"],
            "origin": card["origin"],
            "check_status": card["check_status"],
        }
    )
    row.update(
        {
            "score": result["score"],
            "reasons": list(result["reasons"]),
            "pinned": result["pinned"],
            "plan_input": result["plan_input"],
            "capability_request_candidate": result["capability_request_candidate"],
        }
    )
    return row


class MinerLibrary:
    """The miner's private library under one owner-only root."""

    def __init__(self, root, *, pack=None, clock=time.time):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise LibraryError(LIBRARY_ROOT_INVALID, "an absolute, private root")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if hasattr(os, "getuid") and root.stat().st_uid != os.getuid():
            raise LibraryError(LIBRARY_ROOT_INVALID, "the root is not the miner's")
        root.chmod(0o700)
        for name in (
            "raw",
            "hunted",
            "claims",
            "imports",
            "imports/queue",
            "imports/cards",
            "imports/rejections",
            "curations",
            "snapshots",
            "plans",
            "hunts",
        ):
            (root / name).mkdir(exist_ok=True, mode=0o700)
        if pack is not None and type(pack) is not SharedPack:
            raise TypeError("exact SharedPack required")
        self.root, self.clock, self._pack = root, clock, pack
        self.hunted = method_cards.CardStore(root / "hunted")
        self._views = {}

    # -- the shared pack ------------------------------------------------------------
    @property
    def pack(self):
        if self._pack is None:
            self._pack = load_shared_pack()
        return self._pack

    def _lock(self):
        return _locked(self.root / "library.lock")

    def _now(self):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))

    # -- private cards --------------------------------------------------------------
    def raw(self):
        return RawStore(self.root / "raw")

    def put_hunted_card(self, card):
        """Store a hunted card (`method_cards.make_card`) write-once."""
        return self.hunted.put_card(card)

    def put_import_card(self, card):
        if card.get("schema") != IMPORT_CARD_SCHEMA or card.get("status") != UNCHECKED:
            raise ValueError("an import card is written UNCHECKED")
        if not imports.is_import_id(card.get("card_id")):
            raise ValueError("an import card's id is its import id")
        write_once(
            self.root / "imports" / "cards" / (card["card_id"] + ".json"),
            canonical(card),
        )
        return digest(canonical(card))

    def put_import_rejection(self, import_id, rejection):
        write_once(
            self.root / "imports" / "rejections" / (import_id + ".json"),
            canonical({"schema": method_cards.REJECTION_SCHEMA, **rejection}),
        )

    def _hunted_served(self, card):
        if not card.get("relevant"):
            return None
        record = self.raw().record(card["record_digest"])
        if digest(record["abstract"].encode("utf-8")) != card["abstract_digest"]:
            raise ValueError("a hunted card's abstract no longer matches its record")
        served = {
            **method_cards._index_card(card, record["abstract"], UNCHECKED),
            "origin": MINER_HUNT,
            "check_status": UNCHECKED,
        }
        return None if protected(served) else served

    def _import_card(self, card_id):
        path = self.root / "imports" / "cards" / (card_id + ".json")
        return json.loads(path.read_bytes()) if path.exists() else None

    def _private_served(self, card_id):
        if imports.is_import_id(card_id):
            card = self._import_card(card_id)
            if card is None or not card.get("relevant"):
                return None
            served = import_served(card)
            return None if protected(served) else served
        if not literature._CARD_ID.fullmatch(card_id or ""):
            return None
        card = self.hunted.card(card_id)
        return None if card is None else self._hunted_served(card)

    def private_ids(self):
        hunted = sorted(p.stem for p in (self.hunted.root / "cards").glob("*.json"))
        imported = sorted(
            p.stem for p in (self.root / "imports" / "cards").glob("*.json")
        )
        return hunted + imported

    def private_cards(self):
        """Every private card the library serves now, by id."""
        cards = []
        for card_id in self.private_ids():
            served = self._private_served(card_id)
            if served is not None:
                cards.append(served)
        return cards

    # -- claims: one paid extraction per paper ----------------------------------------
    def _claim_path(self, key, suffix):
        if type(key) is not str or not _KEY.fullmatch(key):
            raise ValueError("a claim key is a paper key or an import id")
        return self.root / "claims" / (key + suffix)

    def claim(self, key, *, request_digest, hunt):
        """Claim a paper (or an import) for one extraction. False when it is
        already claimed: a claim is never taken twice."""
        path = self._claim_path(key, ".claim")
        payload = canonical(
            {
                "schema": CLAIM_SCHEMA,
                "key": key,
                "request_digest": request_digest,
                "hunt": hunt,
            }
        )
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return True

    def claim_state(self, key):
        """`{claim, outcome}` for a claimed key, or None."""
        path = self._claim_path(key, ".claim")
        if not path.exists():
            return None
        outcome = self._claim_path(key, ".outcome")
        return {
            "claim": json.loads(path.read_bytes()),
            "outcome": json.loads(outcome.read_bytes()) if outcome.exists() else None,
        }

    def settle(self, key, outcome):
        write_once(
            self._claim_path(key, ".outcome"),
            canonical({"schema": CLAIM_OUTCOME_SCHEMA, "key": key, **outcome}),
        )

    def release(self, key):
        """Release a claim whose call was certainly not sent."""
        if self._claim_path(key, ".outcome").exists():
            raise ValueError("a settled claim is never released")
        with contextlib.suppress(FileNotFoundError):
            self._claim_path(key, ".claim").unlink()

    def known_paper(self, key):
        """True when the pack or this library already knows the paper."""
        return key in self.pack.paper_keys or self._claim_path(key, ".claim").exists()

    def known_arxiv(self, arxiv_id):
        return self.known_paper(paper_key(arxiv_id))

    # -- imports ----------------------------------------------------------------------
    def import_text(self, title, text):
        """Queue a text for the next Reader stage; its import id."""
        try:
            item = imports.record(title, text)
        except imports.ImportRefused as error:
            raise LibraryError(imports.IMPORT_INVALID, error.detail) from None
        write_once(
            self.root / "imports" / "queue" / (item["import_id"] + ".json"),
            canonical(item),
        )
        return item["import_id"]

    def import_item(self, import_id):
        path = self.root / "imports" / "queue" / (import_id + ".json")
        if not imports.is_import_id(import_id) or not path.exists():
            return None
        item = json.loads(path.read_bytes())
        if item.get("import_id") != import_id:
            raise ValueError("an import does not match its id")
        return item

    def import_done(self, import_id):
        return (self.root / "imports" / "cards" / (import_id + ".json")).exists() or (
            self.root / "imports" / "rejections" / (import_id + ".json")
        ).exists()

    def pending_imports(self):
        """Queued imports with neither a card nor a rejection, by id."""
        rows = []
        for path in sorted((self.root / "imports" / "queue").glob("*.json")):
            if self.import_done(path.stem):
                continue
            item = self.import_item(path.stem)
            rows.append(
                {
                    "import_id": item["import_id"],
                    "title": item["title"],
                    "chars": item["chars"],
                    "text_digest": item["text_digest"],
                }
            )
        return rows

    # -- curation -----------------------------------------------------------------------
    def _curation_fold(self):
        pins, bans = set(), set()
        for entry in _lines(self.root / "curation.jsonl"):
            action, cid = entry["action"], entry["card_id"]
            if action == "pin":
                pins.add(cid)
            elif action == "unpin":
                pins.discard(cid)
            elif action == "ban":
                bans.add(cid)
                pins.discard(cid)
            elif action == "unban":
                bans.discard(cid)
        return pins, bans

    def curation(self):
        """`{pins, bans, digest}`: the current curation state."""
        pins, bans = self._curation_fold()
        return curation_state(pins, bans)

    def curation_state(self, value):
        """A recorded curation state by digest."""
        empty = curation_state()
        if value == empty["digest"]:
            return empty
        path = self.root / "curations" / (_hex(value) + ".json")
        if not path.exists():
            raise LibraryError("curation_not_found")
        return checked_curation(json.loads(path.read_bytes()))

    def _exists(self, card_id):
        if type(card_id) is not str:
            return False
        if card_id in self.pack.by_id:
            return True
        return self._private_served(card_id) is not None

    def _curate(self, action, card_id):
        if not self._exists(card_id):
            raise LibraryError(CARD_NOT_FOUND, str(card_id)[:100])
        with self._lock():
            pins, bans = self._curation_fold()
            if action == "pin" and card_id in bans:
                raise LibraryError(CARD_BANNED, card_id)
            unchanged = (
                (action == "pin" and card_id in pins)
                or (action == "unpin" and card_id not in pins)
                or (action == "ban" and card_id in bans)
                or (action == "unban" and card_id not in bans)
            )
            if not unchanged:
                _append(
                    self.root / "curation.jsonl",
                    canonical(
                        {
                            "schema": CURATION_ENTRY_SCHEMA,
                            "action": action,
                            "card_id": card_id,
                            "at": self._now(),
                        }
                    ),
                )
            state = self.curation()
            body = canonical(state)
            path = self.root / "curations" / (_hex(state["digest"]) + ".json")
            if not path.exists():
                write_once(path, body)
        return state["digest"]

    def pin(self, card_id):
        return self._curate("pin", card_id)

    def unpin(self, card_id):
        return self._curate("unpin", card_id)

    def ban(self, card_id):
        """Ban a card: never served again, and unpinned if it was pinned."""
        return self._curate("ban", card_id)

    def unban(self, card_id):
        return self._curate("unban", card_id)

    # -- the miner's own practice outcomes ---------------------------------------------
    def record_outcome(self, card_ids, improved, evidence):
        """Record that a plan citing `card_ids` did (or did not) improve in the
        miner's own practice. Only the miner's permitted practice results may
        be recorded; the ranking reads only whether it improved. Recording the
        same outcome twice records it once."""
        if (
            type(card_ids) is not list
            or not 1 <= len(card_ids) <= MAX_OUTCOME_CARDS
            or any(type(cid) is not str for cid in card_ids)
        ):
            raise LibraryError(EVIDENCE_INVALID, "card_ids is a list of card ids")
        for cid in card_ids:
            if not self._exists(cid):
                raise LibraryError(CARD_NOT_FOUND, cid[:100])
        if type(improved) is not bool:
            raise LibraryError(EVIDENCE_INVALID, "improved is a Boolean")
        try:
            body = canonical(evidence)
        except (TypeError, ValueError):
            raise LibraryError(EVIDENCE_INVALID, "evidence is JSON data") from None
        if type(evidence) is not dict or len(body) > MAX_EVIDENCE_BYTES:
            raise LibraryError(EVIDENCE_INVALID, "evidence is a small JSON object")
        if protected(evidence):
            raise LibraryError(EVIDENCE_INVALID, "evidence names protected material")
        entry = {
            "schema": OUTCOME_SCHEMA,
            "card_ids": sorted(set(card_ids)),
            "improved": improved,
            "evidence_digest": digest(body),
            "evidence": evidence,
        }
        with self._lock():
            path = self.root / "outcomes.jsonl"
            if any(line == entry for line in _lines(path)):
                return
            _append(path, canonical(entry))

    def evidence(self):
        """`{card_id: {improved, not_improved}}` from the miner's outcomes."""
        counts = {}
        for entry in _lines(self.root / "outcomes.jsonl"):
            for cid in entry["card_ids"]:
                row = counts.setdefault(cid, {"improved": 0, "not_improved": 0})
                row["improved" if entry["improved"] else "not_improved"] += 1
        return dict(sorted(counts.items()))

    # -- snapshots of the private layer ----------------------------------------------
    def _snapshot_document(self):
        return {
            "schema": SNAPSHOT_SCHEMA,
            "cards": [
                {
                    "card_id": card["card_id"],
                    "origin": card["origin"],
                    "digest": digest(canonical(card)),
                }
                for card in self.private_cards()
            ],
            "evidence": self.evidence(),
        }

    def snapshot(self):
        """Freeze the private layer (cards and outcome counts); its digest."""
        body = canonical(self._snapshot_document())
        value = digest(body)
        path = self.root / "snapshots" / (_hex(value) + ".json")
        if not path.exists():
            write_once(path, body)
        return value

    def load_snapshot(self, value):
        """`(cards, evidence)` a snapshot froze, each card verified."""
        path = self.root / "snapshots" / (_hex(value) + ".json")
        if not path.exists():
            raise LibraryError("snapshot_not_found")
        body = path.read_bytes()
        if digest(body) != value:
            raise ValueError("a library snapshot does not match its digest")
        document = json.loads(body)
        if document.get("schema") != SNAPSHOT_SCHEMA:
            raise ValueError("not a miner library snapshot")
        cards = []
        for entry in document["cards"]:
            card = self._private_served(entry["card_id"])
            if (
                card is None
                or card["origin"] != entry["origin"]
                or digest(canonical(card)) != entry["digest"]
            ):
                raise ValueError("a snapshot's card no longer matches its digest")
            cards.append(card)
        return cards, document["evidence"]

    # -- plans -----------------------------------------------------------------------
    def save_plan(self, plan):
        """Store a plan write-once; its digest. `plan["created_by"]` is
        `planner` or `miner`; `plan["parent"]` is None or a stored plan's
        digest. The plan's own schema is the driver's to check."""
        if type(plan) is not dict:
            raise LibraryError(PLAN_INVALID, "a plan is an object")
        try:
            body = canonical(plan)
        except (TypeError, ValueError):
            raise LibraryError(PLAN_INVALID, "a plan is JSON data") from None
        if len(body) > MAX_PLAN_BYTES:
            raise LibraryError(PLAN_INVALID, "a plan is at most 256 KiB")
        if plan.get("created_by") not in PLAN_AUTHORS:
            raise LibraryError(PLAN_INVALID, "created_by is planner or miner")
        parent = plan.get("parent")
        if parent is not None:
            if type(parent) is not str or not _DIGEST.fullmatch(parent):
                raise LibraryError(PLAN_INVALID, "parent is a plan digest")
            if not (self.root / "plans" / (_hex(parent) + ".json")).exists():
                raise LibraryError(PLAN_NOT_FOUND, parent)
        if protected(plan):
            raise LibraryError(PLAN_INVALID, "the plan names protected material")
        value = digest(body)
        with self._lock():
            path = self.root / "plans" / (_hex(value) + ".json")
            if not path.exists():
                write_once(path, body)
            index = self.root / "plans.jsonl"
            if not any(entry["digest"] == value for entry in _lines(index)):
                _append(
                    index,
                    canonical(
                        {
                            "schema": PLAN_INDEX_SCHEMA,
                            "digest": value,
                            "created_by": plan["created_by"],
                            "parent": parent,
                            "created_at": self._now(),
                        }
                    ),
                )
        return value

    def plan(self, value):
        """A stored plan by digest, verified."""
        try:
            path = self.root / "plans" / (_hex(value) + ".json")
        except ValueError:
            raise LibraryError(PLAN_NOT_FOUND, str(value)[:100]) from None
        if not path.exists():
            raise LibraryError(PLAN_NOT_FOUND, value)
        body = path.read_bytes()
        if digest(body) != value:
            raise ValueError("a stored plan does not match its digest")
        return json.loads(body)

    def plans(self):
        """`[{digest, created_by, parent, created_at}]`, oldest first."""
        return [
            {
                key: entry[key]
                for key in ("digest", "created_by", "parent", "created_at")
            }
            for entry in _lines(self.root / "plans.jsonl")
        ]

    # -- reading the library now (the Library doors) ----------------------------------
    def _view(self, challenge, curation):
        evidence = self.evidence()
        private = self.private_cards()
        key = (
            self.pack.digest,
            digest(canonical([c["card_id"] for c in private])),
            curation["digest"],
            digest(canonical(evidence)),
            json.dumps(challenge, sort_keys=True),
        )
        view = self._views.get(key)
        if view is None:
            discovery, contract = focus.public_context(challenge)
            view = _Served(
                self.pack,
                private,
                curation=curation,
                evidence=evidence,
                discovery=discovery,
                contract=contract,
            )
            self._views = {key: view}
        return view

    def _curation_for(self, bans, pins):
        current = self.curation()
        if bans is None and pins is None:
            return current
        bans = set(current["bans"]) | set(bans or ())
        pins = (set(current["pins"]) | set(pins or ())) - bans
        return curation_state(pins, bans)

    def search(self, query, *, challenge, limit=10, bans=None, pins=None):
        """Cards matching `query` (all cards, best first, for an empty query),
        ranked for `challenge`: each with its origin, `check_status`, score
        0-3 and reasons. Banned cards are never returned. `bans` and `pins`
        add to the library's own curation."""
        if type(query) is not str or len(query) > 512:
            raise LibraryError(SEARCH_INVALID, "a query is at most 512 characters")
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise LibraryError(SEARCH_INVALID, f"limit is 1-{MAX_SEARCH_LIMIT}")
        view = self._view(challenge, self._curation_for(bans, pins))
        return [
            _row(card, result, full=True)
            for card, result in view.ranked(query.strip(), limit)
        ]

    def card(self, card_id):
        """One served card by id; `card_not_found` or `card_banned`."""
        if type(card_id) is not str:
            raise LibraryError(CARD_NOT_FOUND, "a card id is text")
        if card_id in self.curation()["bans"] and self._exists(card_id):
            raise LibraryError(CARD_BANNED, card_id)
        found = self.pack.by_id.get(card_id)
        served = (
            _served(found, SHARED)
            if found is not None
            else self._private_served(card_id)
        )
        if served is None or protected(served):
            raise LibraryError(CARD_NOT_FOUND, card_id[:100])
        return served

    def list_cards(self, *, origin=None, offset=0, limit=50):
        """`{total, rows}`: every servable card, with its curation flags.
        Banned cards are listed (flagged) so the miner can unban them; their
        content is not."""
        if origin is not None and origin not in ORIGINS:
            raise LibraryError(
                SEARCH_INVALID, "origin is shared, miner_hunt or miner_import"
            )
        if type(offset) is not int or offset < 0:
            raise LibraryError(SEARCH_INVALID, "offset is a count")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise LibraryError(SEARCH_INVALID, "limit is 1-500")
        curation = self.curation()
        pins, bans = set(curation["pins"]), set(curation["bans"])
        pack_cards, _ = _pack_served(self.pack)
        known = self.pack.paper_keys
        rows = []
        for card in [*pack_cards, *self.private_cards()]:
            if origin is not None and card["origin"] != origin:
                continue
            key = card_paper_key(card["card_id"])
            if card["origin"] != SHARED and key is not None and key in known:
                continue
            rows.append(
                {
                    "card_id": card["card_id"],
                    "title": card["title"],
                    "origin": card["origin"],
                    "check_status": card["check_status"],
                    "pinned": card["card_id"] in pins,
                    "banned": card["card_id"] in bans,
                }
            )
        return {"total": len(rows), "rows": rows[offset : offset + limit]}


class MinerLiterature:
    """The literature one miner campaign serves, frozen by digest.

    `pack` is the campaign's frozen `SharedPack`; `private_snapshot_digest` a
    `MinerLibrary.snapshot()` digest (or None for no private layer);
    `curation` a `{pins, bans, digest}` state (or None for none). The
    Challenge's public discovery document and contract default to Carbon's
    own for `challenge`.
    """

    def __init__(
        self,
        pack,
        library,
        *,
        challenge,
        private_snapshot_digest,
        curation,
        discovery=None,
        contract=None,
    ):
        if type(pack) is not SharedPack:
            raise TypeError("exact SharedPack required")
        if library is not None and type(library) is not MinerLibrary:
            raise TypeError("exact MinerLibrary required")
        self.curation = checked_curation(curation)
        if private_snapshot_digest is None:
            private, evidence = [], {}
        else:
            if library is None:
                raise ValueError("a private snapshot needs its library")
            private, evidence = library.load_snapshot(private_snapshot_digest)
        if discovery is None or contract is None:
            found_discovery, found_contract = focus.public_context(challenge)
            discovery = found_discovery if discovery is None else discovery
            contract = found_contract if contract is None else contract
        self.challenge = focus.challenge_id(challenge)
        self.pack_digest = pack.digest
        self.private_snapshot_digest = private_snapshot_digest
        self._view = _Served(
            pack,
            private,
            curation=self.curation,
            evidence=evidence,
            discovery=discovery,
            contract=contract,
        )

    def document(self):
        return {
            "schema": LITERATURE_SCHEMA,
            "challenge": self.challenge,
            "pack_digest": self.pack_digest,
            "private_snapshot_digest": self.private_snapshot_digest,
            "curation_digest": self.curation["digest"],
            "focus_rule": focus.FOCUS_RULE,
            "focus_rule_digest": focus.rule_digest(),
        }

    @property
    def digest(self):
        return digest(canonical(self.document()))

    def record(self):
        """What a campaign record pins about its literature."""
        origins = {name: 0 for name in ORIGINS}
        for card in self._view.cards.values():
            origins[card["origin"]] += 1
        return {
            **self.document(),
            "literature_digest": self.digest,
            "served": len(self._view.cards),
            "served_by_origin": origins,
            "banned": len(self._view.banned),
            "pinned": sorted(c["card_id"] for c in self._view.pinned()),
            "withheld_protected": len(self._view.withheld),
            "shadowed": len(self._view.shadowed),
            "check_status": UNCHECKED,
        }

    # -- what the toolbox serves ---------------------------------------------------
    def status(self, card_id):
        """`served`, `banned` or `unknown`."""
        return self._view.status(card_id)

    def origin(self, card_id):
        card = self._view.cards.get(card_id) or self._view.banned.get(card_id)
        return None if card is None else card["origin"]

    def card(self, card_id):
        card = self._view.cards.get(card_id)
        return None if card is None else dict(card)

    def pinned(self):
        return [
            {"card_id": c["card_id"], "title": c["title"], "origin": c["origin"]}
            for c in self._view.pinned()
        ]

    def top(self, limit=20):
        """The best cards for the Challenge, pins first, as compact rows."""
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise ValueError(f"limit is 1-{MAX_SEARCH_LIMIT}")
        return [
            _row(card, result, full=False)
            for card, result in self._view.ranked("", limit)
        ]

    def _refusal(self, status, code, detail):
        return {
            "status": status,
            "reason_code": code,
            "detail": detail,
            "authority_granted": False,
            "dispatched": False,
        }

    def lit_search(self, arguments):
        query = arguments.get("query") if type(arguments) is dict else None
        if (
            type(arguments) is not dict
            or set(arguments) != {"query"}
            or type(query) is not str
            or not 1 <= len(query.strip()) <= 512
        ):
            return self._refusal(
                "REFUSED_INVALID_REQUEST",
                "literature_request",
                "lit_search takes query (1-512 characters)",
            )
        return {
            "status": "OK",
            "literature_digest": self.digest,
            "results": [
                _row(card, result, full=False)
                for card, result in self._view.ranked(query.strip(), MAX_RESULTS)
            ],
            "unchecked_note": UNCHECKED_NOTE,
            "content_is_data": True,
        }

    def lit_card(self, arguments):
        cid = arguments.get("card_id") if type(arguments) is dict else None
        if (
            type(arguments) is not dict
            or set(arguments) != {"card_id"}
            or (type(cid) is not str)
        ):
            return self._refusal(
                "REFUSED_INVALID_REQUEST",
                "literature_request",
                "lit_card takes card_id",
            )
        status = self._view.status(cid)
        if status == "banned":
            return self._refusal(
                "REFUSED", CARD_BANNED, "the miner banned this card; it is not served"
            )
        if status != "served":
            return {
                "status": "NOT_FOUND",
                "reason_code": CARD_NOT_FOUND,
                "card_id": cid[:100],
            }
        card = self._view.cards[cid]
        result = self._view.assess(card)
        return {
            "status": "OK",
            "literature_digest": self.digest,
            "card": dict(card),
            "check_status": UNCHECKED,
            "assessment": {
                key: result[key]
                for key in (
                    "score",
                    "reasons",
                    "pinned",
                    "plan_input",
                    "capability_request_candidate",
                )
            },
            "unchecked_note": UNCHECKED_NOTE,
            "content_is_data": True,
        }
