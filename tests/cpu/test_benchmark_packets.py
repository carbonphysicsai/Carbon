"""Specification checks only; no novelty gate, bank draw or reference execution."""

import json
import re
import subprocess
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs/development/challenge_pipeline/benchmark-packets"
TOKENS = ("backward-facing-step", "metagrating-3d")
DECISIONS = {
    "buyer_decision_and_limits",
    "geometry_and_action_grammar",
    "conditions_material_support",
    "P",
    "Q",
    "w",
    "measurement_and_objective",
    "reference_package_and_models",
    "reference_acceptance_and_witnesses",
    "novelty_catalogue",
    "novelty_equivalence_and_normalizers",
    "novelty_acceptance",
    "frontier_power_and_ties",
    "question_and_bank_counts",
    "panel_registration_and_reuse",
    "construction_training_and_rights",
    "execution_and_adoption",
}
SECTIONS = (
    "Engineering job",
    "Physical system",
    "Population P, Q and w",
    "Case contract",
    "Reference policy",
    "Output and measurement contract",
    "Construction contract",
    "Research kit",
    "Evidence plan",
    "Readiness and claim record",
)


def read(name):
    return (FOLDER / name).read_text(encoding="utf-8")


def inventory(token):
    return json.loads(read(token + "-owner-decisions.json"))


@pytest.mark.parametrize("token", TOKENS)
def test_full_packet_maps_all_ten_sections_and_does_not_claim_an_earned_tier(token):
    packet = read(token + ".md")
    headings = re.findall(r"^## (\d+)\. (.+)$", packet, re.MULTILINE)
    assert headings == [(str(n), title) for n, title in enumerate(SECTIONS, 1)]
    assert "HUMAN_INPUT" in packet and "NOT_DEMONSTRATED" in packet
    assert "Tier 2" in packet and "No reference solve" in packet
    assert "not a" in packet and "runtime" in packet
    assert "cheap" in packet and "equal-budget" in packet


@pytest.mark.parametrize("token", TOKENS)
def test_one_closed_owner_inventory_keeps_every_reserved_choice_unselected(token):
    data = inventory(token)
    assert set(data) == {
        "schema",
        "ticket",
        "family",
        "maturity",
        "decision_status",
        "runtime_config",
        "source_basis",
        "artifacts",
        "adopted_method",
        "registered_panel",
        "decisions",
    }
    assert data["schema"] == "carbon.benchmark-packet.owner-decisions.v1"
    assert data["ticket"] == "BENCHMARK-PACKETS-01"
    assert data["family"] == token and data["maturity"] == "SPECIFIED"
    assert data["decision_status"] == "HUMAN_INPUT"
    assert data["runtime_config"] is False
    assert len(data["decisions"]) == len(DECISIONS)
    assert {d["id"] for d in data["decisions"]} == DECISIONS
    for decision in data["decisions"]:
        assert set(decision) == {
            "id",
            "status",
            "value",
            "owner",
            "recommendation",
            "source",
            "blocks",
        }
        assert decision["status"] == "HUMAN_INPUT" and decision["value"] is None
        assert all(
            decision[key].strip() for key in ("owner", "recommendation", "blocks")
        )
        assert (FOLDER / decision["source"].split("#")[0]).is_file()
    separate = {d["id"]: d for d in data["decisions"] if d["id"] in {"P", "Q", "w"}}
    assert len({d["recommendation"] for d in separate.values()}) == 3


@pytest.mark.parametrize("token", TOKENS)
def test_policy_adoption_cannot_be_confused_with_approval_or_dispatch(token):
    data = inventory(token)
    assert data["adopted_method"] == {
        "anchors_scored": False,
        "physically_equivalent_copies_excluded": True,
        "family_novelty_required": True,
        "anomaly_means_misconduct": False,
        "new_reference_changes_sealed_results": False,
    }
    assert data["registered_panel"] == {
        "status": "PROPOSED_NOT_DISPATCHABLE",
        "cases": [],
        "case_count": None,
        "reuse_status": "UNKNOWN_NO_INDEX",
        "dispatch_authorized": False,
        "spend_authorized": False,
    }
    for path in data["artifacts"].values():
        assert (FOLDER / path).is_file()
    for key in ("policy_adoption", "source_register"):
        assert (ROOT / data["source_basis"][key]).is_file()


@pytest.mark.parametrize("token", TOKENS)
def test_laws_separate_question_counts_exposure_and_unresolved_none_feasible(token):
    law = " ".join(read(token + "-law.md").replace("**", "").split())
    assert all(term in law for term in ("## P:", "## Q:", "## w:"))
    assert "carbon/design_search/tasks.py" in law
    assert "questions per batch" in law and "action count" in law
    assert "NONE_FEASIBLE" in law and "UNRESOLVED" in law
    assert "redraw" in law and "two accepted" in law
    assert "five distinct feasible" in law and "five distinct infeasible" in law
    assert "NOT_DEMONSTRATED" in law
    assert "min(k," in law
    assert "exposure" in law and "renew E" in law


def test_family_specific_novelty_preserves_geometry_and_physical_input_semantics():
    step = read("backward-facing-step.md")
    assert "Re_H" in step and "Re_theta" in step and "developed inlet" in step
    assert "SSTm" in step and "shifted Cp" in step
    assert "Require a" in step and "geometry component" in step
    optics = read("metagrating-3d.md")
    assert "full 3D electromagnetic job" in optics
    assert "both x and y" in optics and "cross-polarization" in optics
    assert "Do **not** recompute Px" in optics
    assert "mirror" in optics and "nondispersive" in optics
    assert "mask" in optics and "HUMAN_INPUT" in optics


def test_custody_contract_covers_catalogue_uncertainty_strong_baselines_and_history():
    contract = read("contamination-contract.md")
    for term in (
        "PUBLIC_REFERENCE_ANCHOR",
        "PUBLIC_EQUIVALENCE_CONTROL",
        "PUBLIC_NOVEL_WITNESS",
        "FUTURE_PROTECTED_TASK",
        "every complete catalogue",
        "coverage gaps",
        "outside producer custody",
        "producer",
        "UNRESOLVED",
        "never silently",
        "misconduct",
        "P's support",
        "zero Q support",
        "before candidate outcomes",
        "Hold out complete designs",
    ):
        assert term in contract


@pytest.mark.parametrize("token", TOKENS)
def test_panel_costs_are_research_hypotheses_not_solver_cost_measurements(token):
    research = json.loads(
        (ROOT / "Business/research/benchmark-challenge-briefs/briefs.json").read_text(
            encoding="utf-8"
        )
    )
    cost = next(b for b in research["briefs"] if b["id"] == token)["cost"]
    panel = read(token + "-panel.md")
    for scenario in ("low", "base", "high"):
        hours = (
            Decimal(str(cost["complete_cases"][scenario]))
            * Decimal(str(cost["host_hours_per_complete_case"][scenario]))
            + Decimal(str(cost["anchor_host_hours"][scenario]))
            + Decimal(str(cost["comparator_host_hours"][scenario]))
        )
        euros = (hours * Decimal("1.37")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert hours == Decimal(str(cost["total_host_hours"][scenario]))
        assert euros == Decimal(str(cost["startup_eur"][scenario]))
        assert str(euros) in panel
    assert Decimal(str(cost["startup_eur"]["high"])) > 100
    for term in (
        "ASSUMPTION",
        "UNMEASURED",
        "UNKNOWN_NO_INDEX",
        "scheduled",
        "PROPOSED_NOT_DISPATCHABLE",
    ):
        assert term in panel


def test_relative_document_links_resolve_without_importing_any_external_asset():
    for path in FOLDER.glob("*.md"):
        for target in re.findall(r"\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).resolve().is_file(), (
                    path,
                    target,
                )


def test_historical_tool_run_receipts_are_not_rewritten():
    historical = "docs/development/challenge_pipeline/open-benchmark-onboarding"
    changed = subprocess.check_output(
        [
            "git",
            "diff",
            "dffe703841b43d6319e026d7a8879549bdb4a43c",
            "--name-only",
            "--",
            historical,
        ],
        cwd=ROOT,
        text=True,
    )
    assert changed == ""
