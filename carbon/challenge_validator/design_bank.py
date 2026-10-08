"""Challenge-neutral design-question banks (VALIDATOR-23 slice 3a;
OWNER-BANK-ARCHITECTURE-01). Producer-only: no validator surface imports it.

A design bank is a `BankLedger` bank named `design:<id>`, and one bank case is
one design question:
- `case_id` is the question id;
- `inputs` are `{"task", "task_digest", "draw"}`: the frozen design task
  (plain `carbon.design-task.v2` or indexed `carbon.design-task.indexed.v1`),
  its digest, and the question law's own draw record;
- `reference` is the score bridge's reference for it
  (`{"status": "OK", "panel"}` or `{"status": "OK", "per_index"}`), or a
  terminal status the law names for a question that is not asked (for
  example, no feasible design). Only `OK` goes live.

A Challenge supplies one `QuestionLaw`. The bank core draws, seals, proves,
counts exposure and releases without knowing the Challenge. Each question is
solved once, at tranche seal, through the law's stages: every stage's jobs go
to the Challenge's pinned truth solve, resumably.

**Exposure E counts every question draw.** Each window that serves a
question adds one exposure (`BankLedger.draw_window`), whether the window is
screening or finalist, and whether or not it is later voided. At E, the
question retires into the training release.

**Values** (`DESIGN_BANKS`): the Test Lead's development working values
(slice 3 decision D2, 2026-10-08). `k` is a registered parameter, never a
constant in code.

    python -m carbon.challenge_validator.design_bank fill --config PRODUCER.json --bank battery-q3 --dir BANK_DIR [--workers 6] [--live N]

`--live N` fills toward N live questions only (at most the registered size):
a partial first tranche, the registered target B unchanged. Battery Q3's
first tranche is 24 live (3 windows of k = 8), the Test Lead's direction of
2026-10-08: a machinery rehearsal, since battery v3's charge map replaces
the v8 decision and its full startup is sized for v3.
    python -m carbon.challenge_validator.design_bank status --config PRODUCER.json --bank battery-q3 --dir BANK_DIR

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import abc
import argparse
import json
import os
import stat
import sys
from pathlib import Path

from .bank import BankLedger, BankRefused, BankSource
from .batch_source import ProducerRefused

PREFIX = "design:"
#: Each registered design bank's working values: questions per window `k`,
#: live size `size` (B) and the exposure `retire_at` (E). Development working
#: values, the Test Lead's slice 3 decision D2 (2026-10-08): a single batch's
#: 8 questions cannot separate a bad control on their own, so `k` may rise,
#: and per-miner evidence accumulates across batches (slice 3c).
DESIGN_BANKS = {
    "battery-q3": {
        "k": 8,
        "size": 160,
        "retire_at": 5,
        "values": "DEVELOPMENT_WORKING_VALUES",
    },
}


class QuestionLaw(abc.ABC):
    """One Challenge's design questions: how they are drawn, solved and
    answered. `name` is the bank's id (the bank is `design:<name>`)."""

    name: str
    challenge_id: str
    #: Terminal reference statuses; `OK` is the only live one.
    terminal: tuple = ("OK",)

    @abc.abstractmethod
    def draw(self, role, count):
        """`[{"question_id", "task", "draw"}]`: `count` questions,
        deterministic from the producer's root under `role`, each with its
        frozen task (task digest included)."""

    @abc.abstractmethod
    def next_stage(self, questions, work):
        """`(subdirectory, jobs)` for the next stage with unsolved truth jobs,
        or None once every stage is solved. `questions` maps each unsolved
        question id to its bank inputs; solve records are read from `work`."""

    @abc.abstractmethod
    def references(self, questions, work):
        """`{question id: reference}` once every stage is solved: a bridge
        reference with status `OK`, or another terminal status."""

    def stratum(self, inputs):
        return "all"


def _verify_task(task):
    """The task's digest, re-derived; a malformed task is refused."""
    from carbon.design_search import indexed, tasks

    try:
        if type(task) is dict and task.get("schema") == tasks.INDEXED_SCHEMA:
            indexed.validate_indexed(task)
        else:
            tasks._verify_task_digest(task)
    except (tasks.TaskError, ValueError, TypeError, KeyError):
        raise BankRefused("bank_design_task_malformed") from None
    return task["task_digest"]


class DesignBankSource(BankSource):
    """The bank core's view of one question law."""

    def __init__(self, law):
        if not isinstance(law, QuestionLaw):
            raise TypeError("a QuestionLaw is required")
        self.law = law
        self.challenge_id = law.challenge_id
        self.bank = PREFIX + law.name

    def draw_tranche(self, bank, role, count):
        if bank != self.bank:
            raise BankRefused("bank_not_this_law")
        drawn = []
        for question in self.law.draw(role, count):
            task = question["task"]
            drawn.append(
                {
                    "case_id": question["question_id"],
                    "inputs": {
                        "task": task,
                        "task_digest": _verify_task(task),
                        "draw": question["draw"],
                    },
                }
            )
        return drawn

    def terminal(self):
        return tuple(self.law.terminal)

    def stratum(self, bank, inputs):
        return self.law.stratum(inputs)


def _owner_only_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ProducerRefused("producer_dir_not_owner_only", path=path)
    return path


def _write_jobs(directory, tranche, jobs):
    path = directory / "jobs.json"
    temporary = path.with_name("jobs.json.new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump({"tranche": tranche, "jobs": jobs}, handle, sort_keys=True)
    os.replace(temporary, path)
    records = directory / "records.jsonl"
    if not records.exists():
        records.touch(mode=0o600)


class DesignBank:
    """Fill one design bank: draw a tranche, solve its questions through the
    law's stages, store each reference, and seal. Resumable: a rerun finishes
    a drawn tranche and solves nothing twice."""

    def __init__(self, directory, law, solver):
        self.directory = _owner_only_dir(directory)
        self.source = DesignBankSource(law)
        self.law, self.solver = law, solver
        self.ledger = BankLedger(self.directory, self.source)

    @property
    def bank(self):
        return self.source.bank

    def values(self):
        found = DESIGN_BANKS.get(self.law.name)
        if found is None:
            raise ProducerRefused("producer_design_bank_unregistered")
        return found

    def top_up(self, *, workers=6, live=None):
        """Refill to the registered size, or toward `live` live questions
        when given (never above the size): finish any drawn tranche, then
        draw, solve and seal one tranche of the live deficit."""
        size = self.values()["size"]
        if live is not None:
            if type(live) is not int or not 0 < live <= size:
                raise ProducerRefused("producer_design_live_malformed")
            size = live
        results = [
            self._solve(row["role"], workers)
            for row in self.ledger.tranches(self.bank)
            if row["state"] == "DRAWN"
        ]
        if any(r["state"] != "SEALED" for r in results):
            return results
        deficit = self.ledger.deficit(self.bank, size)
        if deficit:
            drawn = self.ledger.draw_tranche(self.bank, deficit)
            results.append(self._solve(drawn["tranche"], workers))
        return results

    def _solve(self, tranche, workers):
        questions = {job["case_id"]: job["inputs"] for job in self.ledger.jobs(tranche)}
        work = _owner_only_dir(self.directory / "work" / tranche)
        last = None
        while questions:
            stage = self.law.next_stage(questions, work)
            if stage is None:
                break
            subdirectory, jobs = stage
            if subdirectory == last:
                # The same stage is still unsolved after its solve: a rerun
                # resumes it (FAILED_INFRA is retried by the truth solve).
                return {
                    "tranche": tranche,
                    "state": "PENDING",
                    "stage": subdirectory or ".",
                    "jobs": len(jobs),
                }
            directory = _owner_only_dir(work / subdirectory)
            _write_jobs(directory, tranche, jobs)
            self.solver(directory, workers)
            last = subdirectory
        if questions:
            references = self.law.references(questions, work)
            left = self.ledger.ingest(
                tranche,
                [{"case_id": q, **references[q]} for q in sorted(questions)],
            )
            if left:
                return {"tranche": tranche, "state": "PENDING", "unsolved": left}
        sealed = self.ledger.seal(tranche)
        return {"tranche": tranche, "state": "SEALED", "root": sealed["root"]}


def law_for(name, producer, *, repository=None):
    """The registered question law `name`, over the producer's own source."""
    if name == "battery-q3":
        from .battery_q3_bank import BatteryQ3Law

        sources = [s for s in producer.sources.values() if hasattr(s, "adapter")]
        battery = [
            s
            for s in sources
            if s.challenge_id == "battery-fastcharge-ageing-development-v1"
        ]
        if not battery:
            raise ProducerRefused("producer_no_source")
        return BatteryQ3Law(battery[0].adapter.target, repository=repository)
    raise ProducerRefused("producer_design_bank_unregistered")


def main(argv=None):
    from .producer import REPOSITORY, Producer

    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.design_bank")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fill", "status"):
        command = sub.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--bank", required=True, choices=sorted(DESIGN_BANKS))
        command.add_argument("--dir", required=True)
        if name == "fill":
            command.add_argument("--workers", type=int, default=6)
            command.add_argument("--live", type=int)
    args = parser.parse_args(argv)
    try:
        producer = Producer.from_config(args.config)
        law = law_for(args.bank, producer, repository=REPOSITORY)
        source = producer.sources[law.challenge_id]

        def solver(directory, workers):
            from .tuning import solve

            if source.overlay is None:
                raise ProducerRefused("producer_no_truth_overlay")
            solve(directory, source.overlay, workers=workers)

        bank = DesignBank(args.dir, law, solver)
        result = {}
        if args.command == "fill":
            result["tranches"] = bank.top_up(workers=args.workers, live=args.live)
        result["status"] = bank.ledger.status()
    except ProducerRefused as refused:  # BankRefused included
        print(json.dumps(refused.record()))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    from carbon.challenge_validator.design_bank import main as _main

    sys.exit(_main())


__all__ = ["DESIGN_BANKS", "DesignBank", "DesignBankSource", "QuestionLaw"]
