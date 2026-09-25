# BATTERY-TESTNET-M4P — Host preparation tooling for M4 and M7

**Programme:** battery testnet hardening track (parent #341)
**Status:** `in_progress`, pending delivery in its PR
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Authority:** OWNER-BATTERY-TESTNET-01 (OD-3, OD-4a/b, OD-5, OD-6, OD-7),
OWNER-BATTERY-TESTNET-03 and OWNER-DX-03.
**Depends on:** BATTERY-TESTNET-M3.

## Outcome

The operator's host check found three engineering blockers:
- the truth image does not import PyBaMM;
- the operator refuses the chain's runtime 471;
- OD-4a has no executable request to approve.

This ticket gives each a read-only or fail-closed tool. It does not dispatch,
rent, publish or open a wallet.

## Scope

- **`carbon/battery/truth_env.py`:**
  - materializes the pinned PyBaMM overlay from its lock, with each wheel
    hash- and size-checked and zip-slip refused;
  - verifies it in the pinned image with no network;
  - solves inside the image from a jobs file only. The container never sees
    the validator state, root or journal.
- **`operate`:** `truth-materialize`, `truth-verify`, `jobs`. `solve` moves
  into the container.
- **`carbon/chain/runtime_probe.py`:** a read-only comparison of the live
  runtime metadata with the pinned SDK's generated bindings, for the exact
  surface Carbon's publish path uses. It gives the report and a digest; it
  claims no behaviour and grants no authority.
- **`carbon/battery/od4a.py`:** the exact, numbered, digest-bound OD-4a
  request for one all-burn publication, plus the operator-config fragment
  the owner's approval completes.
- **Handoff:** host readiness, secret locations by path, the truth steps,
  the runtime-471 and OD-4a sequence, and the new stop conditions.

## Definition of Done

- [x] Overlay materialization: hash mismatch, member escape and idempotence
      are tested. The real lock's 27 wheels were materialized and
      hash-checked in the sandbox.
- [x] Verification refuses any other pybamm, numpy or scipy, and any failed
      import. The command runs with no network and the overlay read-only.
- [x] Solve refuses outside the pinned PyBaMM. `operate jobs` writes an
      owner-only jobs file and prints no case.
- [x] The runtime probe:
  - reports changed or missing calls, storage and runtime APIs;
  - lets unused additions pass;
  - moves its digest when raw types change;
  - is bound, item for item, by the pinned SDK (tested against
    `bittensor==11.1.0`).
- [x] The OD-4a request:
  - is exactly `[[0, 65535]]`, one dispatch, zero fee and spend, with the
    window anchored to a probe;
  - refuses a winner or tampered intent, an incompatible probe, another
    chain, mainnet and a malformed window or expiry.

## Evidence classes

| Class | Status |
|---|---|
| Implemented, tested locally | yes |
| Run on the operator host | no (truth-verify, the probe and the request need the host) |
| GPU / testnet | no (M4 / M7) |
