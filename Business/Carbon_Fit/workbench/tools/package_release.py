#!/usr/bin/env python3
"""Create a deterministic source/test/evidence release bundle and checksum manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.json"
ARCHIVE = ROOT / "Carbon_Physics_Opportunity_Workbench_v0_2.zip"
EXCLUDED = {MANIFEST.name, ARCHIVE.name}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integration_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True,
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def payloads() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.name not in EXCLUDED
        and "__pycache__" not in p.parts
        and not p.name.endswith(".pyc")
    )


def build() -> tuple[Path, Path]:
    files = payloads()
    manifest = {
        "schema_version": "carbon.workbench.release-manifest.v0.2",
        "status": "OFFLINE_DECISION_SUPPORT_NOT_PRODUCTION",
        "application_version": "Carbon Opportunity Workbench v0.2",
        "decision_id": "EXAM-PROTECT-WORKBENCH-01",
        "repository_base": "2d5872aff89ca7bef3e3f062b293aeefe17769aa",
        "integration_revision_at_packaging": integration_revision(),
        "pinned_research_revision": "ca904dfee93d3574df4e56b99981a6ed3b138e80",
        "accepted_research_head": "0a5690270dc449ea19c941280203987d37db5283",
        "research_merge_commit": "2ac835d1dd55deb9c99e493f3615143efa2e51e0",
        "research_acceptance_run": 34786945000,
        "historical_failed_research_run": 34778525936,
        "pinned_evidence_index_sha256": "4565995a98fe8f238ca88b44e418e6c7da2954de9dca577b80968854bad34ba7",
        "source_archive_sha256": "aabdc04377700334f50a8748bf28b9fc3e44799b8986d2c38f759df5726469fa",
        "authority": "No runtime sharing, qualification, protected-use approval, answer publication, submission, or rights authority is conveyed.",
        "file_count": len(files),
        "files": {
            str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in files
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive_files = payloads() + [MANIFEST]
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for path in sorted(archive_files):
            name = "carbon_opportunity_workbench_v0_2/" + str(path.relative_to(ROOT))
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix == ".py" else 0o644) << 16
            out.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return MANIFEST, ARCHIVE


if __name__ == "__main__":
    manifest, archive = build()
    print(manifest)
    print(archive)
