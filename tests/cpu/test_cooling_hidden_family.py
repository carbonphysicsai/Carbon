"""Cooling's sealed-exam family: its registration is the hidden rule's own
values, its records are judged on the family mesh by the graded analysis, a
batch is one 4 x 4 grid, and it packs into the development bank's format."""

from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path

import pytest

from carbon.challenge_kit import cooling_sealed_pack as pack
from carbon.challenge_kit import physical_pack
from carbon.challenge_validator import cooling_hidden as hidden
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.cooling_source import CoolingBatchSource, cooling_family
from carbon.challenge_validator.family_source import FamilySource, family_source_class
from carbon.cold_plate import openfoam
from carbon.cold_plate.domain import PROFILE_SEGMENTS
from carbon.cold_plate_exam import population

REPOSITORY = Path(__file__).resolve().parents[2]
COOLING = "chip-cold-plate"


def test_the_producer_finds_cooling_as_a_registered_family():
    assert family_source_class(COOLING) is CoolingBatchSource
    assert issubclass(CoolingBatchSource, FamilySource)


def test_coolings_registration_is_its_hidden_rules_own_values():
    family = cooling_family()
    assert (family.challenge_id, family.challenge_version) == (COOLING, "1.1")
    assert family.batch_cases == hidden.BATCH_CASES == 16
    assert family.kinds == ("screening",)
    assert family.every_blocks == 648_000 and family.active_batches == 1
    assert family.image == hidden.SOLVER_IMAGE == openfoam.IMAGE
    assert family.image_env == "CARBON_COOLING_IMAGE"
    assert (REPOSITORY / hidden.RUNNER).is_file()
    assert family.population_version == population.POPULATION_VERSION
    assert physical_pack.PACK_VERSIONS[(COOLING, "1.1")] == hidden.PACK_VERSION


def test_the_rule_cites_the_sealed_exam_and_the_reference_level():
    rule = hidden.hidden_rule()
    assert rule["exam"] == {
        "pack_version": "cooling-normal-construction-development-2",
        "evaluation_version": "cooling-dual-sealed-batch-16-v2",
    }
    assert rule["reference"] == {
        "mesh_family": "graded-hotspot-v1",
        "resolution": 2 * math.sqrt(2),
        "analysis_version": "carbon.cold-plate.graded-heat-in.v1",
    }


@pytest.fixture(scope="module")
def grid():
    return population.draw(random.Random(2), 16)[0]


def document(cases):
    return {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": COOLING, "version": "1.1"},
        "role": "exam",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"k{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }


def ok_record(case_id, inputs, peak=95.0):
    """Synthetic, non-production values with run_batch's record shape."""
    return {
        "case_id": case_id,
        "status": "OK",
        "inputs": inputs,
        "options": dict(hidden.REFERENCE_OPTIONS),
        "image": hidden.SOLVER_IMAGE,
        "outputs": {
            "peak_c": peak,
            "mean_c": peak - 10,
            "outlet_c": inputs["inlet_c"] + 5,
            "pressure_drop_pa": 1500.0,
            "profile_c": [peak - 5] * PROFILE_SEGMENTS,
        },
        "checks": {"energy_balance_rel": 1e-8},
        "diagnostics": {"analysis_version": hidden.ANALYSIS_VERSION},
    }


def test_documents_must_be_one_full_grid(grid):
    good = document(grid)
    assert len(hidden.check_document(good)) == 16
    off_grid = copy.deepcopy(good)
    off_grid["cases"][0]["inputs"]["channel_width_mm"] = 0.21234
    for bad in (
        dict(good, cases=good["cases"][:15]),
        off_grid,
        dict(good, kind="finalist"),
        dict(good, challenge={"id": COOLING, "version": "1.0"}),
    ):
        with pytest.raises(ValueError):
            hidden.check_document(bad)


def test_references_are_judged_on_the_family_by_the_graded_analysis(grid):
    inputs = grid[0]
    hidden.check_reference(ok_record("k00", inputs), inputs)
    for change in (
        {"options": {"resolution": 2.0}},
        {"image": "sha256:" + "0" * 64},
        {"diagnostics": {}},
        {"checks": {"energy_balance_rel": 2e-5}},
    ):
        with pytest.raises(ValueError):
            hidden.check_reference({**ok_record("k00", inputs), **change}, inputs)
    hidden.check_reference(
        {"case_id": "k00", "status": "REFERENCE_TIMEOUT", "inputs": inputs}, inputs
    )


def records_for(doc):
    return [ok_record(c["case_id"], c["inputs"]) for c in doc["cases"]]


def test_the_bank_has_coolings_development_bank_shape_and_names_its_cells(grid):
    doc = document(grid)
    mine = pack.sealed_bank(doc, records_for(doc))
    theirs = physical_pack.development_bank(COOLING, "1.1")
    assert set(mine) == set(theirs)
    assert mine["inputs"].dtype == theirs["inputs"].dtype
    assert mine["inputs"].shape[1] == theirs["inputs"].shape[1]
    assert mine["references"].shape == (16, theirs["references"].shape[1])
    assert mine["cohorts"] == ("decision_sealed_grid",) * 16
    cells = [(r["design_id"], r["condition_id"]) for r in mine["reference_records"]]
    assert cells == [(f"d{i}", f"c{j}") for i in range(1, 5) for j in range(1, 5)]


def test_an_exam_is_the_whole_grid_or_nothing(grid):
    doc = document(grid)
    records = records_for(doc)

    def refusal(recs):
        with pytest.raises(pack.SealedPackRefused) as refused:
            pack.sealed_bank(doc, recs)
        return refused.value.code

    assert refusal(records[:15]) == "cooling_sealed_case_unresolved"
    invalid = copy.deepcopy(records)
    invalid[3] = {**invalid[3], "status": "REFERENCE_INVALID"}
    assert refusal(invalid) == "cooling_sealed_case_unresolved"
    wrong_mesh = copy.deepcopy(records)
    wrong_mesh[2]["options"] = {"resolution": 2.0}
    assert refusal(wrong_mesh) == "cooling_sealed_record_malformed"
    assert refusal(records + [records[0]]) == "cooling_sealed_records_mismatch"


def write_deployment(path, **fields):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps({"schema": hidden.DEPLOYMENT_SCHEMA, **fields}))
    path.chmod(0o600)
    return path


def test_a_shared_deployment_is_refused(tmp_path):
    path = write_deployment(tmp_path / "etc" / "cooling.json", store="s")
    path.chmod(0o644)
    with pytest.raises(hidden.CoolingFamilyError) as refused:
        hidden.load_deployment(path)
    assert refused.value.code == "cooling_sealed_deployment_not_owner_only"


class Solver:
    """`cooling_exam_runner.py`'s contract, scripted; `fail` names cases whose
    first attempt is FAILED_INFRA."""

    def __init__(self):
        self.fail, self.planned = set(), []

    def __call__(self, command, check, cwd, env):
        assert env["CARBON_COOLING_IMAGE"] == hidden.SOLVER_IMAGE
        plan = json.loads(Path(command[2]).read_text())
        out = Path(command[command.index("--out") + 1])
        self.planned.append(sorted(c["case_id"] for c in plan["cases"]))
        with (out / "records.jsonl").open("a") as handle:
            for case in plan["cases"]:
                record = ok_record(case["case_id"], case["inputs"])
                if case["case_id"] in self.fail:
                    self.fail.discard(case["case_id"])
                    record = {
                        "case_id": case["case_id"],
                        "inputs": case["inputs"],
                        "status": "FAILED_INFRA",
                    }
                handle.write(json.dumps(record) + "\n")

        class Done:
            returncode = 0

        return Done()


def test_a_grid_is_drawn_solved_with_a_retry_sealed_and_packed(tmp_path):
    path = write_deployment(
        tmp_path / "producer-etc" / "cooling.json",
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    CoolingBatchSource.init(path)
    solver = Solver()
    source = CoolingBatchSource(path, repository=REPOSITORY, runner=solver)
    producer = pr.Producer(tmp_path / "producer", [source])
    drawn = producer.draw(COOLING, "cooling-exam-1", kind="screening")
    jobs = source.jobs(drawn["fingerprint"])
    assert len(jobs) == 16
    population.grid_of([j["inputs"] for j in jobs])
    solver.fail = {jobs[0]["case_id"]}
    producer.solve(COOLING, drawn["fingerprint"])
    assert source.sealed(drawn["fingerprint"]) is None
    producer.solve(COOLING, drawn["fingerprint"])
    producer.seal(COOLING, drawn["fingerprint"])
    assert [len(p) for p in solver.planned] == [16, 1]
    exported = source.export(drawn["fingerprint"])
    bank = pack.sealed_bank(exported["document"], list(exported["references"].values()))
    assert len(bank["case_ids"]) == 16
