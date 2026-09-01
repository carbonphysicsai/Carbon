"""Acceptance proof for B-03's deliberately small package-root surface."""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError, fields

import pytest

from carbon import generators
from carbon.generators.burgers import (
    BurgersFixtureConfiguration,
    BurgersProductionInputsUnavailable,
    ProductionInputAvailability,
    burgers_fixture_configuration,
    burgers_production_inputs_unavailable,
)

_PUBLIC_EXPORTS = (
    "BurgersFixtureConfiguration",
    "BurgersFixtureConfigurationRef",
    "BurgersProductionInputsUnavailable",
    "GenerationRoleBinding",
    "GeneratorDescriptor",
    "GeneratorEnvironmentClass",
    "GeneratorEnvironmentDescriptor",
    "GeneratorEnvironmentRef",
    "GeneratorOutcomeKind",
    "GeneratorProvenanceMarker",
    "ProductionInputAvailability",
    "PublicGenerationProjection",
    "burgers_fixture_configuration",
    "burgers_fixture_configuration_ref",
    "burgers_production_inputs_unavailable",
    "create_public_generation_projection",
)
_PROTECTED_ROOT_NAMES = (
    "AttemptAccountingDecision",
    "DerivedSeed",
    "GeneratedFixtureArtifact",
    "GenerationAccountingSummary",
    "GeneratorConformanceFacts",
    "GeneratorImplementationManifest",
    "GeneratorRequest",
    "GeneratorResult",
    "ProtectedBurgersFixturePayload",
    "generator_ref",
    "generate_burgers_fixture",
)
_PRODUCTION_INPUT_FIELDS = (
    "primary_population_law",
    "selection_population_law",
    "selection_density_or_mass",
    "importance_weight",
    "viscosity",
    "parameter_ranges",
    "forcing_law",
    "initial_condition_law",
    "grid_specification",
    "horizon_specification",
    "stratification",
    "exclusions",
    "conformance_estimands",
    "conformance_thresholds",
    "qualification_evidence",
)


def test_package_root_has_the_exact_curated_safe_export_set() -> None:
    assert tuple(generators.__all__) == _PUBLIC_EXPORTS

    reloaded = importlib.import_module("carbon.generators")
    imported = {name: getattr(reloaded, name) for name in reloaded.__all__}
    assert tuple(sorted(imported)) == tuple(sorted(_PUBLIC_EXPORTS))
    for name in _PUBLIC_EXPORTS:
        assert imported[name] is getattr(generators, name)
    for name in _PROTECTED_ROOT_NAMES:
        assert name not in generators.__all__
        assert name not in imported


def test_fixed_fixture_configuration_is_the_only_root_configuration() -> None:
    configuration = generators.burgers_fixture_configuration()

    assert type(configuration) is BurgersFixtureConfiguration
    assert configuration is burgers_fixture_configuration()
    assert configuration.configuration_id == "b03_burgers_structural_fixture"
    assert configuration.configuration_version == "1.0"
    assert configuration.boundary_shape == "PERIODIC_1D"
    assert configuration.period == 1.0
    assert configuration.grid_points == 8
    assert configuration.viscosity == 1.0
    assert configuration.latent_codec_id == "carbon.b03.burgers.fixture-latent.v1"
    with pytest.raises(TypeError):
        BurgersFixtureConfiguration()  # type: ignore[call-arg]
    with pytest.raises(FrozenInstanceError):
        configuration.viscosity = 0.01  # type: ignore[misc]


def test_every_unratified_production_input_fails_closed() -> None:
    unavailable = generators.burgers_production_inputs_unavailable()

    assert type(unavailable) is BurgersProductionInputsUnavailable
    assert unavailable is burgers_production_inputs_unavailable()
    assert (
        tuple(field.name for field in fields(unavailable)) == _PRODUCTION_INPUT_FIELDS
    )
    assert all(
        getattr(unavailable, name) is ProductionInputAvailability.HUMAN_INPUT_REQUIRED
        for name in _PRODUCTION_INPUT_FIELDS
    )
    assert not hasattr(unavailable, "production_configuration")
    assert not hasattr(unavailable, "population")
    assert not hasattr(unavailable, "ranges")
    with pytest.raises(TypeError):
        BurgersProductionInputsUnavailable()  # type: ignore[call-arg]
    with pytest.raises(FrozenInstanceError):
        unavailable.viscosity = 1.0  # type: ignore[misc]
