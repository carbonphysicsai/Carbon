"""Challenge-neutral sealed confirmation sets (VALIDATOR-03).

A confirmation set is a fresh, independent batch of private cases for one
Challenge, generated from an operator-held root and committed before any use.
It is never pooled, never shipped to a pod or rented compute, and is solved and
predicted on the operator host only. It generalises battery's EV5 pattern
(`carbon.battery.value.ev5.seal_confirmation`) to every Challenge.

**The registry.** Each confirmation role is one registered document in
`confirmation_sets/`, pinned by digest in `confirmation_sets/registry.json`
(the pattern of `graphite/attribution_policies`). A document fixes the
Challenge, the size (`cases`, `hidden_duplicates`), the sampling law, the
strata, the custody, and the priors the set must not repeat. Size, law and
strata are scientific values. A document leaves each `null` until a recorded
owner decision sets it and lists it under `authority.human_input`, and every
seal refuses until all are set (fail closed).

**Strata.** A stratum is a region of the inputs (lower bounds, `>=`) with a
minimum fraction of the fresh cases. Its quota, `ceil(cases * fraction)`, is
drawn from the population restricted to the region, and the rest from the
whole population, so at least that fraction lies in the region. Strata are
reported separately; `[]` means the set has none. A change is a new document version, never a code
edit. Every registered role must be reserved in
`interface.RESERVED_SEED_ROLES`, so no pool path can ever prepare it.

**Sealing** (`seal`) runs on the operator host, under the custody's writer
lock:
1. generate the batch from the root (deterministic in root, role, size, law);
2. refuse the role if the custody already holds a different batch under it
   (case-insensitive: `interface.canonical_role`);
3. check that no case repeats a prior case: every published case of the
   Challenge, every pooled batch, every batch already sealed in the custody
   (regenerated from the root and checked against its committed fingerprint,
   so EV5's set is compared without ever being stored), and each registered
   private pool the operator supplies;
4. commit the fingerprint, then print only the public commitment.

A rerun is idempotent: it recalls the same batch and commitment.

**Custody.** Battery seals into its validator deployment's seed journal
(`daemon.seal_batch`), as EV5 did. A Challenge without a deployment keeps an
owner-only custody directory (`init`): a 32-byte root and an append-only
journal of public commitments.

Nothing here prints, stores or returns a private case, input, seed or root.
Sealing itself is an operator action: this module is the tooling, and the
owner orders each seal. DEVELOPMENT only: no score, weight or reward.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import random
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from .interface import canonical_role, role_reserved

REPOSITORY = Path(__file__).resolve().parents[2]
SET_DIR = Path(__file__).with_name("confirmation_sets")
SET_SCHEMA = "carbon.challenge-validator.confirmation-set.v1"
REGISTRY_SCHEMA = "carbon.challenge-validator.confirmation-registry.v1"
BATCH_SCHEMA = "carbon.challenge-validator.confirmation-batch.v1"
JOURNAL_SCHEMA = "carbon.challenge-validator.confirmation-journal.v1"
MANIFEST_SCHEMA = "carbon.challenge-validator.confirmation-manifest.v1"
ROOT_DOMAIN = b"carbon.challenge-validator.confirmation-root.v1"
#: The scientific values a document may leave unset (`null`) for the owner.
HUMAN_INPUT_FIELDS = ("cases", "hidden_duplicates", "sampling_law", "strata")
CUSTODIES = frozenset({"battery_deployment", "confirmation_journal"})
FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
_DOCUMENT_KEYS = {
    "schema",
    "role",
    "challenge_id",
    "sealable",
    "cases",
    "hidden_duplicates",
    "sampling_law",
    "strata",
    "subgroups",
    "custody",
    "required_prior_roles",
    "required_private_priors",
    "authority",
}


class ConfirmationRefused(ValueError):
    """A typed refusal. Its code names no private case, input or root."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def _file_digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- the registry ---------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmationSet:
    """One registered confirmation role (its document, checked at load)."""

    role: str
    challenge_id: str
    sealable: bool
    cases: int | None
    hidden_duplicates: int | None
    sampling_law: dict | None
    strata: tuple | None
    subgroups: tuple
    custody: dict
    required_prior_roles: tuple
    required_private_priors: tuple
    authority: dict
    digest: str

    @staticmethod
    def from_document(document, pinned):
        def bad(why):
            raise ConfirmationRefused("confirmation_set_malformed:" + why)

        if type(document) is not dict or set(document) != _DOCUMENT_KEYS:
            bad("keys")
        if document["schema"] != SET_SCHEMA:
            bad("schema")
        role = document["role"]
        if type(role) is not str or canonical_role(role) != role or not role:
            bad("role")
        if not role_reserved(role):
            # A registered confirmation role is always reserved, so no pool
            # path can prepare it (interface.RESERVED_SEED_ROLES).
            raise ConfirmationRefused("confirmation_role_not_reserved:" + role)
        if (
            type(document["challenge_id"]) is not str
            or type(document["sealable"]) is not bool
        ):
            bad("challenge_or_sealable")
        for name in ("cases", "hidden_duplicates"):
            value = document[name]
            if value is not None and (type(value) is not int or value < 1):
                bad(name)
        law = document["sampling_law"]
        if law is not None and (
            type(law) is not dict
            or set(law) != {"id", "description"}
            or not all(type(v) is str and v for v in law.values())
        ):
            bad("sampling_law")
        strata = document["strata"]
        if strata is not None:
            if type(strata) is not list:
                bad("strata")
            for stratum in strata:
                _check_stratum(stratum, bad)
            ids = [stratum["id"] for stratum in strata]
            if len(set(ids)) != len(ids):
                bad("strata")
        custody = document["custody"]
        if (
            type(custody) is not dict
            or set(custody) != {"kind", "made_on", "solved_on"}
            or custody["kind"] not in CUSTODIES
            or not all(type(v) is str for v in custody.values())
        ):
            bad("custody")
        for name in ("subgroups", "required_prior_roles", "required_private_priors"):
            if type(document[name]) is not list or not all(
                type(v) is str and v for v in document[name]
            ):
                bad(name)
        authority = document["authority"]
        if (
            type(authority) is not dict
            or set(authority) != {"decisions", "human_input"}
            or type(authority["decisions"]) is not list
            or type(authority["human_input"]) is not list
        ):
            bad("authority")
        unset = sorted(f for f in HUMAN_INPUT_FIELDS if document[f] is None)
        if sorted(authority["human_input"]) != unset:
            # What is unset is exactly what the owner has still to decide.
            bad("human_input_does_not_match_unset_values")
        if not unset and not authority["decisions"]:
            bad("values_without_a_decision")
        if not unset and document["cases"] < sum(
            _quota(document["cases"], stratum) for stratum in strata
        ):
            bad("strata_exceed_cases")
        return ConfirmationSet(
            role=role,
            challenge_id=document["challenge_id"],
            sealable=document["sealable"],
            cases=document["cases"],
            hidden_duplicates=document["hidden_duplicates"],
            sampling_law=law,
            strata=None if strata is None else tuple(dict(s) for s in strata),
            subgroups=tuple(document["subgroups"]),
            custody=dict(custody),
            required_prior_roles=tuple(
                canonical_role(r) for r in document["required_prior_roles"]
            ),
            required_private_priors=tuple(document["required_private_priors"]),
            authority={k: list(v) for k, v in authority.items()},
            digest=pinned,
        )

    @property
    def human_input(self):
        return list(self.authority["human_input"])

    @property
    def batch_size(self):
        return self.cases + self.hidden_duplicates

    def require_ready(self):
        """Refused unless this role may be sealed now (fail closed)."""
        if not self.sealable:
            raise ConfirmationRefused("confirmation_set_not_sealable:" + self.role)
        if self.human_input:
            raise ConfirmationRefused(
                "confirmation_human_input_missing:" + ",".join(self.human_input)
            )

    def skeleton(self):
        """The public skeleton: no case, input, seed or root."""
        return {
            "role": self.role,
            "challenge_id": self.challenge_id,
            "sealable": self.sealable,
            "cases": self.cases,
            "hidden_duplicates": self.hidden_duplicates,
            "batch_size": None if self.human_input else self.batch_size,
            "sampling_law": self.sampling_law,
            "strata": None if self.strata is None else [dict(s) for s in self.strata],
            "subgroups": list(self.subgroups),
            "custody": dict(self.custody),
            "required_prior_roles": list(self.required_prior_roles),
            "required_private_priors": list(self.required_private_priors),
            "authority": {k: list(v) for k, v in self.authority.items()},
            "set_digest": self.digest,
        }


def _check_stratum(stratum, bad):
    if (
        type(stratum) is not dict
        or set(stratum) != {"id", "description", "lower_bounds", "min_fraction"}
        or type(stratum["id"]) is not str
        or not stratum["id"]
        or type(stratum["description"]) is not str
        or type(stratum["lower_bounds"]) is not dict
        or not stratum["lower_bounds"]
        or not all(
            type(name) is str and type(value) in (int, float)
            for name, value in stratum["lower_bounds"].items()
        )
    ):
        bad("stratum")
    fraction = stratum["min_fraction"]
    if (
        type(fraction) is not dict
        or set(fraction) != {"numerator", "denominator"}
        or not all(type(v) is int for v in fraction.values())
        or not 0 < fraction["numerator"] <= fraction["denominator"]
    ):
        bad("stratum_fraction")


def _quota(cases, stratum):
    """The fresh cases a stratum's region must receive: ceil(cases * f)."""
    fraction = stratum["min_fraction"]
    return -(-cases * fraction["numerator"] // fraction["denominator"])


def in_stratum(inputs, stratum):
    return all(inputs[name] >= low for name, low in stratum["lower_bounds"].items())


def _registry(directory):
    try:
        registry = json.loads((Path(directory) / "registry.json").read_text())
    except (OSError, ValueError):
        raise ConfirmationRefused("confirmation_registry_unreadable") from None
    if (
        type(registry) is not dict
        or registry.get("schema") != REGISTRY_SCHEMA
        or type(registry.get("sets")) is not dict
    ):
        raise ConfirmationRefused("confirmation_registry_malformed")
    return registry


def load_sets(directory=None):
    """Every registered confirmation set, by role. Refused if any document is
    missing, altered from its pinned digest, or breaks an invariant."""
    directory = SET_DIR if directory is None else Path(directory)
    registry = _registry(directory)
    sets = {}
    for role, pinned in registry["sets"].items():
        try:
            document = json.loads((directory / f"{role}.json").read_text())
        except (OSError, ValueError):
            raise ConfirmationRefused("confirmation_set_unreadable:" + role) from None
        if digest(document) != pinned:
            raise ConfirmationRefused("confirmation_set_altered:" + role)
        if type(document) is not dict or document.get("role") != role:
            raise ConfirmationRefused("confirmation_set_names_another_role:" + role)
        sets[role] = ConfirmationSet.from_document(document, pinned)
    for item in sets.values():
        for prior in item.required_prior_roles:
            if prior not in sets:
                raise ConfirmationRefused("confirmation_prior_not_registered:" + prior)
    return sets


def registry_digest(directory=None):
    return digest(_registry(SET_DIR if directory is None else directory))


def confirmation_set(role, directory=None):
    """The registered set for `role`, matched case-insensitively."""
    canonical = canonical_role(role)
    sets = load_sets(directory)
    if canonical not in sets:
        raise ConfirmationRefused("confirmation_role_not_registered")
    return sets[canonical]


# --- the neutral batch ----------------------------------------------------------------


@dataclass(frozen=True)
class SealedBatch:
    """A confirmation batch held in memory on the operator host only."""

    challenge_id: str
    role: str
    law: str
    cases: tuple  # ((case_id, ((name, value), ...)), ...)
    duplicates: tuple  # ((duplicate_id, original_id), ...)

    def __repr__(self):
        return f"SealedBatch({self.role}, {len(self.cases)} cases, <redacted>)"

    def document(self):
        return {
            "schema": BATCH_SCHEMA,
            "challenge": self.challenge_id,
            "role": self.role,
            "law": self.law,
            "cases": [{"case_id": c, "inputs": dict(x)} for c, x in self.cases],
            "duplicates": dict(self.duplicates),
        }

    @property
    def fingerprint(self):
        return digest(self.document())

    def inputs(self):
        return {case_id: dict(values) for case_id, values in self.cases}


def make_batch(root, source, item):
    """`item`'s batch from `root`: `cases` fresh draws under its law plus
    `hidden_duplicates` repeats, with opaque ids, in a root-derived order."""
    if type(root) is not ConfirmationRoot:
        raise TypeError("an operator-held ConfirmationRoot is required")
    law = item.sampling_law["id"]
    role = item.role
    key = hmac.new(root._bytes, b"case-ids/" + role.encode(), hashlib.sha256).digest()

    def generator(label):
        seed = hmac.new(key, label, hashlib.sha256).digest()[:8]
        return random.Random(int.from_bytes(seed, "big"))

    def opaque(label):
        tag = hmac.new(key, label.encode(), hashlib.sha256).hexdigest()[:16]
        return f"{role}-{tag}"

    drawn = []
    for stratum in item.strata:
        quota = _quota(item.cases, stratum)
        rng = generator(b"stratum/" + stratum["id"].encode() + b"/" + law.encode())
        drawn += _draw_stratum(source, rng, quota, law, stratum)
    rest = item.cases - len(drawn)
    drawn += source.draw(generator(b"draw/" + law.encode()), rest, law)
    if len(drawn) != item.cases:
        raise ConfirmationRefused("confirmation_draw_short")
    fresh = [(opaque(f"draw/{i}"), x) for i, x in enumerate(drawn)]
    order = generator(b"order")
    sources = order.sample(range(len(fresh)), item.hidden_duplicates)
    twins = [(opaque(f"repeat/{j}"), fresh[s]) for j, s in enumerate(sources)]
    cases = fresh + [(dup, inputs) for dup, (_, inputs) in twins]
    order.shuffle(cases)
    return SealedBatch(
        item.challenge_id,
        role,
        law,
        tuple((c, tuple(sorted(x.items()))) for c, x in cases),
        tuple((dup, original) for dup, (original, _) in twins),
    )


#: Draws a stratum may take per case before it is refused as unreachable.
STRATUM_ATTEMPTS_PER_CASE = 1000


def _draw_stratum(source, rng, count, law, stratum):
    """`count` population draws inside `stratum`'s region (rejection)."""
    unknown = set(stratum["lower_bounds"]) - set(source.inputs())
    if unknown:
        raise ConfirmationRefused("confirmation_stratum_names_unknown_input")
    cases, attempts = [], 0
    while len(cases) < count:
        if attempts >= STRATUM_ATTEMPTS_PER_CASE * count:
            raise ConfirmationRefused(
                "confirmation_stratum_unreachable:" + stratum["id"]
            )
        attempts += 1
        [case] = source.draw(rng, 1, law)
        if in_stratum(case, stratum):
            cases.append(case)
    return cases


# --- custody: an owner-only root and journal ------------------------------------------


def _outside_repository(path, what):
    resolved = Path(path).resolve()
    if resolved == REPOSITORY or REPOSITORY in resolved.parents:
        raise ConfirmationRefused(what + "_inside_repository")
    return resolved


def _owner_only(path, *, directory):
    try:
        info = os.lstat(path)
    except OSError:
        raise ConfirmationRefused("confirmation_custody_missing") from None
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if stat.S_ISLNK(info.st_mode) or not kind(info.st_mode):
        raise ConfirmationRefused("confirmation_custody_not_a_plain_path")
    if info.st_mode & 0o077:
        raise ConfirmationRefused("confirmation_custody_not_owner_only")


class ConfirmationRoot:
    """A 32-byte private root. Never printed, pickled or serialized."""

    __slots__ = ("_bytes",)

    def __init__(self, value, *, _token=None):
        if _token is not _LOADED or type(value) is not bytes or len(value) != 32:
            raise TypeError("a ConfirmationRoot comes only from its custody")
        object.__setattr__(self, "_bytes", value)

    def __setattr__(self, name, value):
        raise AttributeError("a ConfirmationRoot is immutable")

    def __repr__(self):
        return "ConfirmationRoot(<redacted>)"

    def __reduce__(self):
        raise TypeError("a ConfirmationRoot cannot be serialized")

    def commitment(self):
        """The public commitment: sha256(domain || root)."""
        return "sha256:" + hashlib.sha256(ROOT_DOMAIN + self._bytes).hexdigest()


_LOADED = object()


class ConfirmationCustody:
    """An owner-only directory outside the repository: `root` (32 bytes),
    `journal.jsonl` (public commitments, append-only) and a writer lock."""

    def __init__(self, directory, challenge_id):
        self.directory = _outside_repository(directory, "confirmation_custody")
        self.challenge_id = challenge_id
        _owner_only(self.directory, directory=True)
        self.journal_path = self.directory / "journal.jsonl"
        _owner_only(self.directory / "root", directory=False)
        _owner_only(self.journal_path, directory=False)
        root = self.root()
        entry = self.entries()[0] if self.entries() else None
        if (
            entry is None
            or entry.get("kind") != "root"
            or entry.get("challenge") != challenge_id
            or entry.get("root_commitment") != root.commitment()
        ):
            raise ConfirmationRefused("confirmation_custody_root_not_committed")

    @staticmethod
    def init(directory, challenge_id):
        """Create a custody once: an owner-only directory, a fresh root and
        the journal's root commitment. Never overwrites."""
        directory = _outside_repository(directory, "confirmation_custody")
        if directory.exists():
            raise ConfirmationRefused("confirmation_custody_exists")
        directory.mkdir(parents=True, mode=0o700)
        directory.chmod(0o700)
        fd = os.open(directory / "root", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(os.urandom(32))
        fd = os.open(
            directory / "journal.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        os.close(fd)
        custody = object.__new__(ConfirmationCustody)
        custody.directory, custody.challenge_id = directory, challenge_id
        custody.journal_path = directory / "journal.jsonl"
        entry = custody._append(
            {
                "kind": "root",
                "challenge": challenge_id,
                "root_commitment": custody.root().commitment(),
            }
        )
        return ConfirmationCustody(directory, challenge_id), entry

    def root(self):
        path = self.directory / "root"
        _owner_only(path, directory=False)
        data = path.read_bytes()
        if len(data) != 32:
            raise ConfirmationRefused("confirmation_root_malformed")
        return ConfirmationRoot(data, _token=_LOADED)

    @contextlib.contextmanager
    def writer(self):
        fd = os.open(self.directory / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield self
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def entries(self):
        lines = self.journal_path.read_text().splitlines()
        return [json.loads(line) for line in lines if line]

    def _append(self, entry):
        entry = {"schema": JOURNAL_SCHEMA, "sequence": len(self.entries()), **entry}
        body = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        fd = os.open(self.journal_path, os.O_WRONLY | os.O_APPEND)
        with os.fdopen(fd, "a") as handle:
            handle.write(body + "\n")
        return entry

    def batches(self):
        return [e for e in self.entries() if e.get("kind") == "batch"]

    def commit(self, batch, item):
        return self._append(
            {
                "kind": "batch",
                "challenge": batch.challenge_id,
                "role": batch.role,
                "fingerprint": batch.fingerprint,
                "cases": len(batch.cases),
                "set_digest": item.digest,
            }
        )


# --- overlap --------------------------------------------------------------------------


def overlap_check(source, batch_inputs, priors, duplicates):
    """Refuse if a fresh case repeats another fresh case or any prior case.
    `batch_inputs` maps case id to inputs; `priors` maps a prior's name to its
    case keys (`source.key`). Returns how many prior keys each name held."""
    keys = {
        case_id: source.key(inputs)
        for case_id, inputs in batch_inputs.items()
        if case_id not in duplicates
    }
    if len(set(keys.values())) != len(keys):
        raise ConfirmationRefused("confirmation_fresh_draws_collide")
    fresh = set(keys.values())
    checked = {}
    for name, prior in sorted(priors.items()):
        if fresh & prior:
            raise ConfirmationRefused("confirmation_overlaps_prior:" + name)
        checked[name] = len(prior)
    return checked


def _same_role_refusal(role, committed, fingerprint):
    """Refuse a second, different batch under `role` (any letter case)."""
    other = {
        e["fingerprint"]
        for e in committed
        if canonical_role(e.get("role")) == role and e["fingerprint"] != fingerprint
    }
    if other:
        raise ConfirmationRefused("confirmation_role_reused")
    return any(canonical_role(e.get("role")) == role for e in committed)


def load_private_priors(item, source, supplied):
    """The operator's private pool files: `{name: path}`, each a registered
    prior for this set, owner-only, outside the repository, holding
    `{"cases": [{"inputs": {...}}, ...]}`. Returns (keys by name, digests)."""
    for name in supplied:
        if name not in item.required_private_priors:
            raise ConfirmationRefused(
                "confirmation_private_prior_not_registered:" + name
            )
    keys, digests = {}, {}
    for name in item.required_private_priors:
        if name not in supplied:
            raise ConfirmationRefused("confirmation_private_prior_missing:" + name)
        path = _outside_repository(supplied[name], "confirmation_private_prior")
        _owner_only(path, directory=False)
        try:
            document = json.loads(path.read_text())
            cases = document["cases"]
            found = {source.key(case["inputs"]) for case in cases}
        except (OSError, ValueError, KeyError, TypeError):
            raise ConfirmationRefused(
                "confirmation_private_prior_malformed:" + name
            ) from None
        if not found:
            raise ConfirmationRefused("confirmation_private_prior_empty:" + name)
        keys["private:" + name] = found
        digests[name] = _file_digest(path)
    return keys, digests


# --- sealing --------------------------------------------------------------------------


def sealed(commitment):
    """A public commitment, checked, or None."""
    if (
        type(commitment) is not dict
        or set(commitment) != {"fingerprint", "journal_sequence"}
        or type(commitment["fingerprint"]) is not str
        or not FINGERPRINT.fullmatch(commitment["fingerprint"])
        or type(commitment["journal_sequence"]) is not int
        or commitment["journal_sequence"] < 0
    ):
        return None
    return dict(commitment)


def seal(
    role,
    *,
    custody=None,
    config=None,
    private_priors=None,
    repository=REPOSITORY,
    directory=None,
):
    """Seal `role`'s confirmation set; return only public values.

    `custody` is the owner-only custody directory (a `confirmation_journal`
    set); `config` is the battery deployment configuration (a
    `battery_deployment` set). `private_priors` maps each registered private
    prior's name to the operator's file.
    """
    from .confirmation_sources import source_for

    sets = load_sets(directory)
    canonical = canonical_role(role)
    if canonical not in sets:
        raise ConfirmationRefused("confirmation_role_not_registered")
    item = sets[canonical]
    item.require_ready()
    source = source_for(item.challenge_id)
    if item.sampling_law["id"] not in source.laws:
        raise ConfirmationRefused("confirmation_law_not_served")
    if item.custody["kind"] != source.custody:
        raise ConfirmationRefused("confirmation_custody_not_served")
    private, digests = load_private_priors(item, source, dict(private_priors or {}))
    if source.custody == "battery_deployment":
        if config is None or custody is not None:
            raise ConfirmationRefused("confirmation_needs_the_deployment_config")
        result = source.seal(item, sets, config, private, repository)
    else:
        if custody is None or config is not None:
            raise ConfirmationRefused("confirmation_needs_its_custody")
        result = _seal_journal(item, sets, source, custody, private, repository)
    commitment = sealed(result["commitment"])
    if commitment is None:
        raise ConfirmationRefused("confirmation_commitment_malformed")
    return {
        "challenge_id": item.challenge_id,
        "role": item.role,
        "cases": item.cases,
        "hidden_duplicates": item.hidden_duplicates,
        "set_digest": item.digest,
        "newly_committed": result["newly_committed"],
        "commitment": commitment,
        "overlap_checked": result["overlap_checked"],
        "private_priors": digests,
    }


def _seal_journal(item, sets, source, directory, private, repository):
    custody = ConfirmationCustody(directory, item.challenge_id)
    with custody.writer():
        root = custody.root()
        batch = make_batch(root, source, item)
        committed = custody.batches()
        again = _same_role_refusal(item.role, committed, batch.fingerprint)
        priors = {"published": source.published(repository), **private}
        present = set()
        for entry in committed:
            prior = canonical_role(entry["role"])
            if prior == item.role:
                continue
            present.add(prior)
            if prior not in sets:
                raise ConfirmationRefused("confirmation_prior_not_regenerable:" + prior)
            regenerated = make_batch(root, source, sets[prior])
            if regenerated.fingerprint != entry["fingerprint"]:
                raise ConfirmationRefused(
                    "confirmation_prior_regeneration_mismatch:" + prior
                )
            priors["sealed:" + prior] = {
                source.key(x) for x in regenerated.inputs().values()
            }
        for prior in item.required_prior_roles:
            if prior not in present:
                raise ConfirmationRefused("confirmation_required_prior_absent:" + prior)
        checked = overlap_check(source, batch.inputs(), priors, dict(batch.duplicates))
        if again:
            entry = next(e for e in committed if e["fingerprint"] == batch.fingerprint)
        else:
            entry = custody.commit(batch, item)
    return {
        "newly_committed": not again,
        "commitment": {
            "fingerprint": entry["fingerprint"],
            "journal_sequence": entry["sequence"],
        },
        "overlap_checked": checked,
    }


# --- the pinning manifest -------------------------------------------------------------


def manifest(role, *, commitment=None, directory=None):
    """What a study binds to a confirmation set: its registered document, the
    code that draws and seals it, its commitment, and what still blocks it."""
    from . import confirmation_sources
    from .confirmation_sources import source_for

    item = confirmation_set(role, directory)
    source = source_for(item.challenge_id)
    checked = sealed(commitment) if commitment is not None else None
    if commitment is not None and checked is None:
        raise ConfirmationRefused("confirmation_commitment_malformed")
    blockers = [f"human_input:{name}" for name in item.human_input]
    if not item.sealable:
        blockers.append("not_sealable")
    if item.sampling_law is not None and item.sampling_law["id"] not in source.laws:
        blockers.append("law_not_served")
    if checked is None:
        blockers.append("not_sealed")
    implementation = {
        "confirmation": _file_digest(__file__),
        "confirmation_sources": _file_digest(confirmation_sources.__file__),
        **{name: _file_digest(path) for name, path in source.implementation().items()},
    }
    return {
        "schema": MANIFEST_SCHEMA,
        "role": item.role,
        "challenge_id": item.challenge_id,
        "set_digest": item.digest,
        "registry_digest": registry_digest(directory),
        "skeleton": item.skeleton(),
        "implementation": implementation,
        "commitment": checked,
        "blockers": blockers,
    }


# --- command line ---------------------------------------------------------------------


def _priors(values):
    supplied = {}
    for value in values or ():
        name, sep, path = value.partition("=")
        if not sep or not name or not path or name in supplied:
            raise ConfirmationRefused("confirmation_prior_argument_malformed")
        supplied[name] = path
    return supplied


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.confirmation",
        description="Challenge-neutral sealed confirmation sets (operator tool).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="every registered set's public skeleton")
    skeleton = sub.add_parser("skeleton", help="one set's public skeleton")
    skeleton.add_argument("--role", required=True)
    init = sub.add_parser("init", help="create an owner-only custody once")
    init.add_argument("--challenge", required=True)
    init.add_argument("--custody", required=True)
    run = sub.add_parser("seal", help="seal a set on the operator host")
    run.add_argument("--role", required=True)
    run.add_argument("--custody")
    run.add_argument("--config")
    run.add_argument("--prior", action="append", metavar="NAME=PATH")
    pin = sub.add_parser("manifest", help="a set's pinning manifest")
    pin.add_argument("--role", required=True)
    pin.add_argument("--fingerprint")
    pin.add_argument("--sequence", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = [item.skeleton() for item in load_sets().values()]
        elif args.command == "skeleton":
            result = confirmation_set(args.role).skeleton()
        elif args.command == "init":
            from .confirmation_sources import source_for

            source = source_for(args.challenge)
            if source.custody != "confirmation_journal":
                raise ConfirmationRefused("confirmation_custody_not_served")
            _custody, entry = ConfirmationCustody.init(args.custody, args.challenge)
            result = {
                "challenge_id": args.challenge,
                "root_commitment": entry["root_commitment"],
                "journal_sequence": entry["sequence"],
            }
        elif args.command == "seal":
            result = seal(
                args.role,
                custody=args.custody,
                config=args.config,
                private_priors=_priors(args.prior),
            )
        else:
            given = (args.fingerprint, args.sequence)
            if given.count(None) == 1:
                raise ConfirmationRefused("confirmation_commitment_incomplete")
            commitment = (
                None
                if args.fingerprint is None
                else {
                    "fingerprint": args.fingerprint,
                    "journal_sequence": args.sequence,
                }
            )
            result = manifest(args.role, commitment=commitment)
    except ConfirmationRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
