# OWNER-CATALOG-LICENCES-01: the starter-model catalog licences

Date: 2026-10-23
Status: **DECIDED by the owner, directly in the Carbon Validator's session.** The question named the licences: LGPL-2.1 (DeepXDE) in 32 of 200 entries; otherwise MIT, BSD and Apache-2.0, plus WTFPL (pyaml) and MPL-2.0 (certifi, tqdm, in the base only); no GPL and no unlicensed component. Answer: "Allow LGPL, drop the accidental 24 (Recommended)".
Source: codex-queue/reports/CATALOG_LICENCE_LIST_20261023.md (+ .json), written by the catalog worker from package metadata and vendored LICENSE files.

**A correction to the counts in the question:** the list itself gives **7** entries whose backbone uses DeepXDE and **25** that only pin it through the shared coverage bundle. The question said 8 and 24. The owner's choice applies by kind: entries that use DeepXDE keep it; entries that don't, drop it.

## Decided

- **DeepXDE 1.15.0 (LGPL-2.1)** is allowed, **unmodified**, as a hash-pinned dependency, with its licence text shipped beside it, in the entries whose backbone actually uses it.
- **Entries that don't use DeepXDE drop the pin** (and pyaml, if only DeepXDE pulled it in). Their pair-identity receipts are re-run when their environment changes.
- **Every bundle's LICENSE is replaced** with the real upstream licence (or licences) of what that bundle vendors. The current "MIT License" text in all 200 is a placeholder.
- WTFPL (pyaml) and MPL-2.0 (certifi, tqdm) are accepted as listed.
- **Before serving:** the base versions are confirmed on the pinned image (the list was read from local venvs).

## Not covered

Any modified LGPL code; any GPL or unlicensed component; components added after this list.
