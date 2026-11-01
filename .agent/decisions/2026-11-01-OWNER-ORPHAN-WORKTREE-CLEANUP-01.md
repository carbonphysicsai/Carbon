# OWNER-ORPHAN-WORKTREE-CLEANUP-01: Graphite may remove orphaned git worktrees that meet all safety conditions

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session: "yes".
Question: "Can Graphite remove old code copies (worktrees) that meet ALL of these? Their work is already merged into main or saved on a branch with nothing unpushed; no unsaved changes in them; no live session is using them. Nothing is lost (the work stays in git). It keeps a full list of what it removed; anything that fails a condition stays and is reported."

## Decided
- Graphite (C: steward) may run `git worktree remove` on orphaned worktrees under .worktrees and .w (and other worktree folders) only when ALL hold: (1) HEAD merged into origin/main, OR its branch exists with no commits missing from the remote; (2) no dirty or untracked changes; (3) not the working folder of any live session. Branches are never deleted. `--force` is never used.
- Live sessions clean their own worktrees. Anything failing a condition is kept and listed for the owner.
- A full removal list (path, branch, HEAD SHA) goes to codex-queue/reports/C_DRIVE_LOG.md.
- Never touch WSL vhdx files or the Ubuntu-24.04 distro.
