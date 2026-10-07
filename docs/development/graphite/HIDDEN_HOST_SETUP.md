# The hidden host: one-time setup (VALIDATOR-19 slice 0)

**Why a separate host.** On the operator's PC every agent session runs as
WSL `carbon`. That account is in the `docker` group (root-equivalent), and
`wsl.exe -u root` is open, so no account there can protect hidden cases,
references or tuning material.

The owner decided on 2026-10-06 that every hidden deployment, the tuning set
and their solves live on a **small cloud VM that no agent session has
credentials for**. It is CPU-only first, with an A40 when scored GPU rebuilds
begin. Graphite reaches it only through the signed door
(`carbon/battery/dev_submit.py`): it submits and receives sealed outcomes,
and never sees a case, reference, prediction, score or operator record.

**Who runs this:** Ryan, once, on the VM. Agents never get the VM's SSH key,
cloud console or any credential for it.

## Credential custody (read first)

Agent sessions on the PC can read the PC user's files and drive its browsers.
So:
- **The VM's SSH key.** It must be passphrase-protected or hardware-backed:
  - preferred: a FIDO2 key, `ssh-keygen -t ed25519-sk`, which needs a touch
    on every use;
  - otherwise: a passphrase, and never left unlocked in a running
    `ssh-agent`.
  Either way, a key file an agent can read is not enough to log in.
- **The cloud console.** Never leave it logged in in the Chrome profile that
  Claude in Chrome drives, or in the app's built-in browser. Use another
  profile or browser and sign out after use.
- **Cloud CLI credentials** (for example gcloud, aws or doctl) never live
  on the PC user's account.
- **What the PC may hold:**
  - the Graphite submitter key (`~/.config/carbon/graphite-submitter.key`),
    which can only submit;
  - option A's tunnel key, which reaches only the door;
  - the VM's pinned host key, or option B's public certificate.

## Operator conventions (the first operational run, 2026-10-07)

The filled-in, copy-paste sheet for the first run is
`/home/carbon/shared/operator/HETZNER_PART2.md`, on release
`worker-images-v1`. These conventions bind this document too:
1. **Every `scp` or `ssh` to or from the VM runs from Windows PowerShell,**
   with `-i $HOME\.ssh\carbon-vm`. WSL files are reached as
   `\\wsl.localhost\Ubuntu-24.04\home\carbon\...`. Ryan's admin key lives
   only in Windows and is never copied into WSL, where agent sessions run.
2. **The tuning curves** (`curves.json`, `curves.md`, aggregates only) land
   directly in `/home/carbon/shared/tuning-inputs/`. Nothing else leaves the
   VM.
3. **Graphite runs (§7) are the executor's job,** not Ryan's.
4. **Every VM block starts with `cd /opt/carbon`,** and runs Carbon as
   `sudo -u carbon-producer -H /opt/carbon/.venv/bin/python -m ...`.
   Every module resolves its repository from `/opt/carbon`.

## 0. Discard the `carbon`-owned pool on the PC

It holds a root (key) and a root-only journal, and no batch was ever drawn
from it:

```bash
shred -u <graphite-hidden-v1 dir>/root.bin && rm -r <graphite-hidden-v1 dir>
```

Keep its config only as a template. The VM gets a fresh root.

## 1. Create the VM

A small Linux VM (Ubuntu 24.04) with Docker. Choosing the provider and
spending money are the owner's decision. Only Ryan's own SSH key goes on it
(see Credential custody).

**Firewall and SSH hardening.** The owner's IP changes, so SSH is open from
anywhere, but with keys only:

```bash
sudo ufw default deny incoming && sudo ufw allow OpenSSH && sudo ufw enable
sudo apt-get install -y fail2ban    # its default sshd jail bans repeated failures
```

- Password logins are off (the sshd block in §5).
- Option B in §5 would also open TCP 8468.
- **Lockout recovery:** the Hetzner Robot rescue system. Boot it, mount the
  disk, and fix `/etc/ssh/sshd_config.d/50-carbon.conf`.

## 2. Create the service account and its state

```bash
sudo useradd --system --create-home --home-dir /var/lib/carbon-producer --shell /usr/sbin/nologin carbon-producer
sudo usermod -aG docker carbon-producer
sudo install -d -m 0700 -o carbon-producer -g carbon-producer /var/lib/carbon-producer/{hidden,operator,etc}
```

- `carbon-producer` is the only non-admin account on the VM in the `docker`
  group.
- No agent account exists on the VM.

## 3. Install Carbon and the released worker image (never build on the VM)

The release's exact steps (`worker-images-v1`) are in the sheet, steps 1–4:
1. Docker's containerd image store, which the pull requires.
2. uv 0.12.7, with Python 3.11.16 under `/opt/uv-python`.
3. The checkout at the tag, in `/opt/carbon`, with
   `uv sync --frozen --group chain --group science-jax --group science-torch`.
   Everything is owned by root and read-only to `carbon-producer`.
4. `scripts/dev/worker_image_release.py pull` against the release's
   `c03-worker-image.release.json`, writing the manifest to
   `/var/lib/carbon-producer/etc/c03-worker-image.json`.
5. `operate truth-materialize` for the reference solver's overlay.

## 4. Configure the hidden deployment

`/var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json`, owned by
`carbon-producer`, mode 0600:

```json
{
  "schema": "carbon.battery.validator-deployment.v1",
  "state": "/var/lib/carbon-producer/hidden/state.sqlite3",
  "private_root": "/var/lib/carbon-producer/hidden/root.bin",
  "journal": "/var/lib/carbon-producer/hidden/journal.jsonl",
  "work": "/var/lib/carbon-producer/hidden/work",
  "backend": "carrier",
  "image_manifest": "/var/lib/carbon-producer/etc/<released manifest>.json",
  "rule": "v2",
  "require_commitment": false,
  "development_only": true,
  "service_account": "carbon-producer"
}
```

Every load refuses under any other account (`evaluation_wrong_account`).
Then create the root:

```bash
sudo -u carbon-producer python -m carbon.battery.operate init --config /var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json
```

## 5. The Graphite submitter key (on the PC) and the door (on the VM)

1. **On the PC, as `carbon`, create the submitter key.** Graphite may hold
   it, because it only submits.

   ```bash
   python -m carbon.battery.dev_submit keygen --out ~/.config/carbon/graphite-submitter.key
   ```

   This prints the public key.
2. **How the PC reaches the door.** The owner chose option A on 2026-10-06
   (relayed by the Test Lead), for a Hetzner AX42 host. Option B stays only
   as the documented alternative.

### Option A (chosen): no public door, an SSH local forward

The door binds to `127.0.0.1:8468` on the VM, and nothing new listens on
the internet. Graphite reaches the door through a forwarding-only SSH
account.

**Why A is better than B:**
- **No new public listener.** The door is a Python standard-library HTTP
  server, which in B parses unauthenticated traffic from the network. Under
  A, the only pre-auth surface is sshd, which is already exposed for admin
  logins.
- **Two locks instead of one.** Reaching the door needs the tunnel key, and
  submitting needs the submitter key.
- **No certificate, IP SAN, renewal or exposure record.** The door stays on
  loopback, so `require_exposure` passes.
- **Host authentication is the same strength.** The VM's host key is pinned
  in a dedicated `known_hosts` file, which plays the role of B's pinned
  certificate.
- **A stolen tunnel key gives** only a TCP path to the door, which still
  needs the submitter key. Both live on the PC, so the thief can do no more
  than Graphite already can. It never reaches a shell, a file, another port
  or the admin login, which keeps its own hardware or passphrase key.
- **Drops behave the same as B:** a lost connection is
  `UNAVAILABLE` / `dev_submit_unreachable`, never a score.

**On the VM:**

```bash
sudo useradd --system --create-home --home-dir /var/lib/carbon-tunnel --shell /usr/sbin/nologin carbon-tunnel
sudo install -d -m 0700 -o carbon-tunnel -g carbon-tunnel /var/lib/carbon-tunnel/.ssh
```

Add the following to `/etc/ssh/sshd_config.d/50-carbon.conf`, then run
`sudo sshd -t && sudo systemctl reload ssh`. It keeps the tunnel account to
one local forward even if its `authorized_keys` line is wrong. **Keep your
current SSH session open** until a fresh admin login works: `AllowUsers`
without your exact admin login (`root` on a fresh Hetzner install) locks you
out, and `sshd -t` does not catch it. `prohibit-password` keeps root's
key-only login. Use `PermitRootLogin no` only once you log in as a separate
admin user.

```text
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
AllowUsers <your admin login: root, or your admin user> carbon-tunnel
Match User carbon-tunnel
    AllowTcpForwarding local
    PermitOpen 127.0.0.1:8468
    PermitListen none
    AllowStreamLocalForwarding no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    ForceCommand /bin/false
```

`AllowTcpForwarding local` also blocks remote forwards (`-R`). The
authorized_keys option `port-forwarding` alone would allow those.

**On the PC, as `carbon`:**
1. Create the tunnel key. It has no passphrase, because Graphite runs
   unattended, and it can reach only the door:

   ```bash
   ssh-keygen -t ed25519 -N "" -C carbon-tunnel -f ~/.config/carbon/hidden-tunnel.key
   ```

2. Pin the VM's host key. Check the printed fingerprint against
   `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`, run on the VM in
   your own session:

   ```bash
   ssh-keyscan -t ed25519 <VM_IP> > ~/.config/carbon/hidden-known-hosts && ssh-keygen -lf ~/.config/carbon/hidden-known-hosts
   ```

**On the VM,** put the tunnel key's public line into
`/var/lib/carbon-tunnel/.ssh/authorized_keys` (owner `carbon-tunnel`, mode
0600), prefixed with:

```text
restrict,port-forwarding,permitopen="127.0.0.1:8468",command="/bin/false" ssh-ed25519 AAAA… carbon-tunnel
```

**The door's config** (`/var/lib/carbon-producer/etc/dev-submit.json`, mode
0600):

```json
{
  "schema": "carbon.battery.dev-submit-config.v1",
  "deployment": "/var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json",
  "submitter_public_key": "<printed public key>",
  "nonce_file": "/var/lib/carbon-producer/operator/nonces",
  "operator_dir": "/var/lib/carbon-producer/operator",
  "host": "127.0.0.1",
  "port": 8468
}
```

**The tunnel** runs outside Graphite, as its own supervised process: a
Graphite run never starts or holds an SSH connection. In a WSL shell as
`carbon`, keep this running (for example in a `tmux` window, or as a
`systemd --user` service with `Restart=always`):

```bash
while true; do
  ssh -N -i ~/.config/carbon/hidden-tunnel.key -o IdentitiesOnly=yes \
    -o UserKnownHostsFile=~/.config/carbon/hidden-known-hosts -o StrictHostKeyChecking=yes \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -L 127.0.0.1:18468:127.0.0.1:8468 carbon-tunnel@<VM_IP>
  sleep 5
done
```

### Option B (not chosen): a public TLS door with a pinned certificate

The firewall also allows TCP 8468 (`sudo ufw allow 8468/tcp`).

1. **Create a self-signed certificate on the VM,** replacing `<VM_IP>`:

   ```bash
   E=/var/lib/carbon-producer/etc
   sudo -u carbon-producer openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 825 \
     -subj /CN=carbon-hidden -addext subjectAltName=IP:<VM_IP> -keyout $E/tls.key -out $E/tls.crt
   sudo -u carbon-producer chmod 0600 $E/tls.key
   ```

2. **Copy only `tls.crt` (public) to the PC,** from a WSL shell as `carbon`
   with your own SSH session:

   ```powershell
   ssh -i $HOME\.ssh\carbon-vm root@<VM_IP> cat /var/lib/carbon-producer/etc/tls.crt > \\wsl.localhost\Ubuntu-24.04\home\carbon\.config\carbon\hidden-host.crt
   ```

   Graphite trusts that certificate and nothing else (`--hidden-ca`). Any
   other certificate, including one from a public authority, is refused, and
   so is a mismatched IP. A new IP or an expired certificate means repeating
   both steps.

The door's config is as in A, but with `"host": "0.0.0.0"`,
`"exposure_record"`, `"tls_cert"` and `"tls_key"` added. A public bind
refuses without a recorded owner exposure decision and TLS:
- that record is the owner's security call (AGENTS.md §13);
- it is a `## OWNER-…INTAKE-EXPOSURE-NN` heading under `.agent/decisions/`;
- it must be in the release tag the VM runs.

### Then, either option: run the door as a service under `carbon-producer`

```bash
sudo -u carbon-producer python -m carbon.battery.dev_submit serve --config /var/lib/carbon-producer/etc/dev-submit.json
```

## 6. Batches and the tuning set: all on the VM, as `carbon-producer`

**Pool batches, first run:** follow `HIDDEN_POOL_AND_TUNING_RUNBOOK.md`
section A (the sheet's step 9: 4 screening + 2 finalist), as
`carbon-producer`. These draw their own batches and carry no quiz.

**Pool batches with the quiz, from the next rotation** (the Test Lead's
ruling, 2026-10-07; the mainnet path):
1. Carbon's producer runs on this host with its own deployment and root
   (`TESTNET_REHEARSAL_SETUP.md` Part 1, with its `quiz: {panel}` config).
   Its `tick` draws, solves, seals with the quiz, and publishes into
   `producer/outbox/<challenge>/`.
2. The development deployment gains `"batch_source": "answer_key"`. It stays
   `development_only`.
3. After each tick, import the outbox directly. There is no distribution host
   on the same host:

   ```bash
   cd /opt/carbon
   sudo -u carbon-producer -H /opt/carbon/.venv/bin/python -m carbon.challenge_validator.answer_key import \
     --deployment /var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json \
     --producer-public-key <the producer key's public key> \
     --outbox /var/lib/carbon-producer/producer/outbox/battery-fastcharge-ageing-development-v1
   ```

   Every package is verified as a fetched one is; a bad one is refused by
   code and the rest still import.
4. The open pool keeps scoring its own batches until a producer window
   covers the newest block. It then scores on the producer's batches and
   never stalls.

**The tuning set is never sealed on the PC.** Runbook §B seals it in the
testnet deployment, whose root is on the PC, so its cases would be
agent-readable. That section stays on HOLD.
- `graphite-tuning-v1` is superseded unsealed.
- `graphite-tuning-v2` (VALIDATOR-17 amendment, with slice Q's quiz) is
  sealed **on the VM**, in this hidden deployment's journal. Its overlap
  priors are owner-only files:
  1. **The rotating pool:** `tuning export-pool` on the VM.
  2. **EV5 and `graphite-confirmation-v1`:** these are sealed under the
     testnet root on the PC. Ryan exports their case inputs there
     (`confirmation export-prior`), copies them to
     `/var/lib/carbon-producer/etc/` with `scp` from PowerShell (`-i
     $HOME\.ssh\carbon-vm`, from `\\wsl.localhost\...`), and then runs
     `shred -u` on the PC copies. The sheet's step 10 has the exact commands.
- **The curves** from `tuning_rescore --q3-regret` are copied from PowerShell
  straight into `/home/carbon/shared/tuning-inputs/`. They are aggregates
  only.
- **Why not move the testnet deployment to the VM instead:**
  - The export adds no exposure, because those cases are already reachable
    from the PC root.
  - The tuning cases never touch the PC.
  - Moving the running testnet validator and its chain wallet is a larger,
    separate owner decision.

## 7. Graphite runs (the executor's job)

The Graphite executor session runs these, never Ryan. On the PC, with option
A's tunnel up:

```bash
python -m carbon.agent_campaign.graphite.phase3 run ... --hidden-endpoint http://127.0.0.1:18468 \
  --hidden-submitter-key ~/.config/carbon/graphite-submitter.key
```

With option B: `--hidden-endpoint https://<VM_IP>:8468 --hidden-ca
~/.config/carbon/hidden-host.crt` instead.

The run's hidden report is read on the VM only:

```bash
cd /opt/carbon
sudo -u carbon-producer -H /opt/carbon/.venv/bin/python -m carbon.battery.dev_submit report --config /var/lib/carbon-producer/etc/dev-submit.json --run <run id>
```

## 8. The acceptance check

From the PC, no agent account can reach anything under
`/var/lib/carbon-producer` on the VM: it has no credentials. On the VM,
`sudo -u nobody ls /var/lib/carbon-producer/hidden` prints "Permission
denied".
