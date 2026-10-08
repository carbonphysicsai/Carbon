## 2026-10-07 — DESIGN-TASKS-02: bounded task disclosure and producer diagnostics

Ticket: DESIGN-TASKS-02 (owner request, 2026-10-07). DEVELOPMENT only.

Decision: build a separate positive allow-list projection from the registered
task. It exposes buyer requirements and the action-grammar version, but no
task digest, bank identity/order, candidate or condition IDs, reference values,
seed, starts, or search order. Do not use the projection as a registration or
commitment identity. Keep P, diagnostic Q and evidence w distinct in every
aggregate. The producer diversity command accepts only a sealed bank and a
registered law with explicit masses and exposure inputs; it does not choose
those scientific values.

Why: the current task record is deliberately a private registration object.
A negative filter can miss a new protected field. A producer-only report must
not emit case-level results. These are reversible engineering choices within
the ticket; no scientific distribution or score policy is selected here.

Implementation: `carbon/design_search/task_projection.py`,
`task_measures.py`, `diversity.py`, `__main__.py`, and the #779 optimizer/cost
integration once its code is on main. Freeze code pins and toy tests accompany
the same PR. Alternative rejected: copying a task and removing known secrets;
future private fields would then leak by default. The old v1 task contract
remains available; no migration of historical records is implied.

If a lead disagrees, supersede this decision and adjust those modules and
their tests. Human-reserved inputs remain: actual P/Q/w, question law,
exposure limits, score use, attacks, power and LIVE qualification.
