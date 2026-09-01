# Carbon Development Hub — Decision Console

The Decision Console gives Harsh a short, contextual view of material technical
and SciML decisions without requiring him to read the full chronological issue
#42 thread.

## Open it

- Local or hosted console: [`../decisions.html`](../decisions.html)
- Current structured index: [`../data/decisions.json`](../data/decisions.json)
- Durable technical-lead response location: [issue #42](https://github.com/carbonphysicsai/Carbon/issues/42)
- Owner-deferred response location: [issue #41](https://github.com/carbonphysicsai/Carbon/issues/41)

The HTML console is intended for the same local/static-host use as the richer
Hub application. GitHub's repository file view does not execute the app.

## Queues

### Needs Me

`NEEDS_REVIEW` means Harsh should inspect a material working decision. The card
shows the stable Wave/ticket or system placement, the question, why it matters, the agent
recommendation, what keeping or changing it affects, and the exact durable
response location.

This is still asynchronous oversight unless the repository separately marks
the decision human-reserved or blocked.

### Human Required

`HUMAN_REQUIRED` means the affected behavior cannot proceed correctly without a
genuinely human-reserved choice. The behavior remains fail closed until the
human decision exists.

### For Awareness

`FOR_AWARENESS` is a material working decision that Harsh may change, block, or
defer, but no response is required. Existing B-03-D1 through B-03-D8 are seeded
here because the repository record treated their notification as non-blocking.

### Owner Deferred

`OWNER_DEFERRED` means Harsh explicitly used `DEFER_TO_OWNER` and the complete
decision package has been routed to issue #41.

### Resolved

`RESOLVED` means a durable GitHub response or prospective superseding decision
resolved the attention item. Historical decision records remain preserved.

## Response grammar

The console copies the same commands already defined by Carbon's delegated
decision protocol:

```text
KEEP <decision-id>
CHANGE <decision-id>: <direction>
BLOCKED <decision-id>: <reason>
DEFER_TO_OWNER <decision-id>: <question or recommendation>
```

The console does not post the command itself. Harsh clicks **Open response
location** and puts the response in GitHub so the answer remains durable and
auditable.

## Agent rule

Whenever an agent posts a material decision to issue #42, it must create or
update the corresponding record in `data/decisions.json` in the same development
change. The attention state must reflect the repository record, not an invented
urgency level.

For a decision-only update, the focused check is:

```bash
python docs/development/carbon_hub/tools/test_decisions.py
```

No full browser or Hub-regeneration suite is required unless the change also
modifies the core Hub renderer, map state, routing, authority snapshot, or
validation contract.
