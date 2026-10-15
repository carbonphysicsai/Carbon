# Historical Launchpad cells recorded on 2026-10-15

Authority: OWNER-LAUNCHPAD-E2E-SUITE-01 R2. No new run, signer read, provider
request or chain transaction was performed for this backfill.

| Cell | Historical result | Original source / limit |
|---|---|---|
| F01 attempt1 | FAIL, installer exit126 | Fresh-miner README step1; executable-mode defect LA-F1. Original failed checkout SHA absent, explicitly UNRECORDED; do not attribute later successful source to this attempt. |
| F01 attempt2 | PASS at f1dd652debdfc7a6875c38ef988b1fd3c0ccb26b | Same README; installation and service/image records. LA-F2 untagged-image finding remains linked. |
| F03 | Owner-confirmed historical PASS | Ryan's direct R2 and findings LA-F3. Revision refers to the installed fresh-machine checkout, not a fresh signer/finality observation. Actual owner-used registration command differs from the prepared command; the latter was not exercised. |
| F07, Oct08 | FAIL, context_ceiling and withheld practice feedback | Findings LA-F8/LA-F9; supervisor COMPLETED while both Graphite stages STOPPED, no plan/freeze. Original source f1dd652de; no clean positive smoke inferred. |

Cell JSON uses the existing acceptance-cell schema and points to original
findings. Missing original signer projection/finalized hash is explicit in F03.
These records do not certify a current released image or close the current
T07 F05-F12 path. The scoreboard starts with two historical PASS observations
and two recorded failed attempts, with their original scope and findings.

`within_cap` for F01/F03 refers to the install/read-only setup cells, not an
assertion about unrelated host charges or a new registration transaction. F07's
original provider figure was below its original approved cap; the public cell
records only that Boolean, not spend totals. No financial allowance is created.
