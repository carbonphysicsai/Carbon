'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'..'),ARTIFACT=path.join(ROOT,'Carbon_Opportunity_Workbench.html');
const F=require('../src/engine.js'),A=JSON.parse(fs.readFileSync(path.join(ROOT,'data/atlas.json'))),ids=A.opportunities.map(x=>x.id),sha=A.source.sha256;
const checks=[];function check(name,condition){assert.ok(condition,name);checks.push(name);}
const clone=v=>JSON.parse(JSON.stringify(v));
function legacyDraft(){const n=F.newDraft(ids[0],sha),keys=['schema_version','opportunity_id','source_sha256','planning_state','fit_checks','inputs','brief','reference_roles','reference_architecture','next_test','study_refs','review_note','evidence_status','qualification_status','submission_status','reuse_permission'],d={};for(const k of keys)d[k]=clone(n[k]);d.schema_version=F.LEGACY_DRAFT_VERSION;d.inputs.cohort='3';d.inputs.ref_lo='40';d.inputs.ref_hi='40';d.inputs.hardware='Historical synthetic profile';d.brief.notes='Migrated substantive owner note';d.fit_checks.exam={state:'SUPPORTED_FOR_STAGE',evidence_note:'Historical support note — not current protection evidence'};d.reference_roles=['routine_exam','independent_witness'];d.reference_architecture.independent_witness.evidence_note='Keep the witness role distinct';d.next_test='Preserved v0.1 next test';return d;}
async function downloaded(page,button,tmp,name){const promise=page.waitForEvent('download');await page.locator(button).click();const download=await promise,target=path.join(tmp,name);await download.saveAs(target);return fs.readFileSync(target);}

(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'carbon-workbench-browser-'));
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],outbound=[],dialogs=[];page.setDefaultTimeout(10000);
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))outbound.push(r.url());});page.on('dialog',async d=>{dialogs.push(d.message());await d.accept();});
 await page.goto('file://'+ARTIFACT);await page.locator('[data-tab="atlas"]').click();await page.waitForSelector('.op-item');
 check('actual standalone artifact opens with all 64 opportunities',await page.locator('.op-item').count()===64);
 check('initial client profile is empty',!await page.locator('body').textContent().then(t=>t.includes('private@example')));
 await page.screenshot({path:path.join(ROOT,'tests/preview_atlas.png'),fullPage:true});
 await page.locator('.op-item').nth(0).click();await page.locator('#open-profile').click();
 check('Challenge Profile integrates CPES result',await page.locator('#analysis-summary').innerText().then(t=>t.includes('Variant A · DEVELOPMENT')&&t.includes('UNASSESSED')));
 check('P1-P8 controls are inside Exam review',await page.locator('[data-control-state]').count()===8);
 check('all five blockers are present',await page.locator('[data-blocker-app]').evaluateAll((els)=>els.map(x=>x.dataset.blockerApp).join(','))==='AT-09,AT-16,AT-19,AT-22,AT-30');
 await page.locator('#demo').selectOption('burst');await page.locator('#apply-demo').click();
 check('favorable synthetic B arithmetic shows 120 A, 44 B and 76 saving',await page.locator('#economics-result').innerText().then(t=>t.includes('120')&&t.includes('44')&&t.includes('76')&&t.includes('saves work')));
 check('economic slider cannot change immutable baseline',await page.locator('#analysis-summary').innerText().then(t=>t.includes('Variant A · DEVELOPMENT')));
 check('runtime sharing remains unreachable',await page.locator('button').evaluateAll(bs=>!bs.some(b=>/activate sharing/i.test(b.textContent)&&!b.disabled)));
 await page.locator('[data-path="reference_economics.group_overhead"]').fill('');
 check('removing H clears stale savings',await page.locator('#economics-result').innerText().then(t=>t.includes('UNKNOWN')&&!t.includes('group saving')));
 await page.locator('[data-path="reference_economics.group_overhead"]').fill('4');await page.locator('[data-path="reference_economics.unit"]').selectOption('');
 check('removing matched units makes result unknown',await page.locator('#economics-result').innerText().then(t=>t.includes('matched unit')&&!t.includes('group saving')));
 await page.locator('#demo').selectOption('slow');await page.locator('#apply-demo').click();
 check('slow-member example shows lower work and fewer summaries caveat',await page.locator('#dynamic-result').innerText().then(t=>t.includes('not equivalent productive throughput')&&t.includes('Complete comparisons')));
 await page.screenshot({path:path.join(ROOT,'tests/preview_profile.png'),fullPage:true});

 await page.locator('[data-tab="library"]').click();
 check('study layers are plain-language and not a pass percentage',await page.locator('#library-view').innerText().then(t=>t.includes('17 model rejections; 8 research-prototype rejections; 5 unresolved claims')&&!t.includes('83%')));
 check('all 30 attack rows are expandable evidence',await page.locator('.attack-list article').count()===30);
 for(const id of F.BLOCKER_IDS)check('source-layer evidence retains '+id,await page.locator('#library-view').textContent().then(t=>t.includes(id)));
 check('adaptive negative control keeps exact 32/33/46.875 values',await page.locator('#library-view').innerText().then(t=>t.includes('32 binary labels')&&t.includes('33 exact-score queries')&&t.includes('46.875%')));
 const claimMaterial={schema_version:'carbon.workbench.cpes-study-import.v1',study_id:'USER-SELF-AUTHORED-STUDY',evidence_version:'v1',recommendation:'RECOMMEND_B',source_reference:'local text only',delivery_status:'self-authored',qualified_carbon_evidence:null},claim={...claimMaterial,content_sha256:crypto.createHash('sha256').update(JSON.stringify(claimMaterial)).digest('hex')},claimPath=path.join(tmp,'claim.json');fs.writeFileSync(claimPath,JSON.stringify(claim));
 await page.locator('#evidence-file').setInputFiles(claimPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('unreviewed'));
 check('self-authored hash-matching claim cannot change A baseline',await page.locator('#library-view').innerText().then(t=>t.includes('RETAIN A')));
 check('later user version coexists visibly without becoming qualified',await page.locator('[data-imported-study]').count()===1&&await page.locator('#library-view').innerText().then(t=>t.includes('Qualified Carbon evidence: none')));
 await page.locator('[data-imported-study]').click();check('user version can be deliberately associated without selection',await page.locator('#toast').innerText().then(t=>t.includes('calculations and baseline are unchanged')));
 await page.locator('#evidence-file').setInputFiles(claimPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('deduplicated'));
 check('exact duplicate evidence claim deduplicates',await page.locator('#toast').innerText().then(t=>t.includes('deduplicated')));
 fs.writeFileSync(claimPath,JSON.stringify({...claim,authority:'APPROVED'}));await page.locator('#evidence-file').setInputFiles(claimPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('rejected'));
 check('forged evidence authority field rejects',await page.locator('#toast').innerText().then(t=>t.includes('rejected')));

 const legacy={schema_version:F.LEGACY_WORKSPACE_VERSION,source_sha256:sha,drafts:[legacyDraft()],shortlist:[ids[0]]},legacyPath=path.join(tmp,'realistic-v0.1-workspace.json');fs.writeFileSync(legacyPath,JSON.stringify(legacy));
 await page.locator('#workspace-file').setInputFiles(legacyPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Migrated v0.1'));
 await page.locator('[data-tab="brief"]').click();
 check('v0.1 client note migrates without loss',await page.locator('[data-brief="notes"]').inputValue()==='Migrated substantive owner note');
 await page.locator('[data-brief="notes"]').fill('Migrated substantive owner note — edited after migration');await page.locator('#refresh-previews').click();
 const exported=await downloaded(page,'#export-workspace',tmp,'workspace-v0.2.json'),saved=JSON.parse(exported);
 check('workspace export preserves migration receipt and no authority promotion',saved.migration_receipts.length===1&&saved.drafts[0].qualification_status==='NOT_QUALIFIED_BY_THIS_TOOL'&&saved.drafts[0].legacy_sharing_scenario.status==='LEGACY_HYPOTHETICAL_SHARING_SCENARIO');
 await page.reload();await page.locator('#workspace-file').setInputFiles(path.join(tmp,'workspace-v0.2.json'));await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Imported v0.2'));
 await page.locator('[data-tab="brief"]').click();
 check('v0.2 reload preserves edited note',await page.locator('[data-brief="notes"]').inputValue()==='Migrated substantive owner note — edited after migration');
 const clientJson=JSON.parse(await downloaded(page,'#client-json',tmp,'client.json')),clientMd=(await downloaded(page,'#client-md',tmp,'client.md')).toString(),engJson=JSON.parse(await downloaded(page,'#engineering-json',tmp,'engineering.json')),engMd=(await downloaded(page,'#engineering-md',tmp,'engineering.md')).toString();
 check('client download bytes carry baseline and caveats',/Variant A/.test(clientJson.current_recommendation)&&clientJson.study_reference.qualified_carbon_evidence===null&&/planning summary only/.test(clientMd));
 check('Engineering bytes carry exact blockers and no activation authority',engJson.study_blockers.map(x=>x.attack_id).join(',')===F.BLOCKER_IDS.join(',')&&engJson.all_attack_refs.length===30&&/cannot implement or activate/.test(engMd));
 check('client export excludes private contact field',!Object.hasOwn(clientJson.client_context,'contact'));
 check('send/activation action is visibly disabled',await page.getByRole('button',{name:/Send \/ activate/}).isDisabled());

 const before=await page.locator('[data-brief="notes"]').inputValue(),badPath=path.join(tmp,'bad.json');fs.writeFileSync(badPath,'{"schema_version":"carbon_workbench_workspace_v0.2","schema_version":"forged"}');await page.locator('#workspace-file').setInputFiles(badPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Import rejected'));
 check('duplicate-member import rejects without altering session',await page.locator('[data-brief="notes"]').inputValue()===before);
 const malicious=legacyDraft();malicious.brief.notes='</script><img src=x onerror="window.cpesPwned=true"> inert';fs.writeFileSync(badPath,JSON.stringify({schema_version:F.LEGACY_WORKSPACE_VERSION,source_sha256:sha,drafts:[malicious],shortlist:[]}));await page.locator('#workspace-file').setInputFiles(badPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Migrated v0.1'));await page.locator('[data-tab="brief"]').click();
 check('malicious imported string renders inert',await page.locator('#brief-view img').count()===0&&await page.evaluate(()=>window.cpesPwned)===undefined&&await page.locator('[data-brief="notes"]').inputValue()===malicious.brief.notes);

 await page.locator('[data-tab="profile"]').click();await page.keyboard.press('Tab');check('keyboard navigation produces visible focus',await page.evaluate(()=>document.activeElement&&document.activeElement!==document.body));
 check('status outputs use live regions',await page.locator('[aria-live="polite"]').count()>=4);
 check('all interactive review inputs have label associations or label ancestry',await page.locator('#case-protection input,#case-protection select,#case-protection textarea').evaluateAll(els=>els.every(e=>e.labels&&e.labels.length)));
 await page.setViewportSize({width:390,height:844});check('narrow profile avoids document overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(ROOT,'tests/preview_mobile.png'),fullPage:true});
 await page.route(/^https?:/,route=>route.abort());await page.locator('[data-tab="atlas"]').click();await page.locator('[data-tab="profile"]').click();check('core flow works with outbound network blocked',await page.locator('#analysis-summary').innerText().then(t=>t.includes('Variant A')));
 check('no outbound requests occurred after artifact load',outbound.length===0);check('no browser script exceptions',errors.length===0);
 const result={artifact:'Carbon_Opportunity_Workbench.html',navigation:'file:// standalone artifact',engine:'Google Chrome (Chromium)',viewport_checks:['1440x1050','390x844'],passed:checks.length,failed:0,checks,page_errors:errors,outbound_requests:outbound,dialogs,other_engine:'NOT_AVAILABLE_IN_LOCAL_AUTOMATION; Safari not claimed'};
 fs.writeFileSync(path.join(ROOT,'tests/browser_results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({passed:checks.length,failed:0},null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
