"""The cold capabilities read (22-31 s against a 20 s deadline): what is computed once per process, and that none of it
is ever stale. Every cache here is kept under the inputs it read, so a changed input is read again.
"""

import hashlib
import json
import os
import threading
import time

import pytest

from carbon.backbone_catalog import listing, served
from carbon.development_session import library_bundles as bundles
from carbon.level4 import allowlist
from scripts.dev.miner_launchpad import capabilities

# ---- listing.load ---------------------------------------------------------------------------------------


def test_the_manifest_is_parsed_once_and_served_again_until_the_file_changes(
    tmp_path, monkeypatch
):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": listing.SCHEMA, "entries": []}))
    monkeypatch.setattr(listing, "MANIFEST", path)
    parses = []
    real = listing._json
    monkeypatch.setattr(listing, "_json", lambda p: parses.append(1) or real(p))
    first = listing.load()
    assert listing.load() is first and len(parses) == 1, "served again, not re-parsed"
    path.write_text(
        json.dumps({"schema": listing.SCHEMA, "entries": [{"catalog_id": "x"}]})
    )
    changed = listing.load()
    assert changed is not first and changed["entries"] == [{"catalog_id": "x"}]
    assert len(parses) == 2, "a rewritten file is read again"


def test_a_rewrite_that_restores_the_old_mtime_is_still_seen(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": listing.SCHEMA, "entries": []}))
    monkeypatch.setattr(listing, "MANIFEST", path)
    before = os.stat(path)
    first = listing.load()
    path.write_text(json.dumps({"schema": listing.SCHEMA, "entries": [1, 2]}))
    os.utime(
        path, ns=(before.st_atime_ns, before.st_mtime_ns)
    )  # a writer hiding its edit
    # Same size would hide it from a size+mtime seal; the ctime moved, so it is seen.
    assert listing.load() is not first
    assert listing.load()["entries"] == [1, 2]


def test_a_broken_manifest_is_still_refused_and_never_kept(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": "wrong", "entries": []}))
    monkeypatch.setattr(listing, "MANIFEST", path)
    for _ in range(2):
        with pytest.raises(listing.CatalogBroken):
            listing.load()


# ---- served.digest --------------------------------------------------------------------------------------

CHALLENGE, VERSION = "f08-ribbed-bracket", "1.7"


def _fresh_digest(challenge_id, version):
    return (
        "sha256:"
        + hashlib.sha256(
            served._canonical(served.document(challenge_id, version))
        ).hexdigest()
    )


def test_the_served_digest_equals_a_fresh_computation_and_is_kept():
    first = served.digest(CHALLENGE, VERSION)
    assert first == _fresh_digest(CHALLENGE, VERSION)
    assert served.digest(CHALLENGE, VERSION) == first
    kept = served._DIGESTS[(CHALLENGE, VERSION)]
    assert kept[1] == first


def test_the_served_digest_follows_the_entries_a_version_offers(monkeypatch):
    before = served.digest(CHALLENGE, VERSION)
    manifest = listing.load()
    fewer = {**manifest, "entries": manifest["entries"][:-1]}
    monkeypatch.setattr(listing, "load", lambda: fewer)
    # What a version offers changed (other entry objects): the digest is computed again, never the old one.
    assert served.digest(CHALLENGE, VERSION) == _fresh_digest(CHALLENGE, VERSION)
    monkeypatch.undo()
    assert served.digest(CHALLENGE, VERSION) == before


# ---- allowlist.v8_bytes ---------------------------------------------------------------------------------


def test_v8_bytes_are_hashed_once_per_file_state_and_checked_again_on_change(
    tmp_path, monkeypatch
):
    path = tmp_path / "allowlist_v8.json"
    path.write_bytes(b'{"a":1}')
    monkeypatch.setattr(allowlist, "V8_PATH", path)
    monkeypatch.setattr(allowlist, "V8_SHA256", hashlib.sha256(b'{"a":1}').hexdigest())
    monkeypatch.setattr(allowlist, "_V8_CHECKED", {})
    assert allowlist.v8_bytes() == b'{"a":1}'
    hashed = []
    real = hashlib.sha256
    monkeypatch.setattr(
        allowlist.hashlib, "sha256", lambda raw=b"": hashed.append(1) or real(raw)
    )
    assert allowlist.v8_bytes() == b'{"a":1}' and hashed == [], "not hashed again"
    path.write_bytes(b'{"a":2}')  # same size, different bytes
    with pytest.raises(ValueError, match="allowlist v8 bytes differ"):
        allowlist.v8_bytes()


def test_a_changed_pin_is_checked_again(tmp_path, monkeypatch):
    path = tmp_path / "allowlist_v8.json"
    path.write_bytes(b"x")
    monkeypatch.setattr(allowlist, "V8_PATH", path)
    monkeypatch.setattr(allowlist, "_V8_CHECKED", {})
    monkeypatch.setattr(allowlist, "V8_SHA256", hashlib.sha256(b"x").hexdigest())
    assert allowlist.v8_bytes() == b"x"
    monkeypatch.setattr(allowlist, "V8_SHA256", "0" * 64)
    with pytest.raises(ValueError):
        allowlist.v8_bytes()


# ---- library_bundles._context_digest -------------------------------------------------------------------


def _context(tmp_path):
    root = tmp_path / "context"
    (root / "wheels").mkdir(parents=True)
    (root / "bundle.json").write_text(json.dumps({"wheels": {"w.whl": "sha256:x"}}))
    for name in (
        "source.tar.gz",
        "requirements.txt",
        "LICENSE",
        "Dockerfile",
        "install-source.py",
        "wheels/w.whl",
    ):
        (root / name).write_bytes(name.encode())
    return root


def test_the_context_seal_is_computed_once_per_state_of_the_tree(tmp_path, monkeypatch):
    root = _context(tmp_path)
    monkeypatch.setattr(bundles, "_CONTEXT_SEALS", {})
    calls = []
    real = bundles._context_digest_uncached
    monkeypatch.setattr(
        bundles, "_context_digest_uncached", lambda c: calls.append(1) or real(c)
    )
    first = bundles._context_digest(root)
    assert bundles._context_digest(root) == first and len(calls) == 1
    assert first == real(root), "the kept seal is the real one"


def test_a_rewritten_file_changes_the_seal_even_at_the_same_size(tmp_path, monkeypatch):
    root = _context(tmp_path)
    monkeypatch.setattr(bundles, "_CONTEXT_SEALS", {})
    first = bundles._context_digest(root)
    wheel = root / "wheels" / "w.whl"
    before = os.stat(wheel)
    wheel.write_bytes(b"X" * len(wheel.read_bytes()))
    os.utime(wheel, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert bundles._context_digest(root) != first


def test_an_added_or_removed_file_is_seen_and_a_link_is_refused(tmp_path, monkeypatch):
    root = _context(tmp_path)
    monkeypatch.setattr(bundles, "_CONTEXT_SEALS", {})
    bundles._context_digest(root)
    (root / "extra.txt").write_bytes(b"x")
    with pytest.raises(ValueError, match="bundle context file differs"):
        bundles._context_digest(root)
    (root / "extra.txt").unlink()
    bundles._context_digest(root)
    if hasattr(os, "symlink"):
        try:
            os.symlink(root / "LICENSE", root / "link")
        except OSError:
            return
        with pytest.raises(ValueError, match="link refused"):
            bundles._context_digest(root)


# ---- capabilities.control_center: one build at a time ---------------------------------------------------


class _Runner:
    pass


def test_two_reads_at_once_share_one_build(monkeypatch):
    runner = _Runner()
    started = threading.Event()
    release = threading.Event()
    builds = []

    def slow(r):
        builds.append(r)
        started.set()
        release.wait(5)
        return {"built": len(builds)}

    monkeypatch.setattr(capabilities, "_control_center", slow)
    results = []

    def read():
        results.append(capabilities.control_center(runner))

    first = threading.Thread(target=read)
    first.start()
    assert started.wait(5)
    second = threading.Thread(target=read)
    second.start()
    time.sleep(0.2)
    release.set()
    first.join(5)
    second.join(5)
    assert len(builds) == 1, "the second read joined the first build"
    assert results == [{"built": 1}, {"built": 1}]


def test_a_read_after_the_build_builds_again(monkeypatch):
    runner = _Runner()
    count = []
    monkeypatch.setattr(
        capabilities, "_control_center", lambda r: count.append(1) or {"n": len(count)}
    )
    assert capabilities.control_center(runner) == {"n": 1}
    assert capabilities.control_center(runner) == {"n": 2}, "nothing is served stale"


def test_a_failed_build_is_its_readers_to_report_and_a_joiner_builds_for_itself(
    monkeypatch,
):
    runner = _Runner()
    started = threading.Event()
    release = threading.Event()
    calls = []

    def build(r):
        calls.append(threading.current_thread().name)
        if len(calls) == 1:
            started.set()
            release.wait(5)
            raise RuntimeError("the leader's build failed")
        return {"ok": True}

    monkeypatch.setattr(capabilities, "_control_center", build)
    outcome = {}

    def leader():
        try:
            capabilities.control_center(runner)
        except RuntimeError as failure:
            outcome["leader"] = str(failure)

    def joiner():
        outcome["joiner"] = capabilities.control_center(runner)

    first = threading.Thread(target=leader, name="leader")
    first.start()
    assert started.wait(5)
    second = threading.Thread(target=joiner, name="joiner")
    second.start()
    time.sleep(0.2)
    release.set()
    first.join(5)
    second.join(5)
    assert outcome["leader"] == "the leader's build failed"
    assert outcome["joiner"] == {"ok": True}
    assert len(calls) == 2


def test_different_controllers_do_not_share_a_build(monkeypatch):
    seen = []
    monkeypatch.setattr(
        capabilities, "_control_center", lambda r: seen.append(r) or {"r": id(r)}
    )
    a, b = _Runner(), _Runner()
    assert capabilities.control_center(a) != capabilities.control_center(b)
    assert seen == [a, b]


# ---- the per-build memo and the owner commands ---------------------------------------------------------


def test_build_memo_keeps_work_for_one_build_only_and_hands_out_copies():
    from carbon.challenge_registry import build_memo

    calls = []

    def compute():
        calls.append(1)
        return {"kit": [1, 2]}

    assert build_memo.once("k", compute) == {"kit": [1, 2]} and len(calls) == 1
    assert (
        build_memo.once("k", compute) and len(calls) == 2
    ), "nothing is kept outside a build"
    with build_memo.scope():
        first = build_memo.once("k", compute)
        first["kit"].append(3)  # a caller changing its copy
        second = build_memo.once("k", compute)
        assert (
            second == {"kit": [1, 2]} and len(calls) == 3
        ), "one compute, an untouched copy each time"
        with build_memo.scope():  # nested: the outer build's memo stands
            assert build_memo.once("k", compute) == {"kit": [1, 2]} and len(calls) == 3
    build_memo.once("k", compute)
    assert len(calls) == 4, "forgotten when the build ends"


def test_a_catalog_recipe_builds_its_kit_once_per_version_inside_a_build(monkeypatch):
    from carbon.challenge_kit import physical_public

    from carbon.challenge_registry import build_memo, motor

    real = physical_public.construction_kit
    calls = []
    monkeypatch.setattr(
        physical_public,
        "construction_kit",
        lambda *a, **k: calls.append(a) or real(*a, **k),
    )
    entries = listing.entries(motor_challenge := "electric-motor-magnetics", "1.5")[:5]
    assert len(entries) == 5
    with build_memo.scope():
        recipes = [motor.catalog_recipe(e["catalog_id"], "1.5") for e in entries]
    assert len(calls) == 1, "five recipes, one kit"
    assert all(r["challenge"] == recipes[0]["challenge"] for r in recipes)
    assert (
        recipes[0]["challenge"] is not recipes[1]["challenge"]
    ), "each recipe has its own copy"
    calls.clear()
    for e in entries:
        motor.catalog_recipe(e["catalog_id"], "1.5")
    assert len(calls) == 5, "outside a build the kit is built every time, as before"
    assert motor_challenge


def test_the_capability_build_runs_inside_one_memo_scope(monkeypatch):
    from carbon.challenge_registry import build_memo

    inside = []
    monkeypatch.setattr(
        capabilities,
        "_control_center",
        lambda r: inside.append(build_memo._MEMO.get() is not None) or {},
    )
    capabilities.control_center(_Runner())
    assert inside == [True]
    assert build_memo._MEMO.get() is None, "and it ends with the build"


def test_the_owner_commands_edit_a_private_copy_never_the_shared_manifest():
    import pathlib

    from carbon.backbone_catalog import pipeline

    shared = listing.load()
    private = listing.load_fresh()
    assert private is not shared and private == shared
    private["entries"].append({"catalog_id": "scratch"})
    assert listing.load() is shared and "scratch" not in [
        e["catalog_id"] for e in shared["entries"]
    ]
    source = pathlib.Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "manifest = load()" not in source, "add and add_twin read their own copy"
    assert source.count("manifest = load_fresh()") == 2
