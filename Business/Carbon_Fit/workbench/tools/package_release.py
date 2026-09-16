"""Create a deterministic source/test/evidence release bundle and checksum manifest."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.json"
ARCHIVE = ROOT / "Carbon_Physics_Goal_Workbench_v0_7.zip"
EXCLUDED = {
    MANIFEST.name,
    ARCHIVE.name,
    "Carbon_Physics_Goal_Workbench_v0_5.zip",
    "Carbon_Physics_Goal_Workbench_v0_6.zip",
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
    subprocess.run(
        ["node", str(ROOT / "tools/check_repository_snapshot_admission.cjs")],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    files = payloads()
    manifest = {
        "schema_version": "carbon.workbench.release-manifest.v0.7",
        "status": "OFFLINE_DECISION_SUPPORT_NOT_PRODUCTION",
        "application_version": "Carbon Goal-to-Challenge Workbench v0.7",
        "decision_ids": [
            "EXAM-PROTECT-WORKBENCH-01",
            "GOAL-WORKBENCH-02",
            "GOAL-WORKBENCH-03",
            "GOAL-WORKBENCH-04",
            "GOAL-WORKBENCH-05",
            "GOAL-WORKBENCH-05A",
            "GOAL-WORKBENCH-06",
            "OWNER-GW07-RYAN-SNAPSHOT-01",
            "GOAL-WORKBENCH-07",
            "OWNER-GW07-RYAN-SNAPSHOT-01-ADOPTION-001",
            "GOAL-WORKBENCH-07A",
        ],
        "repository_base": "3681f7fb10be0c6e278f53d59ff9b022099ef12d",
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
        "accepted_goal_workbench_05_baseline": {
            "pull_request": 179,
            "accepted_head": "5344e3da67c10abf35ad177c60c1d10395c28cfa",
            "acceptance_run": 34907708284,
            "merge_commit": "3681f7fb10be0c6e278f53d59ff9b022099ef12d",
        },
        "accepted_goal_workbench_05a_baseline": {
            "pull_request": 181,
            "accepted_head": "36cb25b6d6d010aaf4378eaece99cebb63ca630a",
            "acceptance_run": 34918769638,
            "merge_commit": "e5aafc522ca40db12f1897bcc0beacdedb44d823",
        },
        "accepted_goal_workbench_06_contract": {
            "pull_request": 182,
            "accepted_head": "fa9c565e576ec971366c85c4696b29f3542a1359",
            "merge_commit": "d2067bd4da85edafc24be5917d480089a514c670",
            "authority": "Detached conformance only; historical v1 fixtures remain non-authoritative.",
        },
        "accepted_goal_workbench_06a_delivery_integrity": {
            "pull_request": 184,
            "accepted_head": "27d84615badccfd91d6d04333cc3157df397f8c7",
            "acceptance_run": 34971837843,
            "merge_commit": "5b68da95580c659f8555d1f5a9caaddb049eb487",
            "corrected_delivery_comment": "https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5675346832",
            "authority": "Historical source-owner delivery integrity only; no eligible source response or assessment adoption is inferred.",
        },
        "accepted_cw1_ci_boundary_repair": {
            "pull_request": 186,
            "accepted_head": "7dd1bc8a5c5bcdfe8ed016f34e535c9ea5d4785f",
            "acceptance_run": 34967546351,
            "merge_commit": "d3e285790f722d76270d517947a865d5e5c6bbb1",
            "scope": "Dependency-light structural invariant; runtime behavior remains covered in the declared CPU environment.",
        },
        "accepted_goal_workbench_07_baseline": {
            "pull_request": 187,
            "accepted_head": "0c94cf592b6ce80b2712395e5cb9bd415fd32e22",
            "acceptance_run": 34973852521,
            "acceptance_attempt": 2,
            "merge_commit": "b71b1a68b6f9a895f12fc608e2dec895ea038760",
            "scope": "Repository-pinned reader shipped with an empty production index pending exact owner adoption.",
        },
        "source_assessment_snapshot": {
            "profile": "burgers-dynamics-public.repository-snapshot.v1",
            "policy_decision": "OWNER-GW07-RYAN-SNAPSHOT-01",
            "snapshot_id": "OWNER-GW07-RYAN-SNAPSHOT-01/sha256-49acb3598d034cf7/v1",
            "production_approved_entries": 1,
            "admission_state": "OWNER_ADOPTED_ASSESSMENT_ADMITTED",
            "adoption_source": "EXPLICIT_OWNER_CONVERSATION_DECISION",
            "assessment_id": "GW07-BURGERS-DYNAMICS-ASSESSMENT-001",
            "adoption_record": "source_assessment/repository_snapshot/v1/adoption/owner_gw07_ryan_snapshot_01.json",
            "authority": "Repository-pinned technical correspondence only; no scientific, rights, execution, score, protected-use, or launch authority.",
        },
        "post_merge_review_input": {
            "archive_sha256": "85aa3633410ea41cad9029a5e864e42ca2134c4ff0ec9eb5caef638acd4e2f78",
            "routing_sha256": "cacc140b1e9f9904a2360ba7a798d6789619154b54a27ccdf4faf8adb18accf0",
            "scope": "External reproducer inspected as input; not packaged as source authority.",
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
            "saved_projection_index_sha256": sha256(
                ROOT / "data/c05_fixture_index_v2.json"
            ),
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
            name = "carbon_goal_workbench_v0_7/" + str(path.relative_to(ROOT))
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
