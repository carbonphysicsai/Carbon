"""Graphite's literature fetch: arXiv abstracts for a registered query set.

GRAPHITE-01 phase 2 (plan §4, step 1). The arXiv API is public and free; this
module needs no key and spends nothing.

- **Registered, versioned queries.** `QUERY_SET` is the closed set of searches
  the backfill runs, with a version and a digest. A record is always stored
  with the query it came from. The queries are search terms, not scientific
  claims: they describe what to read, never what is true.
- **Content-addressed storage.** `RawStore` keeps every response page and
  every parsed record under its own sha256, written once. A paper retrieved
  twice is stored once. Each retrieval is journalled with its query, page
  offset, page digest, record digests and retrieval time.
- **Rate limit.** At least `MIN_INTERVAL_S` (3 s, arXiv's published guidance
  for its API) between any two requests from one client, including retries.
- **Hard cap.** A backfill never stores more than its record cap
  (`MAX_RECORDS` at most).
- **Retries.** A rate limit (HTTP 429), a 5xx answer or a network error is
  retried a bounded number of times with growing waits (honouring
  Retry-After). When they run out the fetch stops with a typed
  `FetchFailed` whose status is `FAILED_INFRA`: an infrastructure failure,
  never a literature fact.
- **Resume.** A page already journalled is not fetched again.
- **Injectable.** The client takes an `opener`, `clock` and `sleep`, so tests
  run on fixtures and never touch the network.

Abstract text is data. Nothing here interprets it.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

RECORD_SCHEMA = "carbon.graphite.arxiv-record.v1"
RETRIEVAL_SCHEMA = "carbon.graphite.arxiv-retrieval.v1"
QUERY_SET_SCHEMA = "carbon.graphite.query-set.v1"
API = "https://export.arxiv.org/api/query"
#: arXiv asks API clients for no more than one request every three seconds.
MIN_INTERVAL_S = 3.0
#: The most records one backfill stores, whatever a caller asks for.
MAX_RECORDS = 5000
#: Records per request.
PAGE_SIZE = 100
MAX_RETRIES = 3
BACKOFF_S = 6.0
MAX_BACKOFF_S = 120.0
TIMEOUT_S = 120
#: The longest field accepted from a feed; a longer one is a malformed record.
MAX_FIELD_CHARS = 20000
FAILED_INFRA = "FAILED_INFRA"

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
_ID = re.compile(r"https?://arxiv\.org/abs/([A-Za-z0-9.\-/]+?v\d+)\Z")
_QUERY_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")


class FetchFailed(RuntimeError):
    """A fetch ended without a usable answer: typed, infrastructure only."""

    status = FAILED_INFRA

    def __init__(self, code, *, http_status=None):
        super().__init__(code)
        self.code, self.http_status = code, http_status


class FeedError(ValueError):
    """A response is not a well-formed arXiv Atom feed."""


@dataclass(frozen=True)
class Query:
    query_id: str
    search_query: str
    purpose: str

    def __post_init__(self):
        if type(self.query_id) is not str or not _QUERY_ID.fullmatch(self.query_id):
            raise ValueError("a query id is a lowercase identifier")
        if type(self.search_query) is not str or not 1 <= len(self.search_query) < 512:
            raise ValueError("a search query is 1-511 characters")
        if type(self.purpose) is not str or not self.purpose:
            raise ValueError("a query states its purpose")

    def record(self):
        return {
            "query_id": self.query_id,
            "search_query": self.search_query,
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class QuerySet:
    version: str
    queries: tuple

    def __post_init__(self):
        if type(self.queries) is not tuple or not self.queries:
            raise ValueError("a query set holds a tuple of queries")
        if any(type(query) is not Query for query in self.queries):
            raise TypeError("exact Query required")
        ids = [query.query_id for query in self.queries]
        if len(set(ids)) != len(ids):
            raise ValueError("query ids are unique")

    def document(self):
        return {
            "schema": QUERY_SET_SCHEMA,
            "version": self.version,
            "queries": [query.record() for query in self.queries],
        }

    @property
    def digest(self):
        return digest(canonical(self.document()))


#: The registered query set for the battery development Challenge and
#: neural-operator surrogate construction (GRAPHITE-D11). Changing a query
#: means a new version; records keep the version they came from.
QUERY_SET = QuerySet(
    version="graphite-phase2-queries.v1",
    queries=(
        Query(
            "neural-operator",
            'abs:"neural operator"',
            "operator-learning surrogate construction",
        ),
        Query(
            "fourier-neural-operator",
            'abs:"Fourier neural operator"',
            "spectral operator architectures",
        ),
        Query("deeponet", "abs:DeepONet", "branch-trunk operator architectures"),
        Query(
            "physics-informed-training",
            'abs:"physics-informed" AND abs:operator',
            "physics-informed training of operator surrogates",
        ),
        Query(
            "operator-learning-training",
            'abs:"operator learning" AND abs:training',
            "training strategies for operator learning",
        ),
        Query(
            "battery-surrogate",
            "abs:battery AND abs:surrogate",
            "battery surrogate models",
        ),
        Query(
            "battery-electrochemical-reduced-order",
            'abs:battery AND abs:electrochemical AND abs:"reduced-order"',
            "reduced-order electrochemical battery models",
        ),
        Query(
            "battery-fast-charging-optimization",
            'abs:"fast charging" AND abs:optimization AND abs:battery',
            "fast-charge protocol optimization",
        ),
        Query(
            "surrogate-adversarial-robustness",
            "abs:surrogate AND abs:adversarial AND abs:robustness",
            "adversarial robustness of learned surrogates",
        ),
        Query(
            "neural-surrogate-benchmark",
            'abs:"neural operator" AND abs:benchmark',
            "evaluation and benchmarks for neural surrogates",
        ),
    ),
)


def _text(element, path):
    found = element.find(path)
    if found is None or found.text is None:
        return None
    return " ".join(found.text.split())


def parse_feed(body):
    """The records in one arXiv Atom page, and the feed's total result count.

    Each record is a closed dict: arXiv id (with version), title, abstract,
    authors, categories, primary category, published and updated times, and
    the abstract page link. A malformed entry raises `FeedError`.
    """
    if type(body) is not bytes:
        raise FeedError("a feed is bytes")
    if b"<!DOCTYPE" in body or b"<!ENTITY" in body:
        # The API never sends a document type; refuse entity tricks outright.
        raise FeedError("a feed carries no document type")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        raise FeedError("not XML") from None
    if root.tag != _ATOM + "feed":
        raise FeedError("not an Atom feed")
    total = _text(root, _OPENSEARCH + "totalResults")
    try:
        total = int(total) if total is not None else None
    except ValueError:
        raise FeedError("totalResults is not an integer") from None
    records = []
    for entry in root.findall(_ATOM + "entry"):
        identity = _text(entry, _ATOM + "id")
        match = _ID.fullmatch(identity or "")
        if match is None:
            if (_text(entry, _ATOM + "title") or "").lower() == "error":
                raise FeedError("the API returned an error entry")
            raise FeedError("an entry has no versioned arXiv id")
        title = _text(entry, _ATOM + "title")
        abstract = _text(entry, _ATOM + "summary")
        if not title or not abstract:
            raise FeedError("an entry has no title or abstract")
        authors = [
            name
            for name in (
                _text(author, _ATOM + "name")
                for author in entry.findall(_ATOM + "author")
            )
            if name
        ]
        categories = sorted(
            {
                category.get("term")
                for category in entry.findall(_ATOM + "category")
                if category.get("term")
            }
        )
        primary = entry.find(_ARXIV + "primary_category")
        record = {
            "schema": RECORD_SCHEMA,
            "arxiv_id": match.group(1),
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "categories": categories,
            "primary_category": None if primary is None else primary.get("term"),
            "published": _text(entry, _ATOM + "published"),
            "updated": _text(entry, _ATOM + "updated"),
            "link": "https://arxiv.org/abs/" + match.group(1),
        }
        if any(
            type(value) is str and len(value) > MAX_FIELD_CHARS
            for value in record.values()
        ):
            raise FeedError("an entry field is too long")
        records.append(record)
    return records, total


def record_digest(record):
    """The content address of a parsed record."""
    return digest(canonical(record))


class ArxivClient:
    """One polite arXiv API client: a minimum interval, bounded retries."""

    def __init__(
        self,
        *,
        opener=None,
        clock=time.monotonic,
        sleep=time.sleep,
        min_interval=MIN_INTERVAL_S,
        max_retries=MAX_RETRIES,
    ):
        if type(min_interval) not in (int, float) or min_interval < MIN_INTERVAL_S:
            raise ValueError("arXiv asks for at least 3 s between requests")
        if type(max_retries) is not int or not 0 <= max_retries <= 10:
            raise ValueError("max_retries is 0-10")
        self.opener = opener or urllib.request.urlopen
        self.clock, self.sleep = clock, sleep
        self.min_interval, self.max_retries = float(min_interval), max_retries
        self._last = None
        self.requests = 0

    def _wait(self, at_least=0.0):
        if self._last is not None:
            gap = max(self.min_interval, at_least) - (self.clock() - self._last)
            if gap > 0:
                self.sleep(gap)
        elif at_least > 0:
            self.sleep(at_least)

    @staticmethod
    def url(search_query, start, max_results):
        return (
            API
            + "?"
            + urllib.parse.urlencode(
                {
                    "search_query": search_query,
                    "start": start,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
            )
        )

    def get(self, url):
        """The body at `url`, with the rate limit and bounded retries."""
        backoff = 0.0
        last_status = None
        for attempt in range(self.max_retries + 1):
            self._wait(backoff)
            self._last = self.clock()
            self.requests += 1
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "carbon-graphite-literature/1"}
                )
                with self.opener(request, timeout=TIMEOUT_S) as response:
                    status = getattr(response, "status", 200)
                    body = response.read()
                if status == 200:
                    return body
                last_status = status
                retry_after = None
            except urllib.error.HTTPError as error:
                last_status = error.code
                if error.code != 429 and error.code < 500:
                    raise FetchFailed("http_rejected", http_status=error.code) from None
                retry_after = _retry_after(error.headers)
            except (urllib.error.URLError, TimeoutError, OSError):
                last_status = None
                retry_after = None
            if attempt == self.max_retries:
                break
            backoff = min(
                MAX_BACKOFF_S,
                (retry_after if retry_after is not None else BACKOFF_S * 2**attempt),
            )
        raise FetchFailed("retries_exhausted", http_status=last_status)

    def page(self, query, start, max_results=PAGE_SIZE):
        if type(query) is not Query:
            raise TypeError("exact Query required")
        return self.get(self.url(query.search_query, start, max_results))


def _retry_after(headers):
    value = None if headers is None else headers.get("Retry-After")
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if 0 <= seconds <= MAX_BACKOFF_S else None


def _append(path, payload):
    with path.open("ab") as stream:
        stream.write(payload + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


class RawStore:
    """Content-addressed raw pages and records, plus a retrieval journal."""

    def __init__(self, root):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("the literature store root is private and absolute")
        for name in ("pages", "records"):
            (root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root
        self.journal = root / "retrievals.jsonl"

    def put_page(self, body):
        page = digest(body)
        path = self.root / "pages" / (page[7:] + ".xml")
        if not path.exists():
            write_once(path, body)
        return page

    def put_record(self, record):
        address = record_digest(record)
        path = self.root / "records" / (address[7:] + ".json")
        if not path.exists():
            write_once(path, canonical(record))
        return address

    def record(self, address):
        path = self.root / "records" / (address.removeprefix("sha256:") + ".json")
        body = path.read_bytes()
        if digest(body) != address:
            raise ValueError("a stored record changed")
        return json.loads(body)

    def retrievals(self):
        if not self.journal.exists():
            return []
        return [json.loads(line) for line in self.journal.read_bytes().splitlines()]

    def journal_retrieval(self, entry):
        _append(self.journal, canonical(entry))

    def addresses(self):
        """Every record address, in first-retrieval order, without repeats."""
        seen = []
        for entry in self.retrievals():
            for address in entry["record_digests"]:
                if address not in seen:
                    seen.append(address)
        return seen


def _now_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def backfill(
    client,
    store,
    *,
    query_set=QUERY_SET,
    max_records=MAX_RECORDS,
    page_size=PAGE_SIZE,
    pages_per_query=None,
    now=_now_utc,
):
    """Fetch pages of every query until the record cap; resumable.

    Returns a summary. A page already journalled for this query set is not
    fetched again. A `FetchFailed` propagates after the pages before it are
    stored and journalled, so a later call resumes after them.
    """
    if type(query_set) is not QuerySet:
        raise TypeError("exact QuerySet required")
    if type(max_records) is not int or not 1 <= max_records <= MAX_RECORDS:
        raise ValueError(f"max_records is 1-{MAX_RECORDS}")
    if type(page_size) is not int or not 1 <= page_size <= 2000:
        raise ValueError("page_size is 1-2000")
    done = {
        (entry["query_set_digest"], entry["query_id"], entry["start"]): entry
        for entry in store.retrievals()
    }
    stored = store.addresses()
    fetched = 0
    for query in query_set.queries:
        start, pages = 0, 0
        while len(stored) < max_records:
            if pages_per_query is not None and pages >= pages_per_query:
                break
            key = (query_set.digest, query.query_id, start)
            if key in done:
                entry = done[key]
            else:
                body = client.page(query, start, page_size)
                fetched += 1
                try:
                    records, total = parse_feed(body)
                except FeedError as error:
                    raise FetchFailed("malformed_feed: " + str(error)) from None
                page = store.put_page(body)
                room = max_records - len(stored)
                addresses = []
                for record in records:
                    address = record_digest(record)
                    if address in addresses:
                        continue
                    if address not in stored:
                        if room <= 0:
                            continue  # past the cap: not stored, not journalled
                        room -= 1
                    store.put_record(record)
                    addresses.append(address)
                entry = {
                    "schema": RETRIEVAL_SCHEMA,
                    "query_set_version": query_set.version,
                    "query_set_digest": query_set.digest,
                    "query_id": query.query_id,
                    "search_query": query.search_query,
                    "start": start,
                    "page_size": page_size,
                    "page_digest": page,
                    "total_results": total,
                    "returned": len(records),
                    "record_digests": addresses,
                    "retrieved_at": now(),
                }
                store.journal_retrieval(entry)
                done[key] = entry
            for address in entry["record_digests"]:
                if address not in stored:
                    stored.append(address)
            pages += 1
            start += page_size
            if entry["returned"] < page_size or (
                entry["total_results"] is not None and start >= entry["total_results"]
            ):
                break
        if len(stored) >= max_records:
            break
    return {
        "query_set": query_set.version,
        "query_set_digest": query_set.digest,
        "records": len(stored),
        "pages_fetched": fetched,
        "requests": client.requests,
        "capped": len(stored) >= max_records,
    }
