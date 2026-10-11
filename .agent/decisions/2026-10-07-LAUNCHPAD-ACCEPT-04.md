## 2026-10-07 — LAUNCHPAD-ACCEPT-04: a testnet submit target through the tunnel, and verdict readback

**Authority.** LAUNCHPAD-ACCEPT-01 (the critical path, steps A3 and A4),
ticket LAUNCHPAD-ACCEPT-04, building on LAUNCHPAD-ACCEPT-03.
OWNER-AX42-DOOR-PRIVATE-01 (#770) keeps `published_endpoints.json` empty.
Engineering decisions within that ticket, recorded by the executor. No
scientific value, gate, threshold, tolerance or economic parameter changes.
No change to the validator, the intake, the signer, the AX42, the tunnel
account or `published_endpoints.json`. Authentication-adjacent: it needs the
owner's security review.

### D1. The tunnel target is named as the miner's own intake, never published

The miner names the loopback address (for rehearsal 3a, `http://127.0.0.1:18467`)
at Review as their own intake, with its receiver hotkey (LAUNCHPAD-ACCEPT-03).
There are two doors: MCP `carbon_setup_review` with `intakes.<challenge>` and
`receiver_hotkey`, and the browser's Review step. A test holds that the
published list stays empty.

### D2. The preflight is Review's intake check; the mismatch code is kept

The ticket calls the network/subnet/Challenge refusal `intake_mismatch`.
Review already refuses it as `intake_serves_another_chain_or_challenge`, a
public setup code, and existing codes are not renamed. So that code is kept,
now with a next step naming Carbon's testnet, netuid 567 and the Challenge.
The submit-time path keeps its own `intake_mismatch`. The check itself is
unchanged: the Challenge's `intake_check` compares network, genesis and
netuid with Carbon's testnet context and the Challenge id and version.

"Preflight" is read as Review's check, the one point where the facts are
read before anything is written. The prelaunch review stays configuration
only: it never reaches an endpoint, as its contract says.

### D3. Unreachable says tunnel or validator

`intake_unreachable` at Review carries a next step. For a loopback URL
(`127.0.0.1` or `localhost`), it says to start the tunnel or the validator,
since Carbon cannot tell which is down. For any other URL, it says to check
the address and the connection. The submit-time `NEXT_ACTIONS["intake_unreachable"]`
says the same, in one text (the catalog is keyed by code alone).

### D4. Readback repairs (both doors read one projection and one view)

The browser and MCP `observe` and `campaign_view` run the same operation
bodies, so they were already field-for-field equal. What was missing from
both:
1. **The intake outcome.** A submit refusal from an intake trip now carries
   `intake_outcome` (`QUEUED`, `UNAVAILABLE`, `REFUSED`).
   - It is added in `runner.get` from the Challenge's own campaign, through a
     new optional `ChallengeCampaign.intake_outcome`. So the runner names no
     Challenge module.
   - It is None for codes that are not an intake's (`evaluation_unavailable`,
     and so on), and for refusals of other operations.
   - It is not stored, so stored refusals are unchanged.
   - `campaign_view.last_refusal` and the submit stage pass it through when
     it is one of the three; the page shows it.
2. **The sealed outcome's public identity.** The projection now shows the
   validator's allow-listed public fields: `rule`, `recipe_digest`,
   `contract_digest`, `reconstruction` (backend, validator_path) and a
   refusal's `failure` (code, bounded issues).
   - Each field is checked to its closed shape, and is otherwise left out.
   - Every feedback mode discloses these (`_WITHHELD_OUTCOME_FIELDS`), so the
     campaign view passes them through the frozen mode's field list.
   - `sealed` is true for a SCORED outcome with no screening, exactly as
     `intake_client.describe` reads a sealed rule. The page then says
     "sealed" instead of "not shown in this feedback mode".
   - No hidden score, case, seed or pool version is added.

### D5. The service test drives the commitment through a stand-in

LAUNCHPAD-ACCEPT-02's commit operation is not on this branch. The service
test (`test_6d_...`) serves a throwaway validator on loopback with
`require_commitment: true` and the sealed rule v2. It replaces
`deployment._commitment_reader` with a stand-in that reads what the test
commits.

The journey is:
1. A wrong pinned receiver sends nothing.
2. A submit before the commitment is `commitment_required` (REFUSED) on both
   doors.
3. The test commits the expected digest through the stand-in.
4. The resubmitted candidate is SCORED and sealed, and reads back the same
   on both doors.

The commit step joins this test once LAUNCHPAD-ACCEPT-02 merges. This is
engineering evidence only; the acceptance is plan §5 (A5).

The test serves an advancing chain (`AdvancingChain`), as test 8c does. The
intake's journal refuses two different snapshots of one block
(`TRANSPORT_CONTEXT`), and this journey outlasts the 12 s refresh. Test 6b
still serves `FixedChain` and can hit that same fixture race on a slow host.
That is pre-existing and left unchanged.

**Tests.**
- `tests/cpu/test_launchpad_tunnel_target.py`:
  - Review's loopback preflight: facts read; another netuid, network or
    Challenge refused with a step; an unanswered loopback intake names the
    tunnel or validator.
  - The submit-time step; the published list empty.
  - Intake outcome classification and passthrough.
  - The sealed outcome's public identity, with no hidden fields.
- `tests/service/test_launchpad_production_journey.py::test_6d_a_loopback_intake_requiring_a_commitment_reaches_a_sealed_verdict`.
