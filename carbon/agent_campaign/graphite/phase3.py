"""Graphite phase 3 runner: Constructor sessions on battery, for the Challenge
Roadmap's Phase 1 step 4 (CHALLENGE-PROTOCOL-04 slice 5).

    python -m carbon.agent_campaign.graphite.phase3 session --root DIR \
        --grant docs/development/graphite/grants/GRAPHITE-GRANT-STEP4.json \
        --credential-env ENGY_API_KEY --configuration RUNNER.json --campaign NAME
    python -m carbon.agent_campaign.graphite.phase3 session --root DIR --dry-run
    python -m carbon.agent_campaign.graphite.phase3 log --root DIR

`DIR` is a private directory outside the repository.

**One session** runs these steps:
1. It is launched through the campaign controller, at stage `test_iterate`
   with the stage profile, under the grant, with campaign ceilings of
   USD 5.00 (OWNER-CHALLENGE-STEP4-01).
2. The Constructor drives the owner's battery campaign through the miner
   path (`miner_path.battery_tools`). It practices in the campaign's carrier
   on the owner's host and selects a recipe. It never submits.
3. The controller settles the run.
4. Carbon checks, rebuilds, clean-rebuilds and scores the selection on its
   own side (`score.py`). A refusal that is a reproduced fail-open is
   recorded as a finding (`FAILING_TRIGGER`).
5. One line is appended to `DIR/iteration-log.jsonl`. That log is step 4's
   output.

**Refusals.** The runner refuses to run without:
- the exact grant;
- a credential (from the environment, copied to a 0600 file and removed on
  exit, never printed);
- a stage profile.

It also refuses a second grant under one store, because two stores would
each enforce the full ceiling.

**`--dry-run`** runs the same pipeline with a scripted model and a synthetic
grant, under `DIR/dry-run`. It has no miner path: the miner tools answer
that none is connected. Its selection is still scored for real, on Carbon's
side. It sends nothing and spends nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from carbon.development_session.research_loop import SELECT

from .. import boundaries
from ..controller import CampaignController, ControllerError
from ..grant import SpendingGrant
from ..provider import TaskSpec
from . import attack
from . import score as scoring
from . import stage as stages
from .model import LiveModel, ModelAccessRefused, ScriptedModel, text, tool
from .phase2 import DRY_RUN_GRANT, RunnerRefused, _root, credential_file, load_grant
from .provider import GraphiteProvider, SessionBrief
from .roles import ROLES, RoleName

REPOSITORY = Path(__file__).resolve().parents[3]
STAGE = "test_iterate"
ROLE = RoleName.CONSTRUCTOR
#: Per-role call caps (the grant derivation, `grants/README.md`).
ROLE_CALL_CAPS = {RoleName.CONSTRUCTOR: 48, RoleName.ATTACKER: 16}
#: The owner's per-campaign ceiling (OWNER-CHALLENGE-STEP4-01).
CAMPAIGN_CEILING = "5.00"
CAMPAIGN = "step4-constructor"
#: Each role's campaign: one role, one workspace and one credential each.
CAMPAIGNS = {RoleName.CONSTRUCTOR: CAMPAIGN, RoleName.ATTACKER: "step4-attacker"}
OBJECTIVE = {
    "objective": (
        "Propose a battery recipe inside the published construction contract. "
        "Validate and practice before selecting, and select only with evidence "
        "from your own practice. Stop and say why if nothing beats what you tried."
    ),
    "challenge": "battery-fastcharge-ageing-development-v1",
    "stage": STAGE,
    "construction_level": 0,
}
DRY_RUN_SCRIPT_STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "battery-fastcharge-ageing-development-v1",
    "backbone": "knn",
    "parameters": {"neighbours": 6},
}


def _commit():
    out = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return out if len(out) == 40 else "0" * 40


def _bind_store(root, grant):
    """One store per grant, and one grant per store."""
    marker = root / "store.json"
    document = {"grant_id": grant.grant_id, "grant": grant.document()}
    if marker.exists():
        if json.loads(marker.read_bytes()) != document:
            raise RunnerRefused("grant_changed_under_existing_store")
    else:
        marker.write_text(json.dumps(document, sort_keys=True) + "\n")
        marker.chmod(0o600)


def _brief(role=ROLE):
    checkout = boundaries.manifest_digest(
        boundaries.checkout_manifest(REPOSITORY, ROLES[role].boundary)
    )
    observation = dict(OBJECTIVE) if role is ROLE else attack.brief_observation()
    return SessionBrief(
        role=role,
        initial_observation=observation,
        checkout_commit=_commit(),
        checkout_manifest_digest=checkout,
    )


def _register(control, profile_digest, checkout, role=ROLE):
    campaign = CAMPAIGNS[role]
    try:
        control.register_campaign(
            campaign,
            role=ROLES[role].boundary,
            workspace_id="ws-" + campaign,
            credential_ref="cred-" + campaign,
            checkout_digest=checkout,
            profile_digest=profile_digest,
            ceiling=CAMPAIGN_CEILING,
        )
    except ControllerError as error:
        if error.code != "workspace_or_credential_shared":
            raise


def _log(root, entry):
    with (root / "iteration-log.jsonl").open("a") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")


async def run_session(
    root, *, grant, model, miner_tools, key=None, backend=None, role=ROLE
):
    """One session of `role` (Constructor or Attacker) and Carbon's side of
    it. Returns the log entry."""
    profile = stages.stage_profile(STAGE)
    digest = stages.profile_digest(profile)
    graphite = GraphiteProvider(
        root=root / "graphite",
        grant=grant,
        model=model,
        miner_tools=miner_tools,
        role_call_caps=ROLE_CALL_CAPS,
        stage_profile=profile,
    )
    control = CampaignController(
        root=root / "controller",
        provider=graphite,
        grant=grant,
        operator="carbon-operator",
        clock=lambda: datetime.datetime.now(datetime.UTC),
    )
    session_brief = _brief(role)
    _register(control, digest, session_brief.checkout_manifest_digest, role)
    campaign = CAMPAIGNS[role]
    runs = sorted((root / "graphite" / "runs").glob("graphite-*"))
    key = key or role.value + "-" + str(len(runs) + 1)
    spec = TaskSpec(
        campaign_id=campaign,
        role=ROLES[role].boundary.value,
        workspace_id="ws-" + campaign,
        credential_ref="cred-" + campaign,
        profile_digest=digest,
        instructions_digest=graphite.register_brief(session_brief),
        max_runtime_s=grant.max_runtime_s,
    )
    control.launch(spec, key)
    run_id = graphite.run_id_for(key)
    state = await graphite.run_async(run_id)
    control.poll(key)
    entry = {
        "schema": "carbon.graphite.iteration-log.v1",
        "session": key,
        "run_id": run_id,
        "role": role.value,
        "stage": STAGE,
        "state": state,
        "failure": graphite._state(run_id)["failure"],
        "settled_usd": str(graphite.usage(run_id).settled),
        "model": json.loads((graphite._dir(run_id) / "session-open.json").read_bytes())[
            "role"
        ]["model"],
        "selection": None,
        "score": None,
        "refused": None,
        "finding": None,
        "attempts": None,
        "fail_opens": None,
    }
    if role is RoleName.ATTACKER:
        _attacker_side(root, control, graphite, run_id, entry)
    elif state == "succeeded":
        try:
            selection = scoring.load_selection(graphite._dir(run_id))
            entry["selection"] = {
                "strategy": selection["strategy"],
                "strategy_hash": selection["strategy_hash"],
            }
            report = scoring.score_selection(
                selection, backend=backend or _backend(), repository=REPOSITORY
            )
            path = root / "scores" / (run_id + ".json")
            path.parent.mkdir(mode=0o700, exist_ok=True)
            path.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
            entry["score"] = {
                "eligible": report["candidate"]["eligible"],
                "E": report["candidate"]["E"],
                "E_important": report["candidate"]["E_important"],
                "state_sha256": report["rebuild"]["state_sha256"],
                "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        except scoring.SelectionRefused as refused:
            entry["refused"] = refused.code
            if refused.finding:
                evidence = json.dumps({"run_id": run_id, "code": refused.code}).encode()
                finding_id = (run_id + "-" + refused.code)[:120]
                control.record_finding(finding_id, scoring.FINDING, evidence)
                entry["finding"] = finding_id
    _log(root, entry)
    return entry


def _attacker_side(root, control, graphite, run_id, entry):
    """Carbon's analysis of an Attacker session. Each verified fail-open is a
    finding; the rows are kept for the coverage report."""
    rows, fail_opens = attack.analyse(graphite._dir(run_id))
    path = root / "attacks" / (run_id + ".json")
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    for row in fail_opens:
        evidence = json.dumps({"run_id": run_id, **row}, sort_keys=True).encode()
        control.record_finding(
            (run_id + "-" + row["identity"])[:120], scoring.FINDING, evidence
        )
    entry["attempts"] = len(rows)
    entry["fail_opens"] = [row["identity"] for row in fail_opens]


def write_coverage(root, suite_report):
    """Merge every Attacker session's rows with a suite v1 coverage report."""
    rows = []
    for path in sorted((root / "attacks").glob("*.json")):
        rows.extend(json.loads(path.read_bytes()))
    report = attack.coverage(rows, suite_report)
    (root / "coverage.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n"
    )
    return report


def _backend():
    from carbon.battery.worker import DirectBackend

    return DirectBackend(REPOSITORY)


def session(args, environ=None):
    import os

    environ = os.environ if environ is None else environ
    root = _root(args.root)
    if args.dry_run:
        if args.grant or args.credential_env or args.configuration:
            raise RunnerRefused("dry_run_takes_no_grant_credential_or_campaign")
        root = root / "dry-run"
        root.mkdir(mode=0o700, exist_ok=True)
        grant = SpendingGrant.from_document(DRY_RUN_GRANT)
        _bind_store(root, grant)
        model = ScriptedModel(
            [
                tool("carbon_research_v2__get_challenge_info", {}),
                tool(
                    SELECT,
                    {
                        "strategy_json": json.dumps(DRY_RUN_SCRIPT_STRATEGY),
                        "reason": "dry run: a scripted selection",
                        "used_feedback": False,
                    },
                ),
                text("dry run"),
            ]
        )
        role = RoleName.ATTACKER if args.role == "attacker" else ROLE
        if role is RoleName.ATTACKER:
            model = ScriptedModel(
                [
                    tool(
                        "carbon_research_v2__dry_validate",
                        {"strategy_json": json.dumps(DRY_RUN_SCRIPT_STRATEGY)},
                    ),
                    text("dry run: one attempt"),
                ]
            )
        entry = asyncio.run(
            run_session(root, grant=grant, model=model, miner_tools=None, role=role)
        )
        print(json.dumps({**entry, "dry_run": True}, indent=1, sort_keys=True))
        return 0
    if not (args.grant and args.configuration and args.campaign):
        raise RunnerRefused("grant_configuration_and_campaign_required")
    grant = load_grant(args.grant)
    _bind_store(root, grant)
    with credential_file(env=args.credential_env, environ=environ) as reference:
        try:
            model = LiveModel(
                grant=grant, credential_file=reference, provider="graphite"
            )
        except ModelAccessRefused as error:
            raise RunnerRefused(error.code) from None

        async def attached():
            from .miner_path import battery_tools

            async with battery_tools(args.configuration, args.campaign) as (sdk, _):
                return await run_session(
                    root,
                    grant=grant,
                    model=model,
                    miner_tools=sdk,
                    key=args.key,
                    role=RoleName.ATTACKER if args.role == "attacker" else ROLE,
                )

        entry = asyncio.run(attached())
    print(json.dumps(entry, indent=1, sort_keys=True))
    return 0 if entry["state"] == "succeeded" else 4


def log(args):
    root = _root(args.root)
    path = root / "iteration-log.jsonl"
    with contextlib.suppress(FileNotFoundError):
        sys.stdout.write(path.read_text())
    return 0


def parser():
    top = argparse.ArgumentParser(
        prog="python -m carbon.agent_campaign.graphite.phase3"
    )
    commands = top.add_subparsers(dest="command", required=True)
    one = commands.add_parser("session")
    one.add_argument("--root", required=True)
    one.add_argument("--grant")
    one.add_argument("--credential-env", default="ENGY_API_KEY")
    one.add_argument("--configuration")
    one.add_argument("--campaign")
    one.add_argument("--key")
    one.add_argument("--dry-run", action="store_true")
    one.add_argument(
        "--role", choices=("constructor", "attacker"), default="constructor"
    )
    two = commands.add_parser("log")
    two.add_argument("--root", required=True)
    three = commands.add_parser("coverage")
    three.add_argument("--root", required=True)
    three.add_argument("--suite-report", required=True)
    three.add_argument("--dry-run", action="store_true")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "session":
        if args.dry_run:
            args.credential_env = None
        return session(args)
    if args.command == "coverage":
        root = _root(args.root)
        root = root / "dry-run" if args.dry_run else root
        suite_report = json.loads(Path(args.suite_report).read_bytes())
        print(json.dumps(write_coverage(root, suite_report), indent=1, sort_keys=True))
        return 0
    return log(args)


if __name__ == "__main__":
    sys.exit(main())
