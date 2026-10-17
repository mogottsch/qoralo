async (page) => {
  const failures = [], errors = [], external = [];
  const check = (ok, message) => { if (!ok) failures.push(message); };
  const origin = await page.evaluate(() => location.origin);
  const base = page.url();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url()) && !request.url().startsWith(origin + '/')) external.push(request.url()); });
  await page.reload();
  check(await page.locator('main figure').count() === 3, 'Three custom explanatory figures');
  check(await page.locator('h1').count() === 1, 'One article heading');
  check(await page.locator('audio').count() === 2, 'Failed and recovered exact CPU recordings');
  check(await page.locator('audio[autoplay], iframe, video').count() === 0, 'No autoplay or embedded remote surface');
  check(await page.locator('audio').evaluateAll(audios => audios.every(a => a.paused && a.currentTime === 0 && a.preload === 'none')), 'No audio should start or preload before a reader asks');
  for (const [width,height] of [[1440,1000],[1280,800],[768,1024],[390,844],[320,740]]) {
    await page.setViewportSize({width,height});
    for (const stage of [0,1,2]) {
      await page.locator(`#stage-controls [data-stage="${stage}"]`).click();
      check(await page.locator('#state-figure').getAttribute('data-stage') === String(stage), `${width}: stage control doesn't change figure`);
      const layout = await page.evaluate(() => {
        const bad = [...document.querySelectorAll('h1,h2,h3,p,figure,.model,.phone,.data-object,.measure-heading,figcaption,.trace-lane,.recurrent-flow,.listening')].filter(e => {
          const r=e.getBoundingClientRect();
          return r.width && (r.left < -1 || r.right > innerWidth + 1 || e.scrollWidth > e.clientWidth + 1);
        }).map(e => e.className || e.tagName);
        const models = [...document.querySelectorAll('.model')].every(e => { const [a,b]=[...e.children].map(x=>x.getBoundingClientRect());return a.right<=b.left+.5; });
        const count = selector => [...document.querySelectorAll(selector)].filter(e=>e.getBoundingClientRect().height>0).length;
        const total=Number(document.querySelector('#chapter-figure').dataset.totalFrames);
        const track=document.querySelector('.segments').getBoundingClientRect().width;
        const pieces=[...document.querySelectorAll('.segment,.gap')];
        const whole=document.querySelector('.whole .bar');
        return {bad,models,scrolls:document.documentElement.scrollWidth>innerWidth,
          visible:[count('.lane-input'),count('.lane-step'),count('.lane-outcome')],
          sampleSum:pieces.reduce((sum,x)=>sum+Number(x.dataset.frames),0),total,
          exact:pieces.every(x=>Math.abs(x.getBoundingClientRect().width/track-Number(x.dataset.frames)/total)<.0001),
          wholeRatio:whole.getBoundingClientRect().width/whole.parentElement.getBoundingClientRect().width,expectedWhole:Number(whole.dataset.frames)/total};
      });
      check(!layout.scrolls && !layout.bad.length && layout.models, `${width}/stage${stage}: overflow or model overlap ${layout.bad.join(',')}`);
      check(layout.visible[stage] === 3 && layout.visible.reduce((a,b)=>a+b,0) === 3, `${width}: wrong diagnostic stage contents`);
      check(layout.sampleSum === layout.total && layout.exact && Math.abs(layout.wholeRatio-layout.expectedWhole)<.0001, `${width}: measured audio proportions changed`);
    }
    await page.locator('#records summary').focus();
    await page.keyboard.press('Enter');
    check(await page.locator('.records-body').isVisible(), `${width}: keyboard cannot open sources`);
    check(await page.locator('#records').evaluate(e=>e.scrollWidth<=e.clientWidth+1), `${width}: sources overflow`);
    await page.keyboard.press('Enter');
  }
  for (const name of ['script','speech']) {
    await page.locator(`#route-controls [data-route="${name}"]`).click();
    check(await page.locator('#compute-figure').getAttribute('data-route') === name, 'Route explorer failed');
    check((await page.locator('#route-status').innerText()).includes(name === 'script' ? 'GPU' : 'HTP'), 'Wrong route explanation');
  }
  await page.locator('#segment-picker').focus();
  await page.keyboard.press('End');
  check((await page.locator('#segment-status').innerText()).includes('Piece 15 of 15') && (await page.locator('#segment-status').innerText()).includes('no final gap'), 'Last segment/gap explanation');
  await page.keyboard.press('Home');
  check((await page.locator('#segment-status').innerText()).includes('Piece 1 of 15'), 'Keyboard range navigation');
  check(await page.locator('.segment.is-selected').count() === 1, 'Selected segment should be unique');
  await page.locator('#play-explanation').click();
  await page.waitForFunction(() => document.querySelector('#state-figure').dataset.stage === '2', null, {timeout:8000});
  check(await page.locator('#play-explanation').getAttribute('aria-pressed') === 'false', 'Bounded explanation should stop by itself');
  await page.locator('#play-explanation').click();
  await page.locator('#stage-controls [data-stage="1"]').click();
  check(await page.locator('#play-explanation').getAttribute('aria-pressed') === 'false', 'Manual step must interrupt automatic explanation');
  // Browser playback is muted: this tests decoding/control, not a new listening verdict.
  await page.locator('audio').evaluateAll(audios => audios.forEach(a=>{a.muted=true;a.load();}));
  await page.waitForFunction(() => [...document.querySelectorAll('audio')].every(a=>a.readyState>=1));
  const durations=await page.locator('audio').evaluateAll(audios=>audios.map(a=>a.duration));
  check(Math.abs(durations[0]-10.72)<.001 && Math.abs(durations[1]-4.48)<.001, 'Players loaded wrong recordings');
  await page.locator('audio').nth(0).evaluate(a=>a.play());
  await page.locator('audio').nth(1).evaluate(a=>a.play());
  check(await page.locator('audio').nth(0).evaluate(a=>a.paused), 'Two recordings should not play over each other');
  await page.locator('audio').evaluateAll(audios=>audios.forEach(a=>{a.pause();a.currentTime=0;}));
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('#route-controls [data-route="script"]').click();
  check(await page.locator('.script .packet').first().evaluate(e=>getComputedStyle(e).animationName)==='none', 'Reduced motion still has spatial packet animation');
  await page.locator('#stage-controls [data-stage="2"]').click();
  check(await page.locator('.lane-outcome').first().isVisible(), 'Reduced motion loses diagnostic results');
  await page.context().setOffline(true);
  try {
    await page.locator('#stage-controls [data-stage="0"]').click();
    check(await page.locator('#state-figure').getAttribute('data-stage')==='0', 'Loaded article interaction depends on network');
  } finally {await page.context().setOffline(false);}
  await page.emulateMedia({media:'print'});
  check(await page.locator('.lane-step').first().isVisible() && await page.locator('.lane-outcome').first().isVisible(), 'Print must include all diagnostic evidence');
  await page.emulateMedia({media:'screen',reducedMotion:'no-preference'});
  // A blocked script must leave the complete static outcomes and native players usable.
  await page.route('**/article.js', route=>route.abort());
  await page.goto(base);
  check(await page.locator('main figure').count()===3 && await page.locator('.lane-outcome').first().isVisible(), 'Script failure removes explanatory content');
  check(!(await page.locator('#stage-controls').isVisible()), 'Unavailable enhancement controls should not appear');
  await page.locator('#records summary').click();
  check(await page.locator('.records-body').isVisible(), 'Native details requires JavaScript');
  await page.unroute('**/article.js');
  await page.goto(base);
  await page.setViewportSize({width:1440,height:1000});
  const words=(await page.locator('main').innerText()).trim().split(/\s+/).length;
  check(words<=650, `Keep short; visible main article has ${words} words including all figure labels/controls`);
  check(external.length===0, `External runtime requests: ${external.join('; ')}`);
  check(errors.length===0, `Page errors: ${errors.join('; ')}`);
  if(failures.length)throw new Error(failures.join('\n'));
  return `PASS: ${words} visible words including figures; three interactive figures; five widths × three stages; exact sample geometry; keyboard range/disclosure; bounded replay/interruption; muted WAV playback; reduced motion; offline interaction; print; script-failure fallback; no overflow or external runtime requests.`;
}
