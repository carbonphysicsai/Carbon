"""Exact-coherence proof for the protected support-authority request."""

from __future__ import annotations

import pickle
from dataclasses import replace

import pytest
from b03_fixtures import challenge_owner, make_b03_fixture

from carbon.generators.authorities import SupportExclusionRequest
from carbon.generators.errors import GeneratorValidationError
from carbon.generators.service import generate_fixture_case


@pytest.fixture(scope="module")
def support_request() -> SupportExclusionRequest:
    fixture = make_b03_fixture()
    observed: list[SupportExclusionRequest] = []

    class CapturingSupportAuthority:
        def assess_support_exclusion(self, request: object) -> object:
            assert type(request) is SupportExclusionRequest
            observed.append(request)
            return fixture.support_authority.assess_support_exclusion(request)

    generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=CapturingSupportAuthority(),
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    assert len(observed) == 1
    return observed[0]


def test_support_request_is_redacted_and_rejects_generic_serialization(
    support_request: SupportExclusionRequest,
) -> None:
    assert repr(support_request) == "SupportExclusionRequest(<protected>)"
    assert str(support_request) == repr(support_request)
    with pytest.raises(TypeError):
        pickle.dumps(support_request)


@pytest.mark.parametrize(
    ("field_name", "ref_kind"),
    (
        ("source_event_ref", "generation_event"),
        ("protected_payload_ref", "protected_case_payload"),
        ("attempt_ref", "protected_attempt_commitment"),
    ),
)
def test_support_request_rejects_same_challenge_non_echoing_refs(
    support_request: SupportExclusionRequest,
    field_name: str,
    ref_kind: str,
) -> None:
    forged = challenge_owner(
        ref_kind,
        f"forged_{field_name}",
        challenge_key=support_request.challenge_key,
    )

    with pytest.raises(GeneratorValidationError) as caught:
        replace(support_request, **{field_name: forged})

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
