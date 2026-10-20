"""F08's sealed-exam family (OWNER-F02-F08-EXAM-DRAW-01): its registration is
the hidden rule's own values, it stays closed until its sealed evaluation
version is registered, its records are checked as the development bank's,
and a batch is drawn, solved resumably and sealed by the generic source."""

from __future__ import annotations

import copy
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

from carbon.challenge_validator import f08_hidden as hidden
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.f08_source import F08BatchSource, f08_family
from carbon.challenge_validator.family_source import FamilySource, family_source_class
from carbon.f08 import population

REPOSITORY = Path(__file__).resolve().parents[2]
CALCULIX = REPOSITORY / "scripts/dev/reference_packages/calculix"
sys.path.insert(0, str(CALCULIX))
sys.path.insert(0, str(CALCULIX.parent))
_SPEC = importlib.util.spec_from_file_location(
    "f08_exam_runner_for_family", CALCULIX / "f08_exam_runner.py"
)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def test_the_producer_finds_f08_as_a_registered_family():
    assert family_source_class("f08-ribbed-bracket") is F08BatchSource
    assert issubclass(F08BatchSource, FamilySource)


def test_f08s_registration_is_its_hidden_rules_own_values():
    family = f08_family()
    assert (family.challenge_id, family.challenge_version) == (
        "f08-ribbed-bracket",
        "1.2",
    )
    assert family.kinds == hidden.KINDS == ("screening",)
    assert family.batch_cases == hidden.BATCH_CASES == 8
    assert family.every_blocks == hidden.ROTATION_EVERY_BLOCKS == 648_000
    assert family.active_batches == hidden.ACTIVE_BATCHES == 1
    assert family.terminal == hidden.TERMINAL == runner.TERMINAL
    assert family.image == hidden.SOLVER_IMAGE == runner.solvers_id()
    assert family.image_env == "CARBON_F08_SOLVERS"
    assert family.runner == hidden.RUNNER
    assert (REPOSITORY / hidden.RUNNER).is_file()
    assert family.population_version == population.POPULATION_VERSION
    assert hidden.OBSERVED == runner.OBSERVED


def test_the_rule_cites_the_exam_and_never_restates_scoring():
    rule = hidden.hidden_rule()
    assert rule["exam"] == {
        "pack_version": "f08-normal-construction-development-3",
        "evaluation_version": "f08-dual-sealed-batch-8-v1",
    }
    assert rule["challenge"] == {"id": "f08-ribbed-bracket", "version": "1.2"}
    assert rule["references"] == {"terminal": list(hidden.TERMINAL), "scored": ["OK"]}
    text = json.dumps(rule)
    for scoring in ("weight", "threshold", "margin", "reward"):
        assert scoring not in text


def test_an_unregistered_evaluation_version_closes_the_family(monkeypatch):
    monkeypatch.setattr(hidden, "EVALUATION_VERSION", None)
    with pytest.raises(hidden.F08FamilyError) as refused:
        hidden.hidden_rule()
    assert refused.value.code == "f08_sealed_evaluation_version_unregistered"


def test_the_contract_digest_is_the_1_2_kit():
    from carbon.challenge_kit import f08_public
    from carbon.challenge_validator.interface import digest

    kit = f08_public.construction_kit
    assert hidden.contract_digest() == digest(kit("f08-ribbed-bracket", "1.2"))
    assert hidden.contract_digest() != digest(kit("f08-ribbed-bracket", "1.1"))


def document(seed=3):
    drawn = population.draw(random.Random(seed), 8)[0]
    return {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": "f08-ribbed-bracket", "version": "1.2"},
        "role": "exam",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"c{i}", "inputs": c} for i, c in enumerate(drawn)],
    }


def test_documents_are_checked():
    good = document()
    assert len(hidden.check_document(good)) == 8
    off_lattice = copy.deepcopy(good)
    off_lattice["cases"][0]["inputs"]["length_mm"] += 1.0
    for bad in (
        dict(good, kind="finalist"),
        dict(good, challenge={"id": "f08-ribbed-bracket", "version": "1.1"}),
        dict(good, cases=good["cases"][:7]),
        off_lattice,
        dict(good, extra=1),
    ):
        with pytest.raises(ValueError):
            hidden.check_document(bad)


def ok_record(inputs, worst=0.149):
    """Synthetic, non-production values with the runner's record shape."""
    return {
        "status": "OK",
        "inputs": inputs,
        "image": hidden.SOLVER_IMAGE,
        "solvers": runner.pinned_solvers(),
        "reference_rung_h_mm": 1.7,
        "outputs": {
            "static_tip_mm_per_n": 0.012,
            "worst_dynamic_mm_per_n": worst,
            "mass_kg": 0.3,
            "cad_mass_kg": 0.3,
            "modes": 48,
            "mode_ladder": {"verdict": "PASS"},
            "in_band_modes_hz": [210.0],
        },
        "damping": {
            z: {"worst_mm_per_n": worst * k, "worst_hz": 210.0}
            for z, k in zip(hidden.ZETAS, (1.0, 0.5, 0.25), strict=True)
        },
        "rung_worst_dynamic_mm_per_n": {
            "h3": worst - 1e-4,
            "h2.25": worst,
            "h1.7": worst,
        },
        "convergence": {
            "asymptotic_ok": True,
            "rungs": {"h3": {"verdict": "PASS"}, "h2.25": {"verdict": "PASS"}},
        },
    }


INPUTS = document()["cases"][0]["inputs"]


def test_ok_references_carry_the_development_banks_values():
    hidden.check_reference(ok_record(INPUTS), INPUTS)
    for status in ("REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT"):
        hidden.check_reference(
            {"status": status, "inputs": INPUTS, "image": hidden.SOLVER_IMAGE}, INPUTS
        )

    def changed(path, value):
        record = ok_record(INPUTS)
        target = record
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return record

    other_solvers = runner.pinned_solvers()
    other_solvers["solvers"]["ccx"]["sha256"] = "0" * 64
    for bad in (
        changed(("status",), "FAILED_INFRA"),
        changed(("image",), "sha256:" + "0" * 64),
        changed(("solvers",), other_solvers),
        changed(("inputs",), {**INPUTS, "length_mm": INPUTS["length_mm"] + 5.0}),
        changed(("outputs", "mode_ladder"), {"verdict": "FAIL"}),
        changed(("convergence", "asymptotic_ok"), False),
        changed(("convergence", "rungs", "h3", "verdict"), "FAIL"),
        changed(("rung_worst_dynamic_mm_per_n", "h1.7"), 0.2),
        changed(("damping",), {}),
        changed(("reference_rung_h_mm",), 3.0),
    ):
        with pytest.raises(ValueError):
            hidden.check_reference(bad, INPUTS)


def write_deployment(path, **fields):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps({"schema": hidden.DEPLOYMENT_SCHEMA, **fields}))
    path.chmod(0o600)
    return path


def test_a_shared_deployment_is_refused(tmp_path):
    path = write_deployment(tmp_path / "etc" / "f08.json", store="s")
    path.chmod(0o644)
    with pytest.raises(hidden.F08FamilyError) as refused:
        hidden.load_deployment(path)
    assert refused.value.code == "f08_hidden_deployment_not_owner_only"


class Solver:
    """`f08_exam_runner.py`'s contract, scripted. `fail` names cases whose
    first attempt is FAILED_INFRA."""

    def __init__(self):
        self.fail = set()
        self.planned = []

    def __call__(self, command, check, cwd, env):
        assert env["CARBON_F08_SOLVERS"] == hidden.SOLVER_IMAGE
        plan = json.loads(Path(command[2]).read_text())
        out = Path(command[command.index("--out") + 1])
        self.planned.append(sorted(c["case_id"] for c in plan["cases"]))
        with (out / "records.jsonl").open("a") as handle:
            for case in plan["cases"]:
                record = ok_record(case["inputs"])
                record["case_id"] = case["case_id"]
                if case["case_id"] in self.fail:
                    self.fail.discard(case["case_id"])
                    record = {
                        "case_id": case["case_id"],
                        "inputs": case["inputs"],
                        "image": hidden.SOLVER_IMAGE,
                        "status": "FAILED_INFRA",
                    }
                handle.write(json.dumps(record) + "\n")

        class Done:
            returncode = 0

        return Done()


def test_a_batch_is_drawn_solved_with_a_retry_and_sealed(tmp_path):
    path = write_deployment(
        tmp_path / "producer-etc" / "f08.json",
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    F08BatchSource.init(path)
    solver = Solver()
    source = F08BatchSource(path, repository=REPOSITORY, runner=solver)
    producer = pr.Producer(tmp_path / "producer", [source])
    drawn = producer.draw("f08-ribbed-bracket", "f08-exam-N1r", kind="screening")
    plan = source.jobs(drawn["fingerprint"])
    assert len(plan) == 8
    published = hidden.published_keys(REPOSITORY)
    assert not {hidden.overlap_key(c["inputs"]) for c in plan} & published
    solver.fail = {plan[0]["case_id"]}
    producer.solve("f08-ribbed-bracket", drawn["fingerprint"])
    # FAILED_INFRA is left pending, never stored; the next solve resumes it.
    assert source.sealed(drawn["fingerprint"]) is None
    producer.solve("f08-ribbed-bracket", drawn["fingerprint"])
    producer.seal("f08-ribbed-bracket", drawn["fingerprint"])
    assert [len(p) for p in solver.planned] == [8, 1]  # only the retry
    assert source.sealed(drawn["fingerprint"])["cases"] == 8
