## OWNER-DOOR-HARDENING-ACCEPT-01: the public doors' shared listener hardening (#829) is security-accepted

**Authority.** The owner, 2026-10-08:
- to PR Head, relayed to the Carbon Validator session: they reviewed and
  approve #829's door hardening;
- **confirmed directly in the Carbon Validator session** as a security
  acceptance (AGENTS.md §13). The owner chose **"Exactly #829"**, whose
  description read:

  > Accept the shared LoggedHandler (10 s per-read/write timeout, silent base
  > log, event-only lines), the shared hardened listener (per-connection TLS
  > handshake, 4-per-peer/64-total slots, backlog 128) on the intake, answers
  > host and dev door. Not the hosts' wider security review, and the
  > slow-trickle residual (a client sending one byte under 10 s holds a slot,
  > bounded by the caps) is named as accepted.

### Accepted: exactly #829 (merged ecb638c42)

- **`intake.LoggedHandler`,** the base of every public door's handler:
  - `timeout = SOCKET_TIMEOUT_S` (10 s) on every handshake, header and body
    read and every write;
  - the base class's own log stays silent;
  - one event-only line per timed-out connection.
- **`intake.hardened_listener`:**
  - TLS wrapped with `do_handshake_on_connect=False`, so each handshake runs
    in its connection's own thread under that timeout;
  - `ConnectionSlots`: 4 per peer and 64 in total;
  - `LISTEN_BACKLOG = 128`;
  - one event-only line per refused or failed connection, with no peer
    address.
- **On:** the battery intake, the answer-key distribution host
  (`distribution.make_server`) and the development submission door
  (`dev_submit.make_server`).
- **Accepted residual:** a client that sends one byte within each 10 s can
  hold a slot longer than 10 s. It is bounded by the per-peer and total caps.

### Not accepted here

- **Each host's wider security review:** its exposure, TLS configuration,
  authentication, permits, custody and operating system.
- **Any other listener,** or a later change to these values.

A change to this listener needs a new acceptance.
