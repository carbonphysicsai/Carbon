## 2026-10-21 — LAUNCHPAD-ENDPOINT-VERSIONS-01: published endpoints name the Challenge version

**Ruling (Validator, 2026-10-21, option (a)):** Launchpad's published
evaluation endpoints carry the Challenge version in each entry, under
`carbon.launchpad.published-endpoints.v2`. A receiver serves exactly one
(Challenge id, version), and one Challenge may have several intake versions.

**Decision:**

- v2 entries are closed: `network`, `netuid`, `challenge`, `version`,
  `intake_url`, `receiver_hotkey`. The version must be a registered intake
  version of its Challenge; a list that breaks this, or repeats or conflicts
  on an (id, version), publishes nothing (as v1 did for malformed lists).
- v1 lists are still read. A v1 entry applies to its Challenge only where
  the Challenge has exactly one intake version; where it has several, none
  of its versions is published, and Review (`published_endpoint_unversioned`)
  and setup say so. A v1 entry never covers several versions.
- Review writes every published endpoint into the runner profile's new
  optional `version_intakes` field, `{id: {version: [receiver-paired
  targets]}}`, for exactly that version. A Challenge named there is named
  nowhere by id (the profile refuses both), and each campaign reads its
  intake through `intake_targets.for_version` for its own version, so no
  version's submit reads another's endpoint. Existing profiles (id-keyed
  `intakes`/`receivers`/`intake_targets`) validate and read as before.
- The shipped `published_endpoints.json` is empty and is bumped to v2.

**Not changed:** the miner's own intakes stay named by Challenge id, as
before (Review still resolves an id to its registered campaign).
