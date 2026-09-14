#!/usr/bin/env node
'use strict';

const crypto=require('node:crypto'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),REPO=path.resolve(ROOT,'../../..'),G=require('../src/workflow.js');
const PROTOCOL_PATH=path.join(ROOT,'data/goal_workbench_03_rehearsal_protocol_v1.json');
const CONFORMANCE_PATH=path.join(ROOT,'data/grok_v1_9_conformance_v1.json');
const BRIDGE=path.join(ROOT,'tools/authoring_bridge.py');
const sha=raw=>crypto.createHash('sha256').update(raw).digest('hex');
const clone=value=>JSON.parse(JSON.stringify(value));

function sourceDigest(pathname){return sha(fs.readFileSync(pathname));}
function verifyGrokPlan(pathname,expected){const actual=sourceDigest(pathname);if(actual!==expected)throw Error('Grok v1.9 source digest mismatch');return actual;}

function supportedDesign(goal='Dynamics'){
  const job=G.newJob('gw03-'+goal.toLowerCase().replaceAll(' ','-'),'Synthetic '+goal+' rehearsal'),design=job.designs[0];
  Object.assign(job.assignment,{client_words:'Use a bounded public synthetic flow task to decide whether the declared field evolution is preserved.',client_source:'GOAL-WORKBENCH-03 synthetic rehearsal',intended_decision:'Prepare a DEVELOPMENT-only Challenge design or return a precise extension request.',credible_baseline:'Retain the existing source-defined public Burgers baseline.',context:'No real customer or protected data.',allowances:'No training, solver execution, protected exam, or launch.',rights_summary:'SYNTHETIC_INTERNAL only.',next_owner_decision:'Decide whether source-owned evidence supports the next bounded review.'});
  job.lead='S1';
  Object.assign(design.scope,{physics_family:'periodic_viscous_burgers_1d_v1',requested_goal:goal,intended_use:'Use the bounded public DEVELOPMENT Burgers template to test semantic authoring and handoff behavior without qualification, execution, or launch authority.',inputs:'Finite Fourier initial field, viscosity, and requested times',outputs:'Complete periodic field evolution',units:'source-defined nondimensional variables',geometry:'one-dimensional periodic domain',conditions:'Periodic, unforced, positive viscosity',regime:'source-defined 12-cell DEVELOPMENT population',exclusions:'No customer, protected, or production scope',query_workload:'Closed source-defined public campaign',turnaround:'No service limit established',failure_consequences:'A mandatory physical failure or missing requested work makes the candidate ineligible.',data_access:'Public synthetic fixtures only',rights_scope:'SYNTHETIC_INTERNAL'});
  design.requirements=[G.requirement('REQ-FIELD','Predict the complete declared field evolution.','synthetic rehearsal statement','Determine whether the bounded source template preserves the requested output','MATERIAL')];
  const trace=G.trace('TRACE-FIELD','REQ-FIELD');
  Object.assign(trace,{observable:'periodic field over declared times',requested_output:'complete requested field',measurement_definition:'source-owned measurement proposal',numerical_method:'source-owned DEVELOPMENT operator',role:'MANDATORY',normalization:'source-defined normalization',floor:'source-defined DEVELOPMENT floor',aggregation:'mandatory admissibility before soft quality',uncertainty:'source-owner evidence required',population_ref:'goal_burgers_12cell_v1',stratum_ref:'source 12-cell plans',finite_case_coverage:'source plan only; numerical adequacy unqualified',reference_requirement:'source C-04 candidate and witness references',authoring_binding:'measurement_proposal',gap:''});
  design.traces=[trace];
  const family=G.caseFamily('CASE-EVAL','EVAL');
  Object.assign(family,{requirement_ids:['REQ-FIELD'],target_population:'source public Burgers population',target_mass:'one twelfth per source cell',sampling_frequency:'four parents per source cell',analysis_weight:'one twelfth per source cell',independent_physical_cases:'source-defined DEVELOPMENT plan',reconstruction_replicas:'separate source-owned count',generator_ref:'goal_burgers_12cell_v1',rationale:'Covers the sole material synthetic requirement.',support_status:'SOURCE_SUPPORTED'});
  design.cases=[family];
  Object.assign(design.score_plan,{mandatory_gate_summary:'Source mandatory physics precedes ranking.',soft_estimand:'Source population-weighted quality proposal.',unresolved_tradeoffs:'Numerical qualification and customer trade-offs remain unresolved.'});
  Object.assign(design.reference_plan,{equation:'u_t + d_x(u^2/2) = nu*u_xx',role:'source-owned candidate and witness reference roles',method:'source C-04 candidate and witness references',configuration:'source-defined public DEVELOPMENT configuration',convergence_evidence:'Not qualified by this rehearsal',uncertainty_evidence:'Not executed',applicable_envelope:'Exact public Burgers template only',failures:'Retain failed and censored cases',cost_scope:'Unknown qualified reference cost',independence_limitations:'Source-owner review required'});
  return {job,design};
}

function response(design,handoff,{id,kind,status,digestChar='a'}){return {schema_version:G.RESPONSE_VERSION,response_id:id,request_id:handoff.request_id,base_revision:design.revision,job_id:design.job_id,design_id:design.design_id,design_revision:design.revision,kind,route:'TEST_FIXTURE',source_owner:'Synthetic rehearsal fixture',status,output_reference:'public-synthetic-response',input_digest:'sha256:synthetic-rehearsal',authority_class:'SYNTHETIC_TEST_EVIDENCE',verification_reference:'GOAL-WORKBENCH-03 rehearsal',limitations:'Interface evidence only; no actual owner decision, execution, qualification, rights acceptance, or launch.',note:'Untrusted text stays inert: </script><img src=x onerror=globalThis.pwned=true>',content_sha256:digestChar.repeat(64)};}

function handoffFor(design,id,question){return G.handoff(design,{request_id:id,recipient:'S1',lead:'S1',question,required_output:'Return the exact request/job/design/revision binding, scoped result or blocker, implementation layer, limitations, and artifact digest.',route:'MANUAL',permitted_data:'Public synthetic summaries only',rights:'SYNTHETIC_INTERNAL',required_authority:'Source owner retains all scientific and execution authority.',allowance:'One correction pass maximum; no routine polling.',stop_condition:'After one unsuccessful correction, emit a precise blocker and stop.',input_refs:['GOAL-WORKBENCH-03'],dependency_owner:'Named source owner',restart_event:'A versioned source-owner response for this exact request and design revision.',native_task_id:''});}

function compile(design,request,temp){
  const requestPath=path.join(temp,request.request_id+'.json'),output=path.join(temp,request.request_id);
  fs.writeFileSync(requestPath,JSON.stringify(request,null,2)+'\n');
  const run=spawnSync('python3',[BRIDGE,requestPath,output],{cwd:REPO,encoding:'utf8',env:{...process.env,PYTHONPATH:REPO}});
  if(run.status!==0)throw Error('authoring bridge failed: '+run.stderr.trim());
  const resultPath=path.join(output,'workbench-authoring-result.json'),raw=fs.readFileSync(resultPath),result=JSON.parse(raw);
  const receipt=G.importAuthoringResult(design,request,result);
  return {receipt,result_sha256:sha(raw),proposal_digest:result.proposal_digest,source_revision:result.source_revision};
}

function validateOperatingEvents(events){
  const corrections=events.filter(event=>event.type==='CORRECTION_PASS').length;
  if(corrections>1)throw Error('operating rehearsal exceeded one correction pass');
  if(events.some(event=>event.type==='POLL'))throw Error('routine polling is forbidden');
  if(events.some(event=>event.type==='TIMEOUT'&&event.inference==='NOT_STARTED'))throw Error('timeout cannot prove native work never started');
  if(corrections===1&&!events.some(event=>event.type==='PRECISE_BLOCKER'))throw Error('one correction pass must end in a precise blocker when unresolved');
  return {correction_passes_used:corrections,correction_limit:1,poll_events:0,timeout_start_inference:false,status:corrections?'PRECISE_BLOCKER_RECORDED':'NO_CORRECTION_NEEDED'};
}

function run(outputPath,{grokPlanPath=null}={}){
  const protocolRaw=fs.readFileSync(PROTOCOL_PATH),conformanceRaw=fs.readFileSync(CONFORMANCE_PATH),protocol=JSON.parse(protocolRaw),conformance=JSON.parse(conformanceRaw);
  if(protocol.fixed_rules.maximum_correction_passes!==1||protocol.fixed_rules.routine_polling!==false)throw Error('unsupported operating protocol');
  if(grokPlanPath)verifyGrokPlan(grokPlanPath,protocol.operating_source.source_docx_sha256);
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'goal-workbench-03-'));
  try {
    const a=supportedDesign('Dynamics'),aCoverage=G.coverage(a.design),aDiagnostic=G.diagnosticRequest(a.design,'gw03-a-diagnostic'),aRequest=G.authoringRequest(a.design,'gw03-a-authoring'),aCompile=compile(a.design,aRequest,temp),aHandoff=handoffFor(a.design,'gw03-a-handoff','Does this public synthetic result support the next bounded DEVELOPMENT review?');
    G.markExported(a.design,aHandoff.request_id);
    const aAck=response(a.design,aHandoff,{id:'gw03-a-ack',kind:'ACKNOWLEDGMENT',status:'RECEIVED'}),aResult=response(a.design,aHandoff,{id:'gw03-a-result',kind:'RESULT',status:'SCOPED_SYNTHETIC_RESULT_RETURNED',digestChar:'b'});
    G.importResponse(a.design,aAck);G.importResponse(a.design,aResult);
    const aLaunch=G.launchCandidate(a.design);

    const b=supportedDesign('Front Resolution'),bRequest=G.authoringRequest(b.design,'gw03-b-authoring'),bCompile=compile(b.design,bRequest,temp),bHandoff=handoffFor(b.design,'gw03-b-extension','Can the source owner provide a versioned active Front Resolution template without changing the client request?');
    G.markExported(b.design,bHandoff.request_id);
    const bBlock=response(b.design,bHandoff,{id:'gw03-b-blocker',kind:'BLOCKER',status:'ACTIVE_GOAL_TEMPLATE_UNAVAILABLE',digestChar:'c'});G.importResponse(b.design,bBlock);

    const cJob=G.newJob('gw03-unsupported','Synthetic unsupported client-rights scope'),c=cJob.designs[0];
    cJob.lead='S1';Object.assign(c.scope,{physics_family:'customer_heat_transfer_v1',requested_goal:'Customer thermal decision',intended_use:'Preserve an unsupported synthetic customer-like physics and rights request until the named source owners return a scoped capability and rights decision.',inputs:'customer-defined thermal inputs unresolved',outputs:'temperature and decision observables unresolved',units:'physical units unresolved',geometry:'customer geometry unavailable to this browser',conditions:'boundary and forcing conditions unresolved',regime:'customer operating envelope unresolved',exclusions:'No substitution with Burgers',query_workload:'unresolved',turnaround:'unresolved',failure_consequences:'unsafe or late output consequence unresolved',data_access:'No confidential data supplied',rights_scope:'CLIENT_RESTRICTED'});
    c.requirements=[G.requirement('REQ-C-SCOPE','Preserve the requested customer thermal scope and rights without substitution.','synthetic unsupported rehearsal','Decide which source-owned authoring and rights interfaces are required','CONSTRAINT')];
    const cRequest=G.authoringRequest(c,'gw03-c-extension'),cHandoff=handoffFor(c,'gw03-c-handoff','Which source-owned physics, measurement, generator, reference, and rights decisions are required for this preserved request?');
    G.markExported(c,cHandoff.request_id);
    const cBlock=response(c,cHandoff,{id:'gw03-c-blocker',kind:'BLOCKER',status:'WAITING_ON_NAMED_SOURCE_OWNER',digestChar:'d'}),first=G.importResponse(c,cBlock),duplicate=G.importResponse(c,cBlock);
    const cEvents=[{type:'PREPARED'},{type:'EXPORTED'},{type:'BLOCKER_RETURNED'},{type:'CORRECTION_PASS'},{type:'PRECISE_BLOCKER',restart_event:cHandoff.restart_event}],cOperating=validateOperatingEvents(cEvents);

    const record={schema_version:'carbon.goal-workbench.operational-rehearsal-record.v1',decision_id:protocol.decision_id,protocol_sha256:sha(protocolRaw),conformance_sha256:sha(conformanceRaw),application_baseline:protocol.application_baseline,source_conformance:{source_version:conformance.source_version,source_docx_sha256:conformance.source_docx_sha256,source_docx_digest_status:conformance.source_docx_digest_status,rendered_pdf_sha256:conformance.rendered_pdf_sha256,mapping_count:conformance.mappings.length,divergences:conformance.divergences},journeys:[{journey_id:'GW03-A-BURGERS-DYNAMICS',coverage:aCoverage,diagnostic_status:aDiagnostic.status,diagnostic_route:aDiagnostic.route,authoring_status:aCompile.receipt.status,authoring_result_sha256:aCompile.result_sha256,proposal_digest:aCompile.proposal_digest,source_revision:aCompile.source_revision,response_status:a.design.handoffs[0].status,launch_candidate_status:aLaunch.status,native_launch_interface:aLaunch.native_launch_interface,authority:aLaunch.authority},{journey_id:'GW03-B-FRONT-RESOLUTION',requested_goal:bRequest.requested_goal,emitted_goal:bCompile.receipt.emitted.active_goal,authoring_status:bCompile.receipt.status,mismatches:bCompile.receipt.mismatches,extension_request:clone(b.design.authoring.extension_request),handoff_status:b.design.handoffs[0].status,qualification:bCompile.receipt.qualification,launch:bCompile.receipt.launch},{journey_id:'GW03-C-UNSUPPORTED-RIGHTS',authoring_route:cRequest.route,extension_request:clone(c.authoring.extension_request),response_disposition:first.disposition,duplicate_disposition:duplicate.disposition,handoff_status:c.handoffs[0].status,restart_event:cHandoff.restart_event,operating:cOperating,launch_status:c.decision.native_launch_status}],cpes_assertions:{baseline:a.design.cpes.baseline,blockers:G.BLOCKERS,variant_b_activation:false,qualified_reference_cost:'UNKNOWN',compatible_demand:'UNKNOWN',group_overhead:'UNKNOWN',service_limit:'UNKNOWN'},friction:{reentered_material_fields:0,handoffs_prepared:3,manual_exports:3,responses_imported:4,duplicate_responses_deduplicated:1,correction_passes:1,poll_events:0,human_active_minutes:null,human_active_minutes_status:'NOT_MEASURED',wait_duration:null,wait_duration_status:'NOT_MEASURED'},interfaces:{working:['browser-local job/design record','fixed local C-AUTH1 Burgers compiler bridge','exact-bound manual response import'],manual:['source-owner handoff delivery','measurement/score diagnostic return','owner decision'],unavailable:['Grok account connector','CRM/calendar connector','native launch status interface']},recommended_next_integration:{interface:'Source-owned measurement/score diagnostic response adapter',why:'It closes the earliest evidence gap shared by the supported path while preserving native scientific authority.',minimum_contract:'Versioned request-bound result with source revision, implementation layer, per-example execution status, limitations, artifact digest, and no qualification promotion.'},authority:'Rehearsal evidence only. No real customer, native execution beyond the public authoring compiler, scientific/security/rights qualification, sharing activation, registration, or launch occurred.'};
    fs.writeFileSync(outputPath,JSON.stringify(record,null,2)+'\n');
    return record;
  } finally {fs.rmSync(temp,{recursive:true,force:true});}
}

if(require.main===module){const args=process.argv.slice(2),planIndex=args.indexOf('--grok-plan'),plan=planIndex===-1?null:args.splice(planIndex,2)[1];if(planIndex!==-1&&!plan)throw Error('--grok-plan requires a path');const output=args[0]||path.join(ROOT,'data/goal_workbench_03_rehearsal_record_v1.json');run(path.resolve(output),{grokPlanPath:plan});}
module.exports={run,validateOperatingEvents,sourceDigest,verifyGrokPlan};
