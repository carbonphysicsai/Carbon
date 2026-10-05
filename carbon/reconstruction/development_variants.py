"""Development-only construction-contract variants (OWNER-GRAPHITE-TEST-WAVE-03 §1).

A level above a Challenge's miner-facing contract may be served to Carbon's own
registered Graphite campaigns (the Constructor and the Attacker) through a
development-only contract variant. This module is that mechanism. Engineering
choices are recorded in GRAPHITE-DEV-VARIANTS-01; the owner's answers on what a
variant may widen are OWNER-GRAPHITE-DEV-LEVELS-01.

**What a variant is.** A `DevContractVariant` is a registered, versioned
policy, in the pattern of `carbon.battery.exam.RULES` and of Graphite's
registered attribution policies (`attribution_policies/*.json` plus a
`registry.json` that pins each version's digest). Its document
(`carbon.construction-development-variant.v1`) names:
- the Challenge and the level (1-3);
- the base: the miner-facing contract's digest and the expansion record that
  pins it;
- the widened capabilities, each with its surface and its bounds;
- the Test Lead's review, and that it runs no participant code.

Its own digest is the sha256 of the document's canonical JSON. The registry
(`development_variant_policies/registry.json`) pins every version's digest
and names the variant each (challenge, level) currently runs under
(`DEV_VARIANTS`). A document whose digest is not the pinned one is refused.

**Where it lives.** Outside `capability_registry.CONTRACTS`, so no
miner-facing door resolves it. Every miner-facing door refuses a variant
digest or name by the typed code `development_variant_not_served`, reading
only the registry's data (`capability_registry.is_development_variant`). No
miner surface, the validator or the intake imports this module
(`tests/invariants/test_development_variants_unreachable.py`).

**The owner's bounds** (OWNER-GRAPHITE-DEV-LEVELS-01):
- F1: a variant may widen to a surface Carbon drafts, reviewed by the Test
  Lead and recorded here with its bounds. No technical-owner acceptance is
  needed for internal use; opening any surface to miners still needs it.
- F2: Level 3 is a declarative menu only: every widened surface is a fixed
  `choice` menu, as data. No level runs participant code
  (`participant_code` is always false), and Levels 4-5 are refused until the
  security owner accepts isolation.

**The climb procedure still applies.** A variant is used only once a
development expansion record pins it (`expansions/<token>/dev/NNNN.json`,
`record_development`), and it compiles only where Carbon's reconstruction of
every widened capability is registered (`RECONSTRUCTIONS`). This module ships
the mechanism with an empty registry; real Level 1-3 surfaces and their
reconstructions come in later work after the Test Lead's review.

**What it is not.** Not a construction contract, not an admission, not a
qualification and not a miner opening. A level tested internally is never
opened to miners to gather acceptance data.

Pure data and the standard library at import.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction import capability_registry as _registry
from carbon.reconstruction import expansion_record
from carbon.reconstruction.capability_registry import (
    CONTRACTS,
    Dimension,
    Status,
    Surface,
    catalog_surfaces,
    contract,
)

VARIANT_SCHEMA = "carbon.construction-development-variant.v1"
REGISTRY_SCHEMA = _registry.DEVELOPMENT_VARIANT_REGISTRY_SCHEMA
DEV_RECORD_SCHEMA = "carbon.construction-development-expansion-record.v1"
SCOPE = "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
AUTHORITY = (
    "OWNER-GRAPHITE-TEST-WAVE-03 section 1; OWNER-GRAPHITE-DEV-LEVELS-01; "
    "engineering choices GRAPHITE-DEV-VARIANTS-01"
)
#: A variant reviewed by the Test Lead and registered for internal use.
REGISTERED = "REGISTERED_DEVELOPMENT_POLICY"
#: A test fixture. Never loaded from the shipped registry.
FIXTURE = "FIXTURE_NOT_PRODUCTION"
STATUSES = (REGISTERED, FIXTURE)
#: The levels a variant may serve. Level 0 is the miner-facing contract
#: itself; Levels 4-5 run participant code, which waits for the security
#: owner's isolation acceptance (OWNER-GRAPHITE-DEV-LEVELS-01 F2).
LEVELS = (1, 2, 3)
#: Level 3 is a declarative menu only (F2): every widened surface a `choice`.
MENU_ONLY_LEVEL = 3
#: Development records live in this subfolder of a Challenge's expansion
#: records; `expansion_record.records` reads only 4-digit files beside it.
DEV_FOLDER = "dev"
#: Where development records are kept (the Challenge folders of the expansion
#: records). Tests point this at a temporary directory.
DEV_ROOT = expansion_record.ROOT
#: The registry shipped with the code: no fixture variant is ever loaded from it.
SHIPPED_DIR = _registry.DEVELOPMENT_VARIANT_DIR

UNREGISTERED = "development_variant_unregistered"
NOT_SERVED = _registry.DEVELOPMENT_VARIANT_NOT_SERVED
BASE_STALE = "development_variant_base_stale"
UNRECORDED = "development_variant_unrecorded"
MALFORMED = "development_variant_malformed"
ALTERED = "development_variant_altered"
LEVEL_INVALID = "development_variant_level_invalid"
NEEDS_ISOLATION = "development_variant_level_requires_isolation"
PARTICIPANT_CODE = "development_variant_participant_code_refused"
MENU_ONLY = "development_variant_level3_is_a_declarative_menu"
WIDENS_NOTHING = "development_variant_widens_nothing"
FIXTURE_SHIPPED = "development_variant_fixture_in_shipped_registry"
RECONSTRUCTION_MISSING = "development_reconstruction_missing"
WRONG_CHALLENGE = "development_variant_wrong_challenge"
PARAMETER_REFUSED = "development_parameter_refused"

_KEYS = frozenset(
    {
        "schema",
        "version",
        "challenge",
        "level",
        "scope",
        "status",
        "authority",
        "review",
        "base_contract",
        "participant_code",
        "widened",
    }
)
_WIDENED_KEYS = frozenset({"id", "summary", "surface", "applies_to", "bounds"})
_VERSION = re.compile(r"[a-z0-9][a-z0-9.-]{0,95}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NAME = re.compile(r"[0-9]{4}\.json\Z")
_PLACEHOLDERS = {"", "HUMAN_INPUT", "TODO"}


class VariantRefused(ValueError):
    """A development variant, or a use of one, refused; the code names why."""

    def __init__(self, code, detail="", issues=()):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code, self.issues = code, tuple(issues)


def digest_of(document):
    """A variant's digest: the sha256 of its document's canonical JSON."""
    return expansion_record.digest_of(document)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value):
    return type(value) is str and value.strip() not in _PLACEHOLDERS


@dataclass(frozen=True)
class Widened:
    """One capability a variant widens: its surface and its bounds."""

    capability_id: str
    summary: str
    #: The catalog surface (group, kind, minimum or choices, maximum,
    #: default), or None where the bounds are not a catalog field.
    surface: Surface | None
    applies_to: tuple[str, ...] | None
    #: The bounds as stated in the document, canonical JSON.
    bounds_json: str

    @property
    def name(self):
        return self.capability_id.partition(".")[2]

    def within(self, value):
        """Whether `value` lies inside this capability's catalog surface. A
        capability with no catalog surface is checked by its reconstruction."""
        surface = self.surface
        if surface is None:
            return True
        if surface.kind == "bool":
            return type(value) is bool
        if surface.kind == "choice":
            return any(type(value) is type(c) and value == c for c in surface.low)
        if surface.kind == "uint":
            return type(value) is int and surface.low <= value <= surface.high
        return (
            type(value) in (int, float)
            and type(value) is not bool
            and math.isfinite(value)
            and surface.low <= value <= surface.high
        )


@dataclass(frozen=True)
class DevContractVariant:
    """One registered development-only contract variant, pinned by digest."""

    version: str
    challenge: str
    level: int
    status: str
    base_contract_digest: str
    base_record_sequence: int
    widened: tuple[Widened, ...]
    #: The full document, canonical JSON: what the digest pins.
    canonical_document: str

    schema = VARIANT_SCHEMA

    def document(self):
        return json.loads(self.canonical_document)

    @property
    def digest(self):
        return digest_of(self.document())

    def fields(self):
        """{field name: Widened}, the parameters this variant adds."""
        return {w.name: w for w in self.widened}

    def permissions(self):
        """The capability ids this variant adds to its base contract."""
        return tuple(w.capability_id for w in self.widened)

    @classmethod
    def from_document(cls, document):
        """The variant, or `VariantRefused` naming what is wrong. Checks the
        document's shape and the owner's bounds; not its base's freshness
        (`check_base`)."""
        if type(document) is not dict or set(document) != _KEYS:
            raise VariantRefused(MALFORMED, "exact variant keys required")
        if document["schema"] != VARIANT_SCHEMA:
            raise VariantRefused(MALFORMED, "schema")
        version = document["version"]
        if type(version) is not str or not _VERSION.fullmatch(version):
            raise VariantRefused(MALFORMED, "version")
        challenge = document["challenge"]
        if type(challenge) is not str or challenge not in CONTRACTS:
            raise VariantRefused(MALFORMED, "challenge has no construction contract")
        level = document["level"]
        if type(level) is not int:
            raise VariantRefused(LEVEL_INVALID, "level is an integer")
        if level > max(LEVELS):
            raise VariantRefused(NEEDS_ISOLATION, f"level {level}")
        if level not in LEVELS:
            raise VariantRefused(LEVEL_INVALID, f"level {level}")
        if document["scope"] != SCOPE:
            raise VariantRefused(MALFORMED, "scope")
        if document["status"] not in STATUSES:
            raise VariantRefused(MALFORMED, "status")
        if not _text(document["authority"]):
            raise VariantRefused(MALFORMED, "authority")
        review = document["review"]
        if (
            type(review) is not dict
            or set(review) != {"reviewer", "record"}
            or not all(_text(review[k]) for k in review)
        ):
            raise VariantRefused(MALFORMED, "review names its reviewer and record")
        if document["participant_code"] is not False:
            raise VariantRefused(PARTICIPANT_CODE)
        base = document["base_contract"]
        if (
            type(base) is not dict
            or set(base) != {"digest", "record_sequence"}
            or type(base["digest"]) is not str
            or not _DIGEST.fullmatch(base["digest"])
            or type(base["record_sequence"]) is not int
            or base["record_sequence"] < 0
        ):
            raise VariantRefused(MALFORMED, "base_contract")
        widened = _widened(document["widened"], challenge, level)
        try:
            canonical = _canonical(document)
        except ValueError:
            raise VariantRefused(MALFORMED, "non-finite value") from None
        return cls(
            version=version,
            challenge=challenge,
            level=level,
            status=document["status"],
            base_contract_digest=base["digest"],
            base_record_sequence=base["record_sequence"],
            widened=widened,
            canonical_document=canonical,
        )


def _surface(value, label):
    """A widened entry's surface, checked as a bounded catalog field."""
    if value is None:
        return None
    if type(value) is not list or len(value) != 5:
        raise VariantRefused(
            MALFORMED, label + ": surface is [group, kind, low, high, default]"
        )
    group, kind, low, high, default = value
    try:
        surface = Surface(
            group, kind, tuple(low) if type(low) is list else low, high, default
        )
    except (TypeError, ValueError) as error:
        raise VariantRefused(MALFORMED, f"{label}: {error}") from None
    bounded = False
    if kind == "bool":
        bounded = low is None and high is None and type(default) is bool
    elif kind == "choice":
        choices = surface.low
        bounded = (
            type(choices) is tuple
            and len(choices) >= 1
            and all(type(c) in (str, int, bool) for c in choices)
            and len({(type(c), c) for c in choices}) == len(choices)
            and high is None
            and any(type(default) is type(c) and default == c for c in choices)
        )
    elif kind == "uint":
        bounded = (
            all(type(v) is int for v in (low, high, default))
            and 0 <= low <= default <= high
        )
    else:  # float
        bounded = (
            all(
                type(v) in (int, float) and type(v) is not bool and math.isfinite(v)
                for v in (low, high, default)
            )
            and low <= default <= high
        )
    if not bounded:
        raise VariantRefused(MALFORMED, label + ": surface is not bounded")
    return surface


def _widened(entries, challenge, level):
    if type(entries) is not list or not entries:
        raise VariantRefused(WIDENS_NOTHING, "widened is a non-empty list")
    base = contract(challenge)
    by_id = {c.capability_id: c for c in base.capabilities}
    realized = {
        i
        for c in base.capabilities
        if c.status is Status.REBUILDABLE_DEVELOPMENT
        for i in c.realizes
    }
    families = {
        c.selector
        for c in base.capabilities
        if c.dimension is Dimension.MODEL_FAMILY
        and c.status is Status.REBUILDABLE_DEVELOPMENT
    }
    taken = set(catalog_surfaces(challenge))
    found, ids, names = [], set(), set()
    for entry in entries:
        if type(entry) is not dict or set(entry) != _WIDENED_KEYS:
            raise VariantRefused(MALFORMED, "exact widened keys required")
        capability_id = entry["id"]
        prefix, _, name = (
            capability_id.partition(".") if type(capability_id) is str else ("", "", "")
        )
        if prefix not in {d.value for d in Dimension} or not re.fullmatch(
            r"[a-z][a-z0-9_]*", name
        ):
            raise VariantRefused(MALFORMED, "a widened id is <dimension>.<name>")
        known = by_id.get(capability_id)
        if (
            known is not None and known.status is Status.REBUILDABLE_DEVELOPMENT
        ) or capability_id in realized:
            raise VariantRefused(
                WIDENS_NOTHING, capability_id + " is already rebuildable"
            )
        if name in taken:
            raise VariantRefused(MALFORMED, name + " is already a contract field")
        if capability_id in ids or name in names:
            raise VariantRefused(MALFORMED, "duplicate widened capability " + name)
        ids.add(capability_id)
        names.add(name)
        if not _text(entry["summary"]):
            raise VariantRefused(MALFORMED, capability_id + ": summary")
        surface = _surface(entry["surface"], capability_id)
        if level == MENU_ONLY_LEVEL and (surface is None or surface.kind != "choice"):
            raise VariantRefused(MENU_ONLY, capability_id)
        applies_to = entry["applies_to"]
        if applies_to is not None:
            if (
                type(applies_to) is not list
                or not applies_to
                or not set(applies_to) <= families
            ):
                raise VariantRefused(
                    MALFORMED, capability_id + ": applies only to rebuildable families"
                )
            applies_to = tuple(applies_to)
        bounds = entry["bounds"]
        if type(bounds) is not dict or not bounds:
            raise VariantRefused(MALFORMED, capability_id + ": bounds are stated")
        try:
            bounds_json = _canonical(bounds)
        except ValueError:
            raise VariantRefused(MALFORMED, capability_id + ": finite bounds") from None
        found.append(
            Widened(
                capability_id=capability_id,
                summary=entry["summary"],
                surface=surface,
                applies_to=applies_to,
                bounds_json=bounds_json,
            )
        )
    return tuple(found)


# -- the registry ---------------------------------------------------------------------
@dataclass(frozen=True)
class VariantRegistry:
    """Every registered version, by name and by digest, and the variant each
    (challenge, level) runs under."""

    by_version: dict
    by_digest: dict
    current: dict


def load(directory=None):
    """The registry at `directory` (default: the one the capability registry
    reads), every document verified against its pinned digest."""
    directory = Path(
        _registry.DEVELOPMENT_VARIANT_DIR if directory is None else directory
    )
    try:
        registry = _registry.development_variant_registry(directory)
    except RuntimeError as error:
        raise VariantRefused(MALFORMED, str(error)) from None
    shipped = directory.resolve() == Path(SHIPPED_DIR).resolve()
    by_version, by_digest = {}, {}
    for version, pinned in registry["versions"].items():
        try:
            document = json.loads(
                (directory / f"{version}.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            raise VariantRefused(MALFORMED, "unreadable: " + version) from None
        if digest_of(document) != pinned:
            raise VariantRefused(ALTERED, version)
        variant = DevContractVariant.from_document(document)
        if variant.version != version:
            raise VariantRefused(MALFORMED, version + " names another version")
        if shipped and variant.status == FIXTURE:
            raise VariantRefused(FIXTURE_SHIPPED, version)
        by_version[version] = by_digest[pinned] = variant
    current = {}
    for entry in registry["current"]:
        variant = by_version[entry["version"]]
        key = (entry["challenge"], entry["level"])
        if key != (variant.challenge, variant.level):
            raise VariantRefused(MALFORMED, "current names another challenge or level")
        if key in current:
            raise VariantRefused(
                MALFORMED, "one current variant per challenge and level"
            )
        current[key] = variant
    return VariantRegistry(by_version, by_digest, current)


class _DevVariants(Mapping):
    """`DEV_VARIANTS[(challenge, level)]`: the current registered variant, read
    from the pinned registry at every lookup (so a re-pinned or altered
    document is refused where it is used)."""

    def __getitem__(self, key):
        return load().current[key]

    def __iter__(self):
        return iter(load().current)

    def __len__(self):
        return len(load().current)


DEV_VARIANTS = _DevVariants()


def check_base(variant):
    """The variant's base is the live miner-facing contract, pinned by that
    Challenge's newest expansion record; else `development_variant_base_stale`."""
    live = contract(variant.challenge)
    history = expansion_record.records(variant.challenge)
    newest = history[-1] if history else {}
    if not (
        live.digest == variant.base_contract_digest
        and newest.get("contract_digest") == variant.base_contract_digest
        and newest.get("sequence") == variant.base_record_sequence
    ):
        raise VariantRefused(BASE_STALE, f"{variant.challenge} level {variant.level}")
    return variant


def variant(challenge, level):
    """The current registered variant for (challenge, level), with a fresh base;
    else `development_variant_unregistered` (or `_base_stale`)."""
    found = load().current.get((challenge, level))
    if found is None:
        raise VariantRefused(UNREGISTERED, f"{challenge} level {level}")
    return check_base(found)


def registered(digest, challenge=None):
    """The current registered variant whose pinned digest is `digest` (and, when
    named, whose Challenge is `challenge`), with a fresh base; else
    `development_variant_unregistered`."""
    for found in load().current.values():
        if found.digest == digest and challenge in (None, found.challenge):
            return check_base(found)
    raise VariantRefused(UNREGISTERED, str(digest)[:80])


# -- development expansion records ----------------------------------------------------
def _dev_folder(challenge, root=None):
    return Path(DEV_ROOT if root is None else root) / challenge / DEV_FOLDER


def dev_records(challenge, root=None):
    """A Challenge's development records, oldest first."""
    folder = _dev_folder(challenge, root)
    if not folder.is_dir():
        return []
    names = sorted(p.name for p in folder.iterdir() if _NAME.fullmatch(p.name))
    return [json.loads((folder / n).read_text(encoding="utf-8")) for n in names]


def newest_record(found, root=None):
    """The newest development record that pins `found`, or None."""
    for record in reversed(dev_records(found.challenge, root)):
        if record.get("level") == found.level:
            return record if record.get("variant_digest") == found.digest else None
    return None


def record_development(challenge, level, what, *, root=None, today=None):
    """Append the current variant of (challenge, level) as the Challenge's next
    development record, bound to the variant's digest and its base contract
    record. Refused unless the variant is registered with a fresh base."""
    found = variant(challenge, level)
    if newest_record(found, root) is not None:
        raise ValueError("nothing to record: this variant is already recorded")
    if type(what) is not str or len(what.strip()) < 20:
        raise ValueError("say what this development variant widens, and why")
    history = dev_records(challenge, root)
    entry = {
        "schema": DEV_RECORD_SCHEMA,
        "authority": AUTHORITY,
        "scope": SCOPE,
        "challenge": challenge,
        "sequence": len(history),
        "recorded_on": (
            today or datetime.datetime.now(datetime.UTC).date()
        ).isoformat(),
        "level": found.level,
        "variant_version": found.version,
        "variant_digest": found.digest,
        "variant_document": found.document(),
        "base_contract": {
            "sequence": found.base_record_sequence,
            "contract_digest": found.base_contract_digest,
        },
        "what": what.strip(),
    }
    folder = _dev_folder(challenge, root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{entry['sequence']:04d}.json"
    path.write_text(
        json.dumps(entry, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def dev_problems(root=None):
    """Every way the stored development records are not a well-formed,
    append-only trail bound to real base records."""
    found = []
    for token in CONTRACTS:
        base = {
            r["sequence"]: r["contract_digest"] for r in expansion_record.records(token)
        }
        history = dev_records(token, root)
        for index, record in enumerate(history):
            label = f"{token}/{DEV_FOLDER}/{index:04d}.json"
            if record.get("schema") != DEV_RECORD_SCHEMA:
                found.append(label + ": wrong schema")
                continue
            if record.get("sequence") != index:
                found.append(label + ": sequence is not contiguous from 0")
            if record.get("challenge") != token or record.get("scope") != SCOPE:
                found.append(label + ": names another challenge or scope")
            document = record.get("variant_document")
            if digest_of(document) != record.get("variant_digest"):
                found.append(label + ": digest does not match its variant")
            try:
                variant_ = DevContractVariant.from_document(document)
            except VariantRefused as refused:
                found.append(label + ": " + refused.code)
            else:
                pinned = record.get("base_contract") or {}
                if (
                    variant_.challenge != token
                    or variant_.level != record.get("level")
                    or pinned
                    != {
                        "sequence": variant_.base_record_sequence,
                        "contract_digest": variant_.base_contract_digest,
                    }
                    or base.get(pinned.get("sequence")) != pinned.get("contract_digest")
                ):
                    found.append(label + ": not bound to a recorded base contract")
            if type(record.get("what")) is not str or len(record["what"].strip()) < 20:
                found.append(label + ": says too little about what widened")
            try:
                datetime.date.fromisoformat(record.get("recorded_on", ""))
            except (TypeError, ValueError):
                found.append(label + ": recorded_on is not a date")
            if index and record.get("recorded_on", "") < history[index - 1].get(
                "recorded_on", ""
            ):
                found.append(label + ": dated before the record it follows")
    return found


def dev_unrecorded(root=None):
    """{(challenge, level): why} for every current variant no record pins."""
    return {
        key: "no development record pins the current variant"
        for key, found in load().current.items()
        if newest_record(found, root) is None
    }


def recorded_variant(found, root=None):
    """What a development run constructs under: the base contract record and
    the variant's own record, only if the newest development record for its
    level pins it."""
    check_base(found)
    record = newest_record(found, root)
    if record is None:
        raise VariantRefused(UNRECORDED, f"{found.challenge} level {found.level}")
    return {
        "challenge": found.challenge,
        "level": found.level,
        "contract_digest": found.base_contract_digest,
        "record_sequence": found.base_record_sequence,
        "development_variant": found.digest,
        "development_record_sequence": record["sequence"],
        "scope": SCOPE,
    }


# -- the development-only compile path ------------------------------------------------
#: Carbon's reconstruction of each widened capability, keyed by
#: (challenge, capability id): `(value, admitted) -> JSON record` of what Carbon
#: built for that value from the compiled base submission. A variant compiles
#: only when every capability it widens has one (the reconstruction rule,
#: OWNER-GRAPHITE-02). Empty until a real surface ships with its rebuild.
RECONSTRUCTIONS = {}


@dataclass(frozen=True)
class CompiledDevelopment:
    """One strategy compiled under a development variant: the base compiled
    exactly as `compile_submission` compiles it, plus each widened value and
    Carbon's reconstruction of it, bound to the variant's digest."""

    challenge: str
    contract_digest: str
    compiled: object
    construction: object
    variant_digest: str
    level: int
    widened: dict
    reconstruction: dict

    @property
    def development(self):
        """The binding a built record carries beside the base fields."""
        return {
            "variant_digest": self.variant_digest,
            "level": self.level,
            "widened_digest": digest_of(
                {"widened": self.widened, "reconstruction": self.reconstruction}
            ),
        }


def compile_development(strategy, variant_):
    """Compile `strategy` under the registered development variant `variant_`.

    Development only: Graphite's experiment and pod phase call it when a
    development level is selected; Level 0 and every miner-facing door use
    `challenge_contracts.compile_submission`, which refuses a variant digest.
    The widened parameters are checked against the variant's bounds; the rest
    compiles through `compile_submission` against the variant's base contract.
    Raises `VariantRefused`, or the base path's `SubmissionRefused` and
    `RecipeRejected`."""
    from carbon.reconstruction.challenge_contracts import compile_submission

    if type(variant_) is not DevContractVariant:
        raise TypeError("a DevContractVariant is required")
    if registered(variant_.digest, variant_.challenge) != variant_:
        raise VariantRefused(UNREGISTERED, variant_.version)
    if type(strategy) is not dict:
        raise VariantRefused(PARAMETER_REFUSED, "strategy is an object")
    if strategy.get("challenge_id") != variant_.challenge:
        raise VariantRefused(WRONG_CHALLENGE)
    missing = [
        w.capability_id
        for w in variant_.widened
        if (variant_.challenge, w.capability_id) not in RECONSTRUCTIONS
    ]
    if missing:
        raise VariantRefused(RECONSTRUCTION_MISSING, ", ".join(missing))
    fields = variant_.fields()
    parameters = strategy.get("parameters")
    base, values = dict(strategy), {}
    if type(parameters) is dict:
        values = {k: v for k, v in parameters.items() if k in fields}
        base["parameters"] = {k: v for k, v in parameters.items() if k not in fields}
    issues = []
    backbone = strategy.get("backbone")
    for name in sorted(values):
        widened = fields[name]
        path = "/parameters/" + name
        if not widened.within(values[name]):
            issues.append(("development.out_of_bounds", path))
        elif widened.applies_to is not None and backbone not in widened.applies_to:
            issues.append(("development.not_applicable", path))
    if issues:
        raise VariantRefused(PARAMETER_REFUSED, issues=issues)
    admitted = compile_submission(base, contract_digest=variant_.base_contract_digest)
    reconstruction = {}
    for name in sorted(values):
        widened = fields[name]
        build = RECONSTRUCTIONS[(variant_.challenge, widened.capability_id)]
        reconstruction[widened.capability_id] = build(values[name], admitted)
    try:
        _canonical(values)
        _canonical(reconstruction)
    except (TypeError, ValueError):
        raise VariantRefused(PARAMETER_REFUSED, "values are plain JSON") from None
    return CompiledDevelopment(
        challenge=variant_.challenge,
        contract_digest=admitted.contract_digest,
        compiled=admitted.compiled,
        construction=admitted.construction,
        variant_digest=variant_.digest,
        level=variant_.level,
        widened=values,
        reconstruction=reconstruction,
    )


def built_record(strategy, variant_digest, seed, root=".", scoring=None):
    """What Carbon builds for `strategy` under a registered variant (by its
    digest): the Challenge's `ChallengeScoring.built_from` over
    `compile_development`. Used on the pod and, for the rebuild check, on
    Carbon's host."""
    from carbon.challenge_validator import scoring as challenge_scoring

    found = registered(variant_digest)
    scoring = (
        challenge_scoring.scoring_for(found.challenge) if scoring is None else scoring
    )
    return scoring.built_from(compile_development(strategy, found), seed, root)


def admit(scoring, strategy, seed, root, variant_):
    """The development counterpart of `challenge_scoring.admit`: what Carbon
    would build for `strategy` under `variant_`, with the base record's
    sequence and the variant's binding. Raises `Unrebuildable` (never scored)
    or `NotServed`."""
    from carbon.challenge_validator import scoring as challenge_scoring

    if type(strategy) is not dict:
        raise challenge_scoring.Unrebuildable("strategy_not_an_object")
    if strategy.get("challenge_id") != scoring.challenge_id:
        raise challenge_scoring.Unrebuildable(scoring.wrong_challenge_code)
    try:
        recorded = recorded_variant(variant_)
        built, _files, _program = scoring.built_from(
            compile_development(strategy, variant_), seed, root
        )
    except VariantRefused as refused:
        raise challenge_scoring.Unrebuildable(refused.code, refused.issues) from None
    except Exception as error:
        refused = scoring.refusal(error)
        if refused is None:
            raise
        code, issues = refused
        raise challenge_scoring.Unrebuildable(code, issues) from None
    backend = scoring.backend(built)
    if backend not in scoring.served_backends:
        raise challenge_scoring.NotServed("backend_not_served:" + str(backend))
    return {
        **built,
        "record_sequence": recorded["record_sequence"],
        "development_record_sequence": recorded["development_record_sequence"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("record", help="record the current variant of a level")
    add.add_argument("--challenge", required=True, choices=sorted(CONTRACTS))
    add.add_argument("--level", required=True, type=int, choices=LEVELS)
    add.add_argument("--what", required=True)
    sub.add_parser("check", help="list unrecorded variants and malformed records")
    args = parser.parse_args(argv)
    if args.command == "record":
        print(record_development(args.challenge, args.level, args.what))
        return 0
    issues = [
        f"{c} level {lvl}: {why}" for (c, lvl), why in dev_unrecorded().items()
    ] + dev_problems()
    print("\n".join(issues) if issues else "every development variant is recorded")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
