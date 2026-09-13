"""Compiler-produced C-02 development plans for focused tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from b02b_fixtures import make_compile_fixture, strategy_limits

from carbon.construction import (
    BackboneSurfaceContract,
    ChoiceDomain,
    CompileAccepted,
    ConsumerTarget,
    DependencyPin,
    EnvironmentPin,
    ImplementationPin,
    InterfaceDirection,
    InterfacePin,
    SurfaceValue,
    SurfaceValueType,
    UInt64RangeDomain,
    ValueCompatibilityCell,
    compile_strategy,
)
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
from carbon.reconstruction.profile import (
    DEPENDENCY_SPECS,
    ENVIRONMENT_DIGEST,
    ENVIRONMENT_ID,
    ENVIRONMENT_VERSION,
    IMPLEMENTATION_ID,
    IMPLEMENTATION_VERSION,
    INPUT_INTERFACE_DIGEST,
    OUTPUT_INTERFACE_DIGEST,
    UPSTREAM_WHEEL_DIGEST,
)


def compile_c02_plan(
    tmp_path: Path,
    *,
    backbone: str = "fno",
    steps: int = 2,
    wheel_digest: str = UPSTREAM_WHEEL_DIGEST,
    environment_digest: str = ENVIRONMENT_DIGEST,
):
    fixture = make_compile_fixture(tmp_path)
    old_option = fixture.assembly.backbone_surface.options[0]
    implementation = ImplementationPin(
        IMPLEMENTATION_ID, IMPLEMENTATION_VERSION, wheel_digest
    )
    environment = EnvironmentPin(
        ENVIRONMENT_ID, ENVIRONMENT_VERSION, environment_digest
    )
    dependencies = tuple(DependencyPin(*spec) for spec in DEPENDENCY_SPECS)
    input_pin = InterfacePin(
        "carbon_jax_burgers_input",
        "1.0",
        INPUT_INTERFACE_DIGEST,
        InterfaceDirection.INPUT,
    )
    output_pin = InterfacePin(
        "carbon_jax_burgers_output",
        "1.0",
        OUTPUT_INTERFACE_DIGEST,
        InterfaceDirection.OUTPUT,
    )
    backbone_target = ConsumerTarget("carbon_jax_lab_model", "kind")

    def option(selector: str, backbone_id: str):
        return replace(
            old_option,
            selector_token=selector,
            backbone_id=backbone_id,
            backbone_version="1.0",
            content_digest=wheel_digest,
            implementation_pin=implementation,
            environment_pin=environment,
            dependency_pins=dependencies,
            input_interface_pin=input_pin,
            output_interface_pin=output_pin,
        )

    backbone_surface = BackboneSurfaceContract(
        "strategy_backbone",
        backbone_target,
        (
            option("fno", "carbon_jax_fno1d"),
            option("deeponet", "carbon_jax_deeponet1d"),
        ),
    )
    assembly = replace(
        fixture.assembly,
        backbone_surface=backbone_surface,
        component_slots=(),
        dependency_pins=dependencies,
        environment_pins=(environment,),
    )

    entries = {entry.surface_id: entry for entry in fixture.catalog.entries}
    top = replace(
        entries["strategy_backbone"],
        consumer_target=backbone_target,
        domain=ChoiceDomain(("fno", "deeponet")),
    )
    step_target = ConsumerTarget("carbon_jax_lab_train", "steps")
    training = replace(
        entries["fixture_sampling_level"],
        consumer_target=step_target,
        domain=UInt64RangeDomain(1, 2),
    )
    old_rule = fixture.catalog.compatibility_rules[0]
    rows = tuple(
        (
            ValueCompatibilityCell(
                SurfaceValue(SurfaceValueType.BACKBONE_SELECTOR, selector)
            ),
            ValueCompatibilityCell(SurfaceValue(SurfaceValueType.UINT64, 2)),
        )
        for selector in ("fno", "deeponet")
    )
    compatibility = replace(
        old_rule,
        surface_ids=("strategy_backbone", "fixture_sampling_level"),
        allowed_rows=rows,
    )
    catalog = replace(
        fixture.catalog,
        candidate_assembly_ref=assembly.to_ref(),
        entries=(top, training),
        compatibility_rules=(compatibility,),
    )
    strategy = {
        "schema_version": "1.0",
        "challenge_id": fixture.key.challenge_id,
        "backbone": backbone,
        "parameters": {"fixture_sampling_level": steps},
    }
    result = compile_strategy(
        strategy,
        challenge_key=fixture.key,
        candidate_assembly=assembly,
        candidate_assembly_ref=assembly.to_ref(),
        parameter_catalog=catalog,
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=assembly),
        authoring_origin=fixture.authoring_origin,
        authoring_artifacts=fixture.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )
    assert type(result) is CompileAccepted, result
    return result.construction_plan


__all__ = ["compile_c02_plan"]
