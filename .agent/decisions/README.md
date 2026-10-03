# Decisions

From 2026-10-03 (OWNER-WORKFLOW-SPEED-01), every new decision is its own file
here:

```text
.agent/decisions/YYYY-MM-DD-<ID>.md
```

- `YYYY-MM-DD` is the decision's date and `<ID>` its identifier, for example
  `2026-10-03-OWNER-WORKFLOW-SPEED-01.md`.
- The file starts with one heading, `## YYYY-MM-DD — <ID>: <title>`, the same
  form `.agent/DECISIONS.md` uses, so anything that looks a decision up by its
  heading finds it in either place.
- Owner words are quoted verbatim, as before.
- A later amendment is a new file with its own ID that names the decision it
  amends; an existing file is not rewritten.

`.agent/DECISIONS.md` holds every decision recorded before this directory
existed. It is frozen: nothing is appended to it, and its existing text stays
byte-for-byte as it is. Separate files mean two PRs that each record a
decision never conflict.
