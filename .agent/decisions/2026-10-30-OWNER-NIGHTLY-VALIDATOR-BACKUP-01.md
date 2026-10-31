# OWNER-NIGHTLY-VALIDATOR-BACKUP-01: nightly private backup of the testnet validator's records

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Start the top 3". The Lead's top three were (1) the standing end-to-end test, (2) fixing the GitHub checks so pushes need no bypass, and (3) "saying yes to the nightly backup".

## Decided

- The testnet validator's state (grading, receiver, ladder/KOTH stores, receipt store) is backed up every night.
- Backups contain sealed exam material, so they are stored only on Carbon's own custody hosts (the GPU validator box or the two vault machines), never on a PC, a public host or the public repo. sha256 is checked at both ends, the backups are logged in the private ledger, and the oldest are rotated out.
- A restore test is run once, using a copy with no sealed material on a test host, or on custody.

## Bounds

- No new spend: owned hosts only.
- Keys and passwords are never included. Wallet keys stay by path only and are never copied.
- Sets no score, threshold or economics.
