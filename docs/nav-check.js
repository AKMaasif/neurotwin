const { chromium } = require('playwright');
const B='http://localhost:8000/';
const res=[];const ok=(n,c)=>{res.push((c?'PASS ':'FAIL ')+n);};
async function mk(b,w=1440){const c=await b.newContext({viewport:{width:w,height:900}});const p=await c.newPage();p.errs=[];p.on('pageerror',e=>p.errs.push(e.message));await p.addInitScript(()=>{try{localStorage.setItem('neurotwin.lang','en')}catch(e){}});return p;}
const onDash=async(p,sel)=>!!(await p.$(sel));
const backs=async(p,n)=>{for(let i=0;i<n;i++){await p.goBack().catch(()=>{});await p.waitForTimeout(250);}};
(async()=>{const b=await chromium.launch();
// ---- clinician
let p=await mk(b);await p.goto(B+'?x=1');await p.waitForSelector('.lp-portal');await p.goto(B);await p.waitForSelector('.lp-portal');
await p.locator('.lp-portal').nth(0).click();await p.waitForSelector('.ws',{timeout:15000});await p.waitForTimeout(1500);
await backs(p,6);ok('clin: 6x Back stays in dashboard',await onDash(p,'.ws')&&!(await p.$('.lp-portal')));
// brain gate -> back
await p.locator('button:visible:has-text("Brain Analytics")').first().click();await p.waitForSelector('.entry-notice');
await p.goBack();await p.waitForTimeout(400);ok('clin: Back from Brain notice returns to workspace',await onDash(p,'.ws'));
// gate -> enter -> imaging -> in-app back
await p.locator('button:visible:has-text("Brain Analytics")').first().click();await p.waitForSelector('.entry-notice');
await p.click('.entry-actions button >> nth=0');await p.waitForSelector('.brain-workspace',{timeout:15000});
ok('clin: Brain Analytics open',true);
await p.goBack();await p.waitForTimeout(500);ok('clin: browser Back from Brain Analytics -> workspace',await onDash(p,'.ws')&&!(await p.$('.brain-workspace')));
await p.locator('button:visible:has-text("Brain Analytics")').first().click();await p.waitForSelector('.entry-notice');
await p.click('.entry-actions button >> nth=0');await p.waitForSelector('.brain-workspace',{timeout:15000});
await p.locator('button:has-text("Back to"), button:has-text("Back")').first().click();await p.waitForTimeout(600);
ok('clin: in-app Back from Brain Analytics -> workspace',await onDash(p,'.ws'));
await backs(p,3);ok('clin: more Backs after in-app back stay in dashboard',await onDash(p,'.ws'));
// report dialog
await p.locator('button:visible:has-text("Report")').first().click().catch(()=>{});await p.waitForTimeout(600);
if(await p.$('.report-scrim')){await p.goBack();await p.waitForTimeout(500);ok('clin: Back closes report dialog',!(await p.$('.report-scrim'))&&await onDash(p,'.ws'));}
// analysis dialog and close button
await p.locator('button:visible:has-text("Analyze activity history")').click();await p.waitForSelector('.report.aa');
await p.locator('.report.aa .bar .btn').click();await p.waitForTimeout(500);ok('clin: Close button closes analysis',!(await p.$('.report.aa')));
await p.goBack();await p.waitForTimeout(400);ok('clin: Back after Close stays in dashboard (no dead entry)',await onDash(p,'.ws')&&!(await p.$('.lp-portal')));
// analysis -> report transition
await p.locator('button:visible:has-text("Analyze activity history")').click();await p.waitForSelector('.report.aa');
await p.click('button:has-text("Run analysis")');await p.waitForSelector('.aa-panel');await p.waitForTimeout(5000);
await p.click('.aa-panel-head button[aria-expanded]');await p.click('button:has-text("Open the report")');await p.waitForTimeout(800);
ok('clin: analysis -> report opens report only',!!(await p.$('.report'))&&!(await p.$('.report.aa')));
await p.goBack();await p.waitForTimeout(500);ok('clin: Back from report -> dashboard',!(await p.$('.report-scrim'))&&await onDash(p,'.ws'));
// reload then back
await p.reload();await p.waitForSelector('.ws',{timeout:15000});await backs(p,4);ok('clin: reload then Back x4 stays',await onDash(p,'.ws')&&!(await p.$('.lp-portal')));
// sign out
await p.locator('button:visible:has-text("Sign out")').first().click();await p.waitForSelector('.lp-portal',{timeout:8000});
ok('clin: Sign out shows landing/sign-in',true);
await backs(p,4);ok('clin: Back after sign-out never shows dashboard',!(await p.$('.ws'))&&!(await p.$('.brain-workspace')));
await p.goForward().catch(()=>{});await p.waitForTimeout(400);await p.goForward().catch(()=>{});await p.waitForTimeout(400);
ok('clin: Forward after sign-out never shows dashboard',!(await p.$('.ws')));
const s=await p.request.get(B+'api/auth/session');ok('clin: session API is 401 after sign-out',s.status()===401);
ok('clin: no page errors',p.errs.length===0);if(p.errs.length)console.log(p.errs);
// ---- session expiry
p=await mk(b);await p.goto(B);await p.waitForSelector('.lp-portal');await p.locator('.lp-portal').nth(0).click();await p.waitForSelector('.ws',{timeout:15000});
await p.context().clearCookies();await p.evaluate(()=>fetch('/api/auth/session'));
await p.reload();await p.waitForSelector('.lp-portal',{timeout:8000});ok('expiry: lost session shows sign-in, not dashboard',!(await p.$('.ws')));
await backs(p,3);ok('expiry: Back does not reveal dashboard',!(await p.$('.ws')));
// ---- patient
p=await mk(b,420);await p.goto(B);await p.waitForSelector('.lp-portal');await p.locator('.lp-portal').nth(1).click();await p.waitForTimeout(3000);
const pBefore=await p.evaluate(()=>document.body.innerText.length);await backs(p,5);
ok('patient: 5x Back stays signed in',!(await p.$('.lp-portal'))&&(await p.evaluate(()=>document.body.innerText.length))>200);
const btn=p.locator('main button, .home button').filter({hasText:/check|today|reminder|record/i}).first();
if(await btn.count()){await btn.click();await p.waitForTimeout(600);const t1=await p.evaluate(()=>document.body.innerText);await p.goBack();await p.waitForTimeout(500);
 ok('patient: Back from a sub-page returns to home',(await p.evaluate(()=>document.body.innerText))!==t1&&!(await p.$('.lp-portal')));await backs(p,2);ok('patient: further Back stays',!(await p.$('.lp-portal')));}
await p.locator('button:visible:has-text("Sign out"), a:visible:has-text("Sign out")').first().click().catch(()=>console.log('no patient signout btn'));await p.waitForTimeout(1500);
ok('patient: after Sign out the sign-in/landing shows',!!(await p.$('.lp-portal')));await backs(p,3);const st=await p.request.get(B+'api/auth/session');ok('patient: Back after sign-out shows no signed-in app',st.status()===401&&!(await p.evaluate(()=>/Sign out/i.test(document.body.innerText))));
ok('patient: no page errors',p.errs.length===0);
// ---- family
p=await mk(b,420);await p.goto(B);await p.waitForSelector('.lp-portal');await p.locator('.lp-portal').nth(2).click();await p.waitForTimeout(3000);
await backs(p,5);ok('family: 5x Back stays signed in',!(await p.$('.lp-portal')));
const fb=p.locator('.fam-nav').nth(1);if(await fb.count()){await fb.click();await p.waitForTimeout(400);await p.goBack();await p.waitForTimeout(500);
 ok('family: Back from Write returns to People',(await p.locator('.fam-nav[aria-current="page"]').first().innerText().catch(()=>''))!==''&&!(await p.$('.lp-portal')));}
await p.locator('button:visible:has-text("Sign out"), a:visible:has-text("Sign out")').first().click().catch(()=>console.log('no family signout btn'));await p.waitForTimeout(1500);
ok('family: after Sign out the sign-in/landing shows',!!(await p.$('.lp-portal')));await backs(p,3);const sf=await p.request.get(B+'api/auth/session');ok('family: Back after sign-out shows no signed-in app',sf.status()===401&&!(await p.evaluate(()=>/Sign out/i.test(document.body.innerText))));
ok('family: no page errors',p.errs.length===0);
console.log(res.join('\n'));await b.close();})();
