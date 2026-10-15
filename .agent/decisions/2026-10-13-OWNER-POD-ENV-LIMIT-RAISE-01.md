# OWNER-POD-ENV-LIMIT-RAISE-01 — the owner raises the pod-environment bound, overriding a Validator ruling

Date: 2026-10-13
Status: APPROVED by the owner, confirmed directly in the PR Head session. This
record documents an **owner override of a standing repository-authority
ruling**, not an engineering decision and not a consensus.
Authority: the owner. The Carbon Validator's contrary ruling is preserved below
in full, because the override is only meaningful alongside what it overrode.
Scope: `ENV_LIMIT_CHARS` 90,000 to 108,000, and the accompanying CI headroom
change subject to the conditions in §4.
Maturity: engineering control. No scientific or security acceptance is created.

## 1. What he approved

Raising `scripts/dev/exam_design/runpod/pod_env.py`'s `ENV_LIMIT_CHARS` from
**90,000 to 108,000** characters, as proposed on the Graphite Test executor's
branch `agent/pod-env-limit-raise`, together with a CI headroom test that
counts a 10,000-character Level 4 envelope allowance.

## 2. The ruling it overrides

Earlier on 2026-10-13 the Carbon Validator ruled on the same question:
**"neither raise the bound nor leave it; fix the growth."** The ruling held that
`ENV_LIMIT_CHARS` (90,000) and the 8,000-character headroom stay, and queued the
structural fix as **PLT-29 / `POD-ENV-STRUCTURAL-HEADROOM-01`** with these done
criteria: adding 100 shipped paths costs under 200 characters; a manifest
tampered with after the create is refused on the pod; and **the existing size
test passes unchanged**.

## 3. The reasoning put to the owner before he decided

He was given the Validator's case, unsoftened, and the recommendation was to
**hold and do PLT-29 first**:

- The bound is **deliberately conservative**, not a platform ceiling. It was set
  after RunPod answered every stage-A create with an opaque 500 when the
  whole-tree manifest put the environment near **131,000** characters
  (`GRAPHITE-POD-ENV-SIZE-01`).
- The only **measured** failure is near **118,000**. The "between 100,000 and
  250,000" in `pod_env.py:17-19` is a **code comment, not a measurement** — a
  distinction the merge manager got wrong earlier in the day and was corrected
  on.
- **108,000 is therefore about 10,000 below the one number observed failing.**
- The growth is **linear in shipped paths**. A compression change on #1294
  (`Z_FILTERED` deflate) lowered the constant without changing the slope, so
  raising the ceiling spends margin rather than removing the cause.

He chose to override. That is his to decide, and the Validator has accepted it
as his to decide.

## 4. Conditions the Validator attached, which the override does not displace

The owner approved **the figure**. The accompanying test-semantics change
remains subject to normal review, and the Validator will receipt it only if:

- **(a)** the runtime refusal in `pod_spec` stays at `ENV_LIMIT_CHARS`, **before
  any create**, unchanged in kind;
- **(b)** the 10,000 Level 4 allowance is **derived from the real maximum
  envelope the L4 admit path accepts**, citing that cap, **with a test tying the
  two so they cannot drift**. An asserted 10,000 is a guessed number; if the
  derived figure differs, the derived one governs;
- **(c)** the original assertion is **kept or strictly tightened**, never
  replaced by a looser one.

A guard that fails earlier than the real condition is conservative, which was
the 8,000 reserve's own purpose — so the direction is acceptable; it is the
**provenance of the threshold** that must change.

## 5. What remains in force

- **PLT-29 stays open**, with its original done criteria. The Validator has
  added a note to the queue entry that 108,000 being roughly 10,000 below the
  single measured failure makes per-file growth matter **more** now, not less.
- Nothing here authorises a further raise. A future change to this bound needs
  its own decision; a figure confirmed once does not extend itself.
- The merge manager **declined to push the branch**, because the proposing
  session's own classifier had blocked its push and carrying an action around
  another session's permission boundary is refused regardless of intent. The
  owner's approval of the change does not alter that: the branch is pushed by
  its author from a credentialed checkout. The carbon-fresh worktree having no
  GitHub login is recorded as a separate finding.
