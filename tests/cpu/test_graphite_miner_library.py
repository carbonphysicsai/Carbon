"""Graphite miner edition (S2): the shared card pack and the private library.

The shipped pack is the frozen phase-2 snapshot, verified against its pinned
digest and served UNCHECKED with its withheld cards left out; a tampered or
missing pack is refused `literature_pack_missing`. The private library is
owner-only and content-addressed; bans are never served, pins are flagged,
protected material is withheld at write and at serve, and a campaign serves
a frozen view by digest. No network, no model, no spend.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import stat
import zlib
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import literature, method_cards
from carbon.agent_campaign.graphite.miner import library as lib_module
from carbon.agent_campaign.graphite.miner import pack
from carbon.agent_campaign.graphite.miner.library import (
    LibraryError,
    MinerLibrary,
    MinerLiterature,
)
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
#: A Challenge reference with its version, as a campaign records it.
BATTERY = {"id": BATTERY_CHALLENGE, "version": "1.0"}
#: Set to the phase-2 snapshot file to check the shipped pack rebuilds from it.
SNAPSHOT_ENV = "CARBON_GRAPHITE_P2_SNAPSHOT"


def index_card(card_id, **fields):
    arxiv = card_id.removeprefix("arxiv-")
    value = {
        "card_id": card_id,
        "title": f"Synthetic battery surrogate {arxiv}",
        "technique": "DeepONet; neural operator",
        "claimed_effect": "fixture text | reported evidence: not stated",
        "data_regime": "simulated | required inputs: not stated",
        "cost": "not stated",
        "code_available": False,
        "applicability": "battery surrogate construction",
        "abstract": "A synthetic abstract about a battery DeepONet surrogate.",
        "provenance": (
            f"arXiv {arxiv} (https://arxiv.org/abs/{arxiv}); method card "
            "UNCHECKED; extracted by fixture-model via fixture-provider, prompt "
            "sha256:fixture; the claims are the paper's own as extracted, not "
            "Carbon's"
        ),
    }
    value.update(fields)
    return value


CARDS = (
    index_card("arxiv-2610.00001v1"),
    index_card("arxiv-2610.00002v2", title="Synthetic Fourier neural operator"),
    index_card("arxiv-2610.00003v1", title="Synthetic graph colouring"),
)


def synthetic_pack(cards=CARDS, known=("arxiv-2610.00009v1",)):
    return pack.SharedPack(
        digest="sha256:" + "a" * 64,
        cards=tuple(sorted(cards, key=lambda c: c["card_id"])),
        known=tuple(known),
    )


@pytest.fixture()
def lib(tmp_path):
    return MinerLibrary(tmp_path / "graphite-library", pack=synthetic_pack())


def snapshot_file(directory, cards, *, withheld=(), excluded=(), status="UNCHECKED"):
    index = {
        "schema": literature.INDEX_SCHEMA,
        "label": "synthetic",
        "cards": sorted(cards, key=lambda c: c["card_id"]),
    }
    document = {
        "schema": method_cards.SNAPSHOT_SCHEMA,
        "label": "synthetic",
        "query_set_digest": "sha256:" + "1" * 64,
        "prompt_digest": "sha256:" + "2" * 64,
        "index": index,
        "index_snapshot_digest": digest(canonical(index)),
        "card_digests": {},
        "card_status": {c["card_id"]: status for c in cards},
        "withheld_protected": sorted(withheld),
        "excluded": sorted(excluded),
        "authority": "synthetic",
    }
    body = canonical(document)
    path = Path(directory) / (digest(body)[7:] + ".json")
    path.write_bytes(body)
    return path


# -- the shipped pack -------------------------------------------------------------


def test_the_shipped_pack_serves_the_phase2_cards_unchecked_without_withheld():
    shared = pack.load_shared_pack()
    assert shared.digest == pack.SHARED_PACK_DIGEST
    assert shared.source["snapshot_file_digest"] == pack.SOURCE_SNAPSHOT_DIGEST
    path = pack.pack_path(pack.SHARED_PACK_DIGEST)
    document = json.loads(gzip.decompress(path.read_bytes()))
    withheld = set(document["withheld"]["withheld_protected"])
    assert withheld == {"arxiv-2202.06763v1", "arxiv-2209.05150v3"}
    # 1,773 indexed cards; the two withheld ones were never indexed.
    assert len(shared.cards) == 1773 - len(withheld & set(shared.by_id))
    assert len(shared.cards) == 1773
    assert document["check_status"] == "UNCHECKED"
    for card in shared.cards:
        assert tuple(sorted(card)) == tuple(sorted(literature.CARD_FIELDS))
        assert card["card_id"] not in withheld
        assert "method card UNCHECKED" in card["provenance"]
    assert withheld <= set(shared.known)
    assert len(shared.paper_keys) == len(shared.cards) + len(shared.known)
    assert "arxiv" in document["rights"]["title_and_abstract"].lower()


def test_the_shipped_pack_is_served_unchecked_with_origin_shared(tmp_path):
    library = MinerLibrary(tmp_path / "graphite-library")
    first = pack.load_shared_pack().cards[0]
    served = library.card(first["card_id"])
    assert served == {**first, "origin": "shared", "check_status": "UNCHECKED"}
    served["title"] = "mutated"
    assert pack.load_shared_pack().cards[0]["title"] == first["title"]


def test_the_shipped_pack_rebuilds_byte_for_byte():
    path = pack.pack_path(pack.SHARED_PACK_DIGEST)
    body = path.read_bytes()
    document = gzip.decompress(body)
    assert digest(document) == pack.SHARED_PACK_DIGEST
    assert json.loads(document)["source"]["snapshot_file_digest"] == (
        pack.SOURCE_SNAPSHOT_DIGEST
    )
    if "ng" in zlib.ZLIB_RUNTIME_VERSION:
        pytest.skip("zlib-ng compresses differently; the document is verified")
    assert pack.compress(document) == body


def test_the_pack_rebuilds_from_the_phase2_snapshot_when_present():
    source = os.environ.get(SNAPSHOT_ENV)
    if not source or not Path(source).is_file():
        pytest.skip(f"set {SNAPSHOT_ENV} to the phase-2 snapshot file")
    before = Path(source).read_bytes()
    document, _ = pack.build_document(source)
    assert Path(source).read_bytes() == before
    assert digest(document) == pack.SHARED_PACK_DIGEST
    assert (
        pack.compress(document) == pack.pack_path(pack.SHARED_PACK_DIGEST).read_bytes()
    )


@pytest.mark.parametrize(
    "tamper",
    ["edit", "truncate", "garbage", "rename", "missing", "symlink"],
)
def test_a_tampered_or_missing_pack_is_refused(tmp_path, tamper):
    shipped = pack.pack_path(pack.SHARED_PACK_DIGEST)
    target = tmp_path / shipped.name
    body = shipped.read_bytes()
    if tamper == "edit":
        document = gzip.decompress(body).replace(b"UNCHECKED", b"CHECKED__", 1)
        target.write_bytes(pack.compress(document))
    elif tamper == "truncate":
        target.write_bytes(body[: len(body) // 2])
    elif tamper == "garbage":
        target.write_bytes(b"not a pack")
    elif tamper == "rename":
        target = tmp_path / ("0" * 64 + ".json.gz")
        target.write_bytes(body)
    elif tamper == "symlink":
        target.symlink_to(shipped)
    with pytest.raises(pack.PackError) as refused:
        pack.load_pack_file(target, pack.SHARED_PACK_DIGEST)
    assert refused.value.code == "literature_pack_missing"
    assert refused.value.next_step == "install --update"


def test_a_pack_holding_a_withheld_card_is_refused(tmp_path):
    document = {
        "schema": pack.PACK_SCHEMA,
        "source": {},
        "check_status": "UNCHECKED",
        "cards": [index_card("arxiv-2610.00001v1")],
        "withheld": {
            "withheld_protected": ["arxiv-2610.00001v1"],
            "protected_at_build": [],
        },
        "known_not_indexed": [],
    }
    body = canonical(document)
    value, path = pack.write_pack(body, tmp_path)
    with pytest.raises(pack.PackError, match="withheld"):
        pack.load_pack_file(path, value)


def test_the_builder_is_deterministic_and_excludes_withheld_and_protected(tmp_path):
    cards = [
        *CARDS,
        index_card("arxiv-2610.00004v1", title="Uses the official_seed of the exam"),
    ]
    source = snapshot_file(
        tmp_path,
        cards,
        withheld=["arxiv-2610.00007v1"],
        excluded=["arxiv-2610.00008v1"],
    )
    before = source.read_bytes()
    one, document = pack.build_document(source, expected=None)
    two, _ = pack.build_document(source, expected=None)
    assert one == two and pack.compress(one) == pack.compress(two)
    assert source.read_bytes() == before
    assert [c["card_id"] for c in document["cards"]] == [c["card_id"] for c in CARDS]
    assert document["withheld"] == {
        "withheld_protected": ["arxiv-2610.00007v1"],
        "protected_at_build": ["arxiv-2610.00004v1"],
    }
    assert document["known_not_indexed"] == [
        "arxiv-2610.00004v1",
        "arxiv-2610.00007v1",
        "arxiv-2610.00008v1",
    ]
    value, path = pack.write_pack(one, tmp_path / "packs")
    loaded = pack.load_pack_file(path, value)
    assert [c["card_id"] for c in loaded.cards] == [c["card_id"] for c in CARDS]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    pack.write_pack(one, tmp_path / "packs")  # write-once: same bytes are fine


def test_the_builder_refuses_a_snapshot_it_cannot_trust(tmp_path):
    good = snapshot_file(tmp_path, list(CARDS))
    with pytest.raises(pack.PackError, match="pinned"):
        pack.build_document(good)
    renamed = tmp_path / ("f" * 64 + ".json")
    renamed.write_bytes(good.read_bytes())
    with pytest.raises(pack.PackError, match="address"):
        pack.build_document(renamed, expected=None)
    (tmp_path / "checked").mkdir()
    checked = snapshot_file(
        tmp_path / "checked",
        [
            index_card(
                c["card_id"],
                provenance=c["provenance"].replace(
                    "UNCHECKED", "HUMAN_CHECKED_CORRECT"
                ),
            )
            for c in CARDS
        ],
        status="HUMAN_CHECKED_CORRECT",
    )
    with pytest.raises(pack.PackError, match="UNCHECKED"):
        pack.build_document(checked, expected=None)


def test_the_builder_script_builds_and_checks(tmp_path, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "graphite_pack", REPOSITORY / "scripts/dev/graphite_pack.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    source = snapshot_file(tmp_path, list(CARDS))
    assert (
        script.main(["build", "--snapshot", str(source), "--out", str(tmp_path)]) == 2
    )
    assert json.loads(capsys.readouterr().out)["reason_code"] == "snapshot_invalid"
    assert script.main(["check", "--snapshot", str(source)]) == 2


def test_freezing_copies_the_pack_write_once_and_refuses_a_changed_copy(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    assert pack.freeze_into(root) == pack.SHARED_PACK_DIGEST
    frozen = pack.frozen_path(root)
    assert frozen.read_bytes() == pack.pack_path(pack.SHARED_PACK_DIGEST).read_bytes()
    assert stat.S_IMODE(frozen.stat().st_mode) == 0o600
    assert pack.freeze_into(root) == pack.SHARED_PACK_DIGEST
    assert pack.load_frozen(root).digest == pack.SHARED_PACK_DIGEST
    frozen.write_bytes(b"tampered")
    with pytest.raises(pack.PackError) as refused:
        pack.freeze_into(root)
    assert refused.value.code == "literature_pack_missing"
    with pytest.raises(pack.PackError):
        pack.load_frozen(root)


#: Internal-only Graphite modules the miner edition never imports.
INTERNAL_ONLY = {
    "grant",
    "pods",
    "experiment",
    "delivery",
    "triage",
    "next_level",
    "ladder",
    "pod_phase",
    "phase2",
    "phase3",
}


@pytest.mark.parametrize("name", ["pack", "library", "hunt", "imports", "focus"])
def test_the_literature_modules_import_no_internal_only_module(name):
    import ast

    path = REPOSITORY / "carbon/agent_campaign/graphite/miner" / (name + ".py")
    imported = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            imported.update((node.module or "").split("."))
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.update(alias.name.split("."))
    assert not imported & INTERNAL_ONLY


#: Internal-only modules, plus the internal campaign controller and providers
#: (which load the grant), that must not even be loaded.
NEVER_LOADED = INTERNAL_ONLY | {"controller", "provider", "model"}
_LOADED = """
import importlib, json, sys, types
if sys.argv[1] == "own":
    # Stand in for the graphite package's __init__, which is not S2's: this
    # measures what the literature modules themselves load.
    package = types.ModuleType("carbon.agent_campaign.graphite")
    package.__path__ = [sys.argv[2]]
    sys.modules[package.__name__] = package
for name in ("pack", "library", "hunt", "imports", "focus"):
    importlib.import_module("carbon.agent_campaign.graphite.miner." + name)
print(json.dumps(sorted(m for m in sys.modules if m.startswith("carbon."))))
"""


def _loaded(mode):
    import subprocess
    import sys

    graphite = REPOSITORY / "carbon" / "agent_campaign" / "graphite"
    result = subprocess.run(
        [sys.executable, "-c", _LOADED, mode, str(graphite)],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPOSITORY,
    )
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    return {
        name.rsplit(".", 1)[-1]
        for name in loaded
        if name.startswith("carbon.agent_campaign.")
    }


def test_the_literature_modules_load_no_internal_only_module():
    """At runtime, not only in their own import lines: what the literature
    modules and everything they import load."""
    assert not _loaded("own") & NEVER_LOADED


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "carbon/agent_campaign/graphite/__init__.py (not S2's) eagerly imports "
        "provider, which loads grant, controller, ladder and next_level; handed "
        "off to make it lazy. Remove this mark when it is."
    ),
)
def test_importing_the_miner_literature_loads_no_internal_only_module():
    assert not _loaded("package") & NEVER_LOADED


def test_paper_keys_drop_the_version():
    assert pack.paper_key("2401.12345v2") == pack.paper_key("2401.12345v1")
    assert pack.paper_key("cond-mat/0601001v3") == "cond-mat-0601001"
    assert pack.card_paper_key("arxiv-2401.12345v9") == "2401.12345"
    assert pack.card_paper_key("import-0123456789abcdef") is None


# -- the private library ---------------------------------------------------------


def hunted(library, number, *, arxiv=None, **extraction):
    """A hunted card stored the way a hunt stores one."""
    arxiv = arxiv or f"2611.{number:05d}v1"
    record = {
        "schema": "carbon.graphite.arxiv-record.v1",
        "arxiv_id": arxiv,
        "title": f"Hunted battery DeepONet paper {number}",
        "abstract": "A battery DeepONet surrogate for fast charging.",
        "authors": ["Synthetic Author"],
        "categories": ["cs.LG"],
        "primary_category": "cs.LG",
        "published": None,
        "updated": None,
        "link": "https://arxiv.org/abs/" + arxiv,
    }
    address = library.raw().put_record(record)
    fields = {
        "relevant": True,
        "method_name": "Hunted DeepONet",
        "family": "DeepONet",
        "construction_claims": ["as stated"],
        "required_inputs": [],
        "reported_evidence": [],
        "data_regime": "simulated",
        "cost": "not stated",
        "code_available": False,
        "applicability": "battery",
    }
    fields.update(extraction)
    card = method_cards.make_card(
        record,
        address,
        fields,
        {"model": "fixture-model", "provider_id": "fixture", "prompt_digest": "p"},
    )
    library.put_hunted_card(card)
    return card["card_id"]


def test_the_library_root_is_owner_only_and_absolute(tmp_path):
    library = MinerLibrary(tmp_path / "graphite-library", pack=synthetic_pack())
    assert stat.S_IMODE(library.root.stat().st_mode) == 0o700
    for child in library.root.iterdir():
        if child.is_dir():
            assert stat.S_IMODE(child.stat().st_mode) == 0o700
    library.import_text("A title", "Some neural operator text.")
    for path in (library.root / "imports" / "queue").iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(LibraryError):
        MinerLibrary(Path("relative/graphite-library"))
    link = tmp_path / "link"
    link.symlink_to(library.root)
    with pytest.raises(LibraryError):
        MinerLibrary(link)


def test_every_served_card_has_an_origin_and_is_unchecked(lib):
    hunt_id = hunted(lib, 1)
    shared = lib.card("arxiv-2610.00001v1")
    private = lib.card(hunt_id)
    assert shared["origin"] == "shared" and private["origin"] == "miner_hunt"
    for card in (shared, private):
        assert card["check_status"] == "UNCHECKED"
        assert set(card) == set(literature.CARD_FIELDS) | {"origin", "check_status"}
    assert "method card UNCHECKED" in private["provenance"]
    rows = lib.search("DeepONet", challenge=BATTERY_CHALLENGE)
    assert {row["origin"] for row in rows} == {"shared", "miner_hunt"}
    assert all(row["check_status"] == "UNCHECKED" for row in rows)
    assert all(type(row["score"]) is int and row["reasons"] for row in rows)


def test_a_card_that_names_protected_material_is_never_served(lib):
    leaked = hunted(lib, 2, method_name="Reads the official_seed")
    with pytest.raises(LibraryError) as refused:
        lib.card(leaked)
    assert refused.value.code == "card_not_found"
    assert leaked not in [c["card_id"] for c in lib.private_cards()]
    assert leaked not in [
        r["card_id"] for r in lib.search("", challenge=BATTERY_CHALLENGE, limit=50)
    ]
    flagged = synthetic_pack(
        cards=(*CARDS, index_card("arxiv-2610.00005v1", cost="a draw_id"))
    )
    literature_view = MinerLiterature(
        flagged,
        None,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=None,
        curation=None,
    )
    assert literature_view.status("arxiv-2610.00005v1") == "unknown"
    assert literature_view.record()["withheld_protected"] == 1


def test_a_card_the_reader_found_not_relevant_is_not_served(lib):
    quiet = hunted(lib, 3, relevant=False)
    with pytest.raises(LibraryError):
        lib.card(quiet)


def test_curation_pins_and_bans_with_a_digest(lib):
    empty = lib.curation()
    assert empty == {"pins": [], "bans": [], "digest": empty["digest"]}
    pinned = lib.pin("arxiv-2610.00001v1")
    assert pinned != empty["digest"]
    assert lib.pin("arxiv-2610.00001v1") == pinned
    assert lib.curation()["pins"] == ["arxiv-2610.00001v1"]
    banned = lib.ban("arxiv-2610.00001v1")
    assert lib.curation() == {
        "pins": [],
        "bans": ["arxiv-2610.00001v1"],
        "digest": banned,
    }
    with pytest.raises(LibraryError) as refused:
        lib.pin("arxiv-2610.00001v1")
    assert refused.value.code == "card_banned"
    assert lib.unban("arxiv-2610.00001v1") == empty["digest"]
    assert lib.unpin("arxiv-2610.00001v1") == empty["digest"]
    with pytest.raises(LibraryError) as unknown:
        lib.ban("arxiv-0000.00000v1")
    assert unknown.value.code == "card_not_found"
    assert lib.curation_state(banned)["bans"] == ["arxiv-2610.00001v1"]
    entries = (lib.root / "curation.jsonl").read_bytes().splitlines()
    assert [json.loads(e)["action"] for e in entries] == ["pin", "ban", "unban"]


def test_bans_are_never_served_through_either_door(lib):
    target = "arxiv-2610.00001v1"
    lib.ban(target)
    with pytest.raises(LibraryError) as refused:
        lib.card(target)
    assert refused.value.code == "card_banned"
    assert target not in [
        r["card_id"] for r in lib.search("DeepONet", challenge=BATTERY_CHALLENGE)
    ]
    assert target not in [
        r["card_id"]
        for r in lib.search("", challenge=BATTERY_CHALLENGE, limit=50, bans=[])
    ]
    listed = {r["card_id"]: r for r in lib.list_cards()["rows"]}
    assert listed[target]["banned"] and "abstract" not in listed[target]
    view = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=lib.snapshot(),
        curation=lib.curation(),
    )
    assert view.lit_card({"card_id": target})["reason_code"] == "card_banned"
    assert "card" not in view.lit_card({"card_id": target})
    assert target not in [
        r["card_id"] for r in view.lit_search({"query": "DeepONet battery"})["results"]
    ]
    assert view.status(target) == "banned" and view.origin(target) == "shared"
    other = lib.search("", challenge=BATTERY_CHALLENGE, bans=["arxiv-2610.00002v2"])
    assert "arxiv-2610.00002v2" not in [r["card_id"] for r in other]


def test_pins_are_flagged_for_the_planner(lib):
    lib.pin("arxiv-2610.00003v1")
    rows = lib.search("", challenge=BATTERY_CHALLENGE)
    assert rows[0]["card_id"] == "arxiv-2610.00003v1" and rows[0]["pinned"]
    view = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=None,
        curation=lib.curation(),
    )
    assert view.pinned() == [
        {
            "card_id": "arxiv-2610.00003v1",
            "title": "Synthetic graph colouring",
            "origin": "shared",
            "check_status": "UNCHECKED",
        }
    ]
    assert view.top(2)[0]["pinned"]
    assert view.lit_card({"card_id": "arxiv-2610.00003v1"})["assessment"]["pinned"]


def test_imports_are_validated_queued_once_and_protected_text_refused(lib):
    first = lib.import_text("A miner note", "Neural operator training notes.")
    assert first == lib.import_text("A miner note", "Neural operator training notes.")
    assert [row["import_id"] for row in lib.pending_imports()] == [first]
    assert lib.pending_imports()[0]["chars"] == len("Neural operator training notes.")
    for title, text in (
        ("", "text"),
        ("two\nlines", "text"),
        ("x" * 301, "text"),
        ("title", ""),
        ("title", "x" * 20001),
        ("title", "bell \x07"),
        ("title", "this text names an official_seed"),
        (None, "text"),
    ):
        with pytest.raises(LibraryError) as refused:
            lib.import_text(title, text)
        assert refused.value.code == "import_invalid"
    assert lib.import_text("max", "y" * 20000).startswith("import-")


def test_a_private_card_for_a_paper_the_pack_holds_is_shadowed(lib):
    shadow = hunted(lib, 4, arxiv="2610.00001v3")
    view = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=lib.snapshot(),
        curation=None,
    )
    assert view.status(shadow) == "unknown"
    assert view.record()["shadowed"] == 1
    assert shadow not in [r["card_id"] for r in lib.list_cards()["rows"]]


def test_a_campaign_serves_its_frozen_private_snapshot(lib):
    first = hunted(lib, 5)
    frozen = lib.snapshot()
    assert lib.snapshot() == frozen
    later = hunted(lib, 6)
    view = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=frozen,
        curation=None,
    )
    assert view.status(first) == "served" and view.status(later) == "unknown"
    assert view.lit_card({"card_id": first})["card"]["origin"] == "miner_hunt"
    again = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=frozen,
        curation=None,
    )
    assert again.digest == view.digest
    assert again.lit_search({"query": "battery DeepONet"}) == view.lit_search(
        {"query": "battery DeepONet"}
    )
    newer = lib.snapshot()
    assert newer != frozen
    path = lib.hunted.root / "cards" / (first + ".json")
    card = json.loads(path.read_bytes())
    path.chmod(0o600)
    path.write_bytes(canonical({**card, "method_name": "changed"}))
    with pytest.raises(ValueError):
        lib.load_snapshot(frozen)


def test_the_literature_tool_contract(lib):
    view = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=None,
        curation=None,
    )
    for bad in ({}, {"query": ""}, {"query": 7}, {"query": "x", "extra": 1}, None):
        refused = view.lit_search(bad)
        assert refused["status"] == "REFUSED_INVALID_REQUEST"
        assert refused["authority_granted"] is False
    assert view.lit_card({"card_id": 7})["status"] == "REFUSED_INVALID_REQUEST"
    missing = view.lit_card({"card_id": "arxiv-0000.00000v1"})
    assert missing == {
        "status": "NOT_FOUND",
        "reason_code": "card_not_found",
        "card_id": "arxiv-0000.00000v1",
    }
    found = view.lit_card({"card_id": "arxiv-2610.00001v1"})
    assert found["status"] == "OK" and found["content_is_data"] is True
    assert found["check_status"] == "UNCHECKED" and found["unchecked_note"]
    assert found["literature_digest"] == view.digest
    hits = view.lit_search({"query": "neural operator"})
    assert len(hits["results"]) <= lib_module.MAX_RESULTS
    assert all(
        set(row)
        == {
            "card_id",
            "title",
            "origin",
            "check_status",
            "score",
            "reasons",
            "pinned",
            "plan_input",
            "capability_request_candidate",
        }
        for row in hits["results"]
    )
    record = view.record()
    assert record["literature_digest"] == view.digest
    assert record["served_by_origin"] == {
        "shared": 3,
        "miner_hunt": 0,
        "miner_import": 0,
    }
    with pytest.raises(ValueError):
        MinerLiterature(
            lib.pack,
            lib,
            challenge=BATTERY_CHALLENGE,
            private_snapshot_digest=None,
            curation={"pins": [], "bans": [], "digest": "sha256:" + "0" * 64},
        )


def test_plans_are_stored_by_digest_with_their_lineage(lib):
    plan = {
        "schema": "carbon.graphite.miner-plan.v1",
        "created_by": "planner",
        "parent": None,
    }
    first = lib.save_plan(plan)
    assert lib.save_plan(plan) == first
    assert lib.plan(first) == plan
    edited = {**plan, "created_by": "miner", "parent": first, "note": "edited"}
    second = lib.save_plan(edited)
    assert [p["digest"] for p in lib.plans()] == [first, second]
    assert lib.plans()[1]["parent"] == first and lib.plans()[1]["created_by"] == "miner"
    for bad, code in (
        ({**plan, "created_by": "agent"}, "plan_invalid"),
        ({**plan, "parent": "sha256:" + "0" * 64}, "plan_not_found"),
        ({**plan, "parent": "nope"}, "plan_invalid"),
        ({**plan, "note": "the official_seed"}, "plan_invalid"),
        ({**plan, "blob": "x" * (300 * 1024)}, "plan_invalid"),
        ("not a plan", "plan_invalid"),
    ):
        with pytest.raises(LibraryError) as refused:
            lib.save_plan(bad)
        assert refused.value.code == code
    with pytest.raises(LibraryError) as missing:
        lib.plan("sha256:" + "0" * 64)
    assert missing.value.code == "plan_not_found"
    path = lib.root / "plans" / (first[7:] + ".json")
    path.write_bytes(canonical({**plan, "created_by": "miner"}))
    with pytest.raises(ValueError):
        lib.plan(first)


def test_outcomes_are_the_miners_own_counted_once(lib):
    cards = ["arxiv-2610.00001v1"]
    on = {"challenge": BATTERY}
    lib.record_outcome(cards, True, {"practice_task": "t-1", "rank_delta": 1}, **on)
    lib.record_outcome(cards, True, {"practice_task": "t-1", "rank_delta": 1}, **on)
    lib.record_outcome(cards, False, {"practice_task": "t-2"}, **on)
    assert lib.evidence(BATTERY) == {
        "arxiv-2610.00001v1": {"improved": 1, "not_improved": 1}
    }
    for args, challenge, code in (
        ((["arxiv-0000.00000v1"], True, {}), BATTERY, "card_not_found"),
        ((cards, "yes", {}), BATTERY, "evidence_invalid"),
        ((cards, True, {"hidden": "official_seed 7"}), BATTERY, "evidence_invalid"),
        ((cards, True, ["not", "a", "dict"]), BATTERY, "evidence_invalid"),
        (([], True, {}), BATTERY, "evidence_invalid"),
        ((cards, True, {}), "an-unregistered-challenge", "evidence_invalid"),
        ((cards, True, {}), None, "evidence_invalid"),
    ):
        with pytest.raises(LibraryError) as refused:
            lib.record_outcome(*args, challenge=challenge)
        assert refused.value.code == code


def test_outcomes_on_one_challenge_never_steer_another(lib):
    """Mutation (review): practice is bound to one Challenge and version; it
    moves neither another Challenge's grades nor its learned queries."""
    from carbon.agent_campaign.graphite.miner import focus, hunt

    other = {"id": BATTERY_CHALLENGE, "version": "9.9"}
    practised = "arxiv-2610.00003v1"
    before = lib.search("", challenge=other, limit=50)
    for task in ("t-1", "t-2", "t-3"):
        lib.record_outcome(
            [practised], True, {"practice_task": task}, challenge=BATTERY
        )
    assert lib.evidence(BATTERY)[practised] == {"improved": 3, "not_improved": 0}
    assert lib.evidence(BATTERY_CHALLENGE) == lib.evidence(BATTERY)
    assert lib.evidence(other) == {}
    assert lib.search("", challenge=other, limit=50) == before
    assert not any("miner practice" in r for row in before for r in row["reasons"])
    rows = {r["card_id"]: r for r in lib.search("", challenge=BATTERY, limit=50)}
    assert "miner practice: 3 plan(s) citing it improved, 0 did not" in (
        rows[practised]["reasons"]
    )
    discovery = {"title": "Battery fast charge"}
    assert "learned" in [
        q["source"]
        for q in hunt.plan_queries(lib, challenge=BATTERY, discovery=discovery)
    ]
    assert "learned" not in [
        q["source"]
        for q in hunt.plan_queries(lib, challenge=other, discovery=discovery)
    ]
    frozen = lib.snapshot()
    for challenge, counted in ((BATTERY, True), (other, False)):
        view = MinerLiterature(
            lib.pack,
            lib,
            challenge=challenge,
            private_snapshot_digest=frozen,
            curation=None,
            context=focus.frozen_context(*focus.public_context(BATTERY)),
        )
        reasons = view.lit_card({"card_id": practised})["assessment"]["reasons"]
        assert any("miner practice" in r for r in reasons) is counted


def test_the_literature_digest_freezes_everything_its_ranking_reads(lib):
    """Mutation (review P2): the Challenge version, the public discovery
    fields and contract the ranking reads, and the miner's focus terms are
    all in `literature_digest`; a frozen context replays the same view."""
    from carbon.agent_campaign.graphite.miner import focus

    discovery, contract = focus.public_context(BATTERY)

    def view(**changes):
        kw = {
            "challenge": BATTERY,
            "private_snapshot_digest": None,
            "curation": None,
            "discovery": discovery,
            "contract": contract,
        }
        kw.update(changes)
        return MinerLiterature(lib.pack, lib, **kw)

    base = view()
    target = {"card_id": "arxiv-2610.00001v1"}
    changed = json.loads(json.dumps(contract))
    for item in changed["capabilities"]:
        if item["id"] == "model_family.deeponet":
            item["status"] = "research_only"
    moved = view(contract=changed)
    assert moved.lit_card(target)["assessment"] != base.lit_card(target)["assessment"]
    assert moved.digest != base.digest
    retitled = {**discovery, "title": "Plasma sheath dynamics"}
    assert view(discovery=retitled).digest != base.digest
    assert view(challenge={**BATTERY, "version": "9.9"}).digest != base.digest
    assert view(focus_terms=["graph colouring"]).digest != base.digest
    # Fields the rule does not read change nothing.
    noise = {**discovery, "host": {"cpus": 1}, "exam": {"hidden": "turbulence"}}
    assert view(discovery=noise).digest == base.digest
    # The frozen context replays the same view, whatever Carbon holds later.
    frozen = json.loads(json.dumps(base.record()["context"]))
    replayed = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY,
        private_snapshot_digest=None,
        curation=None,
        context=frozen,
    )
    assert replayed.digest == base.digest
    assert replayed.lit_card(target) == base.lit_card(target)
    query = {"query": "battery DeepONet"}
    assert replayed.lit_search(query) == base.lit_search(query)
    with pytest.raises(ValueError):
        view(context=frozen)
    with pytest.raises(ValueError):
        view(discovery=None, contract=None, context={**frozen, "extra": 1})
    with pytest.raises(ValueError):
        view(
            discovery=None,
            contract=None,
            context={**frozen, "discovery": {**frozen["discovery"], "exam": 1}},
        )


def test_focus_terms_steer_the_campaign_ranking(lib):
    plain = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY,
        private_snapshot_digest=None,
        curation=None,
    )
    focused = MinerLiterature(
        lib.pack,
        lib,
        challenge=BATTERY,
        private_snapshot_digest=None,
        curation=None,
        focus_terms=["graph colouring"],
    )
    target = {"card_id": "arxiv-2610.00003v1"}
    before = plain.lit_card(target)["assessment"]
    after = focused.lit_card(target)["assessment"]
    assert not any("miner focus" in r for r in before["reasons"])
    assert "miner focus: names graph colouring" in after["reasons"]
    # All three cards already grade 3 here; the focus term orders them.
    assert plain.top(3)[0]["card_id"] != target["card_id"]
    assert focused.top(3)[0]["card_id"] == target["card_id"]
    assert focused.record()["focus_terms"] == [["graph", "colouring"]]
    searched = {
        row["card_id"]: row
        for row in lib.search(
            "", challenge=BATTERY, limit=50, focus_terms=["graph colouring"]
        )
    }
    assert "miner focus: names graph colouring" in (
        searched[target["card_id"]]["reasons"]
    )
    with pytest.raises(LibraryError) as refused:
        lib.search("", challenge=BATTERY, focus_terms=['abs:"x"'])
    assert refused.value.code == "search_invalid"


def test_one_predicate_says_what_the_library_serves(lib, tmp_path):
    """Mutation (review P4/P5): a card the campaign view never serves (shadowed
    by the pack, or withheld at serve) cannot be read, pinned, banned or cited
    in an outcome."""
    shadow = hunted(lib, 7, arxiv="2610.00001v3")
    for door in (lib.card, lib.pin, lib.ban):
        with pytest.raises(LibraryError) as refused:
            door(shadow)
        assert refused.value.code == "card_not_found"
    with pytest.raises(LibraryError) as refused:
        lib.record_outcome([shadow], True, {"practice_task": "t"}, challenge=BATTERY)
    assert refused.value.code == "card_not_found"
    assert lib.served_card(shadow) is None
    flagged = synthetic_pack(
        cards=(*CARDS, index_card("arxiv-2610.00005v1", cost="a draw_id"))
    )
    other = MinerLibrary(tmp_path / "other-library", pack=flagged)
    for door in (other.card, other.pin, other.ban):
        with pytest.raises(LibraryError) as refused:
            door("arxiv-2610.00005v1")
        assert refused.value.code == "card_not_found"
    assert other.served_card("arxiv-2610.00001v1")["origin"] == "shared"


def test_a_pin_on_a_card_no_longer_served_can_be_undone(tmp_path):
    root = tmp_path / "graphite-library"
    first = MinerLibrary(root, pack=synthetic_pack())
    private = hunted(first, 8, arxiv="2612.00001v1")
    first.pin(private)
    first.ban("arxiv-2610.00001v1")
    # A later pack holds the paper: the private card is shadowed now.
    later = MinerLibrary(
        root, pack=synthetic_pack(cards=(*CARDS, index_card("arxiv-2612.00001v2")))
    )
    view = MinerLiterature(
        later.pack,
        later,
        challenge=BATTERY,
        private_snapshot_digest=later.snapshot(),
        curation=later.curation(),
    )
    assert private not in [p["card_id"] for p in view.pinned()]
    later.unpin(private)
    assert later.curation()["pins"] == []
    with pytest.raises(LibraryError):
        later.pin(private)
    later.unban("arxiv-2610.00001v1")
    assert later.curation()["bans"] == []


def test_a_torn_journal_line_never_blocks_the_library(lib):
    lib.pin("arxiv-2610.00001v1")
    journal = lib.root / "curation.jsonl"
    torn = b'{"action":"ban","card_id":"arxiv-2610.0'
    with journal.open("ab") as stream:
        stream.write(torn)  # a crash mid-append
    assert lib.curation()["pins"] == ["arxiv-2610.00001v1"]
    lib.ban("arxiv-2610.00002v2")
    assert lib.curation() == {
        "pins": ["arxiv-2610.00001v1"],
        "bans": ["arxiv-2610.00002v2"],
        "digest": lib.curation()["digest"],
    }
    assert all(json.loads(line) for line in journal.read_bytes().splitlines())
    sidecar = lib.root / "curation.jsonl.torn"
    [kept] = [json.loads(line) for line in sidecar.read_bytes().splitlines()]
    assert kept["journal"] == "curation.jsonl"
    assert base64.b64decode(kept["bytes"]) == torn
    assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600
    assert stat.S_IMODE(journal.stat().st_mode) == 0o600


def test_a_claim_is_whole_or_absent(lib, monkeypatch):
    key, request = "2610.00005", "sha256:" + "0" * 64

    class Killed(BaseException):
        pass

    def killed(source, target):
        raise Killed()  # the process dies before the claim lands

    monkeypatch.setattr(lib_module.os, "link", killed)
    with pytest.raises(Killed):
        lib.claim(key, request_digest=request, hunt="h")
    monkeypatch.undo()
    assert lib.claim_state(key) is None
    assert lib.claim(key, request_digest=request, hunt="h") is True
    assert lib.claim(key, request_digest=request, hunt="other") is False
    assert lib.claim_state(key)["claim"]["hunt"] == "h"
    claims = lib.root / "claims"
    assert [p.name for p in claims.iterdir()] == [key + ".claim"]
    assert stat.S_IMODE((claims / (key + ".claim")).stat().st_mode) == 0o600
