"""The battery private-seed service (M2).

Claims tested:
- the promoted derivation regenerates the exam-design campaign's private cases
  from its revealed root, so the service is the campaign's own rule;
- a root is accepted only from an owner-only regular 32-byte file, and never
  prints, pickles or appears in a public projection;
- every private batch carries hidden duplicates with opaque ids;
- a batch is usable only after its fingerprint is committed, and is revealed
  only after it retires, verifiably against the earlier commitment.
"""

import json
import os
import pickle
from pathlib import Path

import pytest

from carbon.battery import seeds
from carbon.battery.challenge import INPUTS

EVID = Path("docs/development/evidence/exam-design-2026-09-24")


def root_file(tmp_path, data=None, mode=0o600):
    path = tmp_path / "root.bin"
    path.write_bytes(data if data is not None else os.urandom(32))
    path.chmod(mode)
    return path


@pytest.fixture
def root(tmp_path):
    return seeds.PrivateRoot.load(root_file(tmp_path))


PIN = seeds.seed_pin("sha256:" + "1" * 64, "sha256:" + "2" * 64)


def test_the_campaign_cases_regenerate_from_the_revealed_root(tmp_path):
    reveal = json.loads((EVID / "private_reveal.json").read_text())
    commitment = json.loads((EVID / "private_commitment.json").read_text())
    root = seeds.PrivateRoot.load(
        root_file(tmp_path, bytes.fromhex(reveal["root_hex"]))
    )
    records = {}
    for line in (
        (EVID / "refs-b/out/battery_refs/records.jsonl").read_text().splitlines()
    ):
        r = json.loads(line)
        if not r.get("refined"):
            records[r["case_id"]] = r
    context = seeds._context(root, commitment["seed_pin"])
    checked = 0
    for role in ("pscreen-B00", "pfinal", "pverify"):
        for i in (0, 1, 57, 197):
            case = f"{role}-{i:04d}"
            if case not in records:
                continue
            assert seeds.draw_inputs(context, role, i) == {
                k: records[case]["inputs"][k] for k in INPUTS
            }, case
            checked += 1
    assert checked >= 9


def test_a_root_is_accepted_only_from_an_owner_only_file(tmp_path, root):
    with pytest.raises(ValueError):
        seeds.PrivateRoot.load(root_file(tmp_path / "..", mode=0o644))
    short = tmp_path / "short.bin"
    short.write_bytes(b"x" * 31)
    short.chmod(0o600)
    with pytest.raises(ValueError):
        seeds.PrivateRoot.load(short)
    link = tmp_path / "link.bin"
    link.symlink_to(tmp_path / "root.bin")
    with pytest.raises(ValueError):
        seeds.PrivateRoot.load(link)
    with pytest.raises(TypeError):  # valid bytes, but not loaded from a file
        seeds.PrivateRoot(os.urandom(32))
    assert "redacted" in repr(root)
    with pytest.raises(TypeError):
        pickle.dumps(root)


def test_every_private_batch_hides_duplicates(root):
    batch = seeds.make_batch(root, PIN, "pscreen-b00", 20, duplicates=2)
    assert len(batch.cases) == 20 and len(batch.duplicates) == 2
    inputs = dict(batch.cases)
    for dup, orig in batch.duplicates:
        assert inputs[dup] == inputs[orig]
    # Opaque ids: nothing in a case id names a repeat or an index.
    for case_id, _ in batch.cases:
        assert "dup" not in case_id and "repeat" not in case_id
        assert len(case_id.rsplit("-", 1)[1]) == 16
    # Duplicates are not all at the end.
    positions = [
        i for i, (c, _) in enumerate(batch.cases) if c in dict(batch.duplicates)
    ]
    assert positions != [18, 19]
    # The same root gives the same batch; a different role, a different one.
    assert (
        seeds.make_batch(root, PIN, "pscreen-b00", 20).fingerprint == batch.fingerprint
    )
    assert (
        seeds.make_batch(root, PIN, "pscreen-b01", 20).fingerprint != batch.fingerprint
    )
    with pytest.raises(ValueError):
        seeds.make_batch(root, PIN, "pverify", 20, duplicates=0)
    with pytest.raises(ValueError):
        seeds.PrivateBatch("x", batch.cases, ())


def test_commit_before_use_and_reveal_only_after_retirement(tmp_path, root):
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, PIN)
    batch = seeds.make_batch(root, PIN, "pscreen-b00", 10)
    with pytest.raises(TypeError):  # a valid batch that skipped the journal
        seeds.CommittedBatch(batch, batch.fingerprint, 0)
    committed = journal.commit(batch, pool_version=0)
    jobs = committed.solver_jobs()
    assert {tuple(sorted(j)) for j in jobs} == {tuple(sorted(("case_id", *INPUTS)))}
    with pytest.raises(seeds.RevealRefused):
        journal.reveal(committed)
    public = json.dumps(journal.public())
    # Before reveal, the public journal carries no case, input or duplicate.
    for case_id, inputs in batch.cases:
        assert case_id not in public
    assert "duplicates" not in public
    journal.retire(committed)
    journal.reveal(committed)
    result = seeds.verify_reveal(journal.public())
    assert result["reveals_checked"] == 1 and result["results"][0]["matches"]
    # A tampered reveal fails verification, and the check says what it read.
    entries = journal.public()
    entries[-1]["batch"]["cases"][0]["inputs"]["c1"] += 0.1
    assert seeds.verify_reveal(entries)["results"][0]["matches"] is False
    assert seeds.verify_reveal([])["reveals_checked"] == 0
