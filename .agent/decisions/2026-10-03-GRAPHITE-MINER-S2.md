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
     id. A claimed key is never claimed again. A claim is released only when
     the reader says the call was certainly not sent (`ReaderNotSent`). An
     open claim (outcome unknown) is retried only by the same hunt with the
     byte-identical request, so the driver's ledger replays it; any other
     open claim is never sent again.
   - **Curation journal.** Pins and bans, with a digest over the resulting
     state; every state is stored by digest. A ban unpins; a banned card
     cannot be pinned.
   - **Plans** are stored write-once by digest with an index of
     `{digest, created_by, parent, created_at}`. The library checks only
     `created_by` (`planner` or `miner`), that a parent exists, the size and
     protected material; the plan schema is the driver's (S3).
   - **Outcomes** (`record_outcome`) are the miner's own practice results
     per cited card, recorded once per identical entry. The ranking reads
     only how many improved and how many did not.
   - **Snapshots** freeze the private layer (served cards by digest and the
     outcome counts) so a campaign serves exactly what it froze.
3. **What a campaign serves** (`MinerLiterature`). Frozen by the pack
   digest, a private snapshot digest, a curation state and the focus rule
   digest, which together give a `literature_digest`.
   - Every served card carries `origin` (`shared`, `miner_hunt`,
     `miner_import`) and `check_status` `UNCHECKED`, with an UNCHECKED note.
   - A card that names protected material is withheld when written and again
     when served. A banned card is refused `card_banned`; an unknown or
     withheld one `card_not_found`. A private card for a paper the pack holds
     is shadowed by the pack's card.
4. **The hunt** (`hunt.run_hunt`).
   - Imports first, then queries in this order: the miner's own (at most 8,
     at most 6 terms of `[A-Za-z0-9-]`, at most 40 characters a term, no
     operator words; raw query syntax is refused `hunt_query_invalid`),
     at most 2 seeded by the miner's own improved outcomes, at most 6 composed
     from the public discovery document, then the registered `QUERY_SET`.
     Carbon writes every search: each term quoted in the abstract field, all
     required, restricted to the categories cs.LG, physics.comp-ph, math.NA,
     eess.SY, physics.chem-ph, cond-mat.mtrl-sci and stat.ML.
   - Deduplication against the pack, the claims and the private store comes
     before triage and before any Reader call.
   - The first-pass triage is free and deterministic: allowed category, and
     the record's title and abstract name the Challenge's domain, two of its
     methods, or a term of the miner's own queries. A record naming protected
     material is withheld before any call.
   - The Reader prompt is the miner variant (`READER_PROMPT`, pinned by
     digest), with the same closed answer fields, so `parse_extraction`
     applies unchanged. Extraction is Challenge-neutral, so a card serves
     every Challenge and a paper is never read twice; per-Challenge relevance
     lives in the ranking. The internal `method_cards` prompt and request are
     unchanged: the miner request mirrors `extraction_request`'s shape.
   - `max_records` (default 200, at most 5,000) counts new papers after
     deduplication, so it bounds the hunt's Reader calls. 50 records a page,
     at most 2 pages a query.
   - An arXiv `FAILED_INFRA` ends the hunt, recorded (`literature_fetch_failed`),
     and the campaign goes on. `ReaderNotSent` ends it `STOPPED` with the
     reader's code (for example `research_share_reached`). `checkpoint` runs
     before every page and before every claim and call; a pause there leaves
     nothing claimed.
   - A hunt id's report is written once; the same hunt id replays it with no
     arXiv or model call. A resumed hunt keeps the queries it started with and
     never fetches a journalled page again; a hunt id reused with another plan
     is refused.
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
   - A grade 0-3 with reasons from a raw score: 3 for the Challenge's primary
     domain, 1 for a secondary one, 1 for one of its methods, 1 when a
     capability the card names is rebuildable under the Challenge's public
     contract (`capability_registry.public_registry`), and +1 or -1 from the
     miner's own outcomes. A card whose named capabilities are all outside
     the contract is a `capability_request` candidate, not a plan input,
     and grades at most 1. Pins come first and say so.
   - Only `RANKED_FIELDS` of a card are read (title, technique, claimed
     effect, data regime, abstract). `applicability` is left out: it is the
     phase-2 extraction prompt's speculation about Carbon's battery
     Challenge, not the paper's content. No other field, and nothing in an
     outcome's evidence beyond its two counts, can change a grade or an order.
7. **Imports** (`library_import`). A one-line title of 1-300 characters and a
   text of 1-20,000 characters, no control characters, no protected
   material, or `import_invalid`. Content-addressed ids, so the same text
   queues once. The next Reader stage extracts it into a `miner_import`
   card whose abstract is the text's first 4,000 characters. PDF import stays
   a follow-up.

**Unchanged.** Every internal Graphite module, prompt and digest
(`method_cards`, `literature_fetch`, `literature`, `tools`); the phase-2
snapshot, read only; every frozen plan, prompt, digest and journal. The
literature modules import no grant, pod, experiment, delivery, triage,
next-level or ladder module. Every scientific value, threshold and gate; no
hidden-test access; no chain writes; no weights. Contributing cards back to
the shared pack stays deferred; provenance and origin are its seam.
