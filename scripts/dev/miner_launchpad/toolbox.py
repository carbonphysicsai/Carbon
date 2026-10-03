"""The toolbox: everything a miner and their agent can use, read from data.

OWNER-MINER-RESEARCH-SURFACE-01 (RSURF-D11). One document answers "where are
the JAX, PyTorch and Julia tools, and what does my agent call?". It is built
from the records that already say so, never from a list kept here:
- the Challenge's registered description: its backends, workflow, limits,
  rebuildable families and the backend control;
- the capability registry: Julia's status and blocker, the backend
  capability;
- the published validator exam environment: what the validator rebuilds
  with, and its pinned versions;
- the research protocol's workspace actions and operations, and the shared
  operations table, for the exact MCP tool names;
- this host's research lanes (whether `run_julia` can run here).

The only text kept here is one line per workspace action, and a test holds
that it covers exactly the protocol's actions. The page's Tools tab, each
Challenge card and an MCP client's `carbon_toolbox` read the same document.
"""

from __future__ import annotations

import functools
import json
import time

SCHEMA = "carbon.control-center.toolbox.v1"
#: One line per workspace action. The set of actions is the research
#: protocol's (DEVELOPMENT_WORKSPACE_ACTIONS, plus run_julia where a host has
#: authored Julia); tests/cpu/test_research_toolbox.py holds the two equal.
WORKSPACE_LINES = {
    "public_material": (
        "Fetch one public document by name: the objective, capabilities, TRAIN "
        "data, PRACTICE data or the reference method."
    ),
    "inventory": "List your workspace files and their digests.",
    "read_file": "Read a byte range (up to 4096 bytes) of one of your workspace files.",
    "write_file": "Write a file into your workspace, guarded by its expected digest.",
    "notebook": "Save a hypothesis, decision or note to the campaign journal.",
    "capability_request": (
        "Ask for something Carbon does not offer yet. It grants nothing; it "
        "counts as demand on the roadmap."
    ),
    "check_design": (
        "Ask whether a design can be submitted: a verdict per choice and the "
        "canonical design Carbon would rebuild. Charges nothing."
    ),
    "roadmap": "Every capability, what blocks it and how many miners asked.",
    "run_python": (
        "Run your own Python in the isolated analysis image, on your own and "
        "public files. Research only."
    ),
    "run_julia": (
        "Run your own Julia in the pinned Julia environments, in the isolated "
        "analysis image. Research only: never part of a submission."
    ),
}
#: The research workflow, step by step, and the tools that take each step.
#: The words come from the Challenge's own description where it has them.
WORKFLOW_STEPS = (
    ("validate", "Validate and compile", ("dry_validate", "compile_strategy"), ()),
    ("estimate", "Estimate", ("inspect_resources", "forecast_resources"), ()),
    ("practice", "Practice", ("start_research_task",), ("practice",)),
    ("progress", "Progress", ("get_research_result", "cancel_research_task"), ()),
    ("freeze", "Freeze a candidate", (), ("freeze_candidate",)),
    ("submit", "Submit (DEVELOPMENT)", (), ("submit",)),
)
_LANES_TTL = 30.0
_lanes_cache = {}


@functools.lru_cache(maxsize=8)
def _sources(challenge_id, version):
    from carbon.challenge_registry import registry
    from carbon.development_session.exam_environment import exam_environment
    from carbon.reconstruction.capability_registry import public_registry

    return json.dumps(
        {
            "described": registry.describe(challenge_id, version),
            "capabilities": public_registry(challenge_id)["capabilities"],
            "exam": exam_environment(),
        }
    )


def _tools():
    from carbon import research
    from carbon.development_session.research_tasks import workspace_fields
    from carbon.development_session.research_tools import PREFIX as RESEARCH
    from carbon.miner_mcp.mcp_operations import PREFIX as OPERATIONS
    from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS

    return (
        RESEARCH,
        OPERATIONS,
        tuple(research.SUPPORTED_OPERATIONS),
        tuple(DEVELOPMENT_WORKSPACE_ACTIONS) + ("run_julia",),
        workspace_fields,
    )


def host_lanes(host):
    """This host's research lanes ({julia, gpu, remote_gpu}), from the shared
    options operation; {} when it cannot be read. Read at most every 30 s."""
    from scripts.dev.miner_launchpad.operations import perform

    key = id(host)
    hit = _lanes_cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < _LANES_TTL:
        return hit[1]
    try:
        lanes = perform(host, "options", {}).get("research_lanes") or {}
    except Exception:  # noqa: BLE001 - unknown is shown as unknown
        lanes = {}
    _lanes_cache[key] = (time.monotonic(), lanes)
    return lanes


def _availability(lane):
    if not lane:
        return {"available": None, "reason": "this host's lanes could not be read"}
    if lane.get("availability") == "configured":
        return {"available": True, "reason": None}
    return {"available": False, "reason": lane.get("reason")}


def for_request(host, request, lanes=None):
    """`toolbox`: one Challenge's toolbox on this host, by its registered id.
    `lanes` overrides the host's (the demo fixture's own)."""
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad.controller import Rejected

    challenge_id, version = request["challenge"], request.get("challenge_version")
    if type(challenge_id) is not str or (
        version is not None and type(version) is not str
    ):
        raise Rejected("challenge_required")
    ref = challenge_ref(challenge_id)
    if ref["version"] is None or version not in (None, ref["version"]):
        raise Rejected("challenge_unknown", 404)
    try:
        return build(ref, lanes=host_lanes(host) if lanes is None else lanes)
    except Exception:  # noqa: BLE001 - a Challenge with no description has no toolbox
        raise Rejected("challenge_has_no_toolbox", 404) from None


#: Where the validator rebuilds, said plainly beside any GPU (RSURF-D19).
VALIDATOR_STAYS = (
    "The validator rebuilds your frozen recipe on its own published exam "
    "environment ({backend} today), so a GPU speeds up your own research only."
)
SET_UP_GPU = "#setup/compute"


def _gpu_frameworks():
    """The frameworks the pinned GPU worker serves: its own profile names
    them (carbon_<framework>_cuda...)."""
    from carbon.reconstruction.accelerators import GPU_PROFILE

    return ("jax",) if "_jax_" in GPU_PROFILE.profile_id else ()


def campaign_compute(compute, remote_machine=None):
    """Where a campaign's practice and GPU code cell run, from its record:
    `compute` is its `local-isolated-cpu`, `local-isolated-gpu` or
    `remote-gpu:<transport>`; `remote_machine` is the runner profile's
    (transport, destination, port), shown to the miner only."""
    if type(compute) is not str:
        return None
    if compute.startswith("remote-gpu:"):
        transport = compute.removeprefix("remote-gpu:")[:32]
        machine = remote_machine if type(remote_machine) is dict else {}
        destination = machine.get("destination")
        where = transport + (
            ", " + str(destination)[:128] if type(destination) is str else ""
        )
        return {
            "kind": "remote_gpu",
            "label": "your remote GPU (" + where + ")",
            "transport": transport,
            "destination": destination if type(destination) is str else None,
        }
    if compute == "local-isolated-gpu":
        return {"kind": "local_gpu", "label": "your GPU (this machine)"}
    if compute == "local-isolated-cpu":
        return {"kind": "cpu", "label": "CPU (the isolated sandbox on this machine)"}
    return {"kind": "unknown", "label": compute[:64]}


def where(compute, lanes, exam_backend):
    """Where this campaign runs, and what each GPU lane on this host is
    (RSURF-D19). `compute` is `campaign_compute(...)` or None (no campaign:
    chosen at launch)."""
    gpu = None if compute is None else compute["kind"] in ("local_gpu", "remote_gpu")
    lane_states = {
        name: _availability(lanes.get(name)) for name in ("gpu", "remote_gpu")
    }
    return {
        "practice": compute
        or {
            "kind": "chosen_at_launch",
            "label": "chosen at launch from your compute setup",
        },
        "code_cell": {
            "cpu": "CPU (the isolated analysis sandbox), always available",
            "gpu": compute["label"] if gpu else None,
            "gpu_reason": None
            if gpu
            else (
                "This campaign was launched without a GPU: its compute is frozen at launch."
                if compute is not None
                else "Launch a campaign with a GPU to run code cells on it."
            ),
        },
        "lanes": lane_states,
        "set_up_gpu": None
        if any(state["available"] for state in lane_states.values())
        else SET_UP_GPU,
        "validator": VALIDATOR_STAYS.format(backend=exam_backend),
    }


def build(challenge, *, lanes=None, compute=None):
    """The toolbox for one Challenge on this host. `lanes` is
    `host_lanes(host)`, or None when no host is known. `compute` is
    `campaign_compute(...)` for a campaign's toolbox, or None."""
    if type(challenge) is not dict or type(challenge.get("id")) is not str:
        return None
    sources = json.loads(_sources(challenge["id"], challenge.get("version")))
    described, capabilities, exam = (
        sources["described"],
        sources["capabilities"],
        sources["exam"],
    )
    research_prefix, operation_prefix, operations, actions, fields = _tools()
    execution = described.get("execution") or {}
    backends = execution.get("backends") or {}
    host_versions = execution.get("host_versions") or {}
    workflow = described.get("workflow") or {}
    limits = described.get("limits") or {}
    models = described.get("models") or {}
    controls = models.get("controls") or {}
    backend_control = controls.get("backend") or {}
    lanes = lanes if lanes is not None else {}
    by_id = {c["id"]: c for c in capabilities}

    runtimes = []
    profiles = [
        {
            "backend": exam["backend_profile"]["backend"],
            "environment_id": exam["backend_profile"]["environment_id"],
            "environment_version": exam["backend_profile"]["environment_version"],
            "environment_digest": exam["backend_profile"]["environment_digest"],
            "pinned": exam.get("pinned_dependencies") or [],
            "worker_image": None,
        },
        *[
            {
                "backend": p.get("backend"),
                "environment_id": p.get("environment_id"),
                "environment_version": p.get("environment_version"),
                "environment_digest": p.get("environment_digest"),
                "pinned": p.get("pinned_dependencies") or [],
                "worker_image": p.get("worker_image"),
            }
            for p in exam.get("additional_backend_profiles") or []
            if challenge["id"] in (p.get("challenges") or [])
        ],
    ]
    served_on_gpu = _gpu_frameworks()
    on_gpu = compute is not None and compute["kind"] in ("local_gpu", "remote_gpu")
    for name, families in backends.items():
        # A validator profile names its backend as "<framework>-<device>".
        profile = next(
            (p for p in profiles if str(p["backend"]).split("-")[0] == name), None
        )
        if compute is None:
            runs_on = "where your campaign runs: CPU, or a GPU you set up"
        elif not on_gpu or name in served_on_gpu:
            runs_on = compute["label"]
        else:
            runs_on = (
                "not served on this campaign's GPU: the pinned GPU worker "
                "carries " + ", ".join(served_on_gpu or ("no framework",)) + " only"
            )
        runtimes.append(
            {
                "id": name,
                "role": "Used for practice and rebuilt by the validator",
                # Where this campaign's practice runs it (RSURF-D19).
                "runs_on": runs_on,
                "families": families,
                "default": backend_control.get("default") == name,
                "validator_environment": None
                if profile is None
                else {
                    k: profile[k]
                    for k in (
                        "backend",
                        "environment_id",
                        "environment_version",
                        "environment_digest",
                        "worker_image",
                    )
                },
                "pinned": [
                    {"name": d.get("name"), "version": d.get("version")}
                    for d in (profile or {}).get("pinned", [])
                ],
            }
        )

    julia = by_id.get("model_family.julia_backend")
    julia_lane = _availability(lanes.get("julia"))
    workspace = []
    for action in actions:
        required, optional = fields(action)
        if action == "run_julia":
            available = julia_lane
        else:
            available = {"available": True, "reason": None}
        workspace.append(
            {
                "id": action,
                "description": WORKSPACE_LINES.get(action),
                "arguments": sorted(required),
                "optional": sorted(optional),
                "available": available["available"],
                "reason": available["reason"],
                "limits": limits.get(action + "_seconds")
                if action in ("run_python", "run_julia")
                else (limits.get("workspace") if action == "write_file" else None),
                "research_only": action in ("run_python", "run_julia"),
                "mcp": {
                    "tool": research_prefix + "start_research_task",
                    "arguments": {"kind": "workspace", "action": action},
                    "needs": operation_prefix + "attach_campaign",
                },
            }
        )

    steps = []
    for key, label, research_ops, table_ops in WORKFLOW_STEPS:
        tools = [operation_prefix + op for op in table_ops] + [
            research_prefix + op for op in research_ops if op in operations
        ]
        steps.append(
            {
                "id": key,
                "label": label,
                "description": workflow.get(key),
                "mcp": tools,
                "note": (
                    "kind=practice on the attached research tools; carbon_practice "
                    "on the operations tools"
                    if key == "practice"
                    else None
                ),
            }
        )

    choosers = set(backend_control.get("families") or [])
    families = [
        {
            "id": m.get("id"),
            "selector": m.get("selector"),
            "summary": m.get("summary"),
            "backend": (
                "the recipe's backend control: "
                + ", ".join(backend_control.get("minimum_or_choices") or [])
                + " (default "
                + str(backend_control.get("default"))
                + ")"
                if m.get("selector") in choosers
                else "the default backend ("
                + str(backend_control.get("default") or "jax")
                + ")"
            ),
        }
        for m in models.get("rebuildable") or []
    ]

    qualification = exam.get("qualification") or {}
    return json.loads(
        json.dumps(
            {
                "schema": SCHEMA,
                "challenge": {
                    "id": challenge["id"],
                    "version": challenge.get("version"),
                    "title": described.get("title"),
                },
                "runtimes": runtimes,
                "execution": execution.get("backend"),
                "controller_versions": {
                    "versions": host_versions,
                    "basis": (
                        "This controller's own Python packages, for reference. "
                        "Practice and the validator run in the pinned worker images."
                    ),
                },
                "julia": {
                    "role": "Research only: never in a submission",
                    "authority": "OWNER-PYTORCH-BACKEND-01",
                    "capability": None
                    if julia is None
                    else {
                        k: julia.get(k)
                        for k in ("id", "status", "blocker", "summary", "trigger")
                    },
                    "run_julia": julia_lane,
                    "exclusion": (described.get("exclusion_scope") or {}).get(
                        "submission"
                    ),
                },
                "workspace": workspace,
                "workflow": steps,
                "families": families,
                "validator": {
                    "plain": (
                        "A validator rebuilds your frozen recipe from scratch, with "
                        "Carbon's own trainer and seed, in the pinned "
                        + str(exam["backend_profile"]["backend"])
                        + " environment (or the PyTorch one when the recipe names "
                        "it). Declared, not qualified. Your own research hardware "
                        "does not have to match it."
                    ),
                    "details": {
                        "backend_profile": exam.get("backend_profile"),
                        "qualification": {
                            k: qualification.get(k)
                            for k in (
                                "declared",
                                "qualified",
                                "backend_support",
                                "basis",
                            )
                        },
                        "pinned_dependencies": exam.get("pinned_dependencies"),
                        "precision": exam.get("precision"),
                        "resource_envelope": exam.get("resource_envelope"),
                        "submission": exam.get("submission"),
                    },
                },
                "limits": limits,
                # The Challenge's registered example recipes, for the page's
                # recipe editor (RSURF-D15).
                "examples": [
                    e["strategy"]
                    for e in described.get("examples") or []
                    if type(e) is dict and type(e.get("strategy")) is dict
                ][:4],
                "lanes": {
                    name: _availability(lanes.get(name))
                    for name in ("julia", "gpu", "remote_gpu")
                },
                # Where this campaign runs, every GPU lane and why one is not
                # set up, and where the validator stays (RSURF-D19).
                "where": where(compute, lanes, str(exam["backend_profile"]["backend"])),
                "agent": {
                    "operations": (
                        "carbon-mcp --configuration <your runner profile>: the "
                        "operations tools, including "
                        + operation_prefix
                        + "campaign_view, "
                        + operation_prefix
                        + "toolbox, "
                        + operation_prefix
                        + "messages and "
                        + operation_prefix
                        + "note"
                    ),
                    "attach": operation_prefix + "attach_campaign",
                    "research_tools": [research_prefix + op for op in operations],
                },
                "basis": (
                    "Read from the Challenge's description, the capability "
                    "registry, the published exam environment and this host's "
                    "lanes. Discovery grants no authority."
                ),
            },
            allow_nan=False,
        )
    )
