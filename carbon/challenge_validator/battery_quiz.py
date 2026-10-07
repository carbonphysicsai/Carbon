"""Battery's near-limit quiz inside every hidden batch, operator-side only
(VALIDATOR-19 slice Q, part 2).

The quiz's science lives in `carbon.battery.quiz_stratum` and
`carbon.battery.value.quiz`. Those modules load the value-analysis code, so
no validator or miner surface may import them (the attack-store and
development-variant invariants walk every import). This module is their only
door, and it is opened by operator entry points alone:

- **`BatteryQuizSource`**, the producer's battery source (`producer.source_for`):
  the batch's quiz drawn from the producer root under the batch's own role,
  solved with the batch, and selected as the tuning set's quiz is.
  - Q3: the first k = 8 feasible scenarios. Protected conditions are refused
    and redrawn, and all-infeasible scenarios skipped, both counted. Too few
    asks for the next round.
  - Q2: the near-limit pool of up to 320, then 80 cases by the registered
    panel's disagreement, from the panel's predictions only.
  - The panel is rebuilt once per panel version and cached owner-only on the
    producer host; each batch then only infers.
- **`install(target)`** gives a battery validator its quiz measures (the
  daemon calls `target.quiz_measures`, never this module). Graphite's hidden
  pool installs it; `report` measures a deployment's scored submissions
  afterwards for validators run without it:

      python -m carbon.challenge_validator.battery_quiz report --config DEPLOYMENT.json

The quiz is drawn and reported and gates nothing: rule v2's scoring,
nomination, finals and weights are unchanged until the owner adopts a rule
v3. Margins and thresholds stay HUMAN_INPUT. DEVELOPMENT only: no
qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import os
import sys
from pathlib import Path

from carbon.battery import quiz_stratum as qs
from carbon.battery.value import quiz as qz

from .batch_source import ProducerRefused
from .battery import BatteryBatchSource, _plain

REPOSITORY = Path(__file__).resolve().parents[2]


@contextlib.contextmanager
def _producer_refusals():
    """quiz_stratum's typed refusals, as the producer's own."""
    try:
        yield
    except qs.QuizRefused as refused:
        raise ProducerRefused("producer_" + refused.code) from None


# --- the producer's battery source ------------------------------------------------------


class BatteryQuizSource(BatteryBatchSource):
    """`BatteryBatchSource` with its quiz. `panel_backend` rebuilds and
    infers the panel (by default the producer deployment's own backend)."""

    def __init__(self, adapter, *, panel_backend=None, **options):
        super().__init__(adapter, **options)
        self.panel_backend = panel_backend

    def quiz_draw(self, fingerprint, round_):
        """Round `round_` of a screening batch's quiz draws, from the
        producer's root under the batch's own role at quiz_stratum's reserved
        indices: Q2's oversample, and `Q3_K + 4 * round_` accepted Q3
        conditions (protected ones refused and redrawn). Uniform draws only."""
        row = self._row(fingerprint)
        if row["kind"] != "screening":
            raise ProducerRefused("producer_quiz_kind_refused")
        if type(round_) is not int or round_ < 1:
            raise ProducerRefused("producer_quiz_round_malformed")
        target, role = self.adapter.target, row["role"]
        with _producer_refusals():
            points = qs.protected_conditions(self.repository)
            return {
                "role": role,
                "q2": qs.q2_candidates(target.root, target.pin, role, qs.q2_draws()),
                "q3": qs.q3_conditions(
                    target.root, target.pin, role, qs.q3_draws(round_), points
                ),
            }

    def quiz_jobs(self, draws):
        return qs.solve_jobs(qs.contract(self.repository), draws["q2"], draws["q3"])

    def quiz_select(self, draws, records, *, panel, cache):
        """quiz_stratum's selection, as the tuning set's: Q3's first `Q3_K`
        feasible scenarios (else the next round), Q2's near-limit pool, then
        `Q2_N` cases by the registered panel's disagreement, from the panel's
        predictions only. The quiz is committed to the producer's seed
        journal (kind `quiz`: digest and counts only) before any use."""
        from carbon.battery.worker import WorkerFailure

        refs = qs.solved(records)
        contract = qs.contract(self.repository)
        try:
            q3, redraws = qs.q3_select(contract, draws["q3"], refs)
            if len(q3) < qz.Q3_K:
                # Infeasible scenarios: the next round adds conditions.
                round_ = (len(draws["q3"]) - qz.Q3_K) // qs.Q3_EXTRA + 1
                return {"next_round": round_}
            pool = qs.q2_pool(contract, draws["q2"], refs)
        except qs.QuizRefused as refused:
            if refused.code == "quiz_unsolved":
                return {"pending": "producer_quiz_unsolved"}
            raise ProducerRefused("producer_" + refused.code) from None
        if len(pool) < qz.Q2_N:
            raise ProducerRefused("producer_quiz_q2_pool_short")
        candidates = {c["case_id"]: dict(c["inputs"]) for c in draws["q2"]}
        inputs = {c: candidates[c] for c in pool}
        try:
            predictions = self._panel_predictions(panel, inputs, Path(cache))
        except WorkerFailure:
            # The panel's infrastructure, never the batch's: retried.
            return {"pending": "producer_quiz_panel_failed_infra"}
        chosen = qs.q2_choose(contract, pool, predictions)
        document = qs.document(
            draws["role"],
            qz.PANEL_VERSION,
            [{"case_id": c, "inputs": inputs[c]} for c in chosen],
            q3,
            redraws,
        )
        references = {c: refs[c] for c in qs.inputs(document)}
        with self.adapter._writer(), _producer_refusals():
            qs.seal(self.adapter.target.journal, document)
        return {"document": document, "references": references}

    def _panel_members(self, panel):
        from .tuning import TuningRefused, load_panel

        try:
            members = load_panel(panel)
        except (OSError, ValueError, TuningRefused):
            raise ProducerRefused("producer_quiz_panel_malformed") from None
        with _producer_refusals():
            registered = qs.registered_panel(self.repository)
        if sorted(m["member"] for m in members) != sorted(registered):
            raise ProducerRefused("producer_quiz_panel_not_registered")
        return members

    def _panel_predictions(self, panel, inputs, cache):
        """Each registered panel member's predictions on `inputs`. A member
        is rebuilt once per panel version (its state cached owner-only under
        `cache`) and then only infers. A member's missing prediction is left
        out, so `q2_select` skips that case."""
        members = self._panel_members(panel)
        backend = self.panel_backend or self.adapter.target.backend
        directory = cache / f"v{qz.PANEL_VERSION}"
        directory.mkdir(mode=0o700, exist_ok=True)
        if os.lstat(directory).st_mode & 0o077:
            raise ProducerRefused("producer_dir_not_owner_only")
        label = hashlib.sha256(json.dumps(sorted(inputs)).encode()).hexdigest()[:16]
        found = {}
        for member in members:
            state = self._panel_state(backend, member, directory)
            predictions = backend.infer(
                f"quiz-panel-v{qz.PANEL_VERSION}-{member['member']}-{label}",
                state,
                inputs,
            )
            found[member["member"]] = {
                c: predictions[c]
                for c in inputs
                if type(predictions) is dict and predictions.get(c) is not None
            }
        return found

    @staticmethod
    def _panel_state(backend, member, directory):
        from carbon.battery.compile import compile_recipe

        from .producer import _read_private, _write_once

        _, recipe = compile_recipe(member["strategy"])
        name = member["member"]
        expected = {
            "member": name,
            "recipe_digest": recipe.recipe_digest,
            "seed": member["seed"],
            "backend": _plain(dict(backend.identity)),
        }
        meta, path = directory / f"{name}.json", directory / f"{name}.state"
        if meta.exists():
            cached = _read_private(meta)
            state = path.read_bytes() if path.exists() else b""
            if (
                {k: cached.get(k) for k in expected} != expected
                or os.lstat(path).st_mode & 0o077
                or "sha256:" + hashlib.sha256(state).hexdigest()
                != cached.get("state_digest")
            ):
                raise ProducerRefused("producer_quiz_panel_cache_stale")
            return state
        state, _stats = backend.reconstruct(
            f"quiz-panel-v{qz.PANEL_VERSION}-{name}", recipe, member["seed"]
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(state)
        _write_once(
            meta,
            {**expected, "state_digest": "sha256:" + hashlib.sha256(state).hexdigest()},
        )
        return state


# --- the validator's quiz measures ------------------------------------------------------


def measure(repository, quizzes, predictions):
    """One model's quiz measures on `quizzes` (`{fingerprint: stored quiz}`):
    Q2's (`quiz.q2_measures`) and Q3's judged decisions and measures over
    the feasible scenarios, per batch and pooled over the batches. Reads the
    model's predictions and the quizzes' references only."""
    contract = qs.contract(repository)
    batches = {
        fingerprint: qs.member_measures(
            contract, quiz["document"], predictions, quiz["references"]
        )
        for fingerprint, quiz in quizzes.items()
    }
    pooled = {
        "q2": [c for q in quizzes.values() for c in q["document"]["q2"]],
        "q3": [s for q in quizzes.values() for s in q["document"]["q3"]],
    }
    refs = {}
    for quiz in quizzes.values():
        refs.update(quiz["references"])
    return {
        "batches": batches,
        "pooled": qs.member_measures(contract, pooled, predictions, refs),
    }


def install(target):
    """Give a battery validator its quiz measures. Returns the target."""
    from carbon.battery.daemon import BatteryValidator

    if type(target) is not BatteryValidator:
        raise TypeError("a BatteryValidator is required")
    target.quiz_measures = functools.partial(measure, target.repository)
    return target


def report(target):
    """Measure the quiz of every scored submission that has no measured
    report yet, under the deployment's writer lock. Returns counts only."""
    from carbon.battery import deployment

    install(target)
    states = {}
    with deployment.writer(target):
        with target.store.db() as db:
            scored = [r[0] for r in db.execute("SELECT submission_id FROM scores")]
        for submission_id in scored:
            result = target.quiz_report(submission_id)
            state = "NO_QUIZ" if result is None else result["state"]
            states[state] = states.get(state, 0) + 1
    return {"scored": len(scored), "states": states}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.battery_quiz")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report").add_argument("--config", required=True)
    args = parser.parse_args(argv)
    from carbon.battery import deployment

    target = deployment.validator(Path(args.config), repository=REPOSITORY)
    print(json.dumps(report(target), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
