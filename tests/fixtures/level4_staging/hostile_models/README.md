# Level 4 hostile lowering sources (PLT-06)

These are **hostile source fixtures**, not ordinary executable tests. The `.py.txt`
suffix prevents Python imports and pytest discovery. Neither local tests nor CI
execute, import, trace or lower them. Tests only parse their syntax as data and
exercise the preparation guard with inert inspection records.

The **Graphite executor** runs each source through the real Level 4 lowering tool
in a separate Launchpad container, after containment passes on the current analysis
image. `init(key)` is harmless; the hostile action occurs when the lowering tool
traces `forward(params, x)`. The 1 MiB allocation/write chunks are fixture workload
sizes, not policy limits. The socket targets a documentation-only address without DNS.

| Source | Expected outcome | Required evidence |
|---|---|---|
| `memory.py.txt` | Typed refusal or memory bound holding | Memory-limit event or allocation refusal; host and other lanes responsive |
| `time.py.txt` | Supervisor timeout | Deadline enforced; entire container removed |
| `scratch_flood.py.txt` | Typed refusal or scratch bound holding | Capped tmpfs byte/inode exhaustion; no host-disk growth |
| `fork_bomb.py.txt` | Timeout or PID bound holding | PID cap enforced; every descendant removed by whole-container cleanup |
| `outside_scratch.py.txt` | Typed refusal | Write denied; `/hostile-l4-outside-scratch` absent |
| `network_socket.py.txt` | Typed refusal or timeout | Connection denied; isolated network remained `none` |

Every probe must leave the host and other lanes unaffected. No successful
submission, envelope, score or qualification is an acceptable probe outcome.
An infrastructure failure or uncertain cleanup is unresolved evidence, never PASS.
Each `forward` first emits a flushed `HOSTILE_L4_PROBE:<name>` marker. Without
that marker the hostile body was not reached: a dependency/startup failure is
unresolved, not evidence that a bound contained this probe. The marker alone is
also insufficient; the corresponding limit/denial and cleanup evidence are required.

## Preparation guard and executor handoff

`tests/cpu/level4_hostile_fixtures.py::prepare_probe_sources` reads source text only
after `require_probe_container` accepts fresh Docker inspection of the executor's
running container, its exact container id, its pinned analysis image and an explicit
wall deadline. It returns the source bytes as text, their digests and expectations;
it contains no execution or readiness-record writer. The executor must enforce that
deadline with Launchpad's supervisor, copy source only into that checked container's
scratch, run one probe per container, and verify whole-container cleanup before
associating any evidence. Preserve the source, image, container, limits and outcome
identities in the executor's evidence. A preparation plan is not a probe result.

The prospective fixture lane label is `carbon.miner-research.bounded.v1`. This PR
does not install or activate that lane. It requires positive memory (swap included),
CPU and PID caps; read-only root/input; non-root user; no capabilities, devices,
privilege escalation or network; and scratch on tmpfs with explicit byte and inode
caps. No operational cap value is chosen by the fixtures.

**Current limitation:** #1199's operator resource profile still uses
`carbon.miner-research.unlimited.v1` and host-disk scratch. The guard refuses it
even when memory/CPU/PID caps or a resource-profile digest are present. Launchpad
must supply the bounded identity and capped scratch before the executor can run
these sources. Do not work around the guard on a host or an unlimited lane.

R8 v1 currently records memory, time and scratch-flood results. This pack also
supplies PID, filesystem and network probes for the executor's isolation evidence;
it does not rewrite historical R8 records, emit a PASS, or grant security acceptance.
