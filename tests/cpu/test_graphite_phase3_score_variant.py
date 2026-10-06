"""Graphite phase 3 under a development score variant (VALIDATOR-09 slice 2).

A registered development score variant is resolved before any spend, pinned
in the brief and the permission profile, recorded by the controller (the
profile digest), frozen into the provider's rule and on every result, summary
and delivery, and checked on resume. Phase 4 refuses one. Without the flag
nothing changes (the pinned replays in `test_graphite_phase3.py` hold too).

The variants here are FIXTURE documents in a test registry, scored through
the Challenge's own score-tuning module (#650), under battery's declared
practice value contract (EV4's development decision contract, the Test Lead
on #668). Synthetic predictions; nothing here is scientific evidence.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from graphite_phase3_fixtures import (
    SCORING,
    controller,
    propose,
    provider,
    run_id,
    steps,
    text,
    variant,
)

from carbon.agent_campaign.graphite import phase3, phase4
from carbon.agent_campaign.graphite import score_variant as sv
from carbon.agent_campaign.graphite.pods import ScriptedPods
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.reconstruction import capability_registry as cr
from carbon.scoring import development_score_variants as dsv

BATTERY = "battery-fastcharge-ageing-development-v1"
VERSION = "fixture-battery-score-variant-v1"
OTHER = "fixture-battery-score-variant-v2"
#: Battery's declared practice value contract (#668): EV4's.
EV4_FILE = "ev4-charge-protocol-selection.v1.json"
EV4 = "sha256:fedd753c0e7aa69d2fd4d6efbf3d877ac8eeb211859d9f32d76a61f38bbe38d1"
ENTRY = {
    "id": "fixture-near-weighted",
    "kind": "geometric",
    "weights": {"a": 0.5, "n": 0.5},
    "gate": {"measure": "near", "cutoff": 2.0},
    "stable": False,
    "basis": "FIXTURE: test only",
}


def document(version=VERSION, **changes):
    value = {
        "schema": dsv.SCHEMA,
        "version": version,
        "challenge_id": BATTERY,
        "base_rule": "battery-practice-v2",
        "candidate": dict(ENTRY),
        "candidate_registry": {"sha256": "a" * 64, "commit": "b" * 40},
        "scope": dsv.SCOPE,
        "status": "SURVIVOR",
        "authority": {"promoted_from": "FIXTURE"},
        # The practice value contract it was registered against (#654).
        "practice_value_contract": EV4,
        "fixture": True,
    }
    value.update(changes)
    return value


def write_registry(directory, *documents):
    directory.mkdir(parents=True, exist_ok=True)
    variants = {}
    for item in documents:
        (directory / f"{item['version']}.json").write_text(json.dumps(item))
        variants[item["version"]] = dsv.digest(item)
    (directory / "registry.json").write_text(
        json.dumps({"schema": dsv.REGISTRY_SCHEMA, "variants": variants})
    )
    return directory


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Two fixture variants in a test registry, read by the runner and by
    every miner door's name check."""
    directory = write_registry(
        tmp_path / "score-variants",
        document(),
        document(OTHER, candidate={**ENTRY, "id": "fixture-accuracy"}),
    )
    monkeypatch.setattr(sv, "_directory", lambda: directory)
    monkeypatch.setattr(cr, "DEVELOPMENT_SCORE_VARIANT_DIR", directory)
    return directory


def reregister(directory, *documents):
    """Register `documents` (replacing the fixture registry)."""
    for path in directory.glob("*.json"):
        path.unlink()
    write_registry(directory, *documents)


def resolved(version=VERSION):
    return sv.resolve(version, SCORING)


def refused_code(capsys):
    """The reason code a `RunnerRefused` printed (it exits 2)."""
    line = capsys.readouterr().out.strip().splitlines()[-1]
    printed = json.loads(line)
    assert printed["status"] == "REFUSED", printed
    return printed["reason_code"]


# --- 1. resolved, typed, before any spend --------------------------------------------


def _no_spend(monkeypatch):
    def spent(*args, **kwargs):
        raise AssertionError("reached a grant, pod or model before the refusal")

    monkeypatch.setattr(phase3, "load_grant", spent)
    monkeypatch.setattr(phase3, "dry_run", spent)


@pytest.mark.parametrize("dry", [True, False])
@pytest.mark.parametrize(
    ("version", "code"),
    [
        ("never-registered", "score_variant_unregistered"),
        ("../" + VERSION, "score_variant_unregistered"),
    ],
)
def test_an_unregistered_variant_is_refused_before_any_spend(
    registry, monkeypatch, tmp_path, capsys, dry, version, code
):
    _no_spend(monkeypatch)
    argv = ["run", "--root", str(tmp_path / "root"), "--challenge", BATTERY]
    argv += ["--dry-run"] if dry else ["--grant", "g", "--credential-file", "c"]
    argv += ["--runpod-key-file", "k", "--code-ref", "0" * 40]
    with pytest.raises(phase3.RunnerRefused):
        phase3.main([*argv, "--score-variant", version])
    assert refused_code(capsys) == code


def test_an_altered_variant_is_refused(registry):
    path = registry / f"{VERSION}.json"
    path.write_text(json.dumps(document(status="CANDIDATE")))
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        resolved()
    assert refused.value.code == "score_variant_altered"


def test_another_challenges_session_refuses_the_variant(registry):
    cooling = challenge_scoring.scoring_for("chip-cold-plate")
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        sv.resolve(VERSION, cooling)
    assert refused.value.code == "score_variant_is_another_challenges"


def test_a_development_level_refuses_a_score_variant(registry, capsys):
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        sv.resolve(VERSION, SCORING, level=1)
    assert refused.value.code == sv.LEVEL0_ONLY
    with pytest.raises(phase3.RunnerRefused):
        phase3.permission_profile(SCORING, object(), resolved().identity())
    assert refused_code(capsys) == sv.LEVEL0_ONLY


def test_battery_declares_ev4s_practice_contract_by_its_digest(registry):
    """The Test Lead on #668: EV4's development decision contract, pinned once
    as battery Challenge data, never EV5's frozen confirmation or a panel
    copy. The declared digest is the committed file's."""
    from carbon.battery.value import contract

    assert SCORING.practice_value_contract == EV4
    assert SCORING.practice_value_contract_file == EV4_FILE
    assert contract.load(contract.CONTRACTS / EV4_FILE)[1] == EV4
    assert sv.practice_contract(SCORING) == (EV4_FILE, EV4)
    assert resolved().identity()["practice_value_contract"] == EV4


def _without_contract():
    value = document()
    del value["practice_value_contract"]
    return value


@pytest.mark.parametrize(
    ("item", "code"),
    [
        # #654's own refusals, through the runner (decision 6).
        (_without_contract(), "score_variant_malformed"),
        (
            document(practice_value_contract="sha256:" + "0" * 64),
            "score_variant_practice_value_contract_not_pinned",
        ),
    ],
)
def test_a_variant_registered_against_another_contract_is_refused(
    registry, capsys, item, code
):
    reregister(registry, item)
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        resolved()
    assert refused.value.code == code
    with pytest.raises(phase3.RunnerRefused):
        phase3.score_variant_for(VERSION, SCORING)
    assert refused_code(capsys) == code


def test_ev5s_digest_is_not_battery_practice_contract(registry):
    from carbon.battery.value import contract

    ev5 = contract.load(contract.CONTRACTS / "ev5-charge-protocol-selection.v1.json")
    reregister(registry, document(practice_value_contract=ev5[1]))
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        resolved()
    assert refused.value.code == "score_variant_practice_value_contract_not_pinned"


def test_a_challenge_without_a_declared_contract_is_unpinned(registry, monkeypatch):
    cooling = challenge_scoring.scoring_for("chip-cold-plate")
    assert cooling.practice_value_contract is None
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        sv.practice_contract(cooling)
    assert refused.value.code == "score_variant_practice_contract_unpinned"
    # #654 accepts a variant when the Challenge pins nothing; the runner
    # still refuses it.
    monkeypatch.setattr(type(SCORING), "practice_value_contract", None)
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        resolved()
    assert refused.value.code == "score_variant_practice_contract_unpinned"


def test_a_declared_digest_the_file_does_not_have_is_refused(monkeypatch):
    monkeypatch.setattr(type(SCORING), "practice_value_contract", "sha256:" + "1" * 64)
    with pytest.raises(sv.ScoreVariantRefused) as refused:
        sv.practice_contract(SCORING)
    assert refused.value.code == "score_variant_practice_contract_altered"


def test_the_shipped_registry_resolves_nothing(capsys):
    assert dsv.registered() == {}
    with pytest.raises(phase3.RunnerRefused):
        phase3.score_variant_for("anything", SCORING)
    assert refused_code(capsys) == "score_variant_unregistered"
    assert phase3.score_variant_for(None, SCORING) is None


# --- 2-3. pinned, recorded, frozen and labelled ---------------------------------------


def scored_session(root, score=None, pods=None, brief_variant="same"):
    """One Level-0 session with one proposal, under `score` (a resolved
    variant or None); `brief_variant` pins another identity in the brief."""
    graphite = provider(
        root,
        [propose(variant(width=128)), text("done")],
        pods if pods is not None else ScriptedPods(steps=steps(1.0, 0.4)),
        **({} if score is None else {"score_variant": score}),
    )
    pinned = sv.identity_of(score) if brief_variant == "same" else brief_variant
    brief = phase3.session_brief(
        checkout_commit="1" * 40,
        budget=graphite.budget,
        literature=graphite.literature,
        **({} if pinned is None else {"score_variant": pinned}),
    )
    control = controller(root, graphite)
    try:
        result = phase3.run_session(control, graphite, brief, 1)
        with control._db() as db:
            campaign = control._campaign(db, phase3.CAMPAIGN)
    finally:
        control.close()
    return result, graphite, brief, campaign


def results(graphite):
    experiment = graphite.experiment(run_id())
    return [experiment.record(r["proposal_id"]) for r in experiment.records()]


def test_a_session_under_a_variant_pins_freezes_and_labels_it(registry, tmp_path):
    score = resolved()
    identity = score.identity()
    result, graphite, brief, campaign = scored_session(tmp_path, score)
    assert result["provider_state"] == "succeeded", result
    # Pinned: the brief and the Level-0 permission profile, which the
    # controller records by digest.
    assert brief.initial_observation["score_variant"] == identity
    document, profile = phase3.permission_profile(SCORING, score_variant=identity)
    assert document["score_variant"] == identity and document["level"] == 0
    assert profile != phase3.permission_profile(SCORING)[1]
    assert campaign["profile"] == profile
    opened = graphite._opened(run_id())
    assert opened["task"]["profile_digest"] == profile
    assert phase3.recorded_level(opened, SCORING, identity) == 0
    # Frozen: the provider's rule is the variant's, over the base rule.
    rule = graphite._frozen_rule()
    assert type(rule) is sv.VariantRule
    assert rule.identity["score_variant"] == identity
    # Labelled: every result, the summary and the delivery.
    records = results(graphite)
    scored = [r for r in records if r["status"] == "SCORED"]
    assert {"baseline", "proposal"} <= {r["kind"] for r in scored}
    # Every result is labelled, scored or not (delivery's ablation here has
    # no scripted pod and closes unscored).
    assert all(r["label"] == identity["label"] for r in records)
    for record in scored:
        assert record["rule"]["score_variant"] == identity
        assert set(record["score_variant"]) == {*identity, "score", "gate"}
        assert record["score_variant"]["score_variant_digest"] == score.digest
    proposal = next(r for r in scored if r["kind"] == "proposal")
    against = proposal["against_baseline"]["score_variant"]
    assert against["label"] == identity["label"] and against["promotable"] is False
    assert against["outcome"] in {
        "ABOVE_BASELINE",
        "BELOW_BASELINE",
        "EQUAL",
        "BOTH_GATE_FAILED",
        "NOT_SCORABLE",
    }
    assert result["summary"]["score_variant"] == identity
    assert result["delivery"]["label"] == identity["label"]
    # The base rule still decides: its comparison is unchanged in shape.
    assert {"outcome", "promotable"} <= set(proposal["against_baseline"])


def test_the_variant_result_is_the_registered_scorers_own(registry, tmp_path):
    """The record's variant score is `score_member` on `member_legs` of the
    same predictions: one definition, byte-identical."""
    from carbon.battery.practice import practice_store
    from carbon.battery.value import contract
    from carbon.battery.value import score_tuning as st

    score = resolved()
    rule = sv.VariantRule(phase3.ex.frozen_rule(phase3.REPOSITORY, SCORING), score)
    predictions = SCORING.synthetic_predictions(0.4, phase3.REPOSITORY)
    _rows, summary = rule.score(predictions)
    base = rule.base
    row = st.member_legs(
        contract.load(contract.CONTRACTS / EV4_FILE)[0],
        predictions,
        practice_store(base.practice, base.material, base.root),
        list(base.practice.case_ids),
    )
    assert summary["score_variant"] == challenge_scoring.clean(
        dsv.score_member(score, row)
    )
    assert rule.identity["score_variant"]["practice_value_contract"] == EV4


def test_feedback_shows_the_variant_result_and_label(registry, tmp_path):
    from carbon.agent_campaign.graphite import experiment as ex

    _result, graphite, _brief, _campaign = scored_session(tmp_path, resolved())
    records = results(graphite)
    assert sum(r["status"] == "SCORED" for r in records) >= 2
    for record in records:
        view = ex._feedback_view(record)
        assert view["label"] == record["label"]
        if record["status"] == "SCORED":
            assert view["score_variant"] == record["score_variant"]


def test_the_agent_is_fed_the_variant_score_while_promotion_stays_on_base(
    registry, tmp_path, monkeypatch
):
    """The Test Lead on #668: during a variant session the agent's practice
    feedback is the VARIANT's score, labelled with its identity, so Graphite
    optimises the variant; promotion and the comparison stay on the base
    rule. The feedback captured is exactly what the propose tool returned."""
    from carbon.agent_campaign.graphite import experiment as ex

    returned = []
    real = ex._feedback_view

    def captured(record):
        view = real(record)
        returned.append((record["proposal_id"], view))
        return view

    monkeypatch.setattr(ex, "_feedback_view", captured)
    score = resolved()
    label = score.identity()["label"]
    _result, graphite, _brief, _campaign = scored_session(tmp_path, score)
    experiment = graphite.experiment(run_id())
    proposal_id, view = next((pid, v) for pid, v in returned if v["kind"] == "proposal")
    record = experiment.record(proposal_id)
    assert record["status"] == "SCORED"
    variant_score = record["score_variant"]["score"]
    base_score = record["frozen_rule"]["score"]
    # The variant's score differs from the base rule's, and the agent sees
    # the variant's as its score, labelled; the base score is withheld.
    assert variant_score is not None and base_score is not None
    assert variant_score != base_score
    assert view["score"] == variant_score
    assert view["score_label"] == label and view["label"] == label
    assert view["score_gate"] == record["score_variant"]["gate"]
    assert "score" not in view["frozen_rule"]
    assert "components" not in view["frozen_rule"]
    assert view["frozen_rule"]["eligible"] == record["frozen_rule"]["eligible"]
    against = view["against_baseline"]
    assert set(against) == {"promotable", "promotion_rule", "score_variant"}
    assert "mean_delta" not in against and "ci" not in against
    assert view["baseline"]["score"] == against["score_variant"]["baseline_score"]
    # Promotion stays on the base rule: the record's and the agent's
    # `promotable` are the base rule's own comparison.
    baseline_id = experiment.baseline_id()
    base = graphite._frozen_rule().base
    expected = base.compare(
        experiment.rows(baseline_id),
        experiment.rows(proposal_id),
        bool(record["frozen_rule"]["eligible"]),
    )
    assert record["against_baseline"]["promotable"] == expected["promotable"]
    assert record["against_baseline"]["outcome"] == expected["outcome"]
    assert against["promotable"] == expected["promotable"]
    assert against["promotion_rule"] == "base"


def test_without_a_variant_the_agent_feedback_is_unchanged(tmp_path):
    from carbon.agent_campaign.graphite import experiment as ex

    _result, graphite, _brief, _campaign = scored_session(tmp_path)
    for record in results(graphite):
        view = ex._feedback_view(record)
        assert "score" not in view and "score_label" not in view
        if record["status"] == "SCORED":
            assert view["frozen_rule"] == record["frozen_rule"]
            if "against_baseline" in record:
                assert view["against_baseline"] == record["against_baseline"]


# --- 4. resume -----------------------------------------------------------------------


@pytest.mark.parametrize("resume_under", [None, OTHER])
def test_a_resume_under_another_variant_is_refused(registry, tmp_path, resume_under):
    scored_session(tmp_path, resolved())
    other = None if resume_under is None else resolved(resume_under)
    graphite = provider(
        tmp_path,
        [text("done")],
        ScriptedPods(steps=[]),
        **({} if other is None else {"score_variant": other}),
    )
    with pytest.raises(phase3.ResumeRefused) as refused:
        phase3.check_resume(graphite, 1)
    assert refused.value.code == "score_variant_changed_since_the_session_opened"
    # The same variant resumes.
    same = provider(
        tmp_path, [text("done")], ScriptedPods(steps=[]), score_variant=resolved()
    )
    phase3.check_resume(same, 1)


def test_a_session_opened_without_a_variant_refuses_one_on_resume(registry, tmp_path):
    scored_session(tmp_path)
    graphite = provider(
        tmp_path, [text("done")], ScriptedPods(steps=[]), score_variant=resolved()
    )
    with pytest.raises(phase3.ResumeRefused) as refused:
        phase3.check_resume(graphite, 1)
    assert refused.value.code == "score_variant_changed_since_the_session_opened"


def test_a_brief_naming_another_variant_never_runs(registry, tmp_path):
    with pytest.raises(ValueError, match="another score variant"):
        scored_session(tmp_path, resolved(), brief_variant=resolved(OTHER).identity())
    with pytest.raises(ValueError, match="another score variant"):
        scored_session(tmp_path / "none", None, brief_variant=resolved().identity())


def test_a_run_pinned_to_another_variant_never_scores(registry, tmp_path):
    graphite = provider(
        tmp_path, [text("done")], ScriptedPods(steps=[]), score_variant=resolved()
    )
    refused = graphite._session_scorer(resolved(OTHER).identity())
    with pytest.raises(ProviderUnavailable, match="score_variant_is_not_the_sessions"):
        refused()
    assert graphite._session_scorer(resolved().identity()) == graphite._frozen_rule


def test_a_variant_never_wraps_an_injected_scorer(registry, tmp_path):
    with pytest.raises(ProviderUnavailable, match="wraps_the_frozen_rule_only"):
        provider(
            tmp_path,
            [],
            ScriptedPods(steps=[]),
            scorer=object(),
            score_variant=resolved(),
        )


# --- the variant comparison: an order, gate failures last ------------------------------


def _result(score, gate, digest):
    return {"score": score, "gate": gate, "score_variant_digest": digest}


def test_a_gate_fail_ranks_last_and_nothing_is_promotable(registry):
    score = resolved()
    base = SimpleNamespace(identity={"rule": "fixture"})
    rule = sv.VariantRule(base, score, legs=lambda p: None)
    fail, digest = rule.fail_verdict(), score.digest
    passing = "PASS" if fail != "PASS" else "OK"
    cases = [
        (_result(0.9, fail, digest), _result(0.1, passing, digest), "ABOVE_BASELINE"),
        (_result(0.1, passing, digest), _result(0.9, fail, digest), "BELOW_BASELINE"),
        (_result(0.1, fail, digest), _result(0.9, fail, digest), "BOTH_GATE_FAILED"),
        (_result(0.5, None, digest), _result(0.6, None, digest), "ABOVE_BASELINE"),
        (_result(0.6, None, digest), _result(0.5, None, digest), "BELOW_BASELINE"),
        (_result(0.5, None, digest), _result(0.5, None, digest), "EQUAL"),
        (_result(None, None, digest), _result(0.5, None, digest), "NOT_SCORABLE"),
        (None, _result(0.5, None, digest), "NO_BASELINE_UNDER_THIS_VARIANT"),
        (
            _result(0.5, None, "sha256:" + "0" * 64),
            _result(0.6, None, digest),
            "NO_BASELINE_UNDER_THIS_VARIANT",
        ),
    ]
    for baseline, result, outcome in cases:
        compared = rule.compare_variant(baseline, result)
        assert compared["outcome"] == outcome, (baseline, result)
        assert compared["promotable"] is False


# --- 5. phase 4 refuses --------------------------------------------------------------


def test_phase4_refuses_a_score_variant_before_anything(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        phase4,
        "attack_modules",
        lambda: pytest.fail("phase 4 read its adapters before refusing"),
    )
    with pytest.raises(phase4.RunnerRefused):
        phase4.main(
            [
                "run",
                "--root",
                str(tmp_path),
                "--challenge",
                BATTERY,
                "--dry-run",
                "--score-variant",
                VERSION,
            ]
        )
    assert refused_code(capsys) == "attacker_score_variant_not_supported"


def test_the_attacker_provider_refuses_a_score_variant():
    with pytest.raises(
        ProviderUnavailable, match="attacker_score_variant_not_supported"
    ):
        phase4.AttackerProvider(
            root=None,
            grant=None,
            model=None,
            pods=None,
            adapter=None,
            score_variant=object(),
        )


# --- 6. no flag, no change -----------------------------------------------------------


def test_without_the_flag_nothing_is_added(tmp_path):
    result, graphite, brief, campaign = scored_session(tmp_path)
    assert "score_variant" not in brief.initial_observation
    document, profile = phase3.permission_profile(SCORING)
    assert "score_variant" not in document and campaign["profile"] == profile
    assert type(graphite._frozen_rule()) is not sv.VariantRule
    for record in results(graphite):
        assert "label" not in record and "score_variant" not in record
        assert "score_variant" not in record.get("rule", {})
        assert "score_variant" not in record.get("against_baseline", {})
    assert "score_variant" not in result["summary"]
    assert "label" not in result["delivery"]
    assert phase3.score_variant_for(None, SCORING) is None
