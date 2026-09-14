# C-06 signed DEVELOPMENT evidence plan

**Decision:** `OWNER-C1-BURGERS-ALPHA-01`, implemented by `C-06-D1`
**Status:** implementation candidate; exact-head acceptance pending
**Base:** C-05 PR #157 merge
`e3324691666da6b8987764048d2bfff45e0578b4`
**Primary Hub map_ref:** `WAVE-C/C-06`

## Scope and ownership

Extend the reserved `carbon.audit` package with one nominal DEVELOPMENT receipt
format. It consumes immutable digest bindings from C-01 through C-05 and does
not call their numerical owners. A receipt signature attests only that an
externally supplied DEVELOPMENT signer bound these exact bytes. It neither
qualifies the evidence nor produces a ScoreInput, archive acknowledgement,
network event, reward, settlement or official result.

## Fixed implementation

1. Canonical ASCII JSON binds submission/Strategy, Challenge/generator/
   population/SamplingPlan, TRAIN commitment, exact three-replica
   reconstruction, inference/prediction, role-explicit reference,
   measurement/result, unresolved uncertainty, Dossier/qualification manifest,
   source tree, worker image and execution policy.
2. An ephemeral Ed25519 signer accepts caller-supplied 32-byte DEVELOPMENT key
   material. Only raw public keys, key validity/revocation facts, signature and
   key identity enter the ledger. Carbon creates no production/testnet key and
   owns no external key custody.
3. A trusted frozen evidence index must contain the complete referenced digest
   closure before append. TRAIN remains a commitment: raw TRAIN bytes are not a
   receipt dependency or disclosure.
4. SQLite `FULL`-synchronous transactions append the receipt and chained event
   atomically. Exact replay is idempotent; changed bytes under one receipt ID,
   partial writes, invalid lifecycle transitions and altered chain material fail
   closed. Supersession/revocation append events instead of rewriting history.
5. Public and reviewer views are separate positive allow-lists. Both retain the
   conspicuous `DEVELOPMENT_EVIDENCE_ONLY_NOT_OFFICIAL` marker; all eligibility
   fields are literal false.

## Acceptance and stop boundary

Focused tests cover signatures, key validity/revocation, missing closure,
atomic rollback, exact replay, changed-byte conflict, tamper, partial state,
supersession/revocation and projection disclosure. Invariant tests forbid audit
imports of scoring, qualification, archive, network, reward and settlement
owners and forbid authority-upgrade adapters.

This slice can earn only `SPECIFIED`, `IMPLEMENTED` and `TESTED` for public
DEVELOPMENT evidence. Official receipt schema, protected execution admission,
scientific qualification, real signer/custody, retention, real archive
acknowledgement, testnet/network/reward/production/LIVE authority remain open.
C-07 may compose this receipt only in an explicitly non-official vertical.
