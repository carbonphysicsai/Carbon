"""Read-only checks of the discovery dossier; no solver, network or third-party imports."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path


def close(a: float, b: float) -> None:
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10), (a, b)


def main() -> None:
    root = Path(__file__).resolve().parent
    data = json.loads((root / "data.json").read_text(encoding="utf-8"))
    longlist, cards = data["longlist"], data["shortlist"]
    assert len(longlist) == 80 and len(cards) == 15
    assert len({r["domain"] for r in longlist}) == 16
    assert len({r["id"] for r in longlist}) == 80
    assert len({r["id"] for r in cards}) == 15
    sources = {s["id"]: s for s in data["sources"]}
    assert len(sources) == len(data["sources"])
    by_id = {r["id"]: r for r in longlist}
    costs = data["cost_assumptions"]
    assert data["admitted_count"] == data["solver_runs"] == data["spend_eur"] == 0
    assert data["adoption"] == "HUMAN_INPUT"
    assert not data["dispatch_ready"] and not data["protected_material"]
    assert not data["historical_rescore"]
    assert not costs["all_in_bill_verified"]

    def bill(cpu: float, equivalents: int) -> float:
        return (
            costs["rate_eur_node_h"]
            * (
                equivalents * cpu * costs["elapsed_to_cpu_ratio"]
                + costs["setup_idle_fit_node_h"]
            )
            * costs["tax_stress_multiplier"]
            + costs["other_reserve_eur"]
        )

    for row in longlist:
        assert row["solver_source"] in sources
        assert row["customer_packet"] == "HUMAN_INPUT" and not row["admitted"]
        assert sorted(row["c1_cpu_h_low_base_high"]) == row["c1_cpu_h_low_base_high"]
        assert min(row["c1_cpu_h_low_base_high"]) > 0
    for i, card in enumerate(cards, 1):
        assert card["id"] in by_id and card["name"] == by_id[card["id"]]["name"]
        assert card["solver"] == by_id[card["id"]]["solver_source"]
        assert all(s in sources for s in card["sources"]) and len(card["sources"]) >= 2
        assert card["computed_base_rank"] == i
        assert not card["admitted"] and not card["dispatch_ready"]
        assert card["earned_credibility"] == "NOT_DEMONSTRATED"
        assert card["p50_cpu_h"] is None and card["p95_cpu_h"] is None
        assert all(v != "PASS" for v in card["gates"].values())
        assert card["gates"]["G6"].startswith("FAIL") == (card["C2_eur"][2] > 100)
        assert card["equivalent_cases"] == (
            card["primary_cases"]
            + 2 * card["refined_cases"]
            + card["charged_failed"]
            + 2 * card["witness_pairs"]
        )
        assert card["primary_cases"] == card["designs"] * card["strata"]
        for j in range(3):
            close(
                card["V2_eur"][j],
                card["engineer_h"][j] * card["engineer_rate_eur_h"][j],
            )
            close(
                card["V3_decisions_year"][j],
                card["teams"][j] * card["decisions_per_team_year"][j],
            )
            close(
                card["annual_gross_eur"][j],
                card["V2_eur"][j] * card["V3_decisions_year"][j],
            )
            close(
                card["C2_eur"][j], bill(card["c1_cpu_h"][j], card["equivalent_cases"])
            )
            close(
                card["C3_weekly_eur"][j],
                card["C2_eur"][j]
                * costs["weekly_windows_R"][j]
                / costs["refresh_exposure_E"][j],
            )
        denominators = [
            card["C2_eur"][j] + 52 * card["C3_weekly_eur"][j] for j in range(3)
        ]
        for j, n, d in [(0, 0, 2), (1, 1, 1), (2, 2, 0)]:
            close(
                card["VCI_low_base_high"][j],
                card["annual_gross_eur"][n] / denominators[d],
            )
        if card["conditional_queue_rank"] is not None:
            panel = card["first_panel"]
            assert panel["equivalent_cases"] == (
                panel["primary_cases"]
                + 2 * panel["refined_cases"]
                + panel["control_cases"]
                + panel["witness_cases"]
                + panel["charged_failures"]
            )
            for j in range(3):
                close(
                    panel["eur_low_base_high"][j],
                    bill(card["c1_cpu_h"][j], panel["equivalent_cases"]),
                )
            text = (root / "dossiers" / (card["slug"] + ".md")).read_text(
                encoding="utf-8"
            )
            numbers = re.findall(r"^## (\d+)\.", text, re.MULTILINE)
            assert numbers == [str(n) for n in range(1, 14)], card["slug"]
            assert "HUMAN_INPUT" in text and "NONE_FEASIBLE" in text
    order = sorted(
        cards,
        key=lambda c: (-c["VCI_low_base_high"][1], -c["excitement_low_base_high"][1]),
    )
    assert [c["slug"] for c in cards] == [c["slug"] for c in order]
    queue = [c for c in cards if c["conditional_queue_rank"] is not None]
    assert [c["conditional_queue_rank"] for c in queue] == list(range(1, 6))
    assert [c["slug"] for c in queue] == [
        "solenoid-pole",
        "seal-gland",
        "planar-transformer",
        "bolted-joint",
        "compliant-gripper",
    ]

    followup = json.loads(
        (root / "flagship-budget" / "scenarios.json").read_text(encoding="utf-8")
    )
    assert followup["original_evidence_unchanged"]
    assert followup["strict_cost_only_count"] == 0
    assert followup["recorded_cost_only_count"] == 3
    assert followup["solver_runs"] == followup["spend_eur"] == 0
    assert not followup["dispatch_ready"] and not followup["protected_material"]
    assert (
        followup["adoption"] == followup["bank_budget_owner_decision"] == "HUMAN_INPUT"
    )
    assert followup["source_head"] == "536a2716bd24a41751a1d382fca40038ff1384ae"
    cutoff = followup["selection_definition"]["high_excitement_base_at_least"]

    def failure_set(c: dict) -> set[str]:
        return {g for g, state in c["gates"].items() if state.startswith("FAIL")}

    selected = [
        c
        for c in cards
        if failure_set(c) == {"G6"} and c["excitement_low_base_high"][1] >= cutoff
    ]
    selected.sort(key=lambda c: -c["VCI_low_base_high"][1])
    assert [c["id"] for c in selected] == [c["id"] for c in followup["cards"]]
    assert [c["slug"] for c in selected] == [
        "package-warpage",
        "pem-header",
        "co2-adsorption-cycle",
    ]
    assert not any(
        c["gates"]["G6"].startswith("FAIL")
        and all(
            state.startswith("PASS") for g, state in c["gates"].items() if g != "G6"
        )
        for c in cards
    )
    unscored = {r["id"] for r in longlist} - {c["id"] for c in cards}
    assert set(followup["unscored_inventory_ids"]) == unscored and len(unscored) == 65
    assert set(followup["scored_inventory_ids"]) == {c["id"] for c in cards}
    audit = followup["source_gate_audit"]
    costly = [c for c in cards if c["gates"]["G6"].startswith("FAIL")]
    assert len(audit) == len(costly) == 7
    assert {c["id"] for c in audit} == {c["id"] for c in costly}
    source_cards = {c["id"]: c for c in cards}
    for entry in audit:
        orig = source_cards[entry["id"]]
        assert set(entry["recorded_failed_gates"]) == failure_set(orig)
        assert entry["C2_eur"] == orig["C2_eur"]
        assert entry["VCI_low_base_high"] == orig["VCI_low_base_high"]
        assert entry["selected"] == (orig in selected)
    for rank, entry in enumerate(followup["cards"], 1):
        original = source_cards[entry["id"]]
        assert entry["original"] == original and entry["rank"] == rank
        assert (
            not entry["literal_cost_only_proved"]
            and not entry["absolute_cost_only_qualified"]
        )
        assert entry["minimum_budget_covering_stated_high_eur"] == math.ceil(
            original["C2_eur"][2]
        )
        narrow = entry["narrow"]
        assert not narrow["adopted"] and not narrow["dispatch_ready"]
        assert (
            not narrow["same_original_buyer_job"] and not narrow["excitement_inherited"]
        )
        assert narrow["reference_adequacy"] == "HUMAN_INPUT"
        assert narrow["equivalent_cases"] == original["equivalent_cases"] == 151
        for j in range(3):
            assert 0 <= narrow["retvalue"][j] <= 1 and 0 <= narrow["retvolume"][j] <= 1
            close(narrow["V2_eur"][j], original["V2_eur"][j] * narrow["retvalue"][j])
            close(
                narrow["V3_eligible_revisions_year"][j],
                original["V3_decisions_year"][j] * narrow["retvolume"][j],
            )
            close(
                narrow["gross_eur"][j],
                narrow["V2_eur"][j] * narrow["V3_eligible_revisions_year"][j],
            )
            close(narrow["C2_eur"][j], bill(narrow["c1"][j], 151))
            close(
                entry["triage_eur_low_base_high"][j], bill(original["c1_cpu_h"][j], 54)
            )
            close(
                narrow["C3_weekly_eur"][j],
                narrow["C2_eur"][j]
                * costs["weekly_windows_R"][j]
                / costs["refresh_exposure_E"][j],
            )
        den = [narrow["C2_eur"][j] + 52 * narrow["C3_weekly_eur"][j] for j in range(3)]
        for j, n, d in [(0, 0, 2), (1, 1, 1), (2, 2, 0)]:
            close(narrow["index_low_base_high"][j], narrow["gross_eur"][n] / den[d])
            close(
                narrow["startup_only_index_low_base_high"][j],
                narrow["gross_eur"][n] / narrow["C2_eur"][d],
            )
            close(
                entry["original_startup_only_index"][j],
                original["annual_gross_eur"][n] / original["C2_eur"][d],
            )
        loss = [
            100 * (1 - narrow["gross_value_retained_fraction"][j]) for j in [2, 1, 0]
        ]
        for j in range(3):
            close(
                narrow["gross_value_retained_fraction"][j],
                narrow["retvalue"][j] * narrow["retvolume"][j],
            )
            close(narrow["gross_value_loss_pct_low_base_high"][j], loss[j])
    followup_words = len(
        (root / "flagship-budget" / "README.md").read_text(encoding="utf-8").split()
    )
    assert followup_words <= 550, followup_words

    expected = {
        "README.md",
        "owner-summary.md",
        "methodology.md",
        "sources.md",
        "longlist.md",
        "shortlist.md",
        "comparison.md",
        "data.json",
        "validate.py",
        "flagship-budget/README.md",
        "flagship-budget/analysis.md",
        "flagship-budget/scenarios.json",
        *("dossiers/" + c["slug"] + ".md" for c in queue),
    }
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert actual == expected, actual ^ expected
    for path in root.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^\s)]+)\)", content):
            if target.startswith(("https://", "http://", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_relative_to(root) and resolved.is_file(), (path, target)
    words = len((root / "owner-summary.md").read_text(encoding="utf-8").split())
    assert words <= 550, words
    print(
        "PASS: 80 rows, 16 domains, 15 cards, five complete conditional dossiers; "
        "cost/value/rank/source/link/manifest checks; zero admitted, no dispatch; "
        "flagship follow-up: 3 cost-only-coded candidates, 4 non-cost exclusions, "
        "65 unscored, 0 proved sole-cost failures; scope/value-loss arithmetic; 17 files."
    )


if __name__ == "__main__":
    main()
