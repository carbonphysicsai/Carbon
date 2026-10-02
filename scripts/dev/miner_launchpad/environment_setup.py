"""Set up a registered miner's environment on their own machine (C-MLP-03).

OWNER-MINER-ENVIRONMENT-01: once the onboarding door confirms the hotkey is
registered, the Control Center takes the miner through one setup - inference,
compute, agent, review - and writes their runner profile itself. Carbon hosts
nothing: every account, key and bill is the miner's.

**Keys stay on this machine.** An inference API key is entered once on the
loopback page and written here to an owner-only file in an owner-only
directory. The profile references it by path. It is never logged, never
returned, and sent only to its own provider.

**Carbon never holds the miner's hotkey** (external signing, #445). The miner
runs `carbon-miner-signer` for their registered hotkey in their own terminal;
the Agent step only asks it, through `carbon.chain.external_signer`, which
hotkey it holds. No hotkey file path and no password is asked for, stored or
written into the profile.

**Every connection is checked live, at the miner's cost, with consent.** A
check that spends runs only on consent to a stated amount: `quote` gives the
check's maximum cost for the chosen model, and the check refuses unless its
`consent` names that same maximum. A bare `true` is not consent - it says
nothing about what was agreed to - so a client that defaults it on spends
nothing.

**Refusals name the field** they are about, so the page can point at it.

Only launchable choices are offered. Inference (slice 2) offers every provider
adapter: Engy's Chat Completions route first, Chutes with the prices it
publishes, the fixed OpenAI and Anthropic APIs, and the generic OpenAI-shaped
adapters with the miner's own endpoint and, optionally, their declared price.
Rented GPUs and other agents are later slices (3 to 5); until each lands, the
research environment standard names it as a Gap rather than this page offering
something that would not run.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from carbon.development_session.profile import canonical
from scripts.dev.miner_launchpad.controller import Rejected

SETUP_SCHEMA = "carbon.launchpad.environment-setup.v1"
STEPS = ("inference", "compute", "agent", "review")
PROFILE_ID = "miner-environment"
REPO = Path(__file__).resolve().parents[3]

#: The only compute this slice can launch: the miner's own machine, CPU.
LOCAL_CPU = "this-machine-cpu"
#: The only agent this slice can launch: Carbon's autonomous battery agent,
#: running in this controller's process on this machine.
AUTONOMOUS = "carbon-autonomous"

#: The order inference choices are offered in; the first is the default
#: (Engy's Chat Completions route, C-MLP-03 slice 2).
INFERENCE_ORDER = (
    "engy-chat",
    "chutes",
    "engy-anthropic",
    "openai-responses",
    "anthropic",
    "openai-compatible-chat",
    "openai-compatible-responses",
)

#: Where a provider lists its models for a key holder. Engy publishes its list
#: without a key (`models_url`); these need the miner's key. Provider facts,
#: read 2026-09-30.
KEYED_MODEL_LISTS = {
    "openai-responses": "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
}

#: How to produce each image the compute step verifies, named in its refusal.
BUILD_STEPS = {
    "image_manifest": (
        "Build the trusted worker from this exact clean checkout: "
        "./scripts/dev/c03_worker_image.sh"
    ),
    "analysis_image_manifest": (
        "Build the analysis image on that worker: python -m "
        "carbon.development_session.research_image --parent-manifest "
        "<worker manifest> --root <directory>"
    ),
}

#: The inference check: one short completion. Its quoted maximum is Carbon's
#: own reservation bound for one request at these settings (the provider's
#: price times the whole input and output ceiling), never a guess.
CHECK_SETTINGS = {
    "max_input_tokens": 16384,
    "max_output_tokens": 256,
    "reasoning_effort": None,
}

_SECRET = re.compile(r"[\x21-\x7e]{1,1024}")
_ADDRESS = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")


#: What a miner does when the Agent step cannot reach their signer.
SIGNER_STEP = "start `carbon-miner-signer` for your registered hotkey"


class SetupRefused(Rejected):
    """A refusal about one field of the setup request."""

    def __init__(self, field: str, code: str, status: int = 409, next_step=None):
        super().__init__(code, status)
        self.field = field
        self.next_step = next_step


def _owner_only(path: Path) -> bool:
    stat = path.lstat()
    return (
        not path.is_symlink()
        and stat.st_uid == os.getuid()
        and not (stat.st_mode & 0o077)
    )


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    if not path.is_dir() or not _owner_only(path):
        raise SetupRefused("state_dir", "setup_directory_not_owner_only", 503)
    return path


def write_private(path: Path, data: bytes) -> Path:
    """Write `data` to an owner-only file, atomically, never through a link."""
    _private_dir(path.parent)
    temporary = path.with_name("." + path.name + ".tmp")
    if temporary.is_symlink() or temporary.exists():
        temporary.unlink()
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    return path


def _secret(value, field):
    if type(value) is not str or not _SECRET.fullmatch(value):
        raise SetupRefused(field, "secret_must_be_one_line_of_printable_text")
    return value.encode()


def _absolute(value, field):
    if type(value) is not str or not 1 <= len(value) <= 4096:
        raise SetupRefused(field, "absolute_path_required")
    path = Path(value)
    if not path.is_absolute():
        raise SetupRefused(field, "absolute_path_required")
    return path


def _consented(value, quote):
    """Consent is to the quoted maximum, and only to it."""
    consent = value.get("consent")
    if type(consent) is not dict or set(consent) != {"max_cost_nano"}:
        raise SetupRefused("consent", "live_check_needs_consent")
    agreed = consent["max_cost_nano"]
    if (agreed is not None and type(agreed) is not int) or (
        agreed != quote["max_cost_nano"]
    ):
        raise SetupRefused("consent", "consent_does_not_match_quoted_cost")


def check_quote(provider_id, model_id, credential_file: Path, spec=None) -> dict:
    """What the inference check can cost at most, before it runs.

    Reads no key: the selection only records where the key file is. `spec`
    carries a generic adapter's `endpoint`, the miner's `declared_pricing` or
    a live-priced provider's `published_pricing`.
    """
    from carbon.development_session.model_provider import (
        ADAPTERS,
        UNKNOWN_SPEND,
        ModelSelectionRefused,
        select,
    )

    try:
        selection = select(
            provider_id=provider_id,
            model_id=model_id,
            credential={"kind": "file", "reference": str(credential_file)},
            settings=CHECK_SETTINGS,
            **(spec or {}),
        )
    except ModelSelectionRefused:
        field = (
            "endpoint"
            if spec and "endpoint" in spec and ADAPTERS[provider_id].endpoint is None
            else "model_id"
        )
        raise SetupRefused(field, "model_selection_refused") from None
    bound = selection.reservation_nano
    name = ADAPTERS[provider_id].display_name
    if bound is None:
        statement = (
            "One short completion, billed by " + name + " to your account. "
            "Maximum " + UNKNOWN_SPEND
        )
    else:
        statement = (
            "One short completion, billed by " + name + " to your account: at "
            "most $"
            + format(bound / 1e9, ".6f")
            + " (up to "
            + format(CHECK_SETTINGS["max_input_tokens"], ",")
            + " input and "
            + format(CHECK_SETTINGS["max_output_tokens"], ",")
            + " output "
            "tokens at "
            + selection.pricing.source.replace("_", " ")
            + " pricing). Listing the models is free."
        )
    return {
        "provider_id": provider_id,
        "model_id": model_id,
        "max_cost_nano": bound,
        "statement": statement,
    }


def _closed(value, required, optional=frozenset()):
    if type(value) is not dict:
        raise SetupRefused("request", "closed_setup_request_required")
    missing = sorted(required - set(value))
    if missing:
        raise SetupRefused(missing[0], "field_required")
    extra = sorted(set(value) - required - optional)
    if extra:
        raise SetupRefused(extra[0], "unknown_field")


def choices() -> dict:
    """What each step offers: only what launches today, each with its cost."""
    from carbon.development_session.model_provider import ADAPTERS

    inference = []
    for adapter in sorted(
        ADAPTERS.values(), key=lambda a: INFERENCE_ORDER.index(a.adapter_id)
    ):
        inference.append(
            {
                "id": adapter.adapter_id,
                "display_name": adapter.display_name,
                "default": adapter.adapter_id == INFERENCE_ORDER[0],
                "models": adapter.summary_models(),
                "model_policy": (
                    "only the listed models"
                    if adapter.allowed_models is not None
                    else "any model id this provider serves; type it"
                ),
                "needs_endpoint": adapter.endpoint is None,
                "pricing": (
                    "listed"
                    if adapter.priced_models
                    else (
                        "published live by the provider"
                        if adapter.live_pricing
                        else (
                            "yours to declare (optional)"
                            if adapter.endpoint is None
                            else "not listed"
                        )
                    )
                ),
                "cost_basis": (
                    "Per token at "
                    + adapter.display_name
                    + "'s price, billed by it to your account; settled from "
                    + (adapter.reported_charge or "metered usage")
                    + ". Carbon bills nothing."
                ),
                "live_check": (
                    "Lists the models (free) and runs one short completion "
                    "with your key, billed to you. Its maximum cost for your "
                    "model is quoted before you agree, and it runs only on "
                    "that agreement."
                ),
            }
        )
    return {
        "schema": SETUP_SCHEMA,
        "inference": inference,
        "compute": [
            {
                "id": LOCAL_CPU,
                "display_name": "This machine (CPU)",
                "cost_basis": "Your own machine: nothing is rented or billed.",
                "live_check": (
                    "Reads this checkout's revision and verifies your locally "
                    "built worker and analysis images. No network, no cost."
                ),
            }
        ],
        "agent": [
            {
                "id": AUTONOMOUS,
                "display_name": "Carbon's autonomous battery agent",
                "cost_basis": (
                    "Runs on this machine. It spends only through your "
                    "inference choice, within the finite ceilings you set at "
                    "launch."
                ),
                "live_check": (
                    "Asks your running carbon-miner-signer which hotkey it "
                    "holds and checks it is the registered one. Carbon never "
                    "sees your key or password. No network, no cost."
                ),
            }
        ],
        "not_yet_offered": (
            "Rented GPUs, your own GPU, other inference providers and other "
            "agents arrive in later C-MLP-03 slices; the research environment "
            "standard names each as a Gap until then."
        ),
    }


class LiveChecks:
    """The live checks, each against the miner's own accounts and files.

    `opener` replaces urllib's for fixture tests; Carbon's tests never reach a
    provider. Each check returns public facts only, never a key or a path.
    """

    def __init__(self, *, opener=None, repo: Path = REPO):
        self.opener = opener
        self.repo = repo

    def published_pricing(self, provider_id, model_id) -> dict:
        """The live-priced provider's published price for `model_id` (free,
        no key). Refused by field when the provider does not price it."""
        from carbon.development_session.model_provider import (
            ProviderHTTPError,
            published_pricing,
        )

        try:
            return published_pricing(provider_id, model_id, opener=self.opener)
        except ProviderHTTPError:
            raise SetupRefused(
                "provider_id", "provider_model_list_unavailable"
            ) from None
        except OSError:
            raise SetupRefused(
                "provider_id", "provider_model_list_unavailable"
            ) from None
        except ValueError:
            raise SetupRefused("model_id", "model_not_priced_by_provider") from None

    def inference(
        self, provider_id, model_id, credential_file: Path, spec=None
    ) -> dict:
        from carbon.development_session.model_provider import (
            ADAPTERS,
            ModelSelectionRefused,
            ProviderHTTPError,
            SelectionTransport,
            fetch_models,
            select,
        )

        adapter = ADAPTERS[provider_id]
        try:
            if adapter.models_url is not None:
                listed = fetch_models(provider_id, opener=self.opener)
                source, models = listed["source"], listed["models"]
            elif provider_id in KEYED_MODEL_LISTS:
                source = KEYED_MODEL_LISTS[provider_id]
                models = self._keyed_models(adapter, source, credential_file)
            else:
                # A generic adapter's endpoint lists nothing Carbon can rely
                # on; the completion below is the check.
                source, models = None, None
        except ProviderHTTPError as refused:
            field = "key" if refused.status in (401, 403) else "provider_id"
            raise SetupRefused(field, "provider_refused_model_list") from None
        except (OSError, ValueError, KeyError):
            raise SetupRefused(
                "provider_id", "provider_model_list_unavailable"
            ) from None
        if models is not None and model_id not in models:
            raise SetupRefused("model_id", "model_not_listed_by_provider")
        try:
            selection = select(
                provider_id=provider_id,
                model_id=model_id,
                credential={"kind": "file", "reference": str(credential_file)},
                settings=CHECK_SETTINGS,
                **(spec or {}),
            )
            reply = SelectionTransport(selection, opener=self.opener)(
                {
                    "model": model_id,
                    "instructions": "Answer with one word.",
                    "input": [{"role": "user", "content": "Reply with: ready"}],
                    "tools": [],
                    "parallel_tool_calls": False,
                    "store": False,
                    "max_output_tokens": CHECK_SETTINGS["max_output_tokens"],
                    "reasoning": None,
                }
            )
        except ModelSelectionRefused:
            raise SetupRefused("model_id", "model_selection_refused") from None
        except ProviderHTTPError as refused:
            field = "key" if refused.status in (401, 403) else "model_id"
            raise SetupRefused(field, "provider_refused_completion") from None
        except (OSError, ValueError):
            raise SetupRefused("provider_id", "provider_completion_failed") from None
        if type(reply) is not dict or type(reply.get("output")) is not list:
            raise SetupRefused("provider_id", "provider_completion_failed")
        return {
            "models_source": source or "not listed: any model id",
            "models_listed": None if models is None else len(models),
            "completion": "answered",
            "usage": reply.get("usage") if type(reply.get("usage")) is dict else None,
        }

    def _keyed_models(self, adapter, url, credential_file: Path):
        import urllib.request

        from carbon.development_session.model_provider import (
            ANTHROPIC_VERSION,
            ProviderHTTPError,
            _NoRedirect,
            read_credential,
        )
        from carbon.development_session.model_provider import (
            CredentialReference as Reference,
        )

        headers = {}
        key = read_credential(Reference("file", str(credential_file)))
        if adapter.auth == "x-api-key":
            headers["x-api-key"] = key
            headers["anthropic-version"] = ANTHROPIC_VERSION
        else:
            headers["Authorization"] = "Bearer " + key
        del key
        request = urllib.request.Request(url, headers=headers, method="GET")
        del headers
        opener = self.opener or urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(request, timeout=30) as response:
                payload = response.read(2 * 1024**2 + 1)
        except urllib.error.HTTPError as rejected:
            raise ProviderHTTPError(rejected.code) from None
        finally:
            del request
        if len(payload) > 2 * 1024**2:
            raise ValueError("model list exceeds bound")
        items = json.loads(payload).get("data")
        if type(items) is not list:
            raise ValueError("model list malformed")
        return sorted(
            item["id"]
            for item in items
            if type(item) is dict and type(item.get("id")) is str
        )

    def revision(self) -> dict:
        """This checkout's exact clean accepted revision and its source digest."""
        from carbon.development_session.research_campaign import (
            accepted_implementation,
        )

        try:
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True, timeout=30
            ).strip()
            return accepted_implementation(head)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise SetupRefused(
                "accepted_revision", "clean_accepted_checkout_required"
            ) from None

    def compute(self, image_manifest: Path, analysis_manifest: Path) -> dict:
        from carbon.development_session.research_campaign import verify_current_worker
        from carbon.development_session.research_image import (
            load_analysis_image,
            verify_image,
        )
        from carbon.reconstruction.worker.docker_runtime import (
            doctor,
            load_image_identity,
        )

        implementation = self.revision()
        try:
            image = load_image_identity(image_manifest)
            verify_current_worker(image, implementation)
            if not doctor(image_id=image.image_id, image_identity=image).eligible:
                raise ValueError("host not eligible")
        except Exception:  # noqa: BLE001 - never echo a local path or error.
            raise SetupRefused("image_manifest", "worker_image_unverified") from None
        try:
            analysis = load_analysis_image(analysis_manifest)
            verify_image(analysis)
            if analysis.parent_image != image.image_id:
                raise ValueError("analysis parent differs")
        except Exception:  # noqa: BLE001
            raise SetupRefused(
                "analysis_image_manifest", "analysis_image_unverified"
            ) from None
        return {
            "implementation": implementation,
            "images": [image.image_id, analysis.image_id],
        }

    def agent(self, hotkey: str, socket_path: Path | None = None) -> dict:
        from carbon.chain.external_signer import SignerFailure, connect_signer

        try:
            connect_signer(hotkey, socket_path=socket_path)
        except SignerFailure as failure:
            raise SetupRefused("signer", failure.code, next_step=SIGNER_STEP) from None
        return {"signing": "carbon-miner-signer holds the registered hotkey"}

    @staticmethod
    def operator_config(path: Path) -> None:
        from carbon.chain.models import CARBON_NETUID
        from carbon.development_testnet.operator import load_config

        try:
            config = load_config(path)
        except Exception:  # noqa: BLE001 - content stays private.
            raise SetupRefused("operator_config", "operator_config_invalid") from None
        if config.netuid != CARBON_NETUID:
            raise SetupRefused("operator_config", "operator_config_not_subnet_567")


class EnvironmentSetup:
    """One miner's setup, kept under the controller's owner-only state dir.

    `onboarding` is the controller's onboarding door: setup begins only when
    its `confirm` reads the hotkey as registered. `attach` is called with the
    written profile's path so the controller loads it without a restart.
    """

    def __init__(self, state_dir: Path, *, onboarding, checks=None, attach=None):
        self.root = Path(state_dir) / "environment"
        self.onboarding = onboarding
        self.checks = checks or LiveChecks()
        self.attach = attach
        self.lock = threading.Lock()

    # -- storage

    @property
    def record_path(self) -> Path:
        return self.root / "setup.json"

    @property
    def profile_path(self) -> Path:
        return self.root / "runner-profile.json"

    def _record(self) -> dict:
        path = self.record_path
        if not path.exists():
            return {}
        if not _owner_only(path) or path.stat().st_size > 64 * 1024:
            raise SetupRefused("state_dir", "setup_record_not_owner_only", 503)
        return json.loads(path.read_bytes())

    def _save(self, record: dict) -> None:
        write_private(self.record_path, canonical(record))

    def _step(self, name: str, value: dict) -> dict:
        record = self._record()
        if "hotkey" not in record:
            raise SetupRefused("address", "registration_not_confirmed")
        record[name] = {**value, "checked_at": int(time.time())}
        record.pop("profile", None)  # Any change needs a new review.
        self._save(record)
        return self.state()

    # -- the steps

    def state(self) -> dict:
        record = self._record()
        done = {name: name in record for name in STEPS[:-1]}
        return {
            "schema": SETUP_SCHEMA,
            "registered_hotkey": record.get("hotkey"),
            "steps": {
                "inference": _public(
                    record.get("inference"),
                    (
                        "provider_id",
                        "model_id",
                        "endpoint",
                        "declared_pricing",
                        "published_pricing",
                        "check",
                    ),
                ),
                "compute": _public(record.get("compute"), ("choice", "check")),
                "agent": _public(record.get("agent"), ("choice", "check")),
                "review": {
                    "ready": "hotkey" in record and all(done.values()),
                    "profile_written": "profile" in record,
                },
            },
        }

    def begin(self, value) -> dict:
        """Start setup for a hotkey the chain reads as registered."""
        from carbon.development_session.chain_onboarding import OnboardingFailure

        _closed(value, {"address"})
        address = value["address"]
        if type(address) is not str or not _ADDRESS.fullmatch(address):
            raise SetupRefused("address", "hotkey_address_required")
        try:
            confirmed = self.onboarding.confirm(address)
        except OnboardingFailure:
            raise SetupRefused("address", "registration_unreadable") from None
        if not confirmed.get("registered") or not confirmed.get("confirmed"):
            raise SetupRefused("address", "hotkey_not_registered")
        with self.lock:
            record = self._record()
            if record.get("hotkey") not in (None, address):
                record = {}  # A different miner starts over.
            record["hotkey"] = address
            self._save(record)
        return self.state()

    def _inference_choice(self, value) -> str:
        from carbon.development_session.model_provider import ADAPTERS

        provider = value["provider_id"]
        if provider not in {c["id"] for c in choices()["inference"]}:
            raise SetupRefused("provider_id", "provider_not_offered")
        if type(value["model_id"]) is not str or not 1 <= len(value["model_id"]) <= 128:
            raise SetupRefused("model_id", "model_id_required")
        adapter = ADAPTERS[provider]
        if (
            adapter.allowed_models is not None
            and value["model_id"] not in adapter.allowed_models
        ):
            raise SetupRefused("model_id", "model_not_offered_for_provider")
        if adapter.endpoint is None and "endpoint" not in value:
            raise SetupRefused("endpoint", "field_required")
        if adapter.endpoint is not None and "endpoint" in value:
            raise SetupRefused("endpoint", "endpoint_is_fixed_for_provider")
        if "declared_pricing" in value and (adapter.endpoint is not None):
            raise SetupRefused("declared_pricing", "price_is_the_providers")
        return provider

    def _spec(self, provider, value) -> dict:
        """The pricing and endpoint a selection for this choice carries."""
        from carbon.development_session.model_provider import ADAPTERS

        spec = {k: value[k] for k in ("endpoint", "declared_pricing") if k in value}
        if ADAPTERS[provider].live_pricing:
            spec["published_pricing"] = self.checks.published_pricing(
                provider, value["model_id"]
            )
        return spec

    def quote(self, value) -> dict:
        """The inference check's maximum cost for this provider and model."""
        _closed(value, {"provider_id", "model_id"}, {"endpoint", "declared_pricing"})
        provider = self._inference_choice(value)
        credential_file = self.root / "keys" / (provider + ".key")
        return check_quote(
            provider, value["model_id"], credential_file, self._spec(provider, value)
        )

    def inference(self, value) -> dict:
        _closed(
            value,
            {"provider_id", "model_id", "consent"},
            {"key", "endpoint", "declared_pricing"},
        )
        provider = self._inference_choice(value)
        credential_file = self.root / "keys" / (provider + ".key")
        spec = self._spec(provider, value)
        _consented(
            value, check_quote(provider, value["model_id"], credential_file, spec)
        )
        with self.lock:
            if "hotkey" not in self._record():
                raise SetupRefused("address", "registration_not_confirmed")
            if "key" in value:
                write_private(credential_file, _secret(value["key"], "key"))
            elif not credential_file.exists():
                raise SetupRefused("key", "field_required")
            check = self.checks.inference(
                provider, value["model_id"], credential_file, spec
            )
            return self._step(
                "inference",
                {
                    "provider_id": provider,
                    "model_id": value["model_id"],
                    **spec,
                    "check": check,
                },
            )

    def compute(self, value) -> dict:
        _closed(value, {"choice", "image_manifest", "analysis_image_manifest"})
        if value["choice"] != LOCAL_CPU:
            raise SetupRefused("choice", "compute_not_offered")
        paths = {}
        for field in ("image_manifest", "analysis_image_manifest"):
            path = _absolute(value[field], field)
            if not path.is_file() or path.is_symlink():
                raise SetupRefused(
                    field, "image_not_built", next_step=BUILD_STEPS[field]
                )
            paths[field] = str(path)
        with self.lock:
            runtime = self.checks.compute(
                Path(paths["image_manifest"]), Path(paths["analysis_image_manifest"])
            )
            return self._step(
                "compute",
                {
                    "choice": LOCAL_CPU,
                    "paths": paths,
                    "runtime": runtime,
                    "check": {
                        "revision": runtime["implementation"]["revision"],
                        "images": runtime["images"],
                        "balance": "not applicable: your own machine",
                    },
                },
            )

    def agent(self, value) -> dict:
        from carbon.chain.models import CARBON_NETUID

        _closed(value, {"choice", "operator_config"}, {"signer_socket"})
        if value["choice"] != AUTONOMOUS:
            raise SetupRefused("choice", "agent_not_offered")
        operator = _absolute(value["operator_config"], "operator_config")
        self.checks.operator_config(operator)
        socket_path = (
            _absolute(value["signer_socket"], "signer_socket")
            if value.get("signer_socket")
            else None
        )
        with self.lock:
            record = self._record()
            if "hotkey" not in record:
                raise SetupRefused("address", "registration_not_confirmed")
            check = self.checks.agent(record["hotkey"], socket_path)
            # A password stored by an earlier version of this page is no
            # longer needed by anything: remove it rather than keep a secret.
            (self.root / "miner-password").unlink(missing_ok=True)
            public = write_private(
                self.root / "miner-public.json",
                canonical({"netuid": CARBON_NETUID, "hotkey": record["hotkey"]}),
            )
            paths = {"miner_public": str(public), "operator_config": str(operator)}
            if socket_path is not None:
                paths["signer_socket"] = str(socket_path)
            return self._step(
                "agent",
                {"choice": AUTONOMOUS, "paths": paths, "check": check},
            )

    def profile(self) -> dict:
        """The runner profile the checked steps describe, validated."""
        from scripts.dev.miner_launchpad.runner import PROFILE_SCHEMA, validated_profile

        record = self._record()
        for step in ("inference", "compute", "agent"):
            if step not in record:
                raise SetupRefused(step, "step_not_checked")
        inference, compute, agent = (
            record[s] for s in ("inference", "compute", "agent")
        )
        key = str(self.root / "keys" / (inference["provider_id"] + ".key"))
        campaigns = _private_dir(self.root / "campaigns")
        cfg = {
            "schema": PROFILE_SCHEMA,
            "profile_id": PROFILE_ID,
            "principal": record["hotkey"],
            "enabled": True,
            "paths": {
                **compute["paths"],
                **agent["paths"],
                # Required by the profile; named for the chosen provider below,
                # so no other provider can fall back to it.
                "api_key_file": key,
                "quarantine_journal": str(self.root / "quarantine-journal.sqlite3"),
            },
            "accepted_revision": compute["runtime"]["implementation"]["revision"],
            "campaigns_root": str(campaigns),
            "runtime": compute["runtime"],
            "provider_credentials": {inference["provider_id"]: key},
            "model_selection": {
                "provider_id": inference["provider_id"],
                "model_id": inference["model_id"],
                **{
                    k: inference[k]
                    for k in ("endpoint", "declared_pricing", "published_pricing")
                    if k in inference
                },
            },
        }
        try:
            return validated_profile(cfg)
        except ValueError:
            raise SetupRefused("review", "profile_invalid") from None

    def review(self, value) -> dict:
        """Write the profile and load it into the controller."""
        _closed(value, {"confirm"})
        if value["confirm"] is not True:
            raise SetupRefused("confirm", "review_needs_confirmation")
        with self.lock:
            cfg = self.profile()
            write_private(self.profile_path, canonical(cfg))
            record = self._record()
            record["profile"] = {"written_at": int(time.time())}
            self._save(record)
        attached = self.attach(self.profile_path) if self.attach is not None else False
        return {**self.state(), "attached": attached}


def _public(step, fields):
    if step is None:
        return {"checked": False}
    return {
        "checked": True,
        "checked_at": step["checked_at"],
        **{f: step[f] for f in fields if f in step},
    }
