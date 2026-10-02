# Practising on your own remote machine or container

Carbon connects your Control Center to a GPU machine or container you already
run, anywhere, and runs battery practice there. You choose the setup. Carbon
provides the wiring and the tooling (OWNER-MINER-COMPUTE-LINK-ONLY-01, amended
2026-10-02: "miners should be able to use whatever they want to run their
setup").

What Carbon never does:

- start, stop, terminate or bill your machine, or read your provider balance;
- ask for a provider key, a registry password or a sudo password;
- send your SSH key anywhere: your own `ssh` uses your agent, `~/.ssh/config`
  and known hosts.

The machine receives the pinned GPU worker, one practice job's public inputs
and a per-job token. Your controller, your hotkey signer and every key stay on
your own machine. Practice there is for speed only: nothing measured remotely
is evidence, and the validator rebuilds your recipe on its own pinned backend.

## Choose a transport

| Transport | Your setup | What Carbon does per practice trial | Worker checked by |
| --- | --- | --- | --- |
| `ssh-docker` | A machine (VM, bare metal, workstation) with Docker and the NVIDIA Container Toolkit. Your SSH user runs `docker` without sudo. | Starts one `carbon-job-<24 hex>` container from the pinned worker, by image ID, and removes it. | Image ID |
| `ssh-container` | A container you started from the pinned GPU worker image, with SSH into it. No Docker inside. | Starts one job server process in `/tmp/carbon-job-<24 hex>`, then stops it and removes the directory. | The build identity the image carries |
| `endpoint` | A job endpoint you expose. | Not built (see [Why there is no endpoint transport](#why-there-is-no-endpoint-transport)). | n/a |

Both built transports reach the job the same way: an SSH local port forward
(`ssh -L`) to the job server on the machine's loopback. **Expose no port for
Carbon** other than SSH itself.

## Steps (any provider)

1. **Build the pinned GPU worker on your controller machine.** No GPU is needed
   to build it.
   - Run `scripts/install_miner.sh --gpu`, or
     `./scripts/dev/accelerator_worker_image.sh` from a clean checkout.
   - It writes `.carbon-artifacts/accelerator-worker-image.json`, the manifest
     setup asks for.
2. **For `ssh-container`, put the worker where your provider can pull it.**
   - Log in to a registry you control with `docker login`, yourself.
   - Run `scripts/dev/push_worker_image.sh --manifest .carbon-artifacts/accelerator-worker-image.json <registry>/<you>/carbon-gpu-worker`.
   - It pushes the pinned worker and prints `Start your container from: <repository>@sha256:...`.
   - Give your provider registry access the way it documents, and keep that
     credential with the provider. Carbon never sees it.
3. **Start your machine or container yourself.**
   - `ssh-docker`: any machine with Docker and the NVIDIA Container Toolkit.
     Let your SSH user run `docker` without sudo, for example by adding it to
     the `docker` group.
   - `ssh-container`: start it from the reference step 2 printed, and make
     sure it serves SSH (see [SSH into a container](#ssh-into-a-container)).
4. **Make `ssh <destination>` work from your controller without a prompt.**
   - Load your key in your agent.
   - Connect once by hand to accept the host key into your known hosts.
   - Optionally give it an alias in `~/.ssh/config` with its user and port.
   - Carbon passes `BatchMode=yes`, so anything that would prompt fails
     instead.
5. **Run setup.** In the Control Center, open Set up your environment, then
   Compute, then "Your own remote machine or container".
   - Choose the transport.
   - Give the destination (`user@host` or your alias) and, if not in your
     alias, the port.
   - Give the GPU worker manifest and the Challenge.
   - The check uses only your SSH, starts nothing and installs nothing:
     - `ssh-docker`: reach, Docker, the toolkit, Docker without sudo, and the
       image by ID;
     - `ssh-container`: reach, the worker's Python, and its build identity.
6. **For `ssh-docker`, send your worker.** If the check reports the image
   missing, tick to agree to send the pinned worker to that destination and
   send it. It streams `docker save <image id> | ssh <destination> docker load`
   and checks the image ID; it can take minutes.
7. **Write your profile and launch.** Practice feedback records
   `REMOTE_GPU` with the transport, how the worker was verified and whether
   the cleanup was confirmed.
8. **Stop your machine yourself when you are done.** Carbon never stops it.
   - Cleanup normally confirms. If a trial's record says
     `cleanup: unconfirmed`, look on the machine for `carbon-job-*` containers
     (`ssh-docker`) or `/tmp/carbon-job-*` directories and processes
     (`ssh-container`) and remove them.
   - A job server also ends itself after its job's lifetime.

If the machine's address changes (many rentals get a new one when restarted),
run the Compute step again with the new destination. A campaign keeps its
transport; changing transport means a new campaign.

## SSH into a container

The pinned worker image carries no SSH server. How a container gets one
depends on the provider:

- Some providers inject SSH into any container (Vast.ai's SSH launch mode, by
  its documentation; see below).
- Others need the image to run its own SSH server (RunPod's full SSH, and Lium
  custom templates, by their documentation; see below).

For the second kind, build your own image on top of the pushed worker that adds
an SSH server, and start your container from that. Carbon's check reads the
build identity file the pinned worker layer carries
(`/opt/carbon/worker-image-build.json`), so a layer you add on top still
passes, as long as it leaves `/opt/carbon` and `/opt/carbon-worker` as built.
That layer is yours: Carbon does not build, publish or check it.
**UNVERIFIED:** Carbon has not built or run such a layer on any provider.

## Per-provider notes

Provider facts below were read from each provider's public documentation on
2026-10-02, through fetched page summaries; the source is named on each.
Nothing here was run live: Carbon has no account with any of them. Anything
marked **UNVERIFIED** was not found in public documentation. Re-check the
provider's current documentation before relying on any of it.

### RunPod pods

- **Transport:** `ssh-container`. A pod is a container started from your image,
  and you cannot run your own Docker daemon in it
  (docs.runpod.io/pods/overview).
- **Image:** the `repository@sha256` reference from `push_worker_image.sh`,
  with an SSH server in your own layer. RunPod's full SSH needs TCP port 22
  exposed, an SSH daemon in the pod, and `PUBLIC_KEY` set for custom templates
  (docs.runpod.io/pods/configuration/use-ssh). Private registry credentials are
  added under Credentials (docs.runpod.io/get-started/credentials).
  - **UNVERIFIED:** whether a pod can be started from a `repository@sha256`
    reference; if not, start it from the tag the helper printed.
- **Ports:** expose TCP 22 only. The destination is `root@<public IP>` with the
  mapped port RunPod shows (docs.runpod.io/pods/configuration/use-ssh).
  - Do not use the basic SSH proxy (`ssh.runpod.io`): RunPod documents no SCP
    or SFTP through it, and **UNVERIFIED:** whether it allows port forwarding,
    which Carbon needs.
  - Do not expose the job port through RunPod's HTTP proxy.
- **Stop it yourself:** Stop or Terminate in the console, or
  `runpodctl pod stop <pod id>` / `runpodctl pod delete <pod id>`. A stopped
  pod still bills its volume disk (docs.runpod.io/pods/manage-pods).

### Lium (Bittensor subnet 51)

- **Transport:** `ssh-container`. A Lium pod is a container started from a
  template image (docs.lium.io/pod-users/templates).
  - **UNVERIFIED:** `ssh-docker` inside a pod. Lium nodes run `sysbox-runc` so
    renters can run Docker in Docker
    (docs.lium.io/providers/nodes/sysbox), but whether the NVIDIA Container
    Toolkit and `--gpus all` work there is not documented.
- **Image:** a custom template from your pushed worker, with an SSH server in
  your own layer. Lium installs sshd only for its official CUDA template;
  custom templates must provide SSH themselves (docs.lium.io/pod-users/templates).
  Templates take Docker credentials and an optional image digest pin (same
  page).
- **Ports:** internal port 22 in the template; each internal port maps to its
  own external port on the host (same page). The destination is `root@<host>`
  with that external port.
  - **UNVERIFIED:** the login user, inferred from the documented `/root` home.
  - **UNVERIFIED:** whether plain `ssh -L` is restricted. Lium's own
    `lium port-forward` runs over SSH
    (docs.lium.io/developers/cli/reference/port-forward).
- **Stop it yourself:** `lium rm <pod>` removes the pod, and cannot be undone
  (docs.lium.io/developers/cli/reference/rm). Volumes and backups bill until
  deleted (docs.lium.io/pod-users/billing).

### Targon VMs (Bittensor subnet 4)

- **Transport:** `ssh-docker`. A Targon VM is a full VM, not a container
  (docs.targon.com/guides/virtual-machines).
  - **UNVERIFIED:** whether any Targon VM image ships Docker and the NVIDIA
    Container Toolkit. If yours does not, install them yourself; Carbon's check
    refuses a machine without them and installs nothing.
- **Image:** none to push. Setup's "Send your worker" step streams it over SSH.
- **Ports:** SSH only. The destination is `ubuntu@<public IP>` with the VM's
  non-standard SSH port; your key is attached when you create the VM and
  cannot be changed later (docs.targon.com/cli/vm).
  - **UNVERIFIED:** whether SSH port forwarding is restricted.
- **Stop it yourself:** Delete in the console, or
  `targon workload delete <uid>`; deletion cannot be undone
  (docs.targon.com/cli/workload).
  - **UNVERIFIED:** whether anything bills after deletion.

### Vast.ai

- **Transport:** `ssh-container` for a standard instance, which is a Docker
  container from your image (docs.vast.ai/guides/instances/docker-environment).
  `ssh-docker` for a VM instance, which runs only Vast's KVM images and provides
  Docker (docs.vast.ai/guides/instances/virtual-machines).
  - **UNVERIFIED:** whether Vast VM images include the NVIDIA Container
    Toolkit.
- **Image:** for an instance, your pushed worker. Templates take registry
  credentials (docs.vast.ai/documentation/templates/template-settings).
  - Vast's SSH launch mode replaces the image's entrypoint and sets up SSH
    itself (docs.vast.ai/guides/instances/connect/ssh).
  - **UNVERIFIED:** that it does so without an SSH server in your image.
  - **UNVERIFIED:** pulling by `repository@sha256`; the documented form is
    `repository/image:tag`.
- **Ports:** SSH only. The destination is `root@<host>` with the mapped port
  Vast shows. Vast documents `ssh -L` (same page).
  - Create `~/.no_auto_tmux` in the container if its tmux session gets in
    the way (same page).
- **Stop it yourself:** `vastai stop instance <id>` or
  `vastai destroy instance <id>`. Stopped instances still bill storage
  (docs.vast.ai/instances-guide).

### Lambda

- **Transport:** `ssh-docker`. A Lambda instance is a VM with Docker and the
  NVIDIA Container Toolkit installed by default
  (docs.lambda.ai/public-cloud/on-demand/managing-system-environment).
- **Image:** none to push. Setup's "Send your worker" step streams it over SSH.
  First add your user to the `docker` group, as Lambda documents
  (`sudo adduser "$(id -un)" docker`, then log in again): Carbon refuses a
  machine where Docker needs sudo.
- **Ports:** SSH (22) only. The destination is `ubuntu@<instance IP>`. Lambda
  documents `ssh -L`
  (docs.lambda.ai/public-cloud/on-demand/connecting-instance).
- **Stop it yourself:** Terminate in the console. There is no stop; shutting
  the VM down leaves it billing
  (docs.lambda.ai/public-cloud/on-demand/creating-managing-instances).

### Your own workstation

- **Transport:** `ssh-docker`, with Docker and the NVIDIA Container Toolkit
  installed and your SSH user in the `docker` group.
  - On the machine the Control Center runs on, choose "This machine (your
    GPU)" instead: no SSH is needed.
- **Image:** none to push; "Send your worker" streams it.
- **Ports:** SSH only, reachable from your controller (your LAN, a VPN, or an
  SSH jump host set in your `~/.ssh/config`).
- **Stop it yourself:** it is yours; nothing runs there between trials.

## Why there is no endpoint transport

LINKONLY-D7 records why `endpoint` is designed and not built.

- **Today's job server serves one job per process.** It takes that job's
  token when it starts. Without a shell on the machine, Carbon cannot start
  one per trial, so you would restart it by hand for every trial.
- **A useful endpoint would weaken protections.** It would need a
  long-lived job server holding a standing secret, accepting programs from
  whoever presents it, and reachable from the internet through your
  provider's proxy.
- **It is the owner's call.** That is a security acceptance, so it waits for
  one. Until then setup refuses `endpoint` by name, and `ssh-container`
  covers the same rentals over SSH.
