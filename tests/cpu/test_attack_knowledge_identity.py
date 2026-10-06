"""The attack-knowledge store under the identity rule, and what it never
reinterprets.

- OWNER-GRAPHITE-TEST-WAVE-04 §1 (decision GRAPHITE-ATTACK-IDENTITY-01):
  record schema v2 carries each record's construction identity; priors v2
  count distinct constructions and findings by it; "found" and regression
  specimens are one per distinct finding.
- Invariant 10: a v1 snapshot (frozen before the rule) is read exactly as it
  was frozen (priors v1, one specimen per finding record); a v1 record in
  the live store is `legacy_unkeyed`, never a distinct construction.
- OWNER-GRAPHITE-TEST-WAVE-05 §4: cooling's and motor's Graphite
  confirmation roles are registered sealed identities, withheld on write and
  on read, with no false positive on ordinary repository text.

Temporary directories only: no network, pod, model, chain or spend.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from carbon.agent_campaign.attack import knowledge
from carbon.agent_campaign.attack.knowledge import AttackStore, KnowledgeError
from carbon.development_session.profile import canonical, digest

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE = "battery-fastcharge-ageing-development-v1"
CONTRACT = "sha256:" + "c" * 64
EVIDENCE = ["sha256:" + "f" * 64]
ART_A = "sha256:" + "a1" * 32
ART_B = "sha256:" + "b2" * 32
COOLING_ROLE = "cooling-graphite-confirmation-v1"
MOTOR_ROLE = "motor-graphite-confirmation-v1"


def base(**overrides):
    row = {
        "challenge_id": CHALLENGE,
        "level": 0,
        "contract_digest": CONTRACT,
        "check": "score_exploitation_and_tail_failures",
        "family": "mandatory_failure",
        "boundary": "frozen_rule.score",
        "strategy": "graphite-attacker",
        "attempt_id": "epoch-1-tool-001",
    }
    row.update(overrides)
    return row


def finding(**overrides):
    row = base(
        condition="FAILING_TRIGGER",
        specimen={"recipe": "as written"},
        evidence=list(EVIDENCE),
        rebuilt=True,
    )
    row.update(overrides)
    return row


@pytest.fixture()
def store(tmp_path):
    return AttackStore(tmp_path / "store")


# -- the identity rule ---------------------------------------------------------------------
def test_a_reworded_copy_adds_no_specimen_no_found_entry_and_no_distinct_count(store):
    store.add_finding(**finding(artifact=ART_A))
    store.add_finding(
        **finding(
            attempt_id="epoch-1-tool-002",
            specimen={"recipe": "reworded"},
            artifact=ART_A,
        )
    )
    store.add_finding(
        **finding(attempt_id="epoch-1-tool-003", specimen={"r": 3}, artifact=ART_B)
    )
    # Every finding is kept (storage identity is the record digest)...
    assert len(store.findings()) == 3
    # ...but distinct findings, "found" and specimens follow the artifact.
    priors = store.priors(CHALLENGE)
    assert priors["schema"] == knowledge.PRIORS_SCHEMA
    assert priors["identity_rule"] == knowledge.IDENTITY_RULE
    family = priors["by_family"]["mandatory_failure"]
    assert family["findings"] == 3 and family["distinct_findings"] == 2
    found = priors["by_strategy"]["graphite-attacker"]["found"]
    assert [entry["identity"]["key"] for entry in found] == [ART_A, ART_B]
    specimens = store.specimens(CHALLENGE, 0)
    assert [s["specimen"] for s in specimens] == [{"recipe": "as written"}, {"r": 3}]
    assert [s["identity"] for s in specimens] == [
        {"basis": "rebuilt_artifact", "key": ART_A},
        {"basis": "rebuilt_artifact", "key": ART_B},
    ]


def test_attempts_count_distinct_constructions_by_artifact(store):
    common = base(check="artifact_and_dependency_attacks", family="recipe_forgery")
    for index, artifact in enumerate((ART_A, ART_A, ART_B, None)):
        store.add_attempt(
            **{**common, "attempt_id": f"a-{index}"},
            attempt={"text": index},
            outcome="HELD",
            artifact=artifact,
        )
    stats = store.priors(CHALLENGE)["by_family"]["recipe_forgery"]
    assert stats["attempts"] == 4
    assert stats["distinct_constructions"] == 2 and stats["without_artifact"] == 1


def test_a_finding_without_an_artifact_counts_once_per_behaviour(store):
    for index in range(3):
        store.add_finding(
            **finding(
                attempt_id=f"e-{index}",
                specimen={"text": index},
                behaviour="exposure:protected_material_in_result",
            )
        )
    store.add_finding(**finding(attempt_id="e-9", behaviour="path_accepted"))
    family = store.priors(CHALLENGE)["by_family"]["mandatory_failure"]
    assert family["findings"] == 4 and family["distinct_findings"] == 2
    assert len(store.specimens(CHALLENGE, 0)) == 2


def test_identity_fields_are_validated(store):
    for bad in ("not-a-digest", "sha256:" + "z" * 64):
        with pytest.raises(KnowledgeError) as caught:
            store.add_finding(**finding(artifact=bad))
        assert caught.value.code == knowledge.RECORD_INVALID
    with pytest.raises(KnowledgeError):
        store.add_attempt(
            **base(), attempt={}, outcome="HELD", artifact="sha256:" + "0" * 63
        )
    assert knowledge.behaviour_label("a reason with spaces") == "unspecified"
    assert knowledge.behaviour_label(None) == "unspecified"
    assert knowledge.behaviour_label("rebuild_mismatch") == "rebuild_mismatch"


# -- invariant 10: v1 material is read as it was frozen ------------------------------------------
def v1_record(**overrides):
    record = {
        "schema": knowledge.RECORD_SCHEMA_V1,
        "kind": "finding",
        "challenge_id": CHALLENGE,
        "level": 0,
        "contract_digest": CONTRACT,
        "check": "score_exploitation_and_tail_failures",
        "family": "mandatory_failure",
        "boundary": "frozen_rule.score",
        "strategy": "graphite-attacker",
        "attempt_id": "epoch-1-tool-001",
        "source": knowledge.ORACLE,
        "condition": "FAILING_TRIGGER",
        "specimen": {"recipe": "as written"},
        "control": None,
        "evidence": list(EVIDENCE),
    }
    record.update(overrides)
    return record


def freeze_v1(store, records):
    """A store and snapshot as they were before the identity rule: v1
    records and a v1 snapshot document."""
    digests = [store._put(record) for record in records]
    body = canonical(
        {
            "schema": knowledge.SNAPSHOT_SCHEMA_V1,
            "records": [
                {"kind": record["kind"], "digest": value}
                for record, value in zip(records, digests, strict=True)
            ],
        }
    )
    value = digest(body)
    path = store.root / "snapshots" / (value.removeprefix("sha256:") + ".json")
    path.write_bytes(body)
    return value, digests


V1_STATS = {"attempts", "held", "breached", "inconclusive", "near_misses", "findings"}


def test_a_v1_snapshot_is_read_exactly_as_it_was_frozen(store):
    """Two v1 findings of one family and condition (a reworded copy, by
    today's rule): the frozen run used two specimens and v1 priors, and is
    served exactly those (no silent reinterpretation)."""
    records = [
        v1_record(),
        v1_record(attempt_id="epoch-1-tool-002", specimen={"recipe": "reworded"}),
    ]
    value, digests = freeze_v1(store, records)
    view = store.pin(value)
    assert view.rule == knowledge.LEGACY_RULE
    assert view.replay(value) is view
    priors = view.priors(CHALLENGE)
    assert priors["schema"] == knowledge.PRIORS_SCHEMA_V1
    assert "identity_rule" not in priors
    assert set(priors["by_check"]["score_exploitation_and_tail_failures"]) == V1_STATS
    family = priors["by_family"]["mandatory_failure"]
    assert set(family) == V1_STATS | {"check", "levels", "boundaries"}
    assert family["findings"] == 2
    assert priors["by_strategy"]["graphite-attacker"]["found"] == [
        {
            "finding": value_,
            "challenge_id": CHALLENGE,
            "family": "mandatory_failure",
            "condition": "FAILING_TRIGGER",
        }
        for value_ in digests
    ]
    specimens = view.specimens(CHALLENGE, 0)
    assert [s["finding"] for s in specimens] == digests
    assert all("identity" not in s for s in specimens)


def test_v1_records_in_the_live_store_are_never_distinct(store):
    freeze_v1(store, [v1_record(), v1_record(attempt_id="epoch-1-tool-002")])
    store.add_finding(**finding(attempt_id="epoch-2-tool-001", artifact=ART_A))
    family = store.priors(CHALLENGE)["by_family"]["mandatory_failure"]
    assert family["findings"] == 3
    assert family["legacy_findings"] == 2 and family["distinct_findings"] == 1
    # Their specimens are kept, one each: a regression is never dropped.
    identities = [s["identity"] for s in store.specimens(CHALLENGE, 0)]
    assert identities == [
        {"basis": "legacy_unkeyed", "key": None},
        {"basis": "legacy_unkeyed", "key": None},
        {"basis": "rebuilt_artifact", "key": ART_A},
    ]
    # A new snapshot is v2 and names its rule.
    value = store.snapshot()
    path = store.root / "snapshots" / (value.removeprefix("sha256:") + ".json")
    document = json.loads(path.read_bytes())
    assert document["schema"] == knowledge.SNAPSHOT_SCHEMA
    assert document["identity_rule"] == knowledge.IDENTITY_RULE
    assert store.pin(value).rule == knowledge.IDENTITY_RULE


def test_a_snapshot_naming_another_rule_or_a_mixed_record_is_refused(store):
    body = canonical(
        {"schema": knowledge.SNAPSHOT_SCHEMA, "identity_rule": "text.v1", "records": []}
    )
    value = digest(body)
    (store.root / "snapshots" / (value.removeprefix("sha256:") + ".json")).write_bytes(
        body
    )
    with pytest.raises(KnowledgeError) as caught:
        store.pin(value)
    assert caught.value.code == knowledge.SNAPSHOT_CORRUPT
    # A v2 record without its identity is corrupt, never read as v1.
    store._put({**v1_record(), "schema": knowledge.RECORD_SCHEMA})
    with pytest.raises(KnowledgeError) as caught:
        store.findings()
    assert caught.value.code == knowledge.RECORD_CORRUPT


def test_mutation_reading_a_v1_snapshot_under_the_new_rule_turns_the_check_red(
    store, monkeypatch
):
    """Mutant: a pinned v1 view is read under the identity rule, so its two
    frozen specimens silently become one."""
    monkeypatch.setattr(
        knowledge.ReadOnlyView,
        "rule",
        property(lambda self: knowledge.IDENTITY_RULE, lambda self, value: None),
    )
    with pytest.raises(AssertionError):
        test_a_v1_snapshot_is_read_exactly_as_it_was_frozen(store)


# -- OWNER-GRAPHITE-TEST-WAVE-05 §4: cooling's and motor's confirmation roles ----------------
@pytest.mark.parametrize(
    ("text", "identity"),
    [
        (COOLING_ROLE, "cooling-graphite-confirmation-role"),
        ("COOLING_GRAPHITE_CONFIRMATION_V1", "cooling-graphite-confirmation-role"),
        (
            "cooling graphite\u200b confirmation v1",
            "cooling-graphite-confirmation-role",
        ),
        ("\u0441ooling-graphite-confirmation-v1", "cooling-graphite-confirmation-role"),
        (MOTOR_ROLE, "motor-graphite-confirmation-role"),
        ("Motor_Graphite_Confirmation_V1 batch", "motor-graphite-confirmation-role"),
        (
            "m\u043etor-graphite-\uff43onfirmation-v1",
            "motor-graphite-confirmation-role",
        ),
        # Battery's role is still battery's.
        ("graphite-confirmation-v1", "graphite-confirmation-role"),
    ],
)
def test_the_confirmation_roles_match_after_normalisation(text, identity):
    assert knowledge.sealed_identity({"probe": text}) == identity
    assert knowledge.sealed({"probe": text})


@pytest.mark.parametrize("role", [COOLING_ROLE, MOTOR_ROLE])
def test_a_record_naming_a_confirmation_role_is_withheld_on_write_and_read(store, role):
    for call, row in (
        (store.add_attempt, base(attempt={"seed_role": role}, outcome="HELD")),
        (
            store.add_near_miss,
            base(attempt={"x": 1}, note="drawn from " + role.upper()),
        ),
    ):
        with pytest.raises(KnowledgeError) as caught:
            call(**row)
        assert caught.value.code in (
            knowledge.PROTECTED_REFUSED,
            knowledge.SEALED_REFUSED,
        )
    # A finding naming it is an exposure, its content withheld.
    store.add_finding(**finding(specimen={"population": role}))
    [record] = store.findings()
    assert record["condition"] == "OTHER_SIGNAL" and record["specimen"] is None
    assert role not in json.dumps(record).lower()
    # On read: a record written before the role was registered is withheld.
    value = store._put(
        {
            **v1_record(),
            "schema": knowledge.RECORD_SCHEMA,
            "identity": {"basis": "none", "key": None},
            "kind": "attempt",
            "attempt": {"seed_role": role},
            "outcome": "HELD",
            "condition": None,
        }
    )
    assert value in store.withheld()
    assert all(r["record_digest"] != value for r in store.records())


def _tracked_text():
    """Ordinary repository text: every tracked Python and Markdown file
    outside the attack package, the tests and the decision records."""
    listed = subprocess.run(
        ["git", "ls-files", "--", "*.py", "*.md"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    skipped = ("carbon/agent_campaign/attack/", "tests/", ".agent/decisions/")
    for name in listed:
        if name.startswith(skipped):
            continue
        try:
            text = (REPOSITORY / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        yield from text.splitlines()


def test_ordinary_repository_text_raises_no_false_confirmation_or_scoped_hit():
    """False positives, string by string: a new role id matches only a line
    that names that role; no ordinary line matches a cooling condition id
    (the scoped entry stays at zero)."""
    roles = {
        "cooling-graphite-confirmation-role": COOLING_ROLE,
        "motor-graphite-confirmation-role": MOTOR_ROLE,
    }
    scanned = hits = 0
    for line in _tracked_text():
        lowered = line.lower()
        if not any(word in lowered for word in ("confirmation", "rep", "boundary")):
            continue
        scanned += 1
        found = knowledge.sealed_identity({"line": line})
        if found in roles:
            hits += 1
            spaced = knowledge.normalise(line)[0]
            assert knowledge.normalise(roles[found])[0] in spaced, line
        assert found != "cooling-final-condition-ids", line
    assert scanned > 1000  # the scan read real text
    # The genuine role names exist in the repository text (cooling's
    # interface constant); each such line is a true hit.
    assert hits >= 1
