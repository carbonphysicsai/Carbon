"""Acceptance covering design; descriptions are requirements, never results.

Source: LAUNCHPAD_ACCEPTANCE_PLAN sections 3.2-3.8 and owner D1/D5/D6.
No function in this module dispatches the described real-world activity.
"""

from __future__ import annotations

from dataclasses import dataclass

D5 = "LEVELS_AFTER_FIRST_REAL_F12_AND_FOLLOWING_WEEK"
D1 = "LA_F17_REQUIRES_SEPARATE_SECURITY_ACCEPTANCE"


@dataclass(frozen=True)
class CellDefinition:
    cell: str
    family: str
    option: str
    pass_means: str
    required_evidence_fields: tuple[str, ...]
    base_required: bool = False
    blocked_reason: str | None = None
    refusal_codes: tuple[str, ...] = ()


def _entry(
    cell, family, option, predicate, fields, *, base=False, blocked=None, refusals=()
):
    return CellDefinition(
        cell,
        family,
        option,
        predicate,
        tuple(fields.split()),
        base,
        blocked,
        tuple(refusals),
    )


FLOWS = (
    _entry(
        "F01",
        "flow",
        "install",
        "Clean CPU and GPU install exits 0; worker/analysis/GPU image identities recorded; after-install accepts them and Control Center starts.",
        "installer_exit_code image_digests after_install_code controller_started",
        base=True,
    ),
    _entry(
        "F02",
        "flow",
        "update",
        "Update advances old checkout to main, rebuilds images, marks old profile stale and rechecks setup; running update is refused.",
        "before_revision after_revision image_digests stale_profile_present refusal_code",
        base=True,
    ),
    _entry(
        "F03",
        "flow",
        "signer-registration",
        "Reachable signer and registration on subnet 567 at a recorded block; unregistered identity receives unsigned human_action_required.",
        "signer_code registration_code block unregistered_refusal_code",
        base=True,
    ),
    _entry(
        "F04",
        "flow",
        "inference",
        "Real provider model list and completion settle within quoted consent; bare consent true is refused; key material is absent from evidence.",
        "quote_digest check_code settlement_code refusal_code",
        base=True,
    ),
    _entry(
        "F05",
        "flow",
        "compute-review",
        "CPU compute verifies images at the selected revision; review writes a profile loaded without restart.",
        "image_digests profile_digest profile_loaded",
        base=True,
    ),
    _entry(
        "F06",
        "flow",
        "environment-estimate",
        "Both doors match registered provisions/named gaps and the driver's reservation at the same model.",
        "browser_digest mcp_digest driver_reservation_digest estimate_digest",
        base=True,
    ),
    _entry(
        "F07",
        "flow",
        "graphite-build",
        "One-epoch Graphite BUILD completes or pauses with all three first-turn calls journalled and settled within the cap; supervisor completion alone is insufficient.",
        "campaign_id final_state first_turn_calls journal_digest settlement_code",
        base=True,
    ),
    _entry(
        "F08",
        "flow",
        "practice",
        "A TRAIN practice returns feedback with backend CPU.",
        "feedback_digest backend",
        base=True,
    ),
    _entry(
        "F09",
        "flow",
        "freeze",
        "Manifest frozen with strategy/contract digests; freeze without practice is refused.",
        "strategy_digest contract_digest refusal_code",
        base=True,
    ),
    _entry(
        "F10",
        "flow",
        "commitment",
        "Plan matches commitment digest; owner confirms on signer TTY; chain readback at finality matches that digest.",
        "commitment_digest extrinsic_digest block tty_confirmed finalized",
        base=True,
    ),
    _entry(
        "F11",
        "flow",
        "submit",
        "Intake returns 202/submission id and matches the profile's pinned receiver without publishing its identifier.",
        "submission_id response_code receiver_pair_matches",
        base=True,
    ),
    _entry(
        "F12",
        "flow",
        "verdict",
        "Both doors report sealed DEVELOPMENT CPU outcome without hidden score, cases or seeds.",
        "browser_digest mcp_digest sealed outcome_code backend",
        base=True,
    ),
    _entry(
        "F13",
        "flow",
        "refusals",
        "Real-chain/validator negative paths return each required closed refusal and next step on both doors.",
        "refusal_codes next_steps_present browser_digest mcp_digest",
        base=True,
        refusals=(
            "commitment_required",
            "ALREADY_COMMITTED_THIS_TEMPO",
            "intake_receiver_mismatch",
            "hotkey_window_used",
            "practice_result_required",
            "registration_required",
            "key_must_be_a_file_on_this_door",
        ),
    ),
    _entry(
        "F14",
        "flow",
        "pause-resume-restart",
        "Closing Control Center pauses the campaign; restart resumes its journal without blindly resending a paid call.",
        "transition_codes journal_digest paid_call_repeated",
        base=True,
    ),
    _entry(
        "F15",
        "flow",
        "multi-intake",
        "Two real receiver-paired targets: one admits and one refuses; both journals retained and verdicts never averaged (owner D6).",
        "target_count receiver_pairs_match admitted_journal_digest refused_journal_digest admit_code refusal_code verdicts_averaged",
        base=True,
    ),
)

_REMOTE = "Check, send worker when ssh-docker, two REMOTE_GPU practices, cleanup and unreachable-host/missing-worker refusals; no live remote address in evidence."
_REMOTE_FIELDS = "transport verification_code practice_count backend cleanup_confirmed unreachable_refusal_code missing_worker_refusal_code"
COMPUTE = (
    _entry(
        "C1",
        "compute",
        "this-machine-cpu",
        "F05 and F08 pass on fresh distro with CPU backend.",
        "backend compute_code feedback_digest",
        base=True,
    ),
    _entry(
        "C2",
        "compute",
        "this-machine-gpu",
        "Host device record installed or prepare named; two ISOLATED_CARRIER_GPU practices record device/JAX observations and the same frozen recipe receives validator verdict.",
        "device_digest practice_digests backend framework_code verdict_digest",
        base=True,
    ),
    _entry(
        "C3", "compute", "own-server/ssh-docker", _REMOTE, _REMOTE_FIELDS, base=True
    ),
    _entry(
        "C4",
        "compute",
        "runpod/ssh-container",
        _REMOTE + " Record pod kind and verified build identity.",
        _REMOTE_FIELDS + " machine_code build_digest",
        base=True,
    ),
    _entry(
        "C5",
        "compute",
        "vast/ssh-docker",
        _REMOTE + " Verify NVIDIA toolkit availability on the VM.",
        _REMOTE_FIELDS + " toolkit_code",
        base=True,
    ),
    _entry("C6", "compute", "vast/ssh-container", _REMOTE, _REMOTE_FIELDS),
    _entry("C7", "compute", "lambda/ssh-docker", _REMOTE, _REMOTE_FIELDS),
    _entry(
        "C8",
        "compute",
        "lium/ssh-container",
        _REMOTE + " Settle the ssh-L restriction note.",
        _REMOTE_FIELDS + " tunnel_code",
    ),
    _entry(
        "C9",
        "compute",
        "targon/ssh-docker",
        _REMOTE + " Verify Docker and NVIDIA toolkit availability.",
        _REMOTE_FIELDS + " toolkit_code",
    ),
    _entry(
        "C10",
        "compute",
        "this-machine-gpu/pytorch",
        "Torch GPU practice follows the requested device and records the actual Torch/backend observation independently of JAX evidence.",
        "device_digest backend framework_code feedback_digest",
    ),
    _entry(
        "C11",
        "compute",
        "device-request-driver",
        "The real device request names Driver nvidia and gpu capability; retain requested/observed public device codes and cleanup evidence, with selected identity recorded only by digest. Typed failures are nonpassing; no containment or scientific qualification is inferred.",
        "requested_device_code observed_device_code driver_code cleanup_confirmed",
    ),
)

INFERENCE = tuple(
    _entry(
        "I" + str(index),
        "inference",
        provider,
        "Quote, live model list and one completion; settlement within quote; wrong consent refused; no key disclosure."
        + (
            " Also one bounded one-epoch Graphite BUILD campaign."
            if index in (1, 2)
            else " Missing owner key is BLOCKED, never PASS."
        ),
        "quote_digest models_digest completion_digest settlement_code refusal_code"
        + (" campaign_id journal_digest" if index in (1, 2) else ""),
        base=index in (1, 2),
    )
    for index, provider in enumerate(
        (
            "engy-chat",
            "chutes",
            "engy-anthropic",
            "openai-responses",
            "anthropic",
            "openai-compatible-chat",
            "openai-compatible-responses",
        ),
        1,
    )
)

AGENTS = (
    _entry(
        "A1",
        "agent",
        "carbon-graphite",
        "BUILD campaign practices, freezes, requests commitment (owner TTY), submits and observes a verdict in one journal.",
        "campaign_id journal_digest verdict_digest",
        base=True,
    ),
    _entry(
        "A2",
        "agent",
        "hermes",
        "Installer/profile consent and per-tool confirmations; actual Hermes campaign practices/freezes/commits/submits and observes verdict; listed files match setup.",
        "client_version_code files_digest campaign_id verdict_digest",
        base=True,
    ),
    _entry(
        "A3",
        "agent",
        "claude-code",
        "Unedited MCP snippet works; tools listed; long practice completes within client timeout; complete loop yields verdict and no UNVERIFIED marker.",
        "client_version_code tool_count long_call_code snippet_digest verdict_digest",
        base=True,
    ),
    _entry(
        "A4",
        "agent",
        "codex",
        "Unedited MCP snippet/config block with tool_timeout_sec 1800 works; same complete loop and long-call/verdict checks as A3.",
        "client_version_code tool_count long_call_code snippet_digest verdict_digest",
        base=True,
    ),
    _entry(
        "A5",
        "agent",
        "hermes-snippet",
        "Standalone mcp_servers config works; hermes mcp add capability is settled and snippet updated or marked unsupported.",
        "client_version_code snippet_digest connect_code",
    ),
)

_LEVEL_REFUSALS = (
    "level_not_registered",
    "level_not_served_by_target",
    "ladder_hotkey_not_listed",
    "ladder_variant_not_accepted",
    "ladder_level_not_accepted",
)
LEVELS = tuple(
    _entry(
        "L" + str(level),
        "level",
        variant,
        "Real Launchpad freeze/owner-TTY commit/ladder submit/verdict on both doors; preserve variant and commitment identities, explicit main-target refusal, and no practice-as-level evidence."
        + (
            " L4 additionally preserves envelope bytes and typed transport-not-open refusals until authorized."
            if level == 4
            else ""
        ),
        "variant_digest commitment_digest block submission_id verdict_digest refusal_codes browser_digest mcp_digest"
        + (" envelope_digest" if level == 4 else ""),
        blocked=D5,
        refusals=_LEVEL_REFUSALS,
    )
    for level, variant in enumerate(
        (
            "battery-l1-loss-expressions-v1",
            "battery-l2-v2",
            "battery-l3-numerics-v1",
            "level4-graph",
        ),
        1,
    )
)
SECURITY = (
    _entry(
        "LA-F17",
        "security",
        "bootstrap-publisher-signing",
        "Separate Carbon Validator review and owner security acceptance; not a base launch blocker (D1).",
        "review_digest acceptance_reference",
        blocked=D1,
    ),
)
MATRIX = FLOWS + COMPUTE + INFERENCE + AGENTS + LEVELS + SECURITY
BY_CELL = {item.cell: item for item in MATRIX}
