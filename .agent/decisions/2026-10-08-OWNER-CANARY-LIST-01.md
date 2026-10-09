## OWNER-CANARY-LIST-01: the first registered canary hotkey, `carbon-canary`

**Authority.** The owner, 2026-10-08:
- relayed by the Test Lead: "approve canary 2-4", item 3. Canary submissions
  are scored, but never incumbent, standing, finals, weighted or promoted.
  This is the Launchpad's CANARY-01 plan (#839).
- **the hotkey:** created and registered by the owner on its own coldkey,
  reported by the Test Lead:
  - `carbon-canary`, UID 13 on testnet 567;
  - hotkey `5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5`;
  - coldkey `5CPkWLqAeMcEZdTMZmMzKgwPMjfDYiZwK9CibAEyNPU9PMZc`;
  - registration extrinsic 8180699-6.
- **direct confirmation:** requested from the owner in the Carbon Validator
  session, because this list decides which hotkey can never be weighted.
  PR Head holds the merge until the owner has confirmed.

**What the list does** (`challenge_validator.canary`, version 1): a listed
hotkey's submission is admitted and scored as any other, which is the
liveness check. It is then excluded by name:
- it is never nominated, so never an incumbent or a finalist;
- it is never a leak-detection baseline;
- it is never weighted: its Challenge share burns;
- it never appears in the score feed, beyond the excluded count.

**A change** to the list (adding, removing or replacing a hotkey) needs a new
owner record and a new list version.
