"""Customer decision search over the cold-plate DEVELOPMENT model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.cold_plate import analytic
from carbon.cold_plate import customer_decision as cd
from carbon.design_search import experiment as ex
from carbon.design_search import methods

REPOSITORY = Path(__file__).resolve().parents[2]
MODEL = {"member": "analytic-v1", "recipe_digest": "sha256:" + "1" * 64, "seed": 0}
METHOD = {
    "name": "fixed_grid",
    "code_digest": "sha256:" + "2" * 64,
    "configuration_digest": "sha256:" + "3" * 64,
}
DESIGNS = [
    {
        "channel_width_mm": width,
        "fin_width_mm": 0.3,
        "channel_depth_mm": 2.0,
        "flow_lpm_per_kw": flow,
    }
    for width in (0.3, 0.4)
    for flow in (1.25, 1.75)
]
CONDITIONS = [
    {
        "inlet_c": 35.0,
        "heat_load_w": 800.0,
        "hotspot_ratio": 1.0,
        "hotspot_center_mm": 15.0,
        "hotspot_width_mm": 2.5,
    },
    {
        "inlet_c": 40.0,
        "heat_load_w": 1000.0,
        "hotspot_ratio": 2.0,
        "hotspot_center_mm": 12.0,
        "hotspot_width_mm": 2.5,
    },
]


def decision_contract(**changes):
    fields = {
        "contract_id": "customer-fixture-1",
        "customer_requirement_ref": "fixture:test-cold-plate-decision",
        # Synthetic test requirements only; no production/customer authority.
        "die_limit_c": 200.0,
        "hydraulic_limit_w": 5.0,
    }
    return cd.contract(**{**fields, **changes})


def neutral(
    adapter, *, designs=DESIGNS, conditions=CONDITIONS, budget=None, model=MODEL
):
    return ex.neutral_request(
        adapter,
        mode=cd.MODE,
        model=model,
        designs=designs,
        conditions=conditions,
        query_budget=budget or len(designs) * len(conditions),
        verification_budget=len(conditions),
        method=METHOD,
        seed_policy="deterministic analytic fixture",
    )


def infer(inputs):
    return {
        query_id: {
            name: value
            for name, value in analytic.predict(case).items()
            if name in cd.exam.SHAPES
        }
        for query_id, case in inputs.items()
    }


def run(tmp_path, contract=None):
    contract = contract or decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter))
    oracle = adapter.oracle(req, space, infer)
    selections = adapter.baseline(oracle, req, space)
    commitment = adapter.commit(req, selections, oracle, tmp_path)
    return contract, adapter, req, space, oracle, selections, commitment


def sound_reference(jobs):
    return {
        job["case_id"]: {
            "status": "OK",
            "inputs": job["inputs"],
            "outputs": analytic.predict(job["inputs"]),
        }
        for job in jobs
    }


def fixture_reference(source=sound_reference, *, budget=100):
    return cd.analytical_fixture_reference(
        source,
        condition_budget=budget,
        session_id="analytic-test-fixture",
    )


def test_customer_limits_have_no_defaults_and_are_bound_by_digest():
    contract = decision_contract()
    assert contract["claims"] == {
        "customer_acceptance": False,
        "global_optimum": False,
        "scientific_qualification": False,
        "production_qualification": False,
    }
    assert cd.validate_contract(contract) is contract
    altered = {
        **contract,
        "constraints": {**contract["constraints"], "die_peak_c_max": 50.0},
    }
    with pytest.raises(cd.DecisionError, match="contract_digest_mismatch"):
        cd.validate_contract(altered)
    with pytest.raises(TypeError):
        cd.contract(contract_id="x", customer_requirement_ref="fixture:x")


@pytest.mark.parametrize(
    "change, code",
    [
        ({"hydraulic_limit_w": -1.0}, "hydraulic_limit_negative"),
        ({"die_limit_c": float("nan")}, "finite_number_required"),
        ({"customer_requirement_ref": ""}, "token_required"),
    ],
)
def test_a_customer_contract_refuses_invalid_requirements(change, code):
    with pytest.raises(cd.DecisionError, match=code):
        decision_contract(**change)


def test_request_binds_the_contract_model_space_and_conditions():
    contract = decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter))
    assert req["contract_digest"] == contract["contract_digest"]
    assert req["candidate_space_digest"].startswith("sha256:")
    assert req["condition_space_digest"].startswith("sha256:")
    assert len(space) == len(DESIGNS)
    assert req["request_digest"].startswith("sha256:")


def test_request_refuses_partial_grids_duplicates_and_out_of_scope_cases():
    contract = decision_contract()
    adapter = cd.adapter(contract)
    with pytest.raises(cd.DecisionError, match="full_grid"):
        adapter.request(neutral(adapter, designs=DESIGNS[:-1]))
    with pytest.raises(cd.DecisionError, match="repeated"):
        adapter.request(neutral(adapter, conditions=[CONDITIONS[0], CONDITIONS[0]]))
    outside = [{**DESIGNS[0], "channel_width_mm": 0.1}]
    with pytest.raises(ValueError, match="outside"):
        adapter.request(neutral(adapter, designs=outside))


def test_oracle_is_budgeted_declared_and_fails_closed_on_bad_predictions():
    contract = decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter, budget=1))
    oracle = adapter.oracle(req, space, infer)
    condition = tuple(CONDITIONS[0][name] for name in cd.CONDITION_VARIABLES)
    oracle.query([(*space[0], *condition)])
    with pytest.raises(cd.DecisionError, match="query_budget_exhausted"):
        oracle.query([(*space[1], *condition)])

    req, space = adapter.request(neutral(adapter))
    scoped = adapter.oracle(req, space, infer)
    undeclared = list(condition)
    undeclared[0] = 36.0
    with pytest.raises(cd.DecisionError, match="undeclared_condition"):
        scoped.query([(*space[0], *undeclared)])
    malformed = adapter.oracle(req, space, lambda inputs: {key: {} for key in inputs})
    with pytest.raises(cd.DecisionError, match="prediction_outputs_are_exact"):
        malformed.query([(*space[0], *condition)])
    assert malformed.used == 1
    assert malformed.successful == 0
    with pytest.raises(cd.DecisionError, match="oracle_sealed"):
        malformed.query([(*space[1], *condition)])

    def invalid_physics(inputs):
        values = infer(inputs)
        for output in values.values():
            output["pressure_drop_pa"] = -1.0
        return values

    physically_invalid = adapter.oracle(req, space, invalid_physics)
    with pytest.raises(cd.DecisionError, match="prediction_failed_physical_gate"):
        physically_invalid.query([(*space[0], *condition)])
    assert physically_invalid.used == 1
    assert physically_invalid.log[0]["status"] == "FAILED_PHYSICS"
    with pytest.raises(cd.DecisionError, match="oracle_sealed"):
        physically_invalid.query([(*space[1], *condition)])


def test_oracle_forbids_duplicates_within_a_batch_and_across_calls():
    contract = decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter))
    condition = tuple(CONDITIONS[0][name] for name in cd.CONDITION_VARIABLES)
    point = (*space[0], *condition)

    within = adapter.oracle(req, space, infer)
    with pytest.raises(cd.DecisionError, match="duplicate_query_within_batch"):
        within.query([point, point])
    assert within.used == 0
    with pytest.raises(cd.DecisionError, match="oracle_sealed"):
        within.query([(*space[1], *condition)])

    across = adapter.oracle(req, space, infer)
    across.query([point])
    with pytest.raises(cd.DecisionError, match="duplicate_query_across_calls"):
        across.query([point])
    assert across.used == 1


def test_failed_inference_is_charged_typed_and_seals_the_oracle(tmp_path):
    contract = decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter))
    condition = tuple(CONDITIONS[0][name] for name in cd.CONDITION_VARIABLES)

    def unavailable(_inputs):
        raise TimeoutError("fixture service timeout")

    oracle = adapter.oracle(req, space, unavailable)
    with pytest.raises(cd.ModelInfrastructureFailure) as failure:
        oracle.query([(*space[0], *condition), (*space[1], *condition)])
    assert failure.value.retryable is True
    assert oracle.used == 2
    assert {row["status"] for row in oracle.log} == {"FAILED_INFRA"}
    with pytest.raises(cd.DecisionError, match="oracle_sealed"):
        adapter.commit(req, [], oracle, tmp_path)


def test_fixed_grid_selects_the_least_pumping_design_feasible_everywhere(tmp_path):
    _contract, _adapter, _req, space, oracle, selections, _commitment = run(tmp_path)
    assert len(selections) == 1
    selected = selections[0]
    assert tuple(selected[name] for name in cd.DESIGN_VARIABLES) in space
    selected_rows = [
        row["quantities"]
        for row in oracle.log
        if tuple(row["point"][: len(cd.DESIGN_VARIABLES)])
        == tuple(selected[name] for name in cd.DESIGN_VARIABLES)
    ]
    assert all(row["feasible"] for row in selected_rows)
    assert selected["predicted_worst_hydraulic_w"] == max(
        row["hydraulic_w"] for row in selected_rows
    )


def test_commitment_exists_before_reference_access_and_cannot_be_rewritten(tmp_path):
    contract, adapter, req, _space, oracle, selections, commitment = run(tmp_path)
    on_disk = json.loads(commitment.path.read_text())
    seen = []

    def watching(jobs):
        assert json.loads(commitment.path.read_text()) == on_disk
        seen.extend(jobs)
        return sound_reference(jobs)

    reference = fixture_reference(watching)
    result = adapter.verify(commitment, reference)
    assert len(seen) == len(CONDITIONS)
    assert result["verdicts"]["FEASIBLE"] == len(CONDITIONS)
    assert result["false_feasible"] is False
    assert not any(result["claims"].values())
    with pytest.raises(FileExistsError):
        adapter.commit(req, selections, oracle, tmp_path)
    with pytest.raises(cd.DecisionError, match="commitment_only_from_commit"):
        cd.verify(contract, commitment.document, fixture_reference())
    edited = json.loads(commitment.path.read_text())
    edited["status"] = "ABSTAIN"
    commitment.path.write_text(json.dumps(edited))
    with pytest.raises(cd.DecisionError, match="commitment_changed_after_commit"):
        adapter.verify(commitment, fixture_reference())


def test_an_oracle_cannot_be_relabelled_as_another_request(tmp_path):
    contract = decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter))
    oracle = adapter.oracle(req, space, infer)
    selections = adapter.baseline(oracle, req, space)
    altered = {**req, "request_digest": "sha256:" + "9" * 64}
    with pytest.raises(cd.DecisionError, match="oracle_request_mismatch"):
        adapter.commit(altered, selections, oracle, tmp_path)
    mutated = {**req, "seed_policy": "changed after the oracle was built"}
    with pytest.raises(cd.DecisionError, match="request_digest_mismatch"):
        adapter.commit(mutated, selections, oracle, tmp_path)


def test_reference_failure_is_not_a_design_failure_and_false_feasible_is_visible(
    tmp_path,
):
    _contract, adapter, _req, _space, _oracle, _selections, commitment = run(tmp_path)

    def mixed(jobs):
        records = sound_reference(jobs)
        records[jobs[0]["case_id"]] = {"status": "REFERENCE_TIMEOUT"}
        second = records[jobs[1]["case_id"]]
        flow = cd.domain.derived(second["inputs"])["flow_m3_s"]
        second["outputs"]["pressure_drop_pa"] = 10.0 / flow
        return records

    result = adapter.verify(commitment, fixture_reference(mixed))
    assert result["verdicts"] == {
        "FEASIBLE": 0,
        "INFEASIBLE": 1,
        "REFERENCE_UNAVAILABLE": 1,
    }
    assert result["false_feasible"] is True
    assert result["claims"]["unavailable_counted_as_feasible_or_infeasible"] is False
    assert result["rows"][0]["reference_status"] == "REFERENCE_TIMEOUT"
    assert result["rows"][1]["reference_status"] == "OK"


def test_reference_is_classified_budgeted_cached_and_not_replayed(tmp_path):
    _contract, adapter, _req, _space, _oracle, _selections, commitment = run(tmp_path)
    with pytest.raises(cd.DecisionError, match="classified_reference_session"):
        adapter.verify(commitment, sound_reference)

    reference = fixture_reference(budget=len(CONDITIONS))
    result = adapter.verify(commitment, reference)
    assert result["reference_evidence_class"] == "ANALYTICAL_FIXTURE"
    assert result["counted_cfd_evidence"] is False
    assert result["verification_accounting"] == {
        "accounting_unit": cd.VERIFICATION_ACCOUNTING_UNIT,
        "condition_evaluations": len(CONDITIONS),
        "cache_hits": 0,
        "cache_misses": len(CONDITIONS),
    }
    with pytest.raises(cd.DecisionError, match="commitment_already_verified"):
        adapter.verify(commitment, reference)


def test_reference_cache_avoids_duplicate_source_work_but_still_counts_evaluation(
    tmp_path,
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _contract, adapter, _req, _space, _oracle, _selections, commitment = run(first)
    other_model = {**MODEL, "member": "analytic-v1-repeat"}
    other_req, other_space = adapter.request(neutral(adapter, model=other_model))
    other_oracle = adapter.oracle(other_req, other_space, infer)
    other_selections = adapter.baseline(other_oracle, other_req, other_space)
    other_commitment = adapter.commit(other_req, other_selections, other_oracle, second)
    reference = fixture_reference(budget=2 * len(CONDITIONS))

    initial = adapter.verify(commitment, reference)
    repeated_cases = adapter.verify(other_commitment, reference)
    assert initial["verification_accounting"]["cache_misses"] == len(CONDITIONS)
    assert repeated_cases["verification_accounting"]["cache_hits"] == len(CONDITIONS)
    assert reference.metrics()["source_calls"] == 1
    assert reference.metrics()["condition_evaluations"] == 2 * len(CONDITIONS)


def test_no_predicted_feasible_design_is_an_abstention_not_a_safe_claim(tmp_path):
    contract, _adapter, _req, _space, _oracle, selections, commitment = run(
        tmp_path, decision_contract(die_limit_c=0.0, hydraulic_limit_w=0.0)
    )
    assert selections == []

    def reference_must_not_run(_jobs):
        raise AssertionError("an abstention has no proposal to verify")

    result = cd.verify(contract, commitment, fixture_reference(reference_must_not_run))
    assert result["status"] == "ABSTAIN"
    assert result["reference_jobs"] == 0
    assert result["false_feasible"] is False
    assert not any(result["claims"].values())


def test_generic_search_can_screen_then_confirm_the_cold_plate(tmp_path):
    contract = decision_contract()
    adapter = cd.adapter(contract)
    req, space = adapter.request(neutral(adapter))
    baseline_oracle = adapter.oracle(req, space, infer)
    baseline = adapter.baseline(baseline_oracle, req, space)
    proposed_oracle = adapter.oracle(req, space, infer)
    proposed = methods.run(
        "screen_then_confirm",
        {"screen_condition": 0},
        adapter.view(req, space),
        proposed_oracle,
    )
    assert proposed == baseline
    assert proposed_oracle.used <= baseline_oracle.used
    commitment = adapter.commit(req, proposed, proposed_oracle, tmp_path)
    assert adapter.verify(commitment, fixture_reference())["status"] == "PROPOSAL"


def test_design_packet_keeps_all_ten_sections_and_open_owner_values_explicit():
    path = REPOSITORY / "docs/development/AI_ACCELERATOR_COOLING_DESIGN_PACKET.md"
    text = path.read_text(encoding="utf-8")
    headings = [
        "## 1. Engineering job",
        "## 2. Physical system",
        "## 3. Population P, Q and w",
        "## 4. Case contract",
        "## 5. Reference policy",
        "## 6. Output and measurement contract",
        "## 7. Construction contract",
        "## 8. Research kit",
        "## 9. Evidence plan",
        "## 10. Readiness and claim record",
    ]
    assert [text.index(heading) for heading in headings] == sorted(
        text.index(heading) for heading in headings
    )
    assert "HUMAN_INPUT" in text
    assert "does not enter the challenge pipeline" in " ".join(text.split())
