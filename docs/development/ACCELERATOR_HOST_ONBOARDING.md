# Bringing your own accelerator host

Carbon's accelerator support is not tied to one machine. A laptop, a
workstation, a virtual machine and rented compute all go through the same steps,
and you never edit Carbon to describe your own hardware.

That is the whole point of the split below, so it is worth stating plainly:

- **The workload profile** says what the work needs — backend, device and
  process counts, topology, dtypes, precision, and a pinned environment. It
  lives in the repository, is byte-identical on every machine, and must stay
  that way, so two runs on different hosts can state that they requested the
  same configuration. That is all a shared digest establishes. It does **not**
  make their results comparable: the device, driver, allocator, thermal
  behaviour and contention still differ, and comparability is a scientific
  judgement about specific measurements, not a property a digest confers.
- **The host device record** says what *your* device is — its identifier, its
  marketed name, driver version and model, compute capability, memory, display
  state, platform, container runtime and provider. It is installed by you, on
  your host, and it never enters the repository.

A host device record is *evidence about a host*. It is not permission to use
one. Installing it qualifies nothing, grants nothing, and does not make any
result comparable or accepted.

## What this does not do

These commands never change your host's configuration. They do not install or
upgrade drivers, change clocks, power or voltage limits, alter display routing,
reconfigure the container daemon or reboot anything. They also never create
authority: `authorize` installs a grant or approval **that the owner wrote**, and
cannot manufacture one.

A passing `doctor` is a statement about the checks that command can make. It is
not acceptance, not a hardware qualification, and not a claim that results from
this host would count.

## The commands

Run them from the repository root.

```bash
python scripts/dev/carbon_accelerator.py inspect
```

Shows the workload profile and whether a bound host record is installed. Note
that the profile carries no device identifier and no device model — if you were
expecting to see your GPU there, that absence is the design.

```bash
python scripts/dev/carbon_accelerator.py observe
```

Reads your device with the vendor's own query tool and prints what it reports.
Read-only. If the tool is not on the path, pass `--smi /path/to/nvidia-smi`.

```bash
python scripts/dev/carbon_accelerator.py prepare --record-id my-host --provider self-hosted
```

Writes the host device record. Add `--dry-run` to see the document without
writing it. On a host with more than one device, `prepare` refuses to choose for
you: pass `--device <identifier>`. You may state `--platform` and
`--container-runtime` explicitly; otherwise they are detected, and anything that
cannot be determined is recorded as unknown rather than guessed.

```bash
python scripts/dev/carbon_accelerator.py doctor
```

Reports every blocker it can see and exits non-zero while any remain. Each
finding is READY, BLOCKED with a reason, or UNKNOWN. UNKNOWN is used wherever
the host could not be read — "we could not see a problem" is not the same as
"there is no problem", and the two are never folded together.

```bash
python scripts/dev/carbon_accelerator.py status
```

What has been consumed and what is outstanding: attempts used, any unreconciled
attempt, and whether the device is quarantined. Read-only.

```bash
python scripts/dev/carbon_accelerator.py authorize <record.json>
```

Installs a grant or development approval the owner authored, where the
controller looks for it. Its contents are verified by the controller at dispatch,
not here. This command cannot write one for you: a host-side tool that could
grant itself device access would defeat the admission design it sits in front of.

## Support matrix

This describes what the *software* can express and what it refuses. It is not a
statement that Carbon has been run successfully on any of these hosts, and it is
not hardware coverage. No row below has been executed.

| Host shape | Record expresses it | Source edit needed | Dispatch status |
| --- | --- | --- | --- |
| Consumer laptop GPU behind WSL2 and Docker Desktop | yes | none | blocked: WDDM enumeration unsupported |
| NVIDIA workstation, bare-metal Linux, Docker Engine | yes | none | blocked: no established observation source |
| NVIDIA device in a Linux virtual machine | yes | none | blocked: no established observation source |
| Hosted/rented NVIDIA instance, any provider | yes | none | blocked: no established observation source |
| One device of a multi-device host | yes | none | blocked: no established observation source |
| A MIG instance rather than a whole device | yes | none | blocked: no established observation source |
| A non-NVIDIA identifier against an NVIDIA workload | n/a | none | refused: vendor identifier rule |
| A record bound to a different workload profile | n/a | none | refused: per-run binding |

Two things to read carefully in that table.

First, **"no source edit needed" is the portability claim, and it is the only
claim being made.** Each shape has a fixture showing the record format carries
it and that the binding rules behave. None of them attaches a device.

Second, **every NVIDIA row is currently blocked for strict dispatch**, and not
because of the hardware. Strict admission and verified whole-device release
require that the controller can enumerate every compute process holding the
device. No observation source has been established as complete for that, so the
registry of established sources is deliberately empty. A driver model reading
does not establish it: `N/A` only says a Windows-only field does not apply to
the observing platform — and the vendor also uses it for unavailable
information — while `TCC` names a compute-oriented Windows driver model. Neither
shows that every process using the device is visible from where the controller
is looking.

Registering a source is a separate decision that needs its own evidence about
that source's visibility and the controls around it. Until then, the honest
status of every host is "not established", regardless of how capable the
hardware is.

## The local development path

There is a separate, narrower path for local development diagnostics. It uses
its own authority record, never the strict grant, and the two are never
interchangeable. It carries its own labels, its own request schema and its own
cleanup, and it reports:

- `other_compute_processes: null` — not an empty list. Nothing observed is not
  the same as nothing there.
- `exclusivity: UNESTABLISHED_DEVELOPMENT_OBSERVATION`
- `evidence: DEVELOPMENT_ONLY_NOT_SECURITY_QUALIFIED`
- `official_eligible: false`

Its cleanup removes the task-owned allocation record and reports
`TASK_OWNED_REMOVAL_ONLY_WHOLE_DEVICE_RELEASE_UNESTABLISHED`. It does not claim
the device was released, and it neither creates nor clears strict quarantine.
A development run cannot complete a strict allocation, and a strict run cannot
complete a development one.

Results from this path are development observations. They are not scientific
results, not comparable, and not eligible for any official evaluation.
