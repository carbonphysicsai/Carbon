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

## E1 — delivered (#318)

**Built:**
- Every record's client content is sealed on disk with AES-256-GCM, under a key
  that belongs to that record alone, bound to the record's identity.
- A store cannot be opened without a keyring, and the receiver will not start
  without one. The keyring is refused inside the store's directory.
- An approved deletion destroys the key first. Every copy of the record, in the
  store and in any backup, is then unreadable, and opens as
  `ARCHIVE_KEY_DESTROYED` (`410`).
- Keyring handles merge rather than overwrite, and a destruction always wins.

**Pinned by:** `tests/test_team_archive_encryption.cjs`. No client text reaches
the disk or a backup, with an in-memory specimen. A backup taken before
deletion becomes unreadable for that record while its other records still
read. Moved ciphertext is refused. The receiver will not start without a
keyring.

**For the review:**
- Key material sits in the clear in a `0600` file.
- Freed filesystem blocks are not scrubbed.
- A backup of the keyring is not reached by key destruction.

## E4 — delivered (#318)

**Built:**
- The store accepts only a basis the record-basis module issued, and it issues
  one only for a complete set of references: a mutual NDA for SCOPING, or an
  MSA and an Order Form for STUDY. A record without an agreement reference
  cannot be built, and a copied literal is refused.
- `retention.legal_basis` is `contract:<reference>`.
- The same bytes under a different agreement are a conflict.
- SCOPING is promoted to STUDY once, append-only.
- Records written before E4 answer `409` until a steward attaches their basis.

**Pinned by:** `tests/test_team_record_basis.cjs`.

## E5 — delivered (#318)

**Built:**
- An export names its recipient and purpose, or releases nothing. The entry is
  durable before the content is returned.
- A copy sent onward by hand is recorded with its digest.
- Entries hold digests and references, never content, so they outlive the
  record. A deletion tombstone names every prior release.
- A pre-E5 store records `PRE_E5_RELEASES_NOT_LOGGED`.

**Pinned by:** `tests/test_team_release_log.cjs`.

**Limit:** a copy leaving the local Workbench that nobody records is invisible
to the log.

## E6 — delivered, except the client-side format (#318)

**Built:**
- The transport copy is recorded in two states that are never collapsed:
  `MOVED_TO_TRASH`, with `purge_expected_by`, then `PERMANENTLY_REMOVED`. They
  move forward only, and each is marked `RECEIVER_ATTESTATION`.
- A relay states its channel and how the package arrived. A `PLAINTEXT` arrival
  records `PERMANENTLY_REMOVED_WITHOUT_DELAY`.
- A standard-library STARTTLS SMTP transport, configured by the operator only
  and sending only to the sender's own domain.
- A missing credential (`NOT_ATTEMPTED_NO_CREDENTIAL`, `501`) is distinct from a
  rejected one (`CREDENTIAL_REJECTED`, `502`).
- The credential is sent only after TLS verifies, and only reply codes are kept.
  The outbox's catch-all no longer records an unexpected error's text.

**Pinned by:**
- `tests/test_team_transport_copy.cjs`.
- `tests/test_team_mail_transport.cjs`, whose leak test uses the credential as
  its own specimen. The servers provably received it, one echoes it back, and
  it appears in no record, response, export, log or error.

**Proposed, not built:** the client-side encryption format, key custody,
plaintext handling and key publication. See
`Business/Carbon_Fit/workbench/docs/E6_INTAKE_ENCRYPTION_PROPOSAL.md`.

**Known limitations:**
- No Vault, so there is no retention rule and no legal hold on mail.
- A possible administrator restore window has not been verified.
- A full intake mailbox bounces unobserved.

## E3 — delivered (#318)

**Built:**
- `retention.v2`: `closure_event`, `active_period`, `archive_period` and
  `scoping_expiry` replace `production_period`, all null. Each record has a
  `closure` slot.
- A STUDY record reads `NOT_APPLICABLE_STUDY_RECORD` for the scoping expiry.
- v1 records migrate, keeping their archive facts and inventing nothing. A v1
  record that ever carried a non-null `production_period` stops the store from
  opening.

**Pinned by:** `tests/test_team_retention_schema.cjs`.

## E2 — delivered (#318)

**Built:** the job reads counsel's values from operator configuration
(`CARBON_TEAM_RETENTION_VALUES_FILE`), never from literals.

**Null behaviour, demonstrated in `tests/test_team_scheduled_destruction.cjs`:**
- With no values, the plan and the run are `REFUSED` and all four missing values
  are named. Nothing is computed, applied or skipped, and the refusal is
  recorded.
- With some values set, the run is still refused, while the plan shows what the
  set values would do.
- A record with an unknown receipt time stops the run.
- With every value set, which is synthetic and tests only: SCOPING expiry,
  archive at the end of the active period, and destruction at the end of the
  archive period (key first) each happen when due and not before. An open study
  is kept.

**Proposed, not built:** a record-level hold that both destruction paths
refuse, to be decided before any period is set.

## E7 — delivered (#318)

**Built:**
- Content (read, export, update, archive, restore) is reachable only by an
  account screened under the configured standard, and only once the record
  carries an export-control reference.
- The standard is counsel's (`CARBON_TEAM_SCREENING_STANDARD`). **While it is
  unset, no record's content is reachable by anyone.**
- A screening names its standard, so changing the standard invalidates earlier
  screenings.
- The reference is recorded once and never replaced. Records written before E7
  are unreachable until they have one.

**Pinned by:** `tests/test_team_screened_access.cjs`. Each refusal is paired with
its configured success.

## Working decisions under the owner's delegation (2026-09-23)

The owner asked for these four to be settled by engineering judgement, on what
makes the Workbench most effective for Carbon and its clients while development
and testing continue. They stand unless the owner objects. None of them settles
a legal question, and none authorizes deployment or collection.

1. **E8 and the public Pilot Designer.** The exclusion starts when Carbon
   receives material, so the public assist stays. It will receive only the
   written answers and never the quantity fields (ranges, units, operating
   values). The consent text will tell visitors not to enter confidential values
   there, and the Data Handling Statement will say the same.
2. **E6 section 3.** The proposal is approved as written:
   - the in-browser *Download encrypted for Carbon* button, using P-256 ECDH
     with AES-256-GCM, with OpenPGP only on request;
   - on a plaintext arrival: relay it, record it, delete the mail permanently at
     once, and reply with the encryption steps;
   - the intake key is generated by the owner on the internal machine, with one
     encrypted offline backup in the owner's password manager.

   The button stays unreleased until the owner has generated the real key.
3. **E2 record hold.** Build it now: a steward-set hold, append-only, that both
   the scheduled destruction job and the key destruction on an approved deletion
   refuse. Whether a hold is legally required remains counsel's question.
4. **E7 before counsel's standard.** A synthetic development standard may be
   configured so development and testing continue. While it is in force, only
   records whose agreement reference is synthetic are reachable, and a real
   agreement reference is refused. Real client records stay unreachable until
   counsel's standard replaces it.

Items 3 and 4 are built: the record hold (`tests/test_team_record_hold.cjs`) and the synthetic development standard (`tests/test_team_synthetic_standard.cjs`). Items 1 and 2 change the public Pilot Designer page, whose exact bytes are pinned by Ask Carbon's public release candidate. They therefore go through a new release candidate, and the owner's publication approval, as their own change. For item 2, the owner generated the intake key on 2026-09-24, with its encrypted offline backup, and the button is wired to it (`data/intake_public_key.json`, stacked on item 1's pull request). Both wait only for the new candidate and the owner's publication approval. One correction to item 1 as first written: the assist already never received the quantity fields. The exposure is the free-text `operating_envelope` and `requested_targets` pilot fields, which is what item 1 will withhold.

## External model provider: Chutes, a per-client switch that defaults off (owner direction, 2026-09-26)

**Direction.** The owner named Chutes as the external model provider for client
intake and asked for the capability to be built. The guard against automatic
transfer stays. It stops being a permanent block and becomes a per-client switch
that defaults off. No client content goes through it: there is no client and no
signed opt-in, so the path is proved on synthetic material only.

The counsel brief's §8.4(c) conditions, as the owner relayed them:

| Condition | State |
|---|---|
| Provider named in the MSA provider schedule | Satisfied. Chutes is named in `data/client_model_provider_schedule.json`, which is the engineering side of the schedule; the MSA itself is held outside the repository. |
| No training on inputs; zero or minimal retention | The owner's determination (TEE, and an API that cannot decrypt the request). Recorded as the owner's, not as an engineering verification. |
| Separately signed per-client opt-in | Required and unchanged. It defaults off, and none exists. |

§7 and §4.8 of the brief hold in full. E8 is unrelated and unchanged: nothing
here reaches the subnet or the public Ask Carbon assistant.

**Model.** `deepseek-ai/DeepSeek-V4-Flash-0731-TEE`. Confirmed from
`GET https://llm.chutes.ai/v1/models` on 2026-09-26:

- $0.44 input / $1.32 output per million tokens;
- 1,048,576-token context and 131,072-token maximum output;
- tools supported, and `confidential_compute: true`.

Context is the deciding property, because client briefs are long. The TEE
premium over the same model on Engy is deliberate. Launchpad stays on Engy and
the two are not consolidated.

**Built** (`tools/team_model_provider.cjs`, store and receiver):

- A provider can only be built from a schedule entry, and it sends only to the
  scheduled endpoint. An opt-in can only be issued from a signed-document
  reference. The store refuses a copied literal of either.
- The switch is per record, off at receipt, and append-only.
  - A data steward turns it on with the client's opt-in, or off on withdrawal.
  - Records written earlier read as off.
- Only an explicit reviewer request, `modelAssist`, reaches a provider. It must
  pass E7 reachability, an active opt-in for that provider, and the
  synthetic-only restriction.
- Each request is logged as an E5 release (`MODEL_PROVIDER`, `EXTERNAL_MODEL`,
  request digest, opt-in reference) before it is sent.
- The request carries the brief, the pilot and the open assumptions, never the
  contact details.
- **Synthetic only, as built in #371.** `MODEL_PROCESSING_SYNTHETIC_ONLY`
  refused any record with a non-synthetic reference. The owner lifted it the
  same day; see below.
- Credential handling:
  - The key is read from its file at send time; the file must be `0600`, not a
    link, and at most 1024 bytes.
  - Only a status code is kept from a provider's refusal, because an error body
    can echo the request.

**Pinned by:** `tests/test_team_model_provider.cjs`. Each refusal is paired with
the same call going through:

- the switch is off by default;
- nothing is sent automatically;
- real references are refused under counsel's standard (as built in #371;
  superseded below);
- forged opt-ins and providers are refused;
- an opt-in for another provider is refused;
- withdrawal turns the switch off;
- the release is logged before a failed send;
- the contact details are withheld while present in the record;
- the credential appears nowhere that is kept;
- unsafe credential files are refused;
- the same behaviour holds over HTTP.

**Live synthetic observation.** `tests/live_model_provider_rehearsal.cjs`
sent one synthetic Path A record, with a synthetic opt-in, to the scheduled
model: 1,010 prompt and 104 completion tokens, 1.6 s. The observation is private
evidence and is not stored here.

**Limit.** A copy that staff export and paste into a model by hand is outside
the receiver. It is covered only by E5's recorded-release rule.

## Synthetic-only lifted; counsel approves E7 (owner, 2026-09-26)

**The owner lifted the synthetic-only restriction.** The gate was removed from
the code rather than switched off. A real client's record can now go to the
scheduled provider. What still has to hold:

- that client's own separately signed opt-in is recorded by a data steward;
- the request is an explicit reviewer request, logged before it is sent;
- the reviewer is screened under counsel's E7 standard.

**One guard replaces the gate.** A synthetic opt-in reference cannot open a real
record. It is refused when recorded on any record with a real agreement or
export-control reference, and again at send time. This is the same rule as the
synthetic E7 standard, which reaches synthetic records only.

**Counsel approves E7,** as the owner reported on 2026-09-26. The approved
standard is operator configuration (`CARBON_TEAM_SCREENING_STANDARD`) and is not
written here. Once it is configured, it replaces the synthetic development
standard of decision 4. Until then, real records stay unreachable, opt-in or
not.

**Pinned by** `tests/test_team_model_provider.cjs`:

- a real record is off by default;
- a synthetic opt-in is refused on each kind of real reference;
- the client's signed opt-in sends, and the release names it;
- under the synthetic development standard, a real record stays unreachable
  even with a signed opt-in.

Each refusal is paired with its specimen.

No real client, signed opt-in or client content exists yet. Nothing has been
sent.

## Open questions that remain

- **Counsel:** the retention values (E2, E3), and whether a legal hold is ever
  required. The E7 screening standard is approved and is configured privately.
- **Owner:** the security review's spend figure, and when to prepare the new
  Ask Carbon release candidate that carries decisions 1 and 2.
