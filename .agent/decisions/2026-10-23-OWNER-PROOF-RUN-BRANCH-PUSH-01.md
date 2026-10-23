# OWNER-PROOF-RUN-BRANCH-PUSH-01: push one test branch so rented GPUs can build the proof-run models

Date: 2026-10-23
Status: **APPROVED by the owner, directly in the Carbon Validator's session.** The owner chose "Push one test branch (Recommended)" to the question of how rented GPUs get the code for the scoring proof run. The pod job tool (POD-JOBS-01) fetches only a pushed GitHub commit, and pushes were on the owner's hold.
Amends: the owner's push hold, **for this one branch only**. The push of `main` stays held.

## Decided

1. **One branch, not `main`,** pushed at the **exact commit** the proof-run builds use: the scoring-v2 RC line plus the calibration-artifact writer job. It's named e.g. `proof-run/<short sha>`.
2. **Before the push, on the branch's full history** (a push publishes every ancestor object, not just the tree):
   - `git merge-base --is-ancestor 68bfee956 <head>` is FALSE; the superseded 17596325d, 95d5a6d6b and e56f7e1e9 are not ancestors;
   - `git rev-list --objects <head>` holds no `koopman|wno-8133` object and no sealed, custody or private-ledger path;
   - the secrets grep is clean, as in TESTNET_RELEASE_CHECKLIST items 1–3.
3. **The pusher** is PR Head or the Test Lead, never an agent outside those lanes. The push is recorded with the full sha.
4. The branch carries no sealed material and no credentials. The pods build on public TRAIN only.

## Not decided here

The push of `main`, the public release, the image publish, and any other branch.
