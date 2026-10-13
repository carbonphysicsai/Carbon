# Launchpad multi-validator submissions and construction options (LP-04)

Implemented DEVELOPMENT controls. These changes neither expose a validator nor
open construction types, qualify security/science, deploy, or activate LIVE.
Launchpad owns operator and outside-network acceptance and deployment.

## Validators

Setup reads every distinct published validator for the selected network,
subnet and Challenge. The existing published-endpoints entry fields stay the
same. Multiple entries for one Challenge are permitted when both URL and receiver
are distinct; a conflicting or malformed list publishes nothing. The held
endpoint-publication PR's data file is unchanged by LP-04.

A multi-validator runner profile has an optional receiver-paired list:

```json
{
  "intake_targets": {
    "battery-fastcharge-ageing-development-v1": [
      {"intake_url": "https://validator-one.example", "receiver_hotkey": "<its public ss58 hotkey>"},
      {"intake_url": "https://validator-two.example", "receiver_hotkey": "<its public ss58 hotkey>"}
    ]
  }
}
```

The placeholders above are documentation, refused as real receiver addresses.
`carbon_setup_review` accepts this same `intake_targets` field for the miner's
own validators, checking each receiver. Setup records the list and preserves
own lists for reinstall review. Published lists are read again on review.
At most 32 distinct validators per Challenge bounds configuration and concurrent
trips. HTTPS and the existing own-loopback URL rule are retained.

Historical single-intake `intakes`/`receivers` and `battery_intake` profiles keep
their previous behavior. A newly written multi-target profile also retains its
first URL/receiver in those fields for older display readers; evaluation uses
the complete paired list, not that primary pointer to select a result.

The runner sends the same frozen strategy and contract to each validator,
using that validator's receiver after comparing its public facts with the pin.
Each canonical URL/receiver pair has a separate private receipt journal.
Reordering does not submit twice, substitute a receiver, or re-read a cached
verdict. One unreachable or refusing validator does not prevent another's send.
The existing commitment gate binds the frozen model before its initial trip;
each validator still enforces its own admission and per-hotkey window.

The page and campaign feedback show each validator independently. The
prospective `carbon.battery.permitted-feedback.multi.v1` schema's
`MULTI_VALIDATOR` state is an execution summary, never a combined score,
scientific agreement or qualification. Individual outcomes keep the existing
allow-listed projection and sealed-result policy. Connection/infrastructure
failures remain infrastructure, never evidence of a bad model.

Queued targets retain their receipt and the frozen candidate. Subsequent
submit/observe uses their recorded submission, preserving receiver, read-floor
and tempo guards. Successful targets use cached independent verdicts. No
cross-validator averaging, best-score selection, ranking or settlement policy
is added.

Completed peers are projected immediately while another trip is still waiting;
pending states do not claim an admission or a scientific result.

When a queued target's local directory/read-floor mark cannot be written, its
row stays QUEUED with a typed infrastructure read error. Its candidate remains
pending while due peers can finish. Recovery reuses cached peer verdicts and
retains the existing floor and once-per-tempo rules.

For an agent-selected model, a stale commitment can request one shared
same-digest recommit through the existing miner-confirmed gate. Each target
keeps the existing one-retry bound; concurrent stale targets share that one
attempt, including a refusal. Own selection never requests a post.

## Construction choices

`carbon_options` and the browser read the same `construction_options` document.
Every registered public change type is listed in plain words, with Available
or Coming soon and its reason. The document binds the public unified digest,
registered ceiling, type opening, check health and serving facts. The current
battery ceiling is unresolved (`null`), and its widenings remain INTERNAL;
they are Coming soon. Hoped-for Level 4 is never substituted for an owner record.

A changed type requires an explicit ceiling, external opening and permitted
arm, passing registered checks, and matching receiver-checked serving facts to
be displayed as available. This describes registered configuration, not
scientific or security qualification. Contract failure is explicitly
PUBLIC_CONTRACT_UNAVAILABLE; an empty catalog is not reported as a pass.

PLT-16's pure classifier is on main, but the composed door wiring in
CONSTRUCTION-CONTRACT-01 S3 is still pending. Both browser and MCP launch
schemas retain `construction_level` and `arm` until S3 supplies the derived
summary. The options document explicitly reports this level-bound launch mode.
The shared classifier previews construction widening before the existing base
check-design path; it does not grant composed admission.
Historical level-bound campaigns retain their versioned manifests, compile,
freeze and commitment interpretation. No historical rescore or ladder cutover
occurs here. Unified intake routing and each type's external security opening
remain their separately owned work.

For a campaign bound to `battery-l4-graph-v3`, validate and compile return the
non-blocking notice when `composition_graphs` accompanies `width` or `depth`:
"width and depth are ignored at Level 4: the graph sets the layers. They'll be
refused from graph-v4." Both doors read it beside the public tool result; it
changes no validation verdict, freeze, commitment or submission. The notice is
absent without the graph or those fields, and is not applied to v4. V4's typed
field refusal remains the registered compiler's responsibility. After S3 lands,
this same LP-04 work must consume its derived label/changes before signing and
remove the manual level fields; that cutover remains a dependency hold.
