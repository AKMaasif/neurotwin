const { chromium } = require('playwright');
const B='http://localhost:8000/'; const res=[]; const ok=(n,c,x)=>res.push((c?'PASS ':'FAIL ')+n+(x?' — '+x:''));
const INIT=`(()=>{window.__gum=0;window.__tracks=[];const o=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=async(c)=>{window.__gum++; if(window.__deny){const e=new Error('denied');e.name='NotAllowedError';throw e;} const s=await o(c); s.getTracks().forEach(t=>window.__tracks.push(t)); return s;};})()`;
async function enter(b,{lang,deny,w=430}={}){
 const c=await b.newContext({viewport:{width:w,height:900},permissions:['microphone']}); const p=await c.newPage(); p.errs=[]; p.on('pageerror',e=>p.errs.push(e.message));
 await p.addInitScript(INIT); if(deny) await p.addInitScript('window.__deny=true');
 await p.goto(B); await p.waitForSelector('.lp-portal'); await p.locator('.lp-portal').nth(1).click(); await p.waitForSelector('.personal',{timeout:15000});
 if(lang==='ar'){ await p.click('.p-bar button:has-text("العربية")'); await p.waitForTimeout(400); }
 await p.waitForSelector('.cmp-launch'); return p; }
const allowAndStart=async(p)=>{ await p.click('.cmp-launch'); await p.waitForSelector('.cmp-panel');
 const a=p.locator('.cmp-card button.primary').first(); if(await p.locator('.cmp-card').count()&&await a.count()&&/Allow|السماح/.test(await a.textContent())) await a.click();
 await p.waitForSelector('.cmp-panel > button.primary'); await p.click('.cmp-panel > button.primary'); };
(async()=>{
 const b=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--autoplay-policy=no-user-gesture-required']});
 // A: no microphone before Start; stays open across screens; End releases
 let p=await enter(b); ok('no microphone request on page load or when the panel is only opened', await p.evaluate(()=>window.__gum)===0);
 await p.click('.cmp-launch'); await p.waitForSelector('.cmp-panel'); ok('still no microphone request after opening the panel', await p.evaluate(()=>window.__gum)===0);
 await p.evaluate(()=>{}); 
 const a=p.locator('.cmp-card button.primary').first(); if(await a.count()) await a.click();
 ok('still no microphone request after consenting (only Start asks)', await p.evaluate(()=>window.__gum)===0);
 await p.waitForSelector('.cmp-panel > button.primary'); await p.click('.cmp-panel > button.primary'); await p.waitForFunction(()=>/Listening|Speaking/.test(document.querySelector('.cmp-state').textContent));
 ok('exactly one microphone request after Start', await p.evaluate(()=>window.__gum)===1);
 ok('track is live while listening', await p.evaluate(()=>window.__tracks.some(t=>t.readyState==='live')));
 // navigate between screens with the session open
 await p.locator('.cmp-ico[aria-label="Close"], .cmp-ico:last-child').first().click().catch(()=>{});
 ok('minimising pauses listening by default (setting off)', /Paused|متوقف/.test(await (async()=>{await p.click('.cmp-launch');return p.textContent('.cmp-state');})()), await p.textContent('.cmp-state'));
 ok('track released after minimise', await p.evaluate(()=>window.__tracks.every(t=>t.readyState==='ended')));
 await p.click('button:has-text("Resume")'); await p.waitForFunction(()=>/Listening/.test(document.querySelector('.cmp-state').textContent));
 ok('resume re-opens the microphone explicitly', await p.evaluate(()=>window.__gum)===2);
 await p.locator('.pt-tabs button').nth(2).click(); await p.waitForTimeout(500);
 ok('panel persists across screens and keeps listening', /Listening/.test(await p.textContent('.cmp-state')));
 // typed request navigates
 await p.fill('#cmp-type','open my records'); await p.keyboard.press('Enter'); await p.waitForTimeout(1200);
 ok('typed request navigates to Records', /records/i.test(await p.evaluate(()=>document.querySelector('.p-main h1')?.textContent||'')) || await p.locator('.pt-tabs button[aria-current="page"]').nth(0).textContent().then(x=>/record/i.test(x)));
 // hidden tab pauses
 await p.evaluate(()=>{Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));});
 await p.waitForTimeout(300); ok('hiding the page pauses and releases the microphone', /Paused/.test(await p.textContent('.cmp-state')) && await p.evaluate(()=>window.__tracks.filter(t=>t.readyState==='live').length)===0);
 await p.evaluate(()=>{Object.defineProperty(document,'hidden',{value:false,configurable:true});});
 await p.click('button:has-text("Resume")'); await p.waitForFunction(()=>/Listening/.test(document.querySelector('.cmp-state').textContent));
 // offline
 await p.context().setOffline(true); await p.evaluate(()=>window.dispatchEvent(new Event('offline'))); await p.waitForTimeout(300);
 ok('offline state shown, microphone released', /No connection/.test(await p.textContent('.cmp-state')) && await p.evaluate(()=>window.__tracks.filter(t=>t.readyState==='live').length)===0);
 await p.context().setOffline(false); await p.evaluate(()=>window.dispatchEvent(new Event('online'))); await p.waitForFunction(()=>/Listening/.test(document.querySelector('.cmp-state').textContent),null,{timeout:5000}).catch(()=>{});
 ok('back online resumes listening', /Listening/.test(await p.textContent('.cmp-state')));
 // revoke consent
 await p.click('button:has-text("History and memory")'); await p.click('button:has-text("Withdraw voice permission")'); await p.waitForTimeout(800);
 ok('withdrawing voice permission ends the session and releases the microphone', /Not listening/.test(await p.textContent('.cmp-state')) && await p.evaluate(()=>window.__tracks.filter(t=>t.readyState==='live').length)===0);
 ok('consent card asks again', !!(await p.$('.cmp-card button.primary')));
 ok('no page errors (A)', p.errs.length===0, p.errs.join('|')); await p.context().close();
 // B: permission denied
 p=await enter(b,{deny:true}); await allowAndStart(p); await p.waitForTimeout(500);
 ok('denied permission shows a clear state and a way to type', /not allowed/i.test(await p.textContent('.cmp-state')) && !!(await p.$('#cmp-type')), await p.textContent('.cmp-panel .cmp-note'));
 ok('start button offered again after denial', !!(await p.$('.cmp-panel > button.primary')));
 await p.context().close();
 // C: Arabic / RTL
 p=await enter(b,{lang:'ar'}); await p.click('.cmp-launch'); await p.waitForSelector('.cmp-panel');
 ok('RTL document', await p.evaluate(()=>document.documentElement.dir==='rtl'||document.body.dir==='rtl'||getComputedStyle(document.querySelector('.personal')).direction==='rtl'));
 ok('Arabic labels', /المرافق الصوتي/.test(await p.textContent('.cmp-title')), await p.textContent('.cmp-state'));
 const box=await p.locator('.cmp-panel').boundingBox(); ok('panel fits the viewport (430px)', box.x>=0 && box.x+box.width<=430, JSON.stringify(box));
 await p.screenshot({path:'cv2_ar.png'});
 await p.context().close();
 // D: keyboard
 p=await enter(b); await p.focus('.cmp-launch'); await p.keyboard.press('Enter'); await p.waitForSelector('.cmp-panel');
 const names=[]; for(let i=0;i<8;i++){ await p.keyboard.press('Tab'); names.push(await p.evaluate(()=>document.activeElement?.getAttribute('aria-label')||document.activeElement?.textContent?.trim().slice(0,20))); }
 ok('keyboard reaches panel controls', names.filter(Boolean).length>=5, names.join(' | '));
 const small=await p.evaluate(()=>[...document.querySelectorAll('.cmp-panel button, .cmp-launch')].filter(b=>{const r=b.getBoundingClientRect();return r.width&&(r.height<44||r.width<44)}).length); ok('touch targets at least 44px', small===0, String(small));
 await p.context().close();
 console.log(res.join('\n')); await b.close();
})().catch(e=>{console.log(res.join('\n'));console.error('ERR',e.message);process.exit(1)});
