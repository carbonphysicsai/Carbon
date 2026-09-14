"""Create a deterministic source/test/evidence release bundle and checksum manifest."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.json"
ARCHIVE = ROOT / "Carbon_Physics_Goal_Workbench_v0_5.zip"
EXCLUDED = {
    MANIFEST.name,
    ARCHIVE.name,
    "Carbon_Physics_Goal_Workbench_v0_4.zip",
    "Carbon_Physics_Goal_Workbench_v0_3.zip",
    "Carbon_Physics_Opportunity_Workbench_v0_2.zip",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integration_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def payloads() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and p.name not in EXCLUDED
        and "__pycache__" not in p.parts
        and not p.name.endswith(".pyc")
    )


def build() -> tuple[Path, Path]:
    files = payloads()
    manifest = {
        "schema_version": "carbon.workbench.release-manifest.v0.5",
        "status": "OFFLINE_DECISION_SUPPORT_NOT_PRODUCTION",
        "application_version": "Carbon Goal-to-Challenge Workbench v0.5",
        "decision_ids": [
            "EXAM-PROTECT-WORKBENCH-01",
            "GOAL-WORKBENCH-02",
            "GOAL-WORKBENCH-03",
            "GOAL-WORKBENCH-04",
            "GOAL-WORKBENCH-05",
        ],
        "repository_base": "e576fbdc711c9194dbcc7d90405480e90577407e",
        "integration_revision_at_packaging": integration_revision(),
        "integration_revision_note": (
            "The checksum manifest describes exact packaged bytes. A commit cannot "
            "contain its own digest; final PR/head identity is reported by delivery."
        ),
        "pinned_research_revision": "ca904dfee93d3574df4e56b99981a6ed3b138e80",
        "accepted_research_head": "0a5690270dc449ea19c941280203987d37db5283",
        "research_merge_commit": "2ac835d1dd55deb9c99e493f3615143efa2e51e0",
        "research_acceptance_run": 34786945000,
        "historical_failed_research_run": 34778525936,
        "accepted_delivery_prerequisite_main": "1a1a5ad4585caebd168725451ca255e06561f693",
        "accepted_workbench_baseline": {
            "pull_request": 156,
            "accepted_head": "3ebc7ac6b1bb72163733db764f89f11f05c8009b",
            "acceptance_run": 34794655627,
            "merge_commit": "3fb98bfbfb9ca8dd3f6dd0d8e5a588a89b1c9932",
        },
        "hub_fixture_repair": {
            "pull_request": 159,
            "accepted_head": "fe89cfa6ca5699dfd00d748e974fbf3a90351043",
            "acceptance_run": 34791088907,
            "merge_commit": "8361181d6690e8c56bcba3805018f41cd4752e45",
        },
        "test_boundary_repair": {
            "pull_request": 160,
            "accepted_head": "2bedd74b4dac8ca49f32e6a2ceb1c356a68d199c",
            "acceptance_run": 34792307014,
            "merge_commit": "1a1a5ad4585caebd168725451ca255e06561f693",
        },
        "pinned_evidence_index_sha256": "4565995a98fe8f238ca88b44e418e6c7da2954de9dca577b80968854bad34ba7",
        "source_archive_sha256": "aabdc04377700334f50a8748bf28b9fc3e44799b8986d2c38f759df5726469fa",
        "accepted_goal_workbench_baseline": {
            "pull_request": 170,
            "accepted_head": "3a01e099466a613ed61cafaf5735d802c62ad3d4",
            "acceptance_run": 34891993646,
            "merge_commit": "e576fbdc711c9194dbcc7d90405480e90577407e",
        },
        "accepted_detached_research_reference": {
            "decision_id": "D-QUAL-PREP-01",
            "pull_request": 176,
            "accepted_head": "1024cd5a0d7bf67bb16f521412309d46dec8df79",
            "acceptance_run": 34894022768,
            "merge_commit": "1fd272c498b7a2b82ab162286c0b739ecc6274a7",
            "owner_request": "https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5670993432",
            "owner_request_status": "EXPORTED_OWNER_REQUEST",
            "authority": "External linked research reference only; not acknowledged, approved, selected, funded, executed, or qualified by this workbench.",
        },
        "accepted_c05_measurement_source": {
            "pull_request": 157,
            "accepted_head": "8dbee54dcd5bdea3a76b22812955e31fbe95e8da",
            "acceptance_run": 34789621325,
            "merge_commit": "e3324691666da6b8987764048d2bfff45e0578b4",
            "fixture_index_sha256": sha256(ROOT / "data/c05_fixture_index_v1.json"),
            "authority": "Public DEVELOPMENT raw measurement evidence only; no scientific limit, uncertainty qualification, score, approval, or launch authority.",
        },
        "grok_plan_artifact": {
            "name": "Carbon_Grok_Master_Plan_v1_9.docx",
            "source_version": "v1.9",
            "source_docx_sha256": "799108791ec951ebfd51b2d56c35f70df51ebc559929a4991cc118efd13981b5",
            "source_docx_digest_status": "VERIFIED_BEFORE_RENDER",
            "rendered_pdf_sha256": "925ff210a40bbb9bd5136d95e8ea937beac5c775e472df5258ab6d4736cec2cb",
            "pages_inspected": 10,
            "use": "Operating conformance only; no Grok/account integration is claimed.",
        },
        "authority": "No runtime sharing, qualification, protected-use approval, answer publication, submission, registration, execution, launch, deployment, or rights authority is conveyed.",
        "file_count": len(files),
        "files": {
            str(path.relative_to(ROOT)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive_files = payloads() + [MANIFEST]
    with zipfile.ZipFile(
        ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as out:
        for path in sorted(archive_files):
            name = "carbon_goal_workbench_v0_5/" + str(path.relative_to(ROOT))
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix == ".py" else 0o644) << 16
            out.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return MANIFEST, ARCHIVE


if __name__ == "__main__":
    manifest, archive = build()
    print(manifest)
    print(archive)
