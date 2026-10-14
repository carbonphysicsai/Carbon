"""Public synthetic metadata targets; never a worker, provider or host run."""

from __future__ import annotations

import dataclasses
import json
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.attack import target_binding as targets
from carbon.agent_campaign.attack.adapters import battery_level4 as l4
from carbon.development_session.profile import canonical, digest

POSIX = pytest.mark.skipif(os.name != "posix", reason="secure POSIX target intake")
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def public_template():
    if os.name != "posix":
        pytest.skip("metadata admission imports POSIX Graphite")
    from carbon.agent_campaign.graphite import delivery, experiment
    from carbon.battery import level4 as battery
    from carbon.level4 import allowlist, intake, staging, submission
    from carbon.reconstruction.artifact_identity import build_identity

    strategy = json.loads(json.dumps(battery.level0_strategies()["scaffold_mlp"]))
    manifest, files = battery.lower_recipe(
        strategy, allowlist.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    raw = submission.canonical(manifest)
    envelope = staging.envelope(raw, files)
    strategy["parameters"][battery.FIELD] = envelope["submission"]
    recipe = experiment.admit(
        strategy, 7, variant=l4.variant(), workspace=staging.workspace(raw, files)
    )
    bodies = {name: b"{}" for name in delivery.FILES}
    bodies.update(
        {
            "strategy.json": canonical(strategy),
            "recipe.json": canonical(recipe),
            "score.json": canonical(
                {"recipe_digest": recipe["recipe_digest"], "fixture_only": True}
            ),
            delivery.LEVEL4_ENVELOPE: canonical(envelope),
        }
    )
    shown = {
        "schema": delivery.BUNDLE_SCHEMA,
        "proposal_id": "synthetic-target",
        "run_id": "synthetic-public-fixture",
        "files": {name: digest(body) for name, body in bodies.items()},
        "contract_digest": recipe["contract_digest"],
        "record_sequence": recipe["record_sequence"],
        "recipe_digest": recipe["recipe_digest"],
        "artifact": build_identity(recipe),
        "authority_granted": False,
        "official_eligible": False,
    }
    bodies["manifest.json"] = canonical(shown)
    return bodies


def exported(tmp_path, template, *, change=None):
    root = tmp_path / "public-exports"
    folder = root / "target-a"
    folder.mkdir(parents=True)
    bodies = dict(template)
    if change is not None:
        change(bodies)
    for name, body in bodies.items():
        (folder / name).write_bytes(body)
    return root, "target-a", digest(bodies["manifest.json"])


@pytest.fixture
def bound(tmp_path, public_template):
    source = exported(tmp_path, public_template)
    return targets.load(*source, l4.ADAPTER, repository=ROOT), source


@pytest.mark.parametrize("value", [{}, SimpleNamespace(), "sha256:" + "0" * 64])
def test_raw_or_claimed_context_never_becomes_a_validated_binding(value):
    with pytest.raises(targets.TargetRefused, match="requires_validated_intake"):
        targets.require(value, l4.ADAPTER)
    with pytest.raises(targets.TargetRefused, match="requires_validated_intake"):
        targets.TargetBinding()


def test_duplicate_and_nonfinite_json_are_closed_refusals():
    for body in (b'{"x":1,"x":2}', b'{"x":NaN}'):
        with pytest.raises(targets.TargetRefused):
            targets._json(body)


def test_the_registered_fixture_is_non_runtime_evidence():
    path = ROOT / "tests/fixtures/graphite/target_binding_controls.json"
    fixture = json.loads(path.read_bytes())
    assert fixture["evidence_class"] == "TEST_ONLY"
    assert fixture["runtime_authority"] == "UNAVAILABLE"
    assert len(set(fixture["cases"])) == len(fixture["cases"]) == 12


def test_unsupported_filesystem_intake_fails_before_opening_a_source(monkeypatch):
    monkeypatch.setattr(targets.os, "supports_dir_fd", frozenset())
    monkeypatch.setattr(targets.os, "open", lambda *_a, **_k: pytest.fail("opened"))
    with pytest.raises(
        targets.TargetRefused, match="secure_filesystem_intake_unavailable"
    ):
        targets.load(
            "not-a-source",
            "target-a",
            "sha256:" + "0" * 64,
            l4.ADAPTER,
            repository=ROOT,
        )


def test_loaded_public_pins_are_immutable_and_rebuild_views_are_copies(bound):
    target, (root, name, expected) = bound
    pin = target.record()
    assert pin["manifest_digest"] == expected
    assert pin["challenge_id"] == l4.CHALLENGE_ID
    assert pin["variant_digest"] == l4.ADAPTER.contract_digest
    assert pin["level"] == 4 and pin["submission_digest"].startswith("sha256:")
    with pytest.raises(dataclasses.FrozenInstanceError):
        target._pin = b"{}"
    original = target.strategy()
    view = target.strategy()
    view.clear()
    workspace = target.workspace()
    workspace.clear()
    (root / name / "strategy.json").write_bytes(b"changed after capture")
    assert target.strategy() == original
    assert target.workspace()
    pin.clear()
    assert target.record()["manifest_digest"] == expected


@pytest.mark.parametrize("name", ["../target-a", "/target-a", "target-a/file", ".", ""])
def test_target_selector_cannot_follow_a_path(tmp_path, public_template, name):
    root, _name, expected = exported(tmp_path, public_template)
    with pytest.raises(targets.TargetRefused, match="bundle_name_invalid"):
        targets.load(root, name, expected, l4.ADAPTER, repository=ROOT)


def test_independent_manifest_pin_and_all_file_digests_are_consumed(
    tmp_path, public_template
):
    root, name, expected = exported(tmp_path, public_template)
    with pytest.raises(targets.TargetRefused, match="manifest_digest_mismatch"):
        targets.load(root, name, "sha256:" + "0" * 64, l4.ADAPTER, repository=ROOT)
    path = root / name / "level4-envelope.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(targets.TargetRefused, match="file_digest_mismatch"):
        targets.load(root, name, expected, l4.ADAPTER, repository=ROOT)


@pytest.mark.parametrize("kind", ["ancestor", "directory", "file", "hardlink", "fifo"])
def test_source_links_and_nonregular_files_are_refused(tmp_path, public_template, kind):
    root, name, expected = exported(tmp_path, public_template)
    folder = root / name
    if kind == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    elif kind == "directory":
        real = root / "real-target"
        folder.rename(real)
        folder.symlink_to(real, target_is_directory=True)
    else:
        path = folder / "recipe.json"
        real = tmp_path / "public-record.json"
        path.rename(real)
        if kind == "file":
            path.symlink_to(real)
        elif kind == "hardlink":
            os.link(real, path)
        else:
            os.mkfifo(path)
    with pytest.raises(targets.TargetRefused):
        targets.load(root, name, expected, l4.ADAPTER, repository=ROOT)


@pytest.mark.parametrize(
    "kind",
    [
        "missing-envelope",
        "extra-path",
        "wrong-challenge",
        "wrong-variant",
        "wrong-contract",
    ],
)
def test_missing_or_rebound_metadata_is_not_a_target(tmp_path, public_template, kind):
    def change(bodies):
        manifest = json.loads(bodies["manifest.json"])
        if kind == "missing-envelope":
            del bodies["level4-envelope.json"]
            del manifest["files"]["level4-envelope.json"]
        elif kind == "extra-path":
            manifest["files"]["../not-readable.json"] = "sha256:" + "0" * 64
        else:
            recipe = json.loads(bodies["recipe.json"])
            if kind == "wrong-challenge":
                recipe["challenge"]["id"] = "different-public-challenge"
            elif kind == "wrong-variant":
                recipe["development"]["variant_digest"] = "sha256:" + "0" * 64
            else:
                recipe["contract_digest"] = "sha256:" + "0" * 64
            bodies["recipe.json"] = canonical(recipe)
            manifest["files"]["recipe.json"] = digest(bodies["recipe.json"])
        bodies["manifest.json"] = canonical(manifest)

    source = exported(tmp_path, public_template, change=change)
    with pytest.raises(targets.TargetRefused):
        targets.load(*source, l4.ADAPTER, repository=ROOT)


def attempt_for(target, *, result=None, tool="compile_strategy", arguments=None):
    from carbon.agent_campaign.attack import analysis

    return analysis.Attempt(
        identity="epoch-1-tool-001",
        epoch=1,
        stage=None,
        turn=1,
        position=0,
        tool=analysis.PREFIX + tool,
        arguments=(
            arguments
            if arguments is not None
            else {"strategy_json": json.dumps(target.strategy())}
        ),
        result={"accepted": True} if result is None else result,
        withheld=None,
        intent_digest=digest(b"public fixture intent"),
        result_digest=digest(b"public fixture result"),
    )


@pytest.mark.parametrize("pods", [None, {}, {"executed": True, "backend": "gpu"}])
def test_the_actual_verifier_binds_metadata_but_never_trusts_worker_claims(bound, pods):
    from carbon.agent_campaign.attack import verify

    target, _source = bound
    verdict = verify.verify(attempt_for(target), l4.ADAPTER, target=target, pods=pods)
    assert verdict.outcome == verify.UNDETERMINED and not verdict.scored
    assert verdict.artifact == target.record()["build_artifact"]
    assert verdict.evidence["target_pin"] == target.pin
    assert verdict.evidence["target_binding"] == target.record()
    assert verdict.reason == (
        targets.RUNTIME_UNAVAILABLE
        if pods is None
        else "target_worker_evidence_not_authorized"
    )


def test_another_construction_cannot_be_counted_as_attacking_the_bound_artifact(bound):
    from carbon.agent_campaign.attack import verify

    target, _source = bound
    strategy = target.strategy()
    strategy["parameters"]["composition_graphs"] = "sha256:" + "0" * 64
    verdict = verify.verify(
        attempt_for(target, arguments={"strategy_json": json.dumps(strategy)}),
        l4.ADAPTER,
        target=target,
    )
    assert verdict.outcome == verify.UNDETERMINED and not verdict.scored
    assert verdict.artifact is None
    assert verdict.reason == "target_construction_or_stage_substituted"


def test_targeting_does_not_hide_an_existing_miner_path_isolation_finding(bound):
    from carbon.agent_campaign.attack import verify

    target, _source = bound
    attempt = attempt_for(
        target,
        tool="start_research_task",
        arguments={"kind": "workspace", "action": "run_python", "arguments_json": "{}"},
    )
    verdict = verify.verify(
        attempt, l4.ADAPTER, target=target, carrier={"network_attempts": 1}
    )
    assert verdict.outcome == verify.BREACHED and verdict.finding
    assert verdict.evidence["verification_scope"] == "research_path"
    assert not verdict.scored and verdict.artifact is None


def test_same_artifact_different_target_cannot_replace_a_resume_or_specimen(
    bound, tmp_path, public_template
):
    from carbon.agent_campaign.attack import verify

    target, _source = bound

    def change(bodies):
        manifest = json.loads(bodies["manifest.json"])
        manifest["run_id"] = "another-public-fixture-export"
        bodies["manifest.json"] = canonical(manifest)

    source = exported(tmp_path / "second", public_template, change=change)
    other = targets.load(*source, l4.ADAPTER, repository=ROOT)
    assert other.record()["build_artifact"] == target.record()["build_artifact"]
    assert other.pin != target.pin
    store = tmp_path / "session"
    store.mkdir()
    targets.session_pin(store, 1, target, resume=False, adapter=l4.ADAPTER)
    targets.session_pin(store, 1, target, resume=True, adapter=l4.ADAPTER)
    for replacement in (other, None):
        with pytest.raises(targets.TargetRefused, match="pin_changed"):
            targets.session_pin(store, 1, replacement, resume=True, adapter=l4.ADAPTER)
    rebuilt = l4.ADAPTER.rebuild_target(target.strategy(), target)
    record = verify.record_of(rebuilt)
    folder = tmp_path / "specimen"
    verify.bundle_attack_specimen(
        l4.ADAPTER,
        target.strategy(),
        record,
        folder,
        label="synthetic-only",
        artifact=target.record()["build_artifact"],
        target=target,
    )
    assert (
        verify.clean_attack_specimen(folder, l4.ADAPTER, target=target)["status"]
        == "REBUILT"
    )
    for replacement in (None, other):
        assert (
            verify.clean_attack_specimen(folder, l4.ADAPTER, target=replacement)[
                "status"
            ]
            == "REBUILD_MISMATCH"
        )


def test_missing_or_linked_resume_pin_fails_closed(bound, tmp_path):
    target, _source = bound
    store = tmp_path / "session"
    store.mkdir()
    with pytest.raises(targets.TargetRefused, match="pin_missing"):
        targets.session_pin(store, 1, target, resume=True, adapter=l4.ADAPTER)
    real = tmp_path / "other-pins"
    real.mkdir()
    (store / "target-pins").symlink_to(real, target_is_directory=True)
    with pytest.raises(targets.TargetRefused, match="unavailable_or_linked"):
        targets.session_pin(store, 1, target, resume=False, adapter=l4.ADAPTER)
    assert list(real.iterdir()) == []


def test_the_actual_cli_loads_the_target_before_delegating_a_dry_run(
    bound, monkeypatch, tmp_path
):
    from carbon.agent_campaign.graphite import phase4

    target, (root, name, expected) = bound
    seen = []
    monkeypatch.setattr(
        phase4, "dry_run", lambda *a, **kw: seen.append(kw["target"]) or 0
    )
    monkeypatch.setattr(phase4, "live_model", lambda *_a, **_kw: pytest.fail("model"))
    argv = [
        "run",
        "--root",
        str(tmp_path / "run"),
        "--challenge",
        l4.CHALLENGE_ID,
        "--level",
        "4",
        "--dry-run",
        "--public-target-root",
        str(root),
        "--target-bundle",
        name,
        "--target-manifest-digest",
        expected,
    ]
    assert phase4.main(argv) == 0
    assert len(seen) == 1 and seen[0].pin == target.pin
    argv[-1] = "sha256:" + "0" * 64
    with pytest.raises(phase4.RunnerRefused, match="manifest_digest_mismatch"):
        phase4.main(argv)
    assert len(seen) == 1


def test_legacy_briefs_have_no_target_and_targeted_briefs_carry_the_same_pin(bound):
    from carbon.agent_campaign.graphite import phase4

    target, _source = bound
    assert "verification_scope" not in phase4.brief_observation(l4.ADAPTER)
    observation = phase4.brief_observation(l4.ADAPTER, target=target)
    assert observation["verification_scope"] == targets.scope(target, l4.ADAPTER)


def test_scripted_session_consumes_the_target_in_its_actual_verifier_and_report(
    bound, tmp_path, monkeypatch, capsys
):
    from carbon.agent_campaign.graphite import phase4

    target, _source = bound
    monkeypatch.setattr(phase4, "ATTACK_BUDGET", 1)
    run_root = tmp_path / "scripted-session"
    run_root.mkdir()
    result = phase4.dry_run(
        run_root,
        l4.ADAPTER,
        phase4.attack_modules(),
        challenge=l4.CHALLENGE_ID,
        variant=l4.variant(),
        target=target,
    )
    assert result == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["session"]["schema"] == phase4.TARGET_LOG_SCHEMA
    assert shown["session"]["verification_scope"] == targets.scope(target, l4.ADAPTER)
    coverage = shown["coverage"]
    assert coverage["schema"] == phase4.TARGET_COVERAGE_SCHEMA
    assert coverage["verification_scope"] == targets.scope(target, l4.ADAPTER)
    assert coverage["target_runtime_verdict"] == "UNDETERMINED"
    assert coverage["targeted_scored_attempts"] == 0
    assert coverage["verdicts"]
    assert all(v["evidence"]["target_pin"] == target.pin for v in coverage["verdicts"])
    assert Decimal(shown["dry_run"]["settled_usd"]) == 0


def test_session_target_drift_is_refused_before_a_controller_can_launch(
    bound, tmp_path
):
    from carbon.agent_campaign.graphite import phase4

    target, _source = bound
    brief = SimpleNamespace(initial_observation={})
    control = SimpleNamespace(grant=SimpleNamespace(permitted_runs=1))
    with pytest.raises(phase4.RunnerRefused, match="target_brief_binding_changed"):
        phase4.run_session(
            tmp_path,
            control,
            None,
            l4.ADAPTER,
            brief,
            1,
            {},
            budget=1,
            kstore=None,
            view=None,
            variant=l4.variant(),
            target=target,
        )
