## 2026-10-03 — GRAPHITE-MINER-S2: the miner edition's literature (shared pack, private library, hunt, import, focus)

**Authority.** OWNER-GRAPHITE-MINER-01 (owner, 2026-10-03) §3 and §5: the
shared card pack ships with the product (the frozen phase-2 snapshot, 1,773
cards, served UNCHECKED, its `withheld_protected` cards left out); miners may
hunt arXiv for more on their own model and budget at no more than one request
every 3 s with deduplication, into a private library layered over the pack;
miners may import their own text; hunts are focused on the Challenge's public
discovery document with a graded per-Challenge ranking that uses only public
material and the miner's own practice results. OWNER-LAUNCHPAD-PROD-01 keeps
its boundaries, and OWNER-LAUNCHPAD-PROD-02 #1 and #10 apply: no
Carbon-imposed output cap on the miner's Reader calls, and no access to hidden
test conditions. The choices below are engineering choices within those
decisions. No scientific value, threshold, gate or tolerance, no spend
default and no authority boundary changes.

**Decision.**
1. **The shared pack** (`carbon/agent_campaign/graphite/miner/pack.py`,
   schema `carbon.graphite.miner-card-pack.v1`).
   - `scripts/dev/graphite_pack.py build` reads the phase-2 snapshot read
     only. Its sha256 must equal its file name and the pinned
     `SOURCE_SNAPSHOT_DIGEST`
     (`sha256:4adb013dd64a18678ccb44589199b96d40b92944dd57fffb1a1218fe80efebfe`),
     its index must
     match its digest, and every card must be `UNCHECKED`, or the build is
     refused.
   - The pack keeps the snapshot's ten method-card fields for every indexed
     card, less the `withheld_protected` cards and any card the current
     `tools.protected` rule flags (none today): 1,773 cards.
   - `SHARED_PACK_DIGEST`
     (`sha256:d517b69672ee06c84c53337dbad57fc1f03cb04c89292c3dedc7a94f98163ec5`)
     is the sha256 of the uncompressed canonical document. The file
     `packs/<digest>.json.gz` is gzip level 9, no file name, mtime 0, so the
     builder reproduces it byte for byte (`check` verifies this); the loader
     verifies the document, never the wrapper.
   - The pack also lists by id the 1,160 papers phase 2 read but did not
     index (not relevant, rejected or withheld). A hunt treats them as known
     papers, so no miner pays to read them again. Ids only, no content.
   - A missing, damaged, renamed or tampered pack is refused
     `literature_pack_missing` (next step `install --update`). `freeze_into`
     copies the pack write-once into a campaign root and `load_frozen` serves
     that copy, so a later product update never changes a frozen campaign.
   - Rights: titles and abstracts are arXiv descriptive metadata (CC0 1.0);
     the other fields are Carbon's extraction. The pack says so.
2. **The private library** (`MinerLibrary(root)`,
   `<profile root>/graphite-library/`).
   - Owner-only: the root and every directory 0700, every file 0600; an
     absolute, non-symlink root the miner owns. Content-addressed and
     write-once where it holds content; append-only where it is a journal.
   - Hunted cards are `method_cards.make_card` cards in a
     `method_cards.CardStore`, with their arXiv records in a
     `literature_fetch.RawStore`. Imported texts and their cards have their
     own write-once stores.
   - **Claims.** Every Reader call is preceded by a write-once claim on the
     paper's key (arXiv id lower case, `/` as `-`, no version) or the import
     id. A claim is written whole to a temporary file and hard-linked into
     place, so a crash leaves a complete claim or none. A claimed key is
     never claimed again. A claim is released only when the reader says the
     call was certainly not sent (`ReaderNotSent`). An open claim (outcome
     unknown) is retried only by the same hunt with the byte-identical
     request, so the driver's ledger replays it; any other open claim is
     never sent again. The Library lists such an import as
     `outcome_unknown`, not `queued`.
   - **Journals** (curation, outcomes, plan index, hunt progress) are
     append-only and fsynced per line. A torn final line a crash left is
     never read as a line; the next append cuts it off and records it in
     `<journal>.torn`.
   - **Curation journal.** Pins and bans, with a digest over the resulting
     state; every state is stored by digest. A ban unpins; a banned card
     cannot be pinned. Pinning or banning needs a card the library serves;
     undoing a pin or a ban always works.
   - **Plans** are stored write-once by digest with an index of
     `{digest, created_by, parent, created_at}`. The library checks only
     `created_by` (`planner` or `miner`), that a parent exists, the size and
     protected material; the plan schema is the driver's (S3).
   - **Outcomes** (`record_outcome(..., challenge=)`) are the miner's own
     practice results per cited card on one Challenge `{id, version}` (a
     version is required), recorded once per identical entry. The ranking and
     the learned queries read only how many improved and how many did not on
     the same Challenge and version (AGENTS.md 7.6): practice on one
     Challenge never steers another.
   - **Snapshots** freeze the private layer (served cards by digest and the
     outcome counts per Challenge) so a campaign serves exactly what it
     froze.
3. **What a campaign serves** (`MinerLiterature`). Frozen by the pack
   digest, a private snapshot digest, a curation state, the Challenge
   `{id, version}`, the focus rule digest, the digest of the public inputs
   its ranking reads (`focus.frozen_context`: the discovery document cut to
   `DISCOVERY_FIELDS` and the contract cut to capability statuses) and the
   miner's focus terms. Together they give a `literature_digest`: the same
   digest always serves the same cards, grades and order. `record()` carries
   the frozen context, and passing it back (`context=`) replays the view
   whatever Carbon's registries hold later.
   - Every served card carries `origin` (`shared`, `miner_hunt`,
     `miner_import`) and `check_status` `UNCHECKED`, with an UNCHECKED note.
   - One predicate (`MinerLibrary.served_card`) says what the library serves:
     a pack card the protected rule does not withhold, or a private card the
     pack does not shadow (its paper is not one the pack knows) that is
     relevant and names no protected material. A card outside it cannot be
     read, pinned, banned or cited in an outcome (`card_not_found`); a banned
     one is refused `card_banned`. A pin the view does not serve is not one
     the Planner can consider: `pinned()` lists only served pins.
4. **The hunt** (`hunt.run_hunt`).
   - Imports first, then queries in this order: the miner's own (at most 8,
     at most 6 terms of `[A-Za-z0-9-]`, at most 40 characters a term, no
     operator words; raw query syntax is refused `hunt_query_invalid`),
     at most 2 seeded by the miner's own improved outcomes on the same
     Challenge, at most 6 composed from the public discovery document, then
     the registered `QUERY_SET`.
     Carbon writes every search: each term quoted in the abstract field, all
     required, restricted to the categories cs.LG, physics.comp-ph, math.NA,
     eess.SY, physics.chem-ph, cond-mat.mtrl-sci and stat.ML.
   - Deduplication against the pack, the claims and the private store comes
     before triage and before any Reader call.
   - The first-pass triage is free and deterministic: an allowed category,
     and the record's title and abstract name the Challenge's primary domain
     (its first two domains), a secondary domain together with a surrogate
     cue, two method cues one of which is a surrogate cue, or every term of
     one of the miner's own queries. A secondary-domain word ("temperature",
     "aging") or broad machine-learning words never keep a record alone. A
     record naming protected material is withheld before any call.
   - The Reader prompt is the miner variant (`READER_PROMPT`, pinned by
     digest), with the same closed answer fields, so `parse_extraction`
     applies unchanged. Extraction is Challenge-neutral, so a card serves
     every Challenge and a paper is never read twice; per-Challenge relevance
     lives in the ranking. The internal `method_cards` prompt and request are
     unchanged: the miner request mirrors `extraction_request`'s shape.
   - `max_records` (default 200, at most 5,000) counts new papers after
     deduplication, so it bounds the hunt's Reader calls. 50 records a page,
     at most 2 pages a query, so a large `max_records` can end `COMPLETED`
     below it: the report says how many queries the page bound cut short
     while arXiv had more (`page_bound_queries`).
   - An arXiv `FAILED_INFRA` ends the hunt, recorded (`literature_fetch_failed`),
     and the campaign goes on. `ReaderNotSent` ends it `STOPPED` with the
     reader's code (for example `research_share_reached`). `checkpoint` runs
     before every page and before every claim and call; a pause there leaves
     nothing claimed.
   - Every hunt has an explicit id (required; the driver's, distinct per
     campaign stage), so a later campaign with the same plan hunts again
     rather than receiving an earlier report. A hunt id's report is written
     once; the same hunt replays it with no arXiv or model call. A hunt id
     reused with another hunt (Challenge `{id, version}`, the miner's
     queries, registered queries on or off, caps, Reader prompt, focus rule,
     pack or model selection) is refused, finished or not. A resumed hunt
     keeps the queries and the Challenge focus it started with and never
     fetches a journalled page again.
5. **The arXiv gate** (`ArxivGate`). One file per user and host
   (`$CARBON_ARXIV_GATE`, else `$XDG_CACHE_HOME/carbon/arxiv-gate`, else
   `~/.cache/carbon/arxiv-gate`), 0600, under an exclusive lock. It holds the
   last request time; every request of every hunt, retries included, waits
   until 3 s (or a longer backoff) have passed since it. A clock that reads
   earlier than the recorded time waits a full interval.
6. **Focus and ranking** (`focus.py`, rule `carbon.graphite.miner-focus.v1`,
   pinned by digest).
   - Only the discovery fields `DISCOVERY_FIELDS` are read: title, task,
     interface units and meanings, reference and protocol, the rebuildable
     model families and the public training-set size.
   - A grade 0-3 with reasons from a raw score (`SCORES`): 3 for the
     Challenge's primary domain, 1 for a secondary one, 1 for one of its
     methods, 1 when a capability the card names is rebuildable under the
     Challenge's public contract (`capability_registry.public_registry`), 1
     when the card names every term of one of the miner's focus terms (the
     campaign's hunt queries), and +1 or -1 from the miner's own outcomes on
     the same Challenge. A card whose named capabilities are all outside the
     contract is a `capability_request` candidate, not a plan input, and
     grades at most 1. Pins come first and say so. Bans, pins and focus terms
     all steer the ranking.
   - Only `RANKED_FIELDS` of a card are read (title, technique, claimed
     effect, data regime, abstract). `applicability` is left out: it is the
     phase-2 extraction prompt's speculation about Carbon's battery
     Challenge, not the paper's content. No other field, and nothing in an
     outcome's evidence beyond its two counts, can change a grade or an order.
   - The rule's document holds its lexicons, limits, triage rule and score
     weights, so any change to them changes its digest. The rule was revised
     before release (triage, focus terms, weights in the document); no
     campaign has frozen an earlier digest, so it keeps the name
     `carbon.graphite.miner-focus.v1` with the pinned digest
     `sha256:da91b31634ddcc511dc7d75a3599b485ffa99e04ecddc0dbe1ab465450fd7448`.
     From the first release on, a change is a new rule version.
7. **Imports** (`library_import`). A one-line title of 1-300 characters and a
   text of 1-20,000 characters, no control characters, no protected
   material, or `import_invalid`. Content-addressed ids, so the same text
   queues once. The next Reader stage extracts it into a `miner_import`
   card whose abstract is the text's first 4,000 characters. PDF import stays
   a follow-up.

**Imports.** The literature modules, and everything they import, load no
grant, pod, experiment, delivery, triage, next-level, ladder, controller,
provider or model module (a subprocess test checks `sys.modules`). Importing
them through the package today also runs
`carbon/agent_campaign/graphite/__init__.py`, which is not S2's: it imports
`provider` eagerly, which loads `grant`, `controller`, `ladder` and
`next_level` (loaded, never called). A strict expected-failure test records
this gap; making that `__init__` lazy is handed off, and the mark comes off
when it is.

**Unchanged.** Every internal Graphite module, prompt and digest
(`method_cards`, `literature_fetch`, `literature`, `tools`); the phase-2
snapshot, read only; every frozen plan, prompt, digest and journal. Every
scientific value, threshold and gate; no hidden-test access; no chain
writes; no weights. Contributing cards back to the shared pack stays
deferred; provenance and origin are its seam.
