# PLT-29: public code manifest delivered outside the pod environment

New Graphite pod creates carry `CODE_MANIFEST_TRANSPORT=authenticated-upload-v1`,
the exact manifest's SHA-256 and its byte count. The public manifest itself is
delivered to the existing pod bootstrap server at `POST /code-manifest`, with
the existing per-pod `X-Probe-Token`. This uses the existing pod connection;
it introduces no artifact hosting service, credentials or spending approval.

The bootstrap first waits for that document. It checks the declared byte count
and SHA-256 before accepting any paths. Only then does it fetch source files
from the public repository at the pinned code ref. Every file retains its
individual SHA-256 check, and all files are verified before any are written
or imported. The upload cannot change the create-request anchor. A wrong
token is refused; altered or oversized data is refused naming the anchor;
invalid paths/digests are refused naming the document. Valid identical replay
is idempotent. A valid received document cannot start code after the deadline.

The document uses the bootstrap's existing generic POST bound, 1 MiB. An
oversized manifest is refused by the producer before a provider call; the
receiver bounds reads by the anchored byte count and the same limit. This
is a bounded transport resource rule, not a physical or scoring threshold.
Unreachable upload remains within existing polling/deadline behavior; a
definitive upload refusal is typed infrastructure failure. It never becomes a
bad-model verdict or scientific success.

## Prospective compatibility

New private job records select the upload version before any create. A record
without a transport version keeps the original inline/gzipped environment
encoding, without rewriting its historical bytes. Legacy operator/A40 callers
also retain that encoding and the existing bootstrap path. The new anchors
are kept out of the phase's child environment. Model inputs, code/image/overlay
pins, ownership, create identity, cancellation and rate/budget bounds remain.

`ENV_LIMIT_CHARS` and the 8,000-character reserve are untouched. The owner's
108,000 override landed in PR #1321 and is preserved. Once that PR merged,
the obsolete oversized-manifest test input was replaced with truly oversized
synthetic phase data; all runtime-refusal/provider-call assertions remain.

## Measured software evidence

Canonical base-fixture measurement at main
`29fa548c45ad7fe7cf71d871c0c1bddc400497e8`, 872 shipped paths:

| Mode | Environment characters |
|---|---:|
| Existing legacy encoding | 76,975 |
| Anchored upload | 26,957 |
| Anchored upload plus 100 dummy paths | 26,958 |

Adding 100 paths grows the environment by one character (the byte-count field),
below the ticket's 200-character control. The larger manifest travels in the
HTTP body; all file identities remain pinned. These are spec-builder/container
tests, not a measured provider limit or real pod/GPU acceptance.

The actual receiver/bootstrap controls check authentication, wrong anchors,
oversized bodies without a read, malformed documents, legacy behavior, deadline
closure and per-file hash refusal before write/phase. The backend wait test
uses the real upload method with a fixture HTTP boundary. Removing the manifest
wait barrier deliberately makes the post-create-tamper control fail when it
reaches the phase boundary. The unchanged ship-size and source-only phase
tests pass. The oversized-environment guard uses a real oversized phase-config
fixture, since a large code manifest no longer makes the environment large.

Maturity: DEVELOPMENT implementation/testing only. This is not security
acceptance, isolation qualification, scientific qualification, deployment or
LIVE authority. Actual operator/host acceptance remains with the host sessions.

## New launch observations remain separate evidence

The owner-supplied POD_ENV_LIMIT_HANDOFF_01 attributes a successful baseline
launch to a 78,076-character environment and ambiguous creates to proposals
at 84,501 and 86,408 characters, plus four further ambiguous proposals. These
are attributed observations from the handoff; this lane did not inspect host
proposal directories or execute those launches. No padded probe isolated
environment size from envelope content or another cause. The 108,000 software
guard therefore has no demonstrated provider-protection claim from these
observations. It remains the owner-approved constant pending a measured,
owner-authorized amendment.

An empty ownership-tag listing does not establish that an ambiguous create
never executed or cost nothing. The six ambiguous reservations remain held
until reconciliation evidence resolves them. PLT-36's provider probe and its
new figure/host execution are separate work; this lane neither duplicates it
nor changes figures. Any carbon-package image change also requires the host
team's R8 hostile probes on the new pinned image before a host run. The local
environment reduction above is software evidence, not that host acceptance.
