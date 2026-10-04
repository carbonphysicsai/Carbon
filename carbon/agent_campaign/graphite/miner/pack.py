"""The Graphite miner edition's shared card pack (OWNER-GRAPHITE-MINER-01 §3).

The pack is the frozen phase-2 literature snapshot (schema
`carbon.graphite.literature-snapshot.v2`, file digest `SOURCE_SNAPSHOT_DIGEST`)
wrapped as `carbon.graphite.miner-card-pack.v1` and shipped in the repository
under `packs/<digest>.json.gz`, with its digest pinned here
(`SHARED_PACK_DIGEST`).

- **What it holds.** Every card the snapshot indexes, in the snapshot's own
  ten method-card fields, except the cards the snapshot withheld because they
  named protected material (`withheld_protected`) and any card the current
  protected-material rule (`tools.protected`) flags at build time. Every card
  is `UNCHECKED`: no person has checked its extraction, and the pack carries
  no person's check.
- **Known papers.** The pack also lists, by id only, the papers phase 2
  already read and found not relevant or withheld. A hunt treats them as
  known, so it never pays to read them again.
- **Digest.** `SHARED_PACK_DIGEST` is the sha256 of the uncompressed canonical
  pack document. The gzip wrapper is deterministic (no file name, mtime 0,
  level 9) so `scripts/dev/graphite_pack.py` rebuilds the same bytes, but the
  loader verifies the document, never the wrapper.
- **Freezing.** `freeze_into` copies the shipped pack write-once into a
  campaign root. A campaign serves its frozen copy (`load_frozen`), so a
  later product update that ships another pack never changes a campaign that
  already froze this one.
- **Fail closed.** A missing, damaged or tampered pack, or a campaign copy that
  differs from its digest, is refused with `literature_pack_missing`; the
  next step is `install --update`.

Rights. Each card's title and abstract are arXiv descriptive metadata, which
arXiv releases under CC0 1.0. The other fields are Carbon's own extraction.
No claim on a card is Carbon's.
"""

from __future__ import annotations

import functools
import gzip
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .. import literature, method_cards
from ..tools import protected

PACK_SCHEMA = "carbon.graphite.miner-card-pack.v1"
#: The phase-2 snapshot the shipped pack wraps (its file's sha256).
SOURCE_SNAPSHOT_DIGEST = (
    "sha256:4adb013dd64a18678ccb44589199b96d40b92944dd57fffb1a1218fe80efebfe"
)
#: The sha256 of the shipped pack's uncompressed canonical document.
SHARED_PACK_DIGEST = (
    "sha256:d517b69672ee06c84c53337dbad57fc1f03cb04c89292c3dedc7a94f98163ec5"
)
PACKS = Path(__file__).resolve().parent / "packs"
#: Where a campaign keeps its frozen copy, under its root.
FROZEN_DIR = "graphite-literature"

#: Where a served card came from.
SHARED = "shared"
MINER_HUNT = "miner_hunt"
MINER_IMPORT = "miner_import"
ORIGINS = (SHARED, MINER_HUNT, MINER_IMPORT)
UNCHECKED = method_cards.UNCHECKED
CARD_FIELDS = literature.CARD_FIELDS

LITERATURE_PACK_MISSING = "literature_pack_missing"
NEXT_STEP = "install --update"
#: The most bytes a pack may decompress to; a larger one is refused.
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024

RIGHTS = {
    "title_and_abstract": (
        "arXiv descriptive metadata, released by arXiv under CC0 1.0"
    ),
    "extracted_fields": (
        "Carbon's own extraction of the paper's claims; every claim is the "
        "paper's own as a model extracted it, not Carbon's"
    ),
}
AUTHORITY = (
    "a literature pack for the Graphite miner edition's read-only tools; every "
    "card is UNCHECKED and no claim on a card is Carbon's"
)

_VERSION = re.compile(r"v[0-9]+\Z")


class PackError(ValueError):
    """The pack cannot be served; nothing was read from it."""

    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code, self.detail = code, detail
        self.next_step = NEXT_STEP if code == LITERATURE_PACK_MISSING else None


def paper_key(arxiv_id):
    """The deduplication key of an arXiv id: lower case, `/` as `-`, no version.

    `2401.12345v2` and `2401.12345v1` are one paper (`2401.12345`), and so are
    `cond-mat/0601001v1` and `cond-mat-0601001`.
    """
    if type(arxiv_id) is not str or not arxiv_id:
        raise ValueError("an arXiv id is text")
    return _VERSION.sub("", arxiv_id.lower().replace("/", "-"))


def card_paper_key(card_id):
    """The deduplication key of an `arxiv-` card id, or None for another id."""
    if type(card_id) is not str or not card_id.startswith("arxiv-"):
        return None
    return paper_key(card_id[len("arxiv-") :])


@dataclass(frozen=True)
class SharedPack:
    """A verified pack: its digest and its cards, sorted by card id.

    The card dicts are shared; serve copies of them, never the dicts.
    """

    digest: str
    cards: tuple
    source: dict = field(default_factory=dict)
    #: Ids of papers phase 2 read and did not index (not relevant or withheld).
    known: tuple = ()

    @functools.cached_property
    def by_id(self):
        return {card["card_id"]: card for card in self.cards}

    @functools.cached_property
    def paper_keys(self):
        """Every paper this pack knows: its cards and the papers it lists as
        read but not indexed."""
        keys = set()
        for card_id in [*self.by_id, *self.known]:
            key = card_paper_key(card_id)
            if key is not None:
                keys.add(key)
        return frozenset(keys)


def compress(document_bytes):
    """The deterministic gzip wrapper: level 9, no file name, mtime 0."""
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", compresslevel=9, fileobj=buffer, mtime=0
    ) as stream:
        stream.write(document_bytes)
    return buffer.getvalue()


def _decompress(body):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body), mode="rb") as stream:
            document = stream.read(MAX_DOCUMENT_BYTES + 1)
    except (OSError, EOFError) as error:
        raise PackError(LITERATURE_PACK_MISSING, "not a gzip pack") from error
    if len(document) > MAX_DOCUMENT_BYTES:
        raise PackError(LITERATURE_PACK_MISSING, "pack too large")
    return document


@dataclass(frozen=True)
class _Index:
    """A snapshot's indexed cards, read without re-indexing them, so a card
    the current protected-material rule flags is withheld, not fatal."""

    cards: tuple


def build_document(snapshot_path, *, expected=SOURCE_SNAPSHOT_DIGEST):
    """`(document_bytes, document)` for the pack wrapping one snapshot file.

    The snapshot is read only. Its file must match its address (the file
    name is its sha256), its index must match its digest, it must be a v2
    snapshot whose every card is `UNCHECKED`, and, unless `expected` is
    None, its address must be `expected`.
    """
    path = Path(snapshot_path)
    try:
        body = path.read_bytes()
    except OSError as error:
        raise PackError("snapshot_invalid", str(error)) from None
    address = digest(body)
    if path.stem != address[len("sha256:") :]:
        raise PackError("snapshot_invalid", "the file does not match its address")
    if expected is not None and address != expected:
        raise PackError("snapshot_invalid", "not the pinned phase-2 snapshot")
    try:
        document = json.loads(body)
        stored = document["index"]
        if document["schema"] != method_cards.SNAPSHOT_SCHEMA:
            raise ValueError("a pack wraps a v2 snapshot")
        if digest(canonical(stored)) != document["index_snapshot_digest"]:
            raise ValueError("the index does not match its digest")
        if stored["schema"] != literature.INDEX_SCHEMA or any(
            type(card) is not dict or tuple(sorted(card)) != tuple(sorted(CARD_FIELDS))
            for card in stored["cards"]
        ):
            raise ValueError("the index holds method cards")
        index = _Index(tuple(stored["cards"]))
        statuses, recorded = method_cards.card_statuses(index, document)
    except (ValueError, KeyError, TypeError) as error:
        raise PackError("snapshot_invalid", str(error)) from None
    if not recorded or any(status != UNCHECKED for status in statuses.values()):
        raise PackError("snapshot_invalid", "every pack card is UNCHECKED")
    withheld = sorted(document["withheld_protected"])
    cards, flagged = [], []
    for card in sorted(index.cards, key=lambda card: card["card_id"]):
        if card["card_id"] in withheld:
            continue
        if protected(card):
            flagged.append(card["card_id"])
            continue
        cards.append({name: card[name] for name in CARD_FIELDS})
    # Read in phase 2 but not served: not relevant, rejected, or withheld.
    known = sorted(set(document["excluded"]) | set(withheld) | set(flagged))
    pack = {
        "schema": PACK_SCHEMA,
        "source": {
            "snapshot_file_digest": address,
            "snapshot_schema": document["schema"],
            "snapshot_label": document["label"],
            "index_snapshot_digest": document["index_snapshot_digest"],
            "query_set_digest": document["query_set_digest"],
            "prompt_digest": document["prompt_digest"],
        },
        "check_status": UNCHECKED,
        "cards": cards,
        "withheld": {
            "withheld_protected": withheld,
            "protected_at_build": sorted(flagged),
        },
        "known_not_indexed": known,
        "rights": RIGHTS,
        "authority": AUTHORITY,
    }
    return canonical(pack), pack


def _verified(document_bytes, expected):
    if digest(document_bytes) != expected:
        raise PackError(LITERATURE_PACK_MISSING, "the pack does not match its digest")
    try:
        document = json.loads(document_bytes)
    except ValueError:
        raise PackError(LITERATURE_PACK_MISSING, "the pack is not JSON") from None
    if type(document) is not dict or document.get("schema") != PACK_SCHEMA:
        raise PackError(LITERATURE_PACK_MISSING, "not a miner card pack")
    if document.get("check_status") != UNCHECKED:
        raise PackError(LITERATURE_PACK_MISSING, "a pack serves UNCHECKED cards")
    cards = document.get("cards")
    withheld = document.get("withheld") or {}
    excluded = set(withheld.get("withheld_protected") or ()) | set(
        withheld.get("protected_at_build") or ()
    )
    if type(cards) is not list or not cards:
        raise PackError(LITERATURE_PACK_MISSING, "a pack holds cards")
    previous = None
    for card in cards:
        if type(card) is not dict or tuple(sorted(card)) != tuple(sorted(CARD_FIELDS)):
            raise PackError(LITERATURE_PACK_MISSING, "a card has the card fields")
        cid = card["card_id"]
        if type(cid) is not str or not literature._CARD_ID.fullmatch(cid):
            raise PackError(LITERATURE_PACK_MISSING, "a card id is an identifier")
        if previous is not None and cid <= previous:
            raise PackError(LITERATURE_PACK_MISSING, "cards are sorted and unique")
        if cid in excluded:
            raise PackError(LITERATURE_PACK_MISSING, "a withheld card is in the pack")
        previous = cid
    known = document.get("known_not_indexed")
    if type(known) is not list or any(type(i) is not str for i in known):
        raise PackError(LITERATURE_PACK_MISSING, "known papers are ids")
    return SharedPack(
        digest=expected,
        cards=tuple(cards),
        source=dict(document["source"]),
        known=tuple(known),
    )


def pack_path(digest_value, directory=PACKS):
    if type(digest_value) is not str or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", digest_value
    ):
        raise PackError(LITERATURE_PACK_MISSING, "a pack digest is sha256")
    return Path(directory) / (digest_value[len("sha256:") :] + ".json.gz")


def load_pack_file(path, expected):
    """The verified `SharedPack` a pack file holds; `literature_pack_missing`
    when it is absent, damaged, tampered or not the expected pack."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PackError(LITERATURE_PACK_MISSING, "the pack file is missing")
    if path.name != pack_path(expected).name:
        raise PackError(LITERATURE_PACK_MISSING, "the pack file is misnamed")
    return _verified(_decompress(path.read_bytes()), expected)


@functools.lru_cache(maxsize=4)
def _cached(path, expected, size, mtime_ns):
    return load_pack_file(Path(path), expected)


def _load_cached(path, expected):
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        raise PackError(LITERATURE_PACK_MISSING, "the pack file is missing") from None
    return _cached(str(path), expected, stat.st_size, stat.st_mtime_ns)


def load_shared_pack():
    """The shipped pack, verified against `SHARED_PACK_DIGEST`."""
    return _load_cached(pack_path(SHARED_PACK_DIGEST), SHARED_PACK_DIGEST)


def frozen_path(campaign_root, digest_value=SHARED_PACK_DIGEST):
    return pack_path(digest_value, Path(campaign_root) / FROZEN_DIR)


def freeze_into(campaign_root):
    """Copy the shipped pack write-once into a campaign root; its digest.

    A copy already there must be the same pack, or the freeze is refused.
    """
    root = Path(campaign_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("a campaign root is an existing absolute directory")
    load_shared_pack()
    source = pack_path(SHARED_PACK_DIGEST)
    target = frozen_path(root)
    target.parent.mkdir(mode=0o700, exist_ok=True)
    if target.exists() or target.is_symlink():
        load_pack_file(target, SHARED_PACK_DIGEST)
        return SHARED_PACK_DIGEST
    write_once(target, source.read_bytes())
    load_pack_file(target, SHARED_PACK_DIGEST)
    return SHARED_PACK_DIGEST


def load_frozen(campaign_root, digest_value=SHARED_PACK_DIGEST):
    """The pack a campaign froze, from its own copy."""
    return _load_cached(frozen_path(campaign_root, digest_value), digest_value)


def write_pack(document_bytes, directory=PACKS):
    """Write a pack write-once under `directory`; `(digest, path)`."""
    value = digest(document_bytes)
    path = pack_path(value, directory)
    Path(directory).mkdir(parents=True, exist_ok=True)
    write_once(path, compress(document_bytes))
    return value, path
