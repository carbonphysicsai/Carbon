## 2026-10-10 — LAUNCHPAD-LEVELS-01-S4: Level 4 envelope transport through signed parts

**Authority.** LAUNCHPAD-LEVELS-01 (S3 decision 11 said Level 4 fails closed
until VALIDATOR-25 slice 4's upload exists); VALIDATOR-25 slice 4
(`carbon/battery/level4_parts.py`, `battery_level4_part` and
`battery_level4_status` in `carbon/battery/intake.py`). Engineering decisions
within the ticket's delegated scope; no bound, gate, score or value is set.

**Decisions.**

1. **What "serves Level 4" means.** A target serves the transport when its
   public facts list the Level 4 variant in `served_contracts` (unchanged
   check, `level_not_served_by_target` otherwise) **and** its `tools` list
   both part tools (`level4_parts.carries_parts`). The intake lists them only
   when it holds a part store, so that is the transport's own signal. Any
   other target is still refused `level4_envelope_transport_unavailable`
   before anything is signed or committed, on the Launchpad's pre-sign check
   and in the campaign. The campaign reads the facts once before the
   commitment gate; facts it cannot read count as not carried (fail closed),
   so the Launchpad's earlier `intake_unreachable` stays the specific answer.
2. **One format.** The parts are the validator store's: consecutive
   `PART_BYTES` slices of the frozen envelope file's bytes, rejoined by
   `Level4Parts.envelope`. The splitter (`level4_parts.split`) sits beside
   that join, standard library only; the message builders are in
   `intake_client`, signing stays with the miner's external signer
   (`remote_submission._signed`). Nothing re-serializes the envelope.
3. **Resume and replay.** `remote_submission.send_level4_envelope` asks
   `battery_level4_status` first and sends only missing parts, then confirms
   every part is held (`level4_envelope_incomplete` otherwise). A held part
   count that differs is `level4_parts_mismatch` with nothing sent; a
   `level4_part_conflict` is raised as typed, never retried. The send runs
   before the first submit and before either resend path, so a validator that
   lost its parts gets them again.
4. **Refusal catalog.** The intake's Level 4 codes already had next steps
   (VALIDATOR-25 slice 4). `level4_envelope_transport_unavailable` joins
   `intake_client.REFUSALS` and its next step now says to point the intake at
   the ladder. `level4_store_not_owner_only` is classed UNAVAILABLE (the
   validator's).

## Level 4 transport check through the campaign seam

The Launchpad door (`scripts/dev/miner_launchpad/levels.py`) is
challenge-neutral (C-MLP-04, `tests/cpu/test_control_center_challenge_neutral.py`):
it must not import a Challenge's own modules, lazily or not. So the check
"does the target intake take Level 4 envelope parts" is a `ChallengeCampaign`
field, `level4_parts: (facts) -> bool`, beside `intake_check`. The battery
campaign sets it to `carbon.battery.level4_parts.carries_parts`; every other
campaign leaves it None. `require_served` resolves the campaign by the
manifest's Challenge id (`campaign_for_id`, as the intake mapping is keyed)
and refuses Level 4 with `level4_envelope_transport_unavailable` when the
field is None, the Challenge does not resolve, or the facts list no part
tools (fail closed). Behaviour and refusal codes are unchanged.
