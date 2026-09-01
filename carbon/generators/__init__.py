"""Curated audience-safe contracts for the deterministic fixture generator.

Protected requests, results, accounting, conformance, capabilities, services,
and raw reference issuance remain available only from their owning modules.
"""

from .burgers import (
    BurgersFixtureConfiguration,
    BurgersProductionInputsUnavailable,
    ProductionInputAvailability,
    burgers_fixture_configuration,
    burgers_fixture_configuration_ref,
    burgers_production_inputs_unavailable,
)
from .disclosure import (
    GeneratorProvenanceMarker,
    PublicGenerationProjection,
    create_public_generation_projection,
)
from .model import (
    GenerationRoleBinding,
    GeneratorDescriptor,
    GeneratorEnvironmentClass,
    GeneratorEnvironmentDescriptor,
    GeneratorOutcomeKind,
)
from .refs import BurgersFixtureConfigurationRef, GeneratorEnvironmentRef

__all__ = [
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
]
