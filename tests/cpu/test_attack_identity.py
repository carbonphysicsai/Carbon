"""Distinct constructions are identified by the rebuilt artifact (§1).

OWNER-GRAPHITE-TEST-WAVE-04 §1 (owner, 2026-10-05; decision
GRAPHITE-ATTACK-IDENTITY-01): anything that counts, limits, deduplicates or
rewards distinct constructions identifies them by the rebuilt artifact, never
by recipe or expression text.

- `identity.distinct`: the report's and B2's distinct counts; an attempt
  with no artifact is never a distinct construction; a breach with none
  counts once per behaviour;
- the build identity: battery's built record carries digests of the recipe
  as written (a default setting made explicit changes them) while what it
  builds is the same; a different seed is a different artifact;
- the copy probe (the leaderboard / copy attack) on battery, cooling and
  motor's real rebuilds: HELD on the real boundary, FIRED on the text-keyed
  specimen, the control (another seed) counted as two; and Level-1-ready: a
  reworded loss expression is one construction when the artifact is the
  trained result, and the probe fires when the artifact is the expression's
  digest;
- proposal ids are run-local labels: two runs reusing one id for different
  recipes merge nowhere;
- one mutation per guard: count by text, dedupe by text, reward a reworded
  copy. Each turns its check red.

No network, pod, model, chain or spend.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from carbon.agent_campaign.attack import adapter as core
from carbon.agent_campaign.attack import (
    analysis,
    benchmark,
    identity,
    knowledge,
    report,
    verify,
)
from carbon.agent_campaign.attack.adapter import Rebuilt, Unrebuildable
from carbon.development_session.profile import canonical, digest

BATTERY = "battery-fastcharge-ageing-development-v1"
COOLING = "chip-cold-plate"
MOTOR = "electric-motor-magnetics"
ART_A = "sha256:" + "a1" * 32
ART_B = "sha256:" + "b2" * 32
CONTRACT = "sha256:" + "c" * 64


def adapter_for(challenge):
    return core.ADAPTERS[(challenge, 0)]


def scaffold(challenge):
    from carbon.challenge_validator import scoring

    return scoring.scoring_for(challenge).baseline_strategy()


def motor_scaffold():
    from carbon.agent_campaign.attack.adapters import motor

    return motor._scaffold()


def row(outcome="HELD", artifact=None, **extra):
    return {
        "attempt": extra.pop("attempt", "a"),
        "outcome": outcome,
        "conditions": ["FAILING_TRIGGER"] if outcome == "BREACHED" else [],
        "artifact": artifact,
        **extra,
    }


# -- distinct counts -----------------------------------------------------------------------
def test_distinct_counts_key_on_the_artifact_never_the_text():
    rows = [
        row("BREACHED", ART_A, construction_digest="sha256:" + "1" * 64),
        row("BREACHED", ART_A, construction_digest="sha256:" + "2" * 64),
        row("HELD", ART_B, construction_digest="sha256:" + "3" * 64, rebuild="REBUILT"),
        row("HELD", None),
        row("INFRA", None),
    ]
    counted = identity.distinct(rows, "family")
    assert counted["constructions"] == 2
    assert counted["verified_constructions"] == 1 and counted["verified"] == 1
    assert counted["held_constructions"] == 1
    assert counted["without_artifact"] == 2
    # The text identities are a diagnostic: three, counted nowhere.
    assert counted["diagnostic"] == {"construction_digests": 3}
    assert counted["rule"] == identity.RULE


def test_a_breach_without_an_artifact_counts_once_per_behaviour_never_per_wording():
    """No rebuilt artifact (an exposure, the path accepting what Carbon
    cannot rebuild): never a distinct construction; reworded, it is the same
    behaviour."""
    exposure = {"reason": "exposure:protected_material_in_result"}
    accepted = {"reason": "path_accepted_an_unrebuildable_construction"}
    rows = [
        row("BREACHED", None, **exposure, construction_digest="sha256:" + "1" * 64),
        row("BREACHED", None, **exposure, construction_digest="sha256:" + "2" * 64),
        row("BREACHED", None, **accepted, rebuild="UNREBUILDABLE"),
        row("BREACHED", None, **accepted, rebuild="UNREBUILDABLE"),
    ]
    counted = identity.distinct(rows, "family")
    assert counted["constructions"] == 0 and counted["without_artifact"] == 4
    assert counted["verified_behaviours"] == 2 and counted["verified"] == 2


def test_carbons_own_declared_attacks_count_once_each():
    """An engine record is Carbon's declared attack, not a participant
    construction: no artifact, a breach counts once per declared attack."""
    rows = [
        row("BREACHED", None, declared="tampered_seed"),
        row("BREACHED", None, declared="tampered_program"),
    ]
    assert identity.distinct(rows, "rebuild_report")["verified"] == 2


def verdicts_for(artifacts):
    return [
        verify.Verdict(
            attempt=f"epoch-1-tool-{index:03d}",
            family="recipe_surface",
            rebuild=verify.REBUILT,
            outcome=verify.BREACHED,
            conditions=(verify.FAILING_TRIGGER,),
            scored=True,
            evidence={"construction": digest(str(index).encode())},
            artifact=artifact,
        )
        for index, artifact in enumerate(artifacts, start=1)
    ]


def test_the_report_and_b2_count_a_reworded_copy_once():
    """Two breaches, two wordings, one artifact: every finding is still
    emitted, but one distinct construction is found, and B2 credits one."""
    runs = report.attacker_runs(verdicts_for([ART_A, ART_A]))
    line = report.family_report(runs, controls_held_out=())["families"][
        "recipe_surface"
    ]
    assert line["verified"] == 2 and len(line["findings"]) == 2
    assert line["distinct"]["verified"] == 1
    b2 = benchmark.b2(runs, [], budget=2)
    assert b2["schema"] == "carbon.attack.b2.v2"
    assert b2["identity_rule"] == identity.RULE
    family = b2["families"]["recipe_surface"]
    assert family["verified_difference"] == 1
    assert family["verified_attempts_difference"] == 2
    # Two artifacts are two.
    runs = report.attacker_runs(verdicts_for([ART_A, ART_B]))
    assert (
        benchmark.b2(runs, [], budget=2)["families"]["recipe_surface"][
            "verified_difference"
        ]
        == 2
    )


def test_a_verdict_carries_an_artifact_only_for_a_rebuilt_construction():
    with pytest.raises(ValueError, match="artifact"):
        verify.Verdict(
            attempt="a",
            family="f",
            rebuild=verify.UNREBUILDABLE,
            outcome=verify.HELD,
            artifact=ART_A,
        )
    assert verify.SCHEMA == "carbon.attack.verdict.v2"


# -- the build identity ----------------------------------------------------------------------
def test_battery_record_digest_aliases_a_default_made_explicit_the_artifact_does_not():
    """Why the artifact is the build identity, not the record digest:
    battery's built record binds `strategy_hash`, `plan_digest` and
    `recipe_digest` of the recipe as written, so the same recipe with a
    default setting made explicit has another record digest. What it builds
    (settings, staged data, program, seed) is the same."""
    battery = adapter_for(BATTERY)
    base = scaffold(BATTERY)
    first = battery.rebuild(base)
    settings = first.detail["record"]["recipe"]["settings"]
    explicit = copy.deepcopy(base)
    explicit["parameters"]["activation"] = settings["activation"]
    second = battery.rebuild(explicit)
    assert first.rebuilt_digest != second.rebuilt_digest
    assert first.detail["record"]["recipe"]["settings"] == settings
    assert second.detail["record"]["recipe"]["settings"] == settings
    one = identity.artifact_of(battery, first, verify.record_of(first))
    two = identity.artifact_of(battery, second, verify.record_of(second))
    assert one == two
    other_seed = battery.rebuild({"strategy": base, "seed": 1})
    assert identity.artifact_of(battery, other_seed, verify.record_of(other_seed)) != (
        one
    )


def test_verify_binds_the_artifact_and_none_without_a_rebuild(tmp_path):
    cooling = adapter_for(COOLING)
    base = scaffold(COOLING)
    texts = (json.dumps(base), json.dumps(base, indent=2))
    found = [
        verify.verify(
            identity._probe_attempt("p", n, text), cooling, family=analysis.UNASSIGNED
        )
        for n, text in enumerate(texts, start=1)
    ]
    assert found[0].artifact and found[0].artifact == found[1].artifact
    assert found[0].record()["artifact"] == found[0].artifact
    refused = verify.verify(
        identity._probe_attempt("p", 3, json.dumps(cooling.recipe_outside_contract())),
        cooling,
        family=analysis.UNASSIGNED,
    )
    assert refused.rebuild == verify.UNREBUILDABLE and refused.artifact is None


# -- the copy probe ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def battery_probe():
    return identity.copy_probe(adapter_for(BATTERY))


def held_and_fired(probe):
    records = probe["run"].records
    attacks = [r for r in records if r["role"] == "attack"]
    specimens = [r for r in records if r["role"] == "specimen"]
    controls = [r for r in records if r["role"] == "control"]
    assert attacks and all(r["verdict"] == "HELD" for r in attacks), attacks
    assert all(r["verdict"] == "FIRED" for r in specimens), specimens
    assert [r["verdict"] for r in controls] == ["PASSED"]
    assert probe["state"] == "IN_PROGRESS"
    return {r["attempt"] for r in attacks}


def test_the_copy_probe_holds_on_battery_and_fires_on_text(battery_probe):
    names = held_and_fired(battery_probe)
    assert {
        "incumbent_0:key_order",
        "incumbent_0:whitespace",
        "incumbent_0:escaped_letters",
        "incumbent_0:explicit_default_seed",
        "incumbent_0:explicit_default:activation",
    } == names
    assert battery_probe["family"] == "construction_copy"
    assert battery_probe["check"] == "score_exploitation_and_tail_failures"
    record = identity.probe_record(battery_probe)
    assert record["attempted"] == 5 and json.loads(canonical(record)) == record


def test_the_copy_probe_holds_on_cooling():
    held_and_fired(identity.copy_probe(adapter_for(COOLING)))


def test_the_copy_probe_on_motor_is_not_run_without_an_incumbent_never_a_pass():
    """Motor registers no scoring yet (OWNER-GRAPHITE-TEST-WAVE-05 §1), so
    the shared layer finds no incumbent: NOT_RUN. With its scaffold as the
    incumbent, motor's real rebuild holds."""
    motor = adapter_for(MOTOR)
    probe = identity.copy_probe(motor)
    assert probe["state"] == "NOT_RUN" and probe["reason"] == identity.NO_INCUMBENT
    assert probe["run"] is None
    held_and_fired(identity.copy_probe(motor, (motor_scaffold(),)))


def test_counts_on_the_real_boundary_and_the_text_specimen():
    cooling = adapter_for(COOLING)
    base = json.dumps(scaffold(COOLING))
    copy_text = json.dumps(scaffold(COOLING), indent=2)
    real = identity.counts(cooling, (base, copy_text))
    text = identity.counts(cooling, (base, copy_text), by_text=True)
    assert set(real.values()) == {1}, real
    assert set(text.values()) == {2}, text


# -- Level 1: a reworded loss expression ---------------------------------------------------------
class LossLevel:
    """A synthetic Level-1 adapter: Carbon "trains" the construction's loss
    expression (`carbon.reconstruction.loss_expressions`) on fixed per-case
    terms, and the artifact is the digest of what it computes, the stand-in
    for the trained parameters. `by_expression=True` makes the artifact the
    compiled expression's digest instead: identity by expression text."""

    challenge_id = "synthetic-loss-level"
    level = 1
    contract_digest = CONTRACT

    def __init__(self, *, by_expression=False):
        from carbon.reconstruction import loss_expressions as le

        self.le = le
        self.by_expression = by_expression
        self.opset = le.OperationSet(
            name="synthetic",
            terms=("h1", "mse"),
            max_depth=6,
            max_nodes=16,
            max_arity=4,
            scale=(0.0, 4.0),
            exponent=(0.5, 2.0),
            epsilon=1e-12,
        )

    def incumbent_constructions(self):
        return (
            {
                "challenge_id": self.challenge_id,
                "backbone": "mlp",
                "parameters": {"width": 64},
                "loss_expression": {
                    "op": "add",
                    "args": [
                        {"term": "mse"},
                        {"op": "scale", "by": 0.5, "arg": {"term": "h1"}},
                    ],
                },
            },
        )

    def rebuild(self, construction):
        import numpy as np

        seed = 0
        if "strategy" in construction:
            construction, seed = construction["strategy"], construction.get("seed", 0)
        try:
            compiled = self.le.compile_expression(
                construction["loss_expression"], self.opset
            )
        except (self.le.ExpressionRefused, KeyError, TypeError):
            return Unrebuildable("refused_by_contract")
        terms = {
            "mse": np.linspace(0.1, 2.0, 7) + seed,
            "h1": np.linspace(0.3, 0.9, 7),
        }
        values = self.le.evaluate(compiled, terms, np)
        trained = digest(
            canonical(
                {"values": values.tobytes().hex(), "width": construction["parameters"]}
            )
        )
        return Rebuilt(
            construction_digest=digest(canonical(construction)),
            rebuilt_digest=compiled.digest if self.by_expression else trained,
            detail={"seed": seed},
        )


def test_a_reworded_loss_expression_is_one_construction_at_level_one():
    """`E` and `scale(1, E)`, and commuted arguments, build the same loss:
    one construction when the artifact is what training computes."""
    probe = identity.copy_probe(LossLevel())
    names = held_and_fired(probe)
    assert "incumbent_0:scale_one:loss_expression" in names
    assert "incumbent_0:commuted:loss_expression" in names


def test_identity_by_expression_digest_is_caught_by_the_probe():
    """At Level 1 an expression digest cannot tell `E` from `scale(1, E)`
    (packet U3): an adapter that identifies by it is a finding."""
    probe = identity.copy_probe(LossLevel(by_expression=True))
    assert probe["state"] == "FINDING"
    breached = {
        r["attempt"]
        for r in probe["run"].records
        if r["role"] == "attack" and r["verdict"] == "BREACHED"
    }
    assert breached == {"incumbent_0:scale_one:loss_expression"}


# -- proposal ids are run-local labels -------------------------------------------------------------
PROPOSAL = "p-891e0fd1ebdb"


def test_two_runs_reusing_one_proposal_id_merge_nowhere(tmp_path):
    """The executor's case: the same proposal id named an MLP in run 4 and
    a DeepONet in run 5. Nothing merges, dedupes or counts them as one."""
    store = knowledge.AttackStore(tmp_path / "store")
    common = {
        "challenge_id": BATTERY,
        "level": 0,
        "contract_digest": CONTRACT,
        "check": "artifact_and_dependency_attacks",
        "family": "recipe_surface",
        "boundary": "compiler",
        "strategy": "graphite-attacker",
        "attempt_id": PROPOSAL,
    }
    for artifact, backbone in ((ART_A, "mlp"), (ART_B, "deeponet")):
        store.add_attempt(
            **common, attempt={"backbone": backbone}, outcome="HELD", artifact=artifact
        )
        store.add_finding(
            **common,
            condition="FAILING_TRIGGER",
            specimen={"backbone": backbone},
            evidence=["sha256:" + "f" * 64],
            rebuilt=True,
            artifact=artifact,
        )
    priors = store.priors(BATTERY)
    family = priors["by_family"]["recipe_surface"]
    assert family["distinct_constructions"] == 2
    assert family["distinct_findings"] == 2
    assert len(priors["by_strategy"]["graphite-attacker"]["found"]) == 2
    assert len(store.specimens(BATTERY, 0)) == 2
    # The report: the same attempt name in two runs, two artifacts.
    verdicts = [
        verify.Verdict(
            attempt=PROPOSAL,
            family="recipe_surface",
            rebuild=verify.REBUILT,
            outcome=verify.BREACHED,
            conditions=(verify.FAILING_TRIGGER,),
            scored=True,
            artifact=artifact,
        )
        for artifact in (ART_A, ART_B)
    ]
    line = report.family_report(report.attacker_runs(verdicts), controls_held_out=())[
        "families"
    ]["recipe_surface"]
    assert line["distinct"]["constructions"] == 2


class Breaching:
    """Battery's real rebuild with an oracle that reports a breach."""

    def __init__(self):
        self.real = adapter_for(BATTERY)
        self.challenge_id, self.level = BATTERY, 0

    def rebuild(self, construction):
        return self.real.rebuild(construction)

    def oracle(self, family, attempt):
        return {"verdict": "BREACHED", "condition": "FAILING_TRIGGER"}


def test_two_sessions_reusing_a_journal_identity_keep_two_specimens(tmp_path):
    """Specimens shared by sessions were keyed by the attempt's journal
    identity, which every session reuses: the second session's different
    recipe collided with the first's bundle. They are keyed by the artifact."""
    base = scaffold(BATTERY)
    wider = copy.deepcopy(base)
    wider["parameters"]["width"] = 128
    shared = tmp_path / "specimens"
    found = [
        verify.verify(
            identity._probe_attempt("p", 1, json.dumps(strategy)),
            Breaching(),
            family="recipe_surface",
            specimen_dir=shared,
        )
        for strategy in (base, wider)
    ]
    assert [v.attempt for v in found] == ["epoch-1-tool-001"] * 2
    assert found[0].artifact != found[1].artifact
    for v in found:
        assert v.specimen["status"] == "REBUILT", v.specimen
        assert v.specimen["reused"] is False
    assert found[0].specimen["folder"] != found[1].specimen["folder"]
    # A reworded copy of the first finds its specimen: one per artifact.
    again = verify.verify(
        identity._probe_attempt("p", 2, json.dumps(base, indent=2)),
        Breaching(),
        family="recipe_surface",
        specimen_dir=shared,
    )
    assert again.specimen["folder"] == found[0].specimen["folder"]
    assert again.specimen["reused"] is True and again.specimen["status"] == "REBUILT"


def test_a_v3_bundle_binds_its_artifact_and_a_v2_bundle_still_reads(tmp_path):
    from carbon.agent_campaign.graphite import delivery, experiment

    base = scaffold(BATTERY)
    record = experiment.admit(base, 0)
    folder = verify.bundle_specimen(base, record, tmp_path / "v3", label=PROPOSAL)
    manifest = json.loads((folder / "manifest.json").read_bytes())
    assert manifest["schema"] == delivery.BUNDLE_SCHEMA
    assert manifest["artifact"] == identity.build_identity(record)
    assert delivery.clean_rebuild(folder)["status"] == "REBUILT"
    # Another recipe under the same label is another artifact.
    wider = copy.deepcopy(base)
    wider["parameters"]["width"] = 128
    other = verify.bundle_specimen(
        wider, experiment.admit(wider, 0), tmp_path / "other", label=PROPOSAL
    )
    assert json.loads((other / "manifest.json").read_bytes())["artifact"] != (
        manifest["artifact"]
    )
    # A forged artifact is a mismatch.
    forged = tmp_path / "forged"
    forged.mkdir()
    for path in folder.iterdir():
        (forged / path.name).write_bytes(path.read_bytes())
    (forged / "manifest.json").write_bytes(canonical({**manifest, "artifact": ART_A}))
    assert "manifest_artifact" in delivery.clean_rebuild(forged)["differences"]
    # A v2 bundle (made before §1) carries no artifact and reads as before.
    old = tmp_path / "v2"
    old.mkdir()
    for path in folder.iterdir():
        (old / path.name).write_bytes(path.read_bytes())
    v2 = {k: v for k, v in manifest.items() if k != "artifact"}
    v2["schema"] = delivery.BUNDLE_SCHEMA_V2
    (old / "manifest.json").write_bytes(canonical(v2))
    assert delivery.clean_rebuild(old)["status"] == "REBUILT"


# -- one mutation per guard ------------------------------------------------------------------------
def copy_counts_once(adapter_name=COOLING):
    """The guard, as one check: the copy probe holds on the real boundary."""
    probe = identity.copy_probe(adapter_for(adapter_name))
    held_and_fired(probe)


def test_mutation_count_by_text_turns_the_check_red(monkeypatch):
    """Mutant: distinct counts key on the construction as written
    (`construction_digest`), not the artifact."""
    real = identity.identity_of

    def by_text(row, family=None):
        if row.get("construction_digest"):
            return identity.ARTIFACT, row["construction_digest"]
        return real(row, family)

    monkeypatch.setattr(identity, "identity_of", by_text)
    with pytest.raises(AssertionError):
        copy_counts_once()


def test_mutation_artifact_by_record_digest_turns_the_check_red(monkeypatch):
    """Mutant: the artifact is the rebuilt record's digest, which carries
    digests of the recipe as written: a default made explicit looks new."""
    monkeypatch.setattr(
        identity,
        "artifact_of",
        lambda adapter, rebuilt, record=None: rebuilt.rebuilt_digest,
    )
    with pytest.raises(AssertionError):
        copy_counts_once(BATTERY)


def test_mutation_dedupe_by_text_turns_the_check_red(monkeypatch):
    """Mutant: the store keys distinct findings, "found" and specimens on
    the specimen text."""
    monkeypatch.setattr(
        knowledge,
        "_finding_key",
        lambda record: (
            record["challenge_id"],
            record["family"],
            record["condition"],
            canonical(record["specimen"]),
        ),
    )
    with pytest.raises(AssertionError):
        copy_counts_once()


def test_mutation_reward_a_reworded_copy_turns_the_check_red(monkeypatch):
    """Mutant: B2 credits each breached attempt, not each distinct finding."""
    monkeypatch.setattr(benchmark, "found", lambda line: line["verified"])
    with pytest.raises(AssertionError):
        copy_counts_once()
    with pytest.raises(AssertionError):
        test_the_report_and_b2_count_a_reworded_copy_once()


def test_the_store_and_the_engine_name_the_same_identity_rule():
    assert knowledge.IDENTITY_RULE == identity.RULE
    assert (
        knowledge.ARTIFACT_BASIS,
        knowledge.BEHAVIOUR_BASIS,
        knowledge.NO_BASIS,
    ) == (
        identity.ARTIFACT,
        identity.BEHAVIOUR,
        identity.NONE,
    )


def test_the_identity_module_names_no_challenge():
    source = Path(identity.__file__).read_text(encoding="utf-8").lower()
    for token in ("battery", "cooling", "cold-plate", "motor"):
        assert token not in source, token
