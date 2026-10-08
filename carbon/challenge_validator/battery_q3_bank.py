"""Battery's Q3 design questions as a design bank (VALIDATOR-23 slice 3a): the
first `QuestionLaw`. Producer-only.

One question is one Q3 scenario (an ambient temperature and a starting state
of charge), drawn from the producer's root under the tranche's role, away
from every protected condition (`quiz_stratum.q3_conditions`). Its task is
v8's neutral one (`battery_q3_v8`): the 117-point lattice of charge designs,
minimise the time to CV onset, within the reach, plating and thermal limits.

It is solved in two stages, once, at tranche seal, as the quiz is
(quiz-registry-v8):
1. the lattice: every candidate at the scenario's condition;
2. the band-edge refine: each lattice point near a limit, solved again,
   refined.

Then it is settled (`quiz_stratum.settle`). The bridge reference is each
candidate's projection of its settled truth (`battery_q3_v8._projection`).

A question is live (`OK`) only when its settled reference has a feasible
design and every candidate's truth is defined, as v8's law keeps only
reference-feasible scenarios. Otherwise it is recorded and never asked:
`NONE_FEASIBLE`, or `UNRESOLVED` when no design is settled feasible but not
every candidate is settled infeasible, or a candidate's truth is undefined.
"""

from __future__ import annotations

from .bank import BankRefused
from .design_bank import QuestionLaw

#: The battery Challenge whose producer root draws the questions.
CHALLENGE = "battery-fastcharge-ageing-development-v1"
#: The refine stage's work subdirectory (`tuning.REFINE_DIR`).
REFINE = "refine"


class BatteryQ3Law(QuestionLaw):
    name = "battery-q3"
    challenge_id = CHALLENGE
    terminal = ("OK", "NONE_FEASIBLE", "UNRESOLVED")

    def __init__(self, target, *, repository):
        from carbon.battery import quiz_stratum as qs

        self.target = target
        self.contract = qs.contract(repository)
        self.protected = qs.protected_conditions(repository)

    @staticmethod
    def _refusals():
        import contextlib

        from carbon.battery.quiz_stratum import QuizRefused

        @contextlib.contextmanager
        def mapped():
            try:
                yield
            except QuizRefused:
                raise BankRefused("bank_design_quiz_refused") from None

        return mapped()

    def draw(self, role, count):
        from carbon.battery import quiz_stratum as qs
        from carbon.design_search import battery_q3_v8 as v8

        # The tranche role names the bank (`bank-design:battery-q3-T1`); a seed
        # role is a canonical identifier, so its ':' becomes '-'. Unique beside
        # the pool's `bank-pool-T<n>` and the producer's slot roles.
        seed_role = role.replace(":", "-")
        with self._refusals():
            entries = qs.q3_conditions(
                self.target.root, self.target.pin, seed_role, count, self.protected
            )
        return [
            {
                "question_id": entry["scenario_id"],
                # v8's neutral task, its reference bank named by the tranche.
                "task": v8._neutral_task(entry, role, self.contract),
                "draw": entry,
            }
            for entry in entries
        ]

    def _entries(self, questions):
        return [questions[q]["draw"] for q in sorted(questions)]

    def next_stage(self, questions, work):
        from carbon.battery import quiz_stratum as qs
        from carbon.battery.value import quiz as bq

        from .tuning import _records, _refined_records

        entries = self._entries(questions)
        refs = _records(work)
        grid = [
            job for e in entries for job in bq.q3_grid(self.contract, qs.scenario(e))
        ]
        if any(job["case_id"] not in refs for job in grid):
            return ("", grid)
        with self._refusals():
            points = qs.refine_points(self.contract, entries, refs)
            if qs.unrefined(points, _refined_records(work)):
                return (REFINE, qs.refine_jobs(points))
        return None

    def references(self, questions, work):
        from carbon.battery import quiz_stratum as qs
        from carbon.battery.value import decision as bd
        from carbon.battery.value import quiz as bq
        from carbon.design_search import battery_q3_v8 as v8

        from .tuning import _records, _refined_records

        entries = self._entries(questions)
        refs, refined = _records(work), _refined_records(work)
        with self._refusals():
            points = qs.refine_points(self.contract, entries, refs)
            settled = qs.settle(refs, points, refined)
        candidates = bq.q3_candidates()
        found = {}
        for entry in entries:
            scenario = qs.scenario(entry)
            grid = bq.q3_grid(self.contract, scenario)
            truth = [settled[job["case_id"]] for job in grid]
            native = bd.assess_reference(
                self.contract,
                scenario,
                candidates,
                {(c["id"], 0): truth[i] for i, c in enumerate(candidates)},
            )
            panel = [
                {
                    "candidate": c["id"],
                    "condition": "one-condition",
                    "values": v8._projection(self.contract, truth[i]),
                }
                for i, c in enumerate(candidates)
            ]
            if bd.best_in_set(candidates, native) is not None and all(
                row["values"] is not None for row in panel
            ):
                reference = {"status": "OK", "panel": panel}
            elif all(row["status"] == bd.INFEASIBLE for row in native.values()):
                reference = {"status": "NONE_FEASIBLE"}
            else:
                reference = {"status": "UNRESOLVED"}
            found[entry["scenario_id"]] = reference
        return found


__all__ = ["BatteryQ3Law"]
