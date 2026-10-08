"""`onboard`: one resumable command that brings a Challenge up on the producer
host (VALIDATOR-20).

    python -m carbon.challenge_validator.onboard --challenge ID --inputs INPUTS.json \\
        --state DIR [--study] [--accept-code COMMIT]

It runs, in order, the same commands the operator sheet runs by hand, each one
an existing module's CLI. No stage re-implements one:
1. `truth`: verify the Challenge's truth environment, and materialize it
   first when the verify refuses;
2. `deployment`: verify the deployment, and initialize its root first when
   it is not initialized yet;
3. `pool`: one producer tick, an optional same-host import of the published
   packages, then a check that the Challenge has a published batch;
4. `tuning` (when the inputs name one): seal the tuning set, then the quiz:
   jobs, solve, refine, solve the refine, select (further rounds when the
   select asks), seal;
5. `study` (only with `--study`): the training-budget study sets;
6. `verify`: the producer timer is enabled and active, and the last push
   succeeded.

**Resumable and idempotent.** `DIR/onboard-state.json` (owner-only) records
each completed step and the public values it produced. A rerun skips every
completed step. Read-only checks rerun every time, and a check whose public
values differ from the recorded ones is refused (`onboard_state_mismatch`),
never redone silently. A rerun on another code commit is refused
(`onboard_code_changed`) unless `--accept-code` names the new commit.

**Owner stops** exit 3 with a code and the next command:
- `onboard_needs_input:<name>`;
- `onboard_needs_approval`;
- `onboard_needs_solver_licence:<name>`;
- `onboard_tell_test_lead:<code>`, for refusals the sheet says never to work
  around.

Other refusals exit 2 as `onboard_refused:<code>`.

**Public values only.** A step's output is reduced to the public fields the
adapter names (fingerprints, digests, journal sequences, counts) before it is
stored or printed. Nothing else from a command's output is kept.

It runs as the producer's service account. `verify` reads systemd state only.
A Challenge with no registered adapter is refused (`onboard_no_adapter`).
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
STATE_SCHEMA = "carbon.challenge-validator.onboard-state.v1"
INPUTS_SCHEMA = "carbon.challenge-validator.onboard-inputs.v1"
STATE_FILE = "onboard-state.json"
#: How often a stage reruns a solve that left work behind before it stops:
#: an engineering bound, never a scientific one.
ATTEMPTS = 3
#: Refusals the operator sheet says never to work around: stop and tell the
#: Test Lead.
TELL_TEST_LEAD = (
    "overlaps_prior",
    "draws_collide",
    "q2_pool_short",
    "published_case",
)


class OnboardStop(Exception):
    """A named stop. `owner` stops wait for the owner; others are refusals."""

    def __init__(self, code, *, step=None, next_command=None, owner=True):
        super().__init__(code)
        self.code = code
        self.step = step
        self.next_command = next_command
        self.owner = owner

    def report(self):
        report = {"stopped": self.code}
        if self.step is not None:
            report["step"] = self.step
        if self.next_command is not None:
            report["next"] = self.next_command
        return report


def _pick(value, *keys):
    """The named public fields of a command's JSON result."""
    if type(value) is not dict:
        return {}
    return {k: value[k] for k in keys if k in value}


def _refusal(result):
    """The refusal code a command printed, or None."""
    if type(result) is not dict:
        return None
    for key in ("refused", "unavailable"):
        if type(result.get(key)) is str:
            return result[key]
    if result.get("status") == "REFUSED" and type(result.get("reason")) is str:
        return result["reason"]
    return None


def _parse(stdout):
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    for line in reversed(text.splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def _stop_for(code, step, argv):
    command = shlex.join(argv)
    if code in ("producer_challenge_not_approved", "study_not_approved"):
        return OnboardStop("onboard_needs_approval", step=step, next_command=command)
    if code.startswith("study_human_input_missing"):
        return OnboardStop(
            "onboard_needs_input:" + code, step=step, next_command=command
        )
    if any(marker in code for marker in TELL_TEST_LEAD):
        return OnboardStop(
            "onboard_tell_test_lead:" + code, step=step, next_command=command
        )
    return OnboardStop(
        "onboard_refused:" + code, step=step, next_command=command, owner=False
    )


def default_runner(argv, *, cwd):
    completed = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False
    )
    return completed.returncode, completed.stdout


def current_commit(repository):
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() or None


# --- the state file -------------------------------------------------------------------


class State:
    """`DIR/onboard-state.json`: owner-only, public values only."""

    def __init__(self, directory, challenge_id, commit, *, accept_code=None):
        self.directory = Path(directory)
        if not self.directory.exists():
            self.directory.mkdir(parents=True, mode=0o700)
        info = os.lstat(self.directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise OnboardStop("onboard_state_not_owner_only", owner=False)
        self.path = self.directory / STATE_FILE
        if self.path.exists():
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise OnboardStop("onboard_state_not_owner_only", owner=False)
            self.value = json.loads(self.path.read_text())
            if (
                self.value.get("schema") != STATE_SCHEMA
                or self.value.get("challenge_id") != challenge_id
            ):
                raise OnboardStop("onboard_state_mismatch", owner=False)
            if self.value.get("code") != commit:
                if accept_code is None or accept_code != commit:
                    raise OnboardStop(
                        "onboard_code_changed",
                        next_command=f"--accept-code {commit}",
                        owner=False,
                    )
                self.value.setdefault("code_history", []).append(self.value["code"])
                self.value["code"] = commit
                self.save()
        else:
            self.value = {
                "schema": STATE_SCHEMA,
                "challenge_id": challenge_id,
                "code": commit,
                "steps": {},
            }
            self.save()

    def save(self):
        body = json.dumps(self.value, sort_keys=True, indent=1) + "\n"
        temporary = self.path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(body)
        os.replace(temporary, self.path)

    def done(self, key):
        return self.value["steps"].get(key)

    def record(self, key, public, digest):
        self.value["steps"][key] = {"public": public, "output_sha256": digest}
        self.save()


# --- running steps --------------------------------------------------------------------


class Context:
    """Runs one stage's steps against the state."""

    def __init__(self, state, stage, *, runner, repository, python):
        self.state = state
        self.stage = stage
        self.runner = runner
        self.repository = repository
        self.python = python
        self.ran = []
        self.send_back = {}

    def module(self, name, *args):
        return [self.python, "-m", name, *[str(a) for a in args]]

    def step(
        self,
        name,
        argv,
        *,
        extract=None,
        check=False,
        always=False,
        tolerate=(),
        send_back=False,
        plain=False,
    ):
        """Run one step unless it is recorded done. Returns its public
        values, or `{"refused": code}` for a refusal named in `tolerate`.

        - `check`: a read-only check, rerun every time; its public values
          must match the recorded ones.
        - `always`: rerun every time and re-record (a status read).
        - `plain`: a non-JSON command that succeeds by exit code alone.
        """
        key = f"{self.stage}/{name}"
        recorded = self.state.done(key)
        if recorded is not None and not (check or always):
            if send_back:
                self.send_back[key] = recorded["public"]
            return recorded["public"]
        returncode, stdout = self.runner(argv, cwd=self.repository)
        self.ran.append(key)
        if plain:
            public = {"ok": returncode == 0, "value": stdout.strip()[:64]}
            self.state.record(key, public, _sha(stdout))
            return public
        result = _parse(stdout)
        code = _refusal(result)
        if code is None and returncode != 0:
            code = f"exit_{returncode}"
        if code is not None:
            if any(code == t or code.startswith(t + ":") or t == "*" for t in tolerate):
                return {"refused": code}
            raise _stop_for(code, key, argv)
        public = extract(result) if extract else {}
        if check and recorded is not None and recorded["public"] != public:
            raise OnboardStop("onboard_state_mismatch", step=key, owner=False)
        self.state.record(key, public, _sha(stdout))
        if send_back:
            self.send_back[key] = public
        return public


def _sha(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


# --- the inputs file ------------------------------------------------------------------


def load_inputs(path, adapter):
    """The operator's inputs: owner-only JSON naming paths and public values.
    A missing required name or file is an owner stop."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise OnboardStop("onboard_needs_input:inputs") from None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise OnboardStop("onboard_inputs_not_owner_only", owner=False)
    try:
        inputs = json.loads(path.read_text())
    except ValueError:
        raise OnboardStop("onboard_inputs_malformed", owner=False) from None
    if type(inputs) is not dict or inputs.get("schema") != INPUTS_SCHEMA:
        raise OnboardStop("onboard_inputs_malformed", owner=False)
    if inputs.get("challenge_id") != adapter.challenge_id:
        raise OnboardStop("onboard_inputs_wrong_challenge", owner=False)
    for name in adapter.required:
        if name not in inputs:
            raise OnboardStop("onboard_needs_input:" + name)
    for name in adapter.required_files:
        value = inputs.get(name)
        if value is not None and not Path(value).exists():
            raise OnboardStop("onboard_needs_input:" + name)
    return inputs


def _require_files(section, names, prefix):
    for name in names:
        value = section.get(name)
        if type(value) is not str or not Path(value).exists():
            raise OnboardStop(f"onboard_needs_input:{prefix}.{name}")


# --- the battery adapter --------------------------------------------------------------


class BatteryOnboard:
    """Battery, exactly as HETZNER_PART2 steps 4, 5, 9, 11 and 14 run it."""

    required = ("deployment", "overlay", "producer_config")
    required_files = ("deployment", "producer_config")
    #: Licensed solvers that must be attested present first: battery's truth
    #: is open source, so none.
    licences = ()

    def __init__(self):
        from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

        self.challenge_id = BATTERY_CHALLENGE

    def stages(self, inputs, *, study):
        stages = ["truth", "deployment", "pool"]
        if "tuning" in inputs:
            stages.append("tuning")
        if study:
            stages.append("study")
        stages.append("verify")
        return stages

    # 1 ---------------------------------------------------------------------

    def truth(self, ctx, inputs):
        overlay = inputs["overlay"]
        verify = ctx.module(
            "carbon.battery.operate", "truth-verify", "--target", overlay
        )
        first = ctx.step("verify", verify, check=True, tolerate=("*",))
        if "refused" in first:
            ctx.step(
                "materialize",
                ctx.module(
                    "carbon.battery.operate", "truth-materialize", "--target", overlay
                ),
            )
            ctx.step("verify", verify, check=True)

    # 2 ---------------------------------------------------------------------

    def deployment(self, ctx, inputs):
        config = inputs["deployment"]
        status = ctx.module("carbon.battery.operate", "status", "--config", config)
        found = ctx.step("status", status, always=True, tolerate=("*",))
        if "refused" in found:
            ctx.step(
                "init",
                ctx.module("carbon.battery.operate", "init", "--config", config),
                extract=lambda r: _pick(r, "root_commitment", "seed_pin"),
                send_back=True,
            )
            ctx.step("status", status, always=True)

    # 3 ---------------------------------------------------------------------

    def pool(self, ctx, inputs):
        producer = inputs["producer_config"]
        challenge = self.challenge_id

        def tick_counts(result):
            report = (result or {}).get(challenge) or {}
            return {
                "filled": report.get("filled"),
                "unfilled": report.get("unfilled"),
                "cadence": report.get("cadence", "set"),
            }

        tick = ctx.step(
            "tick",
            ctx.module(
                "carbon.challenge_validator.producer", "tick", "--config", producer
            ),
            extract=tick_counts,
        )
        if tick.get("cadence") is None:
            raise OnboardStop("onboard_no_cadence", step="pool/tick")
        dev = inputs.get("dev_pool")
        if dev is not None:
            ctx.step(
                "import",
                ctx.module(
                    "carbon.challenge_validator.answer_key",
                    "import",
                    "--deployment",
                    inputs["deployment"],
                    "--producer-public-key",
                    dev["producer_public_key"],
                    "--outbox",
                    Path(dev["outbox"]) / challenge,
                ),
                extract=lambda r: {
                    "states": sorted(p.get("state") for p in r.get("packages", []))
                },
            )
        published = ctx.step(
            "published",
            ctx.module(
                "carbon.challenge_validator.producer", "status", "--config", producer
            ),
            always=True,
            extract=lambda r: {
                "published": (r.get("challenges", {}).get(challenge) or {}).get(
                    "published", 0
                )
            },
        )
        if not published["published"]:
            raise OnboardStop(
                "onboard_pool_not_published",
                step="pool/published",
                next_command="rerun onboard after the next producer tick",
                owner=False,
            )

    # 4 ---------------------------------------------------------------------

    def tuning(self, ctx, inputs):
        tuning = inputs["tuning"]
        names = (
            "role",
            "pool_prior",
            "pool_export",
            "priors",
            "quiz_work",
            "quiz_panel",
        )
        for name in names:
            if name not in tuning:
                raise OnboardStop("onboard_needs_input:tuning." + name)
        _require_files(tuning, ("quiz_panel",), "tuning")
        for prior, path in sorted(tuning["priors"].items()):
            if not Path(path).exists():
                raise OnboardStop("onboard_needs_input:tuning.priors." + prior)
        config, overlay = inputs["deployment"], inputs["overlay"]
        work = Path(tuning["quiz_work"])
        tune = "carbon.challenge_validator.tuning"
        ctx.step(
            "export-pool",
            ctx.module(
                tune, "export-pool", "--config", config, "--out", tuning["pool_export"]
            ),
        )
        priors = [f"{tuning['pool_prior']}={tuning['pool_export']}"] + [
            f"{name}={path}" for name, path in sorted(tuning["priors"].items())
        ]
        ctx.step(
            "seal",
            ctx.module(
                "carbon.challenge_validator.confirmation",
                "seal",
                "--role",
                tuning["role"],
                "--config",
                config,
                *[a for p in priors for a in ("--prior", p)],
            ),
            extract=lambda r: _pick(
                r.get("commitment"), "fingerprint", "journal_sequence"
            ),
            send_back=True,
        )
        ctx.step(
            "quiz-jobs-r1",
            ctx.module(tune, "quiz-jobs", "--config", config, "--work", work),
        )
        round_, attempt = 1, 0
        while True:
            tag = f"r{round_}a{attempt}"
            ctx.step(
                f"solve-{tag}",
                ctx.module(tune, "solve", "--work", work, "--overlay", overlay),
            )
            ctx.step(
                f"quiz-refine-{tag}",
                ctx.module(tune, "quiz-refine", "--work", work),
                extract=lambda r: _pick(r, "round", "refine_jobs"),
                send_back=True,
            )
            ctx.step(
                f"solve-refine-{tag}",
                ctx.module(
                    tune, "solve", "--work", work / "refine", "--overlay", overlay
                ),
            )
            selected = ctx.step(
                f"quiz-select-{tag}",
                ctx.module(
                    tune, "quiz-select", "--work", work, "--panel", tuning["quiz_panel"]
                ),
                extract=lambda r: _pick(
                    r, "digest", "q2_cases", "q3_scenarios", "q3_refine"
                ),
                tolerate=(
                    "tuning_quiz_needs_more_q3",
                    "tuning_quiz_needs_refine",
                    "tuning_quiz_panel_incomplete",
                ),
            )
            refused = selected.get("refused")
            if refused is None:
                break
            if refused.startswith("tuning_quiz_needs_more_q3:"):
                round_ = int(refused.rsplit(" ", 1)[-1])
                attempt = 0
                ctx.step(
                    f"quiz-jobs-r{round_}",
                    ctx.module(
                        tune,
                        "quiz-jobs",
                        "--config",
                        config,
                        "--work",
                        work,
                        "--round",
                        round_,
                    ),
                )
                continue
            attempt += 1
            if attempt >= ATTEMPTS:
                raise OnboardStop(
                    "onboard_refused:" + refused,
                    step=f"tuning/quiz-select-{tag}",
                    owner=False,
                )
        ctx.step(
            "quiz-seal",
            ctx.module(tune, "quiz-seal", "--config", config, "--work", work),
            extract=lambda r: _pick(r, "digest", "journal_sequence"),
            send_back=True,
        )

    # 5 ---------------------------------------------------------------------

    def study(self, ctx, inputs):
        study = inputs.get("study")
        if type(study) is not dict:
            raise OnboardStop("onboard_needs_input:study")
        _require_files(study, ("spec",), "study")
        spec = study["spec"]
        sets = "carbon.challenge_validator.study_sets"
        ctx.step(
            "init",
            ctx.module(sets, "init", "--spec", spec),
            extract=lambda r: _pick(r, "root_commitment", "seed_pin"),
            tolerate=("study_dir_exists",),
            send_back=True,
        )
        ctx.step("draw", ctx.module(sets, "draw", "--spec", spec))
        for name in ("eval", "confirm", "train"):
            ctx.step(
                f"jobs-{name}", ctx.module(sets, "jobs", "--spec", spec, "--set", name)
            )
            for attempt in range(ATTEMPTS):
                ctx.step(
                    f"solve-{name}-a{attempt}",
                    ctx.module(sets, "solve", "--spec", spec, "--set", name),
                )
                ingested = ctx.step(
                    f"ingest-{name}-a{attempt}",
                    ctx.module(sets, "ingest", "--spec", spec, "--set", name),
                    extract=lambda r: _pick(r, "state", "cases"),
                )
                if ingested.get("state") == "COMPLETE":
                    break
            else:
                raise OnboardStop(
                    "onboard_refused:study_incomplete",
                    step=f"study/ingest-{name}",
                    owner=False,
                )
            ctx.step(
                f"manifest-{name}",
                ctx.module(sets, "manifest", "--spec", spec, "--set", name),
                extract=lambda r: _pick(r, "fingerprint", "cases", "journal_sequence"),
                send_back=True,
            )

    # 6 ---------------------------------------------------------------------

    def verify(self, ctx, inputs):
        units = inputs.get("units")
        if type(units) is not dict or not units.get("timers") or not units.get("push"):
            raise OnboardStop("onboard_needs_input:units")
        for timer in units["timers"]:
            for query in ("is-enabled", "is-active"):
                found = ctx.step(
                    f"{query}-{timer}",
                    ["systemctl", query, timer],
                    always=True,
                    plain=True,
                )
                if not found["ok"]:
                    raise OnboardStop(
                        "onboard_unit_not_running:" + timer,
                        step=f"verify/{query}-{timer}",
                        next_command=f"systemctl enable --now {timer}",
                    )
        push = units["push"]
        result = ctx.step(
            f"result-{push}",
            ["systemctl", "show", "-p", "Result", "--value", push],
            always=True,
            plain=True,
        )
        if result["value"] != "success":
            raise OnboardStop(
                "onboard_push_failed",
                step=f"verify/result-{push}",
                next_command=f"journalctl -u {push} -n 50",
            )


#: The registered adapters. A Challenge joins when its producer adapter lands.
def adapters():
    battery = BatteryOnboard()
    return {battery.challenge_id: battery}


def onboard(
    challenge_id,
    inputs_path,
    state_dir,
    *,
    study=False,
    accept_code=None,
    runner=None,
    repository=REPOSITORY,
    commit=None,
    python=None,
):
    """Run every stage in order; return the public summary. Raises
    `OnboardStop` at a stop, with every completed step recorded."""
    registry = adapters()
    if challenge_id not in registry:
        raise OnboardStop("onboard_no_adapter", owner=False)
    adapter = registry[challenge_id]
    if adapter.licences:
        raise OnboardStop("onboard_needs_solver_licence:" + adapter.licences[0])
    inputs = load_inputs(inputs_path, adapter)
    commit = commit if commit is not None else current_commit(repository)
    state = State(state_dir, challenge_id, commit, accept_code=accept_code)
    summary = {"challenge_id": challenge_id, "stages": {}, "send_back": {}}
    for stage in adapter.stages(inputs, study=study):
        ctx = Context(
            state,
            stage,
            runner=runner or default_runner,
            repository=repository,
            python=python or sys.executable,
        )
        getattr(adapter, stage)(ctx, inputs)
        summary["stages"][stage] = {"ran": len(ctx.ran)}
        summary["send_back"].update(ctx.send_back)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.onboard")
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--study", action="store_true")
    parser.add_argument("--accept-code")
    args = parser.parse_args(argv)
    try:
        summary = onboard(
            args.challenge,
            args.inputs,
            args.state,
            study=args.study,
            accept_code=args.accept_code,
        )
    except OnboardStop as stop:
        print(json.dumps(stop.report(), sort_keys=True))
        return 3 if stop.owner else 2
    print(json.dumps(summary, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.challenge_validator.onboard import main as _main

    sys.exit(_main())


__all__ = ["BatteryOnboard", "OnboardStop", "adapters", "onboard"]
