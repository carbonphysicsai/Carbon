"""miner_lookup: the read-only tool Miner X answers miners with (owner order, 20 Nov 2026: "all read authority needed to
answer any miner question"; V2's ruling: reports/MINER_LOOKUP_DISCLOSURE_20261120.md).

One self-contained file (`python3 -I -B miner_lookup.py ssh` behind a forced-command key): it imports nothing from the
repository. It reads four things and nothing else: the attempts ledger (opened `mode=ro` + `query_only`), the auto-grade
marker's `state` and `code`, the door's own public queue feed, and two files others write (the public launch board and
V2's `owed_tasks.tsv`). Every printed value is built field by field from `ALLOWED_FIELDS`: a number, a UTC second, an id
that matches a pattern, or a sentence from the closed word tables below (copied from the Launchpad's own tables; a test
holds the copy equal). `finish()` re-checks the finished document against the allow-list and a secret-shaped-text scan
and refuses the whole answer on any difference; it never sends part of one.

Subcommands, each with a typed argument checked by an exact pattern (no shell, no globbing, one question per call):

    hotkey <ss58 | first4...last4>   task <rtsk_ id or 8+ hex prefix>   entry <id>   public queue|board   verify ...

The OWN fields (about one hotkey's own submissions) sit behind ONE switch, `OWN_READ`. "open" is V2's current ruling
(20 Nov, re-ruled): Miner X may read them for any hotkey with no proof, because reading is not disclosure; the guard is
the reply rule (OWN fields go only to that hotkey's owner, decided at posting). Any other value refuses every OWN
subcommand and leaves `public` working. `verify` is built only as a refusal here: V2's optional proof check is not part
of this head. A field that V2's list names but this tool cannot source is listed in `NOT_AVAILABLE`, so the answer says
"not available" and the question becomes a RECEIPTS row; nothing is ever answered from a hidden source.

Regenerate the word tables after a sentence changes:  python -m scripts.dev.miner_lookup --write-words
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shlex
import sqlite3
import sys
import urllib.request
from pathlib import Path

#: The one switch for OWN fields. "open" = V2's re-ruling of 20 Nov ~12:3xZ (no read gate). Anything else = OWN refused.
OWN_READ = "open"
CONFIG_PATH = "/home/carbon/minerx/config.json"
MAX_TASKS = 200
MAX_BYTES = 262144
SQL_TIMEOUT_S = 20
QUEUE_TIMEOUT_S = 5

#: What may be printed, by section. Nothing outside it is ever produced; `finish` enforces it.
ALLOWED_FIELDS = {
    "lookup": {
        "asked",
        "tasks",
        "task",
        "queue",
        "queue_rows",
        "board",
        "not_available",
        "refused",
    },
    "task": {
        "task_id",
        "entry_id",
        "submitted_utc",
        "last_change_utc",
        "state",
        "outcome_code",
        "reason",
        "charged",
        "slot_given_back",
        "withdrawn",
        "owed",
    },
    "owed": {"owed_id", "state", "rerun_task_id"},
    "queue": {
        "door_state",
        "waiting_to_build",
        "building_now",
        "waiting_to_grade",
        "grading_now",
        "wait_24h",
        "as_of",
        "rows",
    },
    "queue_row": {"position", "hotkey", "state", "in_queue_s"},
    "wait_24h": {"verdicts", "median_s", "p90_s", "reason"},
    "board": {"rank", "total", "status", "hotkey"},
}
#: Fields V2's list names (or the Lead asked for) that this tool cannot source: Miner X says "not available".
NOT_AVAILABLE = (
    "allowance used and left, and reset times",
    "fee and refund amounts",
    "build wall seconds and the registered limit",
    "practice result",
    "gate names and reasons",
    "grade epoch, public pack id and code sha",
    "crown contender state for your own submission",
    "incident windows",
)
#: The only fields allowed to hold a long hex id; every other string is scanned for secret-shaped text.
ID_FIELDS = ("task_id", "rerun_task_id")

TASK_ID = re.compile(r"rtsk_[0-9a-f]{64}")
TASK_PREFIX = re.compile(r"(?:rtsk_)?[0-9a-f]{8,64}")
SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{40,60}")
SHORT = re.compile(r"([1-9A-HJ-NP-Za-km-z]{4})(?:\.\.\.|…)([1-9A-HJ-NP-Za-km-z]{4})")
SHORT_FORM = re.compile(r"[1-9A-HJ-NP-Za-km-z]{4}…[1-9A-HJ-NP-Za-km-z]{4}")
ENTRY_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}")
UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
OWED_ID = re.compile(r"[A-Za-z0-9._-]{1,48}")
OWED_STATES = ("queued", "re-running", "done")
ASKED = re.compile(r"[A-Za-z0-9_.…-]{1,70}")
LONG_HEX = re.compile(r"[0-9a-fA-F]{32,}")
LONG_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{40,}")
#: The door's marker codes the tool can state in the miner's words (a marker code is internal text, so only these map).
MARKER_TO_CODE = {"cancelled_by_carbon_stop": "direct_task_cancelled"}
#: Two tool-authored sentences (closed constants, like the word tables: no ledger text reaches them), for the two cases where the
#: grade-state sentence alone would MISLEAD the miner Miner X answers (Miner X 13:22:20Z and sre 00:47:20Z):
#: a task on V2's owed list is not simply "your model's own run failed", and a build chain that was capped after
#: `build_requeued` is not "waiting in line".
OWED_REASON = "Carbon owes this submission a re-run or a ruling (see 'owed'). Do not read its grade state as the final answer for this task."
BUILD_REQUEUED = "build_requeued"
BUILD_REQUEUED_REASON = (
    "Carbon's build of this submission was requeued and the ledger shows nothing after it: it is not waiting in line. "
    "Check its owed record, if any; otherwise ask the validator team."
)
LIMIT_CODES = ("epoch_limit_reached", "exam_daily_allowance_reached")
TERMINAL_KINDS = ("OUTCOME", "FAILED_INFRA", "UNAVAILABLE", "REFUSED")


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


# --- words:start (generated: python -m scripts.dev.miner_lookup --write-words) ---
WORDS_NEXT = {
    "ALREADY_COMMITTED_THIS_TEMPO": "Your signer already signed a commitment this tempo (at most one per tempo, about 72 minutes). Commit again once the next tempo starts (carbon_commit).",
    "AUTH_BAD_SIGNATURE": "The validator could not verify the signature for your hotkey. Check that carbon-miner-signer runs for your registered hotkey, then submit again; the frozen candidate is kept.",
    "AUTH_MALFORMED": "The validator found the signature headers missing or malformed. Check that carbon-miner-signer is the signer running and that nothing between you and the intake changes requests, then submit again; the frozen candidate is kept.",
    "AUTH_REPLAY": "The validator had already seen this signature. Submit again; the request is signed afresh, and the frozen candidate is kept.",
    "AUTH_STALE": "The signature was more than 10 seconds old when the validator checked it. Check this machine's clock and that your signer answers promptly, then submit again; the frozen candidate is kept.",
    "AUTH_UNAVAILABLE": "The validator cannot verify signatures right now; that is on its side. Submit again later; the frozen candidate is kept.",
    "AUTH_WRONG_RECEIVER": "The request was signed for another validator than the one answering at the intake address. Check the address, then submit again; the frozen candidate is kept.",
    "AUTO_CONFIRM_NOT_ALLOWED": "Your signer auto-confirms only allow-listed testnet 567 hotkeys, and this commitment is not one; nothing was signed or sent. Restart the signer without --auto-confirm-commitments and confirm in its terminal, then commit again (carbon_commit).",
    "BAD_DIGEST": "Your signer refused the digest as not a sha256 digest; nothing was signed or sent. Report it: Carbon computes it from the frozen candidate.",
    "COMMITMENT_NOT_PINNED": "Your signer's commitment pins are incomplete, so it signs no commitment; nothing was sent. Update carbon-miner-signer to a release whose commitment record is complete, restart it, then commit again (carbon_commit).",
    "COMMIT_IN_FLIGHT": "Your signer is already asking you to confirm another commitment. Answer it in the signer's terminal, then observe (carbon_observe).",
    "ERA_TOO_LONG": "Your signer refused a transaction whose era is longer than its cap; nothing was signed or sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "FEE_OVER_CEILING": "The quoted fee is above your signer's recorded ceiling, so it signed nothing and nothing was sent. The ceiling is not changed from here; commit again later (carbon_commit).",
    "FEE_UNKNOWN": "Your signer had no fee to check, so it signed nothing and nothing was sent. Commit again in a few minutes (carbon_commit).",
    "IMMORTAL_ERA": "Your signer refused an immortal transaction; nothing was signed or sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "LEDGER_UNAVAILABLE": "Your signer could not read or write its own commitment ledger, so it signed nothing. Check the signer's state directory, restart it, then commit again (carbon_commit).",
    "MALFORMED_REQUEST": "Your signer refused the commitment request as malformed; nothing was signed or sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "NONZERO_TIP": "Your signer refused a commitment carrying a tip; nothing was signed or sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "NOT_A_COMMITMENT": "Your signer refused a call that is not the one commitment call it signs; nothing was signed or sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "NOT_CONFIRMED": "The commitment was not confirmed in your signer's terminal, so nothing was signed or sent. Commit again (carbon_commit) and type the digest's last 8 characters there; an agent cannot confirm it.",
    "PAYLOAD_MISMATCH": "Your signer's own rebuild of the transaction differs from what was prepared, so it signed nothing and nothing was sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "STALE_CHAIN_CONTEXT": "The chain moved on while your signer was asked, so it signed nothing and nothing was sent. Commit again (carbon_commit).",
    "TRANSPORT_CAPACITY": "The validator's receipt journal is full; that is on its side. Submit again later; the frozen candidate is kept.",
    "TRANSPORT_CONFLICT": "The validator holds a different request under this request id. Submit again; a new request id is used, and the frozen candidate is kept.",
    "TRANSPORT_CONTEXT": "The validator serves another network, subnet or Challenge than the request names. Check this Challenge's validator intake address under Set up your environment, then submit again; the frozen candidate is kept.",
    "TRANSPORT_IDENTITY": "The validator does not find your hotkey (or its own) registered on this subnet. Check your registration (carbon_onboarding_status), then submit again; the frozen candidate is kept.",
    "TRANSPORT_MALFORMED": "The validator did not read the request as a Carbon request. Check that the intake address serves this Carbon version, then submit again; the frozen candidate is kept.",
    "TRANSPORT_RATE": "Too many requests reached the validator from your hotkey at once. Wait a moment, then submit again; the frozen candidate is kept.",
    "TRANSPORT_REPLAY": "The validator had already received this exact request. Submit again; a new request is built and signed, and the frozen candidate is kept.",
    "TRANSPORT_STALE": "The validator turned this request away before admitting it, even after Carbon sent it again a few times. This is on the validator's side, not your machine's clock. Submit again shortly; the request is rebuilt and signed afresh, and the frozen candidate is kept.",
    "TRANSPORT_STORE": "The validator could not record the request; that is on its side. Submit again; the frozen candidate is kept.",
    "WRONG_NETUID": "Your signer refused a commitment for another subnet than the one it started for; nothing was signed or sent. Start it for the subnet your profile names, then commit again (carbon_commit).",
    "WRONG_NETWORK": "Your signer refused a commitment for another network than the one it started for; nothing was signed or sent. Start it for the network your profile names, then commit again (carbon_commit).",
    "allowance_group_unmapped": "This is not a mistake on your side. The validator cannot yet place your coldkey in its list for graded exams, so it cannot grade this submission yet. No graded-exam slot was used for it. Try again later; if it keeps happening, send us the UTC time and the last 4 characters of your hotkey. Your frozen candidate is kept.",
    "allowance_group_unresolved": "This is not a mistake on your side. The validator cannot yet match your hotkey to its coldkey, so it cannot take or grade this submission yet. No graded-exam slot was used for it. Try again later; if it keeps happening, send us the UTC time and the last 4 characters of your hotkey. Your frozen candidate is kept.",
    "already_attached": "This session already holds a campaign. Detach it (carbon_detach_campaign) first.",
    "attach_unavailable": "The campaign must be one of yours, unfinished and not held by another operation or session, with your hotkey registered and your signer running. Observe it (carbon_observe) to see its state.",
    "attachment_busy": "Another attach or detach of this session is under way. Try again when it returns.",
    "autonomous_agent_replaced": "Graphite replaced Carbon's autonomous agent for new launches. Launch with agent=graphite (carbon-graphite in setup) and choose RESEARCH, BUILD or FULL; campaigns launched earlier still run and replay as they were.",
    "backend_not_served": "This validator has no worker image for your recipe's backend. That is not a verdict on the recipe, and nothing was recorded. Submit to a validator that serves the backend, or again once this one does; the frozen candidate is kept.",
    "body": "The intake refused the submission as larger than it accepts (64 KiB), so nothing was evaluated; the frozen candidate is kept. Check that the intake address serves this Carbon version; if it does, this recipe is too large to submit to it.",
    "body_timeout": "The submission's body did not reach the intake in time, so nothing was evaluated; the frozen candidate is kept. Check your connection, then submit again.",
    "bounded_hypothesis_required": "Send hypothesis (and expected_effect, if given) as 1 to 2048 characters of text.",
    "bounded_note_required": "Send 1 to 2000 characters of plain text.",
    "bounded_reason_required": "Send reason as 1 to 4096 characters of text.",
    "call_in_flight": "A model call of this campaign is still being admitted or in flight (it holds the campaign's provider-call lease), or this host cannot show that none is; settle once it has ended or its process has exited.",
    "campaign_busy": "Another session holds this campaign: an attached agent, the Control Center's tools, or an operation still running. Right after a launch the campaign is busy until its launch run finishes (state QUEUED, then READY): wait for it (carbon_wait with the campaign, or watch the page) and try again. Otherwise detach it (carbon_detach_campaign) or close the tools, then try again.",
    "campaign_complete": "This campaign is complete. Launch a new one to continue.",
    "campaign_frozen_on_old_revision": "This campaign was frozen under an earlier Carbon revision than the one your runner profile accepts now, so it cannot practise, freeze or submit on this checkout. Launch a new campaign, practise and freeze the same recipe in it, then submit. Your hotkey's on-chain commitment for that recipe still applies: it binds the Challenge, its contract and the strategy, not the campaign, so there is nothing to recommit. This campaign stays readable.",
    "campaign_interrupted": "The campaign stopped before it finished. Resume it; reconcile first if it asks for reconciliation.",
    "campaign_journal_not_ready": "The campaign is still being prepared. Call wait on it (it returns once preparation is done), then try again.",
    "campaign_manifest_differs": "This campaign's frozen record was not launched under this profile, or differs from its own ledger. Nothing was changed. Attach with the profile that launched it.",
    "campaign_not_found": "No campaign of this profile has that id. List your campaigns (carbon_observe, or the Control Center) and name one by its 32-character id.",
    "campaign_not_prepared": "The campaign is still being prepared. Observe it until it is READY, then try again.",
    "campaign_owner_changed": "Your signer authenticates as another miner than the one this campaign was launched under. Attach with the hotkey and signer that launched it, or launch a new campaign; this one stays readable.",
    "campaign_paused": "This campaign is paused. Resume it, then try again.",
    "campaign_read_failed": "This campaign could not be read just now. Nothing was changed. Reload the page; if it persists, restart the Control Center.",
    "campaign_readback_unavailable": "This campaign's records could not be read back consistently. Nothing was changed. Export its record if you need it, and launch a new campaign to continue.",
    "campaign_revision_differs": "This campaign was frozen under another Carbon revision than your profile accepts. Attach from the checkout and profile it was launched with, or launch a new campaign.",
    "campaign_runtime_differs": "This campaign was frozen with a runtime this host no longer composes. Launch a new campaign; this one stays readable.",
    "campaign_stopped": "This campaign is stopped. Launch a new one to continue.",
    "candidate_awaits_submission": "A frozen candidate is waiting. Submit it before freezing another.",
    "candidate_build_refused": "Carbon's build refused your graph because of something in it (not a feature Carbon is missing): for example a malformed graph, a limit the kit names, or a policy rule. One thing to check first is the 32 KiB size limit: the compressed (zlib level 9) size of the whole graph, in bytes, not tokens. Nothing was graded. Your frozen candidate is kept.",
    "capacity": "The validator intake is busy. Submit again in a few minutes; the frozen candidate is kept.",
    "carbon_capability_gap": "Carbon capability gap: this doesn't count against you; the op is on Carbon's add list; see the kit's supported-ops notes for an alternative (the carbon.level4.tooling.lower_torch module docs).",
    "carbon_mcp_failed": "Carbon MCP stopped unexpectedly. Start it again; if it keeps failing, open the Control Center to check your setup.",
    "carbon_mcp_interrupted": "Interrupted. Start Carbon MCP again when you are ready.",
    "carbon_updated_rerun_installer": "Carbon in this checkout is not the revision your runner profile accepted: it was updated, or its worker image was rebuilt. Re-run the installer so your profile accepts this checkout and its images, then launch. Campaigns frozen under the earlier revision stay readable.",
    "card_banned": "You banned this card, so it is not served or pinned. Lift the ban (carbon_library_unban) first if you want it back.",
    "card_limit_out_of_bounds": "Send card_limit from 1 to 50, or omit it for 10.",
    "card_not_found": "No card in the shared pack or your library has that id. Search for it (carbon_library_search) and send an id it returns.",
    "catalog_gpu_receipt_pending": "This backbone is not yet GPU-checked on the validator, so it cannot be graded officially yet. This is on Carbon's side and does not count against you; nothing was charged. Under Backbone, pick one marked neither 'practice only' nor 'not yet GPU-checked on the validator', or submit a model built from your own graph. Practice on this backbone still works, and your campaign and frozen candidate are kept.",
    "chain_read_failed_infra": "Carbon could not read the subnet's chain: its endpoint was busy or unreachable after several tries. That is infrastructure, not your work; your campaign is kept. Resume it in a minute (carbon_resume, or Resume in the Control Center).",
    "challenge_deferred": "This Challenge is not open yet. Choose another from the Challenge list (carbon_challenges_v1__list).",
    "challenge_has_no_toolbox": "This Challenge has no toolbox to show. Choose a Challenge from the Challenge list (carbon_challenges_v1__list).",
    "challenge_mismatch": "The validator says the candidate names another Challenge than the contract it was sent under. Check the campaign's Challenge and the intake address, then submit again; the frozen candidate is kept.",
    "challenge_not_implemented": "This Challenge is reserved, not implemented. Choose another from the Challenge list (carbon_challenges_v1__list).",
    "challenge_required": "Send challenge and challenge_version as the Challenge list gives them (carbon_challenges_v1__list).",
    "challenge_retired": "This Challenge is retired. Launch a campaign on another (carbon_challenges_v1__list lists them).",
    "challenge_unknown": "Choose a Challenge from the Challenge list (carbon_challenges_v1__list).",
    "challenge_version_unsupported": "Send the version the Challenge list gives for that Challenge (carbon_challenges_v1__list).",
    "charge_exceeds_reservation": "The provider reported a charge above the call's reservation, which the ledger cannot book; reconcile it against the provider's own usage record before this campaign makes another call.",
    "closed_request_required": "Send exactly the operation's arguments: every required field and only declared ones (its arguments schema lists them).",
    "coldkey_submission_waiting": "One waiting submission per coldkey on this Challenge: a submission from a hotkey of this coldkey is already queued, building or waiting for its grade on this validator. Nothing was built or graded for this submission and it used none of your allowance. Submit again once that submission has its result. Another hotkey under your coldkey may be the one waiting; a submission still queued can be withdrawn from the Launchpad that made it (Withdraw (while queued)). Your frozen candidate is kept.",
    "commitment_ambiguous": "A commitment was broadcast and its outcome is not known yet. Carbon never sends it again: it reads the chain until the request's era has passed (about 26 minutes). Observe (carbon_observe), and commit again only if it did not land.",
    "commitment_bad_digest": "The digest to commit is not a sha256 digest, so nothing was asked or sent. Report it: Carbon computes it from the frozen candidate.",
    "commitment_call_mismatch": "Your signer returned another call than the one prepared, so nothing was sent. Check that your signer and Carbon are the same version, then commit again (carbon_commit).",
    "commitment_contested": "Another hotkey committed this recipe's hash on chain first, so it counts for that hotkey, not yours: the earliest commitment block, then the earlier transaction in that block, decides (OWNER-COMMITMENT-POSTER-01 D6). Recommitting the same hash cannot change that; build and freeze a different candidate.",
    "commitment_digest_unavailable": "Carbon could not work out the frozen candidate's commitment digest, so nothing was asked or sent. Report it; the frozen candidate is kept.",
    "commitment_failed": "The chain included the commitment and rejected it, so it is not on chain. Commit again later (carbon_commit); the frozen candidate is kept.",
    "commitment_fee_over_ceiling": "The fee rose above your signer's ceiling after you confirmed, so the signature was discarded unsent. Commit again later (carbon_commit).",
    "commitment_fee_unknown": "The chain did not quote the commitment's fee, so nothing was signed or sent. Commit again in a few minutes (carbon_commit).",
    "commitment_in_flight": "A commitment for this hotkey is already being posted. Observe until it settles (carbon_observe); it is never sent twice.",
    "commitment_not_observed": "The commitment was finalized but did not read back as your hotkey's commitment. Observe again in a minute (carbon_observe); commit again (carbon_commit) only if it is still not on chain.",
    "commitment_not_offered": "This campaign's Challenge uses no on-chain commitment. Submit without one (carbon_submit).",
    "commitment_reader_unavailable": "Your hotkey's on-chain commitment could not be read just now, by this validator or by Carbon before it sent anything; that is not a verdict on the recipe. Try again in a few minutes, or submit to another validator; the frozen candidate is kept.",
    "commitment_required": "This validator requires the frozen candidate's hash committed on chain first. Commit it (carbon_commit with this campaign; your signer asks you to confirm it in its terminal) or with your own Bittensor SDK code, then submit again (or resume, where Carbon's agent selects); the frozen candidate is kept.",
    "commitment_signature_invalid": "The signature did not verify for your hotkey, so nothing was sent. Check that your signer holds your registered hotkey, then commit again (carbon_commit).",
    "commitment_stale": "This validator counts a commitment only if it was posted after your hotkey's previous admitted submission. Recommit it (carbon_commit with this campaign and recommit=true; your signer asks you to confirm it in its terminal), then submit again (or resume, where Carbon's agent selects); the frozen candidate is kept.",
    "compaction_failed": "The agent stopped because it could not write a valid summary of its history to stay inside your model's input window; no history was silently dropped. Launch a new campaign with model_settings.max_input_tokens set higher, up to your model's published context less max_output_tokens (input_window lists both), or with a model that follows the summary instruction.",
    "compute_budget_malformed": "This Challenge's compute budget declaration is malformed, a repository defect: nothing can be frozen or submitted under it until Carbon fixes it. Your practice results are kept.",
    "construction_admission_record_required": "Check for result needs this round's own submission record, which is missing or no longer matches the frozen recipe, so nothing was read. Submit again from this campaign to record it.",
    "construction_checks_unavailable": "A required construction check has no current acceptance evidence. This attempt stopped before execution or signing. Use the registered base settings or wait for the named check; changing a level label does not resolve it.",
    "construction_contract_binding_mismatch": "The recipe's Challenge binding differs from the contract this Carbon registers for that version, so nothing was sent. The frozen candidate is kept. Update Carbon, then start a campaign on the version offered.",
    "construction_contract_not_registered": "This Carbon does not register this Challenge version's recipe contract, so nothing was sent. The frozen candidate is kept. Update Carbon (scripts/install_miner.sh --update), then start a campaign on the version offered.",
    "construction_contract_not_served": "The intake serves this Challenge but not this campaign's construction contract, so nothing was signed or sent; the frozen candidate is kept. The intake may run another Carbon version: check it, or use an intake that serves this version, then submit again.",
    "construction_intake_answer_unrecognised": "Your construction receiver answered in a form this Carbon does not read. The frozen candidate is kept. If the receiver did get your submission, submitting again returns that submission's result; it is never graded twice. If it repeats, the receiver may run another Carbon version: update Carbon, or ask its operator.",
    "construction_intake_chain_mismatch": "The intake this campaign submits to serves another chain or subnet, so nothing was signed or sent; the frozen candidate is kept. Check the intake address under Set up your environment, then submit again.",
    "construction_intake_challenge_mismatch": "The intake this campaign submits to serves another Challenge: each validator intake serves exactly one Challenge version, so nothing was signed or sent, and the frozen candidate is kept. Read your setup (carbon_setup_status, which changes nothing): it shows which Challenge each intake serves. If none serves this Challenge and version, no receiver serves it for you yet: practise it now, and add one when it is published (setup review, which rewrites the profile), then submit again.",
    "construction_intake_changed_since_submission": "This round's candidate was submitted to another receiver than the one your setup names now, and nothing was sent. Its result is read from the receiver it was submitted to; set that one back to read it.",
    "construction_intake_contract_mismatch": "The intake this campaign submits to is not a DEVELOPMENT receiver for this Challenge, so nothing was signed or sent. The frozen candidate is kept. Read your setup (carbon_setup_status, which changes nothing) to see which Challenge each receiver serves.",
    "construction_intake_identity_mismatch": "The receiver reported other identities than the ones your setup pins for it, so nothing was signed or sent. The frozen candidate is kept. Read your setup (carbon_setup_status) and ask the receiver's operator which receiver serves this Challenge now.",
    "construction_intake_unavailable": "Your construction receiver is configured but could not be reached, or did not answer. The frozen candidate is kept. If the receiver did get your submission, submitting again returns that submission's result; it is never graded twice. For a receiver on this machine's loopback (a tunnel), start the tunnel; otherwise the receiver may be down, so ask its operator or wait. Then submit again.",
    "construction_level_arm_invalid": "Send arm as one of the arm names carbon_ladder lists for the level, or omit it for the level's own variant.",
    "construction_level_invalid": "Send construction_level as a whole number from 0 to 5, or omit it for Level 0. arm needs a construction_level.",
    "construction_level_needs_own_selection": "A campaign at a construction level is driven by you or your own MCP agent: launch it with agent none.",
    "construction_level_not_offered_for_challenge": "This Challenge's campaign does not compile at construction levels yet. Launch at Level 0 (omit construction_level).",
    "construction_recipe_binding_mismatch": "The recipe names another Challenge, version or kit: copy challenge and output from the toolbox's catalog recipe for this campaign's exact version.",
    "construction_recipe_graph_workspace_missing": "Your graph is not staged at the receiver yet. Stage it first (the Control Center's stage button, or the stage_construction_graph action), then submit again. Nothing was submitted.",
    "construction_recipe_malformed": 'That is not a construction recipe. A recipe is a JSON object with exactly these keys: schema ("carbon.construction-recipe.v1"), challenge, source, procedure and output; a Strategy 1.0 ({schema_version, backbone, parameters}) is not one. Easiest: call toolbox {challenge, challenge_version}; its catalog list holds a ready recipe for every backbone. Copy one and change only procedure.configuration.',
    "construction_recipe_procedure_invalid": "The recipe's procedure is not valid: keep entrypoint, train_use and initial_state as the toolbox's catalog recipe has them, and change only configuration, with the settings the entry lists.",
    "construction_recipe_source_invalid": "The recipe's source is not one this version takes. Copy a catalog recipe from toolbox {challenge, challenge_version} (source {kind: catalog, catalog_id, catalog_digest}) and keep its source as it is.",
    "construction_request_deadline": "Your construction receiver did not answer before the submit's deadline. The frozen candidate is kept. If the receiver did get your submission, submitting again returns that submission's result; it is never graded twice. Submit again later.",
    "construction_selector_retired": "Remove construction_level, construction_variant_digest, and arm from the launch request (carbon_launch). For a new direct campaign, supply the construction recipe when practicing (carbon_practice). A campaign created with the retired selectors cannot be replayed as a direct campaign; launch a new one.",
    "construction_snapshot_unavailable": "Your construction receiver did not report its current exam, so nothing was signed or sent. The frozen candidate is kept. Submit again later; if it repeats, ask the receiver's operator.",
    "construction_source_idempotency_conflict": "The receiver already holds a different graph for your hotkey. To replace it, stage again and pass expected_manifest_digest: the manifest digest returned when you staged the earlier graph. If you have not staged since a receiver update (1-2 Nov), it may hold nothing for you now: stage again without expected_manifest_digest. Nothing was changed.",
    "construction_source_reference_not_found": "The receiver holds no earlier graph for your hotkey: stage it again without expected_manifest_digest.",
    "construction_staging_connection_reset": "The validator kept dropping the connection while your source uploaded, until the transfer time ran out. The validator keeps what it already received, so submit the same recipe again and the upload continues from there. If it keeps happening, check for a proxy or an unstable network between you and the validator.",
    "construction_submission_unserved": "This campaign's level does not submit through a level intake. A direct campaign (a catalog, graph or bundle recipe) submits to its construction receiver: freeze a practised recipe and submit again; if this persists, update Carbon and review your setup.",
    "construction_variant_invalid": "For the DEVELOPMENT Graphite standalone graph-v3 test, send the exact registered battery variant digest with agent graphite. Omit arm and any conflicting level hint. Omit construction_variant_digest to use the registered combined construction default.",
    "context_ceiling": "The agent stopped because its next request could pass your model's input window as Carbon bounds it; no history was silently dropped. Launch a new campaign with model_settings.max_input_tokens set higher, up to your model's published context less max_output_tokens (input_window lists both). Each call is reserved at that window, so check your provider_nanodollars ceiling too.",
    "contract_digest_malformed": "The validator could not read the contract digest Carbon sent. Check that the intake address serves this Carbon version, then submit again; the frozen candidate is kept.",
    "contract_not_served": "This validator serves another construction contract than the one your candidate was compiled under. Update Carbon so its contract matches the validator's, or submit to a validator that serves yours; the frozen candidate is kept.",
    "control_fenced": "This is not the campaign's reconcile action: settle only from the reconcile action, under the campaign's owner lock and its current control generation.",
    "cost_unmeasurable": "This recipe's cost cannot be calculated in the Challenge's budget unit, and a cost that cannot be checked is refused. Choose a recipe carbon_budget_status shows as Within budget.",
    "curation_not_found": "The pins and bans this campaign was launched with are no longer in your library, so nothing was called. Launch again: the new campaign takes your pins and bans as they are now.",
    "cursor_out_of_bounds": "Send after as 0 or more: the last next_cursor, or 0 to read from the start.",
    "design_excluded": "A choice in this recipe is excluded from submission. Run check_design on it to see which, and choose another.",
    "design_malformed": "The recipe is not a design Carbon can check: send schema_version, challenge_id, backbone and parameters, with parameters an object.",
    "design_needs_owner_decision": "A choice in this recipe awaits an owner decision before it can be submitted. Run check_design on it to see which, and choose another for now.",
    "design_not_yet_rebuildable": "The validator cannot rebuild a choice in this recipe yet. Run check_design on it to see which, and choose one it rebuilds.",
    "design_refused": "A choice in this recipe is refused for submission. Run check_design on it to see which, and change that choice.",
    "development_variant_not_served": "The candidate names a development-only contract variant, which is never served to miners, and nothing was sent for evaluation. Compile it against the Challenge's published contract and submit again; the frozen candidate is kept.",
    "direct_task_cancelled": "The validator stopped before it ran this submission and cancelled it, twice. This is on our side, not a result about your candidate, and nothing was graded or charged. Your frozen candidate is kept. Check for the result later; if it still shows cancelled, send us the UTC time and the last 4 characters of your hotkey.",
    "dispatch_configuration_changed": "The runner profile changed after this request was admitted. Review it, then resume or send the request again.",
    "door_updating": "Carbon is upgrading the validator; please retry shortly. Nothing was built or graded for this request and nothing was charged. The Launchpad's Your place in line card shows when the validator is back. Your frozen candidate is kept.",
    "duplicate_key": "The candidate's recipe repeats a key in one object, which validators refuse. Nothing was evaluated; the frozen candidate is kept.",
    "epoch_limit_reached": "One graded exam per Challenge per round, and your graded exam for this round is already used or in progress. Nothing was built or graded for this submission and it used none of your allowance. Your frozen candidate is kept: submit it again when the next round opens (a round is 360 blocks, about 72 minutes; the receiver's answer names the block and the time).",
    "evaluation_failed_infra": "The validator's infrastructure failed. That is not a scientific result. The frozen candidate is kept; submit again later.",
    "evaluation_queued": "The validator queued your submission and has no verdict yet. On testnet 567 you need not submit again: observe asks the validator for its result, at most once per chain epoch (tempo), and shows the verdict once there is one. Elsewhere, submit again later (carbon_submit) to ask for it. The frozen candidate is kept, and it is the same submission, never a second one.",
    "evaluation_unavailable": "Your frozen candidate is kept, but it cannot be evaluated yet: no validator deployment or intake is configured for this Challenge in your runner profile. When a validator intake is published for it, update Carbon and review again under Set up your environment (carbon_setup_review), which writes it into your profile, or name a validator intake you run yourself; then submit again. Until then you can still launch, practise, observe, and stop or pause your campaign.",
    "exam_daily_allowance_reached": "You have used your graded exams for the day on this Challenge. Nothing was built or graded for this submission and it used none of your allowance. Your frozen candidate is kept: a slot frees as earlier graded exams age past one day, so submit it again in a later round.",
    "exam_feedback_reply_invalid": "The receiver's grade answer was not in the form Carbon accepts, so it is not shown. Your submission is not affected. Try again later; if it repeats, the receiver may run another Carbon version.",
    "exam_feedback_unavailable": "Your grade could not be read from the receiver just now. Your submission is not affected. Try Check for result again later.",
    "feed_not_served": "This validator intake does not publish a score feed, so no released scores were read. Nothing was submitted or changed; the frozen candidate is kept. Read released scores from an intake that serves the feed, or check again later.",
    "feed_unavailable": "The validator's score feed could not be read or did not verify, so no released scores were shown. Nothing was submitted or changed; the frozen candidate is kept. Scores are released only after the windows they came from close; check again later.",
    "feedback_mode_not_offered_by_challenge": "Send a feedback mode this Challenge offers (its description lists them), or omit it for FULL.",
    "final_exams_used": "Both final exams of this campaign are used. Launch a new campaign to continue.",
    "fitted_info_over_budget": "Your graph is over the 32 KiB size limit. It is counted as the compressed (zlib level 9) size of the whole graph, in bytes, not tokens or characters: the operations, wiring, shapes, constants and every static value in your ops' parameters all count. Nothing was graded. Your frozen candidate is kept; the kit's rules for your graph say what counts, and a graph with repeated layers compresses far below pasted numbers.",
    "freeze_a_candidate_first": "Freeze a practiced recipe (carbon_freeze_candidate), then submit.",
    "gpu_scope_is_for_another_challenge": "Your GPU practice was set up through a Challenge's own GPU path, which serves only that Challenge (one set up for any catalog Challenge serves every catalog Challenge). Launch that one, or set up compute again for this one (carbon_setup_compute).",
    "graphite_ceilings_required": "Graphite calls a paid model, so its budget must cap both provider_attempts (model calls) and provider_nanodollars (model spend) as whole numbers. Launch again with budget.ceilings setting both; nothing was called. A campaign launched without them cannot run, so resuming it does not help. Each call holds up to its most possible cost until it is booked, and starts only while that much spend is left: set provider_nanodollars to more than one call's hold (Graphite's options show per_call_reservation_nanodollars and what the ceiling buys).",
    "graphite_edition_unknown": "This launch or campaign names a Graphite edition this Carbon does not have, so nothing was called. For a new launch, send graphite_edition as one carbon_options lists (graphite.editions), or omit it for v1. For a campaign, update Carbon (re-run the installer), then resume; or launch a new campaign.",
    "graphite_field_not_used_by_mode": "That field is not used by this graphite_mode: research_share is for FULL, plan for BUILD, and a hunt runs only in RESEARCH and FULL. Leave it out, or change the mode.",
    "graphite_fields_need_the_graphite_agent": "graphite_mode, graphite_edition, research_share, plan, hunt and limits are Graphite's: send agent=graphite, or leave them out.",
    "graphite_input_window_too_small": "Graphite reads whole discovery documents, several in one turn, and Carbon admits a request only while it stays under max_input_tokens minus 4,096, counting one token for every byte added since the provider's last count. A Graphite launch that sets no max_input_tokens gets its model's published context less its output cap; where Carbon records no context, the historical 65,536, at which Graphite's first reading turns pass that bound. This applies when your window - that default, or the max_input_tokens you set - is 65,536 or less. Set model_settings.max_input_tokens higher, up to your model's published context less max_output_tokens (input_window lists both), or choose a model with a published context, before you launch. Each call is reserved at that window, so a larger one holds more of your provider_nanodollars ceiling per call, and a FULL launch's research share must hold one whole call.",
    "graphite_launch_invalid": "This campaign's Graphite launch fields are not the ones this Carbon reads, so nothing was called. Update Carbon (re-run the installer) and launch again; the campaign itself cannot be repaired.",
    "graphite_limits_invalid": "Send limits with only calls_per_epoch, trials_per_epoch and planner_calls, each a whole number from 1 to 100000, or omit them: your campaign ceilings still bind.",
    "graphite_mode_invalid": "Send graphite_mode as RESEARCH, BUILD or FULL, or omit it for FULL.",
    "graphite_not_offered_for_challenge": "Graphite runs only on a Challenge with a registered research campaign. Choose such a Challenge (carbon_options lists where Graphite is offered), or launch with agent=none.",
    "graphite_plan_output_cap": "The Planner's replies were cut at the output cap before it wrote a plan, so the build was not run without one. Launch a new campaign with max output tokens (model_settings.max_output_tokens, the wizard's max output) set higher, up to your model's own maximum if you know it. Resuming this campaign does not help: it keeps the cap it was launched with.",
    "headers": "The intake refused the request's headers (one was repeated), so nothing was evaluated; the frozen candidate is kept. Check that nothing between you and the intake, such as a proxy, changes requests, then submit again.",
    "hotkey_reserved_for_ladder": "This hotkey is Carbon's development-ladder hotkey, which the main validator never scores, and nothing was evaluated. Point this Challenge's intake at the ladder under Set up your environment, then submit again; the frozen candidate is kept.",
    "hotkey_submission_waiting": "One waiting submission per hotkey on this Challenge: this hotkey already has a submission queued, building or waiting for its grade on this validator. Nothing was built or graded for this submission and it used none of your allowance. Submit again once that submission has its result, or withdraw it while it is still queued, if this validator offers withdrawal (withdraw command). To submit a different model now, use Withdraw (while queued) on the waiting one in the Launchpad first. Your frozen candidate is kept.",
    "hotkey_window_used": "Your hotkey already has its submission for this tempo. Submit again once the next window opens; the frozen candidate is kept.",
    "hunt_query_invalid": "Send hunt as {queries?, max_records?}: up to 8 queries of 1 to 6 terms each (letters, digits and -, starting with a letter or digit; not and, or or not), and max_records from 1 to 5000. Raw arXiv query syntax is not accepted.",
    "import_invalid": "Send title as 1 to 300 characters and text as 1 to 20000 characters of plain text. PDF import is not offered yet: paste the text.",
    "inbox_full": "The validator's queue is full. Submit again later; the frozen candidate is kept.",
    "intake_answer_unrecognised": "The validator intake answered in a way this Carbon does not recognise, so nothing was evaluated; the frozen candidate is kept. Check that the intake address serves this Carbon version, then submit again.",
    "intake_busy": "The validator is busy and turned your submit away before reading it, even after several tries. Nothing was sent, charged or graded, and the frozen candidate is kept. Wait a minute and submit again.",
    "intake_changed_since_submission": "This epoch's candidate was submitted to another validator intake than the one now configured. Configure that intake again, then submit again to read its result; a candidate is never submitted twice.",
    "intake_mismatch": "The configured intake serves another chain or Challenge, or is not a battery intake. Nothing was sent for evaluation; the frozen candidate is kept. Correct this Challenge's validator intake address under Set up your environment, then submit again.",
    "intake_receiver_mismatch": "The validator intake reports another receiver hotkey than the one your profile pins for this Challenge, so nothing was signed or sent; the frozen candidate is kept. Read your setup (carbon_setup_status, which changes nothing) to see the intake address and the receiver hotkey your profile pins; to change either, the miner reviews setup again, which rewrites the profile. Then submit again.",
    "intake_signer_changed": "This epoch's candidate was submitted under another hotkey than the signer now running, and nothing was sent. Start carbon-miner-signer for the hotkey that submitted it, then submit again to read its result; a candidate is never submitted under a second hotkey.",
    "intake_unreachable": "The validator intake could not be reached. The frozen candidate is kept. For an intake on this machine's loopback (a tunnel to a validator), start the tunnel or the validator, since Carbon cannot tell which is not running; otherwise check the address and your connection. Then submit again.",
    "integer_out_of_range": "The candidate's recipe holds an integer outside the signed 64-bit range, which validators refuse. Nothing was evaluated; the frozen candidate is kept.",
    "invalid_agent": "Send graphite (Graphite, Carbon's research agent) or none (you or your own agent select); carbon-graphite and own-agent are accepted too.",
    "invalid_budget": "Send only ceilings, elapsed_seconds or final_reserve, within their bounds (carbon_options lists them).",
    "invalid_feedback_mode": "Send one of the feedback modes carbon_options lists, or omit it for FULL.",
    "invalid_idempotency_key": "Send 16-80 letters, digits, - or _. On launch over MCP you may omit it and the server generates one.",
    "invalid_research_control": "Send stop, pause or reconcile.",
    "invalid_tools_session_token": "Use the current agent tools session's own 32-character lowercase hexadecimal exclusive_token. If that token is unavailable, return to the normal agent tools session setup; do not use another session's token.",
    "ladder_commitment_not_variant": "The development ladder expects the variant's commitment, which binds the variant digest and the whole strategy, and nothing was evaluated. Carbon commits that form for you; commit again, then submit again; the frozen candidate is kept.",
    "ladder_hotkey_not_listed": "This validator is Carbon's development ladder, which serves only its listed rehearsal hotkeys, and nothing was evaluated. Point this Challenge's intake at the main validator under Set up your environment, then submit again; the frozen candidate is kept.",
    "ladder_level_4_not_open": "Level 4 is not open on the development ladder yet, and nothing was evaluated. The frozen candidate is kept.",
    "ladder_level_not_accepted": "The development ladder serves another level than the one this candidate uses, and nothing was evaluated. Submit it to the ladder deployment for its level; the frozen candidate is kept.",
    "ladder_variant_not_accepted": "The development ladder does not serve this level's variant, and nothing was evaluated. Choose a variant the ladder lists for its level, then submit again; the frozen candidate is kept.",
    "launch_choices_unrecorded": "This launch was recorded before its choices were kept, so it cannot be restarted exactly. Stop it and launch again.",
    "launch_record_differs": "This launch's record no longer matches what was admitted. Stop it and launch again.",
    "level4_allowlist_mismatch": "This checkout's Level 4 allowlist is not the one the level's variant pins. Update the Launchpad to the release that pins it.",
    "level4_batch_mismatch": "The lowered forward graph declares another batch than the recipe trains at. Lower it again with --batch set to the recipe's batch and freeze again.",
    "level4_directory_needs_level4": "level4_directory is only for a campaign launched at construction level 4; omit it.",
    "level4_directory_required": "A Level 4 freeze needs level4_directory: the directory python -m carbon.level4.tooling lower wrote on this machine.",
    "level4_envelope_incomplete": "Not every part of the Level 4 envelope had arrived, so nothing was evaluated or counted. Submit again: Carbon sends the missing parts first; the frozen candidate is kept.",
    "level4_envelope_transport_unavailable": "This Challenge's validator intake does not take Level 4 envelope parts, so nothing was signed or sent. Point the intake at the development ladder that serves Level 4 under Set up your environment, then submit again; the frozen candidate and its envelope are kept.",
    "level4_interface_mismatch": "The lowered submission was made for another interface than this recipe's. Lower it again with --interface set to the recipe's interface digest and freeze again.",
    "level4_not_served": "This validator does not take Level 4 envelopes, and nothing was stored. Point this Challenge's intake at the development ladder that serves Level 4, then submit again; the frozen candidate is kept.",
    "level4_part_conflict": "The validator holds other bytes for a part of this envelope, and nothing was replaced. Submit the candidate Carbon froze again; the frozen candidate is kept.",
    "level4_part_malformed": "A Level 4 envelope part was malformed, and nothing was stored. Submit again: Carbon rebuilds the parts from the frozen envelope; the frozen candidate is kept.",
    "level4_parts_mismatch": "An envelope part named another part count than its earlier parts, and nothing was stored. Submit the candidate Carbon froze again; the frozen candidate is kept.",
    "level4_size_bound_not_set": "The Level 4 variant sets no document size bound yet (HUMAN_INPUT), so no Level 4 submission can be verified or frozen. The owners set it; nothing was frozen.",
    "level4_store_not_owner_only": "The validator's Level 4 store is misconfigured, which is the validator's to fix, and nothing was stored. Try again later; the frozen candidate is kept.",
    "level4_submission_not_in_strategy": "The strategy's Level 4 field must be the submission digest the lowering printed. Put it there and freeze again.",
    "level4_submission_refused": "The lowered Level 4 submission was refused when verified: a document, its name, the manifest or the allowlist pin. Lower it again with python -m carbon.level4.tooling lower and freeze again.",
    "level_compile_not_served_by_target": "Your target validator's intake does not list this level's variant digest in its served_contracts, so the level's compile was not run and nothing was practised or frozen. Point this Challenge's intake at the development-ladder deployment that serves the level (Set up your environment), then try again.",
    "level_compile_unavailable": "The level's compile could not run on this machine, and nothing was practised, frozen or sent. Check the Launchpad's Python environment (setup's checks) and try again.",
    "level_not_registered": "No current registered development variant serves that level (or arm) of this Challenge, or the one your campaign froze is no longer current. Read carbon_ladder for the levels and arms that have one; nothing was signed or sent.",
    "level_not_served_by_target": "Your target validator's intake does not list this level's variant in its served_contracts, so nothing was signed or sent. A level above 0 is DEVELOPMENT: submit it only to the development-ladder deployment that lists it. The frozen candidate is kept.",
    "level_strategy_refused": "The recipe does not compile at the campaign's level: a widened value is outside the level's bounds, or the rest is refused by the base contract. Read carbon_ladder for the level's surfaces and bounds, fix the recipe and try again.",
    "library_query_invalid": "Send query as 1 to 200 characters of text, and challenge as the Challenge list gives it (carbon_challenges_v1__list).",
    "library_unavailable": "Your Graphite library could not be opened. Finish Set up your environment so your runner profile is written, then try again.",
    "limit_out_of_bounds": "Send 1 to 100, or omit it for 50.",
    "literature_fetch_failed": "arXiv could not be reached, so the hunt ended where it was; that is not a verdict on any paper. The Planner went on with the cards you have. Hunt again in a later campaign.",
    "literature_pack_missing": "The shared card pack this Carbon ships is missing or differs from its pinned digest. Re-run the installer with --update, then launch or resume.",
    "malformed_submission": "The validator could not read the submission's identity fields. Check that the intake address serves this Carbon version, then submit again; the frozen candidate is kept.",
    "miner_ceiling_reached": "The agent reached a ceiling you set - money, attempts, trials or time - so it stopped there; nothing past it was reserved or sent. Launch a new campaign with a larger ceiling to go further.",
    "miner_differs_from_campaign": "The hotkey in your runner profile is not the one this campaign was launched with. Use that hotkey's profile, or launch a new campaign.",
    "model_provider_auth_credential": "Your model provider refused the key. Set a working key under Set up, Inference, then Resume.",
    "model_provider_context_limit": "Your model provider refused the agent's request as longer than the model accepts. Choose a model with a longer context, or launch a new campaign.",
    "model_provider_credential_not_configured": "No key file is configured for this campaign's model provider. Add it under Set up your environment (carbon_setup_inference), then resume.",
    "model_provider_credential_unusable": "The model provider key file cannot be used (owner-only regular file required). Fix it under Set up your environment, then resume.",
    "model_provider_endpoint_not_configured": "Configure this provider's endpoint under Set up your environment (carbon_setup_inference) first.",
    "model_provider_invalid_request": "Your model provider rejected the agent's request as invalid. Choose another model, or launch a new campaign.",
    "model_provider_quota_exhausted": "Your model provider says your account's quota or credit is used up. Add credit with the provider, then Resume.",
    "model_provider_rate_limited": "Your model provider rate-limited the agent. Wait, then Resume.",
    "model_provider_required": "Name the provider for this model or these settings (carbon_options lists them).",
    "model_provider_server_unavailable": "Your model provider was unavailable. Resume later; nothing was charged for that call.",
    "model_provider_transient_server": "Your model provider failed the agent's call with a server error. Reconcile, then Resume; if it repeats, try again later or choose another model.",
    "model_provider_unknown": "Your model provider did not answer the agent's call in time, or its answer could not be read. Reconcile, then Resume; if it repeats, lower the max output per reply or choose a faster model.",
    "model_provider_unreachable": "Your model provider could not be reached from this machine (no connection or no such host). Check the network, then Resume.",
    "model_selection_needs_the_autonomous_agent": "A model is only for an agent that calls one: send agent=graphite, or omit the model fields.",
    "model_selection_refused": "Send a model and settings within the provider's bounds (carbon_options lists them).",
    "no_interrupted_practice": "This campaign has no interrupted practice to send again: its last refusal is not a practice's operation_interrupted, or that practice's request was not recorded. Observe the campaign, then practise (carbon_practice) with the recipe you want.",
    "no_submitted_result": "No submit of this campaign reached a validator yet, so there is no grade to read. If a submit was refused, its reason is the campaign's last refusal (observe, or the Submission tab): fix that and submit.",
    "non_finite_value": "The candidate's recipe holds NaN, Infinity or a number too large to be finite, which validators refuse. Nothing was evaluated; the frozen candidate is kept.",
    "not_a_provider_call": "This operation is not a model call; reconcile it through its own path.",
    "not_a_workspace_run": "run_output reads run_python and run_julia runs; the campaign view shows practice trials (carbon_campaign_view).",
    "not_found": "The validator holds no submission of this candidate for your hotkey. Submit again; the frozen candidate is kept.",
    "not_uncertain": "This call's outcome is known; there is nothing to settle.",
    "note_kind_unknown": "Send hypothesis, plan, observation or reply.",
    "note_not_retained": "The note could not be kept in the campaign's journal; nothing was written. Observe the campaign, then try again.",
    "operation_interrupted": "The operation stopped before it finished, most likely because the process running it exited. Observe the campaign, then try again; reconcile first if it asks for reconciliation.",
    "operation_not_completed": "The request did not complete. Observe the campaign: its state and last refusal say what happened. Then try again.",
    "operation_replay_conflict": "This key already names a different request. Send that request unchanged to replay it, or use a new key.",
    "operation_unavailable": "This owner has no such operation.",
    "over_compute_budget": "This recipe's calculated cost is over the Challenge's compute budget. Make it cheaper (fewer steps, members or parameters), practise it, and freeze that recipe instead; carbon_budget_status shows the cost and the ceiling.",
    "oversized_submission": "The candidate's recipe is larger than this validator accepts. Nothing was evaluated; the frozen candidate is kept.",
    "paused_for_handover": "Paused for a moment so the Control Center could take this campaign over from the background supervisor running it; the Control Center resumes it on its own once it has it. If it stays paused, resume it.",
    "paused_when_supervisor_closed": "The Control Center (or the supervisor running this campaign) closed, so the campaign was paused, not stopped. Resume it to continue.",
    "peer_header_invalid": "Contact the validator's operator to fix its proxy connection, then retry.",
    "plan_document_required": "Send plan_document as a JSON object, as carbon_plan_get returns a plan.",
    "plan_invalid": "The plan cites a card that is unknown or banned, leaves out a pinned card, or is for another Challenge. Read it (carbon_plan_get), correct it and save it (carbon_plan_edit), change your pins and bans, or launch it on its own Challenge.",
    "plan_not_found": "No plan in your library has that digest. List your plans (carbon_plan_list) and send one of their digests, or omit plan to have the Planner write one.",
    "practice_campaign_read_only": "This campaign was practised without registering. It stays readable, but its practice identity is not your hotkey: launch a new campaign to practise, freeze and submit with your registration.",
    "practice_candidate_failed": "Your graph or recipe reached a limit of the practice worker (its memory or its time) or failed while it ran. This is the recipe's own limit, not an infrastructure problem: the attempt's reservation is used (the trial counts) and nothing was scored. Make it lighter and practise again.",
    "practice_could_not_run": "The practice did not finish: it stopped on an infrastructure problem (the build or a step around it; not your recipe), so no result was made and nothing counts against you. Practise again; if it repeats, the campaign's operation folder holds a failure file naming the stage, and a report of it (Report a problem in the guide) lets Carbon fix it. A host problem such as Docker or the worker images is named in its own message, not this one.",
    "practice_host_too_small": "This machine is too small for the practice worker: Docker must see at least 17 GiB of memory and 4 CPUs (the supported machine has 32 GB of RAM). Nothing ran and nothing counts against you. Practise on a bigger machine. `docker info` shows what Docker sees (MemTotal, NCPU).",
    "practice_identity_malformed": "Your practice identity file is damaged. Choose Practise without registering again at Setup's first step (carbon_setup_practice), then Review.",
    "practice_identity_mismatch": "Your practice identity is not the one your setup recorded. Choose Practise without registering again at Setup's first step (carbon_setup_practice), then Review.",
    "practice_identity_missing": "Your practice identity file is missing. Choose Practise without registering again at Setup's first step (carbon_setup_practice), then Review; campaigns made with the old one stay readable.",
    "practice_identity_not_owner_only": "Your practice identity file must be readable by you alone: run chmod 600 on it (it is in your setup folder), then try again.",
    "practice_mode_invalid": "Send mode as full (the default) or smoke, or omit it.",
    "practice_result_required": "Practice this recipe first; only a practiced recipe can be frozen and submitted.",
    "practice_time_budget_reached": "The full practice ran to the practice time budget and ended without a result, so this recipe is too heavy to practise in full here. Run a smoke practice of the same recipe (carbon_practice {campaign, strategy, hypothesis, mode: smoke}): it runs with its training steps truncated to fit the budget, and a PASSED smoke practice lets that exact recipe be frozen. The validator still rebuilds it in full.",
    "profile_changed_since_launch": "Something this campaign was frozen with has changed in your runner profile since launch (the accepted revision, its images, the hotkey or the research guidance), so it cannot continue under this profile. Launch a new campaign; this one stays readable and can be stopped.",
    "profile_differs_from_request": "The runner profile changed after this request was admitted, or the Control Center and your agent use different profiles. Use one profile, then send the request again.",
    "protected_material_in_result": "Carbon withheld this tool result because it named material an agent is never shown; the request itself was not wrong. Use another source for what you needed; if the result was Carbon's own public document, report the campaign and the marker classes its refusal record names.",
    "provider_charge_invalid": "The retained provider charge is malformed; check the provider's own usage record before this campaign makes another call.",
    "rate": "The validator intake is limiting requests from your address. Wait a minute, then submit again; the frozen candidate is kept.",
    "readback_unavailable": "This could not be read back. Nothing was changed. Reload the page; if it persists, restart the Control Center.",
    "receipt_block_missing": "The validator could not date this submission. Submit again; the frozen candidate is kept.",
    "recommit_boolean_required": "Send recommit as true or false.",
    "reconciliation_required": "Work may have been dispatched and its outcome is unknown. Reconcile the campaign (halt with action=reconcile) before anything else runs.",
    "registration_check_failed": "Your hotkey's registration could not be confirmed on the subnet. Check it is registered (carbon_onboarding status) and the chain is reachable, then try again.",
    "registration_required": "This needs a hotkey registered on the subnet and your signer. Register it in your own wallet tooling (carbon_onboarding_prepare gives the unsigned call), confirm it at Setup's first step (carbon_setup_begin), start your signer, then Review and launch again (carbon_setup_review) and try again or resume. Practice campaigns you ran without registering stay readable.",
    "registration_unreadable": "The chain could not be read. Try again shortly; nothing was started.",
    "registration_wrong_network": "Your profile points at another network. Set up your environment again for Carbon's subnet (carbon_setup_status), then resume.",
    "remote_setup_unavailable": "Your remote GPU setup does not match this campaign, or cannot be used. Check it under Set up your environment, Compute, then try again.",
    "reply_to_only_for_replies": "Send reply_to only with note_kind=reply.",
    "reply_to_unknown_message": "Reply to a sequence the miner's messages listed (carbon_messages).",
    "request_changed": "The retained request differs from the one reserved; keep the campaign as it is and report it.",
    "research_calls_in_flight": "Research calls of this session are still running. Detach when they return.",
    "research_dispatch_disabled": "Research dispatch is disabled in this runner profile. Enable it, then resume.",
    "research_launch_replay_conflict": "This key already launched a different request. If your setup changed since (a profile rewrite changes what a launch carries), launch with a new key; otherwise send that request unchanged to replay it.",
    "research_profile_mismatch": "Omit profile, or send the profile_id of the runner profile this server or Control Center was started with.",
    "research_profile_unavailable": "Your runner profile is missing, disabled or cannot be read. Check it under Set up your environment (carbon_setup_status), or check the profile this server was started with, then try again.",
    "research_review_changed": "Your setup changed since the review you sent. Review again (carbon_setup_review) and send the review digest it gives.",
    "research_run_unavailable": "Use the id your launch returned for one of your own campaigns.",
    "research_runtime_interface_unavailable": "This runner profile names a runtime the runner cannot assemble. Set up your environment again, then resume.",
    "research_share_invalid": "Send research_share as a number from 0 to 1, or omit it for 0.10.",
    "research_share_reached": "The research stages used the share of your budget you set, so they stopped there and the build went on. Launch again with a larger research_share to research longer.",
    "research_share_too_small": "Your research share cannot pay for one model call: each call reserves its most possible cost (the model's whole output and its whole input window unless you cap max_output_tokens or max_input_tokens in model_settings) before it is sent, so this research would send nothing. Raise your provider_nanodollars or provider_attempts ceiling, raise research_share, cap the model's output or input window, or launch BUILD.",
    "research_task_id_required": "Send rtsk_ and 64 hex digits, from the run's start_research_task result.",
    "retired_grant_campaign": "This campaign takes no new work. Observe or stop it, and launch a new one.",
    "retry_interrupted_boolean_required": "Send retry_interrupted as true or false.",
    "run_output_unavailable": "Send a finished run of this campaign; the run may still be going (get_research_result shows it).",
    "runner_profile_missing": "No runner profile is at that path: an update sets it aside when its compute check no longer matches this install. Re-check compute (carbon_setup_recheck {confirm: true}, or Compute in the Control Center's setup), then review; the profile is written again.",
    "runner_profile_unusable": "Your runner profile could not be read, or it does not validate. Check the --configuration path, or write it again under Set up your environment.",
    "runtime_unavailable": "This host cannot run the campaign's accepted worker images right now: Docker is not running, or an image is missing. Start Docker, or re-run the installer, then try again.",
    "same_recipe_already_submitted": "You already submitted this exact recipe and it was graded on the current exam set, so it was not graded again and this final exam is still unused. Its result is the one shown where you first submitted it (Check for result reads it again). Your frozen candidate is kept. To use this exam, submit a different recipe (a new campaign, since this one keeps its frozen candidate), or wait for a new exam set: then this same recipe is graded again.",
    "session_unavailable": "This campaign has no prepared authenticated session yet. Resume the campaign once so it is prepared, then attach.",
    "settlement_journal_invalid": "The immutable settlement journal is corrupt or conflicts with this call; keep the campaign stopped and review its retained records.",
    "signer_invalid_signature": "Your signer's signature did not verify, so nothing it signed was used. Restart carbon-miner-signer, then try again.",
    "signer_not_running": "Start carbon-miner-signer for your hotkey, then try again. Nothing was signed. Keep the signer running until your result shows reconstructed: a submit is only queued until then, and stopping the signer first loses it.",
    "signer_protocol": "Something other than carbon-miner-signer answers on the signer socket. Stop it and start carbon-miner-signer, then try again.",
    "signer_refused": "Your signer declined the request. Check it, then try again.",
    "signer_timeout": "Your signer did not answer in time. Check it, then try again.",
    "signer_unavailable": "Your signer did not sign the submission: it is not running, or it declined. Start carbon-miner-signer for your registered hotkey, then submit again; the frozen candidate is kept.",
    "signer_wrong_hotkey": "Your signer holds a different hotkey than the registered miner. Start it with the registered hotkey, then try again.",
    "smoke_practice_unavailable": "This Challenge offers no smoke practice. Practise the recipe in full (omit mode), or lighten it so its full practice fits the budget.",
    "snapshot_unavailable": "The validator cannot read the chain right now; that is on its side. Submit again in a few minutes; the frozen candidate is kept.",
    "snapshot_unknown": "The validator no longer holds the chain snapshot the request named. Submit again: the request is rebuilt on a fresh snapshot. The frozen candidate is kept.",
    "status_fields": "The intake does not take the status request this Carbon sends; the frozen candidate is kept. Check that the intake address serves this Carbon version, then submit again.",
    "strategy_bom": "The validator refused a recipe that starts with a byte-order mark. Nothing was evaluated; the frozen candidate is kept. Report it: Carbon never writes one.",
    "strategy_json_invalid": "Send the recipe as a JSON object.",
    "strategy_names_another_challenge": "Send a strategy whose challenge_id is the challenge you name.",
    "strategy_nesting_too_deep": "The candidate's recipe nests more deeply than this validator accepts. Nothing was evaluated; the frozen candidate is kept.",
    "strategy_not_json": "The validator could not read the recipe as JSON. Nothing was evaluated; the frozen candidate is kept. Report it: Carbon writes its recipes as JSON.",
    "strategy_not_object": "The validator refused a recipe that is not a JSON object. Nothing was evaluated; the frozen candidate is kept.",
    "strategy_not_utf8": "The validator could not read the recipe as UTF-8 text. Nothing was evaluated; the frozen candidate is kept. Report it: Carbon writes its recipes as UTF-8.",
    "strategy_object_required": "Send the recipe as a JSON object.",
    "submission_fields": "The intake does not take the submission this Carbon sends, so nothing was evaluated; the frozen candidate is kept. Check that the intake address serves this Carbon version, then submit again.",
    "submission_policy_invalid": "Restore the campaign’s original frozen launch records; this policy cannot change on resume.",
    "submission_retained_by_policy": "This launch retains candidates without commitment or validator submission. Launch a separate campaign to submit.",
    "task_left_running": "A research task was left RUNNING by an earlier session. Attach with --cleanup-only (carbon-mcp --configuration PROFILE --campaign ID --cleanup-only) to observe and cancel it, then reconcile the campaign (halt with action=reconcile).",
    "the_agent_selects_in_this_campaign": "Carbon's agent selects in this campaign; freeze and submit are its. Launch with agent=none to select yourself.",
    "time_limit_reached": "The practice needed more time than the campaign's time limit had left, so it did not start; it is your own limit, not a failure, and nothing past it was reserved. Launch a new campaign with a larger budget.elapsed_seconds (or none), or leave more of the time for practice.",
    "too_many_pins": "You pinned more cards than one plan can consider (64), and the Planner must consider each pin. Unpin some (carbon_library_unpin), or launch BUILD with a plan from your library, then launch again.",
    "tool": "The intake does not take the request this Carbon sends, so nothing was evaluated; the frozen candidate is kept. Check that the intake address serves this Carbon version, then submit again.",
    "toolbox_include_invalid": "Send include as catalog, families, or catalog,families for those lists in full, or omit it for the compact answer.",
    "unknown_experiment": "Send a practice run id from the campaign view's experiments, or omit it for the latest.",
    "unknown_model_provider": "Send a provider carbon_options lists.",
    "unknown_practice_case": "Send a public PRACTICE case id from the campaign view's per_case.case_ids, or omit it for the first.",
    "unresolved_operation": "An earlier operation's outcome is unknown. Reconcile the campaign (halt with action=reconcile); nothing is resent blindly.",
    "usage_exceeds_reservation": "The provider reported token usage beyond what the call reserved, and nothing Carbon recorded shows its charge fits the reservation, which is all the ledger can book; reconcile it against the provider's own usage record before this campaign makes another call.",
    "used_feedback_boolean_required": "Send used_feedback as true or false.",
    "version_closed": "This submission was still queued when its version of the Challenge closed, so it was closed, not graded, and nothing was charged. This is not a result about your model.",
    "withdrawn_by_miner": "You withdrew this submission while it was still queued: it was not built or graded and used no try. Your frozen candidate is kept: submit again when ready. Each withdrawal of the same model counts toward the validator's limit of retries for that model on this exam.",
    "withdrawn_when_supervisor_closed": "The Control Center closed before this request started, so it was withdrawn and nothing ran. Send it again.",
}
WORDS_GRADE = {
    "CANDIDATE_FAILED": "counted as your try: your model's own run failed while it was being graded",
    "CROWN_HELD_FOR_REVIEW": "counted as your try: its crown change is held for review",
    "FAILED_INFRA": "the validator's side failed: it is not your result, and a counted slot is given back",
    "GRADED": "counted as your try",
    "NOT_GRADED": "not graded: the slot was given back and nothing was charged",
    "QUEUED": "waiting at this validator: not built or not graded yet",
    "RECONSTRUCTION_FAILED": "your recipe's own run failed before it could be graded: nothing was graded",
    "ROUND_LIMIT_REACHED": "not graded: your key's graded exams for this round or this day were already used",
    "SUPERSEDED_BY_OWN_LATER_SUBMIT": "not graded: your own later submission took this round's graded slot",
    "WITHDRAWN_BY_MINER": "withdrawn by you while it was still queued: not built, not graded, and it used no try",
}
# --- words:end ---


def _utc(ns=None, seconds=None):
    value = ns / 1e9 if seconds is None else seconds
    return datetime.datetime.fromtimestamp(int(value), datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _words(code):
    """The miner-facing sentence for a closed code, or None: the two Launchpad tables, word for word."""
    if code in WORDS_NEXT:
        return WORDS_NEXT[code]
    if code in WORDS_GRADE:
        return (
            "Grade state: "
            + WORDS_GRADE[code][:1].upper()
            + WORDS_GRADE[code][1:]
            + "."
        )
    return None


def _vocab_code(*candidates):
    for value in candidates:
        if type(value) is str and _words(value) is not None:
            return value
    return None


class Root:
    """The places read. A missing source is said (None / empty), never guessed."""

    def __init__(self, ledger, markers=None, owed=None, queue_url=None, board=None):
        self.ledger = Path(ledger)
        self.markers = None if markers is None else Path(markers)
        self.owed = None if owed is None else Path(owed)
        self.queue_url = queue_url
        self.board = None if board is None else Path(board)

    def db(self):
        try:
            db = sqlite3.connect(
                self.ledger.resolve().as_uri() + "?mode=ro",
                uri=True,
                timeout=SQL_TIMEOUT_S,
            )
            db.execute("PRAGMA query_only=ON")
            return db
        except sqlite3.Error as error:
            raise Refused("ledger_unreadable") from error

    def marker(self, task):
        """Only the marker's `state` and `code`, and only as short plain tokens; the rest of a marker is never read on."""
        if self.markers is None or not TASK_ID.fullmatch(task):
            return {}
        try:
            body = json.loads((self.markers / (task + ".json")).read_bytes())
        except (OSError, ValueError):
            return {}
        if type(body) is not dict:
            return {}
        return {
            key: body[key]
            for key in ("state", "code")
            if type(body.get(key)) is str
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", body[key])
        }


def _owed(path):
    """V2's `owed_id TAB task_id TAB state TAB new_task_id` file -> {task_id: [owed rows]}; a malformed row is dropped."""
    out = {}
    if path is None:
        return out
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        parts = line.split("\t")
        if (
            len(parts) != 4
            or not OWED_ID.fullmatch(parts[0])
            or not TASK_ID.fullmatch(parts[1])
        ):
            continue
        if parts[2] not in OWED_STATES or not (
            parts[3] == "-" or TASK_ID.fullmatch(parts[3])
        ):
            continue
        row = {"owed_id": parts[0], "state": parts[2]}
        if parts[3] != "-":
            row["rerun_task_id"] = parts[3]
        out.setdefault(parts[1], []).append(row)
    return out


def _queue(root):
    """The door's public queue document (v4, else v3), rebuilt field by field; None when it cannot be read."""
    if not root.queue_url:
        return None
    document = None
    for suffix in ("/v4", "/v3"):
        try:
            with urllib.request.urlopen(
                root.queue_url.rstrip("/") + suffix, timeout=QUEUE_TIMEOUT_S
            ) as answer:
                raw = answer.read(MAX_BYTES + 1)
            found = json.loads(raw) if len(raw) <= MAX_BYTES else None
        except (OSError, ValueError):
            continue
        if type(found) is dict and "rows" in found:
            document = found
            break
    if document is None:
        return None
    wait = document.get("wait_24h") if type(document.get("wait_24h")) is dict else {}
    rows = []
    for row in document.get("rows") or ():
        if (
            type(row) is dict
            and type(row.get("position")) is int
            and type(row.get("in_queue_s")) is int
        ):
            short = row.get("hotkey")
            state = row.get("state")
            rows.append(
                {
                    "position": row["position"],
                    "hotkey": (
                        short
                        if type(short) is str and SHORT_FORM.fullmatch(short)
                        else None
                    ),
                    "state": (
                        state
                        if type(state) is str
                        and len(state) <= 40
                        and state.isprintable()
                        else None
                    ),
                    "in_queue_s": row["in_queue_s"],
                }
            )
    door = document.get("door_state")
    shown_wait = {
        k: wait[k]
        for k in ("verdicts", "median_s", "p90_s")
        if type(wait.get(k)) in (int, type(None))
    }
    if wait.get("reason") == "fewer_than_5_verdicts_in_24h":
        shown_wait["reason"] = wait["reason"]
    return {
        "door_state": (
            door
            if type(door) is str and len(door) <= 40 and door.isprintable()
            else None
        ),
        **{
            key: document[key]
            for key in (
                "waiting_to_build",
                "building_now",
                "waiting_to_grade",
                "grading_now",
            )
            if type(document.get(key)) is int
        },
        "wait_24h": shown_wait,
        "as_of": (
            document["as_of"]
            if type(document.get("as_of")) is str and UTC.fullmatch(document["as_of"])
            else None
        ),
        "rows": rows,
    }


def _board(root):
    """{hotkey: {rank, total, status}} from the public launch board's ladder; {} when it cannot be read."""
    if root.board is None:
        return {}
    try:
        document = json.loads(root.board.read_bytes())
    except (OSError, ValueError):
        return {}
    out = {}
    for row in (document.get("ladder") or ()) if type(document) is dict else ():
        if (
            type(row) is not dict
            or type(row.get("hotkey")) is not str
            or not SS58.fullmatch(row["hotkey"])
        ):
            continue
        shown = {}
        if type(row.get("rank")) is int and 1 <= row["rank"] <= 10**6:
            shown["rank"] = row["rank"]
        if type(row.get("total")) in (int, float) and 0 <= row["total"] <= 1:
            shown["total"] = round(float(row["total"]), 3)
        if (
            type(row.get("status")) is str
            and len(row["status"]) <= 40
            and row["status"].isprintable()
        ):
            shown["status"] = row["status"]
        out[row["hotkey"]] = shown
    return out


def _slot(db, task):
    """`(state, status)` of the task's latest graded-exam slot row (`exam_graded`), or `(None, None)`: nothing is read but
    those two tokens, and a ledger without the table says nothing rather than failing.
    """
    try:
        row = db.execute(
            "SELECT state, status FROM exam_graded WHERE submission_id=? AND kind='GRADED' ORDER BY id DESC LIMIT 1",
            (task,),
        ).fetchone()
    except sqlite3.Error:
        return None, None
    return (row[0], row[1]) if row else (None, None)


def _grade_state(marker, slot, latest):
    """`(state, code, charged, slot_given_back)`: the validator's own grade state of one task, the way the receiver derives it
    (`direct_intake._grade_state_v4`): from the auto-grade marker's state and the task's exam slot row. A task that was only
    admitted is QUEUED; it is never "succeeded" because the ledger holds an admission.
    """
    mstate, mcode = marker.get("state"), marker.get("code")
    slot_state, slot_status = slot
    if not mstate:
        if slot_status == "FAILED_INFRA" or latest in ("FAILED_INFRA", "UNAVAILABLE"):
            return "FAILED_INFRA", "FAILED_INFRA", "no", "yes"
        if latest == "REFUSED":
            return "REFUSED", None, "not stated", "not stated"
        return "QUEUED", "QUEUED", "not stated", "not stated"
    if mstate == "CANDIDATE_FAILED":
        return "CANDIDATE_FAILED", "CANDIDATE_FAILED", "yes", "not stated"
    if mstate == "DUPLICATE":
        return "GRADED", "GRADED", "yes", "not stated"
    if mstate == "FAILED":
        return "FAILED_INFRA", "FAILED_INFRA", "no", "yes"
    if mstate == "VERSION_CLOSED":
        return "NOT_GRADED", "version_closed", "no", "yes"
    if mstate == "GRADED" and mcode in LIMIT_CODES:
        return "ROUND_LIMIT_REACHED", mcode, "no", "not stated"
    if slot_state in ("RESERVED", "COUNTED"):
        return "GRADED", "GRADED", "yes", "not stated"
    if slot_state == "RELEASED" and slot_status == "SLOT_RETURNED":
        return "GRADED", "GRADED", "no", "yes"
    return "NOT_GRADED", "NOT_GRADED", "no", "yes"


def _task(root, db, task, owed, *, detail):
    rows = db.execute(
        "SELECT at_ns, kind, code, state, hotkey FROM attempts WHERE submission_id=? ORDER BY seq",
        (task,),
    ).fetchall()
    if not rows:
        return None
    withdrawn = (
        db.execute(
            "SELECT 1 FROM miner_withdrawals WHERE submission_id=?", (task,)
        ).fetchone()
        is not None
    )
    marker = root.marker(task)
    marker_code = marker.get("code")
    stopped = marker_code in MARKER_TO_CODE
    latest = next((row[1] for row in reversed(rows) if row[1] in TERMINAL_KINDS), None)
    if withdrawn or stopped or marker.get("state") == "WITHDRAWN_BY_MINER":
        state, code = "CANCELLED", _vocab_code(
            MARKER_TO_CODE.get(marker_code), rows[-1][2], rows[-1][3]
        )
        charged, given_back = "no", "not stated"
        withdrawn = withdrawn or marker.get("state") == "WITHDRAWN_BY_MINER"
    else:
        slot = _slot(db, task)
        state, code, charged, given_back = _grade_state(marker, slot, latest)
        if state == "QUEUED" and rows[-1][3] == BUILD_REQUEUED and slot == (None, None):
            # a capped build chain: its only trace is the requeue, and it will not be built again
            state, code, charged, given_back = (
                BUILD_REQUEUED,
                None,
                "not stated",
                "not stated",
            )
        if code is None:
            code = _vocab_code(rows[-1][2], rows[-1][3])
    shown = {
        "task_id" if TASK_ID.fullmatch(task) else "entry_id": task,
        "submitted_utc": _utc(rows[0][0]),
        "last_change_utc": _utc(rows[-1][0]),
        "state": state,
        "outcome_code": code if code is None or _words(code) else None,
        "charged": charged,
        "slot_given_back": given_back,
        "withdrawn": withdrawn,
        "owed": owed.get(task, []),
    }
    if detail:
        if shown["owed"]:
            shown["reason"] = OWED_REASON
        elif state == BUILD_REQUEUED:
            shown["reason"] = BUILD_REQUEUED_REASON
        else:
            shown["reason"] = (
                None if shown["outcome_code"] is None else _words(shown["outcome_code"])
            )
    return shown


def _own_rows(queued, hotkey):
    if not queued or type(hotkey) is not str or len(hotkey) <= 8:
        return []
    short = hotkey[:4] + "…" + hotkey[-4:]
    return [row for row in queued["rows"] if row["hotkey"] == short]


def resolve_hotkeys(db, text):
    """Hotkeys matching a full address or `first4...last4`: at most two come back (ambiguity, never a list)."""
    short = SHORT.fullmatch(text)
    if SS58.fullmatch(text):
        rows = db.execute(
            "SELECT DISTINCT hotkey FROM attempts WHERE hotkey=? LIMIT 2", (text,)
        ).fetchall()
    elif short:
        rows = db.execute(
            "SELECT DISTINCT hotkey FROM attempts WHERE substr(hotkey,1,4)=? AND substr(hotkey,-4)=? LIMIT 2",
            (short.group(1), short.group(2)),
        ).fetchall()
    else:
        raise Refused("hotkey_form")
    return [r[0] for r in rows if type(r[0]) is str]


def _own_allowed():
    if OWN_READ != "open":
        raise Refused("own_fields_off")


def lookup(root, name, argument=None):
    """One question: `hotkey`, `task`, `entry`, `public` (queue|board). Returns the document (not yet checked)."""
    if name == "public":
        if argument == "queue":
            return {"asked": "public queue", "queue": _queue(root)}
        if argument == "board":
            ladder = sorted(
                (
                    {**value, "hotkey": key[:4] + "…" + key[-4:]}
                    for key, value in _board(root).items()
                    if "rank" in value
                ),
                key=lambda value: value["rank"],
            )
            return {"asked": "public board", "board": ladder[:25]}
        raise Refused("public_form")
    if name == "verify":
        raise Refused("verify_not_built")
    _own_allowed()
    owed = _owed(root.owed)
    queued = _queue(root)
    db = root.db()
    try:
        if name in ("task", "entry"):
            if name == "task":
                if not TASK_PREFIX.fullmatch(argument or ""):
                    raise Refused("task_form")
                found = db.execute(
                    "SELECT DISTINCT submission_id FROM attempts WHERE submission_id LIKE ? LIMIT 2",
                    (
                        (
                            argument
                            if argument.startswith("rtsk_")
                            else "rtsk_" + argument
                        )
                        + "%",
                    ),
                ).fetchall()
                task = (
                    found[0][0]
                    if len(found) == 1 and TASK_ID.fullmatch(str(found[0][0]))
                    else None
                )
                if task is None and len(found) == 1:
                    raise Refused("task_not_found")
                if len(found) != 1:
                    raise Refused("task_not_found_or_ambiguous")
            else:
                if not ENTRY_ID.fullmatch(argument or ""):
                    raise Refused("entry_form")
                task = argument
            shown = _task(root, db, task, owed, detail=True)
            if shown is None:
                raise Refused("entry_not_found")
            hotkey = db.execute(
                "SELECT hotkey FROM attempts WHERE submission_id=? LIMIT 1", (task,)
            ).fetchone()
            return {
                "asked": name,
                "task": shown,
                "queue_rows": _own_rows(queued, hotkey[0] if hotkey else None),
                "board": _board(root).get(hotkey[0]) if hotkey else None,
                "not_available": list(NOT_AVAILABLE),
            }
        if name == "hotkey":
            keys = resolve_hotkeys(db, argument or "")
            if len(keys) != 1:
                raise Refused(
                    "hotkey_not_found"
                    if not keys
                    else "hotkey_ambiguous_send_more_characters"
                )
            ids = db.execute(
                "SELECT submission_id, MIN(seq) FROM attempts WHERE hotkey=? AND submission_id LIKE 'rtsk\\_%' ESCAPE '\\' "
                "GROUP BY submission_id ORDER BY MIN(seq) DESC LIMIT ?",
                (keys[0], MAX_TASKS),
            ).fetchall()
            tasks = [
                shown
                for shown in (
                    _task(root, db, i[0], owed, detail=False)
                    for i in ids
                    if TASK_ID.fullmatch(str(i[0]))
                )
                if shown
            ]
            return {
                "asked": "hotkey",
                "tasks": tasks,
                "queue_rows": _own_rows(queued, keys[0]),
                "board": _board(root).get(keys[0]),
                "not_available": list(NOT_AVAILABLE),
            }
        raise Refused("subcommand_form")
    finally:
        db.close()


def _check(value, section):
    allowed = ALLOWED_FIELDS.get(section)
    if allowed is None or type(value) is not dict or set(value) - allowed:
        raise Refused("not_on_the_allow_list")


def _scan(value, key=None):
    """Refuse secret-shaped text (a seed, key or long digest) anywhere but the named id fields."""
    if type(value) is str:
        if key in ID_FIELDS:
            if not TASK_ID.fullmatch(value):
                raise Refused("secret_shaped_text")
        elif LONG_HEX.search(value) or LONG_TOKEN.search(value):
            raise Refused("secret_shaped_text")
    elif type(value) is dict:
        for name, inner in value.items():
            _scan(inner, name)
    elif type(value) in (list, tuple):
        for inner in value:
            _scan(inner, key)


def finish(document):
    """The document as compact JSON, only when every section matches `ALLOWED_FIELDS` and nothing is secret-shaped;
    over `MAX_BYTES` is refused, never cut."""
    _check(document, "lookup")
    tasks = list(document.get("tasks") or ())
    if document.get("task"):
        tasks.append(document["task"])
    for task in tasks:
        _check(task, "task")
        for row in task["owed"]:
            _check(row, "owed")
    for row in document.get("queue_rows") or ():
        _check(row, "queue_row")
    queue = document.get("queue")
    if queue is not None:
        _check(queue, "queue")
        _check(queue["wait_24h"], "wait_24h")
        for row in queue["rows"]:
            _check(row, "queue_row")
    board = document.get("board")
    for row in board if type(board) is list else ([board] if board else []):
        _check(row, "board")
    _scan(document)
    text = json.dumps(
        document, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise Refused("answer_too_large")
    return text


def parse_words(words):
    """`[subcommand, argument...]` -> (name, argument): exact patterns, nothing else; no option is ever accepted."""
    if not words or len(words) > 4 or any(w.startswith("-") for w in words):
        raise Refused("command_form")
    name, rest = words[0], words[1:]
    if name in ("hotkey", "task", "entry", "public") and len(rest) == 1:
        return name, rest[0]
    if name == "verify" and len(rest) == 3:
        return name, None
    raise Refused("command_form")


def parse_ssh_command(text):
    """`SSH_ORIGINAL_COMMAND` -> (name, argument): an optional leading `miner_lookup`, then one subcommand. The asker can
    never name a path, host or option; the operator's paths come from the config file the forced command names.
    """
    try:
        words = shlex.split(text or "")
    except ValueError as error:
        raise Refused("command_form") from error
    if words and words[0] == "miner_lookup":
        words = words[1:]
    return parse_words(words)


def _audit(path, name, asked, size):
    """One line per call, append-only, 0600: UTC, subcommand, what was asked about, bytes out. No output content."""
    if not path:
        return
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            now = datetime.datetime.now(datetime.UTC).timestamp()
            handle.write(f"{_utc(seconds=now)}\t{name}\t{asked}\t{size}\n")
    except OSError:
        pass


def _config(path):
    try:
        body = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as error:
        raise Refused("config_unreadable") from error
    allowed = {"ledger", "markers", "owed_tasks", "queue_url", "board", "audit"}
    if (
        type(body) is not dict
        or set(body) - allowed
        or type(body.get("ledger")) is not str
    ):
        raise Refused("config_invalid")
    return body


def main(argv=None, env=None):
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=CONFIG_PATH)
    parser.add_argument(
        "--write-words",
        action="store_true",
        help="regenerate the word tables in this file",
    )
    parser.add_argument(
        "words", nargs="*", help="`ssh`, or one subcommand with its argument"
    )
    args = parser.parse_args(argv)
    if args.write_words:
        write_words(Path(__file__))
        return 0
    name, asked, text, code, audit = "unknown", "-", "", "refused", None
    try:
        config = _config(args.config)
        audit = config.get("audit")
        if args.words == ["ssh"]:
            name, argument = parse_ssh_command(env.get("SSH_ORIGINAL_COMMAND"))
        else:
            name, argument = parse_words(args.words)
        asked = argument if type(argument) is str and ASKED.fullmatch(argument) else "-"
        root = Root(
            config["ledger"],
            config.get("markers"),
            config.get("owed_tasks"),
            config.get("queue_url"),
            config.get("board"),
        )
        text = finish(lookup(root, name, argument))
        code = "ok"
    except Refused as refused:
        text, code = json.dumps({"refused": refused.code}), refused.code
    except sqlite3.Error:
        text, code = json.dumps({"refused": "ledger_unreadable"}), "ledger_unreadable"
    _audit(audit, name, asked, len(text.encode("utf-8")))
    sys.stdout.write(text + "\n")
    return 0 if code == "ok" else 2


# --- generator: the only place that imports the repository, and only from the command line ---
START = "# --- words:start (generated: python -m scripts.dev.miner_lookup --write-words) ---"
END = "# --- words:end ---"


def _literal(text):
    """A string literal as black writes it: double quotes unless that would need more escapes than single quotes."""
    if text.count('"') > text.count("'") and text.isprintable() and "\\" not in text:
        return "'" + text.replace("'", "\\'") + "'"
    return json.dumps(text, ensure_ascii=False)


def words_block():
    from scripts.dev.miner_launchpad import projection, supervisor

    lines = [START, "WORDS_NEXT = {"]
    lines += [
        f"    {json.dumps(k)}: {_literal(v)},"
        for k, v in sorted(supervisor.NEXT_ACTIONS.items())
    ]
    lines += ["}", "WORDS_GRADE = {"]
    lines += [
        f"    {json.dumps(k)}: {_literal(v)},"
        for k, v in sorted(projection.GRADE_STATE_WORDS.items())
    ]
    lines += ["}", END]
    return "\n".join(lines)


def write_words(path):
    text = path.read_bytes().decode("utf-8")
    start, end = text.index(START), text.index(END) + len(END)
    path.write_bytes((text[:start] + words_block() + text[end:]).encode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
