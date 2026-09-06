"""Constructor-injected nominal provider interfaces for research v2."""

from __future__ import annotations

from typing import Protocol

from carbon.registry import ChallengeKey

from .model import (
    CancelResearchTaskRequest,
    CancelResearchTaskResult,
    ChallengeInfo,
    CompileStrategyRequest,
    CompileStrategyResult,
    DryValidateRequest,
    DryValidationResult,
    ForecastResourcesRequest,
    GetMockScaffoldRequest,
    GetPriorRequest,
    GetResearchResultRequest,
    GetResearchResultResult,
    InspectPriorAlignmentRequest,
    InspectResourcesRequest,
    InspectResourcesResult,
    InteractionManifest,
    MockScaffold,
    PriorAlignmentResult,
    PriorLookupResult,
    ResourceForecast,
    ServiceCall,
    ServiceReply,
    StartResearchTaskRequest,
    StartResearchTaskResult,
)


class ChallengeCatalogProvider(Protocol):
    def get_challenge_info(self, challenge_key: ChallengeKey) -> ChallengeInfo: ...


class ManifestProvider(Protocol):
    def get_interaction_manifest(
        self, challenge_key: ChallengeKey
    ) -> InteractionManifest: ...


class PublicPriorProvider(Protocol):
    def get_prior(self, request: GetPriorRequest) -> PriorLookupResult: ...


class TestOnlyPriorProvider(Protocol):
    def get_prior(self, request: GetPriorRequest) -> PriorLookupResult: ...


class ScaffoldProvider(Protocol):
    def get_mock_scaffold(self, request: GetMockScaffoldRequest) -> MockScaffold: ...


class ValidationProvider(Protocol):
    def dry_validate(self, request: DryValidateRequest) -> DryValidationResult: ...


class CompilationProvider(Protocol):
    def compile_strategy(
        self, request: CompileStrategyRequest
    ) -> CompileStrategyResult: ...


class PriorAlignmentProvider(Protocol):
    def inspect_prior_alignment(
        self, request: InspectPriorAlignmentRequest
    ) -> PriorAlignmentResult: ...


class ResourceInspectionProvider(Protocol):
    def inspect_resources(
        self, request: InspectResourcesRequest
    ) -> InspectResourcesResult: ...


class ResourceForecastProvider(Protocol):
    def forecast_resources(
        self, request: ForecastResourcesRequest
    ) -> ResourceForecast: ...


class ResearchTaskProvider(Protocol):
    def start_research_task(
        self, request: StartResearchTaskRequest
    ) -> StartResearchTaskResult: ...

    def get_research_result(
        self, request: GetResearchResultRequest
    ) -> GetResearchResultResult: ...

    def cancel_research_task(
        self, request: CancelResearchTaskRequest
    ) -> CancelResearchTaskResult: ...


class ResearchService(Protocol):
    def call(self, call: ServiceCall) -> ServiceReply: ...

    def call_bytes(self, payload: bytes) -> bytes: ...


__all__ = (
    "ChallengeCatalogProvider",
    "CompilationProvider",
    "ManifestProvider",
    "PriorAlignmentProvider",
    "PublicPriorProvider",
    "ResearchService",
    "ResearchTaskProvider",
    "ResourceForecastProvider",
    "ResourceInspectionProvider",
    "ScaffoldProvider",
    "TestOnlyPriorProvider",
    "ValidationProvider",
)
