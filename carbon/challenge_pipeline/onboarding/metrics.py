"""Public preparation history, not accepted stage exits or inferred labour."""

from __future__ import annotations

import json
import re
from datetime import datetime
from statistics import median

from carbon.challenge_pipeline.onboarding import packet, timeline

STAGES = (
    "brief",
    "packet",
    "question_law",
    "panel",
    "generators_decks",
    "verification_spec",
    "comparator",
    "equal_budget",
    "train_kit",
    "readiness_bindings",
)
CHALLENGES = {
    "battery-v3",
    "motor",
    "f02",
    "f13",
    "cooling-cell",
    "backward-facing-step",
    "metagrating-3d",
    "bolted-joint",
    "package-warpage",
    "f17",
    "f08",
}
SHA = re.compile(r"[0-9a-f]{40}")
PREFIXES = (
    ".agent/decisions/",
    "Design_Specs/",
    "Business/research/",
    "docs/development/challenge_pipeline/",
    "carbon/challenge_pipeline/",
    "carbon/design_search/",
    "carbon/development_comparison/",
    "scripts/dev/reference_packages/",
    "scripts/dev/motor/feasibility02/",
    "scripts/dev/battery/",
    "scripts/dev/evidence_runs/",
)


def seconds(start, end):
    if not start or not end:
        return None
    value = (
        datetime.fromisoformat(end) - datetime.fromisoformat(start)
    ).total_seconds()
    return int(value) if value >= 0 else None


def source_check(source):
    name = source["path"]
    if (
        type(name) is not str
        or not name.startswith(PREFIXES)
        or not re.fullmatch(r"[A-Za-z0-9_./-]{1,350}", name)
        or any(p in {"", ".", ".."} for p in name.split("/"))
        or any(
            v in name.lower()
            for v in ("hidden", "protected", "secret", "ev5", "journal")
        )
        or not SHA.fullmatch(source["ref"])
    ):
        raise packet.DraftError("public immutable source required")
    if "json_entry" in source and (
        name != "docs/development/challenge_pipeline/evidence-readiness/bindings.json"
        or source["json_entry"] not in CHALLENGES
    ):
        raise packet.DraftError("only public readiness-family selectors permitted")


def selected_history(root, commits, source):
    """Read only an explicit public registry entry, never arbitrary case bodies."""
    selected, previous = [], None
    for commit in commits:
        try:
            doc = json.loads(
                timeline.git(root, "show", commit["commit"] + ":" + source["path"])
            )
            matches = [
                e for e in doc["challenges"] if e["challenge"] == source["json_entry"]
            ]
        except (ValueError, KeyError, TypeError) as exc:
            raise packet.DraftError("public registry history malformed") from exc
        if len(matches) > 1:
            raise packet.DraftError("duplicate public family binding")
        entry = matches[0] if matches else None
        if entry != previous:
            if entry is not None:
                selected.append(commit)
            previous = entry
    return selected


def validate_sources(doc):
    if doc["schema"] != "carbon.onboarding.metrics-sources.v1" or not SHA.fullmatch(
        doc["main"]
    ):
        raise packet.DraftError("pinned metrics sources required")
    if [s["id"] for s in doc["stages"]] != list(STAGES):
        raise packet.DraftError("exact preparation sequence required")
    if (
        len(doc["challenges"]) != 11
        or {c["challenge"] for c in doc["challenges"]} != CHALLENGES
    ):
        raise packet.DraftError("exact eleven public cohorts required")
    for c in doc["challenges"]:
        if [s["id"] for s in c["stages"]] != list(STAGES):
            raise packet.DraftError("complete source sequence required")
        for source in c["stages"]:
            source_check(source)
    return doc


def observe(root, source, main):
    """Explicit path metadata and optionally one public registry entry."""
    source_check(source)
    result = {
        **source,
        "coverage": "UNKNOWN",
        "first_draft": None,
        "last_revision": None,
        "first_main": None,
        "publication_pr": None,
        "commits": [],
        "accepted_exit_utc": None,
        "current_revision_in_main": None,
    }
    try:
        # A deleted/renamed path cannot masquerade as a current-stage artifact.
        timeline.git(root, "cat-file", "-e", source["ref"] + ":" + source["path"])
        history = timeline.git(
            root,
            "log",
            "--no-merges",
            "--reverse",
            "--topo-order",
            "--max-count=1001",
            "--format=%H|%cI|%an",
            source["ref"],
            "--",
            source["path"],
        ).splitlines()
        if len(history) > 1000:
            raise packet.DraftError("history bounded")
        commits = []
        for row in history:
            sha, when, actor = row.split("|", 2)
            commits.append(
                {
                    "commit": sha,
                    "committed_utc": timeline.utc(when),
                    "git_author": actor,
                }
            )
        added = timeline.additions(root, source["ref"], source["path"])
        integrated = timeline.additions(root, main, source["path"], main=True)
        if source.get("json_entry"):
            commits = selected_history(root, commits, source)
            main_history = timeline.git(
                root,
                "log",
                "--first-parent",
                "--reverse",
                "--topo-order",
                "--max-count=1001",
                "--format=%H|%cI|%an",
                main,
                "--",
                source["path"],
            ).splitlines()
            if len(main_history) > 1000:
                raise packet.DraftError("public registry history bounded")
            main_commits = []
            for row in main_history:
                sha, when, actor = row.split("|", 2)
                main_commits.append(
                    {
                        "commit": sha,
                        "committed_utc": timeline.utc(when),
                        "git_author": actor,
                    }
                )
            selected_main = selected_history(root, main_commits, source)
            added = commits[:1]
            integrated = selected_main[:1]
        renamed = timeline.git(
            root,
            "log",
            "--max-count=1",
            "--format=%H",
            "--diff-filter=R",
            "--follow",
            source["ref"],
            "--",
            source["path"],
        )
        if len(added) != 1 or len(integrated) > 1 or renamed:
            result["coverage"] = "AMBIGUOUS_ADDITION_OR_RENAME"
            return result
        result.update(
            first_draft=added[0],
            last_revision=commits[-1] if commits else None,
            first_main=integrated[0] if integrated else None,
            commits=commits,
            coverage="MAIN_ARTIFACT" if integrated else "BRANCH_ONLY_ARTIFACT",
        )
        if integrated:
            subject = timeline.git(
                root, "show", "-s", "--format=%s", integrated[0]["commit"]
            )
            match = re.search(r"Merge pull request #(\d+)\b", subject)
            result["publication_pr"] = int(match[1]) if match else None
    except packet.DraftError:
        result["coverage"] = "MISSING_OR_HISTORY_UNAVAILABLE"
    return result


def effort_totals(events):
    """Explicit duration telemetry only. No Git/PR-time labour inference."""
    totals, seen = {}, set()
    for event in events:
        if set(event) != {
            "event_id",
            "challenge",
            "stage",
            "actor",
            "duration_s",
            "basis",
            "source",
        }:
            raise packet.DraftError("closed effort event required")
        if (
            event["event_id"] in seen
            or event["challenge"] not in CHALLENGES
            or event["stage"] not in STAGES
            or type(event["duration_s"]) is not int
            or not 1 <= event["duration_s"] <= 86400
            or event["basis"]
            not in {"MEASURED_ACTIVE_DURATION", "SELF_REPORTED_ACTIVE_DURATION"}
            or not event["actor"]
            or not event["source"]
        ):
            raise packet.DraftError("unique sourced active duration required")
        seen.add(event["event_id"])
        key = (event["challenge"], event["stage"])
        totals[key] = totals.get(key, 0) + event["duration_s"]
    return totals


def summarize(observations, sources, prs, *, captured_at, effort_events=()):
    validate_sources(sources)
    timeline.utc(captured_at)
    efforts = effort_totals(effort_events)
    rows, unique_commits, unique_prs = [], {}, set()
    owner_map = {s["id"]: s for s in sources["stages"]}
    for cohort in sources["challenges"]:
        challenge = cohort["challenge"]
        group = [observations[(challenge, s)] for s in STAGES]
        brief = group[0]["first_draft"]
        brief_time = brief["committed_utc"] if brief else None
        previous = None
        for o in group:
            first = o["first_draft"]["committed_utc"] if o["first_draft"] else None
            last = o["last_revision"]["committed_utc"] if o["last_revision"] else None
            reused = bool(first and brief_time and first < brief_time)
            gap = seconds(previous, first) if not reused else None
            gap_kind = "UNKNOWN"
            if first and previous:
                gap_kind = (
                    "REUSE_PREDATES_BRIEF"
                    if reused
                    else (
                        "OUT_OF_ORDER"
                        if gap is None
                        else (
                            "BUNDLED_OR_SIMULTANEOUS"
                            if gap == 0
                            else "OBSERVED_ARRIVAL_GAP"
                        )
                    )
                )
            pr_num = o["publication_pr"] or o.get("pending_pr")
            pr = prs.get(str(pr_num)) if pr_num else None
            integration = o["first_main"]
            main_time = integration["committed_utc"] if integration else None
            api_merged = None
            if (
                pr
                and integration
                and (pr.get("mergeCommit") or {}).get("oid") == integration["commit"]
            ):
                api_merged = pr.get("mergedAt")
            published = api_merged or main_time
            attribution = [
                c
                for c in o["commits"]
                if not brief_time or c["committed_utc"] >= brief_time
            ]
            for c in attribution:
                unique_commits[c["commit"]] = c
            if pr_num:
                unique_prs.add(pr_num)
            e = efforts.get((challenge, o["id"]))
            rows.append(
                {
                    "challenge": challenge,
                    "stage": o["id"],
                    "owner": owner_map[o["id"]]["owner"],
                    "authority_stage": owner_map[o["id"]]["authority_stage"],
                    "source": o,
                    "first_draft_utc": first,
                    "last_revision_utc": last,
                    "first_main_utc": main_time,
                    "github_first_publication_utc": api_merged,
                    "revision_span_s": seconds(first, last),
                    "previous_artifact_arrival_gap_s": gap,
                    "arrival_gap_basis": gap_kind,
                    "brief_to_artifact_s": (
                        seconds(brief_time, first) if not reused else None
                    ),
                    "reuse_predates_brief": reused,
                    "draft_to_first_publication_s": seconds(first, published),
                    "pr": pr_num,
                    "pr_state_at_capture": pr.get("state") if pr else "UNKNOWN",
                    "pr_open_to_merge_s": (
                        seconds(pr.get("createdAt"), pr.get("mergedAt")) if pr else None
                    ),
                    "pending_pr_age_s": (
                        seconds(pr.get("createdAt"), captured_at)
                        if pr and pr["state"] == "OPEN"
                        else None
                    ),
                    "current_revision_in_main": o.get("current_revision_in_main"),
                    "stage_elapsed_s": None,
                    "team_effort_hours": e / 3600 if e is not None else None,
                    "team_effort_basis": (
                        "EXPLICIT_ACTIVE_DURATION_RECORDS_PARTIAL"
                        if e is not None
                        else "NOT_RECORDED"
                    ),
                    "post_brief_touch_commits_proxy": len(attribution),
                    "git_author_identities_proxy": len(
                        {c["git_author"] for c in attribution}
                    ),
                }
            )
            previous = first
    bottlenecks = []
    for stage in STAGES[1:]:
        sample = [
            r
            for r in rows
            if r["stage"] == stage and r["arrival_gap_basis"] == "OBSERVED_ARRIVAL_GAP"
        ]
        events = {}
        for row in sample:
            key = row["source"]["first_draft"]["commit"]
            events.setdefault(key, []).append(row["previous_artifact_arrival_gap_s"])
        # A shared-spec batch is one delivery event, not several replications.
        event_gaps = [median(values) for values in events.values()]
        if len(event_gaps) >= 3:
            bottlenecks.append(
                {
                    "stage": stage,
                    "sample_n": len(event_gaps),
                    "cohort_rows_n": len(sample),
                    "event_basis": "UNIQUE_FIRST_DRAFT_COMMIT_MEDIAN_ACROSS_COHORT_ROWS",
                    "median_arrival_gap_s": median(event_gaps),
                    "max_arrival_gap_s": max(
                        r["previous_artifact_arrival_gap_s"] for r in sample
                    ),
                }
            )
    bottlenecks.sort(key=lambda b: (-b["median_arrival_gap_s"], b["stage"]))
    return {
        "schema": "carbon.onboarding.preparation-metrics.v1",
        "captured_at": captured_at,
        "main": sources["main"],
        "cohorts": len(sources["challenges"]),
        "rows": rows,
        "slowest_recurring_observed_arrivals": bottlenecks[:3],
        "activity_proxy": {
            "unique_post_brief_commits": len(unique_commits),
            "unique_prs": len(unique_prs),
            "git_author_identities": len(
                {c["git_author"] for c in unique_commits.values()}
            ),
            "team_effort_hours": None,
            "headcount": None,
        },
        "limits": [
            "These ten preparation milestones map to, not replace, #970 accepted stages. No stage exit or TESTED is inferred.",
            "Arrival gap is calendar delay between artifact additions, not labour, causal blocking or sequential execution; bundled, reused and out-of-order cases are excluded from ranking.",
            "First publication is not publication of every later revision. Current revision integration is checked separately.",
            "Shared file histories and PRs recur across cohorts; activity totals deduplicate them. One Git identity may represent many sessions.",
            "Recurring-arrival ranking requires at least three distinct first-draft commits; a shared batch is one event, using its median cohort gap, not independent replications.",
            "Historical effort and true stage entry/exit are unrecorded; active durations cannot be reconstructed from commits, API times or generated-tool wall time.",
            "This is a right-censored eleven-cohort preparation inventory, not proof that each Challenge is faster than the last.",
        ],
    }


def collect(root, sources):
    validate_sources(sources)
    if timeline.git(root, "rev-parse", "--is-shallow-repository") != "false":
        raise packet.DraftError(
            "full history required for metrics; shallow is not absence"
        )
    cache, observations = {}, {}
    for cohort in sources["challenges"]:
        for source in cohort["stages"]:
            key = (source["ref"], source["path"], source.get("json_entry"))
            if key not in cache:
                cache[key] = observe(root, source, sources["main"])
                latest = cache[key]["last_revision"]
                if latest:
                    try:
                        common = timeline.git(
                            root, "merge-base", latest["commit"], sources["main"]
                        )
                        cache[key]["current_revision_in_main"] = (
                            common == latest["commit"]
                        )
                    except packet.DraftError:
                        cache[key]["current_revision_in_main"] = None
            observations[(cohort["challenge"], source["id"])] = {**cache[key], **source}
    return observations


def render(report):
    def hours(s):
        return "UNKNOWN" if s is None else f"{s / 3600:.2f}"

    lines = [
        "# Eleven-Challenge onboarding preparation metrics",
        "",
        f"Public history pinned at main `{report['main']}`; API capture `{report['captured_at']}`.",
        "",
        "Actual accepted-stage elapsed and historical person-hours are **UNKNOWN**. The table measures artifact history, not stage acceptance. TRAIN/kit means a plan/hook, not registered solved TRAIN or an accepted kit.",
        "",
        "## Cohort overview (preparation only)",
        "",
        "| Challenge | Brief UTC | Brief to latest first-draft h | Current source revision on main | Other/unknown source revisions |",
        "|---|---|---:|---:|---:|",
    ]
    for challenge in sorted({r["challenge"] for r in report["rows"]}):
        group = [r for r in report["rows"] if r["challenge"] == challenge]
        brief = next(r["first_draft_utc"] for r in group if r["stage"] == "brief")
        elapsed = [
            r["brief_to_artifact_s"]
            for r in group
            if r["brief_to_artifact_s"] is not None
        ]
        current = sum(r["current_revision_in_main"] is True for r in group)
        lines.append(
            f"| {challenge} | {brief or 'UNKNOWN'} | {hours(max(elapsed) if elapsed else None)} | {current}/10 | {10-current}/10 |"
        )
    lines.extend(
        [
            "",
            "The overview ends at the latest artifact's *first draft*, not completion; revisions and pending merges can occur later. Ten sources are not ten accepted stages or seven readiness items.",
            "",
            "## Full milestone history",
            "",
            "| Challenge | Milestone | First draft UTC | Arrival gap h | Revision span h | First-publication lag h | PR | Main has current revision | Effort h | Touch commits proxy |",
            "|---|---|---|---:|---:|---:|---|---|---:|---:|",
        ]
    )
    for r in report["rows"]:
        label = (
            r["arrival_gap_basis"]
            if r["previous_artifact_arrival_gap_s"] is None
            else hours(r["previous_artifact_arrival_gap_s"])
        )
        pr = (
            f"[#{r['pr']}](https://github.com/carbonphysicsai/Carbon/pull/{r['pr']})"
            if r["pr"]
            else "UNKNOWN"
        )
        integrated = {True: "YES (artifact only)", False: "NO", None: "UNKNOWN"}[
            r["current_revision_in_main"]
        ]
        lines.append(
            f"| {r['challenge']} | {r['stage']} | {r['first_draft_utc'] or 'UNKNOWN'} | {label} | {hours(r['revision_span_s'])} | {hours(r['draft_to_first_publication_s'])} | {pr} | {integrated} | {r['team_effort_hours'] if r['team_effort_hours'] is not None else 'UNKNOWN'} | {r['post_brief_touch_commits_proxy']} |"
        )
    lines.extend(["", "## Three slowest recurring observed preparation arrivals", ""])
    for b in report["slowest_recurring_observed_arrivals"]:
        lines.append(
            f"- {b['stage']}: median {hours(b['median_arrival_gap_s'])} h, max cohort gap {hours(b['max_arrival_gap_s'])} h, n={b['sample_n']} distinct delivery events ({b['cohort_rows_n']} positive non-reuse cohort arrivals). See README for automation and exclusions."
        )
    lines.extend(["", "## Limits", "", *[f"- {v}" for v in report["limits"]], ""])
    return "\n".join(lines)
