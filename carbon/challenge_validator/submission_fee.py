"""Per-version TAO->Alpha buyback-and-burn submission fee gate & shared host credit ledger.

Constitutional & operational invariants (`OWNER-SUBMISSION-FEE-01`):
- **Host-state only (clean git tree):** Both the live ``submission_fee_policy.json``
  and the shared ``submission_fees_<netuid>.sqlite3`` ledger live strictly in a
  fixed host-wide state directory outside the git checkout (`/var/lib/carbon/submission-fee-netuid-<N>`
  or explicit `submission_fee_state_dir` / `CARBON_SUBMISSION_FEE_STATE_DIR`;
  `is_inside_repo` is refused). Absent policy file before first arming = dark
  (`None`, zero DB or RPC activity); once armed, a missing or unreadable (`EACCES`)
  policy file fails closed (`503 fee_policy_unavailable`) across restarts until
  explicitly disabled.
- **Per-version Mainnet scope & SHA-256-pinned Terms v1 gate:** Mainnet `116` forbids
  wildcard `"116:*"` enablement (requiring explicit `"116:<challenge_id> <version>"`
  rows) and fails closed (`503 fee_policy_unavailable`) unless
  `carbon-submission-terms-v1` is served and verified at its pinned SHA-256
  (`321100f9b4342f36a13bd9cf5c0bfbefbca99a44543e4e8da99c4760315ff1a5`).
- **Receiver-bound v2 remark, one host per receiver hotkey, & shared host ledger:**
  Remarks bind `carbon.fee.v2|<netuid>|<challenge_id>|<receiver>|<hotkey>`
  (Challenge-version-free so unspent burns carry across version flips on the same
  validator while remaining unreplayable across validator boxes), and one shared
  SQLite ledger per `(host, netuid)` prevents cross-version double-spends while
  carrying `VERSION_CLOSED` credits onto successor doors.
- **Never spent on turn-aways, three-state crash-safe on admission:** A burn or credit
  is reserved with `(door_id, expected_submission_id)` right before `Validator.evaluate`
  (or short-circuited idempotently if `expected_submission_id` is already settled, `M2`)
  and committed `SPENT` only when admitted (`OUTCOME`); startup recovery holds a
  per-door process lease (`C5`) and resolves each door's own `RESERVED` rows via a
  three-state check against `AttemptLedger` (`OUTCOME` rows only; unknown/unreadable
  leaves `RESERVED` fail-closed, `C4`).
- **Proven Carbon-side `RETRY_CREDIT`s only (`AGENTS.md` §6.7, `A3`):** Following any
  door-initiated `requeued_as` chain to its leaf after automatic retries settle with
  no pending or owed-list rerun (`C1`, `C7`), only proven `CARBON_CLASSES` build
  failures (excluding `carbon_unclassified`, `C6`), repo-verified Carbon grade
  infrastructure failures (`C2`, `C3`), and `VERSION_CLOSED` mint one non-cash
  `RETRY_CREDIT`. Candidate verdicts, `DUPLICATE`, and `WITHDRAWN_BY_MINER` consume.
- **Architecture boundary (`carbon/fees` separate, `AGENTS.md` §6.11):** Wave-A
  `carbon/fees` is a fixture-only `Strategy` package importing `carbon.scoring`;
  this module never touches `carbon.scoring` or `carbon.rewards` (enforced by
  `tests/invariants/test_submission_fee_unreachable.py`).
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import decimal
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import stat
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from carbon.chain.fee_burns import (
    DEFAULT_MAX_LOOKBACK_BLOCKS,
    REMARK_VERSION,
    FeeBurnNotFinalized,
    FeeBurnUnavailable,
    ObservedFeeBurn,
    exclusive_file_lock,
    fee_remark,
    fee_remark_hash,
    parse_extrinsic_id,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_HOST_STATE_ROOT = Path("/var/lib/carbon")
POLICY_FILE_NAME = "submission_fee_policy.json"
ARMED_FLAG_NAME = "fee_policy_armed.flag"
SCHEMA = "carbon.exam.submission-fee-policy.v1"
PREFLIGHT_TOOL = "construction_preflight"
PREFLIGHT_REPLY_SCHEMA = "carbon.construction.preflight-reply.v1"
MAINNET_NETUID = 116

#: Terms versions carrying Section 9 (submission burn & retry credits) mapped to
#: their byte-verified published SHA-256 (`OWNER-SUBMISSION-FEE-01` A2, `B8`).
TERMS_V1_SHA256 = "321100f9b4342f36a13bd9cf5c0bfbefbca99a44543e4e8da99c4760315ff1a5"
FEE_BEARING_TERMS_SHA256: dict[str, str] = {
    "carbon-submission-terms-v1": TERMS_V1_SHA256,
}
FEE_BEARING_TERMS_VERSIONS = frozenset(FEE_BEARING_TERMS_SHA256)

#: Subtensor DefaultMinStake (2,000,000 RAO) + AMM swap fee safety margin.
MIN_SUBTENSOR_BURN_RAO = 2_100_000
#: Owner-confirmed hard upper bound per submission (`1.0 TAO`, `OWNER-SUBMISSION-FEE-01` A2 / `M4`).
MAX_SUBMISSION_BURN_RAO = 1_000_000_000

#: Closed submit payment fields (mutually exclusive on a fee-enabled door).
BURN_FIELD = "fee_extrinsic"
CREDIT_FIELD = "fee_credit_id"
PAYMENT_FIELDS = frozenset({BURN_FIELD, CREDIT_FIELD})

#: Closed refusal codes.
FEE_REQUIRED = "fee_required"
FEE_FIELDS_INVALID = "fee_fields_invalid"
FEE_EXTRINSIC_MALFORMED = "fee_extrinsic_malformed"
FEE_NOT_FINALIZED = "fee_not_finalized"
FEE_TOO_OLD = "fee_extrinsic_expired"
FEE_BEFORE_MIN_BLOCK = "fee_before_policy_min_block"
FEE_NOT_FOUND = "fee_burn_not_found"
FEE_HOTKEY_MISMATCH = "fee_hotkey_mismatch"
FEE_CHALLENGE_MISMATCH = "fee_challenge_mismatch"
FEE_INSUFFICIENT = "fee_amount_insufficient"
FEE_ALREADY_SPENT = "fee_already_spent"
FEE_CREDIT_INVALID = "fee_credit_invalid"
FEE_CREDIT_NOT_FOUND = "fee_credit_not_found"
FEE_CREDIT_ALREADY_SPENT = "fee_credit_already_spent"
FEE_POLICY_UNAVAILABLE = "fee_policy_unavailable"
FEE_VERIFIER_UNAVAILABLE = "fee_verifier_unavailable"

UNREADABLE_POLICY = "fee-policy-unreadable"

_POLICY_VERSION = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}\Z", re.ASCII)
#: Scope keys MUST carry an explicit `<netuid>:` prefix (`H12`).
_KEY = re.compile(
    r"([0-9]{1,5}):(\*|[a-z0-9][a-z0-9-]{0,63} [0-9]+(?:\.[0-9]+)*)\Z",
    re.ASCII,
)
_CREDIT_ID = re.compile(r"fcrd_[0-9a-f]{32}\Z", re.ASCII)

#: Grade `FAILED` codes caused by the candidate's own model/runtime or unproven
#: worker exit — NEVER auto-credited (`B4`, `C3`).
MINER_OR_AMBIGUOUS_GRADE_CODES = frozenset(
    {
        "nonfinite_output",
        "output_contract_differs",
        "speed_outputs_disagree",
        "WorkerFailure",
        "WORKER_WALL_LIMIT_REACHED",
        "WORKER_MEMORY_LIMIT_REACHED",
        "OOM_KILLED",
        "NONZERO_EXIT",
        "OWN_ALLOWANCE_ELAPSED",
        "exam_daily_allowance_reached",
        "epoch_limit_reached",
    }
)

#: Repo-verified Carbon-side grade `FAILED` codes & prefixes (`C2`, `C3`, `A3`).
#: Every entry here is enforced against real raise/marker sites in
#: `carbon/challenge_validator/` by `test_submission_fee_redteam.py`.
PROVEN_CARBON_GRADE_CODES = frozenset(
    {
        # Exception class names written by `auto_retry.failure_code`:
        "PoolConstantsNotRegistered",
        "ExamRefused",
        "MenuRefused",
        "ExamCapRefused",
        "RetentionUnavailable",
        "LedgerUnavailable",
        # Explicit Carbon grade/reclass/stop marker codes:
        "grade_hung_carbon",
        "replayed_not_rerun",
        "reclassed_not_the_candidates",
        "cancelled_by_carbon_stop",
        "graded_program_changed",
        "vmap64_grade_needs_sealed_pack",
        "leg_minimum_platform_mismatch",
        "contract_not_served",
        "direct_receiver_stopping",
        "crown_average_not_installed",
        "crown_paused_entry_unavailable",
        # Exact `RetentionUnavailable` codes in `lean_recipe_retention.py`:
        "build_example_snapshot_unavailable",
        "catalog_reexpansion_differs",
        "dual_measurement_registration_changed",
        "dual_model_originals_unavailable",
        "graded_inference_image_graph_only",
        "graded_inference_image_not_in_the_image_store",
        "graded_query_contract_changed",
        "graded_query_unavailable",
        "graded_query_unreadable",
        "graph_bank_role_contract_unavailable",
        "graph_build_receipt_changed",
        "graph_per_case_receipt_unavailable",
        "graph_worker_evidence_unavailable",
        "inference_pair_incomplete",
        "inference_pair_procedure_unreadable",
        "menu_rowcheck_structural_unproven",
        "migrated_admitted_accelerator_differs",
        "migrated_admitted_image_unavailable",
        "native_comparison_changed",
        "native_comparison_unavailable",
        "operator_bank_custody_unavailable",
        "owned_task_unavailable",
        "pool_admit_request_digest_unavailable",
        "pool_has_no_timed_query",
        "pool_owner_unknown",
        "practice_inputs_changed",
        "practice_reference_partly_missing",
        "producer_successor_mismatch",
        "public_battery_train_changed",
        "public_input_target_unavailable",
        "public_measurement_bytes_unavailable",
        "public_train_changed",
        "repeat_state_not_retained_here",
        "single_call_alone_host_not_quiet",
        "single_call_key_unavailable",
        "single_call_needs_the_cpu_grading_image",
        "single_call_pack_is_not_pool_graded",
        "single_call_stage_incomplete",
        "source_context_unavailable",
        "source_image_unavailable",
        "source_kind_unavailable",
        "source_overlay_unavailable",
        "task_identity_invalid",
        "task_not_succeeded",
        "timed_controls_invalid",
        "timed_operation_invalid",
        "verified_attempt_unavailable",
        "worker_evidence_unpack",
        "worker_operation_invalid",
    }
)
PROVEN_CARBON_GRADE_PREFIXES = (
    "admitted_",
    "direct_provider_",
    "dual_native_reference_",
    "evaluation_pack_",
    "evaluation_pack.",
    "exam_cadence_",
    "exam_cap_",
    "exam_key_expired",
    "king_rebuild_",
    "menu_",
    "pack_",
    "pool_constants_",
    "pool_material_",
    "rebind_",
    "rebuild_",
    "regrade_",
    "remeasure_",
    "repeat_grade_",
    "subset_repeat_",
)

#: In-memory mtime caches for `auto-grade/requeued/` operator logs (avoids N+1 rescans).
_OPERATOR_CACHE_GUARD = threading.Lock()
_RELEASES_CACHE: dict[str, tuple[tuple[int, int], frozenset[str]]] = {}
_RECLASS_CACHE: dict[str, tuple[int, frozenset[str]]] = {}
_OWED_ALERTS_CACHE: dict[str, tuple[tuple[int, int], frozenset[str]]] = {}


def ledger_file_name(netuid: int) -> str:
    return f"submission_fees_{int(netuid)}.sqlite3"


def local_host_identity() -> str:
    """Stable per-machine identity (`L2`) so a ledger copied across hosts fails closed."""
    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        p = Path(candidate)
        with contextlib.suppress(OSError):
            if p.is_file() and not p.is_symlink():
                val = p.read_text(encoding="ascii", errors="ignore").strip()
                if val:
                    return f"machine:{val}"
    return f"host:{socket.gethostname().strip().lower() or 'unknown'}"


def is_inside_repo(path: Path | str) -> bool:
    """Return True if ``path`` resolves inside the git repository checkout (`B2`)."""
    try:
        resolved = Path(path).expanduser().resolve(strict=False)
        repo = REPO_ROOT.resolve(strict=False)
    except OSError:
        return True
    return resolved == repo or repo in resolved.parents


def resolve_host_state_dir(
    *,
    netuid: int,
    receiver_root: Path | str | None = None,
    configured_dir: Path | str | None = None,
) -> Path:
    """Resolve the fixed per-`(host, netuid)` state directory strictly outside `REPO_ROOT` (`L1`).

    `receiver_root` is intentionally ignored (`L1`) so two doors in non-sibling
    roots on the same host ALWAYS share the exact same ledger and policy directory:
    1. Explicit `configured_dir` (`receiver.json` `submission_fee_state_dir`), else
    2. `CARBON_SUBMISSION_FEE_STATE_DIR` environment variable, else
    3. `/var/lib/carbon/submission-fee-netuid-<netuid>`.
    """
    del receiver_root
    raw_cfg = configured_dir or os.environ.get("CARBON_SUBMISSION_FEE_STATE_DIR")
    if raw_cfg:
        candidate = Path(raw_cfg).expanduser()
        if not candidate.is_absolute() or is_inside_repo(candidate):
            raise ValueError(
                f"submission_fee_state_dir must be an absolute path outside {REPO_ROOT}"
            )
        return candidate
    fixed = FIXED_HOST_STATE_ROOT / f"submission-fee-netuid-{int(netuid)}"
    if is_inside_repo(fixed):
        raise ValueError(f"default host state path resolves inside repo: {fixed}")
    return fixed


class FeeRefused(ValueError):
    """Typed refusal for a submission fee check (never a scientific verdict)."""

    def __init__(self, code: str, *, status: int = 400, extra: dict | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = dict(extra or {})


def _normalize_grace_tiers(
    grace_tiers: Iterable[tuple[int, int] | dict[str, int]] | None,
    previous_amount_rao: int | None,
    effective_from_block: int | None,
) -> tuple[tuple[int, int], ...] | None:
    tiers: list[tuple[int, int]] = []
    if grace_tiers is not None:
        if not isinstance(grace_tiers, (list, tuple)):
            return None
        for item in grace_tiers:
            if isinstance(item, dict):
                if set(item) != {"until_block", "amount_rao"}:
                    return None
                ub, amt = item["until_block"], item["amount_rao"]
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                ub, amt = item[0], item[1]
            else:
                return None
            if (
                type(ub) is not int
                or isinstance(ub, bool)
                or ub < 0
                or type(amt) is not int
                or isinstance(amt, bool)
                or not MIN_SUBTENSOR_BURN_RAO <= amt <= MAX_SUBMISSION_BURN_RAO
            ):
                return None
            tiers.append((ub, amt))
    if (previous_amount_rao is None) != (effective_from_block is None):
        return None
    if previous_amount_rao is not None and effective_from_block is not None:
        if (
            type(previous_amount_rao) is not int
            or isinstance(previous_amount_rao, bool)
            or not MIN_SUBTENSOR_BURN_RAO
            <= previous_amount_rao
            <= MAX_SUBMISSION_BURN_RAO
            or type(effective_from_block) is not int
            or isinstance(effective_from_block, bool)
            or effective_from_block < 0
        ):
            return None
        pair = (effective_from_block, previous_amount_rao)
        if pair not in tiers:
            tiers.append(pair)
    tiers.sort(key=lambda t: (t[0], t[1]))
    return tuple(tiers)


@dataclass(frozen=True)
class FeePolicy:
    """Per-Challenge-version submission burn policy served by a door."""

    policy_version: str
    amount_rao: int | None
    netuid: int | None
    min_block: int | None
    max_lookback_blocks: int = DEFAULT_MAX_LOOKBACK_BLOCKS
    previous_amount_rao: int | None = None
    effective_from_block: int | None = None
    grace_tiers: tuple[tuple[int, int], ...] = ()
    allow_testnet_without_terms: bool = False

    def __post_init__(self) -> None:
        normalized = _normalize_grace_tiers(
            self.grace_tiers, self.previous_amount_rao, self.effective_from_block
        )
        if normalized is None:
            object.__setattr__(self, "policy_version", UNREADABLE_POLICY)
            object.__setattr__(self, "grace_tiers", ())
            return
        object.__setattr__(self, "grace_tiers", normalized)
        if normalized and self.previous_amount_rao is None:
            object.__setattr__(self, "effective_from_block", normalized[0][0])
            object.__setattr__(self, "previous_amount_rao", normalized[0][1])

    @property
    def ready(self) -> bool:
        return (
            self.policy_version != UNREADABLE_POLICY
            and type(self.amount_rao) is int
            and not isinstance(self.amount_rao, bool)
            and MIN_SUBTENSOR_BURN_RAO <= self.amount_rao <= MAX_SUBMISSION_BURN_RAO
            and type(self.netuid) is int
            and not isinstance(self.netuid, bool)
            and 0 <= self.netuid <= 65535
            and type(self.min_block) is int
            and not isinstance(self.min_block, bool)
            and self.min_block >= 0
            and type(self.max_lookback_blocks) is int
            and not isinstance(self.max_lookback_blocks, bool)
            and 1 <= self.max_lookback_blocks <= 2_600_000
            and type(self.allow_testnet_without_terms) is bool
            and not (self.netuid == MAINNET_NETUID and self.allow_testnet_without_terms)
        )

    def required_amount_at_block(self, block: int) -> int:
        """Required burn RAO for a burn finalized in ``block``, honoring all active
        rate-hike grace tiers (`grace_tiers` where ``block < until_block``)."""
        assert self.amount_rao is not None
        candidates = [self.amount_rao]
        for until_block, tier_amount in self.grace_tiers:
            if block < until_block:
                candidates.append(tier_amount)
        return min(candidates)

    def facts(
        self, challenge_id: str, *, receiver: str | None = None
    ) -> dict[str, object]:
        out: dict[str, object] = {
            "policy_version": self.policy_version,
            "amount_rao": self.amount_rao,
            "netuid": self.netuid,
            "challenge_id": challenge_id,
            "min_block": self.min_block,
            "max_lookback_blocks": self.max_lookback_blocks,
            "remark_version": REMARK_VERSION,
            "preflight_tool": PREFLIGHT_TOOL,
        }
        if receiver is not None:
            out["receiver"] = receiver
        if self.grace_tiers:
            out["grace_tiers"] = [
                {"until_block": ub, "amount_rao": amt} for ub, amt in self.grace_tiers
            ]
            out["previous_amount_rao"] = self.grace_tiers[0][1]
            out["effective_from_block"] = self.grace_tiers[0][0]
        return out


def check_door_terms_for_fee(
    policy: FeePolicy | None, terms: object
) -> FeePolicy | None:
    """Enforce `B8` / `A2`: an enabled fee policy fails closed (`503`) unless the door
    serves `carbon-submission-terms-v1` at its exact pinned SHA-256 (`TERMS_V1_SHA256`),
    except when `allow_testnet_without_terms` is explicitly set on a non-Mainnet row."""
    if policy is None or not policy.ready:
        return policy
    if (
        policy.allow_testnet_without_terms
        and policy.netuid != MAINNET_NETUID
        and terms is None
    ):
        return policy
    if terms is None or not getattr(terms, "ready", False):
        return FeePolicy(UNREADABLE_POLICY, None, None, None)
    tver = getattr(terms, "version", None)
    expected_sha = FEE_BEARING_TERMS_SHA256.get(tver) if type(tver) is str else None
    if expected_sha is None or getattr(terms, "sha256", None) != expected_sha:
        return FeePolicy(UNREADABLE_POLICY, None, None, None)
    if hasattr(terms, "text"):
        raw_text = getattr(terms, "text", None)
        if not isinstance(raw_text, (bytes, bytearray)):
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
        if hashlib.sha256(bytes(raw_text)).hexdigest() != expected_sha:
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
    return policy


def _valid_row(row: object) -> tuple[bool, FeePolicy] | None:
    """Return ``(enabled, policy)`` for a valid row, or ``None`` if malformed."""
    if type(row) is not dict:
        return None
    required = {"policy_version", "amount_rao", "netuid", "min_block"}
    optional = {
        "enabled",
        "max_lookback_blocks",
        "previous_amount_rao",
        "effective_from_block",
        "grace_tiers",
        "allow_testnet_without_terms",
    }
    if not required <= set(row) <= required | optional:
        return None
    enabled = row.get("enabled", True)
    if type(enabled) is not bool:
        return None
    version = row["policy_version"]
    amount = row["amount_rao"]
    netuid = row["netuid"]
    min_block = row["min_block"]
    lookback = row.get("max_lookback_blocks", DEFAULT_MAX_LOOKBACK_BLOCKS)
    prev_amount = row.get("previous_amount_rao")
    eff_block = row.get("effective_from_block")
    raw_tiers = row.get("grace_tiers")
    allow_no_terms = row.get("allow_testnet_without_terms", False)
    if type(allow_no_terms) is not bool:
        return None
    normalized_tiers = _normalize_grace_tiers(raw_tiers, prev_amount, eff_block)
    if normalized_tiers is None:
        return None
    if (
        type(version) is not str
        or _POLICY_VERSION.fullmatch(version) is None
        or version == UNREADABLE_POLICY
        or type(amount) is not int
        or isinstance(amount, bool)
        or not MIN_SUBTENSOR_BURN_RAO <= amount <= MAX_SUBMISSION_BURN_RAO
        or type(netuid) is not int
        or isinstance(netuid, bool)
        or not 0 <= netuid <= 65535
        or type(min_block) is not int
        or isinstance(min_block, bool)
        or min_block < 0
        or type(lookback) is not int
        or isinstance(lookback, bool)
        or not 1 <= lookback <= 2_600_000
    ):
        return None
    pol = FeePolicy(
        policy_version=version,
        amount_rao=amount,
        netuid=netuid,
        min_block=min_block,
        max_lookback_blocks=lookback,
        grace_tiers=normalized_tiers,
        allow_testnet_without_terms=allow_no_terms,
    )
    if not pol.ready:
        return None
    return enabled, pol


def for_door(
    challenge_id: str,
    version: str,
    *,
    expected_netuid: int | None = None,
    path: Path | str,
) -> FeePolicy | None:
    """Return this door's ``FeePolicy``, or ``None`` if no fee is enabled for it.

    Scope & emergency recovery rules (`A2`, `H3`, `H12`):
    - Top-level `"kill_switch": true` or disabled `"<netuid>:*"` is checked **before**
      other rows so an emergency kill-switch ALWAYS clears a `503` caused by a bad row!
    - `FileNotFoundError` returns ``None`` (caller checks armed flag); `PermissionError`
      (`EACCES`), symlinks, or corrupt JSON fail closed (`UNREADABLE_POLICY`, `503`).
    - On Mainnet `116`, `"116:*"` with `"enabled": true` fails closed (`503`).
    """
    target = Path(path)
    if is_inside_repo(target):
        return FeePolicy(UNREADABLE_POLICY, None, None, None)
    try:
        st_info = target.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        # `EACCES` or broken path fails closed (`H3`), never reads as dark!
        return FeePolicy(UNREADABLE_POLICY, None, None, None)
    if not stat.S_ISREG(st_info.st_mode):
        return FeePolicy(UNREADABLE_POLICY, None, None, None)
    try:
        doc = json.loads(target.read_bytes())
    except (OSError, ValueError):
        return FeePolicy(UNREADABLE_POLICY, None, None, None)
    if (
        type(doc) is not dict
        or not {"schema", "source", "rows"}
        <= set(doc)
        <= {"schema", "source", "rows", "kill_switch"}
        or doc.get("schema") != SCHEMA
        or type(doc.get("source")) is not str
        or type(doc.get("rows")) is not dict
        or type(doc.get("kill_switch", False)) is not bool
    ):
        return FeePolicy(UNREADABLE_POLICY, None, None, None)

    # `H3`: host-wide kill_switch MUST take precedence before per-row validation
    # so `disable --kill-switch` clears a 503 caused by any malformed row!
    if doc.get("kill_switch") is True:
        return None

    rows = doc["rows"]
    if expected_netuid is not None:
        raw_wc = rows.get(f"{expected_netuid}:*")
        if type(raw_wc) is dict and raw_wc.get("enabled") is False:
            return None

    parsed_rows: dict[str, tuple[bool, FeePolicy]] = {}
    for key, raw_row in rows.items():
        m = _KEY.fullmatch(key) if type(key) is str else None
        if m is None:
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
        validated = _valid_row(raw_row)
        if validated is None:
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
        prefix_netuid = int(m.group(1))
        scope_body = m.group(2)
        enabled_flag, row_pol = validated
        if prefix_netuid != row_pol.netuid:
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
        if prefix_netuid == MAINNET_NETUID and scope_body == "*" and enabled_flag:
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
        parsed_rows[key] = validated

    if expected_netuid is None:
        matching_nets = {
            pol.netuid
            for k, (_, pol) in parsed_rows.items()
            if k.endswith((f":{challenge_id} {version}", ":*"))
        }
        if len(matching_nets) > 1:
            return FeePolicy(UNREADABLE_POLICY, None, None, None)
        expected_netuid = next(iter(matching_nets), None)
        if expected_netuid is None:
            return None

    wildcard_key = f"{expected_netuid}:*"
    if wildcard_key in parsed_rows and not parsed_rows[wildcard_key][0]:
        return None

    exact_key = f"{expected_netuid}:{challenge_id} {version}"
    if exact_key in parsed_rows:
        enabled, pol = parsed_rows[exact_key]
        return pol if enabled else None

    if wildcard_key in parsed_rows:
        enabled, pol = parsed_rows[wildcard_key]
        return pol if enabled else None

    return None


def split_submit_fields(
    policy: FeePolicy | None,
    fields: dict[str, object],
    *,
    require_payment: bool,
) -> tuple[str | None, dict[str, object], dict[str, str] | None]:
    """Extract ``(refusal_code, core_fields, payment_spec)`` before terms/recipe checks."""
    present_payment = set(fields) & PAYMENT_FIELDS
    if policy is None:
        if present_payment:
            return "submission_fields", {}, None
        return None, dict(fields), None

    core = {k: v for k, v in fields.items() if k not in PAYMENT_FIELDS}
    if not require_payment:
        if present_payment:
            return FEE_FIELDS_INVALID, {}, None
        return None, core, None

    if not present_payment:
        return FEE_REQUIRED, {}, None
    if len(present_payment) != 1:
        return FEE_FIELDS_INVALID, {}, None

    if BURN_FIELD in present_payment:
        raw_ext = fields[BURN_FIELD]
        if type(raw_ext) is not str or parse_extrinsic_id(raw_ext) is None:
            return FEE_EXTRINSIC_MALFORMED, {}, None
        return None, core, {"kind": "burn", "extrinsic_id": raw_ext}

    raw_cred = fields[CREDIT_FIELD]
    if type(raw_cred) is not str or _CREDIT_ID.fullmatch(raw_cred) is None:
        return FEE_CREDIT_INVALID, {}, None
    return None, core, {"kind": "credit", "credit_id": raw_cred}


def refusal_body(
    code: str,
    policy: FeePolicy | None,
    challenge_id: str,
    *,
    receiver: str | None = None,
    **extra: object,
) -> dict[str, object]:
    body: dict[str, object] = {"refused": code}
    if policy is not None and policy.ready:
        body["fee"] = policy.facts(challenge_id, receiver=receiver)
    body.update(extra)
    return body


_DDL = """
CREATE TABLE IF NOT EXISTS fee_ledger_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_indexer_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    last_indexed_block INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_indexed_blocks (
    block INTEGER PRIMARY KEY,
    indexed_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observed_burns (
    netuid INTEGER NOT NULL,
    extrinsic_id TEXT NOT NULL,
    block INTEGER NOT NULL,
    extrinsic_idx INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    hotkey TEXT NOT NULL,
    payer TEXT NOT NULL,
    amount_rao INTEGER NOT NULL,
    alpha_burned_rao INTEGER NOT NULL,
    remark_hash TEXT NOT NULL,
    observed_utc TEXT NOT NULL,
    PRIMARY KEY (netuid, extrinsic_id)
);
CREATE INDEX IF NOT EXISTS observed_burns_hotkey
    ON observed_burns(netuid, hotkey, block);

CREATE TABLE IF NOT EXISTS fee_burn_claims (
    netuid INTEGER NOT NULL,
    extrinsic_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('RESERVED', 'SPENT')),
    reservation_token TEXT NOT NULL,
    door_id TEXT NOT NULL DEFAULT '',
    expected_submission_id TEXT,
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    amount_rao INTEGER NOT NULL,
    alpha_burned_rao INTEGER NOT NULL,
    submission_id TEXT,
    claimed_utc TEXT NOT NULL,
    PRIMARY KEY (netuid, extrinsic_id)
);

CREATE TABLE IF NOT EXISTS infra_credits (
    credit_id TEXT PRIMARY KEY,
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    source_settlement_id INTEGER NOT NULL UNIQUE,
    source_submission_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('AVAILABLE', 'RESERVED', 'REDEEMED')),
    reservation_token TEXT,
    door_id TEXT NOT NULL DEFAULT '',
    expected_submission_id TEXT,
    redeemed_submission_id TEXT,
    issued_utc TEXT NOT NULL,
    redeemed_utc TEXT
);
CREATE INDEX IF NOT EXISTS infra_credits_hotkey
    ON infra_credits(hotkey, challenge_id, state);

CREATE TABLE IF NOT EXISTS fee_settlements (
    settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL UNIQUE,
    current_leaf_submission_id TEXT NOT NULL,
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    payment_kind TEXT NOT NULL CHECK (payment_kind IN ('BURN', 'CREDIT')),
    payment_ref TEXT NOT NULL,
    amount_rao INTEGER NOT NULL,
    alpha_burned_rao INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK (
        lifecycle_state IN ('ADMITTED', 'CONSUMED_TERMINAL', 'CREDITED_INFRA')
    ),
    issued_credit_id TEXT,
    admitted_utc TEXT NOT NULL,
    settled_utc TEXT
);
CREATE INDEX IF NOT EXISTS fee_settlements_hotkey
    ON fee_settlements(hotkey, lifecycle_state);
CREATE INDEX IF NOT EXISTS fee_settlements_leaf
    ON fee_settlements(current_leaf_submission_id);
"""


def _utc_now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class _Reservation:
    token: str
    payment_kind: str
    payment_ref: str
    netuid: int
    hotkey: str
    challenge_id: str
    challenge_version: str
    policy_version: str
    amount_rao: int
    alpha_burned_rao: int
    door_id: str
    expected_submission_id: str | None


class FeeLedger:
    """Shared per-`(host, netuid)` owner-only SQLite ledger of burns, claims, and credits."""

    def __init__(
        self,
        path: Path | str,
        *,
        expected_netuid: int | None = None,
        expected_genesis_hash: str | None = None,
        expected_host_id: str | None = None,
        receiver_hotkey: str | None = None,
    ) -> None:
        self.path = Path(path)
        if is_inside_repo(self.path):
            raise FeeBurnUnavailable("fee_ledger_inside_repo_refused")
        self._guard = threading.Lock()
        self._ensure_owner_only()
        host_pin = (
            local_host_identity() if expected_host_id is None else str(expected_host_id)
        )
        with closing(self._connect()) as db:
            db.executescript(_DDL)
            self._ensure_columns(db)
            self._bind_identity(
                db,
                expected_netuid=expected_netuid,
                expected_genesis_hash=expected_genesis_hash,
                expected_host_id=host_pin,
                receiver_hotkey=receiver_hotkey,
            )
        self._chmod_sidecars()

    @staticmethod
    def _ensure_columns(db: sqlite3.Connection) -> None:
        for table in ("fee_burn_claims", "infra_credits"):
            cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            if "door_id" not in cols:
                db.execute(
                    f"ALTER TABLE {table} ADD COLUMN door_id TEXT NOT NULL DEFAULT ''"
                )
            if "expected_submission_id" not in cols:
                db.execute(
                    f"ALTER TABLE {table} ADD COLUMN expected_submission_id TEXT"
                )

    def _bind_identity(
        self,
        db: sqlite3.Connection,
        *,
        expected_netuid: int | None,
        expected_genesis_hash: str | None,
        expected_host_id: str | None,
        receiver_hotkey: str | None,
    ) -> None:
        pairs: list[tuple[str, str]] = []
        if expected_netuid is not None:
            pairs.append(("netuid", str(int(expected_netuid))))
        if expected_genesis_hash is not None:
            pairs.append(("genesis_hash", str(expected_genesis_hash).lower()))
        if expected_host_id:
            pairs.append(("host_id", str(expected_host_id)))
        db.execute("BEGIN IMMEDIATE")
        try:
            for k, val in pairs:
                row = db.execute(
                    "SELECT value FROM fee_ledger_meta WHERE key = ?", (k,)
                ).fetchone()
                if row is None:
                    db.execute(
                        "INSERT INTO fee_ledger_meta(key, value) VALUES (?, ?)",
                        (k, val),
                    )
                elif str(row[0]) != val:
                    db.execute("ROLLBACK")
                    raise FeeBurnUnavailable(f"fee_ledger_{k}_mismatch")
            if type(receiver_hotkey) is str and receiver_hotkey:
                r_row = db.execute(
                    "SELECT value FROM fee_ledger_meta WHERE key = 'receiver_hotkey'"
                ).fetchone()
                if r_row is None:
                    db.execute(
                        "INSERT INTO fee_ledger_meta(key, value) VALUES ('receiver_hotkey', ?)",
                        (receiver_hotkey,),
                    )
            db.execute("COMMIT")
        except FeeBurnUnavailable:
            raise
        except Exception as exc:
            db.execute("ROLLBACK")
            raise FeeBurnUnavailable("fee_ledger_meta_failed") from exc

    def _ensure_owner_only(self) -> None:
        if self.path.is_symlink():
            raise FeeBurnUnavailable("fee_ledger_symlink_refused")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.exists():
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise FeeBurnUnavailable("fee_ledger_not_regular_file")
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                raise FeeBurnUnavailable("fee_ledger_wrong_owner")
            if info.st_mode & 0o077:
                os.chmod(self.path, 0o600)
        else:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)

    def _chmod_sidecars(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            with contextlib.suppress(OSError):
                if sidecar.exists() and not sidecar.is_symlink():
                    st_info = sidecar.lstat()
                    if stat.S_ISREG(st_info.st_mode) and (st_info.st_mode & 0o077):
                        os.chmod(sidecar, 0o600)

    def _connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise FeeBurnUnavailable("fee_ledger_symlink_refused")
        conn = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def register_lookback(self, max_lookback_blocks: int) -> None:
        """Record the largest lookback window across all doors sharing this ledger."""
        if type(max_lookback_blocks) is not int or max_lookback_blocks < 1:
            return
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT value FROM fee_ledger_meta WHERE key = 'max_lookback_blocks'"
                ).fetchone()
                cur_max = int(row[0]) if row is not None else 0
                if max_lookback_blocks > cur_max:
                    db.execute(
                        """INSERT INTO fee_ledger_meta(key, value)
                           VALUES ('max_lookback_blocks', ?)
                           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                        (str(int(max_lookback_blocks)),),
                    )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def effective_prune_lookback(self, fallback_lookback: int) -> int:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT value FROM fee_ledger_meta WHERE key = 'max_lookback_blocks'"
            ).fetchone()
        stored = int(row[0]) if row is not None and str(row[0]).isdigit() else 0
        return max(int(fallback_lookback), stored)

    def recover_door_reservations(
        self,
        door_id: str,
        is_admitted_fn: Callable[[str], bool | None],
        *,
        log_fn: Callable[..., None] | None = None,
    ) -> dict[str, int]:
        """Resolve this door's leftover `RESERVED` rows after a crash (`B5`, `H5`, `C4`).

        Three-state fail-closed semantics (`C4`):
        - `True` (`OUTCOME` row recorded in `AttemptLedger`): checks `fee_settlements`
          first (`H6` — releases duplicate reservation if already settled) and otherwise
          commits `SPENT`/`REDEEMED` + inserts `ADMITTED` settlement.
        - `False` (proven not admitted): releases the reservation cleanly.
        - `None` (`expected_submission_id` missing or `AttemptLedger` unreadable):
          keeps the row `RESERVED` fail-closed and logs an operator alert!
        """
        committed_count = 0
        released_count = 0
        unknown_count = 0
        stamp = _utc_now()

        def _ask_admitted(sub_id: object) -> bool | None:
            if type(sub_id) is not str or not sub_id:
                return None
            try:
                res = is_admitted_fn(sub_id)
            except Exception:  # noqa: BLE001
                return None
            return res if type(res) is bool else None

        with self._guard, closing(self._connect()) as db:
            burn_rows = db.execute(
                """SELECT netuid, extrinsic_id, reservation_token, expected_submission_id,
                          hotkey, challenge_id, challenge_version, policy_version,
                          amount_rao, alpha_burned_rao
                   FROM fee_burn_claims
                   WHERE state = 'RESERVED' AND door_id = ?""",
                (door_id,),
            ).fetchall()
            credit_rows = db.execute(
                """SELECT credit_id, reservation_token, expected_submission_id,
                          hotkey, challenge_id
                   FROM infra_credits
                   WHERE state = 'RESERVED' AND door_id = ?""",
                (door_id,),
            ).fetchall()

            for (
                netuid,
                ext_id,
                tok,
                exp_sub,
                hk,
                cid,
                cver,
                pver,
                amt,
                alpha,
            ) in burn_rows:
                admitted = _ask_admitted(exp_sub)
                if admitted is None:
                    unknown_count += 1
                    if callable(log_fn):
                        with contextlib.suppress(Exception):
                            log_fn(
                                "fee_reservation_recovery_unknown",
                                kind="BURN",
                                ref=str(ext_id),
                                expected_submission_id=exp_sub,
                            )
                    continue
                db.execute("BEGIN IMMEDIATE")
                try:
                    existing_settlement = (
                        db.execute(
                            """SELECT 1 FROM fee_settlements
                               WHERE submission_id = ? OR current_leaf_submission_id = ?""",
                            (str(exp_sub), str(exp_sub)),
                        ).fetchone()
                        if admitted
                        else None
                    )
                    if admitted and existing_settlement is None:
                        cur = db.execute(
                            """UPDATE fee_burn_claims
                               SET state = 'SPENT', submission_id = ?
                               WHERE netuid = ? AND extrinsic_id = ?
                                 AND reservation_token = ? AND state = 'RESERVED'""",
                            (str(exp_sub), int(netuid), str(ext_id), str(tok)),
                        )
                        if cur.rowcount == 1:
                            db.execute(
                                """INSERT OR IGNORE INTO fee_settlements(
                                       submission_id, current_leaf_submission_id, hotkey,
                                       challenge_id, challenge_version, policy_version,
                                       payment_kind, payment_ref, amount_rao, alpha_burned_rao,
                                       lifecycle_state, issued_credit_id, admitted_utc, settled_utc
                                   ) VALUES (?, ?, ?, ?, ?, ?, 'BURN', ?, ?, ?, 'ADMITTED', NULL, ?, NULL)""",
                                (
                                    str(exp_sub),
                                    str(exp_sub),
                                    str(hk),
                                    str(cid),
                                    str(cver),
                                    str(pver),
                                    str(ext_id),
                                    int(amt),
                                    int(alpha),
                                    stamp,
                                ),
                            )
                            committed_count += 1
                    else:
                        cur = db.execute(
                            """DELETE FROM fee_burn_claims
                               WHERE netuid = ? AND extrinsic_id = ?
                                 AND reservation_token = ? AND state = 'RESERVED'""",
                            (int(netuid), str(ext_id), str(tok)),
                        )
                        released_count += cur.rowcount
                    db.execute("COMMIT")
                except Exception:
                    db.execute("ROLLBACK")
                    raise

            for credit_id, tok, exp_sub, hk, cid in credit_rows:
                admitted = _ask_admitted(exp_sub)
                if admitted is None:
                    unknown_count += 1
                    if callable(log_fn):
                        with contextlib.suppress(Exception):
                            log_fn(
                                "fee_reservation_recovery_unknown",
                                kind="CREDIT",
                                ref=str(credit_id),
                                expected_submission_id=exp_sub,
                            )
                    continue
                db.execute("BEGIN IMMEDIATE")
                try:
                    existing_settlement = (
                        db.execute(
                            """SELECT 1 FROM fee_settlements
                               WHERE submission_id = ? OR current_leaf_submission_id = ?""",
                            (str(exp_sub), str(exp_sub)),
                        ).fetchone()
                        if admitted
                        else None
                    )
                    if admitted and existing_settlement is None:
                        cur = db.execute(
                            """UPDATE infra_credits
                               SET state = 'REDEEMED',
                                   redeemed_submission_id = ?,
                                   redeemed_utc = ?
                               WHERE credit_id = ? AND reservation_token = ? AND state = 'RESERVED'""",
                            (str(exp_sub), stamp, str(credit_id), str(tok)),
                        )
                        if cur.rowcount == 1:
                            db.execute(
                                """INSERT OR IGNORE INTO fee_settlements(
                                       submission_id, current_leaf_submission_id, hotkey,
                                       challenge_id, challenge_version, policy_version,
                                       payment_kind, payment_ref, amount_rao, alpha_burned_rao,
                                       lifecycle_state, issued_credit_id, admitted_utc, settled_utc
                                   ) VALUES (?, ?, ?, ?, '', 'recovered', 'CREDIT', ?, 0, 0, 'ADMITTED', NULL, ?, NULL)""",
                                (
                                    str(exp_sub),
                                    str(exp_sub),
                                    str(hk),
                                    str(cid),
                                    str(credit_id),
                                    stamp,
                                ),
                            )
                            committed_count += 1
                    else:
                        cur = db.execute(
                            """UPDATE infra_credits
                               SET state = 'AVAILABLE',
                                   reservation_token = NULL,
                                   door_id = '',
                                   expected_submission_id = NULL
                               WHERE credit_id = ? AND reservation_token = ? AND state = 'RESERVED'""",
                            (str(credit_id), str(tok)),
                        )
                        released_count += cur.rowcount
                    db.execute("COMMIT")
                except Exception:
                    db.execute("ROLLBACK")
                    raise
        return {
            "committed": committed_count,
            "released": released_count,
            "unknown": unknown_count,
        }

    # --- Indexer state ---------------------------------------------------------

    def indexer_cursor(self) -> int | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT last_indexed_block FROM fee_indexer_state WHERE singleton = 1"
            ).fetchone()
            return None if row is None else int(row[0])

    def advance_indexer_cursor(self, block: int) -> None:
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """INSERT INTO fee_indexer_state(singleton, last_indexed_block)
                       VALUES (1, ?)
                       ON CONFLICT(singleton) DO UPDATE
                       SET last_indexed_block = MAX(last_indexed_block, excluded.last_indexed_block)""",
                    (int(block),),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def is_block_indexed(self, block: int) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT 1 FROM fee_indexed_blocks WHERE block = ?", (int(block),)
            ).fetchone()
            return row is not None

    def prune_indexed_blocks(self, keep_from_block: int) -> int:
        """Prune old block-index markers while keeping all observed burns and claims."""
        if keep_from_block <= 0:
            return 0
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                cur = db.execute(
                    "DELETE FROM fee_indexed_blocks WHERE block < ?",
                    (int(keep_from_block),),
                )
                db.execute("COMMIT")
                return int(cur.rowcount)
            except Exception:
                db.execute("ROLLBACK")
                raise

    def record_indexed_block(
        self, block: int, burns: tuple[ObservedFeeBurn, ...] | list[ObservedFeeBurn]
    ) -> None:
        stamp = _utc_now()
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for burn in burns:
                    db.execute(
                        """INSERT OR IGNORE INTO observed_burns(
                               netuid, extrinsic_id, block, extrinsic_idx, block_hash,
                               hotkey, payer, amount_rao, alpha_burned_rao, remark_hash, observed_utc
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            burn.netuid,
                            burn.extrinsic_id,
                            burn.block,
                            burn.extrinsic_idx,
                            burn.block_hash,
                            burn.hotkey,
                            burn.payer,
                            burn.amount_rao,
                            burn.alpha_burned_rao,
                            burn.remark_hash,
                            stamp,
                        ),
                    )
                db.execute(
                    "INSERT OR IGNORE INTO fee_indexed_blocks(block, indexed_utc) VALUES (?, ?)",
                    (int(block), stamp),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    # --- Credits & preflight helpers -------------------------------------------

    def available_credit(self, hotkey: str, challenge_id: str) -> str | None:
        """Oldest available ``credit_id`` for ``(hotkey, challenge_id)``, or None."""
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT credit_id FROM infra_credits
                   WHERE hotkey = ? AND challenge_id = ? AND state = 'AVAILABLE'
                   ORDER BY issued_utc ASC, credit_id ASC LIMIT 1""",
                (hotkey, challenge_id),
            ).fetchone()
            return None if row is None else str(row[0])

    def settled_payment_for_submission(
        self, hotkey: str, submission_id: str | None
    ) -> tuple[str, str] | None:
        """Return ``(payment_kind, payment_ref)`` if ``submission_id`` is ALREADY paid
        (in `fee_settlements` or pinned on an interrupted post-admit `RESERVED` row, `M2`/`C4`).
        """
        if type(submission_id) is not str or not submission_id:
            return None
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT payment_kind, payment_ref
                   FROM fee_settlements
                   WHERE hotkey = ?
                     AND (submission_id = ? OR current_leaf_submission_id = ?)
                   ORDER BY settlement_id DESC LIMIT 1""",
                (hotkey, submission_id, submission_id),
            ).fetchone()
            if row is not None:
                return str(row[0]), str(row[1])
            b_row = db.execute(
                """SELECT extrinsic_id FROM fee_burn_claims
                   WHERE hotkey = ? AND expected_submission_id = ? AND state = 'RESERVED'
                   LIMIT 1""",
                (hotkey, submission_id),
            ).fetchone()
            if b_row is not None:
                return "BURN", str(b_row[0])
            c_row = db.execute(
                """SELECT credit_id FROM infra_credits
                   WHERE hotkey = ? AND expected_submission_id = ? AND state = 'RESERVED'
                   LIMIT 1""",
                (hotkey, submission_id),
            ).fetchone()
            if c_row is not None:
                return "CREDIT", str(c_row[0])
        return None

    def is_submission_credited(self, submission_id: str) -> bool:
        """Return True if ``submission_id`` (or its chain) already received a `RETRY_CREDIT` (`C7`)."""
        if type(submission_id) is not str or not submission_id:
            return False
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT 1 FROM fee_settlements
                   WHERE lifecycle_state = 'CREDITED_INFRA'
                     AND (submission_id = ? OR current_leaf_submission_id = ?)
                   LIMIT 1""",
                (submission_id, submission_id),
            ).fetchone()
            if row is not None:
                return True
            c_row = db.execute(
                "SELECT 1 FROM infra_credits WHERE source_submission_id = ? LIMIT 1",
                (submission_id,),
            ).fetchone()
            return c_row is not None

    def unspent_burns_for_hotkey(
        self,
        *,
        netuid: int,
        challenge_id: str,
        receiver: str,
        hotkey: str,
        min_block: int,
        known_finalized_head: int | None = None,
        policy: FeePolicy | None = None,
    ) -> list[str]:
        """Unspent indexed ``extrinsic_id``s matching ``(netuid, challenge_id, receiver, hotkey)``,
        filtered to the active lookback window and ordered **newest first** (`B7(a)`).
        """
        expected_hash = fee_remark_hash(netuid, challenge_id, receiver, hotkey)
        lookback = (
            policy.max_lookback_blocks
            if policy is not None and policy.ready
            else DEFAULT_MAX_LOOKBACK_BLOCKS
        )
        effective_min_block = int(min_block)
        if known_finalized_head is not None:
            effective_min_block = max(
                effective_min_block, int(known_finalized_head) - int(lookback)
            )
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT b.extrinsic_id, b.block, b.amount_rao
                   FROM observed_burns b
                   LEFT JOIN fee_burn_claims c
                     ON c.netuid = b.netuid AND c.extrinsic_id = b.extrinsic_id
                   WHERE b.netuid = ?
                    AND b.hotkey = ?
                    AND b.remark_hash = ?
                    AND b.block >= ?
                    AND c.extrinsic_id IS NULL
                   ORDER BY b.block DESC, b.extrinsic_idx DESC""",
                (netuid, hotkey, expected_hash, effective_min_block),
            ).fetchall()
            out: list[str] = []
            for ext_id, blk, amt in rows:
                if (
                    policy is not None
                    and policy.ready
                    and int(amt) < policy.required_amount_at_block(int(blk))
                ):
                    continue
                out.append(str(ext_id))
            return out

    def open_settlements(self, hotkey: str) -> list[dict[str, object]]:
        """`ADMITTED` settlements for ``hotkey`` awaiting terminal classification (never rescans `CONSUMED_TERMINAL`)."""
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT settlement_id, submission_id, current_leaf_submission_id,
                          challenge_id, challenge_version, lifecycle_state
                   FROM fee_settlements
                   WHERE hotkey = ?
                     AND lifecycle_state = 'ADMITTED'
                     AND issued_credit_id IS NULL
                   ORDER BY settlement_id ASC""",
                (hotkey,),
            ).fetchall()
            return [dict(r) for r in rows]

    def open_settlements_for_tasks(
        self, hotkey: str, task_ids: Iterable[str]
    ) -> list[dict[str, object]]:
        """Targeted lookup of `CONSUMED_TERMINAL` rows whose task appears in operator `releases.jsonl` / `reclass-kept` (`C2`)."""
        targets = sorted({str(t) for t in task_ids if t})
        if not targets:
            return []
        placeholders = ",".join("?" for _ in targets)
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                f"""SELECT settlement_id, submission_id, current_leaf_submission_id,
                           challenge_id, challenge_version, lifecycle_state
                    FROM fee_settlements
                    WHERE hotkey = ?
                      AND lifecycle_state = 'CONSUMED_TERMINAL'
                      AND issued_credit_id IS NULL
                      AND (submission_id IN ({placeholders})
                           OR current_leaf_submission_id IN ({placeholders}))
                    ORDER BY settlement_id ASC""",
                (hotkey, *targets, *targets),
            ).fetchall()
            return [dict(r) for r in rows]

    def advance_settlement_leaf(
        self, settlement_id: int, new_leaf_submission_id: str
    ) -> None:
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """UPDATE fee_settlements
                       SET current_leaf_submission_id = ?
                       WHERE settlement_id = ? AND issued_credit_id IS NULL""",
                    (new_leaf_submission_id, int(settlement_id)),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def mark_settlement_consumed(self, settlement_id: int) -> None:
        stamp = _utc_now()
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """UPDATE fee_settlements
                       SET lifecycle_state = 'CONSUMED_TERMINAL', settled_utc = ?
                       WHERE settlement_id = ? AND lifecycle_state = 'ADMITTED'""",
                    (stamp, int(settlement_id)),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def issue_infra_credit_for_settlement(
        self,
        settlement_id: int,
        *,
        leaf_submission_id: str,
        reason: str,
    ) -> str | None:
        """Atomically mint at most 1 ``RETRY_CREDIT`` for ``settlement_id``."""
        stamp = _utc_now()
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT credit_id FROM infra_credits WHERE source_settlement_id = ?",
                    (int(settlement_id),),
                ).fetchone()
                if existing is not None:
                    db.execute("COMMIT")
                    return str(existing[0])

                row = db.execute(
                    """SELECT hotkey, challenge_id, lifecycle_state
                       FROM fee_settlements
                       WHERE settlement_id = ?""",
                    (int(settlement_id),),
                ).fetchone()
                if row is None or row[2] not in ("ADMITTED", "CONSUMED_TERMINAL"):
                    db.execute("COMMIT")
                    return None
                hotkey, challenge_id, _ = row
                entropy = (
                    f"{settlement_id}:{leaf_submission_id}:{secrets.token_hex(16)}"
                )
                credit_id = (
                    "fcrd_" + hashlib.sha256(entropy.encode("ascii")).hexdigest()[:32]
                )
                db.execute(
                    """INSERT INTO infra_credits(
                           credit_id, hotkey, challenge_id, source_settlement_id,
                           source_submission_id, reason, state, issued_utc
                       ) VALUES (?, ?, ?, ?, ?, ?, 'AVAILABLE', ?)""",
                    (
                        credit_id,
                        hotkey,
                        challenge_id,
                        int(settlement_id),
                        leaf_submission_id,
                        reason,
                        stamp,
                    ),
                )
                db.execute(
                    """UPDATE fee_settlements
                       SET lifecycle_state = 'CREDITED_INFRA',
                           current_leaf_submission_id = ?,
                           issued_credit_id = ?,
                           settled_utc = ?
                       WHERE settlement_id = ?""",
                    (leaf_submission_id, credit_id, stamp, int(settlement_id)),
                )
                db.execute("COMMIT")
                return credit_id
            except Exception:
                db.execute("ROLLBACK")
                raise

    def credit_submission_by_id(self, submission_id: str, *, reason: str) -> str | None:
        """Operator escape hatch: mint at most 1 `RETRY_CREDIT` for a specific `submission_id`."""
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT settlement_id, current_leaf_submission_id
                   FROM fee_settlements
                   WHERE submission_id = ? OR current_leaf_submission_id = ?
                   ORDER BY settlement_id DESC LIMIT 1""",
                (submission_id, submission_id),
            ).fetchone()
        if row is None:
            return None
        return self.issue_infra_credit_for_settlement(
            int(row[0]), leaf_submission_id=str(row[1]), reason=reason
        )

    def credit_version_closed(self, submission_ids: Iterable[str]) -> list[str]:
        """Mint `version_closed` retry credits for closed submissions in this shared ledger (`B6`)."""
        targets = sorted({str(s) for s in submission_ids if s})
        if not targets:
            return []
        placeholders = ",".join("?" for _ in targets)
        with closing(self._connect()) as db:
            rows = db.execute(
                f"""SELECT settlement_id, current_leaf_submission_id
                    FROM fee_settlements
                    WHERE issued_credit_id IS NULL
                      AND (submission_id IN ({placeholders})
                           OR current_leaf_submission_id IN ({placeholders}))
                    ORDER BY settlement_id ASC""",
                (*targets, *targets),
            ).fetchall()
        minted: list[str] = []
        for settlement_id, leaf in rows:
            cid = self.issue_infra_credit_for_settlement(
                int(settlement_id),
                leaf_submission_id=str(leaf),
                reason="version_closed",
            )
            if cid is not None:
                minted.append(cid)
        return minted

    def submission_fee_view(self, submission_id: str, hotkey: str) -> dict[str, object]:
        """Allow-listed fee status of the caller's own ``submission_id`` (`exam_feedback_v14`)."""
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT payment_kind, lifecycle_state, issued_credit_id
                   FROM fee_settlements
                   WHERE (submission_id = ? OR current_leaf_submission_id = ?)
                     AND hotkey = ?
                   ORDER BY settlement_id DESC LIMIT 1""",
                (submission_id, submission_id, hotkey),
            ).fetchone()
        if row is None:
            return {"status": "UNCHARGED", "credit_id": None}
        payment_kind, lifecycle_state, issued_credit_id = row
        if lifecycle_state == "CREDITED_INFRA":
            return {"status": "CREDITED_INFRA", "credit_id": issued_credit_id}
        status = "CHARGED_CREDIT" if payment_kind == "CREDIT" else "CHARGED_BURN"
        return {"status": status, "credit_id": None}

    def public_stats(self) -> dict[str, int]:
        """Operator-facing aggregate counters (not exposed on public `/info`)."""
        with closing(self._connect()) as db:
            burn_row = db.execute(
                """SELECT COUNT(*), COALESCE(SUM(amount_rao), 0), COALESCE(SUM(alpha_burned_rao), 0)
                   FROM fee_burn_claims WHERE state = 'SPENT'"""
            ).fetchone()
            issued = db.execute("SELECT COUNT(*) FROM infra_credits").fetchone()[0]
            redeemed = db.execute(
                "SELECT COUNT(*) FROM infra_credits WHERE state = 'REDEEMED'"
            ).fetchone()[0]
        return {
            "admitted_burns": int(burn_row[0]),
            "burned_tao_rao": int(burn_row[1]),
            "burned_alpha_rao": int(burn_row[2]),
            "credits_issued": int(issued),
            "credits_redeemed": int(redeemed),
        }

    # --- Atomic Admission Claim ------------------------------------------------

    def _finalize_pinned_reservation_if_any(
        self, hotkey: str, submission_id: str
    ) -> bool:
        """If an earlier `commit` failed after admitting `submission_id` (`C4`), finalize it now (`M2`)."""
        stamp = _utc_now()
        with self._guard, closing(self._connect()) as db:
            existing = db.execute(
                """SELECT 1 FROM fee_settlements
                   WHERE hotkey = ?
                     AND (submission_id = ? OR current_leaf_submission_id = ?)""",
                (hotkey, submission_id, submission_id),
            ).fetchone()
            if existing is not None:
                return True
            b_row = db.execute(
                """SELECT netuid, extrinsic_id, reservation_token, challenge_id,
                          challenge_version, policy_version, amount_rao, alpha_burned_rao
                   FROM fee_burn_claims
                   WHERE hotkey = ? AND expected_submission_id = ? AND state = 'RESERVED'
                   LIMIT 1""",
                (hotkey, submission_id),
            ).fetchone()
            c_row = (
                None
                if b_row is not None
                else db.execute(
                    """SELECT credit_id, reservation_token, challenge_id
                       FROM infra_credits
                       WHERE hotkey = ? AND expected_submission_id = ? AND state = 'RESERVED'
                       LIMIT 1""",
                    (hotkey, submission_id),
                ).fetchone()
            )
            if b_row is None and c_row is None:
                return False
            db.execute("BEGIN IMMEDIATE")
            try:
                if b_row is not None:
                    netuid, ext_id, tok, cid, cver, pver, amt, alpha = b_row
                    db.execute(
                        """UPDATE fee_burn_claims
                           SET state = 'SPENT', submission_id = ?
                           WHERE netuid = ? AND extrinsic_id = ?
                             AND reservation_token = ? AND state = 'RESERVED'""",
                        (submission_id, int(netuid), str(ext_id), str(tok)),
                    )
                    db.execute(
                        """INSERT OR IGNORE INTO fee_settlements(
                               submission_id, current_leaf_submission_id, hotkey,
                               challenge_id, challenge_version, policy_version,
                               payment_kind, payment_ref, amount_rao, alpha_burned_rao,
                               lifecycle_state, issued_credit_id, admitted_utc, settled_utc
                           ) VALUES (?, ?, ?, ?, ?, ?, 'BURN', ?, ?, ?, 'ADMITTED', NULL, ?, NULL)""",
                        (
                            submission_id,
                            submission_id,
                            hotkey,
                            str(cid),
                            str(cver),
                            str(pver),
                            str(ext_id),
                            int(amt),
                            int(alpha),
                            stamp,
                        ),
                    )
                elif c_row is not None:
                    cred_id, tok, cid = c_row
                    db.execute(
                        """UPDATE infra_credits
                           SET state = 'REDEEMED', redeemed_submission_id = ?, redeemed_utc = ?
                           WHERE credit_id = ? AND reservation_token = ? AND state = 'RESERVED'""",
                        (submission_id, stamp, str(cred_id), str(tok)),
                    )
                    db.execute(
                        """INSERT OR IGNORE INTO fee_settlements(
                               submission_id, current_leaf_submission_id, hotkey,
                               challenge_id, challenge_version, policy_version,
                               payment_kind, payment_ref, amount_rao, alpha_burned_rao,
                               lifecycle_state, issued_credit_id, admitted_utc, settled_utc
                           ) VALUES (?, ?, ?, ?, '', 'recovered', 'CREDIT', ?, 0, 0, 'ADMITTED', NULL, ?, NULL)""",
                        (
                            submission_id,
                            submission_id,
                            hotkey,
                            str(cid),
                            str(cred_id),
                            stamp,
                        ),
                    )
                db.execute("COMMIT")
                return True
            except Exception:
                db.execute("ROLLBACK")
                raise

    @contextlib.contextmanager
    def claim_for_admission(
        self,
        *,
        policy: FeePolicy,
        payment: dict[str, str],
        hotkey: str,
        receiver: str,
        challenge_id: str,
        challenge_version: str,
        known_finalized_head: int | None,
        indexer=None,
        door_id: str = "",
        expected_submission_id: str | None = None,
    ):
        """Reserve a burn or credit before ``Validator.evaluate``, committing only if
        ``commit(submission_id)`` is called (`H5`, `C4`, `M2`)."""
        if (
            not policy.ready
            or policy.netuid is None
            or policy.amount_rao is None
            or policy.min_block is None
        ):
            raise FeeRefused(FEE_POLICY_UNAVAILABLE, status=503)

        # `M2`: Lost-202 idempotent replay fast-path — if `expected_submission_id` is
        # ALREADY settled (or pinned on an interrupted post-admit reservation) for this
        # hotkey, yield a no-op commit without touching or rejecting `payment`!
        if type(expected_submission_id) is str and expected_submission_id:
            try:
                if self._finalize_pinned_reservation_if_any(
                    hotkey, expected_submission_id
                ):
                    yield lambda _sub_id: None
                    return
            except Exception as exc:
                raise FeeRefused(FEE_VERIFIER_UNAVAILABLE, status=503) from exc

        reservation = self._reserve(
            policy=policy,
            payment=payment,
            hotkey=hotkey,
            receiver=receiver,
            challenge_id=challenge_id,
            challenge_version=challenge_version,
            known_finalized_head=known_finalized_head,
            indexer=indexer,
            door_id=door_id,
            expected_submission_id=expected_submission_id,
        )
        committed = False
        admitted_submission_id: str | None = None

        def commit(submission_id: str) -> None:
            nonlocal committed, admitted_submission_id
            admitted_submission_id = submission_id
            try:
                self._commit_reservation(reservation, submission_id)
                committed = True
            except Exception as exc:
                # `C4`: Evaluation already admitted `submission_id` — pin it on the
                # RESERVED row so recovery / `M2` finalizes SPENT, and map to typed 503
                # (never an unhandled 500 traceback).
                self._pin_admitted_on_reservation(reservation, submission_id)
                raise FeeRefused(FEE_VERIFIER_UNAVAILABLE, status=503) from exc

        try:
            yield commit
        finally:
            if not committed and admitted_submission_id is None:
                self._release_reservation(reservation)

    def _pin_admitted_on_reservation(
        self, reservation: _Reservation, submission_id: str
    ) -> None:
        with (
            contextlib.suppress(Exception),
            self._guard,
            closing(self._connect()) as db,
        ):
            db.execute("BEGIN IMMEDIATE")
            if reservation.payment_kind == "CREDIT":
                db.execute(
                    """UPDATE infra_credits
                       SET expected_submission_id = ?
                       WHERE credit_id = ? AND reservation_token = ?""",
                    (submission_id, reservation.payment_ref, reservation.token),
                )
            else:
                db.execute(
                    """UPDATE fee_burn_claims
                       SET expected_submission_id = ?
                       WHERE netuid = ? AND extrinsic_id = ? AND reservation_token = ?""",
                    (
                        submission_id,
                        reservation.netuid,
                        reservation.payment_ref,
                        reservation.token,
                    ),
                )
            db.execute("COMMIT")

    def _reserve(
        self,
        *,
        policy: FeePolicy,
        payment: dict[str, str],
        hotkey: str,
        receiver: str,
        challenge_id: str,
        challenge_version: str,
        known_finalized_head: int | None,
        indexer=None,
        door_id: str = "",
        expected_submission_id: str | None = None,
    ) -> _Reservation:
        assert policy.netuid is not None
        assert policy.amount_rao is not None
        assert policy.min_block is not None

        token = secrets.token_hex(16)
        stamp = _utc_now()

        if payment["kind"] == "credit":
            credit_id = payment["credit_id"]
            with self._guard, closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    row = db.execute(
                        """SELECT hotkey, challenge_id, state
                           FROM infra_credits WHERE credit_id = ?""",
                        (credit_id,),
                    ).fetchone()
                    if row is None or row[0] != hotkey or row[1] != challenge_id:
                        db.execute("ROLLBACK")
                        raise FeeRefused(FEE_CREDIT_NOT_FOUND, status=400)
                    if row[2] != "AVAILABLE":
                        db.execute("ROLLBACK")
                        raise FeeRefused(FEE_CREDIT_ALREADY_SPENT, status=409)
                    db.execute(
                        """UPDATE infra_credits
                           SET state = 'RESERVED',
                               reservation_token = ?,
                               door_id = ?,
                               expected_submission_id = ?
                           WHERE credit_id = ? AND state = 'AVAILABLE'""",
                        (token, door_id, expected_submission_id, credit_id),
                    )
                    db.execute("COMMIT")
                except FeeRefused:
                    raise
                except Exception as exc:
                    db.execute("ROLLBACK")
                    raise FeeRefused(FEE_VERIFIER_UNAVAILABLE, status=503) from exc
            return _Reservation(
                token=token,
                payment_kind="CREDIT",
                payment_ref=credit_id,
                netuid=policy.netuid,
                hotkey=hotkey,
                challenge_id=challenge_id,
                challenge_version=challenge_version,
                policy_version=policy.policy_version,
                amount_rao=0,
                alpha_burned_rao=0,
                door_id=door_id,
                expected_submission_id=expected_submission_id,
            )

        extrinsic_id = payment["extrinsic_id"]
        parsed = parse_extrinsic_id(extrinsic_id)
        if parsed is None:
            raise FeeRefused(FEE_EXTRINSIC_MALFORMED, status=400)
        block, _ = parsed

        if block < policy.min_block:
            raise FeeRefused(FEE_BEFORE_MIN_BLOCK, status=400)
        if (
            known_finalized_head is not None
            and block > known_finalized_head
            and indexer is None
        ):
            raise FeeRefused(FEE_NOT_FINALIZED, status=409)
        if (
            known_finalized_head is not None
            and known_finalized_head - block > policy.max_lookback_blocks
        ):
            raise FeeRefused(FEE_TOO_OLD, status=400)

        with closing(self._connect()) as db:
            claimed = db.execute(
                "SELECT 1 FROM fee_burn_claims WHERE netuid = ? AND extrinsic_id = ?",
                (policy.netuid, extrinsic_id),
            ).fetchone()
            if claimed is not None:
                raise FeeRefused(FEE_ALREADY_SPENT, status=409)

        if not self.is_block_indexed(block):
            if indexer is None:
                raise FeeRefused(FEE_VERIFIER_UNAVAILABLE, status=503)
            try:
                indexer.ensure_block(
                    block,
                    known_finalized_head=known_finalized_head,
                    min_allowed_block=policy.min_block,
                    max_lookback_blocks=policy.max_lookback_blocks,
                )
            except FeeBurnNotFinalized as exc:
                raise FeeRefused(FEE_NOT_FINALIZED, status=409) from exc
            except FeeBurnUnavailable as exc:
                raise FeeRefused(FEE_VERIFIER_UNAVAILABLE, status=503) from exc

        expected_remark_digest = fee_remark_hash(
            policy.netuid, challenge_id, receiver, hotkey
        )

        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                already = db.execute(
                    "SELECT 1 FROM fee_burn_claims WHERE netuid = ? AND extrinsic_id = ?",
                    (policy.netuid, extrinsic_id),
                ).fetchone()
                if already is not None:
                    db.execute("ROLLBACK")
                    raise FeeRefused(FEE_ALREADY_SPENT, status=409)

                indexed = db.execute(
                    "SELECT 1 FROM fee_indexed_blocks WHERE block = ?",
                    (block,),
                ).fetchone()
                if indexed is None:
                    db.execute("ROLLBACK")
                    raise FeeRefused(FEE_TOO_OLD, status=400)

                burn = db.execute(
                    """SELECT hotkey, amount_rao, alpha_burned_rao, remark_hash
                       FROM observed_burns
                       WHERE netuid = ? AND extrinsic_id = ?""",
                    (policy.netuid, extrinsic_id),
                ).fetchone()
                if burn is None:
                    db.execute("ROLLBACK")
                    raise FeeRefused(FEE_NOT_FOUND, status=400)

                burn_hotkey, amount_rao, alpha_rao, remark_digest = burn
                if burn_hotkey != hotkey:
                    db.execute("ROLLBACK")
                    raise FeeRefused(FEE_HOTKEY_MISMATCH, status=400)
                if remark_digest != expected_remark_digest:
                    db.execute("ROLLBACK")
                    raise FeeRefused(FEE_CHALLENGE_MISMATCH, status=400)
                required_rao = policy.required_amount_at_block(block)
                if int(amount_rao) < required_rao:
                    db.execute("ROLLBACK")
                    raise FeeRefused(
                        FEE_INSUFFICIENT,
                        status=400,
                        extra={
                            "observed_amount_rao": int(amount_rao),
                            "required_amount_rao": required_rao,
                        },
                    )

                db.execute(
                    """INSERT INTO fee_burn_claims(
                           netuid, extrinsic_id, state, reservation_token,
                           door_id, expected_submission_id,
                           hotkey, challenge_id, challenge_version, policy_version,
                           amount_rao, alpha_burned_rao, submission_id, claimed_utc
                       ) VALUES (?, ?, 'RESERVED', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
                    (
                        policy.netuid,
                        extrinsic_id,
                        token,
                        door_id,
                        expected_submission_id,
                        hotkey,
                        challenge_id,
                        challenge_version,
                        policy.policy_version,
                        int(amount_rao),
                        int(alpha_rao),
                        stamp,
                    ),
                )
                db.execute("COMMIT")
            except FeeRefused:
                raise
            except Exception as exc:
                db.execute("ROLLBACK")
                raise FeeRefused(FEE_VERIFIER_UNAVAILABLE, status=503) from exc

        return _Reservation(
            token=token,
            payment_kind="BURN",
            payment_ref=extrinsic_id,
            netuid=policy.netuid,
            hotkey=hotkey,
            challenge_id=challenge_id,
            challenge_version=challenge_version,
            policy_version=policy.policy_version,
            amount_rao=int(amount_rao),
            alpha_burned_rao=int(alpha_rao),
            door_id=door_id,
            expected_submission_id=expected_submission_id,
        )

    def _commit_reservation(
        self, reservation: _Reservation, submission_id: str
    ) -> None:
        stamp = _utc_now()
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    """SELECT 1 FROM fee_settlements
                       WHERE submission_id = ? OR current_leaf_submission_id = ?""",
                    (submission_id, submission_id),
                ).fetchone()
                if existing is not None:
                    self._release_in_tx(db, reservation)
                    db.execute("COMMIT")
                    return

                if reservation.payment_kind == "CREDIT":
                    cur = db.execute(
                        """UPDATE infra_credits
                           SET state = 'REDEEMED',
                               redeemed_submission_id = ?,
                               redeemed_utc = ?
                           WHERE credit_id = ? AND reservation_token = ? AND state = 'RESERVED'""",
                        (
                            submission_id,
                            stamp,
                            reservation.payment_ref,
                            reservation.token,
                        ),
                    )
                else:
                    cur = db.execute(
                        """UPDATE fee_burn_claims
                           SET state = 'SPENT', submission_id = ?
                           WHERE netuid = ? AND extrinsic_id = ?
                             AND reservation_token = ? AND state = 'RESERVED'""",
                        (
                            submission_id,
                            reservation.netuid,
                            reservation.payment_ref,
                            reservation.token,
                        ),
                    )
                if cur.rowcount != 1:
                    raise FeeBurnUnavailable("fee_reservation_lost")

                db.execute(
                    """INSERT INTO fee_settlements(
                           submission_id, current_leaf_submission_id, hotkey,
                           challenge_id, challenge_version, policy_version,
                           payment_kind, payment_ref, amount_rao, alpha_burned_rao,
                           lifecycle_state, issued_credit_id, admitted_utc, settled_utc
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ADMITTED', NULL, ?, NULL)""",
                    (
                        submission_id,
                        submission_id,
                        reservation.hotkey,
                        reservation.challenge_id,
                        reservation.challenge_version,
                        reservation.policy_version,
                        reservation.payment_kind,
                        reservation.payment_ref,
                        reservation.amount_rao,
                        reservation.alpha_burned_rao,
                        stamp,
                    ),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        self._chmod_sidecars()

    def _release_reservation(self, reservation: _Reservation) -> None:
        with self._guard, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._release_in_tx(db, reservation)
                db.execute("COMMIT")
            except Exception:  # noqa: BLE001
                db.execute("ROLLBACK")

    @staticmethod
    def _release_in_tx(db: sqlite3.Connection, reservation: _Reservation) -> None:
        if reservation.payment_kind == "CREDIT":
            db.execute(
                """UPDATE infra_credits
                   SET state = 'AVAILABLE',
                       reservation_token = NULL,
                       door_id = '',
                       expected_submission_id = NULL
                   WHERE credit_id = ? AND reservation_token = ? AND state = 'RESERVED'""",
                (reservation.payment_ref, reservation.token),
            )
        else:
            db.execute(
                """DELETE FROM fee_burn_claims
                   WHERE netuid = ? AND extrinsic_id = ?
                     AND reservation_token = ? AND state = 'RESERVED'""",
                (reservation.netuid, reservation.payment_ref, reservation.token),
            )


def _auto_retry_proven_sets() -> tuple[frozenset[str], tuple[str, ...]]:
    try:
        from carbon.challenge_validator import auto_retry

        codes = (
            PROVEN_CARBON_GRADE_CODES
            | frozenset(getattr(auto_retry, "_VERSION_WIDE_CLASSES", ()))
            | frozenset(getattr(auto_retry, "_GAP_CODES", ()))
            | frozenset(getattr(auto_retry, "_PER_TASK_CODES", ()))
        )
        prefixes = tuple(
            dict.fromkeys(
                (
                    *PROVEN_CARBON_GRADE_PREFIXES,
                    *getattr(auto_retry, "_VERSION_WIDE_PREFIXES", ()),
                )
            )
        )
        return codes, prefixes
    except Exception:  # noqa: BLE001
        return PROVEN_CARBON_GRADE_CODES, PROVEN_CARBON_GRADE_PREFIXES


def _classify_failed_grade_marker(
    marker: dict, *, failure_path: Path | None = None
) -> str:
    """Classify a `state == 'FAILED'` grade marker as `'PENDING'`, `'CREDIT'`, or `'CONSUMED'` (`B4`, `C2`, `C3`, `C7`)."""
    has_next_step = "next_step" in marker
    next_step = marker.get("next_step")
    if next_step == "retry_scheduled":
        return "PENDING"
    # `C7`: when `AutoGrader` records `next_step: None` (e.g. a `COUNTED` slot that
    # could not be proven undelivered), hold `PENDING` until operator `release` or `regrade`!
    if has_next_step and next_step is None:
        return "PENDING"

    raw_code = str(marker.get("code") or "")
    if not raw_code or raw_code.startswith("nonfinite_output"):
        return "CONSUMED"
    base_code = raw_code.split(":", 1)[0]
    if base_code in MINER_OR_AMBIGUOUS_GRADE_CODES:
        return "CONSUMED"

    if base_code == "MinerProgramFailure":
        # Only a contended wall stop proven by `infra_requeue._carbons_failure` is Carbon's (`C3`).
        if failure_path is None or not failure_path.is_file():
            return "CONSUMED"
        with contextlib.suppress(Exception):
            from carbon.challenge_validator.infra_requeue import _carbons_failure

            if _carbons_failure(raw_code, failure_path):
                is_proven = True
            else:
                return "CONSUMED"
        if not locals().get("is_proven", False):
            return "CONSUMED"
    else:
        proven_codes, proven_prefixes = _auto_retry_proven_sets()
        is_proven = (
            raw_code in proven_codes
            or base_code in proven_codes
            or raw_code.startswith(proven_prefixes)
            or base_code.startswith(proven_prefixes)
        )
    if not is_proven:
        return "CONSUMED"

    if has_next_step and next_step not in (
        "slot_returned",
        "resubmit_after_fix",
        "resubmit_program_changed",
    ):
        return "CONSUMED"
    return "CREDIT"


def _miner_withdrew_task(adapter, projected: object, submission_id: str) -> bool:
    """Return True if ``submission_id`` was withdrawn by its miner (`H8`, `A2`)."""
    if isinstance(projected, dict):
        failure = projected.get("failure")
        if isinstance(failure, dict) and failure.get("code") == "withdrawn_by_miner":
            return True
    ledger_obj = getattr(adapter, "ledger", None)
    check_fn = getattr(ledger_obj, "miner_withdrawal", None)
    if callable(check_fn):
        with contextlib.suppress(Exception):
            if check_fn(adapter.contract_digest, submission_id) is not None:
                return True
    return False


def _requeue_dir_for_adapter(adapter) -> Path | None:
    ledger_path = getattr(getattr(adapter, "ledger", None), "path", None)
    if ledger_path is None:
        return None
    return Path(ledger_path).parent / "auto-grade" / "requeued"


def _failures_dir_for_adapter(adapter) -> Path | None:
    ledger_path = getattr(getattr(adapter, "ledger", None), "path", None)
    if ledger_path is None:
        return None
    return Path(ledger_path).parent / "auto-grade" / "failures"


def _operator_credited_tasks(requeue_dir: Path | None) -> frozenset[str]:
    """Mtime-cached task IDs released via `infra_requeue release` (`releases.jsonl`)
    or reclassed via `infra_requeue reclass` (`reclass-kept/*.json`) (`C2`, zero DB lock).
    """
    if requeue_dir is None:
        return frozenset()
    key = str(requeue_dir)
    released: frozenset[str] = frozenset()
    reclassed: frozenset[str] = frozenset()

    releases_path = requeue_dir / "releases.jsonl"
    try:
        st_rel = releases_path.lstat()
        sig_rel = (st_rel.st_mtime_ns, st_rel.st_size)
    except OSError:
        sig_rel = None
    if sig_rel is not None:
        with _OPERATOR_CACHE_GUARD:
            cached_rel = _RELEASES_CACHE.get(key)
        if cached_rel is not None and cached_rel[0] == sig_rel:
            released = cached_rel[1]
        else:
            found_rel: set[str] = set()
            with contextlib.suppress(OSError):
                for raw in releases_path.read_text(encoding="utf-8").splitlines():
                    if not raw.strip():
                        continue
                    with contextlib.suppress(ValueError):
                        rec = json.loads(raw)
                        if (
                            type(rec) is dict
                            and rec.get("state") == "RELEASED"
                            and rec.get("status") == "FAILED_INFRA"
                            and type(rec.get("task")) is str
                        ):
                            found_rel.add(rec["task"])
            released = frozenset(found_rel)
            with _OPERATOR_CACHE_GUARD:
                _RELEASES_CACHE[key] = (sig_rel, released)

    reclass_dir = requeue_dir / "reclass-kept"
    try:
        st_rc = reclass_dir.lstat()
        mtime_rc = st_rc.st_mtime_ns if stat.S_ISDIR(st_rc.st_mode) else None
    except OSError:
        mtime_rc = None
    if mtime_rc is not None:
        with _OPERATOR_CACHE_GUARD:
            cached_rc = _RECLASS_CACHE.get(key)
        if cached_rc is not None and cached_rc[0] == mtime_rc:
            reclassed = cached_rc[1]
        else:
            found_rc: set[str] = set()
            with contextlib.suppress(OSError):
                for p in reclass_dir.glob("*.json"):
                    if p.stem:
                        found_rc.add(p.stem)
            reclassed = frozenset(found_rc)
            with _OPERATOR_CACHE_GUARD:
                _RECLASS_CACHE[key] = (mtime_rc, reclassed)

    return released | reclassed


def _owed_rerun_tasks(requeue_dir: Path | None) -> frozenset[str]:
    """Mtime-cached task IDs currently placed on `auto-retry-alerts.jsonl` with
    `reason == 'owed_list'` (`C7` mutual exclusion: hold off automatic credit while
    awaiting an owed-list rerun unless explicitly settled via `credit-settlement`)."""
    if requeue_dir is None:
        return frozenset()
    from carbon.challenge_validator.lean_recipe import BUILD_ALERTS

    alerts_path = requeue_dir / BUILD_ALERTS
    try:
        st_al = alerts_path.lstat()
        sig_al = (st_al.st_mtime_ns, st_al.st_size)
    except OSError:
        return frozenset()
    key = str(requeue_dir)
    with _OPERATOR_CACHE_GUARD:
        cached = _OWED_ALERTS_CACHE.get(key)
    if cached is not None and cached[0] == sig_al:
        return cached[1]
    found: set[str] = set()
    with contextlib.suppress(OSError):
        for raw in alerts_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            with contextlib.suppress(ValueError):
                rec = json.loads(raw)
                if (
                    type(rec) is dict
                    and rec.get("reason") == "owed_list"
                    and type(rec.get("task")) is str
                ):
                    found.add(rec["task"])
    result = frozenset(found)
    with _OPERATOR_CACHE_GUARD:
        _OWED_ALERTS_CACHE[key] = (sig_al, result)
    return result


def _build_requeue_still_settling(adapter, hotkey: str, leaf: str) -> bool:
    """Guard against racing `LeanRecipeAdapter._requeue_failed_build` (`H7`, `C1`).

    Imports the exact hyphenated filenames (`REBUILD_APPLIED`, `REBUILD_REQUESTS`,
    `STOP_CANCELLED`) from `lean_recipe` (`C1`). Even when `leaf` is in
    `_requeue_settled`, an unapplied `rebuild-requests.jsonl` or `stop-cancelled.jsonl`
    entry keeps the settlement pending until applied!
    """
    from carbon.challenge_validator.lean_recipe import (
        REBUILD_APPLIED,
        REBUILD_REQUESTS,
        REQUEUE_ASK_SECONDS,
        STOP_CANCELLED,
    )

    requeue_dir = _requeue_dir_for_adapter(adapter)
    if requeue_dir is not None and requeue_dir.is_dir():
        with contextlib.suppress(Exception):
            applied_file = requeue_dir / REBUILD_APPLIED
            applied = (
                {
                    line.get("task")
                    for line in (
                        json.loads(raw)
                        for raw in applied_file.read_text(encoding="utf-8").splitlines()
                        if raw.strip()
                    )
                    if type(line) is dict
                }
                if applied_file.is_file()
                else set()
            )
            for req_name in (REBUILD_REQUESTS, STOP_CANCELLED):
                req_file = requeue_dir / req_name
                if req_file.is_file():
                    for raw in req_file.read_text(encoding="utf-8").splitlines():
                        if not raw.strip():
                            continue
                        rec = json.loads(raw)
                        if (
                            type(rec) is dict
                            and rec.get("task") == leaf
                            and leaf not in applied
                        ):
                            return True

    if not hasattr(adapter, "_requeue_failed_build"):
        return False
    settled = getattr(adapter, "_requeue_settled", set())
    if leaf in settled:
        return False
    with contextlib.suppress(Exception):
        from carbon.research import DirectGetTaskRequestV3

        provider = adapter._provider(hotkey)
        task = provider.get_research_result(
            DirectGetTaskRequestV3(adapter.discovery.info.challenge_key, leaf)
        ).task
        completed_us = getattr(
            getattr(task, "terminal_receipt", None), "completed_at_micros", None
        )
        if type(completed_us) is int:
            age_s = time.time() - (completed_us / 1e6)
            if age_s >= REQUEUE_ASK_SECONDS:
                return False
    return True


def reconcile_hotkey_credits(intake, hotkey: str) -> list[str]:
    """Follow rerun chains for ``hotkey``'s paid admissions and mint credits ONLY
    for proven Carbon-side `FAILED_INFRA` (`CARBON_CLASSES` / verified grade codes,
    mutually exclusive with owed-list reruns) or `VERSION_CLOSED`."""
    ledger: FeeLedger | None = getattr(intake, "fee_ledger", None)
    if ledger is None:
        return []

    minted: list[str] = []
    adapter = getattr(intake, "adapter", None)
    grade_marker = getattr(intake, "grade_marker", None)
    version_closed = getattr(intake, "version_closed", None) or {}
    intake_cid = getattr(getattr(intake, "challenge", None), "challenge_id", None)
    intake_cver = getattr(getattr(intake, "challenge", None), "version", None)

    requeue_dir = _requeue_dir_for_adapter(adapter) if adapter is not None else None
    failures_dir = _failures_dir_for_adapter(adapter) if adapter is not None else None
    operator_tasks = _operator_credited_tasks(requeue_dir)
    owed_tasks = _owed_rerun_tasks(requeue_dir)

    candidates = ledger.open_settlements(hotkey)
    if operator_tasks:
        seen_ids = {int(r["settlement_id"]) for r in candidates}
        for extra in ledger.open_settlements_for_tasks(hotkey, operator_tasks):
            if int(extra["settlement_id"]) not in seen_ids:
                candidates.append(extra)

    for row in candidates:
        settlement_id = int(row["settlement_id"])
        leaf = str(row["current_leaf_submission_id"])
        state_now = str(row["lifecycle_state"])
        row_cid = str(row["challenge_id"])
        row_cver = str(row["challenge_version"])

        same_door = intake_cid is None or (
            row_cid == intake_cid and (not row_cver or row_cver == intake_cver)
        )
        if same_door and adapter is not None and hasattr(adapter, "ledger"):
            for _ in range(16):
                try:
                    nxt = adapter.ledger.requeued_as(
                        adapter.contract_digest, leaf, hotkey
                    )
                except Exception:  # noqa: BLE001
                    nxt = None
                if nxt is None or nxt == leaf:
                    break
                leaf = str(nxt)
                ledger.advance_settlement_leaf(settlement_id, leaf)

        # 1. Cross-version `version-closed.json` (`B6`).
        if (
            version_closed.get(leaf) == hotkey
            or version_closed.get(str(row["submission_id"])) == hotkey
        ):
            cid = ledger.issue_infra_credit_for_settlement(
                settlement_id, leaf_submission_id=leaf, reason="version_closed"
            )
            if cid is not None:
                minted.append(cid)
            continue

        if not same_door:
            continue

        # 2. Operator `releases.jsonl` (`infra_requeue release`) on `leaf` (`C2`).
        released_by_operator = (
            leaf in operator_tasks
            and requeue_dir is not None
            and (requeue_dir / "releases.jsonl").is_file()
            and leaf in _operator_credited_tasks(requeue_dir)
        )

        marker = None
        if callable(grade_marker):
            try:
                marker = grade_marker(leaf)
            except Exception:  # noqa: BLE001
                marker = None

        if isinstance(marker, dict):
            m_state = marker.get("state")
            if m_state == "VERSION_CLOSED":
                cid = ledger.issue_infra_credit_for_settlement(
                    settlement_id, leaf_submission_id=leaf, reason="version_closed"
                )
                if cid is not None:
                    minted.append(cid)
                continue
            if m_state == "FAILED":
                # Check if `releases.jsonl` explicitly released an undelivered COUNTED slot (`C2`).
                if (
                    marker.get("next_step") is None
                    and released_by_operator
                    and _classify_failed_grade_marker(
                        {**marker, "next_step": "slot_returned"},
                        failure_path=(
                            None
                            if failures_dir is None
                            else failures_dir / f"{leaf}.txt"
                        ),
                    )
                    == "CREDIT"
                ):
                    cid = ledger.issue_infra_credit_for_settlement(
                        settlement_id,
                        leaf_submission_id=leaf,
                        reason="operator_released_infra",
                    )
                    if cid is not None:
                        minted.append(cid)
                    continue

                verdict = _classify_failed_grade_marker(
                    marker,
                    failure_path=(
                        None if failures_dir is None else failures_dir / f"{leaf}.txt"
                    ),
                )
                if verdict == "PENDING":
                    continue
                if verdict == "CREDIT":
                    # `C7`: hold `ADMITTED` if task is on the owed-list awaiting operator rerun!
                    if leaf in owed_tasks:
                        continue
                    cid = ledger.issue_infra_credit_for_settlement(
                        settlement_id,
                        leaf_submission_id=leaf,
                        reason="grade_failed_infra",
                    )
                    if cid is not None:
                        minted.append(cid)
                    continue
                if state_now == "ADMITTED":
                    ledger.mark_settlement_consumed(settlement_id)
                continue
            if m_state in (
                "GRADED",
                "CANDIDATE_FAILED",
                "DUPLICATE",
                "WITHDRAWN_BY_MINER",
            ):
                if state_now == "ADMITTED":
                    ledger.mark_settlement_consumed(settlement_id)
                continue

        if state_now == "CONSUMED_TERMINAL":
            continue

        if adapter is not None:
            try:
                projected = adapter.outcome(leaf)
            except Exception:  # noqa: BLE001
                projected = {}
            if _miner_withdrew_task(adapter, projected, leaf):
                ledger.mark_settlement_consumed(settlement_id)
                continue
            p_state = projected.get("state") if isinstance(projected, dict) else None
            if p_state == "FAILED_INFRA":
                if _build_requeue_still_settling(adapter, hotkey, leaf):
                    continue
                if leaf in owed_tasks:
                    continue
                # `C6` / `A3`: require proven `CARBON_CLASSES` (exclude `carbon_unclassified`).
                if callable(getattr(adapter, "failure_class", None)):
                    from carbon.development_session import infra_diagnosis

                    fclass = adapter.failure_class(leaf)
                    if fclass not in infra_diagnosis.CARBON_CLASSES:
                        ledger.mark_settlement_consumed(settlement_id)
                        continue
                cid = ledger.issue_infra_credit_for_settlement(
                    settlement_id, leaf_submission_id=leaf, reason="build_failed_infra"
                )
                if cid is not None:
                    minted.append(cid)
            elif p_state == "RECONSTRUCTION_FAILED":
                ledger.mark_settlement_consumed(settlement_id)

    return minted


def door_identifier(intake) -> str:
    cid = getattr(getattr(intake, "challenge", None), "challenge_id", "")
    ver = getattr(getattr(intake, "challenge", None), "version", "")
    ledger_path = getattr(
        getattr(getattr(intake, "adapter", None), "ledger", None), "path", ""
    )
    return f"{cid}:{ver}:{ledger_path}"


def is_outcome_admitted_in_attempt_ledger(
    attempt_ledger, contract_digest: str, submission_id: str
) -> bool | None:
    """Three-state `AttemptLedger` admission check (`C4`):
    - Checks `attempts` for `kind = 'OUTCOME'` ONLY (never `recipe_task_intents`!).
    - Returns `None` on empty `submission_id` or any DB/read failure so recovery
      keeps `RESERVED` fail-closed instead of deleting!
    """
    if (
        attempt_ledger is None
        or type(contract_digest) is not str
        or not contract_digest
        or type(submission_id) is not str
        or not submission_id
    ):
        return None
    try:
        from carbon.challenge_validator.ledger import read_snapshot

        with read_snapshot(attempt_ledger) as db:
            row = db.execute(
                """SELECT 1 FROM attempts
                   WHERE kind = 'OUTCOME'
                     AND contract_digest = ?
                     AND submission_id = ?
                   LIMIT 1""",
                (contract_digest, submission_id),
            ).fetchone()
        return row is not None
    except Exception:  # noqa: BLE001
        return None


def predict_submission_id(intake, submitted) -> str | None:
    """Compute the deterministic `task_id` `LeanRecipeAdapter` will assign to
    ``submitted`` so crash recovery (`H5`, `C4`) and lost-202 replay (`M2`) match."""
    with contextlib.suppress(Exception):
        from carbon.challenge_validator.lean_recipe import MAX_INFRA_RERUNS
        from carbon.challenge_validator.strict_json import parse_strategy

        adapter, _ = intake.door._adapter_for(submitted.contract_digest)
        if adapter is None:
            return None
        strategy = parse_strategy(
            submitted.strategy_json, max_bytes=adapter.max_strategy_bytes
        )
        recipe = adapter.validate_strategy(strategy)
        provider = adapter._provider(submitted.hotkey)
        for rerun in range(MAX_INFRA_RERUNS + 1):
            req = adapter._request(
                submitted.hotkey,
                recipe,
                evaluation_pack_digest=provider.evaluation_pack_digest,
                rerun=rerun,
            )
            tid = provider._task_id(req)
            if not adapter._ended_on_infra(submitted.hotkey, tid, provider):
                return str(tid.value)
    return None


def dry_preflight_submission(intake, submitted) -> dict[str, object] | None:
    """Side-effect-free pre-build admission check for ``construction_preflight`` (`B3`, `H13`).

    Mirrors `Validator.screen` (`dispatch.py:323-363`), `LeanRecipeAdapter` pre-build
    checks, AND `DirectTaskProvider.start_research_task` pre-task checks (`_bindings`,
    `measure_query` interface dtype, `_at_task_bound`, `_verify_images`, image/source
    envelope checks, `H13`) without recording any `AttemptLedger` row or task!
    """
    from carbon.challenge_validator import crown_average
    from carbon.challenge_validator.dispatch import (
        RECIPE_SCREEN_REFUSALS,
        _result,
        _well_formed,
    )
    from carbon.challenge_validator.interface import Unavailable, is_digest
    from carbon.challenge_validator.lean_recipe import MAX_INFRA_RERUNS
    from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy
    from carbon.development_session.construction_recipe import (
        RecipeRefused,
        graph_envelope_from_workspace,
    )

    if not _well_formed(submitted):
        return _result("REFUSED", code="malformed_submission")
    if not is_digest(submitted.contract_digest):
        return _result("REFUSED", code="contract_digest_malformed")
    adapter, refused = intake.door._adapter_for(submitted.contract_digest)
    if adapter is None:
        return _result("REFUSED", code=refused)
    if (submitted.challenge_id, submitted.challenge_version) != (
        adapter.challenge_id,
        adapter.challenge_version,
    ):
        return _result("REFUSED", code="challenge_mismatch", adapter=adapter)

    try:
        strategy = parse_strategy(
            submitted.strategy_json, max_bytes=adapter.max_strategy_bytes
        )
    except MalformedStrategy as malformed:
        return _result("REFUSED", code=malformed.code, adapter=adapter)
    except Exception as malformed:  # noqa: BLE001
        code = getattr(malformed, "code", "strategy_not_json")
        return _result("REFUSED", code=code, adapter=adapter)

    if adapter.strategy_schema is None:
        named_challenge = strategy.get("challenge_id")
        named_version = adapter.challenge_version
        schema_matches = strategy.get("schema") != "carbon.construction-recipe.v1"
    else:
        named = strategy.get("challenge")
        named_challenge = named.get("id") if type(named) is dict else None
        named_version = named.get("version") if type(named) is dict else None
        schema_matches = strategy.get("schema") == adapter.strategy_schema
    if (
        not schema_matches
        or named_challenge != adapter.challenge_id
        or named_version != adapter.challenge_version
    ):
        return _result("REFUSED", code="challenge_mismatch", adapter=adapter)

    try:
        recipe = adapter.validate_strategy(strategy)
    except ValueError as rejected:
        code = getattr(rejected, "code", None)
        return _result(
            "REFUSED",
            code=code if code in RECIPE_SCREEN_REFUSALS else "malformed_submission",
            adapter=adapter,
        )

    try:
        adapter.require_registered_pool()
        if submitted.hotkey == crown_average.HOST_OWNER:
            raise Unavailable("direct_owner_reserved")
        provider = adapter._provider(submitted.hotkey)
        for rerun in range(MAX_INFRA_RERUNS + 1):
            request = adapter._request(
                submitted.hotkey,
                recipe,
                evaluation_pack_digest=provider.evaluation_pack_digest,
                rerun=rerun,
            )
            task_id = provider._task_id(request)
            if adapter._already_graded(submitted.hotkey, task_id.value, provider):
                return _result(
                    "REFUSED",
                    code="same_recipe_already_submitted",
                    adapter=adapter,
                    outcome=adapter.outcome(task_id.value),
                )
            if not adapter._ended_on_infra(submitted.hotkey, task_id, provider):
                break
        else:
            raise Unavailable("direct_infra_rerun_limit_reached")

        from .interface import Submission as _Sub

        bound_sub = _Sub(
            hotkey=submitted.hotkey,
            receipt=submitted.receipt,
            challenge_id=submitted.challenge_id,
            challenge_version=submitted.challenge_version,
            strategy_json=submitted.strategy_json,
            contract_digest=submitted.contract_digest,
        )
        adapter._refuse_spent_round(bound_sub, task_id.value, provider)
        with adapter._coldkey_place(submitted.hotkey, task_id.value):
            source = recipe.to_dict()["source"]
            raw_graph_envelope = None
            if source["kind"] == "graph":
                try:
                    raw_graph_envelope = graph_envelope_from_workspace(
                        provider.ledger, provider.owner, recipe
                    )
                except RecipeRefused as refused_rec:
                    raise Unavailable(refused_rec.code) from None

            # Mirror `DirectTaskProvider.start_research_task` pre-task checks (`H13`)
            # when running against a real `DirectTaskProvider`.
            if callable(getattr(provider, "_bindings", None)):
                from carbon.development_session.gpu_practice import DirectParentRefused
                from carbon.reconstruction.worker.model import WorkerFailure
                from carbon.research.errors import ResearchServiceErrorCode
                from carbon.research.lifecycle import ResearchTaskProviderError

                try:
                    provider._bindings(request)
                    if getattr(adapter, "_measure_query", False):
                        from carbon.challenge_kit.interface_dtype import output_dtype

                        try:
                            declared = output_dtype(
                                provider.discovery._material.get(
                                    "interface_document", {}
                                )
                            )
                        except ValueError:
                            declared = None
                        if type(declared) is not str or not declared:
                            raise ResearchTaskProviderError(
                                ResearchServiceErrorCode.REFERENCE_MISMATCH
                            )
                    prior = getattr(provider, "_idempotency", {}).get(
                        request.idempotency_key
                    )
                    if prior is None:
                        if (
                            callable(getattr(provider, "_at_task_bound", None))
                            and provider._at_task_bound()
                        ):
                            raise ResearchTaskProviderError(
                                ResearchServiceErrorCode.BOUND_EXCEEDED
                            )
                        try:
                            provider._verify_images()
                            staged_source = (
                                getattr(provider, "image_resolver", None) is not None
                                and callable(
                                    getattr(
                                        provider.image_resolver, "inspect_source", None
                                    )
                                )
                                and callable(
                                    getattr(
                                        provider.image_resolver,
                                        "provision_admitted",
                                        None,
                                    )
                                )
                                and source["kind"] == "bundle"
                            )
                            if staged_source:
                                provider._inspected_source_binding(request)
                            else:
                                provider._resolved_image(request)
                            if (
                                source["kind"] == "graph"
                                and raw_graph_envelope is not None
                            ):
                                from carbon.development_session.direct_graph_construction_worker import (
                                    _checked_envelope,
                                )

                                _checked_envelope(recipe, raw_graph_envelope)
                        except DirectParentRefused as refused_parent:
                            raise ResearchTaskProviderError(
                                ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
                                if refused_parent.code == "backend_not_served"
                                else ResearchServiceErrorCode.REFERENCE_MISMATCH
                            ) from None
                        except FileNotFoundError:
                            raise ResearchTaskProviderError(
                                ResearchServiceErrorCode.REFERENCE_NOT_FOUND
                            ) from None
                        except ValueError:
                            raise ResearchTaskProviderError(
                                ResearchServiceErrorCode.REFERENCE_MISMATCH
                            ) from None
                        except (OSError, WorkerFailure):
                            raise ResearchTaskProviderError(
                                ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
                            ) from None
                except ResearchTaskProviderError as prov_err:
                    if prov_err.code in (
                        ResearchServiceErrorCode.REFERENCE_NOT_FOUND,
                        ResearchServiceErrorCode.REFERENCE_MISMATCH,
                        ResearchServiceErrorCode.BOUND_EXCEEDED,
                    ):
                        raise Unavailable(
                            "direct_" + prov_err.code.value.lower()
                        ) from None
                    raise Unavailable("direct_provider_unavailable") from None
    except Unavailable as unavailable:
        return _result(
            "UNAVAILABLE",
            code=unavailable.code,
            adapter=adapter,
            retry=getattr(unavailable, "retry", None),
        )
    except Exception as fault:  # noqa: BLE001
        code = getattr(fault, "code", "construction_recipe_malformed")
        return _result("REFUSED", code=code, adapter=adapter)

    return None


def preflight_reply(
    *,
    policy: FeePolicy,
    ledger: FeeLedger,
    challenge_id: str,
    receiver: str,
    hotkey: str,
    known_finalized_head: int | None = None,
    predicted_submission_id: str | None = None,
    indexer=None,
) -> dict[str, object]:
    assert policy.netuid is not None
    if indexer is not None and callable(getattr(indexer, "ensure_running", None)):
        with contextlib.suppress(Exception):
            indexer.ensure_running()

    already_paid = ledger.settled_payment_for_submission(
        hotkey, predicted_submission_id
    )
    credit_id = ledger.available_credit(hotkey, challenge_id)
    unspent = ledger.unspent_burns_for_hotkey(
        netuid=policy.netuid,
        challenge_id=challenge_id,
        receiver=receiver,
        hotkey=hotkey,
        min_block=policy.min_block or 0,
        known_finalized_head=known_finalized_head,
        policy=policy,
    )
    # `M2`: if this exact `predicted_submission_id` was ALREADY paid before a lost 202,
    # surface its original payment reference so an idempotent retry never burns again!
    if already_paid is not None:
        paid_kind, paid_ref = already_paid
        if paid_kind == "CREDIT" and credit_id is None:
            credit_id = paid_ref
        elif paid_kind == "BURN" and paid_ref not in unspent:
            unspent = [paid_ref, *unspent]

    remark_str = fee_remark(policy.netuid, challenge_id, receiver, hotkey).decode(
        "ascii"
    )
    remark_digest = fee_remark_hash(policy.netuid, challenge_id, receiver, hotkey)
    if credit_id is not None:
        fee_status = "CREDIT_AVAILABLE"
    elif unspent:
        fee_status = "UNSPENT_BURN_AVAILABLE"
    else:
        fee_status = "BURN_REQUIRED"
    return {
        "schema": PREFLIGHT_REPLY_SCHEMA,
        "admissible": True,
        "fee_status": fee_status,
        "credit_id": credit_id,
        "unspent_extrinsics": unspent,
        "fee": policy.facts(challenge_id, receiver=receiver),
        "remark": remark_str,
        "remark_hash": remark_digest,
    }


def _armed_flag_path(policy_path: Path) -> Path:
    return policy_path.parent / ARMED_FLAG_NAME


def _write_armed_flag(policy_path: Path) -> None:
    flag = _armed_flag_path(policy_path)
    flag.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not flag.exists():
        fd = os.open(flag, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, (_utc_now() + "\n").encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)


def _clear_armed_flag(policy_path: Path) -> None:
    flag = _armed_flag_path(policy_path)
    with contextlib.suppress(FileNotFoundError):
        flag.unlink()


def _is_armed_on_disk(policy_path: Path) -> bool:
    flag = _armed_flag_path(policy_path)
    try:
        flag.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        # `EACCES` on the armed flag fails closed (`True`).
        return True


class LiveFeePolicySource:
    """Zero-restart stat-cached policy watcher in validator host state (`B2`, `H3`, `C5`)."""

    def __init__(
        self,
        intake,
        *,
        challenge_id: str,
        version: str,
        expected_netuid: int,
        expected_genesis_hash: str | None = None,
        ledger_path: Path,
        path: Path | str,
        indexer_factory=None,
        log_fn=None,
        refresh_interval_s: float = 1.0,
    ) -> None:
        self._intake = intake
        self.challenge_id = challenge_id
        self.version = version
        self.expected_netuid = expected_netuid
        self.expected_genesis_hash = expected_genesis_hash
        self.ledger_path = Path(ledger_path)
        self.path = Path(path)
        self._indexer_factory = indexer_factory
        self._log_fn = log_fn
        self.refresh_interval_s = max(0.0, float(refresh_interval_s))
        self._lock = threading.Lock()
        self._last_check_mono = -1e9
        self._last_sig: object = ("__init__",)
        self._cached: FeePolicy | None = None
        self._ever_ready = False
        self._door_recovered = False
        self._lease_cm = None
        self.current(force=True)

    def _emit_log(self, event: str, **fields: object) -> None:
        if callable(self._log_fn):
            with contextlib.suppress(Exception):
                self._log_fn(event, **fields)

    def _acquire_door_lease(self, door_id: str) -> None:
        """Hold a non-blocking OS file lease per `door_id` (`C5`) so overlapping
        process restarts can NEVER run `recover_door_reservations` concurrently!"""
        if self._lease_cm is not None:
            return
        digest = hashlib.sha256(door_id.encode("utf-8")).hexdigest()[:24]
        lease_path = self.ledger_path.parent / f".door-lease-{digest}.lock"
        cm = exclusive_file_lock(lease_path, blocking=False)
        try:
            cm.__enter__()
        except BlockingIOError as exc:
            raise FeeBurnUnavailable("fee_door_lease_held_by_another_process") from exc
        self._lease_cm = cm

    def close(self) -> None:
        with self._lock:
            indexer = getattr(self._intake, "fee_indexer", None)
            if indexer is not None and callable(getattr(indexer, "stop", None)):
                with contextlib.suppress(Exception):
                    indexer.stop()
            cm, self._lease_cm = self._lease_cm, None
            if cm is not None:
                with contextlib.suppress(Exception):
                    cm.__exit__(None, None, None)

    def _is_submission_admitted(self, submission_id: str) -> bool | None:
        adapter = getattr(self._intake, "adapter", None)
        if adapter is None or not hasattr(adapter, "ledger"):
            return None
        return is_outcome_admitted_in_attempt_ledger(
            adapter.ledger, adapter.contract_digest, submission_id
        )

    def current(self, *, force: bool = False) -> FeePolicy | None:
        now = time.monotonic()
        if not force and (now - self._last_check_mono) < self.refresh_interval_s:
            return self._cached
        with self._lock:
            now = time.monotonic()
            if not force and (now - self._last_check_mono) < self.refresh_interval_s:
                return self._cached
            self._last_check_mono = now

            indexer_now = getattr(self._intake, "fee_indexer", None)
            if indexer_now is not None and callable(
                getattr(indexer_now, "ensure_running", None)
            ):
                with contextlib.suppress(Exception):
                    indexer_now.ensure_running()

            try:
                st = self.path.lstat()
                sig: object = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
            except FileNotFoundError:
                sig = None
            except OSError:
                # `H3`: `PermissionError` (`EACCES`) or broken path MUST fail closed (`503`)!
                sig = ("__unreadable__",)

            if sig != self._last_sig or force:
                prev_summary = (
                    None
                    if self._cached is None
                    else (
                        self._cached.policy_version,
                        self._cached.amount_rao,
                        self._cached.ready,
                    )
                )
                if sig == ("__unreadable__",):
                    loaded: FeePolicy | None = FeePolicy(
                        UNREADABLE_POLICY, None, None, None
                    )
                elif sig is None:
                    if (
                        is_inside_repo(self.path)
                        or self._ever_ready
                        or _is_armed_on_disk(self.path)
                    ):
                        # `H3`: Fail closed (`503`) across restarts if an armed policy disappears!
                        loaded = FeePolicy(UNREADABLE_POLICY, None, None, None)
                    else:
                        loaded = None
                else:
                    loaded = for_door(
                        self.challenge_id,
                        self.version,
                        expected_netuid=self.expected_netuid,
                        path=self.path,
                    )
                    if loaded is None:
                        self._ever_ready = False

                if loaded is not None and loaded.ready:
                    try:
                        if getattr(self._intake, "fee_ledger", None) is None:
                            self._intake.fee_ledger = FeeLedger(
                                self.ledger_path,
                                expected_netuid=self.expected_netuid,
                                expected_genesis_hash=self.expected_genesis_hash,
                                receiver_hotkey=getattr(self._intake, "receiver", None),
                            )
                        self._intake.fee_ledger.register_lookback(
                            loaded.max_lookback_blocks
                        )
                        if not self._door_recovered:
                            d_id = door_identifier(self._intake)
                            self._acquire_door_lease(d_id)
                            self._intake.fee_ledger.recover_door_reservations(
                                d_id,
                                self._is_submission_admitted,
                                log_fn=self._emit_log,
                            )
                            self._door_recovered = True
                        if getattr(self._intake, "fee_indexer", None) is None:
                            if self._indexer_factory is not None:
                                self._intake.fee_indexer = self._indexer_factory(
                                    self._intake.fee_ledger,
                                    loaded.max_lookback_blocks,
                                )
                        else:
                            upd = getattr(
                                self._intake.fee_indexer, "update_lookback", None
                            )
                            if callable(upd):
                                upd(loaded.max_lookback_blocks)
                        with contextlib.suppress(OSError):
                            _write_armed_flag(self.path)
                        self._ever_ready = True
                        self._last_sig = sig
                    except Exception as exc:  # noqa: BLE001
                        loaded = FeePolicy(UNREADABLE_POLICY, None, None, None)
                        self._last_sig = ("__retry__",)
                        self._emit_log(
                            "submission_fee_init_failed",
                            error=f"{type(exc).__name__}:{exc}",
                        )
                else:
                    self._last_sig = (
                        ("__unreadable_retry__",) if sig == ("__unreadable__",) else sig
                    )

                self._cached = loaded
                self._intake.submission_fee = loaded
                new_summary = (
                    None
                    if loaded is None
                    else (loaded.policy_version, loaded.amount_rao, loaded.ready)
                )
                if new_summary != prev_summary:
                    self._emit_log(
                        "submission_fee_policy_changed",
                        policy=None if loaded is None else loaded.policy_version,
                        amount_rao=None if loaded is None else loaded.amount_rao,
                        ready=False if loaded is None else loaded.ready,
                    )
            return self._cached


@contextlib.contextmanager
def _policy_file_lock(target: Path):
    lock_path = target.parent / f".{target.name}.lock"
    with exclusive_file_lock(lock_path, blocking=True):
        yield


def _atomic_write_policy_doc(target: Path, doc: dict[str, object]) -> None:
    if target.exists():
        st_existing = target.lstat()
        if hasattr(os, "getuid") and st_existing.st_uid != os.getuid():
            raise PermissionError(
                f"refusing to overwrite policy file {target} owned by uid {st_existing.st_uid} "
                f"from uid {os.getuid()} (run as the validator service user, not root/sudo)"
            )
    payload = (json.dumps(doc, indent=2, sort_keys=False) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=".fee_policy.", dir=str(target.parent))
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        os.write(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_name, target)
        if hasattr(os, "O_DIRECTORY"):
            with contextlib.suppress(OSError):
                dir_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
    finally:
        if fd != -1:
            os.close(fd)
        if os.path.exists(tmp_name):
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)


def _any_enabled_row(doc: dict[str, object]) -> bool:
    if doc.get("kill_switch") is True:
        return False
    rows = doc.get("rows")
    if type(rows) is not dict:
        return False
    return any(
        type(v) is dict and v.get("enabled", True) is True for v in rows.values()
    )


def update_policy_row(
    *,
    path: Path | str,
    scope: str,
    enabled: bool,
    amount_rao: int | None = None,
    netuid: int | None = None,
    min_block: int | None = None,
    current_head: int | None = None,
    effective_from_block: int | None = None,
    policy_version: str | None = None,
    source: str | None = None,
    allow_testnet_without_terms: bool | None = None,
    clear_kill_switch: bool = False,
) -> dict[str, object]:
    """Atomically update or insert a `<netuid>:`-prefixed scope row in host state."""
    target = Path(path)
    if is_inside_repo(target):
        raise ValueError(
            f"refusing to write live submission fee policy inside git checkout: {target}"
        )
    m = _KEY.fullmatch(scope)
    if m is None:
        raise ValueError(
            f"invalid scope {scope!r}: must include '<netuid>:' prefix "
            "(e.g. '116:electric-motor-magnetics 1.9' or '567:*')"
        )
    prefix_net = int(m.group(1))
    scope_body = m.group(2)
    if netuid is None:
        netuid = prefix_net
    if netuid != prefix_net:
        raise ValueError("netuid must match the '<netuid>:' scope prefix")
    if netuid == MAINNET_NETUID and scope_body == "*" and enabled:
        raise ValueError(
            "Mainnet 116 forbids enabling wildcard '116:*'; specify '116:<challenge_id> <version>'"
        )

    with _policy_file_lock(target):
        if target.exists():
            doc = json.loads(target.read_bytes())
            if (
                type(doc) is not dict
                or doc.get("schema") != SCHEMA
                or type(doc.get("rows")) is not dict
            ):
                raise ValueError(f"existing policy file {target} is malformed")
        else:
            doc = {
                "schema": SCHEMA,
                "source": source or "OWNER-SUBMISSION-FEE-01",
                "rows": {},
            }

        if source is not None:
            doc["source"] = source
        if enabled and doc.get("kill_switch") is True:
            if not clear_kill_switch:
                raise ValueError(
                    "host kill_switch is active; pass --clear-kill-switch (or clear_kill_switch=True) to clear it"
                )
            doc["kill_switch"] = False

        existing = doc["rows"].get(scope)
        existing_dict = existing if type(existing) is dict else {}
        prev_amount = existing_dict.get("amount_rao")
        prev_min_block = existing_dict.get("min_block")
        prev_enabled = existing_dict.get("enabled", True) if existing_dict else False
        prev_version = existing_dict.get("policy_version")
        lookback = int(
            existing_dict.get("max_lookback_blocks", DEFAULT_MAX_LOOKBACK_BLOCKS)
        )

        final_amount = (
            amount_rao
            if amount_rao is not None
            else (prev_amount if type(prev_amount) is int else 25_000_000)
        )
        if amount_rao is None and type(prev_amount) is not int and enabled:
            raise ValueError(
                "amount_rao (or --tao) is required when enabling a new scope"
            )
        final_min_block = (
            min_block
            if min_block is not None
            else (prev_min_block if type(prev_min_block) is int else 0)
        )
        final_version = (
            policy_version
            if policy_version is not None
            else (prev_version if type(prev_version) is str else "tao-burn-v1")
        )

        existing_tiers = (
            _normalize_grace_tiers(
                existing_dict.get("grace_tiers"),
                existing_dict.get("previous_amount_rao"),
                existing_dict.get("effective_from_block"),
            )
            or ()
        )
        kept_tiers: list[tuple[int, int]] = [
            (ub, amt)
            for ub, amt in existing_tiers
            if amt < final_amount and (current_head is None or ub > current_head)
        ]

        if (
            enabled
            and prev_enabled
            and type(prev_amount) is int
            and final_amount > prev_amount
        ):
            if effective_from_block is None or current_head is None:
                raise ValueError(
                    "dialing fee UP requires both --current-head and --effective-from-block"
                )
            if not (
                current_head + 1 <= int(effective_from_block) <= current_head + lookback
            ):
                raise ValueError(
                    f"effective_from_block ({effective_from_block}) must be in "
                    f"[{current_head + 1}, {current_head + lookback}]"
                )
            kept_tiers.append((int(effective_from_block), prev_amount))
        elif effective_from_block is not None:
            if current_head is not None and not (
                current_head + 1 <= int(effective_from_block) <= current_head + lookback
            ):
                raise ValueError("effective_from_block out of bounded lookback window")

        kept_tiers.sort(key=lambda t: (t[0], t[1]))

        new_row: dict[str, object] = {
            "enabled": bool(enabled),
            "policy_version": final_version,
            "amount_rao": int(final_amount),
            "netuid": int(netuid),
            "min_block": int(final_min_block),
        }
        if "max_lookback_blocks" in existing_dict:
            new_row["max_lookback_blocks"] = lookback
        if kept_tiers:
            new_row["grace_tiers"] = [
                {"until_block": ub, "amount_rao": amt} for ub, amt in kept_tiers
            ]
        final_allow_no_terms = (
            allow_testnet_without_terms
            if allow_testnet_without_terms is not None
            else existing_dict.get("allow_testnet_without_terms", False)
        )
        if final_allow_no_terms:
            new_row["allow_testnet_without_terms"] = True

        if _valid_row(new_row) is None:
            raise ValueError(f"resulting policy row fails validation: {new_row}")

        doc["rows"][scope] = new_row
        for k, r in doc["rows"].items():
            if _KEY.fullmatch(k) is None or _valid_row(r) is None:
                raise ValueError(f"invalid row {k!r} in policy document")

        _atomic_write_policy_doc(target, doc)
        if _any_enabled_row(doc):
            _write_armed_flag(target)
        else:
            _clear_armed_flag(target)
        return new_row


def disable_policy(
    *,
    path: Path | str,
    scope: str | None = None,
    netuid: int | None = None,
    kill_switch: bool = False,
    force: bool = False,
) -> dict[str, object]:
    """Pause a single scope or engage the host-wide `kill_switch` (`H3`).

    When ``force=True`` repairs a corrupt file or prunes malformed rows, saves a
    forensic `.corrupt.<ts>` backup and reports `backed_up_corrupt_file` +
    `dropped_corrupt_rows` explicitly (never silent, `H3`).
    """
    target = Path(path)
    if is_inside_repo(target):
        raise ValueError(
            f"refusing to write live submission fee policy inside git checkout: {target}"
        )
    if scope is None and not kill_switch:
        raise ValueError("provide --scope or --kill-switch")

    backed_up_path: str | None = None
    dropped_keys: list[str] = []

    with _policy_file_lock(target):
        doc: dict[str, object] | None = None
        had_corrupt_file = False
        if target.exists():
            try:
                loaded = json.loads(target.read_bytes())
                if (
                    type(loaded) is dict
                    and loaded.get("schema") == SCHEMA
                    and type(loaded.get("rows")) is dict
                ):
                    doc = loaded
                elif not force:
                    raise ValueError(
                        f"policy file {target} is malformed (re-run with --force to repair)"
                    )
                else:
                    had_corrupt_file = True
            except (OSError, ValueError):
                if not force:
                    raise
                had_corrupt_file = True
        if doc is None:
            doc = {
                "schema": SCHEMA,
                "source": "OWNER-SUBMISSION-FEE-01",
                "rows": {},
            }
        if force:
            clean_rows = {}
            for k, v in dict(doc.get("rows") or {}).items():
                if type(k) is str and _KEY.fullmatch(k) and _valid_row(v) is not None:
                    clean_rows[k] = v
                else:
                    dropped_keys.append(str(k))
            if (had_corrupt_file or dropped_keys) and target.exists():
                backup = target.with_name(f"{target.name}.corrupt.{int(time.time())}")
                shutil.copyfile(target, backup)
                os.chmod(backup, 0o600)
                backed_up_path = str(backup)
            doc["rows"] = clean_rows

        if kill_switch:
            doc["kill_switch"] = True

        if scope is not None:
            m = _KEY.fullmatch(scope)
            if m is None:
                raise ValueError(f"invalid scope {scope!r}: expected '<netuid>:...'")
            prefix_net = int(m.group(1))
            if netuid is not None and netuid != prefix_net:
                raise ValueError("netuid mismatch with scope prefix")
            existing = doc["rows"].get(scope)
            ex_dict = existing if type(existing) is dict else {}
            prev_amt = ex_dict.get("amount_rao")
            row_out: dict[str, object] = {
                "enabled": False,
                "policy_version": str(ex_dict.get("policy_version") or "tao-burn-v1"),
                "amount_rao": (
                    int(prev_amt)
                    if type(prev_amt) is int
                    and MIN_SUBTENSOR_BURN_RAO <= prev_amt <= MAX_SUBMISSION_BURN_RAO
                    else 25_000_000
                ),
                "netuid": prefix_net,
                "min_block": int(ex_dict.get("min_block") or 0),
            }
            doc["rows"][scope] = row_out

        _atomic_write_policy_doc(target, doc)
        if _any_enabled_row(doc):
            _write_armed_flag(target)
        else:
            _clear_armed_flag(target)

        result = dict(doc)
        if backed_up_path is not None:
            result["backed_up_corrupt_file"] = backed_up_path
        if dropped_keys:
            result["dropped_corrupt_rows"] = dropped_keys
        return result


def _tao_to_rao(text: str) -> int:
    try:
        val = decimal.Decimal(text)
    except decimal.InvalidOperation as exc:
        raise ValueError(f"invalid TAO decimal {text!r}") from exc
    if not val.is_finite() or val <= 0:
        raise ValueError(f"TAO amount must be finite and > 0: {text!r}")
    scaled = val * decimal.Decimal(1_000_000_000)
    if scaled != int(scaled):
        raise ValueError(f"TAO amount {text!r} exceeds 9 decimal places (1 RAO)")
    return int(scaled)


def _resolve_cli_policy_path(args) -> Path:
    if args.path is not None:
        return Path(args.path)
    if args.state_dir is not None:
        return Path(args.state_dir) / POLICY_FILE_NAME
    env_p = os.environ.get("CARBON_SUBMISSION_FEE_POLICY")
    if env_p:
        return Path(env_p)
    env_d = os.environ.get("CARBON_SUBMISSION_FEE_STATE_DIR")
    if env_d:
        return Path(env_d) / POLICY_FILE_NAME
    netuid = getattr(args, "netuid", None)
    if type(netuid) is int:
        return resolve_host_state_dir(netuid=netuid) / POLICY_FILE_NAME
    raise ValueError(
        "specify --path, --state-dir, or --netuid (in host state outside the git checkout)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.submission_fee",
        description="Inspect or hot-dial validator submission fee policy in host state (zero restart).",
    )
    parser.add_argument("--path", type=Path, default=None, help="Host policy JSON file")
    parser.add_argument(
        "--state-dir", type=Path, default=None, help="Host fee state directory"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show", help="Print current submission fee policy rows")

    stats_p = sub.add_parser("stats", help="Print operator fee ledger stats")
    stats_p.add_argument("--netuid", type=int, required=True)

    cred_p = sub.add_parser(
        "credit-settlement",
        help="Mint a single RETRY_CREDIT for an owed/released paid submission",
    )
    cred_p.add_argument("--netuid", type=int, required=True)
    cred_p.add_argument("--submission-id", required=True)
    cred_p.add_argument("--reason", default="operator_ruled_infra")

    dial_p = sub.add_parser("dial", help="Enable or adjust fee for a scope")
    dial_p.add_argument(
        "--scope",
        required=True,
        help="Scope key: '567:*' or '<netuid>:<challenge_id> <version>'",
    )
    dial_p.add_argument("--tao", required=True, help="Fee in TAO (e.g. 0.025)")
    dial_p.add_argument("--netuid", type=int, default=None)
    dial_p.add_argument("--min-block", type=int, default=None)
    dial_p.add_argument(
        "--current-head",
        type=int,
        default=None,
        help="Current finalized block height (required when dialing UP)",
    )
    dial_p.add_argument(
        "--effective-from-block",
        type=int,
        default=None,
        help="When dialing UP, honor previous rate for burns before this block",
    )
    dial_p.add_argument("--policy-version", default=None)
    dial_p.add_argument("--source", default=None)
    dial_p.add_argument(
        "--allow-testnet-without-terms",
        action="store_true",
        default=None,
        help="Testnet only: permit rehearsal on a door without pinned submission_terms",
    )
    dial_p.add_argument(
        "--clear-kill-switch",
        action="store_true",
        help="Explicitly clear an active host-wide kill_switch when dialing on",
    )

    off_p = sub.add_parser(
        "disable", help="Instantly pause fee requirement for a scope or entire host"
    )
    off_p.add_argument("--scope", default=None)
    off_p.add_argument("--netuid", type=int, default=None)
    off_p.add_argument(
        "--kill-switch",
        action="store_true",
        help="Disable fees across all scopes in this policy file",
    )
    off_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite/repair even if the existing policy file is corrupt",
    )

    args = parser.parse_args(argv)
    target = _resolve_cli_policy_path(args)
    if args.cmd == "show":
        if not target.exists():
            print(json.dumps({"rows": {}}))
            return 0
        print(target.read_text(encoding="utf-8"), end="")
        return 0
    if args.cmd == "stats":
        db_path = target.parent / ledger_file_name(args.netuid)
        if not db_path.is_file():
            raise SystemExit(f"fee ledger does not exist yet at {db_path}")
        ldg = FeeLedger(db_path, expected_netuid=args.netuid)
        print(json.dumps(ldg.public_stats(), indent=2))
        return 0
    if args.cmd == "credit-settlement":
        db_path = target.parent / ledger_file_name(args.netuid)
        if not db_path.is_file():
            raise SystemExit(f"fee ledger does not exist yet at {db_path}")
        ldg = FeeLedger(db_path, expected_netuid=args.netuid)
        cid = ldg.credit_submission_by_id(args.submission_id, reason=args.reason)
        print(
            json.dumps(
                {"submission_id": args.submission_id, "credit_id": cid}, indent=2
            )
        )
        return 0 if cid is not None else 2
    if args.cmd == "dial":
        row = update_policy_row(
            path=target,
            scope=args.scope,
            enabled=True,
            amount_rao=_tao_to_rao(args.tao),
            netuid=args.netuid,
            min_block=args.min_block,
            current_head=args.current_head,
            effective_from_block=args.effective_from_block,
            policy_version=args.policy_version,
            source=args.source,
            allow_testnet_without_terms=(
                True if args.allow_testnet_without_terms else None
            ),
            clear_kill_switch=bool(args.clear_kill_switch),
        )
        print(json.dumps({"updated": args.scope, "row": row}, indent=2))
        return 0
    if args.cmd == "disable":
        doc = disable_policy(
            path=target,
            scope=args.scope,
            netuid=args.netuid,
            kill_switch=bool(args.kill_switch),
            force=bool(args.force),
        )
        out: dict[str, object] = {
            "disabled": args.scope or "*",
            "kill_switch": doc.get("kill_switch", False),
        }
        if "backed_up_corrupt_file" in doc:
            out["backed_up_corrupt_file"] = doc["backed_up_corrupt_file"]
        if "dropped_corrupt_rows" in doc:
            out["dropped_corrupt_rows"] = doc["dropped_corrupt_rows"]
        print(json.dumps(out, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
