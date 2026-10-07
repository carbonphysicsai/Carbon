"""A Challenge's training budget adapter: what its existing records define.

The adapter is the only Challenge-specific code the study, the cost
calculator and the capacity calculation use. Each Challenge registers its
adapter in `adapters.json` (challenge id -> `module:attribute`), so the shared
modules hold no Challenge literal. A Challenge with a construction contract and
no adapter is a named gap (`NoAdapter`), never a silent default.

The items (`SHEET_TEMPLATE.md`, "The adapter"):
- the construction contract and its cost-driving settings (`contract`);
- the rebuild worker and its backends (`worker`, `backends`);
- the exam code, the equivalence margin and the finalist rule (`exam`,
  `equivalence_margin`, `finalist_rule`);
- the public generator and truth service (`generator`);
- the legitimate admission panel (`panel`);
- the current TRAIN size (`train_cases`);
- for the cost calculator, the recipe's training programs
  (`training_programs`).
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

REGISTRY = Path(__file__).resolve().parent / "adapters.json"
#: The record items an adapter names by `module:attribute`.
RECORD_ITEMS = (
    "worker",
    "exam",
    "equivalence_margin",
    "finalist_rule",
    "generator",
    "panel",
)


class NoAdapter(LookupError):
    """The Challenge has no training budget adapter (a named gap)."""

    def __init__(self, challenge_id):
        super().__init__(f"no training budget adapter for {challenge_id}")
        self.challenge_id = challenge_id


class AdapterGap(LookupError):
    """The adapter does not yet supply an item a phase needs."""

    def __init__(self, challenge_id, item):
        super().__init__(f"{challenge_id} supplies no {item} yet")
        self.challenge_id, self.item = challenge_id, item


@dataclass(frozen=True)
class Program:
    """One training program of a recipe: `members` identical members.

    `fit(steps)` trains one member for `steps` main steps with no polish and
    returns its statistics (with `n_params`); the cost calculator runs it
    under its own capture, so it never trains to the recipe's full length.
    `parameters(args)` counts a captured JAX program's parameters from its
    arguments.
    """

    backend: str
    members: int
    main_steps: int
    polish_steps: int
    cases_per_update: int
    fit: Callable[[int], dict]
    parameters: Callable[[tuple], int]


@runtime_checkable
class ChallengeAdapter(Protocol):
    challenge_id: str
    records: dict

    def contract(self): ...

    def backends(self) -> tuple: ...

    def train_cases(self) -> int: ...

    def training_programs(self, strategy, *, train_cases=None) -> list: ...


def _registry():
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if document.get("schema") != "carbon.training-budget.adapters.v1":
        raise ValueError("unknown adapter registry schema")
    return document


def registered():
    """The Challenge ids that have an adapter, sorted."""
    return sorted(_registry()["adapters"])


def gaps():
    """The Challenges with a construction contract and no adapter yet, each
    with its reason."""
    return dict(_registry()["gaps"])


def adapter_for(challenge_id) -> ChallengeAdapter:
    target = _registry()["adapters"].get(challenge_id)
    if target is None:
        raise NoAdapter(challenge_id)
    module, _, attribute = target.partition(":")
    adapter = getattr(importlib.import_module(module), attribute)()
    if (
        not isinstance(adapter, ChallengeAdapter)
        or adapter.challenge_id != challenge_id
    ):
        raise TypeError(f"{target} is not {challenge_id}'s adapter")
    return adapter


def record(adapter, item):
    """Resolve one named record item, or `AdapterGap`."""
    if item not in RECORD_ITEMS:
        raise KeyError(item)
    target = adapter.records.get(item)
    if not target:
        raise AdapterGap(adapter.challenge_id, item)
    module, _, attribute = target.partition(":")
    value = importlib.import_module(module)
    for part in attribute.split(".") if attribute else ():
        value = getattr(value, part)
    return value
