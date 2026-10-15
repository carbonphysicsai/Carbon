# SCORELAB-V3-CALIBRATION-STOP-01-D1: bounded dispatch at the registered stop seam

Ticket: SCORELAB-V3-CALIBRATION-STOP-01. Working engineering decision, 2026-10-15.
Authority: acquisition-v1/acquisition.json calibration.release and owner_v3_numerics
calibration_report require checking each completed triple before later work.
Root and Research confirmed the eager 18-job invocation cannot satisfy this.

Use an optional `solve --calibration-binding FILE --calibration-binding-sha256 HEX`
mode, inside the existing pinned image (not nested Docker). The digest binds a
closed data-only contract containing scope, exact plan/digest, numerical-policy
digest, observer, execution source and actual source-file hashes. Require the
exact complete pilot jobs, fresh outputs and 1..2 workers before work. Do not
resume old unguarded rows, subtract partial triples or change the input menu.

Existing worker process pooling is bounded to a single three-rung physical
tuple. Returned rows are durable before the producer's _raw_rows/_extract and
existing calibration_report run. A compatible current tuple permits the next;
failures or unresolved quantities stop. The cumulative receipt still reports
missing future tuples. A complete six-tuple pilot is not full 15-tuple release.

Rejected: eager whole-pilot map with post-hoc check (spends after a stop);
Root polling/cancelling asynchronous worker output (race before next dispatch);
another solver, calibration formula or tolerance (not authorized); changing the
ordinary solve path (unnecessary historical behavior change).

Reversible: remove the optional branch and two CLI flags. Superseding change
touches this decision, worker and exclusive tests only. Root/Research must bind
the new execution-source hash prospectively; historical source identities stay
unchanged. Scientific thresholds, roles, source authentication by Root and full
release criteria remain unchanged. No new human-reserved value is needed.
