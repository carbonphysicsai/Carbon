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
    python -m carbon.challenge_validator.producer tick --config PRODUCER.json [--block N]
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

- **`tick`** (slice 3) is rotation and retirement by finalized block, with
  no human or agent in the loop. A Challenge's cadence comes from its own
  registered rule (`BatchSource.cadence`): one batch per slot of
  `every_blocks`, each live for `active` slots. A slot's window is
  `[slot * every_blocks, (slot + active) * every_blocks)` in finalized blocks,
  the same for every validator. Each tick:
  - retires every published batch whose window has ended. It leaves the
    outbox, so the push removes it from the distribution host, and it enters
    the owner-only release queue. Releasing it is HUMAN_INPUT and never
    automatic.
  - fills the next slots ahead of their windows: it takes the earliest
    sealed, unscheduled batch, or draws, solves and seals a new one, then
    schedules and publishes it.
  - A slot left unfilled is recorded, never stalls validators, and is never
    filled after it starts.
  A Challenge with no registered cadence gets no scheduled batch.
- **`publish`** (slice 2) signs a sealed batch's package with Carbon's
  producer key (`answer_key.package`) and writes it to the owner-only outbox.
  The operator pushes the outbox to the distribution host over a
  key-restricted channel; the producer host itself is never
  internet-facing.
- **The quiz** (VALIDATOR-19 slice Q, part 2), only with the optional config
  `quiz: {"panel": PATH}`. Each screening batch drawn under it carries a
  private quiz, drawn by its source from the batch's own role (`quiz_draw`):
  - its jobs are written beside the batch's in the same `jobs.json`, and
    solved in the same `solve`;
  - `seal` selects it once its solves are in (`quiz_select`, which reads the
    registered panel's predictions only). When the source needs more draws
    (battery's Q3), the round is advanced and the batch stays PENDING, so
    the next tick solves the new round; a slot it misses is unfilled;
  - when the source asks for refined solves first (battery's Q3 band-edge
    points, quiz-registry-v8), they are stored owner-only
    (`quiz-refine.json`) and added to `jobs.json`, and the batch stays
    PENDING (`QUIZ_REFINE`) until the next `solve` and `seal` ingest them.
    A tick runs that second solve and seal at once;
  - the commitment gains `quiz_digest`, `quiz_references_digest` and
    `quiz_panel_version`, and the package payload `quiz: {document,
    references}`. It rotates and retires with its batch.
  Finalist batches carry no quiz, and a batch drawn without the config never
  gains one. The quiz is drawn and reported, and gates nothing (rule v3 is
  the owner's).
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import stat
import sys
from pathlib import Path

from .batch_source import (  # noqa: F401 - re-exported
    COMMITMENT_SCHEMA,
    QUIZ_COMMITMENT_FIELDS,
    SERVED_KINDS,
    BatchSource,
    ProducerRefused,
    quiz_digests,
)

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG_SCHEMA = "carbon.challenge-validator.producer-config.v1"
JOURNAL_SCHEMA = "carbon.challenge-validator.producer-journal.v1"


def require_approval(approval, *, repository=REPOSITORY):
    """A Challenge is produced only under the owner's approval record, named
    by its id and pinned by the sha256 of its decision file in this checkout
    (`.agent/decisions/`). Returns the record id."""
    if type(approval) is not dict or set(approval) != {"record", "file", "sha256"}:
        raise ProducerRefused("producer_challenge_not_approved")
    record, name = approval["record"], approval["file"]
    if (
        type(record) is not str
        or not record.startswith("OWNER-")
        or type(name) is not str
        or "/" in name
        or not name.endswith(".md")
    ):
        raise ProducerRefused("producer_challenge_not_approved")
    path = Path(repository) / ".agent" / "decisions" / name
    try:
        body = path.read_bytes()
    except OSError:
        raise ProducerRefused("producer_challenge_not_approved") from None
    if (
        hashlib.sha256(body).hexdigest() != approval["sha256"]
        or record.encode() not in body
    ):
        raise ProducerRefused("producer_challenge_not_approved")
    return record


def source_for(challenge_id, spec, *, repository=REPOSITORY):
    """The registered `BatchSource` for one configured, owner-approved
    Challenge."""
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        MOTOR_CHALLENGE,
    )

    require_approval(spec.get("approval"), repository=repository)

    if challenge_id == BATTERY_CHALLENGE:
        # Battery's source with its quiz (slice Q, part 2): it draws a quiz
        # only for a producer configured with one.
        from .battery_quiz import BatteryQuizSource

        return BatteryQuizSource.from_deployment(
            spec["deployment"], overlay=spec.get("overlay"), repository=repository
        )
    if challenge_id == MOTOR_CHALLENGE:
        # Motor's hidden pool (VALIDATOR-21): its solver image is pinned by
        # its hidden rule, so it takes no overlay.
        if "overlay" in spec:
            raise ProducerRefused("producer_config_malformed")
        from .motor_source import MotorBatchSource

        return MotorBatchSource(spec["deployment"], repository=repository)
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


def _replace_private(path, value):
    """Write an owner-only file, replacing a different earlier one whole."""
    path = Path(path)
    if path.exists() and _read_private(path) == value:
        return
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _quiz_config(value):
    return (
        value is None
        or type(value) is dict
        and set(value) == {"panel"}
        and type(value["panel"]) is str
        and bool(value["panel"])
    )


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
        or set(config) - keys - {"signing_key", "chain", "quiz"}
        or not _quiz_config(config.get("quiz"))
        or config["schema"] != CONFIG_SCHEMA
        or type(config["sources"]) is not dict
        or any(
            type(spec) is not dict
            or not {"deployment", "approval"} <= set(spec)
            or set(spec) - {"deployment", "overlay", "approval"}
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
            if (entry["event"], entry["challenge_id"], entry.get("fingerprint")) == (
                event,
                challenge_id,
                fingerprint,
            ):
                return entry
        return None


# --- the producer ---------------------------------------------------------------------


class Producer:
    """Draw, solve once, and seal batches for the configured Challenges."""

    def __init__(self, directory, sources, *, signing_key=None, quiz=None):
        self.directory = _owner_only_dir(directory)
        self.sources = {source.challenge_id: source for source in sources}
        self.journal = ProducerJournal(self.directory / "journal.jsonl")
        self.signing_key = signing_key
        if not _quiz_config(quiz):
            raise ProducerRefused("producer_config_malformed")
        #: `{"panel": PATH}` or None: without it, batches are drawn and sealed
        #: exactly as before slice Q, with no quiz fields.
        self.quiz = quiz

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
            quiz=config.get("quiz"),
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
            # A quiz is decided once, at the draw: only a screening batch,
            # only under the quiz config. The field is absent otherwise.
            quiz = {"quiz": True} if self.quiz and kind == "screening" else {}
            self.journal.append(
                "drawn",
                challenge_id=challenge_id,
                fingerprint=fingerprint,
                kind=kind,
                **quiz,
            )
        jobs = source.jobs(fingerprint)
        work = self._work(challenge_id, fingerprint)
        if not self._has_quiz(challenge_id, fingerprint):
            _write_once(work / "jobs.json", {"fingerprint": fingerprint, "jobs": jobs})
            return {"fingerprint": fingerprint, "jobs": len(jobs)}
        draws = self._quiz_draws(source, fingerprint, work)
        quiz_jobs = self._write_quiz_jobs(source, fingerprint, work, jobs, draws)
        return {"fingerprint": fingerprint, "jobs": len(jobs), "quiz_jobs": quiz_jobs}

    # --- the quiz (slice Q, part 2) -------------------------------------------

    QUIZ_DRAWS = "quiz-draws.json"
    QUIZ_FILE = "quiz.json"
    QUIZ_REFINE = "quiz-refine.json"

    def _has_quiz(self, challenge_id, fingerprint):
        drawn = self.journal.find("drawn", challenge_id, fingerprint)
        return bool(drawn and drawn.get("quiz"))

    def _quiz_draws(self, source, fingerprint, work, round_=None):
        """The batch's current quiz round `{"round", "draws"}` (round 1 at the
        first draw), regenerated and checked against the stored one; with
        `round_`, that round is drawn and stored."""
        path = work / self.QUIZ_DRAWS
        stored = _read_private(path) if path.exists() else None
        if round_ is None:
            round_ = 1 if stored is None else stored["round"]
        value = {"round": round_, "draws": source.quiz_draw(fingerprint, round_)}
        if stored is not None and stored["round"] == round_ and stored != value:
            raise ProducerRefused("producer_quiz_draws_changed")
        _replace_private(path, value)
        return value

    def _write_quiz_jobs(self, source, fingerprint, work, jobs, draws):
        """`jobs.json`: the batch's jobs, then the quiz round's, then any
        refined solves the source asked for (`quiz-refine.json`), so one
        solve runs them all. The solve is resumable, so a later round
        re-solves nothing."""
        quiz_jobs = source.quiz_jobs(draws["draws"])
        path = work / self.QUIZ_REFINE
        refine = _read_private(path)["jobs"] if path.exists() else []
        _replace_private(
            work / "jobs.json",
            {"fingerprint": fingerprint, "jobs": jobs + quiz_jobs + refine},
        )
        return len(quiz_jobs)

    def _quiz(self, challenge_id, fingerprint):
        """A selected quiz `{"document", "references"}`, or None."""
        path = self._work(challenge_id, fingerprint) / self.QUIZ_FILE
        return _read_private(path) if path.exists() else None

    def _select_quiz(self, source, challenge_id, fingerprint, work, draws, records):
        """Select the batch's quiz once; None when selected, else why the
        batch is still pending."""
        if (work / self.QUIZ_FILE).exists():
            return None
        if self.quiz is None:
            # Drawn with a quiz: never sealed without one.
            raise ProducerRefused("producer_quiz_not_configured")
        result = source.quiz_select(
            draws["draws"],
            records,
            panel=self.quiz["panel"],
            cache=self._private_dir("quiz-panel", challenge_id),
        )
        if "next_round" in result:
            round_ = result["next_round"]
            if type(round_) is not int or round_ <= draws["round"]:
                raise ProducerRefused("producer_quiz_round_malformed")
            advanced = self._quiz_draws(source, fingerprint, work, round_)
            self._write_quiz_jobs(
                source, fingerprint, work, source.jobs(fingerprint), advanced
            )
            if not any(
                e["event"] == "quiz_round"
                and e["challenge_id"] == challenge_id
                and e.get("fingerprint") == fingerprint
                and e.get("round") == round_
                for e in self.journal.entries()
            ):
                self.journal.append(
                    "quiz_round",
                    challenge_id=challenge_id,
                    fingerprint=fingerprint,
                    round=round_,
                )
            return "QUIZ_NEXT_ROUND"
        if "refine" in result:
            jobs = result["refine"]
            if type(jobs) is not list or not all(
                type(job) is dict and job.get("refined") is True for job in jobs
            ):
                raise ProducerRefused("producer_quiz_malformed")
            _replace_private(work / self.QUIZ_REFINE, {"jobs": jobs})
            self._write_quiz_jobs(
                source, fingerprint, work, source.jobs(fingerprint), draws
            )
            return "QUIZ_REFINE"
        if "pending" in result:
            return str(result["pending"])
        quiz = {"document": result["document"], "references": result["references"]}
        if type(quiz["document"].get("panel_version")) is not int:
            raise ProducerRefused("producer_quiz_malformed")
        _write_once(work / self.QUIZ_FILE, quiz)
        return None

    def _split_quiz_records(self, source, draws, records):
        """`(batch records, quiz records)`. A quiz record must have solved its
        own job's inputs."""
        jobs = {job["case_id"]: job for job in source.quiz_jobs(draws["draws"])}
        batch, quiz = [], []
        for record in records:
            job = jobs.get(record.get("case_id"))
            if job is None:
                batch.append(record)
                continue
            expected = {k: v for k, v in job.items() if k != "case_id"}
            if record.get("inputs") not in (None, expected):
                raise ProducerRefused("producer_quiz_records_mismatch")
            quiz.append(record)
        return batch, quiz

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
        quiz = self._has_quiz(challenge_id, fingerprint)
        if quiz:
            draws = self._quiz_draws(source, fingerprint, work)
            records, quiz_records = self._split_quiz_records(source, draws, records)
        if not source.ingest(fingerprint, records):
            return {"fingerprint": fingerprint, "state": "PENDING"}
        if quiz:
            waiting = self._select_quiz(
                source, challenge_id, fingerprint, work, draws, quiz_records
            )
            if waiting is not None:
                # The slot-unfilled logic applies as to any pending batch.
                return {"fingerprint": fingerprint, "state": "PENDING", "quiz": waiting}
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
        quiz = {}
        if self._has_quiz(source.challenge_id, fingerprint):
            # Private membership, public digests: committed with the batch.
            value = self._quiz(source.challenge_id, fingerprint)
            if value is None:
                raise ProducerRefused("producer_references_pending")
            quiz = {
                **quiz_digests(value),
                "quiz_panel_version": value["document"]["panel_version"],
            }
        return {
            **quiz,
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

    def withdraw(self, challenge_id, fingerprint, reason, *, block):
        """Withdraw one batch window (VALIDATOR-24): journaled, its package
        out of the outbox (the next push removes it from the distribution
        host), and a signed notice in `outbox/<challenge>/withdrawals/` that
        every validator applies before importing anything. Never undone, and
        never republished. Idempotent."""
        from .answer_key import AnswerKeyRefused, withdrawal_notice, write_private

        if self.signing_key is None:
            raise ProducerRefused("producer_no_signing_key")
        if self.journal.find("drawn", challenge_id, fingerprint) is None:
            raise ProducerRefused("producer_not_drawn")
        earlier = self.journal.find("withdrawn", challenge_id, fingerprint)
        if earlier is not None:
            reason, block = earlier["reason"], earlier["block"]
        try:
            value = withdrawal_notice(
                self.signing_key, challenge_id, fingerprint, reason, block
            )
        except AnswerKeyRefused as refused:
            raise ProducerRefused(refused.code) from None
        if earlier is None:
            self.journal.append(
                "withdrawn",
                challenge_id=challenge_id,
                fingerprint=fingerprint,
                reason=reason,
                block=block,
            )
        name = fingerprint.removeprefix("sha256:") + ".json"
        package = self.directory / "outbox" / challenge_id / name
        if package.exists():
            os.replace(package, self._private_dir("withdrawn", challenge_id) / name)
        notices = self._private_dir("outbox", challenge_id, "withdrawals")
        write_private(notices / name, value)
        return {"fingerprint": fingerprint, "reason": reason, "notice": name}

    def _withdrawn(self, challenge_id, fingerprint):
        return self.journal.find("withdrawn", challenge_id, fingerprint) is not None

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
        if self._withdrawn(challenge_id, fingerprint):
            raise ProducerRefused("producer_withdrawn")
        source = self._source(challenge_id)
        # Re-checked, so a batch changed after its seal is never published.
        source.check(fingerprint)
        if (
            source.sealed(fingerprint) is None
            or self._commitment(source, fingerprint) != sealed["commitment"]
        ):
            raise ProducerRefused("producer_commitment_changed")
        scheduled = self.journal.find("scheduled", challenge_id, fingerprint)
        if scheduled is None:
            # A validator activates a batch only by its window (slice 3).
            raise ProducerRefused("producer_not_scheduled")
        if self.journal.find("retired", challenge_id, fingerprint) is not None:
            raise ProducerRefused("producer_retired")
        commitment = {**sealed["commitment"], "window": scheduled["window"]}
        payload = source.export(fingerprint)
        if "quiz_digest" in commitment:
            # Checked above: the stored quiz still digests to the commitment.
            payload = {**payload, "quiz": self._quiz(challenge_id, fingerprint)}
        try:
            value = package(self.signing_key, commitment, payload)
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

    # --- rotation and retirement (slice 3) ------------------------------------

    def _cadence(self, challenge_id):
        cadence = self._source(challenge_id).cadence()
        if cadence is None:
            raise ProducerRefused("producer_no_cadence")
        return cadence

    @staticmethod
    def window(cadence, slot):
        every, active = cadence["every_blocks"], cadence["active"]
        return {
            "slot": slot,
            "activate_block": slot * every,
            "retire_block": (slot + active) * every,
        }

    def _scheduled(self, challenge_id, kind="screening"):
        """`{slot: fingerprint}` for one kind. Each slot holds one screening
        and one finalist batch, under the same window."""
        return {
            e["window"]["slot"]: e["fingerprint"]
            for e in self.journal.entries()
            if e["event"] == "scheduled"
            and e["challenge_id"] == challenge_id
            and e.get("kind", "screening") == kind
        }

    def schedule(self, challenge_id, fingerprint, slot, *, block):
        """Give a sealed batch one slot's window, before the window starts.
        A slot holds one batch and a batch one slot, for good."""
        if type(slot) is not int or type(block) is not int or slot < 0:
            raise ProducerRefused("producer_slot_malformed")
        sealed = self.journal.find("sealed", challenge_id, fingerprint)
        if sealed is None:
            raise ProducerRefused("producer_not_sealed")
        if self._withdrawn(challenge_id, fingerprint):
            raise ProducerRefused("producer_withdrawn")
        kind = sealed["commitment"]["kind"]
        window = self.window(self._cadence(challenge_id), slot)
        earlier = self.journal.find("scheduled", challenge_id, fingerprint)
        if earlier is not None:
            if earlier["window"] != window:
                raise ProducerRefused("producer_already_scheduled")
            return window
        if slot in self._scheduled(challenge_id, kind):
            raise ProducerRefused("producer_slot_taken")
        if window["activate_block"] <= block:
            # Never mid-window: a validator might already be scoring without it.
            raise ProducerRefused("producer_slot_started")
        self.journal.append(
            "scheduled",
            challenge_id=challenge_id,
            fingerprint=fingerprint,
            kind=kind,
            window=window,
        )
        return window

    def _retire(self, challenge_id, block):
        """Retire every scheduled batch whose window has ended."""
        retired = []
        for entry in self.journal.entries():
            if entry["event"] != "scheduled" or entry["challenge_id"] != challenge_id:
                continue
            fingerprint = entry["fingerprint"]
            if entry["window"]["retire_block"] > block or self.journal.find(
                "retired", challenge_id, fingerprint
            ):
                continue
            name = fingerprint.removeprefix("sha256:") + ".json"
            outbox = self.directory / "outbox" / challenge_id / name
            if outbox.exists():
                # Out of the outbox: the next push removes it from the
                # distribution host. Kept, owner-only, for the release
                # decision.
                destination = self._private_dir("retired", challenge_id) / name
                os.replace(outbox, destination)
            self.journal.append(
                "retired",
                challenge_id=challenge_id,
                fingerprint=fingerprint,
                block=block,
                # OWNER-BATTERY-3B-AND-EXPOSURE-01: retirement releases
                # nothing; the release decision is HUMAN_INPUT.
                release="HUMAN_INPUT",
            )
            retired.append(fingerprint)
        return retired

    def _fill(self, challenge_id, slot, block, role_prefix, kind="screening"):
        """One slot of one kind: an existing sealed batch, or a new one drawn,
        solved and sealed now; then scheduled and published. Returns its
        fingerprint, or None (recorded once) when it could not be filled."""
        scheduled = set(self._scheduled(challenge_id, kind).values())
        sealed = [
            e["fingerprint"]
            for e in self.journal.entries()
            if e["event"] == "sealed"
            and e["challenge_id"] == challenge_id
            and e["commitment"]["kind"] == kind
            and e["fingerprint"] not in scheduled
            and not self._withdrawn(challenge_id, e["fingerprint"])
        ]
        fingerprint = sealed[0] if sealed else None
        if fingerprint is None:
            drawn = self.draw(challenge_id, f"{role_prefix}{slot}", kind=kind)
            fingerprint = drawn["fingerprint"]
            if self.journal.find("sealed", challenge_id, fingerprint) is None:
                self.solve(challenge_id, fingerprint)
                result = self.seal(challenge_id, fingerprint)
                if result.get("quiz") == "QUIZ_REFINE":
                    # The quiz's refined solves were just added: solve them
                    # now rather than leave the slot to the next tick.
                    self.solve(challenge_id, fingerprint)
                    result = self.seal(challenge_id, fingerprint)
                if result.get("state") == "PENDING":
                    fingerprint = None
        if fingerprint is None:
            if not any(
                e["event"] == "slot_unfilled"
                and e["challenge_id"] == challenge_id
                and e.get("slot") == slot
                and e.get("kind", "screening") == kind
                for e in self.journal.entries()
            ):
                self.journal.append(
                    "slot_unfilled",
                    challenge_id=challenge_id,
                    slot=slot,
                    kind=kind,
                    block=block,
                )
            return None
        self.schedule(challenge_id, fingerprint, slot, block=block)
        self.publish(challenge_id, fingerprint)
        return fingerprint

    #: Each slot's finalist batch: one fresh set, consumed by the first final
    #: frozen while its window is live (`PoolStore.claim_finalist_set`).
    FINALIST_PREFIX = "pfinal-S"

    def tick(self, block, *, lead_slots=1, role_prefix="pscreen-S"):
        """One rotation step at finalized `block`, for every configured
        Challenge with a registered cadence. Idempotent at a given block.
        `lead_slots` is how many slots ahead are filled: an engineering value,
        never a scientific one."""
        if type(block) is not int or block < 0:
            raise ProducerRefused("producer_block_malformed")
        report = {}
        for challenge_id in sorted(self.sources):
            cadence = self.sources[challenge_id].cadence()
            if cadence is None:
                report[challenge_id] = {"cadence": None}
                continue
            retired = self._retire(challenge_id, block)
            current = block // cadence["every_blocks"]
            filled, unfilled = [], []
            finalists = {"filled": [], "unfilled": []}
            taken = self._scheduled(challenge_id)
            final_taken = self._scheduled(challenge_id, "finalist")
            finals = "finalist" in self.sources[challenge_id].kinds()
            for slot in range(current + 1, current + 1 + lead_slots):
                if slot not in taken:
                    result = self._fill(challenge_id, slot, block, role_prefix)
                    (filled if result else unfilled).append(slot)
                if finals and slot not in final_taken:
                    result = self._fill(
                        challenge_id, slot, block, self.FINALIST_PREFIX, "finalist"
                    )
                    finalists["filled" if result else "unfilled"].append(slot)
            report[challenge_id] = {
                "block": block,
                "slot": current,
                "retired": len(retired),
                "filled": filled,
                "unfilled": unfilled,
                "finalist": finalists,
            }
        return report

    def status(self):
        """Counts per Challenge; public values only."""
        counts = {}
        for entry in self.journal.entries():
            row = counts.setdefault(
                entry["challenge_id"], {"drawn": 0, "sealed": 0, "published": 0}
            )
            row[entry["event"]] = row.get(entry["event"], 0) + 1
        return {"challenges": counts}


def finalized_block(chain):
    """The chain's finalized head, for `tick` without `--block`."""
    from carbon.chain.models import ChainContext
    from carbon.chain.permits import PermitUnavailable
    from carbon.chain.permits import finalized_block as read

    if type(chain) is not dict:
        raise ProducerRefused("producer_no_chain")
    try:
        return read(ChainContext(**chain))
    except (PermitUnavailable, TypeError, ValueError):
        raise ProducerRefused("producer_chain_unavailable") from None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.producer")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("draw", "solve", "seal", "publish", "withdraw", "tick", "status"):
        command = sub.add_parser(name)
        command.add_argument("--config", required=True)
        if name in ("tick", "withdraw"):
            command.add_argument("--block", type=int)
        if name == "withdraw":
            command.add_argument("--reason", required=True)
        if name in ("status", "tick"):
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
        elif args.command == "withdraw":
            block = args.block
            if block is None:
                block = finalized_block(load_config(args.config).get("chain"))
            result = producer.withdraw(
                args.challenge, args.fingerprint, args.reason, block=block
            )
        elif args.command == "seal":
            result = producer.seal(args.challenge, args.fingerprint)
        elif args.command == "publish":
            result = producer.publish(args.challenge, args.fingerprint)
        elif args.command == "tick":
            block = args.block
            if block is None:
                block = finalized_block(load_config(args.config).get("chain"))
            result = producer.tick(block)
        else:
            result = producer.status()
    except ProducerRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
