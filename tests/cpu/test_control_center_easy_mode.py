"""The Control Center's easy mode (LINKONLY-D10), held where the server makes it.

The owner, 2026-10-02: "we just need to help miners figure out what to do
easily." The page leads with one next step; these tests hold the server
facts it is built from, without a browser:
- each "Where's your GPU?" card takes the transport its own guide section
  names, and shows that section with its UNVERIFIED marks;
- the guide is text data served from this checkout, and links nowhere off
  the machine;
- setup fills in the images it finds and otherwise names one command;
- every blocking status has one plain sentence and keeps its code;
- Compute lists this machine and a GPU run elsewhere, side by side;
- the wordmark and font are the website's own files, served locally, and the
  page loads nothing from the internet.
No provider, chain, SSH or container is touched.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import threading
from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import capabilities, controller, guide, installed
from scripts.dev.miner_launchpad.environment_setup import (
    REMOTE,
    REMOTE_GUIDES,
    EnvironmentSetup,
    choices,
    guide_commands,
    signer_command,
)

ROOT = Path(__file__).resolve().parents[2]
LAUNCHPAD = ROOT / "scripts/dev/miner_launchpad"
MANIFEST = ROOT / "website/ask-carbon/production-baseline.manifest.json"
TOKEN = "z" * 40


def remote_choice(**kwargs):
    return {c["id"]: c for c in choices(**kwargs)["compute"]}[REMOTE]


def spans(blocks):
    """Every text span in parsed guide blocks, depth first."""
    for block in blocks:
        if block["type"] in ("heading", "paragraph"):
            yield from block["text"]
        elif block["type"] == "table":
            for row in [block["header"], *block["rows"]]:
                for cell in row:
                    yield from cell
        elif block["type"] == "list":
            stack = list(block["items"])
            while stack:
                item = stack.pop()
                yield from item["text"]
                stack.extend(item["items"])


# --- Where's your GPU? -------------------------------------------------------


def test_each_gpu_card_takes_the_transport_its_guide_section_names():
    from carbon.compute.remote_transport import BUILT, SSH_CONTAINER, SSH_DOCKER

    cards = {c["id"]: c for c in remote_choice()["guides"]["cards"]}
    assert list(cards) == [
        "runpod",
        "lium",
        "targon",
        "vast",
        "lambda",
        "own-server",
    ]
    # Container rentals are reached as ssh-container; machines and VMs with
    # Docker as ssh-docker. Only built transports are ever set.
    assert {i for i, c in cards.items() if c["transport"] == SSH_CONTAINER} == {
        "runpod",
        "lium",
        "vast",
    }
    assert {i for i, c in cards.items() if c["transport"] == SSH_DOCKER} == {
        "targon",
        "lambda",
        "own-server",
    }
    assert {c["transport"] for c in cards.values()} <= set(BUILT)
    # The map is held to the guide: each section's "Transport:" line names the
    # card's transport first. The specimen is a section that names both.
    for card in cards.values():
        first = card["steps"][0]["items"][0]["text"]
        assert first[0] == {"text": "Transport:", "strong": True}, card["id"]
        assert next(s["text"] for s in first if s.get("code")) == card["transport"]
    vast = guide.plain(cards["vast"]["steps"][0]["items"][0]["text"])
    assert "`" not in vast and "ssh-docker" in vast


def test_each_card_keeps_its_sections_unverified_marks():
    source = (ROOT / "docs/development/MINER_REMOTE_SETUP.md").read_text()
    sections = re.split(r"^### ", source, flags=re.MULTILINE)
    expected = {}
    for guide_id, _, _, heading in REMOTE_GUIDES:
        text = next(s for s in sections if s.startswith(heading + "\n"))
        text = text.split("\n## ", 1)[0]
        expected[guide_id] = text.count("**UNVERIFIED:**")
    for card in remote_choice()["guides"]["cards"]:
        shown = [
            s
            for s in spans(card["steps"])
            if s.get("strong") and s["text"].startswith("UNVERIFIED")
        ]
        assert len(shown) == expected[card["id"]], card["id"]
    # Specimen: the marks are there to keep - RunPod, Lium, Targon and Vast.ai
    # each carry some.
    assert all(expected[i] for i in ("runpod", "lium", "targon", "vast"))
    # The provenance note travels with the cards.
    notes = guide.plain(remote_choice()["guides"]["notes"][0]["text"])
    assert "Nothing here was run live" in notes


def test_a_container_rental_gets_the_push_helper_and_ssh_checks():
    container = guide_commands("runpod", "ssh-container", "/m/accelerator.json")
    machine = guide_commands("lambda", "ssh-docker", "/m/accelerator.json")
    push = container[0]["command"]
    assert push.endswith(
        "scripts/dev/push_worker_image.sh --manifest /m/accelerator.json"
        " <registry>/<you>/carbon-gpu-worker"
    )
    # Without a found worker the helper builds it: no --manifest is named.
    built = guide_commands("runpod", "ssh-container")[0]["command"]
    assert "--manifest" not in built and "push_worker_image.sh" in built
    # A machine with Docker is sent its worker by setup: nothing to push.
    assert not any("push_worker_image" in c["command"] for c in machine)
    for commands in (container, machine):
        checks = [c for c in commands if c.get("destination")]
        assert [c["command"] for c in checks] == [
            "ssh <destination>",
            "ssh -o BatchMode=yes <destination> true",
        ]
    # A provider's own documented command, as the guide quotes it.
    assert machine[-1]["command"] == 'sudo adduser "$(id -un)" docker'
    assert (
        'sudo adduser "$(id -un)" docker'
        in (ROOT / "docs/development/MINER_REMOTE_SETUP.md").read_text()
    )
    # Nothing asks for a key, a password or a provider account.
    text = json.dumps([container, machine]).lower()
    for forbidden in ("password", "api key", "api_key", "token"):
        assert forbidden not in text


def test_the_signer_command_names_placeholders_only():
    command = signer_command()
    assert command.endswith(" --wallet <your wallet> --hotkey <your hotkey>")
    assert "carbon-miner-signer" in command


def test_setup_checks_the_signer_first_by_its_public_address(tmp_path):
    """Step 1 asks the miner's signer which hotkey it holds, before
    registration if the miner likes: the Agent step's identity handshake,
    for a public address, recorded only for that hotkey."""
    from test_miner_launchpad_environment_setup import HOTKEY, Checks, Onboarding

    from scripts.dev.miner_launchpad.environment_setup import SIGNER_STEP, SetupRefused

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    checks = Checks()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    assert setup.state()["steps"]["signer"] == {"checked": False}
    checked = setup.signer({"address": HOTKEY})
    assert checked["registered_hotkey"] is None
    signer = checked["steps"]["signer"]
    assert (signer["checked"], signer["hotkey"]) == (True, HOTKEY)
    assert checks.calls[-1] == ("agent", HOTKEY, None)
    # Registering the same hotkey keeps it.
    assert setup.begin({"address": HOTKEY})["steps"]["signer"]["checked"] is True
    # Only an address is accepted: a phrase, or any other field, is refused
    # by name and nothing is asked.
    asked = len(checks.calls)
    for request, field, code in (
        (
            {"address": "bottom drive obey lake curtain"},
            "address",
            "hotkey_address_required",
        ),
        ({"address": HOTKEY, "key_file": "/k"}, "key_file", "unknown_field"),
    ):
        with pytest.raises(SetupRefused) as refused:
            setup.signer(request)
        assert (refused.value.field, refused.value.code) == (field, code)
    assert len(checks.calls) == asked
    # Once registered, a signer for another hotkey is refused.
    other = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    with pytest.raises(SetupRefused) as refused:
        setup.signer({"address": other})
    assert refused.value.code == "signer_hotkey_is_not_the_registered_one"

    # A signer checked for one hotkey does not count for another registered.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    second = EnvironmentSetup(elsewhere, onboarding=Onboarding(), checks=Checks())
    second.signer({"address": other})
    assert second.begin({"address": HOTKEY})["steps"]["signer"] == {"checked": False}

    # A signer that does not answer is refused by field, with how to start
    # it, and nothing is recorded.
    class Silent(Checks):
        def agent(self, hotkey, socket_path=None):
            raise SetupRefused("signer", "signer_not_running", next_step=SIGNER_STEP)

    quiet = tmp_path / "quiet"
    quiet.mkdir(mode=0o700)
    silent = EnvironmentSetup(quiet, onboarding=Onboarding(), checks=Silent())
    with pytest.raises(SetupRefused) as refused:
        silent.signer({"address": HOTKEY})
    assert (refused.value.field, refused.value.next_step) == ("signer", SIGNER_STEP)
    assert silent.state()["steps"]["signer"] == {"checked": False}


# --- the guide, served locally --------------------------------------------------


def test_the_guide_is_text_data_and_links_nowhere_off_the_machine():
    document = guide.document("remote-setup")
    assert document["available"] is True
    assert document["title"] == "Practising on your own remote machine or container"
    anchors = {b["anchor"] for b in document["blocks"] if b["type"] == "heading"}
    allowed = {"text", "strong", "code", "anchor"}
    linked = []
    for span in spans(document["blocks"]):
        assert set(span) <= allowed, span
        if "anchor" in span:
            linked.append(span["anchor"])
    # Every link resolves inside the guide; none carries a URL.
    assert linked and set(linked) <= anchors
    assert "http" not in json.dumps(document)
    # Specimen: the source does link within itself.
    assert (
        "](#why-there-is-no-endpoint-transport)"
        in (ROOT / guide.GUIDES["remote-setup"]).read_text()
    )


def test_a_missing_guide_is_reported_not_raised(tmp_path):
    document = guide.document("remote-setup", repo=tmp_path)
    assert document["available"] is False and document["blocks"] == []


@pytest.fixture
def server(tmp_path):
    served = controller.Server(
        controller.Controller(tmp_path / "runs.sqlite3"), TOKEN, 0
    )
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    yield served
    served.shutdown()
    served.server_close()
    thread.join(timeout=3)


def get(server, path, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    connection.request("GET", path, None, headers or {})
    response = connection.getresponse()
    result = (response.status, dict(response.getheaders()), response.read())
    connection.close()
    return result


def test_the_guide_route_serves_only_named_guides_behind_the_token(server):
    auth = {"Authorization": "Bearer " + TOKEN}
    assert get(server, "/api/v1/guide/remote-setup")[0] == 401
    status, _, body = get(server, "/api/v1/guide/remote-setup", auth)
    assert status == 200
    assert json.loads(body)["schema"] == guide.SCHEMA
    for name in ("other", "..%2F..%2Fsecrets", "remote-setup/../x"):
        status, _, body = get(server, "/api/v1/guide/" + name, auth)
        assert (status, json.loads(body)) == (404, {"error": "guide_not_found"})


# --- no typed paths -----------------------------------------------------------------


def test_setup_fills_in_the_images_it_finds_and_names_the_command_otherwise(
    tmp_path,
):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    repo = tmp_path / "checkout"
    repo.mkdir()
    nothing = installed.found(state, repo)
    for field in installed.FIELDS:
        assert nothing[field]["path"] is None and nothing[field]["found_by"] is None
    assert nothing["image_manifest"]["build"] == (
        str(repo / "scripts/install_miner.sh") + " --no-start"
    )
    assert nothing["gpu_image_manifest"]["build"] == str(
        repo / "scripts/dev/accelerator_worker_image.sh"
    )
    # The GPU worker where its build script writes it, found without a record.
    built = repo / installed.GPU_DEFAULT
    built.parent.mkdir(parents=True)
    built.write_text("{}")
    gpu = installed.found(state, repo)["gpu_image_manifest"]
    assert (gpu["path"], gpu["found_by"]) == (str(built), "accelerator_worker_image.sh")
    # The installer's record comes first, for every image it names.
    worker = tmp_path / "worker.json"
    worker.write_text("{}")
    installed.write(
        state,
        image_manifest=worker,
        analysis_image_manifest=worker,
        gpu_image_manifest=worker,
    )
    recorded = installed.found(state, repo)
    for field in installed.FIELDS:
        assert recorded[field] == {
            "path": str(worker),
            "found_by": "install_miner.sh",
            "build": recorded[field]["build"],
        }


def test_setup_state_and_offer_carry_what_was_found(tmp_path):
    from test_miner_launchpad_environment_setup import Checks, Onboarding

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    gpu = tmp_path / "gpu.json"
    gpu.write_text("{}")
    installed.write(
        state,
        image_manifest=gpu,
        analysis_image_manifest=gpu,
        gpu_image_manifest=gpu,
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    assert setup.state()["images"]["gpu_image_manifest"]["path"] == str(gpu)
    offered = setup.offered()
    assert offered["signer"]["command"] == signer_command()
    remote = {c["id"]: c for c in offered["compute"]}[REMOTE]
    runpod = next(c for c in remote["guides"]["cards"] if c["id"] == "runpod")
    assert "--manifest " + str(gpu) in runpod["commands"][0]["command"]


# --- plain statuses -----------------------------------------------------------------


@pytest.fixture
def host(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad.journey_fixture import journey_host

    root = tmp_path / "journey"
    root.mkdir(mode=0o700)
    runner = journey_host(root, patch=monkeypatch.setattr)
    yield runner
    runner.close()


def blocking(document):
    """Every blocking status the page shows, with where it sits."""
    found = []
    if not document["profile"]["configured"]:
        found.append(("profile", document["profile"]))
    for entry in document["challenges"]:
        if not entry["selectable"]:
            found.append((entry["challenge_id"], entry))
    for group, items in (
        ("agents", document["agents"]["choices"] + document["agents"]["unavailable"]),
        ("model", document["model"]["providers"] + document["model"]["unavailable"]),
        (
            "compute",
            document["compute"]["choices"] + document["compute"]["unavailable"],
        ),
        ("connections", document["connections"]),
        ("wallet", document["wallet"]),
    ):
        for item in items:
            if item.get("availability", "unavailable") == "unavailable":
                found.append((group, item))
    return found


@pytest.mark.parametrize("configured", [False, True])
def test_blocking_statuses_are_plain_with_their_codes_kept(configured, request):
    runner = request.getfixturevalue("host") if configured else None
    document = capabilities.control_center(runner)
    statuses = blocking(document)
    assert statuses
    for where, item in statuses:
        # The code and its full next action are kept for Details ...
        assert item["reason"] and item["next_action"], where
        plain = item["plain"]
        # ... and the miner reads one short sentence this map knows.
        assert plain["known"] is True, (where, item["reason"])
        assert plain["sentence"].endswith(".") and len(plain["sentence"]) <= 60
        assert item["reason"] not in plain["sentence"]
        if plain["next"] is not None:
            assert plain["next"]["href"].startswith("#") and plain["next"]["label"]
    if not configured:
        # Unconfigured, the fix is the one place a miner sets up.
        assert document["profile"]["plain"]["next"] == {
            "label": "Continue setup",
            "href": "#setup",
        }


def test_an_unknown_reason_is_marked_rather_than_invented():
    value = capabilities.plain("some_future_reason")
    assert value == {
        "sentence": "Not available here yet.",
        "next": None,
        "known": False,
    }


# --- Compute: this machine and a GPU elsewhere ----------------------------------


def test_compute_lists_this_machine_and_a_gpu_elsewhere():
    routes = capabilities.control_center(None)["compute"]["routes"]
    assert [r["id"] for r in routes] == ["this-machine", "remote-machine"]
    here, there = routes
    assert here["availability"] == "unavailable" and here["plain"]["known"]
    assert there["availability"] == "not_set_up"
    assert there["plain"]["next"] == {"label": "Set it up", "href": "#setup/compute"}
    assert there["started_stopped_and_billed_by"] == "you; Carbon never does"
    cfg = {
        "runtime": {"gpu_research": [{}], "remote_gpu": [{}]},
        "remote_machine": {"transport": "ssh-container", "destination": "root@pod"},
    }
    here, there = capabilities._routes(cfg, {"availability": "available"})
    assert (there["availability"], there["transport"]) == (
        "configured",
        "ssh-container",
    )
    assert there["in_use"] and not here["in_use"]
    # Where it is stays out of the capability document.
    assert "root@pod" not in json.dumps([here, there])


# --- Carbon's brand, served locally ------------------------------------------------


def test_the_bundled_font_and_wordmark_are_the_websites_own():
    """The owner, 2026-10-02: "Our license covers it, bundle the font"."""
    entries = {
        entry["path"]: entry for entry in json.loads(MANIFEST.read_text())["assets"]
    }
    for bundled, site in (
        ("fonts/neue-0.otf", "assets/neue-0.otf"),
        ("fonts/neue-1.otf", "assets/neue-1.otf"),
        ("brand/brand-2.svg", "assets/brand-2.svg"),
    ):
        data = (LAUNCHPAD / bundled).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entries[site]["sha256"], bundled
        assert len(data) == entries[site]["bytes"], bundled


def test_the_page_loads_nothing_from_the_internet(server):
    status, headers, page = get(server, "/")
    assert status == 200
    policy = headers["Content-Security-Policy"]
    for directive in ("font-src 'self'", "img-src 'self' blob:", "default-src 'none'"):
        assert directive in policy
    assert "http" not in policy
    for path, kind in (
        ("/fonts/neue-0.otf", "font/otf"),
        ("/fonts/neue-1.otf", "font/otf"),
        ("/brand/brand-2.svg", "image/svg+xml"),
    ):
        status, headers, body = get(server, path)
        assert (status, headers["Content-Type"]) == (200, kind)
        assert body == (LAUNCHPAD / controller.STATIC[path][0]).read_bytes()
    # The same host and origin checks as the page itself.
    assert get(server, "/fonts/neue-0.otf", {"Host": "attacker.example"})[0] == 403
    style = (LAUNCHPAD / "style.css").read_text()
    assert "font-family:Montreal" in style.replace(" ", "")
    for face in ("/fonts/neue-0.otf", "/fonts/neue-1.otf"):
        assert "url(" + face + ")" in style.replace('"', "")
    # Nothing on the page is fetched from anywhere else. The one http string in
    # the script is the SVG namespace, an identifier rather than a request.
    script = (LAUNCHPAD / "app.js").read_text()
    for text in (
        page.decode(),
        style,
        script.replace("http://www.w3.org/2000/svg", ""),
    ):
        assert not re.search(r"https?://", text)
