# Carbon development runs on Linux

Owner direction: <https://github.com/carbonphysicsai/Carbon/issues/245>

Carbon development — editing, coding-agent execution, Git, generation, builds and
tests — runs on Linux, with the source tree and Git metadata on Linux-native
storage. Ubuntu on WSL2 counts as Linux for this purpose. A Windows or macOS
machine may host the editor or the browser; it must not host the source tree, the
Git metadata or the tools.

This is a development-environment policy. It does not change what Carbon
supports at runtime, and it does not restrict miners to a platform or a provider.

## Why, concretely

A Windows checkout reached through an interop mount does not announce itself. It
looks like a working tree: imports resolve, the prompt shows the right directory,
and most tests pass. What fails is everything that depends on exact bytes or on
Git behaving normally, and it fails in a way that invites someone to change
correct code.

Observed on this repository from a Windows worktree, against a tree that is clean
on Linux:

- 303 test failures across scoring, evaluation-pack and workbench suites, every
  one of them a golden-fixture digest comparing CRLF bytes against the LF bytes
  Git stores. The same 548 tests pass from Linux.
- The Development Hub generated-output check reported all 95 generated files as
  drifted, for the same reason. Nothing had actually drifted.
- `scripts/check_quality.py` could not run at all: it resolves the repository
  with Git, and Linux Git cannot follow a worktree pointer that records a Windows
  path.
- A worktree `.git` pointer written by Windows Git is unreadable from Linux, and
  the reverse is also true — a Linux path written into shared Git configuration
  breaks the Windows checkout.

That last one is the sharpest point. Running Linux Git against a Windows
repository with `GIT_DIR` and `GIT_WORK_TREE` exported writes Linux paths, and
whatever identity happens to be configured, into the *shared* repository
configuration. The damage is invisible in the working tree and affects every
other worktree in that repository.

## The rules

1. One Linux-native clone per machine holds the source and the Git common
   directory. Create linked worktrees from it with Linux Git. Never copy a
   worktree's `.git` pointer between platforms.
2. Do not run Git against a repository that lives on another platform's
   filesystem, and do not export `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`,
   `GIT_INDEX_FILE` or `GIT_CONFIG_*` to reach one.
3. Leave `core.autocrlf` unset on Linux and let `.gitattributes` decide.
4. Development tools come from the Linux environment. WSL appends the Windows
   PATH by default, so `git`, `python` and Git Bash are all reachable by name
   there; checking `--version` proves a tool answered, not which tool answered.
5. The canonical environment identity stays where it already is —
   `scripts/dev/doctor.sh` and `scripts/dev/canonical.sh`. Nothing here defines a
   second one.

## Preflight

```bash
./scripts/dev/workspace_preflight.sh
```

Run it before a build, a generator or a long test run. It verifies the execution
platform, that the source root and Git common directory are on Linux-native
storage, that the development executables are the Linux ones, that no inherited
Git environment variables are redirecting writes, that byte-sensitive source
rules hold, which container daemon is selected, and non-secret authentication
readiness. Then it defers to `scripts/dev/doctor.sh` for the canonical
environment.

It decides by filesystem type, not by path spelling: a container path such as
`/workspaces/carbon` is valid when it is backed by real Linux storage, and no
particular `/home` spelling is required. It names Ubuntu on WSL2 plainly rather
than reporting it as a bare-metal host.

A passing preflight says the workspace can produce trustworthy results. It is not
a scientific, security or hardware qualification, and it says so.

## What this does not cover

Ubuntu on WSL2 keeps the Windows GPU driver and virtualization layer, along with
the documented telemetry limitations of that arrangement. Moving development to
Linux does not change GPU admission, does not establish compute-process
enumeration, and is not a step toward strict GPU qualification. Eliminating that
driver layer would require native Linux hardware and boot selection, which is a
separate decision.
