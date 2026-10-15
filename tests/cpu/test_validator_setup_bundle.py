"""Public source packaging fixtures; no real image/host/chain acceptance."""

import json
import subprocess

import pytest

from carbon.battery import intake
from carbon.validator_setup import bundle as b


def command(root, *args):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for path, body in {
        "pyproject.toml": 'dependencies=["bittensor==11.1.0"]',
        "uv.lock": "public-fixture-lock",
        "carbon/validator_setup/__main__.py": "# public fixture entrypoint",
        "scripts/dev/battery_validator_service/__main__.py": "# public fixture service",
        ".agent/DECISIONS.md": "Public fixture history; no owner authority.\n",
        ".agent/decisions/fixture.md": "public fixture, no authority",
        ".agent/private.txt": "synthetic-excluded-agent-marker",
        "Business/private.txt": "synthetic-business-marker",
        "state/history.json": "synthetic-state-marker",
        "docs/development/evidence/exam-design-2026-09-24/private.json": "synthetic-excluded-marker",
        "scripts/dev/exam_design/private.py": "# synthetic excluded script",
        **{path: "public fixture material" for path in b.PUBLIC_RUNTIME_MATERIALS},
    }.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    command(root, "init", "-q")
    command(root, "config", "user.name", "Public Fixture")
    command(root, "config", "user.email", "fixture@example.invalid")
    command(root, "add", ".")
    command(root, "commit", "-qm", "public fixture")
    return root, command(root, "rev-parse", "HEAD")


def test_exact_tracked_blobs_ignore_worktree_edits_untracked_secrets_and_state(
    tmp_path,
):
    root, revision = source(tmp_path)
    (root / "uv.lock").write_text("modified worktree", encoding="utf-8")
    (root / "untracked.key").write_text("synthetic-key-marker", encoding="utf-8")
    built = b.materialize(root, revision, tmp_path / "release")
    assert (built.root / "uv.lock").read_text() == "public-fixture-lock"
    assert not (built.root / "Business").exists()
    assert not (built.root / "state").exists()
    assert not (built.root / "untracked.key").exists()
    assert not (built.root / ".agent/private.txt").exists()
    assert not (
        built.root / "docs/development/evidence/exam-design-2026-09-24/private.json"
    ).exists()
    assert not (built.root / "scripts/dev/exam_design/private.py").exists()
    assert b.PUBLIC_RUNTIME_MATERIALS <= {
        row["path"] for row in built.manifest["files"]
    }
    assert b.verify(built.root, built.digest) == built
    assert built.manifest["credentials_and_state"] == "EXTERNAL_ONLY"
    assert "NOT_QUALIFICATION" in built.manifest["scope"]


@pytest.mark.parametrize("decision", ["legacy", "file", "missing", "mismatched"])
def test_materialized_bundle_retains_exposure_decision_lookup(tmp_path, decision):
    root, _ = source(tmp_path)
    record = "OWNER-FIXTURE-INTAKE-EXPOSURE-01"
    authority = (
        root
        / ".agent"
        / ("DECISIONS.md" if decision == "legacy" else "decisions/fixture.md")
    )
    if decision == "missing":
        authority.unlink()
    else:
        heading = "#" if decision == "mismatched" else "##"
        authority.write_text(
            f"{heading} Synthetic fixture - {record}: no owner authority\n",
            encoding="utf-8",
            newline="\n",
        )
    command(root, "add", "-A")
    command(root, "commit", "-qm", "public fixture exposure record")
    built = b.materialize(
        root, command(root, "rev-parse", "HEAD"), tmp_path / "release"
    )
    assert b.verify(built.root, built.digest) == built
    config = {
        "host": "127.0.0.1",
        "exposure": {
            "via": "trusted_proxy",
            "header": "CF-Connecting-IP",
            "record": record,
        },
    }
    if decision in ("legacy", "file"):
        intake.require_exposure(config, repository=built.root)
    else:
        with pytest.raises(
            intake.IntakeUnavailable, match="^intake_exposure_unrecorded$"
        ):
            intake.require_exposure(config, repository=built.root)
    config["exposure"]["record"] = "OWNER-FIXTURE-INTAKE-EXPOSURE-99"
    with pytest.raises(intake.IntakeUnavailable, match="^intake_exposure_unrecorded$"):
        intake.require_exposure(config, repository=built.root)


def test_missing_exposure_history_refuses_before_writing_destination(tmp_path):
    root, _ = source(tmp_path)
    command(root, "rm", ".agent/DECISIONS.md")
    command(root, "commit", "-qm", "public fixture missing exposure history")
    destination = tmp_path / "release"
    with pytest.raises(b.SetupRefused, match="COMPLETE_OPERATOR_SOURCE_REQUIRED"):
        b.materialize(root, command(root, "rev-parse", "HEAD"), destination)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["bytes", "extra", "manifest", "symlink"])
def test_changed_bytes_manifest_file_set_or_symlink_refuse(tmp_path, kind):
    root, revision = source(tmp_path)
    built = b.materialize(root, revision, tmp_path / "release")
    if kind == "bytes":
        target = built.root / "uv.lock"
        target.chmod(0o644)
        target.write_bytes(b"changed")
        target.chmod(0o444)
    elif kind == "extra":
        (built.root / "new.key").write_bytes(b"synthetic-secret-marker")
    elif kind == "manifest":
        target = built.root / b.MANIFEST
        target.chmod(0o644)
        value = json.loads(target.read_bytes())
        value["sdk"] = "unreviewed-sdk"
        target.write_bytes(b.encoded(value))
    else:
        (built.root / "outside").symlink_to(root, target_is_directory=True)
    with pytest.raises(b.SetupRefused):
        b.verify(built.root, built.digest)


@pytest.mark.parametrize(
    "path",
    [
        "../state",
        "/absolute",
        "carbon/../private",
        "carbon\\private",
        "C:/private",
        "wallet/key",
        "carbon//file",
    ],
)
def test_payload_paths_are_closed_and_cannot_escape(path):
    with pytest.raises(b.SetupRefused):
        b.safe_path(path)


def test_nonempty_target_or_mutable_revision_never_overwrites(tmp_path):
    root, revision = source(tmp_path)
    target = tmp_path / "release"
    target.mkdir()
    marker = target / "history"
    marker.write_bytes(b"keep")
    with pytest.raises(b.SetupRefused):
        b.materialize(root, revision, target)
    with pytest.raises(b.SetupRefused, match="EXACT_SOURCE_REVISION_REQUIRED"):
        b.materialize(root, "main", tmp_path / "another")
    assert marker.read_bytes() == b"keep"
    assert not (tmp_path / "another").exists()


@pytest.mark.parametrize("missing", sorted(b.PUBLIC_RUNTIME_MATERIALS))
def test_missing_public_material_refuses_before_writing_destination(tmp_path, missing):
    root, _ = source(tmp_path)
    command(root, "rm", missing)
    command(root, "commit", "-qm", "public fixture missing material")
    destination = tmp_path / "release"
    with pytest.raises(
        b.SetupRefused, match="COMPLETE_PUBLIC_RUNTIME_MATERIAL_REQUIRED"
    ):
        b.materialize(root, command(root, "rev-parse", "HEAD"), destination)
    assert not destination.exists()


def test_historical_bundle_verification_preserves_original_file_set(tmp_path):
    root, revision = source(tmp_path)
    built = b.materialize(root, revision, tmp_path / "release")
    manifest = dict(built.manifest)
    historical_omissions = b.PUBLIC_RUNTIME_MATERIALS | {".agent/DECISIONS.md"}
    manifest["files"] = [
        row for row in manifest["files"] if row["path"] not in historical_omissions
    ]
    for path in historical_omissions:
        target = built.root / path
        target.chmod(0o644)
        target.unlink()
    manifest_path = built.root / b.MANIFEST
    manifest_path.chmod(0o644)
    raw = b.encoded(manifest)
    manifest_path.write_bytes(raw)
    manifest_path.chmod(0o444)
    assert b.verify(built.root, b.sha(raw)).manifest == manifest
