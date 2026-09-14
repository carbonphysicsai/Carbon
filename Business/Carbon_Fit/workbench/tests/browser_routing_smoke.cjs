'use strict';
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),ARTIFACT=path.join(ROOT,'Carbon_Opportunity_Workbench.html');
const checks=[];function check(name,condition){if(!condition)throw Error('FAILED: '+name);checks.push(name);}

(async()=>{
 const errors=[],outbound=[];
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(12000);
 page.on('pageerror',error=>errors.push(String(error)));page.on('request',request=>{if(/^https?:/.test(request.url()))outbound.push(request.url());});page.on('dialog',dialog=>dialog.accept());
 await page.goto('file://'+ARTIFACT);await page.waitForSelector('#owner-console-view');
 check('Owner Console starts with deterministic zero attention counts',await page.locator('#owner-console-view').innerText().then(x=>x.includes('No client job yet')&&x.includes('NEEDS DECISION')));

 await page.locator('[data-tab="jobs"]').click();await page.locator('#new-job').click();
 await page.locator('#journey-existing').click();
 check('Journey A selects USE_EXISTING_CAPABILITY',await page.locator('#route-choice').inputValue()==='USE_EXISTING_CAPABILITY');
 check('Journey A avoids unnecessary Challenge authoring',await page.locator('#authoring-preview').innerText().then(x=>x.includes('NOT_PREPARED')));
 check('Journey A exposes one intended-use action without fit percent',await page.locator('#jobs-view').innerText().then(x=>x.includes('REVIEW_INTENDED_USE_APPLICABILITY')&&!x.includes('percent complete')));

 await page.locator('#journey-adapt').click();
 check('Journey B selects the exact supported Burgers adaptation',await page.locator('#route-choice').inputValue()==='ADAPT_SUPPORTED_CHALLENGE'&&await page.locator('#route-source').inputValue().then(x=>x.includes('periodic_viscous_burgers_1d_v1')));
 await page.locator('#c05-evidence-file').setInputFiles(path.join(ROOT,'data/c05_public_development_evidence_v1.json'));
 await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('scientific decision remains unresolved'));
 check('native C-05 result is visibly native and unresolved',await page.locator('#jobs-view').innerText().then(x=>x.includes('NATIVE_IMPORTED_RESULT')&&x.includes('not supplied / unresolved')&&x.includes('Not qualified')));

 await page.locator('#revise-design').click();
 check('new revision resets route but explicitly carries prior evidence',await page.locator('#route-choice').inputValue()==='UNASSESSED'&&await page.locator('#jobs-view').innerText().then(x=>x.includes('CARRIED_FORWARD_UNCHANGED_SCOPE')));
 await page.locator('[data-scope="outputs"]').fill('Changed output semantics requiring new measurement review');
 await page.locator('[data-tab="owner-console"]').click();await page.locator('[data-tab="jobs"]').click();
 check('output change selectively marks retained evidence for review',await page.locator('#jobs-view').innerText().then(x=>x.includes('REVIEW_REQUIRED')&&x.includes('OUTPUT_CONTRACT')));
 check('source result remains historical in sealed parent revision',await page.locator('#design-select option').count()===2);

 await page.locator('#link-owner-request').click();
 await page.locator('[data-tab="owner-console"]').click();
 check('#42 EXPORTED_OWNER_REQUEST is waiting not approved',await page.locator('#owner-console-view').innerText().then(x=>x.includes('WAITING_ON_DEPENDENCY')&&x.includes('EXTERNAL_LINKED_RECORD')&&!x.includes('APPROVED')));
 check('Owner Console separates workflow evidence and customer outcome',await page.locator('#owner-console-view').innerText().then(x=>x.includes('WAITING_ON_DEPENDENCY')&&x.includes('UNDER_REVIEW')&&x.includes('OPEN')));

 await page.locator('[data-tab="jobs"]').click();await page.locator('#new-job').click();await page.locator('#journey-develop').click();
 check('Journey C freezes one bounded unsupported-physics feasibility question',await page.locator('#route-choice').inputValue()==='DEVELOP_NEW_CAPABILITY'&&await page.locator('#route-question').inputValue().then(x=>x.length>20)&&await page.locator('#route-stop').inputValue().then(x=>x.length>10));
 await page.locator('#prepare-handoff').click();
 const downloadPromise=page.waitForEvent('download');await page.locator('[data-export-handoff]').click();await downloadPromise;
 await page.locator('[data-tab="owner-console"]').click();
 check('exported feasibility handoff produces one WAITING state',await page.locator('#owner-console-view').innerText().then(x=>x.includes('WAITING_ON_DEPENDENCY')&&x.includes('WAIT_FOR_RESTART_EVENT')));
 check('unsupported physics does not force Burgers authoring',await page.locator('[data-tab="jobs"]').click().then(()=>page.locator('#authoring-preview').innerText()).then(x=>x.includes('NOT_PREPARED')));

 await page.locator('[data-tab="owner-console"]').click();
 await page.waitForFunction(()=>!document.querySelector('#toast').textContent);
 await page.screenshot({path:path.join(ROOT,'tests/preview_owner_console.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('[data-tab="owner-console"]').click();
 check('Owner Console is usable at narrow width',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:path.join(ROOT,'tests/preview_owner_console_mobile.png'),fullPage:true});
 check('browser emitted no script exception',errors.length===0);
 check('offline journeys emitted zero external requests',outbound.length===0);
 const result={artifact:'Carbon_Opportunity_Workbench.html',scope:'GOAL-WORKBENCH-05 route, console, applicability journeys',engine:'Google Chrome (Chromium)',passed:checks.length,failed:0,checks,page_errors:errors,outbound_requests:outbound,other_engine:'NOT_AVAILABLE_IN_LOCAL_AUTOMATION; Safari/WebKit not claimed'};
 fs.writeFileSync(path.join(ROOT,'tests/browser_routing_results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({passed:checks.length,failed:0},null,2));await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
