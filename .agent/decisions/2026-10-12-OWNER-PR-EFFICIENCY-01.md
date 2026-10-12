## 2026-10-12 — OWNER-PR-EFFICIENCY-01: owner decision records batch daily, one PR per ticket, separate PRs only for security or release blockers

**Authority.** The owner, 2026-10-12, approving an efficiency proposal put to
him in the Test Lead session, relayed verbatim by the Test Lead:

> I approve that efficiency change

The one-line approval is the owner's. The four rules below are the Test Lead's
formulation of the proposal he approved, recorded here as relayed; the owner
has not restated them himself in this session.

**Decided:**
1. **Owner decision records go in one batched pull request per day**, owned by
   PR Head, unless a release or a gate needs a record sooner.
2. **One pull request per ticket.** A follow-up fix is pushed to the open pull
   request, not opened as a new one.
3. **Separate pull requests only for security-sensitive or release-blocking
   changes.**
4. **Operator sheets and working notes stay out of the repository.**

**Scope.** This is engineering process. It changes nothing about authority: it
does not alter what requires the owner's own word (grants, spend figures,
security and isolation acceptances, LIVE, mainnet, release cuts), and it does
not permit a record to be withheld from a gate that needs it. Rule 1's
exception is what keeps a grant or security record from waiting on a batch.

**Applied from:** 2026-10-12, this record. PR Head pushes back on a new pull
request that should have been a commit on an open one.
