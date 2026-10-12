"""Q1 report for the readiness gate (items V1 and V2).

V1 is a measurement gate, not a threshold: it passes when a score-to-value
alignment report for the challenge's registered panel EXISTS, is internally
consistent and is current against the scoring rule in force. V2 is a real
threshold: the panel's members must reach at least `MIN_DISTINCT_OUTCOMES`
distinct decision outcomes on the decision study. Members the report lists as
`aliases` (`[{alias, target}]`, identical predictions) are skipped, not counted
as distinct evidence.

The report for level N is `readiness/<challenge>/q1_report.L<N>.json`; the
level-0 report is also read from the older single-file name `q1_report.json`
(`report_name`), so existing records stay valid. V1 and V2 at level N read only
that level's report, and a report whose recorded level differs from the level
asked still fails. It is built from the panel Data Collection's Track B harness produced (`carbon.design_search.
track_b.alignment` and `score_value.alignment`):

    python -m carbon.challenge_pipeline.readiness.q1 build \
        --challenge ID --level 0 --panel PANEL.json --out REPORT.json

`PANEL.json` is `{"reference": {"provenance": KIND, "ref": PATH},
"decision_study": REF, "members": {name: {score, value, eligible, recipe, kind, decision_outcome}}}`,
exactly the `members` shape `score_value.alignment` takes plus each member's
`decision_outcome` (the design it chose, or ABSTAIN). The build recomputes the
alignment, so a recorded report cannot disagree with its members, and binds the
report to the digest of the scoring rule in force.

Score basis (Test Lead ruling, 2026-10-12). V1 and V2 are gate evidence only over members
that share ONE named, reproducible score basis. A panel that mixes bases (for example
Graphite frozen-rule pod scores and a Launchpad aggregate under an unnamed rule) is not
gate evidence as a whole. The gate reads a DERIVED primary-basis report: `basis_split`
names the primary basis, the source report it was derived from (file and sha256, kept
beside it as the labelled SECONDARY), the per-member basis evidence (file and sha256) and
the excluded members with their bases. `split_problem` re-derives the split from those
two committed files on every gate run: the primary members must be exactly the source
members whose recorded basis is the primary basis, each row must equal its source row,
the excluded members must be the rest with a recorded basis, and the secondary summary
must equal the source's own alignment. A member with no recorded basis fails closed. A
non-primary member whose stored outputs were recovered may be RESCORED under the primary
rule: `rescored` names it and `rescore` the committed record (verified output digest, the
recomputed score rounding to the recorded one); the report row then carries the recomputed
score. Rescoring never changes the source file, which stays byte-identical. A
report without `basis_split` (the level-0 report) is read as before.

Nothing here chooses a value: no threshold other than the two-outcome floor the
gate document names, and no panel is produced.

Reference provenance (Test Lead ruling, 2026-10-05). The gate refuses a panel
whose DECISION VALUES rest on synthetic or fixture references; it does not
refuse constructed MEMBERS (controls built from public TRAIN, such as a
fixture panel's flat, phase-shifted and saturation-blind members) when their
decisions are judged against real reference evidence. `reference.provenance`
must be one of `REAL_REFERENCE_KINDS` and `reference.ref` must be a committed
repository path; an analytical-fixture or synthetic reference, an unknown kind,
a missing or non-existent path all FAIL (provenance that cannot be determined
fails closed). The member kinds are recorded in the report so constructed
controls stay visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .model import FAIL, PACKAGE, PASS, REPOSITORY, Result, digest

REPORT_SCHEMA = "carbon.challenge-pipeline.readiness-q1-report.v1"
#: The gate document's V2 floor: "at least two distinct decision outcomes".
MIN_DISTINCT_OUTCOMES = 2
#: The only reference kinds that count as real (Test Lead, 2026-10-05): committed
#: real-solver references. Nothing else is inferred to be real.
REAL_REFERENCE_KINDS = (
    "COUNTED_CAMPAIGN",
    "EV4_REFERENCE",
    "REFINED_REFERENCE_WAVE07",
)
#: Named so a report that says so is refused with the reason, not as "unknown".
FIXTURE_REFERENCE_KINDS = ("ANALYTICAL_FIXTURE", "SYNTHETIC")


def reference_problem(report, repository=REPOSITORY):
    """Why the report's decision references do not count as real, or None."""
    reference = report.get("reference")
    if not isinstance(reference, dict):
        return "no reference provenance is recorded"
    kind = reference.get("provenance")
    if kind in FIXTURE_REFERENCE_KINDS:
        return (
            f"decisions rest on a {kind} reference, not committed real-solver evidence"
        )
    if kind not in REAL_REFERENCE_KINDS:
        return f"reference provenance {kind!r} cannot be determined to be real"
    ref = reference.get("ref")
    if not (isinstance(ref, str) and ref and (Path(repository) / ref).exists()):
        return f"the {kind} reference path {ref!r} is not a committed path"
    return None


def member_kinds(members):
    counts = {}
    for row in members.values():
        kind = str(row.get("kind"))
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def current_rule_digest(challenge, repository=REPOSITORY):
    """The digest of the registered scoring's frozen rule identity, or None
    when no scoring is registered for the challenge."""
    from carbon.challenge_validator import scoring

    try:
        rule = scoring.scoring_for(challenge).frozen_rule(Path(repository))
    except scoring.ScoringUnavailable:
        return None
    return digest(rule.identity)


def _alignment_of(members):
    """`score_value.alignment` over members whose JSON list values (class,
    number) are the tuples it expects, as plain JSON data for comparison."""
    from carbon.design_search import score_value

    fixed = {
        name: {
            **row,
            "value": (
                tuple(row["value"])
                if isinstance(row.get("value"), list)
                else row.get("value")
            ),
        }
        for name, row in members.items()
    }
    return json.loads(json.dumps(score_value.alignment(fixed)))


def build_report(challenge, level, panel, rule_digest):
    """The Q1 report for `panel`, with its alignment recomputed."""
    members = panel["members"]
    return {
        "schema": REPORT_SCHEMA,
        "challenge": challenge,
        "level": level,
        "scoring_rule_digest": rule_digest,
        "reference": panel["reference"],
        "member_kinds": member_kinds(members),
        "decision_study": panel["decision_study"],
        "aliases": panel.get("aliases", []),
        "members": members,
        "alignment": _alignment_of(members),
    }


def file_sha256(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sibling(folder, name):
    """A committed file next to the report, by plain name only (no path parts)."""
    if not (isinstance(name, str) and name and Path(name).name == name):
        return None
    path = Path(folder) / name
    return path if path.is_file() else None


def _split_files(split, folder):
    """`(source, evidence, problem)`: the two committed files a split rests on, each
    matching its recorded digest."""
    loaded = []
    for key in ("source", "basis_evidence"):
        entry = split.get(key)
        if not isinstance(entry, dict):
            return None, None, f"basis_split has no {key}"
        path = _sibling(folder, entry.get("file"))
        if path is None:
            return (
                None,
                None,
                f"basis_split {key} file is not committed beside the report",
            )
        if file_sha256(path) != entry.get("sha256"):
            return (
                None,
                None,
                f"basis_split {key} digest differs from the committed file",
            )
        try:
            loaded.append(json.loads(path.read_bytes()))
        except ValueError:
            return None, None, f"basis_split {key} file is not JSON"
    return loaded[0], loaded[1], None


def _secondary_summary(source):
    alignment = source.get("alignment") or {}
    return {
        "members": len(source.get("members") or {}),
        "kendall_tau_b": alignment.get("kendall_tau_b"),
        "spearman_rho": alignment.get("spearman_rho"),
        "top_k_overlap": (alignment.get("top_k") or {}).get("overlap"),
        "divergences": sum(
            1
            for c in alignment.get("conditions", [])
            if c.get("condition") == "SCORE_VALUE_DIVERGENCE"
        ),
    }


#: A score recorded to six decimals: a recomputed value agrees with it when it rounds to it.
RESCORE_TOLERANCE = 5e-7


def _rescored_scores(split, folder, source_members, bases, primary):
    """`({member: score}, problem)` for members whose score was recomputed under the
    primary basis from recovered outputs. Each needs a committed rescore row whose output
    digest was verified, whose recomputed value rounds to the recorded one, and whose
    negated value is the score the report row carries."""
    entries = split.get("rescored")
    if entries is None:
        return {}, None
    entry = split.get("rescore")
    if not (isinstance(entries, list) and isinstance(entry, dict)):
        return {}, "basis_split rescored or rescore is malformed"
    path = _sibling(folder, entry.get("file"))
    if path is None or file_sha256(path) != entry.get("sha256"):
        return {}, "basis_split rescore file is missing or its digest differs"
    try:
        rows = {
            r.get("member"): r for r in json.loads(path.read_bytes()).get("rows", [])
        }
    except (ValueError, AttributeError):
        return {}, "basis_split rescore file is not a rescore record"
    scores = {}
    for item in entries:
        name = item.get("member") if isinstance(item, dict) else None
        row = rows.get(name)
        if name not in source_members or bases.get(name) == primary or row is None:
            return (
                {},
                f"rescored member {name} is not a non-primary source member with a rescore row",
            )
        recorded, recomputed = row.get("recorded_score"), row.get("recomputed_score")
        if row.get("output_digest_matches") is not True or not all(
            type(v) in (int, float) for v in (recorded, recomputed)
        ):
            return {}, f"rescored member {name} has no verified output digest or score"
        if abs(recomputed - recorded) > RESCORE_TOLERANCE:
            return (
                {},
                f"rescored member {name}: the recomputed score differs from the recorded one",
            )
        if abs(-recorded - source_members[name]["score"]) > 1e-9:
            return (
                {},
                f"rescored member {name}: the rescore row differs from the source score",
            )
        if item.get("score") != -recomputed:
            return (
                {},
                f"rescored member {name}: the report score is not the recomputed score",
            )
        scores[name] = item["score"]
    return scores, None


def _superseded_problem(split, folder):
    """Why a recorded SUPERSEDED result does not match its committed file, or None. A
    superseded result stays in the report with its reason (history, never deleted); it is
    never gate evidence."""
    entries = split.get("superseded")
    if entries is None:
        return None
    if not isinstance(entries, list):
        return "basis_split superseded is not a list"
    for entry in entries:
        if not isinstance(entry, dict) or not (
            isinstance(entry.get("reason"), str) and entry["reason"]
        ):
            return "a superseded result has no reason"
        path = _sibling(folder, entry.get("file"))
        if path is None or file_sha256(path) != entry.get("sha256"):
            return "a superseded result's file is missing or its digest differs"
        try:
            document = json.loads(path.read_bytes())
        except ValueError:
            return "a superseded result's file is not JSON"
        expected = _secondary_summary(document)
        if any(entry.get(k) != v for k, v in expected.items()):
            return "a superseded result's recorded numbers differ from its file"
    return None


def split_problem(report, folder):
    """Why a report's `basis_split` does not follow from its committed source and basis
    evidence, or None (also None when the report carries no split)."""
    split = report.get("basis_split")
    if split is None:
        return None
    if not isinstance(split, dict):
        return "basis_split is not an object"
    primary = split.get("primary_basis")
    if not (isinstance(primary, str) and primary):
        return "basis_split names no primary basis"
    source, evidence, problem = _split_files(split, folder)
    if problem:
        return problem
    if not (isinstance(source, dict) and source.get("schema") == REPORT_SCHEMA):
        return "basis_split source is not a readiness Q1 report"
    for key in (
        "challenge",
        "level",
        "reference",
        "decision_study",
        "scoring_rule_digest",
    ):
        if source.get(key) != report.get(key):
            return f"basis_split source differs from the report in {key}"
    source_members = source.get("members")
    if not (isinstance(source_members, dict) and isinstance(evidence, dict)):
        return "basis_split source or evidence has no members"
    bases = {}
    for name, row in source_members.items():
        recorded = evidence.get(name)
        basis = recorded.get("basis") if isinstance(recorded, dict) else None
        if not (isinstance(basis, str) and basis):
            return f"member {name} has no recorded score basis"
        if recorded.get("score") != row.get("score"):
            return f"member {name}: the basis evidence score differs from the source"
        bases[name] = basis
    rescored, rescore_problem = _rescored_scores(
        split, folder, source_members, bases, primary
    )
    if rescore_problem:
        return rescore_problem
    primary_names = {n for n, b in bases.items() if b == primary} | set(rescored)
    members = report["members"]
    if set(members) != primary_names:
        return "the report's members are not exactly the source members on the primary basis"
    for name, row in members.items():
        expected = {**source_members[name], "basis": primary}
        if name in rescored:
            expected["score"] = rescored[name]
        if row != expected:
            return f"member {name} differs from its source row"
    excluded = sorted(
        (
            {"basis": bases[n], "member": n}
            for n in source_members
            if n not in primary_names
        ),
        key=lambda e: e["member"],
    )
    if split.get("excluded") != excluded:
        return "the excluded members are not the rest of the source with their bases"
    superseded_problem = _superseded_problem(split, folder)
    if superseded_problem:
        return superseded_problem
    secondary = split.get("secondary")
    expected = _secondary_summary(source)
    if not isinstance(secondary, dict) or any(
        secondary.get(k) != v for k, v in expected.items()
    ):
        return (
            "the recorded secondary summary differs from the source report's alignment"
        )
    return None


def build_primary_report(
    source_path,
    evidence_path,
    primary_basis,
    rule_digest=None,
    rescore_path=None,
    superseded=(),
):
    """The derived primary-basis report for a mixed-basis source report: the members
    whose recorded basis is `primary_basis`, alignment recomputed on them, the source and
    its excluded members recorded. Both files must sit in the report folder."""
    source_path, evidence_path = Path(source_path), Path(evidence_path)
    source = json.loads(source_path.read_bytes())
    evidence = json.loads(evidence_path.read_bytes())
    members = {}
    excluded = []
    rescored = []
    rescore_rows = {}
    if rescore_path is not None:
        rescore_path = Path(rescore_path)
        rescore_rows = {
            r["member"]: r for r in json.loads(rescore_path.read_bytes())["rows"]
        }
    for name, row in sorted(source["members"].items()):
        recorded = evidence.get(name)
        basis = recorded.get("basis") if isinstance(recorded, dict) else None
        if not (isinstance(basis, str) and basis):
            raise ValueError(f"member {name} has no recorded score basis")
        again = rescore_rows.get(name) if basis != primary_basis else None
        if basis == primary_basis:
            members[name] = {**row, "basis": primary_basis}
        elif (
            again
            and again.get("output_digest_matches") is True
            and abs(again["recomputed_score"] - again["recorded_score"])
            <= RESCORE_TOLERANCE
        ):
            score = -again["recomputed_score"]
            members[name] = {**row, "basis": primary_basis, "score": score}
            rescored.append({"member": name, "score": score})
        else:
            excluded.append({"basis": basis, "member": name})
    panel = {
        "reference": source["reference"],
        "decision_study": source["decision_study"],
        "aliases": source.get("aliases", []),
        "members": members,
    }
    report = build_report(
        source["challenge"],
        source["level"],
        panel,
        rule_digest or source["scoring_rule_digest"],
    )
    report["basis_split"] = {
        "primary_basis": primary_basis,
        "label": (
            "PRIMARY: every member on the named Graphite frozen-rule basis (the non-primary "
            "members rescored from recovered outputs)"
            if rescored and not excluded
            else "PRIMARY: members on one named score basis. The source report mixes bases "
            "and is the SECONDARY, not gate evidence"
        ),
        "source": {"file": source_path.name, "sha256": file_sha256(source_path)},
        "basis_evidence": {
            "file": evidence_path.name,
            "sha256": file_sha256(evidence_path),
        },
        "excluded": excluded,
        **(
            {
                "rescored": rescored,
                "rescore": {
                    "file": rescore_path.name,
                    "sha256": file_sha256(rescore_path),
                },
            }
            if rescored
            else {}
        ),
        "secondary": {
            "label": (
                "SOURCE REPORT: the executor's file before the non-primary members were "
                "rescored"
                if rescored and not excluded
                else "MIXED-BASIS SECONDARY: not gate evidence"
            ),
            **_secondary_summary(source),
        },
        **(
            {
                "superseded": [
                    {
                        "file": Path(item["file"]).name,
                        "sha256": file_sha256(item["file"]),
                        "reason": item["reason"],
                        **_secondary_summary(
                            json.loads(Path(item["file"]).read_bytes())
                        ),
                    }
                    for item in superseded
                ]
            }
            if superseded
            else {}
        ),
    }
    return report


def report_names(level):
    """The file names a level's Q1 report may have, in order. Level 0 also reads
    the older single-file name; every other level has exactly one."""
    named = f"q1_report.L{int(level)}.json"
    return (named, "q1_report.json") if level == 0 else (named,)


def report_name(level):
    """The name `build` writes by default: `q1_report.json` for level 0 (the
    existing record, read as level 0), `q1_report.L<N>.json` otherwise."""
    return "q1_report.json" if level == 0 else report_names(level)[0]


def load_report(challenge, level=0, root=None):
    folder = Path(PACKAGE if root is None else root) / challenge
    names = report_names(level)
    path = next((folder / n for n in names if (folder / n).is_file()), None)
    if path is None:
        return None, folder / names[0]
    try:
        return json.loads(path.read_bytes()), path
    except ValueError:
        return False, path


def _problem(report, challenge, level):
    if not isinstance(report, dict) or report.get("schema") != REPORT_SCHEMA:
        return "not a readiness Q1 report"
    if report.get("challenge") != challenge or report.get("level") != level:
        return "names another challenge or level"
    members = report.get("members")
    if not (isinstance(members, dict) and members):
        return "no panel members"
    if not isinstance(report.get("alignment"), dict):
        return "no alignment"
    return None


def v1_alignment_report(item, ctx):
    report, path = load_report(ctx.challenge, ctx.level)
    if report is None:
        return Result(
            FAIL,
            "no Q1 alignment report is recorded for level "
            f"{ctx.level} (readiness/<challenge>/{report_name(ctx.level)}); run the "
            "Track B alignment on the registered panel and build one with "
            "`readiness.q1 build --level N`",
        )
    problem = _problem(report, ctx.challenge, ctx.level) if report else "unreadable"
    if problem:
        return Result(FAIL, f"{path.name} is unusable: {problem}", (path.name,))
    split = split_problem(report, path.parent)
    if split:
        return Result(
            FAIL, f"{path.name} has an invalid score-basis split: {split}", (path.name,)
        )
    refused = reference_problem(report, ctx.repository)
    if refused:
        return Result(FAIL, refused, (path.name,))
    current = current_rule_digest(ctx.challenge, ctx.repository)
    if current is None:
        return Result(
            FAIL,
            "no scoring is registered for the challenge, so the report cannot be "
            "shown current against a scoring rule",
            (path.name,),
        )
    if report.get("scoring_rule_digest") != current:
        return Result(
            FAIL,
            "the report is stale: it was built under another scoring rule digest",
            (f"recorded {report.get('scoring_rule_digest')}", f"current {current}"),
        )
    if _alignment_of(report["members"]) != report["alignment"]:
        return Result(
            FAIL,
            "the recorded alignment does not follow from its members",
            (path.name,),
        )
    a = report["alignment"]
    band = a["tau_noise_band"]["band"]
    divergences = [
        c["member"]
        for c in a["conditions"]
        if c["condition"] == "SCORE_VALUE_DIVERGENCE"
    ]
    basis_note = ""
    basis_evidence = ()
    if report.get("basis_split"):
        split_block = report["basis_split"]
        secondary = split_block["secondary"]
        basis_note = (
            f" Primary basis {split_block['primary_basis']!r}, n={len(report['members'])}; the "
            f"{secondary['members']}-member mixed-basis source is a labelled SECONDARY "
            f"(tau {secondary['kendall_tau_b']}), not gate evidence."
        )
        basis_evidence = (
            f"primary_basis:{split_block['primary_basis']}",
            f"primary_n:{len(report['members'])}",
            f"secondary_mixed_basis_n:{secondary['members']}",
            f"source:{split_block['source']['sha256']}",
            *[
                f"superseded:{item['sha256']}"
                for item in split_block.get("superseded", [])
            ],
        )
    return Result(
        PASS,
        f"Q1 report recorded: tau {a['kendall_tau_b']} (band {band}), rho "
        f"{a['spearman_rho']}, {len(divergences)} divergences. A measurement, not a "
        "threshold: a negative or within-noise tau is recorded, and the first runs "
        "are framed as alignment measurements (review)." + basis_note,
        (
            f"report:{digest(report)}",
            f"tau:{a['kendall_tau_b']}",
            f"rho:{a['spearman_rho']}",
            f"tau_band:{band}",
            *basis_evidence,
            *[f"divergence:{m}" for m in divergences],
        ),
    )


def _alias_map(report):
    """`({alias: target}, problem)`. An alias has identical predictions to its
    target (an aliasing record), so its outcome vector is identical by
    construction and is not distinct evidence: V2 skips it. Each alias and target
    must be a panel member; otherwise the report is unusable (fail closed)."""
    aliases = report.get("aliases", [])
    members = report["members"]
    mapping = {}
    if not isinstance(aliases, list):
        return {}, "aliases is not a list"
    for entry in aliases:
        if not (
            isinstance(entry, dict)
            and entry.get("alias") in members
            and entry.get("target") in members
            and entry["alias"] != entry["target"]
        ):
            return {}, "an alias entry does not name two distinct panel members"
        mapping[entry["alias"]] = entry["target"]
    if any(target in mapping for target in mapping.values()):
        return {}, "an alias targets another alias"
    return mapping, None


def _outcome_key(outcome):
    """A member's decision outcome as a comparable key, or None if unrecorded.
    A scalar (a design id, or ABSTAIN) is itself. A per-scenario mapping
    `{scenario: selected-or-ABSTAIN}` is its whole vector: two members differ
    when they differ in any scenario; key order is irrelevant; an empty mapping
    is unrecorded."""
    if isinstance(outcome, str):
        return outcome or None
    if isinstance(outcome, dict) and outcome:
        if not all(
            isinstance(k, str) and isinstance(v, str) and v for k, v in outcome.items()
        ):
            return None
        return json.dumps(outcome, sort_keys=True, separators=(",", ":"))
    return None


def v2_panel_discrimination(item, ctx):
    report, path = load_report(ctx.challenge, ctx.level)
    if report is None:
        return Result(
            FAIL,
            f"no Q1 report is recorded for level {ctx.level}, so panel "
            "discrimination is unmeasured",
        )
    problem = _problem(report, ctx.challenge, ctx.level) if report else "unreadable"
    if problem:
        return Result(FAIL, f"{path.name} is unusable: {problem}", (path.name,))
    split = split_problem(report, path.parent)
    if split:
        return Result(
            FAIL, f"{path.name} has an invalid score-basis split: {split}", (path.name,)
        )
    aliased, alias_problem = _alias_map(report)
    if alias_problem:
        return Result(FAIL, alias_problem, (path.name,))
    outcomes = {}
    for name, row in sorted(report["members"].items()):
        if row.get("eligible") is not True or name in aliased:
            continue
        outcome = row.get("decision_outcome")
        key = _outcome_key(outcome)
        if key is None:
            return Result(
                FAIL, f"member {name} records no decision outcome", (path.name,)
            )
        outcomes.setdefault(key, []).append(name)
    evidence = tuple(f"{o}:{','.join(m)}" for o, m in sorted(outcomes.items()))
    refused = reference_problem(report, ctx.repository)
    if refused:
        return Result(FAIL, refused, evidence)
    if len(outcomes) >= MIN_DISTINCT_OUTCOMES:
        return Result(
            PASS,
            f"{len(outcomes)} distinct decision outcomes among panel members",
            evidence,
        )
    return Result(
        FAIL,
        f"{len(outcomes)} distinct decision outcome(s), below {MIN_DISTINCT_OUTCOMES}: "
        "widen the construction families first (development variant)",
        evidence,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_pipeline.readiness.q1"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build a Q1 report from a harness panel")
    b.add_argument("--challenge", required=True)
    b.add_argument("--level", type=int, default=0)
    b.add_argument("--panel", required=True)
    b.add_argument(
        "--out",
        help="default: readiness/<challenge>/q1_report.json for level 0, "
        "q1_report.L<N>.json otherwise",
    )
    d = sub.add_parser(
        "build-primary",
        help="derive the primary-basis report from a mixed-basis source report",
    )
    d.add_argument("--source", required=True)
    d.add_argument("--basis-evidence", required=True)
    d.add_argument("--primary-basis", required=True)
    d.add_argument(
        "--rescore", help="a verified rescore record for non-primary members"
    )
    d.add_argument(
        "--superseded",
        action="append",
        default=[],
        metavar="FILE=REASON",
        help="a superseded result kept in the report with its reason",
    )
    d.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "build-primary":
        try:
            report = build_primary_report(
                args.source,
                args.basis_evidence,
                args.primary_basis,
                rescore_path=args.rescore,
                superseded=[
                    {"file": f, "reason": r}
                    for f, _, r in (x.partition("=") for x in args.superseded)
                ],
            )
        except (OSError, ValueError, KeyError) as error:
            print(f"cannot derive the primary-basis report: {error}")
            return 2
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline=chr(10)) as out:
            out.write(json.dumps(report, indent=1, sort_keys=True) + chr(10))
        return 0
    panel = json.loads(Path(args.panel).read_bytes())
    for key in ("reference", "decision_study", "members"):
        if key not in panel:
            print(f"panel is missing {key}")
            return 2
    rule = current_rule_digest(args.challenge)
    if rule is None:
        print("no scoring is registered for the challenge; cannot bind a rule digest")
        return 2
    report = build_report(args.challenge, args.level, panel, rule)
    out_path = args.out or str(Path(PACKAGE) / args.challenge / report_name(args.level))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline=chr(10)) as out:
        out.write(json.dumps(report, indent=1, sort_keys=True) + chr(10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
