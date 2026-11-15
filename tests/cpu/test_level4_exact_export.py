"""A run exports its Level 4 graph files under their EXACT names (owner via the Lead, 15 Nov 2026: "miners enabled, not
limited"; the k1 / SN79 report: a 392 KB forward document could reach a direct campaign's workspace by no route).

`PublicResearchExecutor.export` renames a run's ../output files ``<task>-<name>``; the graph reader
(`graph_envelope_from_workspace`) needs ``level4-manifest.json`` and ``level4-doc-<sha256>.json`` exactly. Those two forms
now keep their names (a document only when its name IS the sha256 of its bytes); everything else keeps the prefix. The
end-to-end test exports a ~392 KB document and reads the frozen-recipe envelope back from the workspace. Synthetic
documents only (the reader checks byte identity; G0-G4 run later).
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from carbon.development_session import research_tasks as rt


def _ledger(tmp_path):
    from carbon.development_session.research_ledger import VERSION, CampaignLedger

    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "level4-exact-export-test",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "alice",
        }
    )
    return ledger


def _executor(ledger):
    return rt.PublicResearchExecutor(
        ledger=ledger,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda name, workspace: {},
        practice=lambda *args: None,
    )


def _run(ledger, operation, files):
    """A finished run's output snapshot, as the carrier leaves it: ``{relative name: digest}``."""
    snapshot = ledger.root / operation / "snapshot"
    snapshot.mkdir(parents=True)
    for name, body in files.items():
        (snapshot / name).write_bytes(body)
    return {
        "operation": operation,
        "files": {n: rt.digest(b) for n, b in files.items()},
    }


def _doc(size, salt=b""):
    body = json.dumps({"pad": "x" * size, "salt": salt.decode()}).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest(), body


TASK = "rtsk_" + "a" * 44 + "0123456789abcdefghij"


def test_only_a_digest_named_document_and_a_complete_manifest_keep_their_names(
    tmp_path,
):
    from carbon.development_session.research_workspace import ResearchWorkspace

    workspace = ResearchWorkspace(_ledger(tmp_path), "alice")
    name, body = _doc(10)
    hexed = name[7:]
    assert rt._level4_export(f"level4-doc-{hexed}.json", body, workspace) == (
        f"level4-doc-{hexed}.json"
    )
    assert rt._level4_export(f"level4-doc-{'0' * 64}.json", body, workspace) is None
    for other in (
        "notes.txt",
        "level4-envelope.json.gz",
        f"level4-doc-{hexed}.json.bak",
    ):
        assert rt._level4_export(other, body, workspace) is None
    manifest = json.dumps({"documents": {"forward": name}}).encode()
    # its document is not in the workspace yet: the manifest keeps the run's prefix
    assert rt._level4_export("level4-manifest.json", manifest, workspace) is None
    workspace.put(f"level4-doc-{hexed}.json", body)
    assert rt._level4_export("level4-manifest.json", manifest, workspace) == (
        "level4-manifest.json"
    )
    for bad in (b"{", b"[]", b'{"documents": {}}', b'{"documents": {"forward": "x"}}'):
        assert rt._level4_export("level4-manifest.json", bad, workspace) is None


def test_a_392_kb_forward_document_reaches_the_frozen_recipes_envelope(tmp_path):
    """The k1 shape: a run lowers its model, writes the manifest and a ~392 KB forward document to ../output; the
    graph reader then builds the envelope a direct campaign freezes and stages."""
    import sys
    from pathlib import Path

    from carbon.development_session.construction_recipe import (
        graph_envelope_from_workspace,
    )
    from carbon.level4 import staging, submission

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_construction_recipe import bind, graph_recipe

    ledger = _ledger(tmp_path)
    forward, body = _doc(392 * 1024)
    manifest = json.dumps({"documents": {"forward": forward}}).encode()
    run = _run(
        ledger,
        "op-1",
        {
            "level4-manifest.json": manifest,
            f"level4-doc-{forward[7:]}.json": body,
            "notes.txt": b"lowered",
        },
    )
    exported = _executor(ledger).export(TASK, run)
    assert sorted(exported) == sorted(
        [
            "level4-manifest.json",
            f"level4-doc-{forward[7:]}.json",
            TASK[-20:] + "-notes.txt",  # everything else keeps the run's prefix
        ]
    )
    value = graph_recipe()
    value["source"]["submission_digest"] = submission.name(manifest)
    envelope = graph_envelope_from_workspace(ledger, "alice", bind(value))
    digest, raw_manifest, files = staging.from_envelope(json.loads(envelope))
    assert digest == value["source"]["submission_digest"]
    assert raw_manifest == manifest and files == {forward: body}
    assert len(body) > 392 * 1024  # larger than any single write_file (~9 KiB) by 40x


def test_a_later_run_replaces_the_manifest_and_an_identical_document_is_a_no_op(
    tmp_path,
):
    from carbon.development_session.research_workspace import ResearchWorkspace

    ledger = _ledger(tmp_path)
    executor = _executor(ledger)
    first, first_body = _doc(1000, b"1")
    second, second_body = _doc(1000, b"2")
    executor.export(
        TASK,
        _run(
            ledger,
            "op-1",
            {
                "level4-manifest.json": json.dumps(
                    {"documents": {"forward": first}}
                ).encode(),
                f"level4-doc-{first[7:]}.json": first_body,
            },
        ),
    )
    newer = json.dumps({"documents": {"forward": second}}).encode()
    exported = executor.export(
        TASK[:-1] + "k",
        _run(
            ledger,
            "op-2",
            {
                "level4-manifest.json": newer,
                f"level4-doc-{first[7:]}.json": first_body,  # the same bytes again
                f"level4-doc-{second[7:]}.json": second_body,
            },
        ),
    )
    assert "level4-manifest.json" in exported
    workspace = ResearchWorkspace(ledger, "alice")
    assert workspace.get("level4-manifest.json") == newer
    assert workspace.get(f"level4-doc-{first[7:]}.json") == first_body


def test_a_document_whose_name_is_not_its_digest_is_never_put_under_a_level4_name(
    tmp_path,
):
    from carbon.development_session.research_workspace import ResearchWorkspace

    ledger = _ledger(tmp_path)
    _name, body = _doc(100)
    wrong = "level4-doc-" + "0" * 64 + ".json"
    exported = _executor(ledger).export(TASK, _run(ledger, "op-1", {wrong: body}))
    # the prefixed form exceeds the 96-character name limit, so it is not exported at all (as before)
    assert exported == []
    assert ResearchWorkspace(ledger, "alice").current_digest(wrong) is None


@pytest.mark.parametrize("size_mib", [9])
def test_a_document_larger_than_the_8_mib_export_cap_is_exported_up_to_the_level4_bound(
    tmp_path, size_mib
):
    from carbon.level4 import intake

    ledger = _ledger(tmp_path)
    name, body = _doc(size_mib * 1024**2)
    assert 8 * 1024**2 < len(body) <= intake.CONTAINMENT_BOUNDS["document_bytes"]
    exported = _executor(ledger).export(
        TASK, _run(ledger, "op-1", {f"level4-doc-{name[7:]}.json": body})
    )
    assert exported == [f"level4-doc-{name[7:]}.json"]


def test_a_manifest_whose_documents_did_not_arrive_never_replaces_a_usable_one(
    tmp_path,
):
    from carbon.development_session.research_workspace import ResearchWorkspace

    ledger = _ledger(tmp_path)
    executor = _executor(ledger)
    good, good_body = _doc(100, b"g")
    held = json.dumps({"documents": {"forward": good}}).encode()
    executor.export(
        TASK,
        _run(
            ledger,
            "op-1",
            {"level4-manifest.json": held, f"level4-doc-{good[7:]}.json": good_body},
        ),
    )
    lost, _lost_body = _doc(100, b"l")
    broken = json.dumps({"documents": {"forward": lost}}).encode()
    exported = executor.export(
        TASK[:-1] + "k", _run(ledger, "op-2", {"level4-manifest.json": broken})
    )
    assert exported == [
        TASK[:-1][-19:] + "k-level4-manifest.json"
    ]  # the run's prefixed name, as before
    assert ResearchWorkspace(ledger, "alice").get("level4-manifest.json") == held


def test_a_run_replaces_a_manifest_the_miner_wrote_with_write_file(tmp_path):
    from carbon.development_session.research_workspace import ResearchWorkspace

    ledger = _ledger(tmp_path)
    workspace = ResearchWorkspace(ledger, "alice")
    workspace.put(
        "level4-manifest.json", b'{"documents": {}}'
    )  # as write_file leaves it
    name, body = _doc(100)
    newer = json.dumps({"documents": {"forward": name}}).encode()
    exported = _executor(ledger).export(
        TASK,
        _run(
            ledger,
            "op-1",
            {"level4-manifest.json": newer, f"level4-doc-{name[7:]}.json": body},
        ),
    )
    assert exported == [
        f"level4-doc-{name[7:]}.json",
        "level4-manifest.json",
    ]  # documents first
    assert workspace.get("level4-manifest.json") == newer


def test_an_oversized_manifest_and_a_write_conflict_fall_back_to_the_prefixed_name(
    tmp_path, monkeypatch
):
    from carbon.development_session.research_workspace import WorkspaceConflict

    ledger = _ledger(tmp_path)
    executor = _executor(ledger)
    name, body = _doc(100)
    big = json.dumps(
        {"documents": {"forward": name}, "pad": "x" * (17 * 1024)}
    ).encode()
    executor.workspace.put(f"level4-doc-{name[7:]}.json", body)
    assert executor.export(
        TASK, _run(ledger, "op-1", {"level4-manifest.json": big})
    ) == [TASK[-20:] + "-level4-manifest.json"]
    real = executor.workspace.put

    def racing(file_name, data, *, expected_digest=None):
        if file_name == "level4-manifest.json":
            raise WorkspaceConflict("changed while exporting")
        return real(file_name, data, expected_digest=expected_digest)

    monkeypatch.setattr(executor.workspace, "put", racing)
    small = json.dumps({"documents": {"forward": name}}).encode()
    assert executor.export(
        TASK[:-1] + "m", _run(ledger, "op-2", {"level4-manifest.json": small})
    ) == [TASK[:-1][-19:] + "m-level4-manifest.json"]
