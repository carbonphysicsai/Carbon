# PLT36-D1: prepare controlled padding without a launch capability

The source preflight probe provisions directly after balance arithmetic; it
does not claim a dedicated probe grant or independently guarantee pod deletion
after controller interruption. Expanding its spending CLI now would leave
unresolved execution/accounting inputs behind an apparently ready command.

Use a separate offline helper that accepts the existing fixed-sleep probe spec,
adds one fixed-name padding variable to an exact runtime-character target,
and rechecks the existing guard before returning it. Build the spec through
RunPodPods.pod_spec. Measure character, UTF8, environment JSON and full request
bytes using the adapter's existing create_body and exact default JSON serializer,
including the injected ownership tag. No values, request bytes or hashes of
private inputs appear in the numeric report.

The helper has no provisioning entry point, credential or usable transport.
Do not modify pods.py, preflight.py, the transport/closure, any grant or limit.
This also avoids competing with Platform's structural PLT-29 work. The new
script/tests/docs can be removed independently if superseded; existing public
interfaces and historical receipts do not migrate.

At most four sequential host creates are the proposed first tranche; missing
finite cleanup/reconcile caps, independent deletion, dedicated grant claim,
approved offer/rate and stock/headroom remain explicit blocking inputs. Sleep
exit or a listing miss does not prove deletion/noncreation or zero charges.
The owner sets any new figure and guard after controlled evidence, not this code.
Primary map SYSTEM/AGENT-EXECUTION; Hub retired under OWNER-DX-03.
