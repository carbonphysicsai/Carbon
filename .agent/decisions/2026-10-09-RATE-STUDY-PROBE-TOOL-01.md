## 2026-10-09 — RATE-STUDY-PROBE-TOOL-01: the G-sealed probe tool, offered to study sessions only

**Authority.**
- **The specification.** Run sheet D.3 and the plan's O5. The Test Lead
  pointed this work (2b) at VALIDATOR-30's consumer contract, #876, as the
  study route's interface.
- **The scope.** This is development tooling. It grants nothing, and it
  moves no threshold.

**Decision.**
- **The tool.** `roles.STUDY_PROBE` (`rate_study_next_probe`) joins the tool
  registry. Only a study role offers it:
  - `roles.study_role(CONSTRUCTOR, "SUBMISSION-RATE-STUDY-01")` is the
    Constructor plus the tool, with its record naming the study;
  - no other study or role is accepted;
  - a role that offers the tool without a study is refused at construction.
- **Every ordinary role is unchanged:** its tools, its record and its
  manifest digest. A test pins the Constructor's v1 and v2 digests.
- **The study flows** from `phase3 run --study` to
  `Phase3Provider(study=...)` and then to `session_brief(study=...)`:
  - the brief records `study` and the study role's manifest;
  - an ordinary brief's document is byte for byte as before;
  - the provider refuses a brief whose study is not its own
    (`brief_study_mismatch`) and resumes a session as its recorded role.
- **The toolbox answers the tool** with `study_prober.probe_tool`. The
  answer is the S-sealed search's next strategy, computed from the session's
  own `history_json`. A malformed or oversized request gets a typed refusal,
  and the toolbox's protected-material check runs first.
- **The prober for VALIDATOR-30's runner** (#876, `--prober MODULE:OBJECT`)
  is `study_prober:sealed` or `:revealed`:
  - each is a factory that returns a fresh `ContractProber`, whose
    `propose(feedback)` returns a JSON-ready strategy document;
  - S-revealed accepts the batch score alone;
  - a `REPEATED` answer visits its recipe, so it is never proposed again.

  #876 left the object's name and return type open; this record fixes them,
  and the run sheet's D.3 states them.

**Tests.** `tests/cpu/test_rate_study_probe_tool.py`, 19 passed natively:
- ordinary roles are unchanged, with digests pinned;
- the study role adds only the tool, and no other study role exists;
- the study toolbox answers as the prober would, and the ordinary
  Constructor refuses the tool;
- malformed and protected requests are refused;
- `REPEATED` is never re-proposed;
- `ContractProber` matches `Prober`.

The brief test needs POSIX (`fcntl`) and runs in CI.

**Not claimed.**
- **The study route itself** (VALIDATOR-30 slices A and B) is not built
  here.
- **No proof the tool helps.** Whether an LLM gains anything from the tool
  is what G-sealed measures.
