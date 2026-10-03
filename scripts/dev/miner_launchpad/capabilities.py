"""The Control Center's capability contract, built from runtime truth.

`carbon.control-center.capabilities.v1` is what the browser renders every
launch choice from. Nothing here is a hard-coded list of choices: Challenges
come from `carbon.challenge_registry` (catalog and describe), who selects comes
from the shared `options` operation, model providers are the agent's own
transport and the registered provider adapters (the miner chooses and holds
the credential; availability is the profile's key file for each), compute is what the runner profile's runtime
assembles, tools come from each Challenge's own description, and the budget
vocabulary is the ledger's.

Anything Carbon does not offer is listed as unavailable with a reason and the
next action, never as a working choice. Reading this document grants no
authority, starts nothing and reads no chain.
"""

from __future__ import annotations

import functools

SCHEMA = "carbon.control-center.capabilities.v1"

#: The one execution profile the launch path resolves (`runner._challenge`).
LAUNCH_PROFILE = "cpu_research"

NO_PROFILE = {
    "reason": "research_profile_not_configured",
    "next_action": (
        "Finish Set up your environment (after Wallet & Identity confirms your "
        "registration): the profile it writes loads at once. Launching needs "
        "only your subnet registration, read at launch."
    ),
}


def _unavailable(reason, next_action, **extra):
    return {
        "availability": "unavailable",
        "reason": reason,
        "next_action": next_action,
        **extra,
    }


def _integrations(category):
    from scripts.dev.miner_launchpad.controller import (
        INTEGRATION_PLACEMENT,
        INTEGRATIONS,
    )

    found = []
    for item in INTEGRATIONS:
        placed, next_action = INTEGRATION_PLACEMENT.get(item["id"], (None, None))
        if placed == category:
            found.append(
                {"id": item["id"], **_unavailable(item["reason"], next_action)}
            )
    return found


def _profile(runner):
    """The runner profile's state: configured, disabled, or absent."""
    if runner is None:
        return None, {"configured": False, **NO_PROFILE}
    try:
        cfg = runner.configured()
    except Exception as refused:  # noqa: BLE001 - the code only, never content
        code = getattr(refused, "code", "research_profile_unavailable")
        return None, {
            "configured": False,
            "reason": code,
            "next_action": (
                "Check the runner profile: dispatch must be enabled and its "
                "runtime one this runner can assemble. Campaigns you already "
                "have stay observable and stoppable."
            ),
        }
    return cfg, {"configured": True, "profile_id": cfg.get("profile_id")}


def _options(runner):
    """The shared `options` operation, exactly as an MCP client reads it."""
    if runner is None:
        return None, NO_PROFILE
    from scripts.dev.miner_launchpad.operations import perform

    try:
        return perform(runner, "options", {}), None
    except Exception as refused:  # noqa: BLE001 - the code only, never content
        return None, {
            "reason": getattr(refused, "code", "launch_options_unreadable"),
            "next_action": "Check the runner profile, then re-read capabilities.",
        }


def _host_facts(cfg):
    from carbon.miner_mcp.mcp_challenges import configured_host_facts

    return configured_host_facts(cfg)


def _composed(challenge_id, version):
    from carbon.challenge_registry import ResolutionError
    from carbon.challenge_registry.campaigns import campaign_for

    try:
        campaign_for({"id": challenge_id, "version": version})
    except ResolutionError as refused:
        return refused.public()
    return None


def _tools(description):
    """What a miner uses on this Challenge, from its own description."""
    models = description.get("models", {})
    return {
        "workflow": dict(description.get("workflow", {})),
        "public_material": list(
            description.get("public_material", {}).get("names", [])
        ),
        "rebuildable_models": [m["selector"] for m in models.get("rebuildable", [])],
        "limits": dict(description.get("limits", {})),
        "how_to_request_unsupported": description.get("how_to_request_unsupported"),
    }


def _provisions(challenge_id):
    """The research environment the Challenge declares (OWNER-RESEARCH-
    ENVIRONMENT-01): each provision provided, or a named gap. None when the
    Challenge declares none yet (a reserved or deferred one)."""
    from carbon.challenge_kit.standard import ENVIRONMENTS, Gap, Retired

    table = ENVIRONMENTS.get(challenge_id)
    if table is None:
        return None
    if isinstance(table, Retired):
        return {"retired": table.decision}
    return {
        name: (
            {"status": "gap", "reason": status.reason, "next_step": status.next_step}
            if isinstance(status, Gap)
            else {"status": "provided", "note": status.note}
        )
        for name, status in table.items()
    }


def _setup_offers(entry):
    """What setup and launch offer for an implemented Challenge, read from its
    own campaign; nothing for one that cannot be launched."""
    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.challenge_registry.registry import GPU_RESEARCH, IMPLEMENTED

    none = {"gpu": False, "intake": False, "feedback_modes": []}
    if entry["status"] != IMPLEMENTED:
        return none
    try:
        campaign = campaign_for(
            {"id": entry["challenge_id"], "version": entry["version"]}
        )
    except Exception:  # noqa: BLE001 - a Challenge without a campaign offers nothing
        return none
    gpu = GPU_RESEARCH in {p["profile"] for p in entry["profiles"]} and (
        campaign.gpu_scope is not None
    )
    return {
        "gpu": gpu,
        "intake": campaign.intake_check is not None,
        "feedback_modes": list(campaign.feedback_modes),
    }


def _challenges(profile_state, host):
    from carbon.challenge_registry import catalog, describe
    from carbon.challenge_registry.registry import (
        DEFERRED,
        IMPLEMENTED,
        RESERVED,
        ChallengeDeferred,
        ChallengeNotImplemented,
    )

    result = []
    for entry in catalog(host)["challenges"]:
        profiles = [p for p in entry["profiles"] if p["profile"] == LAUNCH_PROFILE]
        profile = profiles[0] if profiles else None
        item = {
            "challenge_id": entry["challenge_id"],
            "version": entry["version"],
            "title": entry["title"],
            "status": entry["status"],
            "portfolio": entry["portfolio"],
            "tracking": entry["tracking"],
            "profile": LAUNCH_PROFILE if profile else None,
            "implemented": entry["status"] == IMPLEMENTED,
            "usable_here": bool(profile and profile["usable_here"]),
            "missing_here": list(profile["missing_here"]) if profile else [],
            # Everything the miner weighs when choosing what to mine
            # (C-MLP-04): every execution profile, the research provisions,
            # and what setup offers for this Challenge.
            "profiles": [
                {
                    "profile": p["profile"],
                    "summary": p["summary"],
                    "usable_here": p["usable_here"],
                    "missing_here": list(p["missing_here"]),
                }
                for p in entry["profiles"]
            ],
            "provisions": _provisions(entry["challenge_id"]),
            "setup_offers": _setup_offers(entry),
        }
        refusal = None
        if entry["status"] == RESERVED:
            refusal = {
                "code": ChallengeNotImplemented.code,
                "next_action": "Follow " + str(entry["tracking"]) + ".",
            }
        elif entry["status"] == DEFERRED:
            refusal = {
                "code": ChallengeDeferred.code,
                "next_action": ChallengeDeferred.next_action,
            }
        elif profile is None:
            refusal = {
                "code": "execution_profile_unavailable",
                "next_action": "This Challenge has no " + LAUNCH_PROFILE + " profile.",
            }
        else:
            refusal = _composed(entry["challenge_id"], entry["version"])
        if item["implemented"]:
            description = describe(entry["challenge_id"], entry["version"], host=host)
            item["description"] = description
            item["tools"] = _tools(description)
            examples = description.get("examples") or []
            item["example_strategy"] = examples[0]["strategy"] if examples else None
        if refusal is None and not profile_state["configured"]:
            refusal = {
                "code": profile_state["reason"],
                "next_action": profile_state["next_action"],
            }
        # Selectable is what the launch path accepts: implemented, composed as a
        # campaign, and a configured profile to launch it. Host readiness is
        # reported beside it (usable_here, missing_here), never assumed.
        item["selectable"] = refusal is None
        if refusal is not None:
            item["reason"] = refusal["code"]
            item["next_action"] = refusal["next_action"]
        result.append(item)
    # The launch portfolio first; the historical DEVELOPMENT Challenge after it.
    order = {"launch": 0, "historical_development": 1, "deferred": 2}
    result.sort(key=lambda c: (order.get(c["portfolio"], 3), not c["implemented"]))
    return result


def _agents(options, refusal):
    offered = {a["value"]: a for a in (options or {}).get("agents", [])}

    def state(launch_agent):
        if options is None:
            return _unavailable(refusal["reason"], refusal["next_action"])
        agent = offered.get(launch_agent)
        if agent is None:
            return _unavailable(
                "not_offered_by_launch_options", "Re-read capabilities."
            )
        if agent["availability"] == "available":
            return {"availability": "available"}
        next_action = {
            "model_provider_key_not_configured": (
                "Add api_key_file to your runner profile, or choose Manual or "
                "your own agent over MCP."
            )
        }.get(agent.get("reason"), "Choose another agent.")
        return _unavailable(agent.get("reason"), next_action)

    return {
        "choices": [
            {
                "id": "autonomous",
                "label": "Carbon's autonomous agent",
                "summary": "Carbon's agent researches, freezes and submits within your budget.",
                "launch_agent": "autonomous",
                "uses_model": True,
                **state("autonomous"),
            },
            {
                "id": "manual",
                "label": "Manual",
                "summary": "You practice, freeze and submit from this browser. No model is called.",
                "launch_agent": "none",
                "uses_model": False,
                **state("none"),
            },
            {
                "id": "external_mcp",
                "label": "Your own agent over MCP",
                "summary": (
                    "Launches with no Carbon agent; your own MCP client drives "
                    "practice, freeze and submit through the same operations, "
                    "over stdio, with nothing issued by Carbon."
                ),
                "launch_agent": "none",
                "uses_model": False,
                "door": "stdio",
                "command": "carbon-mcp --configuration <your runner profile>",
                **state("none"),
            },
        ],
        "unavailable": _integrations("agent"),
    }


@functools.lru_cache(maxsize=1)
def _implemented_transport():
    """The one provider transport the agent implements today, as it states it."""
    from carbon.development_session.agent import proposal

    value = proposal()
    return value["provider"], value["model"]


def _model(options, refusal):
    """Model providers the miner can choose, each with its own credential.

    The miner chooses the provider and model and supplies the credential; Carbon
    holds none. The pinned default is reported first, from the agent's own
    transport rather than named as Carbon's model; the registered provider
    adapters follow, each available only when the runner profile configures
    its key file. A launch names one with `model_provider` and `model`.
    """
    provider, model = _implemented_transport()
    if options is None:
        credential = {"configured": None, "basis": "NOT_READ: " + refusal["reason"]}
        state = _unavailable(refusal["reason"], refusal["next_action"])
    else:
        autonomous = next(
            (a for a in options["agents"] if a["value"] == "autonomous"), None
        )
        ready = bool(autonomous and autonomous["availability"] == "available")
        credential = {"configured": ready, "basis": "read from your runner profile"}
        state = (
            {"availability": "available"}
            if ready
            else _unavailable(
                "model_provider_key_not_configured",
                "Point api_key_file in your runner profile at your own key file.",
            )
        )
    return {
        "used_by": ["autonomous"],
        "chosen_by": "miner",
        "providers": [
            {
                "id": "openai-responses",
                "provider": provider,
                "models": [{"id": model, "availability": "available"}],
                "credential": {
                    "reference": "api_key_file in your runner profile",
                    "held_by": "you; Carbon never stores or transmits it",
                    **credential,
                },
                **state,
            },
            *_registered_providers(options, refusal),
        ],
        "launch_field": ["model_provider", "model"],
        "selection": (
            "The launch carries model_provider and model. The key file is the "
            "one your runner profile configures for that provider; a provider "
            "without one is refused, never replaced by another."
        ),
        "unavailable": _integrations("model_provider"),
    }


_CREDENTIAL_NEXT = {
    "model_provider_credential_not_configured": (
        "Add provider_credentials.{id} to your runner profile, pointing at "
        "your own key file."
    ),
    "model_provider_credential_unusable": (
        "Make provider_credentials.{id} a regular, owner-only file of at "
        "most 1024 bytes in an owner-only directory."
    ),
    "model_provider_endpoint_not_configured": (
        "This adapter needs your endpoint URL. Choose it under Set up your "
        "environment, Inference, with your endpoint and its price; a launch "
        "then uses it."
    ),
}


def _registered_providers(options, refusal):
    """The other registered provider adapters (`model_provider.ADAPTERS`),
    each with this profile's availability from the shared `options`
    operation. Only an available one is selectable."""
    from carbon.development_session.model_provider import ADAPTERS

    offered = {
        row["provider_id"]: row for row in (options or {}).get("model_providers", [])
    }
    rows = []
    for provider_id, adapter in ADAPTERS.items():
        if provider_id == "openai-responses":
            continue  # Listed first, from the agent's own transport.
        row = offered.get(provider_id)
        if options is None or row is None:
            credential = {
                "configured": None,
                "basis": "NOT_READ: " + refusal["reason"],
            }
            state = _unavailable(refusal["reason"], refusal["next_action"])
        else:
            reason = row.get("reason")
            credential = {
                "configured": reason
                not in (
                    "model_provider_credential_not_configured",
                    "model_provider_endpoint_not_configured",
                ),
                "basis": "key file metadata from your runner profile; no key read",
            }
            state = (
                {"availability": "available"}
                if row["availability"] == "available"
                else _unavailable(
                    reason,
                    _CREDENTIAL_NEXT.get(reason, "Choose another provider.").format(
                        id=provider_id
                    ),
                )
            )
        models = [m["model_id"] for m in adapter.summary_models()]
        rows.append(
            {
                "id": provider_id,
                "provider": adapter.display_name,
                "models": [{"id": m, "availability": "available"} for m in models],
                "default_model": adapter.default_model,
                "credential": {
                    "reference": "provider_credentials."
                    + provider_id
                    + " in your runner profile",
                    "held_by": "you; Carbon never stores or transmits it",
                    **credential,
                },
                **state,
            }
        )
    return rows


def _compute(cfg, options, refusal, host):
    from scripts.dev.miner_launchpad.controller import research_compute_choices

    docker = "docker_cli" in host.facts
    if cfg is None:
        local = _unavailable(refusal["reason"], refusal["next_action"])
    elif not docker:
        local = _unavailable(
            "docker_cli_not_found",
            "Install a container runtime on this machine.",
        )
    else:
        local = {"availability": "available"}
    lanes = {"cpu": {"availability": "configured"} if cfg else local}
    for lane, state in ((options or {}).get("research_lanes") or {}).items():
        lanes[lane] = state
    return {
        "choices": [
            {
                "id": "local-isolated-worker",
                "label": "This machine · isolated Docker worker",
                "lane": (
                    "gpu" if cfg and "gpu_research" in cfg.get("runtime", {}) else "cpu"
                ),
                "lanes": lanes,
                "host_facts": sorted(host.facts),
                **local,
            }
        ],
        "selection": "Set by your runner profile's runtime; the launch carries no compute field.",
        "destinations": research_compute_choices(),
        "unavailable": _integrations("compute_provider"),
    }


def _budget():
    from carbon.development_session.product_campaign import BUDGET_KEYS
    from carbon.development_session.research_ledger import DIMENSIONS

    return {
        "keys": sorted(BUDGET_KEYS),
        "ceilings": list(DIMENSIONS),
        "elapsed_seconds": "a whole number of seconds, at least 1",
        "final_reserve": "hold back a final phase so the run can finish",
        "blank": "no limit",
        "bounds": "Carbon sets none: blank is no limit, never a default.",
    }


def _launch():
    from scripts.dev.miner_launchpad.operations import describe

    launch = next(op for op in describe() if op["operation"] == "launch")
    return {
        **launch,
        "browser_sends": [
            "profile",
            "agent",
            "challenge",
            "challenge_version",
            "budget",
            "review_digest",
            "model_provider",
            "model",
        ],
        "challenge_default": None,
    }


def control_center(runner=None):
    """The whole capability document for one controller."""
    cfg, profile_state = _profile(runner)
    options, options_refusal = _options(runner)
    refusal = options_refusal or NO_PROFILE
    host = _host_facts(cfg)
    return {
        "schema": SCHEMA,
        "mode": "DEVELOPMENT",
        "authority": "Discovery grants no authority; nothing here is qualified, paid or on chain.",
        "profile": profile_state,
        "challenges": _challenges(profile_state, host),
        "agents": _agents(options, refusal),
        "model": _model(options, refusal),
        "compute": _compute(cfg, options, refusal, host),
        "budget": _budget(),
        "launch": _launch(),
        "connections": _integrations("connection"),
        "wallet": _integrations("wallet"),
    }
