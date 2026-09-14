#!/usr/bin/env node
'use strict';
const crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),F=require('../src/engine.js'),E=require('../src/c05_evidence.js'),G=require('../src/workflow.js');
E.installFixtureIndex(JSON.parse(fs.readFileSync(path.join(ROOT,'data/c05_fixture_index_v1.json'))));
const d=G.newJob('job-001','C-05 public DEVELOPMENT evidence').designs[0];
d.scope.physics_family='periodic_viscous_burgers_1d_v1';
d.requirements=[G.requirement('REQ-DYNAMICS','Predict complete field evolution.','public fixture','Inform bounded design')];
const trace=G.trace('TRACE-DYNAMICS','REQ-DYNAMICS');Object.assign(trace,{measurement_definition:'source C-05 measurement',authoring_binding:'carbon.goal-authoring-proposal/1',role:'MANDATORY',floor:'source-owned DEVELOPMENT normalization only'});d.traces=[trace];
const family=G.caseFamily('BURGERS-12-CELL','EVAL');Object.assign(family,{requirement_ids:['REQ-DYNAMICS'],generator_ref:'goal_burgers_12cell_v1',support_status:'SOURCE_SUPPORTED'});d.cases=[family];
const raw=fs.readFileSync(path.join(ROOT,'data/c05_public_development_evidence_v1.json'),'utf8');
const sha=async value=>crypto.createHash('sha256').update(value).digest('hex');
(async()=>{const request=G.diagnosticRequest(d,'diagnostic-job-001-design-1-r1'),result=await E.importBundle(d,request,raw,sha);fs.writeFileSync(path.join(ROOT,'data/c05_evidence_association_v1.json'),JSON.stringify(result.record,null,2)+'\n');})();
