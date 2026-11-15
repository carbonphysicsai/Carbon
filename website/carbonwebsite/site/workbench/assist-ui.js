(function(){
 'use strict';
 const E=window.CarbonWorkbench,A=window.CarbonAssist,D=window.CarbonDraftUI;
 const root=document.getElementById('carbon-live-workbench')||document;
 const $=s=>root.querySelector(s), esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const integration=window.CarbonWorkbenchIntegration;
 const liveAI=typeof integration?.assist==='function'&&integration?.config?.aiNotice;
 const liveIntake=typeof integration?.submit==='function'&&integration?.config?.intakeNotice;
 let review=null,history=[],busy=false,submission=null,editSequence=0;
 const demoText='We design cooling plates. We want to compare designs across heat loads and flow rates. Our outputs are peak temperature and pressure drop. We have CFD results, but their uncertainty and test coverage need review.';
 const shell=document.createElement('section');shell.className='assist-shell';shell.id='assistant';
 shell.innerHTML=`<p class="eyebrow">Optional / AI-assisted drafting</p><h2>Describe the decision you want to improve.</h2><div class="assist-grid"><div><label for="ai-description">Your engineering problem</label><textarea id="ai-description" maxlength="3000" placeholder="What are you building? What needs to be predicted, compared or improved? What evidence do you have?"></textarea><p class="note">Use a high-level description. Keep files, credentials and confidential design details out of this form.</p><details><summary>What would be sent to the assistant?</summary><p id="ai-notice" class="note"></p><pre id="ai-payload"></pre></details><label for="ai-consent"><input id="ai-consent" type="checkbox">I want to send this description and the displayed draft fields to the AI service.</label><div class="actions"><button id="ai-run" class="button primary" type="button">Suggest a problem structure</button><button id="ai-demo" class="button secondary" type="button">Try a scripted example</button><a href="#composer" class="text-button">Build manually ↓</a></div><p id="ai-status" class="note assist-status" role="status"></p></div><div><div id="ai-review"><h3>You stay in control.</h3><p>Suggestions appear here before they change your brief. Review the reasoning, keep what fits, and leave unknowns unresolved.</p><p class="note">A proposed evidence plan describes what Carbon could investigate. It is not a measured performance result.</p></div></div></div>`;
 $('#examples').before(shell);
 const inbox=document.createElement('section');inbox.className='assist-shell';inbox.id='send-brief';
 inbox.innerHTML=`<p class="eyebrow">When your brief is ready</p><h2>Ask Carbon to scope the next step.</h2><p>Review what you share. Carbon can use the submitted brief to prepare a private analysis of evidence gaps, required work and a possible challenge.</p><details><summary>Review the exact submission</summary><pre id="intake-preview"></pre></details><label for="intake-email">Your work email</label><input id="intake-email" type="email" maxlength="254" autocomplete="email"><label for="intake-consent"><input id="intake-consent" type="checkbox">Send this brief to Carbon for private scoping analysis and a response.</label><p id="intake-notice" class="note"></p><button id="intake-send" class="button primary" type="button">Send brief to Carbon</button><p id="intake-status" role="status" class="note"></p>`;
 $('#assessment').after(inbox);
 $('#ai-notice').textContent=liveAI?integration.config.aiNotice:'This preview has no connected AI service. The scripted example stays local and makes no model call. On the website, this notice must name the provider and applicable retention before AI is enabled.';
 $('#intake-notice').textContent=liveIntake?integration.config.intakeNotice:'Private submission is not connected in this preview. You can continue editing and save your draft. No contact details or brief will be sent.';
 function payload(){const j=D.get();return {description:$('#ai-description').value,problem:Object.fromEntries(A.FIELDS.map(k=>[k,j.problem[k]]))};}
 function packet(){const j=D.get();return {schema:'carbon.client-intake/1',job:j,contact:{email:$('#intake-email').value.trim()},consent:{analysis:true,noticeVersion:integration?.config?.intakeNoticeVersion||'UNCONFIGURED'},assistantHistory:history};}
 function update(){
  $('#ai-payload').textContent=JSON.stringify(payload(),null,2);
  $('#intake-preview').textContent=JSON.stringify(packet(),null,2);
  $('#ai-run').disabled=!liveAI||busy||!$('#ai-consent').checked||!$('#ai-description').value.trim();
  $('#intake-send').disabled=!liveIntake||busy||!$('#intake-consent').checked||!$('#intake-email').validity.valid||!$('#intake-email').value.trim();
 }
 function display(){const out=review.output;
  $('#ai-review').innerHTML=`<p class="eyebrow">${review.mode==='demo'?'Scripted example / no AI call':'AI suggestions / review required'}</p><p>${esc(out.summary)}</p>${out.changes.map(c=>`<article class="suggestion"><label><input type="checkbox" data-suggestion="${esc(c.field)}">Use proposed ${esc(c.field)}</label><p class="note">${c.basis==='explicit'?'From your description':'Inferred: please check'} · ${esc(c.reason)}</p>${c.quote?`<p>“${esc(c.quote)}”</p>`:''}<details><summary>Compare current and proposed values</summary><strong>Current</strong><pre>${esc(JSON.stringify(D.get().problem[c.field],null,2))}</pre><strong>Proposed</strong><pre>${esc(JSON.stringify(JSON.parse(c.value_json),null,2))}</pre></details></article>`).join('')}<button id="ai-apply" type="button" class="button primary">Apply selected suggestions</button>${out.questions.length?`<h3>Next question</h3><p>${esc(out.questions[0])}</p><p class="note">Add your answer to the description, then request another review.</p>`:''}`;
  $('#ai-apply').onclick=()=>{try{
   if($('#ai-description').value!==review.description)throw Error('Your description changed. Request fresh suggestions.');
   if(!D.valid())throw Error('Resolve the invalid draft fields first.');
   const fields=Array.from(root.querySelectorAll('[data-suggestion]:checked')).map(x=>x.dataset.suggestion);
   const result=A.apply(review,D.get(),fields);history.push(result.provenance);D.applyReviewed(result.job);
   review=null;$('#ai-review').innerHTML='<h3>Reviewed suggestions added.</h3><p>Inspect your brief and evidence plan below. You can keep editing every field.</p>';$('#ai-status').textContent='Your accepted changes are working assumptions. Nothing was submitted.';update();
  }catch(e){$('#ai-status').textContent=e.message;}};
 }
 $('#ai-demo').onclick=()=>{
  if(busy)return;$('#ai-description').value=demoText;$('#ai-consent').checked=false;
  const j=D.get();const changes=[{field:'goal',value_json:JSON.stringify('ranking'),basis:'explicit',quote:'compare designs',reason:'Comparing designs calls for decision and ranking evidence.'},{field:'description',value_json:JSON.stringify(demoText),basis:'explicit',quote:demoText,reason:'Preserve the original problem description.'},{field:'decision',value_json:JSON.stringify('Choose a cooling plate using peak temperature and pressure drop across loads and flow rates.'),basis:'inferred',quote:'',reason:'Check that this reflects the engineering decision you intend to make.'}];
  review=A.pending({summary:'A design-comparison study is a possible starting point. The reference quality, operating envelope and success criteria remain open.',changes,questions:['Which design decisions would change if temperature or pressure-drop predictions were wrong?']},j,demoText,'demo');display();$('#ai-status').textContent='Scripted interaction only. The real AI adapter is included in the integration package; it is not connected here.';update();
 };
 $('#ai-run').onclick=async()=>{
  if(!liveAI||busy||!$('#ai-consent').checked||!D.valid())return;
  const j=D.get(),description=$('#ai-description').value,request=payload();busy=true;update();$('#ai-status').textContent='Preparing suggestions…';
  try{const output=await integration.assist(request);if(A.canonical(j)!==A.canonical(D.get())||description!==$('#ai-description').value)throw Error('The draft changed while the assistant was working. Request fresh suggestions.');review=A.pending(output,j,description,'ai');display();$('#ai-status').textContent='Review each proposed change. No changes have been applied.';}catch(e){$('#ai-status').textContent='Suggestions could not be prepared. Your draft is safe; continue manually or try again when ready.';}finally{busy=false;update();}
 };
 $('#intake-send').onclick=async()=>{
  if(!liveIntake||busy||!$('#intake-consent').checked||!$('#intake-email').validity.valid||!D.valid())return;
  const current=packet(),serialized=A.canonical(current);
  if(!submission||submission.payload!==serialized)submission={key:crypto.randomUUID(),payload:serialized};
  busy=true;update();$('#intake-status').textContent='Sending your reviewed brief…';
  try{const receipt=await integration.submit(current,{idempotencyKey:submission.key});
   if(typeof receipt?.receiptId!=='string'||receipt.state!=='RECEIVED')throw Error('Invalid receipt.');
   $('#intake-status').textContent='Received by Carbon. Reference: '+receipt.receiptId+'. Analysis is queued; this is not an acceptance or performance result.';
  }catch(e){$('#intake-status').textContent='Receipt not confirmed. Your draft is still here. Retry this same submission to check or complete it without creating a duplicate.';}finally{busy=false;update();}
 };
 root.addEventListener('input',()=>{editSequence++;update();});root.addEventListener('change',update);root.addEventListener('click',()=>queueMicrotask(update));
 update();
})();
