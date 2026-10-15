# V8_8-OPERATOR-SOCKET-GROUP-01

Root relays Ryan's v8.8 engineering-upgrade mandate and explicitly assigns this
bounded correctness repair, 2026-10-14. Starting main:
`408552f39bbcb90ed553d6575e267abc2800eb64`. One fresh isolated branch/PR;
the stale root checkout, other lanes and frozen operator packets are untouched.
Current OWNER-DX-03 / continuous queue delivery applies; Hub retired.

## Working contract and decision

KEEP the registered service user UID/GID, explicit socket/source/state mounts,
image/source binding, network mode, signer/CA/TLS checks, existing supervisor,
immutable releases and rollback/state semantics. REPAIR only image-backed unit
generation: inspect the configured Docker socket at configuration/render time,
require a real accessible socket and a writable identity class, and add its
actual numeric GID as a supplementary container group for all three roles.
Do not hardcode an AX42 GID, change the primary group, run as root, add
privileged mode, loosen file modes or substitute a new operator identity.

Before repair `units.render` emits `--user` without `--group-add`; the acceptance
kit already supplies the latter. An operator whose primary GID differs from the
mounted socket GID cannot connect. Existing unit fixtures never configured an
actual Docker socket, so their command assertions did not catch this seam.

Expected files: this ticket, its one decision record,
`carbon/validator_setup/units.py`, `tests/cpu/test_validator_setup_units.py`,
`tests/cpu/test_validator_setup_docker_transport.py`, and the operator-route doc.
No public profile schema change or new configuration knob is required.

## Validation and completion

Meaningful controls: multiple observed socket GIDs propagate to service/sync/
weights without changing UID/GID; missing/non-socket/symlink/unreadable metadata
and insufficient socket/config permissions refuse before unit output. Preserve
existing credential, network, source/state and image checks. Add a disposable
real Unix-socket connection test using generated identity arguments: the normal
UID/GID connects only with the derived supplementary group, and removal of that
group produces PermissionError. Use synthetic socket/data, no actual Docker
socket in the probe container, no keys, service installation or chain action.

Product may prepare static checks and remote CI during the current TEST sprint,
but runs no local runtime/Docker/canonical tests. Root owns any focused canonical
baseline/repair/disposable execution under the existing lease. No unexecuted
counterexample is called RED or PASS. Exact-head required CI and scoped review
close this bounded engineering repair; Root owns merge and host acceptance.

## Artifact impact and revised operator step

`units.py` is baked public controller content. A repaired source manifest/bundle
and operator image are therefore required before the new units are generated
for v8.8 cutover. Published521a/source6f7 and its actual pull/extract/mirror
receipts remain immutable historical evidence; no relabel or mixed source.
After repair review, Root builds the affected operator artifact once, publishes
its observed digest and verifies the new bundle/controller. Unchanged science,
policy, worker/reference isolation and old evidence need no reassurance rerun.

Revised host sequence: privately bind actual existing service UID/GID and socket
path; generate units using the repaired matched image/bundle; compare preserved
primary identity plus observed supplementary socket GID in each ExecStart;
then use the existing drain/backup/upgrade/preflight/cutover/rollback sheet.
Re-render after a socket path/GID change; metadata rendering does not guarantee
the daemon remains available or grant deployment/security acceptance.

No science/economics/exposure/signing/default/production authority changes.
Known r8.7 orphan state and append-only journals remain outside this repair.
