"""OPT-08 public Level 1 Q1 wiring; all outcome rows here are toy fixtures."""

import contextlib
import copy
import json

import pytest

from carbon.battery.value import contract as ev
from carbon.battery.value import level_compile
from carbon.battery.value import panel as pn
from carbon.battery.value.experiment import Experiment
from carbon.challenge_pipeline.readiness import checks, model, q1
from scripts.dev.battery import l1_decision_q1 as l1


def test_registered_panel_is_exactly_the_anchors_and_nine_counted_l1_rows():
    names = {m for m, *_ in pn.members(l1.MEMBERS)}
    levels = pn.levels(l1.MEMBERS)
    assert len(names) == 20
    assert sum(levels[name][0] == 0 for name in names) == 11
    assert sum(levels[name][0] == 1 for name in names) == 9
    assert not any(name.startswith("l4v3-") for name in names)
    assert l1.MEMBERS not in pn.ATTACK_PANELS
    contract, _digest = ev.load(l1.CONTRACT)
    assert contract["panel"] == l1.MEMBERS
    assert contract["panel_registration"] == l1.registration()
    assert contract["public_reference_sha256"] == l1.REFERENCE_SHA


def test_contract_refuses_changed_member_or_source_digest():
    contract, _digest = ev.load(l1.CONTRACT)
    bad = copy.deepcopy(contract)
    member = next(iter(bad["panel_registration"]["member_sha256"]))
    bad["panel_registration"]["member_sha256"][member] = "sha256:" + "0" * 64
    with pytest.raises(ev.ContractError, match="panel_member_mismatch"):
        ev.validate(bad)
    bad = copy.deepcopy(contract)
    bad["panel_registration"]["source_sha256"]["proof-panel-levels-v1.json"] = (
        "sha256:" + "0" * 64
    )
    with pytest.raises(ev.ContractError, match="panel_source_mismatch"):
        ev.validate(bad)


def test_public_scoring_source_is_only_ev4():
    _store, cases, identity = l1.public_ev4_scoring_set(l1.ROOT)
    assert len(cases) == 840
    assert identity["sha256"] == l1.REFERENCE_SHA
    assert identity["path"].endswith("/decision-references.jsonl.gz")
    assert "private" not in identity["path"]


def test_freeze_pins_only_the_public_ev4_scoring_set(tmp_path):
    experiment = Experiment(
        tmp_path / "study",
        repository=l1.ROOT,
        level_compiler=level_compile,
        scoring_set=l1.public_ev4_scoring_set,
    )
    manifest = experiment.freeze(l1.CONTRACT)
    assert len(manifest["panel"]) == 20
    assert manifest["scoring_set"]["sha256"] == l1.REFERENCE_SHA
    assert manifest["scoring_set"]["classification"] == "PUBLIC_SYNTHETIC_DEVELOPMENT"
    assert not (tmp_path / "q1_report.json").exists()


def test_missing_bundles_fail_before_any_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(q1, "current_rule_digest", lambda *_: "sha256:" + "a" * 64)
    predictions = tmp_path / "public-predictions"
    predictions.mkdir()
    scores = tmp_path / "scores.json"
    scores.write_text(
        json.dumps(
            {
                "classification": "PUBLIC_SYNTHETIC_DEVELOPMENT",
                "score_direction": "higher_is_better",
                "scoring_rule_digest": "sha256:" + "a" * 64,
                "members": {
                    m: {"score": 0.5, "eligible": True}
                    for m, *_ in pn.members(l1.MEMBERS)
                },
            }
        )
    )
    with pytest.raises(ValueError, match="prediction bundles: missing"):
        l1.run(
            tmp_path / "experiment",
            predictions,
            scores,
            tmp_path / "panel.json",
            tmp_path / "q1_report.L1.json",
        )
    assert not (tmp_path / "experiment").exists()
    assert not (tmp_path / "q1_report.L1.json").exists()


def test_toy_l1_q1_report_is_read_by_v1_v2_at_l1_only(tmp_path, monkeypatch):
    monkeypatch.setattr(q1, "PACKAGE", tmp_path)
    rule = "sha256:" + "a" * 64
    monkeypatch.setattr(q1, "current_rule_digest", lambda *_: rule)
    names = sorted(m for m, *_ in pn.members(l1.MEMBERS))
    results = {
        "references": {
            "D-one": {"split": "development"},
            "D-two": {"split": "development"},
            "V-one": {"split": "verification"},
        },
        "summary": {
            "members": {
                m: {
                    "eligible": True,
                    "kind": "RECONSTRUCTED",
                    "loss_development": i / 20,
                }
                for i, m in enumerate(names)
            }
        },
        "decisions": {
            m: {
                "D-one": {
                    "outcome": {
                        "kind": "SELECTED_FEASIBLE",
                        "selected": "d1" if i % 2 else "d2",
                        "decision_loss": i / 20,
                    }
                },
                "D-two": {
                    "outcome": {
                        "kind": "CORRECT_ABSTENTION",
                        "selected": None,
                        "decision_loss": i / 20,
                    }
                },
            }
            for i, m in enumerate(names)
        },
    }
    scores = {m: {"score": 1 - i / 20, "eligible": True} for i, m in enumerate(names)}
    panel = l1.q1_panel(results, scores)
    assert len(panel["members"]) == 20
    results["decisions"][names[0]]["D-two"]["outcome"]["kind"] = "ABSTENTION_UNRESOLVED"
    masked = l1.q1_panel(results, scores)
    assert all(
        set(row["decision_outcome"]) == {"D-one"} for row in masked["members"].values()
    )
    assert masked["members"][names[3]]["value"] == 3 / 20
    report = q1.build_report(l1.CHALLENGE, 1, panel, rule)
    folder = tmp_path / l1.CHALLENGE
    folder.mkdir()
    (folder / "q1_report.L1.json").write_text(json.dumps(report))
    ctx = checks.Context(challenge=l1.CHALLENGE, level=1)
    assert q1.v1_alignment_report({}, ctx).status == model.PASS
    assert q1.v2_panel_discrimination({}, ctx).status == model.PASS
    assert (
        q1.v1_alignment_report(
            {}, checks.Context(challenge=l1.CHALLENGE, level=0)
        ).status
        == model.FAIL
    )


def test_fixture_run_writes_only_l1_report(tmp_path, monkeypatch):
    """Stand-in orchestration: no reconstruction, solver or hidden input."""
    monkeypatch.setattr(q1, "PACKAGE", tmp_path / "readiness")
    rule = "sha256:" + "a" * 64
    monkeypatch.setattr(q1, "current_rule_digest", lambda *_: rule)
    names = sorted(m for m, *_ in pn.members(l1.MEMBERS))
    predictions = tmp_path / "predictions"
    predictions.mkdir()
    for member in names:
        (predictions / f"{member}.json.gz").write_bytes(b"fixture")
    scores = tmp_path / "scores.json"
    scores.write_text(
        json.dumps(
            {
                "classification": "PUBLIC_SYNTHETIC_DEVELOPMENT",
                "score_direction": "higher_is_better",
                "scoring_rule_digest": rule,
                "members": {
                    member: {"score": 1 - i / 20, "eligible": True}
                    for i, member in enumerate(names)
                },
            }
        )
    )
    results = {
        "manifest_digest": "sha256:" + "b" * 64,
        "references": {"D-one": {"split": "development"}},
        "summary": {
            "members": {
                member: {
                    "eligible": True,
                    "kind": "RECONSTRUCTED",
                    "loss_development": i / 20,
                }
                for i, member in enumerate(names)
            }
        },
        "decisions": {
            member: {
                "D-one": {
                    "outcome": {
                        "kind": "SELECTED_FEASIBLE",
                        "selected": "d1" if i % 2 else "d2",
                        "decision_loss": i / 20,
                    }
                }
            }
            for i, member in enumerate(names)
        },
    }

    class FixtureExperiment:
        def __init__(self, root, **_kwargs):
            self.root = root

        @contextlib.contextmanager
        def lock(self):
            self.root.mkdir()
            yield

        def freeze(self, contract):
            assert contract == l1.CONTRACT

        def import_references(self, path):
            assert path.read_bytes().startswith(b"{")

        def import_predictions(self, source):
            assert source == predictions

        def evaluate(self):
            return results

    monkeypatch.setattr(l1, "Experiment", FixtureExperiment)
    report = tmp_path / "readiness" / l1.CHALLENGE / "q1_report.L1.json"
    l1.run(tmp_path / "work", predictions, scores, tmp_path / "panel.json", report)
    assert json.loads(report.read_text())["level"] == 1
    assert (
        q1.v1_alignment_report(
            {}, checks.Context(challenge=l1.CHALLENGE, level=1)
        ).status
        == model.PASS
    )
    assert (
        q1.v2_panel_discrimination(
            {}, checks.Context(challenge=l1.CHALLENGE, level=1)
        ).status
        == model.PASS
    )
    assert not (report.parent / "q1_report.json").exists()
