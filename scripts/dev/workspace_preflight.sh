#!/usr/bin/env bash
set -euo pipefail

# Carbon development workspace preflight.
#
# Carbon development runs on Linux, with source and Git metadata on Linux-native
# storage. A Windows or macOS machine may host the editor; it must not host the
# source tree, the Git metadata or the tools.
#
# This exists because the failure it catches is quiet. A Windows checkout reached
# through an interop mount still looks like a working tree: imports resolve,
# most tests pass, and the shell prompt says the right directory. What breaks is
# everything byte-sensitive - golden fixture digests, generated-output drift
# checks, Git-dependent tooling - and it breaks as content failures that invite
# someone to "fix" correct code. Run this before a build, a generator or a long
# test run, not after.
#
# It reuses scripts/dev/doctor.sh for the canonical environment identity. It does
# not define a second one, and it changes no application, miner, validator or CI
# behaviour: it only refuses to start development work in a workspace that cannot
# produce trustworthy results.

usage() {
  cat <<'EOF'
Usage:
  ./scripts/dev/workspace_preflight.sh [--quiet] [--no-doctor] [--workspace DIR]

  --quiet          Print only failures and the final verdict.
  --no-doctor      Skip the canonical environment check (scripts/dev/doctor.sh).
                   Use only when doctor has already run in this same workspace.
  --workspace DIR  Check DIR instead of this script's own repository.

By default the checked workspace is the repository this script lives in. That is
the common case and it is deliberate: a preflight that silently checked somewhere
else would be worse than none.

--workspace exists because a reviewed copy of this script lives on one branch
while the work happens in another linked worktree. Copying the script into the
working tree to check that tree would mean running an unreviewed script, so point
the reviewed one at the workspace instead. The checked workspace is reported in
the output either way, so it is never ambiguous which tree passed.
EOF
}

quiet=0
run_doctor=1
workspace=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --quiet) quiet=1 ;;
    --no-doctor) run_doctor=0 ;;
    --workspace)
      shift
      [[ $# -gt 0 ]] || { printf '%s\n' 'workspace preflight: --workspace needs a directory' >&2; exit 2; }
      workspace="$1"
      ;;
    --workspace=*) workspace="${1#--workspace=}" ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'workspace preflight: unknown argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

failures=0

note() { [[ "${quiet}" -eq 1 ]] || printf '  %s\n' "$*"; }
ok()   { [[ "${quiet}" -eq 1 ]] || printf 'ok    %s\n' "$*"; }
warn() { printf 'warn  %s\n' "$*" >&2; }
bad()  { printf 'FAIL  %s\n' "$*" >&2; failures=$((failures + 1)); }

# --- 1. the execution platform ------------------------------------------------
#
# Deliberately derived from the kernel and from /etc/os-release, never from an
# environment variable a launcher can set. A variable says what something was
# told; it does not say where this process is running.

kernel="$(uname -s 2>/dev/null || true)"
case "${kernel}" in
  MINGW*|MSYS*|CYGWIN*)
    bad "running under ${kernel} on Windows. Open an Ubuntu shell (or the" \
        "Carbon dev container) and run development there."
    printf '\nworkspace preflight: refused (%d problem(s))\n' "${failures}" >&2
    exit 2
    ;;
esac
if [[ "${OS:-}" == "Windows_NT" ]]; then
  bad "running on Windows. Open an Ubuntu shell and run development there."
  printf '\nworkspace preflight: refused (%d problem(s))\n' "${failures}" >&2
  exit 2
fi
if [[ "${kernel}" != "Linux" ]]; then
  bad "Linux is required (found ${kernel:-unknown})."
  printf '\nworkspace preflight: refused (%d problem(s))\n' "${failures}" >&2
  exit 2
fi

platform="Linux"
if [[ -r /proc/sys/kernel/osrelease ]] \
   && grep -qi microsoft /proc/sys/kernel/osrelease; then
  # Named plainly. Ubuntu on WSL2 is a supported development host; it is not a
  # bare-metal Linux host, and it keeps the Windows GPU driver and
  # virtualization layer with its documented telemetry limitations.
  platform="Linux (Ubuntu on WSL2)"
fi
if [[ -f /.dockerenv ]] || grep -qa 'docker\|containerd' /proc/1/cgroup 2>/dev/null; then
  platform="${platform}, inside a container"
fi
ok "platform: ${platform}"

# --- 2. source and Git metadata live on Linux-native storage -------------------
#
# Checked by filesystem type, not by path spelling. A container path such as
# /workspaces/carbon is perfectly valid when it is backed by real Linux storage,
# and an arbitrary /home spelling is not required.

# Filesystem types that mean "this is really a Windows or network filesystem
# reached through a translation layer". 9p and drvfs are how WSL exposes a
# Windows drive; the rest are network or foreign-filesystem mounts.
foreign_filesystems='9p|drvfs|cifs|smb3|smbfs|ntfs|ntfs3|fuseblk|vboxsf|prl_fs|vmhgfs'

storage_kind() {
  findmnt -n -o FSTYPE --target "$1" 2>/dev/null | head -1
}

require_native_storage() {
  local label="$1" path="$2" fstype
  if [[ ! -e "${path}" ]]; then
    bad "${label} does not exist: ${path}"
    return
  fi
  fstype="$(storage_kind "${path}")"
  if [[ -z "${fstype}" ]]; then
    warn "${label}: filesystem type could not be determined for ${path}"
    return
  fi
  if printf '%s' "${fstype}" | grep -Eqi "^(${foreign_filesystems})$"; then
    bad "${label} is on a ${fstype} filesystem (${path})."
    note "That is a Windows or network filesystem reached through a translation"
    note "layer. Byte-sensitive checks and Git-dependent tooling are not"
    note "trustworthy there. Use a Linux-native clone instead."
    return
  fi
  ok "${label}: ${path} (${fstype})"
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
own_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"

if [[ -n "${workspace}" ]]; then
  if [[ ! -d "${workspace}" ]]; then
    bad "the requested workspace does not exist: ${workspace}"
    printf '\nworkspace preflight: refused (%d problem(s))\n' "${failures}" >&2
    exit 2
  fi
  repo_root="$(CDPATH= cd -- "${workspace}" && pwd -P)"
else
  repo_root="${own_root}"
fi
cd "${repo_root}"

# Always stated, so a passing report can never be read against the wrong tree.
ok "checking workspace: ${repo_root}"
if [[ "${repo_root}" != "${own_root}" ]]; then
  note "(this script is running from ${own_root})"
fi

require_native_storage "source root" "${repo_root}"

if git rev-parse --git-common-dir >/dev/null 2>&1; then
  common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)"
  require_native_storage "Git common dir" "${common_dir}"
  git_dir="$(git rev-parse --absolute-git-dir)"
  ok "Git dir: ${git_dir}"
else
  bad "not inside a Git repository, or the Git metadata pointer is unreadable"
  note "from this platform. A worktree created on Windows records a Windows"
  note "path that Linux Git cannot follow. Create the worktree with Linux Git."
fi

# --- 3. the tools are the Linux ones ------------------------------------------
#
# WSL appends the Windows PATH by default, so git.exe, python.exe and Windows
# Git Bash are all reachable by name. Checking --version proves a tool answered;
# it does not prove which tool answered.

check_executable() {
  local name="$1" required="$2" resolved
  resolved="$(command -v "${name}" 2>/dev/null || true)"
  if [[ -z "${resolved}" ]]; then
    if [[ "${required}" == "required" ]]; then
      bad "${name} is not installed in this Linux environment."
    else
      warn "${name} is not installed in this Linux environment (optional here)."
    fi
    return
  fi
  resolved="$(readlink -f "${resolved}" 2>/dev/null || printf '%s' "${resolved}")"
  case "${resolved}" in
    /mnt/*|*.exe)
      bad "${name} resolves to a Windows executable: ${resolved}"
      note "Install the Linux build, or remove the Windows directories from PATH"
      note "for this shell. A Windows tool writes Windows paths into Git and"
      note "shared configuration, which breaks the Linux workspace."
      ;;
    *) ok "${name}: ${resolved}" ;;
  esac
}

check_executable git required
check_executable python3 required
check_executable uv required
check_executable tar required
check_executable node optional
check_executable gh optional

# A wrapper or alias can shadow a correct binary without changing its path.
if alias git >/dev/null 2>&1; then
  warn "git is aliased in this shell; the alias may not be the Linux binary."
fi

# --- 4. inherited Git environment contamination -------------------------------
#
# These variables silently redirect Git writes. Pointed at another repository's
# metadata they will write into it - including core.worktree and user identity -
# and the damage is not visible in the working tree.

for name in GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_OBJECT_DIRECTORY; do
  if [[ -n "${!name:-}" ]]; then
    bad "${name} is set in this shell (${!name})."
    note "Start development from a clean shell. An inherited Git directory"
    note "variable makes Git operate on a repository other than this one."
  fi
done
if [[ -n "${GIT_CONFIG_COUNT:-}" ]]; then
  bad "GIT_CONFIG_COUNT is set; injected Git configuration is in effect."
fi
if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ "${VIRTUAL_ENV}" == /mnt/* ]]; then
  bad "VIRTUAL_ENV points at a Windows path: ${VIRTUAL_ENV}"
fi
if [[ -n "${PYTHONPATH:-}" ]] && printf '%s' "${PYTHONPATH}" | grep -q '/mnt/'; then
  bad "PYTHONPATH contains a Windows path: ${PYTHONPATH}"
fi

# --- 5. byte-sensitive source rules -------------------------------------------
#
# Carbon has golden fixture digests and generated-output drift checks that
# compare exact bytes. A checkout that rewrites line endings fails those as
# content errors, which is a very good way to talk someone into changing correct
# code.

autocrlf="$(git config --get core.autocrlf 2>/dev/null || true)"
case "${autocrlf}" in
  true|input)
    bad "core.autocrlf is '${autocrlf}' for this repository."
    note "Line-ending rewriting breaks byte-exact fixtures and generated-output"
    note "checks. Leave it unset on Linux and let .gitattributes decide."
    ;;
  *) ok "core.autocrlf: ${autocrlf:-unset}" ;;
esac

if [[ -f .gitattributes ]]; then
  ok ".gitattributes present"
else
  warn ".gitattributes is absent; line-ending policy is not pinned by the tree."
fi

crlf_found=0
while IFS= read -r sample; do
  [[ -f "${sample}" ]] || continue
  if grep -qU $'\r' "${sample}" 2>/dev/null; then
    bad "${sample} contains CRLF line endings in the working tree."
    crlf_found=1
  fi
done <<'SAMPLES'
docs/development/carbon_hub/README.md
pyproject.toml
scripts/dev/doctor.sh
SAMPLES
[[ "${crlf_found}" -eq 0 ]] && ok "sampled tracked text is LF"

# --- 6. the container runtime is the expected existing one ---------------------
#
# Reported, not enforced: most development does not need Docker, and this must
# not become a reason to start a second daemon.

if command -v docker >/dev/null 2>&1; then
  if docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
    docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
    ok "docker context: $(docker context show 2>/dev/null || echo unknown)" \
       "(server $(docker info --format '{{.ServerVersion}}' 2>/dev/null))"
    case "${docker_root}" in
      /mnt/*) bad "the Docker daemon stores state on a Windows path: ${docker_root}" ;;
      *) ok "docker root: ${docker_root:-unknown}" ;;
    esac
  else
    warn "the docker client cannot reach a daemon; container work will not run."
  fi
else
  warn "docker is not installed here; container work will not run."
fi

# --- 7. non-secret authentication readiness -----------------------------------
#
# Readiness only. No token is read, printed or requested.

if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    ok "gh: authenticated for this host"
  else
    warn "gh is installed but not authenticated. Run:" \
         "gh auth login --hostname github.com --git-protocol https --web"
  fi
fi

# --- 8. canonical environment -------------------------------------------------
#
# The dependency groups are the caller's declaration, passed through untouched.
# Guessing them here would be the wrong kind of helpful: doctor would then report
# an environment nobody asked for, and a suite needing another group would fail
# later with a missing import rather than here with a clear reason. The groups
# actually checked are printed, so a passing report states its own scope.

if [[ "${run_doctor}" -eq 1 ]]; then
  if [[ -f scripts/dev/doctor.sh ]]; then
    ok "dependency groups checked: dev${CARBON_UV_GROUPS:+ ${CARBON_UV_GROUPS}}"
    [[ -n "${CARBON_UV_GROUPS:-}" ]] || note \
      "(set CARBON_UV_GROUPS for a suite that needs more than the dev group)"
    if bash scripts/dev/doctor.sh >/tmp/carbon-preflight-doctor.$$ 2>&1; then
      ok "canonical environment: scripts/dev/doctor.sh passed"
      [[ "${quiet}" -eq 1 ]] || sed 's/^/      /' /tmp/carbon-preflight-doctor.$$ \
        | grep -E 'OS:|Python:|uv:|repository:|lock/groups:' || true
    else
      bad "scripts/dev/doctor.sh failed:"
      sed 's/^/      /' /tmp/carbon-preflight-doctor.$$ >&2 || true
      note "If it reports an outdated environment, the installed groups and the"
      note "checked groups differ. Set CARBON_UV_GROUPS to the groups this suite"
      note "actually needs; do not sync the environment down to silence it."
    fi
    rm -f /tmp/carbon-preflight-doctor.$$
  else
    warn "scripts/dev/doctor.sh not found; canonical environment unverified."
  fi
fi

# --- verdict ------------------------------------------------------------------

if [[ "${failures}" -gt 0 ]]; then
  printf '\nworkspace preflight: refused (%d problem(s)).\n' "${failures}" >&2
  printf 'Fix the items marked FAIL before building, generating or running tests.\n' >&2
  exit 2
fi
printf '\nworkspace preflight: this workspace is suitable for Carbon development.\n'
printf 'It is not a scientific, security or hardware qualification.\n'
exit 0
