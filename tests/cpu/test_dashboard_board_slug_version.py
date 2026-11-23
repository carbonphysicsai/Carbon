"""A board's slug carries the Challenge version (Lead audit #3): two live versions of one Challenge (Motor 1.8 and 1.9)
are two boards, never `duplicate_board`; the version-less slug stays an alias of the newest version, so links made
before still open a board (the Worker, the static build and the page agree).
"""

from __future__ import annotations

import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_dashboard_worker import _fixture, _production, _public, _site, _worker

from carbon.dashboard import build, feed

MOTOR = "electric-motor-magnetics"


def test_the_slug_carries_the_version_and_the_bare_slug_names_the_newest():
    assert feed.board_slug(MOTOR, "no-class", "1.9") == f"{MOTOR}-1.9--no-class"
    assert feed.board_slug(MOTOR, "no-class") == f"{MOTOR}--no-class"
    boards = [
        {
            "challenge": {"id": MOTOR, "version": v},
            "device_class": None,
            "slug": feed.board_slug(MOTOR, "no-class", v),
        }
        for v in ("1.8", "1.10", "1.9")
    ]
    assert feed.alias_slugs(boards) == {f"{MOTOR}--no-class": f"{MOTOR}-1.10--no-class"}
    assert feed.version_order("1.10") > feed.version_order("1.9")


def _two_versions(key):
    older = _fixture()
    older["challenge"] = {**older["challenge"], "version": "1.8"}
    newer = _fixture()
    newer["challenge"] = {**newer["challenge"], "version": "1.9"}
    return _production(older, key), _production(newer, key)


def test_the_static_build_writes_one_board_per_version(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    documents = _two_versions(key)
    index = build.build(tmp_path / "site", list(documents), trust)
    entries = [e for e in index["boards"] if e["state"] == "ACCEPTED"]
    assert sorted(e["challenge"]["version"] for e in entries) == ["1.8", "1.9"]
    for entry in entries:
        assert entry["slug"].endswith(
            f"-{entry['challenge']['version']}--gpu-fixture-gpu"
        )
        assert (tmp_path / "site" / "data" / "v2" / f"{entry['slug']}.json").is_file()


def test_the_worker_serves_both_versions_and_the_bare_slug_opens_the_newest(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    older, newer = _two_versions(key)
    site = _site(tmp_path, [older, newer], trust)
    challenge = older["challenge"]["id"]
    urls = [
        f"https://door18.example/carbon/v1/feed/{challenge}",
        f"https://door19.example/carbon/v1/feed/{challenge}",
    ]
    env = {"FEED_URLS": ",".join(urls), "FEED_KEYS": _public(key), "CACHE_SECONDS": "0"}
    feeds = {urls[0]: json.dumps(older), urls[1]: json.dumps(newer)}
    slug18, slug19 = (feed.project(d, trust)["slug"] for d in (older, newer))
    bare = feed.board_slug(
        challenge, feed.project(older, trust)["device_class"] or "no-class"
    )
    assert len({slug18, slug19, bare}) == 3
    requests = [
        "/data/index.json",
        f"/data/v2/{slug18}.json",
        f"/data/v2/{slug19}.json",
        f"/data/v2/{bare}.json",
        f"/data/boards/{bare}.json",
        f"/data/queue/{slug18}.json",
        f"/data/queue/{bare}.json",
        "/data/queue/nobody.json",
    ]
    got = {r["path"]: r for r in _worker(tmp_path, site, env, feeds, requests)}
    index = json.loads(got["/data/index.json"]["body"])
    assert sorted((e["state"], e["slug"]) for e in index["boards"]) == [
        ("ACCEPTED", slug18),
        ("ACCEPTED", slug19),
    ]
    for slug, version in ((slug18, "1.8"), (slug19, "1.9"), (bare, "1.9")):
        page = got[f"/data/v2/{slug}.json"]
        assert page["status"] == 200, slug
        assert json.loads(page["body"])["challenge"]["version"] == version
    assert json.loads(got[f"/data/boards/{bare}.json"]["body"])["slug"] == slug19
    assert got[f"/data/queue/{slug18}.json"]["status"] == 200
    assert got[f"/data/queue/{bare}.json"]["status"] == 200
    assert got["/data/queue/nobody.json"]["status"] == 404
