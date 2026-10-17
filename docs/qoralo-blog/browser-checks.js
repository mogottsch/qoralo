async (page) => {
  const failures=[];
  const check=(ok,text)=>{if(!ok)failures.push(text);};
  const base=page.url();
  const origin=base.match(/^https?:\/\/[^/]+/)[0];
  const external=[],errors=[];
  page.on('request',r=>{const u=r.url();if(!u.startsWith(origin)&&!u.startsWith('data:')&&!u.startsWith('blob:')&&!u.startsWith('file:'))external.push(u);});
  page.on('pageerror',e=>errors.push(e.message));
  await page.reload();
  check(await page.locator('figure').count()===3,'Three figures: processor route, one generation step, stop-score replay');
  check(await page.locator('#step-figure .loop-box').count()===5,'One-step diagram has five boxes');
  check(await page.locator('#chapter-figure,#lifetime-figure,#state-figure,.segment').count()===0,'Removed chapter, lifetime stepper and logit-only diagrams');
  check(await page.locator('audio[autoplay]').count()===0,'No autoplay audio');

  // Chart data: embedded arrays must equal the retained evidence, and drawn polylines must carry every point.
  const embedded=await page.evaluate(()=>JSON.parse(document.querySelector('#trajectories').textContent));
  const evidence=await (await page.request.get(base.split('#')[0].replace(/index\.html$/,'')+'evidence/bos-zero-replay.json')).json();
  const e=evidence.logits;
  const same=(a,b)=>a.length===b.length&&a.every((v,i)=>Math.abs(v-b[i])<6e-4);
  check(same(embedded.android,e.android_original_retained)&&same(embedded.zero,e.all_zero_bos_replay)&&same(embedded.nan,e.correct_nan_bos_replay),'Chart data equals evidence JSON');
  const counts=await page.evaluate(()=>['android','zero','nan'].map(n=>document.querySelector('.series.'+n).getAttribute('points').split(' ').length));
  check(counts.join()==='134,134,57','Polyline point counts '+counts);
  const ys=await page.evaluate(()=>{const f=n=>document.querySelector('.series.'+n).getAttribute('points').split(' ').map(p=>9-Number(p.split(',')[1]));return {android:f('android'),zero:f('zero'),nan:f('nan')};});
  check(same(ys.android,embedded.android)&&same(ys.nan,embedded.nan),'Drawn points match data');
  const claims=evidence.full_trajectory;
  check(claims.all_zero_bos_vs_android_original.max_abs<0.08&&claims.correct_nan_bos_vs_android_original.max_abs>16&&claims.all_zero_replay_eos_step===-1,'Evidence supports the headline claim');
  check(Math.max(...embedded.android)<-4&&Math.max(...embedded.zero)<-4&&embedded.nan.findIndex(v=>v>-4)===53,'No-stop vs stop at frame 53');

  for(const [width,height] of [[1440,1000],[1280,800],[768,1024],[390,844],[320,740]]) {
    await page.setViewportSize({width,height});
    for(const input of ['both','nan','zero']) {
      await page.locator(`.variant-controls [data-input="${input}"]`).click();
      await page.waitForTimeout(280);
      const layout=await page.evaluate(()=>{
        const box=e=>e.getBoundingClientRect();
        const chart=box(document.querySelector('.chart'));
        const overlaps=(a,b)=>!(a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top);
        const yt=[...document.querySelectorAll('.tick.y')].map(box), xt=[...document.querySelectorAll('.tick.x')].map(box);
        const notes=[...document.querySelectorAll('.note,.axis-name')].map(e=>({n:e.className,b:box(e)}));
        return {
          overflow:document.documentElement.scrollWidth>innerWidth,
          bad:[...document.querySelectorAll('h1,h2,h3,p,figure,.model,.model-path,.chart,.legend,.scrub,.phone,.editor,pre')].filter(e=>{const r=box(e);return r.width&&(r.left<-1||r.right>innerWidth+1);}).map(e=>e.id||e.className||e.tagName),
          loopClipped:[...document.querySelectorAll('.loop-box')].some(e=>e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1),
          loopOverlap:(()=>{const b=[...document.querySelectorAll('.loop-box')].map(box);return b.some((x,i)=>b.some((y,j)=>j>i&&overlaps(x,y)));})(),
          loopOrder:(()=>{const t=n=>box(document.querySelector('#step-figure .loop-box.'+n)).top;return t('start')<t('core')&&t('core')<t('frame')&&t('core')<t('stop');})(),
          preOverflow:[...document.querySelectorAll('pre')].some(p=>p.scrollWidth>p.clientWidth+1),
          modelOverlap:[...document.querySelectorAll('.model')].some(e=>{const[a,b]=[...e.children].map(x=>x.getBoundingClientRect());return a.right>b.left+.5;}),
          tickOverlap:yt.some((a,i)=>yt.some((b,j)=>j>i&&overlaps(a,b)))||xt.some((a,i)=>xt.some((b,j)=>j>i&&overlaps(a,b))),
          noteOutside:notes.filter(x=>x.b.left<-1||x.b.right>innerWidth+1).map(x=>x.n),
          stopNoteInChart:(()=>{const n=box(document.querySelector('.stop-note'));return n.right<=chart.right+2&&n.left>=chart.left;})(),
          thresholdNoteVsStop:overlaps(box(document.querySelector('.threshold-note')),box(document.querySelector('.stop-note'))),
          chartHeight:chart.height, chartWidth:chart.width,
          opacity:{zero:getComputedStyle(document.querySelector('.series.zero')).opacity,nan:getComputedStyle(document.querySelector('.series.nan')).opacity,intended:getComputedStyle(document.querySelector('.intended')).opacity,actual:getComputedStyle(document.querySelector('.actual')).opacity}
        };
      });
      const id=`${width}/${input}`;
      check(!layout.overflow&&!layout.bad.length&&!layout.noteOutside.length,`${id} overflow: ${layout.bad} ${layout.noteOutside}`);
      check(!layout.preOverflow||width<=390,`${id} code excerpt overflows (horizontal scroll is acceptable only on phones)`);
      check(!layout.modelOverlap,`${id} model label overlap`);
      check(!layout.loopClipped&&!layout.loopOverlap&&layout.loopOrder,`${id} one-step diagram clipped/overlapping/out of order`);
      check(!layout.tickOverlap,`${id} axis tick overlap`);
      check(layout.stopNoteInChart,`${id} stop note leaves chart`);
      check(!layout.thresholdNoteVsStop,`${id} chart annotations overlap`);
      check(layout.chartWidth>200&&layout.chartHeight>200,`${id} chart too small`);
      const o=layout.opacity;
      if(input==='both')check(o.zero==='1'&&o.nan==='1'&&o.intended==='1'&&o.actual==='1',`${id} both visible`);
      if(input==='nan')check(Number(o.zero)<.2&&o.nan==='1'&&Number(o.actual)<.5&&o.intended==='1',`${id} NaN emphasis`);
      if(input==='zero')check(Number(o.nan)<.2&&o.zero==='1'&&Number(o.intended)<.5&&o.actual==='1',`${id} zero emphasis`);
    }
    await page.locator('summary').focus();await page.keyboard.press('Enter');
    check(await page.locator('.records-body').isVisible(),`${width} keyboard sources`);
    await page.keyboard.press('Enter');
  }
  await page.locator('.variant-controls [data-input="both"]').click();
  await page.waitForTimeout(280);

  // Scrubber: keyboard operable, readout is exact against the data.
  await page.locator('#why-step').focus();
  await page.locator('#why-step').evaluate(r=>{r.value=53;r.dispatchEvent(new Event('input',{bubbles:true}));});
  let readout=await page.locator('#why-readout').innerText();
  check(/Frame 53 \(4\.32 s\)/.test(readout)&&/phone \u22129\.10, continue/.test(readout)&&/zero-input replay \u22129\.10, continue/.test(readout)&&/NaN-input replay \+0\.40, stop/.test(readout),'Frame 53 readout: '+readout);
  await page.keyboard.press('ArrowRight');
  readout=await page.locator('#why-readout').innerText();
  check(/Frame 54 \(4\.40 s\)/.test(readout)&&/\+8\.26, stop/.test(readout),'Keyboard ArrowRight to frame 54: '+readout);
  await page.locator('#why-step').evaluate(r=>{r.value=100;r.dispatchEvent(new Event('input',{bubbles:true}));});
  readout=await page.locator('#why-readout').innerText();
  check(/Frame 100 \(8\.08 s\)/.test(readout)&&/ended at 4\.48 s/.test(readout)&&/phone [\u2212+][0-9.]+, continue/.test(readout),'After NaN replay ends: '+readout);
  check(await page.locator('#step-marker').getAttribute('x1')==='100','Marker tracks frame');

  // Wording must match the retained receipts, in both directions: no stale "inferred", no claim beyond the evidence.
  const body=await page.locator('main').innerText();
  const notes=await page.locator('#records').evaluate(e=>e.textContent);
  const phone=await (await page.request.get(base.split('#')[0].replace(/index\.html$/,'')+'evidence/phone-bos-check/results.json')).json();
  const ob=phone.observations;
  check(ob.original_lifetime_bos_all_zero_runs===2&&ob.fixed_lifetime_bos_all_nan_runs===2,'Receipt: dump builds show zeros 2/2 and NaN 2/2');
  check(ob.unmodified_original_run1_wav_identical_to_retained_failure===true&&ob.unmodified_original_run2_wav_identical_to_retained_failure===false&&ob.unmodified_original_runs_differ,'Receipt: orig run 1 byte-identical, run 2 different');
  const fixedRuns=phone.runs.filter(r=>/fixed/.test(r.run));
  check(fixedRuns.length===4&&ob.fixed_runs_all_stop_at_53&&ob.fixed_runs_identical_wav,'Receipt: four fixed runs stop at 53 with identical audio');
  check(phone.runs.length===8&&phone.runs.every(r=>r.exit===0),'Receipt: eight planned runs, all exited 0');
  const fd=(await (await page.request.get(base.split('#')[0].replace(/index\.html$/,'')+'evidence/bos-zero-replay.json')).json());
  const dr=fd.frame_drift, ft=fd.full_trajectory;
  check(dr.hidden_state_c.frame0>0.9&&dr.hidden_state_c.frame0<1.2&&dr.latent_frame.frame0>0.7&&dr.latent_frame.frame0<0.8,'Receipt supports "about its own size" and "about three quarters": '+dr.hidden_state_c.frame0+' / '+dr.latent_frame.frame0);
  check(Math.abs(fd.step0_logit.correct_nan+9.8847)<1e-3&&Math.abs(fd.step0_logit.all_zeros+10.2709)<1e-3&&ft.max_logit.all_zero_replay<-7.3&&ft.max_logit.all_zero_replay>-7.5,'Receipt supports -9.9, -10.3 and never above -7.4');
  check(fd.validation.correct_nan_bos.eos_step===53&&ft.frame_cap===134,'Receipt supports stop at 53 and the 134-frame cap');
  check(Math.round(56*80)/1000===4.48&&Math.round(134*80)/1000===10.72,'Frame arithmetic: 56 and 134 frames of 80 ms');
  check(/same internal state/.test(body)&&/80 ms/.test(body)&&/never rises above \u22127\.4/.test(body)&&/about its own size/.test(body)&&/about three quarters/.test(body),'Chain explanation is present with its numbers');
  check(!/compounds/i.test(body),'Dropped the unsupported "compounds" claim');
  check(/a build that prints the 32 start values/.test(body)&&/32 zeros, in both runs/.test(body),'Zero observation is labelled as the instrumented build');
  check(/four of four runs/.test(body)&&/byte for byte/.test(body)&&/different wrong answer on its second run/.test(body),'Main text states the exact run counts and the nondeterminism');
  check(!/inferred|closest match|didn.t read the phone.s memory/i.test(body),'No stale inference wording');
  check(!/the allocator (zeroes|zeros|clears)/i.test(body+notes),'No invented allocator explanation');
  check(/not retained/.test(notes)&&/may change allocation/.test(notes)&&/not deterministic/.test(notes)&&/no explanation for why this allocator/i.test(notes)&&/same-size reconstruction/.test(notes),'Limits stay in the notes');
  check(/62 inputs/.test(notes)&&!/65 /.test(body+notes),'Pattern-scan count is exact');
  check(/I made no new listening judgment/.test(notes),'No listening claim');

  await page.locator('#play-explanation').count().then(n=>check(n===0,'Removed lifetime controls'));
  await page.locator('#route-controls [data-route="script"]').click();
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('#route-controls [data-route="speech"]').click();
  check(await page.locator('.speech .packet').first().evaluate(e=>getComputedStyle(e).animationName)==='none','Reduced motion');
  check(await page.locator('.series').first().evaluate(e=>getComputedStyle(e).transitionDuration)==='0s','Reduced-motion chart transition');
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.locator('audio').evaluateAll(es=>es.forEach(e=>{e.muted=true;e.load();}));
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.readyState>=1));
  const durations=await page.locator('audio').evaluateAll(es=>es.map(e=>e.duration));
  check(Math.abs(durations[0]-4.48)<.001&&Math.abs(durations[1]-10.72)<.001,'Exact recording durations, working clip first');
  check(await page.locator('.listening').nth(0).evaluate(e=>e.classList.contains('recovered'))&&/Accepted/.test(await page.locator('audio').nth(0).getAttribute('aria-label')),'Working recording is listed before the broken one');
  await page.locator('audio').nth(0).evaluate(a=>a.play());await page.locator('audio').nth(1).evaluate(a=>a.play());
  check(await page.locator('audio').nth(0).evaluate(a=>a.paused),'No overlapping audio');
  await page.locator('audio').evaluateAll(es=>es.forEach(e=>e.pause()));

  const key=await page.evaluate(()=>`phone-podcast-copy-v3:${location.pathname}`);
  const previous=await page.evaluate(key=>localStorage.getItem(key),key);
  try {
    await page.locator('#edit-copy').click();
    check(await page.locator('[data-edit="intro"]').getAttribute('contenteditable')==='plaintext-only','Inline plain-text edit mode');
    check(await page.locator('[data-edit]').count()>=14,'Prose and headings are editable');
    await page.locator('[data-edit="intro"]').fill('My own intro <b>stays plain text</b>.');
    await page.locator('#edit-copy').click();
    await page.reload();
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Local edit restore');
    check(await page.locator('[data-edit="intro"] b').count()===0,'Edits must not inject HTML');
    check((await page.locator('[data-edit="why-input"] code').count())===1,'Untouched paragraphs keep inline code');
    const download=page.waitForEvent('download');await page.locator('#save-copy').click();
    await(await download).saveAs('/tmp/qoralo-story-v3/phone-podcast-edited.html');
    await page.goto('file:///tmp/qoralo-story-v3/phone-podcast-edited.html');
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Export contains edits');
    check(await page.locator('[contenteditable]').count()===0,'Export strips live edit state');
    check(await page.locator('#edit-copy').isVisible(),'Export keeps working script');
    check(await page.locator('body').evaluate(e=>getComputedStyle(e).color)==='rgb(243, 245, 248)','Export keeps linked styles via base');
    check(await page.locator('.series').count()===3&&await page.locator('#trajectories').count()===1,'Export keeps chart and data');
    await page.locator('.variant-controls [data-input="nan"]').click();
    await page.waitForTimeout(280);
    check(Number(await page.locator('.series.zero').evaluate(e=>getComputedStyle(e).opacity))<.2,'Export keeps working toggle');
    await page.locator('#why-step').evaluate(r=>{r.value=53;r.dispatchEvent(new Event('input',{bubbles:true}));});
    check(/NaN-input replay \+0\.40/.test(await page.locator('#why-readout').innerText()),'Export keeps working scrubber');
    await page.goto(base);
  } finally {
    if(page.url()!==base)await page.goto(base);
    await page.evaluate(({key,previous})=>{if(previous===null)localStorage.removeItem(key);else localStorage.setItem(key,previous);},{key,previous});
    await page.reload();
  }

  // Print and script-failure fallback.
  await page.emulateMedia({media:'print'});
  check(await page.locator('.chart').isVisible()&&!(await page.locator('.editor').isVisible()),'Print keeps chart and hides editor');
  await page.emulateMedia({media:'screen'});
  await page.route('**/article.js',route=>route.abort());await page.reload();
  check(await page.locator('.chart').isVisible()&&await page.locator('.series').count()===3,'Static chart remains');
  check(!(await page.locator('.editor').isVisible())&&!(await page.locator('.scrub').isVisible())&&!(await page.locator('.variant-controls').isVisible()),'Unavailable controls hidden');
  check((await page.locator('#why-readout').innerText())==='','No stale readout without script');
  await page.locator('summary').click();check(await page.locator('.records-body').isVisible(),'Native sources without script');
  await page.unroute('**/article.js');await page.reload();
  await page.setViewportSize({width:1440,height:1000});
  check(!external.length,'External runtime requests: '+external.join(','));
  check(!errors.length,'Page errors: '+errors.join(' | '));
  if(failures.length)throw new Error(failures.join('\n'));
  return 'PASS: chart data equals retained evidence; five widths × three input modes; chart/tick/annotation geometry; keyboard scrubber with exact readouts; overclaim wording guards; reduced motion; exact WAV decoding and exclusive play; inline editing, restore and exported copy with working chart; print; script-failure fallback; no external requests or page errors.';
}
