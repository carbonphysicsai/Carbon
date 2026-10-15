# V8_8-OPERATOR-SOCKET-GROUP-01: observed supplementary Docker socket group

Authorized bounded engineering decision under the matching ticket and Root's
direct assignment. Domain: operator configuration, IMPLEMENTATION_LAG.

`carbon/validator_setup/units.py` derives the actual configured socket's numeric
GID at rendering time and emits Docker `--group-add` for service, sync and weights.
It preserves the supplied UID/primary GID and refuses unavailable, non-socket or
non-writable socket metadata. Existing profile/mount/credential authority stays.

Rejected: hardcoded AX42 group110, changing primary GID, root/privileged execution,
chmod or widening mounts, and silent optional-group fallback. These either fail
on another operator's host or change established identity/permissions.

No new profile field or historical migration. Reversal is the focused renderer
change and its tests/doc. A socket/GID change requires regeneration. The baked
controller changes, so Root must bind a rebuilt matched bundle/image before
cutover; published521a/6f7 is never relabelled. Actual service, rollback, exposure,
signing and qualification evidence remain separate. Root notified directly.
