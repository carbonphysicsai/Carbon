"""The attack-knowledge store (OWNER-GRAPHITE-ATTACKER-01 §2-§3, slice AT-D).

Content-addressed and append-only; a snapshot digest pins what a frozen
admission run used, and a replay under another digest is refused; one
regression specimen per verified finding, re-run on a new adapter or contract
version; per-Challenge and cross-Challenge priors; the protected rule on
every write and every read; no sealed or confirmation material; a development
finding that names a protected case becomes an OTHER_SIGNAL finding; findings
only in the CONDITIONS vocabulary; held-out controls never stored and never
read by the engine.

Each boundary this slice owns has a mutation-style test: the mutant is
applied with `monkeypatch` and the boundary's own check is shown to fail.
Everything runs in temporary directories with injected fakes: no network,
model, pod, chain or spend.
"""

from __future__ import annotations

import ast
import contextlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from carbon.agent_campaign.attack import knowledge
from carbon.agent_campaign.attack.knowledge import (
    AttackStore,
    KnowledgeError,
    ReadOnlyView,
    SpecimenAttempt,
    training_view,
)
from carbon.agent_campaign.graphite import tools
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
#: A second, synthetic Challenge: the store is Challenge-neutral.
SYNTHETIC = "synthetic-heat-sink-v1"
CONTRACT = "sha256:" + "c" * 64
NEXT_CONTRACT = "sha256:" + "d" * 64
LATER_CONTRACT = "sha256:" + "e" * 64
EVIDENCE = ["sha256:" + "f" * 64]
#: Two rebuilt artifacts' identities (`attack.identity.artifact_of`).
ARTIFACT_A = "sha256:" + "a1" * 32
ARTIFACT_B = "sha256:" + "b2" * 32


def base(**overrides):
    row = {
        "challenge_id": BATTERY_CHALLENGE,
        "level": 0,
        "contract_digest": CONTRACT,
        "check": "artifact_and_dependency_attacks",
        "family": "recipe_forgery",
        "boundary": "compiler.unknown_field",
        "strategy": "graphite-attacker",
        "attempt_id": "epoch-1-attack-tool-001",
    }
    row.update(overrides)
    return row


def attempt(**overrides):
    row = base(attempt={"recipe": {"pretrained_weights_field": "x"}}, outcome="HELD")
    row.update(overrides)
    return row


def near_miss(**overrides):
    row = base(
        attempt={"recipe": {"width": 513}},
        note="accepted up to the declared width",
        margin=1.0,
    )
    row.update(overrides)
    return row


def finding(**overrides):
    row = base(
        check="score_exploitation_and_tail_failures",
        family="mandatory_failure",
        boundary="frozen_rule.score",
        attempt_id="epoch-1-attack-tool-002",
        condition="FAILING_TRIGGER",
        specimen={"predictions": "nonfinite", "case": 3},
        evidence=list(EVIDENCE),
        rebuilt=True,
    )
    row.update(overrides)
    return row


@pytest.fixture()
def store(tmp_path):
    return AttackStore(tmp_path / "store")


def refused(code, call, /, **kwargs):
    with pytest.raises(KnowledgeError) as caught:
        call(**kwargs)
    assert caught.value.code == code, caught.value
    return caught.value


@dataclass(frozen=True)
class Verdict:
    """`attack.adapter.OracleResult`'s shape (AT-A): the oracle's verdict on
    one attempt. Verdicts there: HELD, BREACHED, FAILED_INFRA, TIMEOUT,
    CRASHED, NOT_RUN."""

    verdict: str
    family: str = "mandatory_failure"
    attempt: str = "epoch-1-attack-tool-002"
    evidence_digest: str = EVIDENCE[0]
    condition: str | None = None


BREACH = Verdict("BREACHED", condition="FAILING_TRIGGER")


class Spy:
    """An adapter as `attack.adapter` defines it (AT-A's `DeclaredAdapter`
    shape, including its public `control_set` of both splits), recording what
    is read. Its oracle takes an attempt with a `name` and a `value`, as
    `attack.adapter.family_oracle` does, and raises TypeError otherwise."""

    def __init__(self, *, challenge_id=BATTERY_CHALLENGE, level=0, contract=CONTRACT):
        self.challenge_id, self.level, self.contract_digest = (
            challenge_id,
            level,
            contract,
        )
        self.splits, self.oracle_calls = [], []
        self.result = BREACH
        self.control_set = (
            {"control_id": "trained-1", "split": "trained"},
            {"control_id": "kept-back-1", "split": "held_out"},
        )

    def families(self):
        return ("mandatory_failure",)

    def level_families(self):
        return ()

    def rebuild(self, construction):
        return {"rebuilt": construction}

    def controls(self, split):
        self.splits.append(split)
        return tuple(c for c in self.control_set if c["split"] == split)

    def oracle(self, family, attempt):
        if not (hasattr(attempt, "name") and hasattr(attempt, "value")):
            raise TypeError("an attempt has a name and a value")
        self.oracle_calls.append((family, attempt))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


# -- content addressing and append-only --------------------------------------------


def test_records_are_content_addressed_and_written_once(store):
    first = store.add_attempt(**attempt())
    again = store.add_attempt(**attempt())
    assert first == again
    path = store.root / "objects" / (first.removeprefix("sha256:") + ".json")
    assert digest(path.read_bytes()) == first
    assert len(store.journal.read_text().splitlines()) == 1
    assert [r["record_digest"] for r in store.attempts()] == [first]
    # Owner-only, like the miner's library.
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_the_journal_is_append_only_in_order(store):
    one = store.add_attempt(**attempt())
    two = store.add_near_miss(**near_miss())
    three = store.add_finding(**finding())
    entries = [json.loads(line) for line in store.journal.read_text().splitlines()]
    assert [e["digest"] for e in entries] == [one, two, three]
    assert [e["seq"] for e in entries] == [1, 2, 3]
    assert [e["kind"] for e in entries] == ["attempt", "near_miss", "finding"]
    assert [r["record_digest"] for r in store.records()] == [one, two, three]


def test_the_journal_is_hash_chained(store):
    """Each entry names the sha256 of the line before it (None for the
    first), so the order and contents of the journal are bound together."""
    store.add_attempt(**attempt())
    store.add_near_miss(**near_miss())
    store.add_finding(**finding())
    lines = store.journal.read_bytes().splitlines()
    entries = [json.loads(line) for line in lines]
    assert entries[0]["prev"] is None
    assert [e["prev"] for e in entries[1:]] == [digest(line) for line in lines[:-1]]
    assert {e["schema"] for e in entries} == {knowledge.JOURNAL_SCHEMA}


def _rewrite(store, lines):
    store.journal.chmod(0o600)
    store.journal.write_bytes(b"".join(line + b"\n" for line in lines))


@pytest.mark.parametrize(
    "tamper",
    ["drop_first", "drop_middle", "swap", "duplicate", "edit_kind", "renumber"],
)
def test_a_broken_journal_chain_or_sequence_is_refused_on_read(store, tamper):
    """A dropped, reordered, duplicated or edited journal entry is refused on
    read (`attack_record_corrupt`), never read past; so is any write after
    it."""
    store.add_attempt(**attempt())
    store.add_near_miss(**near_miss())
    store.add_finding(**finding())
    lines = store.journal.read_bytes().splitlines()
    if tamper == "drop_first":
        lines = lines[1:]
    elif tamper == "drop_middle":
        lines = [lines[0], lines[2]]
    elif tamper == "swap":
        lines = [lines[1], lines[0], lines[2]]
    elif tamper == "duplicate":
        lines = [*lines, lines[2]]
    elif tamper == "edit_kind":
        entry = json.loads(lines[1])
        lines[1] = canonical({**entry, "kind": "attempt"})
    else:
        entry = json.loads(lines[2])
        lines[2] = canonical({**entry, "seq": 7})
    _rewrite(store, lines)
    refused(knowledge.RECORD_CORRUPT, store.records)
    refused(knowledge.RECORD_CORRUPT, store.snapshot)
    refused(
        knowledge.RECORD_CORRUPT,
        store.add_attempt,
        **attempt(attempt_id="epoch-1-attack-tool-010"),
    )


def test_failed_infra_is_stored_as_itself_and_never_a_hold(store):
    """An infrastructure failure keeps its own outcome (never folded into
    CRASH) and counts inconclusive, never held."""
    store.add_attempt(**attempt(outcome="FAILED_INFRA"))
    store.add_attempt(**attempt(outcome="CRASH", attempt_id="epoch-1-attack-tool-003"))
    assert [a["outcome"] for a in store.attempts()] == ["FAILED_INFRA", "CRASH"]
    family = store.priors(BATTERY_CHALLENGE)["by_family"]["recipe_forgery"]
    assert (family["inconclusive"], family["held"]) == (2, 0)
    assert "FAILED_INFRA" in knowledge.INCONCLUSIVE_OUTCOMES


def test_a_journal_without_its_chain_is_refused(store):
    """An entry of the unchained v1 shape (no `prev`) is not read as v2."""
    store.add_attempt(**attempt())
    (line,) = store.journal.read_bytes().splitlines()
    entry = json.loads(line)
    del entry["prev"]
    _rewrite(store, [canonical(entry)])
    refused(knowledge.RECORD_CORRUPT, store.records)


def test_a_torn_journal_line_is_cut_and_never_read(store):
    one = store.add_attempt(**attempt())
    with store.journal.open("ab") as stream:
        stream.write(b'{"schema":"torn')
    assert [r["record_digest"] for r in store.records()] == [one]
    two = store.add_attempt(**attempt(attempt_id="epoch-1-attack-tool-009"))
    assert [r["record_digest"] for r in store.records()] == [one, two]


def test_a_tampered_record_is_refused_on_read(store):
    value = store.add_attempt(**attempt())
    path = store.root / "objects" / (value.removeprefix("sha256:") + ".json")
    path.chmod(0o600)
    path.write_bytes(path.read_bytes().replace(b"HELD", b"BREACHED"))
    refused(knowledge.RECORD_CORRUPT, store.attempts)


def test_an_identical_record_in_another_store_has_the_same_digest(tmp_path):
    left, right = AttackStore(tmp_path / "left"), AttackStore(tmp_path / "right")
    for target in (left, right):
        target.add_attempt(**attempt())
        target.add_finding(**finding())
    assert left.snapshot() == right.snapshot()
    empty = AttackStore(tmp_path / "empty").snapshot()
    assert empty == digest(
        canonical(
            {
                "schema": knowledge.SNAPSHOT_SCHEMA,
                "identity_rule": knowledge.IDENTITY_RULE,
                "records": [],
            }
        )
    )


# -- snapshots, pins and frozen replay ---------------------------------------------


def frozen_replay_is_pinned(store):
    """The frozen-replay boundary, as one check: a run frozen under digest d1
    keeps exactly d1's specimens; a specimen added later belongs to the next
    suite version (d2); replaying the frozen run under d2 is refused. (The
    two findings rebuild two different artifacts: two distinct findings.)"""
    store.add_finding(**finding(artifact=ARTIFACT_A))
    d1 = store.snapshot()
    frozen = store.pin(d1).suite_pin()
    store.add_finding(
        **finding(
            attempt_id="epoch-2-attack-tool-001",
            specimen={"case": 9},
            artifact=ARTIFACT_B,
        )
    )
    d2 = store.snapshot()
    assert d2 != d1
    pinned = store.pin(frozen["attack_knowledge_digest"])
    assert [s["specimen"] for s in pinned.specimens(BATTERY_CHALLENGE, 0)] == [
        finding()["specimen"]
    ]
    assert len(store.pin(d2).specimens(BATTERY_CHALLENGE, 0)) == 2
    assert pinned.replay(d1) is pinned
    try:
        pinned.replay(d2)
    except KnowledgeError as error:
        assert error.code == knowledge.REPLAY_REFUSED
    else:
        raise AssertionError("a frozen run replayed under another store digest")


def test_a_frozen_run_replays_only_under_its_pinned_digest(store):
    frozen_replay_is_pinned(store)


def test_mutation_replay_under_a_changed_digest_turns_the_check_red(
    tmp_path, monkeypatch
):
    """Mutant: the pinned view accepts any digest on replay."""
    monkeypatch.setattr(ReadOnlyView, "replay", lambda self, value: self)
    with pytest.raises(AssertionError):
        frozen_replay_is_pinned(AttackStore(tmp_path / "store"))


def test_mutation_a_pin_that_reads_the_live_journal_turns_the_check_red(
    tmp_path, monkeypatch
):
    """Mutant: the pinned view serves the store's current records, so a
    specimen added after the freeze leaks into the frozen run."""
    target = AttackStore(tmp_path / "store")
    monkeypatch.setattr(
        ReadOnlyView, "_entries", lambda self: AttackStore._entries(target)
    )
    with pytest.raises(AssertionError):
        frozen_replay_is_pinned(target)


def test_the_suite_pin_names_the_digest(store):
    store.add_attempt(**attempt())
    value = store.snapshot()
    assert store.pin(value).suite_pin() == {
        "schema": knowledge.SUITE_PIN_SCHEMA,
        "attack_knowledge_digest": value,
    }
    assert store.pin(value).digest == value


def test_a_pinned_view_is_never_written(store):
    view = store.pin(store.snapshot())
    for name in (
        "add_attempt",
        "add_near_miss",
        "add_finding",
        "add_regression",
        "replay_specimens",
        "snapshot",
    ):
        refused(knowledge.READ_ONLY, getattr(view, name))


def test_an_unknown_or_tampered_snapshot_is_refused(store):
    refused(knowledge.SNAPSHOT_NOT_FOUND, store.pin, value="sha256:" + "0" * 64)
    refused(knowledge.SNAPSHOT_NOT_FOUND, store.pin, value="not-a-digest")
    value = store.add_attempt(**attempt())
    frozen = store.snapshot()
    path = store.root / "snapshots" / (frozen.removeprefix("sha256:") + ".json")
    body = path.read_bytes()
    path.chmod(0o600)
    path.write_bytes(body + b" ")
    refused(knowledge.SNAPSHOT_CORRUPT, store.pin, value=frozen)
    path.write_bytes(body)
    record = store.root / "objects" / (value.removeprefix("sha256:") + ".json")
    record.unlink()
    refused(knowledge.RECORD_CORRUPT, store.pin, value=frozen)


# -- specimens and regression --------------------------------------------------------


def test_one_specimen_per_verified_finding_by_challenge_and_level(store):
    found = store.add_finding(**finding())
    store.add_finding(**finding(level=1, attempt_id="epoch-1-attack-tool-003"))
    store.add_finding(**finding(challenge_id=SYNTHETIC))
    store.add_attempt(**attempt())
    store.add_near_miss(**near_miss())
    specimens = store.specimens(BATTERY_CHALLENGE, 0)
    assert [s["finding"] for s in specimens] == [found]
    assert specimens[0]["specimen"] == finding()["specimen"]
    assert specimens[0]["condition"] == "FAILING_TRIGGER"
    assert specimens[0]["contract_digest"] == CONTRACT
    assert len(store.specimens(BATTERY_CHALLENGE, 1)) == 1
    assert len(store.specimens(SYNTHETIC, 0)) == 1
    assert store.specimens(SYNTHETIC, 1) == []


def regression_detects_a_reintroduced_breach(store):
    """The regression boundary, as one check: under a new contract version
    the specimen goes to the adapter's oracle as an attempt (`name`,
    `value`), and the oracle's BREACHED verdict is recorded BREACHED."""
    found = store.add_finding(**finding())
    adapter = Spy(contract=NEXT_CONTRACT)
    rows = store.replay_specimens(adapter)
    assert rows == [{"finding": found, "state": "BREACHED"}], rows
    return found, adapter


def test_specimens_re_run_on_every_new_contract_version(store):
    assert store.regression_due(BATTERY_CHALLENGE, 0, CONTRACT) == []
    found, adapter = regression_detects_a_reintroduced_breach(store)
    assert adapter.oracle_calls == [
        (
            "mandatory_failure",
            SpecimenAttempt("epoch-1-attack-tool-002", finding()["specimen"]),
        )
    ]
    assert store.regression_due(BATTERY_CHALLENGE, 0, NEXT_CONTRACT) == []
    assert store.replay_specimens(adapter) == []
    # A later version makes it due again; the fix now holds.
    later = Spy(contract=LATER_CONTRACT)
    later.result = Verdict("HELD")
    assert store.replay_specimens(later) == [{"finding": found, "state": "HELD"}]
    states = [(r["contract_digest"], r["state"]) for r in store.regressions()]
    assert states == [(NEXT_CONTRACT, "BREACHED"), (LATER_CONTRACT, "HELD")]
    # Regressions never touch controls.
    assert adapter.splits == [] and later.splits == []


def test_a_specimen_is_any_finite_json_value(store):
    """An attack input may be a list or a scalar (a tuple is stored as a
    list); a missing or nonfinite specimen is refused."""
    value = store.add_finding(**finding(specimen=("recipe", 3)))
    assert store.specimens(BATTERY_CHALLENGE, 0)[0]["specimen"] == ["recipe", 3]
    adapter = Spy(contract=NEXT_CONTRACT)
    store.replay_specimens(adapter)
    assert adapter.oracle_calls == [
        ("mandatory_failure", SpecimenAttempt("epoch-1-attack-tool-002", ["recipe", 3]))
    ]
    store.add_finding(**finding(attempt_id="f-2", specimen="width=513"))
    for specimen in (None, [float("nan")], {"x": float("inf")}):
        refused(
            knowledge.RECORD_INVALID,
            store.add_finding,
            **finding(attempt_id="f-3", specimen=specimen),
        )
    assert len(store.findings()) == 2 and store.findings()[0]["record_digest"] == value


def test_a_dict_verdict_and_a_refused_verdict_are_read(store):
    store.add_finding(**finding())
    adapter = Spy(contract=NEXT_CONTRACT)
    adapter.result = {"verdict": "REFUSED", "family": "mandatory_failure"}
    assert [row["state"] for row in store.replay_specimens(adapter)] == ["HELD"]


def test_mutation_a_raw_specimen_attempt_turns_the_regression_check_red(
    tmp_path, monkeypatch
):
    """Mutant: the store hands the oracle the raw specimen dict, which a real
    family oracle refuses (TypeError), so every re-run is INCONCLUSIVE and a
    re-introduced breach goes unseen."""
    monkeypatch.setattr(knowledge, "SpecimenAttempt", lambda name, value: value)
    with pytest.raises(AssertionError):
        regression_detects_a_reintroduced_breach(AttackStore(tmp_path / "store"))


def test_mutation_reading_a_state_not_the_verdict_turns_the_check_red(
    tmp_path, monkeypatch
):
    """Mutant: the store reads `state` (not the OracleResult's `verdict`)."""
    monkeypatch.setattr(
        knowledge,
        "_oracle_state",
        lambda result, family: (
            "BREACHED" if getattr(result, "state", None) == "BREACHED" else "HELD"
        ),
    )
    with pytest.raises(AssertionError):
        regression_detects_a_reintroduced_breach(AttackStore(tmp_path / "store"))


@pytest.mark.parametrize(
    "result",
    [
        Verdict("TIMEOUT"),
        Verdict("CRASHED"),
        Verdict("FAILED_INFRA"),
        Verdict("NOT_RUN"),
        Verdict("UNKNOWN"),
        Verdict("BREACHED", family="another_family", condition="FAILING_TRIGGER"),
        {"state": "BREACHED"},
        {"breached": False},
        {"verdict": ["HELD"]},
        {},
        None,
        TimeoutError("wall time"),
        RuntimeError("worker died"),
    ],
)
def test_a_timeout_or_crash_on_re_run_is_inconclusive_never_held(store, result):
    store.add_finding(**finding())
    adapter = Spy(contract=NEXT_CONTRACT)
    adapter.result = result
    [row] = store.replay_specimens(adapter)
    assert row["state"] == "INCONCLUSIVE"


def test_a_regression_names_a_recorded_finding(store):
    attempted = store.add_attempt(**attempt())
    refused(
        knowledge.RECORD_INVALID,
        store.add_regression,
        finding=attempted,
        contract_digest=NEXT_CONTRACT,
        state="HELD",
    )
    found = store.add_finding(**finding())
    refused(
        knowledge.RECORD_INVALID,
        store.add_regression,
        finding=found,
        contract_digest=NEXT_CONTRACT,
        state="PASSED",
    )


# -- priors ---------------------------------------------------------------------------


def test_priors_per_challenge_and_across_challenges(store):
    store.add_attempt(**attempt())
    store.add_attempt(**attempt(attempt_id="a-2", outcome="REFUSED"))
    store.add_attempt(**attempt(attempt_id="a-3", outcome="BREACHED"))
    store.add_attempt(**attempt(attempt_id="a-4", outcome="TIMEOUT"))
    store.add_attempt(**attempt(attempt_id="a-5", outcome="UNREBUILDABLE"))
    store.add_near_miss(**near_miss())
    found = store.add_finding(**finding(strategy="track-a-deterministic"))
    store.add_attempt(
        **attempt(
            challenge_id=SYNTHETIC,
            family="fin_count",
            boundary="geometry.fin_count",
            attempt_id="s-1",
            outcome="BREACHED",
        )
    )
    battery = store.priors(BATTERY_CHALLENGE)
    assert battery["schema"] == knowledge.PRIORS_SCHEMA
    assert battery["scope"] == BATTERY_CHALLENGE
    assert battery["challenges"] == [BATTERY_CHALLENGE]
    assert set(battery["by_check"]) == CHECKS["construction_integrity"]
    artifact = battery["by_check"]["artifact_and_dependency_attacks"]
    # A timeout and an unrebuildable construction are never holds. None of
    # these attempts names a rebuilt artifact: none is a distinct
    # construction (OWNER-GRAPHITE-TEST-WAVE-04 §1).
    assert artifact == {
        "attempts": 5,
        "held": 2,
        "breached": 1,
        "inconclusive": 2,
        "near_misses": 1,
        "findings": 0,
        "distinct_constructions": 0,
        "without_artifact": 5,
        "distinct_findings": 0,
        "legacy_findings": 0,
    }
    forgery = battery["by_family"]["recipe_forgery"]
    assert forgery["check"] == "artifact_and_dependency_attacks"
    assert forgery["levels"] == [0]
    assert forgery["boundaries"]["compiler.unknown_field"]["attempts"] == 5
    assert battery["by_strategy"]["track-a-deterministic"]["found"] == [
        {
            "finding": found,
            "challenge_id": BATTERY_CHALLENGE,
            "family": "mandatory_failure",
            "condition": "FAILING_TRIGGER",
            "identity": {"basis": "behaviour", "key": "unspecified"},
        }
    ]
    assert "fin_count" not in battery["by_family"]
    across = store.priors(None)
    assert across["scope"] is None
    assert across["challenges"] == sorted([BATTERY_CHALLENGE, SYNTHETIC])
    assert set(across["by_family"]) == {
        BATTERY_CHALLENGE + "/recipe_forgery",
        BATTERY_CHALLENGE + "/mandatory_failure",
        SYNTHETIC + "/fin_count",
    }
    assert across["by_check"]["artifact_and_dependency_attacks"]["breached"] == 2
    assert across == store.priors(None)
    assert canonical(across) == canonical(json.loads(canonical(across)))


# -- what the store learns from --------------------------------------------------------


def test_only_oracle_rows_and_public_material_are_learned_from(store):
    store.add_attempt(**attempt(source=knowledge.PUBLIC))
    refused(knowledge.SOURCE_REFUSED, store.add_attempt, **attempt(source="miner"))
    refused(knowledge.SOURCE_REFUSED, store.add_near_miss, **near_miss(source="vendor"))
    refused(
        knowledge.SOURCE_REFUSED,
        store.add_finding,
        **finding(source=knowledge.PUBLIC),
    )


def test_a_finding_needs_a_rebuilt_construction(store):
    for rebuilt in (False, None, "REBUILT", 1):
        refused(
            knowledge.UNREBUILT_REFUSED, store.add_finding, **finding(rebuilt=rebuilt)
        )
    assert store.findings() == []


def test_findings_use_only_the_conditions_vocabulary(store):
    for condition in sorted(CONDITIONS):
        store.add_finding(**finding(condition=condition, attempt_id="f-" + condition))
    assert {r["condition"] for r in store.findings()} == CONDITIONS
    for condition in ("BREACH", "EXPLOIT", "failing_trigger", None, "PASS"):
        refused(
            knowledge.CONDITION_REFUSED,
            store.add_finding,
            **finding(condition=condition),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"level": -1},
        {"level": True},
        {"level": 65},
        {"check": "reference_and_decision_contract"},
        {"check": "made_up_check"},
        {"contract_digest": "sha256:short"},
        {"family": "Recipe-Forgery"},
        {"challenge_id": "Battery"},
        {"strategy": ""},
        {"boundary": "line\nbreak"},
        {"attempt": []},
        {"attempt": {"x": float("nan")}},
        {"attempt": {"x": "y" * (65 * 1024)}},
        {"outcome": "PASSED"},
        {"control": {"split": "train", "control_id": "c-1"}},
    ],
)
def test_malformed_records_are_refused(store, overrides):
    refused(knowledge.RECORD_INVALID, store.add_attempt, **attempt(**overrides))
    assert store.records() == []


# -- protected, sealed and confirmation material ------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("attempt", {"probe": "official_seed 7"}, knowledge.PROTECTED_REFUSED),
        ("attempt", {"probe": "the draw-id list"}, knowledge.PROTECTED_REFUSED),
        ("attempt", {"probe": "CARBON-CANARY-0123"}, knowledge.PROTECTED_REFUSED),
        ("attempt", {"ev5_batch": 1}, knowledge.PROTECTED_REFUSED),
        ("boundary", "verification reference", knowledge.PROTECTED_REFUSED),
        ("attempt", {"probe": "the sealed batch"}, knowledge.SEALED_REFUSED),
        ("attempt", {"probe": "motor private pool"}, knowledge.SEALED_REFUSED),
        ("boundary", "cooling final conditions", knowledge.SEALED_REFUSED),
        ("attempt", {"probe": "a held-out control"}, knowledge.HELD_OUT_REFUSED),
    ],
)
def test_protected_material_is_refused_on_write(store, field, value, code):
    # (Test names stay clear of the root's deny words: pytest names the
    # temporary root after the test.)
    refused(code, store.add_attempt, **attempt(**{field: value}))
    refused(code, store.add_near_miss, **near_miss(**{field: value}))
    assert store.records() == [] and not store.journal.exists()


def test_the_protected_rule_applies_again_on_every_read(store, monkeypatch):
    """A record written clean and later named protected (the markers grew) is
    withheld on read: from records, priors and specimens alike."""
    kept = store.add_attempt(**attempt(family="rebuild_identity", attempt={"x": 1}))
    found = store.add_finding(**finding())
    store.add_attempt(**attempt())
    frozen = store.snapshot()
    monkeypatch.setattr(
        tools, "PROTECTED_MARKERS", (*tools.PROTECTED_MARKERS, "pretrained_weights")
    )
    withheld = store.withheld()
    assert len(withheld) == 1 and kept not in withheld
    served = {r["record_digest"] for r in store.records()}
    assert served == {kept, found}
    assert (
        store.priors(BATTERY_CHALLENGE)["by_check"]["artifact_and_dependency_attacks"][
            "attempts"
        ]
        == 1
    )
    # A frozen run is never served a subset: its pin is refused outright.
    refused(knowledge.SNAPSHOT_WITHHELD, store.pin, value=frozen)
    # A snapshot taken now freezes only what is served, and pins whole.
    now = store.snapshot()
    assert now != frozen
    assert {r["record_digest"] for r in store.pin(now).records()} == served
    # The finding's specimen is withheld once the rule names it, too.
    monkeypatch.setattr(
        tools, "PROTECTED_MARKERS", (*tools.PROTECTED_MARKERS, "nonfinite")
    )
    assert store.specimens(BATTERY_CHALLENGE, 0) == []
    assert store.regression_due(BATTERY_CHALLENGE, 0, NEXT_CONTRACT) == []


def frozen_view_is_all_or_nothing(store, monkeypatch):
    """The frozen-read boundary, as one check: a view pinned before the
    protected rule grew refuses every read and its own replay once a frozen
    record is no longer admissible; it never serves a subset."""
    store.add_finding(**finding())
    store.add_attempt(**attempt())
    frozen = store.snapshot()
    view = store.pin(frozen)
    assert len(view.specimens(BATTERY_CHALLENGE, 0)) == 1
    monkeypatch.setattr(
        tools, "PROTECTED_MARKERS", (*tools.PROTECTED_MARKERS, "nonfinite")
    )
    for call in (
        lambda: view.specimens(BATTERY_CHALLENGE, 0),
        view.records,
        view.priors,
        view.withheld,
        lambda: view.replay(frozen),
        lambda: store.pin(frozen),
    ):
        try:
            served = call()
        except KnowledgeError as error:
            assert error.code == knowledge.SNAPSHOT_WITHHELD, error
        else:
            raise AssertionError(f"a frozen run was served a subset: {served!r}")


def test_a_pinned_view_serves_all_frozen_records_or_none(store, monkeypatch):
    frozen_view_is_all_or_nothing(store, monkeypatch)


def test_mutation_a_view_that_withholds_turns_the_frozen_check_red(
    tmp_path, monkeypatch
):
    """Mutant: the pinned view withholds like the live store (a subset)."""
    monkeypatch.setattr(ReadOnlyView, "_served", knowledge._Reader._served)
    with pytest.raises(AssertionError):
        frozen_view_is_all_or_nothing(AttackStore(tmp_path / "store"), monkeypatch)


def test_a_finding_that_names_a_protected_case_is_an_other_signal(store):
    """A development finding that names a protected case is itself an
    exposure: recorded OTHER_SIGNAL, the protected content withheld."""
    row = finding(
        boundary="official_seed reuse",
        specimen={"case": "hidden_case 4", "draw_id": 12},
    )
    value = store.add_finding(**row)
    [record] = store.findings()
    assert record["record_digest"] == value
    assert record["condition"] == "OTHER_SIGNAL"
    assert record["reported_condition"] == "FAILING_TRIGGER"
    assert record["protected_case_named"] is True
    assert record["specimen"] is None and record["boundary"] is None
    assert record["family"] == "mandatory_failure"
    expected = {k: v for k, v in row.items() if k not in ("check", "rebuilt")}
    stored = dict(expected)
    stored.update(
        schema=knowledge.RECORD_SCHEMA,
        kind="finding",
        source=knowledge.ORACLE,
        control=None,
        identity={"basis": "behaviour", "key": "unspecified"},
    )
    assert record["withheld_digest"] == digest(canonical(stored))
    path = store.root / "objects" / (value.removeprefix("sha256:") + ".json")
    assert not tools.protected(json.loads(path.read_bytes()))
    # An exposure has no specimen to re-run.
    assert store.specimens(BATTERY_CHALLENGE, 0) == []
    sealed = store.add_finding(
        **finding(attempt_id="f-2", specimen={"from": "the sealed batch"})
    )
    assert store.pin(store.snapshot()).findings()[1]["record_digest"] == sealed
    assert store.findings()[1]["condition"] == "OTHER_SIGNAL"


def test_a_finding_that_exposes_kept_back_controls_is_an_other_signal(store):
    """A verified finding whose content names held-out control material is an
    exposure, never refused (refusing it would lose the finding)."""
    value = store.add_finding(
        **finding(specimen={"probe": "attacker read the held-out control"})
    )
    [record] = store.findings()
    assert record["record_digest"] == value
    assert record["condition"] == "OTHER_SIGNAL"
    assert record["reported_condition"] == "FAILING_TRIGGER"
    assert record["protected_case_named"] is True and record["specimen"] is None
    assert not knowledge.held_out(record) and store.withheld() == []


def test_an_exposure_keeps_a_specimen_that_names_nothing(store):
    """Only the boundary names protected material: the exposure keeps its
    specimen, which is served and re-run like any other."""
    value = store.add_finding(**finding(boundary="official_seed reuse"))
    [record] = store.findings()
    assert record["condition"] == "OTHER_SIGNAL" and record["boundary"] is None
    assert record["specimen"] == finding()["specimen"]
    assert [s["finding"] for s in store.specimens(BATTERY_CHALLENGE, 0)] == [value]
    rows = store.replay_specimens(Spy(contract=NEXT_CONTRACT))
    assert rows == [{"finding": value, "state": "BREACHED"}]
    # A family that names the material is dropped, and so is the specimen
    # (it could not be re-run without its family).
    store.add_finding(**finding(family="ev5_probe", attempt_id="f-3"))
    assert store.findings()[1]["family"] is None
    assert store.findings()[1]["specimen"] is None


def test_an_exposure_that_still_names_material_is_refused_typed(store):
    """The exposure keeps its Challenge; if that names protected material the
    exposure is refused typed, never stored to be withheld on read."""
    refused(
        knowledge.PROTECTED_REFUSED,
        store.add_finding,
        **finding(challenge_id="ev5-batch"),
    )
    assert not store.journal.exists() and store.withheld() == []


def test_the_fresh_attack_confirmation_check_is_vocabulary_not_material(store):
    """The eighth Track A check's name contains a deny word; it is accepted as
    the check's name and nowhere else."""
    store.add_attempt(
        **attempt(
            check="fresh_attack_confirmation", family="fresh_attack", outcome="NOT_RUN"
        )
    )
    assert (
        store.priors(BATTERY_CHALLENGE)["by_check"]["fresh_attack_confirmation"][
            "inconclusive"
        ]
        == 1
    )
    refused(
        knowledge.PROTECTED_REFUSED,
        store.add_attempt,
        **attempt(family="fresh_attack_confirmation"),
    )


EV5_FINGERPRINT = "0add08ed7a3c6568a0779b0becb123578eedee6ca8e4f9f014588ed4ba934f3e"
MOTOR_COMMITMENT = "5ec0222502eb608c52d1162f4be6c7347deed7b6d4f03777ec4ea31b6d619559"


@pytest.mark.parametrize(
    ("text", "identity"),
    [
        ("sha256:" + EV5_FINGERPRINT, "ev5-confirmation-fingerprint"),
        ("SHA256:" + EV5_FINGERPRINT.upper(), "ev5-confirmation-fingerprint"),
        ("fingerprint " + EV5_FINGERPRINT[:12], "ev5-confirmation-fingerprint"),
        # Separators inside the hex and a zero-width space are normalised away.
        (
            EV5_FINGERPRINT[:20] + "-" + EV5_FINGERPRINT[20:],
            "ev5-confirmation-fingerprint",
        ),
        ("Journal_Sequence-14", "ev5-confirmation-journal-sequence"),
        ("the seed JOURNAL seq 14", "ev5-confirmation-journal-sequence"),
        ("pool commitment 5ec0222", "motor-private-pool-commitment"),
        ("sha256:" + MOTOR_COMMITMENT, "motor-private-pool-commitment"),
        ("GRAPHITE_CONFIRMATION_V1", "graphite-confirmation-role"),
        ("graphite\u200b-confirmation-v1", "graphite-confirmation-role"),
        # Full-width letters fold under NFKC; a cooling condition id counts
        # study-qualified.
        (
            "ai-accelerator-cooling-synthetic-v1/\uff52\uff45\uff50-01",
            "cooling-final-condition-ids",
        ),
        ("CHIP_COLD_PLATE Boundary_02 case", "cooling-final-condition-ids"),
        ("ev5 confirmation role", "ev5-confirmation-role"),
        # Cyrillic and Greek look-alikes fold to Latin.
        ("graphite-\u0441onfirmation-v1", "graphite-confirmation-role"),
        ("j\u03bfurnal sequence 14", "ev5-confirmation-journal-sequence"),
        ("pool commitment 5\u0435c0222", "motor-private-pool-commitment"),
    ],
)
def test_registered_sealed_identities_match_after_normalisation(text, identity):
    """Sealed material is recognised by its registered PUBLIC identity (the
    EV5 fingerprint and journal sequence, the motor private-pool commitment,
    the Graphite confirmation role and cooling's final condition ids), after
    case, separator and Unicode normalisation, never by reading it."""
    assert knowledge.sealed_identity({"probe": text}) == identity
    assert knowledge.sealed({"probe": text})


@pytest.mark.parametrize(
    "text",
    ["rep-010", "journal sequence 140", "dev5 build", "5ec022", "boundary"],
)
def test_near_misses_of_a_sealed_identity_do_not_match(text):
    assert knowledge.sealed_identity({"probe": text}) is None


@pytest.mark.parametrize(
    "value",
    [
        {"probe": "boundary 01"},
        {"probe": "the recipe hit boundary-01 of the width sweep"},
        {"note": "rep 03 of 5 repeats", "family": "recipe_surface"},
        {"attempt": ["Boundary_02", "REP-04"]},
        # The study's name alone, apart from an id, names nothing.
        {"probe": "ai-accelerator-cooling-synthetic-v1 decision study"},
    ],
)
def test_a_bare_cooling_condition_id_in_ordinary_text_does_not_match(value):
    """Short cooling ids are scoped: ordinary text such as "boundary 01"
    raises no false exposure (it would block expansion)."""
    assert knowledge.sealed_identity(value) is None
    assert not knowledge.sealed(value)


@pytest.mark.parametrize(
    "value",
    [
        {"probe": "ai-accelerator-cooling-synthetic-v1/boundary-01"},
        {"probe": "AI_ACCELERATOR_COOLING_SYNTHETIC_V1 rep 02"},
        {"probe": "chip-cold-plate:rep-04"},
        # A cooling-context record: the study or Challenge named elsewhere.
        {"challenge": "chip-cold-plate", "case": "Rep_03"},
        {"study": "ai-accelerator-cooling-synthetic-v1", "cases": ["boundary 02"]},
        {"probe": "chipcoldplate run", "case": "rep-01"},
    ],
)
def test_the_study_qualified_or_cooling_context_id_matches(value):
    assert knowledge.sealed_identity(value) == "cooling-final-condition-ids"
    assert knowledge.sealed(value)


def test_every_registered_identity_is_copied_from_a_committed_public_record():
    for entry in knowledge.SEALED_IDENTITIES:
        path = entry["source"].split(" ")[0]
        body = (REPOSITORY / path).read_text(encoding="utf-8").lower()
        values = [entry["value"]] if entry["kind"] == "digest" else entry["value"]
        # A scoped entry's scope (its study and Challenge) is copied too.
        values = [*values, *entry.get("scope", ())]
        for value in values:
            needle = value.removeprefix("sha256:")
            if entry["kind"] == "phrase":
                needle = needle.split()[0]
            assert needle.lower() in body, (entry["id"], value)


def test_a_record_naming_a_registered_identity_is_refused(store):
    # (The name stays clear of the root's deny words: pytest names the
    # temporary root after the test.)
    # The role's name also carries a protected fragment ("confirmation").
    refused(
        knowledge.PROTECTED_REFUSED,
        store.add_attempt,
        **attempt(attempt={"seed_role": "Graphite-Confirmation-V1"}),
    )
    for named in (
        {"commitment": "sha256:" + MOTOR_COMMITMENT},
        {"fingerprint": EV5_FINGERPRINT.upper()},
        {"study": "ai-accelerator-cooling-synthetic-v1", "case": "Rep_03"},
    ):
        refused(knowledge.SEALED_REFUSED, store.add_attempt, **attempt(attempt=named))
    assert store.records() == []


#: A sandbox escape's attack input: it names the repository's tests, the
#: campaign package, an `.env` file and a credential path, all attack targets.
ESCAPE = {
    "action": "run_python",
    "source": (
        "open('../../tests/fixtures/.env').read();"
        " open('carbon/agent_campaign/secrets/credential.json')"
    ),
}


def test_a_real_breach_keeps_its_condition_and_specimen(store):
    """A genuine sandbox-escape breach that names attack targets (`.env`,
    `secret`, `credential`, `tests/`, `carbon/agent_campaign/`) is a breach,
    not an exposure: it keeps FAILING_TRIGGER and its regression specimen,
    stored operator-side in the store."""
    assert tools.protected(ESCAPE)  # the live session's request filter
    assert not knowledge.sealed(ESCAPE) and not knowledge.protected(ESCAPE)
    value = store.add_finding(
        **finding(
            check="construction_evaluation_isolation",
            family="sandbox_escape",
            boundary="the research sandbox's filesystem",
            specimen=ESCAPE,
        )
    )
    [record] = store.findings()
    assert record["record_digest"] == value
    assert record["condition"] == "FAILING_TRIGGER"
    assert "protected_case_named" not in record
    assert record["specimen"] == ESCAPE
    assert [s["finding"] for s in store.specimens(BATTERY_CHALLENGE, 0)] == [value]


@pytest.mark.parametrize(
    "text",
    [
        "read .env",
        "client_secret",
        "credential_file",
        "tests/cpu/test_x.py",
        "carbon/agent_campaign/graphite/tools.py",
    ],
    ids=["dotenv", "client", "file", "tests", "package"],
)
def test_the_over_broad_fragments_no_longer_misclassify(store, text):
    assert not knowledge.sealed({"probe": text})
    store.add_attempt(**attempt(attempt={"probe": text}))
    assert len(store.attempts()) == 1 and store.withheld() == []


def test_mutation_the_checkout_deny_rule_drops_the_specimen(store, monkeypatch):
    """Mutant: the store reads Graphite's full request filter again."""
    monkeypatch.setattr(knowledge, "protected", tools.protected)
    with pytest.raises(AssertionError):
        test_a_real_breach_keeps_its_condition_and_specimen(store)


def test_a_replay_is_checked_against_the_independently_recorded_pin(store):
    """`replay_recorded` compares the view with a digest recorded elsewhere
    (a suite run record or a session pin), never with itself."""
    store.add_attempt(**attempt())
    first = store.snapshot()
    store.add_near_miss(**near_miss())
    second = store.snapshot()
    view = store.pin(second)
    assert view.replay_recorded({"attack_knowledge_digest": second}) is view
    refused(
        knowledge.REPLAY_REFUSED,
        view.replay_recorded,
        record={"attack_knowledge_digest": first},
    )
    refused(knowledge.REPLAY_REFUSED, view.replay_recorded, record={})
    from carbon.challenge_pipeline import suite

    pin = view.suite_pin()
    assert suite.attack_knowledge_digest(pin) == second
    with pytest.raises(ValueError, match="attack_knowledge_pin_malformed"):
        suite.attack_knowledge_digest({**pin, "schema": "other"})


@pytest.mark.parametrize(
    "name", ["ev5-store", "confirmation", "sealed-batch", "my-secrets", "held_out"]
)
def test_the_store_never_lives_in_sealed_material(tmp_path, name):
    refused(knowledge.STORE_ROOT_INVALID, AttackStore, root=tmp_path / name / "store")
    assert not (tmp_path / name).exists()


def test_the_store_root_is_absolute_and_not_a_link(tmp_path):
    refused(knowledge.STORE_ROOT_INVALID, AttackStore, root=Path("relative/store"))
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    refused(knowledge.STORE_ROOT_INVALID, AttackStore, root=link)


#: Everything the store's own source imports. A new import is a reviewed
#: change: it is how sealed or confirmation material could come within reach.
STORE_IMPORTS = {
    "__future__",
    "contextlib",
    "json",
    "math",
    "os",
    "re",
    "unicodedata",
    "pathlib",
    "fcntl",
    "msvcrt",
    "carbon.agent_campaign.graphite",
    "carbon.challenge_pipeline",
    "carbon.challenge_readiness.admission",
    "carbon.development_session.data",
    "carbon.development_session.profile",
}


def test_the_store_imports_only_its_listed_modules():
    tree = ast.parse(Path(knowledge.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported == STORE_IMPORTS, sorted(imported ^ STORE_IMPORTS)
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    # It never looks for files: no home, environment, working directory,
    # glob or directory listing.
    assert not calls & {
        "expanduser",
        "home",
        "getenv",
        "cwd",
        "glob",
        "rglob",
        "iterdir",
        "listdir",
        "scandir",
        "walk",
    }
    assert "environ" not in {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }


def test_importing_the_store_loads_no_sealed_confirmation_or_miner_module():
    """In a fresh interpreter the store loads no EV4/EV5, confirmation, sealed
    pool, exam, seed-material or miner-edition module."""
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys\n"
                "import carbon.agent_campaign.attack.knowledge\n"
                "print(json.dumps(sorted(sys.modules)))\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPOSITORY,
        env={**os.environ, "JAX_PLATFORMS": "cpu"},
        timeout=300,
    )
    loaded = set(json.loads(done.stdout.strip().splitlines()[-1]))
    assert {
        "carbon.agent_campaign.graphite.tools",
        "carbon.challenge_readiness.admission",
    } <= loaded  # specimen for reach
    denied = sorted(
        name
        for name in loaded
        if name.startswith("carbon")
        and any(
            word in name
            for word in (
                "ev4",
                "ev5",
                "confirm",
                "seal",
                "pool_store",
                "battery.exam",
                "battery.seeds",
                "battery.value",
                "graphite.miner",
            )
        )
    )
    assert not denied, denied


#: Paths opened while an audit is running (see `opened_paths`).
_AUDIT = {"active": None}


def _audit(event, args):
    found = _AUDIT["active"]
    if found is not None and event == "open" and args:
        found.append(args[0])


sys.addaudithook(_audit)


@contextlib.contextmanager
def opened_paths():
    found = []
    _AUDIT["active"] = found
    try:
        yield found
    finally:
        _AUDIT["active"] = None


def test_the_store_opens_nothing_outside_its_root(tmp_path):
    """Behaviourally: a full round of writes, reads, snapshots, a pin, priors
    and a specimen re-run opens files only under the store's root."""
    import fcntl  # noqa: F401 - loaded before the audit, as the store loads it

    root = tmp_path / "store"
    with opened_paths() as found:
        target = AttackStore(root)
        target.add_attempt(**attempt())
        target.add_near_miss(**near_miss())
        target.add_finding(**finding())
        target.priors(None)
        view = target.pin(target.snapshot())
        view.specimens(BATTERY_CHALLENGE, 0)
        target.replay_specimens(Spy(contract=NEXT_CONTRACT))
        target.withheld()
    assert found, "the audit saw no file opened"
    outside = [
        path
        for path in found
        if not isinstance(path, int) and not os.fsdecode(path).startswith(str(root))
    ]
    assert not outside, outside
    # Specimen: the audit does see an open outside the root.
    elsewhere = tmp_path / "elsewhere.json"
    with opened_paths() as found:
        elsewhere.write_text("{}", encoding="utf-8")
    assert [os.fsdecode(path) for path in found] == [str(elsewhere)]


# -- held-out controls ----------------------------------------------------------------------


def test_only_trained_controls_are_stored(store):
    store.add_attempt(**attempt(control={"split": "trained", "control_id": "c-1"}))
    for call, row in ((store.add_attempt, attempt), (store.add_finding, finding)):
        refused(
            knowledge.HELD_OUT_REFUSED,
            call,
            **row(control={"split": "held_out", "control_id": "c-9"}),
        )
    refused(
        knowledge.HELD_OUT_REFUSED,
        store.add_near_miss,
        **near_miss(attempt={"control": "held out set"}),
    )
    assert [r["control"] for r in store.records()] == [
        {"split": "trained", "control_id": "c-1"}
    ]


def engine_reads_only_trained_controls(store):
    """The held-out boundary, as one check: the engine's way to an adapter's
    controls returns the trained split, refuses the held-out split, and the
    store's own replay reads no control at all."""
    spy = Spy(contract=NEXT_CONTRACT)
    store.add_finding(**finding())
    assert knowledge.trained_controls(spy) == (
        {"control_id": "trained-1", "split": "trained"},
    )
    store.replay_specimens(spy)
    view = knowledge.training_view(spy)
    try:
        view.controls(knowledge.HELD_OUT)
    except KnowledgeError as error:
        assert error.code == knowledge.HELD_OUT_REFUSED
    else:
        raise AssertionError("the engine read the held-out controls")
    assert spy.splits == ["trained"], spy.splits


def view_exposes_only_the_allow_list(adapter):
    """The training view is an allow-list: no route by attribute access
    reaches the held-out split, whatever else the adapter carries."""
    view = knowledge.training_view(adapter)
    for name in ("control_set", "_adapter", "adapter", "__dict__"):
        assert not hasattr(view, name), name
    for name in knowledge.TRAINING_CALLS:
        assert not hasattr(getattr(view, name), "__self__"), name
    assert not hasattr(view.controls, "__self__")
    reachable = {name for name in dir(view) if not name.startswith("__")}
    assert reachable == {
        *knowledge.TRAINING_VALUES,
        *knowledge.TRAINING_CALLS,
        "controls",
    }, reachable


def test_the_engine_never_reads_held_out_controls(store):
    engine_reads_only_trained_controls(store)
    spy = Spy()
    view = training_view(spy)
    assert training_view(view) is view
    assert view.challenge_id == BATTERY_CHALLENGE and view.level == 0
    assert view.contract_digest == CONTRACT
    assert view.families() == ("mandatory_failure",) and view.level_families() == ()
    assert view.rebuild("x") == {"rebuilt": "x"}
    with pytest.raises(AttributeError):
        view.controls_split = "held_out"
    with pytest.raises(AttributeError):
        view.controls = spy.controls
    view_exposes_only_the_allow_list(spy)
    with pytest.raises(AttributeError):
        view.control_set  # noqa: B018 - the access itself is refused
    with pytest.raises(AttributeError):
        view._adapter  # noqa: B018


def test_a_trained_answer_carrying_another_split_is_refused():
    """An adapter that answers `controls('trained')` with a held-out control
    is refused, not passed through."""
    spy = Spy()
    spy.controls = lambda split: spy.control_set
    refused(knowledge.HELD_OUT_REFUSED, knowledge.trained_controls, adapter=spy)


class DenyListView:
    """The earlier training view: it refused `controls('held_out')` and
    forwarded every other attribute to the adapter."""

    def __init__(self, adapter):
        object.__setattr__(self, "_adapter", adapter)

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    def controls(self, split):
        if split != knowledge.TRAINING_SPLIT:
            raise KnowledgeError(knowledge.HELD_OUT_REFUSED, "refused")
        return self._adapter.controls(split)


def test_mutation_a_deny_list_view_turns_the_allow_list_check_red(monkeypatch):
    """Mutant: the deny-list proxy; `control_set` and `_adapter` reach the
    held-out split."""
    monkeypatch.setattr(knowledge, "training_view", DenyListView)
    with pytest.raises(AssertionError):
        view_exposes_only_the_allow_list(Spy())


def test_mutation_the_engine_reading_held_out_controls_turns_the_check_red(
    tmp_path, monkeypatch
):
    """Mutant: the engine's training split is the held-out one. The check goes
    red either way: the controls returned are the held-out ones, or the
    view's second guard refuses an answer carrying the held-out split."""
    monkeypatch.setattr(knowledge, "TRAINING_SPLIT", knowledge.HELD_OUT)
    with pytest.raises((AssertionError, KnowledgeError)) as caught:
        engine_reads_only_trained_controls(AttackStore(tmp_path / "store"))
    if isinstance(caught.value, KnowledgeError):
        assert caught.value.code == knowledge.HELD_OUT_REFUSED
    # Without the second guard the check itself fails on the controls read.
    monkeypatch.setattr(knowledge, "_split", lambda control: None)
    with pytest.raises(AssertionError):
        engine_reads_only_trained_controls(AttackStore(tmp_path / "again"))


def test_mutation_an_unguarded_adapter_turns_the_check_red(tmp_path, monkeypatch):
    """Mutant: the training view hands the adapter over unguarded."""
    monkeypatch.setattr(knowledge, "training_view", lambda adapter: adapter)
    with pytest.raises(AssertionError):
        engine_reads_only_trained_controls(AttackStore(tmp_path / "store"))
