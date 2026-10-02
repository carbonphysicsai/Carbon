"""Graphite phase 4: the Attacker's sessions, beside #504's Constructor
(CHALLENGE-PROTOCOL-04; OWNER-CHALLENGE-STEP4-01).

    python -m carbon.agent_campaign.graphite.phase4 run --root DIR \
        --grant docs/development/graphite/grants/GRAPHITE-GRANT-STEP4.json \
        --credential-file PATH \
        --miner-profile PROFILE.json --miner-campaign ID [--session N] \
        [--challenge TOKEN]
    python -m carbon.agent_campaign.graphite.phase4 run --root DIR --dry-run
    python -m carbon.agent_campaign.graphite.phase4 coverage --root DIR [--dry-run]
    python -m carbon.agent_campaign.graphite.phase4 log --root DIR [--dry-run]

Challenge-neutral: the runner takes the Challenge (`--challenge`, its
contract token; by default the Challenge that defines the protocol in
Phase 1) and reads its specifics from that Challenge's records
(`challenge.py`): the campaign, grant, ceiling and call cap; the code-run
wall allowance; the suite coverage report; the admission gate; and, through
the stage profile, the permission inventory and construction level.

For battery, the Constructor block runs on #504's runner (`phase3`) under
GRAPHITE-GRANT-PHASE3, and this runner runs the Attacker block on the same
harness under the step 4 grant (PROTO4-D4, PROTO4-D5). One session:

1. **Launch.** The #475 campaign controller reserves the grant's
   `worst_case_run_cost` for the run, inside the attacker campaign's ceiling
   (OWNER-CHALLENGE-STEP4-01 for battery). The campaign's profile is the
   stage profile of `test_iterate` (`stage.py`, PROTO4-D1 and -D2), which
   names the construction level the campaign runs at (PROTO4-D9).
2. **The session.** `AttackerProvider` is #504's `GraphiteProvider` with:
   - the stage profile, without which it refuses to exist (PROTO4-D3);
   - the Attacker's own call cap from the Challenge's campaign record, as
     the run ledger's `provider_attempts` and the research loop's
     `max_provider_calls` (#504's GRAPHITE-D26 mechanism);
   - the real miner path, attached for the session through #504's
     `miner_path.attach` (the standard miner door to the Challenge's
     DEVELOPMENT campaign; operation ids namespaced by run);
   - `AttackerTools` between the Attacker's toolbox and the miner path: at
     most `MAX_CODE_RUNS` code runs a session (practice, `run_python`,
     `run_julia`), counted across resumes, and every sandbox code run with a
     wall allowance of at most the Challenge's `code_run_seconds`. Both are
     refused before dispatch (PROTO4-D6).
3. **Carbon's side** (`attack.analyse`), from the session's journal, never the
   model's prose. The rows are kept under `STORE/attacks/` with the
   Challenge and construction level the session recorded. Each reproduced
   fail-open is recorded on the controller as a finding (`FAILING_TRIGGER`),
   where it stops any later expansion. One line is appended to
   `STORE/iteration-log.jsonl`.
4. **Coverage.** `coverage` merges every session's rows with the Challenge's
   test suite v1 coverage report under its digest (`STORE/coverage.json`),
   at the one construction level the sessions ran at.

**Stores.** `STORE` is `DIR/attacker`, so one `DIR` can also hold #504's
Constructor store. The controller binds one grant to the store; a registry
outside the store (`--grant-registry`) binds the grant to one store, so a
second store can never enforce the same ceiling twice. Only the grant the
Challenge's campaign record names is accepted.

**Credential.** Only the path of an owner-only Engy key file
(`--credential-file`): a regular file, not a link, owned by this user, mode
0600 or stricter. It is checked by its metadata and never read, printed or
logged here; the model access reads it when it calls.

**`--dry-run`** runs one session with a scripted model, a synthetic copy of
the Challenge's grant and no miner path (its tools answer that none is
attached), under `DIR/attacker-dry-run`, then the coverage merge. It sends
nothing and spends nothing.

Nothing here grades a finding, submits, opens a pull request or touches chain
state. Not security acceptance.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import MAX_RESEARCH_TRIALS
from carbon.development_session.research_loop import run_epoch
from carbon.development_session.research_tools import PREFIX

from .. import boundaries
from ..grant import SpendingGrant
from ..provider import ProviderUnavailable, TaskSpec
from . import attack
from . import challenge as challenges
from . import stage as stages
from . import tools as toolbox
from .phase3 import RunnerRefused, _root, load_grant
from .provider import EPOCH, OWNER, GraphiteProvider, SessionBrief
from .roles import ROLES, RoleName

REPOSITORY = Path(__file__).resolve().parents[3]
#: The pipeline stage an Attacker campaign runs at (PROTO4-D2).
STAGE = "test_iterate"
OPERATOR = "graphite-phase4-runner"
#: Code runs a session may start: the research loop's own per-epoch limit,
#: which it cannot count for delegated miner tools (PROTO4-D6).
MAX_CODE_RUNS = MAX_RESEARCH_TRIALS
GRANT_REGISTRY = Path("~/.carbon/graphite/grant-stores")
ROWS_SCHEMA = attack.ROWS_SCHEMA
LOG_SCHEMA = "carbon.graphite.iteration-log.v2"
_TERMINAL = ("succeeded", "failed", "cancelled")


def limits(challenge):
    """An Attacker session's limits, from the Challenge's records: the
    campaign's per-session model calls, the shared code-run cap, and the
    Challenge's code-run wall allowance."""
    return {
        "model_calls": challenge.campaign["session_turns"],
        "code_runs": MAX_CODE_RUNS,
        "code_run_seconds_at_most": challenge.code_run_seconds(),
    }


# -- the Attacker's tools ------------------------------------------------------------------
class AttackerTools:
    """What the Attacker's toolbox delegates to: the real miner path, with the
    session's code-run cap and wall allowance enforced before dispatch."""

    def __init__(self, *, miner, emit, started, limits):
        self.miner, self.emit, self.started = miner, emit, started
        self.limits = dict(limits)

    def _code_run_refusal(self, arguments):
        if self.started >= self.limits["code_runs"]:
            return "attacker_code_run_cap_reached"
        if arguments.get("action") in attack.CODE_ACTIONS:
            try:
                inner = json.loads(arguments.get("arguments_json"))
            except (TypeError, ValueError):
                inner = None
            if type(inner) is not dict:
                return "code_run_arguments_unreadable"
            seconds = inner.get("seconds")
            most = self.limits["code_run_seconds_at_most"]
            if type(seconds) is not int or not 1 <= seconds <= most:
                return "code_run_needs_seconds_up_to_" + str(most)
        return None

    async def call(self, name, arguments, identity):
        code_run = attack.is_code_run(name, arguments)
        if code_run:
            refused = self._code_run_refusal(arguments)
            if refused is not None:
                return toolbox.refusal(
                    "REFUSED_NOT_RUN", refused, limits=dict(self.limits)
                )
        if self.miner is None:
            return toolbox.refusal(
                toolbox.UNAVAILABLE,
                "miner_path_not_attached",
                reason="This session has no miner campaign attached; nothing ran.",
            )
        if code_run:
            self.started += 1
            self.emit(
                "code-run-" + identity,
                {"kind": "code_run_dispatched", "tool": name, "identity": identity},
            )
        return await self.miner.call(name, arguments, identity)


# -- the provider --------------------------------------------------------------------------
class AttackerProvider(GraphiteProvider):
    """#504's `GraphiteProvider` for Attacker sessions: staged, for the
    Challenge its stage profile names, with that Challenge's call cap and
    limits, the real miner path and `AttackerTools`."""

    def __init__(
        self,
        *,
        root,
        grant,
        model,
        stage_profile,
        miner_attach=None,
        miner_tools=None,
        **kwargs,
    ):
        if stage_profile is None:
            raise ProviderUnavailable("stage_profile_required")
        try:
            stages.check(stage_profile)
            challenge = challenges.get(stage_profile["challenge"])
            session_limits = limits(challenge)
        except ValueError as error:
            raise ProviderUnavailable(str(error)) from None
        self.challenge, self.limits = challenge, session_limits
        kwargs.setdefault("max_calls_per_run", session_limits["model_calls"])
        super().__init__(
            root=root,
            grant=grant,
            model=model,
            miner_tools=miner_tools,
            stage_profile=stage_profile,
            **kwargs,
        )
        self.miner_attach = miner_attach

    def start(self, spec, idempotency_key):
        if type(spec) is TaskSpec and self.find(idempotency_key) is None:
            brief = self._brief(spec.instructions_digest)
            if brief is not None and brief["role"] != RoleName.ATTACKER.value:
                raise ProviderUnavailable("phase4_runs_the_attacker_only")
        return super().start(spec, idempotency_key)

    def _manifest(self, opened):
        return {**super()._manifest(opened), "implementation": "graphite-phase4"}

    def code_runs(self, run_id):
        """Code runs dispatched so far in this session, from its events, so a
        resumed session keeps counting."""
        return sum(
            1
            for event in self.events(run_id, 0)
            if event["kind"] == "code_run_dispatched"
        )

    @contextlib.asynccontextmanager
    async def _attached(self, run_id):
        if self.miner_attach is None:
            yield self.miner_tools
            return
        async with self.miner_attach(session=run_id.removeprefix("graphite-")) as tools:
            yield tools

    async def _epoch(self, run_id, ledger, role, brief, selection):
        def emit(event_id, body):
            self._emit(run_id, event_id, body)

        async with self._attached(run_id) as miner:
            sdk = toolbox.GraphiteToolbox(
                role=role,
                literature_index=self.literature,
                emit=emit,
                miner_tools=AttackerTools(
                    miner=miner,
                    emit=emit,
                    started=self.code_runs(run_id),
                    limits=self.limits,
                ),
            )
            return await run_epoch(
                ledger,
                owner=OWNER,
                epoch=EPOCH,
                sdk=sdk,
                credential_file=None,
                initial_observation=brief["initial_observation"],
                transport=self.model.transport_for(selection),
                provider=selection,
                instructions=role.prompt,
                tools=role.tool_schemas(),
                max_provider_calls=self.max_calls_per_run,
            )


# -- brief, controller and one session -------------------------------------------------------
def session_brief(challenge, *, checkout_commit, repository=REPOSITORY):
    """The Attacker's brief: the Challenge's public development path and suite
    v1's eight vectors."""
    role = ROLES[RoleName.ATTACKER]
    manifest = boundaries.checkout_manifest(repository, role.boundary)
    return SessionBrief(
        role=RoleName.ATTACKER,
        initial_observation=attack.brief_observation(
            challenge, stage=STAGE, limits=limits(challenge)
        ),
        checkout_commit=checkout_commit,
        checkout_manifest_digest=boundaries.manifest_digest(manifest),
    )


def controller_for(store, provider, grant, clock=None):
    from ..controller import CampaignController

    kwargs = {} if clock is None else {"clock": clock}
    return CampaignController(
        root=Path(store) / "controller",
        provider=provider,
        grant=grant,
        operator=OPERATOR,
        **kwargs,
    )


def ensure_campaign(control, challenge, *, checkout_digest, profile_digest):
    campaign = challenge.campaign
    if campaign["campaign"] in control.budget()["campaigns"]:
        return
    control.register_campaign(
        campaign["campaign"],
        role=ROLES[RoleName.ATTACKER].boundary,
        workspace_id=campaign["workspace"],
        credential_ref=campaign["credential_ref"],
        checkout_digest=checkout_digest,
        profile_digest=profile_digest,
        ceiling=campaign["ceiling_usd"],
    )


def session_key(challenge, number):
    return f"{challenge.campaign['campaign']}-session-{number}"


def carbon_side(store, control, provider, run_id):
    """Carbon's analysis of a finished session: rows kept with the Challenge
    and construction level the session recorded, each reproduced fail-open
    recorded as a finding. Returns (rows, finding ids)."""
    rows, fail_opens = attack.analyse(provider._dir(run_id), provider.challenge)
    recorded = provider._opened(run_id)["stage"]
    directory = Path(store) / "attacks"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / (run_id + ".json")
    if not path.exists():
        write_once(
            path,
            canonical(
                {
                    "schema": ROWS_SCHEMA,
                    "run_id": run_id,
                    "challenge": recorded["challenge"],
                    "construction_level": recorded["construction_level"],
                    "rows": rows,
                }
            ),
        )
    findings = []
    for row in fail_opens:
        evidence = canonical(
            {"schema": "carbon.graphite.attack-finding.v1", "run_id": run_id, **row}
        )
        finding_id = "graphite-attack-" + digest(evidence)[7:23]
        control.record_finding(finding_id, attack.FINDING_CONDITION, evidence)
        findings.append(finding_id)
    return rows, findings


def _log(store, entry):
    path = Path(store) / "iteration-log.jsonl"
    if path.exists() and any(
        json.loads(line)["run_id"] == entry["run_id"]
        for line in path.read_bytes().splitlines()
    ):
        return
    with path.open("ab") as stream:
        stream.write(canonical(entry) + b"\n")
    path.chmod(0o600)


def run_session(store, control, provider, brief, number):
    """Launch (or resume) Attacker session `number` under the controller, run
    it, and do Carbon's side. Returns the iteration-log entry."""
    if type(number) is not int or not 1 <= number <= control.grant.permitted_runs:
        raise ValueError("session is 1 .. the grant's permitted runs")
    challenge = provider.challenge
    if brief.initial_observation.get("challenge") != challenge.public_identity():
        raise ValueError("brief_for_another_challenge")
    profile = stages.profile_digest(provider.stage_profile)
    ensure_campaign(
        control,
        challenge,
        checkout_digest=brief.checkout_manifest_digest,
        profile_digest=profile,
    )
    campaign = challenge.campaign
    spec = TaskSpec(
        campaign_id=campaign["campaign"],
        role=ROLES[RoleName.ATTACKER].boundary.value,
        workspace_id=campaign["workspace"],
        credential_ref=campaign["credential_ref"],
        profile_digest=profile,
        instructions_digest=provider.register_brief(brief),
        max_runtime_s=control.grant.max_runtime_s,
    )
    key = session_key(challenge, number)
    control.recover()
    control.launch(spec, key)
    run_id = provider.run_id_for(key)
    final = provider.run(run_id) if provider.find(key) is not None else None
    phase = control.poll(key)
    rows, findings = (
        carbon_side(store, control, provider, run_id) if final else ([], [])
    )
    opened = provider._opened(run_id) if final else None
    entry = {
        "schema": LOG_SCHEMA,
        "session": number,
        "run_id": run_id,
        "challenge": challenge.token,
        "construction_level": provider.stage_profile["construction_level"],
        "role": RoleName.ATTACKER.value,
        "stage": STAGE,
        "provider_state": final,
        "controller_phase": str(phase),
        "failure": provider._state(run_id)["failure"] if final else None,
        "settled_usd": str(provider.usage(run_id).settled) if final else None,
        "model": opened["role"]["model"] if opened else None,
        "attempts": len(rows),
        "fail_opens": [r["identity"] for r in rows if r["verdict"] == "FAIL_OPEN"],
        "findings": findings,
    }
    if final in _TERMINAL:
        _log(store, entry)
    return entry


def load_suite_report(challenge, path=None):
    """The Challenge's suite v1 coverage report (its record names it), or the
    one at `path`, checked against the suite pin and the Challenge."""
    try:
        report = json.loads(
            Path(path or REPOSITORY / challenge.suite_report).read_bytes()
        )
    except (OSError, ValueError):
        raise RunnerRefused("suite_report_not_the_current_suite_pin") from None
    try:
        attack.check_suite_report(report, challenge)
    except ValueError as error:
        raise RunnerRefused(str(error)) from None
    return report


def write_coverage(store, suite_report, challenge):
    """Merge every Attacker session's rows with the Challenge's suite v1
    coverage report, at the one construction level the sessions ran at."""
    rows, levels = [], set()
    for path in sorted((Path(store) / "attacks").glob("*.json")):
        document = json.loads(path.read_bytes())
        if document.get("schema") != ROWS_SCHEMA:
            raise RunnerRefused("attack_rows_schema_unknown")
        if document["challenge"] != challenge.token:
            raise RunnerRefused("attack_rows_for_another_challenge")
        levels.add(document["construction_level"])
        rows.extend(document["rows"])
    if len(levels) != 1:
        # A climb is a new frozen run: evidence stays bound to its level.
        raise RunnerRefused(
            "sessions_at_different_construction_levels"
            if levels
            else "no_attacker_session_analysed"
        )
    try:
        report = attack.coverage(
            rows, suite_report, challenge=challenge, construction_level=levels.pop()
        )
    except ValueError as error:
        raise RunnerRefused(str(error)) from None
    target = Path(store) / "coverage.json"
    temporary = target.with_name("coverage.json.tmp")
    temporary.write_bytes(canonical(report))
    temporary.chmod(0o600)
    os.replace(temporary, target)
    return report


# -- the runner ----------------------------------------------------------------------------
def owner_only_file(path):
    """The Engy key's file, checked by its metadata alone: a regular file, not
    a link, owned by this user, with no group or other permission."""
    candidate = Path(path).expanduser()
    try:
        info = os.lstat(candidate)
    except OSError:
        raise RunnerRefused("credential_file_missing") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RunnerRefused("credential_file_not_a_regular_file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RunnerRefused("credential_file_must_be_owner_only")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RunnerRefused("credential_file_not_owned_by_this_user")
    if info.st_size == 0:
        raise RunnerRefused("credential_file_empty")
    return str(candidate)


def bind_grant_store(registry, grant, store):
    """One store per grant: the registry records the store a grant is spent
    from, and refuses another (the controller already refuses another grant
    under one store)."""
    registry = Path(registry).expanduser()
    registry.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {
        "grant_id": grant.grant_id,
        "grant_digest": digest(canonical(grant.document())),
        "store": str(Path(store).resolve()),
    }
    path = registry / (grant.grant_id + ".json")
    if path.exists():
        if json.loads(path.read_bytes()) != record:
            raise RunnerRefused("grant_bound_to_another_store")
        return
    write_once(path, canonical(record))


def _head(repository=REPOSITORY):
    out = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if len(out) != 40:
        raise RunnerRefused("checkout_commit_unavailable")
    return out


def _store(root, dry_run):
    store = root / ("attacker-dry-run" if dry_run else "attacker")
    store.mkdir(mode=0o700, exist_ok=True)
    return store


def _challenge(token):
    """The Challenge named on the command line, or by default the one that
    defines the protocol in Phase 1."""
    try:
        if token is None:
            return challenges.protocol_challenge()
        return challenges.get(token)
    except challenges.ChallengeError as error:
        raise RunnerRefused(str(error)) from None


def _stage_profile(challenge):
    try:
        return stages.stage_profile(STAGE, challenge)
    except ValueError as error:
        raise RunnerRefused(str(error)) from None


def command_run(args):
    root = _root(args.root)
    challenge = _challenge(args.challenge)
    if args.dry_run:
        if any(
            (args.grant, args.credential_file, args.miner_profile, args.miner_campaign)
        ):
            raise RunnerRefused("dry_run_takes_no_grant_credential_or_miner_campaign")
        return dry_run(root, challenge)
    missing = [
        name
        for name, value in (
            ("--grant", args.grant),
            ("--credential-file", args.credential_file),
            ("--miner-profile", args.miner_profile),
            ("--miner-campaign", args.miner_campaign),
        )
        if not value
    ]
    if missing:
        raise RunnerRefused("required: " + ", ".join(missing))
    grant = load_grant(args.grant)
    if grant.grant_id != challenge.campaign["grant"]["id"]:
        # The reason code predates the generalization and is kept unchanged.
        raise RunnerRefused("grant_is_not_the_step4_grant")
    engy = owner_only_file(args.credential_file)
    store = _store(root, False)
    bind_grant_store(args.grant_registry, grant, store)
    from . import miner_path
    from .model import LiveModel, ModelAccessRefused

    try:
        model = LiveModel(grant=grant, credential_file=engy, provider="graphite")
    except ModelAccessRefused as refused:
        raise RunnerRefused(refused.code) from None

    def attach(*, session):
        return miner_path.attach(
            args.miner_profile, args.miner_campaign, session=session
        )

    provider = AttackerProvider(
        root=store / "graphite",
        grant=grant,
        model=model,
        stage_profile=_stage_profile(challenge),
        miner_attach=attach,
    )
    control = controller_for(store, provider, grant)
    try:
        brief = session_brief(challenge, checkout_commit=_head())
        entry = run_session(store, control, provider, brief, args.session)
    finally:
        control.close()
    print(json.dumps(entry, indent=1, sort_keys=True))
    return 0 if entry["provider_state"] == "succeeded" else 4


def command_coverage(args):
    root = _root(args.root)
    challenge = _challenge(args.challenge)
    store = root / ("attacker-dry-run" if args.dry_run else "attacker")
    if not (store / "attacks").is_dir():
        raise RunnerRefused("no_attacker_session_analysed")
    report = write_coverage(
        store, load_suite_report(challenge, args.suite_report), challenge
    )
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


def command_log(args):
    root = Path(args.root).expanduser().resolve()
    store = root / ("attacker-dry-run" if args.dry_run else "attacker")
    with contextlib.suppress(FileNotFoundError):
        sys.stdout.write((store / "iteration-log.jsonl").read_text())
    return 0


# -- the dry run ---------------------------------------------------------------------------
#: What a dry-run grant changes in the Challenge's grant: who and what it
#: names. Its amounts, runs and runtime are the real grant's.
DRY_RUN_IDENTITY = {
    "account": "dry-run-no-account",
    "granted_by": "nobody-dry-run",
    "expires_at": "2099-01-01T00:00:00Z",
}


def dry_run_grant(challenge):
    """A synthetic copy of the grant the Challenge's campaign record names."""
    named = challenge.campaign["grant"]
    try:
        document = json.loads((REPOSITORY / named["file"]).read_bytes())
    except (OSError, ValueError):
        raise RunnerRefused("campaign_grant_file_unreadable") from None
    if document.get("grant_id") != named["id"]:
        raise RunnerRefused("campaign_grant_file_names_another_grant")
    return SpendingGrant.from_document(
        {
            **document,
            **DRY_RUN_IDENTITY,
            "grant_id": challenge.campaign["campaign"] + "-dry-run-synthetic",
        }
    )


def dry_run_script(challenge):
    from .model import text, tool

    outside = challenge.recipe_outside_contract()
    return [
        tool(PREFIX + "get_challenge_info", {}),
        tool(PREFIX + "dry_validate", {"strategy_json": json.dumps(outside)}),
        tool(
            PREFIX + "start_research_task",
            {
                "kind": "workspace",
                "strategy_json": None,
                "action": "run_python",
                "arguments_json": json.dumps({"source": "print(1)", "files": []}),
                "hypothesis": "a code run without a wall allowance",
                "expected_effect": "refused before dispatch",
            },
        ),
        text("DRY RUN: the scripted Attacker stops here."),
    ]


def dry_run(root, challenge):
    from .model import ScriptedModel

    store = root / "attacker-dry-run"
    if store.exists():
        shutil.rmtree(store)
    store.mkdir(mode=0o700)
    grant = dry_run_grant(challenge)
    bind_grant_store(store / "grant-stores", grant, store)
    provider = AttackerProvider(
        root=store / "graphite",
        grant=grant,
        model=ScriptedModel(dry_run_script(challenge)),
        stage_profile=_stage_profile(challenge),
    )
    control = controller_for(store, provider, grant)
    try:
        entry = run_session(
            store,
            control,
            provider,
            session_brief(challenge, checkout_commit="0" * 40),
            1,
        )
    finally:
        control.close()
    report = write_coverage(store, load_suite_report(challenge), challenge)
    print(
        json.dumps(
            {
                **entry,
                "dry_run": {
                    "synthetic": True,
                    "note": "scripted model, synthetic grant, no miner path; "
                    "Carbon's re-verification and coverage merge are its own",
                    "coverage_suite_digest": report["suite_digest"],
                    "coverage_construction_level": report["construction_level"],
                },
            },
            indent=1,
            sort_keys=True,
        )
    )
    return 0 if entry["provider_state"] == "succeeded" else 4


def main(argv=None):
    parser = argparse.ArgumentParser(prog="graphite.phase4")
    sub = parser.add_subparsers(dest="command", required=True)
    challenge_help = (
        "the Challenge's contract token (default: the Challenge that defines "
        "the protocol in Phase 1)"
    )
    run = sub.add_parser("run")
    run.add_argument("--root", required=True)
    run.add_argument("--challenge", help=challenge_help)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--grant")
    run.add_argument(
        "--credential-file",
        help="path of an owner-only file holding the Engy key; never read here",
    )
    run.add_argument("--miner-profile")
    run.add_argument("--miner-campaign")
    run.add_argument("--session", type=int, default=1)
    run.add_argument("--grant-registry", default=str(GRANT_REGISTRY))
    coverage = sub.add_parser("coverage")
    coverage.add_argument("--root", required=True)
    coverage.add_argument("--challenge", help=challenge_help)
    coverage.add_argument("--suite-report")
    coverage.add_argument("--dry-run", action="store_true")
    log = sub.add_parser("log")
    log.add_argument("--root", required=True)
    log.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return {"run": command_run, "coverage": command_coverage, "log": command_log}[
        args.command
    ](args)


if __name__ == "__main__":
    sys.exit(main())
