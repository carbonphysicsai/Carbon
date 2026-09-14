'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),REPO=path.resolve(ROOT,'../../..'),ARTIFACT=path.join(ROOT,'Carbon_Opportunity_Workbench.html'),PYTHON='/private/tmp/carbon-c04-science-env/bin/python';
const F=require('../src/engine.js'),A=JSON.parse(fs.readFileSync(path.join(ROOT,'data/atlas.json'))),checks=[];
function check(name,value){assert.ok(value,name);checks.push(name);}
async function downloaded(page,selector,directory,name){const pending=page.waitForEvent('download');await page.locator(selector).click();const item=await pending,target=path.join(directory,name);await item.saveAs(target);return target;}
function response(request){return {schema_version:'carbon.goal-workbench.response.v1',response_id:'response-1',request_id:request.request_id,base_revision:request.base_revision,job_id:request.job_id,design_id:request.design_id,design_revision:request.design_revision,kind:'ACKNOWLEDGMENT',route:'MANUAL',source_owner:'S1',status:'RECEIVED',output_reference:'manual public-safe note',input_digest:'sha256:'+crypto.createHash('sha256').update(JSON.stringify(request)).digest('hex'),authority_class:'UNVERIFIED_ASSERTION',verification_reference:'',limitations:'Manual route does not verify owner authority.',note:'</script><img src=x onerror="window.goalPwned=true"> remains inert data',content_sha256:'a'.repeat(64)};}

(async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'carbon-goal-browser-')),errors=[],outbound=[];
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}),page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(12000);
 page.on('pageerror',error=>errors.push(String(error)));page.on('request',request=>{if(/^https?:/.test(request.url()))outbound.push(request.url());});page.on('dialog',dialog=>dialog.accept());
 await page.goto('file://'+ARTIFACT);await page.waitForSelector('#new-job');
 check('direct client intake is the initial route without Atlas',await page.locator('#jobs-view').isVisible()&&!await page.locator('#atlas-view').isVisible());
 check('initial client profile is empty',await page.locator('#jobs-view').innerText().then(text=>text.includes('No client job yet')));
 await page.locator('#new-job').click();
 await page.locator('[data-job="title"]').fill('Public Burgers decision');await page.locator('[data-job="lead"]').fill('S1');
 await page.locator('[data-assignment="client_words"]').fill('Need a trustworthy full-field DEVELOPMENT comparison. </script><img src=x onerror="window.goalPwned=true">');
 await page.locator('[data-assignment="intended_decision"]').fill('Decide whether the fixed public template preserves the bounded Dynamics intent.');
 await page.locator('[data-assignment="credible_baseline"]').fill('Existing source-owned DEVELOPMENT Burgers baseline.');
 await page.locator('#new-alternative').click();
 check('one job supports multiple design alternatives',await page.locator('#design-select option').count()===2);
 await page.locator('#design-select').selectOption('job-001-design-1');await page.locator('#burgers-demo').click();
 check('supported Burgers demonstration binds requirement score case reference and CPES',await page.locator('#goal-summary').innerText().then(text=>text.includes('EXACT_SUPPORTED')&&text.includes('Variant A · DEVELOPMENT')));
 check('P1-P8 and five blockers are bound inside the same design',await page.locator('[data-control]').count()===8&&await page.locator('[data-blocker]').count()===5);
 check('source case plan distinguishes target sample and weight',await page.locator('#jobs-view').innerText().then(text=>text.includes('population mass distinct from sampling frequency')));
 await page.getByText('Prospective behavior checks',{exact:true}).click();
 const diagnosticPath=await downloaded(page,'#download-diagnostic',tmp,'diagnostic-request.json'),diagnostic=JSON.parse(fs.readFileSync(diagnosticPath));
 check('numerical diagnostic remains NOT_EXECUTED with a bound source-owner request',diagnostic.status==='NOT_EXECUTED'&&diagnostic.frozen_expectations.length===8&&diagnostic.authority==='REQUEST_ONLY_NO_SCORER_EXECUTION_OR_QUALIFICATION');

 await page.locator('#prepare-authoring').click();
 const requestPath=await downloaded(page,'#download-authoring',tmp,'authoring-request.json'),request=JSON.parse(fs.readFileSync(requestPath));
 check('authoring export is exact DEVELOPMENT request only',request.route==='LOCAL_FIXED_CLI'&&request.authority==='DEVELOPMENT_REQUEST_ONLY'&&request.compatibility.status==='EXACT_SUPPORTED');
 const authoringDirectory=path.join(tmp,'authoring-result'),bridge=spawnSync(PYTHON,[path.join(ROOT,'tools/authoring_bridge.py'),requestPath,authoringDirectory],{cwd:REPO,env:{...process.env,PYTHONPATH:REPO},encoding:'utf8'});
 check('installed source-owned CLI bridge completed',bridge.status===0&&fs.existsSync(path.join(authoringDirectory,'workbench-authoring-result.json')));
 await page.locator('#authoring-result-file').setInputFiles(path.join(authoringDirectory,'workbench-authoring-result.json'));await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('semantic status recomputed'));
 check('native result returns to exact design with intent preserved and no qualification',await page.locator('#goal-summary').innerText().then(text=>text.includes('INTENT_PRESERVED'))&&JSON.parse(fs.readFileSync(path.join(authoringDirectory,'workbench-authoring-result.json'))).proposal.capabilities.scientifically_qualified===false);

 await page.locator('[data-econ="compatible_demand_status"]').selectOption('user_assumed');await page.locator('[data-econ="field_dependent"]').selectOption('NO');
 check('conditional B scenario is favorable while baseline stays A',await page.locator('#goal-economics-result').innerText().then(text=>text.includes('FAVORABLE')&&text.includes('A=120')&&text.includes('B=44')&&text.includes('saving=76'))&&await page.locator('#goal-summary').innerText().then(text=>text.includes('Variant A · DEVELOPMENT')));
 await page.locator('[data-score="soft_estimand"]').fill('Changed evidence depth requiring renewed review');await page.locator('[data-score="soft_estimand"]').dispatchEvent('change');
 check('score change preserves but invalidates old CPES economics',await page.locator('#goal-economics-result').innerText().then(text=>text.includes('UNKNOWN')&&text.includes('earlier design meaning')&&text.includes('CPES economics')));

 await page.locator('#prepare-handoff').click();
 const handoffPath=await downloaded(page,'[data-export-handoff]',tmp,'handoff.json'),handoff=JSON.parse(fs.readFileSync(handoffPath));
 check('download proves export only and retains one lead stop condition and rights',handoff.status==='EXPORTED'&&handoff.lead==='S1'&&handoff.stop_condition.length>0&&handoff.authority==='REQUEST_ONLY_NO_EXECUTION_OR_APPROVAL');
 const responsePath=path.join(tmp,'response.json');fs.writeFileSync(responsePath,JSON.stringify(response(handoff)));
 await page.locator('#handoff-response-file').setInputFiles(responsePath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('scoped assertion'));
 check('returned acknowledgement updates same request without authority promotion',await page.locator('#jobs-view').innerText().then(text=>text.includes('MANUAL / ACKNOWLEDGED')));
 check('injection-bearing response remains inert',await page.evaluate(()=>window.goalPwned)===undefined&&await page.locator('#jobs-view img').count()===0);

 const clientPath=await downloaded(page,'#export-client',tmp,'client.json'),engineeringPath=await downloaded(page,'#export-engineering',tmp,'engineering.json'),launchPath=await downloaded(page,'#export-launch',tmp,'launch.json');
 const client=JSON.parse(fs.readFileSync(clientPath)),engineering=JSON.parse(fs.readFileSync(engineeringPath)),launch=JSON.parse(fs.readFileSync(launchPath));
 check('client projection excludes private native and rights fields',!Object.hasOwn(client,'native_task_id')&&!Object.hasOwn(client,'rights_summary')&&client.current_recommendation.includes('Variant A'));
 check('Engineering projection keeps exact design response blockers and stale economics',engineering.design.responses.length===1&&engineering.conditional_economics.status==='STALE_FOR_REVIEW'&&engineering.launch_candidate.remaining_decisions.some(x=>x.includes('AT-09')));
 check('launch artifact is candidate only with unavailable native launch interface',launch.status==='MANUAL_OWNER_HANDOFF_REQUIRED'&&launch.native_launch_interface==='UNAVAILABLE'&&launch.authority==='CANDIDATE_ONLY_NOT_AUTHORIZED_OR_LAUNCHED');
 check('no send or launch control is reachable',await page.getByRole('button',{name:/Send \/ launch unavailable/}).isDisabled());

 const workspacePath=await downloaded(page,'#export-goal',tmp,'goal-workspace.json'),saved=JSON.parse(fs.readFileSync(workspacePath));
 check('v0.3 export preserves alternatives CPES responses and immutable authority',saved.jobs[0].designs.length===2&&saved.jobs[0].designs[0].responses.length===1&&saved.authority.launch==='NOT_LAUNCHED');
 const component={schema_version:F.WORKSPACE_VERSION,application_version:F.APP_VERSION,source_sha256:A.source.sha256,evidence_catalog:[],drafts:[],shortlist:[],migration_receipts:[]},componentPath=path.join(tmp,'v0.2.json');fs.writeFileSync(componentPath,JSON.stringify(component));
 await page.locator('#goal-workspace-file').setInputFiles(componentPath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('migration receipt'));
 check('v0.2 component migrates into empty direct-job layer',await page.locator('#jobs-view').innerText().then(text=>text.includes('No client job yet')));
 await page.locator('#goal-workspace-file').setInputFiles(workspacePath);await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Imported v0.3'));
 check('reimport resumes without retyping scope responses or malicious text',await page.locator('[data-assignment="client_words"]').inputValue().then(text=>text.includes('trustworthy full-field'))&&await page.locator('#jobs-view img').count()===0&&await page.evaluate(()=>window.goalPwned)===undefined);

 await page.setViewportSize({width:390,height:844});check('narrow job view avoids document overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.keyboard.press('Tab');check('keyboard navigation moves focus',await page.evaluate(()=>document.activeElement&&document.activeElement!==document.body));
 check('interactive job fields retain labels',await page.locator('#jobs-view input,#jobs-view select,#jobs-view textarea').evaluateAll(elements=>elements.every(element=>element.labels&&element.labels.length)));
 await page.route(/^https?:/,route=>route.abort());await page.locator('[data-tab="atlas"]').click();await page.locator('[data-tab="jobs"]').click();
 check('offline navigation remains usable and no outbound request occurred',outbound.length===0&&await page.locator('#jobs-view').isVisible());
 check('browser emitted no script exception',errors.length===0);
 const result={artifact:'Carbon_Opportunity_Workbench.html',navigation:'file:// standalone artifact',engine:'Google Chrome (Chromium)',passed:checks.length,failed:0,checks,page_errors:errors,outbound_requests:outbound,other_engine:'NOT_AVAILABLE_IN_LOCAL_AUTOMATION; Safari/WebKit not claimed'};
 fs.writeFileSync(path.join(ROOT,'tests/browser_goal_results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({passed:checks.length,failed:0},null,2));await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
