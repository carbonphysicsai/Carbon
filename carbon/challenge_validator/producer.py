"""Carbon's pool-batch producer, Challenge-neutral (VALIDATOR-19 slice 1).

Carbon draws and solves every hidden batch once, on the producer host, so
every validator scores every miner on the same cases and the same solver
results (OWNER-SHARED-ANSWER-KEY-01). The producer drives one `BatchSource`
per Challenge:

    python -m carbon.challenge_validator.producer draw --config PRODUCER.json \\
        --challenge ID --role ROLE --kind screening [--size N]
    python -m carbon.challenge_validator.producer solve --config PRODUCER.json \\
        --challenge ID --fingerprint FP
    python -m carbon.challenge_validator.producer seal --config PRODUCER.json \\
        --challenge ID --fingerprint FP
    python -m carbon.challenge_validator.producer publish --config PRODUCER.json \\
        --challenge ID --fingerprint FP
    python -m carbon.challenge_validator.producer status --config PRODUCER.json

- **`draw`** draws one batch from the registered population with the source's
  own root, commits its fingerprint to the source's seed journal before any
  use, and writes the solve jobs owner-only. Uniform draws only: steering
  Q(x) is HUMAN_INPUT (OWNER-VALIDATOR-MAINNET-PARITY-01 §5).
- **`solve`** runs the Challenge's pinned truth solves on the producer's
  compute.
- **`seal`** ingests the solves and, once every case has a terminal record,
  re-checks the batch against its seed-journal commitment and records the
  public commitment: fingerprint, references digest, case count, and the
  contract, rule and seed-pin identities. Its activation window is set by
  rotation (slice 3); it is null until then.

Every file is owner-only and lives outside the repository; the producer runs
only under its configured service account. Its journal and commitments hold
public values only: no case id, input, reference or score.

- **`publish`** (slice 2) signs a sealed batch's package with Carbon's
  producer key (`answer_key.package`) and writes it to the owner-only outbox.
  The operator pushes the outbox to the distribution host over a
  key-restricted channel; the producer host itself is never
  internet-facing.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import abc
import argparse
import json
import os
import pwd
import stat
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG_SCHEMA = "carbon.challenge-validator.producer-config.v1"
JOURNAL_SCHEMA = "carbon.challenge-validator.producer-journal.v1"
COMMITMENT_SCHEMA = "carbon.challenge-validator.batch-commitment.v1"

#: Batch kinds a validator scores with. Producer-only sets (tuning,
#: confirmation) are sealed by their own tools and never drawn here.
SERVED_KINDS = ("screening", "finalist")


class ProducerRefused(ValueError):
    """A typed refusal; its code carries no private case, input or output."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


# --- one Challenge's batches ----------------------------------------------------------


class BatchSource(abc.ABC):
    """One Challenge's batches, as the producer drives them.

    Subclasses set `challenge_id`. Every method takes and returns public
    values, except `jobs`, whose cases go only to the truth solves.
    """

    challenge_id: str

    @abc.abstractmethod
    def identities(self):
        """Public identities every commitment binds: `contract_digest`,
        `rule_digest` and `seed_pin`."""

    @abc.abstractmethod
    def draw(self, role, *, kind, size=None):
        """Draw and journal-commit one batch (idempotent by role); return its
        fingerprint."""

    @abc.abstractmethod
    def jobs(self, fingerprint):
        """The distinct cases the truth solves need. Private."""

    @abc.abstractmethod
    def solve(self, work, **options):
        """Run the pinned truth solves of `work/jobs.json` into
        `work/records.jsonl`."""

    @abc.abstractmethod
    def ingest(self, fingerprint, records):
        """Store terminal reference records; return whether the batch is
        complete. Refuses (`producer_references_changed`) when a stored record
        no longer matches the digest it completed with."""

    @abc.abstractmethod
    def sealed(self, fingerprint):
        """The batch's public identity once its references are complete:
        `role`, `kind`, `journal_sequence`, `cases` and `references_digest`.
        None while any reference is pending."""

    @abc.abstractmethod
    def export(self, fingerprint):
        """A sealed batch's payload for its answer-key package: the batch
        document and its reference records. Private."""

    @abc.abstractmethod
    def check(self, fingerprint):
        """Refuse unless the stored batch still matches its seed-journal
        commitment. Raises `ProducerRefused`."""


def source_for(challenge_id, spec, *, repository=REPOSITORY):
    """The registered `BatchSource` for one configured Challenge."""
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    if challenge_id == BATTERY_CHALLENGE:
        from .battery import BatteryBatchSource

        return BatteryBatchSource.from_deployment(
            spec["deployment"], overlay=spec.get("overlay"), repository=repository
        )
    raise ProducerRefused("producer_no_source")


# --- files ----------------------------------------------------------------------------


def _outside_repository(path):
    resolved = Path(path).resolve()
    root = REPOSITORY.resolve()
    if resolved == root or root in resolved.parents:
        raise ProducerRefused("producer_dir_inside_repository")
    return Path(path)


def _owner_only_dir(path):
    path = _outside_repository(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ProducerRefused("producer_dir_not_owner_only")
    return path


def _read_private(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ProducerRefused("producer_file_not_owner_only")
    return json.loads(Path(path).read_bytes())


def _write_once(path, value):
    """Write an owner-only file once; an existing file must hold `value`."""
    path = Path(path)
    if path.exists():
        if _read_private(path) != value:
            raise ProducerRefused("producer_file_changed")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")


def load_config(path, *, account=None):
    """The producer's configuration: owner-only, exact keys, and loaded only
    under its service account."""
    try:
        config = _read_private(path)
    except FileNotFoundError:
        raise ProducerRefused("producer_config_missing") from None
    keys = {"schema", "service_account", "producer_dir", "sources"}
    if (
        type(config) is not dict
        or not keys <= set(config)
        or set(config) - keys - {"signing_key"}
        or config["schema"] != CONFIG_SCHEMA
        or type(config["sources"]) is not dict
        or any(
            type(spec) is not dict
            or "deployment" not in spec
            or set(spec) - {"deployment", "overlay"}
            for spec in config["sources"].values()
        )
    ):
        raise ProducerRefused("producer_config_malformed")
    account = account or pwd.getpwuid(os.geteuid()).pw_name
    if type(config["service_account"]) is not str or config["service_account"] != (
        account
    ):
        raise ProducerRefused("producer_wrong_account")
    return config


# --- the journal ----------------------------------------------------------------------


class ProducerJournal:
    """The producer's append-only, owner-only journal of public events."""

    def __init__(self, path):
        self.path = Path(path)

    def entries(self):
        if not self.path.exists():
            return []
        if os.lstat(self.path).st_mode & 0o077:
            raise ProducerRefused("producer_file_not_owner_only")
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def append(self, event, **fields):
        entry = {
            "schema": JOURNAL_SCHEMA,
            "sequence": len(self.entries()),
            "event": event,
            **fields,
        }
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def find(self, event, challenge_id, fingerprint):
        for entry in self.entries():
            if (entry["event"], entry["challenge_id"], entry["fingerprint"]) == (
                event,
                challenge_id,
                fingerprint,
            ):
                return entry
        return None


# --- the producer ---------------------------------------------------------------------


class Producer:
    """Draw, solve once, and seal batches for the configured Challenges."""

    def __init__(self, directory, sources, *, signing_key=None):
        self.directory = _owner_only_dir(directory)
        self.sources = {source.challenge_id: source for source in sources}
        self.journal = ProducerJournal(self.directory / "journal.jsonl")
        self.signing_key = signing_key

    @classmethod
    def from_config(cls, path, *, repository=REPOSITORY):
        from .answer_key import ProducerKey

        config = load_config(path)
        key = config.get("signing_key")
        return cls(
            config["producer_dir"],
            [
                source_for(challenge_id, spec, repository=repository)
                for challenge_id, spec in sorted(config["sources"].items())
            ],
            signing_key=None if key is None else ProducerKey.load(key),
        )

    def _source(self, challenge_id):
        if challenge_id not in self.sources:
            raise ProducerRefused("producer_no_source")
        return self.sources[challenge_id]

    def _private_dir(self, *parts):
        """An owner-only directory under the producer's, every level made
        owner-only (`mkdir(parents=True)` would leave parents at the umask)."""
        directory = self.directory
        for part in parts:
            directory = _owner_only_dir(directory / part)
        return directory

    def _work(self, challenge_id, fingerprint):
        return self._private_dir(
            "work", challenge_id, fingerprint.removeprefix("sha256:")
        )

    def draw(self, challenge_id, role, *, kind, size=None):
        """Draw one batch and write its solve jobs. Idempotent by role."""
        if kind not in SERVED_KINDS:
            raise ProducerRefused("producer_kind_refused")
        source = self._source(challenge_id)
        fingerprint = source.draw(role, kind=kind, size=size)
        if self.journal.find("drawn", challenge_id, fingerprint) is None:
            self.journal.append(
                "drawn", challenge_id=challenge_id, fingerprint=fingerprint, kind=kind
            )
        jobs = source.jobs(fingerprint)
        work = self._work(challenge_id, fingerprint)
        _write_once(work / "jobs.json", {"fingerprint": fingerprint, "jobs": jobs})
        return {"fingerprint": fingerprint, "jobs": len(jobs)}

    def solve(self, challenge_id, fingerprint, **options):
        """The pinned truth solves for one drawn batch. Resumable."""
        if self.journal.find("drawn", challenge_id, fingerprint) is None:
            raise ProducerRefused("producer_not_drawn")
        work = self._work(challenge_id, fingerprint)
        records = work / "records.jsonl"
        if not records.exists():
            records.touch(mode=0o600)
        return self._source(challenge_id).solve(work, **options)

    def seal(self, challenge_id, fingerprint):
        """Ingest the solves; once complete, re-check the batch and record its
        public commitment. A sealed batch is never re-sealed differently."""
        if self.journal.find("drawn", challenge_id, fingerprint) is None:
            raise ProducerRefused("producer_not_drawn")
        source = self._source(challenge_id)
        # The stored batch is checked before any record is ingested for it.
        source.check(fingerprint)
        work = self._work(challenge_id, fingerprint)
        path = work / "records.jsonl"
        records = []
        if path.exists():
            if os.lstat(path).st_mode & 0o077:
                raise ProducerRefused("producer_file_not_owner_only")
            records = [
                json.loads(line) for line in path.read_text().splitlines() if line
            ]
        if not source.ingest(fingerprint, records):
            return {"fingerprint": fingerprint, "state": "PENDING"}
        commitment = self._commitment(source, fingerprint)
        earlier = self.journal.find("sealed", challenge_id, fingerprint)
        if earlier is not None:
            if earlier["commitment"] != commitment:
                raise ProducerRefused("producer_commitment_changed")
            return commitment
        directory = self._private_dir("commitments", challenge_id)
        _write_once(
            directory / (fingerprint.removeprefix("sha256:") + ".json"), commitment
        )
        self.journal.append(
            "sealed",
            challenge_id=challenge_id,
            fingerprint=fingerprint,
            commitment=commitment,
        )
        return commitment

    def _commitment(self, source, fingerprint):
        sealed = source.sealed(fingerprint)
        if sealed is None:
            raise ProducerRefused("producer_references_pending")
        identities = source.identities()
        return {
            "schema": COMMITMENT_SCHEMA,
            "challenge_id": source.challenge_id,
            "fingerprint": fingerprint,
            "role": sealed["role"],
            "kind": sealed["kind"],
            "journal_sequence": sealed["journal_sequence"],
            "cases": sealed["cases"],
            "references_digest": sealed["references_digest"],
            "contract_digest": identities["contract_digest"],
            "rule_digest": identities["rule_digest"],
            "seed_pin": identities["seed_pin"],
            # Set by rotation (slice 3) from the Challenge's cadence, which is
            # HUMAN_INPUT; null until then.
            "window": None,
        }

    def publish(self, challenge_id, fingerprint):
        """Sign a sealed batch's answer-key package into the outbox, for the
        operator to push to the distribution host. Idempotent: the signature
        is deterministic, so a second publish writes the same bytes."""
        from .answer_key import AnswerKeyRefused, package, write_private

        if self.signing_key is None:
            raise ProducerRefused("producer_no_signing_key")
        sealed = self.journal.find("sealed", challenge_id, fingerprint)
        if sealed is None:
            raise ProducerRefused("producer_not_sealed")
        source = self._source(challenge_id)
        # Re-checked, so a batch changed after its seal is never published.
        source.check(fingerprint)
        if (
            source.sealed(fingerprint) is None
            or self._commitment(source, fingerprint) != sealed["commitment"]
        ):
            raise ProducerRefused("producer_commitment_changed")
        try:
            value = package(
                self.signing_key, sealed["commitment"], source.export(fingerprint)
            )
        except AnswerKeyRefused as refused:
            raise ProducerRefused(refused.code) from None
        name = fingerprint.removeprefix("sha256:") + ".json"
        try:
            write_private(self._private_dir("outbox", challenge_id) / name, value)
        except AnswerKeyRefused as refused:
            raise ProducerRefused(refused.code) from None
        if self.journal.find("published", challenge_id, fingerprint) is None:
            self.journal.append(
                "published",
                challenge_id=challenge_id,
                fingerprint=fingerprint,
                key_id=value["key_id"],
            )
        return {"fingerprint": fingerprint, "key_id": value["key_id"], "file": name}

    def status(self):
        """Counts per Challenge; public values only."""
        counts = {}
        for entry in self.journal.entries():
            row = counts.setdefault(
                entry["challenge_id"], {"drawn": 0, "sealed": 0, "published": 0}
            )
            row[entry["event"]] += 1
        return {"challenges": counts}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.producer")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("draw", "solve", "seal", "publish", "status"):
        command = sub.add_parser(name)
        command.add_argument("--config", required=True)
        if name == "status":
            continue
        command.add_argument("--challenge", required=True)
        if name == "draw":
            command.add_argument("--role", required=True)
            command.add_argument("--kind", required=True, choices=SERVED_KINDS)
            command.add_argument("--size", type=int)
        else:
            command.add_argument("--fingerprint", required=True)
        if name == "solve":
            command.add_argument("--workers", type=int, default=7)
    args = parser.parse_args(argv)
    try:
        producer = Producer.from_config(args.config)
        if args.command == "draw":
            result = producer.draw(
                args.challenge, args.role, kind=args.kind, size=args.size
            )
        elif args.command == "solve":
            result = producer.solve(
                args.challenge, args.fingerprint, workers=args.workers
            )
        elif args.command == "seal":
            result = producer.seal(args.challenge, args.fingerprint)
        elif args.command == "publish":
            result = producer.publish(args.challenge, args.fingerprint)
        else:
            result = producer.status()
    except ProducerRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
