# OWNER-F02-STAGE2-CAP-35-MOVE-BACK-LIUM-01: work moves back to Lium; Burst Thermal 3.0 Stage-2 card cap USD 35

Date: 2026-11-01 (CST), ~19:25
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722), after the 19:03 CST Lium deletion and his top-up.
Owner's words: "Move back to Lium. Approve all here", then, to the Lead's question on the cap, the option "Yes: raise the Burst Thermal 3.0 Stage-2 card cap to USD 35, within the week's USD 250."

## Decided
- The jobs moved to owned hosts during the outage (Burst Thermal 3.0 Stage-2 reruns on the AX42, MOT-EXTU-01 on the Hostkey) move back to fresh Lium pods; the owned hosts go back to custody and their normal roles.
- Card F02-STAGE2-01 (the signed pod sets, their reruns and the 63 edge jobs) gets a cap of USD 35, replacing OWNER-F02-STAGE2-CAP-20-01. USD 6.76 of the first run was spent before the deletion and counts.
- Every other restart (Runner gate pods, leak set B, COOL-EXTU, COOL18, RB 2.0 C7, the TE build pod, MOT-EXTU) runs under its existing card cap and Launchpad's standing approval, within the week's USD 250 (record e6c454b7). Any card that would exceed its cap comes back to the owner with a figure.
- Fresh pods only; the deleted pods' ports and host keys are never reused.
