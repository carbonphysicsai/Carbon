# LAUNCHPAD-F15-PER-TARGET-REFUSAL-JOURNAL-01

Status: in progress. Starting base: `4124b0080c7e6d30571a75a7307f7f3849f23405`.
Primary Development Hub `map_ref`: `SYSTEM/AGENT-EXECUTION`. Hub impact:
none; this closes a retained private execution-evidence gap without changing
the mapped purpose, placement, authority, dependencies, or maturity. Current
main's OWNER-DX-03 retires routine Hub maintenance.

## Contract and delegated decision

Owner D6 requires F15 to retain two independent receiver-paired target
journals when one real target admits and one refuses. Today a refusal before
HTTP 202 leaves its target directory empty; the aggregate status has a typed
row, but no target-owned file can support `refused_journal_digest`. This is an
implementation lag, not permission to infer a real F15 result.

Keep `intake_targets.journal`, the existing remote submission record,
permitted-result file, and aggregate semantics. Repair only the multi-intake
`OperationRefused` path: after mapping the private exception to a closed public
code, atomically retain a private, target-owned, epoch-bound refusal record
with that closed code and target identity. Do not write private exception text,
signing material, model contents, or a synthetic verdict. A failed journal
write becomes `evaluation_failed_infra` for that target; the other target
continues independently. Queued work is not labelled refused and keeps its
existing submission record. The record is evidence of a refusal event, not a
cache that suppresses a later legitimate read or changes admission behavior.

Alternatives rejected: the aggregate alone cannot establish two independent
journals; writing a fake submission ID would misstate admission; changing
`remote_submission` would alter the single-intake path; persisting raw
exception text would risk disclosure. This bounded private format is
reversible and adds no public schema or scientific/economic authority.

## Plan, scope, and validation

Owned paths: this ticket, `carbon/battery/multi_intake.py`, and
`tests/cpu/test_launchpad_multi_intake.py`. Add focused fixture assertions for
a pre-admission refusal alongside a successful peer, including target/epoch
binding, closed code, no wrong-receiver signature or POST, and a journal-write
failure that remains infrastructure while the peer succeeds. Inspect static
format/diff locally; Root owns canonical tests, exact-head CI, merge, TEST
host, chain, signer, provider, and the eventual real F15 cell.

F15 remains `UNTESTED`: Main and ladder currently share one receiver, no
second approved live URL/receiver pair or controlled target-B refusal is
bound, and no two-target actual run is claimed. Preserve no verdict averaging,
no cross-target overwrite, infrastructure/science separation, and historical
evidence interpretation. Conditional completion is a reviewed implementation
and passing required tests on the exact PR head; only a later actual two-pair
run may support F15 acceptance.
