"""Actual disposable Docker namespace/mount controls; no operator acceptance.

Only synthetic loopback listeners, public marker files and an unused socket.
The child executes the existing production peer-identity functions. No TLS
tunnel, signer, key, wallet, protected data, miner workload or chain is used.
"""

import inspect
import json
import os
import shlex
import socket
import struct
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest
from test_validator_setup_units import arrangement, materials

from carbon.battery import intake as ib
from carbon.validator_setup import units

pytestmark = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_DOCKER_TESTS") != "1",
    reason="disposable Docker evidence runs in explicitly Docker-capable CI",
)


def docker(*argv, check=True):
    return subprocess.run(
        ["docker", *argv], capture_output=True, text=True, check=check, timeout=180
    )


@pytest.fixture(scope="module")
def fixture_image(tmp_path_factory):
    repo = Path(__file__).resolve().parents[2]
    iid = tmp_path_factory.mktemp("public-controller-image") / "iid"
    docker("info")  # Required execution, never a false green when CI asks for it.
    docker("build", "--iidfile", str(iid), str(repo / ".devcontainer"))
    image = iid.read_text(encoding="utf-8").strip()
    found = json.loads(docker("image", "inspect", image).stdout)[0]
    assert found["Id"] == image
    assert (found["Os"], found["Architecture"]) == ("linux", "amd64")
    assert found["Config"]["User"] == "ubuntu"
    return image


def service_argv(profile):
    text = units.render(profile)["fixture-validator-service.service"]
    return shlex.split(
        next(
            s.removeprefix("ExecStart=")
            for s in text.splitlines()
            if s.startswith("ExecStart=")
        )
    )


def test_generated_identity_connects_only_with_observed_supplementary_socket_group(
    tmp_path, monkeypatch, fixture_image
):
    profile, raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    endpoint = Path(raw["docker_socket"])
    info = endpoint.stat()
    uid = 65532 if info.st_uid != 65532 else 65531
    gid = 65532 if info.st_gid != 65532 else 65531
    raw["user"] = f"{uid}:{gid}"
    profile.write_text(json.dumps(raw), encoding="utf-8")
    argv = service_argv(profile)
    identity = argv[argv.index("--user") + 1]
    supplementary = argv[argv.index("--group-add") + 1]
    assert identity == raw["user"] and supplementary == str(info.st_gid)
    marker = uuid.uuid4().hex
    names = ["carbon-setup-socket-" + marker + suffix for suffix in ("-yes", "-no")]
    peers, errors = [], []
    code = """import json,os,socket
s=socket.socket(socket.AF_UNIX)
try:
 s.connect('/operator.sock')
except PermissionError:
 print(json.dumps({'refused':'permission'}));raise SystemExit(77)
s.sendall(b'ping')
echo=s.recv(256).decode('ascii')
print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups(),'echo':echo}))
s.close()
"""
    # This is a synthetic endpoint, never the real Docker socket or operator state.
    endpoint.unlink()
    with socket.socket(socket.AF_UNIX) as listener:
        with monkeypatch.context() as local:
            local.chdir(endpoint.parent)
            listener.bind(endpoint.name)
        endpoint.chmod(0o660)
        listener.listen(1)
        listener.settimeout(60)

        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(10)
                    peers.append(
                        struct.unpack(
                            "3i",
                            connection.getsockopt(
                                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
                            ),
                        )[1:]
                    )
                    assert connection.recv(4) == b"ping"
                    connection.sendall(marker.encode("ascii"))
            except Exception as error:
                errors.append(type(error).__name__)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            common = [
                "run",
                "--rm",
                "--read-only",
                "--network",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--user",
                identity,
                "--mount",
                f"type=bind,source={endpoint},target=/operator.sock",
            ]
            positive = docker(
                *common,
                "--name",
                names[0],
                "--group-add",
                supplementary,
                fixture_image,
                "/usr/local/bin/python3",
                "-c",
                code,
            )
            actual = json.loads(positive.stdout)
            worker.join(timeout=10)
            assert not worker.is_alive() and not errors
            assert peers == [(uid, gid)] and uid != 0
            assert (actual["uid"], actual["gid"], actual["echo"]) == (uid, gid, marker)
            assert int(supplementary) in actual["groups"]
            negative = docker(
                *common,
                "--name",
                names[1],
                fixture_image,
                "/usr/local/bin/python3",
                "-c",
                code,
                check=False,
            )
            assert negative.returncode == 77
            assert json.loads(negative.stdout) == {"refused": "permission"}
            assert peers == [(uid, gid)]
        finally:
            for name in names:
                docker("rm", "--force", name, check=False)
                assert not docker(
                    "container",
                    "ls",
                    "-a",
                    "--filter",
                    "name=^" + name + "$",
                    "--format",
                    "{{.ID}}",
                ).stdout.strip()


def test_generated_host_namespace_reaches_loopback_and_rejects_wrong_proxy_peer(
    tmp_path, monkeypatch, fixture_image
):
    from scripts.dev.battery_validator_service import service

    profile, raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    intake = service._intake(None, None)
    intake["exposure"] = {
        "via": "trusted_proxy",
        "header": "CF-Connecting-IP",
        "record": "OWNER-FIXTURE-INTAKE-EXPOSURE-99",
    }
    monkeypatch.setattr(service, "_intake", lambda *_args: intake)
    raw["service_network"]["proxy_peer"] = "127.0.0.1"
    profile.write_text(json.dumps(raw), encoding="utf-8")
    argv = service_argv(profile)
    mode = argv[argv.index("--network") + 1] if "--network" in argv else "bridge"
    marker = uuid.uuid4().hex
    code = (
        "import ipaddress,json\nfrom http.server import HTTPServer,BaseHTTPRequestHandler\n"
        + inspect.getsource(ib.trusted_proxy_peer)
        + "\n"
        + inspect.getsource(ib.peer_identity)
        + f"""
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  identity=peer_identity(self.headers,self.client_address[0],'CF-Connecting-IP')
  self.send_response(200 if identity is not None else 403);self.end_headers()
  self.wfile.write(json.dumps({{'marker':{marker!r},'identity':identity,'peer':self.client_address[0]}}).encode())
 def log_message(self,*args): pass
server=HTTPServer(('127.0.0.1',0),Handler)
print(json.dumps({{'port':server.server_port}}),flush=True)
server.serve_forever()
"""
    )
    name = "carbon-setup-loopback-" + marker
    docker(
        "run",
        "-d",
        "--name",
        name,
        "--network",
        mode,
        "--read-only",
        "--cap-drop",
        "ALL",
        fixture_image,
        "/usr/local/bin/python3",
        "-u",
        "-c",
        code,
    )
    try:
        for _ in range(100):
            logged = docker("logs", name).stdout.strip()
            if logged:
                break
            time.sleep(0.1)
        port = json.loads(logged.splitlines()[0])["port"]
        assert (
            json.loads(docker("inspect", name).stdout)[0]["HostConfig"]["NetworkMode"]
            == "host"
        )
        client = f"""import http.client,json,sys
c=http.client.HTTPConnection('127.0.0.1',{port},timeout=2,source_address=(sys.argv[1],0))
c.request('GET','/',headers={{'CF-Connecting-IP':'198.51.100.9'}})
r=c.getresponse(); print(json.dumps({{'code':r.status,'body':json.loads(r.read())}}))
"""

        def request(network, peer, check=True):
            return docker(
                "run",
                "--rm",
                "--network",
                network,
                "--read-only",
                "--cap-drop",
                "ALL",
                fixture_image,
                "/usr/local/bin/python3",
                "-c",
                client,
                peer,
                check=check,
            )

        legitimate = json.loads(request("host", "127.0.0.1").stdout)
        assert legitimate == {
            "code": 200,
            "body": {"marker": marker, "identity": "198.51.100.9", "peer": "127.0.0.1"},
        }
        forged_peer = json.loads(request("host", "127.0.0.2").stdout)
        assert forged_peer == {
            "code": 403,
            "body": {"marker": marker, "identity": None, "peer": "127.0.0.2"},
        }
        assert request("bridge", "127.0.0.1", check=False).returncode != 0
        assert (
            ib.peer_identity(
                {"CF-Connecting-IP": "198.51.100.9"}, "172.17.0.1", "CF-Connecting-IP"
            )
            is None
        )
    finally:
        docker("rm", "-f", name)


def test_generated_credential_bind_reaches_files_socket_and_missing_bind_cannot(
    tmp_path, monkeypatch, fixture_image
):
    profile, raw, fetch, _state, intake = materials(tmp_path, monkeypatch)
    # The native CI runner need not be the image's default ubuntu UID1000.
    # Keep private permissions; bind every fixture phase to its actual owner.
    owner = f"{os.getuid()}:{os.getgid()}"
    raw["user"] = owner
    suffix = "carbon-setup-public-material-" + uuid.uuid4().hex
    host = "/tmp/" + suffix
    names = ("signer.sock", "ca", "tls_cert", "tls_key")
    creation = f"""import os,socket
p='/hosttmp/{suffix}';os.mkdir(p,0o700)
for n in ('ca','tls_cert','tls_key'):
 with open(p+'/'+n,'xb') as f: f.write(b'public-synthetic-'+n.encode())
 os.chmod(p+'/'+n,0o600)
with socket.socket(socket.AF_UNIX) as s: s.bind(p+'/signer.sock')
"""
    docker(
        "run",
        "--rm",
        "--user",
        owner,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--mount",
        "type=bind,source=/tmp,target=/hosttmp",
        fixture_image,
        "/usr/local/bin/python3",
        "-c",
        creation,
    )
    mirror = Path(host)
    created_mirror = not mirror.exists()
    try:
        if created_mirror:
            # CI's test controller may be in another namespace. Its fixture
            # mirror lets render inspect identical declared path/type; the
            # actual Docker-host bytes are independently read below.
            mirror.mkdir(mode=0o700)
            for name in names[1:]:
                (mirror / name).write_bytes(b"public-synthetic-" + name.encode())
                (mirror / name).chmod(0o600)
            with socket.socket(socket.AF_UNIX) as s:
                s.bind(str(mirror / names[0]))
        body = json.loads(fetch.read_bytes())
        body.update(signer_socket=host + "/signer.sock", ca=host + "/ca")
        fetch.write_text(json.dumps(body), encoding="utf-8")
        intake.update(tls_cert=host + "/tls_cert", tls_key=host + "/tls_key")
        raw["state_mounts"].append(host)
        profile.write_text(json.dumps(raw), encoding="utf-8")
        argv = service_argv(profile)
        assert argv[argv.index("--user") + 1] == owner
        mount = f"type=bind,source={host},target={host}"
        assert mount in argv
        probe = f"""import json,os,stat
from pathlib import Path
p=Path({host!r})
assert stat.S_ISSOCK((p/'signer.sock').stat().st_mode)
assert all((p/n).read_bytes()==b'public-synthetic-'+n.encode() for n in ('ca','tls_cert','tls_key'))
print(json.dumps({{'files':3,'socket_type_verified':True,'uid':os.getuid(),'gid':os.getgid()}}))
"""
        base = [
            "run",
            "--rm",
            "--user",
            owner,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
        ]
        observed = docker(
            *base,
            "--mount",
            mount + ",readonly",
            fixture_image,
            "/usr/local/bin/python3",
            "-c",
            probe,
        )
        assert json.loads(observed.stdout) == {
            "files": 3,
            "socket_type_verified": True,
            "uid": os.getuid(),
            "gid": os.getgid(),
        }
        absent = docker(
            *base, fixture_image, "/usr/local/bin/python3", "-c", probe, check=False
        )
        assert absent.returncode != 0
        wrong_owner = [*base]
        wrong_owner[wrong_owner.index("--user") + 1] = (
            f"{os.getuid() + 1}:{os.getgid()}"
        )
        inaccessible = docker(
            *wrong_owner,
            "--mount",
            mount + ",readonly",
            fixture_image,
            "/usr/local/bin/python3",
            "-c",
            probe,
            check=False,
        )
        assert inaccessible.returncode != 0
        assert "PermissionError" in inaccessible.stderr
        raw["state_mounts"].remove(host)
        profile.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(
            units.SetupRefused, match="OPERATOR_CREDENTIAL_NOT_MOUNTED_IDENTICALLY"
        ):
            units.render(profile)
    finally:
        cleanup = f"""from pathlib import Path
p=Path('/hosttmp/{suffix}')
for n in {names!r}: (p/n).unlink()
p.rmdir()
"""
        docker(
            "run",
            "--rm",
            "--user",
            owner,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--mount",
            "type=bind,source=/tmp,target=/hosttmp",
            fixture_image,
            "/usr/local/bin/python3",
            "-c",
            cleanup,
        )
        if created_mirror:
            for name in names:
                (mirror / name).unlink()
            mirror.rmdir()
