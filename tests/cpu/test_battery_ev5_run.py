"""EV5-RUN-01: known-answer fixtures for every EV5 verdict, passing and
failing, the run record's refusals, and the sealed batch's recall check.

Fixtures are synthetic and tiny; no EV5 data exists when these are written.
"""

from __future__ import annotations

import json

import pytest

from carbon.battery import seeds
from carbon.battery.value import admissibility, ev5
from carbon.battery.value import ev5_run as run

V = ("V1", "V2", "V3", "V4")
BOOT = {"replicates": 300, "rng_seed": 20261001, "level": 0.95}
FAMILIES = ("mlp", "knn", "deeponet")


def _results(rows):
    """rows: name -> dict(kind, eligible, cand, dec, loss, infeasible)."""
    members, scores, decisions, variation = {}, {}, {}, {}
    for name, row in rows.items():
        loss = row.get("loss")
        members[name] = {
            "kind": row.get("kind", "RECONSTRUCTED"),
            "eligible": row.get("eligible", True),
            "loss_development": loss,
            "loss_verification": loss,
        }
        scores[name] = {run.DECIDING: row.get("dec"), run.CANDIDATE: row.get("cand")}
        decisions[name] = {
            s: {
                "split": "verification",
                "outcome": {
                    "decision_loss": loss,
                    "kind": (
                        "SELECTED_INFEASIBLE"
                        if s in row.get("infeasible", ())
                        else "SELECTED_FEASIBLE"
                    ),
                },
            }
            for s in V
        }
        recipe = name.rsplit("-s", 1)[0]
        variation[recipe] = {
            split: {"seeds": 1, "max": loss, "min": loss}
            for split in ("development", "verification")
        }
    return {
        "schema": "carbon.engineering-value-results.v1",
        "summary": {"members": members},
        "rule_scores": scores,
        "decisions": decisions,
        "seed_variation": variation,
    }


def _real(n=12, *, aligned):
    """n real members over three families; loss i. The candidate ranks them
    by value; the deciding rule (−E < 0) ranks them in reverse, or the
    other way round when `aligned` is False."""
    rows = {}
    for i in range(n):
        good, bad = -float(i), float(i) - n
        rows[f"{FAMILIES[i % 3]}_r{i}-s0"] = {
            "loss": float(i),
            "cand": (good if aligned else bad) + n + 1.0,
            "dec": bad if aligned else good,
        }
    return rows


# --- H1 --------------------------------------------------------------------------------


def test_h1_promotes_only_when_all_three_conditions_hold():
    result = run.h1(
        _results(_real(aligned=True)), list(V), bootstrap=BOOT, band={"band": 0.1}
    )
    assert result["paired_bootstrap"]["interval"][0] > 0
    assert all(result["conditions"].values())
    assert result["outcome"] == run.PROMOTE


def test_h1_confirms_the_deciding_rule_otherwise():
    result = run.h1(
        _results(_real(aligned=False)), list(V), bootstrap=BOOT, band={"band": 0.1}
    )
    assert not result["conditions"]["interval_lower_bound_above_zero"]
    assert result["outcome"] == run.CONFIRMED


def test_h1_a_wide_noise_band_alone_blocks_promotion():
    result = run.h1(
        _results(_real(aligned=True)), list(V), bootstrap=BOOT, band={"band": 5.0}
    )
    assert result["conditions"]["interval_lower_bound_above_zero"]
    assert not result["conditions"]["delta_tau_exceeds_noise_band"]
    assert result["outcome"] == run.CONFIRMED


def test_h1_pool_excludes_controls_and_attack_constructions():
    rows = _real(aligned=True)
    rows["control-oracle"] = {
        "kind": "SYNTHETIC_CONTROL",
        "loss": 0.0,
        "cand": 99.0,
        "dec": 99.0,
    }
    rows["attack_x-s0"] = {
        "kind": "ATTACK_CONSTRUCTION",
        "loss": 0.0,
        "cand": 99.0,
        "dec": 99.0,
    }
    result = run.h1(_results(rows), list(V), bootstrap=BOOT, band={"band": 0.1})
    assert result["paired_bootstrap"]["members"] == 12


# --- H2 --------------------------------------------------------------------------------


def _verdicts(fail=(), controls_ok=True):
    out = {}
    for kind in ev5.GATE_MUST_FAIL:
        out["control-" + kind] = {"verdict": "FAIL" if controls_ok else "PASS"}
    for kind in ev5.GATE_MUST_PASS:
        out["control-" + kind] = {"verdict": "PASS"}
    out[run.SIGN_ERROR] = {"verdict": "PASS"}
    return out | {m: {"verdict": "FAIL" if m in fail else "PASS"} for m in fail}


def _h2(results, fail, controls_ok=True):
    verdicts = _verdicts(fail, controls_ok)
    for m in results["summary"]["members"]:
        verdicts.setdefault(m, {"verdict": "PASS"})
    return run.h2(results, list(V), verdicts, bootstrap=BOOT)


def test_h2_holds_when_failed_members_decide_worse_and_controls_behave():
    rows = _real(aligned=True)
    worst = sorted(rows, key=lambda m: rows[m]["loss"])[-4:]
    result = _h2(_results(rows), worst)
    assert result["controls_hold"]
    assert result["group_difference"]["difference"] > 0
    assert result["outcome"] == run.HOLDS
    assert result["real_members_failed"] == 4
    assert not result["fails_more_than_half"]


def test_h2_does_not_hold_when_the_boundary_optimist_passes():
    rows = _real(aligned=True)
    worst = sorted(rows, key=lambda m: rows[m]["loss"])[-4:]
    result = _h2(_results(rows), worst, controls_ok=False)
    assert not result["controls_hold"]
    assert result["outcome"] == run.NOT_HOLD


def test_h2_does_not_hold_when_failed_members_decide_better():
    rows = _real(aligned=True)
    best = sorted(rows, key=lambda m: rows[m]["loss"])[:4]
    assert _h2(_results(rows), best)["outcome"] == run.NOT_HOLD


def test_h2_is_undefined_with_an_empty_group_and_flags_more_than_half():
    rows = _real(aligned=True)
    assert _h2(_results(rows), [])["outcome"] == run.UNDEFINED
    many = sorted(rows)[:7]
    assert _h2(_results(rows), many)["fails_more_than_half"]


# --- H3 --------------------------------------------------------------------------------


def _h3(control_rate, real_rate, gate="PASS"):
    rows = _real(aligned=True)
    rows[run.SIGN_ERROR] = {
        "kind": "SYNTHETIC_CONTROL",
        "loss": 3.0,
        "cand": 50.0,
        "dec": -0.1,
    }
    results = _results(rows)
    report = {
        "members": {
            m: {"measurement": {"worst_false_acceptance_rate": real_rate}}
            for m in rows
            if m != run.SIGN_ERROR
        },
        "controls": {
            run.SIGN_ERROR: (
                None
                if control_rate is None
                else {"worst_false_acceptance_rate": control_rate}
            )
        },
    }
    verdicts = {m: {"verdict": "PASS"} for m in rows}
    verdicts[run.SIGN_ERROR] = {"verdict": gate}
    return run.h3(report, results, verdicts)


def test_h3_separation_and_its_failure():
    assert _h3(0.95, 0.2)["separation"] == run.HOLDS
    assert _h3(0.95, 0.95)["separation"] == run.NOT_HOLD
    assert _h3(None, 0.2)["separation"] == run.UNDEFINED


def test_h3_reports_the_control_rank_under_all_four_rules():
    result = _h3(0.95, 0.2, gate="FAIL")
    ranks = result["sign_error_rank"]
    assert set(ranks) == {
        f"{r}/{v}"
        for r in (run.DECIDING, run.CANDIDATE)
        for v in ("ungated", "gated_failures_last")
    }
    # Under the deciding rule its −E is best: rank 1 ungated, last once gated.
    assert ranks[f"{run.DECIDING}/ungated"]["rank"] == 1
    assert ranks[f"{run.DECIDING}/gated_failures_last"][
        "below_every_eligible_real_member"
    ]
    assert result["caught"]["by_gate"]


# --- the adversarial score ---------------------------------------------------------------


def _adversarial(attack_dec, attack_gate, findings=None):
    rows = _real(aligned=True)
    rows["attack_rebuild_identity_width_a-s0"] = {
        "kind": "ATTACK_CONSTRUCTION",
        "loss": 9.0,
        "dec": attack_dec,
        "infeasible": ("V2",),
    }
    results = _results(rows)
    verdicts = {m: {"verdict": "PASS"} for m in rows}
    verdicts["attack_rebuild_identity_width_a-s0"] = {"verdict": attack_gate}
    return run.adversarial(results, verdicts, findings or {})


def test_adversarial_passes_when_violators_score_low():
    result = _adversarial(-50.0, "PASS")
    assert result["counted"]["track_a"] == 1
    assert result["verdict"] == run.PASS


def test_adversarial_fails_when_a_violator_scores_in_the_top_half():
    result = _adversarial(-0.5, "PASS")
    assert result["in_top_half"] == ["attack_rebuild_identity_width_a-s0"]
    assert result["verdict"] == run.FAIL


def test_a_gate_failure_ranks_last_even_under_negative_scores():
    """Ruling 1: the deciding rule scores −E < 0, where the pinned
    `admissibility.gated` 0.0 would rank a FAIL first. The verdict ranks it
    last; the literal-0 reading is only a sensitivity line."""
    assert admissibility.gated(-0.5, 99.0) == 0.0  # the pinned helper, unchanged
    result = _adversarial(-0.5, "FAIL")
    assert result["verdict"] == run.PASS
    sensitivity = result["sensitivity_literal_zero"]
    assert sensitivity["in_top_half"] == ["attack_rebuild_identity_width_a-s0"]
    assert sensitivity["enters_verdict"] is False


def test_mode_x_findings_count_in_and_out_of_band():
    rows = _real(aligned=True)
    best = max(rows, key=lambda m: rows[m]["dec"])
    findings = {
        "in_band": [{"member": best, "design": "c1=1,c2=1"}],
        "out_of_band": [{"member": min(rows)}],
    }
    result = _adversarial(-50.0, "PASS", findings)
    assert result["counted"] == {
        "track_a": 1,
        "mode_x_in_band": 1,
        "mode_x_out_of_band": 1,
    }
    assert best in result["in_top_half"]
    assert result["verdict"] == run.FAIL


def test_top_half_is_the_frozen_cut():
    assert run.top_half(5, 10) and not run.top_half(6, 10)
    assert not run.top_half(None, 10)
    assert run.rank_in(-1.0, [-2.0, -0.5, None]) == (2, 3)


# --- construction integrity -----------------------------------------------------------


REFUSED = [
    {"label": "attack_recipe_surface_x", "codes": [["strategy.invalid", "/strategy"]]}
]


def _integrity(**changes):
    args = {
        "track_a_report": {
            "families": {"recipe_surface": "IN_PROGRESS"},
            "findings": [],
        },
        "refused": REFUSED,
        "frozen": {"refused": REFUSED},
        "bundles": {"a-s0": True, "b-s0": True},
        "failures": {},
        "scan": {
            "test": "tests/service/test_battery_track_a_service.py",
            "conclusion": "success",
        },
    }
    args.update(changes)
    return run.construction_integrity(**args)["verdict"]


def test_construction_integrity_known_answers():
    assert _integrity() == run.PASS
    assert _integrity(scan=None) == run.INCOMPLETE
    assert _integrity(scan={"conclusion": "failure"}) == run.FAIL
    finding = {"condition": "FAILING_TRIGGER"}
    breached = {"families": {"recipe_surface": "IN_PROGRESS"}, "findings": [finding]}
    assert _integrity(track_a_report=breached) == run.FAIL
    held = {"families": {"recipe_surface": "SPECIMEN_SILENT"}, "findings": []}
    assert _integrity(track_a_report=held) == run.FAIL
    assert _integrity(refused=[]) == run.FAIL
    assert _integrity(bundles={"a-s0": False}) == run.FAIL
    assert _integrity(bundles={"a-s0": None}) == run.FAIL
    typed = {"a-s0": {"member": "a-s0", "failure": "WorkerFailure: timeout"}}
    assert _integrity(bundles={"a-s0": None}, failures=typed) == run.PASS


def test_the_frozen_refusals_still_hold():
    frozen = json.loads((run.REPOSITORY / ev5.FREEZE_MANIFEST).read_bytes())
    from carbon.battery.value import panel as pn

    refused = pn.attack_constructions()["refused"]
    assert list(refused) == frozen["panel"]["attack_constructions"]["refused"]
    assert (
        run.construction_integrity(
            {"families": {}, "findings": []},
            refused,
            frozen["panel"]["attack_constructions"],
            {},
            {},
            {"conclusion": "success"},
        )["refusals_match_freeze"]
        is True
    )


# --- the run record ---------------------------------------------------------------------


def _repo(tmp_path):
    (tmp_path / "carbon" / "battery").mkdir(parents=True)
    (tmp_path / "carbon" / "battery" / "admissibility.py").write_text(
        "THRESHOLD_BANDS = 2.0\n"
    )
    (tmp_path / "carbon" / "__pycache__").mkdir()
    (tmp_path / "carbon" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    manifest = tmp_path / ev5.FREEZE_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "contract": {"digest": "sha256:" + "a" * 64},
                "confirmation": {
                    "commitment": {
                        "fingerprint": "sha256:" + "b" * 64,
                        "journal_sequence": 14,
                    }
                },
            }
        )
    )
    return tmp_path


def test_the_run_record_refuses_any_drift(tmp_path):
    repo = _repo(tmp_path)
    record = repo / "record.json"
    with pytest.raises(run.RunError, match="run_record_missing"):
        run.verify_pins(repo, record)
    run.pin(repo, record)
    with pytest.raises(run.RunError, match="run_record_exists"):
        run.pin(repo, record)
    assert "carbon/battery/admissibility.py" in run.verify_pins(repo, record)["files"]
    (repo / "carbon" / "__pycache__" / "y.pyc").write_bytes(b"\1")  # caches ignored
    run.verify_pins(repo, record)
    target = repo / "carbon" / "battery" / "admissibility.py"
    target.write_text("THRESHOLD_BANDS = 1.0\n")
    with pytest.raises(run.RunError, match="module_changed"):
        run.verify_pins(repo, record)
    target.write_text("THRESHOLD_BANDS = 2.0\n")
    (repo / "carbon" / "battery" / "new.py").write_text("")
    with pytest.raises(run.RunError, match="module_unpinned"):
        run.verify_pins(repo, record)
    (repo / "carbon" / "battery" / "new.py").unlink()
    target.unlink()
    with pytest.raises(run.RunError, match="module_missing"):
        run.verify_pins(repo, record)
    target.write_text("THRESHOLD_BANDS = 2.0\n")
    run.verify_pins(repo, record)
    (repo / ev5.FREEZE_MANIFEST).write_text("{}")
    with pytest.raises(run.RunError, match="manifest_changed"):
        run.verify_pins(repo, record)


def test_ranked_last_never_uses_the_literal_zero():
    scores = {"a": -0.5, "b": -2.0, "c": None}
    gated = run.ranked_last(scores, {"a": "FAIL"})
    assert gated["a"] < gated["b"] and gated["c"] is None
    assert run.literal_zero(scores, {"a": "FAIL"})["a"] == 0.0


# --- the sealed confirmation batch ------------------------------------------------------


def test_the_confirmation_batch_is_recalled_only_as_frozen(tmp_path):
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    pin = seeds.seed_pin("sha256:" + "1" * 64, "sha256:" + "2" * 64)
    journal.commit_root(root, pin)
    batch = seeds.make_batch(root, pin, ev5.CONFIRMATION_ROLE, 124, 4)
    with pytest.raises(ValueError, match="never committed"):
        run.recall_confirmation(
            root,
            pin,
            journal,
            {"fingerprint": batch.fingerprint, "journal_sequence": 1},
        )
    committed = journal.commit(batch, pool_version=0)
    good = {
        "fingerprint": committed.fingerprint,
        "journal_sequence": committed.sequence,
    }
    assert (
        run.recall_confirmation(root, pin, journal, good).fingerprint
        == batch.fingerprint
    )
    with pytest.raises(run.RunError, match="confirmation_fingerprint_mismatch"):
        run.recall_confirmation(
            root, pin, journal, {**good, "fingerprint": "sha256:" + "0" * 64}
        )
    with pytest.raises(run.RunError, match="confirmation_sequence_mismatch"):
        run.recall_confirmation(root, pin, journal, {**good, "journal_sequence": 14})
    assert len(journal.public()) == 2  # recall never commits
