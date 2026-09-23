# GOAL-WORKBENCH-15: client-data engineering changes E1–E9

Programme: #139. Owner authority: the owner decision record for engineering
changes E1–E9, 23 September 2026 (decided by the owner and APPROVED), forwarded
with a Workbench handoff of the same date. The record is the owner's system of
record. It lives outside the repository, which is public, and it is cited here
by name and date only. The counsel brief lists the same nine changes for
counsel's context only. It is not the authority to build them.

Status: bounded engineering delivery, one item per pull request. No client-facing
collection, no deployment beyond the one internal machine, no spend and no
security review is authorized by this ticket. The review is gated on E9 and on a
spend figure the owner has not yet supplied.

Primary Development Hub map_ref: `SYSTEM/BUSINESS-AUTHORITY`; impact
`mapped_detail`.

## Why this exists

W-C had been described as "engineering complete, waiting only on answers". That
was true of the system as designed. The owner's v1 client-data position requires
nine changes that did not exist, so it is no longer true. Building E1–E9 does
**not** advance W-C's preconditions and is not to be reported as W-C
progressing.

## The nine changes, in build order

| Item | What | Group | Values |
|---|---|---|---|
| E8 | No code path from client material to the subnet or the public Ask Carbon assistant; absolute, no opt-in, no flag | 1 | none needed |
| E9 | Rate limiting, lockout and MFA on every account that can reach client records; mechanical controls only | 1 | none needed |
| E1 | Per-client archive encryption and key destruction, from the first record | 2 | none needed |
| E4 | Record class (SCOPING / STUDY) and a required agreement reference, enforced at construction | 2 | agreement references are operator data |
| E5 | Export log: what was released, to whom, when | 2 | none needed |
| E2 | Scheduled destruction job; a null period stops it | 3 | periods are counsel's, null |
| E3 | Retention schema: `closure_event`, `active_period`, `archive_period` replace `production_period`; `scoping_expiry`; versioned migration | 3 | values are counsel's, null |
| E6 | Encrypted intake package, one intake address, transport-copy deletion logged | 3 | address and Workspace settings are the owner's, operator configuration |
| E7 | Client-record access limited to screened people; export-control reference per record | 3 | screening standard is counsel's, null — a null makes the record unreachable |

The security review cannot start until E9 is complete. E2 and E5 must be
complete before the first paying client. None of E1–E9 is a prerequisite for
anything already launched.

For group 3, a null value prevents the operation. It never defaults to a
behaviour: neither "keep" nor "delete" is a safe default for a missing period.

E3 touches the same files as E2 and E4. They are sequenced, not built in
parallel, because two branches editing one structured file can merge cleanly and
still lose an entry.

No retention period, entity name, agreement reference, account identifier,
staff roster, intake address or jurisdiction-specific text is written into the
repository. Shape here, instances in private operator configuration.

## E8 — delivered (#314)

**What was found.** A read-only map of every route from Workbench client
material toward the subnet or the public assistant found:

- **Study route.** A Workbench design goes to `WorkbenchScience`, then to the
  miner research campaign. The only numerical input allowed to cross must equal
  the one granted public TRAIN definition, and the research call is built from a
  fixed material name and a digest. No client parameter could cross. This was
  already structural, but nothing pinned it.
- **Authoring route.** A Workbench authoring request goes to
  `tools/authoring_bridge.py`, then to a Challenge proposal. This was **live**.
  The design's free-text `intended_use` and its identifiers were compiled into
  the proposal, and the only guard was the `rights_scope` label, which staff can
  choose and a client can type.
- **Assistant.** The Worker imports nothing outside its tree. Knowledge
  `repo_path` values were not contained: an absolute path or `..` could name any
  file on the machine, although only its digest was read.
- **Miner MCP Workbench app.** Not a separate egress. Its requests come from the
  operator's own MCP host and leave only by the study route.

**What was built.**

- The bridge now compiles only source-owned constants, the closed goal enum, and
  a challenge identifier derived by digest from the Workbench identifiers. The
  design's text, including its identifiers, is never read into the compiled
  input. The historical v1 source-assessment fixture is unchanged.
- Knowledge sources are contained to the public repository, and that includes
  symlinks. A source outside it fails validation before anything is read.

**The tests that pin it.** Each one asserts absence and has a specimen:

- `tests/cpu/test_e8_client_material_exclusion.py`, run by the canonical job's
  full CPU lane:
  - A sentinel is planted in every client-controlled study field. Everything
    that crossed to the research service is searched byte for byte, together
    with the full campaign ledger and task store. Specimen: a variant whose
    research call carries one scope field fails.
  - A client parameter sent as the physical definition is refused before
    anything crosses. Specimen: the public definition does cross.
  - Sentinel text and a client parameter in every authoring request field are
    absent from the compiled input and the proposal. Specimen: the previous
    bridge fails.
  - No module under `carbon/` or `scripts/` names a client-record format. The
    assistant runtime names exactly one; see the open question below. Specimen:
    the same scan finds those formats in the Workbench intake and receiver code.
- `website/ask-carbon/tests/client-material-exclusion.test.mjs`:
  - The assistant's runtime (`worker/`, `public/`) imports nothing outside its
    own tree, and a computed import is reported rather than trusted. Specimen:
    the offline evaluation harness, which really does import Workbench code.
  - Knowledge paths that are absolute, contain `..`, or are symlinks pointing out
    are refused.
  - The internal Workbench build names no route to the assistant. Specimen: the
    Pilot Designer preview, built from the same tree, does.

**What a future caller would have to do to reintroduce a route.**

- **Study route:** change the equality between the request's physical
  definition and the granted public one. That is the scientific contract of
  `WorkbenchScience`, not incidental code, and the sentinel test fails.
- **Authoring route:** read a request field into `compile_request`'s input, and
  the sentinel test fails.
- **Assistant runtime:** import anything outside `website/ask-carbon/{worker,public,knowledge}`,
  or compute an import, and the import test fails.
- **Stated limit:** a *new* module that reads a client record by path, without
  naming its format, and sends it somewhere, is not caught by these tests. They
  pin every route that exists. Stopping one that has not been written yet is what
  E1 adds: client records encrypted at rest under per-client keys that neither
  the subnet side nor the assistant ever holds. Until E1 lands, that residual is
  real and stated here rather than hidden.

**Open owner question, recorded rather than decided.** The public Pilot
Designer's optional AI assist sends what a visitor types into the public site
(their own draft, before Carbon has received anything, after explicit consent)
to the public assistant and its model provider. The v1 wording covers "Workbench
client material, and nothing derived from it that contains client parameters".
The working reading is that E8 starts when Carbon receives material, so a
visitor's own pre-receipt text is outside it. That reading leaves a launched
product unchanged, and the handoff says none of E1–E9 is a prerequisite for
anything already launched. The owner may read "the parameters are the secret"
more broadly. The single identifier concerned is named in the invariant test, so
it cannot widen silently. The internal Workbench, where received material is
held, has no route to the assistant either way.

## E9 — delivered (#315)

**Built:**
- The receiver is the one server that returns client records. The Workbench
  host returns no draft text, so its staff tokens are not in scope. The basis:
  a study response carries the binding and the result, never `draft_scope`.
- A staff credential alone opens nothing. The single-factor `authenticate` is
  removed. A principal is issued only by the access control that owns the
  brand, for a live session, and a session opens only with the credential and a
  current RFC 6238 code.
- An `ACTIVE` account without an enrolled second factor makes the directory
  refuse to load.
- Rate limiting per source, lockout per account (which refuses even a correct
  code and ends live sessions), rejection of a replayed code, a per-session
  request rate, and a session lifetime.
- `401`, `423` and `429` with `Retry-After`.

**Pinned by:**
- `tests/test_team_access_control.cjs`: RFC 6238 vectors, and every refusal
  paired with its success.
- The structural assertion in `test_team_intake_server.cjs`: identity is
  resolved only through `access.authenticate`.

**Values:** the limits are engineering defaults in `DEFAULT_LIMITS`, for the
review to change. Escalation and abuse response are policy, and stay behind the
review.
