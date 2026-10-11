# OWNER-CW1-DEVELOPMENT-CI-02: Python is runtime wherever it lives

**Authority.** The owner, 2026-10-11, directly in the PR Head session. Asked
how to close a quality-gate gap whose clean fix meant changing the classifier
pinned by OWNER-CW1-DEVELOPMENT-CI-01, he chose **"Authorize the classifier
change"**, whose description read: a new classifier migration, the
python-is-runtime rule added and the digests re-pinned under a new owner
record, with the existing record kept as history.

## What was wrong

`classify_changes.py` scores paths by prefix. `Business/` is a
`_CONTRACT_PREFIXES` entry, so a pull request touching only `Business/` took
the CONTRACT_AUTHORITY lane and never met the canonical quality job. No rule
looked at the file's suffix, so **17 tracked Python files under `Business/`**
were never checked by strict Black or Ruff.

That is how Black-failing and Ruff-failing research Python reached main in
#1055 and #1059, both of which merged on a green gate. Once on main it was
worse than latent: the quality job counts debt against a resolved base, so
main's debt was reported as *new* debt introduced by any pull request that
merely synced onto main. #1039 failed that way with four clean files of its
own, and #1071 clears the debt itself.

## Decided

A path ending `.py` classifies RUNTIME_FULL, placed before the contract and
documentation prefixes. One rule, in `classify_path`.

Measured before and after over all 1,972 tracked Python files: every one
scores RUNTIME_FULL afterwards, and the 27 paths that previously scored
CONTRACT_AUTHORITY -- all under `Business/`, the `Carbon_Fit/workbench` tools
and tests among them -- are the only ones whose scope changes. Markdown and
data keep their lanes, and an unknown path still fails closed to
RUNTIME_FULL.

## Why this needed the owner

The pinned block in `ci.yml` says a classifier change "has to avoid touching
any path the two versions would score differently". This change deliberately
does exactly that for those 27 paths, which is the point of it, so it could
not be made quietly under the existing authorization.

## Digests

`scripts/dev/classify_changes.py` in the OWNER-CW1-DEVELOPMENT-CI-01 block of
`.github/workflows/ci.yml` is re-pinned:

```
prior: ddfd11795b6da89339160e9f78fbf7b8978fa81420fbcbcd6d4f7ac5defce06e
now:   fe88ff6edf7b4753fbb1dc688f808eda21d7590c79ff63809c2316d079ad22a7
```

`scripts/dev/development_scope.py` is unchanged and keeps
`8f061b9f5f7ce705d8824358ef34d38e1578b17c5965b088fa81e945ce2b987a`.

OWNER-CW1-DEVELOPMENT-CI-01 stands as the record of the prior migration; this
record supersedes only its classifier digest. The block stays conditional on
the same historical base commit and still does not execute for any current
base.

## Not decided

No change to any scope's meaning, to what the quality job checks, or to the
protected-base Merge gate. Clearing the existing debt is #1071, separately.
