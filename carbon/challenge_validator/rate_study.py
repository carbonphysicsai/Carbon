"""SUBMISSION-RATE-STUDY-01's operator-side harness (VALIDATOR-30). Operator
only: no miner surface imports it. Built to the study's consumer contract
(`docs/development/graphite/VALIDATOR_30_CONSUMER_CONTRACT.md`).

**Commands** (`python -m carbon.challenge_validator.rate_study`):
- `check --config PATH [--arm ARM]`: read-only preflight; exit 0, or exit 2
  with one line `refused: <code>` (a closed code, `REFUSALS`);
- `run --config PATH --arm H --rate {1,2,4} --replicate R`: one run;
- `fresh --config PATH --submission ID --set fresh-wNN`: the non-consuming
  fresh-set score of one retained model.

Exit codes: `0` done; `1` infrastructure, resumable by rerunning the same
command (only the missing submissions are added, with the same `t`); `2`
refused, nothing written.

**Arm H** (`run`). Per window `w` = 1 ... `W`: the run's own study producer
ticks at the window's simulated block (a short study bank makes the window's
submissions UNAVAILABLE; it is never topped up), its packages are imported
into the run's own import-only validator, and the next `3m` library entries
are submitted through the hidden route as one development hotkey at the
rule's per-hotkey spacing, on a simulated clock (no chain read). Each scored
submission is scored on window `w`'s fresh set. One record line per
submission, exactly `FIELDS` (the analysis's schema): no case, seed,
fingerprint, prediction or batch identity. `d_index = s_fresh - s_current`
(lower-is-better score: positive is better on the scored batch). A
submission the route already scored is REPEATED, its own line, never
scored. The library is cycled from position 0 when a run needs more
submissions than it holds.

`probes_batch` and `probes_case_max` count this run's own hotkey's scored
probes: how many of its submissions so far were scored on this window's
batch, and the most any one of the batch's cases has been scored on.

**Fixture mode** (`fixture: true`): an in-memory bank and a synthetic scorer
seeded by the library's public order seed, for acceptance tests only. Every
root must be under the temporary directory, and every record and manifest
says `provenance: "FIXTURE"`, which the analysis refuses as evidence.

**The non-consuming fresh scorer** (`fresh_score`): a run's retained model is
scored once on the study's sealed fresh set for window `w` (`bank-fresh-T<w>`
in the study ledger), with the validator's own metric
(`exam.evaluate`, the case store built as the validator builds its own). The
set is never consumed: every model at window `w` scores the same set, and a
repeat for one model returns its stored result. The result goes to the run's
private state only.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

FRESH_SCHEMA = "carbon.rate-study.fresh-score.v1"
FRESH_PREDICTIONS = "fresh/"


class StudyRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _private_json(path):
    if not path.exists():
        return {}
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise StudyRefused("study_file_not_owner_only")
    return json.loads(path.read_text())


def _write_private(path, value):
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
    os.replace(temporary, path)


def fresh_set(ledger, window):
    """`(case ids, inputs, references)` of the sealed fresh set for window
    index `window`. Private."""
    role = f"bank-fresh-T{int(window)}"
    rows = {r["role"]: r for r in ledger.tranches("fresh")}
    if rows.get(role, {}).get("state") != "SEALED":
        raise StudyRefused("study_fresh_set_not_sealed")
    leaves = ledger._leaves(role)
    ids = [case_id for case_id, _, _ in leaves]
    inputs = {case_id: case_inputs for case_id, case_inputs, _ in leaves}
    refs = {case_id: reference for case_id, _, reference in leaves}
    return ids, inputs, refs


def fresh_score(target, ledger, submission_id, window, state_dir):
    """The model's `s_fresh` on window `window`'s fresh set: scored once,
    stored in `state_dir/fresh-scores.json` (owner-only), never consumed."""
    from carbon.battery import exam
    from carbon.battery.worker import WorkerFailure

    from .tuning import case_store

    path = Path(state_dir) / "fresh-scores.json"
    stored = _private_json(path)
    key = f"{submission_id}/w{int(window):02d}"
    if key in stored and stored[key]["state"] != "FAILED_INFRA":
        return stored[key]
    ids, inputs, refs = fresh_set(ledger, window)
    try:
        predictions = target._quiz_predictions(
            submission_id,
            inputs,
            f"fresh-w{int(window):02d}",
            namespace=FRESH_PREDICTIONS,
        )
        _rows, aggregate = exam.evaluate(
            predictions,
            ids,
            case_store({"duplicates": []}, refs, target.repository),
        )
        found = {
            "schema": FRESH_SCHEMA,
            "state": "SCORED",
            "window": int(window),
            "s_fresh": aggregate["score"],
            "eligible": aggregate["eligible"],
        }
    except WorkerFailure as failure:
        found = {
            "schema": FRESH_SCHEMA,
            "state": "CANDIDATE_FAILED" if failure.candidate else "FAILED_INFRA",
            "window": int(window),
            "code": failure.code,
        }
    stored[key] = found
    _write_private(path, stored)
    return found


# --- the consumer contract: config, checks, arm H ---------------------------------

CONFIG_SCHEMA = "carbon.rate-study.config.v1"
STUDY = "SUBMISSION-RATE-STUDY-01"
LIBRARY_SCHEMA = "carbon.rate-study.candidate-library.v1"
#: Where a relative library path resolves (the committed libraries).
LIBRARY_DIR = Path("docs/development/evidence/submission-rate-study-01")
#: Every real root lives here (run sheet B.1). Anything else, including the
#: live producer's, the testnet deployments', EV5's, graphite-confirmation-v1's
#: and the tuning set's, is refused.
STUDY_ROOT = "/var/lib/carbon-producer/rate-study"
ROOTS = ("producer", "battery", "bank", "fresh", "runs")
RATES = (1, 2, 4)
ARMS = ("H", "S-sealed", "S-revealed")
FIELDS = (
    "arm",
    "rate",
    "replicate",
    "window",
    "t",
    "probes_batch",
    "probes_case_max",
    "d_index",
    "s_current",
    "s_fresh",
    "state",
    "wall_s",
    "provenance",
)
#: The closed set of typed refusals (exit 2).
REFUSALS = (
    "config_unreadable",
    "config_schema_mismatch",
    "rule_unknown",
    "rule_not_study_variant",
    "rule_window_blocks_mismatch",
    "library_digest_mismatch",
    "study_bank_not_sealed",
    "study_bank_wrong_size",
    "study_bank_not_sacrificial",
    "topup_not_off",
    "fresh_bank_missing",
    "fresh_bank_drawable_by_a_window",
    "clock_not_simulated",
    "production_root_refused",
    "revealed_on_non_sacrificial_bank",
    "freeze_manifest_required",
    "freeze_manifest_mismatch",
    "replicate_already_complete",
    "run_dir_not_fresh",
    "fixture_with_real_root",
    # The scripted arms' prober runner is a later slice: until it lands an
    # S arm is refused, never run on the wrong path.
    "arm_not_built",
)
REQUIRED_KEYS = frozenset(
    {
        "schema",
        "fixture",
        "roots",
        "rules",
        "library",
        "order_seed",
        "windows",
        "clock",
        "hotkey",
        "bank",
        "fresh",
        "records_dir",
    }
)
#: `producer_configs` ({"1"|"2"|"4": the rate's study producer configuration})
#: and `validator_config` (a path with `{rate}` and `{replicate}`: each run's
#: own import-only validator deployment) are required for a real run.
OPTIONAL_KEYS = frozenset({"freeze_manifest", "producer_configs", "validator_config"})
#: Simulated slots: each (arm, rate, replicate) starts at its own offset past
#: the configured start block, so no two runs share a window of the bank.
SLOT_GAP, REPLICATE_SPAN = 16, 100


class StudyInfrastructure(RuntimeError):
    """Infrastructure failed: exit 1, resumable."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(body):
    import hashlib

    return "sha256:" + hashlib.sha256(body).hexdigest()


def _hashed(value):
    """A private progress key: never the batch or case identity itself."""
    return _sha256(str(value).encode("utf-8"))[7:23]


def _under(path, directory):
    path, directory = os.path.realpath(path), os.path.realpath(directory)
    return path == directory or path.startswith(directory.rstrip(os.sep) + os.sep)


def load_config(path):
    """`(config, config_digest)`, or `StudyRefused` with a closed code."""
    try:
        raw = Path(path).read_bytes()
        config = json.loads(raw)
    except (OSError, ValueError):
        raise StudyRefused("config_unreadable") from None
    if (
        type(config) is not dict
        or config.get("schema") != CONFIG_SCHEMA
        or not REQUIRED_KEYS <= set(config) <= REQUIRED_KEYS | OPTIONAL_KEYS
        or type(config["fixture"]) is not bool
        or type(config["roots"]) is not dict
        or set(config["roots"]) != set(ROOTS)
        or any(type(v) is not str or not v for v in config["roots"].values())
        or type(config["rules"]) is not dict
        or set(config["rules"]) != {str(m) for m in RATES}
        or type(config["library"]) is not dict
        or set(config["library"]) != {"path", "digest"}
        or type(config["order_seed"]) is not str
        or type(config["windows"]) is not int
        or config["windows"] < 1
        or type(config["clock"]) is not dict
        or type(config["hotkey"]) is not str
        or not config["hotkey"]
        or type(config["bank"]) is not dict
        or type(config["fresh"]) is not dict
        or type(config["records_dir"]) is not str
    ):
        raise StudyRefused("config_schema_mismatch")
    if not config["fixture"]:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise StudyRefused("config_unreadable")
        producers = config.get("producer_configs")
        validator = config.get("validator_config")
        if (
            type(producers) is not dict
            or set(producers) != {str(m) for m in RATES}
            or type(validator) is not str
            or "{rate}" not in validator
            or "{replicate}" not in validator
        ):
            raise StudyRefused("config_schema_mismatch")
    return config, _sha256(raw)


def load_library(config, *, repository):
    """Arm H's frozen, ordered library (`scripts/dev/rate_study/library.py`),
    its digest and every entry's strategy digest re-derived. The configured
    digest pins it (a fixture may leave it unpinned). Returns `(strategies,
    library_digest)`."""
    path = Path(config["library"]["path"])
    if not path.is_absolute():
        path = Path(repository) / LIBRARY_DIR / path
    try:
        library = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise StudyRefused("library_digest_mismatch") from None
    entries = library.get("entries") if type(library) is dict else None
    if type(entries) is not list or not entries:
        raise StudyRefused("library_digest_mismatch")
    body = {k: v for k, v in library.items() if k != "library_digest"}
    digest = library.get("library_digest")
    pinned = config["library"]["digest"]
    if (
        library.get("schema") != LIBRARY_SCHEMA
        or library.get("study") != STUDY
        or library.get("arm") != "H"
        or library.get("order_seed") != config["order_seed"]
        or digest != _sha256(_canonical(body))
        or (pinned is None and not config["fixture"])
        or (pinned is not None and pinned != digest)
    ):
        raise StudyRefused("library_digest_mismatch")
    for index, entry in enumerate(entries):
        if (
            type(entry) is not dict
            or entry.get("position") != index
            or entry.get("strategy_digest")
            != _sha256(_canonical(entry.get("strategy")))
        ):
            raise StudyRefused("library_digest_mismatch")
    return [entry["strategy"] for entry in entries], digest


def _rules(config):
    from carbon.battery import exam

    found = {}
    for rate in RATES:
        name = config["rules"][str(rate)]
        rule = exam.RULES.get(name) if type(name) is str else None
        if rule is None:
            raise StudyRefused("rule_unknown")
        if rule.get("study") != STUDY:
            raise StudyRefused("rule_not_study_variant")
        spacing = rule["per_hotkey"]["window_blocks"]
        if spacing * 3 * rate != rule["rotation"]["every_blocks"]:
            raise StudyRefused("rule_window_blocks_mismatch")
        found[rate] = (name, rule)
    return found


def _check(config, arm, *, repository):
    """Every refusal a run needs before it writes anything. Returns the rules
    and the library. Raises `StudyRefused`."""
    import tempfile

    from .bank import NOT_WINDOW_DRAWABLE

    if arm not in ARMS:
        raise StudyRefused("config_schema_mismatch")
    roots = list(config["roots"].values())
    if config["fixture"]:
        temporary = tempfile.gettempdir()
        if not all(_under(r, temporary) for r in roots + [config["records_dir"]]):
            raise StudyRefused("fixture_with_real_root")
    elif not all(_under(r, STUDY_ROOT) for r in roots):
        raise StudyRefused("production_root_refused")
    clock = config["clock"]
    if clock.get("mode") != "simulated":
        raise StudyRefused("clock_not_simulated")
    if type(clock.get("start_block")) is not int or clock["start_block"] < 0:
        raise StudyRefused("config_schema_mismatch")
    rules = _rules(config)
    bank = config["bank"]
    if arm == "S-revealed" and bank.get("sacrificial") is not True:
        raise StudyRefused("revealed_on_non_sacrificial_bank")
    if arm != "H":
        if config.get("freeze_manifest") is None:
            raise StudyRefused("freeze_manifest_required")
        raise StudyRefused("arm_not_built")
    pools = [rule["bank"]["pool"] for _, rule in rules.values()]
    if bank.get("top_up") != "off" or any(
        pool.get("top_up", True) is not False for pool in pools
    ):
        raise StudyRefused("topup_not_off")
    if any(bank.get("cases") != pool["size"] for pool in pools):
        raise StudyRefused("study_bank_wrong_size")
    if bank.get("sacrificial") is not True:
        raise StudyRefused("study_bank_not_sacrificial")
    if "fresh" not in NOT_WINDOW_DRAWABLE:
        raise StudyRefused("fresh_bank_drawable_by_a_window")
    fresh_windows = config["fresh"].get("windows")
    if type(fresh_windows) is not int or fresh_windows < 1:
        raise StudyRefused("fresh_bank_missing")
    if not config["fixture"] and fresh_windows < config["windows"]:
        # A fixture's fresh sets are synthetic, so it may run past them.
        raise StudyRefused("fresh_bank_missing")
    library = load_library(config, repository=repository)
    if not config["fixture"]:
        _check_bank(config, rules, repository=repository)
    return rules, library


def _check_bank(config, rules, *, repository):
    """The real study bank: every rate's producer names it, its pool is
    sealed at the configured size, and its fresh sets are sealed."""
    from .producer import load_config as producer_config

    bank_dir = os.path.realpath(config["roots"]["bank"])
    for rate in RATES:
        sources = producer_config(config["producer_configs"][str(rate)])["sources"]
        banks = {os.path.realpath(spec.get("bank", "")) for spec in sources.values()}
        if len(sources) != 1 or banks != {bank_dir}:
            raise StudyRefused("config_schema_mismatch")
    ledger = _ledger(config, rules[1][1], repository=repository)
    pool = ledger.tranches("pool")
    if not pool or any(row["state"] != "SEALED" for row in pool):
        raise StudyRefused("study_bank_not_sealed")
    with ledger._db() as db:
        (cases,) = db.execute(
            "SELECT COUNT(*) FROM cases WHERE bank = 'pool'"
        ).fetchone()
    if cases != config["bank"]["cases"]:
        raise StudyRefused("study_bank_wrong_size")
    sealed = [row for row in ledger.tranches("fresh") if row["state"] == "SEALED"]
    if len(sealed) < config["windows"]:
        raise StudyRefused("fresh_bank_missing")


def _ledger(config, rule, *, repository):
    from .bank import BankLedger
    from .battery_bank import BatteryBankSource

    target = type("StudyRule", (), {"rule": rule, "repository": repository})()
    return BankLedger(config["roots"]["bank"], BatteryBankSource(target))


def check(config, arm="H", *, repository=None):
    """The read-only preflight: None, or the closed refusal code."""
    from .producer import REPOSITORY

    try:
        loaded, _digest = load_config(config)
        _check(loaded, arm, repository=repository or REPOSITORY)
    except StudyRefused as refused:
        return refused.code
    return None


def slot_base(config, arm, rate, replicate, every):
    """The first simulated slot of one run (each run's slots are its own)."""
    if type(replicate) is not int or not 1 <= replicate < REPLICATE_SPAN:
        raise StudyRefused("config_schema_mismatch")
    cell = ARMS.index(arm) * len(RATES) + RATES.index(rate)
    index = cell * REPLICATE_SPAN + replicate
    first = config["clock"]["start_block"] // every + 1
    return first + index * (config["windows"] + SLOT_GAP)


def _write_atomic(path, text):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.replace(temporary, path)


class FixtureWorld:
    """No bank, pool or host: a synthetic route and scorer seeded by a public
    string. For acceptance tests only; every record says FIXTURE."""

    provenance = "FIXTURE"

    def __init__(self, config):
        self.seed = config["order_seed"]
        self.config = config

    def _unit(self, *parts):
        digest = _sha256(":".join([self.seed, *map(str, parts)]).encode("utf-8"))
        return 0.1 + int(digest[7:15], 16) / 0xFFFFFFFF

    def tick(self, window, block):
        return True

    def submit(self, strategy, block, window):
        sid = _sha256(_canonical(strategy))
        return {
            "state": "SCORED",
            "submission_id": sid,
            "s_current": self._unit("current", sid, window),
            "batches": {f"w{window}": [f"w{window}-{i}" for i in range(98)]},
            "wall_s": 0.0,
        }

    def fresh(self, submission_id, window):
        score = self._unit("fresh", submission_id, window)
        return {"state": "SCORED", "s_fresh": score}

    def roots(self):
        return list(self.config["bank"].get("tranche_roots", [])), dict(
            self.config["fresh"].get("roots", {})
        )

    def close(self):
        pass


class StudyWorld:
    """The real run: its own producer directory on the rate's study producer
    configuration and the shared study bank, and its own validator."""

    provenance = "STUDY"

    def __init__(self, config, rate, replicate, run_dir, *, repository):
        from . import producer as producers
        from .answer_key import ProducerKey
        from .battery import BatteryAdapter
        from .battery_bank import BankedBatterySource

        settings = producers.load_config(config["producer_configs"][str(rate)])
        self.lock = producers.exclusive(run_dir / "producer")
        try:
            sources = [
                producers.source_for(challenge_id, spec, repository=repository)
                for challenge_id, spec in sorted(settings["sources"].items())
            ]
            if len(sources) != 1 or not isinstance(sources[0], BankedBatterySource):
                raise StudyRefused("config_schema_mismatch")
            if settings.get("signing_key") is None:
                raise StudyRefused("config_schema_mismatch")
            key = ProducerKey.load(settings["signing_key"])
            self.source = sources[0]
            self.producer = producers.Producer(
                run_dir / "producer",
                sources,
                signing_key=key,
                quiz=settings.get("quiz"),
            )
            self.public_key = key.public_key
            self.adapter = BatteryAdapter.from_deployment(
                config["validator_config"].format(rate=rate, replicate=replicate),
                repository=repository,
            )
            if self.adapter.target.rule != self.source.adapter.target.rule:
                raise StudyRefused("rule_window_blocks_mismatch")
        except BaseException:
            os.close(self.lock)
            raise
        self.target = self.adapter.target
        self.run_id = f"{config['hotkey']}-m{rate}-r{replicate}"
        self.run_dir = run_dir

    def tick(self, window, block):
        from . import answer_key
        from .batch_source import ProducerRefused

        try:
            self.producer.tick(block)
        except ProducerRefused as refused:
            if refused.code == "producer_bank_short":
                return False
            raise StudyInfrastructure(refused.code) from None
        outbox = self.producer.directory / "outbox" / self.source.challenge_id
        if outbox.is_dir():
            answer_key.import_local(self.adapter, self.public_key, outbox)
        return True

    def submit(self, strategy, block, window):
        import time

        from carbon.agent_campaign.graphite import hidden_score

        pool = hidden_score.HiddenPool(
            self.target, run_id=self.run_id, clock=lambda: block
        )
        started = time.monotonic()
        view, operator = pool.submit("proposal", strategy)
        wall = round(time.monotonic() - started, 3)
        state = view["state"]
        if state == "NOT_SCORED":
            outcome = view.get("outcome") or {}
            if outcome.get("state") == "FAILED_INFRA":
                raise StudyInfrastructure("route_failed_infra")
            return {"state": "NOT_SCORED", "wall_s": wall}
        if state != "SCORED" or operator is None or "aggregate" not in operator:
            if state not in ("UNAVAILABLE", "WINDOW_USED"):
                state = "NOT_SCORED"
            return {"state": state, "wall_s": wall}
        batches = {}
        for fingerprint in operator["active_batches"]:
            document = self.target.store.batch(fingerprint)["document"]
            twins = {twin for twin, _ in document.get("duplicates", [])}
            batches[fingerprint] = [
                c["case_id"] for c in document["cases"] if c["case_id"] not in twins
            ]
        return {
            "state": "SCORED",
            "submission_id": operator["submission_id"],
            "s_current": operator["aggregate"].get("score"),
            "batches": batches,
            "wall_s": wall,
        }

    def fresh(self, submission_id, window):
        found = fresh_score(
            self.target, self.source.ledger, submission_id, window, self.run_dir
        )
        if found["state"] == "FAILED_INFRA":
            raise StudyInfrastructure("fresh_failed_infra")
        return {"state": found["state"], "s_fresh": found.get("s_fresh")}

    def roots(self):
        ledger = self.source.ledger
        return (
            [row["root"] for row in ledger.tranches("pool")],
            {row["role"]: row["root"] for row in ledger.tranches("fresh")},
        )

    def close(self):
        os.close(self.lock)


def _git_sha(repository):
    import subprocess

    try:
        found = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return found.stdout.strip() or None


def _record(progress_line, arm, rate, replicate, provenance):
    """One record line: exactly `FIELDS`, the missing numbers null."""
    fixed = {"arm": arm, "rate": rate, "replicate": replicate}
    fixed["provenance"] = provenance
    return {k: fixed[k] if k in fixed else progress_line.get(k) for k in FIELDS}


def _probe(progress, batches):
    """Count one scored probe of each active batch and each of its distinct
    cases (keyed by a hash, never the identity). Returns `(probes_batch,
    probes_case_max)`."""
    probed, cases = [], set()
    for batch, members in batches.items():
        key = _hashed(batch)
        progress["batch"][key] = progress["batch"].get(key, 0) + 1
        probed.append(progress["batch"][key])
        cases.update(_hashed(case) for case in members)
    for case in cases:
        progress["case"][case] = progress["case"].get(case, 0) + 1
    most = max((progress["case"][case] for case in cases), default=0)
    return max(probed, default=0), most


def _counts(lines):
    states = ("scored", "unavailable", "window_used", "repeated", "not_scored")
    counts = dict.fromkeys(states, 0)
    for line in lines:
        counts[line["state"].lower()] += 1
    return counts


def run(config, arm, rate, replicate, *, prober=None, repository=None, world=None):
    """One run: arm, rate, replicate. Returns the exit code and prints one
    line (`refused: <code>`, the counts, or `failed: <code>`)."""
    from .producer import REPOSITORY

    repository = repository or REPOSITORY
    try:
        loaded, config_digest = load_config(config)
        if rate not in RATES:
            raise StudyRefused("config_schema_mismatch")
        rules, (library, library_digest) = _check(loaded, arm, repository=repository)
        rule_name, rule = rules[rate]
        every = rule["rotation"]["every_blocks"]
        base = slot_base(loaded, arm, rate, replicate, every)
        run_dir = Path(loaded["roots"]["runs"]) / arm / f"m{rate}-r{replicate}"
        progress_path = run_dir / "progress.json"
        progress = None
        if progress_path.exists():
            progress = json.loads(progress_path.read_text())
            if progress.get("config_digest") != config_digest:
                raise StudyRefused("run_dir_not_fresh")
            if len(progress["lines"]) == loaded["windows"] * 3 * rate:
                raise StudyRefused("replicate_already_complete")
        elif run_dir.exists() and {p.name for p in run_dir.iterdir()} - {"producer"}:
            # The run's own producer directory (idempotent ticks) may predate
            # its first progress entry; anything else is another run's.
            raise StudyRefused("run_dir_not_fresh")
        run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if world is None:
            world = (
                FixtureWorld(loaded)
                if loaded["fixture"]
                else StudyWorld(loaded, rate, replicate, run_dir, repository=repository)
            )
    except StudyRefused as refused:
        print(f"refused: {refused.code}")
        return 2
    except Exception as failure:  # noqa: BLE001 - infrastructure: exit 1, rerun
        print(f"failed: study_infrastructure {type(failure).__name__}")
        return 1
    spacing = rule["per_hotkey"]["window_blocks"]
    per_window = 3 * rate
    progress = progress or {
        "config_digest": config_digest,
        "lines": [],
        "ticked": {},
        "seen": [],
        "batch": {},
        "case": {},
    }
    stem = Path(loaded["records_dir"]) / arm / str(rate) / str(replicate)

    def save():
        _write_atomic(progress_path, json.dumps(progress, sort_keys=True))

    def publish():
        lines = progress["lines"]
        text = ""
        for line in lines:
            record = _record(line, arm, rate, replicate, world.provenance)
            text += json.dumps(record, sort_keys=True) + "\n"
        _write_atomic(stem.with_suffix(".jsonl"), text)
        from carbon.battery.daemon import rule_digest

        tranche_roots, fresh_roots = world.roots()
        _write_atomic(
            stem.with_suffix(".manifest.json"),
            json.dumps(
                {
                    "rule": rule_name,
                    "rule_digest": rule_digest(rule),
                    "library_digest": library_digest,
                    "bank_tranche_roots": tranche_roots,
                    "fresh_roots": fresh_roots,
                    "clock_start_block": loaded["clock"]["start_block"],
                    "counts": _counts(lines),
                    "git_sha": _git_sha(repository),
                    "config_digest": config_digest,
                    "provenance": world.provenance,
                },
                sort_keys=True,
            ),
        )

    try:
        seen = set(progress["seen"])
        total = loaded["windows"] * per_window
        for k in range(len(progress["lines"]), total):
            window, j = k // per_window + 1, k % per_window
            slot = base + window
            line = {"t": k + 1, "window": window}
            if str(window) not in progress["ticked"]:
                ticked = world.tick(window, (slot - 1) * every + 1)
                progress["ticked"][str(window)] = ticked
                save()
            if not progress["ticked"][str(window)]:
                progress["lines"].append({**line, "state": "UNAVAILABLE"})
                save()
                continue
            strategy = library[k % len(library)]
            found = world.submit(strategy, slot * every + j * spacing + 5, window)
            line["wall_s"] = found.get("wall_s")
            sid = found.get("submission_id")
            if found["state"] != "SCORED":
                line["state"] = found["state"]
            elif sid in seen:
                line["state"] = "REPEATED"
            elif found["s_current"] is None:
                line["state"] = "NOT_SCORED"
            else:
                rescored = world.fresh(sid, window)
                if rescored["state"] != "SCORED" or rescored["s_fresh"] is None:
                    line["state"] = "NOT_SCORED"
                else:
                    seen.add(sid)
                    progress["seen"] = sorted(seen)
                    probes_batch, probes_case_max = _probe(progress, found["batches"])
                    line.update(
                        state="SCORED",
                        s_current=found["s_current"],
                        s_fresh=rescored["s_fresh"],
                        d_index=rescored["s_fresh"] - found["s_current"],
                        probes_batch=probes_batch,
                        probes_case_max=probes_case_max,
                    )
            progress["lines"].append(line)
            save()
            if (k + 1) % per_window == 0:
                publish()
        publish()
    except StudyInfrastructure as failure:
        publish()
        print(f"failed: {failure}")
        return 1
    except Exception as failure:  # noqa: BLE001 - infrastructure: exit 1, rerun
        print(f"failed: study_infrastructure {type(failure).__name__}")
        return 1
    finally:
        world.close()
    print(json.dumps(_counts(progress["lines"]), sort_keys=True))
    return 0


def fresh(config, submission, set_id, *, rate=None, replicate=None, repository=None):
    """The `fresh` command: one model's non-consuming score on a sealed fresh
    set. Prints `{"state", "s_fresh"}` and nothing else; returns the exit
    code."""
    import re

    from .producer import REPOSITORY

    repository = repository or REPOSITORY
    world = None
    try:
        loaded, _digest = load_config(config)
        _check(loaded, "H", repository=repository)
        match = re.fullmatch(r"fresh-w(\d{2})", set_id or "")
        if match is None or type(submission) is not str or not submission:
            raise StudyRefused("config_schema_mismatch")
        window = int(match.group(1))
        if not 1 <= window <= loaded["fresh"]["windows"]:
            raise StudyRefused("fresh_bank_missing")
        if loaded["fixture"]:
            state = Path(loaded["roots"]["fresh"]) / "fixture-scores.json"
            state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            stored = _private_json(state)
            key = f"{submission}/w{window:02d}"
            if key not in stored:
                stored[key] = FixtureWorld(loaded).fresh(submission, window)
                _write_private(state, stored)
            found = stored[key]
        else:
            if rate not in RATES or replicate is None:
                raise StudyRefused("config_schema_mismatch")
            run_dir = Path(loaded["roots"]["runs"]) / "H" / f"m{rate}-r{replicate}"
            world = StudyWorld(loaded, rate, replicate, run_dir, repository=repository)
            found = world.fresh(submission, window)
    except StudyRefused as refused:
        print(f"refused: {refused.code}")
        return 2
    except Exception as failure:  # noqa: BLE001 - infrastructure: exit 1, rerun
        print(f"failed: study_infrastructure {type(failure).__name__}")
        return 1
    finally:
        if world is not None:
            world.close()
    print(json.dumps({"state": found["state"], "s_fresh": found.get("s_fresh")}))
    return 0


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.rate_study")
    sub = parser.add_subparsers(dest="command", required=True)
    checking = sub.add_parser("check")
    checking.add_argument("--config", required=True)
    checking.add_argument("--arm", default="H", choices=ARMS)
    running = sub.add_parser("run")
    running.add_argument("--config", required=True)
    running.add_argument("--arm", required=True, choices=ARMS)
    running.add_argument("--rate", required=True, type=int, choices=RATES)
    running.add_argument("--replicate", required=True, type=int)
    running.add_argument("--prober")
    scoring = sub.add_parser("fresh")
    scoring.add_argument("--config", required=True)
    scoring.add_argument("--submission", required=True)
    scoring.add_argument("--set", required=True, dest="set_id")
    scoring.add_argument("--rate", type=int, choices=RATES)
    scoring.add_argument("--replicate", type=int)
    args = parser.parse_args(argv)
    if args.command == "check":
        code = check(args.config, args.arm)
        print("ok" if code is None else f"refused: {code}")
        return 0 if code is None else 2
    if args.command == "run":
        return run(args.config, args.arm, args.rate, args.replicate, prober=args.prober)
    return fresh(
        args.config,
        args.submission,
        args.set_id,
        rate=args.rate,
        replicate=args.replicate,
    )


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.challenge_validator.rate_study import main as _main

    sys.exit(_main())


__all__ = [
    "REFUSALS",
    "StudyRefused",
    "check",
    "fresh",
    "fresh_score",
    "fresh_set",
    "load_config",
    "load_library",
    "main",
    "run",
]
