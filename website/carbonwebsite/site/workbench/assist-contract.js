/* Shared closed proposal contract. AI suggestions never establish facts or authority. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./engine.js'):root.CarbonWorkbench);if(typeof module==='object'&&module.exports)module.exports=api;else root.CarbonAssist=api;})(typeof window==='object'?window:this,function(E){
 'use strict';
 const SCHEMA='carbon.intake-assistant.proposal/1';
 const FIELDS=E.problemKeys.filter(k=>!['sourceRefs','economics','notes'].includes(k));
 function exact(v,keys){if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==keys.length||keys.some(k=>!Object.hasOwn(v,k)))throw Error('Unsupported assistant response fields.');}
 function text(v,max){if(typeof v!=='string'||v.length>max)throw Error('Assistant text exceeds its contract.');}
 function canonical(v){if(v===null||typeof v!=='object')return JSON.stringify(v);if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}
 function validate(output,job,description){
  E.validateJob(job);text(description,3000);exact(output,['summary','changes','questions']);text(output.summary,1200);
  if(!Array.isArray(output.changes)||output.changes.length>8||!Array.isArray(output.questions)||output.questions.length>3)throw Error('Assistant response exceeds its review limit.');
  const seen=new Set(),next=E.copy(job.problem);
  for(const c of output.changes){exact(c,['field','value_json','basis','quote','reason']);
   if(!FIELDS.includes(c.field)||seen.has(c.field))throw Error('Unsupported or repeated change field.');seen.add(c.field);
   text(c.value_json,16000);text(c.reason,700);text(c.quote,700);
   if(!['explicit','inferred'].includes(c.basis))throw Error('Unsupported provenance.');
   if(c.basis==='explicit'&&(!c.quote||!description.includes(c.quote)))throw Error('Explicit suggestion needs an exact quote from the description.');
   // Quote presence is traceability, not proof of semantic entailment.
   next[c.field]=JSON.parse(c.value_json);
  }
  for(const q of output.questions)text(q,500);
  E.validateProblem(next);return E.copy(output);
 }
 function pending(output,job,description,mode){return {base:canonical(job),description,mode,output:validate(output,job,description)};}
 function apply(review,job,fields){
  if(review.base!==canonical(job))throw Error('Your draft changed. Request fresh suggestions before applying them.');
  validate(review.output,job,review.description);
  if(!Array.isArray(fields)||!fields.length||new Set(fields).size!==fields.length||fields.some(f=>!review.output.changes.some(c=>c.field===f)))throw Error('Choose valid suggestions to apply.');
  const next=E.checkpoint(job,'Before reviewed assistant suggestions');
  const chosen=review.output.changes.filter(c=>fields.includes(c.field));
  for(const c of chosen)next.problem[c.field]=JSON.parse(c.value_json);
  E.exportJob(next); // Partial selections must still satisfy all cross-field constraints.
  return {job:next,provenance:{kind:review.mode==='demo'?'SCRIPTED_DEMO_CLIENT_CONFIRMED':'AI_SUGGESTED_CLIENT_CONFIRMED',source:review.description,changes:chosen,base:review.base,result:canonical(next),authority:'CUSTOMER_ASSUMPTIONS'}};
 }
 const responseSchema={type:'object',additionalProperties:false,required:['summary','changes','questions'],properties:{summary:{type:'string'},changes:{type:'array',maxItems:8,items:{type:'object',additionalProperties:false,required:['field','value_json','basis','quote','reason'],properties:{field:{type:'string',enum:FIELDS},value_json:{type:'string'},basis:{type:'string',enum:['explicit','inferred']},quote:{type:'string'},reason:{type:'string'}}}},questions:{type:'array',maxItems:3,items:{type:'string'}}}};
 return {SCHEMA,FIELDS,canonical,validate,pending,apply,responseSchema};
});
