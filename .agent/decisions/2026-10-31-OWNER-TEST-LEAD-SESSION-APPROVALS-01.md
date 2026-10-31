# OWNER-TEST-LEAD-SESSION-APPROVALS-01: the owner's direct approvals in the Test Lead session, 2026-10-30/31

Date: 2026-10-31 (UTC)
Status: RECORD of approvals the owner gave **directly, in his own words, in the Test Lead session** (not relayed by another session).
Recorded by: the Test Lead (the session that received them). Words below are verbatim; nothing is paraphrased inside a quotation.
Maturity: DEVELOPMENT / testnet netuid 567 only. No mainnet, no other netuid, no registration, staking or transfer, no change to a safety limit.

## 1. Move C exam copies, keys, door and first weights (owner message, verbatim)

> I approve, for tonight:
> (a) Exam copies on Move C, in two batches, one copy each to UID 0 (5HWGPx…V1wR): the 3 calibration packs plus Cooling’s final pack, then the 3 final packs. Each must be built at the Validator-approved Move C head from the served batches (Motor 2273774f, Ribbed Bracket 0e64343e, Burst Thermal 4322b8ac, Cooling 6a0b9a4a), with fingerprints the Validator approves.
> (b) Two one-time access keys, restricted to the one port each needs, checked before and after, and removed right after use: custody2 to GPUYard for the copies, and Launchpad’s temporary tunnel for the 3 starting-model submissions.
> (c) Opening each Challenge to crowns only when all 9 items of its door checklist are green and approved by the Validator.
> (d) The first set_weights only after a real crown exists, with a preview showing only crowned UIDs.

Reading the Test Lead applies: copies are issued only after the Validator names the Move C head and approves each fingerprint; each key is one port, with the `authorized_keys` sha256 recorded before and after, and is removed at once; no Challenge opens to crowns, and no `set_weights` runs, outside (c) and (d). The UID 0 receiver hotkey is `5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR`.

## 2. Standing approvals until the owner is back (owner message, verbatim)

> Standing until I’m back tomorrow: (1) the Validator or you may pause crowns and weights on any Challenge at once if something looks wrong; reopening a paused Challenge waits for me; (2) test machines within the $300/week grant, deleted after use; (3) more one-time access keys to the box for team steps, each restricted to one port, checked before and after, and removed right after use. A failed safety test or a change to safety limits waits for me.

## 3. cloudflared on GPUYard (owner message, verbatim)

> Go: install cloudflared on GPUYard from Cloudflare’s official GitHub release, pinned version with its sha256 checked, user-level, no sudo. Run the tunnel as a user service that reads the token from ~/.cloudflared/tunnel-token, and never print the token. Receiver ports fixed: Motor 8771, Cooling 8772, Ribbed Bracket 8773, Burst Thermal 8775.

Done under it (Test Lead evidence): release 2026.10.7, asset `cloudflared-linux-amd64`, sha256 `1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872` (equal to the release notes and to the GitHub asset digest), installed to `/home/carbon/.local/bin/cloudflared`, user service `cloudflared-carbon.service` reading `~/.cloudflared/tunnel-token`. The first token was exposed by the owner and replaced (tunnel `carbon-validator-567b`); the token was never read or printed by the Test Lead.

## 4. Weights runtime and standing window (owner message, verbatim)

> Adopt runtime spec 486. Standing authorization window: from the current block for 100,800 blocks (14 days).

Done under it (Test Lead evidence): chain read at block 8338921, spec_version 486; `standing.json` sha256 `62897f2cb09dc315ce7af4b3bf0b83fc5f7facef9bdc2ff24fac6c2e328257df` (valid_from_block 8338921, valid_through_block 8439721; policy `testnet-winner-v4-launch` sha256:b26fed6c50229413223b3c785bc0439b66094e60b9af1afad2dce406fe41c325; publisher UID 0; authority record OWNER-TESTNET-WEIGHTS-01, sha256 `b7c36ec5f01d3d15c01d518391ede2bb3ba3a11fb5996ec6de84766591fb4fac`); `operator.json` sha256 `669453a868e544c281572f45b0c9940f34a3244feb41010070024e33425a2732`. Weights stay paused until a real crown exists (see 1(d)).

## 5. Earlier same-session answers the owner gave to the Test Lead's direct questions (Move B night)

Each was an answer to a yes/no question the Test Lead asked in the session; the question text and the owner's selected answer:

- Issue seven Move B exam copies to UID 0 (digests listed in the question): "Yes, issue all 7".
- Move them custody2 to GPUYard with a one-time key (authorized_keys before 439bca98…, with key dd1b3685…, restored 439bca98…): "Yes, one-time key".
- Relay the Cooling rest-72 practice-probe shards through the PC, sha-verified at each end and deleted: "Yes, relay via PC".
- Load two public Docker parent images (about 818 MB) into custody2's Docker: "Yes, load the images".
- NOT asked separately: the six public child library images (864 MB, same route and conditions, public builds, no custody data) were relayed and loaded under the previous answer. The Test Lead treated them as covered and flags this here so the owner can say otherwise.
- Launchpad's temporary tunnel key for the three baseline submissions (Move B): "Yes, all three".
- Launchpad's temporary key for the Ribbed Bracket (F08) rehearsal, port 8773 only: "Yes, one key for F08".
- `loginctl enable-linger carbon` on GPUYard (so detached receivers survive logout): "Yes, enable linger".

None of these approvals lifts a safety limit, resumes a paused Challenge, or covers mainnet.
