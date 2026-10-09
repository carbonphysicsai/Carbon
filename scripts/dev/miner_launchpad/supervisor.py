"""One long-lived supervisor owns a runner's campaign threads (LP-PROD-C).

A campaign's work - the launch that prepares it, Carbon's agent loop, a
miner's practice, freeze or submit - runs on a thread for minutes or hours.
Before this module that thread lived in whichever process received the
request, including a short-lived MCP stdio process: when the miner's client
exited, the thread died with it, a launch was left QUEUED with no frozen
manifest, and closing a client sent every live campaign an irreversible stop.

Now one process per runner database and principal supervises:

- **The Control Center**, while it runs, is the supervisor (`SUPERVISOR`).
  It starts its own requests on its own threads and drains everything other
  clients queue.
- **Otherwise a detached supervisor** (`DETACHED`) does: a client that queues
  work and finds no supervisor alive starts
  ``python -m scripts.dev.miner_launchpad.supervisor --configuration PROFILE``
  in a new session, so it outlives the client. It exits once nothing is
  queued and none of its threads is alive.
- **Clients** (`CLIENT`: every MCP door) never own a campaign thread. They
  run the operations table's gates, record what was admitted in the queue
  below, wake or start the supervisor, and observe.

Exactly one supervisor holds the lock for a runner database and principal at
a time: an OS lock (`controller.owner_lock`) in a directory beside the
database, released by the OS when its process exits. Only the holder starts
queued work, and only the holder recovers campaigns a dead process left
behind, because only then is every earlier holder known to be gone.

**A Control Center that starts while a detached supervisor holds the lock
takes over** (the handover): it holds a second OS lock, its presence, for as
long as it runs. A detached supervisor that sees it starts nothing more,
pauses Carbon's agent in each campaign it runs (`paused_for_handover`), lets
the miner's operations finish, then releases the lock and exits; the Control
Center takes the lock and resumes what was paused for it. Until then the
Control Center queues its own work like a client, and if it closes first,
what it admitted is withdrawn or paused, as closing it would pause what it
supervised.

The queue (`launchpad_dispatch`, in the runner's own database) holds what a
client admitted, not authority: the supervisor re-reads the runner profile,
refuses an item admitted under a different profile, and re-reads the chain for
a launch it rebuilds (`RunnerAdapter._recorded_launch`). A claimed item is
never started twice. One whose supervisor died is marked interrupted and never
replayed: the campaign's ledger, not the queue, says what may have been
dispatched. (A launch that died before it was prepared, with nothing
outstanding, is carried out again once, as a new item: nothing could have been
dispatched for it. See `RunnerAdapter._redispatch_stranded`.)

`INLINE` is the historical single-process behaviour, kept for fixtures and
tests that drive a host directly: it starts its own threads and recovers at
construction, but never re-dispatches.

Refusals that happen on a supervisor thread, where no caller can see them,
are kept as the campaign's `last_refusal`: a closed code, the next action
from `NEXT_ACTIONS`, and when (`refusal`). No exception text, provider
response or path is ever kept. A refusal returned to its caller stays the
caller's `{error}`; the same table, served as the refusal catalog
(`catalog`, `GET /api/v1/refusals`), says what to do next for any code.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import signal
import sys
import threading
import time
from pathlib import Path

INLINE, SUPERVISOR, DETACHED, CLIENT = "inline", "supervisor", "detached", "client"
ROLES = (INLINE, SUPERVISOR, DETACHED, CLIENT)
#: How often a supervisor looks for queued work when nothing wakes it.
POLL_SECONDS = 0.5
#: How long a detached supervisor stays with nothing queued and no live
#: thread before it exits.
IDLE_EXIT_SECONDS = 10.0
#: How long a starting (or re-arming) supervisor keeps trying for the lock.
#: A client's liveness probe holds it for microseconds; a supervisor holds it
#: for its whole life, so a few seconds tells the two apart.
ACQUIRE_SECONDS = 3.0
#: How long closing a supervisor waits for its paused threads to settle.
CLOSE_JOIN_SECONDS = 5.0

#: Queue item states. A QUEUED item is admitted and not started; RUNNING was
#: claimed by one supervisor; DONE never runs again.
QUEUED, RUNNING, DONE = "QUEUED", "RUNNING", "DONE"
#: The `last_refusal` a detached supervisor records on a campaign whose agent
#: it paused so a starting Control Center could take it over. Only a Control
#: Center resumes it; any other supervisor keeps the pause (D4).
HANDED_OVER = "paused_for_handover"
#: What a queue item carries out: the campaign's run (a launch or resume), or
#: one of a miner's operations. A commit runs here because the miner's signer
#: waits on its own terminal for the miner to confirm (LAUNCHPAD-ACCEPT-02).
OPERATIONS = ("run", "practice", "freeze_candidate", "submit", "commit")

#: Ledger control states in which some process was working when it last
#: wrote. Seen by a supervisor holding the campaign's free ownership lock,
#: they are stale: that process is gone.
IN_FLIGHT = frozenset(
    {
        "QUEUED",
        "RECONCILING",
        "RUNNING",
        "PAUSE_REQUESTED",
        "RESUME_REQUESTED",
        "STOPPING",
    }
)
TERMINAL = frozenset({"COMPLETED", "STOPPED"})

_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}|[A-Z][A-Z0-9_]{0,63}")

#: The next step for each refusal or interruption code a supervisor records,
#: and for every closed code either door answers. Closed: a code not listed
#: gets `FALLBACK_ACTION`, and the code itself is still shown, so a new code
#: from another slice reaches the miner before this table names it.
#:
#: The one source of next steps (W1): the browser's door (`controller.
#: error_body`), the MCP door (`operations.refusal`, which adds only the field
#: to correct), a campaign's `last_refusal` and the refusal catalog all read
#: this table, so one code has one next step whichever way the miner meets it.
#: Each step is fixed text; it names an MCP tool in parentheses where one
#: helps, as the Control Center's own steps do.
NEXT_ACTIONS = {
    # The campaign's own lock and state.
    "campaign_busy": (
        "Another session holds this campaign: an attached agent, the "
        "Control Center's tools, or an operation still running. Detach it "
        "(carbon_detach_campaign) or close the tools, then try again."
    ),
    "campaign_stopped": "This campaign is stopped. Launch a new one to continue.",
    "campaign_paused": "This campaign is paused. Resume it, then try again.",
    "campaign_complete": "This campaign is complete. Launch a new one to continue.",
    "reconciliation_required": (
        "Work may have been dispatched and its outcome is unknown. Reconcile "
        "the campaign (halt with action=reconcile) before anything else runs."
    ),
    "unresolved_operation": (
        "An earlier operation's outcome is unknown. Reconcile the campaign "
        "(halt with action=reconcile); nothing is resent blindly."
    ),
    # Why Reconcile would not settle a model call whose outcome is unknown
    # (LP-PROD-A's `research_agent.SETTLEMENT_REFUSALS`, reached through the
    # reconcile action since W2): A's own steps, as sentences, so the catalog
    # and a `last_refusal` name them. The reconcile's answer at either door
    # carries A's step itself (`runner.stepped`). The call stays unresolved.
    "operation_unavailable": "This owner has no such operation.",
    "not_a_provider_call": (
        "This operation is not a model call; reconcile it through its own path."
    ),
    "not_uncertain": "This call's outcome is known; there is nothing to settle.",
    "request_changed": (
        "The retained request differs from the one reserved; keep the campaign "
        "as it is and report it."
    ),
    "charge_exceeds_reservation": (
        "The provider reported a charge above the call's reservation, which the "
        "ledger cannot book; reconcile it against the provider's own usage "
        "record before this campaign makes another call."
    ),
    "usage_exceeds_reservation": (
        "The provider reported token usage beyond what the call reserved, and "
        "nothing Carbon recorded shows its charge fits the reservation, which "
        "is all the ledger can book; reconcile it against the provider's own "
        "usage record before this campaign makes another call."
    ),
    "call_in_flight": (
        "A model call of this campaign is still being admitted or in flight "
        "(it holds the campaign's provider-call lease), or this host cannot "
        "show that none is; settle once it has ended or its process has exited."
    ),
    "control_fenced": (
        "This is not the campaign's reconcile action: settle only from the "
        "reconcile action, under the campaign's owner lock and its current "
        "control generation."
    ),
    # Interruptions this module records.
    "operation_interrupted": (
        "The operation stopped before it finished, most likely because the "
        "process running it exited. Observe the campaign, then try again; "
        "reconcile first if it asks for reconciliation."
    ),
    "campaign_interrupted": (
        "The campaign stopped before it finished. Resume it; reconcile first "
        "if it asks for reconciliation."
    ),
    "paused_when_supervisor_closed": (
        "The Control Center (or the supervisor running this campaign) closed, "
        "so the campaign was paused, not stopped. Resume it to continue."
    ),
    "paused_for_handover": (
        "Paused for a moment so the Control Center could take this campaign "
        "over from the background supervisor running it; the Control Center "
        "resumes it on its own once it has it. If it stays paused, resume it."
    ),
    "withdrawn_when_supervisor_closed": (
        "The Control Center closed before this request started, so it was "
        "withdrawn and nothing ran. Send it again."
    ),
    # Launch and profile.
    "launch_choices_unrecorded": (
        "This launch was recorded before its choices were kept, so it cannot "
        "be restarted exactly. Stop it and launch again."
    ),
    "launch_record_differs": (
        "This launch's record no longer matches what was admitted. Stop it "
        "and launch again."
    ),
    "profile_differs_from_request": (
        "The runner profile changed after this request was admitted, or the "
        "Control Center and your agent use different profiles. Use one "
        "profile, then send the request again."
    ),
    "dispatch_configuration_changed": (
        "The runner profile changed after this request was admitted. Review "
        "it, then resume or send the request again."
    ),
    "profile_changed_since_launch": (
        "Something this campaign was frozen with has changed in your runner "
        "profile since launch (the accepted revision, its images, the hotkey "
        "or the research guidance), so it cannot continue under this profile. "
        "Launch a new campaign; this one stays readable and can be stopped."
    ),
    "carbon_updated_rerun_installer": (
        "Carbon in this checkout is not the revision your runner profile "
        "accepted: it was updated, or its worker image was rebuilt. Re-run the "
        "installer so your profile accepts this checkout and its images, then "
        "launch. Campaigns frozen under the earlier revision stay readable."
    ),
    "campaign_readback_unavailable": (
        "This campaign's records could not be read back consistently. Nothing "
        "was changed. Export its record if you need it, and launch a new "
        "campaign to continue."
    ),
    "campaign_read_failed": (
        "This campaign could not be read just now. Nothing was changed. Reload "
        "the page; if it persists, restart the Control Center."
    ),
    "operation_not_completed": (
        "The request did not complete. Observe the campaign: its state and "
        "last refusal say what happened. Then try again."
    ),
    "readback_unavailable": (
        "This could not be read back. Nothing was changed. Reload the page; if "
        "it persists, restart the Control Center."
    ),
    "research_profile_unavailable": (
        "Your runner profile is missing, disabled or cannot be read. Check it "
        "under Set up your environment (carbon_setup_status), or check the "
        "profile this server was started with, then try again."
    ),
    "research_dispatch_disabled": (
        "Research dispatch is disabled in this runner profile. Enable it, then resume."
    ),
    "research_runtime_interface_unavailable": (
        "This runner profile names a runtime the runner cannot assemble. "
        "Set up your environment again, then resume."
    ),
    "challenge_retired": (
        "This Challenge is retired. Launch a campaign on another "
        "(carbon_challenges_v1__list lists them)."
    ),
    # Registration and the miner's signer (operations._registered, SignerCode).
    "registration_required": (
        "Your hotkey is not registered on the subnet. Register it in your own "
        "wallet tooling (carbon_onboarding_prepare gives the unsigned call), "
        "confirm, then try again or resume."
    ),
    "registration_unreadable": (
        "The chain could not be read. Try again shortly; nothing was started."
    ),
    "registration_wrong_network": (
        "Your profile points at another network. Set up your environment "
        "again for Carbon's subnet (carbon_setup_status), then resume."
    ),
    "signer_not_running": (
        "Start carbon-miner-signer for your hotkey, then try again. Nothing was signed."
    ),
    "signer_refused": "Your signer declined the request. Check it, then try again.",
    "signer_wrong_hotkey": (
        "Your signer holds a different hotkey than the registered miner. "
        "Start it with the registered hotkey, then try again."
    ),
    "signer_timeout": "Your signer did not answer in time. Check it, then try again.",
    "signer_invalid_signature": (
        "Your signer's signature did not verify, so nothing it signed was "
        "used. Restart carbon-miner-signer, then try again."
    ),
    "signer_protocol": (
        "Something other than carbon-miner-signer answers on the signer "
        "socket. Stop it and start carbon-miner-signer, then try again."
    ),
    # The model provider key, from the runner profile.
    "model_provider_credential_not_configured": (
        "No key file is configured for this campaign's model provider. Add "
        "it under Set up your environment (carbon_setup_inference), then "
        "resume."
    ),
    "model_provider_credential_unusable": (
        "The model provider key file cannot be used (owner-only regular file "
        "required). Fix it under Set up your environment, then resume."
    ),
    # A miner's own journey (research_campaign).
    "the_agent_selects_in_this_campaign": (
        "Carbon's agent selects in this campaign; freeze and submit are its. "
        "Launch with agent=none to select yourself."
    ),
    "campaign_not_prepared": (
        "The campaign is still being prepared. Observe it until it is READY, "
        "then try again."
    ),
    "practice_result_required": (
        "Practice this recipe first; only a practiced recipe can be frozen "
        "and submitted."
    ),
    "candidate_awaits_submission": (
        "A frozen candidate is waiting. Submit it before freezing another."
    ),
    "freeze_a_candidate_first": (
        "Freeze a practiced recipe (carbon_freeze_candidate), then submit."
    ),
    "final_exams_used": (
        "Both final exams of this campaign are used. Launch a new campaign to continue."
    ),
    # The validator's answer to a DEVELOPMENT submission (carbon.battery).
    "evaluation_queued": (
        "The validator queued your submission. Observe later; the frozen "
        "candidate is kept, and submitting again replays the same admission."
    ),
    # LAUNCHPAD-PAGE-USABILITY-01: says what still works and what to do,
    # since a miner usually cannot add an intake until one is published.
    "evaluation_unavailable": (
        "Your frozen candidate is kept, but it cannot be evaluated yet: no "
        "validator deployment or intake is configured for this Challenge in "
        "your runner profile. When a validator intake is published for it, "
        "update Carbon and review again under Set up your environment "
        "(carbon_setup_review), which writes it into your profile, or name a "
        "validator intake you run yourself; then submit again. Until then you "
        "can still launch, practise, observe, and stop or pause your campaign."
    ),
    "evaluation_failed_infra": (
        "The validator's infrastructure failed. That is not a scientific "
        "result. The frozen candidate is kept; submit again later."
    ),
    "intake_unreachable": (
        "The validator intake could not be reached. The frozen candidate is "
        "kept. For an intake on this machine's loopback (a tunnel to a "
        "validator), start the tunnel or the validator, since Carbon cannot "
        "tell which is not running; otherwise check the address and your "
        "connection. Then submit again."
    ),
    # Every other closed code a submission through a validator intake can
    # end with (`carbon.battery.campaign.intake_code`: the intake's and its
    # transport's codes, `intake_client.REFUSALS`, and the trip's own). None
    # is a verdict on the recipe, and none uses the epoch: the frozen
    # candidate is kept, and Carbon builds and your signer signs a fresh
    # request each time you submit (W1; LP-PROD-G's codes).
    "intake_mismatch": (
        "The configured intake serves another chain or Challenge, or is not a "
        "battery intake. Nothing was sent for evaluation; the frozen candidate "
        "is kept. Correct this Challenge's validator intake address under Set "
        "up your environment, then submit again."
    ),
    # LAUNCHPAD-ACCEPT-03: checked before anything is signed.
    "intake_receiver_mismatch": (
        "The validator intake reports another receiver hotkey than the one "
        "your profile pins for this Challenge, so nothing was signed or sent; "
        "the frozen candidate is kept. Review the evaluation endpoint under "
        "Set up your environment (carbon_setup_review): check the intake "
        "address and its receiver hotkey, then submit again."
    ),
    "intake_signer_changed": (
        "This epoch's candidate was submitted under another hotkey than the "
        "signer now running, and nothing was sent. Start carbon-miner-signer "
        "for the hotkey that submitted it, then submit again to read its "
        "result; a candidate is never submitted under a second hotkey."
    ),
    "intake_changed_since_submission": (
        "This epoch's candidate was submitted to another validator intake "
        "than the one now configured. Configure that intake again, then submit "
        "again to read its result; a candidate is never submitted twice."
    ),
    "intake_answer_unrecognised": (
        "The validator intake answered in a way this Carbon does not "
        "recognise, so nothing was evaluated; the frozen candidate is kept. "
        "Check that the intake address serves this Carbon version, then "
        "submit again."
    ),
    "signer_unavailable": (
        "Your signer did not sign the submission: it is not running, or it "
        "declined. Start carbon-miner-signer for your registered hotkey, then "
        "submit again; the frozen candidate is kept."
    ),
    "rate": (
        "The validator intake is limiting requests from your address. Wait a "
        "minute, then submit again; the frozen candidate is kept."
    ),
    "capacity": (
        "The validator intake is busy. Submit again in a few minutes; the "
        "frozen candidate is kept."
    ),
    "inbox_full": (
        "The validator's queue is full. Submit again later; the frozen "
        "candidate is kept."
    ),
    "body": (
        "The intake refused the submission as larger than it accepts (64 "
        "KiB), so nothing was evaluated; the frozen candidate is kept. Check "
        "that the intake address serves this Carbon version; if it does, this "
        "recipe is too large to submit to it."
    ),
    "body_timeout": (
        "The submission's body did not reach the intake in time, so nothing "
        "was evaluated; the frozen candidate is kept. Check your connection, "
        "then submit again."
    ),
    "headers": (
        "The intake refused the request's headers (one was repeated), so "
        "nothing was evaluated; the frozen candidate is kept. Check that "
        "nothing between you and the intake, such as a proxy, changes "
        "requests, then submit again."
    ),
    "not_found": (
        "The validator holds no submission of this candidate for your hotkey. "
        "Submit again; the frozen candidate is kept."
    ),
    "tool": (
        "The intake does not take the request this Carbon sends, so nothing "
        "was evaluated; the frozen candidate is kept. Check that the intake "
        "address serves this Carbon version, then submit again."
    ),
    "submission_fields": (
        "The intake does not take the submission this Carbon sends, so "
        "nothing was evaluated; the frozen candidate is kept. Check that the "
        "intake address serves this Carbon version, then submit again."
    ),
    "status_fields": (
        "The intake does not take the status request this Carbon sends; the "
        "frozen candidate is kept. Check that the intake address serves this "
        "Carbon version, then submit again."
    ),
    "snapshot_unknown": (
        "The validator no longer holds the chain snapshot the request named. "
        "Submit again: the request is rebuilt on a fresh snapshot. The frozen "
        "candidate is kept."
    ),
    "snapshot_unavailable": (
        "The validator cannot read the chain right now; that is on its side. "
        "Submit again in a few minutes; the frozen candidate is kept."
    ),
    "hotkey_window_used": (
        "Your hotkey already has its submission for this tempo. Submit again "
        "once the next window opens; the frozen candidate is kept."
    ),
    "receipt_block_missing": (
        "The validator could not date this submission. Submit again; the "
        "frozen candidate is kept."
    ),
    "commitment_contested": (
        "Another hotkey committed this recipe's hash on chain first, so it counts "
        "for that hotkey, not yours: the earliest commitment block, then the "
        "earlier transaction in that block, decides (OWNER-COMMITMENT-POSTER-01 "
        "D6). Recommitting the same hash cannot change that; build and freeze a "
        "different candidate."
    ),
    "commitment_reader_unavailable": (
        "Your hotkey's on-chain commitment could not be read just now, by "
        "this validator or by Carbon before it sent anything; that is not a "
        "verdict on the recipe. Try again in a few minutes, or submit to "
        "another validator; the frozen candidate is kept."
    ),
    "commitment_required": (
        "This validator requires the frozen candidate's hash committed on "
        "chain first. Commit it (carbon_commit with this campaign; your "
        "signer asks you to confirm it in its terminal) or with your own "
        "Bittensor SDK code, then submit again (or resume, where Carbon's "
        "agent selects); the frozen candidate is kept."
    ),
    "commitment_stale": (
        "This validator counts a commitment only if it was posted after your "
        "hotkey's previous admitted submission. Recommit it (carbon_commit "
        "with this campaign and recommit=true; your signer asks you to "
        "confirm it in its terminal), then submit again (or resume, where "
        "Carbon's agent selects); the frozen candidate is kept."
    ),
    # The commitment itself (LAUNCHPAD-ACCEPT-02): the Launchpad's door and
    # the poster (`carbon.chain.commitment_poster.PostCode`).
    "recommit_boolean_required": "Send recommit as true or false.",
    "commitment_not_offered": (
        "This campaign's Challenge uses no on-chain commitment. Submit "
        "without one (carbon_submit)."
    ),
    "commitment_digest_unavailable": (
        "Carbon could not work out the frozen candidate's commitment digest, "
        "so nothing was asked or sent. Report it; the frozen candidate is "
        "kept."
    ),
    "commitment_bad_digest": (
        "The digest to commit is not a sha256 digest, so nothing was asked "
        "or sent. Report it: Carbon computes it from the frozen candidate."
    ),
    "commitment_fee_unknown": (
        "The chain did not quote the commitment's fee, so nothing was signed "
        "or sent. Commit again in a few minutes (carbon_commit)."
    ),
    "commitment_fee_over_ceiling": (
        "The fee rose above your signer's ceiling after you confirmed, so the "
        "signature was discarded unsent. Commit again later (carbon_commit)."
    ),
    "commitment_call_mismatch": (
        "Your signer returned another call than the one prepared, so nothing "
        "was sent. Check that your signer and Carbon are the same version, "
        "then commit again (carbon_commit)."
    ),
    "commitment_signature_invalid": (
        "The signature did not verify for your hotkey, so nothing was sent. "
        "Check that your signer holds your registered hotkey, then commit "
        "again (carbon_commit)."
    ),
    "commitment_in_flight": (
        "A commitment for this hotkey is already being posted. Observe until "
        "it settles (carbon_observe); it is never sent twice."
    ),
    "commitment_ambiguous": (
        "A commitment was broadcast and its outcome is not known yet. Carbon "
        "never sends it again: it reads the chain until the request's era has "
        "passed (about 26 minutes). Observe (carbon_observe), and commit "
        "again only if it did not land."
    ),
    "commitment_failed": (
        "The chain included the commitment and rejected it, so it is not on "
        "chain. Commit again later (carbon_commit); the frozen candidate is "
        "kept."
    ),
    "commitment_not_observed": (
        "The commitment was finalized but did not read back as your hotkey's "
        "commitment. Observe again in a minute (carbon_observe); commit again "
        "(carbon_commit) only if it is still not on chain."
    ),
    # The signer's own commit refusals (`carbon_miner_signer.CommitRefusal`),
    # by their closed values. None signed anything.
    "MALFORMED_REQUEST": (
        "Your signer refused the commitment request as malformed; nothing was "
        "signed or sent. Check that your signer and Carbon are the same "
        "version, then commit again (carbon_commit)."
    ),
    "COMMITMENT_NOT_PINNED": (
        "Your signer's commitment pins are incomplete, so it signs no "
        "commitment; nothing was sent. Update carbon-miner-signer to a "
        "release whose commitment record is complete, restart it, then commit "
        "again (carbon_commit)."
    ),
    "NOT_A_COMMITMENT": (
        "Your signer refused a call that is not the one commitment call it "
        "signs; nothing was signed or sent. Check that your signer and Carbon "
        "are the same version, then commit again (carbon_commit)."
    ),
    "BAD_DIGEST": (
        "Your signer refused the digest as not a sha256 digest; nothing was "
        "signed or sent. Report it: Carbon computes it from the frozen "
        "candidate."
    ),
    "WRONG_NETUID": (
        "Your signer refused a commitment for another subnet than the one it "
        "started for; nothing was signed or sent. Start it for the subnet "
        "your profile names, then commit again (carbon_commit)."
    ),
    "WRONG_NETWORK": (
        "Your signer refused a commitment for another network than the one it "
        "started for; nothing was signed or sent. Start it for the network "
        "your profile names, then commit again (carbon_commit)."
    ),
    "NONZERO_TIP": (
        "Your signer refused a commitment carrying a tip; nothing was signed "
        "or sent. Check that your signer and Carbon are the same version, "
        "then commit again (carbon_commit)."
    ),
    "IMMORTAL_ERA": (
        "Your signer refused an immortal transaction; nothing was signed or "
        "sent. Check that your signer and Carbon are the same version, then "
        "commit again (carbon_commit)."
    ),
    "ERA_TOO_LONG": (
        "Your signer refused a transaction whose era is longer than its cap; "
        "nothing was signed or sent. Check that your signer and Carbon are the "
        "same version, then commit again (carbon_commit)."
    ),
    "PAYLOAD_MISMATCH": (
        "Your signer's own rebuild of the transaction differs from what was "
        "prepared, so it signed nothing and nothing was sent. Check that your "
        "signer and Carbon are the same version, then commit again "
        "(carbon_commit)."
    ),
    "FEE_UNKNOWN": (
        "Your signer had no fee to check, so it signed nothing and nothing "
        "was sent. Commit again in a few minutes (carbon_commit)."
    ),
    "FEE_OVER_CEILING": (
        "The quoted fee is above your signer's recorded ceiling, so it signed "
        "nothing and nothing was sent. The ceiling is not changed from here; "
        "commit again later (carbon_commit)."
    ),
    "ALREADY_COMMITTED_THIS_TEMPO": (
        "Your signer already signed a commitment this tempo (at most one per "
        "tempo, about 72 minutes). Commit again once the next tempo starts "
        "(carbon_commit)."
    ),
    "STALE_CHAIN_CONTEXT": (
        "The chain moved on while your signer was asked, so it signed nothing "
        "and nothing was sent. Commit again (carbon_commit)."
    ),
    "COMMIT_IN_FLIGHT": (
        "Your signer is already asking you to confirm another commitment. "
        "Answer it in the signer's terminal, then observe (carbon_observe)."
    ),
    "NOT_CONFIRMED": (
        "The commitment was not confirmed in your signer's terminal, so "
        "nothing was signed or sent. Commit again (carbon_commit) and type the "
        "digest's last 8 characters there; an agent cannot confirm it."
    ),
    "LEDGER_UNAVAILABLE": (
        "Your signer could not read or write its own commitment ledger, so it "
        "signed nothing. Check the signer's state directory, restart it, then "
        "commit again (carbon_commit)."
    ),
    "AUTO_CONFIRM_NOT_ALLOWED": (
        "Your signer auto-confirms only allow-listed testnet 567 hotkeys, and "
        "this commitment is not one; nothing was signed or sent. Restart the "
        "signer without --auto-confirm-commitments and confirm in its "
        "terminal, then commit again (carbon_commit)."
    ),
    "backend_not_served": (
        "This validator has no worker image for your recipe's backend. That "
        "is not a verdict on the recipe, and nothing was recorded. Submit to "
        "a validator that serves the backend, or again once this one does; "
        "the frozen candidate is kept."
    ),
    # The validator's neutral door (VALIDATOR-01 VAL-D3): refused at once,
    # nothing queued, evaluated or counted against your window.
    "contract_not_served": (
        "This validator serves another construction contract than the one "
        "your candidate was compiled under. Update Carbon so its contract "
        "matches the validator's, or submit to a validator that serves yours; "
        "the frozen candidate is kept."
    ),
    "development_variant_not_served": (
        "The candidate names a development-only contract variant, which is "
        "never served to miners, and nothing was sent for evaluation. Compile "
        "it against the Challenge's published contract and submit again; the "
        "frozen candidate is kept."
    ),
    "contract_digest_malformed": (
        "The validator could not read the contract digest Carbon sent. Check "
        "that the intake address serves this Carbon version, then submit "
        "again; the frozen candidate is kept."
    ),
    "challenge_mismatch": (
        "The validator says the candidate names another Challenge than the "
        "contract it was sent under. Check the campaign's Challenge and the "
        "intake address, then submit again; the frozen candidate is kept."
    ),
    "malformed_submission": (
        "The validator could not read the submission's identity fields. Check "
        "that the intake address serves this Carbon version, then submit "
        "again; the frozen candidate is kept."
    ),
    "oversized_submission": (
        "The candidate's recipe is larger than this validator accepts. "
        "Nothing was evaluated; the frozen candidate is kept."
    ),
    "strategy_not_utf8": (
        "The validator could not read the recipe as UTF-8 text. Nothing was "
        "evaluated; the frozen candidate is kept. Report it: Carbon writes "
        "its recipes as UTF-8."
    ),
    "strategy_bom": (
        "The validator refused a recipe that starts with a byte-order mark. "
        "Nothing was evaluated; the frozen candidate is kept. Report it: "
        "Carbon never writes one."
    ),
    "strategy_nesting_too_deep": (
        "The candidate's recipe nests more deeply than this validator "
        "accepts. Nothing was evaluated; the frozen candidate is kept."
    ),
    "strategy_not_json": (
        "The validator could not read the recipe as JSON. Nothing was "
        "evaluated; the frozen candidate is kept. Report it: Carbon writes "
        "its recipes as JSON."
    ),
    "strategy_not_object": (
        "The validator refused a recipe that is not a JSON object. Nothing "
        "was evaluated; the frozen candidate is kept."
    ),
    "non_finite_value": (
        "The candidate's recipe holds NaN, Infinity or a number too large to "
        "be finite, which validators refuse. Nothing was evaluated; the "
        "frozen candidate is kept."
    ),
    "duplicate_key": (
        "The candidate's recipe repeats a key in one object, which validators "
        "refuse. Nothing was evaluated; the frozen candidate is kept."
    ),
    "integer_out_of_range": (
        "The candidate's recipe holds an integer outside the signed 64-bit "
        "range, which validators refuse. Nothing was evaluated; the frozen "
        "candidate is kept."
    ),
    "TRANSPORT_IDENTITY": (
        "The validator does not find your hotkey (or its own) registered on "
        "this subnet. Check your registration (carbon_onboarding_status), "
        "then submit again; the frozen candidate is kept."
    ),
    "TRANSPORT_STALE": (
        "The request was too old when the validator received it. Check this "
        "machine's clock, then submit again; the request is rebuilt and "
        "signed afresh, and the frozen candidate is kept."
    ),
    "TRANSPORT_REPLAY": (
        "The validator had already received this exact request. Submit "
        "again; a new request is built and signed, and the frozen candidate "
        "is kept."
    ),
    "TRANSPORT_CONFLICT": (
        "The validator holds a different request under this request id. "
        "Submit again; a new request id is used, and the frozen candidate is "
        "kept."
    ),
    "TRANSPORT_CONTEXT": (
        "The validator serves another network, subnet or Challenge than the "
        "request names. Check this Challenge's validator intake address under "
        "Set up your environment, then submit again; the frozen candidate is "
        "kept."
    ),
    "TRANSPORT_MALFORMED": (
        "The validator did not read the request as a Carbon request. Check "
        "that the intake address serves this Carbon version, then submit "
        "again; the frozen candidate is kept."
    ),
    "TRANSPORT_RATE": (
        "Too many requests reached the validator from your hotkey at once. "
        "Wait a moment, then submit again; the frozen candidate is kept."
    ),
    "TRANSPORT_CAPACITY": (
        "The validator's receipt journal is full; that is on its side. Submit "
        "again later; the frozen candidate is kept."
    ),
    "TRANSPORT_STORE": (
        "The validator could not record the request; that is on its side. "
        "Submit again; the frozen candidate is kept."
    ),
    "AUTH_BAD_SIGNATURE": (
        "The validator could not verify the signature for your hotkey. Check "
        "that carbon-miner-signer runs for your registered hotkey, then "
        "submit again; the frozen candidate is kept."
    ),
    "AUTH_WRONG_RECEIVER": (
        "The request was signed for another validator than the one answering "
        "at the intake address. Check the address, then submit again; the "
        "frozen candidate is kept."
    ),
    "AUTH_STALE": (
        "The signature was more than 10 seconds old when the validator "
        "checked it. Check this machine's clock and that your signer answers "
        "promptly, then submit again; the frozen candidate is kept."
    ),
    "AUTH_REPLAY": (
        "The validator had already seen this signature. Submit again; the "
        "request is signed afresh, and the frozen candidate is kept."
    ),
    "AUTH_MALFORMED": (
        "The validator found the signature headers missing or malformed. "
        "Check that carbon-miner-signer is the signer running and that "
        "nothing between you and the intake changes requests, then submit "
        "again; the frozen candidate is kept."
    ),
    "AUTH_UNAVAILABLE": (
        "The validator cannot verify signatures right now; that is on its "
        "side. Submit again later; the frozen candidate is kept."
    ),
    # Attaching to a campaign (`standard_cli.attached`): which check failed.
    "runner_profile_unusable": (
        "Your runner profile could not be read, or it does not validate. "
        "Check the --configuration path, or write it again under Set up your "
        "environment."
    ),
    "campaign_not_found": (
        "No campaign of this profile has that id. List your campaigns "
        "(carbon_observe, or the Control Center) and name one by its "
        "32-character id."
    ),
    "campaign_manifest_differs": (
        "This campaign's frozen record was not launched under this profile, "
        "or differs from its own ledger. Nothing was changed. Attach with the "
        "profile that launched it."
    ),
    "campaign_revision_differs": (
        "This campaign was frozen under another Carbon revision than your "
        "profile accepts. Attach from the checkout and profile it was launched "
        "with, or launch a new campaign."
    ),
    "runtime_unavailable": (
        "This host cannot run the campaign's accepted worker images right "
        "now: Docker is not running, or an image is missing. Start Docker, or "
        "re-run the installer, then try again."
    ),
    "campaign_runtime_differs": (
        "This campaign was frozen with a runtime this host no longer "
        "composes. Launch a new campaign; this one stays readable."
    ),
    "remote_setup_unavailable": (
        "Your remote GPU setup does not match this campaign, or cannot be "
        "used. Check it under Set up your environment, Compute, then try again."
    ),
    "session_unavailable": (
        "This campaign has no prepared authenticated session yet. Resume the "
        "campaign once so it is prepared, then attach."
    ),
    "campaign_owner_changed": (
        "Your signer authenticates as another miner than the one this "
        "campaign was launched under. Attach with the hotkey and signer that "
        "launched it, or launch a new campaign; this one stays readable."
    ),
    "registration_check_failed": (
        "Your hotkey's registration could not be confirmed on the subnet. "
        "Check it is registered (carbon_onboarding status) and the chain is "
        "reachable, then try again."
    ),
    "miner_differs_from_campaign": (
        "The hotkey in your runner profile is not the one this campaign was "
        "launched with. Use that hotkey's profile, or launch a new campaign."
    ),
    "task_left_running": (
        "A research task was left RUNNING by an earlier session. Attach with "
        "--cleanup-only (carbon-mcp --configuration PROFILE --campaign ID "
        "--cleanup-only) to observe and cancel it, then reconcile the "
        "campaign (halt with action=reconcile)."
    ),
    "carbon_mcp_failed": (
        "Carbon MCP stopped unexpectedly. Start it again; if it keeps failing, "
        "open the Control Center to check your setup."
    ),
    "carbon_mcp_interrupted": "Interrupted. Start Carbon MCP again when you are ready.",
    # The operations table's own refusals at either door (`operations.perform`
    # and the bodies it admits). Until W1 the MCP door read a second table and
    # gave most codes here a generic step; `operations.REFUSAL_FIELDS` now
    # names only the field to correct.
    "closed_request_required": (
        "Send exactly the operation's arguments: every required field and "
        "only declared ones (its arguments schema lists them)."
    ),
    "research_profile_mismatch": (
        "Omit profile, or send the profile_id of the runner profile this "
        "server or Control Center was started with."
    ),
    "challenge_required": (
        "Send challenge and challenge_version as the Challenge list gives "
        "them (carbon_challenges_v1__list)."
    ),
    "challenge_unknown": (
        "Choose a Challenge from the Challenge list (carbon_challenges_v1__list)."
    ),
    "challenge_deferred": (
        "This Challenge is not open yet. Choose another from the Challenge "
        "list (carbon_challenges_v1__list)."
    ),
    "challenge_not_implemented": (
        "This Challenge is reserved, not implemented. Choose another from the "
        "Challenge list (carbon_challenges_v1__list)."
    ),
    "challenge_version_unsupported": (
        "Send the version the Challenge list gives for that Challenge "
        "(carbon_challenges_v1__list)."
    ),
    "challenge_has_no_toolbox": (
        "This Challenge has no toolbox to show. Choose a Challenge from the "
        "Challenge list (carbon_challenges_v1__list)."
    ),
    "gpu_scope_is_for_another_challenge": (
        "Your GPU practice was set up for another Challenge. Launch that one, "
        "or set up compute again for this one (carbon_setup_compute)."
    ),
    "invalid_agent": (
        "Send graphite (Graphite, Carbon's research agent) or none (you or "
        "your own agent select); carbon-graphite and own-agent are accepted "
        "too."
    ),
    "invalid_idempotency_key": (
        "Send 16-80 letters, digits, - or _. On launch over MCP you may omit "
        "it and the server generates one."
    ),
    "research_launch_replay_conflict": (
        "This key already launched a different request. Send that request "
        "unchanged to replay it, or use a new key."
    ),
    "operation_replay_conflict": (
        "This key already names a different request. Send that request "
        "unchanged to replay it, or use a new key."
    ),
    "invalid_budget": (
        "Send only ceilings, elapsed_seconds or final_reserve, within their "
        "bounds (carbon_options lists them)."
    ),
    "research_review_changed": (
        "Your setup changed since the review you sent. Review again "
        "(carbon_setup_review) and send the review digest it gives."
    ),
    "invalid_feedback_mode": (
        "Send one of the feedback modes carbon_options lists, or omit it for FULL."
    ),
    "feedback_mode_not_offered_by_challenge": (
        "Send a feedback mode this Challenge offers (its description lists "
        "them), or omit it for FULL."
    ),
    "model_provider_required": (
        "Name the provider for this model or these settings (carbon_options "
        "lists them)."
    ),
    "unknown_model_provider": "Send a provider carbon_options lists.",
    "model_selection_refused": (
        "Send a model and settings within the provider's bounds "
        "(carbon_options lists them)."
    ),
    # The code keeps its historical name; the agent that calls a model for
    # a new launch is Graphite (OWNER-GRAPHITE-MINER-01).
    "model_selection_needs_the_autonomous_agent": (
        "A model is only for an agent that calls one: send agent=graphite, or "
        "omit the model fields."
    ),
    "model_provider_endpoint_not_configured": (
        "Configure this provider's endpoint under Set up your environment "
        "(carbon_setup_inference) first."
    ),
    "retired_grant_campaign": (
        "This campaign takes no new work. Observe or stop it, and launch a new one."
    ),
    "research_run_unavailable": (
        "Use the id your launch returned for one of your own campaigns."
    ),
    "campaign_journal_not_ready": (
        "The campaign is still being prepared. Try again once observe shows it running."
    ),
    "strategy_json_invalid": "Send the recipe as a JSON object.",
    "strategy_object_required": "Send the recipe as a JSON object.",
    "design_malformed": (
        "The recipe is not a design Carbon can check: send schema_version, "
        "challenge_id, backbone and parameters, with parameters an object."
    ),
    "design_refused": (
        "A choice in this recipe is refused for submission. Run check_design "
        "on it to see which, and change that choice."
    ),
    "design_excluded": (
        "A choice in this recipe is excluded from submission. Run "
        "check_design on it to see which, and choose another."
    ),
    "design_not_yet_rebuildable": (
        "The validator cannot rebuild a choice in this recipe yet. Run "
        "check_design on it to see which, and choose one it rebuilds."
    ),
    "design_needs_owner_decision": (
        "A choice in this recipe awaits an owner decision before it can be "
        "submitted. Run check_design on it to see which, and choose another "
        "for now."
    ),
    "bounded_hypothesis_required": (
        "Send hypothesis (and expected_effect, if given) as 1 to 2048 "
        "characters of text."
    ),
    "bounded_reason_required": "Send reason as 1 to 4096 characters of text.",
    "used_feedback_boolean_required": "Send used_feedback as true or false.",
    "invalid_research_control": "Send stop, pause or reconcile.",
    "note_kind_unknown": "Send hypothesis, plan, observation or reply.",
    "bounded_note_required": "Send 1 to 2000 characters of plain text.",
    "note_not_retained": (
        "The note could not be kept in the campaign's journal; nothing was "
        "written. Observe the campaign, then try again."
    ),
    "reply_to_unknown_message": (
        "Reply to a sequence the miner's messages listed (carbon_messages)."
    ),
    "reply_to_only_for_replies": "Send reply_to only with note_kind=reply.",
    "cursor_out_of_bounds": (
        "Send after as 0 or more: the last next_cursor, or 0 to read from the start."
    ),
    "limit_out_of_bounds": "Send 1 to 100, or omit it for 50.",
    "unknown_experiment": (
        "Send a practice run id from the campaign view's experiments, or omit "
        "it for the latest."
    ),
    "unknown_practice_case": (
        "Send a public PRACTICE case id from the campaign view's "
        "per_case.case_ids, or omit it for the first."
    ),
    "research_task_id_required": (
        "Send rtsk_ and 64 hex digits, from the run's start_research_task result."
    ),
    "run_output_unavailable": (
        "Send a finished run of this campaign; the run may still be going "
        "(get_research_result shows it)."
    ),
    "not_a_workspace_run": (
        "run_output reads run_python and run_julia runs; the campaign view "
        "shows practice trials (carbon_campaign_view)."
    ),
    # An MCP session's research attachment (`mcp_operations.Attachment`).
    "already_attached": (
        "This session already holds a campaign. Detach it "
        "(carbon_detach_campaign) first."
    ),
    "attachment_busy": (
        "Another attach or detach of this session is under way. Try again "
        "when it returns."
    ),
    "research_calls_in_flight": (
        "Research calls of this session are still running. Detach when they return."
    ),
    "attach_unavailable": (
        "The campaign must be one of yours, unfinished and not held by "
        "another operation or session, with your hotkey registered and your "
        "signer running. Observe it (carbon_observe) to see its state."
    ),
    # Graphite, the miner edition (OWNER-GRAPHITE-MINER-01): its launch, its
    # run, and the miner's library and plans.
    "autonomous_agent_replaced": (
        "Graphite replaced Carbon's autonomous agent for new launches. Launch "
        "with agent=graphite (carbon-graphite in setup) and choose RESEARCH, "
        "BUILD or FULL; campaigns launched earlier still run and replay as "
        "they were."
    ),
    "graphite_edition_unknown": (
        "This campaign names a Graphite edition this Carbon does not have, so "
        "nothing was called. Update Carbon (re-run the installer), then "
        "resume; or launch a new campaign."
    ),
    "graphite_not_offered_for_challenge": (
        "Graphite runs only on a Challenge with a registered research "
        "campaign. Choose such a Challenge (carbon_options lists where "
        "Graphite is offered), or launch with agent=none."
    ),
    "graphite_fields_need_the_graphite_agent": (
        "graphite_mode, research_share, plan, hunt and limits are Graphite's: "
        "send agent=graphite, or leave them out."
    ),
    "graphite_mode_invalid": "Send graphite_mode as RESEARCH, BUILD or FULL, or omit it for FULL.",
    "graphite_field_not_used_by_mode": (
        "That field is not used by this graphite_mode: research_share is for "
        "FULL, plan for BUILD, and a hunt runs only in RESEARCH and FULL. "
        "Leave it out, or change the mode."
    ),
    "graphite_launch_invalid": (
        "This campaign's Graphite launch fields are not the ones this Carbon "
        "reads, so nothing was called. Update Carbon (re-run the installer) "
        "and launch again; the campaign itself cannot be repaired."
    ),
    "curation_not_found": (
        "The pins and bans this campaign was launched with are no longer in "
        "your library, so nothing was called. Launch again: the new campaign "
        "takes your pins and bans as they are now."
    ),
    "research_share_invalid": "Send research_share as a number from 0 to 1, or omit it for 0.10.",
    "graphite_limits_invalid": (
        "Send limits with only calls_per_epoch, trials_per_epoch and "
        "planner_calls, each a whole number from 1 to 100000, or omit them: "
        "your campaign ceilings still bind."
    ),
    "graphite_ceilings_required": (
        "Graphite calls a paid model, so its budget must cap both "
        "provider_attempts (model calls) and provider_nanodollars (model "
        "spend) as whole numbers. Launch again with budget.ceilings setting "
        "both; nothing was called. A campaign launched without them cannot "
        "run, so resuming it does not help."
    ),
    "hunt_query_invalid": (
        "Send hunt as {queries?, max_records?}: up to 8 queries of 1 to 6 "
        "terms each (letters, digits and -, starting with a letter or digit; "
        "not and, or or not), and max_records from 1 to 5000. Raw arXiv "
        "query syntax is not accepted."
    ),
    "research_share_too_small": (
        "Your research share cannot pay for one model call: each call reserves "
        "its most possible cost (the model's whole output and its whole input "
        "window unless you cap max_output_tokens or max_input_tokens in "
        "model_settings) before it is sent, so this research would send "
        "nothing. Raise your provider_nanodollars or provider_attempts "
        "ceiling, raise research_share, cap the model's output or input "
        "window, or launch BUILD."
    ),
    # LA-F8 (LAUNCHPAD-FINDINGS-F8-F9): the input window, before a launch
    # (the options' `input_window` advisory) and after a stop at it.
    "graphite_input_window_too_small": (
        "Graphite reads whole discovery documents, several in one turn, and "
        "Carbon admits a request only while it stays under max_input_tokens "
        "minus 4,096, counting one token for every byte added since the "
        "provider's last count. A Graphite launch that sets no "
        "max_input_tokens gets its model's published context less its output "
        "cap; where Carbon records no context, the historical 65,536, at "
        "which Graphite's first reading turns pass that bound. This applies "
        "when your window - that default, or the max_input_tokens you set - "
        "is 65,536 or less. Set model_settings.max_input_tokens higher, up to "
        "your model's published context less max_output_tokens (input_window "
        "lists both), or choose a model with a published context, before you "
        "launch. Each call is reserved at that window, so a larger one holds "
        "more of your provider_nanodollars ceiling per call, and a FULL "
        "launch's research share must hold one whole call."
    ),
    "context_ceiling": (
        "The agent stopped because its next request could pass your model's "
        "input window as Carbon bounds it; no history was silently dropped. "
        "Launch a new campaign with model_settings.max_input_tokens set "
        "higher, up to your model's published context less max_output_tokens "
        "(input_window lists both). Each call is reserved at that window, so "
        "check your provider_nanodollars ceiling too."
    ),
    "too_many_pins": (
        "You pinned more cards than one plan can consider (64), and the "
        "Planner must consider each pin. Unpin some (carbon_library_unpin), "
        "or launch BUILD with a plan from your library, then launch again."
    ),
    # The typed stop S4 proposes to S1/S3 for a session the miner's own
    # ceiling ends (money, attempts, trials or time): Graphite's limits.
    "miner_ceiling_reached": (
        "The agent reached a ceiling you set - money, attempts, trials or "
        "time - so it stopped there; nothing past it was reserved or sent. "
        "Launch a new campaign with a larger ceiling to go further."
    ),
    "research_share_reached": (
        "The research stages used the share of your budget you set, so they "
        "stopped there and the build went on. Launch again with a larger "
        "research_share to research longer."
    ),
    "plan_not_found": (
        "No plan in your library has that digest. List your plans "
        "(carbon_plan_list) and send one of their digests, or omit plan to "
        "have the Planner write one."
    ),
    "plan_invalid": (
        "The plan cites a card that is unknown or banned, leaves out a "
        "pinned card, or is for another Challenge. Read it (carbon_plan_get), "
        "correct it and save it (carbon_plan_edit), change your pins and "
        "bans, or launch it on its own Challenge."
    ),
    "plan_document_required": (
        "Send plan_document as a JSON object, as carbon_plan_get returns a plan."
    ),
    "literature_pack_missing": (
        "The shared card pack this Carbon ships is missing or differs from "
        "its pinned digest. Re-run the installer with --update, then launch "
        "or resume."
    ),
    "literature_fetch_failed": (
        "arXiv could not be reached, so the hunt ended where it was; that is "
        "not a verdict on any paper. The Planner went on with the cards you "
        "have. Hunt again in a later campaign."
    ),
    "library_unavailable": (
        "Your Graphite library could not be opened. Finish Set up your "
        "environment so your runner profile is written, then try again."
    ),
    "library_query_invalid": (
        "Send query as 1 to 200 characters of text, and challenge as the "
        "Challenge list gives it (carbon_challenges_v1__list)."
    ),
    "card_limit_out_of_bounds": "Send card_limit from 1 to 50, or omit it for 10.",
    "card_not_found": (
        "No card in the shared pack or your library has that id. Search for "
        "it (carbon_library_search) and send an id it returns."
    ),
    "card_banned": (
        "You banned this card, so it is not served or pinned. Lift the ban "
        "(carbon_library_unban) first if you want it back."
    ),
    "import_invalid": (
        "Send title as 1 to 300 characters and text as 1 to 20000 characters "
        "of plain text. PDF import is not offered yet: paste the text."
    ),
}
FALLBACK_ACTION = (
    "Read the code: it names what was refused. Correct what it names and try "
    "again; observe shows the campaign's state."
)


def next_action(code):
    """The next step for `code`: its `NEXT_ACTIONS` entry, or the fallback."""
    return NEXT_ACTIONS.get(code, FALLBACK_ACTION)


def exception_code(exc):
    """A typed failure's closed code (its `code`, or that code's `value`), or
    None. Never the message: a `Rejected`, an `OperationRefused`, a
    `SignerFailure` and the attach refusals carry one; a bare ValueError does
    not."""
    code = getattr(exc, "code", None)
    code = getattr(code, "value", code)
    return code if type(code) is str and _CODE.fullmatch(code) else None


#: The refusal catalog's schema (`catalog`).
CATALOG_SCHEMA = "carbon.launchpad.refusal-catalog.v1"


def catalog():
    """The closed table, as a door serves it (`GET /api/v1/refusals`), so a
    page renders the next action for any code it meets - a synchronous
    refusal's `{error}`, or a campaign's `last_refusal` - from this one
    source. A code the table does not name takes `fallback`."""
    return {
        "schema": CATALOG_SCHEMA,
        "next_actions": dict(NEXT_ACTIONS),
        "fallback": FALLBACK_ACTION,
    }


def refusal(code, *, operation=None, kind="refused", at=None):
    """A `last_refusal` entry: closed code, next action, when, and which
    operation. An unrecognisable code is kept as `operation_refused` rather
    than echoed, so nothing free-form reaches the record."""
    if type(code) is not str or not _CODE.fullmatch(code):
        code = "operation_refused" if kind == "refused" else "campaign_interrupted"
    return {
        "code": code,
        "next_action": next_action(code),
        "at": round(time.time() if at is None else at, 3),
        "operation": operation if operation in OPERATIONS else None,
        "kind": kind if kind in ("refused", "interrupted", "paused") else "refused",
    }


def read_refusal(stored):
    """A stored `last_refusal`, rechecked, or None. A record that does not
    parse into the closed shape is withheld rather than shown."""
    if stored is None:
        return None
    try:
        value = json.loads(stored)
        if type(value) is not dict or type(value.get("code")) is not str:
            return None
        entry = refusal(
            value["code"],
            operation=value.get("operation"),
            kind=value.get("kind", "refused"),
            at=float(value["at"]),
        )
    except (ValueError, TypeError, KeyError):
        return None
    return entry if entry["code"] == value["code"] else None


def recovery_actions(state, in_flight=None, *, resumable=True):
    """What gets a campaign moving again from `state`, as operations a door
    can call: `[{"action", "operation"}]`, empty when nothing is needed.

    `resumable` is False for a campaign nothing resumes - one launched under
    the retired grant, or on a retired Challenge - whose resume is always
    refused: it is offered only what can succeed (stop, reconcile).

    Reconcile is offered for INTERRUPTED and PAUSE_REQUESTED too, after
    resume, as the lead's W3 contract states (review repair): it never
    resends anything. On an INTERRUPTED campaign it checks again what is
    held and settles it as it stands. A PAUSE_REQUESTED whose holder has
    gone without settling it (its process died, and no supervisor has
    recovered it yet) is settled PAUSED; while a holder lives, Reconcile
    answers `campaign_busy` and changes nothing."""
    resume = [{"action": "resume", "operation": "resume"}] if resumable else []
    reconcile = {"action": "reconcile", "operation": "halt"}
    stop = {"action": "stop", "operation": "halt"}
    if state == "RECONCILIATION_REQUIRED":
        return [reconcile, stop]
    if state in ("INTERRUPTED", "PAUSE_REQUESTED"):
        return [*resume, reconcile, stop]
    if state == "PAUSED":
        return [*resume, stop]
    if state == "QUEUED" and in_flight is None:
        # Admitted and nothing carrying it out: resume dispatches it again.
        return [*resume, stop]
    return []


# ---- The queue, in the runner's own database.


def ensure_schema(db):
    """The queue table and the campaign columns this module reads. Additive:
    an older database gains them in place and loses nothing."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS launchpad_dispatch (seq INTEGER PRIMARY KEY AUTOINCREMENT, principal TEXT NOT NULL, campaign TEXT NOT NULL, operation TEXT NOT NULL, params BLOB NOT NULL, config_digest TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT, supervisor TEXT, created REAL NOT NULL, claimed REAL, finished REAL)"
    )
    columns = {r[1] for r in db.execute("PRAGMA table_info(launchpad_campaigns)")}
    # What a launch chose, so a supervisor in another process (or after a
    # restart) can carry it out exactly; and the campaign's last refusal.
    for column in ("launch_request", "last_refusal"):
        if column not in columns:
            db.execute(f"ALTER TABLE launchpad_campaigns ADD COLUMN {column} BLOB")


def enqueue(
    db, *, principal, campaign, operation, params, config_digest, state, supervisor=None
):
    """Record one admitted dispatch; returns its sequence number. A QUEUED
    item waits for a supervisor; a RUNNING one was started at once by
    `supervisor`, the process that records it."""
    if operation not in OPERATIONS or state not in (QUEUED, RUNNING):
        raise ValueError("closed dispatch required")
    if (state == RUNNING) != (supervisor is not None):
        raise ValueError("a running dispatch names its supervisor")
    return db.execute(
        "INSERT INTO launchpad_dispatch (principal,campaign,operation,params,config_digest,state,supervisor,created,claimed) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            principal,
            campaign,
            operation,
            json.dumps(params, sort_keys=True, separators=(",", ":")),
            config_digest,
            state,
            supervisor,
            time.time(),
            time.time() if state == RUNNING else None,
        ),
    ).lastrowid


def claim(db, *, principal, supervisor):
    """Claim every queued item of `principal`, oldest first, for
    `supervisor`. Each item is claimed exactly once."""
    db.execute("BEGIN IMMEDIATE")
    rows = db.execute(
        "SELECT * FROM launchpad_dispatch WHERE principal=? AND state=? ORDER BY seq",
        (principal, QUEUED),
    ).fetchall()
    for row in rows:
        db.execute(
            "UPDATE launchpad_dispatch SET state=?,supervisor=?,claimed=? WHERE seq=? AND state=?",
            (RUNNING, supervisor, time.time(), row["seq"], QUEUED),
        )
    return [dict(r) for r in rows]


def finish(db, seq, outcome):
    db.execute(
        "UPDATE launchpad_dispatch SET state=?,outcome=?,finished=? WHERE seq=? AND state!=?",
        (DONE, outcome, time.time(), seq, DONE),
    )


def withdraw(db, seq):
    """Withdraw a QUEUED item no supervisor has claimed. True when withdrawn;
    False when one claimed it first (it is then that supervisor's)."""
    return (
        db.execute(
            "UPDATE launchpad_dispatch SET state=?,outcome=?,finished=? WHERE seq=? AND state=?",
            (DONE, "withdrawn", time.time(), seq, QUEUED),
        ).rowcount
        == 1
    )


def interrupted_runs(db, *, principal, campaign):
    """How many of the campaign's runs a dead supervisor left unfinished."""
    return db.execute(
        "SELECT COUNT(*) FROM launchpad_dispatch WHERE principal=? AND campaign=? AND operation='run' AND outcome='interrupted'",
        (principal, campaign),
    ).fetchone()[0]


def active(db, *, principal, campaign):
    """The newest item admitted for `campaign` and not yet done, or None."""
    row = db.execute(
        "SELECT * FROM launchpad_dispatch WHERE principal=? AND campaign=? AND state!=? ORDER BY seq DESC LIMIT 1",
        (principal, campaign, DONE),
    ).fetchone()
    return dict(row) if row is not None else None


def queued(db, *, principal):
    return (
        db.execute(
            "SELECT 1 FROM launchpad_dispatch WHERE principal=? AND state=? LIMIT 1",
            (principal, QUEUED),
        ).fetchone()
        is not None
    )


def orphaned(db, *, principal, supervisor):
    """RUNNING items another supervisor claimed. Seen by the lock holder,
    their supervisor is gone: they are interrupted, never replayed."""
    rows = db.execute(
        "SELECT * FROM launchpad_dispatch WHERE principal=? AND state=? AND (supervisor IS NULL OR supervisor!=?)",
        (principal, RUNNING, supervisor),
    ).fetchall()
    for row in rows:
        finish(db, row["seq"], "interrupted")
    return [dict(r) for r in rows]


# ---- The lock: one supervisor per runner database and principal.


def lock_directory(database, principal):
    """Where the supervisor lock for `principal`'s campaigns in `database`
    lives: beside the database, one directory per principal."""
    from carbon.development_session.profile import canonical, digest

    return Path(database).parent / (
        ".supervisor-" + digest(canonical([str(principal)]))[7:23]
    )


def presence_directory(database, principal):
    """Where a running Control Center's presence lock lives: beside the
    supervisor lock. Held for the Control Center's whole life, so a detached
    supervisor knows to hand over to it."""
    return lock_directory(database, principal) / "control-center"


class SupervisorLock:
    """The supervisor's OS lock, held for as long as this process supervises."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.stack = None

    @property
    def held(self):
        return self.stack is not None

    def try_acquire(self, wait=0.0):
        """Take the lock, trying for up to `wait` seconds. True when held."""
        from scripts.dev.miner_launchpad.controller import owner_lock

        if self.stack is not None:
            return True
        deadline = time.monotonic() + wait
        while True:
            stack = contextlib.ExitStack()
            try:
                stack.enter_context(owner_lock(self.directory))
            except RuntimeError:
                stack.close()
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue
            self.stack = stack
            return True

    def release(self):
        stack, self.stack = self.stack, None
        if stack is not None:
            stack.close()


def supervisor_alive(directory):
    """Whether some process holds the supervisor lock now. Probes by taking
    it for an instant; a supervisor that meets the probe retries."""
    from scripts.dev.miner_launchpad.controller import owner_lock

    try:
        with owner_lock(Path(directory)):
            return False
    except RuntimeError:
        return True


def repository_root():
    return Path(__file__).resolve().parents[3]


def spawn_detached(configuration):
    """Start a detached supervisor for the runner profile at `configuration`.

    A new session, so it outlives the client that started it; its own
    standard streams, so a client's stdio protocol is never written to. What
    it does is recorded in the campaigns themselves (their ledger, journal,
    interruptions and `last_refusal`), never in an output stream.
    """
    import subprocess

    root = repository_root()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root), *filter(None, [environment.get("PYTHONPATH")])]
    )
    options = {}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        options["start_new_session"] = True
    # A fixed module of this checkout and the profile path; no shell.
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.dev.miner_launchpad.supervisor",
            "--configuration",
            str(Path(configuration)),
        ],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        **options,
    )


class Supervisor:
    """The loop in whichever process supervises a host's campaigns.

    `tick` is one pass: take the lock if it is free (recovering what a dead
    supervisor left, once per acquisition), then start every queued item.
    The Control Center runs `start` (a daemon thread, until closed); a
    detached supervisor runs `run_until_idle`.

    The handover: a Control Center's `tick` also holds its presence lock; a
    detached supervisor's `tick` that finds it held starts nothing more and
    hands over (`RunnerAdapter.hand_over`), releasing the lock once nothing of
    its own is working. The Control Center's next `tick` takes the lock,
    recovers, and resumes what was paused for it (`RunnerAdapter.take_over`).
    """

    def __init__(
        self,
        host,
        *,
        poll=POLL_SECONDS,
        idle_exit=IDLE_EXIT_SECONDS,
        acquire_wait=ACQUIRE_SECONDS,
    ):
        self.host = host
        self.lock = SupervisorLock(lock_directory(host.database, host.principal))
        self.presence_directory = presence_directory(host.database, host.principal)
        #: The Control Center's presence (SUPERVISOR only), held while it runs.
        self.presence = (
            SupervisorLock(self.presence_directory) if host.role == SUPERVISOR else None
        )
        self.poll, self.idle_exit, self.acquire_wait = poll, idle_exit, acquire_wait
        self.wakeup = threading.Event()
        self.stopping = threading.Event()
        self.thread = None
        self.tick_lock = threading.Lock()
        #: DETACHED: a Control Center is running and this supervisor is
        #: handing over to it; `handed_over` once it released the lock to it.
        self.handing_over = False
        self.handed_over = False

    @property
    def held(self):
        return self.lock.held

    def control_center_running(self):
        """Whether a Control Center for this runner holds its presence lock.
        Probed by taking it for an instant; a Control Center that meets the
        probe takes it on its next pass."""
        return supervisor_alive(self.presence_directory)

    def acquire(self, wait=0.0):
        """Hold the lock; on taking it, recover what an earlier holder left.

        A detached supervisor that takes it with no Control Center running
        leaves what was paused to hand over to one paused, and says why
        (D4)."""
        if self.lock.held:
            return True
        if not self.lock.try_acquire(wait):
            return False
        # A failed recovery never takes the lock down; the campaign it could
        # not settle is settled by the next one, or by its miner.
        with contextlib.suppress(Exception):
            self.host.recover(redispatch=True)
        if self.presence is None:
            with contextlib.suppress(Exception):
                if not self.control_center_running():
                    self.host.release_handover_pauses()
        return True

    def tick(self, wait=0.0):
        """Start every queued item, if this process holds (or takes) the lock.

        A detached supervisor that finds a Control Center running starts
        nothing: it hands over, and answers False. A Control Center holding
        the lock resumes, on each pass, what was paused to hand over to it
        once the process that paused it is gone (`RunnerAdapter.take_over`)."""
        with self.tick_lock:
            if self.presence is not None:
                with contextlib.suppress(Exception):
                    self.presence.try_acquire()
            elif self.host.role == DETACHED:
                if self.control_center_running():
                    if self.lock.held:
                        self.handing_over = True
                        if self.host.hand_over():
                            self.lock.release()
                            self.handed_over = True
                    return False
                if self.handing_over:
                    # The Control Center closed before it took over: what was
                    # paused for it stays paused, as closing it pauses (D4).
                    self.handing_over = False
                    with contextlib.suppress(Exception):
                        self.host.release_handover_pauses()
            if not self.acquire(wait):
                return False
            if self.presence is not None:
                with contextlib.suppress(Exception):
                    self.host.take_over()
            with self.host.db() as db:
                items = claim(
                    db, principal=self.host.principal, supervisor=self.host.token
                )
            for item in items:
                self.host.start_item(item)
            return True

    def wake(self):
        self.wakeup.set()

    def start(self):
        """Supervise on a daemon thread until `stop` (the Control Center)."""
        if self.thread is not None:
            return

        def loop():
            while not self.stopping.is_set():
                # A bad pass never ends supervision.
                with contextlib.suppress(Exception):
                    self.tick()
                self.wakeup.wait(self.poll)
                self.wakeup.clear()

        self.thread = threading.Thread(
            target=loop, name="carbon-campaign-supervisor", daemon=True
        )
        self.thread.start()

    def idle(self):
        """No queued item and no campaign thread here still working.

        A run parked at its campaign's checkpoint while the campaign is
        paused (`RunnerAdapter.busy_threads`) does not count: it waits for a
        resume that a new run carries out anywhere, so exiting loses nothing.
        Before this, one paused autonomous campaign kept a detached
        supervisor alive for as long as it stayed paused."""
        with self.host.db() as db:
            waiting = queued(db, principal=self.host.principal)
        return not waiting and not self.host.busy_threads()

    def run_until_idle(self, clock=time.monotonic):
        """A detached supervisor's life: take the lock, work, and exit once
        idle for `idle_exit` seconds, or once it has handed over to a
        Control Center. Returns False when it never held the lock (another
        supervisor, or a running Control Center, carries the work out)."""
        if not self.tick(self.acquire_wait):
            return self.handed_over
        idle_since = None
        while not self.stopping.is_set():
            with contextlib.suppress(Exception):
                self.tick()
            if self.handed_over:
                return True
            if self.handing_over or not self.idle():
                idle_since = None
            else:
                idle_since = clock() if idle_since is None else idle_since
                if clock() - idle_since >= self.idle_exit and self._retire():
                    return True
            self.wakeup.wait(self.poll)
            self.wakeup.clear()
        return True

    def _retire(self):
        """Release the lock, then look once more: work queued in between is
        taken back (or left to whoever took the lock, or to a Control Center
        now running). True when retired."""
        self.lock.release()
        with contextlib.suppress(Exception):
            if (
                not self.idle()
                and not self.control_center_running()
                and self.acquire(self.acquire_wait)
            ):
                return False
        return True

    def stop(self):
        self.stopping.set()
        self.wake()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=5)

    def release(self):
        """Release the lock, then the presence: a detached supervisor that
        sees the presence go hands nothing over any more."""
        self.lock.release()
        if self.presence is not None:
            self.presence.release()


def main(argv=None):
    """`python -m scripts.dev.miner_launchpad.supervisor --configuration P`:
    supervise the campaigns of the runner profile P until idle."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument(
        "--idle-exit-seconds",
        type=float,
        default=IDLE_EXIT_SECONDS,
        help="How long to stay with nothing to do before exiting (0.1-3600).",
    )
    args = parser.parse_args(argv)
    if not 0.1 <= args.idle_exit_seconds <= 3600:
        parser.error("--idle-exit-seconds is between 0.1 and 3600")
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    try:
        host = RunnerAdapter.for_profile(args.configuration, role=DETACHED)
    except Exception:  # noqa: BLE001 - an unusable profile supervises nothing
        return 2
    host.supervisor.idle_exit = args.idle_exit_seconds
    stopping = host.supervisor.stopping

    def stop(*_):
        stopping.set()
        host.supervisor.wake()

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        if hasattr(signal, name):
            with contextlib.suppress(ValueError, OSError):
                signal.signal(getattr(signal, name), stop)
    try:
        host.supervisor.run_until_idle()
    finally:
        host.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
