"""The environment check, exercised on the case it exists for.

The runner's integration test can only be run against whatever image is present,
so a genuine version mismatch was unexercised: the refusal mechanism had been
seen to fire, but only on a bug, never on the case it was written for.

The comparison is pure, so that gap closes without a second image, a pull or a
device. Fabricated values in, `mismatched` and `unverifiable` out.

What remains untestable here is narrower than it first appeared, and worth naming
precisely: whether the *readers* return correct values inside a different real
image. That is a property of the image and the plugin build, not of this logic,
and no unit test can establish it.
"""

from __future__ import annotations

import pytest

from carbon.reconstruction.environment_guard import (
    DECLARED_PROPERTIES,
    NOT_A_DIGEST_CHECK,
    environment_check_record,
    environment_problems,
)

DECLARED = {
    "profile_id": "carbon_jax_cuda13_nvidia_development_v1",
    "python": "3.11.16",
    "jax": "0.10.2",
    "jaxlib": "0.10.2",
}
MATCHING = {"python": "3.11.16", "jax": "0.10.2", "jaxlib": "0.10.2"}
CUDA_13 = 13000


def test_the_declared_environment_passes():
    mismatched, unverifiable = environment_problems(
        declared=DECLARED, found=MATCHING, cuda_version=CUDA_13
    )
    assert mismatched == []
    assert unverifiable == []


# --- the case the guard exists for ---------------------------------------------


@pytest.mark.parametrize("name", DECLARED_PROPERTIES)
def test_a_readable_but_different_version_is_a_mismatch(name):
    """The case an integration test on one image cannot reach.

    A version that reads perfectly well and is not the declared one. This is the
    realistic pod failure - a tag instead of a digest resolving to a neighbouring
    build - and it must refuse rather than proceed.
    """
    found = {**MATCHING, name: "9.9.9"}
    mismatched, unverifiable = environment_problems(
        declared=DECLARED, found=found, cuda_version=CUDA_13
    )
    assert len(mismatched) == 1
    assert name in mismatched[0]
    assert "9.9.9" in mismatched[0]
    assert DECLARED[name] in mismatched[0]
    assert unverifiable == []


def test_several_mismatches_are_all_reported():
    """A caller should not have to re-run to discover the second problem."""
    found = {"python": "3.12.0", "jax": "0.11.0", "jaxlib": "0.10.2"}
    mismatched, _ = environment_problems(
        declared=DECLARED, found=found, cuda_version=CUDA_13
    )
    assert len(mismatched) == 2


def test_a_different_cuda_line_is_a_mismatch():
    mismatched, unverifiable = environment_problems(
        declared=DECLARED, found=MATCHING, cuda_version=12080
    )
    assert len(mismatched) == 1
    assert "CUDA runtime major is 12" in mismatched[0]
    assert unverifiable == []


# --- unknown must not become a definite claim ----------------------------------


@pytest.mark.parametrize("unreadable", [None, "13.0", 13.0, "", {}])
def test_an_unreadable_cuda_version_is_unverifiable_not_mismatched(unreadable):
    """The inverse of the observation rule, and the bug this module was born from.

    Refusing on "could not check" is the same error as recording "could not
    observe" as "nothing was there". The first version of this logic treated an
    unreadable CUDA version as a mismatch and refused every run on a build whose
    readers are absent - including correct ones.
    """
    mismatched, unverifiable = environment_problems(
        declared=DECLARED, found=MATCHING, cuda_version=unreadable
    )
    assert mismatched == []
    assert len(unverifiable) == 1
    assert "not verified" in unverifiable[0]


def test_an_unreadable_cuda_version_does_not_mask_a_real_mismatch():
    """Unverifiable is not a free pass for the properties that *can* be read."""
    found = {**MATCHING, "jaxlib": "0.9.0"}
    mismatched, unverifiable = environment_problems(
        declared=DECLARED, found=found, cuda_version=None
    )
    assert len(mismatched) == 1
    assert len(unverifiable) == 1


def test_a_non_cuda_profile_raises_no_cuda_question():
    declared = {**DECLARED, "profile_id": "carbon_jax_cpu_v1"}
    mismatched, unverifiable = environment_problems(
        declared=declared, found=MATCHING, cuda_version=None
    )
    assert mismatched == []
    assert unverifiable == []


# --- the record must not overstate what was established ------------------------


def test_the_record_says_it_is_not_a_digest_check():
    """A container cannot read its own image digest, and the record must say so.

    Without this the note is one careless edit from implying byte identity with
    the published image, which nothing here establishes.
    """
    record = environment_check_record([])
    assert record["note"] == NOT_A_DIGEST_CHECK
    assert "NOT the image digest" in record["note"]
    assert record["verified"] == list(DECLARED_PROPERTIES)


def test_the_record_carries_what_was_not_checked():
    _, unverifiable = environment_problems(
        declared=DECLARED, found=MATCHING, cuda_version=None
    )
    record = environment_check_record(unverifiable)
    assert record["unverifiable"] == unverifiable
    assert record["unverifiable"], "an incomplete check must be visible in the record"


def test_the_record_cannot_be_mutated_through_its_source():
    """Callers share this record; one caller must not edit another's."""
    unverifiable = ["something unreadable"]
    record = environment_check_record(unverifiable)
    unverifiable.append("added later")
    assert record["unverifiable"] == ["something unreadable"]
