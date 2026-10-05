"""Construction identity: what counts as one distinct construction.

OWNER-GRAPHITE-TEST-WAVE-04 §1 (owner, 2026-10-05): anything that counts,
limits, deduplicates or rewards *distinct constructions* identifies them by
the rebuilt artifact (the trained-parameter or built-artifact digest the
reconstruction rule binds), never by recipe or expression text. Limits keyed
on the participant are unaffected. Challenge-neutral: nothing here names a
Challenge.

**The identity (`artifact_of`).** Carbon's own rebuild of a construction
(`adapter.rebuild`) is the only source:

1. an adapter that knows its artifact better says so
   (`adapter.artifact_identity(rebuilt)`, a sha256 digest);
2. otherwise, when Carbon's rebuilt record has the Graphite built-record
   shape (`recipe` and `staged`), the **build identity** (`build_identity`):
   the digest of everything the record binds that the trainer consumes
   (Challenge, contract, recipe family and settings, staged data and program
   files, program, seed, any development binding), with the fields that only
   digest the submission as written left out (`PROVENANCE_FIELDS`, and the
   staged `recipe.json`, which carries `recipe_digest` beside the family,
   settings and seed the record already binds). Same recipe, same seed and
   same pinned trainer give the same build identity however the recipe was
   written; a different seed or setting is a different one;
3. otherwise the rebuilt record's own digest (`Rebuilt.rebuilt_digest`, or
   the digest of the record).

**No artifact.** An attempt Carbon rebuilt nothing for (it carried no
construction, Graphite refused it, the path or Carbon refused it before a
rebuild, or Carbon could not rebuild it) has no artifact. It is counted as an
attempt and `without_artifact`, and never as a distinct construction. A
*breach* without an artifact (an exposure, or the path accepting what Carbon
cannot rebuild) is still a finding; for distinct counts it counts once per
**behaviour** (`behaviour_key`: its family, its conditions and the verdict's
reason, or, for an attack Carbon's own deterministic harness declared, that
attack), never once per wording. It can therefore never be rewarded as a
distinct construction.

**Text identity** (`text_identity`, a digest of the construction as written)
is kept as a diagnostic only. Nothing counts, limits, deduplicates or rewards
by it.

**The copy probe** (`copy_family`, `copy_probe`): the leaderboard / copy
attack. A trivially reworded copy of an incumbent's recipe (`rewordings`:
key order, whitespace, escaped letters, the default seed or a default
setting made explicit and, once Level 1 exists, a loss expression wrapped in
`scale(1, E)` or with its commutative arguments reordered) must not count as
a new construction anywhere: the report's distinct counts, B2's, the
knowledge store's priors ("strategies that worked") and its regression
specimens. The probe runs the real mechanisms on the incumbent and its copy;
its vulnerable specimen runs the same mechanisms with identity assigned by
text, so the detector fires there. Its valid control is a genuinely
different construction (the incumbent at another seed), which must count as
two. It lives here, in the shared layer, so every Challenge gets it: the
incumbent comes from the adapter (`incumbent_constructions()`) or the
Challenge's registered scoring (`baseline_strategy()`), and an adapter with
neither is NOT_RUN, never a pass.

Nothing here is a grade, a score or security acceptance.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path

from carbon.development_session.profile import canonical, digest
from carbon.reconstruction import artifact_identity as _build

SCHEMA = "carbon.attack.construction-identity.v1"
#: The identity rule's name, recorded wherever a count depends on it.
RULE = "rebuilt_artifact.v1"
#: How an attempt is identified for distinct counts.
ARTIFACT, BEHAVIOUR, NONE = "rebuilt_artifact", "behaviour", "none"
#: The build identity (`carbon.reconstruction.artifact_identity`): Carbon's
#: rebuilt record less the fields that digest the submission as written.
PROVENANCE_FIELDS = _build.PROVENANCE_FIELDS
PROVENANCE_STAGED = _build.PROVENANCE_STAGED
build_identity = _build.build_identity
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
#: Attempt outcomes (`attack.verify`), named here so this module imports none.
_HELD, _BREACHED, _UNREBUILDABLE = "HELD", "BREACHED", "UNREBUILDABLE"


class IdentityError(ValueError):
    """An adapter's artifact identity that is not a sha256 digest."""


# -- the identity ---------------------------------------------------------------------------
def _checked(value):
    if not (isinstance(value, str) and _DIGEST.fullmatch(value)):
        raise IdentityError("artifact_identity_is_a_sha256_digest")
    return value


def artifact_of(adapter, rebuilt, record=None):
    """The rebuilt artifact's identity (module docstring): the adapter's own
    `artifact_identity(rebuilt)`, else the build identity of Carbon's rebuilt
    `record`, else `rebuilt.rebuilt_digest`, else the record's digest."""
    own = getattr(adapter, "artifact_identity", None)
    if callable(own):
        return _checked(own(rebuilt))
    built = build_identity(record)
    if built is not None:
        return built
    value = getattr(rebuilt, "rebuilt_digest", None)
    if isinstance(value, str) and _DIGEST.fullmatch(value):
        return value
    if record is None:
        raise IdentityError("rebuilt_construction_has_no_identity")
    return digest(canonical({"schema": SCHEMA, "record": dict(record)}))


def text_identity(construction):
    """A DIAGNOSTIC digest of a construction as written: the text itself
    when it is text, else its JSON in the order given. Never a count key."""
    if isinstance(construction, (bytes, str)):
        body = construction.encode() if isinstance(construction, str) else construction
    else:
        body = json.dumps(construction, default=repr).encode()
    return digest(body)


def behaviour_key(family, conditions=(), reason=None, declared=None):
    """The behaviour a breach without an artifact counts as (module
    docstring): its family, conditions and reason, or the attack Carbon's
    own harness declared."""
    return digest(
        canonical(
            {
                "family": family,
                "conditions": sorted(conditions or ()),
                "reason": reason,
                "declared": declared,
            }
        )
    )


def identity_of(row, family=None):
    """`(basis, key)` for one attempt row (`report` shape): the artifact when
    it has one; a breach without one by its behaviour; anything else NONE."""
    artifact = row.get("artifact")
    if artifact:
        return ARTIFACT, artifact
    if row.get("outcome") == _BREACHED:
        return BEHAVIOUR, behaviour_key(
            row.get("family", family),
            row.get("conditions") or (),
            row.get("reason"),
            row.get("declared"),
        )
    return NONE, None


def distinct(rows, family=None):
    """Distinct counts over attempt rows (`report` shape: `outcome`,
    `conditions`, `artifact`, `reason`, optional `declared`, `rebuild`,
    `construction_digest`), under `RULE`:

    - `constructions`: distinct rebuilt artifacts among the attempts;
    - `without_artifact`: attempts with none (counted, never distinct);
    - `held_constructions`: distinct artifacts among holds;
    - `verified_constructions`: distinct artifacts among breaches;
    - `verified_behaviours`: distinct behaviours among breaches with none;
    - `verified`: the two together, the only distinct finding count;
    - `diagnostic.construction_digests`: distinct text identities, a
      diagnostic that counts nothing."""
    rows = list(rows)
    artifacts, held, verified, behaviours, texts = set(), set(), set(), set(), set()
    without = 0
    for row in rows:
        basis, key = identity_of(row, family)
        if row.get("construction_digest"):
            texts.add(row["construction_digest"])
        if basis == ARTIFACT:
            artifacts.add(key)
            if row.get("outcome") == _HELD and row.get("rebuild") != _UNREBUILDABLE:
                held.add(key)
            if row.get("outcome") == _BREACHED:
                verified.add(key)
            continue
        without += 1
        if basis == BEHAVIOUR:
            behaviours.add(key)
    return {
        "rule": RULE,
        "constructions": len(artifacts),
        "without_artifact": without,
        "held_constructions": len(held),
        "verified_constructions": len(verified),
        "verified_behaviours": len(behaviours),
        "verified": len(verified) + len(behaviours),
        "diagnostic": {"construction_digests": len(texts)},
    }


# -- the copy probe -------------------------------------------------------------------------
COPY_FAMILY = "construction_copy"
#: Farming distinctness with a reworded copy is score exploitation.
COPY_CHECK = "score_exploitation_and_tail_failures"
COPY_DESCRIPTION = (
    "a trivially reworded copy of an incumbent's recipe counts as one "
    "construction with it: never a new one"
)
#: The tool a probe attempt names: a construction submitted for validation.
_PROBE_TOOL = "dry_validate"
#: Loss-expression operations whose arguments commute (Level 1,
#: `carbon.reconstruction.loss_expressions`).
_COMMUTATIVE = ("add", "mul")


def _reversed_keys(value):
    if isinstance(value, dict):
        return {k: _reversed_keys(value[k]) for k in reversed(list(value))}
    if isinstance(value, list):
        return [_reversed_keys(item) for item in value]
    return value


def _escaped(value):
    """JSON text with every letter in every string written as `\\uXXXX`."""
    if isinstance(value, str):
        return (
            '"'
            + "".join(
                f"\\u{ord(ch):04x}" if ch.isalpha() else json.dumps(ch)[1:-1]
                for ch in value
            )
            + '"'
        )
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(_escaped(str(k)) + ":" + _escaped(v) for k, v in value.items())
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(_escaped(item) for item in value) + "]"
    return json.dumps(value)


def _is_expression(node):
    if not isinstance(node, dict):
        return False
    if set(node) == {"term"}:
        return isinstance(node["term"], str)
    from carbon.reconstruction import loss_expressions

    return node.get("op") in loss_expressions.OPERATIONS


def _expression_paths(value, path=()):
    """Paths to every loss-expression root a construction carries: a value
    under a key naming a loss that is a loss-expression node."""
    if isinstance(value, dict):
        for key, item in value.items():
            if "loss" in str(key) and _is_expression(item):
                yield (*path, key)
            else:
                yield from _expression_paths(item, (*path, key))


def _replace(value, path, new):
    if not path:
        return new
    out = dict(value)
    out[path[0]] = _replace(value[path[0]], path[1:], new)
    return out


def _get_path(value, path):
    for key in path:
        value = value[key]
    return value


def _reorder_commutative(node):
    if not isinstance(node, dict):
        return node
    out = {k: _reorder_commutative(v) for k, v in node.items()}
    if out.get("op") in _COMMUTATIVE and isinstance(out.get("args"), list):
        out["args"] = list(reversed(out["args"]))
    if isinstance(out.get("arg"), dict):
        out["arg"] = _reorder_commutative(out["arg"])
    return out


def loss_rewordings(construction):
    """Level-1 rewordings of every loss expression a construction carries:
    `E` as `scale(1, E)`, and commutative arguments reordered. None today:
    no contract registers a loss expression."""
    out = []
    for path in _expression_paths(construction):
        expression = _get_path(construction, path)
        tag = ".".join(str(p) for p in path)
        scaled = {"op": "scale", "by": 1.0, "arg": expression}
        out.append(("scale_one:" + tag, _replace(construction, path, scaled)))
        reordered = _reorder_commutative(expression)
        if reordered != expression:
            out.append(("commuted:" + tag, _replace(construction, path, reordered)))
    return out


def rewordings(construction, record=None, adapter=None):
    """`((name, text), ...)`: the construction as a participant would submit
    a trivially reworded copy of it (`strategy_json` text). `record` is
    Carbon's rebuilt record of it, for a default setting made explicit;
    `adapter.rewordings(construction)` adds the adapter's own (each a
    `(name, construction or text)`)."""
    plain = json.dumps(construction)
    out = [
        ("key_order", json.dumps(_reversed_keys(construction))),
        ("whitespace", json.dumps(construction, indent=2) + "\n"),
        ("escaped_letters", _escaped(construction)),
        ("explicit_default_seed", json.dumps({"strategy": construction, "seed": 0})),
    ]
    settings = None
    if isinstance(record, Mapping) and isinstance(record.get("recipe"), Mapping):
        settings = record["recipe"].get("settings")
    parameters = (
        construction.get("parameters") if isinstance(construction, dict) else None
    )
    if isinstance(settings, Mapping) and isinstance(parameters, dict):
        for key in sorted(settings):
            if key not in parameters:
                explicit = {
                    **construction,
                    "parameters": {**parameters, key: settings[key]},
                }
                out.append(("explicit_default:" + key, json.dumps(explicit)))
                break
    for name, value in loss_rewordings(construction):
        out.append((name, json.dumps(value)))
    own = getattr(adapter, "rewordings", None)
    if callable(own):
        for name, value in own(construction):
            out.append(("adapter:" + str(name), _text(value)))
    return tuple((name, text) for name, text in out if text != plain)


def _text(value):
    return value if isinstance(value, str) else json.dumps(value)


def incumbents(adapter):
    """The incumbent constructions the copy probe copies: the adapter's own
    `incumbent_constructions()`, else its Challenge's registered scoring
    baseline (`challenge_validator.scoring.baseline_strategy`), else none."""
    own = getattr(adapter, "incumbent_constructions", None)
    if callable(own):
        return tuple(own())
    from carbon.challenge_validator import scoring

    try:
        return (scoring.scoring_for(adapter.challenge_id).baseline_strategy(),)
    except scoring.ScoringUnavailable:
        return ()


def _probe_attempt(name, position, text):
    from carbon.agent_campaign.attack import analysis

    return analysis.Attempt(
        identity=f"epoch-1-tool-{position:03d}",
        epoch=1,
        stage=None,
        turn=position,
        position=0,
        tool=analysis.PREFIX + _PROBE_TOOL,
        arguments={"strategy_json": text},
        result={"status": "OK", "accepted": True},
        withheld=None,
        intent_digest=digest(text.encode()),
        result_digest=digest(canonical({"probe": name})),
    )


def _as_finding(verdict, artifact):
    """A probe verdict as the finding a session would report for it: both
    the incumbent and the copy breached, so every mechanism that could
    reward the copy sees it."""
    from carbon.agent_campaign.attack import verify

    return verify.Verdict(
        attempt=verdict.attempt,
        family=COPY_FAMILY,
        rebuild=verdict.rebuild,
        outcome=verify.BREACHED,
        conditions=(verify.FAILING_TRIGGER,),
        scored=verdict.rebuild == verify.REBUILT,
        unrebuildable=verdict.unrebuildable,
        refused_by=verdict.refused_by,
        reason="copy_probe",
        evidence=dict(verdict.evidence),
        artifact=artifact,
    )


def counts(adapter, texts, *, by_text=False):
    """Every mechanism's count of distinct constructions over the attempts
    `texts` (strategy_json text, in order), each first verified by Carbon
    (`verify.verify`) and reported as a breach. `by_text=True` is the
    vulnerable specimen: identity assigned from the text as written."""
    from carbon.agent_campaign.attack import analysis, benchmark, knowledge, report
    from carbon.agent_campaign.attack import verify as verifier

    findings = []
    for position, text in enumerate(texts, start=1):
        attempt = _probe_attempt(COPY_FAMILY, position, text)
        verdict = verifier.verify(attempt, adapter, family=analysis.UNASSIGNED)
        artifact = text_identity(text) if by_text else verdict.artifact
        findings.append(_as_finding(verdict, artifact))
    submitted = dict(zip((v.attempt for v in findings), texts, strict=True))
    runs = report.attacker_runs(findings)
    line = report.family_report(runs, controls_held_out=())["families"][COPY_FAMILY]
    b2 = benchmark.b2(runs, [], budget=len(findings))["families"][COPY_FAMILY]
    root = Path(tempfile.gettempdir()) / ("carbon-copy-probe-" + uuid.uuid4().hex)
    try:
        store = knowledge.AttackStore(root)
        for verdict in findings:
            store.add_finding(
                challenge_id=adapter.challenge_id,
                level=adapter.level,
                contract_digest=adapter.contract_digest,
                check=COPY_CHECK,
                family=COPY_FAMILY,
                boundary=COPY_DESCRIPTION,
                strategy="copy-probe",
                attempt_id=verdict.attempt,
                condition=verdict.conditions[0],
                specimen={"strategy_json": submitted[verdict.attempt]},
                evidence=[verdict.evidence["intent"]],
                rebuilt=True,
                artifact=verdict.artifact,
                behaviour=verdict.reason,
            )
        priors = store.priors(adapter.challenge_id)
        specimens = store.specimens(adapter.challenge_id, adapter.level)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return {
        "report_constructions": line["distinct"]["constructions"],
        "report_verified": line["distinct"]["verified"],
        # Against an empty baseline: what B2 credits the attacker with.
        "b2_verified": b2["verified_difference"],
        "store_found": len(priors["by_strategy"]["copy-probe"]["found"]),
        "store_distinct_findings": priors["by_family"][COPY_FAMILY][
            "distinct_findings"
        ],
        "store_specimens": len(specimens),
    }


def _counted(adapter, value, by_text):
    tally = counts(adapter, (value["incumbent"], value["other"]), by_text=by_text)
    expected = value["expect"]
    return {
        "counts": tally,
        "expect": expected,
        "accepted": all(n == expected for n in tally.values()),
        "counted_as_new": any(n > expected for n in tally.values()),
    }


def copy_family(adapter, constructions=None, *, plan=None):
    """The copy probe as an engine `Family` (module docstring), over the
    adapter's incumbents (or `constructions`). Each attack is one incumbent
    and one reworded copy Carbon rebuilds; a rewording Carbon refuses is not
    a copy of anything and is left out (`copy_probe` lists it)."""
    from carbon.agent_campaign.attack import engine

    adapter = _remembered(adapter)
    if plan is None:
        plan = _plan(adapter, constructions)

    def attacks():
        return tuple(plan["attacks"])

    def control():
        if not plan["controls"]:
            return False  # nothing to tell apart: never a pass
        return all(
            _counted(adapter, value, False)["accepted"] for value in plan["controls"]
        )

    return engine.Family(
        name=COPY_FAMILY,
        check=COPY_CHECK,
        boundary=lambda value: _counted(adapter, value, False),
        attacks=attacks,
        specimen=lambda value: _counted(adapter, value, True),
        breached=lambda result: result["counted_as_new"],
        control=control,
        description=COPY_DESCRIPTION,
    )


class _Remembered:
    """The adapter, with each rebuild remembered by the construction's
    content for one probe run: the probe rebuilds the same incumbent and
    copies many times, and a rebuild is deterministic. A performance memo
    only: nothing is counted by it."""

    def __init__(self, adapter):
        self._adapter = adapter
        self._rebuilt = {}

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    def rebuild(self, construction):
        try:
            key = canonical(construction)
        except (TypeError, ValueError):
            return self._adapter.rebuild(construction)
        if key not in self._rebuilt:
            self._rebuilt[key] = self._adapter.rebuild(construction)
        return self._rebuilt[key]


def _remembered(adapter):
    return adapter if type(adapter) is _Remembered else _Remembered(adapter)


def _plan(adapter, constructions=None):
    from carbon.agent_campaign.attack import verify as verifier

    found = incumbents(adapter) if constructions is None else tuple(constructions)
    plan = {"attacks": [], "controls": [], "refused": [], "incumbents": 0}
    for index, construction in enumerate(found):
        label = f"incumbent_{index}"
        made = adapter.rebuild(construction)
        if verifier.is_unrebuildable(made):
            plan["refused"].append({"incumbent": label, "rewording": None})
            continue
        plan["incumbents"] += 1
        record = verifier.record_of(made)
        original = json.dumps(construction)
        for name, text in rewordings(construction, record, adapter):
            copy = json.loads(text)
            if verifier.is_unrebuildable(adapter.rebuild(copy)):
                plan["refused"].append({"incumbent": label, "rewording": name})
                continue
            plan["attacks"].append(
                (
                    f"{label}:{name}",
                    {"incumbent": original, "other": text, "expect": 1},
                )
            )
        other = json.dumps({"strategy": construction, "seed": 1})
        plan["controls"].append({"incumbent": original, "other": other, "expect": 2})
    return plan


NOT_RUN = "NOT_RUN"
NO_INCUMBENT = "no_incumbent_construction"


def copy_probe(adapter, constructions=None):
    """Run the copy probe for one adapter: `{state, rule, incumbents,
    refused_rewordings, run}`. `run` is the engine `FamilyRun` (None when
    NOT_RUN). With no incumbent Carbon rebuilds, the probe is NOT_RUN
    (`no_incumbent_construction`), never a pass."""
    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import engine

    context = core.run_context(adapter)
    adapter = _remembered(adapter)
    plan = _plan(adapter, constructions)
    if not plan["incumbents"]:
        return {
            "schema": SCHEMA,
            "family": COPY_FAMILY,
            "check": COPY_CHECK,
            "rule": RULE,
            "state": NOT_RUN,
            "reason": NO_INCUMBENT,
            "incumbents": 0,
            "refused_rewordings": plan["refused"],
            "run": None,
        }
    run = engine.run_family(copy_family(adapter, plan=plan), context=context)
    return {
        "schema": SCHEMA,
        "family": COPY_FAMILY,
        "check": COPY_CHECK,
        "rule": RULE,
        "state": engine.family_state(run),
        "reason": None,
        "incumbents": plan["incumbents"],
        "refused_rewordings": plan["refused"],
        "run": run,
    }


def probe_record(probe):
    """The copy probe as JSON data for a coverage report."""
    run = probe["run"]
    return {
        **{key: value for key, value in probe.items() if key != "run"},
        "records": [] if run is None else list(run.records),
        "attempted": 0 if run is None else run.attempted,
    }
