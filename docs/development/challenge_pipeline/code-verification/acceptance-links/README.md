# Later owner acceptance of historical MMS evidence

These three records link the merged OWNER-CODE-VERIFICATION-ACCEPT-01 decision
to exact solver images, criteria, decision bytes and measured public evidence.
They preserve the earlier HUMAN_INPUT and false acceptance flags as history.
The criteria digest uses the historical checker's canonical JSON SHA-256;
decision and measured evidence digests bind exact file bytes.

PyBaMM covers the accepted particle discretisation on the pinned battery image;
the owner's separate lumped-heat tolerance-tracking acceptance is retained in
the decision. GetDP covers the accepted magnetostatic MMS. Neither establishes
full application/reference adequacy or physical validation.

Elmer heat is conditional on the registered MMS end time t_end = 0.375. The
criteria record transcribes the accepted test, without changing a threshold.
Both the earlier t_end = 0.5 result and the separate t_end = 0.375 rerun are
bound as evidence: the earlier adverse time-order observation stays visible.
It does not become an accepted temporal test at t_end = 0.5.

The trust-map v2 panel carries reference_verification with family, image_digest,
criteria_digest and a nonempty evidence description. Its aggregate output
carries validated acceptance provenance rather than a caller PASS flag. v1
panels/maps remain history; re-export a disclosed panel under v2 to use this
reader. Maps still use only PUBLIC/RELEASED cases and never choose scored cases.

The deliverable generator reads the link, criteria, decision and measured
records from the same committed evidence revision or checked public export.
Absent/mismatched acceptance keeps dependent package joins and maps unavailable;
independent historical MMS observations remain visible. A rebuild, re-pin or
criteria change requires fresh evidence and a new owner acceptance link.
