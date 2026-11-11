#!/usr/bin/env bash
# RULE B release gate (runbook delta 0cace8f7 section 2.1): the PREVIOUS release's receiver starts on, and grades
# from, a state root written by the NEW release.
#
#   scripts/dev/release/downgrade_gate.sh OLD NEW
#
# OLD, NEW: revisions of this repository (OLD = the release a door would roll back to, NEW = the release under gate).
# Both are exported (`git archive`) into one temporary directory, removed after; the repository is only read.
#   1. NEW runs (D) (`tests/cpu/test_door_release_e2e.py`, first test) with CARBON_RELEASE_GATE_STATE = one state root:
#      a carried previous-release ledger, a fresh admission, advance, the real grade round; the root is kept.
#   2. OLD runs that file's second test, from NEW's copy of it, on the SAME root: its receiver starts on what NEW
#      wrote and must admit, build and grade a new submission from it.
# Each phase imports `carbon` from its own tree (checked, fail closed). The last line is the verdict:
#   DOWNGRADE_GATE PASS old=<sha> new=<sha>        (exit 0)
#   DOWNGRADE_GATE FAIL <phase> old=<sha> new=<sha> (exit 1; a usage or setup refusal exits 2)
# A FAIL means NEW cannot use the code rollback to OLD: its GO must say so (Rule B 2.1).
# Run it where the full suite runs (the canonical environment): PYTHON names the interpreter (default python).
set -euo pipefail

usage() {
    echo "usage: $0 OLD NEW" >&2
    exit 2
}
[ "$#" -eq 2 ] || usage
PYTHON="${PYTHON:-python}"
TEST=tests/cpu/test_door_release_e2e.py
NEW_TEST="$TEST::test_a_carried_state_admits_builds_and_grades_after_the_release"
OLD_TEST="$TEST::test_a_release_rolled_back_to_grades_on_the_state_the_new_release_wrote"

repo="$(git rev-parse --show-toplevel)"
old="$(git -C "$repo" rev-parse --verify --quiet "$1^{commit}")" || { echo "DOWNGRADE_GATE REFUSED unknown OLD $1" >&2; exit 2; }
new="$(git -C "$repo" rev-parse --verify --quiet "$2^{commit}")" || { echo "DOWNGRADE_GATE REFUSED unknown NEW $2" >&2; exit 2; }
[ "$old" != "$new" ] || { echo "DOWNGRADE_GATE REFUSED OLD and NEW are the same commit" >&2; exit 2; }
git -C "$repo" cat-file -e "$new:$TEST" 2>/dev/null || { echo "DOWNGRADE_GATE REFUSED NEW carries no $TEST" >&2; exit 2; }

work="$(mktemp -d "${TMPDIR:-/tmp}/carbon-downgrade-gate.XXXXXXXX")"
cleanup() {
    case "$work" in
        */carbon-downgrade-gate.????????) rm -rf -- "$work" ;;
    esac
}
trap cleanup EXIT

# Each tree is exported, never checked out: the repository (and its .git, read-only in the canonical container) is
# only read.
for side in new old; do
    mkdir "$work/$side"
    git -C "$repo" archive --format=tar "$([ "$side" = new ] && echo "$new" || echo "$old")" | tar -x -C "$work/$side"
done
# OLD runs NEW's copy of the test (its own helpers and code); the throwaway tree is discarded after.
git -C "$repo" show "$new:$TEST" >"$work/old/$TEST"
state="$work/state"

phase() {
    # phase NAME TREE TEST COMMIT: run one test from TREE, importing carbon from TREE only
    local name="$1" tree="$2" test="$3" origin
    origin="$(cd "$tree" && PYTHONPATH="$tree" "$PYTHON" -c 'import carbon, os; print(os.path.realpath(carbon.__file__))')"
    case "$origin" in
        "$(realpath "$tree")"/*) ;;
        *)
            echo "DOWNGRADE_GATE REFUSED $name imports carbon from outside its tree: $origin" >&2
            exit 2
            ;;
    esac
    echo "== $name $4 =="
    local log="$work/$name.log" rc=0
    (cd "$tree" && CARBON_RELEASE_GATE_STATE="$state" PYTHONPATH="$tree" \
        "$PYTHON" -m pytest -q -p no:cacheprovider -rs "$test") >"$log" 2>&1 || rc=$?
    tail -n 40 "$log"
    # exactly one test ran and passed: a skip or a deselect is never a pass
    [ "$rc" -eq 0 ] && tail -n 1 "$log" | grep -Eq '^=*[[:space:]]*1 passed( in |,)' \
        && ! tail -n 1 "$log" | grep -q skipped
}

if ! phase NEW "$work/new" "$NEW_TEST" "$new"; then
    echo "DOWNGRADE_GATE FAIL new_release_e2e old=$old new=$new"
    exit 1
fi
if ! phase OLD "$work/old" "$OLD_TEST" "$old"; then
    echo "DOWNGRADE_GATE FAIL old_release_on_new_state old=$old new=$new"
    exit 1
fi
echo "DOWNGRADE_GATE PASS old=$old new=$new"
