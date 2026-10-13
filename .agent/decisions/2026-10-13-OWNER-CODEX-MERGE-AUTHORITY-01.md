# OWNER-CODEX-MERGE-AUTHORITY-01 — a time-boxed Codex merge window

Date: 2026-10-13
Status: APPROVED by the owner. Delivered as his own text in the PR Head
session and recorded verbatim below.
Authority: the owner. It waives a requirement that exists for his benefit —
the distinct non-author **human** approval of `AGENTS.md` §9 — and waives
nothing else.
Maturity: engineering control, time-boxed. It creates no scientific, security,
economic or commercial authority.

## His decision, verbatim

> For the window beginning now and ending when Claude sessions return, a
> dedicated Codex merge agent may merge pull requests without the distinct
> non-author human approval required by AGENTS.md §9, and without that
> approval carrying a protected review-gate receipt as a separate human step.
>
> It merges only on the standards in PR-HEAD-MERGE-STANDARD-02: a Merge gate
> run concluding success for the exact head SHA; a named non-author reviewer's
> receipt naming that same gated head; patch identity proven after any base
> sync; and the diff checked against what the PR claims.
>
> It may not merge its own work or anything it reviewed, anything resting on a
> relayed approval of mine, anything touching sealed or protected material,
> keys, chains or signers, anything setting a scientific threshold, a LIVE
> value, economics or a security acceptance, or a release tag.
>
> This is for this window only and expires when Claude sessions return.
> Everything AGENTS.md reserves to me or to a named domain owner is unchanged.

## What is waived, and what is not

**Waived:** the distinct non-author **human** approval step, and that approval
carrying a protected review-gate receipt as a separate human step.

**Not waived, and required of every merge the agent makes:**

1. a `Merge gate` run concluding **`success` for the exact head SHA**;
2. a **named non-author reviewer's receipt naming that same gated head**;
3. **patch identity** proven after any base sync;
4. **the diff checked against what the PR claims**.

**Forbidden to the agent entirely:** its own work or anything it reviewed;
anything resting on a relayed approval of the owner's; anything touching sealed
or protected material, keys, chains or signers; anything setting a scientific
threshold, a LIVE value, economics or a security acceptance; and any release
tag.

Everything `AGENTS.md` reserves to the owner or a named domain owner is
unchanged.

## Two seams, recorded rather than resolved silently

**1. Which standard governs.** `PR-HEAD-MERGE-STANDARD-02` is in force on main
at the time of writing, so his citation is current. **`PR-HEAD-MERGE-STANDARD-03`
supersedes it** and is open in #1323, carrying his own `OWNER-MERGE-APPROVAL-01`.
The four mechanics he names — gate on the exact SHA, head-bound receipt, patch
identity, content checked against the claim — are **unchanged in 03**, so the
delegation is coherent under either.

One interaction is worth stating plainly, because it is a difference and not a
conflict: under `OWNER-MERGE-APPROVAL-01` an **ordinary** PR may merge with no
reviewer receipt at all, while **this record requires a receipt for everything
the agent merges**. The stricter bar is read as deliberate — a compensating
control for the absent human approval — and it binds the agent whichever
standard is current. An agent merging without human approval should not also be
the one merging without review.

**2. When the window ends.** "Ending when Claude sessions return" has no
mechanical boundary. The operative reading recorded here: the window **begins
when the PR Head session stops merging** and **ends when any Claude session
resumes merging**. Where it is unclear whether the window is open, it is
**closed** — the authority fails closed, as a lapsed delegation should.

**3. Reserved categories wait.** A PR in any of the four categories of
`OWNER-MERGE-APPROVAL-01`, with the edges in `PR-HEAD-MERGE-STANDARD-03` §2
(including a test change that loosens an assertion protecting one of them, or a
decision record stating policy in one), requires the **Carbon Validator's own**
receipt: a named domain owner's reservation that this delegation leaves
unchanged. A receipt from any other reviewer does not satisfy it, so such PRs
wait for the window to close. Where it is unclear whether a PR is reserved, it
is.

This is the seam an agent would most likely get wrong, because the record's
words — "a named non-author reviewer's receipt" — are satisfied by **any**
reviewer, while the owner's own closing line keeps the reserved categories with
their domain owner. Gate design and gate comprehensiveness are the Carbon
Validator's (owner, 2026-10-05). The Validator is a Claude session and so is
absent for the window, which is why those PRs wait rather than finding another
receipt.

It is recorded here rather than added later because a later note would itself
be a reserved decision record — policy in one of the four — with nobody able to
approve it while the window is open.

## Why this record could not wait for the agent it authorises

A delegation cannot be merged by its own delegate: until it is on main the
agent has no authority, and using the authority to land the grant of it would
be circular. It is therefore merged the existing way, by PR Head, with a named
non-author reviewer's receipt and a successful gate on the exact head — the
same bar it sets for the agent.
