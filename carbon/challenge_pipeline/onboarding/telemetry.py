"""Public process event/timer records. Reports activity, never accepts a stage."""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from carbon.challenge_pipeline.onboarding import metrics, packet

FOLDER = "docs/development/challenge_pipeline/onboarding-events"
STAGE_MAP = "docs/development/challenge_pipeline/onboarding/stage_map.json"
SCHEMA = "carbon.onboarding.process-event.v1"
MAPPING = dict(
    zip(
        metrics.STAGES,
        (
            "S0_brief",
            "S1_packet",
            "S4_question_law",
            "S3_feasibility_value_panel",
            "S2_solver_package",
            "S2_solver_package",
            "S10_tested",
            "S10_tested",
            "S4_question_law",
            "S6_readiness",
        ),
        strict=True,
    )
)
BASE = {
    "schema",
    "id",
    "challenge",
    "cycle",
    "stage",
    "kind",
    "at",
    "actor",
    "actor_kind",
    "source",
    "source_sha256",
    "stage_map_sha256",
}
EXTRA = {
    "ENTRY": set(),
    "EXIT": {"entry_id", "disposition"},
    "EFFORT_START": {"milestone"},
    "EFFORT_END": {"start_id"},
}


def moment(value):
    try:
        when = datetime.fromisoformat(value)
    except (AttributeError, ValueError, TypeError) as exc:
        raise packet.DraftError("explicit UTC process timestamp required") from exc
    if when.utcoffset() != UTC.utcoffset(when):
        raise packet.DraftError("UTC process timestamps required")
    return when


def validate(event, stages):
    if (
        type(event) is not dict
        or event.get("kind") not in EXTRA
        or set(event) != BASE | EXTRA[event["kind"]]
        or event["schema"] != SCHEMA
    ):
        raise packet.DraftError("closed process event required")
    for key in ("id", "challenge", "cycle", "actor"):
        if type(event[key]) is not str or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", event[key]
        ):
            raise packet.DraftError("bounded public process token required")
    if event["stage"] not in stages or event["actor_kind"] not in {
        "HUMAN",
        "AI_AGENT",
        "TOOL",
    }:
        raise packet.DraftError("registered stage and contributor kind required")
    for key in ("source_sha256", "stage_map_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(event[key])):
            raise packet.DraftError("process source identities required")
    packet.text(event["source"])
    moment(event["at"])
    if event["kind"] == "EXIT":
        packet.text(event["entry_id"])
        if event["disposition"] not in {"PREPARED", "BLOCKED", "ACCEPTANCE_RECORDED"}:
            raise packet.DraftError("explicit recorded disposition required")
    if event["kind"] == "EFFORT_START" and (
        event["milestone"] not in MAPPING
        or MAPPING[event["milestone"]] != event["stage"]
    ):
        raise packet.DraftError("effort milestone must map to this stage")
    if event["kind"] == "EFFORT_END":
        packet.text(event["start_id"])


def analyze(events, challenge, stages, stage_digest):
    if type(events) is not list or len(events) > 10000:
        raise packet.DraftError("bounded explicit event collection required")
    index = {}
    for event in events:
        validate(event, stages)
        if event["id"] in index:
            raise packet.DraftError("duplicate process event")
        index[event["id"]] = event
    pairs, closures, intervals = [], set(), {}
    for end in events:
        if end["kind"] not in {"EXIT", "EFFORT_END"}:
            continue
        ref = end["entry_id"] if end["kind"] == "EXIT" else end["start_id"]
        start = index.get(ref)
        expected = "ENTRY" if end["kind"] == "EXIT" else "EFFORT_START"
        if start is None or start["kind"] != expected or ref in closures:
            raise packet.DraftError("unique complete process pair required")
        if any(
            start[k] != end[k]
            for k in ("challenge", "cycle", "stage", "stage_map_sha256")
        ):
            raise packet.DraftError("process pair context changed")
        seconds = (moment(end["at"]) - moment(start["at"])).total_seconds()
        if seconds < 0:
            raise packet.DraftError("reversed process interval")
        closures.add(ref)
        if end["kind"] == "EFFORT_END":
            if any(start[k] != end[k] for k in ("actor", "actor_kind")):
                raise packet.DraftError("effort contributor changed")
            if seconds > 86400:
                raise packet.DraftError(
                    "finish active block before idle or day-long wait"
                )
            key = start["actor"].casefold()
            interval = (moment(start["at"]), moment(end["at"]))
            for lo, hi in intervals.get(key, []):
                if interval[0] < hi and lo < interval[1]:
                    raise packet.DraftError(
                        "overlapping contributor effort, including cross-Challenge"
                    )
            intervals.setdefault(key, []).append(interval)
        pairs.append({"start": start, "end": end, "seconds": seconds})
    open_actors = set()
    for event in events:
        if event["kind"] == "EFFORT_START" and event["id"] not in closures:
            key = event["actor"].casefold()
            if key in open_actors or any(
                lo <= moment(event["at"]) < hi for lo, hi in intervals.get(key, [])
            ):
                raise packet.DraftError("contributor has overlapping open effort")
            open_actors.add(key)
    selected = [p for p in pairs if p["start"]["challenge"] == challenge]
    rows, converted = [], {"HUMAN": [], "AI_AGENT": [], "TOOL": []}
    for stage in stages:
        accepted = [
            p
            for p in selected
            if p["end"]["kind"] == "EXIT" and p["start"]["stage"] == stage
        ]
        effort = [
            p
            for p in selected
            if p["end"]["kind"] == "EFFORT_END" and p["start"]["stage"] == stage
        ]
        active = [
            e
            for e in events
            if e["challenge"] == challenge
            and e["stage"] == stage
            and e["kind"] in {"ENTRY", "EFFORT_START"}
            and e["id"] not in closures
        ]
        totals = {}
        for kind in ("HUMAN", "AI_AGENT", "TOOL"):
            matching = [p for p in effort if p["start"]["actor_kind"] == kind]
            totals[kind] = (
                sum(p["seconds"] for p in matching) / 3600 if matching else None
            )
        rows.append(
            {
                "stage": stage,
                "recorded_cycles": [
                    {
                        "entered_at": p["start"]["at"],
                        "exited_at": p["end"]["at"],
                        "calendar_s": p["seconds"],
                        "disposition": p["end"]["disposition"],
                        "source": p["end"]["source"],
                        "source_sha256": p["end"]["source_sha256"],
                        "current_stage_definition": p["start"]["stage_map_sha256"]
                        == stage_digest,
                    }
                    for p in accepted
                ],
                "active_hours_partial": totals,
                "open_events": len(active),
                "accepted_exit_verified": False,
            }
        )
        for p in effort:
            start = p["start"]
            if challenge in metrics.CHALLENGES and int(p["seconds"]) >= 1:
                converted[start["actor_kind"]].append(
                    {
                        "event_id": p["end"]["id"],
                        "challenge": challenge,
                        "stage": start["milestone"],
                        "actor": start["actor"] + ":" + start["actor_kind"],
                        "duration_s": int(p["seconds"]),
                        "basis": "SELF_REPORTED_ACTIVE_DURATION",
                        "source": FOLDER + "/" + p["end"]["id"] + ".json",
                    }
                )
    return {
        "schema": "carbon.onboarding.recorded-process-view.v1",
        "challenge": challenge,
        "events_examined": len(events),
        "stages": rows,
        "metrics_effort_events": converted["HUMAN"],
        "effort_exports_by_kind": converted,
        "authority_granted": False,
        "basis": "Measured clock intervals declared active by contributor; no independent activity/identity verification. HUMAN, AI_AGENT and TOOL kept separate. Missing/open effort UNKNOWN, totals PARTIAL. Recorded exits do not accept stages. Legacy metrics_effort_events exports HUMAN only: agent/tool time is not labour. Conversion floors whole seconds and omits subsecond intervals.",
    }


def load(root):
    directory = root / FOLDER
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
        raise packet.DraftError("public event directory required")
    paths = sorted(directory.glob("*.json"))
    if len(paths) > 10000:
        raise packet.DraftError("process event count bounded")
    events = []
    for path in paths:
        event = packet.read_json(
            packet.source_path(root, path.relative_to(root).as_posix())
        )
        if path.stem != event.get("id"):
            raise packet.DraftError("event filename must match identity")
        source = event.get("source", "")
        if any(
            v in source.lower()
            for v in ("ev5", "journal", "secret", "hidden", "protected")
        ):
            raise packet.DraftError("process record cannot open protected source")
        events.append(event)
    return events


def view(root, challenge):
    path = packet.source_path(root, STAGE_MAP)
    stages = [s["id"] for s in packet.read_json(path)["stages"]]
    events = load(root)
    result = analyze(events, challenge, stages, packet.digest(path.read_bytes()))
    sources = {}
    for event in events:
        if event["challenge"] != challenge:
            continue
        try:
            current = packet.digest(
                packet.source_path(root, event["source"]).read_bytes()
            )
            state = (
                "SAME_SOURCE" if current == event["source_sha256"] else "SOURCE_CHANGED"
            )
        except (packet.DraftError, OSError):
            current, state = None, "SOURCE_UNAVAILABLE_NOT_ABSENCE"
        sources[event["id"]] = {
            "path": event["source"],
            "recorded_sha256": event["source_sha256"],
            "current_sha256": current,
            "state": state,
        }
    result["source_observations"] = sources
    result["event_store"] = FOLDER
    return result


def render(report):
    lines = ["Recorded onboarding process and active effort", report["basis"]]
    for row in report["stages"]:
        if (
            row["recorded_cycles"]
            or row["open_events"]
            or any(v is not None for v in row["active_hours_partial"].values())
        ):
            lines.append(
                f"  {row['stage']}: cycles={row['recorded_cycles']}; active hours={row['active_hours_partial']}; open={row['open_events']}"
            )
    if report["events_examined"] == 0:
        lines.append(
            "  No explicit process events: stage intervals and active effort UNKNOWN."
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "command", choices=("entry", "exit", "start", "finish", "view", "export-effort")
    )
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--cycle")
    parser.add_argument("--stage")
    parser.add_argument("--actor")
    parser.add_argument("--actor-kind", choices=("HUMAN", "AI_AGENT", "TOOL"))
    parser.add_argument("--source")
    parser.add_argument("--milestone", choices=metrics.STAGES)
    parser.add_argument("--ref-id")
    parser.add_argument(
        "--disposition",
        choices=("PREPARED", "BLOCKED", "ACCEPTANCE_RECORDED"),
        default="PREPARED",
    )
    args = parser.parse_args()
    try:
        if args.command in {"view", "export-effort"}:
            report = view(args.root, args.challenge)
            print(
                json.dumps(
                    (
                        report["metrics_effort_events"]
                        if args.command == "export-effort"
                        else report
                    ),
                    indent=2,
                )
            )
            return 0
        prior = load(args.root)
        stage_path = packet.source_path(args.root, STAGE_MAP)
        if args.command in {"finish", "exit"}:
            start = next((e for e in prior if e["id"] == args.ref_id), None)
            if start is None or start["challenge"] != args.challenge:
                raise packet.DraftError("matching process start required")
            event = {k: start[k] for k in BASE}
            event.update(kind="EFFORT_END" if args.command == "finish" else "EXIT")
            event.update(
                {"start_id": args.ref_id}
                if args.command == "finish"
                else {"entry_id": args.ref_id, "disposition": args.disposition}
            )
        else:
            if not all(
                (args.cycle, args.stage, args.actor, args.actor_kind, args.source)
            ):
                raise packet.DraftError(
                    "cycle/stage/contributor/public source required"
                )
            if any(
                v in args.source.lower()
                for v in ("ev5", "journal", "hidden", "protected", "secret")
            ):
                raise packet.DraftError("public process source required")
            event = {
                "schema": SCHEMA,
                "challenge": args.challenge,
                "cycle": args.cycle,
                "stage": args.stage,
                "kind": "ENTRY" if args.command == "entry" else "EFFORT_START",
                "actor": args.actor,
                "actor_kind": args.actor_kind,
                "source": args.source,
                "source_sha256": packet.digest(
                    packet.source_path(args.root, args.source).read_bytes()
                ),
                "stage_map_sha256": packet.digest(stage_path.read_bytes()),
            }
            if args.command == "start":
                event["milestone"] = args.milestone
        event.update(id=uuid4().hex, at=datetime.now(UTC).isoformat())
        analyze(
            [*prior, event],
            args.challenge,
            [s["id"] for s in packet.read_json(stage_path)["stages"]],
            packet.digest(stage_path.read_bytes()),
        )
        directory = args.root / FOLDER
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (event["id"] + ".json")
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, indent=2) + "\n")
        print(json.dumps(event, indent=2))
    except (packet.DraftError, OSError, StopIteration) as exc:
        parser.exit(2, "process record refused: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
