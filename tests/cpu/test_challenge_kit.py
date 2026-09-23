"""The Burgers challenge kit: the challenge's own generator and solvers, for miners.

The claims tested: the kit is the challenge's law and not a look-alike (it
reproduces the controller's own cases byte for byte, given the same root); the
files shipped are the validator's own bytes; and nothing private ships with
them. Each absence is paired with the same thing present where it really is.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import burgers as kit
from carbon.development_session import research_profile
from carbon.development_session.research_image import (
    KIT_FORBIDDEN,
    challenge_kit_files,
    permitted_files,
)
from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)

REPO = Path(__file__).resolve().parents[2]
ROOT = bytes(range(32))


def controller_context(tmp_path, root):
    """The controller's own context for `root`, built exactly as it builds one."""
    private = tmp_path / "role-roots"
    private.mkdir(mode=0o700)
    (private / "research-train.bin").write_bytes(root)
    return research_profile._context(tmp_path, "research-train")


def test_the_baked_pin_is_the_controllers_pin(tmp_path):
    ours = kit.context(ROOT).pin
    theirs = controller_context(tmp_path, ROOT).pin
    for field in (
        "challenge_key",
        "generator_version",
        "generator_digest",
        "scoring_version",
        "scoring_digest",
    ):
        assert getattr(ours, field) == getattr(theirs, field), field


def test_the_kit_reproduces_the_controllers_cases_byte_for_byte(tmp_path):
    ctx = controller_context(tmp_path, ROOT)
    theirs = [
        generate_development_case(
            ctx, BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, i % 12, i // 12)
        ).public_record()
        for i in range(24)
    ]
    ours = [case.public_record() for case in kit.generate(ROOT, 24)]
    assert json.dumps(ours, sort_keys=True) == json.dumps(theirs, sort_keys=True)
    # Specimen: the match is not trivial - another root is another population draw.
    other = [case.public_record() for case in kit.generate(bytes(32), 24)]
    assert json.dumps(other, sort_keys=True) != json.dumps(theirs, sort_keys=True)


def test_the_trusted_primary_labels_a_case(tmp_path):
    case = kit.generate(ROOT, 1)[0]
    solution = kit.solve(case, "cole_hopf")
    assert solution.shape == (13, 64) and np.isfinite(solution).all()
    inputs = kit.inputs(case)
    assert np.allclose(solution[0], inputs["initial"], atol=1e-8)
    with pytest.raises(ValueError, match="method"):
        kit.solve(case, "julia_crosscheck")


def test_a_small_labelled_dataset_has_the_challenges_shapes():
    data = kit.dataset(ROOT, 3)
    assert data["initial"].shape == (3, 64)
    assert data["times"].shape == (3, 13)
    assert data["solution"].shape == (3, 13, 64)


def test_the_image_carries_the_validators_own_bytes():
    shipped = permitted_files()
    for name in challenge_kit_files(REPO):
        assert shipped[name] == (REPO / name).read_bytes(), name
    assert "carbon/generators/burgers_dynamics.py" in shipped
    assert "carbon/reference_runtime/model.py" in shipped


def test_nothing_forbidden_or_private_ships():
    """Absences, each with the specimen that the thing exists in the repository."""
    shipped = permitted_files()
    for forbidden in (
        "carbon/reference_runtime/controller.py",
        "carbon/development_session/research_profile.py",
        "carbon/development_session/research_campaign.py",
        "carbon/scoring/development.py",
    ):
        assert (REPO / forbidden).is_file(), forbidden
        assert forbidden not in shipped, forbidden
    modules = {
        name.removesuffix("/__init__.py").removesuffix(".py").replace("/", ".")
        for name in shipped
        if name.endswith(".py")
    }
    assert not [m for m in modules if m.startswith(KIT_FORBIDDEN)]
    assert not [
        name
        for name in shipped
        if "role-roots" in name or "final-seeds" in name or name.endswith(".bin")
    ]
