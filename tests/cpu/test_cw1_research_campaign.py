"""Controller contracts only; no fake transcripts are campaign inference."""

import json

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_campaign import (
    CONTROL,
    frozen_seeds,
    private_file,
    trial_supports_selection,
)
from carbon.development_session.research_catalog import compile_recipe
from carbon.development_session.research_tasks import PublicResearchExecutor
from carbon.development_session.research_tools import PREFIX, ResearchMinerTools


def test_control_is_registered_and_final_seeds_do_not_change_on_resume(tmp_path):
    compiled, profile = compile_recipe(CONTROL)
    assert json.loads(profile.task_config_json)["enforce_mean"] is True
    assert compiled.construction_plan.strategy_hash.value
    seeds = frozen_seeds(tmp_path)
    assert frozen_seeds(tmp_path) == seeds
    assert (
        len({s for epoch in seeds.values() for group in epoch.values() for s in group})
        == 12
    )
    path = tmp_path / "private-final-seeds.json"
    body = json.loads(path.read_bytes())
    body["2"]["challenger"][2] = body["1"]["baseline"][0]
    path.write_bytes(canonical(body))
    with pytest.raises(ValueError, match="distinct"):
        frozen_seeds(tmp_path)


def test_selected_recipe_needs_real_practice_and_integrity(tmp_path):
    meter = ledger(tmp_path)
    PublicResearchExecutor(
        ledger=meter, owner="alice", image=None, public_material=None, practice=None
    )
    assert not trial_supports_selection(meter, "alice", CONTROL)

    def insert(value):
        body = canonical(value)
        with meter.db() as db:
            db.execute(
                "INSERT OR REPLACE INTO research_results VALUES(?,?,?,?)",
                ("alice", "test-fixture", body, digest(body)),
            )

    insert({"provenance": "FIXTURE_ONLY", "recipe": CONTROL})
    assert not trial_supports_selection(meter, "alice", CONTROL)
    # Synthetic record tests the guard only; it is not a real practice observation.
    insert({"provenance": "REAL_JAX_PUBLIC_PRACTICE", "recipe": CONTROL})
    assert trial_supports_selection(meter, "alice", CONTROL)
    assert not trial_supports_selection(meter, "other", CONTROL)
    with meter.db() as db:
        db.execute("UPDATE research_results SET digest='altered'")
    with pytest.raises(ValueError, match="changed"):
        trial_supports_selection(meter, "alice", CONTROL)


def test_invalid_numerical_attempt_consumes_one_slot_and_replay_does_not_repeat(
    tmp_path,
):
    import asyncio

    meter = ledger(tmp_path)
    sdk = ResearchMinerTools(
        connection=None, wrapper=None, composition=None, ledger=meter, owner="alice"
    )
    args = {"kind": "practice", "extra": "invalid closed fields"}
    for _ in range(2):
        result = asyncio.run(
            sdk.call(PREFIX + "start_research_task", args, "invalid-proposal")
        )
        assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert meter.status(owner="alice")["used"]["research_trials"] == 1


def test_private_credential_file_never_accepts_world_readable_or_symlink(tmp_path):
    path = tmp_path / "key"
    path.write_text("engineering-placeholder")
    path.chmod(0o644)
    with pytest.raises(ValueError):
        private_file(path)
    path.chmod(0o600)
    assert private_file(path) == path
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        private_file(link)


def test_practice_score_uses_same_arithmetic_without_inventing_replicas():
    from test_cw1_development_scoring import rows

    from carbon.scoring.development import RULE, practice_diagnostics, summarize

    values = rows()
    one = [r for r in values if r["replica"] == 0]
    measures = [r["measurement"] for r in one]
    scales = [
        {"role": r["role"], "cell": int(r["case"].rsplit("-", 1)[1])} for r in one
    ]
    result = practice_diagnostics(measures, scales)
    assert result["descriptive_score"] == summarize(values)["score"]
    assert (
        result["final_admissibility"] is None
        and result["accepted_improvement"] is False
    )
    assert all(r["replicas"] == 1 for r in result["roles"].values())
    measures[-1]["metrics"]["conserved_mean"] = RULE["hard_limits"]["conserved_mean"]
    assert (
        "STRESS:conserved_mean"
        in practice_diagnostics(measures, scales)["sampled_gate_failures"]
    )
    with pytest.raises(ValueError, match="complete"):
        practice_diagnostics(measures[:-1], scales[:-1])


def test_reward_lineage_is_not_reopened_for_fresh_epoch(tmp_path, monkeypatch):
    from dataclasses import dataclass

    from carbon.development_comparison.acceptance import DevelopmentAcceptanceRef
    from carbon.development_session import research_rewards as owner

    @dataclass
    class SyntheticSimulation:
        provenance: str = "SYNTHETIC_TEST_ONLY"

    monkeypatch.setattr(
        owner,
        "resolve_acceptance",
        lambda ref: {"decision": {"accepted_improvement": True}},
    )
    monkeypatch.setattr(owner, "simulate", lambda *a, **k: SyntheticSimulation())
    first = DevelopmentAcceptanceRef(tmp_path / "first", "registration", "first")
    second = DevelopmentAcceptanceRef(tmp_path / "second", "registration", "second")
    a = owner.update_simulation(tmp_path, first, epoch=1)
    assert (
        a["opening_credit"] == 0 and a["result"]["provenance"] == "SYNTHETIC_TEST_ONLY"
    )
    b = owner.update_simulation(tmp_path, second, epoch=2)
    assert (
        b["status"] == "WITHHELD_INCOMPATIBLE_INCUMBENT_LINEAGE"
        and b["opening_reset"] is False
    )


def test_old_worker_image_is_rejected_before_campaign_dispatch():
    from types import SimpleNamespace

    from carbon.development_session.research_campaign import verify_current_worker

    with pytest.raises(ValueError, match="exact accepted"):
        verify_current_worker(
            SimpleNamespace(source_tree_digest="old"),
            {"source_tree_digest": "accepted"},
        )
    verify_current_worker(
        SimpleNamespace(source_tree_digest="accepted"),
        {"source_tree_digest": "accepted"},
    )


def test_provider_timeout_must_fit_remaining_elapsed_envelope(tmp_path):
    from carbon.development_session.agent import MAX_OUTPUT_TOKENS, MODEL
    from carbon.development_session.research_agent import request_model
    from carbon.development_session.research_ledger import DEVELOPMENT_ELAPSED_SECONDS

    meter = ledger(tmp_path, clock=lambda: 1000)
    meter.reserve("start", owner="alice", phase="selection", request={}, resources={})
    meter.finish("start", owner="alice", state="SUCCEEDED", actual={}, result={})
    meter.clock = lambda: 1000 + DEVELOPMENT_ELAPSED_SECONDS - 119
    request = {
        "model": MODEL,
        "instructions": "test",
        "input": [],
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": "low"},
    }
    with pytest.raises(ValueError, match="timeout"):
        request_model(
            meter,
            owner="alice",
            identity="late",
            request=request,
            credential_file=None,
            transport=lambda req: pytest.fail("expired dispatch"),
        )
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 0
