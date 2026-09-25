"""The battery shadow scorer (M2): admission, committed pools and disclosure.

Claims tested:
- a submission is admitted only through the battery contract: another
  Challenge's family or a stale contract digest is refused by name before
  anything is rebuilt;
- a pool is built only from committed batches of exactly one screening batch,
  so hidden duplicates are always inside what is scored;
- rotation retires the oldest batch in the seed journal, which is what
  permits its reveal;
- the public projection is exactly the allow-list, and planted private values
  (case ids, inputs, reference outputs, per-case errors, the seed) never
  appear in it.
"""

import json
from pathlib import Path

import pytest

from carbon.battery import seeds, shadow
from carbon.battery.challenge import INPUTS, PublicMaterial
from carbon.reconstruction import capability_registry as r
from carbon.reconstruction.challenge_contracts import SubmissionRefused

EVID = Path("docs/development/evidence/exam-design-2026-09-24")
BATTERY = r.BATTERY_CHALLENGE
PUBLIC_KEYS = {
    "schema",
    "challenge",
    "submission_id",
    "recipe_digest",
    "contract_digest",
    "pool_version",
    "pool_fingerprints",
    "eligible",
    "score",
    "important_score",
    "gates_failed",
    "cases",
    "evidence",
    "rule",
    "qualification",
    "reward",
}


def strategy(backbone="knn", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": backbone,
        "parameters": parameters,
    }


@pytest.fixture(scope="module")
def campaign():
    refs = {}
    for line in (
        (EVID / "refs-b/out/battery_refs/records.jsonl").read_text().splitlines()
    ):
        rec = json.loads(line)
        if not rec.get("refined"):
            refs[rec["case_id"]] = rec
    slots = json.loads((EVID / "plans/private-slots.json").read_text())
    return refs, slots, PublicMaterial.load()


def batch_from_campaign(refs, slots, role):
    """A 100-case private batch: 98 campaign cases and two hidden repeats."""
    ids = [c["case_id"] for c in slots[role] if "duplicate_of" not in c][:98]
    cases = [(c, tuple(sorted((k, refs[c]["inputs"][k]) for k in INPUTS))) for c in ids]
    dups = [(f"{role}-r{j}", ids[j * 40]) for j in range(2)]
    inputs = dict(cases)
    cases += [(d, inputs[o]) for d, o in dups]
    return seeds.PrivateBatch(role, tuple(cases), tuple(dups))


@pytest.fixture
def pool(tmp_path, campaign):
    refs, slots, material = campaign
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    committed = [
        journal.commit(
            batch_from_campaign(refs, slots, f"pscreen-B0{b}"), pool_version=0
        )
        for b in range(4)
    ]
    return shadow.ShadowPool(committed, refs, material, journal), journal, committed


def test_admission_goes_through_the_battery_contract(pool):
    scorer, _, _ = pool
    digest = r.contract_digest(BATTERY)
    with pytest.raises(SubmissionRefused):
        scorer.score("s1", strategy("fno"), digest, 0)
    with pytest.raises(SubmissionRefused) as refused:
        scorer.score("s1", strategy("knn"), r.contract_digest(r.BURGERS_CHALLENGE), 0)
    assert refused.value.issues[0].code == "contract.digest_mismatch"
    assert scorer.pool.history == []  # nothing was scored


def test_pools_take_only_whole_committed_batches(tmp_path, campaign):
    refs, slots, material = campaign
    batch = batch_from_campaign(refs, slots, "pscreen-B00")
    journal = seeds.SeedJournal(tmp_path / "j.jsonl")
    with pytest.raises(TypeError):
        shadow.ShadowPool([batch] * 3, refs, material, journal)
    short = seeds.PrivateBatch(
        batch.role, batch.cases[:50] + batch.cases[98:], batch.duplicates
    )
    with pytest.raises(ValueError):
        shadow.ShadowPool(
            [journal.commit(short, pool_version=0)] * 3, refs, material, journal
        )


def test_scoring_rotation_and_disclosure(pool, campaign):
    scorer, journal, committed = pool
    refs, _, _ = campaign
    digest = r.contract_digest(BATTERY)
    results = []
    for i, (backbone, params) in enumerate(
        [
            ("knn", {}),
            ("knn", {"neighbours": 9}),
            ("knn", {"neighbours": 2}),
            ("knn", {}),
        ]
    ):
        internal, public = scorer.score(
            f"sub-{i}", strategy(backbone, **params), digest, 7
        )
        results.append((internal, public))
        assert set(public) == PUBLIC_KEYS
        assert public["eligible"] is True and public["qualification"] is False
        assert public["reward"] is False
    # Every duplicate of the active batches was inside what was scored.
    assert results[0][0]["n_cases"] == 300
    scored = set(scorer.pool.active_case_ids())
    for b in scorer.pool.active:
        assert {d for d, _ in committed[b].batch.duplicates} <= scored
    # The third admission rotated the pool and retired the oldest batch.
    assert results[3][1]["pool_version"] == 1
    assert results[3][1]["pool_fingerprints"][0] == committed[1].fingerprint
    retired = [e for e in journal.public() if e["kind"] == "retire"]
    assert [e["fingerprint"] for e in retired] == [committed[0].fingerprint]
    journal.reveal(committed[0])  # permitted now
    with pytest.raises(seeds.RevealRefused):
        journal.reveal(committed[1])
    # Disclosure: nothing private reaches a public projection.
    text = json.dumps([p for _, p in results])
    for batch in committed:
        for case_id, inputs in batch.batch.cases:
            assert case_id not in text
    planted = [refs[c]["outputs"]["plating_margin_v"] for c in list(refs)[:50]]
    planted += [v for c in list(refs)[:20] for v in refs[c]["inputs"].values()]
    for value in planted:
        assert repr(value) not in text
    assert '"seed"' not in text and "params_sha256" not in text
