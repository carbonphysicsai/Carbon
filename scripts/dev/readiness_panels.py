"""Operator-only S3/H2 packaging; no real producer inputs are used by this ticket.

Outputs are outside the repository, owner-only and never overwritten. The only
console output is a digest/count summary or a closed refusal code. H4 has no
hidden-host producer here: its declared input format is tested synthetically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from carbon.challenge_pipeline.readiness import evidence_checks as ec
from carbon.challenge_pipeline.readiness import scoring_checks as sc
from carbon.challenge_pipeline.readiness.checks import Context, load_challenge_data
from carbon.challenge_pipeline.readiness.model import CHALLENGE_TOKEN, REPOSITORY
from carbon.challenge_pipeline.readiness.study_checks import _json

PUBLIC_MARGINS_SCHEMA = "carbon.readiness.public-reference-margins.v1"


def outside(path, repository):
    path = Path(path).resolve()
    root = Path(repository).resolve()
    if path == root or root in path.parents:
        raise ec.EvidenceInvalid("producer_path_inside_repository")
    return path


def write_panel(panel, out, repository=REPOSITORY):
    destination = outside(out, repository)
    body = (json.dumps(panel, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    # Exclusive create protects any existing operator export from replacement.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(body)
    return "sha256:" + hashlib.sha256(body).hexdigest()


def margin_panel(ctx, registration, record):
    sc._roster(ctx, record, registration)
    source = registration.get("public_reference_margins")
    if type(source) is not dict:
        raise ec.EvidenceInvalid("public_reference_margins_not_registered")
    document, sha = _json(ctx, source["path"])
    if (
        sha != source.get("sha256")
        or document.get("schema") != PUBLIC_MARGINS_SCHEMA
        or document.get("challenge") != ctx.challenge
        or document.get("levels") != sc.LEVELS
    ):
        raise ec.EvidenceInvalid("public_reference_margin_binding_mismatch")
    margins = document.get("margins")
    if type(margins) is not dict or set(margins) != {
        g["name"] for g in registration["gates"]
    }:
        raise ec.EvidenceInvalid("margin_gate_coverage_incomplete")
    if any(
        type(v) is not list or not v or not all(ec._finite(x) for x in v)
        for v in margins.values()
    ):
        raise ec.EvidenceInvalid("public_reference_margins_malformed")
    return {
        "schema": ec.MARGIN_PANEL_SCHEMA,
        "challenge": ctx.challenge,
        "levels": sc.LEVELS,
        "margins": margins,
    }


def _private_prior(path, repository):
    if Path(path).is_symlink():
        raise ec.EvidenceInvalid("producer_prior_not_owner_only")
    path = outside(path, repository)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ec.EvidenceInvalid("producer_prior_not_owner_only")
    document = ec._load(path)
    cases = document.get("cases")
    if type(cases) is not list or not cases:
        raise ec.EvidenceInvalid("producer_prior_empty")
    inputs = []
    for case in cases:
        if type(case) is not dict or set(case) != {"inputs"}:
            raise ec.EvidenceInvalid("producer_prior_shape_invalid")
        ec._case_key(case["inputs"])
        inputs.append(case["inputs"])
    return inputs


def _export_pool(config, destination):
    # Only explicit operator invocation can reach the existing read-only export.
    from carbon.challenge_validator.tuning import export_pool

    export_pool(config, destination)


def overlap_panel(ctx, registration, groups, *, pool_config=None):
    roles, _ = sc.registered_roles(ctx)
    tuning = registration.get("tuning_role")
    sealed, unsealed = registration.get("sealed_roles"), registration.get(
        "unsealed_roles"
    )
    if type(sealed) is not list or type(unsealed) is not list:
        raise ec.EvidenceInvalid("operator_custody_classification_required")
    if (
        tuning not in roles
        or not all(type(r) is str for r in sealed + unsealed)
        or len(set(sealed + unsealed + [tuning])) != len(sealed + unsealed) + 1
        or set(sealed + unsealed + [tuning]) != roles
    ):
        raise ec.EvidenceInvalid("overlap_role_roster_incomplete")
    expected = {tuning, *sealed, *ec.PUBLIC_PRIORS}
    if type(groups) is not dict or not set(groups) <= expected:
        raise ec.EvidenceInvalid("overlap_group_coverage_incomplete")
    supplied = dict(groups)
    supplied_names = set(supplied) | (
        {"rotating_pool"} if pool_config is not None else set()
    )
    if supplied_names != expected:
        raise ec.EvidenceInvalid("overlap_group_coverage_incomplete")
    if pool_config is not None:
        if "rotating_pool" in supplied:
            raise ec.EvidenceInvalid("producer_duplicate_rotating_pool")
        config = outside(pool_config, ctx.repository)
        # Temporary export remains on the operator's filesystem, outside Git.
        with tempfile.TemporaryDirectory(
            prefix="readiness-prior-", dir=config.parent
        ) as private:
            path = Path(private) / "pool.json"
            _export_pool(config, path)
            inputs = _private_prior(path, ctx.repository)
        exported = {"rotating_pool": inputs}
    else:
        exported = {}
    if set(supplied) | set(exported) != expected:
        raise ec.EvidenceInvalid("overlap_group_coverage_incomplete")
    panel = {
        "schema": ec.OVERLAP_PANEL_SCHEMA,
        "challenge": ctx.challenge,
        "levels": sc.LEVELS,
        "groups": {
            **{
                role: _private_prior(path, ctx.repository)
                for role, path in supplied.items()
            },
            **exported,
        },
    }
    ec.overlap_study(registration, panel, roles)
    return panel


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "producer refused: arguments_invalid\n")


def main(argv=None):
    parser = Parser(description="Operator S3/H2 producer; counts/digests only")
    parser.add_argument("item", choices=("S3", "H2"))
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--level", type=int, choices=sc.LEVELS, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--pool-config")
    args = parser.parse_args(argv)
    try:
        if not CHALLENGE_TOKEN.fullmatch(args.challenge):
            raise ec.EvidenceInvalid("producer_challenge_invalid")
        ctx = Context(
            args.challenge, args.level, data=load_challenge_data(args.challenge)
        )
        record = sc._record(ctx, args.item)
        if record is None:
            raise ec.EvidenceInvalid("producer_scope_not_registered")
        outside(args.out, ctx.repository)
        schema = (
            ec.MARGIN_REGISTRATION_SCHEMA
            if args.item == "S3"
            else ec.OVERLAP_REGISTRATION_SCHEMA
        )
        registration, _ = sc._registration(ctx, record, schema)
        if args.item == "S3":
            if args.group or args.pool_config:
                raise ec.EvidenceInvalid("margin_producer_arguments_invalid")
            panel = margin_panel(ctx, registration, record)
        else:
            groups = {}
            for value in args.group:
                role, separator, path = value.partition("=")
                if not separator or role in groups:
                    raise ec.EvidenceInvalid("producer_group_arguments_invalid")
                groups[role] = path
            panel = overlap_panel(
                ctx, registration, groups, pool_config=args.pool_config
            )
        sha = write_panel(panel, args.out, ctx.repository)
        count = sum(map(len, panel.get("groups", panel.get("margins", {})).values()))
        print(
            json.dumps(
                {"item": args.item, "panel_digest": sha, "rows": count}, sort_keys=True
            )
        )
        return 0
    except (ec.EvidenceInvalid, sc.Invalid):
        # A closed error avoids echoing a private path, object or witness.
        print("producer refused: evidence_invalid_or_owner_input_missing")
    except (OSError, ValueError, TypeError, KeyError, ImportError):
        print("producer refused: evidence_unavailable_or_malformed")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
