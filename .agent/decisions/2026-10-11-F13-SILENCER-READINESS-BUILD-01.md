# F13-SILENCER-READINESS-BUILD-01 working engineering decisions

Base main: 0a848db68bf052e6d784c7b350ccd3ac2d07851b.
Owner: user assignment; scientific acceptance remains Test Lead/science.
KEEP existing f13_deck.v2; WRAP, do not run or rewrite retained v1 evidence.
Treat the extra 50 mm per port as numerical extensions, not a new saleable
package allowance. At exp(+i omega t), shift reflection by exp(2ikd) and
transmission by exp(2ikd), d=50 mm, to the original 10 mm stub planes.
Power TL is invariant only in the uniform matched single-propagating-mode
ports; modal/lead convergence must establish applicability. No renormalizing
away power findings. Report packet 1% criterion and adopted probe 0.02%
diagnostic separately; the latter is not an automatic qualification rule.

Alternative rejected: counting the 120 mm numerical leads as extra permissible
product length, or shrinking offset scope so a plane-wave competitor suffices.
Use the existing four-family EQUAL-BUDGET-V1 f13 cap; complete action curves,
all frequency work and final verification remain charged. New scientific law
values are draft recommendations, never runtime inputs.
Reversible: remove new silencer_readiness module/docs/tests; old packages,
registration and public/runtime interfaces remain unchanged. Missing accepted
refinement/uncertainty prevents buyer verdicts. Existing image pins establish
identity, not present operator-store inventory. Readiness adapter wiring waits
for #1039 to merge; its candidate is not copied into this independent PR.
