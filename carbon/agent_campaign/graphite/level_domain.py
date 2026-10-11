"""A level's declared domain, rendered for the Constructor and checked early.

A Constructor that is not told a level's domain proposes outside it: a value past a
ceiling, a name the level calls something else, or a family the Challenge's pods do
not serve. Stage A's Constructor L0 runs lost seven proposals to the first two and one
to the third (GRAPHITE_STAGE_A_REFUSALS.md). This module states the domain instead:

* it reads the accepted level documents
  (`carbon/challenge_pipeline/proposals/<challenge>/level-N.json`): Level 0's document
  gives the parameter ranges, allowed names, the families and which family needs which
  backend, and every level builds on it; a higher level's own document states what it
  adds in prose and is listed as written;
* it intersects that with the backends the Challenge's scoring record serves
  (`ChallengeScoring.served_backends`), so a family a Challenge cannot serve is not
  offered and a backend it does not serve is not listed;
* it adds the Challenge's combination rules (`level_rules.json`), each checked
  against the real compile step by a test, so the brief cannot drift from it;
* `precheck` refuses, before the compile step, a request for a backend or a family
  that intersection removes.

This is DEVELOPMENT tooling. It changes no frozen or LIVE rule, edits no compile
module, and refuses only what the pods could not serve anyway (the same status and
code as the served-backend check that already ran after the compile). A Challenge
with no level document has no declared domain here: nothing is rendered and
nothing is refused early.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
PROPOSALS = Path("carbon/challenge_pipeline/proposals")
RULES = Path(__file__).with_name("level_rules.json")
SCHEMA = "carbon.graphite.level-domain.v1"
EN_DASH = "–"

_RANGE = re.compile(
    rf"^(uint|float),\s*(\S+?){EN_DASH}(\S+?),\s*default\s*(\S+?)"
    r"(?:;\s*applies to\s*(.+))?$"
)
_BOOL = re.compile(r"^bool,\s*default\s*(\S+?)(?:;\s*applies to\s*(.+))?$")
_CHOICE = re.compile(r"^choice:\s*(.+?);\s*default\s*(\S+?)(?:;\s*applies to\s*(.+))?$")
_SELECTOR = re.compile(r"selector\s+(\w+)")
_BACKEND_ONLY = re.compile(r"(\w+)\s+backend only", re.IGNORECASE)


def _number(text, kind):
    return int(text) if kind == "uint" else float(text)


def _applies(text):
    return [] if text is None else [part.strip() for part in text.split(",")]


def parse_bounds(text):
    """The structured domain a `bounds` string states, or None when it is not a
    parameter domain (a family or an extension is described, not bounded)."""
    text = text.strip()
    found = _RANGE.match(text)
    if found:
        kind, low, high, default, applies = found.groups()
        return {
            "kind": kind,
            "min": _number(low, kind),
            "max": _number(high, kind),
            "default": _number(default, kind),
            "applies_to": _applies(applies),
        }
    found = _BOOL.match(text)
    if found:
        default, applies = found.groups()
        return {
            "kind": "bool",
            "default": default == "true",
            "applies_to": _applies(applies),
        }
    found = _CHOICE.match(text)
    if found:
        choices, default, applies = found.groups()
        return {
            "kind": "choice",
            "choices": [c.strip() for c in choices.split(",")],
            "default": default,
            "applies_to": _applies(applies),
        }
    return None


def level_document(challenge_id, level, repository=REPOSITORY):
    """The level's accepted document, or None when the Challenge has none."""
    path = Path(repository) / PROPOSALS / challenge_id / f"level-{level}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def combination_rules(challenge_id):
    document = json.loads(RULES.read_text(encoding="utf-8"))
    return [r["text"] for r in document["challenges"].get(challenge_id, [])]


def declared(document):
    """`(families, parameters)` the level document declares, before any
    intersection. `families` maps a selector to the backend only it needs (or
    None); `parameters` maps a short parameter name to its domain."""
    families, parameters, unparsed = {}, {}, []
    for capability in document["capabilities"]:
        identifier, bounds = capability["id"], capability.get("bounds", "")
        if identifier.startswith("model_family."):
            selector = _SELECTOR.search(bounds)
            only = _BACKEND_ONLY.search(bounds)
            name = selector.group(1) if selector else identifier.split(".", 1)[1]
            families[name] = only.group(1).lower() if only else None
            continue
        domain = parse_bounds(bounds)
        if domain is None:
            unparsed.append({"id": identifier, "bounds": bounds})
            continue
        name = identifier.split(".", 1)[1]
        if name in parameters:
            raise ValueError(f"level document names parameter {name} twice")
        parameters[name] = {"id": identifier, **domain}
    return families, parameters, unparsed


def domain_for(challenge_id, level, served_backends, repository=REPOSITORY):
    """The level's domain intersected with the served backends, or None when the
    Challenge has no level document."""
    # Level 0's document is the base every level builds on (its parameters keep
    # their domains); a higher level's own document states what that level adds, in
    # prose, so it is listed as written and not parsed.
    document = level_document(challenge_id, 0, repository)
    if document is None:
        return None
    additions = []
    if level:
        own = level_document(challenge_id, level, repository)
        if own is not None:
            additions = [c["id"] for c in own["capabilities"]]
    served = [str(b).lower() for b in served_backends]
    families, parameters, unparsed = declared(document)
    offered = sorted(
        f for f, need in families.items() if need is None or need in served
    )
    removed = {
        f: need
        for f, need in sorted(families.items())
        if need is not None and need not in served
    }
    effective = {}
    for name, domain in parameters.items():
        domain = dict(domain)
        if domain["kind"] == "choice" and name == "backend":
            domain["declared_choices"] = list(domain["choices"])
            domain["choices"] = [c for c in domain["choices"] if c in served]
            if domain["default"] not in domain["choices"]:
                domain["default"] = domain["choices"][0] if domain["choices"] else None
        domain["applies_to"] = [
            a for a in domain["applies_to"] if a == "all" or a in offered
        ]
        effective[name] = domain
    return {
        "schema": SCHEMA,
        "challenge": challenge_id,
        "level": level,
        "source": [
            (PROPOSALS / challenge_id / f"level-{n}.json").as_posix()
            for n in sorted({0, level})
        ],
        "served_backends": served,
        "families": offered,
        "families_not_served": [
            {"family": f, "needs_backend": need} for f, need in removed.items()
        ],
        "parameters": effective,
        "combination_rules": combination_rules(challenge_id),
        "other_capabilities": unparsed,
        "level_additions": additions,
        "note": (
            "A request outside this domain is refused before any pod is reserved. "
            "Only the names and values listed here are accepted."
        ),
    }


def for_scoring(scoring, variant, repository=REPOSITORY):
    """The domain for a session: its Challenge's scoring record and its level
    (a development variant's level, else 0)."""
    level = 0 if variant is None else variant.level
    return domain_for(scoring.challenge_id, level, scoring.served_backends, repository)


def precheck(strategy, domain):
    """None, or the early refusal for a request the intersection removes:
    `{"reason_code", "issues", "served_backends"}`. Only a backend or a family the
    Challenge's pods do not serve is refused here; every other check stays with
    the compile step."""
    if domain is None or type(strategy) is not dict:
        return None
    served = domain["served_backends"]
    parameters = strategy.get("parameters")
    backend = parameters.get("backend") if type(parameters) is dict else None
    spec = domain["parameters"].get("backend")
    if (
        type(backend) is str
        and spec is not None
        and backend in spec.get("declared_choices", [])
        and backend not in served
    ):
        return {
            "reason_code": "backend_not_served:" + backend,
            "issues": [["level_domain.backend_not_served", "/parameters/backend"]],
            "served_backends": served,
        }
    for entry in domain["families_not_served"]:
        if strategy.get("backbone") == entry["family"]:
            return {
                "reason_code": "backend_not_served:" + entry["needs_backend"],
                "issues": [["level_domain.family_not_served", "/backbone"]],
                "served_backends": served,
            }
    return None
