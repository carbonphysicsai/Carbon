'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),F=require('../src/engine.js'),E=require('../src/c05_evidence.js'),G=require('../src/workflow.js'),R=require('../tools/run_operational_rehearsal.cjs');
const protocol=JSON.parse(fs.readFileSync(path.join(ROOT,'data/goal_workbench_03_rehearsal_protocol_v1.json'))),conformance=JSON.parse(fs.readFileSync(path.join(ROOT,'data/grok_v1_9_conformance_v1.json')));
const sha=raw=>crypto.createHash('sha256').update(raw).digest('hex');

function design(){const job=G.newJob('impact-job','Impact audit'),d=job.designs[0];return d;}

test('rehearsal protocol freezes three journeys and fail-closed operating rules',()=>{
  assert.equal(protocol.decision_id,'GOAL-WORKBENCH-03');
  assert.deepEqual(protocol.journeys.map(x=>x.journey_id),['GW03-A-BURGERS-DYNAMICS','GW03-B-FRONT-RESOLUTION','GW03-C-UNSUPPORTED-RIGHTS']);
  assert.equal(protocol.fixed_rules.maximum_correction_passes,1);
  assert.equal(protocol.fixed_rules.routine_polling,false);
  assert.equal(protocol.fixed_rules.timeout_means_not_started,false);
  assert.equal(protocol.fixed_rules.variant_a_baseline,'RETAIN_A_DEVELOPMENT');
  assert.equal(protocol.fixed_rules.training_permitted,false);
  assert.equal(protocol.fixed_rules.launch_permitted,false);
  assert.equal(protocol.operating_source.source_docx_sha256,'799108791ec951ebfd51b2d56c35f70df51ebc559929a4991cc118efd13981b5');
  assert.equal(protocol.operating_source.source_docx_digest_status,'VERIFIED_BEFORE_RENDER');
});

test('Grok v1.9 mapping covers roles, correction, no-polling, timeout, pilot and projections without a connector claim',()=>{
  const rules=conformance.mappings.map(x=>x.source_rule).join('\n');
  for(const phrase of ['one lead','One correction pass','No routine polling','timeout','Foundax FNO','H1','Ryan','N1','pilot rules','actual tool routes'])assert.match(rules,new RegExp(phrase,'i'));
  assert.deepEqual(conformance.verified_connectors,[]);
  assert.deepEqual(conformance.verified_local_routes,['C-AUTH1 fixed local CLI']);
  assert.equal(conformance.source_docx_sha256,'799108791ec951ebfd51b2d56c35f70df51ebc559929a4991cc118efd13981b5');
  assert.ok(conformance.unavailable_routes.includes('Grok account'));
  assert.deepEqual(conformance.divergences,[]);
});

test('operating event validator permits one correction then precise blocker and forbids polling, second correction, and timeout inference',()=>{
  const valid=R.validateOperatingEvents([{type:'CORRECTION_PASS'},{type:'PRECISE_BLOCKER'}]);
  assert.equal(valid.correction_passes_used,1);
  assert.equal(valid.poll_events,0);
  assert.throws(()=>R.validateOperatingEvents([{type:'POLL'}]),/polling/);
  assert.throws(()=>R.validateOperatingEvents([{type:'CORRECTION_PASS'},{type:'CORRECTION_PASS'},{type:'PRECISE_BLOCKER'}]),/exceeded/);
  assert.throws(()=>R.validateOperatingEvents([{type:'TIMEOUT',inference:'NOT_STARTED'}]),/cannot prove/);
  assert.throws(()=>R.validateOperatingEvents([{type:'CORRECTION_PASS'}]),/precise blocker/);
});

test('runtime Grok source verification rejects bytes that do not match the frozen digest',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gw03-plan-')),fake=path.join(dir,'Carbon_Grok_Master_Plan_v1_9.docx');
  try{fs.writeFileSync(fake,'not the operating source');assert.throws(()=>R.verifyGrokPlan(fake,protocol.operating_source.source_docx_sha256),/digest mismatch/);}
  finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('CPES change impact is scoped and commercial notes do not stale protection or economics',()=>{
  const population=design();G.recordImpact(population,'population','changed sample population');
  assert.deepEqual(population.cpes.invalidated_by,['population: CPES economics']);
  const score=design();G.recordImpact(score,'score','changed evidence depth');
  assert.deepEqual(score.cpes.invalidated_by,['score: CPES economics']);
  const reference=design();G.recordImpact(reference,'reference','changed reference role');
  assert.deepEqual(reference.cpes.invalidated_by,['reference: CPES protection, CPES economics']);
  const disclosure=design();G.recordImpact(disclosure,'disclosure','changed feedback scope');
  assert.deepEqual(disclosure.cpes.invalidated_by,['disclosure: CPES protection']);
  const commercial=design();G.recordImpact(commercial,'commercial_note','editorial pricing note');
  assert.deepEqual(commercial.cpes.invalidated_by,[]);
  assert.equal(commercial.change_log[0].kind,'EDITORIAL_OR_COMMERCIAL');
});

test('three-journey rehearsal is deterministic and stops before authority',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gw03-test-')),a=path.join(dir,'a.json'),b=path.join(dir,'b.json');
  try{
    const first=R.run(a),second=R.run(b);
    assert.equal(sha(fs.readFileSync(a)),sha(fs.readFileSync(b)));
    assert.deepEqual(first,second);
    assert.equal(first.protocol_sha256,sha(fs.readFileSync(path.join(ROOT,'data/goal_workbench_03_rehearsal_protocol_v1.json'))));
    assert.equal(first.conformance_sha256,sha(fs.readFileSync(path.join(ROOT,'data/grok_v1_9_conformance_v1.json'))));
    const [supported,front,unsupported]=first.journeys;
    assert.equal(supported.authoring_status,'INTENT_PRESERVED');
    assert.equal(supported.diagnostic_status,'NOT_EXECUTED');
    assert.equal(supported.native_launch_interface,'UNAVAILABLE');
    assert.equal(front.authoring_status,'INTENT_MISMATCH');
    assert.equal(front.emitted_goal,'Dynamics');
    assert.equal(front.qualification,'NOT_QUALIFIED');
    assert.equal(unsupported.authoring_route,'SOURCE_OWNER_EXTENSION');
    assert.equal(unsupported.duplicate_disposition,'DEDUPLICATED');
    assert.equal(unsupported.launch_status,'NOT_LAUNCHED');
    assert.equal(first.cpes_assertions.baseline,'RETAIN_A_DEVELOPMENT');
    assert.deepEqual(first.cpes_assertions.blockers,['AT-09','AT-16','AT-19','AT-22','AT-30']);
    assert.equal(first.friction.human_active_minutes,null);
    assert.equal(first.friction.poll_events,0);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
