"""F02's sealed-exam family (OWNER-F02-F08-EXAM-DRAW-01): its registration is
the hidden rule's own values, its records are checked as the development
bank's, and a batch is drawn, solved resumably and sealed by the generic
family source."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

from carbon.challenge_validator import f02_hidden as hidden
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.f02_source import F02BatchSource, f02_family
from carbon.challenge_validator.family_source import FamilySource, family_source_class
from carbon.f02 import population

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "scripts/dev/reference_packages/elmer"))


def test_the_producer_finds_f02_as_a_registered_family():
    assert family_source_class("f02") is F02BatchSource
    assert issubclass(F02BatchSource, FamilySource)


def test_f02s_registration_is_its_hidden_rules_own_values():
    family = f02_family()
    assert (family.challenge_id, family.challenge_version) == ("f02", "2.1")
    assert family.kinds == hidden.KINDS == ("screening",)
    assert family.batch_cases == hidden.BATCH_CASES == 8
    assert family.every_blocks == hidden.ROTATION_EVERY_BLOCKS == 648_000
    assert family.active_batches == hidden.ACTIVE_BATCHES == 1
    assert family.terminal == hidden.TERMINAL
    assert family.image == hidden.SOLVER_IMAGE
    assert family.image_env == "CARBON_F02_IMAGE"
    assert family.runner == hidden.RUNNER
    assert family.population_version == population.POPULATION_VERSION


def test_the_image_and_terminal_statuses_are_the_runners():
    import f02_exam_runner as runner
    import f02_readiness as readiness

    assert hidden.SOLVER_IMAGE == readiness.IMAGE
    assert hidden.TERMINAL == runner.TERMINAL
    assert hidden.OBSERVED == runner.OBSERVED
    assert (REPOSITORY / hidden.RUNNER).is_file()


def test_the_rule_cites_the_exam_and_never_restates_scoring():
    rule = hidden.hidden_rule()
    assert rule["exam"] == {
        "pack_version": "f02-normal-construction-development-3",
        "evaluation_version": "f02-dual-sealed-batch-8-v1",
    }
    assert rule["challenge"] == {"id": "f02", "version": "2.1"}
    assert rule["status"] == "PROVISIONAL_DEVELOPMENT_NON_QUALIFYING"
    # Only which references are eligible ("scored": ["OK"], motor's form); no
    # weight, threshold, margin or reward is restated.
    assert rule["references"] == {"terminal": list(hidden.TERMINAL), "scored": ["OK"]}
    text = json.dumps(rule)
    for scoring in ("weight", "threshold", "margin", "reward", "evaluation_rule"):
        assert scoring not in text


def test_the_contract_digest_is_the_2_1_kit_and_not_the_2_0_kit():
    from carbon.challenge_kit import f02_public
    from carbon.challenge_validator.interface import digest

    assert hidden.contract_digest() == digest(f02_public.construction_kit("f02", "2.1"))
    assert hidden.contract_digest() != digest(f02_public.construction_kit("f02", "2.0"))


def document(cases=None):
    import random

    drawn = cases or population.draw(random.Random(3), 8)[0]
    return {
        "schema": hidden.DOCUMENT_SCHEMA,
        "challenge": {"id": "f02", "version": "2.1"},
        "role": "exam",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"c{i}", "inputs": c} for i, c in enumerate(drawn)],
    }


def test_documents_are_checked():
    good = document()
    assert len(hidden.check_document(good)) == 8
    exam_action = dict(good, cases=list(good["cases"]))
    exam_action["cases"][0] = {
        "case_id": "c0",
        "inputs": {"peak_w": 85.0, "on_time_s": 5.0},
    }
    for bad in (
        dict(good, kind="finalist"),
        dict(good, challenge={"id": "f02", "version": "2.0"}),
        dict(good, cases=good["cases"][:7]),
        exam_action,
        dict(good, extra=1),
    ):
        with pytest.raises(ValueError):
            hidden.check_document(bad)


INPUTS = {"peak_w": 81.0, "on_time_s": 4.7}


def ok_record(**changes):
    record = {
        "status": "OK",
        "inputs": INPUTS,
        "image": hidden.SOLVER_IMAGE,
        "outputs": {
            "peak_top_c": 93.1,
            "extra_energy_j": 405.0,
            "first_95c_crossing_s": None,
            "peak_time_s": 6.0,
            "recovery_s": 30.0,
        },
        "rung_peaks_c": {"primary": 93.1, "mesh2": 93.11, "dt0.5": 93.09},
        "rung_comparison": {"pass": True},
    }
    record.update(changes)
    return record


def test_ok_references_carry_the_development_banks_values():
    hidden.check_reference(ok_record(), INPUTS)
    for status in ("REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT"):
        hidden.check_reference(
            {"status": status, "inputs": INPUTS, "image": hidden.SOLVER_IMAGE},
            INPUTS,
        )
    for bad in (
        ok_record(status="FAILED_INFRA"),
        ok_record(image="sha256:" + "0" * 64),
        ok_record(inputs={"peak_w": 82.0, "on_time_s": 4.7}),
        ok_record(outputs={"peak_top_c": 93.1}),
        ok_record(rung_peaks_c={"primary": 93.2, "mesh2": 93.1, "dt0.5": 93.1}),
        ok_record(rung_peaks_c={"primary": 93.1, "mesh2": 93.1}),
        ok_record(rung_comparison={"pass": False}),
        ok_record(rung_comparison=None),
    ):
        with pytest.raises(ValueError):
            hidden.check_reference(bad, INPUTS)


def write_deployment(path, **fields):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps({"schema": hidden.DEPLOYMENT_SCHEMA, **fields}))
    path.chmod(0o600)
    return path


def test_a_shared_deployment_is_refused(tmp_path):
    path = write_deployment(tmp_path / "etc" / "f02.json", store="s")
    path.chmod(0o644)
    with pytest.raises(hidden.F02FamilyError) as refused:
        hidden.load_deployment(path)
    assert refused.value.code == "f02_hidden_deployment_not_owner_only"


class Solver:
    """`f02_exam_runner.py`'s contract, scripted. `fail` names cases whose
    first attempt is FAILED_INFRA."""

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.planned = []

    def __call__(self, command, check, cwd, env):
        assert env["CARBON_F02_IMAGE"] == hidden.SOLVER_IMAGE
        plan = json.loads(Path(command[2]).read_text())
        out = Path(command[command.index("--out") + 1])
        self.planned.append(sorted(c["case_id"] for c in plan["cases"]))
        with (out / "records.jsonl").open("a") as handle:
            for case in plan["cases"]:
                peak = 60.0 + 0.4 * case["inputs"]["peak_w"]
                record = ok_record(
                    inputs=case["inputs"],
                    outputs=dict(ok_record()["outputs"], peak_top_c=peak),
                    rung_peaks_c={"primary": peak, "mesh2": peak, "dt0.5": peak},
                )
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


def test_a_batch_is_drawn_solved_with_a_retry_and_sealed(tmp_path, monkeypatch):
    path = write_deployment(
        tmp_path / "producer-etc" / "f02.json",
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    # A custody root whose batch collided with a published case before the
    # draw skipped them (found by search; checked below), so this test fails
    # without the fix every time instead of about 44% (F02) or 4% (F08).
    root = bytes.fromhex(
        "f364aa162129bb1e1ae37d48932740951104fad7e04f81cfb71cc6516f299380"
    )
    published = hidden.published_keys(REPOSITORY)
    stale = _pre_fix_draw(population, root, "f02-exam-S1", hidden.BATCH_CASES)
    assert {hidden.overlap_key(c) for c in stale} & published
    from carbon.challenge_validator import confirmation

    with monkeypatch.context() as patch:
        patch.setattr(confirmation.os, "urandom", lambda n: root)
        F02BatchSource.init(path)
    solver = Solver()
    source = F02BatchSource(path, repository=REPOSITORY, runner=solver)
    producer = pr.Producer(tmp_path / "producer", [source])
    drawn = producer.draw("f02", "f02-exam-S1", kind="screening")
    published = hidden.published_keys(REPOSITORY)
    plan = source.jobs(drawn["fingerprint"])
    assert len(plan) == 8
    assert not {hidden.overlap_key(c["inputs"]) for c in plan} & published
    solver.fail = {plan[0]["case_id"]}
    producer.solve("f02", drawn["fingerprint"])
    # FAILED_INFRA is left pending, never stored; the next solve resumes it.
    assert source.sealed(drawn["fingerprint"]) is None
    producer.solve("f02", drawn["fingerprint"])
    producer.seal("f02", drawn["fingerprint"])
    assert [len(p) for p in solver.planned] == [8, 1]  # only the retry
    assert source.sealed(drawn["fingerprint"])["cases"] == 8


def _pre_fix_draw(pop, root, role, count):
    """The batch a custody root draws for `role` under the pre-fix predicate
    (no published-case skip), by make_batch's own seed derivation."""
    import hashlib
    import hmac

    key = hmac.new(root, b"case-ids/" + role.encode(), hashlib.sha256).digest()
    label = b"draw/" + pop.POPULATION_VERSION.encode()
    seed = hmac.new(key, label, hashlib.sha256).digest()[:8]
    saved = pop._published_key
    pop._published_key = lambda case: False
    try:
        return pop.draw(random.Random(int.from_bytes(seed, "big")), count)[0]
    finally:
        pop._published_key = saved
