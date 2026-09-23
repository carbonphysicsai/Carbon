"""The owner's DEVELOPMENT qualification of R1 (Amendment 10), through compare_r1.

Every refusal below is paired with the acceptance it is the complement of, on
the same data, so a green run cannot come from a check that is unable to fire:
a registered part decides where an unregistered one is refused, identical
outputs are REPRODUCIBLE where one float32 ulp is not, and the pinned authority
digest is shown moving when the recorded ruling moves.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from pathlib import Path

import pytest

from carbon import reproducibility
from carbon.reproducibility import development
from tests.cpu import test_be1_reproducibility_harness as be1

REPO = Path(__file__).resolve().parents[2]
ACCEPTANCE = REPO / "docs/development/TWO_HOST_STUDY_ACCEPTANCE.md"
ONE_ULP = 2.0**-24  # one float32 ulp in [0.5, 1), the measured unpinned divergence


@pytest.fixture(autouse=True)
def on_the_development_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    """The B-E1 fixture builders, pointed at the Challenge the ruling names."""
    monkeypatch.setattr(be1, "KEY", development.DEVELOPMENT_CHALLENGE)


def manifest(part: str | None = "A40"):
    base = be1.identity_manifest()
    profile = (
        development.development_backend_profile_ref(part)
        if part
        else base.backend_profile_ref
    )
    return replace(
        base,
        backend_profile_ref=profile,
        backend_support=development.development_backend_support(profile),
    )


def captures(part: str = "A40", second=(0.9803, 0.5)):
    identity = manifest(part)
    return be1.run_capture(identity, (0.9803, 0.5)), be1.run_capture(identity, second)


def test_identical_same_part_outputs_are_reproducible() -> None:
    first, second = captures()
    procedure = development.development_procedure("A40")
    result = reproducibility.compare_r1(first, second, procedure)
    assert result.outcome is reproducibility.R1Outcome.REPRODUCIBLE
    assert all(delta.absolute_delta == 0.0 for delta in result.deltas)
    assert result.procedure_ref == procedure.qualification.procedure_ref


def test_one_ulp_is_not_reproducible() -> None:
    """Bit-exact: the smallest difference float32 can express is refused."""
    first, second = captures(second=(0.9803 + ONE_ULP, 0.5))
    result = reproducibility.compare_r1(
        first, second, development.development_procedure("A40")
    )
    assert result.outcome is reproducibility.R1Outcome.NOT_REPRODUCIBLE
    assert max(delta.absolute_delta for delta in result.deltas) > 0.0


@pytest.mark.parametrize("part", development.QUALIFIED_PARTS)
def test_every_qualified_part_decides(part: str) -> None:
    first, second = captures(part)
    result = reproducibility.compare_r1(
        first, second, development.development_procedure(part)
    )
    assert result.outcome is reproducibility.R1Outcome.REPRODUCIBLE


def test_different_parts_never_reach_a_numerical_comparison() -> None:
    """Same part is enforced by identity: two parts are two backend profiles."""
    first = be1.run_capture(manifest("A40"), (0.9803, 0.5))
    second = be1.run_capture(manifest("L4"), (0.9803, 0.5))
    result = reproducibility.compare_r1(
        first, second, development.development_procedure("A40")
    )
    assert result.outcome is reproducibility.R1Outcome.R0_IDENTITY_MISMATCH
    assert "backend_profile_ref" in result.r0_result.mismatched_fields


@pytest.mark.parametrize("part", ["A100", "L40S", "B200", "RTX 4090", "a40"])
def test_a_part_the_ruling_did_not_name_has_no_profile(part: str) -> None:
    development.development_backend_profile_ref("A40")  # a named part is served
    with pytest.raises(ValueError, match="not a part Amendment 10 qualifies"):
        development.development_backend_profile_ref(part)
    with pytest.raises(ValueError):
        development.development_procedure(part)


def test_an_unregistered_profile_is_unsupported_and_compare_r1_says_so() -> None:
    fixture_profile = be1.identity_manifest().backend_profile_ref
    assert (
        development.development_backend_support(fixture_profile)
        is reproducibility.BackendProfileSupport.UNSUPPORTED
    )
    first = be1.run_capture(manifest(None), (0.9803, 0.5))
    result = reproducibility.compare_r1(
        first, first, development.development_procedure("A40")
    )
    assert result.outcome is reproducibility.R1Outcome.BACKEND_UNSUPPORTED


def test_a_supported_capture_with_another_parts_procedure_decides_nothing() -> None:
    first, second = captures("A40")
    result = reproducibility.compare_r1(
        first, second, development.development_procedure("H100 SXM")
    )
    assert result.outcome is reproducibility.R1Outcome.INDETERMINATE


def test_the_procedure_cannot_be_built_around_its_factory() -> None:
    qualification = development.development_procedure("A40").qualification
    with pytest.raises(TypeError, match="development_procedure"):
        development.DevelopmentBitExactProcedure("A40", qualification)


def test_everything_is_fixture_origin() -> None:
    """DEVELOPMENT-typed: nothing here crosses B-E1's fixture-only boundary."""
    for part in development.QUALIFIED_PARTS:
        assert development.development_procedure(part).qualification.fixture_origin
    assert manifest().fixture_origin is True


def amendment_ten(text: str) -> str:
    """The section the pinned digest covers, extracted as the module documents."""
    start = text.index("\n# Amendment 10 - ") + 1
    end = re.search(r"\n---\n\n# Amendment ", text[start:])
    return (text[start : start + end.start()] if end else text[start:]).rstrip() + "\n"


def digest(section: str) -> str:
    return "sha256:" + hashlib.sha256(section.encode("utf-8")).hexdigest()


def test_the_pinned_authority_is_the_recorded_ruling() -> None:
    section = amendment_ten(ACCEPTANCE.read_text(encoding="utf-8"))
    assert digest(section) == development.DEVELOPMENT_AUTHORITY_DIGEST
    assert "Bit-exact" in section and "DEVELOPMENT" in section
    # Specimen: the check moves when the ruling does, so a match means something.
    edited = section.replace("Bit-exact", "Bit-exact-ish", 1)
    assert digest(edited) != development.DEVELOPMENT_AUTHORITY_DIGEST
    # And a later amendment appended after it does not disturb the pin.
    later = ACCEPTANCE.read_text(encoding="utf-8") + "\n---\n\n# Amendment 11 - x\n"
    assert digest(amendment_ten(later)) == development.DEVELOPMENT_AUTHORITY_DIGEST


def test_the_profiles_name_the_configuration_the_study_ran_under() -> None:
    from carbon.reconstruction.accelerators import GPU_PROFILE

    assert development.ENVIRONMENT_PROFILE_ID == GPU_PROFILE.profile_id
    runner = (REPO / "scripts/dev/gpu_determinism_study/run_on_pod.sh").read_text()
    exported = re.search(r'export XLA_FLAGS="([^"]+)"', runner).group(1).split()
    assert tuple(exported) == development.PINNED_XLA_FLAGS
    assert f"NVIDIA_TF32_OVERRIDE={development.PINNED_NVIDIA_TF32_OVERRIDE}" in runner
    assert (
        f'CUBLAS_WORKSPACE_CONFIG="{development.PINNED_CUBLAS_WORKSPACE_CONFIG}"'
        in runner
    )
