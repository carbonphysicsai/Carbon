"""The battery near-limit quiz stratum, drawn from a private root
(VALIDATOR-19 slice Q; VALIDATOR-17's v2 amendment).

The quiz's meaning lives in `value.quiz` (Data Collection's library): what
"near the limit" is, how the disagreement panel picks Q2's cases, and how a
Q3 decision is judged. This module only draws and assembles a quiz from an
operator-held root, so the tuning set now and the batch producer later make
it the same way:

- **Draws** are `seeds.draw_inputs` under the stratum's seed role, at draw
  indices far above any main batch's (`Q2_BASE`, `Q3_BASE`), so they are
  uniform over the published box, rounded as every battery draw is, and
  unpredictable without the root. Nothing steers a draw.
- **Q2.** `Q2_POOL * Q2_OVERSAMPLE` candidates are drawn and solved. The pool
  is the candidates whose reference is `quiz.q2_near` (within
  `quiz.Q2_POOL_BANDS` bands), in draw order, capped at `quiz.Q2_POOL`.
  `quiz.q2_select` then picks `quiz.Q2_N` from the panel's predictions only.
- **Q3.** Each scenario is one (t_amb_c, soc0) condition from the same draw.
  A condition within both `PROTECTED_T_C` and `PROTECTED_SOC` of a protected
  condition is refused and redrawn. Protected conditions are every scenario
  condition in the committed engineering-value contracts and the committed
  practice decision set's (PRACTICE-SAFETY-01 B4). The first `quiz.Q3_K`
  conditions whose 35-candidate reference grid holds a feasible design
  (`quiz.q3_feasible`) are kept; the rest count as redraws.
- **The quiz document** names its role, the panel version and each case's
  inputs. It is private; only its digest and counts are committed to the
  seed journal (kind `quiz`, `seal`).

Every margin, cutoff and gate threshold stays HUMAN_INPUT: only the
registered constants are used. DEVELOPMENT only; no LIVE authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from . import seeds
from .value import quiz

SCHEMA = "carbon.battery.quiz-stratum.v1"
JOURNAL_KIND = "quiz"
CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
CONTRACTS = "carbon/battery/value/contracts"
PANEL_REGISTRY = (
    "docs/development/evidence/battery-quiz-designs/disagreement-panel-v{}.json"
)
PANEL_SCHEMA = "carbon.battery.quiz-disagreement-panel.v1"
#: The agreed draw sizes (VALIDATOR-19 slice Q): round 1 draws Q2's pool four
#: times over and Q3_K + 4 conditions; each later round adds 4 conditions.
Q2_OVERSAMPLE = 4
Q3_EXTRA = 4
#: Data Collection's ruling 1 (2026-10-06), B4's own refusal rule: a condition
#: within BOTH 2 degC and 0.03 soc0 of a protected one is redrawn.
PROTECTED_T_C, PROTECTED_SOC = 2.0, 0.03
#: Draw indices under the stratum's role. A main batch draws indices from 0
#: up to its size, so the quiz's draws never repeat one of them.
Q2_BASE = 1 << 40
Q3_BASE = 2 << 40
#: Refused draws a condition may take before the box is called unreachable.
Q3_ATTEMPTS_PER_CONDITION = 1000
STATUS_FAILED_INFRA = "FAILED_INFRA"


class QuizRefused(ValueError):
    """A typed refusal; its code names no case, input, output or root."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def contract(repository):
    """EV4's decision contract: the quiz's limits, bands and decision rules."""
    from .value import contract as ev

    document, _digest = ev.load(Path(repository) / CONTRACT)
    return document


def q2_draws():
    return quiz.Q2_POOL * Q2_OVERSAMPLE


def q3_draws(round_):
    return quiz.Q3_K + Q3_EXTRA * round_


# --- draws -----------------------------------------------------------------------------


def _key(root, role):
    if type(root) is not seeds.PrivateRoot:
        raise TypeError("an operator-held PrivateRoot is required")
    return hmac.new(
        root._bytes, b"quiz-case-ids/" + role.encode(), hashlib.sha256
    ).digest()


def _tag(key, label):
    return hmac.new(key, label.encode(), hashlib.sha256).hexdigest()[:16]


def q2_candidates(root, pin, role, count):
    """The first `count` Q2 candidates, by index: an opaque case id (shaped as
    a main batch's) and one uniform draw."""
    key, context = _key(root, role), seeds._context(root, pin)
    return [
        {
            "case_id": f"{role}-{_tag(key, f'q2/{index}')}",
            "inputs": seeds.draw_inputs(context, role, Q2_BASE + index),
        }
        for index in range(count)
    ]


#: The practice decision set's committed conditions (PRACTICE-SAFETY-01 B4),
#: pinned here by their own sha256. The quiz reads only these public points,
#: never the practice-safety code: practice feedback stays apart from the
#: hidden path (`test_only_the_practice_providers_import_the_safety_code`).
#: A changed file is refused until this pin moves with it (fail closed).
PRACTICE_CONDITIONS = (
    "docs/development/evidence/practice-decision-set-v2/conditions.json"
)
PRACTICE_CONDITIONS_SHA256 = (
    "36b90c54f2d34ce201e1e8fe4ae5c05bf9ebf6e037a572c1c167365064eb5dc7"
)
PRACTICE_CONDITIONS_SCHEMA = "carbon.battery.practice-decision-set.v2"


def practice_conditions(repository):
    """The committed practice decision set's (t_amb_c, soc0) points,
    verified against their pin, or refused."""
    import hashlib
    import json

    try:
        body = (Path(repository) / PRACTICE_CONDITIONS).read_bytes()
    except OSError:
        raise QuizRefused("quiz_practice_decision_set_refused") from None
    if hashlib.sha256(body).hexdigest() != PRACTICE_CONDITIONS_SHA256:
        raise QuizRefused("quiz_practice_decision_set_refused")
    document = json.loads(body)
    if document.get("schema") != PRACTICE_CONDITIONS_SCHEMA:
        raise QuizRefused("quiz_practice_decision_set_refused")
    return [(float(c["t_amb_c"]), float(c["soc0"])) for c in document["conditions"]]


def protected_conditions(repository):
    """Every condition a Q3 scenario keeps its distance from: each scenario
    condition in the committed contracts, and the committed practice decision
    set's conditions (verified against their pin, or refused)."""
    from .value import contract as ev

    points = set()
    for path in sorted((Path(repository) / CONTRACTS).glob("*.json")):
        document, _digest = ev.load(path)
        for scenario in ev.scenarios(document):
            points.update((float(t), float(s)) for t, s in scenario["conditions"])
    points.update(practice_conditions(repository))
    return sorted(points)


def is_protected(condition, points):
    t, s = condition
    return any(
        abs(t - pt) < PROTECTED_T_C and abs(s - ps) < PROTECTED_SOC for pt, ps in points
    )


def q3_conditions(root, pin, role, count, points):
    """The first `count` accepted Q3 conditions, in draw order. Each carries
    an opaque scenario id and its draw `attempt`; a protected draw is
    refused and the next one taken."""
    key, context = _key(root, role), seeds._context(root, pin)
    accepted, attempt = [], 0
    while len(accepted) < count:
        if attempt >= Q3_ATTEMPTS_PER_CONDITION * count:
            raise QuizRefused("quiz_q3_conditions_unreachable")
        drawn = seeds.draw_inputs(context, role, Q3_BASE + attempt)
        condition = [drawn["t_amb_c"], drawn["soc0"]]
        if not is_protected(condition, points):
            accepted.append(
                {
                    "scenario_id": f"q3-{_tag(key, f'q3/{attempt}')}",
                    "condition": condition,
                    "attempt": attempt,
                }
            )
        attempt += 1
    return accepted


def scenario(entry):
    return quiz.q3_scenario(entry["scenario_id"], entry["condition"])


def solve_jobs(contract, q2, q3):
    """The reference jobs: every Q2 candidate, and every Q3 condition's grid.
    Case ids carry no reference information."""
    jobs = [{"case_id": c["case_id"], **c["inputs"]} for c in q2]
    for entry in q3:
        jobs += quiz.q3_grid(contract, scenario(entry))
    return jobs


# --- selection -------------------------------------------------------------------------


def solved(records):
    """Reference records by case id; FAILED_INFRA is not a solve."""
    return {r["case_id"]: r for r in records if r.get("status") != STATUS_FAILED_INFRA}


def q2_pool(contract, candidates, refs):
    """The near-limit pool: candidates whose reference is `quiz.q2_near`, in
    draw order, capped at `quiz.Q2_POOL`. Every candidate must be solved."""
    if any(c["case_id"] not in refs for c in candidates):
        raise QuizRefused("quiz_unsolved")
    near = [
        c["case_id"] for c in candidates if quiz.q2_near(contract, refs[c["case_id"]])
    ]
    return near[: quiz.Q2_POOL]


def q2_choose(contract, pool_ids, panel_predictions):
    """`quiz.Q2_N` pool cases by panel disagreement. Only the panel's
    predictions are read; no candidate model's, and no reference."""
    return quiz.q2_select(contract, pool_ids, panel_predictions, n=quiz.Q2_N)


def q3_select(contract, conditions, refs):
    """The first `quiz.Q3_K` conditions, in draw order, whose reference grid
    holds a feasible design, each with its grid; and the redraws: protected
    draws refused and infeasible scenarios skipped, up to the last one kept.
    Fewer than `quiz.Q3_K` are returned when the draws run out."""
    chosen, infeasible, last = [], 0, None
    for ordinal, entry in enumerate(conditions):
        grid = quiz.q3_grid(contract, scenario(entry))
        if any(job["case_id"] not in refs for job in grid):
            raise QuizRefused("quiz_unsolved")
        grid_refs = {job["case_id"]: refs[job["case_id"]] for job in grid}
        if quiz.q3_feasible(contract, scenario(entry), grid_refs):
            chosen.append(
                {
                    "scenario_id": entry["scenario_id"],
                    "condition": list(entry["condition"]),
                    "grid": grid,
                }
            )
            last = (ordinal, entry["attempt"])
            if len(chosen) == quiz.Q3_K:
                break
        else:
            infeasible += 1
    protected = 0 if last is None else last[1] - last[0]
    return chosen, {"q3_protected": protected, "q3_infeasible": infeasible}


# --- the document ----------------------------------------------------------------------


def document(role, panel_version, q2, q3, redraws):
    """The private quiz document."""
    return {
        "schema": SCHEMA,
        "role": role,
        "panel_version": panel_version,
        "q2": [{"case_id": c["case_id"], "inputs": dict(c["inputs"])} for c in q2],
        "q3": [
            {
                "scenario_id": s["scenario_id"],
                "condition": list(s["condition"]),
                "grid": [dict(job) for job in s["grid"]],
            }
            for s in q3
        ],
        "redraws": dict(redraws),
    }


def check(value):
    """A quiz document, checked for shape, or refused."""
    if (
        type(value) is not dict
        or set(value) != {"schema", "role", "panel_version", "q2", "q3", "redraws"}
        or value["schema"] != SCHEMA
        or type(value["role"]) is not str
        or type(value["panel_version"]) is not int
        or type(value["q2"]) is not list
        or type(value["q3"]) is not list
        or type(value["redraws"]) is not dict
        or not all(
            type(c) is dict and set(c) == {"case_id", "inputs"} for c in value["q2"]
        )
        or not all(
            type(s) is dict and set(s) == {"scenario_id", "condition", "grid"}
            for s in value["q3"]
        )
    ):
        raise QuizRefused("quiz_document_malformed")
    return value


def inputs(value):
    """Every case the quiz asks a model to predict: case id to inputs."""
    found = {c["case_id"]: dict(c["inputs"]) for c in value["q2"]}
    for s in value["q3"]:
        for job in s["grid"]:
            found[job["case_id"]] = {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")}
    return found


def public_entry(value):
    """The seed journal's `quiz` entry: public fields only."""
    return {
        "kind": JOURNAL_KIND,
        "role": value["role"],
        "digest": digest(value),
        "q2_cases": len(value["q2"]),
        "q3_scenarios": len(value["q3"]),
        "panel_version": value["panel_version"],
    }


def seal(journal, value):
    """Commit the quiz's digest to `journal` (kind `quiz`). Idempotent: a
    rerun returns the earlier entry. A different quiz under the same role is
    refused. Every other journal reader selects its own kinds, so it skips
    this entry."""
    entry = public_entry(check(value))
    for earlier in journal.public():
        if earlier.get("kind") == JOURNAL_KIND and earlier.get("role") == entry["role"]:
            if earlier.get("digest") == entry["digest"]:
                return earlier
            raise QuizRefused("quiz_role_already_sealed")
    return journal._append(entry)


# --- the panel -------------------------------------------------------------------------


def registered_panel(repository, version=None):
    """The registered disagreement panel's member names for `version`."""
    version = quiz.PANEL_VERSION if version is None else version
    path = Path(repository) / PANEL_REGISTRY.format(version)
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise QuizRefused("quiz_panel_registry_unreadable") from None
    members = value.get("members") if type(value) is dict else None
    if (
        value.get("schema") != PANEL_SCHEMA
        or value.get("version") != version
        or type(members) is not list
        or not members
        or len(set(members)) != len(members)
    ):
        raise QuizRefused("quiz_panel_registry_malformed")
    return tuple(members)


# --- measures --------------------------------------------------------------------------


def member_measures(contract, value, predictions, refs):
    """One model's quiz measures: Q2's (`quiz.q2_measures`), and Q3's over
    the quiz's feasible scenarios (`quiz.q3_judge`, `quiz.q3_measures`)."""
    q2_ids = [c["case_id"] for c in value["q2"]]
    if any(case_id not in refs for case_id in q2_ids):
        raise QuizRefused("quiz_unsolved")
    outcomes = []
    for s in value["q3"]:
        grid_refs = {
            j["case_id"]: refs[j["case_id"]] for j in s["grid"] if j["case_id"] in refs
        }
        outcomes.append(
            {
                "scenario_id": s["scenario_id"],
                **quiz.q3_judge(contract, scenario(s), predictions, grid_refs),
            }
        )
    return {
        "q2": quiz.q2_measures(contract, predictions, q2_ids, refs),
        "q3": {**quiz.q3_measures(outcomes), "outcomes": outcomes},
    }
