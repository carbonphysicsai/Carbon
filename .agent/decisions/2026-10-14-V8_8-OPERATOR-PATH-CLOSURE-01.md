# V8_8-OPERATOR-PATH-CLOSURE-01: host identity and private writable paths

Domain: operator runtime integration; IMPLEMENTATION_LAG. Platform identified
missing deployment-path closure and default tempfile reliance under read-only
root. Root's metadata confirms actual carbon-val account is absent from the
candidate image; existing AX42 mounts already cover actual deployment paths.

REPAIR units.py and weights.py with focused tests. Reuse explicit state mounts,
the host's root-owned public account map and tempfile cleanup. Read-only passwd
binding supports arbitrary independent-validator identities without a schema
change, NSS package, caller environment assertion or hardcoded AX42 UID/name.
Preserve runtime deployment account checks and actual numeric UID/GID. Reject
untrusted map permissions and account mismatch before writing units. No shadow,
key or credential content is read or mounted by this identity repair.

Parse owner-only deployment configuration for path references only. Unit render
does not build private state or claim service readiness. Preview scratch is
private and transient under its explicit journal parent, never source/HOME or
an unspecified system temporary directory. Existing persistent state is retained.

Alternatives rejected: run-as-root, removing service_account enforcement, broad
writable source/tmpfs and baked machine identity. Changes are reversible; no
existing config/schema migration. Root notified directly before implementation.
Canonical CI and actual Root image/host evidence remain separate maturity gates.
