"""Registered metadata in public Gitless bundles; never scoring or host acceptance."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_battery_validator_service import checks, throwaway
from test_validator_setup_bundle import command, source

from carbon.battery import deployment
from carbon.battery.value import registered_score as rs
from carbon.battery.value import score_tuning as st
from carbon.validator_setup import bundle as b
from scripts.dev.battery_validator_service import service as svc
from scripts.dev.battery_validator_service import supervisor as sup

REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRY = "docs/development/evidence/battery-score-tuning/registry-v5.json"
DECISION_PATH = ".agent/decisions/2026-10-11-OWNER-BATTERY-SCORE-CANDIDATE-01.md"
CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
TERM = {
    "registry": REGISTRY,
    "registry_sha256": "70f2943814db0531429613e6ca5e2bd1c0b656673c6ee74de08e98f540758277",
    "candidate": "G-FEAS/A-Q>@0.05",
    "decision": "OWNER-BATTERY-SCORE-CANDIDATE-01",
}


@pytest.fixture(autouse=True)
def metadata_only(monkeypatch):
    monkeypatch.delenv(b.RUNTIME_DIGEST_ENV, raising=False)
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    monkeypatch.setattr(deployment, "_SCORE_SETUP", None)

    def forbidden(*_args, **_kwargs):
        pytest.fail("metadata readiness must not compute a score")

    for name in ("member_legs", "score_member", "gate_verdict"):
        monkeypatch.setattr(st, name, forbidden)


def metadata_source(tmp_path):
    root, _revision = source(tmp_path)
    # Only already public committed metadata, not prediction/reference cases.
    for path in (REGISTRY, DECISION_PATH, CONTRACT):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPOSITORY / path).read_bytes())
    command(root, "add", "-A")
    command(root, "commit", "-qm", "public registered metadata fixture")
    return root, command(root, "rev-parse", "HEAD")


@pytest.fixture
def release(tmp_path):
    root, revision = metadata_source(tmp_path)
    return b.materialize(root, revision, tmp_path / "release")


def test_actual_registered_candidate_installs_from_verified_gitless_bundle(release):
    assert REGISTRY in b.PUBLIC_RUNTIME_MATERIALS
    assert not (release.root / ".git").exists()
    target = SimpleNamespace(rule={"score": TERM}, repository=release.root)
    with b.runtime_identity(release):
        assert rs.install(target) is target
    assert target.registered_score.candidate.id == TERM["candidate"]
    assert (
        target.registered_score.registry_identity["sha256"] == TERM["registry_sha256"]
    )
    assert target.registered_score.registry_identity["commit"] == (
        release.manifest["source_revision"]
    )
    assert b.RUNTIME_DIGEST_ENV not in os.environ


def test_a_bundle_cannot_supply_its_own_expected_manifest_pin(release):
    with pytest.raises(
        rs.RegisteredScoreRefused, match="registered_score_bundle_unbound"
    ):
        rs.RegisteredScore(TERM, release.root)


def test_wrong_external_pin_and_symlink_release_do_not_gain_bundle_trust(
    release, monkeypatch, tmp_path
):
    monkeypatch.setenv(b.RUNTIME_DIGEST_ENV, "sha256:" + "0" * 64)
    with pytest.raises(
        rs.RegisteredScoreRefused, match="registered_score_bundle_refused"
    ):
        rs.RegisteredScore(TERM, release.root)
    monkeypatch.setenv(b.RUNTIME_DIGEST_ENV, release.digest)
    link = tmp_path / "release-link"
    link.symlink_to(release.root, target_is_directory=True)
    with pytest.raises(
        rs.RegisteredScoreRefused, match="registered_score_bundle_refused"
    ):
        rs.RegisteredScore(TERM, link)


def test_runtime_identity_rejects_a_different_inherited_pin(release, monkeypatch):
    monkeypatch.setenv(b.RUNTIME_DIGEST_ENV, "sha256:" + "0" * 64)
    with (
        pytest.raises(b.SetupRefused, match="EXECUTION_BUNDLE_DIGEST_DIFFERS"),
        b.runtime_identity(release),
    ):
        pytest.fail("a different inherited release pin must refuse")


@pytest.mark.parametrize("change", ("missing", "tampered", "unmanifested"))
def test_registry_omission_tamper_and_unmanifested_bytes_refuse(release, change):
    registry = release.root / REGISTRY
    if change == "missing":
        registry.parent.chmod(0o755)
        registry.unlink()
    elif change == "tampered":
        registry.chmod(0o644)
        registry.write_bytes(registry.read_bytes() + b"\n")
        registry.chmod(0o444)
    else:
        manifest = release.root / b.MANIFEST
        raw = json.loads(manifest.read_bytes())
        raw["files"] = [row for row in raw["files"] if row["path"] != REGISTRY]
        manifest.chmod(0o644)
        manifest.write_bytes(b.encoded(raw))
        manifest.chmod(0o444)
        # Even an externally pinned manifest may not conceal an extra file.
        release = b.VerifiedBundle(release.root, b.sha(manifest.read_bytes()), raw)
    with (
        b.runtime_identity(release),
        pytest.raises(
            rs.RegisteredScoreRefused, match="registered_score_bundle_refused"
        ),
    ):
        rs.RegisteredScore(TERM, release.root)


@pytest.mark.parametrize(
    "change,reason",
    (
        ({"registry_sha256": "0" * 64}, "registered_score_registry_changed"),
        (
            {"candidate": "not-a-registered-candidate"},
            "registered_score_candidate_unknown",
        ),
        ({"decision": "OWNER-NOT-RECORDED-99"}, "registered_score_decision_unrecorded"),
        (
            {"registry": REGISTRY.replace("registry-v5", "registry-v6")},
            "registered_score_registry_unavailable",
        ),
    ),
)
def test_bundle_keeps_configured_sha_candidate_and_decision_checks(
    release, change, reason
):
    with (
        b.runtime_identity(release),
        pytest.raises(rs.RegisteredScoreRefused, match=reason),
    ):
        rs.RegisteredScore({**TERM, **change}, release.root)


@pytest.mark.parametrize("change", ("clean", "dirty", "uncommitted", "nongit"))
def test_checkout_registration_provenance_is_not_replaced_by_a_missing_git_fallback(
    tmp_path, change
):
    root, _revision = metadata_source(tmp_path)
    term = dict(TERM)
    if change == "dirty":
        path = root / REGISTRY
        path.write_bytes(path.read_bytes() + b"\n")
    elif change == "uncommitted":
        term["registry"] = REGISTRY.replace("registry-v5", "registry-uncommitted")
        (root / term["registry"]).write_bytes((root / REGISTRY).read_bytes())
    elif change == "nongit":
        detached = tmp_path / "not-a-checkout"
        (detached / REGISTRY).parent.mkdir(parents=True)
        (detached / REGISTRY).write_bytes((root / REGISTRY).read_bytes())
        root = detached
    if change == "clean":
        assert rs.RegisteredScore(term, root).candidate.id == TERM["candidate"]
    else:
        with pytest.raises(
            rs.RegisteredScoreRefused, match="registered_score_registry_unavailable"
        ):
            rs.RegisteredScore(term, root)


def test_preflight_refuses_missing_active_registry_before_deployment_build(tmp_path):
    term = {**TERM, "registry": REGISTRY.replace("registry-v5", "registry-missing")}
    made = throwaway(
        tmp_path, deployment_changes={"rule": "v3-bank-sched", "score": term}
    )
    report = svc.preflight(made.service, repository=REPOSITORY)
    assert report["ready"] is False
    found = checks(report)
    assert (
        found["registered_score"]["refused"] == "registered_score_registry_unavailable"
    )
    assert found["deployment"]["status"] == "skipped"


def test_preflight_without_a_registered_term_is_explicitly_not_applicable():
    assert svc.check_registered_score({}, REPOSITORY) == {"status": "not_applicable"}


def test_invalid_unit_bundle_pin_refuses_before_config_or_output_access(tmp_path):
    with pytest.raises(svc.ServiceRefused, match="bundle_digest_malformed"):
        sup.units(
            tmp_path / "absent-config", tmp_path / "units", bundle_digest="bad\npin"
        )
    assert not (tmp_path / "units").exists()


def test_fresh_operator_process_binds_registered_preflight_and_host_units(
    tmp_path,
):
    revision = command(REPOSITORY, "rev-parse", "HEAD")
    release = b.materialize(REPOSITORY, revision, tmp_path / "release")
    made = throwaway(
        tmp_path / "public-fixture-state",
        deployment_changes={"rule": "v3-bank-sched", "score": TERM},
    )
    # The operator prepares this owner-only directory before acquiring the
    # runtime lease; direct service.preflight fixtures do not need the lease.
    svc.load_service(made.service).state_dir.mkdir(mode=0o700)
    env = {
        **os.environ,
        "PYTHONPATH": str(release.root),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop(b.RUNTIME_DIGEST_ENV, None)
    env.pop("CARBON_VALIDATOR_IMAGE_BUNDLE_DIGEST", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.validator_setup",
            "service",
            "preflight",
            "--bundle",
            str(release.root),
            "--digest",
            release.digest,
            "--config",
            str(made.service),
        ],
        cwd=release.root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ready"] is True
    assert checks(report)["registered_score"]["detail"]["status"] == "metadata_verified"
    unit_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.validator_setup",
            "service",
            "units",
            "--bundle",
            str(release.root),
            "--digest",
            release.digest,
            "--config",
            str(made.service),
            "--out",
            str(tmp_path / "units"),
        ],
        cwd=release.root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert unit_result.returncode == 0, unit_result.stdout + unit_result.stderr
    written = json.loads(unit_result.stdout)["units"]
    assert len(written) == 2
    for path in written:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        bindings = [
            line.removeprefix("Environment=")
            for line in lines
            if line.startswith("Environment=" + b.RUNTIME_DIGEST_ENV + "=")
        ]
        assert bindings == [b.RUNTIME_DIGEST_ENV + "=" + release.digest]
    preflight = shlex.split(
        next(
            line.removeprefix("ExecStartPre=")
            for line in lines
            if line.startswith("ExecStartPre=")
        )
    )
    # Reproduce a later systemd process using only the generated pin; no
    # inheritance from the unit generator or operator wrapper is available.
    later = subprocess.run(
        preflight,
        cwd=release.root,
        env={**env, b.RUNTIME_DIGEST_ENV: bindings[0].split("=", 1)[1]},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert later.returncode == 0, later.stdout + later.stderr
    assert (
        checks(json.loads(later.stdout))["registered_score"]["detail"]["status"]
        == "metadata_verified"
    )
    missing_pin = subprocess.run(
        preflight,
        cwd=release.root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert missing_pin.returncode == 2, missing_pin.stdout + missing_pin.stderr
    assert (
        checks(json.loads(missing_pin.stdout))["registered_score"]["refused"]
        == "registered_score_bundle_unbound"
    )
