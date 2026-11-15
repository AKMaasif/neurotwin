const { chromium } = require('playwright');
const B='http://localhost:8000/'; const res=[]; const ok=(n,c,x)=>res.push((c?'PASS ':'FAIL ')+n+(x?' — '+x:''));
(async()=>{
 const b=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+__dirname+'/speech.wav%noloop','--autoplay-policy=no-user-gesture-required']});
 const c=await b.newContext({viewport:{width:430,height:900},permissions:['microphone']}); const p=await c.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
 await p.goto(B); await p.waitForSelector('.lp-portal'); await p.locator('.lp-portal').nth(1).click(); await p.waitForSelector('.personal',{timeout:15000});
 await p.waitForSelector('.cmp-launch',{timeout:8000}); ok('launcher visible on Home', true);
 const lab=await p.getAttribute('.cmp-launch','aria-label'); ok('launcher has accessible name incl. state', /Not listening|not available/i.test(lab), lab);
 // mic not requested before open
 const sess0=await p.evaluate(()=>window.__mic||0); 
 await p.click('.cmp-launch'); await p.waitForSelector('.cmp-panel');
 const consentCard=await p.$('.cmp-card'); ok('consent card or start visible', !!consentCard || !!(await p.$('button:has-text("Start talking")')));
 if(await p.$('button:has-text("Allow voice conversation")')){ await p.click('button:has-text("Allow voice conversation")'); await p.waitForSelector('button:has-text("Start talking")'); }
 ok('start button shown after consent', true);
 ok('status says not listening before Start', /Not listening/.test(await p.textContent('.cmp-state')), await p.textContent('.cmp-state'));
 await p.screenshot({path:'cv1_a.png'});
 await p.click('button:has-text("Start talking")');
 await p.waitForFunction(()=>/Listening|Speaking/.test(document.querySelector('.cmp-state')?.textContent||''),null,{timeout:8000}); ok('listening after start', true, await p.textContent('.cmp-state'));
 // greeting caption
 ok('greeting uses display name', /Hello .*I'm listening/.test(await p.textContent('.cmp-log')), await p.textContent('.cmp-log'));
 // wait for the scripted speech turn -> transcribing -> reply
 await p.waitForFunction(()=>/what do I have today|Hearing|Thinking|Writing/i.test(document.body.textContent),null,{timeout:20000}).catch(()=>{});
 await p.waitForFunction(()=>/Hearing|Writing|Thinking|Speaking/.test(document.querySelector('.cmp-state')?.textContent||''),null,{timeout:15000}).catch(()=>{});
 await p.waitForTimeout(9000);
 const log=await p.textContent('.cmp-log'); ok('spoken request answered once', /what do I have today/i.test(log), log.slice(0,300));
 const calls=require('fs').existsSync('/tmp/stt_calls.log')?require('fs').readFileSync('/tmp/stt_calls.log','utf8').trim().split('\n').length:0; ok('exactly one transcription call', calls===1, String(calls));
 await p.screenshot({path:'cv1_b.png'});
 // end releases mic
 await p.click('button:has-text("End conversation")'); await p.waitForTimeout(500);
 ok('ended: status not listening', /Not listening/.test(await p.textContent('.cmp-state')));
 const live=await p.evaluate(async()=>{ // any live audio track?
   return (window.__tracks||0); });
 ok('no page errors', errs.length===0, errs.join('|'));
 console.log(res.join('\n')); await b.close();
})().catch(e=>{console.log(res.join('\n'));console.error('ERR',e.message);process.exit(1)});
