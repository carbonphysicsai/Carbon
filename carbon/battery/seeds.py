"""The battery private-seed service: committed before use, revealed at retirement.

It replaces the exam-design campaign's container-local root
(`scripts/dev/exam_design/private_cases.py`) with these properties, each
enforced by construction:

- **The root stays private.** `PrivateRoot` is built only from an
  operator-held file outside the repository: 32 bytes, a regular file (not a
  symlink), owner-only permissions. Its `repr` never shows the bytes, and it
  cannot be pickled or copied into a public projection.
- **The derivation is the campaign's own.** Seeds come from
  `carbon.seeding.derive_mock_seed` bound to a `SeedPin`. A test regenerates
  the campaign's private cases from its revealed root.
- **Hidden duplicates are always present.** A `PrivateBatch` cannot be built
  without at least one duplicate. Duplicates carry opaque case ids and are
  shuffled among the originals, so nothing about a case id or its position
  marks it as a repeat. The duplicate map is private until reveal.
- **Commit before use.** A batch reaches evaluation only as a `CommittedBatch`,
  which only `SeedJournal.commit` creates, after appending the batch
  fingerprint to the append-only journal. A batch built any other way,
  including a valid one, is refused.
- **Reveal at retirement.** `SeedJournal.reveal` publishes a batch's plaintext
  only after the batch has retired from the pool. Anyone can then recompute
  its fingerprint against the earlier commitment.

The mock seeding namespace is deliberate: DEVELOPMENT, non-paying, with no
official or LIVE seed authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .challenge import CHALLENGE, INPUT_BOUNDS, INPUTS

COMMIT_DOMAIN = b"carbon.battery.private-root.v1"
FINGERPRINT_SCHEMA = "carbon.battery.private-batch.v1"
JOURNAL_SCHEMA = "carbon.battery.seed-journal.v1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class PrivateRoot:
    """A 32-byte private root. Never printed, pickled or serialized."""

    __slots__ = ("_bytes",)

    def __init__(self, value, *, _token=None):
        if _token is not _LOADED or type(value) is not bytes or len(value) != 32:
            raise TypeError("a PrivateRoot comes only from PrivateRoot.load")
        object.__setattr__(self, "_bytes", value)

    def __setattr__(self, name, value):
        raise AttributeError("a PrivateRoot is immutable")

    def __repr__(self):
        return "PrivateRoot(<redacted>)"

    def __reduce__(self):
        raise TypeError("a PrivateRoot cannot be serialized")

    @staticmethod
    def load(path):
        """Load an operator-held root file; refuse anything looser."""
        path = Path(path)
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ValueError("the private root must be a regular file")
        if info.st_mode & 0o077:
            raise ValueError("the private root must be readable by its owner only")
        if info.st_size != 32:
            raise ValueError("the private root is exactly 32 bytes")
        return PrivateRoot(path.read_bytes(), _token=_LOADED)

    @staticmethod
    def create(path):
        """Write a fresh root once, owner-only; never overwrites."""
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(os.urandom(32))
        return PrivateRoot.load(path)

    def commitment(self):
        """The public commitment: sha256(domain || root)."""
        return hashlib.sha256(COMMIT_DOMAIN + self._bytes).hexdigest()


_LOADED = object()


def seed_pin(generator_digest, scoring_digest):
    """The pin binding derivations to this Challenge, generator and score."""
    binding = hashlib.sha256(
        f"{CHALLENGE.challenge_id}/{CHALLENGE.version}/{generator_digest}/"
        f"{scoring_digest}".encode()
    ).hexdigest()
    return {
        "challenge": [CHALLENGE.challenge_id, CHALLENGE.version],
        "generator_version": "carbon.battery.reference.v1",
        "generator_digest": generator_digest,
        "scoring_version": "carbon.battery.exam.v1",
        "scoring_digest": scoring_digest,
        "evaluation_binding": binding,
    }


#: The modules whose bytes determine the cases and their reference answers.
GENERATOR_MODULES = ("challenge.py", "seeds.py", "reference.py", "truth.py")


def generator_digest(repository):
    """The reference generator's identity for a deployment's seed pin: the
    case derivation, the reference model and solver, and the pinned truth
    environment (base image and overlay lock). Recorded once, in the
    journal's root entry; later code changes never rewrite it."""
    from .truth import TRUTH_IMAGE, lock_digest

    here = Path(__file__).parent
    identity = {
        "modules": {
            name: hashlib.sha256((here / name).read_bytes()).hexdigest()
            for name in GENERATOR_MODULES
        },
        "truth_image": TRUTH_IMAGE["base_image"],
        "overlay_lock": lock_digest(repository),
    }
    return "sha256:" + hashlib.sha256(_canonical(identity).encode()).hexdigest()


def _context(root, pin):
    from carbon.registry.model import ChallengeKey
    from carbon.seeding.model import (
        EvaluationBinding,
        MockContext,
        MockEntropy,
        SeedPin,
    )

    sp = SeedPin(
        ChallengeKey(*pin["challenge"]),
        pin["generator_version"],
        pin["generator_digest"],
        pin["scoring_version"],
        pin["scoring_digest"],
        EvaluationBinding(bytes.fromhex(pin["evaluation_binding"])),
    )
    return MockContext(MockEntropy(root._bytes), sp)


def draw_inputs(context, role, index):
    """One uniform draw over the input bounds: the campaign's exact rule."""
    from carbon.seeding.derive import derive_mock_seed
    from carbon.seeding.model import RoleKey

    seed = derive_mock_seed(context, RoleKey(role.lower()), index)
    material = seed.as_backend_bytes()
    rng = np.random.default_rng(
        int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    )
    return {k: float(np.round(rng.uniform(*INPUT_BOUNDS[k]), 4)) for k in INPUTS}


@dataclass(frozen=True)
class PrivateBatch:
    """One private evaluation set with hidden duplicates. Private until reveal."""

    role: str
    cases: tuple[tuple[str, tuple[tuple[str, float], ...]], ...]
    duplicates: tuple[tuple[str, str], ...]  # duplicate id -> original id

    def __post_init__(self):
        ids = [c for c, _ in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case ids are unique")
        if not self.duplicates:
            raise ValueError("every private set carries hidden duplicates")
        inputs = dict(self.cases)
        for dup, orig in self.duplicates:
            if dup not in inputs or orig not in inputs or dup == orig:
                raise ValueError("a duplicate names two cases of this batch")
            if inputs[dup] != inputs[orig]:
                raise ValueError("a duplicate repeats its original's inputs")

    def document(self):
        return {
            "schema": FINGERPRINT_SCHEMA,
            "challenge": [CHALLENGE.challenge_id, CHALLENGE.version],
            "role": self.role,
            "cases": [{"case_id": c, "inputs": dict(x)} for c, x in self.cases],
            "duplicates": dict(self.duplicates),
        }

    @staticmethod
    def from_document(document):
        """A batch from its own `document()`; the fingerprint then matches
        only if every case, input and duplicate is exactly as committed."""
        if document.get("schema") != FINGERPRINT_SCHEMA or document.get(
            "challenge"
        ) != [CHALLENGE.challenge_id, CHALLENGE.version]:
            raise ValueError("not a battery private batch document")
        return PrivateBatch(
            document["role"],
            tuple(
                (c["case_id"], tuple(sorted(c["inputs"].items())))
                for c in document["cases"]
            ),
            tuple(document["duplicates"].items()),
        )

    @property
    def fingerprint(self):
        return (
            "sha256:" + hashlib.sha256(_canonical(self.document()).encode()).hexdigest()
        )


def make_batch(root, pin, role, count, duplicates=2):
    """`count` cases for `role`: `count - duplicates` fresh draws plus hidden
    duplicates, with opaque ids, in a root-derived shuffled order."""
    if type(root) is not PrivateRoot:
        raise TypeError("an operator-held PrivateRoot is required")
    if not 1 <= duplicates < count:
        raise ValueError("a batch carries at least one hidden duplicate")
    context = _context(root, pin)
    key = hmac.new(root._bytes, b"case-ids/" + role.encode(), hashlib.sha256).digest()

    def opaque(label):
        tag = hmac.new(key, label.encode(), hashlib.sha256).hexdigest()[:16]
        return f"{role}-{tag}"

    fresh = [
        (opaque(f"draw/{i}"), draw_inputs(context, role, i))
        for i in range(count - duplicates)
    ]
    order = np.random.default_rng(
        int.from_bytes(hmac.new(key, b"order", hashlib.sha256).digest()[:8], "big")
    )
    sources = order.choice(len(fresh), size=duplicates, replace=False)
    twins = [(opaque(f"repeat/{j}"), fresh[int(s)]) for j, s in enumerate(sources)]
    cases = fresh + [(dup, inputs) for dup, (_, inputs) in twins]
    permutation = order.permutation(len(cases))
    cases = [cases[int(p)] for p in permutation]
    return PrivateBatch(
        role,
        tuple((c, tuple(sorted(x.items()))) for c, x in cases),
        tuple((dup, orig) for dup, (orig, _) in twins),
    )


def reconstruction_seed(root, submission_id):
    """Carbon's reconstruction seed for one submission: derived from the
    private root, so no miner can choose or predict it."""
    if type(root) is not PrivateRoot:
        raise TypeError("an operator-held PrivateRoot is required")
    tag = hmac.new(
        root._bytes, b"reconstruction/" + submission_id.encode(), hashlib.sha256
    ).digest()
    return int.from_bytes(tag[:4], "big")


@dataclass(frozen=True)
class CommittedBatch:
    """A batch whose fingerprint is already in the journal."""

    batch: PrivateBatch
    fingerprint: str
    sequence: int
    token: object = None

    def __post_init__(self):
        if self.token is not _COMMITTED:
            raise TypeError("a CommittedBatch comes only from SeedJournal.commit")

    def solver_jobs(self):
        """What a truth or prediction worker receives: case ids and inputs."""
        return [{"case_id": c, **dict(x)} for c, x in self.batch.cases]


_COMMITTED = object()


class RevealRefused(PermissionError):
    """A reveal requested before the batch retired."""


class SeedJournal:
    """Append-only public journal of root and batch commitments and reveals."""

    def __init__(self, path):
        self.path = Path(path)

    def _entries(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def _append(self, entry):
        entry = {"schema": JOURNAL_SCHEMA, "sequence": len(self._entries()), **entry}
        with self.path.open("a") as handle:
            handle.write(_canonical(entry) + "\n")
        return entry

    def commit_root(self, root, pin):
        return self._append(
            {"kind": "root", "root_commitment": root.commitment(), "seed_pin": pin}
        )

    def commit(self, batch, *, pool_version):
        if type(batch) is not PrivateBatch:
            raise TypeError("a PrivateBatch is required")
        entry = self._append(
            {
                "kind": "batch",
                "role": batch.role,
                "fingerprint": batch.fingerprint,
                "cases": len(batch.cases),
                "pool_version": pool_version,
            }
        )
        return CommittedBatch(batch, batch.fingerprint, entry["sequence"], _COMMITTED)

    def recall(self, batch):
        """The `CommittedBatch` for a batch committed earlier, regenerated from
        its root. Refused unless this exact fingerprint is already in the
        journal: recall never commits, so it cannot bypass commit-before-use."""
        if type(batch) is not PrivateBatch:
            raise TypeError("a PrivateBatch is required")
        for entry in self._entries():
            if entry["kind"] == "batch" and entry["fingerprint"] == batch.fingerprint:
                return CommittedBatch(
                    batch, batch.fingerprint, entry["sequence"], _COMMITTED
                )
        raise ValueError("this batch was never committed")

    def retired(self):
        """Fingerprints of every retired batch."""
        return {e["fingerprint"] for e in self._entries() if e["kind"] == "retire"}

    def root_pin(self, root):
        """The seed pin committed with this root; refused for another root."""
        for entry in self._entries():
            if (
                entry["kind"] == "root"
                and entry["root_commitment"] == root.commitment()
            ):
                return entry["seed_pin"]
        raise ValueError("this root was never committed")

    def retire(self, committed):
        return self._append({"kind": "retire", "fingerprint": committed.fingerprint})

    def reveal(self, committed):
        """Publish a retired batch's plaintext; refused before retirement."""
        entries = self._entries()
        if not any(
            e["kind"] == "retire" and e["fingerprint"] == committed.fingerprint
            for e in entries
        ):
            raise RevealRefused("a batch is revealed only after it retires")
        return self._append(
            {
                "kind": "reveal",
                "fingerprint": committed.fingerprint,
                "batch": committed.batch.document(),
            }
        )

    def public(self):
        """The journal as anyone may read it: commitments, retirements and
        reveals only."""
        return self._entries()


def verify_reveal(entries):
    """Every reveal's plaintext matches the fingerprint committed before it.
    Returns what was checked, so an empty check never reads as a pass."""
    committed = {
        e["fingerprint"]: e["sequence"] for e in entries if e["kind"] == "batch"
    }
    checked = []
    for e in entries:
        if e["kind"] != "reveal":
            continue
        digest = "sha256:" + hashlib.sha256(_canonical(e["batch"]).encode()).hexdigest()
        ok = digest == e["fingerprint"] and committed.get(digest, 1e18) < e["sequence"]
        checked.append({"fingerprint": e["fingerprint"], "matches": ok})
    return {"reveals_checked": len(checked), "results": checked}
