## 2026-10-06 — OWNER-REHEARSAL-AND-RELEASE-01: rehearsal-first testing; one main line with promoted releases

**Authority.** The owner, 2026-10-06, in the Test Lead session.

The owner asked: "why don't we do all testing that dress rehearsal way? I want
to leave each challenge confident we can launch it." The Test Lead proposed:
(1) rehearsal-first testing, including moving testnet's batch production behind
the hidden producer now; (2) one main line with tagged releases promoted from
testnet to mainnet, and testnet kept as permanent staging. The owner answered:

> 1. yes 2. yes as long as that's the standard and best way to do it in bittensor

On (2), the Bittensor practice is: develop locally, deploy on the test network
to emulate mainnet, then run mainnet; validators run tagged releases and
auto-update to the latest release. This record follows that practice.

**Supplements** OWNER-GRAPHITE-TEST-WAVE-08, OWNER-VALIDATOR-MAINNET-PARITY-01,
OWNER-SHARED-ANSWER-KEY-01 and OWNER-TESTNET-V2-SWITCH-01.

### 1. Rehearsal-first testing

- **The dress rehearsal is the default path.** It covers:
  - a miner practising through the Launchpad;
  - committing on chain and submitting through the real miner door (signed intake) on testnet 567;
  - several validators importing the same shared batch from the distribution host and producing identical scores;
  - weights set on testnet;
  - the batch rotating, retiring and being published.
- **Every run under adopted rules goes through it.** That means the rules miners may legally use.
- **No Challenge exits testing without it.** A Challenge exits only after a dress rehearsal passes under its final rules.
- **Nothing is adopted without it.** This covers a rule version, a construction-level LOCK and a gate threshold.
- **The development door remains only for what the real door must not carry:**
  - candidate score variants and construction levels not yet adopted (the miner door serves only locked rules, and that protection stays);
  - score tuning on the sealed tuning set;
  - Attacker testing.
- **Testnet becomes mainnet-shaped now.**
  - Testnet's batch production moves behind the hidden producer (VALIDATOR-19).
  - It reaches testnet through the public distribution host (VALIDATOR-18/S2).
  - Testnet's validators run import-only.

  This is no longer deferred. Provisioning the distribution host is an owner spending decision.

### 2. Environments and releases

- **Development** is on `main`.
- **A release** is a tag cut from `main` plus the images it pins, by digest (e.g. `worker-images-vN`). Nothing is rebuilt after release.
- **Testnet 567 is permanent staging.** It runs the next release candidate, with full rehearsals.
- **Mainnet runs the last promoted release.** Promotion moves the exact tag and image digests that passed on testnet. What launches is byte-identical to what was rehearsed.
- **Fixes:** a mainnet fix is a short-lived branch from the release tag, merged back to `main`. There are no long-lived mainnet or development branches.
- **Validators run tagged releases.** Any auto-update follows promoted releases only.

**Not decided here.** These stay the owner's:
- the mainnet netuid and its registration;
- production hosts;
- security acceptance;
- settlement values;
- each Challenge's scientific qualification and LIVE flag.

**No execution** happens through this record.
