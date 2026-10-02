"""GRAPHITE-01 phase 2: the arXiv fetch, on fixtures (no network).

Parsing, the 3 s rate limit, bounded retries with typed infrastructure
failures, content-addressed storage, the hard record cap and resume.
"""

from __future__ import annotations

import json
import urllib.error

import pytest
from graphite_phase2_fixtures import client, entry, feed, one_query

from carbon.agent_campaign.graphite import literature_fetch as lf
from carbon.development_session.profile import canonical, digest

NOW = "2026-10-02T00:00:00Z"


def test_the_query_set_is_registered_versioned_and_digested():
    document = lf.QUERY_SET.document()
    assert document["version"] == "graphite-phase2-queries.v1"
    assert lf.QUERY_SET.digest == digest(canonical(document))
    ids = [q["query_id"] for q in document["queries"]]
    assert len(ids) == len(set(ids)) >= 8
    with pytest.raises(ValueError):
        lf.QuerySet(version="x", queries=(lf.QUERY_SET.queries[0],) * 2)


def test_a_feed_parses_into_closed_records():
    body = feed(
        entry(1, title="Synthetic\n   title", categories=("cs.LG", "physics.comp-ph"))
    )
    records, total = lf.parse_feed(body)
    assert total == 1
    (record,) = records
    assert record["arxiv_id"] == "2610.00001v1"
    assert record["title"] == "Synthetic title"
    assert record["abstract"].startswith("A synthetic abstract 1 about")
    assert "\n" not in record["abstract"]
    assert record["categories"] == ["cs.LG", "physics.comp-ph"]
    assert record["primary_category"] == "cs.LG"
    assert record["link"] == "https://arxiv.org/abs/2610.00001v1"
    assert record["authors"] == ["Synthetic Author"]
    assert set(record) == {
        "schema",
        "arxiv_id",
        "title",
        "abstract",
        "authors",
        "categories",
        "primary_category",
        "published",
        "updated",
        "link",
    }


@pytest.mark.parametrize(
    "body",
    [
        b"not xml",
        b"<root/>",
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><feed/>',
        feed(entry(1).replace("http://arxiv.org/abs/2610.00001v1", "nonsense")),
        feed(entry(1).replace("<title>Synthetic operator paper 1</title>", "")),
    ],
)
def test_a_malformed_feed_is_refused(body):
    with pytest.raises(lf.FeedError):
        lf.parse_feed(body)


def test_requests_are_at_least_three_seconds_apart():
    fetcher, opener = client([feed(entry(1)), feed(entry(2)), feed(entry(3))])
    query = one_query().queries[0]
    for start in (0, 1, 2):
        fetcher.page(query, start, 1)
    gaps = [b - a for a, b in zip(opener.times, opener.times[1:])]
    assert gaps and all(gap >= lf.MIN_INTERVAL_S for gap in gaps)
    with pytest.raises(ValueError, match="3 s"):
        lf.ArxivClient(min_interval=1.0)


def test_a_rate_limit_is_retried_after_its_retry_after():
    fetcher, opener = client([(429, 10), (503, None), feed(entry(1))])
    body = fetcher.page(one_query().queries[0], 0, 1)
    assert lf.parse_feed(body)[0][0]["arxiv_id"] == "2610.00001v1"
    assert len(opener.urls) == 3
    assert opener.times[1] - opener.times[0] >= 10
    assert opener.times[2] - opener.times[1] >= lf.MIN_INTERVAL_S


def test_exhausted_retries_are_a_typed_infrastructure_failure():
    fetcher, opener = client([(503, None)] * (lf.MAX_RETRIES + 1))
    with pytest.raises(lf.FetchFailed) as raised:
        fetcher.page(one_query().queries[0], 0, 1)
    assert raised.value.status == "FAILED_INFRA"
    assert raised.value.code == "retries_exhausted"
    assert len(opener.urls) == lf.MAX_RETRIES + 1
    fetcher, opener = client([urllib.error.URLError("down")] * (lf.MAX_RETRIES + 1))
    with pytest.raises(lf.FetchFailed):
        fetcher.page(one_query().queries[0], 0, 1)


def test_a_client_error_is_not_retried():
    fetcher, opener = client([(400, None), feed(entry(1))])
    with pytest.raises(lf.FetchFailed) as raised:
        fetcher.page(one_query().queries[0], 0, 1)
    assert raised.value.code == "http_rejected"
    assert raised.value.http_status == 400
    assert len(opener.urls) == 1


def test_records_are_content_addressed_and_journalled_with_their_query(tmp_path):
    store = lf.RawStore(tmp_path / "raw")
    queries = lf.QuerySet(
        version="t.v1",
        queries=(lf.Query("first", "abs:a", "t"), lf.Query("second", "abs:b", "t")),
    )
    fetcher, _ = client([feed(entry(1), entry(2)), feed(entry(2), entry(3))])
    summary = lf.backfill(
        fetcher, store, query_set=queries, page_size=5, now=lambda: NOW
    )
    assert summary["records"] == 3
    addresses = store.addresses()
    assert len(addresses) == 3
    for address in addresses:
        path = tmp_path / "raw" / "records" / (address[7:] + ".json")
        assert digest(path.read_bytes()) == address
        assert store.record(address)["schema"] == lf.RECORD_SCHEMA
    # Paper 2 came from both queries and is stored once.
    assert len(list((tmp_path / "raw" / "records").iterdir())) == 3
    journal = store.retrievals()
    assert [e["query_id"] for e in journal] == ["first", "second"]
    assert all(e["retrieved_at"] == NOW for e in journal)
    assert journal[1]["record_digests"][0] in journal[0]["record_digests"]
    for e in journal:
        page = tmp_path / "raw" / "pages" / (e["page_digest"][7:] + ".xml")
        assert digest(page.read_bytes()) == e["page_digest"]
        assert e["query_set_digest"] == queries.digest


def test_the_record_cap_is_hard(tmp_path):
    store = lf.RawStore(tmp_path / "raw")
    fetcher, opener = client([feed(*(entry(n) for n in range(1, 6)), total=50)])
    summary = lf.backfill(
        fetcher, store, query_set=one_query(), max_records=3, page_size=5
    )
    assert summary["capped"] is True
    assert summary["records"] == 3
    assert len(store.addresses()) == 3
    assert len(list((tmp_path / "raw" / "records").iterdir())) == 3
    assert len(opener.urls) == 1
    with pytest.raises(ValueError):
        lf.backfill(fetcher, store, max_records=lf.MAX_RECORDS + 1)


def test_a_backfill_resumes_without_refetching(tmp_path):
    store = lf.RawStore(tmp_path / "raw")
    pages = [feed(entry(1), entry(2), total=6), (503, None)]
    fetcher, _ = client(pages + [(503, None)] * lf.MAX_RETRIES)
    with pytest.raises(lf.FetchFailed):
        lf.backfill(fetcher, store, query_set=one_query(), page_size=2)
    assert len(store.addresses()) == 2
    fetcher, opener = client([feed(entry(3), entry(4), total=6), feed(entry(5))])
    summary = lf.backfill(fetcher, store, query_set=one_query(), page_size=2)
    assert summary["records"] == 5
    assert summary["pages_fetched"] == 2
    assert "start=0" not in opener.urls[0] and "start=2" in opener.urls[0]
    # Nothing left to fetch.
    fetcher, opener = client([])
    lf.backfill(fetcher, store, query_set=one_query(), page_size=2)
    assert opener.urls == []


def test_a_malformed_page_is_a_typed_infrastructure_failure(tmp_path):
    store = lf.RawStore(tmp_path / "raw")
    fetcher, _ = client([b"<html>busy</html>"])
    with pytest.raises(lf.FetchFailed) as raised:
        lf.backfill(fetcher, store, query_set=one_query())
    assert raised.value.status == "FAILED_INFRA"
    assert raised.value.code.startswith("malformed_feed")
    assert store.retrievals() == []


def test_a_retrieval_journal_line_is_canonical_json(tmp_path):
    store = lf.RawStore(tmp_path / "raw")
    fetcher, _ = client([feed(entry(1))])
    lf.backfill(fetcher, store, query_set=one_query(), page_size=5, now=lambda: NOW)
    line = store.journal.read_bytes().splitlines()[0]
    assert canonical(json.loads(line)) == line
    assert oct(store.journal.stat().st_mode & 0o777) == "0o600"
