"""Graphite phase 3 and phase 4 at a construction level (`--level`).

GRAPHITE-DEV-VARIANTS-01, OWNER-GRAPHITE-TEST-WAVE-03 §1. Claims tested:

- Level 0 behaves exactly as before: the same permission profile and digest,
  the same brief, the same pod job configuration and Level 0's own compile
  path (`compile_submission`);
- a level above 0 resolves its registered variant from `DEV_VARIANTS`; an
  unregistered level is refused (`development_variant_unregistered`) before
  anything is read or spent, on both runners' command lines;
- at a development level the permission profile is the variant itself, the
  recorded level and variant are read back from the run's task, every
  proposal compiles through `development_variants.compile_development`, the
  pod job names the variant, and the pod's build and the bundle's clean
  rebuild go through the variant too;
- phase 4's attack adapter is keyed by (challenge, level): a level with no
  adapter is a typed refusal, and an adapter must attack its level's variant;
- a whole dry-run session at a development level runs end to end and records
  the variant as a development expansion on the controller.

Synthetic fixture variants, a fixture reconstruction, scripted models and
scripted pods only: no spend. Nothing here is scientific or security
acceptance.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import types

import pytest
from test_development_variants import BATTERY, FIXTURE_DIGESTS, install

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import phase3, phase4, pod_phase
from carbon.agent_campaign.graphite import pods as podlib
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.battery.research import SCAFFOLD
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv

UNREGISTERED = "development_variant_unregistered"
#: Every runner names its Challenge explicitly (#584): battery here.
SCORING = challenge_scoring.scoring_for(BATTERY)


def _refusal(capsys):
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    return json.loads(lines[-1])["reason_code"]


def _budget():
    return ex.phase3_budget(SpendingGrant.from_document(phase3.DRY_RUN_GRANT), SCORING)


def _strategy(**parameters):
    strategy = copy.deepcopy(SCAFFOLD)
    strategy.setdefault("parameters", {}).update(parameters)
    return strategy


@pytest.fixture
def variants(tmp_path, monkeypatch):
    return install(tmp_path / "registry", monkeypatch)


# --- Level 0 is unchanged ----------------------------------------------------------


def test_level_0_is_exactly_as_before(tmp_path):
    assert phase3.development_variant_for(0, SCORING) is None
    document, profile = phase3.permission_profile(SCORING)
    assert document == {
        "schema": phase3.PROFILE_SCHEMA,
        "level": 0,
        "construction_contract": ex.recorded_contract(SCORING),
        "surface": "declarative TrainingStrategy inside the recorded contract",
        "widens": [],
    }
    assert profile == digest(canonical(document))
    assert phase3.recorded_level({"task": {"profile_digest": profile}}, SCORING) == 0
    opened = {"task": {"profile_digest": profile}}
    assert phase3.recorded_variant(opened, SCORING) is None
    brief = phase3.session_brief(
        checkout_commit="0" * 40, budget=_budget(), scoring=SCORING
    )
    observation = brief.initial_observation
    assert observation["level"] == 0
    assert observation["construction_contract"] == ex.recorded_contract(SCORING)
    job = podlib.PodJob("i", {}, "sha256:" + "0" * 64, 1, {}, 1, 1)
    assert set(job.config(None)) == {
        "strategy",
        "contract_digest",
        "seed",
        "expected",
        "seconds",
        "stop_admitting_epoch",
    }
    assert "development" not in ex.admit(SCAFFOLD, 7, scoring=SCORING)


# --- an unregistered level is refused before anything runs ----------------------------


def check_unregistered_level_is_refused(tmp_path, capsys):
    tmp_path.mkdir(parents=True, exist_ok=True)
    # Levels 1-4 are registered in the shipped registry (GRAPHITE-L1-BUILD-01,
    # BATTERY-L2-SPECMUON-BUILD-01, BATTERY-L3-NUMERICS-BUILD-01,
    # LEVEL4-DEV-VARIANT-01); Level 5 has no variant.
    for level in (5,):
        with pytest.raises(SystemExit):
            phase3.development_variant_for(level, SCORING)
        assert _refusal(capsys) == UNREGISTERED
        with pytest.raises(SystemExit):
            phase4.development_variant_for(BATTERY, level)
        assert _refusal(capsys) == UNREGISTERED
    for level in (-1, "1"):
        with pytest.raises(SystemExit):
            phase3.development_variant_for(level, SCORING)
        assert _refusal(capsys) == "level_is_a_ladder_level"
    with pytest.raises(SystemExit):
        phase3.main(
            ["run", "--root", str(tmp_path), "--challenge", BATTERY]
            + ["--dry-run", "--level", "5"]
        )
    assert _refusal(capsys) == UNREGISTERED
    with pytest.raises(SystemExit):
        phase4.main(
            ["run", "--root", str(tmp_path), "--challenge", BATTERY]
            + ["--dry-run", "--level", "5"]
        )
    assert _refusal(capsys) == UNREGISTERED
    # Levels 2 and 3 are registered but have no attack adapter yet: the
    # Attacker refuses them before anything runs.
    with pytest.raises(SystemExit):
        phase4.main(
            ["run", "--root", str(tmp_path), "--challenge", BATTERY]
            + ["--dry-run", "--level", "3"]
        )
    assert _refusal(capsys) == "no_attack_adapter_for_challenge_level"
    assert list(tmp_path.iterdir()) == []  # nothing was read, written or spent


def test_an_unregistered_level_is_refused_before_anything_runs(tmp_path, capsys):
    check_unregistered_level_is_refused(tmp_path, capsys)


# --- phase 4: the attack adapter is keyed by (challenge, level) -------------------------


def check_attack_adapter_per_level(variants, capsys):
    # Battery Level 1 ships its own adapter (GRAPHITE-L1-BUILD-01); Level 2
    # has none, so it is the level that must be refused.
    variant = variants[2]
    with pytest.raises(SystemExit):
        phase4.adapter_for(phase4.attack_modules(), BATTERY, 2)
    assert _refusal(capsys) == "no_attack_adapter_for_challenge_level"
    from carbon.agent_campaign.attack import adapter as adapters

    with pytest.raises(adapters.AdapterError) as refused:
        adapters.get(BATTERY, 2)
    assert refused.value.code == "adapter_not_registered"
    # The shipped Level-1 adapter attacks the shipped variant, not a fixture.
    with pytest.raises(SystemExit):
        phase4.adapter_for(phase4.attack_modules(), BATTERY, 1)
    assert _refusal(capsys) == "attack_adapter_is_not_for_this_variant"

    def engine(contract_digest):
        attack = types.SimpleNamespace(contract_digest=contract_digest, level=2)
        registry = types.SimpleNamespace(ADAPTERS={(BATTERY, 2): attack})
        return {"adapter": registry}, attack

    atk, _wrong = engine(cr.contract(BATTERY).digest)
    with pytest.raises(SystemExit):
        phase4.adapter_for(atk, BATTERY, 2)
    assert _refusal(capsys) == "attack_adapter_is_not_for_this_variant"
    atk, attack = engine(variant.digest)
    assert phase4.adapter_for(atk, BATTERY, 2) == (attack, variant)
    assert phase4.attacker_profile(attack, variant) == (
        variant.document(),
        variant.digest,
    )


def test_a_level_needs_its_own_attack_adapter(variants, capsys):
    check_attack_adapter_per_level(variants, capsys)


def test_level_0s_attack_adapter_is_unchanged():
    atk = phase4.attack_modules()
    adapter, variant = phase4.adapter_for(atk, BATTERY, 0)
    assert variant is None
    assert adapter is phase4.get_adapter(atk, BATTERY, phase4.CONSTRUCTION_LEVEL)
    document, profile = phase4.attacker_profile(adapter)
    assert document["level"] == 0 and profile == digest(canonical(document))


# --- phase 3 at a development level ---------------------------------------------------


def test_a_development_levels_profile_brief_and_recorded_level(variants):
    variant = variants[2]
    assert phase3.development_variant_for(2, SCORING) == variant
    document, profile = phase3.permission_profile(SCORING, variant)
    assert (document, profile) == (variant.document(), variant.digest)
    opened = {"task": {"profile_digest": profile}}
    assert phase3.recorded_level(opened, SCORING) == 2
    assert phase3.recorded_variant(opened, SCORING) == variant
    assert (
        phase3.recorded_level({"task": {"profile_digest": FIXTURE_DIGESTS[1]}}, SCORING)
        == 1
    )
    assert phase3.recorded_level(
        {"task": {"profile_digest": "sha256:" + "e" * 64}}, SCORING
    ) is (None)
    brief = phase3.session_brief(
        checkout_commit="0" * 40, budget=_budget(), scoring=SCORING, variant=variant
    )
    observation = brief.initial_observation
    assert observation["level"] == 2
    assert observation["construction_contract"] == dv.recorded_variant(variant)
    phase3.check_observation(observation, SCORING)
    with pytest.raises(
        ProviderUnavailable, match="development_variant_is_another_level"
    ):
        phase3.check_observation(dict(observation, level=3), SCORING)
    named = dict(
        observation,
        construction_contract={
            **observation["construction_contract"],
            "development_variant": "sha256:" + "e" * 64,
        },
    )
    with pytest.raises(ProviderUnavailable, match=UNREGISTERED):
        phase3.check_observation(named, SCORING)


def test_a_variant_serves_only_its_own_challenge(variants, capsys):
    """A development level composes with the explicit-Challenge rule: a
    battery variant is never another Challenge's level."""
    other = next(
        challenge_scoring.scoring_for(token)
        for token in challenge_scoring.registered()
        if token != BATTERY
    )
    with pytest.raises(SystemExit):
        phase3.development_variant_for(1, other)
    assert _refusal(capsys) == UNREGISTERED
    with pytest.raises(SystemExit):
        phase3.permission_profile(other, variants[1])
    assert _refusal(capsys) == "development_variant_is_another_challenges"
    opened = {"task": {"profile_digest": variants[1].digest}}
    assert phase3.recorded_variant(opened, other) is None
    assert phase3.recorded_level(opened, other) is None
    with pytest.raises(SystemExit):
        phase4.development_variant_for(other.challenge_id, 1)
    assert _refusal(capsys) == UNREGISTERED


def check_development_admission(variants):
    variant = variants[2]
    strategy = _strategy(fixture_only_cycles=3)
    built = ex.admit(strategy, 7, scoring=SCORING, variant=variant)
    compiled = dv.compile_development(strategy, variant)
    assert built["development"] == compiled.development
    assert built["contract_digest"] == cr.contract(BATTERY).digest
    assert built["record_sequence"] == variant.base_record_sequence
    assert built["development_record_sequence"] == 1
    # The pod builds exactly what Carbon's host computed, through the variant.
    pod, _files, _program = pod_phase.development_built_record(
        strategy, built["contract_digest"], variant.digest, 7, ex.REPOSITORY
    )
    expected = {
        k: v
        for k, v in built.items()
        if k not in ("record_sequence", "development_record_sequence")
    }
    assert pod == expected
    assert ex.development_differences(built, pod) == []
    # A build without the variant's binding is a rebuild difference.
    plain = ex.admit(_strategy(), 7, scoring=SCORING)
    assert ex.development_differences(built, plain) == ["development"]
    # Level 0 never compiles the widened field; the variant's other value
    # binds differently.
    with pytest.raises(ex.Unrebuildable):
        ex.admit(strategy, 7, scoring=SCORING)
    other = ex.admit(
        _strategy(fixture_only_cycles=4), 7, scoring=SCORING, variant=variant
    )
    assert other["development"] != built["development"]
    with pytest.raises(dv.VariantRefused) as refused:
        pod_phase.development_built_record(
            strategy, "sha256:" + "0" * 64, variant.digest, 7, ex.REPOSITORY
        )
    assert refused.value.code == dv.BASE_STALE


def test_a_development_level_compiles_through_its_variant(variants):
    check_development_admission(variants)


def test_a_development_pod_job_names_its_variant(variants):
    job = podlib.PodJob(
        "i",
        {},
        "sha256:" + "0" * 64,
        1,
        {},
        1,
        1,
        development_variant=FIXTURE_DIGESTS[1],
    )
    assert job.config(None)["development_variant"] == FIXTURE_DIGESTS[1]


def test_a_development_dry_run_runs_end_to_end(variants, tmp_path, capsys, monkeypatch):
    import containment_double

    # The dry run's carrier containment check (synthetic passing double).
    containment_double.install(monkeypatch)
    root = tmp_path / "root"
    root.mkdir()
    assert phase3.dry_run(root, SCORING, development_variant=variants[1]) == 0
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{\n") :])
    assert result["provider_state"] == "succeeded"
    assert result["delivery"]["clean_rebuild"]["status"] == "REBUILT"
    run = root / "dry-run" / "graphite" / "runs" / result["run_id"]
    expected = [
        json.loads(p.read_bytes())
        for p in sorted((run / "experiment" / "proposals").glob("*/expected.json"))
    ]
    assert expected and all(
        e["development"]["variant_digest"] == variants[1].digest for e in expected
    )
    database = sqlite3.connect(root / "dry-run" / "controller" / "campaign.sqlite3")
    try:
        development = [
            json.loads(body)
            for (body,) in database.execute(
                "SELECT body FROM development_expansions ORDER BY sequence"
            )
        ]
        expansions = database.execute("SELECT COUNT(*) FROM expansions").fetchone()[0]
    finally:
        database.close()
    assert [e["permissions"] for e in development] == [variants[1].digest]
    assert expansions == 0  # never Track A's LOCK ledger


# --- switching each guard off fails its test -------------------------------------------


def _level_0_compile(m):
    from carbon.challenge_validator import scoring as challenge_scoring

    def admit(scoring, strategy, seed, root, variant_):
        return challenge_scoring.admit(scoring, strategy, seed, root)

    m.setattr(dv, "admit", admit)


@pytest.mark.parametrize(
    "name", ["unregistered_level", "attack_adapter", "development_compile"]
)
def test_switching_a_guard_off_fails_its_test(name, tmp_path, monkeypatch, capsys):
    if name == "unregistered_level":
        check_unregistered_level_is_refused(tmp_path / "intact", capsys)
        monkeypatch.setattr(dv, "variant", lambda challenge, level: None)
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            check_unregistered_level_is_refused(tmp_path / "mutated", capsys)
        return
    found = install(tmp_path / "registry", monkeypatch)
    if name == "attack_adapter":
        check_attack_adapter_per_level(found, capsys)
        monkeypatch.setattr(
            phase4,
            "get_adapter",
            lambda atk, challenge, level: types.SimpleNamespace(
                contract_digest=found[1].digest, level=level
            ),
        )
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            check_attack_adapter_per_level(found, capsys)
        return
    check_development_admission(found)
    _level_0_compile(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception, ex.Unrebuildable)):
        check_development_admission(found)
