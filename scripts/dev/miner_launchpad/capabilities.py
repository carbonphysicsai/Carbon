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
import os
import shlex
from pathlib import Path

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

_SETUP = ("Continue setup", "#setup")
_INFERENCE = ("Set up inference", "#setup/inference")
_REREAD = ("Re-read capabilities", "#settings")

#: What a blocking reason means to a miner, in one short sentence, and the one
#: place in the Control Center that fixes it, or None when nothing a miner
#: does here changes it (LINKONLY-D10). The reason code and its full next
#: action stay beside it, for the page's Details.
PLAIN = {
    "research_profile_not_configured": ("Finish setup first.", _SETUP),
    "research_profile_unavailable": ("Your profile can't be loaded.", _SETUP),
    "research_dispatch_disabled": ("Your profile has research off.", _SETUP),
    "research_runtime_interface_unavailable": (
        "Your profile's runtime can't run here.",
        _SETUP,
    ),
    "runner_profile_v1_retired": ("Your profile is an old version.", _SETUP),
    "rented_gpu_retired_connect_your_machine": (
        "Your profile names rented compute Carbon no longer runs.",
        ("Set up compute", "#setup/compute"),
    ),
    "launch_options_unreadable": ("Your profile's options can't be read.", _REREAD),
    "not_offered_by_launch_options": ("Your profile doesn't offer this.", _REREAD),
    "docker_cli_not_found": ("Docker isn't installed on this machine.", _REREAD),
    "model_provider_key_not_configured": (
        "Carbon's agent needs your model key.",
        _INFERENCE,
    ),
    "model_provider_credential_not_configured": (
        "This provider has no key yet.",
        _INFERENCE,
    ),
    "model_provider_credential_unusable": (
        "This provider's key file can't be used.",
        _INFERENCE,
    ),
    "model_provider_endpoint_not_configured": (
        "This provider needs your endpoint.",
        _INFERENCE,
    ),
    "challenge_not_implemented": ("Not built yet.", None),
    "challenge_deferred": ("Not offered in this release.", None),
    "challenge_retired": ("Retired.", None),
    "challenge_unknown": ("Not in this registry.", None),
    "challenge_version_unsupported": ("This version isn't offered.", None),
    "challenge_has_no_campaign": ("Not launchable yet.", None),
    "challenge_resolution_failed": ("Not launchable here.", None),
    "execution_profile_unavailable": ("It can't run on this machine's profile.", None),
    "remote_door_not_hosted": (
        "Carbon hosts no remote agent door.",
        ("Use your own MCP client", "#connections"),
    ),
    "integration_interface_unverified": ("There's no way to connect it yet.", None),
    "flow_implemented_execution_is_the_miners_own": (
        "You sign registration in your own wallet.",
        ("Wallet & Identity", "#wallet"),
    ),
}


def plain(reason) -> dict:
    """One sentence and one link for a blocking reason; `known` is false for
    a reason this map does not name yet."""
    sentence, go = PLAIN.get(reason, ("Not available here yet.", None))
    return {
        "sentence": sentence,
        "next": {"label": go[0], "href": go[1]} if go else None,
        "known": reason in PLAIN,
    }


def _unavailable(reason, next_action, **extra):
    return {
        "availability": "unavailable",
        "reason": reason,
        "next_action": next_action,
        "plain": plain(reason),
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
        return None, {
            "configured": False,
            **NO_PROFILE,
            "plain": plain(NO_PROFILE["reason"]),
        }
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
            "plain": plain(code),
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

    none = {
        "gpu": False,
        "remote_gpu": False,
        "intake": False,
        "feedback_modes": [],
        "graphite": False,
    }
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
        # GPU practice on the miner's own remote machine or container
        # (OWNER-MINER-COMPUTE-LINK-ONLY-01): offered by the Challenge's own
        # campaign, never assumed.
        "remote_gpu": gpu and campaign.remote_worker is not None,
        "intake": campaign.intake_check is not None,
        "feedback_modes": list(campaign.feedback_modes),
        # Graphite runs on a Challenge with a registered research campaign
        # (OWNER-GRAPHITE-MINER-01; `runner.graphite_offered`).
        "graphite": True,
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
            item["plain"] = plain(refusal["code"])
        result.append(item)
    # The launch portfolio first; the historical DEVELOPMENT Challenge after it.
    order = {"launch": 0, "historical_development": 1, "deferred": 2}
    result.sort(key=lambda c: (order.get(c["portfolio"], 3), not c["implemented"]))
    return result


#: Choices this document shares with setup are named as setup names them
#: (`environment_setup.choices`), so one choice reads the same on every page
#: (LP-PROD-F). Held to setup's names by test. Graphite replaced the
#: autonomous agent for new launches (OWNER-GRAPHITE-MINER-01).
GRAPHITE_LABEL = "Graphite, Carbon's research agent"
OWN_AGENT_LABEL = "Your own agent, over MCP"
LOCAL_CPU_LABEL = "This machine (CPU)"
LOCAL_GPU_LABEL = "This machine (your GPU)"
REMOTE_LABEL = "Your own remote machine or container"
#: The MCP command when no runner profile is loaded here: the miner names it.
MCP_PLACEHOLDER = "carbon-mcp --configuration <your runner profile>"


def _mcp_connection(profile_path):
    """How the miner's own MCP client starts Carbon's server for this
    controller's runner profile: the real command, with the profile's path,
    when one is loaded (LP-PROD-F); the placeholder otherwise. Naming the path
    loads nothing: the server verifies the profile when it starts. The path
    is made absolute against the controller's working directory (the one it
    was given relative to), because the miner's MCP client starts the server
    from a directory of its own."""
    if profile_path is None:
        return {"command": MCP_PLACEHOLDER, "profile_path": None}
    from carbon.miner_mcp.agent_connection import connection_instructions

    try:
        profile_path = Path(os.path.abspath(profile_path))
        connection = connection_instructions(configuration=profile_path)
    except Exception:  # noqa: BLE001 - the placeholder still connects a client
        return {"command": MCP_PLACEHOLDER, "profile_path": None}
    return {
        "command": shlex.join(connection["command"]),
        "profile_path": str(profile_path),
        "client_configuration": connection["client_configuration"],
    }


def _agents(options, refusal, profile_path=None):
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

    graphite = (options or {}).get("graphite") or {}
    return {
        "choices": [
            {
                "id": "graphite",
                "label": GRAPHITE_LABEL,
                "summary": (
                    "Graphite hunts and reads literature, writes a ranked "
                    "plan, then constructs, practises, selects and submits, "
                    "on your model within your budget. Choose Research, Build "
                    "or Full."
                ),
                "launch_agent": "graphite",
                "uses_model": True,
                # The launch form's Graphite choices, from the shared
                # `options` operation (S4): modes, research share, hunt and
                # its planning estimate, limits.
                "modes": graphite.get("modes", []),
                "launch_fields": [
                    "graphite_mode",
                    "research_share",
                    "plan",
                    "hunt",
                    "limits",
                ],
                **state("graphite"),
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
                "label": OWN_AGENT_LABEL,
                "summary": (
                    "Launches with no Carbon agent; your own MCP client drives "
                    "practice, freeze and submit through the same operations, "
                    "over stdio, with nothing issued by Carbon."
                ),
                "launch_agent": "none",
                "uses_model": False,
                "door": "stdio",
                **_mcp_connection(profile_path),
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


def _setup_choice(cfg):
    """The provider and model the runner profile's setup chose
    (`model_selection`), or None. Only the two ids: its endpoint, price and
    key file stay in the profile."""
    chosen = (cfg or {}).get("model_selection")
    if type(chosen) is not dict:
        return None
    provider_id, model_id = chosen.get("provider_id"), chosen.get("model_id")
    if type(provider_id) is not str or type(model_id) is not str or not model_id:
        return None
    return {"provider_id": provider_id, "model_id": model_id}


def _with_setup_model(row, setup):
    """A provider row offering setup's model when setup chose this provider
    and the adapter does not list that model (LP-PROD-F): Chutes, Anthropic
    and the OpenAI-compatible adapters list none, so without it their Model
    step could never be passed. The launch then names setup's own choice,
    which the runner validates exactly as setup did."""
    if setup is None or setup["provider_id"] != row["id"]:
        return row
    if any(model["id"] == setup["model_id"] for model in row["models"]):
        return row
    model = {"id": setup["model_id"], "availability": "available", "from_setup": True}
    return {**row, "models": [*row["models"], model]}


def _output_cap(providers):
    """The launch's optional output cap (`model_settings.max_output_tokens`,
    LAUNCHPAD-PAGE-USABILITY-01): its bounds, and for each offered model the
    default a launch with no cap gets - the model's own maximum as
    `model_provider.output_maximum` records it, exactly what the runner's
    `select(output_default=OUTPUT_DEFAULT_V2)` chooses. The page shows and
    pre-checks these; the runner validates the launch and has the last word."""
    from carbon.development_session.model_provider import (
        DEFAULT_SETTINGS,
        OUTPUT_TOKEN_BOUNDS,
        ModelSelectionRefused,
        output_maximum,
    )

    defaults = {}
    for row in providers:
        for model in row["models"]:
            try:
                chosen = output_maximum(row["id"], model["id"])
            except ModelSelectionRefused:
                continue
            defaults.setdefault(row["id"], {})[model["id"]] = {
                "max_output_tokens": chosen["max_output_tokens"],
                "basis": chosen["basis"],
            }
    low, high = OUTPUT_TOKEN_BOUNDS
    return {
        "launch_field": "model_settings.max_output_tokens",
        "bounds": [low, high],
        "defaults": defaults,
        "basis": (
            "Optional. Blank: the model's own maximum output where Carbon "
            f"records one, otherwise {DEFAULT_SETTINGS.max_output_tokens:,} "
            "tokens. A number caps each reply; "
            "each call is reserved at the cap. Sent only with a provider and "
            "model, and validated by the runner at launch."
        ),
    }


def _model(options, refusal, cfg=None):
    """Model providers the miner can choose, each with its own credential.

    The miner chooses the provider and model and supplies the credential; Carbon
    holds none. The pinned default is reported first, from the agent's own
    transport rather than named as Carbon's model; the registered provider
    adapters follow, each available only when the runner profile configures
    its key file. A launch names one with `model_provider` and `model`. The
    model setup chose is `setup_choice`, listed under its provider, so the
    page can preselect it; a launch naming none runs with it.
    """
    provider, model = _implemented_transport()
    setup = _setup_choice(cfg)
    if options is None:
        credential = {"configured": None, "basis": "NOT_READ: " + refusal["reason"]}
        state = _unavailable(refusal["reason"], refusal["next_action"])
    else:
        agent = next((a for a in options["agents"] if a["value"] == "graphite"), None)
        ready = bool(agent and agent["availability"] == "available")
        credential = {"configured": ready, "basis": "read from your runner profile"}
        state = (
            {"availability": "available"}
            if ready
            else _unavailable(
                "model_provider_key_not_configured",
                "Point api_key_file in your runner profile at your own key file.",
            )
        )
    rows = [
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
    ]
    providers = [_with_setup_model(row, setup) for row in rows]
    return {
        "used_by": ["graphite"],
        "chosen_by": "miner",
        "providers": providers,
        "setup_choice": setup,
        "launch_field": ["model_provider", "model"],
        "output_cap": _output_cap(providers),
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
    runtime = (cfg or {}).get("runtime", {})
    if "remote_gpu" in runtime:
        # GPU practice on the miner's own remote machine or container. This
        # controller still runs its trusted worker locally, so this machine's
        # Docker is still needed.
        transport = cfg["remote_machine"]["transport"]
        choice = {
            "id": "remote-machine",
            "label": REMOTE_LABEL + " · " + transport,
            "lane": "remote-gpu",
            "transport": transport,
            "started_stopped_and_billed_by": "you; Carbon never does",
        }
    else:
        # Named as setup names it; the isolated Docker worker is how it runs.
        gpu = "gpu_research" in runtime
        choice = {
            "id": "local-isolated-worker",
            "label": LOCAL_GPU_LABEL if gpu else LOCAL_CPU_LABEL,
            "lane": "gpu" if gpu else "cpu",
            "isolation": "an isolated Docker worker on this machine",
        }
    return {
        "choices": [
            {
                **choice,
                "lanes": lanes,
                "host_facts": sorted(host.facts),
                **local,
            }
        ],
        "selection": "Set by your runner profile's runtime; the launch carries no compute field.",
        "routes": _routes(cfg, local),
        "destinations": research_compute_choices(),
        "unavailable": _integrations("compute_provider"),
    }


def _routes(cfg, local):
    """Where research can run, side by side (LINKONLY-D10): this machine, and
    a GPU the miner runs elsewhere, each with its state from the profile and
    the one place that sets it up."""
    runtime = (cfg or {}).get("runtime", {})
    remote = (cfg or {}).get("remote_machine") if "remote_gpu" in runtime else None
    # The two routes are the Compute page's side-by-side headings (LINKONLY-
    # D10), not setup's choices: their own plain names stay.
    here = {
        "id": "this-machine",
        "label": "This machine",
        "lane": "gpu" if "gpu_research" in runtime and remote is None else "cpu",
        "in_use": remote is None and cfg is not None,
        **local,
    }
    if remote is None:
        there = {
            "availability": "not_set_up",
            "in_use": False,
            "plain": {
                "sentence": "Not set up.",
                "next": {"label": "Set it up", "href": "#setup/compute"},
                "known": True,
            },
        }
    else:
        there = {
            "availability": "configured",
            "in_use": True,
            "transport": remote["transport"],
            "plain": {
                "sentence": "In your profile, over your own SSH.",
                "next": {"label": "Change it", "href": "#setup/compute"},
                "known": True,
            },
        }
    return [
        here,
        {
            "id": "remote-machine",
            "label": "A GPU you run elsewhere",
            "started_stopped_and_billed_by": "you; Carbon never does",
            **there,
        },
    ]


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
            # Only max_output_tokens, only with model_provider and model.
            "model_settings",
            # Graphite's own, with agent=graphite only (S4).
            "graphite_mode",
            "research_share",
            "plan",
            "hunt",
            "limits",
        ],
        "challenge_default": None,
    }


def _graphite(options, refusal):
    """Graphite's launch choices and library for the page (S4): the shared
    `options` operation's `graphite` block, and the operations its Library
    tab calls - each the shared operation of that name, at either door."""
    from scripts.dev.miner_launchpad.operations import LIBRARY_READS, LIBRARY_WRITES

    value = (options or {}).get("graphite")
    return {
        **(
            value
            if value is not None
            else _unavailable(refusal["reason"], refusal["next_action"])
        ),
        "library": {
            "reads": list(LIBRARY_READS),
            "writes": list(LIBRARY_WRITES),
            "http": {
                "library": "/api/v1/library/<search|card|list|pin|unpin|ban|unban|import>",
                "plans": "/api/v1/plans/<list|get|edit>",
            },
            "check_status": "UNCHECKED",
            "origins": ["shared", "miner_hunt", "miner_import"],
        },
    }


def control_center(runner=None):
    """The whole capability document for one controller."""
    cfg, profile_state = _profile(runner)
    options, options_refusal = _options(runner)
    refusal = options_refusal or NO_PROFILE
    host = _host_facts(cfg)
    # The loaded profile's own path, for the MCP command: only once it loads.
    profile_path = getattr(runner, "configuration", None) if cfg is not None else None
    return {
        "schema": SCHEMA,
        "mode": "DEVELOPMENT",
        "authority": "Discovery grants no authority; nothing here is qualified, paid or on chain.",
        "profile": profile_state,
        "challenges": _challenges(profile_state, host),
        "agents": _agents(options, refusal, profile_path),
        "graphite": _graphite(options, refusal),
        "model": _model(options, refusal, cfg),
        "compute": _compute(cfg, options, refusal, host),
        "budget": _budget(),
        "launch": _launch(),
        "connections": _integrations("connection"),
        "wallet": _integrations("wallet"),
    }
