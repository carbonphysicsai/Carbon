## 2026-10-07 — LAUNCHPAD-ACCEPT-03: the receiver-hotkey check at submit

**Authority.** LAUNCHPAD-ACCEPT-01 (the critical path, step A2), ticket
LAUNCHPAD-ACCEPT-03. Engineering decisions within that ticket, recorded by
the executor. No scientific value, gate, threshold, tolerance or economic
parameter changes. No change to the intake, the validator, the signer or
`published_endpoints.json`. Authentication-adjacent: it needs the owner's
security review.

### D1. A profile pins each Challenge's receiver

1. Runner profile v2 gains an optional `receivers` map, `{challenge_id:
   ss58}`, beside `intakes`. It is validated closed: registered Challenge
   ids, ss58 addresses, and each key beside an intake of the profile
   (`intakes`, or the legacy `battery_intake`). A profile without it
   validates unchanged, and its `review_pin` (a digest of the profile as
   written) is the same; `campaign_args` carries `receivers` (empty for it).
2. Review writes it: a published endpoint's `receiver_hotkey`, without
   reaching the endpoint (as before: published endpoints are reviewed into
   the repository and checked at submit); for the miner's own intake, a
   `receiver_hotkey` named beside it (one own intake) or a `receivers` map
   (several). A new Review with an own intake requires it
   (`receiver_hotkey_required`); other refusals are
   `receiver_hotkey_invalid`, `receiver_hotkey_names_one_intake` and
   `receiver_hotkey_needs_its_intake`. All name the field `receiver_hotkey`
   and carry a next step.
3. Review reads the own intake's public facts first (as before) and refuses
   `intake_receiver_mismatch` (field `receiver_hotkey`) when they report
   another receiver. Nothing is written.
4. Setup's record keeps each written intake's pinned `receiver`, so an
   update's Review pins it again, and a set-aside own intake offers it again
   (`set_aside_receiver`; MCP status `options.receivers_again`).

### D2. Checked before every signing

`remote_submission.check_receiver(facts, receiver)` runs after every read of
the intake's facts and before the request is signed: the submit, the status
poll (`submit_and_wait`) and the resend (`campaign._resend`). A mismatch is
`IntakeRefusal("intake_receiver_mismatch")`: nothing signed or sent, no
submission recorded. It is a new closed code, REFUSED by
`campaign.intake_outcome` (the miner acts), explained in
`intake_client.REFUSALS` and given a next step in `supervisor.NEXT_ACTIONS`
that sends the miner to review the evaluation endpoint. Both doors read that
one catalog. Existing codes are unchanged.

The check is kept apart from `_signed` (whose signature tests and callers
use) so that a signer stand-in cannot bypass it.

### D3. A legacy profile warns, never refuses (the ticket's working decision)

A profile written before this change has an intake and no receiver. Its
submit is not checked (`receiver` None), because refusing would strand
running campaigns. Setup's Evaluation step shows `receiver_hotkey_warning`,
and the prelaunch review shows `receiver_pinned: false` with
`warning: intake_receiver_not_pinned` and a next step to review again. The
prelaunch review shows only whether a receiver is pinned, never the hotkey,
as it never shows a miner's own intake.

An update (`after_install`) writes such a profile again: its own intake has
no recorded receiver, and the update cannot ask the miner. It is written
again unpinned, with Review's `intake_receiver_not_pinned` warning, rather
than left unwritten (which would strand the miner after an update). Every
Review a miner makes pins a receiver.

### D4. Docs

`RECEIVER_NOTE` now says the receiver is binding; FRESH_MINER_JOURNEY.md and
the runbook's refusal table say so too. `published_endpoints.json`'s own
`entry_fields` text ("informational until the intake client checks it at
submit") is left unchanged, per the instruction not to change that file's
contents; it is now stale and named as a follow-up.

**Tests.**
- `tests/cpu/test_battery_remote_submission.py`: a mismatch refuses the
  submit, the status poll and the resend before any signing, sending
  nothing; a match proceeds and signs every request; a profile with no
  receiver proceeds; through the campaign, REFUSED and the epoch kept.
- `tests/cpu/test_miner_setup_after_install.py`: Review pins from a
  published endpoint and from an own intake (string or map); each receiver
  refusal; a mismatched own intake is refused; an update pins again; a
  legacy record is written again with a warning; a legacy profile validates
  and its review pin is unchanged; malformed `receivers` are refused.
- `tests/cpu/test_lp_prod_wiring.py`: door parity for Review's receiver
  fields and refusals; a set-aside intake named again with its receiver.
- `tests/cpu/test_miner_operations_doors.py`: the submit refusal reads the
  same next step at both doors.
- `tests/cpu/test_miner_launchpad_prelaunch.py`: the prelaunch review's
  `receiver_pinned` and legacy warning, the hotkey never shown.
- `tests/cpu/control_center_page_check.cjs`: the page's receiver field is
  filled when a set-aside intake is named again; the published receiver is
  shown as binding.
