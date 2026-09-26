"""Separate miner analysis image: permitted lab code, no evaluator modules.

The parent supplies pinned numerical dependencies. The Carbon package is
replaced with an explicit file allowlist. This image is never represented as the
unchanged C-03 evaluator image or as a production security qualification.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    doctor,
    load_image_identity,
)
from carbon.reconstruction.worker.model import OUTPUT_BYTES, OUTPUT_MEMBERS

from .data import write_once
from .profile import canonical, digest

SCHEMA = "carbon.autoresearch.analysis-image.v1"
ENTRYPOINT = """import signal,time
from pathlib import Path
done=False
def stop(*args):
    global done
    done=True
for name in ('home','tmp','cache','jax-cache'):
    (Path('/scratch')/name).mkdir(mode=0o700,exist_ok=False)
Path('/scratch/control-ready').touch(mode=0o400,exist_ok=False)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
while not done:time.sleep(.05)
"""
INSTALL = """import shutil,sysconfig
from pathlib import Path
site=Path(sysconfig.get_paths()['purelib']).resolve()
if not str(site).startswith('/opt/carbon-worker/lib/') or site.name!='site-packages':
    raise ValueError('unexpected build installation root')
target=site/'carbon'
if target.is_symlink() or target.resolve().parent!=site:raise ValueError('unexpected package target')
shutil.rmtree(target)
shutil.copytree('/tmp/permitted/carbon',target)
for path in target.rglob('*'):
    path.chmod(0o555 if path.is_dir() else 0o444)
target.chmod(0o555)
shutil.rmtree('/tmp/permitted')
Path('/tmp/install-analysis.py').unlink()
"""


def permitted_files():
    repo = Path(__file__).resolve().parents[2]
    result = {
        "carbon/__init__.py": b'__version__="0.9.0"\n',
        "carbon/reconstruction/__init__.py": b'"""Public research lab only; no evaluator exports."""\n',
        "carbon/reconstruction/_vendor/__init__.py": b"",
        "carbon/reconstruction/worker/__init__.py": b"",
        "carbon/reconstruction/worker/entrypoint.py": ENTRYPOINT.encode(),
        "carbon/reconstruction/worker/model.py": f"OUTPUT_BYTES={OUTPUT_BYTES}\nOUTPUT_MEMBERS={OUTPUT_MEMBERS}\n".encode(),
    }
    for name in (
        "carbon/reconstruction/scaling.py",
        "carbon/reconstruction/worker/exporter.py",
    ):
        result[name] = (repo / name).read_bytes()
    lab = repo / "carbon/reconstruction/_vendor/carbon_jax_lab"
    for path in sorted(lab.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            result[path.relative_to(repo).as_posix()] = path.read_bytes()
    for name in challenge_kit_files(repo):
        result.setdefault(name, (repo / name).read_bytes())
    return result


#: Never shipped to a miner, whatever the kit's imports reach: the controller,
#: the evaluator's orchestration, private stores and anything that holds or
#: routes protected material. The kit's closure is checked against these.
KIT_FORBIDDEN = (
    "carbon.development_session",
    "carbon.reference_runtime.controller",
    "carbon.measurement_runtime",
    "carbon.audit",
    "carbon.chain",
    "carbon.miner_mcp",
    "carbon.scoring",
    "carbon.transport",
)


def challenge_kit_files(repo):
    """The challenge kit and the exact import closure of what it runs.

    Computed in a fresh interpreter from what the kit actually imports, so the
    shipped generator and reference solvers are the validator's own files,
    byte for byte, and nothing extra rides along. Fails closed if the closure
    ever reaches a forbidden module.
    """
    import json as _json
    import subprocess
    import sys

    probe = (
        "import json,sys\n"
        "import carbon.challenge_kit.burgers\n"
        "import carbon.reference_runtime.model\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('carbon'))))\n"
    )
    modules = _json.loads(
        subprocess.run(
            [sys.executable, "-I", "-c", probe],
            cwd=repo,
            env={"PYTHONPATH": str(repo), "PATH": "/usr/bin:/bin"},
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    reached = [m for m in modules if m.startswith(KIT_FORBIDDEN)]
    if reached:
        raise ValueError(
            "challenge kit reaches forbidden modules: " + ", ".join(reached)
        )
    files = [
        "carbon/challenge_kit/burgers_pin.json",
        "carbon/challenge_kit/CarbonBurgers.jl",
    ]
    for module in modules:
        path = repo / (module.replace(".", "/") + ".py")
        package = repo / module.replace(".", "/") / "__init__.py"
        target = package if package.is_file() else path
        if module == "carbon" or not target.is_file():
            continue
        files.append(target.relative_to(repo).as_posix())
    return sorted(set(files))


def runtime_document(parent):
    return {
        "schema": SCHEMA,
        "parent_image": parent,
        "files": {name: digest(body) for name, body in permitted_files().items()},
        "entrypoint_digest": digest(ENTRYPOINT.encode()),
        "installer_digest": digest(INSTALL.encode()),
        "builder_digest": digest(Path(__file__).read_bytes()),
        "scope": "PUBLIC_MINER_ANALYSIS_NO_EVALUATOR",
        "qualification": False,
    }


@dataclass(frozen=True)
class ResearchImageIdentity:
    image_id: str
    parent_image: str
    runtime_digest: str


def verify_image(image, cli=None):
    if type(image) is not ResearchImageIdentity:
        raise ValueError("separate miner analysis image required")
    expected = digest(canonical(runtime_document(image.parent_image)))
    if image.runtime_digest != expected:
        raise ValueError("analysis runtime source binding differs")
    cli = cli or DockerCLI()
    metadata = cli.json(["image", "inspect", image.image_id, "--format", "{{json .}}"])
    config = metadata.get("Config", {})
    labels = config.get("Labels", {})
    if (
        metadata.get("Id") != image.image_id
        or metadata.get("Os") != "linux"
        or metadata.get("Architecture") != "amd64"
        or config.get("User") != "65532:65532"
    ):
        raise ValueError("analysis image identity differs")
    if (
        labels.get("org.opencontainers.image.carbon.d4.runtime") != expected
        or labels.get("org.opencontainers.image.carbon.d4.parent") != image.parent_image
        or config.get("Entrypoint")
        != [
            "/opt/carbon-worker/bin/python",
            "-I",
            "-m",
            "carbon.reconstruction.worker.entrypoint",
        ]
    ):
        raise ValueError("analysis image build binding differs")
    parent = cli.json(
        ["image", "inspect", image.parent_image, "--format", "{{json .}}"]
    )
    layers = parent.get("RootFS", {}).get("Layers", [])
    if (
        not layers
        or metadata.get("RootFS", {}).get("Layers", [])[: len(layers)] != layers
    ):
        raise ValueError("analysis parent layers differ")
    return image


def load_analysis_image(path):
    if path.is_symlink() or path.stat().st_size > 8192:
        raise ValueError("bounded analysis image manifest required")
    value = json.loads(path.read_bytes())
    if (
        set(value) != {"schema", "image_id", "parent_image", "runtime_digest"}
        or value.pop("schema") != SCHEMA
    ):
        raise ValueError("closed analysis image manifest required")
    return ResearchImageIdentity(**value)


def build_analysis_image(parent_manifest, root):
    parent = load_image_identity(parent_manifest)
    cli = DockerCLI()
    if not doctor(image_id=parent.image_id, image_identity=parent, cli=cli).eligible:
        raise ValueError("eligible pinned C-03 parent required")
    runtime = runtime_document(parent.image_id)
    fingerprint = digest(canonical(runtime))
    root = root / fingerprint[7:]
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = root / "analysis-image.json"
    if manifest.exists():
        return verify_image(load_analysis_image(manifest), cli)
    context = root / "build-context"
    context.mkdir(mode=0o700, exist_ok=True)
    for name, body in permitted_files().items():
        path = context / "permitted" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        write_once(path, body)
    write_once(context / "install-analysis.py", INSTALL.encode())
    tag = "carbon-cw1d4-parent:" + parent.image_id[7:]
    cli.run(["tag", parent.image_id, tag])
    if (
        cli.json(["image", "inspect", tag, "--format", "{{json .}}"])["Id"]
        != parent.image_id
    ):
        raise ValueError("local parent tag identity changed")
    dockerfile = f"""FROM {tag}
USER 0:0
COPY permitted /tmp/permitted
COPY install-analysis.py /tmp/install-analysis.py
RUN /opt/carbon-worker/bin/python -I /tmp/install-analysis.py
LABEL org.opencontainers.image.carbon.d4.runtime="{fingerprint}" org.opencontainers.image.carbon.d4.parent="{parent.image_id}" org.opencontainers.image.title="Carbon public miner analysis, no evaluator"
USER 65532:65532
ENTRYPOINT ["/opt/carbon-worker/bin/python","-I","-m","carbon.reconstruction.worker.entrypoint"]
"""
    write_once(context / "Dockerfile", dockerfile.encode())
    built = cli.run(
        [
            "build",
            "--network=none",
            "--pull=false",
            "--platform=linux/amd64",
            "-q",
            str(context),
        ],
        timeout=600,
    )
    image_id = built.stdout.decode().strip()
    image = ResearchImageIdentity(image_id, parent.image_id, fingerprint)
    verify_image(image, cli)
    write_once(root / "runtime-material.json", canonical(runtime))
    write_once(
        manifest,
        canonical(
            {
                "schema": SCHEMA,
                "image_id": image_id,
                "parent_image": parent.image_id,
                "runtime_digest": fingerprint,
            }
        ),
    )
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    image = build_analysis_image(args.parent_manifest, args.root)
    print(
        json.dumps(
            {
                "image_id": image.image_id,
                "manifest": str(
                    args.root / image.runtime_digest[7:] / "analysis-image.json"
                ),
                "scope": "PUBLIC_MINER_ANALYSIS_NO_EVALUATOR",
                "qualification": False,
            }
        )
    )


if __name__ == "__main__":
    main()
