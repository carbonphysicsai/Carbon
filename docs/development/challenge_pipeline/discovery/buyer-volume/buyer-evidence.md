# Buyer evidence and the units it can support

**Research only.** Source IDs resolve in [evidence.json](evidence.json), accessed
2026-10-09. Numeric notation throughout is **low / base / high**. Sourced point
triples preserve the author's report; they do not assert a confidence interval.
`HUMAN_INPUT` means an unknown, including the upper end of a censored count.

## Battery v3: engineering work and deployed sessions are separate

The engineering buyer is a BMS/charging calibration or battery thermal-management
team choosing safe protocol/cooling recipes and releasing an offline map. The
deployment-value beneficiary may instead be a fleet operator or driver. Those
roles need not be the same purchaser.

**Exponent Energy:** Richard Davis, lead system architect, describes developing
the BMS, charger and thermal system with MATLAB/Simulink, Simscape and generated
embedded code. The case reports whole-solution development, testing and
verification acceleration of **at least 5 / HUMAN_INPUT / HUMAN_INPUT times**.
This supports a real calibration/deployment workflow and schedule value, but it
does not isolate a solver bottleneck, map revisions/year, DOE count or the
incremental saving Carbon could produce. B01:
[customer case](https://www.mathworks.com/company/user_stories/exponent-energy-develops-a-15-minute-fast-charging-battery-system-for-electric-vehicles-using-model-based-design.html).

**Mahindra Electric:** Vipin K. Venugopal's team uses Simscape and Simulink to
choose BTMS component configurations, tune operating parameters and develop
compressor logic. This is direct evidence of the cooling/control job, with an
existing system model as an incumbent. Annual programmes, scenario counts and
recalibration cadence are absent. B02:
[engineering presentation](https://in.mathworks.com/company/user_stories/case-studies/mahindra-electric-uses-system-level-simulation-to-optimize-battery-thermal-management-system-for-an-electric-vehicle.html).

**PATAC:** Chen Bowen, vehicle energy consumption integration engineer, reports
a calibrated low-temperature vehicle thermal model using Simscape Fluids and
Simulink Design Optimization. Reported setup time is
**3 / HUMAN_INPUT / 4 months**; reported physical testing avoided is
**2,000 / 2,000 / 2,000 hours**. This is a useful adjacent value observation,
but low-temperature driving-range optimization is broader than Carbon's
fast-charge map. Setup duration is not an annual programme count; physical-test
hours are not solver evaluations or avoided labour attributable to Carbon.
B03: [customer case](https://www.mathworks.com/company/user_stories/patac-optimizes-ev-thermal-management-modeling.html).

Volkswagen documents charging-performance changes through its ID. software
updates. This confirms that a released charging policy can be revised, including
on installed vehicles. It does not establish a periodic annual cadence, a
fresh electrochemical bank on every software release or today's evaluation
count. B04: [OEM update documentation](https://www.volkswagen.co.uk/en/owners-and-services/my-car/software-update/software-update-3-0.html/__layer/layers/owners/software_update/software-update-3-0/improved-charging-performance/master.layer).

The annual deployment proxy is stronger than a vehicle-stock proxy:
Electrify America's own CEC filing reports **>16,000,000 / HUMAN_INPUT /
HUMAN_INPUT charging sessions in 2024** on its national network. It does not
identify a particular cell family, thermal state, controller, fleet, bottleneck
eligibility or buyer-controlled rollout. Eligible sessions remain
`HUMAN_INPUT`. The source's count cannot replace the existing scenario.
B05: [filed company statement, attachment opening page](https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=103159&tn=266135).

For evaluations within a decision, Attia et al. report a menu of
**224 / 224 / 224 protocols**, of which **117 / 117 / 117 were never tested**,
in an experimental closed-loop study. These are not annual OEM programmes or a
menu of fully evaluated Carbon reference cases. The chemistry, experiment and
constraints differ. B06: [primary paper, pp. 1–3](https://web.mit.edu/braatzgroup/Attia_Nature_2020.pdf).

The strongest cheap comparison must include already validated lookup maps and
calibrated system models. Ansys documents a fast-charge current table indexed
by depth of discharge and temperature, with interpolation. Once a feasible map
exists, repeated serving can be cheap. Carbon's plausible value is better
decisions during a genuine new recipe/context search, with retained validation
and setup cost included; it has no demonstrated need to solve physics on every
charging session. B07:
[Fluent fast-charge lookup documentation](https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/flu_ug/flu_bat_MSMD_sec_use_battery_model.html).

**Finding:** buyer/workflow supported; annual exact engineering volume,
eligible deployed volume, complete per-decision simulation ledger and
incremental monetary value all remain `HUMAN_INPUT`. Existing positive V2/V3
ranges stay assumptions.

## Robot-joint motor: custom magnetics versus selection and control

Universal Robots' Esben H. Ostergaard, technical business manager, describes
using specially adapted Kollmorgen KBM frameless motors inside robot joints.
This is a named commercial integration decision. It supports size, torque,
cogging, heat and manufacturability concerns. It supplies neither annual new
magnetic designs nor a solver ledger. Stock frame options can serve multiple
arms and production units, so do not multiply arm shipments by joint count.
M01: [supplier/customer case](https://www.kollmorgen.com/en-us/service-and-support/knowledge-center/success-stories/direct-drives-in-lightweight-robots).

Siemens' robotics workflow begins with mission profiles and required actuator
torque/speed/power, then catalogue selection. This strengthens the cheap
incumbent and shows why a custom magnetics Challenge applies to a narrower
subset of programmes. M02:
[Simcenter engineering workflow](https://blogs.sw.siemens.com/simcenter/robotics-engineering/).

Figure's Electrical Engineer, Actuator Systems posting establishes a current
buyer-side engineering team performing motor-control/power-electronics trade
studies with simulation experience. Its duties concern PCBAs and control;
LTspice does not establish magnetic FE geometry work. The posting cannot
confirm annual motor-family revisions or supply a fully loaded hourly value.
M03: [employer job description](https://job-boards.greenhouse.io/figureai/jobs/4688381006).

A task-oriented geared-actuator study by Huang, Dong and Zhao uses separate
quadratic ridge surrogates for **7 / 7 / 7 slot-pole combinations**, each with
**1,000 / 1,000 / 1,000 valid cross-sectional training designs**. It reports
**1,488 / 1,488 / 1,488 hardware evaluations per enumerated optimization
case**, using surrogates and analytical models. These optimizer evaluations
are not new field solves. This provides a relevant workload analogue and
a stronger incumbent than analytical magnetics alone; it is university
research, not a company's annual procurement or design ledger. M04:
[primary paper, III-C and III-F](https://arxiv.org/html/2609.22795v1).

**Finding:** commercial joint integration and task-driven repeated design are
supported, but the exact precision-joint magnetic question, annual geometry
revisions, complete command-panel evaluations and avoided rework remain
unverified. Faster catalog selection, robot-policy training and torque-density
improvements in another architecture cannot populate Carbon's V2.

## Package warpage: brief evidence update

Amkor's Nathan Whitchurch describes comparing underfill and other package
choices, and a coupled large-body thermal/structural workflow using Icepak and
Workbench Mechanical. ASE offers ANSYS-based BGA stress/warpage simulation from
customer design parameters. Its thermal-service turnaround is a different
output and must not become warpage latency. W01:
[Amkor engineering case](https://amkor.com/blog/thermal-simulation-of-dsmbga-coupled-thermal-mechanical-simulation-of-large-body-hdfo/);
W02: [ASE service](https://ase.aseglobal.com/package-design/).

Amkor's mechanical characterization sheet explicitly places quick calculators
and numerical DOE before detailed FE, actual warpage measurements and
reliability tests. This is direct evidence of the buyer's current cheap-to-detailed
workflow. None of these sources gives annual full-history stack decisions,
DOE/FE counts for the exact job, rebuild cadence or monetized avoided error.
W03: [service sheet](https://amkor.com/kr/wp-content/uploads/2018/02/Mechanical_Package_Characterization_SS23.pdf).
D016 stays a conditional research hypothesis; no original 3D job is narrowed.

## Solenoid pole: brief evidence update

Bosch authors Fuchs, Ott and Bauer, with Mantwill, describe choosing proportional
solenoid topology/materials/tolerances against customer force-stroke curves,
using optiSLang, scripted geometry and Gmsh. The workflow reports a
**4,000 / 4,000 / 4,000 design** sensitivity study; each solver call takes
approximately **5 / 5 / 5 minutes**, while a Metamodel of Optimal Prognosis
replaces subsequent calls. Robustness analysis uses
**50 / 50 / 50 additional metamodel variants**. No annual fresh pole-design
count or exact complete-panel latency is given. The case is unusually close to
D012 and makes response-surface competition essential. It does not prove
Carbon's incremental advantage. S01:
[industrial case, pp. 4 and 6](https://ansys.synopsys.com/content/dam/resource-center/case-study/cost-function-optimization-applied-proportional-solenoid.pdf).

Magnet-Schultz confirms customer-specific electromagnetic development with
simulation/calculation, but gives no annual frequency. IMI's Murray Schofield,
Simulation Design Engineer, reports an already-fast Amesim valve/system
analysis of **5 / 5 / 5 minutes**; this is a separate system workflow, not a
magnetic pole panel. S02:
[supplier development](https://www.magnet-schultz.com/produkte);
S03: [IMI customer case](https://resources.sw.siemens.com/en-US/case-study-imi-precision-engineering/).
Annual decisions and incremental value remain `HUMAN_INPUT`.
