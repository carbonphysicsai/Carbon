# INCENTIVE-RUNNER-TIMERS-SCRAPPED: no timers for the role miners

**Owner decision, 2026-10-11** (relayed by the Test Lead, and settled in
PR Head's session): "If I'm making it harder with these timers, scrap them.
Stop inhibiting testing. That's on me."

**Supersedes** the permanent `incentive-runner@<lane>.timer` units that #1037
added for minerH and minerI: one runner cycle per 1080-block rotation.

**Decision:**
- The timers are stopped and disabled on `carbon-fresh`. Their runner
  configs, cursors and journals are kept.
- The timer, service template and installer are removed from
  `scripts/dev/survive_reboot/`, and so is the reboot check's timer listing.
- The role miners' cycles are run by hand. The next is the bank-cutover
  handover test: round-2 lists, one cycle per tempo, after the AX42 moves
  to v2-bank-e1-r360.

**Unchanged:** the reboot-surviving test signers and the validator tunnel
(SURVIVE-REBOOT-01).

**Process note:** when an owner instruction reverses something already
recorded on main, tell the merge manager as well as acting on the host, so the
record is corrected at the same time.
