"""Setup's one table, driving both doors (OWNER-MINER-SETUP-AGENT-FIRST-01).

The owner, 2026-10-02: "yes make this more agent first and easy for an agent
to automate". The browser's `/api/v1/setup/<step>` routes and the MCP
`carbon_setup_<step>` tools are both generated from `SETUP_OPERATIONS` and
both call `perform`, over the same `EnvironmentSetup` and the same setup
records, so the two doors apply the same gates in the same order and cannot
drift (the same pattern as `operations.py` for the miner operations).

`status` drives the whole loop: the steps done, the next step, what it is
missing as closed codes, and the exact next call with its arguments schema.
An agent loops status -> next call -> status until launch, parsing no prose.

Two steps stay the miner's by design: starting their signer, and signing
their registration. When a call reaches one, it answers a closed
`human_action_required` result naming the exact instruction or command;
status shows when it is done. No field anywhere accepts, and no result
returns, a private key, seed, mnemonic or password: the only hotkey value is
the public ss58 address, and a model key reaches the MCP door only as the path
to an owner-only file the miner made.

The doors differ in one declared way: the browser may paste a model key once
(`key`); the MCP door takes `model_key_file` only, and refuses a key value.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA = "carbon.miner-setup.status.v1"
#: The setup steps, in the order a miner takes them.
ORDER = ("signer", "register", "agent", "inference", "compute", "review")
TITLES = {
    "signer": "Start your signer",
    "register": "Register on the subnet",
    "agent": "Who researches?",
    "inference": "Inference",
    "compute": "Compute",
    "review": "Review and launch",
}
#: Where a step's tools appear: the open tier (anyone, before registration),
#: or once registration is confirmed (C-MLP-02-D10: absent, not refusing).
OPEN, REGISTERED = "open", "registered"
#: The doors.
HTTP, MCP = "http", "mcp"


@dataclass(frozen=True)
class SetupOperation:
    name: str
    step: str
    tier: str
    summary: str
    required: frozenset
    optional: frozenset = frozenset()
    #: Fields only the browser door accepts.
    browser_only: frozenset = frozenset()


def _op(name, step, tier, summary, required=(), optional=(), browser_only=()):
    return SetupOperation(
        name,
        step,
        tier,
        summary,
        frozenset(required),
        frozenset(optional),
        frozenset(browser_only),
    )


#: Every setup call, both doors. Its gates live in `EnvironmentSetup`.
SETUP_OPERATIONS = {
    op.name: op
    for op in (
        _op(
            "signer",
            "signer",
            OPEN,
            "Ask your running carbon-miner-signer which hotkey it holds, for "
            "your public hotkey address. Nothing is signed.",
            {"address"},
            {"signer_socket"},
        ),
        _op(
            "begin",
            "register",
            OPEN,
            "Confirm your hotkey is registered on the subnet, from the chain.",
            {"address"},
        ),
        _op(
            "agent",
            "agent",
            REGISTERED,
            "Choose who researches: carbon-graphite (Graphite, Carbon's "
            "research agent, on your model), own-agent (your own MCP client, "
            "with its own model) or hermes (its ready-made profile). Checks "
            "your signer and reads the network.",
            {"choice"},
            {"operator_config", "signer_socket", "consent"},
        ),
        _op(
            "quote",
            "inference",
            REGISTERED,
            "The inference check's maximum cost for this provider and model. "
            "Free; reads no key.",
            {"provider_id", "model_id"},
            {"endpoint", "declared_pricing"},
        ),
        _op(
            "inference",
            "inference",
            REGISTERED,
            "Check the model with your key file, billed to you, on consent to "
            "the quoted maximum.",
            {"provider_id", "model_id", "consent"},
            {"model_key_file", "endpoint", "declared_pricing"},
            {"key"},
        ),
        _op(
            "compute",
            "compute",
            REGISTERED,
            "Check where practice runs: this machine, or your own remote "
            "machine or container over your own SSH. Starts nothing.",
            {"choice", "image_manifest", "analysis_image_manifest"},
            {"gpu_image_manifest", "challenge", "remote"},
        ),
        _op(
            "send_worker",
            "compute",
            REGISTERED,
            "Send the pinned GPU worker to your own machine with Docker, on "
            "consent naming the destination and image. Can take minutes.",
            {"consent"},
        ),
        _op(
            "review",
            "review",
            REGISTERED,
            "Write your runner profile and load it. Nothing is launched or spent.",
            {"confirm"},
            {"intakes", "receiver_hotkey", "receivers"},
        ),
    )
}

#: Each field's JSON type and meaning, for both doors' schemas.
FIELDS = {
    "address": ("string", "Your public hotkey ss58 address; never a key or phrase."),
    "signer_socket": ("string", "Absolute path to your signer's socket (optional)."),
    "choice": ("string", "One of the choices status lists for this step."),
    "operator_config": ("string", "Operators only; miners leave it out."),
    "consent": ("object", "Exactly the consent object status describes."),
    "provider_id": ("string", "An inference provider id status lists."),
    "model_id": ("string", "The model id."),
    "endpoint": ("string", "A generic adapter's https completion route."),
    "declared_pricing": ("object", "Your declared price (optional)."),
    "model_key_file": (
        "string",
        "Absolute path to an owner-only file holding your model key.",
    ),
    "key": ("string", "Browser only: the key, pasted once."),
    "image_manifest": ("string", "Absolute path; status gives the one it found."),
    "analysis_image_manifest": ("string", "Absolute path; status gives it."),
    "gpu_image_manifest": (
        "string",
        (
            "Absolute path; status gives it. Only with a GPU choice (this "
            "machine's GPU, or your remote machine): required there, refused "
            "with the CPU choice (gpu_image_is_for_the_gpu_choice)."
        ),
    ),
    "challenge": (
        "object",
        (
            "{id, version} of a Challenge status lists under options.challenge "
            "- the one your GPU practice is set up for. Only with a GPU choice "
            "(this machine's GPU, or your remote machine): required there, "
            "refused with the CPU choice (challenge_is_for_the_gpu_choice)."
        ),
    ),
    "remote": (
        "object",
        (
            "{transport, destination, port?} of your own setup. Only with the "
            "remote choice: required there, refused otherwise."
        ),
    ),
    "confirm": ("boolean", "true"),
    "intakes": ("object", "Challenge id to validator intake URL (optional)."),
    "receiver_hotkey": (
        "string",
        (
            "The ss58 receiver hotkey of the one validator intake of your own "
            "you name in intakes; required with it. Nothing is signed for an "
            "intake that reports another."
        ),
    ),
    "receivers": (
        "object",
        (
            "Challenge id to receiver hotkey, one per intake of your own in "
            "intakes, when you name several (instead of receiver_hotkey)."
        ),
    ),
}

#: The next step for a refusal that names none of its own.
NEXT_STEPS = {
    "registration_not_confirmed": "confirm your registration: carbon_setup_begin",
    "step_not_checked": "take the step named in field first; carbon_setup_status",
    "unknown_field": "send only the fields in the step's arguments schema",
    "field_required": "send every required field in the step's arguments schema",
    "agent_not_offered": "choose carbon-graphite, own-agent or hermes",
    "autonomous_agent_replaced": (
        "choose carbon-graphite: Graphite replaced Carbon's autonomous agent "
        "for new setups (OWNER-GRAPHITE-MINER-01)"
    ),
    "hotkey_address_required": "send your public hotkey ss58 address",
    "key_must_be_a_file_on_this_door": (
        "put the key alone in an owner-only file and send model_key_file"
    ),
    "challenge_is_for_the_gpu_choice": (
        "leave challenge out with the CPU choice: it names the Challenge GPU "
        "practice is set up for"
    ),
    "gpu_image_is_for_the_gpu_choice": (
        "leave gpu_image_manifest out with the CPU choice"
    ),
}

#: Signer refusals: the miner starts or restarts their own signer.
SIGNER_CODES = frozenset(
    {
        "signer_not_running",
        "signer_timeout",
        "signer_refused",
        "signer_wrong_hotkey",
        "signer_protocol",
        "signer_invalid_signature",
    }
)


def schema(name: str, door: str) -> dict:
    """A step's arguments as JSON Schema, for one door."""
    op = SETUP_OPERATIONS[name]
    fields = op.required | op.optional | (op.browser_only if door == HTTP else set())
    return {
        "type": "object",
        "properties": {
            field: {"type": FIELDS[field][0], "description": FIELDS[field][1]}
            for field in sorted(fields)
        },
        "required": sorted(op.required),
        "additionalProperties": False,
    }


def call(name: str, door: str) -> dict:
    """The exact call for one setup operation on one door."""
    return {
        "operation": name,
        "tool": "carbon_setup_" + name,
        "http": "POST /api/v1/setup/" + name,
        "door": door,
        "arguments": schema(name, door),
    }


def human_action(step: str, code: str, address=None) -> dict:
    """A step only the miner can take, with exactly what to do."""
    from scripts.dev.miner_launchpad.environment_setup import signer_command

    if step == "signer":
        command = signer_command()
        return {
            "result": "human_action_required",
            "step": "signer",
            "code": code,
            "action": "start_signer",
            "instruction": (
                "Ask the miner to start carbon-miner-signer for this hotkey in "
                "their own terminal and leave it open. Carbon never holds the "
                "key; the agent must not ask for it."
            ),
            "for_miner": (
                "Start carbon-miner-signer for this hotkey in your own terminal "
                "and leave it open, then check again."
            ),
            "command": command,
            "then": call("signer", MCP),
        }
    return {
        "result": "human_action_required",
        "step": "register",
        "code": code,
        "action": "sign_registration",
        "instruction": (
            "Ask the miner to register this hotkey on the subnet in their own "
            "wallet: carbon_onboarding_prepare gives the unsigned call; they "
            "sign it, paid from their coldkey. Then confirm."
        ),
        "for_miner": (
            "Register this hotkey on the subnet in your own wallet: Wallet & "
            "Identity prepares the unsigned call, and the recycle amount comes "
            "from your coldkey. Then check again."
        ),
        "command": None,
        "address": address,
        "then": call("begin", MCP),
    }


def perform(setup, name: str, request, *, door: str):
    """One setup operation, the same on both doors.

    Returns the setup state, or a `human_action_required` result. Raises
    `SetupRefused` with a closed code, the field, and a next step.
    """
    from scripts.dev.miner_launchpad.environment_setup import SetupRefused

    op = SETUP_OPERATIONS[name]
    if type(request) is dict and door == MCP:
        given = set(request) & op.browser_only
        if given:
            raise SetupRefused(
                min(given),
                "key_must_be_a_file_on_this_door",
                next_step=NEXT_STEPS["key_must_be_a_file_on_this_door"],
            )
    try:
        return getattr(setup, name)(request)
    except SetupRefused as refused:
        if refused.code in SIGNER_CODES and name in ("signer", "agent"):
            return human_action("signer", refused.code)
        if name == "begin" and refused.code == "hotkey_not_registered":
            return human_action("register", refused.code, request.get("address"))
        if refused.next_step is None and refused.code in NEXT_STEPS:
            refused.next_step = NEXT_STEPS[refused.code]
        raise


def _reconnect_command(setup):
    """`carbon-mcp` with this setup's runner profile, and its state directory
    when that is not the Control Center's default, so the new session reads
    the same setup records as this one."""
    import shlex

    from scripts.dev.miner_launchpad.environment_setup import DEFAULT_STATE_DIR

    profile = getattr(setup, "profile_path", None)
    parts = [
        "carbon-mcp",
        "--configuration",
        str(profile) if profile is not None else "<your runner profile>",
    ]
    root = getattr(setup, "root", None)
    if root is not None and Path(root).parent != DEFAULT_STATE_DIR:
        parts += ["--state-dir", str(Path(root).parent)]
    return " ".join(
        part if part.startswith("<") else shlex.quote(part) for part in parts
    )


def _launch_call(setup, door, launch_available, *, profile_unusable=False):
    """The launch entry: where launch is, said only of tools that exist.

    `launch_available` is the MCP door's own answer - whether `carbon_launch`
    is in this session - or None where the door does not say. A session
    without it is told how to get it (LP-PROD-B), never sent to a tool it
    does not have. `profile_unusable` is the door's report that the runner
    profile review wrote failed to load here: a reconnect with that profile
    would fail the same way, so the step is review again, not a reconnect.
    """
    call = {"tool": "carbon_launch", "http": "POST /api/v1/research"}
    if door != MCP or launch_available is None:
        call["note"] = (
            "the registered tier's launch operation; its arguments schema lists "
            "every field"
        )
    elif launch_available:
        call["in_this_session"] = True
        call["note"] = (
            "carbon_launch is in this session; its arguments schema lists every "
            "field (challenge and challenge_version are required)"
        )
    elif profile_unusable:
        call["in_this_session"] = False
        call["missing"] = ["runner_profile_unusable"]
        call["fix"] = {"tool": "carbon_setup_review"}
        call["note"] = (
            "carbon_launch is not in this session: the runner profile review "
            "wrote could not be loaded here, so the launch operation was not "
            "added, and a reconnect with it would fail the same way. Call "
            "carbon_setup_review again; once the profile it writes loads, "
            "carbon_launch is added to this session"
        )
    else:
        call["in_this_session"] = False
        call["reconnect"] = _reconnect_command(setup)
        call["note"] = (
            "carbon_launch is not in this session: reconnect your MCP client "
            "with the reconnect command (your runner profile, which review "
            "wrote), then call carbon_launch"
        )
    return call


def status(
    setup, *, door: str, campaigns=None, launch_available=None, profile_unusable=False
) -> dict:
    """Where setup stands and the exact next call (OWNER-MINER-SETUP-AGENT-
    FIRST-01). `campaigns`, when the door knows it, is how many campaigns
    this miner's profile has; one or more means launch is done.
    `launch_available`, when the door knows it, is whether this session
    already has `carbon_launch`, and `profile_unusable` whether the written
    profile failed to load here (`_launch_call`)."""
    from scripts.dev.miner_launchpad.environment_setup import (
        OWN_AGENT,
        USES_SETUP_MODEL,
    )

    state = setup.state()
    steps = state["steps"]
    registered = state["registered_hotkey"]
    agent = steps["agent"]
    own = agent.get("checked") and agent.get("choice") not in USES_SETUP_MODEL
    pending_worker = bool(
        steps["compute"].get("checked") and steps["compute"]["check"].get("next_step")
    )
    # A compute check that no longer describes this install (LP-PROD-E):
    # why, and the one step that clears it, as setup states them.
    stale = steps["compute"].get("stale") or []
    if pending_worker:
        compute_missing = "worker_not_sent"
    elif stale:
        compute_missing = "compute_check_is_stale"
    else:
        compute_missing = "compute_not_checked"
    written = steps["review"]["profile_written"]
    done = {
        "signer": steps["signer"]["checked"] or agent.get("checked", False),
        "register": registered is not None,
        "agent": agent.get("checked", False),
        "inference": steps["inference"].get("checked", False),
        "compute": steps["compute"].get("checked", False) and not pending_worker,
        "review": written,
    }
    missing = {
        "signer": ["signer_not_checked"],
        "register": ["registration_not_confirmed"],
        "agent": ["agent_not_chosen"],
        "inference": ["inference_not_checked"],
        "compute": [compute_missing],
        "review": ["profile_not_written"],
    }
    rows = []
    for step in ORDER:
        row = {"id": step, "title": TITLES[step]}
        if step == "inference" and own:
            row.update(state="skipped", why="your agent uses its own model")
        elif done[step]:
            row["state"] = "done"
        elif step in ("signer", "register") or registered is not None:
            row.update(state="open", missing=missing[step])
        else:
            row.update(state="waiting", missing=missing[step], after="register")
        if step == "review" and row["state"] == "open":
            blockers = [
                s
                for s in ("agent", "inference", "compute")
                if not done[s] and not (s == "inference" and own)
            ]
            if blockers:
                row.update(state="waiting", after=blockers[0])
        rows.append(row)
    nxt = next((row for row in rows if row["state"] == "open"), None)
    if nxt is not None:
        nxt["state"] = "next"
    result = {
        "schema": SCHEMA,
        "door": door,
        "registered_hotkey": registered,
        "steps": rows,
        "done": [row["id"] for row in rows if row["state"] == "done"],
        "profile_written": written,
        # Where each Challenge's frozen candidates are evaluated: Carbon's
        # published endpoint, the miner's own intake, or none yet, with what
        # to do (LP-PROD-E). Setup's own `steps.evaluation`, as it is.
        "evaluation": steps.get("evaluation"),
        "next": None,
    }
    # Whether this install's Control Center comes back after a reboot
    # (MINER-SURVIVE-REBOOT-01): setup's own read-only warning, as Review's.
    reboot = getattr(setup, "reboot_warnings", None)
    result["warnings"] = reboot() if reboot is not None else []
    if nxt is None:
        launched = campaigns is not None and campaigns > 0
        result["next"] = {
            "step": "launch",
            "done": launched,
            "call": _launch_call(
                setup, door, launch_available, profile_unusable=profile_unusable
            ),
        }
        return result
    step = nxt["id"]
    entry = {"step": step, "title": TITLES[step], "missing": nxt["missing"]}
    if step == "signer":
        entry["human_action_required"] = human_action("signer", "signer_not_checked")
        entry["call"] = call("signer", door)
    elif step == "register":
        entry["human_action_required"] = human_action(
            "register", "registration_not_confirmed"
        )
        entry["call"] = call("begin", door)
    elif step == "compute" and pending_worker:
        machine = steps["compute"]["remote_machine"]
        entry["call"] = call("send_worker", door)
        entry["consent"] = {
            "send": {
                "destination": machine["destination"],
                **({"port": machine["port"]} if machine.get("port") else {}),
                "image": steps["compute"]["check"]["gpu_image"],
            }
        }
    else:
        entry["call"] = call(step, door)
        entry["options"] = _options(setup, step, state)
        if step == "inference":
            entry["before"] = call("quote", door)
            entry["consent"] = {"max_cost_nano": "the quote's max_cost_nano"}
        if step == "compute" and stale:
            # Checking again clears it, or only the installer does: setup's
            # own next step says which.
            entry["stale"] = stale
            entry["next_step"] = steps["compute"].get("next_step")
        elif step == "compute" and steps["compute"].get("set_aside"):
            entry["set_aside"] = steps["compute"]["set_aside"].get("reasons", [])
    result["next"] = entry
    result["skips"] = {OWN_AGENT: {"inference": "your agent uses its own model"}}
    return result


def _options(setup, step, state) -> dict:
    """The ids a step's call may name, from what setup offers now."""
    offered = setup.offered()
    if step == "agent":
        return {
            "choice": [
                {
                    "id": choice["id"],
                    "uses_setup_model": choice.get("uses_setup_model", False),
                    **(
                        {"consent": {"writes": choice["writes"]}}
                        if choice.get("needs_consent_to_write")
                        else {}
                    ),
                }
                for choice in offered["agent"]
            ]
        }
    if step == "inference":
        return {
            "provider_id": [
                {
                    "id": choice["id"],
                    "default_model": next(
                        (m["model_id"] for m in choice["models"] if m.get("default")),
                        None,
                    ),
                    "needs_endpoint": choice["needs_endpoint"],
                }
                for choice in offered["inference"]
            ]
        }
    if step == "compute":
        images = state["images"]
        remote = next(c for c in offered["compute"] if c.get("needs_remote"))
        return {
            "choice": [c["id"] for c in offered["compute"]],
            "image_manifest": images["image_manifest"]["path"],
            "analysis_image_manifest": images["analysis_image_manifest"]["path"],
            "gpu_image_manifest": images["gpu_image_manifest"]["path"],
            "build": {field: images[field]["build"] for field in images},
            "challenge": [
                {"id": c["id"], "version": c["version"]}
                for c in remote.get("for_challenges", [])
            ],
            "transport": [t["id"] for t in remote["transports"] if t["available"]],
            "setups": [
                {"id": card["id"], "transport": card["transport"]}
                for card in remote["guides"]["cards"]
            ],
        }
    if step == "review":
        # The Challenge ids `intakes` may name, and each intake of the miner's
        # own that an update set aside: sent again as `intakes`, Review keeps
        # it (it writes only the intakes it is given; LP-PROD-E).
        challenges = (state["steps"].get("evaluation") or {}).get("challenges") or []
        kept = {
            item["id"]: item["set_aside_intake"]
            for item in challenges
            if item.get("set_aside_intake")
        }
        # Their receivers, pinned at the Review that wrote them: sent again
        # as `receivers` (LAUNCHPAD-ACCEPT-03).
        receivers = {
            item["id"]: item["set_aside_receiver"]
            for item in challenges
            if item.get("set_aside_intake") and item.get("set_aside_receiver")
        }
        return {
            "intakes": [item["id"] for item in challenges],
            **({"name_again": kept} if kept else {}),
            **({"receivers_again": receivers} if receivers else {}),
        }
    return {}
