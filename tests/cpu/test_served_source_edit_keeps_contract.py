"""R66, unit form: an edit to a SERVED SOURCE file (lean_recipe._SOURCE_PATHS or a staged worker module, e.g.
research_tasks.py) moves only the adapter's implementation identity, never a served contract digest or an evaluation
key, so it strands no king (Release Architect 13:36 / Validator-2 13:37, 5 Nov; the decisive live form is Deploy's R66
on a spare with a copy of a door's state).

- The contract digest (`served_recipe_contract.registered(...).digest`, the key the ledger's owned outcomes and every
  door's contract are filed under) is a function of the registered kit material only.
- `_source_identity` hashes the served files: it reaches `implementation_digest` / `identities_digest` (results'
  pinned fields) and the in-process `served_recipe_source_changed` refusal only.
- The evaluation key (`bank_promotion.private_evaluation_key`) reads only the exam and scoring fields, never a pinned
  adapter identity.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from carbon.challenge_validator import lean_recipe
from carbon.challenge_validator.bank_promotion import private_evaluation_key
from carbon.challenge_validator.interface import digest

EDITED = "carbon/development_session/research_tasks.py"


def _contracts():
    """Every served contract this tree registers that builds here: physical families, battery and synthetic."""
    from carbon.battery import challenge as battery_challenge
    from carbon.challenge_kit import physical_material

    return [
        *sorted(physical_material.REGISTERED),
        (battery_challenge.CHALLENGE.challenge_id, battery_challenge.CHALLENGE.version),
        *((battery_challenge.CHALLENGE.challenge_id, v) for v in ("2.0", "2.1", "2.2")),
        ("synthetic-linear-field-2d", "1.3"),
    ]


def _digests(keys):
    from carbon.reconstruction.served_recipe_contract import registered

    out = {}
    for key in keys:
        try:
            out[key] = registered(*key).digest
        except (
            LookupError,
            OSError,
            ValueError,
        ) as unavailable:  # material absent in this tree
            out[key] = type(unavailable).__name__
    return out


def _edit(monkeypatch, which):
    """Append a comment to the served files ``which`` selects, as a release that changes only them would."""
    original = Path.read_bytes

    def changed(path):
        body = original(path)
        return (
            body + b"\n# R66: a plumbing-only edit\n"
            if which(path.as_posix())
            else body
        )

    monkeypatch.setattr(Path, "read_bytes", changed)


@pytest.mark.parametrize(
    "which",
    [
        pytest.param(
            lambda posix: posix.endswith("/" + EDITED), id="research_tasks_only"
        ),
        pytest.param(
            lambda posix: any(
                posix.endswith("/" + name) for name in lean_recipe._SOURCE_PATHS
            ),
            id="every_source_path",
        ),
    ],
)
def test_a_served_source_edit_moves_the_implementation_identity_and_no_contract(
    monkeypatch, which
):
    assert EDITED in lean_recipe._SOURCE_PATHS
    keys = _contracts()
    before_contracts = _digests(keys)
    assert (
        sum(
            type(v) is str and v.startswith("sha256:")
            for v in before_contracts.values()
        )
        >= 2
    )
    before_identity = lean_recipe._implementation_identity()
    _edit(monkeypatch, which)
    assert lean_recipe._implementation_identity() != before_identity
    assert _digests(keys) == before_contracts


def test_negative_control_a_kit_material_edit_moves_every_contract(monkeypatch):
    """The edit above reaches what the contracts read: changing the kit MATERIAL (a new exam version, rightly)
    moves each contract that builds here, so an unchanged digest after a source edit is not a vacuous pass.
    """
    keys = _contracts()
    before = _digests(keys)
    built = [key for key, value in before.items() if value.startswith("sha256:")]
    _edit(monkeypatch, lambda posix: posix.endswith(".json"))
    after = _digests(keys)
    assert built
    assert all(after[key] != before[key] for key in built)


def _evidence():
    """A valid pack-bound private evaluation binding (v2), as the core files it."""
    return {
        "schema": "carbon.scoring.private-evaluation-binding.v2",
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "status": "BOUND_DEVELOPMENT_ONLY",
        "challenge": "carbon-r66-fixture",
        "challenge_version": "1.0",
        "evaluation_version": "carbon.r66-fixture-exam.v1",
        **{
            field: digest([field, "r66"])
            for field in (
                "source_receipt_sha256",
                "evaluation_version_digest",
                "entry_id",
                "state_digest",
                "model_result_digest",
                "score_result_digest",
                "benchmark_result_digest",
                "evaluation_pack_digest",
            )
        },
        "score_compatibility": {
            "score_pack_digest": digest("score pack"),
            "scoring_version": "carbon.scoring.solver-benchmark-pack.v3",
            "execution_profile_digest": digest("execution profile"),
        },
    }


def test_the_evaluation_key_reads_no_adapter_identity():
    evidence = _evidence()
    key = private_evaluation_key(evidence)
    moved = deepcopy(evidence)
    # what a served-source edit changes in a result: its pinned adapter identities
    moved["pinned"] = {
        "implementation_digest": digest("after the edit"),
        "identities_digest": digest("after the edit, all identities"),
    }
    moved["implementation_digest"] = digest("after the edit")
    moved["identities_digest"] = digest("after the edit, all identities")
    # one model's own run, not the shared exam context
    for field in (
        "entry_id",
        "state_digest",
        "model_result_digest",
        "score_result_digest",
    ):
        moved[field] = digest([field, "another model"])
    assert private_evaluation_key(moved) == key
    # negative control: the exam itself still moves the key
    for field in ("evaluation_pack_digest", "evaluation_version_digest"):
        other = deepcopy(evidence)
        other[field] = digest([field, "another exam"])
        assert private_evaluation_key(other) != key
