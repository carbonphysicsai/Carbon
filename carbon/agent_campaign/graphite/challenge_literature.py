"""Literature for a named Challenge (VALIDATOR-08).

Battery's literature pipeline stays exactly as it was: the
`graphite-phase2-queries.v1` query set, the v1 extraction prompt, the
`backfill/` card store and its frozen snapshot. Every other Challenge gets
its literature through a registered **literature profile**, one document per
Challenge in `literature_profiles/`, pinned by digest in its `registry.json`.
A profile holds:
- **its query set:** a `literature_fetch.QuerySet` of the Challenge's domain
  searches;
- **its arXiv categories:** what the free pre-filter keeps;
- **its cues:** primary-domain, secondary-domain and method phrases, matched
  as whole phrases in lower-case text, as the miner edition's focus rule
  does (`miner.focus`).

**Extraction is Challenge-neutral.** Cards are made with the miner edition's
Challenge-neutral Reader prompt (`miner.hunt.READER_PROMPT`), card schema v2,
in one shared store (`backfill-v2/cards`), since a neutral card serves every
Challenge. Each Challenge extracts only the records its own query set
retrieved and its free pre-filter keeps (`triage`), so no paid call is spent
on an off-topic paper.

**Relevance is a deterministic grade, never the model's applicability text.**
`grade` scores a card's ranked fields (`miner.focus.RANKED_FIELDS`, which
leave out `applicability`):
- 3 for a primary domain, or 1 for a secondary one;
- 1 for a surrogate or learning method;
- 1 when the card says code is available.

The grade thresholds are the focus rule's (`GRADE_THRESHOLDS`): a score of 5
or more is grade 3, 3 or more is grade 2, 1 or more is grade 1. A Challenge's
snapshot (schema v3) keeps its cards of grade 1 or more, best first, and
records the ranking rule's digest. A session offered it lists cards in that
order and records the ranking digest and its unchecked fraction.

DEVELOPMENT literature: a card's claims are its paper's, never Carbon's.
"""

from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path

from carbon.development_session.profile import canonical, digest

from .literature_fetch import Query, QuerySet
from .miner import focus

PROFILE_DIR = Path(__file__).with_name("literature_profiles")
PROFILE_SCHEMA = "carbon.graphite.literature-profile.v1"
REGISTRY_SCHEMA = "carbon.graphite.literature-profile-registry.v1"
RANK_RULE = "graphite-internal-focus.v1"
#: The raw score's parts (see the module notes); the grade thresholds are the
#: miner focus rule's.
SCORES = {"primary_domain": 3, "secondary_domain": 1, "method": 1, "code": 1}
#: Method cues every profile shares: the focus rule's surrogate and broad
#: learning cues.
METHOD_CUES = tuple(sorted(set(focus.SURROGATE_CUES) | set(focus.BROAD_ML_CUES)))
_KEYS = {
    "schema",
    "version",
    "challenge_id",
    "query_set",
    "categories",
    "primary_cues",
    "secondary_cues",
    "authority",
}


class LiteratureProfileRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@functools.lru_cache(maxsize=4096)
def _cue(cue):
    return re.compile(r"(?<![a-z0-9])" + re.escape(cue) + r"(?![a-z0-9])")


def _named(text, cues):
    return sorted(cue for cue in cues if cue in text and _cue(cue).search(text))


def _lower(value):
    return value.lower() if type(value) is str else ""


@dataclass(frozen=True)
class LiteratureProfile:
    version: str
    challenge_id: str
    query_set: QuerySet
    categories: tuple
    primary_cues: tuple
    secondary_cues: tuple
    digest: str

    @staticmethod
    def from_document(document, pinned):
        def bad(why):
            raise LiteratureProfileRefused("literature_profile_malformed:" + why)

        if type(document) is not dict or set(document) != _KEYS:
            bad("keys")
        if document["schema"] != PROFILE_SCHEMA:
            bad("schema")
        for name in ("version", "challenge_id", "authority"):
            if type(document[name]) is not str or not document[name]:
                bad(name)
        for name in ("categories", "primary_cues", "secondary_cues"):
            values = document[name]
            if (
                type(values) is not list
                or not values
                or not all(type(v) is str and v and v == v.strip() for v in values)
                or len(set(values)) != len(values)
            ):
                bad(name)
        for name in ("primary_cues", "secondary_cues"):
            if any(cue != cue.lower() for cue in document[name]):
                bad(name + "_not_lower_case")
        if set(document["primary_cues"]) & set(document["secondary_cues"]):
            bad("cues_overlap")
        queries = document["query_set"]
        if (
            type(queries) is not dict
            or set(queries) != {"version", "queries"}
            or type(queries["queries"]) is not list
        ):
            bad("query_set")
        try:
            query_set = QuerySet(
                version=queries["version"],
                queries=tuple(
                    Query(q["query_id"], q["search_query"], q["purpose"])
                    for q in queries["queries"]
                ),
            )
        except (KeyError, TypeError, ValueError):
            bad("query_set")
        from .literature_fetch import QUERY_SET

        if query_set.version == QUERY_SET.version:
            # Battery's query set is v1's alone, unchanged.
            bad("query_set_is_battery's")
        return LiteratureProfile(
            version=document["version"],
            challenge_id=document["challenge_id"],
            query_set=query_set,
            categories=tuple(document["categories"]),
            primary_cues=tuple(document["primary_cues"]),
            secondary_cues=tuple(document["secondary_cues"]),
            digest=pinned,
        )

    def ranking_rule(self):
        """Everything a grade depends on, as data, and its digest."""
        document = {
            "rule": RANK_RULE,
            "profile_digest": self.digest,
            "ranked_fields": list(focus.RANKED_FIELDS),
            "scores": dict(SCORES),
            "grade_thresholds": [list(pair) for pair in focus.GRADE_THRESHOLDS],
            "method_cues": list(METHOD_CUES),
            "minimum_grade": 1,
        }
        return {**document, "digest": digest(canonical(document))}

    def triage(self, record):
        """`(keep, reasons)` for an arXiv record before any paid call: an
        allowed category, and a primary domain, or a secondary domain and a
        surrogate cue, or two method cues of which one is a surrogate cue."""
        categories = record.get("categories") if type(record) is dict else None
        if type(categories) is not list or not set(categories) & set(self.categories):
            return False, ["category outside the profile"]
        text = _lower(record.get("title")) + " | " + _lower(record.get("abstract"))
        primary = _named(text, self.primary_cues)
        secondary = _named(text, self.secondary_cues)
        surrogate = _named(text, focus.TRIAGE_SURROGATE_CUES)
        methods = _named(text, METHOD_CUES + tuple(focus.TRIAGE_SURROGATE_CUES))
        if primary:
            return True, ["primary domain: " + ", ".join(primary[:3])]
        if secondary and surrogate:
            return True, ["secondary domain and a surrogate cue"]
        if surrogate and len(set(methods)) >= 2:
            return True, ["two method cues, one a surrogate cue"]
        return False, ["no domain cue and too few method cues"]

    def grade(self, card):
        """`(grade 0-3, reasons)` for an index card under this profile."""
        text = " | ".join(_lower(card.get(name)) for name in focus.RANKED_FIELDS)
        primary = _named(text, self.primary_cues)
        secondary = _named(text, self.secondary_cues)
        methods = _named(text, METHOD_CUES)
        domain = SCORES["secondary_domain"] if secondary else 0
        score = SCORES["primary_domain"] if primary else domain
        score += SCORES["method"] if methods else 0
        score += SCORES["code"] if card.get("code_available") is True else 0
        grade = next((g for floor, g in focus.GRADE_THRESHOLDS if score >= floor), 0)
        reasons = [
            f"domain: {', '.join((primary or secondary)[:3]) or 'none'}",
            f"method: {', '.join(methods[:3]) or 'none'}",
        ]
        return grade, reasons


def _registry(directory):
    try:
        registry = json.loads((Path(directory) / "registry.json").read_text())
    except (OSError, ValueError):
        raise LiteratureProfileRefused(
            "literature_profile_registry_unreadable"
        ) from None
    if (
        type(registry) is not dict
        or registry.get("schema") != REGISTRY_SCHEMA
        or type(registry.get("profiles")) is not dict
    ):
        raise LiteratureProfileRefused("literature_profile_registry_malformed")
    return registry


def load_profiles(directory=None):
    """Every registered profile, by Challenge; each checked against its pin."""
    directory = PROFILE_DIR if directory is None else Path(directory)
    profiles = {}
    for challenge, pinned in _registry(directory)["profiles"].items():
        try:
            document = json.loads((directory / f"{challenge}.json").read_text())
        except (OSError, ValueError):
            raise LiteratureProfileRefused(
                "literature_profile_unreadable:" + challenge
            ) from None
        if digest(canonical(document)) != pinned:
            raise LiteratureProfileRefused("literature_profile_altered:" + challenge)
        profile = LiteratureProfile.from_document(document, pinned)
        if profile.challenge_id != challenge:
            raise LiteratureProfileRefused("literature_profile_names_another_challenge")
        profiles[challenge] = profile
    return profiles


def profile_for(challenge_id, directory=None):
    profiles = load_profiles(directory)
    if challenge_id not in profiles:
        raise LiteratureProfileRefused("literature_profile_not_registered")
    return profiles[challenge_id]


def retrieved_by(raw, query_set):
    """The record addresses `query_set` retrieved, in first-retrieval order."""
    seen = []
    for entry in raw.retrievals():
        if entry.get("query_set_digest") != query_set.digest:
            continue
        for address in entry.get("record_digests") or ():
            if address not in seen:
                seen.append(address)
    return seen


__all__ = [
    "METHOD_CUES",
    "PROFILE_DIR",
    "RANK_RULE",
    "SCORES",
    "LiteratureProfile",
    "LiteratureProfileRefused",
    "load_profiles",
    "profile_for",
    "retrieved_by",
]
