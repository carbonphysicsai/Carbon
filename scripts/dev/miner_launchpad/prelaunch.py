"""Read-only, allow-listed review of a miner's configured campaign, never admission.

Admission is subnet registration, read at launch (C-MLP-02-D11). This review
reports that it will be read; it does not read it, and a clean review is not a
registration.

Where a frozen candidate is evaluated is stated before launch (LP-PROD-E): for
each Challenge submitted through an intake, the profile's intake and whether
it is the endpoint Carbon publishes, or plainly that none is published yet.
Only a published endpoint's URL is shown; a miner's own intake and validator
paths stay private.

No backend initialization, key access, ledger creation or task execution occurs.
Expected dependencies and configured identities are not observations or evidence.
"""

from __future__ import annotations

from carbon.development_session.research_catalog import public_catalog
from carbon.development_session.research_ledger import SERVICE_LIMITS
from carbon.reconstruction.profile import DEPENDENCY_SPECS, ENVIRONMENT_ID
from scripts.dev.miner_launchpad.runner import (
    REQUIRED_RUNTIME_KEYS,
    SUPPORTED_RUNTIME_KEYS,
)

#: Each Challenge's evaluation endpoint, as the review states it.
ENDPOINT_STATES = (
    "INTAKE_CONFIGURED",
    "VALIDATOR_ON_THIS_MACHINE",
    "PUBLISHED_REVIEW_AGAIN",
    "NONE_PUBLISHED",
)


def evaluation(cfg):
    """Where a frozen candidate of each Challenge is evaluated, from the
    profile's intakes and validators and the endpoints Carbon publishes
    (LP-PROD-E). Configuration only: an endpoint is reached when a candidate
    is submitted, never here."""
    from scripts.dev.miner_launchpad.environment_setup import (
        NO_ENDPOINT,
        intake_challenges,
        published_endpoints,
    )
    from scripts.dev.miner_launchpad.runner import intakes, validators

    published = published_endpoints()["endpoints"]
    configured = intakes(cfg)
    local = validators(cfg) if type(cfg.get("paths")) is dict else {}
    challenges = []
    for challenge in intake_challenges():
        entry = published.get(challenge["id"])
        url = configured.get(challenge["id"])
        item = {"challenge_id": challenge["id"], "title": challenge["title"]}
        if type(url) is str:
            mine = not (entry and entry["intake_url"] == url)
            item.update(
                status="INTAKE_CONFIGURED",
                source="YOURS" if mine else "PUBLISHED",
                **({} if mine else {"intake": url}),
            )
        elif challenge["id"] in local:
            item.update(status="VALIDATOR_ON_THIS_MACHINE", source="YOURS")
        elif entry is not None:
            item.update(
                status="PUBLISHED_REVIEW_AGAIN",
                source="PUBLISHED",
                intake=entry["intake_url"],
                next_step="Carbon has published an evaluation endpoint for "
                + challenge["title"]
                + " since this profile was written: review again in setup "
                "to add it.",
            )
        else:
            item.update(
                status="NONE_PUBLISHED",
                source=None,
                next_step=NO_ENDPOINT.format(title=challenge["title"]),
            )
        challenges.append(item)
    ready = [item["status"] in ENDPOINT_STATES[:2] for item in challenges]
    if not ready:
        summary = "NO_CHALLENGE_SUBMITS_THROUGH_AN_INTAKE"
    elif all(ready):
        summary = "CONFIGURED_FOR_ALL"
    else:
        summary = "CONFIGURED_FOR_SOME" if any(ready) else "NOT_CONFIGURED"
    return {
        "challenges": challenges,
        "configured": summary,
        "basis": "CONFIGURATION_ONLY; an evaluation endpoint is reached when you submit a frozen candidate, never by this review. Practice and freezing need none.",
    }


def review(cfg):
    runtime = cfg.get("runtime")
    if type(runtime) is not dict:
        raise ValueError("unsupported review contract")
    # Historical engineering fixtures may have nominal runtime values. These
    # do not become asserted image identities in the new review projection.
    implementation = runtime.get("implementation")
    identities = {}
    if type(implementation) is dict:
        for name in ("revision", "tree", "source_tree_digest"):
            value = implementation.get(name)
            if (
                type(value) is not str
                or len(value) > 80
                or any(
                    c not in "0123456789abcdef:" for c in value.removeprefix("sha256:")
                )
            ):
                raise ValueError("invalid configured runtime identity")
            identities[name] = value
    images = runtime.get("images", [])
    if type(images) is not list or len(images) > 8:
        raise ValueError("invalid image identities")
    images = [
        v
        for v in images
        if type(v) is str
        and len(v) == 71
        and v.startswith("sha256:")
        and all(c in "0123456789abcdef" for c in v[7:])
    ]
    catalog = public_catalog()
    try:
        endpoints = evaluation(cfg)
    except (ValueError, TypeError, LookupError, AttributeError, OSError):
        # A profile whose intakes cannot be read states that, never a guess.
        endpoints = {
            "challenges": [],
            "configured": "NOT_READABLE",
            "basis": "CONFIGURATION_ONLY; this profile's intakes could not be read.",
        }
    blockers = []
    if cfg.get("disabled_reason") == "OWNER_EXPERIMENT_PAUSE":
        blockers.append("OWNER_EXPERIMENT_PAUSE")
    if cfg.get("enabled") is not True:
        blockers.append("OPERATOR_DISPATCH_DISABLED")
    if type(implementation) is dict and cfg.get(
        "accepted_revision"
    ) != implementation.get("revision"):
        blockers.append("RUNTIME_REVISION_MISMATCH")
    if not set(runtime) <= SUPPORTED_RUNTIME_KEYS:
        blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
    if not REQUIRED_RUNTIME_KEYS <= set(runtime):
        blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
    research_execution = {"profile": ENVIRONMENT_ID, "backend": "cpu"}
    assurance = None
    if "gpu_research" in runtime:
        from carbon.challenge_registry.campaigns import declared_gpu
        from carbon.reconstruction.accelerators import GPU_PROFILE, miner_lane_assurance

        try:
            declared_gpu(runtime)
        except (ValueError, KeyError, TypeError, LookupError):
            # A declared GPU runtime whose scope is malformed is not a GPU
            # campaign. Reviewing it as one would show a miner a cuda backend
            # the runner would refuse to assemble, which is the mismatch this
            # projection exists to prevent.
            blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
        else:
            research_execution = {
                "profile": GPU_PROFILE.profile_id,
                "backend": GPU_PROFILE.backend.value,
            }
            assurance = miner_lane_assurance()
    if "remote_gpu" in runtime and assurance is not None:
        from carbon.challenge_registry.campaigns import declared_remote

        try:
            scope = declared_remote(runtime)
        except (ValueError, KeyError, TypeError, LookupError):
            blockers.append("LAUNCHPAD_CAMPAIGN_RUNTIME_COMPOSITION_UNAVAILABLE")
        else:
            # Where the GPU practice runs: the miner's own remote machine or
            # container. Its address is the profile's and is not shown here.
            research_execution["remote"] = {
                "transport": scope["transport"],
                "image_verified_by": scope["image_verified_by"],
                "job_transport": scope["job_transport"],
                "started_stopped_and_billed_by": "YOU; CARBON NEVER DOES",
            }
    return {
        "schema": "carbon.launchpad.prelaunch-review.v1",
        "experiment_pause": (
            "ACTIVE"
            if cfg.get("disabled_reason") == "OWNER_EXPERIMENT_PAUSE"
            else "NOT_DECLARED"
        ),
        "dispatch_enabled": cfg.get("enabled") is True,
        "blockers": blockers,
        "admission": {
            "gate": "SUBNET_REGISTRATION",
            "checked": "AT_LAUNCH_BEFORE_ANYTHING_IS_RECORDED",
            "basis": "Registration on the subnet is the only thing that admits a campaign. It is read from the chain when you launch, and again on every research call. No grant or approval exists on this path.",
        },
        "resources": {
            "miner_budget": "SET_AT_LAUNCH_OR_NONE",
            "carbon_service_limits": dict(SERVICE_LIMITS),
            "basis": "Your budget is yours to set when you launch, per dimension, or not at all; with none set, nothing is capped and nothing is blocked. Carbon's service limits bound Carbon's own shared reference service, never your resources. CampaignLedger owns actual usage and reservations.",
        },
        "runtime": {
            "implementation": identities,
            "images": images,
            "basis": "CONFIGURATION_ONLY; exact accepted revision and images checked at execution",
        },
        # Two separately described runtimes, deliberately not merged into one
        # badge. The miner chooses where their research runs; they do not choose
        # what judges it. Showing a GPU here while the comparison below stays CPU
        # is the accurate picture, not an inconsistency.
        "execution": {
            **research_execution,
            "scope": "MINER_RESEARCH_ONLY",
            "lane": (
                "MINER_CONTAINED" if assurance is not None else "CPU_NO_ACCELERATOR"
            ),
            "assurance": assurance,
            "basis": (
                "CONFIGURATION_ONLY; this is the runtime the miner's own research runs on"
            ),
            "installed_dependencies": "NOT_INSPECTED",
            "device_visibility": "NOT_OBSERVED",
            "runtime_evidence": "NOT_ATTACHED",
            "admission_readiness": "NOT_ESTABLISHED_BY_REVIEW",
            "compiled_updates": "DEFAULT_UNCHANGED; no GPU speedup inferred",
        },
        "final_evaluation": {
            # Stated before launch rather than discovered afterwards. A GPU
            # research selection neither selects nor rewrites this.
            "profile": ENVIRONMENT_ID,
            "backend": "cpu",
            "route": "INDEPENDENT_DEVELOPMENT_RECONSTRUCTION",
            "selected_by_research_runtime": False,
            "basis": "The independent DEVELOPMENT comparison runs on the accepted CPU reconstruction route regardless of the research runtime chosen above. It is not a GPU-qualified official result.",
        },
        # Recomputed from the runtime actually selected, so an option existing in
        # the interface never by itself advertises a capability.
        "capabilities": {
            "catalog_version": catalog["version"],
            "backbones": catalog["backbones"],
            "training": catalog["training"],
            "surfaces": list(catalog["surfaces"]),
            "julia_scientific_tasks": "authored_research" in runtime,
            # What was actually validated, not which option exists. A malformed
            # GPU scope advertises nothing.
            "gpu_research": assurance is not None,
            # Julia's code cell runs on this machine's GPU lane, in its CUDA
            # environment (JULIA-GPU-01); a remote GPU lane runs run_python only.
            "julia_on_gpu": (
                "authored_research" in runtime
                and assurance is not None
                and "remote_gpu" not in runtime
            ),
            "selection": "Agent selects a legal strategy during research; no trained model selected at prelaunch",
        },
        # Distinct states, never collapsed into one green badge. Review reads
        # configuration; it observes no host, device, dependency or capacity.
        "readiness": {
            "connection_configured": cfg.get("enabled") is True,
            "dependencies_inspected": False,
            "compatible_runtime_available": "NOT_OBSERVED_BY_REVIEW",
            "registration_checked": "AT_LAUNCH",
            "task_admitted": False,
            "device_execution_observed": False,
            "task_completed": False,
            "cleanup_verified": False,
            # Configuration only (LP-PROD-E): which Challenges this profile
            # can submit to, stated before launch rather than learnt at
            # submit. Whether the endpoint answers is observed at submit.
            "independent_development_evaluation_available": endpoints["configured"],
            "official_qualification": False,
            "basis": "Each state is established by its own evidence. Personal research does not require official qualification; a missing runtime does prevent a managed job from executing.",
        },
        # Where a frozen candidate of each Challenge is evaluated (LP-PROD-E).
        "evaluation_endpoints": endpoints,
        "expected_dependencies": [
            {"name": name, "version": version, "identity": identity}
            for name, version, identity in DEPENDENCY_SPECS
        ],
        # The Challenge, its exam environment and its rule are the chosen
        # Challenge's own (C-MLP-04): the miner chooses one at launch from the
        # catalog, and its description publishes what the design is graded
        # on, beside what the miner chose to research with.
        "challenge": "CHOSEN_AT_LAUNCH_FROM_THE_CATALOG",
        "validator_exam_environment": "PUBLISHED_BY_THE_CHOSEN_CHALLENGE",
        "reconstruction": "Fresh independent DEVELOPMENT reconstruction; practice checkpoints do not replace final evaluation",
    }
