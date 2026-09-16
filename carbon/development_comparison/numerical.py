"""Bounded trusted diagnostics using the existing C-03 isolated carrier."""

from __future__ import annotations
import fcntl
import json
import time
from pathlib import Path
from carbon.development_session.budget import SessionBudget
from carbon.development_session.data import write_once
from carbon.development_session.profile import (
    canonical,
    digest,
    profile_digest,
    profile_document,
)
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    create_arguments,
    doctor,
    inspect_effective_controls,
    observe_effective_resources,
    remove_exact_container,
    spawn_watchdog,
)
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile

CODE = """
import importlib.util,json,sys
from pathlib import Path
root=Path('/input')
for name in ('carbon.measurement_runtime.development','carbon.measurement_runtime.development_controls','carbon.development_comparison.numerical_worker'):
    spec=importlib.util.spec_from_file_location(name,root/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
from carbon.development_comparison.numerical_worker import execute
print(json.dumps(execute(json.loads((root/'bundle.json').read_bytes())),allow_nan=False,separators=(',',':')))
"""


def run_numerical(root: Path, identity: str, bundle: dict, image):
    if not identity.replace("-", "").isalnum() or len(identity) > 60:
        raise ValueError("bounded operation identity required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    task_root = root
    for ancestor in (root, *root.parents):
        if (ancestor / "task-envelope.json").is_file():
            task_root = ancestor
            break
    with (task_root / "numerical.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        budget = SessionBudget(task_root / "numerical-budget.sqlite3")
        budget.reserve(identity, "numerical", 600.0, 7200.0, 12)
        started = time.time()
        # Storage includes failures/partial output. Reserve 32 MiB before each run.
        files = list(task_root.rglob("*"))
        if (
            any(p.is_symlink() for p in files)
            or sum(p.stat().st_size for p in files if p.is_file()) + 32 * 1024**2
            > 10 * 1024**3
        ):
            raise ValueError("diagnostic storage cap")
        operation = root / identity
        stage = operation / "input"
        stage.mkdir(parents=True, mode=0o755)
        stage.chmod(0o755)
        modules = (
            "carbon.measurement_runtime.development",
            "carbon.measurement_runtime.development_controls",
            "carbon.development_comparison.numerical_worker",
        )
        repo = Path(__file__).resolve().parents[2]
        sources = {
            name: (repo / (name.replace(".", "/") + ".py")).read_bytes()
            for name in modules
        }
        for name, body in sources.items():
            path = stage / (name + ".py")
            write_once(path, body)
            path.chmod(0o444)
        write_once(stage / "bundle.json", canonical(bundle))
        (stage / "bundle.json").chmod(0o444)
        launch = digest(
            canonical(
                {
                    "input": digest(canonical(bundle)),
                    "code": digest(CODE.encode()),
                    "sources": {k: digest(v) for k, v in sources.items()},
                    "image": image.image_id,
                }
            )
        )
        name = "carbon-d3-" + launch[7:31]
        cli = DockerCLI()
        checked = doctor(image_id=image.image_id, image_identity=image, cli=cli)
        if not checked.eligible:
            raise ValueError("diagnostic host ineligible")
        worker = DevelopmentWorkerProfile(
            profile_digest(), digest(canonical(profile_document()["budget"]))
        )
        write_once(
            operation / "intent.json",
            canonical(
                {
                    "launch": launch,
                    "container": name,
                    "started": started,
                    "deadline": started + 600,
                    "image": image.image_id,
                }
            ),
        )
        created = False
        try:
            cli.run(
                create_arguments(
                    container_name=name,
                    image_id=image.image_id,
                    input_directory=stage,
                    cpuset=checked.cpuset,
                    launch_digest=launch,
                    worker_profile=worker,
                ),
                timeout=30,
            )
            created = True
            spawn_watchdog(
                container_name=name, launch_digest=launch, deadline_unix=started + 600
            )
            cli.run(["start", name], timeout=20)
            cd, controls = inspect_effective_controls(
                cli=cli,
                container_name=name,
                image_id=image.image_id,
                input_directory=stage,
                cpuset=checked.cpuset,
                launch_digest=launch,
                worker_profile=worker,
            )
            output = operation / "output.json"
            cli.stream_to_file(
                ["exec", name, "/opt/carbon-worker/bin/python", "-I", "-c", CODE],
                output,
                maximum=16 * 1024**2,
                timeout=max(1, 570 - (time.time() - started)),
            )
            resources = observe_effective_resources(cli=cli, container_name=name)
            write_once(
                operation / "resources.json",
                canonical(
                    {
                        "controls": controls,
                        "controls_digest": cd,
                        "resources": resources,
                        "wall_seconds": time.time() - started,
                        "output_digest": digest(output.read_bytes()),
                    }
                ),
            )
        finally:
            if created:
                remove_exact_container(
                    cli=cli, container_name=name, launch_digest=launch
                )
        budget.finish(identity, time.time() - started, "COMPLETE")
        return json.loads(output.read_bytes())
