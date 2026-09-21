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
    FOUNDAX_IMPLEMENTATION_ID,
    FOUNDAX_IMPLEMENTATION_VERSION,
    FOUNDAX_WHEEL_DIGEST,
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
    width: int | None = None,
    n_modes: int | None = None,
    wheel_digest: str = UPSTREAM_WHEEL_DIGEST,
    environment_digest: str = ENVIRONMENT_DIGEST,
    foundax: bool = False,
    challenge_key=None,
):
    """Compile one C-02 development plan.

    `steps` widens the training length (C-CORE-19 item N3). `width` and
    `n_modes` widen the *model*, and they are the dimension that decides tensor
    shapes rather than how many times a shape is reused.

    That distinction is why they are here. With `--xla_gpu_autotune_level=0`
    pinned, the kernel is fixed **per shape**: a new width or mode count selects
    a different fixed kernel whose determinism has never been measured, while a
    larger step count runs the *same* kernel more times. A determinism result at
    `width=8, n_modes=8` therefore says little about the kernels a real workload
    would take.

    All three are opt-in and default to the values the catalog has always
    carried, so a caller that does not ask gets a byte-identical contract and an
    unchanged plan digest. `width` and `n_modes` add surfaces to the parameter
    catalog when requested, which necessarily changes the digest - that is the
    point of making them opt-in rather than always present.

    Bounds and evenness follow `carbon.burgers-autoresearch-recipes.v1`
    (`research_catalog.SURFACES`): width 2-128, n_modes 2-64, both even. Odd
    `n_modes` alias the preceding even value in the installed FNO, and odd width
    is incompatible with the C-02 head count, so both are refused here rather
    than silently producing a model the caller did not ask for.
    """
    if type(steps) is not int or steps < 1:
        raise ValueError("steps must be a positive integer")
    for name, value, ceiling in (("width", width, 128), ("n_modes", n_modes, 64)):
        if value is None:
            continue
        if type(value) is not int or not 2 <= value <= ceiling or value % 2:
            raise ValueError(
                f"{name} must be an even integer within 2..{ceiling}; "
                "the registered catalog rejects odd values as an ignored "
                "degree of freedom"
            )
    if (width is None) != (n_modes is None):
        # Both or neither. Widening one alone would produce a model shape no
        # registered recipe describes, and would make the resulting digest hard
        # to attribute to anything.
        raise ValueError("width and n_modes must be widened together")
    # The step count is pinned in three places, and all three have to move
    # together: the parameter domain, the compatibility rows, and the training
    # support contract's resource lookup. Missing any one of them fails the
    # compile rather than silently producing a plan with the wrong step count.
    sampling_levels = tuple(range(1, max(steps, 2) + 1))
    fixture = make_compile_fixture(
        tmp_path, challenge_key=challenge_key, sampling_levels=sampling_levels
    )
    old_option = fixture.assembly.backbone_surface.options[0]
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

    def option(selector: str, backbone_id: str, *, is_foundax: bool = False):
        source_digest = FOUNDAX_WHEEL_DIGEST if is_foundax else wheel_digest
        implementation = ImplementationPin(
            FOUNDAX_IMPLEMENTATION_ID if is_foundax else IMPLEMENTATION_ID,
            (FOUNDAX_IMPLEMENTATION_VERSION if is_foundax else IMPLEMENTATION_VERSION),
            source_digest,
        )
        return replace(
            old_option,
            selector_token=selector,
            backbone_id=backbone_id,
            backbone_version="0.2.0" if is_foundax else "1.0",
            content_digest=source_digest,
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
            option(
                "fno",
                "foundax_fno1d" if foundax else "carbon_jax_fno1d",
                is_foundax=foundax,
            ),
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
        domain=UInt64RangeDomain(sampling_levels[0], sampling_levels[-1]),
    )
    # The model surfaces, derived from the training one rather than written
    # afresh: same entry shape, same authority plumbing, retargeted at the model
    # component. Built only when asked for, so the default catalog is unchanged.
    model_entries: tuple = ()
    model_columns: tuple = ()
    model_cells: dict[str, object] = {}
    if width is not None:
        from carbon.construction import (
            DiscreteLookupResourceContribution,
            ResourceLookupCase,
        )

        for surface_id, field, value in (
            ("fixture_model_width", "width", width),
            ("fixture_model_modes", "n_modes", n_modes),
        ):
            model_entries += (
                replace(
                    entries["fixture_sampling_level"],
                    surface_id=surface_id,
                    consumer_target=ConsumerTarget("carbon_jax_lab_model", field),
                    domain=UInt64RangeDomain(2, value),
                    static_resource_contributions=(
                        DiscreteLookupResourceContribution(
                            "abstract_units",
                            entries["fixture_sampling_level"]
                            .static_resource_contributions[0]
                            .unit_ref,
                            surface_id,
                            (
                                ResourceLookupCase(
                                    SurfaceValue(SurfaceValueType.UINT64, value),
                                    4 * value,
                                ),
                            ),
                            ("sampling_impact",),
                        ),
                    ),
                ),
            )
            model_columns += (surface_id,)
            model_cells[surface_id] = ValueCompatibilityCell(
                SurfaceValue(SurfaceValueType.UINT64, value)
            )

    old_rule = fixture.catalog.compatibility_rules[0]
    rows = tuple(
        (
            ValueCompatibilityCell(
                SurfaceValue(SurfaceValueType.BACKBONE_SELECTOR, selector)
            ),
            # The requested level only. Admitting every level in the domain
            # would change the catalog for callers asking for the default, and
            # with it every plan digest derived from it.
            ValueCompatibilityCell(SurfaceValue(SurfaceValueType.UINT64, steps)),
            *(model_cells[name] for name in model_columns),
        )
        for selector in ("fno", "deeponet")
    )
    compatibility = replace(
        old_rule,
        surface_ids=("strategy_backbone", "fixture_sampling_level", *model_columns),
        allowed_rows=rows,
    )
    catalog = replace(
        fixture.catalog,
        candidate_assembly_ref=assembly.to_ref(),
        entries=(top, training, *model_entries),
        compatibility_rules=(compatibility,),
    )
    parameters = {"fixture_sampling_level": steps}
    if width is not None:
        parameters["fixture_model_width"] = width
        parameters["fixture_model_modes"] = n_modes
    strategy = {
        "schema_version": "1.0",
        "challenge_id": fixture.key.challenge_id,
        "backbone": backbone,
        "parameters": parameters,
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
