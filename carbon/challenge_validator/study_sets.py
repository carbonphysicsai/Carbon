"""Training-budget study sets, made on the producer host (TRAINING-BUDGET-01
slice 2b; OWNER-COMPUTE-BUDGET-01).

**VM-only (S11).** Every command runs on the producer VM, as its configured
service account, and nowhere else: never on a pod, a laptop or rented
compute. The study root, the sets' inputs and the sealed confirmation set
never leave that host except through `export` and `release-confirmation`,
which write owner-only files for the operator to carry to the study pod.

    python -m carbon.challenge_validator.study_sets init --spec SPEC
    python -m carbon.challenge_validator.study_sets draw --spec SPEC
    python -m carbon.challenge_validator.study_sets jobs --spec SPEC --set SET
    python -m carbon.challenge_validator.study_sets solve --spec SPEC --set SET
    python -m carbon.challenge_validator.study_sets ingest --spec SPEC --set SET
    python -m carbon.challenge_validator.study_sets manifest --spec SPEC --set SET
    python -m carbon.challenge_validator.study_sets export --spec SPEC --out DIR
    python -m carbon.challenge_validator.study_sets release-confirmation \\
        --spec SPEC --harness-journal PATH --out DIR

`SET` is `train`, `eval` or `confirm`. The spec is an owner-only JSON file
outside the repository (`SPEC_SCHEMA`). It names the service account, the
Challenge, the study directory, the sizes, the private prior files, the
owner's approval record and the truth overlay. Its sizes come from the
Challenge's study sheet. A size that is null or `HUMAN_INPUT` refuses every
command that needs it (fail closed); nothing here chooses a size.

- **The study root** is separate from every live root: `<study_dir>/root.bin`,
  32 bytes, owner-only, made once by `init`. Beside it is the study journal
  (`journal.jsonl`, owner-only, append-only, one sequence number per entry,
  public values only), whose first entry commits the root and its seed pin.
- **Three sets, each under its own reserved role**
  (`interface.STUDY_ROLES`): `train` draws indices `0..N_max-1`, so every
  ladder size is a prefix of the next; `eval` draws `eval_cases`; `confirm`
  draws `confirm_cases`. `N_max` is the largest ladder multiple times the
  current TRAIN size, and is refused above `generation_ceiling`. A ladder
  size that is not a whole number of cases is refused, never rounded.
- **Overlap before any use** (`draw`), with `confirmation.overlap_check`.
  Each set is checked against every published case of the Challenge (and
  its public decision cases, where the source has them), every private prior
  file the spec names (the live pool, the tuning and confirmation sets, EV5),
  and the other two study sets. Any overlap stops the draw: nothing is
  committed, and the typed refusal names only the prior.
- **Commit before use.** Each set's fingerprint (sha256 of its canonical
  document) is in the journal before any job, export or release. Every later
  command regenerates the set from the root and checks it against that
  fingerprint.
- **References** come from the Challenge's own truth service: `jobs` writes
  the distinct jobs owner-only, `solve` runs the pinned solve
  (`study_solve_command`, with an injectable runner), and `ingest` reads
  `records.jsonl`. Its references digest is computed as
  `PoolStore.complete_references` computes one. A case whose reference is
  not OK is withdrawn for every model: it stays in the export with its
  status, is listed as withdrawn, and is counted. It is never dropped.
- **Manifest** (`MANIFEST_SCHEMA`): public values only. No case id, input,
  seed or reference.
- **Export** writes the TRAIN and eval sets' inputs and references,
  owner-only, for the study pod.
- **The confirmation set stays sealed.** `release-confirmation` writes its
  inputs and references only when the given harness journal records
  `limit_frozen` and then `confirmation_opened`. It releases once: the study
  journal records the release, and a second one is refused.

DEVELOPMENT only: no score, weight, reward, qualification or LIVE authority.
Not a security audit (AGENTS.md section 13).
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import pwd
import stat
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from .confirmation import ConfirmationRefused, load_private_priors, overlap_check
from .interface import (
    STUDY_CONFIRM_ROLE,
    STUDY_EVAL_ROLE,
    STUDY_TRAIN_ROLE,
    digest,
)

REPOSITORY = Path(__file__).resolve().parents[2]
SPEC_SCHEMA = "carbon.training-budget.study-set-spec.v1"
JOURNAL_SCHEMA = "carbon.training-budget.study-set-journal.v1"
DOCUMENT_SCHEMA = "carbon.training-budget.study-set-document.v1"
MANIFEST_SCHEMA = "carbon.training-budget.study-set.v1"
EXPORT_SCHEMA = "carbon.training-budget.study-set-export.v1"
#: The study harness's journal (slice 2a), read as JSON lines only.
HARNESS_JOURNAL_SCHEMA = "carbon.training-budget.study-journal.v1"
HUMAN_INPUT = "HUMAN_INPUT"

ROLES = {
    "train": STUDY_TRAIN_ROLE,
    "eval": STUDY_EVAL_ROLE,
    "confirm": STUDY_CONFIRM_ROLE,
}
SETS = tuple(ROLES)
#: The sets `export` writes; `confirm` leaves only by `release_confirmation`.
EXPORTED = ("train", "eval")
#: Truth-service statuses that end a case (`truth.TERMINAL`); only OK may
#: enter a score. FAILED_INFRA is never a reference: the solve retries it.
TERMINAL = frozenset({"OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT"})
OK = "OK"

#: Values the owner's sheet and records supply. Each refuses while null or
#: HUMAN_INPUT.
SIZE_FIELDS = (
    "train_size",
    "train_size_ladder",
    "generation_ceiling",
    "eval_cases",
    "confirm_cases",
)
HUMAN_INPUT_FIELDS = ("approval", *SIZE_FIELDS, "private_priors")
_SPEC_KEYS = {
    "schema",
    "service_account",
    "challenge_id",
    "study_dir",
    "truth_overlay",
    *HUMAN_INPUT_FIELDS,
}


class StudyRefused(ValueError):
    """A typed refusal. Its code names no case, input, seed or root."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _file_digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _unset(value):
    return value is None or value == HUMAN_INPUT


# --- owner-only files -----------------------------------------------------------------


def _outside_repository(path, what):
    resolved = Path(path).resolve()
    root = REPOSITORY.resolve()
    if resolved == root or root in resolved.parents:
        raise StudyRefused(what + "_inside_repository")
    return resolved


def _owner_only(path, *, directory=False):
    try:
        info = os.lstat(path)
    except OSError:
        raise StudyRefused("study_file_missing") from None
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if stat.S_ISLNK(info.st_mode) or not kind(info.st_mode):
        raise StudyRefused("study_file_not_a_plain_path")
    if info.st_mode & 0o077:
        raise StudyRefused("study_file_not_owner_only")


def _private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, exist_ok=True)
    _owner_only(path, directory=True)
    return path


def _read_private(path):
    _owner_only(path)
    try:
        return json.loads(Path(path).read_bytes())
    except ValueError:
        raise StudyRefused("study_file_malformed") from None


def _write_once(path, value):
    """Write an owner-only file once; an existing one must hold `value`."""
    path = Path(path)
    if path.exists():
        if _read_private(path) != value:
            raise StudyRefused("study_file_changed")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(_canonical(value) + "\n")


# --- the spec -------------------------------------------------------------------------


def load_spec(path, *, account=None):
    """The study-set spec: owner-only, outside the repository, exact keys,
    and loaded only under its configured service account."""
    path = _outside_repository(path, "study_spec")
    try:
        spec = _read_private(path)
    except StudyRefused as refused:
        if refused.code == "study_file_missing":
            raise StudyRefused("study_spec_missing") from None
        raise
    if (
        type(spec) is not dict
        or set(spec) != _SPEC_KEYS
        or spec["schema"] != SPEC_SCHEMA
        or type(spec["challenge_id"]) is not str
        or not spec["challenge_id"]
        or type(spec["study_dir"]) is not str
        or not spec["study_dir"]
        or (
            spec["truth_overlay"] is not None and type(spec["truth_overlay"]) is not str
        )
    ):
        raise StudyRefused("study_spec_malformed")
    account = account or pwd.getpwuid(os.geteuid()).pw_name
    if type(spec["service_account"]) is not str or spec["service_account"] != account:
        raise StudyRefused("study_wrong_account")
    _outside_repository(spec["study_dir"], "study_dir")
    return spec


def _positive_int(value):
    return type(value) is int and value >= 1


def _positive_number(value):
    return type(value) in (int, float) and value > 0


def require(spec, fields):
    """Refuse while any of `fields` is null or HUMAN_INPUT; then check each
    value's shape. Never fills a value in."""
    missing = [name for name in fields if _unset(spec[name])]
    if missing:
        raise StudyRefused("study_human_input_missing:" + ",".join(missing))
    checks = {
        "approval": lambda v: type(v) is dict,
        "train_size": _positive_int,
        "train_size_ladder": lambda v: type(v) is list
        and bool(v)
        and all(_positive_number(x) for x in v),
        "generation_ceiling": _positive_number,
        "eval_cases": _positive_int,
        "confirm_cases": _positive_int,
        "private_priors": lambda v: type(v) is dict
        and bool(v)
        and all(type(k) is str and k and type(p) is str and p for k, p in v.items()),
    }
    for name in fields:
        if not checks[name](spec[name]):
            raise StudyRefused("study_spec_value_malformed:" + name)


def ladder(spec):
    """`[(position, multiple, size)]`: each ladder multiple times the current
    TRAIN size, a whole number of cases, strictly increasing; refused above
    the generation ceiling."""
    require(spec, ("train_size", "train_size_ladder", "generation_ceiling"))
    rungs, previous = [], 0
    for position, multiple in enumerate(spec["train_size_ladder"]):
        # Read as the decimal the sheet wrote (0.5, not its binary float).
        size = Fraction(str(multiple)) * spec["train_size"]
        if size.denominator != 1:
            raise StudyRefused("study_ladder_size_not_whole")
        if size <= previous:
            raise StudyRefused("study_ladder_not_increasing")
        rungs.append((position, multiple, int(size)))
        previous = size
    if rungs[-1][2] > spec["generation_ceiling"]:
        raise StudyRefused("study_generation_ceiling_exceeded")
    return rungs


# --- the study journal ----------------------------------------------------------------


class StudyJournal:
    """Append-only, owner-only journal of public values, sequence-numbered."""

    def __init__(self, path):
        self.path = Path(path)

    def entries(self):
        _owner_only(self.path)
        lines = self.path.read_text().splitlines()
        return [json.loads(line) for line in lines if line]

    def append(self, kind, **fields):
        entry = {
            "schema": JOURNAL_SCHEMA,
            "sequence": len(self.entries()),
            "kind": kind,
            **fields,
        }
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        with os.fdopen(fd, "a") as handle:
            handle.write(_canonical(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    def find(self, kind, name=None):
        for entry in self.entries():
            if entry["kind"] == kind and (name is None or entry.get("set") == name):
                return entry
        return None


# --- the study sets -------------------------------------------------------------------


def _document(challenge_id, name, cases):
    return {
        "schema": DOCUMENT_SCHEMA,
        "challenge": challenge_id,
        "set": name,
        "role": ROLES[name],
        "cases": [{"case_id": c, "inputs": dict(x)} for c, x in cases],
    }


def _refusal(refused):
    """A confirmation refusal from `overlap_check` or a prior file, as the
    study's own; the code names only the prior."""
    code = refused.code
    for old, new in (
        ("confirmation_overlaps_prior:", "study_overlaps_prior:"),
        ("confirmation_private_prior_", "study_private_prior_"),
        ("confirmation_fresh_draws_collide", "study_draws_collide"),
        # `load_private_priors` checks each prior file as custody files are.
        ("confirmation_custody_", "study_private_prior_"),
    ):
        if code.startswith(old):
            return StudyRefused(new + code[len(old) :])
    return StudyRefused("study_" + code)


class _Priors:
    """The spec's private priors, shaped as `load_private_priors` reads a
    registered set: every name the spec gives is required."""

    def __init__(self, names):
        self.required_private_priors = tuple(sorted(names))


class StudySets:
    """The three study sets of one Challenge, in one owner-only directory."""

    def __init__(self, spec, *, repository=REPOSITORY, runner=None):
        from .confirmation_sources import source_for

        self.spec = spec
        self.challenge_id = spec["challenge_id"]
        self.repository = Path(repository)
        self.runner = runner
        self.directory = _outside_repository(spec["study_dir"], "study_dir")
        try:
            self.source = source_for(self.challenge_id)
        except ConfirmationRefused:
            raise StudyRefused("study_challenge_not_served") from None
        if not all(
            hasattr(self.source, name)
            for name in ("study_root", "study_seed_pin", "study_draws")
        ):
            raise StudyRefused("study_challenge_not_served")
        self.journal = StudyJournal(self.directory / "journal.jsonl")

    @classmethod
    def from_spec(cls, path, *, account=None, repository=REPOSITORY, runner=None):
        return cls(
            load_spec(path, account=account), repository=repository, runner=runner
        )

    # --- custody ---------------------------------------------------------------------

    def _approved(self):
        from .producer import ProducerRefused, require_approval

        require(self.spec, ("approval",))
        try:
            return require_approval(self.spec["approval"], repository=self.repository)
        except ProducerRefused:
            raise StudyRefused("study_not_approved") from None

    def init(self):
        """Create the study directory, root and journal once. Never
        overwrites; returns the root's public commitment."""
        record = self._approved()
        if self.directory.exists():
            raise StudyRefused("study_dir_exists")
        self.directory.mkdir(parents=True, mode=0o700)
        self.directory.chmod(0o700)
        root = self.source.study_root(self.directory / "root.bin", create=True)
        fd = os.open(
            self.directory / "journal.jsonl",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.close(fd)
        entry = self.journal.append(
            "root",
            challenge=self.challenge_id,
            root_commitment=root.commitment(),
            seed_pin=self.source.study_seed_pin(self.repository),
            approval=record,
        )
        return {
            "challenge_id": self.challenge_id,
            "root_commitment": entry["root_commitment"],
            "journal_sequence": entry["sequence"],
        }

    def _open(self):
        """The root and its committed seed pin, every file checked."""
        _owner_only(self.directory, directory=True)
        path = self.directory / "root.bin"
        _owner_only(path)
        try:
            root = self.source.study_root(path)
        except ValueError:
            raise StudyRefused("study_root_malformed") from None
        entries = self.journal.entries()
        first = entries[0] if entries else None
        if (
            first is None
            or first.get("kind") != "root"
            or first.get("challenge") != self.challenge_id
            or first.get("root_commitment") != root.commitment()
        ):
            raise StudyRefused("study_root_not_committed")
        return root, first["seed_pin"]

    @contextlib.contextmanager
    def _writer(self):
        _owner_only(self.directory, directory=True)
        fd = os.open(self.directory / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    # --- drawing ---------------------------------------------------------------------

    def _sizes(self):
        """Each set's case count, from the spec; refused while any is unset."""
        rungs = ladder(self.spec)
        require(self.spec, ("eval_cases", "confirm_cases"))
        return {
            "train": rungs[-1][2],
            "eval": self.spec["eval_cases"],
            "confirm": self.spec["confirm_cases"],
        }, rungs

    def _draw(self, root, pin, name, count):
        return [
            (case_id, dict(inputs))
            for case_id, inputs in self.source.study_draws(
                root, pin, ROLES[name], count
            )
        ]

    def documents(self, root, pin, sizes):
        """Every set's private document, in draw order. Private: in memory on
        the producer host only."""
        return {
            name: _document(self.challenge_id, name, self._draw(root, pin, name, count))
            for name, count in sizes.items()
        }

    def _rungs_public(self, document, rungs):
        return [
            {
                "position": position,
                "multiple": multiple,
                "size": size,
                "fingerprint": digest({**document, "cases": document["cases"][:size]}),
            }
            for position, multiple, size in rungs
        ]

    def _priors(self):
        """`(keys by prior name, private file digests)` for the overlap
        check: published cases, public decision cases where the source has
        them, and every private prior file the spec names."""
        require(self.spec, ("private_priors",))
        supplied = self.spec["private_priors"]
        try:
            private, digests = load_private_priors(
                _Priors(supplied), self.source, supplied
            )
        except ConfirmationRefused as refused:
            raise _refusal(refused) from None
        priors = {"published": self.source.published(self.repository), **private}
        if hasattr(self.source, "public_decision"):
            priors["public_decision"] = self.source.public_decision(self.repository)
        return priors, digests

    def draw(self):
        """Draw all three sets, check every overlap, and commit each set's
        fingerprint before any use. Idempotent; a changed set is refused."""
        self._approved()
        sizes, rungs = self._sizes()
        with self._writer():
            root, pin = self._open()
            documents = self.documents(root, pin, sizes)
            fingerprints = {name: digest(doc) for name, doc in documents.items()}
            committed = {name: self.journal.find("set", name) for name in SETS}
            for name, entry in committed.items():
                if entry is not None and entry["fingerprint"] != fingerprints[name]:
                    raise StudyRefused("study_set_changed:" + name)
            priors, digests = self._priors()
            keys = {
                name: {
                    case["case_id"]: case["inputs"] for case in documents[name]["cases"]
                }
                for name in SETS
            }
            checked = {}
            for name in SETS:
                others = {
                    "study:" + other: {self.source.key(x) for x in keys[other].values()}
                    for other in SETS
                    if other != name
                }
                try:
                    checked[name] = overlap_check(
                        self.source, keys[name], {**priors, **others}, {}
                    )
                except ConfirmationRefused as refused:
                    raise _refusal(refused) from None
            result = {}
            for name in SETS:
                entry = committed[name]
                if entry is None:
                    extra = {}
                    if name == "train":
                        extra["ladder"] = self._rungs_public(documents[name], rungs)
                    entry = self.journal.append(
                        "set",
                        challenge=self.challenge_id,
                        set=name,
                        role=ROLES[name],
                        size=sizes[name],
                        fingerprint=fingerprints[name],
                        overlap={
                            "verdict": "NO_OVERLAP",
                            "priors": checked[name],
                            "private_prior_digests": digests,
                        },
                        **extra,
                    )
                result[name] = {
                    "fingerprint": entry["fingerprint"],
                    "journal_sequence": entry["sequence"],
                    "newly_committed": committed[name] is None,
                }
        return result

    def _committed(self, name):
        """`(entry, document)`: the set regenerated from the root and checked
        against the fingerprint committed before any use."""
        if name not in ROLES:
            raise StudyRefused("study_set_unknown")
        entry = self.journal.find("set", name)
        if entry is None:
            raise StudyRefused("study_set_not_committed:" + name)
        root, pin = self._open()
        document = _document(
            self.challenge_id, name, self._draw(root, pin, name, entry["size"])
        )
        if digest(document) != entry["fingerprint"]:
            raise StudyRefused("study_set_regeneration_mismatch:" + name)
        return entry, document

    # --- references ------------------------------------------------------------------

    def _work(self, name):
        return _private_dir(_private_dir(self.directory / "work") / name)

    def jobs(self, name):
        """Write the set's distinct solve jobs, owner-only."""
        entry, document = self._committed(name)
        jobs = [{"case_id": c["case_id"], **c["inputs"]} for c in document["cases"]]
        if len({_canonical(c["inputs"]) for c in document["cases"]}) != len(jobs):
            # The overlap check refused colliding draws; this cannot repeat.
            raise StudyRefused("study_draws_collide:" + name)
        _write_once(
            self._work(name) / "jobs.json",
            {"fingerprint": entry["fingerprint"], "jobs": jobs},
        )
        return {"set": name, "fingerprint": entry["fingerprint"], "jobs": len(jobs)}

    def solve(self, name, *, workers=7, timeout_s=1200.0):
        """The Challenge's pinned truth solve of the set's jobs. Resumable."""
        self._committed(name)
        work = self._work(name)
        if not (work / "jobs.json").exists():
            raise StudyRefused("study_jobs_not_written")
        overlay = self.spec["truth_overlay"]
        if overlay is None or not hasattr(self.source, "study_solve_command"):
            raise StudyRefused("study_no_truth_overlay")
        records = work / "records.jsonl"
        if not records.exists():
            records.touch(mode=0o600)
        _owner_only(records)
        command = self.source.study_solve_command(
            overlay,
            work,
            repository=self.repository,
            workers=workers,
            timeout_s=timeout_s,
        )
        completed = (self.runner or subprocess.run)(command, check=False)
        return {"set": name, "returncode": completed.returncode}

    def _records(self, name, document):
        """`{case_id: record}`: each case's first terminal record, as
        `PoolStore.record_references` keeps it. A record that solved other
        inputs, or names a case outside the set, refuses the file."""
        path = self._work(name) / "records.jsonl"
        if not path.exists():
            return {}
        _owner_only(path)
        cases = {c["case_id"]: c["inputs"] for c in document["cases"]}
        found = {}
        for line in path.read_text().splitlines():
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                raise StudyRefused("study_records_malformed") from None
            if type(record) is not dict:
                raise StudyRefused("study_records_malformed")
            case_id = record.get("case_id")
            if case_id not in cases:
                raise StudyRefused("study_records_name_another_case")
            if record.get("inputs") not in (None, cases[case_id]):
                raise StudyRefused("study_records_inputs_mismatch")
            if record.get("status") not in TERMINAL or record.get("refined"):
                continue
            found.setdefault(case_id, record)
        return found

    @staticmethod
    def _references_digest(records, case_ids):
        """`PoolStore.complete_references`'s digest over these cases."""
        body = _canonical([[c, records[c]] for c in sorted(case_ids)])
        return "sha256:" + hashlib.sha256(body.encode()).hexdigest()

    def ingest(self, name):
        """Read the set's records. Once every case has a terminal record,
        commit its references digest and withdrawn count; until then,
        PENDING. A reference that is not OK is withdrawn for every model."""
        with self._writer():
            entry, document = self._committed(name)
            records = self._records(name, document)
            ids = [c["case_id"] for c in document["cases"]]
            missing = sum(1 for c in ids if c not in records)
            if missing:
                return {"set": name, "state": "PENDING", "missing": missing}
            value = {
                "fingerprint": entry["fingerprint"],
                "references_digest": self._references_digest(records, ids),
                "withdrawn": sum(1 for c in ids if records[c]["status"] != OK),
            }
            if name == "train":
                value["ladder"] = [
                    {
                        "position": rung["position"],
                        "references_digest": self._references_digest(
                            records, ids[: rung["size"]]
                        ),
                        "withdrawn": sum(
                            1 for c in ids[: rung["size"]] if records[c]["status"] != OK
                        ),
                    }
                    for rung in entry["ladder"]
                ]
            earlier = self.journal.find("references", name)
            if earlier is not None:
                if {k: earlier.get(k) for k in value} != value:
                    raise StudyRefused("study_references_changed:" + name)
                return {"set": name, "state": "COMPLETE", **value}
            _write_once(
                self._work(name) / "references.json",
                {
                    "fingerprint": entry["fingerprint"],
                    "references_digest": value["references_digest"],
                    "records": records,
                },
            )
            self.journal.append(
                "references", challenge=self.challenge_id, set=name, **value
            )
        return {"set": name, "state": "COMPLETE", **value}

    def _references(self, name, entry, document):
        """The stored references, checked against the committed digest."""
        committed = self.journal.find("references", name)
        if committed is None:
            raise StudyRefused("study_references_pending:" + name)
        stored = _read_private(self._work(name) / "references.json")
        ids = [c["case_id"] for c in document["cases"]]
        records = stored.get("records")
        if (
            stored.get("fingerprint") != entry["fingerprint"]
            or type(records) is not dict
            or set(records) != set(ids)
            or self._references_digest(records, ids) != committed["references_digest"]
        ):
            raise StudyRefused("study_references_changed:" + name)
        return records

    # --- the public manifest ---------------------------------------------------------

    def manifest(self, name):
        """The public manifest of one set: no case id, input, seed or
        reference."""
        if name not in ROLES:
            raise StudyRefused("study_set_unknown")
        entry = self.journal.find("set", name)
        if entry is None:
            raise StudyRefused("study_set_not_committed:" + name)
        references = self.journal.find("references", name)
        value = {
            "schema": MANIFEST_SCHEMA,
            "challenge": self.challenge_id,
            "set": name,
            "role": entry["role"],
            "size": entry["size"],
            "fingerprint": entry["fingerprint"],
            "references_digest": (
                None if references is None else (references["references_digest"])
            ),
            "withdrawn": None if references is None else references["withdrawn"],
            "overlap": {
                "verdict": entry["overlap"]["verdict"],
                "priors": sorted(entry["overlap"]["priors"]),
                "private_prior_digests": entry["overlap"]["private_prior_digests"],
            },
            "journal_sequence": entry["sequence"],
            "evidence": "DEVELOPMENT",
        }
        if name == "train":
            by_position = {
                r["position"]: r for r in (references or {}).get("ladder", [])
            }
            value["ladder"] = [
                {
                    **rung,
                    "references_digest": by_position.get(rung["position"], {}).get(
                        "references_digest"
                    ),
                    "withdrawn": by_position.get(rung["position"], {}).get("withdrawn"),
                }
                for rung in entry["ladder"]
            ]
        if name == "confirm":
            released = self.journal.find("confirmation_released")
            value["released_sequence"] = (
                None if released is None else (released["sequence"])
            )
        return value

    # --- export and release ----------------------------------------------------------

    def _payload(self, name):
        entry, document = self._committed(name)
        records = self._references(name, entry, document)
        return {
            "schema": EXPORT_SCHEMA,
            "manifest": self.manifest(name),
            "cases": document["cases"],
            "references": records,
            "withdrawn": sorted(c for c, r in records.items() if r["status"] != OK),
        }

    def export(self, out):
        """Write the TRAIN and eval sets for the study pod, owner-only. Never
        the confirmation set."""
        out = _private_dir(_outside_repository(out, "study_export"))
        with self._writer():
            payloads = {name: self._payload(name) for name in EXPORTED}
            result = {}
            for name, payload in payloads.items():
                path = out / f"{name}.json"
                _write_once(path, payload)
                file_digest = _file_digest(path)
                earlier = [
                    e
                    for e in self.journal.entries()
                    if e["kind"] == "exported"
                    and e["set"] == name
                    and e["file_digest"] == file_digest
                ]
                entry = (
                    earlier[0]
                    if earlier
                    else self.journal.append(
                        "exported",
                        challenge=self.challenge_id,
                        set=name,
                        fingerprint=payload["manifest"]["fingerprint"],
                        file_digest=file_digest,
                    )
                )
                result[name] = {
                    "file": path.name,
                    "file_digest": file_digest,
                    "journal_sequence": entry["sequence"],
                }
        return result

    def _harness_opened_confirmation(self, path):
        """Whether the harness journal at `path` records `limit_frozen` and
        then `confirmation_opened`, for this Challenge. Its digest."""
        try:
            body = Path(path).read_bytes()
            events = [json.loads(line) for line in body.decode().splitlines() if line]
        except (OSError, ValueError):
            raise StudyRefused("study_harness_journal_unreadable") from None
        if not events or any(
            type(e) is not dict or e.get("schema") != HARNESS_JOURNAL_SCHEMA
            for e in events
        ):
            raise StudyRefused("study_harness_journal_malformed")
        kinds = [e.get("event") for e in events]
        if kinds[0] != "opened" or events[0].get("challenge") != self.challenge_id:
            raise StudyRefused("study_harness_journal_names_another_challenge")
        if "limit_frozen" not in kinds:
            raise StudyRefused("study_limit_not_frozen")
        if "confirmation_opened" not in kinds:
            raise StudyRefused("study_confirmation_not_opened")
        if kinds.index("confirmation_opened") < kinds.index("limit_frozen"):
            raise StudyRefused("study_confirmation_opened_before_limit")
        return "sha256:" + hashlib.sha256(body).hexdigest()

    def release_confirmation(self, harness_journal, out):
        """Release the sealed confirmation set once, after the harness froze L
        and opened the confirmation set."""
        out = _private_dir(_outside_repository(out, "study_export"))
        with self._writer():
            if self.journal.find("confirmation_released") is not None:
                raise StudyRefused("study_confirmation_already_released")
            harness = self._harness_opened_confirmation(harness_journal)
            payload = self._payload("confirm")
            path = out / "confirm.json"
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                raise StudyRefused("study_release_file_exists") from None
            with os.fdopen(fd, "w") as handle:
                handle.write(_canonical(payload) + "\n")
            entry = self.journal.append(
                "confirmation_released",
                challenge=self.challenge_id,
                set="confirm",
                fingerprint=payload["manifest"]["fingerprint"],
                file_digest=_file_digest(path),
                harness_journal_digest=harness,
            )
        return {
            "file": path.name,
            "file_digest": entry["file_digest"],
            "journal_sequence": entry["sequence"],
        }


# --- command line ---------------------------------------------------------------------


def main(argv=None, *, runner=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.study_sets",
        description="Training-budget study sets (producer VM only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "init",
        "draw",
        "jobs",
        "solve",
        "ingest",
        "manifest",
        "export",
        "release-confirmation",
    ):
        command = sub.add_parser(name)
        command.add_argument("--spec", required=True)
        if name in ("jobs", "solve", "ingest", "manifest"):
            command.add_argument("--set", required=True, choices=SETS)
        if name == "solve":
            command.add_argument("--workers", type=int, default=7)
            command.add_argument("--timeout-s", type=float, default=1200.0)
        if name in ("export", "release-confirmation"):
            command.add_argument("--out", required=True)
        if name == "release-confirmation":
            command.add_argument("--harness-journal", required=True)
    args = parser.parse_args(argv)
    try:
        study = StudySets.from_spec(args.spec, runner=runner)
        if args.command == "init":
            result = study.init()
        elif args.command == "draw":
            result = study.draw()
        elif args.command == "jobs":
            result = study.jobs(args.set)
        elif args.command == "solve":
            result = study.solve(
                args.set, workers=args.workers, timeout_s=args.timeout_s
            )
        elif args.command == "ingest":
            result = study.ingest(args.set)
        elif args.command == "manifest":
            result = study.manifest(args.set)
        elif args.command == "export":
            result = study.export(args.out)
        else:
            result = study.release_confirmation(args.harness_journal, args.out)
    except StudyRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
