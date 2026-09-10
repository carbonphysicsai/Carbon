#!/usr/bin/env python3
"""Select bounded tooling acceptance; runtime and unknown inputs keep full CPU CI."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from classify_changes import (
    ChangeClassificationError,
    ChangeScope,
    changed_paths,
    classify_paths,
)

# This list owns only development-tooling regression files. A new file is not
# implicitly exempt from runtime acceptance merely because it has a similar name.
TOOLING_TESTS = (
    "tests/cpu/test_canonical_wrapper.py",
    "tests/cpu/test_change_classifier.py",
    "tests/cpu/test_code_authority.py",
    "tests/cpu/test_delivery_hygiene.py",
    "tests/cpu/test_github_ruleset.py",
    "tests/cpu/test_gpt_review_gate.py",
    "tests/cpu/test_hoh_adapters.py",
    "tests/cpu/test_hoh_controller.py",
    "tests/cpu/test_hoh_models.py",
    "tests/cpu/test_select_cpu_profile.py",
)
_TOOLING_PATHS = frozenset(TOOLING_TESTS) | frozenset(
    {
        ".github/workflows/ci.yml",
        ".github/workflows/development-hub.yml",
        ".github/workflows/gpt-review.yml",
        ".github/workflows/main-smoke.yml",
        "scripts/dev/apply_github_ruleset.py",
        "scripts/dev/check_delivery_hygiene.py",
        "scripts/dev/check_diff_hygiene.py",
        "scripts/dev/check_gpt_review_gate.py",
        "scripts/dev/check_merge_gate.py",
        "scripts/dev/ci.sh",
        "scripts/dev/ci_contract_authority.sh",
        "scripts/dev/ci_derived_documentation.sh",
        "scripts/dev/ci_hub.sh",
        "scripts/dev/ci_preflight.sh",
        "scripts/dev/classify_changes.py",
        "scripts/dev/select_cpu_profile.py",
        "docs/development/carbon_hub/tools/validate_hub.py",
        "docs/development/carbon_hub/tools/test_validator.py",
        "docs/development/carbon_hub/tools/test_newcomer.py",
    }
)


NETWORK_TESTS = (
    *TOOLING_TESTS,
    "tests/cpu/test_net1_chain_adapter.py",
    "tests/cpu/test_net2_transport.py",
    "tests/cpu/test_mcp_skeleton.py",
    "tests/cpu/test_net3_candidates.py",
    "tests/cpu/test_submission_fsm.py",
    "tests/cpu/test_traineval_stub.py",
    "tests/cpu/test_reward_core.py",
    "tests/cpu/test_reward_ledger.py",
    "tests/cpu/test_net4a_intents.py",
    "tests/cpu/test_net4b_publication.py",
    "tests/cpu/test_net4b_sdk.py",
    "tests/cpu/test_net5_setup.py",
    "tests/cpu/test_net5_integration.py",
    "tests/cpu/test_card_store.py",
    "tests/cpu/test_scoring_engine.py",
    "tests/cpu/test_leaderboard.py",
)
_NETWORK_PATHS = frozenset(
    {
        "carbon/chain/localnet.py",
        "scripts/dev/localnet.sh",
        ".github/workflows/localnet.yml",
        "tests/cpu/net5_fixture_support.py",
        "tests/cpu/test_net5_setup.py",
        "tests/cpu/test_net5_integration.py",
        "tests/invariants/test_net5_localnet_boundary.py",
        "docs/development/LOCALNET_INTEGRATION.md",
        "carbon/rewards/__init__.py",
        "carbon/rewards/core.py",
        "carbon/rewards/ledger.py",
        "carbon/rewards/review.py",
        "carbon/rewards/treasury.py",
        "carbon/rewards/intents.py",
        "tests/cpu/test_net4a_intents.py",
        "tests/invariants/test_net4a_intent_boundary.py",
        "docs/development/WEIGHT_INTENTS.md",
        "carbon/chain/publication.py",
        "carbon/chain/dispatch.py",
        "carbon/chain/publisher.py",
        "carbon/chain/sdk_weights.py",
        "tests/cpu/test_net4b_publication.py",
        "tests/cpu/test_net4b_sdk.py",
        "tests/invariants/test_net4b_publication_boundary.py",
        "docs/development/WEIGHT_PUBLICATION.md",
        "carbon/cards/development_scorecard.py",
        "tests/cpu/test_reward_core.py",
        "tests/cpu/test_reward_ledger.py",
        "tests/invariants/test_reward_boundary.py",
        "docs/development/SCORE_REWARDS.md",
        "carbon/candidates/__init__.py",
        "carbon/candidates/model.py",
        "carbon/candidates/store.py",
        "carbon/candidates/service.py",
        "tests/cpu/test_net3_candidates.py",
        "tests/invariants/test_net3_candidate_boundary.py",
        "docs/development/CANDIDATE_COMMITMENTS.md",
        "carbon/chain/__init__.py",
        "carbon/chain/models.py",
        "carbon/chain/adapter.py",
        "carbon/chain/sdk.py",
        "tests/cpu/test_net1_chain_adapter.py",
        "tests/invariants/test_net1_chain_boundary.py",
        "scripts/dev/localnet-runtime.json",
        "docs/development/CHAIN_ADAPTER.md",
        "launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.6.md",
        "carbon/chain/auth.py",
        "carbon/transport/__init__.py",
        "carbon/transport/gateway.py",
        "carbon/transport/models.py",
        "carbon/transport/store.py",
        "tests/cpu/test_net2_transport.py",
        "tests/invariants/test_net2_auth_boundary.py",
        "docs/development/AUTHENTICATED_TRANSPORT.md",
    }
)


# Exact NET-5 finite synthetic identity migration, never a general A8 exemption.
_NET5_AFTER = {
    "carbon/traineval/model.py": "30dccbcf63aef8d7e9cab9557f8217fdccb747690902e041e2c5a23d658b5705",
    "carbon/traineval/service.py": "d0bbbcb93ab7e88c7efa77aecb9149db36846956712b55b7957a4fe5249649c6",
    "tests/fixtures/score_packs/a5_fixture_net5_b_v1.json": "11c7dec2ea770ded856897f0dd778d0ff39f51375bd9f023cfe0e3abb3b68bc2",
    "tests/fixtures/score_packs/a5_fixture_net5_c_v1.json": "960820dab74f8113f725e8b8ddb36152529b0e12c4b12b55ed4769b49b69c7f0",
}
_NET5_BEFORE = {
    "carbon/traineval/model.py": "693c921c832723d6e5af403efd4de7a1494a7521246d2fc128d9949afe818cac",
    "carbon/traineval/service.py": "ddbd7bbfc9532d849e7a4ad8889c2a8ee3bd45b3942f606f1891c370bb18b239",
}


def exact_net5_fixture_extension(repository: Path, base: str) -> bool:
    for path, expected in _NET5_AFTER.items():
        try:
            value = (repository / path).read_text(encoding="utf-8").encode()
        except OSError:
            return False
        if hashlib.sha256(value).hexdigest() != expected:
            return False
        prior = subprocess.run(
            ["git", "show", f"{base}:{path}"],
            cwd=repository,
            capture_output=True,
            check=False,
        )
        if path in _NET5_BEFORE:
            if (
                prior.returncode
                or hashlib.sha256(prior.stdout).hexdigest() != _NET5_BEFORE[path]
            ):
                return False
        elif prior.returncode == 0:
            return False
    return True


def chain_constraint_tightening(before_project, after_project, before_lock, after_lock):
    """Exact NET-1 constraint migration; no resolved package/artifact may change."""
    return (
        before_project.count("bittensor>=9.0.0") == 2
        and before_project.replace("bittensor>=9.0.0", "bittensor==11.1.0")
        == after_project
        and before_lock.count('specifier = ">=9.0.0"') == 2
        and before_lock.replace('specifier = ">=9.0.0"', 'specifier = "==11.1.0"')
        == after_lock
        and 'name = "bittensor"\nversion = "11.1.0"' in before_lock
    )


def select_cpu_profile(
    paths: tuple[str, ...] | list[str],
    *,
    unchanged_chain_resolution: bool = False,
    transport_root_addition: bool = False,
    net5_fixture_extension: bool = False,
) -> str:
    """Allow only known tooling plus already lighter authority/document paths.

    Runtime code, scientific tests, dependency manifests, shared test fixtures,
    environment/bootstrap changes, and unclassified paths retain full CPU CI.
    No caller-supplied flag can label one of those paths as tooling-only.
    """
    classification = classify_paths(paths)
    network = any(path in _NETWORK_PATHS for path in paths)
    allowed = _TOOLING_PATHS | (_NETWORK_PATHS if network else frozenset())
    if network and net5_fixture_extension:
        allowed |= set(_NET5_AFTER)
    if network and unchanged_chain_resolution:
        allowed |= {"pyproject.toml", "uv.lock"}
    if network and transport_root_addition:
        allowed |= {".agent/CODE_AUTHORITY.toml"}
    if any(path not in allowed for path in classification.unknown_paths):
        return "RUNTIME_FULL"
    for item in classification.paths:
        if item.scope is ChangeScope.RUNTIME_FULL and item.path not in allowed:
            return "RUNTIME_FULL"
    return "NETWORK_FOUNDATION" if network else "TOOLING_ONLY"


def unchanged_chain_resolution(repository: Path, base: str) -> bool:
    values = []
    for path in ("pyproject.toml", "uv.lock"):
        result = subprocess.run(
            ["git", "show", f"{base}:{path}"],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            return False
        values.extend((result.stdout, (repository / path).read_text(encoding="utf-8")))
    return chain_constraint_tightening(*values)


def only_transport_root_added(before: str, after: str) -> bool:
    original = '    "carbon/traineval",\n'
    return (
        before.count(original) == 1
        and before.replace(original, original + '    "carbon/transport",\n') == after
    )


def only_candidate_root_added(before: str, after: str) -> bool:
    original = '    "carbon/cards",\n'
    return (
        before.count(original) == 1
        and before.replace(original, '    "carbon/candidates",\n' + original) == after
    )


def only_reward_root_added(before: str, after: str) -> bool:
    original = '    "carbon/resource_policy",\n'
    return (
        before.count(original) == 1
        and before.replace(original, original + '    "carbon/rewards",\n') == after
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--tooling-tests", action="store_true")
    parser.add_argument("--network-tests", action="store_true")
    args = parser.parse_args()
    try:
        paths = changed_paths(args.repository, args.base)
        same_resolution = False
        if "pyproject.toml" in paths or "uv.lock" in paths:
            same_resolution = unchanged_chain_resolution(args.repository, args.base)
        root_addition = False
        if ".agent/CODE_AUTHORITY.toml" in paths:
            result = subprocess.run(
                ["git", "show", f"{args.base}:.agent/CODE_AUTHORITY.toml"],
                cwd=args.repository,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                root_addition = any(
                    proof(
                        result.stdout,
                        (args.repository / ".agent/CODE_AUTHORITY.toml").read_text(
                            encoding="utf-8"
                        ),
                    )
                    for proof in (
                        only_transport_root_added,
                        only_candidate_root_added,
                        only_reward_root_added,
                    )
                )
        profile = select_cpu_profile(
            paths,
            unchanged_chain_resolution=same_resolution,
            transport_root_addition=root_addition,
            net5_fixture_extension=bool(set(paths) & set(_NET5_AFTER))
            and exact_net5_fixture_extension(args.repository, args.base),
        )
    except (ChangeClassificationError, OSError) as error:
        print(f"CPU profile selection failed: {error}", file=sys.stderr)
        return 2
    if args.tooling_tests or args.network_tests:
        expected = "NETWORK_FOUNDATION" if args.network_tests else "TOOLING_ONLY"
        if profile != expected:
            print("Full runtime acceptance is required.", file=sys.stderr)
            return 2
        tests = NETWORK_TESTS if args.network_tests else TOOLING_TESTS
        for path in tests:
            if not (args.repository / path).is_file():
                print(f"Required tooling test is missing: {path}", file=sys.stderr)
                return 2
        print("\n".join(tests))
    else:
        print(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
