# V8_8-VALIDATOR-SETUP-01: reuse the operator stack and bind its distribution

The AX42 Git/venv/systemd path and a reconstruction-worker image are distinct
installation claims. Root/Ryan require a portable full validator route and
real external HTTPS competition using current chain behavior. Existing runtime
services and authorization checks already implement much of the behavior.

Select KEEP/WRAP: immutable public runtime payload plus a separate validator
service OCI build recipe, explicit operator-owned configuration/state and
entry points delegating existing services/sync/checked weights. Bind source,
lock, payload and image separately. A worker image never substitutes for this
operator artifact. No embedded credential, protected data or automatic launch.

Select an additive neutral operator configuration for winner publication;
leave the bounded development-testnet configuration unchanged. No registered
finney policy means a closed refusal before wallet/source access, not an
implicit adoption of testnet policy. Scientific/economic/custody/exposure
decisions remain reserved; SDK pin11.1.0 is not changed by this engineering work.

Repair existing import completeness using the required persisted salt/design,
and explicit import-only pool initialization through current operations.
Current windows/clocks/reference identities remain unchanged. Historical
partial imports are recoverable, never silently counted complete or rescored.

Alternatives: treating the existing worker digest or a host upgrade as install
parity would misstate evidence; rewriting the daemon/gateway would duplicate
working code; widening the development-testnet profile would weaken its bounded
contract. Reverse by removing additive setup/artifact entry points; existing
operator APIs and persistent history remain intact. Support files in this
single candidate, not a contract-only PR. Root sees the tracked contract and
one complete checkpoint; Platform2 packages it and Validator reviews once.

Human-reserved gaps: final tag/release identity, actual host/image/exposure and
runtime acceptance, mainnet registered policy/coldkey custody, security/science/
payment qualification. No value or authority is inferred from fixture success.
