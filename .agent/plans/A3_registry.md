# A3 challenge registry implementation plan

**Ticket:** A3 — Challenge registry + LIVE qualification hash gate
**Branch:** `agent/a3-challenge-registry`
**Exact base:** `e6fb20b1dc361ded442fcf41d118cea5f2c775cd`
**Status:** done

## Authority and reconciliation

- Implement `Design_Specs/Build_Out.md` C1 and section 8 under the domain
  specifications and root `AGENTS.md`.
- Keep `(challenge_id, version)` as the immutable `ChallengeKey`.
- Verify only tagged SHA-256 digests computed from actual regular-file bytes
  beneath an explicitly configured artifact root.
- Require the exact eight qualification slots and their slot-specific states;
  do not interpret evidence as scientific or signer authorization.
- Preserve four independent fixture barriers: fixture status, fixture
  qualification mode, save-immutable-per-key `fixture_origin`, and an explicit
  fixture-mode gate call. Production rejects fixture origin after relabelling.
- The ratified `Build_Out_Protocol_Extension.md` adds optional reserved bindings
  for receipt schema and backend profile identity. A3 will represent those
  bindings without selecting or approving a real backend. The generic artifact
  map and `train_backend` slot bind environment/backend qualification references
  and hashes. Receipt signing and backend execution remain later work.

No authoritative source changes the ticket's ChallengeKey, SHA-256, exact-slot,
or fixture-isolation contract. No qualification-manifest signing mechanism is
currently ratified.

## Archaeology

| Area | Disposition |
|---|---|
| `carbon/registry/` | KEEP namespace; implement A3 here |
| `carbon/qualification/` | KEEP human-owned boundary; no scientific logic added |
| `carbon/challenges/*` | RETIRE/defer; it is not A3's canonical registry authority and remains untouched as history |
| historical mutable challenge dataclasses/loaders | REPLACE for A3 semantics; retain untouched |
| PoC raw-byte SHA-256 patterns | WRAP concept only in dependency-free A3 helper |
| mutable runtime backbone registry | KEEP for its own role; do not import from A3 |
| PoC scoring, seeding, cards, and execution | Defer; outside A3 |

## Implementation

1. Add frozen, slotted registry models and stable validation/errors.
2. Add strict deterministic JSON parsing/serialization, duplicate-key checks,
   exact file-location identity, scan duplicate detection, descriptor-relative
   access, per-key locking, and same-directory atomic replacement.
3. Add descriptor-relative artifact access and one-open SHA-256 verification of
   actual regular-file bytes.
4. Add deterministic diagnostic LIVE assessment, effective-LIVE revalidation,
   checked activation, ordinary-save restrictions, fixture-origin isolation,
   a non-empty production LIVE backbone declaration, and exact challenge-version
   backbone compatibility lookup.
5. Export the public dependency-free API from `carbon.registry`.

The canonical record path is
`<registry_root>/<challenge_id>/<version>.json`; artifact bindings are POSIX
relative paths beneath a separately configured artifact root. Digests have the
only accepted form `sha256:<64 lowercase hexadecimal characters>`.

The public exact-version API is `load(challenge_id, version)`,
`save(record)`, `scan()`, `assess_live_eligibility(challenge_id, version)`,
`can_go_live(challenge_id, version)`, `is_effectively_live(challenge_id,
version)`, `activate_live(challenge_id, version)`, and
`is_backbone_allowed(challenge_id, version, backbone)`. Fixture assessment is
an explicit keyword mode on the two eligibility APIs; activation is always a
production assessment.

The required slot/state pairs are fixed and ordered:

| Slot | Required state |
|---|---|
| `generator_envelope` | `APPROVED` |
| `generator_validation` | `PASSED` |
| `dossier_level_1` | `APPROVED` |
| `score_pack` | `APPROVED` |
| `mock_incompleteness` | `APPROVED` |
| `train_backend` | `QUALIFIED` |
| `launch_bar` | `SIGNED` |
| `mcp_readiness` | `SIGNED` |

Optional receipt/backend identities are reserved structural bindings. The
`train_backend` evidence must reproduce the record's ordered allowed-profile
binding exactly and the required profile must select from that binding;
`mcp_readiness` evidence must reproduce the record's receipt schema version.
These equalities do not approve a backend, establish scientific correctness,
verify a qualification signer, or make a receipt signed.

## Tests and verification

- Add `tests/cpu/test_registry.py` covering hostile parsing, exact identity,
  qualification structure, digest/path failures, activation atomicity and
  immutability, fixture barriers, compatibility, determinism, and import
  isolation.
- Add a static structure-only record and artifact under
  `tests/fixtures/registry/`; its `fixture` lifecycle, `fixture` qualification
  mode, required save-immutable-per-key `fixture_origin`, and explicit
  `fixture_mode=True` call are four independent barriers.
- Run the focused registry suite and full default CPU suite.
- Run strict Ruff and Black on every changed Python file, the no-new-debt gate
  against the exact base, and `git diff --check`.
- Build a no-dependency wheel, install it in a fresh environment, run outside
  the repository, and prove registry use imports no optional scientific,
  validator, MCP, or Bittensor modules.
- Run the inherited PoC smoke command and report its result without widening A3.

## Risks and boundaries

- Registry records and artifact paths are hostile input; all malformed state
  fails closed without leaking values, bytes, or private paths.
- A3 verifies structure, exact-version references, and artifact bytes only. It
  does not decide whether human evidence is scientifically correct.
- No ratified A2/A3 convention bounds canonical identifier length; this repair
  intentionally defers a protocol maximum instead of inventing one.
- No real challenge, fixture default, scientific threshold, backend approval,
  receipt/signature system, scoring, seeding, submission version resolution,
  or emission capability is added.

## Local verification evidence

- Untouched supported baseline: `258 passed`.
- Focused registry suite: `134 passed in 0.33s`.
- Complete default CPU suite: `392 passed in 0.74s`.
- Strict Ruff and Black: all six changed Python files clean.
- CI-equivalent no-new-debt gate against exact base: passed; inventory
  `Ruff 757/776; Black 62/68`, unchanged from the exact A3 base; no new debt.
- Fresh no-dependency wheel SHA-256:
  `06acded5a9b11c8420e660bf922f656fbc5d8fb85a96a46a0cd36e4e8089edbb`;
  outside-tree use loaded no blocked optional or Carbon execution modules.
- Inherited PoC smoke: exit 2 after protocol-only NumPy runs because
  `poc.generators.burgers1d.role_seed` is absent during legacy test collection.

A3 is `done` for its structural registry/LIVE-gate scope. Independent
review/rereview approved final head
`149f9a74351b02a9b615d0015c22b74187ab0f55`; repaired-head PR CI
`32377387086` passed; PR #14 merged as
`69b938d1c4fd0aca58276940d15df50b1b68e5d1`; reviewed-head ancestry is
confirmed; and exact-merge `main` push CI `32379421897` passed 392 CPU tests and
Code quality at inventory `Ruff 757/776; Black 62/68`, unchanged from the A3
base with no new debt and changed files clean. This supports **SPECIFIED**,
**IMPLEMENTED**, **TESTED**, independently reviewed, merged, and
post-merge-CI-verified maturity only for the structural A3 boundary. It does
not establish scientific, backend, security/operations, production, or
emission qualification, and no real challenge is LIVE. A4 remains `todo` and
has not started.
