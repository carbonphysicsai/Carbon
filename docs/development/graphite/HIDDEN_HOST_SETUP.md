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
- **What the PC may hold:** the Graphite submitter key
  (`~/.config/carbon/graphite-submitter.key`, which can only submit) and the
  VM's public TLS certificate.

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

**Cloud firewall:** allow inbound TCP 22 and 8468 only from the PC's public
IP. Deny everything else inbound.

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

```bash
sudo git clone --branch <release tag> --depth 1 https://github.com/carbonphysicsai/Carbon.git /opt/carbon
sudo chown -R root:root /opt/carbon
```

Then **pull release `<tag>`** with the release's pull-by-digest script. This
step is filled in when the Test Engineer's released-image work lands. The
manifest goes in `/var/lib/carbon-producer/etc/`.

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
2. **On the VM, create the door's TLS certificate.** It is self-signed, and
   the PC pins it. Replace `<VM_IP>` with the VM's public IP:

   ```bash
   E=/var/lib/carbon-producer/etc
   sudo -u carbon-producer openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 825 \
     -subj /CN=carbon-hidden -addext subjectAltName=IP:<VM_IP> -keyout $E/tls.key -out $E/tls.crt
   sudo -u carbon-producer chmod 0600 $E/tls.key
   ```

   Copy **`tls.crt` only** (public) to the PC. From a WSL shell on the PC,
   as `carbon`, with your own SSH session:

   ```bash
   ssh <VM_IP> sudo cat /var/lib/carbon-producer/etc/tls.crt > ~/.config/carbon/hidden-host.crt
   ```

   Graphite trusts that certificate and nothing else (`--hidden-ca`). Any other certificate, including one from a
   public authority, is refused, and so is a mismatched IP. A new IP or an
   expired certificate means repeating this step and the copy.
3. **On the VM, write the door's config.**
   `/var/lib/carbon-producer/etc/dev-submit.json` (mode 0600):

   ```json
   {
     "schema": "carbon.battery.dev-submit-config.v1",
     "deployment": "/var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json",
     "submitter_public_key": "<printed public key>",
     "nonce_file": "/var/lib/carbon-producer/operator/nonces",
     "operator_dir": "/var/lib/carbon-producer/operator",
     "host": "0.0.0.0",
     "port": 8468,
     "exposure_record": "<the owner's OWNER-…INTAKE-EXPOSURE-NN record for this door>",
     "tls_cert": "/var/lib/carbon-producer/etc/tls.crt",
     "tls_key": "/var/lib/carbon-producer/etc/tls.key"
   }
   ```

   A public bind refuses without a recorded owner exposure decision and TLS.
   That record is the owner's security call (AGENTS.md §13). It is a
   `## OWNER-…INTAKE-EXPOSURE-NN` heading under `.agent/decisions/`, and it
   must be in the release tag the VM runs.
4. **Run the door as a service** under `carbon-producer`:

   ```bash
   sudo -u carbon-producer python -m carbon.battery.dev_submit serve --config /var/lib/carbon-producer/etc/dev-submit.json
   ```

## 6. Batches and the tuning set: all on the VM, as `carbon-producer`

**Pool batches:** follow `HIDDEN_POOL_AND_TUNING_RUNBOOK.md` section A,
prefixing every command with `sudo -u carbon-producer`.

**The tuning set is never sealed on the PC.** Runbook §B seals it in the
testnet deployment, whose root is on the PC, so its cases would be
agent-readable. That section stays on HOLD.
- `graphite-tuning-v1` is superseded unsealed.
- `graphite-tuning-v2` (VALIDATOR-17 amendment, with slice Q's quiz) is
  sealed **on the VM**, in this hidden deployment's journal. Its overlap
  priors are owner-only files:
  1. **The rotating pool:** `tuning export-pool` on the VM.
  2. **EV5 and `graphite-confirmation-v1`:** these are sealed under the
     testnet root on the PC. Ryan exports their case inputs there, copies
     them to `/var/lib/carbon-producer/etc/` with `scp`, and then runs
     `shred -u` on the PC copies. The export command (`confirmation
     export-prior`) and v2's registration land together with slice Q.
- **Why not move the testnet deployment to the VM instead:**
  - The export adds no exposure, because those cases are already reachable
    from the PC root.
  - The tuning cases never touch the PC.
  - Moving the running testnet validator and its chain wallet is a larger,
    separate owner decision.

## 7. Graphite runs

On the PC:

```bash
python -m carbon.agent_campaign.graphite.phase3 run ... --hidden-endpoint https://<VM_IP>:8468 \
  --hidden-submitter-key ~/.config/carbon/graphite-submitter.key --hidden-ca ~/.config/carbon/hidden-host.crt
```

The run's hidden report is read on the VM only:

```bash
sudo -u carbon-producer python -m carbon.battery.dev_submit report --config /var/lib/carbon-producer/etc/dev-submit.json --run <run id>
```

## 8. The acceptance check

From the PC, no agent account can reach anything under
`/var/lib/carbon-producer` on the VM: it has no credentials. On the VM,
`sudo -u nobody ls /var/lib/carbon-producer/hidden` prints "Permission
denied".
