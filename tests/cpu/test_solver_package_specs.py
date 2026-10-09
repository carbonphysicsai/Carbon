"""Static DC handoff checks; no build, subprocess, solver or physical evidence."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "docs/development/challenge_pipeline/solver-package-specs"
DATA = json.loads((DIRECTORY / "package-specs.json").read_text(encoding="utf-8"))


def text(name):
    return (DIRECTORY / name).read_text(encoding="utf-8")


def test_only_specifications_and_no_runtime_or_execution_authority():
    assert DATA["maturity"] == "SPECIFIED"
    for field in (
        "executable",
        "build_authorised",
        "solver_runs_authorised",
        "spend_authorised",
        "protected_data_access",
    ):
        assert DATA[field] is False
    assert DATA["runtime_ids"] == []
    assert DATA["earned_credibility"] == "NOT_DEMONSTRATED"
    assert set(DATA["packages"]) == {"f17", "f06", "warpage"}
    for package in DATA["packages"].values():
        assert package["accepted_image_digest"] is None
        assert package["accepted_task_manifest_sha256"] is None
        assert package["cost"]["status"] == "UNMEASURED"
        assert package["cost"]["measured_cpu_h"] is None
        assert package["cost"]["measured_rss_gib"] is None
        assert package["tier_target"] == 2


def test_immutable_proposal_pins_are_not_accepted_build_identities():
    common = DATA["common"]
    assert re.fullmatch("[0-9a-f]{40}", common["recipe_source_head"])
    assert re.fullmatch("debian@sha256:[0-9a-f]{64}", common["base_candidate"])
    assert common["accepted_platform_base_digest"] is None
    assert common["compatibility_proven"] is False
    assert common["dependency_versions_and_hashes"].startswith("HUMAN_INPUT")
    for name in ("f17", "f06"):
        package = DATA["packages"][name]
        assert re.fullmatch("[0-9a-f]{40}", package["upstream_commit"])
        assert package["upstream_commit"] in text(package["spec"])
        assert package["source_archive_sha256"] is None
    warpage = DATA["packages"]["warpage"]
    assert re.fullmatch("[0-9a-f]{64}", warpage["source_archive_sha256"])
    assert warpage["source_archive_sha256"] in text(warpage["spec"])
    assert "not present on this" in text(warpage["spec"])


def test_all_packet_and_handoff_links_exist():
    for package in DATA["packages"].values():
        assert (DIRECTORY / package["spec"]).is_file()
        assert (DIRECTORY / package["packet"]).is_file()
        for destination in re.findall(r"\]\(([^)]+)\)", text(package["spec"])):
            if "://" not in destination:
                assert (DIRECTORY / destination.split("#")[0]).is_file()


def test_flow_reuse_counts_and_observer_do_not_manufacture_mixing():
    package = DATA["packages"]["f17"]
    reuse = package["flow_reuse"]
    assert reuse["proven"] is False and reuse["rescale_flow_allowed"] is False
    assert reuse["retain_exact_phi"] is True
    assert reuse["flow_starts"] + reuse["scalar_starts"] == 12
    assert reuse["total_proven_reuse_starts"] == 12
    assert reuse["no_reuse_starts"] == 18
    observer = package["observer"]
    assert observer["mixing_clamped"] is False
    assert "diffusive" in observer["scalar_balance"]
    assert "backflow" in observer["mixing_weights"]
    assert (
        package["field_units"]["p_native"] != package["field_units"]["delta_p_export"]
    )
    assert "zero_D" in " ".join(package["smoke_required"])
    assert package["selected_development_gates"] == {
        "M_min": 0.8,
        "delta_p_max_pa": 250,
        "volume_over_Q_max_s": 20,
    }


def test_meep_memory_is_only_a_lower_bound_and_wavelengths_are_exact():
    package = DATA["packages"]["f06"]
    memory = package["memory"]
    assert memory["status"] == "LOWER_BOUND_NOT_TOTAL_MEMORY"
    assert memory["full_10nm_fit_proven"] is False
    assert len(memory["omitted"]) == 6
    for spacing, expected in (
        (30, ["1.90", "3.97"]),
        (20, ["6.40", "13.41"]),
        (10, ["51.23", "107.29"]),
    ):
        lower = [
            cells * (10 / spacing) ** 3 * 96 / 2**30
            for cells in memory["fine_bare_cells_low_high"]
        ]
        assert [f"{value:.2f}" for value in lower] == expected
        assert " / ".join(expected) in text(package["spec"])
    assert package["outputs_per_design"] == len(package["wavelengths_nm"]) * 9
    assert package["p10_order_statistic"] == 5
    assert package["observer"]["uniform_frequency_grid_substitution"] is False
    assert package["observer"]["broadband_parity_proven"] is False
    assert package["observer"]["double_count_fibre_in_upward_power"] is False
    assert package["two_dimensional_role"] == "SCREENING_ONLY_INACTIVE_REFRAME"


def test_warpage_requires_full_history_and_missing_material_feature_proofs():
    package = DATA["packages"]["warpage"]
    assert package["scope_reduction_allowed"] is False
    assert "Full 3D" in package["physical_scope"]
    assert package["task_smoke_blocked"] is True
    assert len(package["missing_feature_proofs"]) == 7
    assert package["material_history_contract"].startswith("HUMAN_INPUT")
    assert package["numeric_tolerances"].startswith("HUMAN_INPUT")
    assert package["cost"]["node_h_low_base_high_prior"] == [0.03, 0.12, 0.45]
    assert package["cost"]["cpu_h_hypothesis"].startswith("HUMAN_INPUT")
    document = text(package["spec"])
    assert "not measured CPU-hours" in document
    assert "integration-point" in document and "restarted" in document
    assert "tiny elastic modulus" in document and "not cure/viscoelasticity" in document


def test_credibility_balance_and_shared_engine_boundaries_are_explicit():
    common = DATA["common"]
    assert "never hidden EVAL/STRESS/quiz/tuning" in common["witness_custody"]
    assert "no silent sealed-history rescore" in common["disagreement_policy"]
    assert "Never prune shared Docker" in common["cleanup_policy"]
    document = text("README.md")
    assert "Missing truth is never candidate failure" in document
    assert "pointwise agreement **and** feasibility/pick agreement" in document
    assert "No automatic retries" in document
    assert "Byte-stable metadata" in document
