"""Read-only source-backed onboarding progress, not a new readiness judge."""

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet, timeline
from carbon.challenge_pipeline.readiness.model import digest as readiness_digest

STAGE_MAP = "docs/development/challenge_pipeline/onboarding/stage_map.json"
BINDINGS = "docs/development/challenge_pipeline/onboarding-automation/artifacts.json"


def path(root, relative):
    # Narrow addition to packet's public-doc roots: existing readiness metadata,
    # not reference cases, worker outputs, ledgers, credentials or bank bodies.
    if relative.startswith("carbon/challenge_readiness/records/"):
        parts = relative.split("/")
        target = root.joinpath(*parts).resolve()
        if (
            len(parts) != 4
            or not target.is_relative_to(root.resolve())
            or not target.is_file()
            or target.stat().st_size > packet.LIMIT
            or not relative.endswith(".json")
        ):
            raise packet.DraftError("readiness metadata path refused")
        return target
    return packet.source_path(root, relative)


def git_basis(root):
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return {"sha": sha, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"sha": None, "dirty": None}


def gaps(value, prefix=""):
    """Report policy-shaped gaps only, never raw panel data or generic strings."""
    found = []
    if type(value) is dict:
        for key, child in value.items():
            at = f"{prefix}.{key}" if prefix else key
            if key in {
                "registered",
                "registered_P",
                "registered_Q",
                "registered_outer_w",
                "accepted_manifest_digest",
                "dispatch_grant",
                "CCX63_throughput",
                "reference_interval_adopted",
                "physical_coordinates_and_full_signed_curves",
                "full_buyer_status",
                "per_boundary_status",
                "status",
            } and (
                child is None
                or child is False
                or (
                    type(child) is str
                    and any(
                        token in child
                        for token in (
                            "HUMAN_INPUT",
                            "HOLD",
                            "AWAITING",
                            "NOT_DEMONSTRATED",
                            "UNMEASURED",
                            "NOT_STARTED",
                        )
                    )
                )
            ):
                found.append({"field": at, "state": child})
            if len(at) < 240 and isinstance(child, (dict, list)):
                found.extend(gaps(child, at))
    elif type(value) is list:
        for i, child in enumerate(value[:1000]):
            found.extend(gaps(child, f"{prefix}[{i}]"))
    return found[:100]


def inspect(root, relative):
    try:
        target = path(root, relative)
    except packet.DraftError:
        return {
            "path": relative,
            "state": "UNAVAILABLE_OR_REFUSED",
            "basis": "No permitted readable artifact; cannot conclude it does not exist",
        }
    raw = target.read_bytes()
    result = {
        "path": relative,
        "sha256": packet.digest(raw),
        "state": "READ",
        "size_bytes": len(raw),
    }
    try:
        content = raw.decode("utf-8")
        if relative.endswith(".json"):
            result["gaps"] = gaps(packet.read_json(target))
        elif relative.endswith(".md"):
            result["numbered_sections"] = len(
                re.findall(r"^## \d+\.", content, re.MULTILINE)
            )
            result["human_input_markers"] = content.count(
                "HUMAN_INPUT"
            ) + content.count("`OPEN`")
        elif relative.endswith("history.jsonl"):
            lines = content.splitlines()
            if not lines:
                result["state"] = "EMPTY_NO_EVIDENCE"
            else:
                latest = json.loads(lines[-1])
                counts = latest.get("counts")
                if (
                    type(counts) is not dict
                    or not counts
                    or any(type(v) is not int or v < 0 for v in counts.values())
                ):
                    raise packet.DraftError("readiness count basis required")
                result["readiness_snapshot"] = {
                    "sha": latest.get("git_sha"),
                    "dirty": latest.get("git_dirty"),
                    "counts": counts,
                    "partial": latest.get("partial"),
                    "green": latest.get("green"),
                    "launch_ready": latest.get("launch_ready"),
                    "report_digest": latest.get("report_digest"),
                }
                rd = latest.get("report_digest", "")
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", rd):
                    raise packet.DraftError("readiness digest required")
                report_path = str(
                    Path(relative).parent / "reports" / (rd[7:23] + ".json")
                ).replace("\\", "/")
                report = packet.read_json(path(root, report_path))
                body = {k: v for k, v in report.items() if k != "report_digest"}
                if (
                    readiness_digest(body) != rd
                    or report.get("report_digest") != rd
                    or report.get("counts") != counts
                    or report.get("git", {}).get("sha") != latest.get("git_sha")
                ):
                    raise packet.DraftError("readiness snapshot/report mismatch")
                items = report.get("items", [])
                if not items or Counter(i["status"] for i in items) != counts:
                    raise packet.DraftError("readiness item/count mismatch")
                result["readiness_snapshot"]["items_checked"] = len(items)
                result["readiness_snapshot"]["report_verified"] = True
    except (
        UnicodeError,
        json.JSONDecodeError,
        packet.DraftError,
        OSError,
        KeyError,
        TypeError,
    ):
        result["state"] = "MALFORMED_OR_UNVERIFIED"
        result.pop("readiness_snapshot", None)
    return result


def generate(
    root: Path, challenge: str, *, bindings_path=BINDINGS, main_ref="origin/main"
):
    root = root.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", challenge):
        raise packet.DraftError("planning challenge token required")
    map_path = path(root, STAGE_MAP)
    mapping = packet.read_json(map_path)
    stages = mapping.get("stages")
    if (
        mapping.get("schema") != "carbon.challenge-pipeline.onboarding-stage-map.v1"
        or type(stages) is not list
        or len(stages) != 11
        or any(
            type(s) is not dict
            or not {"id", "order", "name", "owner_session", "exit"} <= set(s)
            or any(
                type(s[k]) is not str for k in ("id", "name", "owner_session", "exit")
            )
            for s in stages
        )
        or [s.get("order") for s in stages] != list(range(11))
        or len({s.get("id") for s in stages}) != 11
    ):
        raise packet.DraftError("complete ordered stage map required")
    binding_file = path(root, bindings_path)
    bindings = packet.read_json(binding_file)
    if (
        type(bindings) is not dict
        or set(bindings) != {"schema", "challenges"}
        or bindings["schema"] != "carbon.onboarding.artifact-bindings.v1"
        or type(bindings["challenges"]) is not dict
    ):
        raise packet.DraftError("artifact path bindings required")
    seen_aliases = set(bindings["challenges"])
    for candidate in bindings["challenges"].values():
        if (
            type(candidate) is not dict
            or set(candidate) != {"aliases", "stages"}
            or type(candidate["aliases"]) is not list
            or type(candidate["stages"]) is not dict
            or set(candidate["stages"]) - {s["id"] for s in stages}
        ):
            raise packet.DraftError("closed challenge binding required")
        for alias in candidate["aliases"]:
            if type(alias) is not str or alias in seen_aliases:
                raise packet.DraftError("unique challenge alias required")
            seen_aliases.add(alias)
    entry = bindings["challenges"].get(challenge)
    if entry is None:
        for token, candidate in bindings["challenges"].items():
            if challenge in candidate.get("aliases", []):
                challenge, entry = token, candidate
                break
    basis = git_basis(root)
    rows = []
    for stage in stages:
        paths = entry["stages"].get(stage["id"], []) if entry else []
        if (
            type(paths) is not list
            or len(paths) > 20
            or any(type(p) is not str for p in paths)
        ):
            raise packet.DraftError("bounded explicit artifact paths required")
        artifacts = [inspect(root, p) for p in paths]
        read = sum(a["state"] == "READ" for a in artifacts)
        blockers = [
            {"path": a["path"], "gaps": a.get("gaps", []), "state": a["state"]}
            for a in artifacts
            if a["state"] != "READ" or a.get("gaps")
        ]
        progress = (
            "ARTIFACTS_PRESENT_EXIT_NOT_VERIFIED"
            if read
            else "NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT"
        )
        for a in artifacts:
            snapshot = a.get("readiness_snapshot")
            if snapshot:
                exact = (
                    basis["sha"] is not None
                    and snapshot["sha"] == basis["sha"]
                    and basis["dirty"] is False
                    and snapshot["dirty"] is False
                )
                progress = (
                    "EXACT_READINESS_SNAPSHOT"
                    if exact
                    else "HISTORICAL_READINESS_NOT_CURRENT"
                )
                # Even a green readiness snapshot is not the seven-part TESTED exit.
                blockers.append(
                    {"path": a["path"], "state": progress, "counts": snapshot["counts"]}
                )
        rows.append(
            {
                "id": stage["id"],
                "name": stage["name"],
                "owner": stage["owner_session"],
                "definition_note": stage.get("note"),
                "progress": progress,
                "exit_verified": False,
                "what_was_checked": {"configured": len(paths), "read": read},
                "artifacts": artifacts,
                "blockers": blockers,
                "next_required": stage["exit"],
            }
        )
    history = timeline.generate(root, challenge, rows, main_ref=main_ref)
    return {
        "schema": "carbon.onboarding.status-view.v1",
        "challenge": challenge,
        "current_stage": "UNDETERMINED_WITHOUT_VERIFIED_EXIT_EVIDENCE",
        "observed_artifact_stages": [
            r["id"] for r in rows if r["what_was_checked"]["read"]
        ],
        "basis": {
            "repository": basis,
            "stage_map_sha256": packet.digest(map_path.read_bytes()),
            "bindings_sha256": packet.digest(binding_file.read_bytes()),
        },
        "binding_status": "CONFIGURED" if entry else "HUMAN_INPUT_ARTIFACT_BINDINGS",
        "stages": rows,
        "artifact_timeline": history,
        "tested_challenge_claim": False,
        "limit": "Reports source-backed draft/gap/snapshot progress. No stage exit is adjudicated from file presence; independent stage acceptance remains with #970 owners.",
    }


def render(report):
    lines = [f"{report['challenge']}: {report['current_stage']}", report["limit"], ""]
    for stage in report["stages"]:
        history = next(
            s for s in report["artifact_timeline"]["stages"] if s["id"] == stage["id"]
        )
        basis = stage["what_was_checked"]
        lines.extend(
            [
                f"{stage['id']} {stage['name']}: {stage['progress']} ({basis['read']}/{basis['configured']} artifacts read)",
                f"  Owner: {stage['owner']}",
            ]
        )
        for artifact in stage["artifacts"]:
            lines.append(f"  {artifact['path']}: {artifact['state']}")
            for gap in artifact.get("gaps", [])[:12]:
                lines.append(f"    {gap['field']}: {gap['state']}")
            if "readiness_snapshot" in artifact:
                lines.append(
                    f"    Historical counts: {artifact['readiness_snapshot']['counts']}"
                )
        lines.append(f"  Still required: {stage['next_required']}")
        for item in history["artifacts"]:
            first = item.get("first_recorded")
            merged = item.get("first_main_integration")
            lines.append(
                f"  Artifact history {item['path']}: first commit {first['committed_utc'] if first else 'UNKNOWN'}; first main integration {merged['committed_utc'] if merged else 'UNKNOWN'}; {item['coverage']}"
            )
        lines.append(
            "  Accepted stage entry/exit and effort: UNKNOWN (artifact dates are not completion)."
        )
    return "\n".join(lines)
