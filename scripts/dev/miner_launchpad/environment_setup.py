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
setup's first step and the Agent step only ask it, through
`carbon.chain.external_signer`, which hotkey it holds. No hotkey file path and no password is asked for, stored or
written into the profile.

**Every connection is checked live, at the miner's cost, with consent.** A
check that spends runs only on consent to a stated amount: `quote` gives the
check's maximum cost for the chosen model, and the check refuses unless its
`consent` names that same maximum. A bare `true` is not consent - it says
nothing about what was agreed to - so a client that defaults it on spends
nothing.

**Refusals name the field** they are about, so the page can point at it.

Only launchable choices are offered.
- Inference (C-MLP-03 slice 2) offers every provider adapter: Engy's Chat
  Completions route first, Chutes with the prices it publishes, the fixed
  OpenAI and Anthropic APIs, and the generic OpenAI-shaped adapters with the
  miner's own endpoint and, optionally, their declared price.
- Compute (slice 3) offers this machine's CPU, every miner's default, and
  this machine's own GPU for practice speed. Carbon rents no compute
  (OWNER-MINER-COMPUTE-LINK-ONLY-01): the rented-GPU choice of slices 4 and
  4b is refused by name, and Carbon's stored copy of its provider key is
  deleted the next time compute is set up.
- Compute also offers the miner's own remote machine or container, any
  setup they run (the decision's amendment, LINKONLY-D5 to D9). Setup
  reaches it with the miner's own SSH, checks what practice needs there and
  starts nothing; for a machine with Docker, sending the pinned worker is its
  own step, with consent to the destination and the image. Its "Where's your
  GPU?" cards (LINKONLY-D10) set the transport for each setup the wiring
  guide covers and show that setup's notes and commands from the guide.
- Agent (slice 5) offers Graphite, Carbon's research agent, which replaced
  the autonomous agent for new setups (OWNER-GRAPHITE-MINER-01); the miner's
  own agent over MCP; or Hermes. A setup that recorded the autonomous agent
  keeps it; choosing it again is refused `autonomous_agent_replaced`.
- The network (C-MLP-04) is read from the chain: Carbon's testnet and its
  publisher, the hotkey at UID 0. A miner names no operator configuration;
  only an operator running Carbon's own deployment does.
- The evaluation endpoint (LP-PROD-E) is the one Carbon publishes for each
  Challenge in `published_endpoints.json`. Review writes it into the
  profile, and says plainly when none is published yet: such a profile
  practises and freezes, but cannot submit. Review also pins each intake's
  receiver hotkey (LAUNCHPAD-ACCEPT-03): the published one, or the one the
  miner names beside their own intake. Nothing is signed for an intake that
  reports another.

**A check describes one install** (LP-PROD-E). The compute check pins each
image manifest it verified by digest, and the installer records what it
installed. A check made at another revision or with other images is stale:
setup shows it unchecked and Review refuses it. After a (re)install,
`python -m scripts.dev.miner_launchpad.environment_setup after-install` sets a
stale check aside, checks this machine's compute again, and writes the
profile again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

from carbon.compute import retired
from carbon.development_session.gpu_practice import SPEED_ONLY as SPEED_ONLY_NOTE
from carbon.development_session.profile import canonical
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.hermes_setup import START

SETUP_SCHEMA = "carbon.launchpad.environment-setup.v1"
STEPS = ("inference", "compute", "agent", "review")
PROFILE_ID = "miner-environment"
REPO = Path(__file__).resolve().parents[3]

#: The miner's own machine, CPU: every miner's default (owner, 2026-10-01).
LOCAL_CPU = "this-machine-cpu"
#: The miner's own machine with its GPU, for practice speed only (C-MLP-03
#: slice 3). Research and practice run there; the validator rebuilds on its
#: own pinned backend and resources.
LOCAL_GPU = "this-machine-gpu"
#: The miner's own remote machine or container, reached over their own SSH,
#: for practice speed only (OWNER-MINER-COMPUTE-LINK-ONLY-01, amended
#: 2026-10-02: any setup the miner runs). Carbon never starts, stops or
#: bills it.
REMOTE = "remote-machine"
#: The wiring guide setup names for it.
REMOTE_GUIDE = "docs/development/MINER_REMOTE_SETUP.md"
#: Where a miner's GPU can be beyond this machine, as setup's "Where's your
#: GPU?" cards show it (LINKONLY-D10): each setup the wiring guide covers, the
#: transport it takes and its section there. A machine or VM with Docker is
#: reached as `ssh-docker`; a container rental as `ssh-container`. These are
#: notes for the miner's own accounts: Carbon calls no provider API and
#: starts, stops and bills none of them (OWNER-MINER-COMPUTE-LINK-ONLY-01).
REMOTE_GUIDES = (
    ("runpod", "RunPod", "ssh-container", "RunPod pods"),
    ("lium", "Lium", "ssh-container", "Lium (Bittensor subnet 51)"),
    ("targon", "Targon", "ssh-docker", "Targon VMs (Bittensor subnet 4)"),
    ("vast", "Vast.ai", "ssh-container", "Vast.ai"),
    ("lambda", "Lambda", "ssh-docker", "Lambda"),
    ("own-server", "My own server / workstation", "ssh-docker", "Your own workstation"),
)
#: A command a provider documents for the miner's own machine, as the guide
#: quotes it.
GUIDE_COMMANDS = {
    "lambda": (
        (
            "On the instance: run docker without sudo, then log in again",
            'sudo adduser "$(id -un)" docker',
        ),
    ),
}
#: The retired choice of a GPU rented with the miner's provider key (C-MLP-03
#: slices 4 and 4b), refused by name (OWNER-MINER-COMPUTE-LINK-ONLY-01).
RETIRED_RENTED_GPU = retired.RENTED_CHOICE
#: Carbon's stored copies of the provider keys that choice took.
RETIRED_COMPUTE_KEYS = "*.compute-key"
#: What the compute check says once it has deleted one.
COMPUTE_KEY_REMOVED = (
    "Carbon deleted its stored copy of your rented-GPU provider key. Revoke "
    "that key at your provider."
)
#: The host device record setup installs names this machine and provider.
GPU_RECORD_ID = "this-machine"
GPU_PROVIDER = "own-machine"
#: Graphite, Carbon's research agent (miner edition, OWNER-GRAPHITE-MINER-01),
#: running in this controller's process on this machine on the miner's own
#: model, key and budget. Launch's name for it is `graphite`.
GRAPHITE = "carbon-graphite"
#: Carbon's autonomous research agent: replaced by Graphite for new setups. A
#: setup that recorded it keeps it, and its campaigns run as they were;
#: choosing it now is refused `autonomous_agent_replaced`.
AUTONOMOUS = "carbon-autonomous"
#: Hermes Agent on the miner's machine, driving Carbon's MCP server over stdio
#: (C-MLP-03 slice 5).
HERMES = "hermes"
#: The miner's own agent, any MCP client (OWNER-MINER-SETUP-AGENT-FIRST-01):
#: it brings its own model, so setup's Inference step is skipped for it.
OWN_AGENT = "own-agent"
#: The agents that call a model chosen in setup's Inference step: Carbon's own
#: agent (Graphite, or the autonomous agent a setup recorded earlier), and
#: Hermes' ready-made profile, which is written with that model.
USES_SETUP_MODEL = (GRAPHITE, AUTONOMOUS, HERMES)
#: Who researches, as setup offers it now.
AGENT_CHOICES = (GRAPHITE, OWN_AGENT, HERMES)
#: Graphite's name, as setup and the capability document both show it.
GRAPHITE_DISPLAY_NAME = "Graphite, Carbon's research agent"
#: Where a profile points its model key when no Inference step was taken: no
#: file is there, so Carbon's agent stays unavailable and nothing reads it.
NO_MODEL_KEY = "no-model.key"

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
    "gpu_image_manifest": (
        "Build the GPU worker from this exact clean checkout: "
        "./scripts/dev/accelerator_worker_image.sh"
    ),
}

#: What a miner does when setup cannot install the host device record itself.
GPU_RECORD_STEP = (
    "install it as the user that owns /var/lib/carbon/accelerators: "
    "python scripts/dev/carbon_accelerator.py prepare --record-id "
    + GPU_RECORD_ID
    + " --provider "
    + GPU_PROVIDER
    + " --container-runtime DOCKER_ENGINE"
)

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

#: The evaluation endpoints Carbon publishes (LP-PROD-E): for a network,
#: subnet and Challenge, the validator intake a frozen candidate is
#: submitted to and the hotkey that receives it. An operator adds the live
#: entry by pull request (BATTERY_VALIDATOR_SERVICE_RUNBOOK); an empty list
#: publishes none. The receiver hotkey is binding (LAUNCHPAD-ACCEPT-03):
#: Review pins it in the profile's `receivers`, and the intake must report it
#: before a submit, a resend or a status poll is signed (`RECEIVER_NOTE`).
PUBLISHED_ENDPOINTS = Path(__file__).resolve().with_name("published_endpoints.json")
PUBLISHED_SOURCE = "scripts/dev/miner_launchpad/published_endpoints.json"
PUBLISHED_SCHEMA = "carbon.launchpad.published-endpoints.v1"
PUBLISHED_KEYS = frozenset({"schema", "about", "entry_fields", "endpoints"})
PUBLISHED_FIELDS = frozenset(
    {"network", "netuid", "challenge", "intake_url", "receiver_hotkey"}
)
#: What Review says for a Challenge with no evaluation endpoint.
NO_ENDPOINT = (
    "No evaluation endpoint is published for {title} yet. Your profile can "
    "practise and freeze, but cannot submit to it until one is published; "
    "update Carbon and review again then, or name a validator intake you "
    "run yourself."
)
#: What setup says beside a pinned receiver hotkey (LAUNCHPAD-ACCEPT-03).
RECEIVER_NOTE = (
    "binding: your profile pins this hotkey as the endpoint's receiver. Before "
    "your signer signs a submission, a resend or a status request, Carbon "
    "checks that the intake reports this receiver, and otherwise refuses "
    "intake_receiver_mismatch with nothing signed or sent."
)
#: What setup and the prelaunch review say about an intake whose profile was
#: written before receivers were pinned: it keeps working, unchecked.
RECEIVER_NOT_PINNED = (
    "Your profile was written before Carbon pinned each intake's receiver "
    "hotkey, so the receiver of your intake for {title} is not checked before "
    "your signer signs. Review again in setup to pin it."
)
#: What a miner's own intake needs at Review (LAUNCHPAD-ACCEPT-03).
RECEIVER_STEP = (
    "name the validator's public receiver hotkey (its ss58 address) beside "
    "your own intake: receiver_hotkey"
)
#: What a miner does when an intake reports another receiver than named.
RECEIVER_MISMATCH_STEP = (
    "check the intake address and the receiver hotkey you named: the intake "
    "reports another receiver, so nothing would be signed for it"
)
#: How several own intakes name their receivers.
RECEIVER_ONE_STEP = (
    "send receiver_hotkey beside exactly one intake of your own, or receivers "
    "mapping each of your intakes' Challenge ids to its receiver hotkey"
)


#: What a miner does when Review cannot read an intake's public facts
#: (LAUNCHPAD-ACCEPT-04). A loopback address is usually the near end of a
#: tunnel to a validator that binds its own loopback.
LOOPBACK_UNREACHABLE_STEP = (
    "nothing answered at this loopback address: start your tunnel to the "
    "validator (for example ssh -N -L <local port>:127.0.0.1:<intake port> "
    "<validator host>) or the validator itself, then review again; Carbon "
    "cannot tell which of them is not running"
)
INTAKE_UNREACHABLE_STEP = (
    "the intake did not answer as a battery intake: check its address and "
    "your connection, then review again"
)
#: What a miner does when the intake serves another network, subnet or
#: Challenge than the one it is named for.
INTAKE_MISMATCH_STEP = (
    "this intake serves another network, subnet or Challenge: name the "
    "intake of a validator on Carbon's testnet (netuid 567) for this "
    "Challenge, then review again"
)


def _loopback(url) -> bool:
    """Whether an intake URL names this machine's loopback."""
    from urllib.parse import urlsplit

    try:
        return urlsplit(url).hostname in ("127.0.0.1", "localhost")
    except ValueError:
        return False


def _named_receivers(value, intakes, unpinned=frozenset()) -> dict:
    """The receiver hotkey a Review request names for each of the miner's
    own `intakes` (LAUNCHPAD-ACCEPT-03): `receiver_hotkey` beside exactly one,
    or `receivers` mapping several. Each own intake needs one, except one in
    `unpinned` (an update writing a profile from before receivers were
    pinned again). Refusals name the field `receiver_hotkey`."""

    def refused(code, step=RECEIVER_ONE_STEP):
        return SetupRefused("receiver_hotkey", code, next_step=step)

    named = value.get("receivers", {})
    if type(named) is not dict:
        raise refused("receiver_hotkey_names_one_intake")
    named = dict(named)
    if "receiver_hotkey" in value:
        if "receivers" in value or len(intakes) != 1:
            raise refused("receiver_hotkey_names_one_intake")
        named[next(iter(intakes))] = value["receiver_hotkey"]
    for challenge_id, hotkey in named.items():
        if challenge_id not in intakes:
            raise refused("receiver_hotkey_needs_its_intake")
        if type(hotkey) is not str or not _ADDRESS.fullmatch(hotkey):
            raise refused("receiver_hotkey_invalid", RECEIVER_STEP)
    for challenge_id in intakes:
        if challenge_id not in named and challenge_id not in unpinned:
            raise refused("receiver_hotkey_required", RECEIVER_STEP)
    return named


#: What setup says about the miner's own intake in a profile an update set
#: aside: Review writes only the intakes it is given, so it is named again.
KEPT_INTAKE_NOTE = (
    "Your own intake for {title} was in the runner profile this update set "
    "aside. Review writes only the intakes you name, and otherwise Carbon's "
    "published endpoint if there is one: name yours again at Review to keep it."
)

#: What the installer installed here (LP-PROD-E): the checkout's revision and
#: each image manifest it recorded, with the manifest's digest and image ID.
INSTALLATION = "installation.json"
INSTALLATION_SCHEMA = "carbon.launchpad.installation.v1"
#: The image manifests a compute check pins, and what each is called.
IMAGE_LABELS = {
    "image_manifest": "the worker image",
    "analysis_image_manifest": "the analysis image",
    "gpu_image_manifest": "the GPU worker image",
}
#: A compute check made before checks pinned their images.
STALE_UNPINNED = "this check was made before setup pinned the images it checked"
#: What a miner does about a stale compute check that checking again clears:
#: an image rebuilt or gone, a check from before pinning, or one made at
#: another revision or with other images while this checkout is still the
#: one the installer installed (setup fills in the installer's images).
RECHECK_STEP = "check Compute again in setup"
#: What a miner does when only the installer can clear it: its own record is
#: unusable, or this checkout moved since it ran (a check made now would be
#: made at a revision the installer built no images for).
REINSTALL_STEP = "run scripts/install_miner.sh --update"
#: Where `after_install` moves a runner profile whose compute check it set
#: aside, so no restarted Control Center attaches it (LP-PROD-E).
STALE_PROFILE = "runner-profile.stale.json"
#: What clears a runner profile that no longer describes this install while
#: this checkout is still the one the installer installed: a compute check
#: made now, then Review writes the profile again (LP-PROD-W2).
PROFILE_RECHECK_STEP = RECHECK_STEP + ", then review to write your profile again"
#: Where a runner profile names each image it pins by image ID
#: (`runtime.images`), as `runner.checkout_refusal` reads them.
PROFILE_IMAGE_POSITIONS = {"image_manifest": 0, "analysis_image_manifest": 1}
#: Why an update leaves the miner's own remote setup to them.
REMOTE_RECHECK = (
    "your remote setup needs the new GPU worker: check Compute again in "
    "setup, then send or push the worker; Carbon reaches your setup only "
    "when you check it"
)
#: Characters a path may have in the service unit: nothing systemd would
#: expand, split or quote.
_UNIT_PATH = re.compile(r"/[A-Za-z0-9._/@+=:,-]{1,4095}")


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


def signer_command() -> str:
    """How the miner starts their signer, from this controller's environment
    when it holds the signer, otherwise by name."""
    binary = Path(sys.executable).with_name("carbon-miner-signer")
    name = shlex.quote(str(binary)) if binary.is_file() else "carbon-miner-signer"
    return name + " --wallet <your wallet> --hotkey <your hotkey>"


def guide_commands(guide_id, transport, gpu_manifest=None) -> list[dict]:
    """The commands a miner runs for one remote setup, each to copy.

    `<destination>` is the SSH destination the miner types in setup; the page
    fills it in. A container rental pulls the worker image from a registry the
    miner controls, so its first command is the push helper, with the GPU
    worker setup found when there is one (otherwise the helper builds it).
    """
    commands = []
    if transport == "ssh-container":
        push = shlex.quote(str(REPO / "scripts/dev/push_worker_image.sh"))
        if gpu_manifest:
            push += " --manifest " + shlex.quote(str(gpu_manifest))
        commands.append(
            {
                "label": "Push your worker image to a registry you control "
                "(after your own docker login)",
                "command": push + " <registry>/<you>/carbon-gpu-worker",
            }
        )
    commands += [
        {"label": "Load your SSH key into your agent", "command": "ssh-add"},
        {
            "label": "Connect once by hand to accept the host key",
            "command": "ssh <destination>",
            "destination": True,
        },
        {
            "label": "Check it answers without a prompt, as Carbon will",
            "command": "ssh -o BatchMode=yes <destination> true",
            "destination": True,
        },
    ]
    for label, command in GUIDE_COMMANDS.get(guide_id, ()):
        commands.append({"label": label, "command": command})
    return commands


#: The Control Center's state directory when none is named (controller.main).
DEFAULT_STATE_DIR = Path.home() / ".carbon" / "development-launchpad"
#: Where each client's MCP configuration was read, 2026-10-02. Nothing here
#: was run against the client: each snippet says so (UNVERIFIED).
CLIENT_DOCS = {
    "claude-code": "code.claude.com/docs/en/mcp",
    "codex": "learn.chatgpt.com/docs/extend/mcp (Codex CLI)",
    "hermes": "hermes-agent.nousresearch.com/docs/user-guide/features/mcp",
}


def mcp_connect(state_dir=None) -> dict:
    """How the miner's own agent connects: one command, and a snippet per
    client from that client's public documentation (OWNER-MINER-SETUP-AGENT-
    FIRST-01).

    The server starts with no runner profile: the open tier and setup, over
    the same setup records as this Control Center. The checkout must be on
    the import path (its `scripts` package), so each snippet names it.
    """
    python = sys.executable
    args = ["-m", "carbon.miner_mcp.standard_cli"]
    if state_dir is not None and Path(state_dir) != DEFAULT_STATE_DIR:
        args += ["--state-dir", str(state_dir)]
    repo = str(REPO)
    command = " ".join(shlex.quote(part) for part in [python, *args])
    # LA-F14: a snippet that names the checkout by PYTHONPATH, with no cwd,
    # starts in whatever directory the agent runs in, and `python -m` puts
    # that directory first on the import path: inside another Carbon
    # checkout, that checkout's packages load instead. `-P` (Python 3.11+)
    # leaves it off. Snippets with `cwd` set to this checkout are already right.
    env_args = ["-P", *args]
    env_command = " ".join(shlex.quote(part) for part in [python, *env_args])
    quoted = lambda value: json.dumps(value)
    claude = {
        "mcpServers": {
            "carbon": {
                "command": python,
                "args": env_args,
                "env": {"PYTHONPATH": repo},
            }
        }
    }
    toml = (
        # One whole table: a key appended after `codex mcp add` would land
        # in the [mcp_servers.carbon.env] table it writes.
        "# The whole table: use it in place of any [mcp_servers.carbon]\n"
        "# tables `codex mcp add` wrote.\n"
        "[mcp_servers.carbon]\n"
        f"command = {quoted(python)}\n"
        f"args = {json.dumps(args)}\n"
        f"cwd = {quoted(repo)}\n"
        "tool_timeout_sec = 1800\n"
        # LA-F13: `codex exec` runs with no one to approve a prompt, so a
        # Carbon tool it calls fails "requires approval". Codex's documented
        # per-server setting (learn.chatgpt.com/docs/extend/mcp): `prompt`
        # asks each time; `approve` is the value its example uses for a tool
        # that runs without asking.
        "# Codex asks before each Carbon tool. For unattended runs\n"
        '# (codex exec), set "approve" (run on Codex 0.161.0). Starting your\n'
        "# signer, signing your registration and confirming a commitment stay\n"
        "# yours either way.\n"
        'default_tools_approval_mode = "prompt"\n'
    )
    yaml = (
        "mcp_servers:\n"
        "  carbon:\n"
        f"    command: {quoted(python)}\n"
        f"    args: {json.dumps(args)}\n"
        f"    cwd: {quoted(repo)}\n"
        "    timeout: 1800\n"
    )
    not_run = "UNVERIFIED: Carbon has not run this client against the server."
    return {
        "command": command,
        "cwd": repo,
        "note": (
            "Run it from your Carbon checkout. With no runner profile it serves "
            "the open tier and setup; once setup writes your profile, the same "
            "session gains launch and the research operations."
        ),
        "clients": [
            {
                "id": "claude-code",
                "name": "Claude Code",
                "source": CLIENT_DOCS["claude-code"] + ", read 2026-10-02",
                "snippets": [
                    {
                        "label": "Add it",
                        # The server name before --env: Claude Code's --env
                        # takes several values and would swallow the name
                        # (LA-F12, Claude Code 2.1.294). --scope user makes
                        # it available in every directory; Claude Code's
                        # default scope is the current directory only.
                        "text": "claude mcp add --transport stdio --scope user "
                        + "carbon --env "
                        + shlex.quote("PYTHONPATH=" + repo)
                        + " -- "
                        + env_command,
                    },
                    {"label": "Or in .mcp.json", "text": json.dumps(claude, indent=2)},
                ],
                # Run on Claude Code 2.1.294 (LA-F12, cell A3, 2026-10-08).
                "verified": "Claude Code 2.1.294, 2026-10-08",
                "unverified": [
                    (
                        "UNVERIFIED: how Claude Code bounds a long tool call; "
                        "Send your worker can take minutes."
                    ),
                ],
            },
            {
                "id": "codex",
                "name": "Codex",
                "source": CLIENT_DOCS["codex"] + ", read 2026-10-02",
                "snippets": [
                    {
                        "label": "Add it",
                        "text": "codex mcp add carbon --env "
                        + shlex.quote("PYTHONPATH=" + repo)
                        + " -- "
                        + env_command,
                    },
                    {"label": "Or in ~/.codex/config.toml", "text": toml},
                ],
                # Run on Codex 0.161.0, interactive and unattended with
                # default_tools_approval_mode = "approve" (LA-F13, cell A4).
                "verified": "Codex 0.161.0, 2026-10-08",
                "unverified": [],
            },
            {
                "id": "hermes",
                "name": "Hermes Agent",
                "source": CLIENT_DOCS["hermes"] + ", read 2026-10-02",
                "snippets": [
                    {
                        "label": "In ~/.hermes/config.yaml, then /reload-mcp in Hermes",
                        "text": yaml,
                    }
                ],
                "unverified": [
                    not_run,
                    (
                        "UNVERIFIED: whether `hermes mcp add` takes your own "
                        "command; its documentation shows presets."
                    ),
                ],
            },
        ],
    }


def remote_guides(gpu_manifest=None) -> dict:
    """The "Where's your GPU?" cards beyond this machine, from the guide.

    Each card carries its transport, its section of the wiring guide as text
    data (UNVERIFIED marks included) and its commands. When this checkout has
    no guide, the cards keep their transport and commands and show no steps.
    """
    from scripts.dev.miner_launchpad import guide

    document = guide.document("remote-setup")
    parsed = document["blocks"]
    return {
        "source": document["source"],
        "notes": guide.section(parsed, "Per-provider notes", nested=False) or [],
        "cards": [
            {
                "id": guide_id,
                "display_name": name,
                "transport": transport,
                "anchor": guide.slug(heading),
                "steps": guide.section(parsed, heading) or [],
                "commands": guide_commands(guide_id, transport, gpu_manifest),
            }
            for guide_id, name, transport, heading in REMOTE_GUIDES
        ],
    }


def choices(gpu_manifest=None) -> dict:
    """What each step offers: only what launches today, each with its cost.

    `gpu_manifest`, when setup has found the GPU worker, goes into the remote
    cards' push command."""
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
                "default": True,
                "needs_gpu_image": False,
                "cost_basis": "Your own machine: nothing is rented or billed.",
                "live_check": (
                    "Reads this checkout's revision and verifies your locally "
                    "built worker and analysis images. No network, no cost."
                ),
            },
            {
                "id": LOCAL_GPU,
                "display_name": "This machine (your GPU)",
                "default": False,
                "needs_gpu_image": True,
                # GPU practice is set up for one Challenge (C-MLP-04).
                "for_challenges": gpu_challenges(),
                "cost_basis": "Your own machine: nothing is rented or billed.",
                "live_check": (
                    "Everything the CPU check does, then detects your GPU with "
                    "nvidia-smi, installs this host's device record, and "
                    "verifies your GPU worker image and the NVIDIA container "
                    "runtime. No network, no cost."
                ),
                "note": SPEED_ONLY_NOTE,
            },
            {
                "id": REMOTE,
                "display_name": "Your own remote machine or container",
                "default": False,
                "needs_gpu_image": True,
                "needs_remote": True,
                # Remote practice is set up for one Challenge whose campaign
                # offers it (Challenge-neutral, LINKONLY-D9).
                "for_challenges": remote_challenges(),
                "transports": remote_transports(),
                "cost_basis": (
                    "A machine or container you run on your own account: you "
                    "start, stop and pay for it. Carbon never starts, stops or "
                    "bills it, and asks for no provider key."
                ),
                "live_check": (
                    "Everything the CPU check does, then reaches your setup "
                    "with your own SSH (your agent, config and known hosts) "
                    "and checks what practice needs there: Docker, the NVIDIA "
                    "Container Toolkit, Docker without sudo and your GPU "
                    "worker by image ID on a machine; the pinned worker and "
                    "its build identity in a container. It starts nothing and "
                    "installs nothing."
                ),
                "note": SPEED_ONLY_NOTE,
                "guide": REMOTE_GUIDE,
                # The "Where's your GPU?" cards, from the guide (LINKONLY-D10).
                "guides": remote_guides(gpu_manifest),
            },
        ],
        "agent": [
            {
                "id": GRAPHITE,
                "display_name": GRAPHITE_DISPLAY_NAME,
                "cost_basis": (
                    "Runs on this machine. It spends only through your "
                    "inference choice, within the ceilings you set at launch: "
                    "money and time bind it, and you choose how much of your "
                    "budget goes to research."
                ),
                "live_check": (
                    "Asks your running carbon-miner-signer which hotkey it "
                    "holds and checks it is the registered one. Carbon never "
                    "sees your key or password. No network, no cost."
                ),
                "uses_setup_model": True,
                # Chosen at each launch (OWNER-GRAPHITE-MINER-01).
                "modes": ["RESEARCH", "BUILD", "FULL"],
                "summary": (
                    "Hunts and reads literature, writes a ranked plan into "
                    "your library, then constructs, practises, selects and "
                    "submits. Choose Research, Build or Full at launch."
                ),
            },
            {
                "id": OWN_AGENT,
                "display_name": "Your own agent, over MCP",
                "cost_basis": (
                    "Your agent runs where you run it, with its own model, "
                    "billed by its own provider. Carbon bills nothing."
                ),
                "live_check": (
                    "Asks your running carbon-miner-signer which hotkey it "
                    "holds and checks it is the registered one. Carbon never "
                    "sees your key or password. No network, no cost."
                ),
                "uses_setup_model": False,
                "skips": {"inference": "your agent uses its own model"},
                "connect": mcp_connect(),
            },
            {
                "id": HERMES,
                "display_name": "Hermes Agent (Nous Research), on this machine",
                "cost_basis": (
                    "Runs on this machine with your inference choice as its "
                    "model, billed by your provider. Carbon bills nothing."
                ),
                "live_check": (
                    "Finds your installed Hermes and its version, checks your "
                    "signer as above, then, with your consent to the exact "
                    "files, writes a Hermes profile named carbon: your model "
                    "and Carbon's research tools over MCP stdio, each tool "
                    "that can change anything asking you first. No network, "
                    "no cost."
                ),
                "needs_consent_to_write": True,
                "start": START,
                # Its ready-made profile is written with setup's model, so
                # Inference stays; the files are written once it is known.
                "uses_setup_model": True,
            },
        ],
        "not_yet_offered": (
            "Mira (autoscience.ai) publishes no way to connect it to tools "
            "on your machine; the research environment standard names it."
        ),
    }


class LiveChecks:
    """The live checks, each against the miner's own accounts and files.

    `opener` replaces urllib's for fixture tests; Carbon's tests never reach a
    provider. Each check returns public facts only, never a key or a path.
    """

    def __init__(
        self,
        *,
        opener=None,
        repo: Path = REPO,
        host_root=None,
        hermes_home=None,
        ssh=None,
    ):
        self.opener = opener
        self.repo = repo
        # The miner's own ssh client (`remote_machine.SSHClient` unless a test
        # names a double): it reaches their remote setup and nothing else.
        self.ssh = ssh
        # Where Hermes keeps its profiles (`HERMES_HOME` or ~/.hermes).
        self.hermes_home = hermes_home
        # Where the host device record lives (`HOST_ROOT` unless a test names
        # another directory).
        self.host_root = host_root

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

    def gpu(self, gpu_manifest: Path, campaign=None) -> dict:
        """Detect this machine's GPU, install its device record, and verify
        the GPU worker image and container runtime. Nothing leaves the host."""
        from carbon.development_session.gpu_practice import is_gpu_image
        from carbon.reconstruction import onboarding
        from carbon.reconstruction.host_inventory import (
            HOST_DEVICE_RECORD,
            HostDeviceRecord,
        )
        from carbon.reconstruction.worker.accelerator_runtime import (
            HOST_ROOT,
            verify_image_and_toolkit,
        )
        from carbon.reconstruction.worker.docker_runtime import (
            DockerCLI,
            load_image_identity,
        )
        from carbon.reconstruction.worker.model import WorkerFailure

        root = self.host_root or HOST_ROOT
        try:
            image = load_image_identity(gpu_manifest)
        except Exception:  # noqa: BLE001 - never echo a local path or error.
            image = None
        if not is_gpu_image(image):
            raise SetupRefused(
                "gpu_image_manifest",
                "gpu_image_unverified",
                next_step=BUILD_STEPS["gpu_image_manifest"],
            )
        try:
            observed = onboarding.observe_local_device()
        except WorkerFailure:
            raise SetupRefused(
                "gpu",
                "gpu_not_detected",
                next_step="install the NVIDIA driver so nvidia-smi reports your GPU",
            ) from None
        cli = DockerCLI()
        try:
            info = cli.json(["info", "--format", "{{json .}}"])
        except WorkerFailure:
            info = None
        runtime = onboarding._detect_container_runtime(info)
        try:
            document = onboarding.build_host_record(
                observed=observed,
                record_id=GPU_RECORD_ID,
                provider=GPU_PROVIDER,
                container_runtime=None if runtime == onboarding.UNKNOWN else runtime,
                provenance="detected by Launchpad setup with "
                + str(observed.get("source")),
            )
        except WorkerFailure:
            # Several GPUs, an unknown platform or container runtime: the
            # miner names them; Carbon does not pick for them.
            raise SetupRefused(
                "gpu", "gpu_record_needs_your_choice", next_step=GPU_RECORD_STEP
            ) from None
        try:
            installed = HostDeviceRecord.load(root)
        except WorkerFailure:
            installed = None
        if installed is None or installed.device_uuid != document["device_uuid"]:
            try:
                onboarding.install_record(root, document, name=HOST_DEVICE_RECORD)
            except WorkerFailure:
                raise SetupRefused(
                    "gpu", "host_device_record_not_writable", next_step=GPU_RECORD_STEP
                ) from None
        try:
            verify_image_and_toolkit(cli=cli, image=image)
        except WorkerFailure:
            raise SetupRefused(
                "gpu_image_manifest",
                "gpu_container_runtime_unavailable",
                next_step=(
                    "install the NVIDIA Container Toolkit, then build the GPU "
                    "worker: ./scripts/dev/accelerator_worker_image.sh"
                ),
            ) from None
        blockers = onboarding.miner_lane_blockers(
            onboarding.doctor_report(root=root, cli=cli, image=image)
        )
        if blockers:
            raise SetupRefused("gpu", "gpu_host_not_ready:" + ",".join(blockers))
        record = HostDeviceRecord.load(root)
        return {
            # The chosen Challenge's own GPU practice scope (C-MLP-04).
            "scope": campaign.gpu_scope(image),
            "device_kind": record.device_kind,
            "record_digest": record.digest,
        }

    def _remote(self, gpu_manifest: Path, machine):
        """The pinned GPU worker and the transport to the miner's setup."""
        from carbon.compute.remote_transport import transport_for
        from carbon.development_session.gpu_practice import is_gpu_image
        from carbon.reconstruction.worker.docker_runtime import load_image_identity

        try:
            image = load_image_identity(gpu_manifest)
        except Exception:  # noqa: BLE001 - never echo a local path or error.
            image = None
        if not is_gpu_image(image):
            raise SetupRefused(
                "gpu_image_manifest",
                "gpu_image_unverified",
                next_step=BUILD_STEPS["gpu_image_manifest"],
            )
        options = {} if self.ssh is None else {"ssh": self.ssh}
        return image, transport_for(machine, **options)

    @staticmethod
    def _remote_refused(refused):
        return SetupRefused(
            REMOTE_FIELDS.get(refused.code, "remote"),
            refused.code,
            next_step=refused.next_step,
        )

    def remote(self, gpu_manifest: Path, machine, campaign) -> dict:
        """Reach the miner's remote setup with their own SSH and check what
        practice needs there. Starts nothing, installs nothing, costs
        nothing (OWNER-MINER-COMPUTE-LINK-ONLY-01)."""
        from carbon.compute.remote_machine import RemoteMachineError
        from carbon.compute.remote_route import remote_scope

        image, transport = self._remote(gpu_manifest, machine)
        try:
            check = transport.check(image)
        except RemoteMachineError as refused:
            raise self._remote_refused(refused) from None
        return {
            # The chosen Challenge's own GPU practice scope, and remote
            # practice beside it over the miner's transport.
            "scope": campaign.gpu_scope(image),
            "remote_scope": remote_scope(
                campaign.key.challenge_id, image, machine.transport
            ),
            "check": check,
        }

    def send_worker(self, gpu_manifest: Path, machine, image_id: str) -> str:
        """Stream the pinned GPU worker `image_id` to the miner's machine with
        Docker, and check it arrived by image ID: "present" or "sent"."""
        from carbon.compute.remote_machine import RemoteMachineError

        image, transport = self._remote(gpu_manifest, machine)
        if image.image_id != image_id:
            # Rebuilt since the check: the miner agreed to send another image.
            raise SetupRefused(
                "gpu_image_manifest", "gpu_image_changed_since_the_check"
            )
        try:
            return transport.send(image)
        except RemoteMachineError as refused:
            raise self._remote_refused(refused) from None

    def hermes_files(self) -> list[str]:
        """The exact files a Hermes choice writes, for the miner's consent."""
        from scripts.dev.miner_launchpad.hermes_setup import (
            hermes_home,
            profile_files,
        )

        return [str(p) for p in profile_files(self.hermes_home or hermes_home())]

    def hermes(self, document: dict, key: str) -> dict:
        """Find Hermes, then write the consented profile files."""
        from scripts.dev.miner_launchpad import hermes_setup

        binary = hermes_setup.find_hermes()
        version = None if binary is None else hermes_setup.hermes_version(binary)
        if version is None:
            raise SetupRefused(
                "hermes", "hermes_not_installed", next_step=hermes_setup.INSTALL_STEP
            )
        written = hermes_setup.write_profile(
            self.hermes_home or hermes_setup.hermes_home(),
            document,
            key,
            write_private,
        )
        return {"hermes": version, "written": written}

    def intake(self, url: str, campaign=None) -> dict:
        """Read the validator intake's public facts and check, through the
        Challenge's own campaign, that it serves this chain and Challenge.
        Sends nothing signed and costs nothing."""
        from carbon.challenge_registry.campaigns import IntakeMismatch

        try:
            facts = campaign.intake_check(url)
        except IntakeMismatch:
            raise SetupRefused(
                "intakes",
                "intake_serves_another_chain_or_challenge",
                next_step=INTAKE_MISMATCH_STEP,
            ) from None
        except (OSError, ValueError, KeyError, TypeError):
            # A loopback intake is usually a tunnel to a validator's loopback
            # door (LAUNCHPAD-ACCEPT-04): its tunnel or the validator is not
            # running, and Carbon cannot tell which.
            raise SetupRefused(
                "intakes",
                "intake_unreachable",
                next_step=(
                    LOOPBACK_UNREACHABLE_STEP
                    if _loopback(url)
                    else INTAKE_UNREACHABLE_STEP
                ),
            ) from None
        return {"receiver": facts["receiver"], "snapshot": facts["snapshot"]["id"]}

    def agent(self, hotkey: str, socket_path: Path | None = None) -> dict:
        from carbon.chain.external_signer import SignerFailure, connect_signer

        try:
            connect_signer(hotkey, socket_path=socket_path)
        except SignerFailure as failure:
            raise SetupRefused("signer", failure.code, next_step=SIGNER_STEP) from None
        return {"signing": "carbon-miner-signer holds the registered hotkey"}

    def network(self) -> tuple[dict, int]:
        """Carbon's testnet context and its publisher (the hotkey at UID 0),
        read from a finalized snapshot: what a miner's campaign talks to,
        without an operator file (C-MLP-04)."""
        from carbon.chain.models import ChainFailure
        from carbon.chain.sdk import BittensorReader
        from carbon.development_session import miner_network

        try:
            bound, block = miner_network.resolve(BittensorReader())
        except (ChainFailure, miner_network.NetworkUnavailable):
            raise SetupRefused("network", "network_unreadable") from None
        return miner_network.document(bound, block), block

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


def _gpu_campaign(challenge):
    """The campaign of the Challenge GPU practice is set up for, or a refusal
    naming the field. Only an IMPLEMENTED Challenge whose campaign offers GPU
    practice qualifies (C-MLP-04)."""
    from carbon.challenge_registry import ResolutionError, resolve
    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.challenge_registry.registry import GPU_RESEARCH

    if (
        type(challenge) is not dict
        or set(challenge) != {"id", "version"}
        or not all(type(v) is str for v in challenge.values())
    ):
        raise SetupRefused("challenge", "challenge_id_and_version_required")
    try:
        resolve(challenge["id"], challenge["version"], GPU_RESEARCH)
        campaign = campaign_for(challenge)
    except ResolutionError as refused:
        raise SetupRefused("challenge", refused.code) from None
    if campaign.gpu_scope is None:
        raise SetupRefused("challenge", "challenge_offers_no_gpu_practice")
    return campaign


def gpu_challenges() -> list[dict]:
    """The implemented Challenges whose campaigns offer GPU practice."""
    from carbon.challenge_registry.campaigns import implemented_campaigns
    from carbon.challenge_registry.registry import GPU_RESEARCH

    return [
        {"id": entry.challenge_id, "version": entry.version, "title": entry.title}
        for entry, campaign in implemented_campaigns()
        if GPU_RESEARCH in {p.name for p in entry.profiles}
        and campaign.gpu_scope is not None
    ]


def remote_challenges() -> list[dict]:
    """The implemented Challenges whose campaigns offer GPU practice on the
    miner's own remote setup."""
    from carbon.challenge_registry.campaigns import implemented_campaigns
    from carbon.challenge_registry.registry import GPU_RESEARCH

    return [
        {"id": entry.challenge_id, "version": entry.version, "title": entry.title}
        for entry, campaign in implemented_campaigns()
        if GPU_RESEARCH in {p.name for p in entry.profiles}
        and campaign.gpu_scope is not None
        and campaign.remote_worker is not None
    ]


def remote_transports() -> list[dict]:
    """How Carbon can reach the miner's remote setup: the two built
    transports, and the endpoint transport with why it is not built."""
    from carbon.compute.remote_transport import (
        ENDPOINT,
        ENDPOINT_NEXT_STEP,
        ENDPOINT_NOT_BUILT,
        SSH_CONTAINER,
        SSH_DOCKER,
    )

    return [
        {
            "id": SSH_DOCKER,
            "available": True,
            "display_name": "A machine with Docker, over SSH",
            "summary": (
                "Docker and the NVIDIA Container Toolkit, and your SSH user "
                "runs docker without sudo. Each practice trial runs one job "
                "container from your GPU worker, by image ID, then removes it."
            ),
            "send_worker": True,
        },
        {
            "id": SSH_CONTAINER,
            "available": True,
            "display_name": "A container from the pinned worker, over SSH",
            "summary": (
                "A container you started from the pinned GPU worker image "
                "(push it with scripts/dev/push_worker_image.sh), with SSH "
                "into it and no Docker inside. Each practice trial runs one "
                "job process there after checking the worker's build "
                "identity, then stops it."
            ),
            "send_worker": False,
        },
        {
            "id": ENDPOINT,
            "available": False,
            "display_name": "A job endpoint you expose",
            "reason": ENDPOINT_NOT_BUILT,
            "next_step": ENDPOINT_NEXT_STEP,
        },
    ]


def _remote_machine(value):
    """The miner's remote setup from a setup request, or a refusal naming
    the field."""
    from carbon.compute.remote_machine import RemoteMachineError, checked_destination
    from carbon.compute.remote_transport import BUILT, RemoteMachine

    if type(value) is not dict:
        raise SetupRefused("remote", "closed_setup_request_required")
    _closed(value, {"transport", "destination"}, {"port"})
    try:
        return RemoteMachine.from_document(value)
    except RemoteMachineError as refused:
        raise SetupRefused(
            "transport", refused.code, next_step=refused.next_step
        ) from None
    except ValueError:
        if value["transport"] not in BUILT:
            raise SetupRefused("transport", "remote_transport_not_offered") from None
        try:
            checked_destination(value["destination"])
        except ValueError:
            raise SetupRefused("destination", "ssh_destination_invalid") from None
        raise SetupRefused("port", "ssh_port_invalid") from None


#: Which field a refusal from the miner's remote setup is about.
REMOTE_FIELDS = {
    "ssh_unreachable": "destination",
    "ssh_timed_out": "destination",
    "worker_identity_mismatch": "gpu_image_manifest",
}


def intake_challenges() -> list[dict]:
    """The implemented Challenges whose campaigns submit through an intake."""
    from carbon.challenge_registry.campaigns import implemented_campaigns

    return [
        {"id": entry.challenge_id, "version": entry.version, "title": entry.title}
        for entry, campaign in implemented_campaigns()
        if campaign.intake_check is not None
    ]


def published_endpoints(path=None) -> dict:
    """The evaluation endpoints Carbon publishes for this network and subnet,
    by Challenge id, and whether the published list could be read.

    The list is closed: a top level of `schema`, `about`, `entry_fields` and
    `endpoints`, and entries of exactly `network`, `netuid`, `challenge`,
    `intake_url` (https) and `receiver_hotkey` (an ss58 address), one per
    network, subnet and Challenge. Entries for another network or subnet are
    not this deployment's and are skipped. A list that breaks any of this is
    read as publishing nothing, with `problem` saying so: a malformed entry
    never reaches a profile.
    """
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
    from scripts.dev.miner_launchpad.runner import _intake_url

    source = Path(path or PUBLISHED_ENDPOINTS)
    try:
        if source.is_symlink() or source.stat().st_size > 64 * 1024:
            raise ValueError("published endpoints unreadable")
        document = json.loads(source.read_bytes())
        if (
            type(document) is not dict
            or document.get("schema") != PUBLISHED_SCHEMA
            or not set(document) <= PUBLISHED_KEYS
            or type(document.get("endpoints")) is not list
        ):
            raise ValueError("published endpoints malformed")
        seen, found = set(), {}
        for entry in document["endpoints"]:
            if type(entry) is not dict or set(entry) != PUBLISHED_FIELDS:
                raise ValueError("published endpoint malformed")
            if (
                type(entry["network"]) is not str
                or type(entry["netuid"]) is not int
                or type(entry["challenge"]) is not str
                or not 1 <= len(entry["challenge"]) <= 128
                or type(entry["intake_url"]) is not str
                or not entry["intake_url"].startswith("https://")
                or not _intake_url(entry["intake_url"])
                or type(entry["receiver_hotkey"]) is not str
                or not _ADDRESS.fullmatch(entry["receiver_hotkey"])
            ):
                raise ValueError("published endpoint malformed")
            key = (entry["network"], entry["netuid"], entry["challenge"])
            if key in seen:
                raise ValueError("one published endpoint per Challenge")
            seen.add(key)
            if (entry["network"], entry["netuid"]) == (CARBON_NETWORK, CARBON_NETUID):
                found[entry["challenge"]] = dict(entry)
    except (OSError, ValueError):
        return {"endpoints": {}, "problem": "published_endpoints_unreadable"}
    return {"endpoints": found, "problem": None}


def checkout_revision(repo=REPO):
    """This checkout's HEAD commit, or None when git cannot say."""
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return head if re.fullmatch(r"[0-9a-f]{40}", head) else None


def _manifest(path) -> dict | None:
    """An image manifest's digest and the image ID it names, or None when
    there is no regular file at `path`."""
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2**20:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    try:
        image = json.loads(data).get("image_id")
    except (ValueError, AttributeError):
        image = None
    return {
        "path": str(path),
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
        "image_id": image if type(image) is str else None,
    }


def _manifest_paths(compute) -> dict:
    """{field: path} of each image manifest a compute step was checked with."""
    paths = {
        field: path
        for field, path in (compute.get("paths") or {}).items()
        if field in IMAGE_LABELS
    }
    if compute.get("gpu_image"):
        paths["gpu_image_manifest"] = compute["gpu_image"]
    return paths


def _revision_of(compute):
    runtime = compute.get("runtime") or {}
    return (runtime.get("implementation") or {}).get("revision")


def profile_staleness(profile, cfg) -> tuple[list[str], str | None]:
    """`EnvironmentSetup.profile_staleness` for the runner profile at
    `profile`, whose content is `cfg`: judged against the installer's record
    where setup keeps it, in the profile's own directory (`<state
    dir>/environment`, where Review writes `runner-profile.json`). A profile
    kept anywhere else - an operator's own - has no installer's record to be
    judged by: ([], None), and `runner.checkout_refusal` still guards each
    launch (LP-PROD-W2)."""
    profile = Path(profile)
    setup = EnvironmentSetup(profile.parent.parent, onboarding=None)
    if setup.root != profile.parent:
        return [], None
    return setup.profile_staleness(cfg)


def service_unit(state_dir, port, repo=REPO) -> str:
    """The systemd user unit that runs this checkout's Control Center
    (LP-PROD-E): `carbon-control-center` on loopback, restarted on failure.

    Its output, which carries the session token, goes to an owner-only file
    in the owner-only state directory rather than to the journal, unbuffered:
    Python block-buffers output to a file, so without it the token line
    would reach the file only when the Control Center exits (review finding,
    2026-10-03). Every path must be absolute and plain (no space, quote, `%`
    or `$`), so nothing in it is expanded or split by systemd.
    """
    state_dir, repo = Path(state_dir), Path(repo)
    binary = repo / ".venv" / "bin" / "carbon-control-center"
    log = state_dir / "control-center.log"
    for path in (state_dir, repo, binary, log):
        if not _UNIT_PATH.fullmatch(str(path)):
            raise ValueError("service_paths_must_be_plain_absolute_paths")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("service_port_must_be_unprivileged")
    return (
        "# Written by scripts/install_miner.sh (LP-PROD-E); it rewrites this\n"
        "# file on every install. Loopback only: nothing here is public.\n"
        "[Unit]\n"
        "Description=Carbon Control Center (DEVELOPMENT, loopback only)\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={repo}\n"
        f"ExecStart={binary} --state-dir {state_dir} --port {port}\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        "UMask=0077\n"
        f"StandardOutput=append:{log}\n"
        "StandardError=inherit\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


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
        self.lock = _SetupLock(self.root)

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
        record.pop(name + "_set_aside", None)  # Checked again.
        self._save(record)
        return self.state()

    @property
    def installation_path(self) -> Path:
        return self.root / INSTALLATION

    def installation(self) -> dict | None:
        """What the installer last installed here, or None when it never ran
        here (a developer's checkout). A record that is not one is refused,
        never read past."""
        path = self.installation_path
        if not path.exists() and not path.is_symlink():
            return None
        try:
            if not _owner_only(path) or path.stat().st_size > 64 * 1024:
                raise ValueError("installation record not owner-only")
            stamp = json.loads(path.read_bytes())
        except (OSError, ValueError):
            stamp = None
        if (
            type(stamp) is not dict
            or stamp.get("schema") != INSTALLATION_SCHEMA
            or type(stamp.get("revision")) is not str
            or type(stamp.get("images")) is not dict
        ):
            raise SetupRefused(
                "state_dir",
                "installation_record_unreadable",
                503,
                next_step=REINSTALL_STEP,
            )
        return stamp

    def _stale(self, compute) -> list[str]:
        """Why a checked compute step no longer describes this install, or
        [] when it still does (LP-PROD-E)."""
        return self._staleness(compute)[0]

    def _staleness(self, compute) -> tuple[list[str], str | None]:
        """Why a checked compute step no longer describes this install, and
        the one step that clears every reason: ([], None) when it still does
        (LP-PROD-E).

        The check pinned each image manifest it verified by digest; one
        rebuilt or removed since makes it stale. Once the installer has run
        here, so does a check made at another revision than the one it
        installed or than this checkout's, or with other images than the
        ones it built.

        Checking Compute again clears all of that while this checkout is the
        one the installer installed: a new check is made at HEAD, with the
        images setup fills in from the installer's record. When the checkout
        moved since (a `git pull`, or an update whose build failed after the
        checkout moved), or the record is unusable, a new check would be
        stale again for the same reason, so the step is the installer's
        (review finding, 2026-10-03: the miner was sent round a loop).
        """
        pinned = compute.get("manifests")
        manifests = _manifest_paths(compute)
        reasons = []
        if type(pinned) is not dict:
            reasons.append(STALE_UNPINNED)
        else:
            for field, path in manifests.items():
                found = _manifest(path)
                if found is None:
                    reasons.append(IMAGE_LABELS[field] + " is gone since the check")
                elif found["digest"] != pinned.get(field):
                    reasons.append(IMAGE_LABELS[field] + " was rebuilt since the check")
        drift, reinstall = self._install_drift(
            _revision_of(compute),
            manifests,
            made="the check was made at",
            other="setup checked another",
        )
        reasons += drift
        if not reasons:
            return [], None
        return reasons, REINSTALL_STEP if reinstall else RECHECK_STEP

    def _install_drift(self, revision, manifests, *, made, other):
        """Why `revision` and the image manifests at `manifests` ({field:
        path}) are not what the installer last installed here, and whether
        only the installer clears that: ([], False) when they are, or when it
        never ran here. One comparison for a compute check (`_staleness`) and
        for a runner profile (`profile_staleness`); `made` and `other` word
        each reason for the one judged."""
        try:
            stamp = self.installation()
        except SetupRefused:
            return ["the installer's record here is unreadable"], True
        reasons, reinstall = [], False
        if stamp is None:
            return reasons, reinstall
        if stamp["revision"] != revision:
            reasons.append(
                "Carbon was installed at "
                + stamp["revision"][:12]
                + " and "
                + made
                + " "
                + str(revision)[:12]
            )
        head = checkout_revision()
        if head != stamp["revision"]:
            reasons.append(
                "this checkout is at "
                + str(head)[:12]
                + ", not the "
                + stamp["revision"][:12]
                + " Carbon was installed at"
            )
            reinstall = True
        for field, entry in stamp["images"].items():
            if (
                field in manifests
                and type(entry) is dict
                and entry.get("path") != manifests[field]
            ):
                reasons.append(
                    other
                    + " "
                    + IMAGE_LABELS[field].removeprefix("the ")
                    + " than the one the installer built"
                )
        return reasons, reinstall

    def profile_staleness(self, cfg) -> tuple[list[str], str | None]:
        """Why a runner profile no longer describes what the installer
        installed here, and the one step that clears every reason: ([], None)
        when it still does, or when the installer never ran here.

        The controller attached `runner-profile.json` on every start, and an
        MCP door attached any profile it was given, whatever the installer
        had installed since; only `after_install` moved a stale one aside
        (LP-PROD-W2). This is the compute check's own comparison
        (`_install_drift`) applied to the profile's accepted revision and
        image manifests. A profile pins its worker and analysis images by
        image ID (`runtime.images`), not by manifest digest, so a manifest
        that is gone or names another image makes it stale too.

        Only the installer clears it when this checkout moved since the
        install or the installer's record is unusable; otherwise a compute
        check made now and Review write the profile again."""
        if not os.path.lexists(self.installation_path):
            return [], None
        manifests = _manifest_paths(cfg)
        reasons, reinstall = self._install_drift(
            cfg.get("accepted_revision"),
            manifests,
            made="this profile accepts",
            other="this profile names another",
        )
        runtime = cfg.get("runtime") if type(cfg.get("runtime")) is dict else {}
        images = runtime.get("images") if type(runtime.get("images")) is list else []
        for field, path in manifests.items():
            found = _manifest(path)
            position = PROFILE_IMAGE_POSITIONS.get(field)
            if found is None:
                reasons.append(
                    IMAGE_LABELS[field] + " is gone since this profile was written"
                )
            elif position is not None and images[position : position + 1] != [
                found["image_id"]
            ]:
                reasons.append(
                    IMAGE_LABELS[field] + " was rebuilt since this profile was written"
                )
        if not reasons:
            return [], None
        return reasons, REINSTALL_STEP if reinstall else PROFILE_RECHECK_STEP

    # -- the steps

    def state(self) -> dict:
        record = self._record()
        # Inference is needed only by an agent that calls setup's model.
        needed = [
            name
            for name in STEPS[:-1]
            if name != "inference" or _needs_inference(record)
        ]
        # A compute check that no longer describes this install shows as
        # unchecked, with why and the step that clears it (LP-PROD-E).
        stale, clears = (
            self._staleness(record["compute"]) if "compute" in record else ([], None)
        )
        done = {
            name: name in record and not (name == "compute" and stale)
            for name in needed
        }
        compute = _public(
            record.get("compute"), ("choice", "challenge", "remote_machine", "check")
        )
        if stale:
            compute = {**compute, "checked": False, "stale": stale, "next_step": clears}
        elif "compute_set_aside" in record and "compute" not in record:
            compute = {**compute, "set_aside": record["compute_set_aside"]}
        from scripts.dev.miner_launchpad import installed

        return {
            "schema": SETUP_SCHEMA,
            "registered_hotkey": record.get("hotkey"),
            # The images the installer built here, for setup to fill in.
            "installed": installed.read(self.root.parent),
            # Each image setup fills in, where it was found, or the one
            # command that builds it (LINKONLY-D10: no typed paths).
            "images": installed.found(self.root.parent, REPO),
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
                "compute": compute,
                "agent": _public(record.get("agent"), ("choice", "check")),
                "review": {
                    "ready": "hotkey" in record and all(done.values()),
                    "profile_written": "profile" in record,
                },
                # Setup's first step (LINKONLY-D10): the miner's signer
                # answered for this hotkey, by the same identity handshake the
                # Agent step makes. It counts only for the registered hotkey,
                # once there is one.
                "signer": self._signer(record),
                # Where a frozen candidate of each Challenge is evaluated:
                # Carbon's published endpoint, or the miner's own intake
                # (LP-PROD-E). Nothing to check: Review writes it.
                "evaluation": self._evaluation(record),
            },
        }

    def _evaluation(self, record) -> dict:
        """Each Challenge a frozen candidate is submitted to through an
        intake, and the intake its profile submits to: what Review wrote, or,
        before Review, what it will write. Says plainly when none is
        published."""
        published = published_endpoints()
        written = (record.get("profile") or {}).get("intakes")
        if "profile" in record and type(written) is not dict:
            # Written before Review recorded its intakes: they were the
            # miner's own, in the profile itself.
            written = {
                challenge_id: {"url": url, "source": "yours"}
                for challenge_id, url in self._own_intakes(record).items()
            }
        # The miner's own intakes in a profile an update set aside: Review
        # writes only what it is given, so setup says to name them again.
        kept = {}
        if type(written) is not dict:
            kept = (record.get("profile_set_aside") or {}).get("intakes") or {}
        challenges = []
        for challenge in intake_challenges():
            entry = published["endpoints"].get(challenge["id"])
            receiver = None
            if type(written) is dict:
                mine = written.get(challenge["id"])
                intake = mine.get("url") if type(mine) is dict else None
                source = mine.get("source") if type(mine) is dict else None
                receiver = mine.get("receiver") if type(mine) is dict else None
            else:
                intake = entry["intake_url"] if entry else None
                source = "published" if entry else None
                if "profile" not in record and entry is not None:
                    # Before Review: the receiver it will pin.
                    receiver = entry["receiver_hotkey"]
            item = {**challenge, "intake": intake, "source": source}
            if type(receiver) is str:
                # Binding (LAUNCHPAD-ACCEPT-03): see RECEIVER_NOTE.
                item["receiver_hotkey"] = receiver
                item["receiver_hotkey_note"] = RECEIVER_NOTE
            elif intake is not None and "profile" in record:
                # Written before receivers were pinned: it keeps working,
                # unchecked, and setup says to review again.
                item["receiver_hotkey_warning"] = RECEIVER_NOT_PINNED.format(
                    title=challenge["title"]
                )
            if intake is None:
                item["note"] = NO_ENDPOINT.format(title=challenge["title"])
                if entry is not None:
                    item["note"] = (
                        "An evaluation endpoint has been published for "
                        + challenge["title"]
                        + " since your profile was written: review again to "
                        "add it."
                    )
            own = kept.get(challenge["id"])
            if type(own) is dict and type(own.get("url")) is str:
                item["set_aside_intake"] = own["url"]
                if type(own.get("receiver")) is str:
                    item["set_aside_receiver"] = own["receiver"]
                item["note"] = KEPT_INTAKE_NOTE.format(title=challenge["title"])
            challenges.append(item)
        return {
            "published_by": PUBLISHED_SOURCE,
            "ready": all(item["intake"] for item in challenges),
            "challenges": challenges,
            **({"problem": published["problem"]} if published["problem"] else {}),
        }

    @staticmethod
    def _signer(record) -> dict:
        signer = record.get("signer")
        if signer is None or record.get("hotkey") not in (None, signer["hotkey"]):
            return {"checked": False}
        return {
            "checked": True,
            "checked_at": signer["checked_at"],
            "hotkey": signer["hotkey"],
            "check": signer["check"],
        }

    def signer(self, value) -> dict:
        """Ask the miner's signer which hotkey it holds, before or after
        registration: the identity handshake only, nothing is signed and
        nothing leaves this machine. `address` is the public hotkey address
        whose signer socket is asked."""
        _closed(value, {"address"}, {"signer_socket"})
        address = value["address"]
        if type(address) is not str or not _ADDRESS.fullmatch(address):
            raise SetupRefused("address", "hotkey_address_required")
        socket_path = (
            _absolute(value["signer_socket"], "signer_socket")
            if value.get("signer_socket")
            else None
        )
        check = self.checks.agent(address, socket_path)
        with self.lock:
            record = self._record()
            if record.get("hotkey") not in (None, address):
                raise SetupRefused("address", "signer_hotkey_is_not_the_registered_one")
            record["signer"] = {
                "hotkey": address,
                "check": check,
                "checked_at": int(time.time()),
            }
            self._save(record)
        return self.state()

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
        """Check the model with the miner's key, at their cost, on consent.

        The key arrives one of two ways: pasted once on the loopback page
        (`key`), written here to an owner-only file; or as `model_key_file`, the
        absolute path to an owner-only file the miner made, which an agent
        names and Carbon references without copying it. The MCP door accepts
        only the path (`setup_operations`).
        """
        _closed(
            value,
            {"provider_id", "model_id", "consent"},
            {"key", "model_key_file", "endpoint", "declared_pricing"},
        )
        if "key" in value and "model_key_file" in value:
            raise SetupRefused("model_key_file", "key_or_model_key_file_not_both")
        provider = self._inference_choice(value)
        stored = self.root / "keys" / (provider + ".key")
        named = (
            _owner_only_key_file(value["model_key_file"])
            if "model_key_file" in value
            else None
        )
        credential_file = named or stored
        spec = self._spec(provider, value)
        _consented(
            value, check_quote(provider, value["model_id"], credential_file, spec)
        )
        with self.lock:
            record = self._record()
            if "hotkey" not in record:
                raise SetupRefused("address", "registration_not_confirmed")
            if "key" in value:
                write_private(stored, _secret(value["key"], "key"))
            elif named is None:
                # Neither given: the file named or written before, if any.
                previous = (record.get("inference") or {}).get("credential_file")
                if previous and record["inference"].get("provider_id") == provider:
                    credential_file = _owner_only_key_file(previous)
                elif not stored.exists():
                    raise SetupRefused(
                        "model_key_file", "field_required", next_step=KEY_FILE_STEP
                    )
            check = self.checks.inference(
                provider, value["model_id"], credential_file, spec
            )
            return self._step(
                "inference",
                {
                    "provider_id": provider,
                    "model_id": value["model_id"],
                    "credential_file": str(credential_file),
                    **spec,
                    "check": check,
                },
            )

    def _forget_compute_keys(self) -> bool:
        """Delete Carbon's stored copies of rented-GPU provider keys.

        The retired route (OWNER-MINER-COMPUTE-LINK-ONLY-01) kept the miner's
        provider key here. Nothing reads it any more, so it is removed rather
        than kept, as the Agent step removes a stored hotkey password. Only
        Carbon's copy goes: the key itself is the miner's to revoke.
        """
        removed = False
        keys = self.root / "keys"
        if keys.is_dir() and not keys.is_symlink():
            for path in keys.glob(RETIRED_COMPUTE_KEYS):
                path.unlink(missing_ok=True)
                removed = True
        return removed

    def compute(self, value) -> dict:
        if type(value) is dict and value.get("choice") == RETIRED_RENTED_GPU:
            # Refused by name before the closed check, so a request from an
            # earlier page is told what changed, not that a field is unknown.
            with self.lock:
                self._forget_compute_keys()
            raise SetupRefused(
                "choice", retired.RENTED_GPU_RETIRED, next_step=retired.NEXT_STEP
            )
        _closed(
            value,
            {"choice", "image_manifest", "analysis_image_manifest"},
            {"gpu_image_manifest", "challenge", "remote"},
        )
        if value["choice"] not in (LOCAL_CPU, LOCAL_GPU, REMOTE):
            raise SetupRefused("choice", "compute_not_offered")
        # The remote choice runs the GPU practice program too, on the miner's
        # own setup: it needs the GPU worker and the Challenge as well.
        gpu = value["choice"] in (LOCAL_GPU, REMOTE)
        remote = value["choice"] == REMOTE
        if gpu != ("gpu_image_manifest" in value):
            raise SetupRefused(
                "gpu_image_manifest",
                "field_required" if gpu else "gpu_image_is_for_the_gpu_choice",
            )
        if gpu != ("challenge" in value):
            raise SetupRefused(
                "challenge",
                "field_required" if gpu else "challenge_is_for_the_gpu_choice",
            )
        if remote != ("remote" in value):
            raise SetupRefused(
                "remote",
                "field_required" if remote else "remote_is_for_the_remote_choice",
            )
        campaign = _gpu_campaign(value["challenge"]) if gpu else None
        if remote and campaign.remote_worker is None:
            raise SetupRefused("challenge", "challenge_offers_no_remote_practice")
        machine = _remote_machine(value["remote"]) if remote else None
        paths, manifests = {}, {}
        fields = ("image_manifest", "analysis_image_manifest") + (
            ("gpu_image_manifest",) if gpu else ()
        )
        for field in fields:
            path = _absolute(value[field], field)
            found = _manifest(path)
            if found is None:
                raise SetupRefused(
                    field, "image_not_built", next_step=BUILD_STEPS[field]
                )
            paths[field] = str(path)
            # Each manifest this check verifies, pinned by digest: one rebuilt
            # or removed afterwards makes the check stale (LP-PROD-E).
            manifests[field] = found["digest"]
        gpu_image = paths.pop("gpu_image_manifest", None)
        with self.lock:
            runtime = self.checks.compute(
                Path(paths["image_manifest"]), Path(paths["analysis_image_manifest"])
            )
            check = {
                "revision": runtime["implementation"]["revision"],
                "images": runtime["images"],
                "balance": "not applicable: your own machine",
            }
            step = {
                "choice": value["choice"],
                "paths": paths,
                "manifests": manifests,
            }
            if gpu:
                # GPU practice is set up for one Challenge, the miner's choice.
                step["challenge"] = dict(value["challenge"])
                check["challenge"] = value["challenge"]["id"]
                step["gpu_image"] = gpu_image
            if value["choice"] == LOCAL_GPU:
                detected = self.checks.gpu(Path(gpu_image), campaign=campaign)
                runtime = {**runtime, "gpu_research": [detected["scope"]]}
                check.update(
                    gpu=detected["device_kind"],
                    device_record=detected["record_digest"],
                    gpu_image=detected["scope"]["image"],
                    note=SPEED_ONLY_NOTE,
                )
            if remote:
                found = self.checks.remote(Path(gpu_image), machine, campaign)
                runtime = {
                    **runtime,
                    "gpu_research": [found["scope"]],
                    "remote_gpu": [found["remote_scope"]],
                }
                # Where it is stays in the profile, never in a campaign.
                step["remote_machine"] = machine.document()
                check.update(
                    remote=found["check"],
                    gpu_image=found["scope"]["image"],
                    balance="not applicable: your own setup, never billed by Carbon",
                    note=SPEED_ONLY_NOTE,
                )
                if found["check"].get("worker_image") == "missing":
                    check["next_step"] = "send your worker"
            if self._forget_compute_keys():
                check["retired_compute_key"] = COMPUTE_KEY_REMOVED
            return self._step("compute", {**step, "runtime": runtime, "check": check})

    def send_worker(self, value) -> dict:
        """Send the pinned GPU worker to the miner's own machine with Docker.

        A step of its own, with consent: the request must name the
        destination (and port) and the worker's image ID exactly as the
        checked compute step records them, so a page that changed either
        sends nothing. It streams `docker save <image id> | ssh <destination>
        docker load` over the miner's own SSH, checks the image ID arrived,
        and may take minutes. Nothing else is sent, and nothing is started.
        """
        from carbon.compute.remote_transport import SSH_DOCKER, RemoteMachine

        _closed(value, {"consent"})
        with self.lock:
            record = self._record()
            compute = record.get("compute") or {}
            if compute.get("choice") != REMOTE:
                raise SetupRefused("compute", "step_not_checked")
            machine = RemoteMachine.from_document(compute["remote_machine"])
            if machine.transport != SSH_DOCKER:
                raise SetupRefused("transport", "send_worker_is_for_ssh_docker")
            image_id = compute["runtime"]["remote_gpu"][0]["image"]
            expected = {
                "destination": machine.destination,
                **({"port": machine.port} if machine.port is not None else {}),
                "image": image_id,
            }
            if value["consent"] != {"send": expected}:
                raise SetupRefused(
                    "consent", "consent_must_name_the_destination_and_image"
                )
            sent = self.checks.send_worker(
                Path(compute["gpu_image"]), machine, image_id
            )
            check = dict(compute["check"])
            check["remote"] = {**check["remote"], "worker_image": "present"}
            check["worker"] = sent
            check.pop("next_step", None)
            record["compute"] = {**compute, "check": check}
            self._save(record)
        return self.state()

    def offered(self) -> dict:
        """What each step offers, with the exact files a Hermes choice writes."""
        from scripts.dev.miner_launchpad import installed

        found = installed.found(self.root.parent, REPO)["gpu_image_manifest"]
        value = choices(gpu_manifest=found["path"])
        # How the miner starts their signer: the first step, before setup can
        # ask it anything (the Agent step's check confirms it).
        value["signer"] = {"command": signer_command(), "checked_by": "agent"}
        # The Challenges a frozen candidate can be submitted to through a
        # validator's intake, each named in review (C-MLP-04).
        value["intake_challenges"] = intake_challenges()
        for choice in value["agent"]:
            if choice["id"] == HERMES:
                choice["writes"] = self.checks.hermes_files()
            if choice["id"] == OWN_AGENT:
                # The command for this controller's own setup records.
                choice["connect"] = mcp_connect(self.root.parent)
        return value

    def _hermes_consent(self, value) -> None:
        """The miner's consent must name exactly the files Hermes' profile
        writes."""
        consent = value.get("consent")
        if (
            type(consent) is not dict
            or consent.get("writes") != self.checks.hermes_files()
        ):
            raise SetupRefused("consent", "consent_must_name_the_files")

    def _hermes_document(self, value):
        """The Hermes profile for this setup's inference choice, or a refusal.

        The miner's consent must name exactly the files it writes.
        """
        from scripts.dev.miner_launchpad import hermes_setup

        self._hermes_consent(value)
        inference = self._record().get("inference")
        if inference is None:
            raise SetupRefused("inference", "step_not_checked")
        try:
            base_url = hermes_setup.model_base_url(
                inference["provider_id"], inference.get("endpoint")
            )
        except hermes_setup.HermesUnavailable as refused:
            raise SetupRefused(
                refused.field, refused.code, next_step=refused.next_step
            ) from None
        document = hermes_setup.config_document(
            model_id=inference["model_id"],
            base_url=base_url,
            runner_profile=self.profile_path,
            repo=REPO,
        )
        key = Path(self._credential(inference)).read_text()
        return document, key

    def _credential(self, inference) -> str:
        """The key file the checked inference step used: the one the miner
        named, or the one written from the page."""
        return inference.get("credential_file") or str(
            self.root / "keys" / (inference["provider_id"] + ".key")
        )

    def agent(self, value) -> dict:
        """Who researches (setup step 3): Graphite (Carbon's agent), the
        miner's own agent over MCP, or Hermes with its ready-made profile.
        Each asks the miner's signer which hotkey it holds and reads the
        network.

        Hermes' profile is written with setup's model: at once when Inference
        is already checked, otherwise at Review, on the consent given here.
        """
        from carbon.chain.models import CARBON_NETUID

        # `operator_config` is for an operator running Carbon's own deployment;
        # a miner names none, and setup reads the network itself (C-MLP-04).
        _closed(value, {"choice"}, {"operator_config", "signer_socket", "consent"})
        if value["choice"] == AUTONOMOUS:
            # Graphite replaced it for new setups (OWNER-GRAPHITE-MINER-01).
            raise SetupRefused("choice", "autonomous_agent_replaced")
        if value["choice"] not in AGENT_CHOICES:
            raise SetupRefused("choice", "agent_not_offered")
        if value["choice"] != HERMES and "consent" in value:
            raise SetupRefused("consent", "nothing_to_consent_to")
        operator = None
        if value.get("operator_config"):
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
            hermes = None
            if value["choice"] == HERMES:
                if "inference" in record:
                    hermes = self._hermes_document(value)
                else:
                    # Written at Review, once the model is checked.
                    self._hermes_consent(value)
            check = self.checks.agent(record["hotkey"], socket_path)
            if value["choice"] == HERMES and hermes is None:
                check = {**check, "hermes_profile": "written at review"}
            if hermes is not None:
                # Written only after the signer answered, so a refused setup
                # leaves the miner's Hermes untouched.
                check = {
                    **check,
                    **self.checks.hermes(*hermes),
                    "profile": "carbon",
                    "start": START,
                    "tools_ask_first": True,
                }
            # A password stored by an earlier version of this page is no
            # longer needed by anything: remove it rather than keep a secret.
            (self.root / "miner-password").unlink(missing_ok=True)
            public = write_private(
                self.root / "miner-public.json",
                canonical({"netuid": CARBON_NETUID, "hotkey": record["hotkey"]}),
            )
            paths = {"miner_public": str(public)}
            if operator is not None:
                paths["operator_config"] = str(operator)
            else:
                network, block = self.checks.network()
                paths["miner_network"] = str(
                    write_private(self.root / "miner-network.json", canonical(network))
                )
                check = {
                    **check,
                    "publisher": network["publisher_hotkey"],
                    "network_block": block,
                }
            if socket_path is not None:
                paths["signer_socket"] = str(socket_path)
            return self._step(
                "agent",
                {"choice": value["choice"], "paths": paths, "check": check},
            )

    def profile(self) -> dict:
        """The runner profile the checked steps describe, validated."""
        from scripts.dev.miner_launchpad.runner import PROFILE_SCHEMA, validated_profile

        record = self._record()
        # Inference only for an agent that calls setup's model; the miner's
        # own agent brings its own (OWNER-MINER-SETUP-AGENT-FIRST-01).
        for step in ("agent", "inference", "compute"):
            if step not in record and (step != "inference" or _needs_inference(record)):
                raise SetupRefused(step, "step_not_checked")
        inference, compute, agent = (
            record.get(s) for s in ("inference", "compute", "agent")
        )
        if compute.get("choice") == RETIRED_RENTED_GPU or retired.declares_rented(
            compute.get("runtime")
        ):
            # A compute step checked by an earlier page for a rented GPU: it
            # is set up again, never written into a profile.
            raise SetupRefused(
                "compute", retired.RENTED_GPU_RETIRED, next_step=retired.NEXT_STEP
            )
        stale, clears = self._staleness(compute)
        if stale:
            # Observed 2026-10-03: after a reinstall at a new revision, Review
            # wrote a profile with the old accepted revision. A check that no
            # longer describes this install is never written (LP-PROD-E). The
            # next step is the one that clears every reason.
            raise SetupRefused(
                "compute",
                "compute_check_is_stale",
                next_step=clears + ": " + "; ".join(stale),
            )
        key = (
            self._credential(inference)
            if inference
            else str(self.root / "keys" / NO_MODEL_KEY)
        )
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
            **({"gpu_image": compute["gpu_image"]} if "gpu_image" in compute else {}),
            # Where the miner's remote setup is: the profile's, never a
            # campaign's (LINKONLY-D9).
            **(
                {"remote_machine": compute["remote_machine"]}
                if "remote_machine" in compute
                else {}
            ),
        }
        if inference:
            cfg["provider_credentials"] = {inference["provider_id"]: key}
            cfg["model_selection"] = {
                "provider_id": inference["provider_id"],
                "model_id": inference["model_id"],
                **{
                    k: inference[k]
                    for k in ("endpoint", "declared_pricing", "published_pricing")
                    if k in inference
                },
            }
        try:
            return validated_profile(cfg)
        except ValueError:
            raise SetupRefused("review", "profile_invalid") from None

    def review(self, value) -> dict:
        """Write the profile and load it into the controller.

        `intakes`, optional, maps a Challenge id to the validator intake a
        frozen candidate of that Challenge is submitted to when its validator
        runs elsewhere (C-MLP-03 slice 6, per Challenge since C-MLP-04). Each
        intake's public facts are checked first, by that Challenge's own
        campaign. A legacy `battery_intake` is read as the intake of the
        Challenge it was written for.

        Every other Challenge submitted through an intake gets the
        evaluation endpoint Carbon publishes for it (LP-PROD-E). A published
        endpoint was reviewed into `published_endpoints.json` and is checked
        by the intake client when a candidate is submitted, so Review reaches
        no network for it. A Challenge with no endpoint is never passed over
        silently: the profile is written and `warnings` says it cannot
        submit there, and setup's Evaluation step keeps saying so.

        Each intake's receiver hotkey is pinned in the profile's `receivers`
        (LAUNCHPAD-ACCEPT-03): a published endpoint's `receiver_hotkey`, or,
        for the miner's own intake, the `receiver_hotkey` named beside it
        (`receivers` maps several), which is required. The own intake's
        public facts must report that receiver, or Review refuses
        `intake_receiver_mismatch`.
        """
        return self._review(value)

    def _review(self, value, unpinned=frozenset()) -> dict:
        """Review, where `unpinned` names the Challenges whose own intake was
        written before receivers were pinned and is written again without
        one (an update's Review, `after_install`): kept working, with a
        warning, rather than stranded."""
        from carbon.challenge_registry import ResolutionError
        from carbon.challenge_registry.campaigns import campaign_for_id
        from scripts.dev.miner_launchpad.runner import (
            LEGACY_INTAKE,
            _intake_url,
            _legacy_challenge,
        )

        _closed(
            value,
            {"confirm"},
            {"intakes", LEGACY_INTAKE, "receiver_hotkey", "receivers"},
        )
        if value["confirm"] is not True:
            raise SetupRefused("confirm", "review_needs_confirmation")
        intakes = value.get("intakes", {})
        if type(intakes) is not dict:
            raise SetupRefused("intakes", "intakes_map_challenge_ids_to_urls")
        intakes = dict(intakes)
        if LEGACY_INTAKE in value:
            intakes.setdefault(_legacy_challenge(), value[LEGACY_INTAKE])
        campaigns = {}
        for challenge_id, url in intakes.items():
            if not _intake_url(url):
                raise SetupRefused("intakes", "intake_url_invalid")
            try:
                campaigns[challenge_id] = campaign_for_id(challenge_id)
            except (ResolutionError, TypeError):
                raise SetupRefused("intakes", "challenge_not_implemented") from None
            if campaigns[challenge_id].intake_check is None:
                raise SetupRefused("intakes", "challenge_has_no_intake")
        receivers = _named_receivers(value, intakes, unpinned)
        for challenge_id, url in intakes.items():
            facts = self.checks.intake(url, campaign=campaigns[challenge_id])
            pinned = receivers.get(challenge_id)
            if pinned is not None and facts.get("receiver") != pinned:
                raise SetupRefused(
                    "receiver_hotkey",
                    "intake_receiver_mismatch",
                    next_step=RECEIVER_MISMATCH_STEP,
                )
        sources = {challenge_id: "yours" for challenge_id in intakes}
        published = published_endpoints()
        warnings = [
            {
                "code": "intake_receiver_not_pinned",
                "challenge": challenge["id"],
                "message": RECEIVER_NOT_PINNED.format(title=challenge["title"]),
            }
            for challenge in intake_challenges()
            if challenge["id"] in intakes and challenge["id"] not in receivers
        ]
        if published["problem"]:
            warnings.append(
                {
                    "code": published["problem"],
                    "message": "Carbon's list of evaluation endpoints could not "
                    "be read, so none was written: " + REINSTALL_STEP + ".",
                }
            )
        for challenge in intake_challenges():
            if challenge["id"] in intakes:
                continue
            entry = published["endpoints"].get(challenge["id"])
            if entry is None:
                warnings.append(
                    {
                        "code": "no_evaluation_endpoint",
                        "challenge": challenge["id"],
                        "message": NO_ENDPOINT.format(title=challenge["title"]),
                    }
                )
                continue
            intakes[challenge["id"]] = entry["intake_url"]
            receivers[challenge["id"]] = entry["receiver_hotkey"]
            sources[challenge["id"]] = "published"
        with self.lock:
            cfg = self.profile()
            if intakes:
                cfg = {**cfg, "intakes": intakes}
            if receivers:
                cfg = {**cfg, "receivers": receivers}
            record = self._record()
            agent = record["agent"]
            if agent.get("check", {}).get("hermes_profile") == "written at review":
                # Hermes chosen before the model: its profile now, on the
                # consent to these exact files given at the Agent step.
                written = self.checks.hermes(
                    *self._hermes_document(
                        {"consent": {"writes": self.checks.hermes_files()}}
                    )
                )
                agent["check"] = {
                    **agent["check"],
                    **written,
                    "hermes_profile": "carbon",
                    "start": START,
                    "tools_ask_first": True,
                }
            write_private(self.profile_path, canonical(cfg))
            record["profile"] = {
                "written_at": int(time.time()),
                # Each intake written and whose it is, so setup shows them and
                # an update keeps the miner's own (LP-PROD-E).
                "intakes": {
                    challenge_id: {
                        "url": url,
                        "source": sources[challenge_id],
                        **(
                            {"receiver": receivers[challenge_id]}
                            if challenge_id in receivers
                            else {}
                        ),
                    }
                    for challenge_id, url in intakes.items()
                },
                "warnings": warnings,
            }
            # A profile an update set aside is replaced by this one.
            record.pop("profile_set_aside", None)
            self._save(record)
        attached = self.attach(self.profile_path) if self.attach is not None else False
        return {**self.state(), "attached": attached, "warnings": warnings}

    def _own_intakes(self, record) -> dict:
        """The intakes the miner named in their last Review, which an update
        writes again; Carbon's published ones are looked up afresh."""
        written = (record.get("profile") or {}).get("intakes")
        if type(written) is dict:
            return {
                challenge_id: entry["url"]
                for challenge_id, entry in written.items()
                if type(entry) is dict
                and entry.get("source") == "yours"
                and type(entry.get("url")) is str
            }
        # A profile Review wrote before it recorded whose each intake was:
        # every intake in it was the miner's own; none was published then.
        from scripts.dev.miner_launchpad.runner import intakes

        try:
            if not _owner_only(self.profile_path):
                return {}
            cfg = json.loads(self.profile_path.read_bytes())
            return {
                challenge_id: url
                for challenge_id, url in intakes(cfg).items()
                if type(challenge_id) is str and type(url) is str
            }
        except (OSError, ValueError, TypeError, AttributeError):
            return {}

    def _own_receivers(self, record) -> dict:
        """The receiver hotkeys the miner's last Review pinned beside their
        own intakes (LAUNCHPAD-ACCEPT-03); none for a Review from before."""
        written = (record.get("profile") or {}).get("intakes")
        if type(written) is not dict:
            return {}
        return {
            challenge_id: entry["receiver"]
            for challenge_id, entry in written.items()
            if type(entry) is dict
            and entry.get("source") == "yours"
            and type(entry.get("url")) is str
            and type(entry.get("receiver")) is str
        }

    def _set_profile_aside(self) -> str | None:
        """Move the written runner profile, if any, to `STALE_PROFILE` in the
        same owner-only directory, replacing an earlier one, and return its
        new name; None when there was none. The controller attaches
        `runner-profile.json` on start whenever it exists, so a profile whose
        compute check was set aside must not stay there. Called under the
        setup lock."""
        path = self.profile_path
        if not os.path.lexists(path):
            return None
        os.replace(path, self.root / STALE_PROFILE)
        return STALE_PROFILE

    def after_install(self) -> dict:
        """What a (re)install changed for this setup, and what it did about
        it (LP-PROD-E). `scripts/install_miner.sh` runs it once it has built
        and recorded the images.

        Observed live 2026-10-03: after a reinstall at a new revision, setup
        still showed compute as checked, at the old revision and images, and
        Review wrote a profile with the old accepted revision. So:
        1. What was installed is recorded: the checkout's revision and each
           recorded image manifest's digest and image ID.
        2. A compute check that no longer describes it is set aside, with
           why, and the profile with it: the marker, and the profile file,
           moved to `STALE_PROFILE`, since a restarted Control Center
           attaches `runner-profile.json` whenever it exists (review
           finding, 2026-10-03). The miner's own intakes in it are kept in
           the record, so setup can say to name them again.
        3. This machine's compute (CPU, or its own GPU) is checked again with
           the new images: no network and no cost, as in setup. The miner's
           own remote setup is never reached: they check it again, since it
           needs the new GPU worker.
        4. A profile written before is written again by Review, with the
           intakes the miner named and the endpoints Carbon publishes.
        Each refusal is reported with its next step; nothing is retried.
        """
        from scripts.dev.miner_launchpad import installed

        recorded = installed.read(self.root.parent) or {}
        if not {"image_manifest", "analysis_image_manifest"} <= set(recorded):
            raise SetupRefused(
                "image_manifest",
                "installed_images_not_recorded",
                next_step=REINSTALL_STEP,
            )
        head = checkout_revision()
        if head is None:
            raise SetupRefused(
                "accepted_revision",
                "clean_accepted_checkout_required",
                next_step=REINSTALL_STEP,
            )
        images = {}
        for field, path in recorded.items():
            found = _manifest(path)
            if found is not None:
                images[field] = found
        stamp = {
            "schema": INSTALLATION_SCHEMA,
            "revision": head,
            "images": images,
            "installed_at": int(time.time()),
        }
        report = {"revision": {"to": head}, "images": {}, "next_steps": []}
        with self.lock:
            try:
                before = self.installation()
            except SetupRefused:
                before = None
            record = self._record()
            compute = record.get("compute")
            write_private(self.installation_path, canonical(stamp))
            # What was installed before: the installer's last record, or,
            # the first time it runs here, what the compute check recorded.
            was = {}
            if before is not None:
                report["revision"]["from"] = before["revision"]
                was = {
                    field: entry.get("image_id")
                    for field, entry in before["images"].items()
                    if type(entry) is dict
                }
            elif compute is not None:
                report["revision"]["from"] = _revision_of(compute)
                checked = (compute.get("runtime") or {}).get("images") or []
                was = dict(zip(("image_manifest", "analysis_image_manifest"), checked))
            for field, found in images.items():
                report["images"][field] = {
                    "from": was.get(field),
                    "to": found["image_id"],
                }
            if compute is None:
                report["compute"] = "not set up yet"
                return report
            stale = self._stale(compute)
            if not stale:
                report["compute"] = "unchanged"
                return report
            had_profile = "profile" in record
            own = self._own_intakes(record) if had_profile else {}
            pinned = self._own_receivers(record) if had_profile else {}
            now = int(time.time())
            record.pop("compute")
            record.pop("profile", None)
            record["compute_set_aside"] = {"reasons": stale, "at": now}
            moved = self._set_profile_aside()
            if had_profile or moved:
                record["profile_set_aside"] = {
                    "at": now,
                    **({"file": moved} if moved else {}),
                    "intakes": {
                        challenge_id: {
                            "url": url,
                            "source": "yours",
                            **(
                                {"receiver": pinned[challenge_id]}
                                if challenge_id in pinned
                                else {}
                            ),
                        }
                        for challenge_id, url in own.items()
                    },
                }
            self._save(record)
        report.update(compute="set aside", reasons=stale)
        if moved:
            report["profile_set_aside"] = moved
        if compute.get("choice") not in (LOCAL_CPU, LOCAL_GPU):
            report["next_steps"].append(
                REMOTE_RECHECK if compute.get("choice") == REMOTE else RECHECK_STEP
            )
            return report
        request = {
            "choice": compute["choice"],
            "image_manifest": recorded["image_manifest"],
            "analysis_image_manifest": recorded["analysis_image_manifest"],
        }
        if compute["choice"] == LOCAL_GPU:
            gpu = installed.found(self.root.parent, REPO)["gpu_image_manifest"]
            if gpu["path"] is None:
                report["next_steps"].append(
                    "build the GPU worker (" + gpu["build"] + "), then " + RECHECK_STEP
                )
                return report
            request.update(
                gpu_image_manifest=gpu["path"], challenge=dict(compute["challenge"])
            )
        try:
            self.compute(request)
        except SetupRefused as refused:
            report["recheck"] = _refusal(refused)
            report["next_steps"].append(RECHECK_STEP)
            return report
        report["compute"] = "checked again"
        if not had_profile:
            report["next_steps"].append("review in setup to write your profile")
            return report
        try:
            # The receivers the miner's last Review pinned are pinned again;
            # an own intake from before pinning is written again without
            # one, with a warning, rather than stranded (LAUNCHPAD-ACCEPT-03).
            reviewed = self._review(
                {
                    "confirm": True,
                    **({"intakes": own} if own else {}),
                    **({"receivers": pinned} if pinned else {}),
                },
                unpinned=frozenset(own) - set(pinned),
            )
        except SetupRefused as refused:
            report["profile"] = {"written": False, **_refusal(refused)}
            report["next_steps"].append("review in setup to write your profile")
            return report
        report["profile"] = {
            "written": True,
            "accepted_revision": head,
            "warnings": reviewed["warnings"],
        }
        return report


def _needs_inference(record) -> bool:
    """Whether setup's Inference step is part of this miner's path: yes until
    an agent is chosen, and for an agent that calls setup's model."""
    agent = record.get("agent")
    return agent is None or agent.get("choice") in USES_SETUP_MODEL


class _SetupLock:
    """One writer at a time over the setup records, in this process and in any
    other door onto them: the browser's controller and a miner's MCP server
    read and write the same files (OWNER-MINER-SETUP-AGENT-FIRST-01)."""

    def __init__(self, root: Path):
        self.root = root
        self.thread = threading.Lock()
        self.handle = None

    def __enter__(self):
        import fcntl

        self.thread.acquire()
        try:
            _private_dir(self.root)
            self.handle = os.open(
                self.root / "setup.lock",
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            fcntl.flock(self.handle, fcntl.LOCK_EX)
        except BaseException:
            if self.handle is not None:
                os.close(self.handle)
                self.handle = None
            self.thread.release()
            raise
        return self

    def __exit__(self, *exc):
        import fcntl

        try:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            os.close(self.handle)
        finally:
            self.handle = None
            self.thread.release()


def _owner_only_key_file(value) -> Path:
    """A model key file the miner made: an absolute path to a regular file,
    not a link, owned by this user, with no group or other access. Its
    content is not read here; only its own provider ever receives it."""
    path = _absolute(value, "model_key_file")
    try:
        stat = path.lstat()
    except OSError:
        raise SetupRefused(
            "model_key_file", "model_key_file_not_found", next_step=KEY_FILE_STEP
        ) from None
    import stat as kinds

    if (
        not kinds.S_ISREG(stat.st_mode)
        or stat.st_uid != os.getuid()
        or stat.st_mode & 0o077
        or not 1 <= stat.st_size <= 1024
    ):
        raise SetupRefused(
            "model_key_file", "model_key_file_not_owner_only", next_step=KEY_FILE_STEP
        )
    return path


#: How a miner makes a key file an agent may name (never the key itself).
KEY_FILE_STEP = (
    "put your model key alone in a file only you can read, for example: "
    "umask 077 && cat > ~/.carbon/model.key, then give its absolute path"
)


def _public(step, fields):
    if step is None:
        return {"checked": False}
    return {
        "checked": True,
        "checked_at": step["checked_at"],
        **{f: step[f] for f in fields if f in step},
    }


def _refusal(refused: SetupRefused) -> dict:
    """A refusal as a report states it: its code, field and next step."""
    return {
        "code": refused.code,
        "field": refused.field,
        **({"next_step": refused.next_step} if refused.next_step else {}),
    }


def _short(value) -> str:
    text = str(value)
    return text.removeprefix("sha256:")[:12]


def describe_install(report: dict) -> list[str]:
    """`after_install`'s report as the lines the installer prints."""
    lines = ["What this install changed:"]
    revision = report["revision"]
    if revision.get("from") and revision["from"] != revision["to"]:
        lines.append(
            "  Carbon: " + _short(revision["from"]) + " -> " + _short(revision["to"])
        )
    else:
        lines.append(
            "  Carbon: "
            + _short(revision["to"])
            + (", unchanged" if revision.get("from") else "")
        )
    for field, image in report["images"].items():
        label = IMAGE_LABELS[field].removeprefix("the ")
        label = label[0].upper() + label[1:]
        if image["from"] and image["from"] != image["to"]:
            lines.append(
                "  "
                + label
                + ": "
                + _short(image["from"])
                + " -> "
                + _short(image["to"])
            )
        else:
            lines.append(
                "  "
                + label
                + ": "
                + _short(image["to"])
                + (", unchanged" if image["from"] else "")
            )
    lines.append("Your setup:")
    compute = report.get("compute")
    if compute == "not set up yet":
        lines.append(
            "  Compute: not set up yet. Set up your environment in the Control Center."
        )
    elif compute == "unchanged":
        lines.append("  Compute: your check still describes this install.")
    else:
        lines.append(
            "  Compute: your earlier check was set aside ("
            + "; ".join(report.get("reasons", []))
            + ")."
        )
        if compute == "checked again":
            lines.append("  Compute: checked again with the new images.")
    if "recheck" in report:
        refused = report["recheck"]
        lines.append(
            "  Compute check refused: "
            + refused["code"]
            + " ("
            + refused["field"]
            + ")"
            + (". " + refused["next_step"] if "next_step" in refused else "")
        )
    profile = report.get("profile")
    if profile and profile["written"]:
        lines.append(
            "  Runner profile: written again, accepted revision "
            + _short(profile["accepted_revision"])
            + "."
        )
        for warning in profile["warnings"]:
            lines.append("  Note: " + warning["message"])
    elif profile:
        lines.append(
            "  Runner profile: not written: "
            + profile["code"]
            + (". " + profile["next_step"] if "next_step" in profile else "")
        )
    if report.get("profile_set_aside") and not (profile and profile["written"]):
        lines.append(
            "  Runner profile: set aside with the compute check, as environment/"
            + report["profile_set_aside"]
            + "; the Control Center will not load it."
        )
    for next_step in report.get("next_steps", []):
        lines.append("Next: " + next_step[0].upper() + next_step[1:] + ".")
    return lines


def main(argv=None) -> int:
    """The installer's commands (LP-PROD-E), run by scripts/install_miner.sh:
    `after-install` checks setup against what was just installed and prints
    what changed; `gpu-installed` says whether a GPU worker was built here
    before; `service-unit` prints the systemd user unit for the Control
    Center."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("after-install", "gpu-installed", "service-unit"):
        command = commands.add_parser(name)
        command.add_argument("--state-dir", type=Path, required=True)
        if name == "service-unit":
            command.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    state_dir = args.state_dir
    if args.command == "gpu-installed":
        from scripts.dev.miner_launchpad import installed

        found = installed.found(state_dir, REPO)["gpu_image_manifest"]["path"]
        print("yes" if found else "no")
        return 0
    if args.command == "service-unit":
        try:
            print(service_unit(state_dir, args.port), end="")
        except ValueError as refused:
            print("Carbon service unit refused: " + str(refused), file=sys.stderr)
            return 2
        return 0
    setup = EnvironmentSetup(state_dir, onboarding=None)
    try:
        report = setup.after_install()
    except SetupRefused as refused:
        print(
            "Carbon could not check your setup against this install: "
            + refused.code
            + " ("
            + refused.field
            + ")"
            + (". Next: " + refused.next_step if refused.next_step else ""),
            file=sys.stderr,
        )
        return 2
    print("\n".join(describe_install(report)))
    return 0


if __name__ == "__main__":
    # One module, whichever way it is run: the installer's commands use the
    # same classes the Control Center imports.
    from scripts.dev.miner_launchpad import environment_setup as module

    raise SystemExit(module.main())
