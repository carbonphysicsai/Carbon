"""Synthetic metadata exercises engineering checks, not Challenge qualification."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import evidence_readiness as er
from carbon.challenge_pipeline.onboarding import packet

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 10, 22, tzinfo=UTC)
IMAGE = "sha256:" + "a" * 64


class Tree:
    def __init__(self):
        self.files = {}
        self.commit = "synthetic"

    def add(self, name, value):
        path = "docs/development/fixture/" + name
        self.files[path] = json.dumps(value).encode()
        return {"path": path, "sha256": er.sha(self.files[path])}

    def read(self, path):
        return self.files.get(path)

    def source(self, binding):
        return (
            self.read(binding["path"]) is not None
            and er.sha(self.read(binding["path"])) == binding["sha256"]
        )

    def json(self, path):
        return json.loads(self.files[path])


@pytest.fixture
def evidence():
    tree = Tree()
    case = {
        "action": {"power_w": 100},
        "condition": {"ambient_c": 25},
        "rung": {"mesh": 2},
    }
    pins = {
        k: IMAGE
        for k in ("solver", "environment", "materials", "observer", "geometry_grammar")
    }
    registration = tree.add(
        "registration.json",
        {
            "scope": "PUBLIC_DEVELOPMENT",
            "panel_digest": er.identity({"cases": [case], "pins": pins}),
        },
    )
    index = tree.add("reuse.json", [])
    panel = {
        "registration": registration,
        "cases": [case],
        "pins": pins,
        "reuse": {"source": index, "inventory_coverage": ["COMPLETED", "SCHEDULED"]},
    }
    package = tree.add("package.json", {"image_id": IMAGE})
    inventory = tree.add(
        "inventory.json",
        {
            "scope": "PUBLIC_DEVELOPMENT",
            "package_sha256": package["sha256"],
            "image_digest": IMAGE,
            "store_id": "synthetic",
            "present": True,
            "checked_at": NOW.isoformat(),
        },
    )
    solver = {"package": package, "image_digest": IMAGE, "inventory": inventory}
    reference = {"checks": []}
    for kind in ("convergence", "conservation", "code_verification"):
        reference["checks"].append(
            {
                "kind": kind,
                "image_digest": IMAGE,
                "family": "f02",
                "acceptance": tree.add(
                    kind + "-criteria.json",
                    {
                        "status": "ACCEPTED_DEVELOPMENT",
                        "kind": kind,
                        "family": "f02",
                        "metrics": {"error": [0, 0.1]},
                    },
                ),
                "result": tree.add(
                    kind + "-result.json",
                    {
                        "image_digest": IMAGE,
                        "family": "f02",
                        "kind": kind,
                        "metrics": {"error": 0.02},
                    },
                ),
            }
        )
    kit_source = tree.add("kit.json", {"synthetic": True})
    domain = tree.add(
        "domain.json",
        {
            "kit_sha256": kit_source["sha256"],
            "action_bounds": {"power_w": [80, 140]},
            "conditions": [{"ambient_c": 25}],
            "observables": ["peak_c"],
        },
    )
    kit = {
        "source": kit_source,
        "domain_source": domain,
        "required_observables": ["peak_c"],
    }
    training_case = copy.deepcopy(case)
    training_case["action"]["power_w"] = 101
    training = {"scope": "PUBLIC_DEVELOPMENT", "cases": [training_case]}
    train = {
        "registration": tree.add(
            "train-reg.json", {"train_digest": er.identity(training)}
        ),
        "inventory": tree.add("train.json", training),
    }
    return tree, panel, solver, reference, kit, train


def test_all_five_metadata_checks_recompute_their_basis(evidence):
    tree, panel, solver, reference, kit, train = evidence
    checks = [
        er.check_panel(tree, panel),
        er.check_image(tree, solver, NOW),
        er.check_reference(tree, reference, IMAGE, "f02"),
        er.check_kit(tree, kit, panel["cases"]),
        er.check_train(tree, train, panel["cases"]),
    ]
    assert all(result is True and basis for result, basis in checks)


def test_panel_duplicate_and_missing_reuse_coverage_not_pass(evidence):
    tree, panel, *_ = evidence
    panel["cases"] *= 2
    assert er.check_panel(tree, panel)[0] is False
    panel["cases"] = panel["cases"][:1]
    panel["reuse"]["inventory_coverage"] = ["COMPLETED"]
    assert er.check_panel(tree, panel)[0] is False
    panel["cases"] = []
    with pytest.raises(packet.DraftError):
        er.check_panel(tree, panel)


@pytest.mark.parametrize("offset", [-25, 1])
def test_image_presence_is_time_bounded(evidence, offset):
    tree, _, solver, *_ = evidence
    row = tree.json(solver["inventory"]["path"])
    row["checked_at"] = (NOW + timedelta(hours=offset)).isoformat()
    solver["inventory"] = tree.add("inventory.json", row)
    assert er.check_image(tree, solver, NOW)[0] is None


def test_removed_or_repinned_image_cannot_use_old_presence(evidence):
    tree, _, solver, *_ = evidence
    solver["image_digest"] = "sha256:" + "b" * 64
    assert er.check_image(tree, solver, NOW)[0] is False
    solver["image_digest"] = IMAGE
    row = tree.json(solver["inventory"]["path"])
    row["present"] = False
    solver["inventory"] = tree.add("inventory.json", row)
    assert er.check_image(tree, solver, NOW)[0] is False


def test_reference_requires_nonempty_three_check_basis_and_current_image(evidence):
    tree, _, _, reference, *_ = evidence
    assert er.check_reference(tree, reference, IMAGE, "motor")[0] is False
    assert er.check_reference(tree, reference, "sha256:" + "b" * 64, "f02")[0] is False
    ref = copy.deepcopy(reference)
    ref["checks"].pop()
    assert er.check_reference(tree, ref, IMAGE, "f02")[0] is None
    result = tree.json(reference["checks"][0]["result"]["path"])
    result["metrics"] = {}
    reference["checks"][0]["result"] = tree.add("empty.json", result)
    assert er.check_reference(tree, reference, IMAGE, "f02")[0] is None


def test_reference_failure_is_not_candidate_failure(evidence):
    tree, _, _, reference, *_ = evidence
    result = tree.json(reference["checks"][0]["result"]["path"])
    result["metrics"]["error"] = 0.3
    reference["checks"][0]["result"] = tree.add("bad.json", result)
    ok, basis = er.check_reference(tree, reference, IMAGE, "f02")
    assert ok is False and "Reference finding" in basis


def test_kit_checks_every_case_context_and_observable(evidence):
    tree, panel, _, _, kit, _ = evidence
    cases = copy.deepcopy(panel["cases"])
    cases.append(copy.deepcopy(cases[0]))
    cases[-1]["action"]["power_w"] = 200
    assert er.check_kit(tree, kit, cases)[0] is False
    cases[-1]["action"]["power_w"] = 100
    cases[-1]["condition"]["ambient_c"] = 40
    assert er.check_kit(tree, kit, cases)[0] is False
    kit["required_observables"].append("energy_j")
    assert er.check_kit(tree, kit, panel["cases"])[0] is False


def test_train_overlap_survives_a_different_refinement_rung(evidence):
    tree, panel, _, _, _, train = evidence
    overlap = copy.deepcopy(panel["cases"][0])
    overlap["rung"]["mesh"] = 8
    training = {"scope": "PUBLIC_DEVELOPMENT", "cases": [overlap]}
    train["inventory"] = tree.add("train.json", training)
    train["registration"] = tree.add(
        "train-reg.json", {"train_digest": er.identity(training)}
    )
    assert er.check_train(tree, train, panel["cases"])[0] is False


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        "../escape",
        "docs/development/hidden-case.json",
        "carbon/challenge_validator/bank.json",
        "docs/development/EVAL/cases.json",
    ],
)
def test_read_paths_refuse_private_or_case_store_inputs(path):
    with pytest.raises(packet.DraftError):
        er.public_path(path)


def test_missing_main_reports_unknown_without_spend_permission():
    result = er.generate(ROOT, "motor", main_ref="no-such-main-ref", now=NOW)
    assert result["main"] is None
    assert all(r["state"] == "UNKNOWN" for r in result["items"])
    assert not result["spend_authorized"] and not result["qualified"]


def test_all_eleven_rank_ties_and_attach_source_digests():
    reports = er.portfolio(ROOT, now=NOW)
    assert len(reports) == 11
    assert {r["challenge"] for r in reports} >= {
        "solenoid-pole",
        "bolted-joint",
        "seal-gland",
        "f13",
    }
    for report in reports:
        assert len(report["items"]) == 7
        assert report["rank"] == 1 + sum(
            r["yes_count"] > report["yes_count"] for r in reports
        )
        assert report["examined_sources"]
        assert not report["spend_authorized"]
        assert all(row["owner"] and row["basis"] for row in report["items"])
