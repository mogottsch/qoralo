async (page) => {
  const failures=[];
  const check=(ok,text)=>{if(!ok)failures.push(text);};
  const base=page.url();
  await page.reload();
  check(await page.locator('figure').count()===2,'Keep only processor and ownership figures');
  check(await page.locator('#chapter-figure,#state-figure').count()===0,'Remove chapter and logit-only explanation');
  check(await page.locator('audio[autoplay]').count()===0,'No autoplay audio');
  for(const [width,height] of [[1440,1000],[1280,800],[768,1024],[390,844],[320,740]]) {
    await page.setViewportSize({width,height});
    for(const variant of ['broken','kept']) {
      await page.locator(`.variant-controls button[data-variant="${variant}"]`).click();
      for(const step of [0,1,2,3]) {
        await page.locator(`#lifetime-controls [data-step="${step}"]`).click();
        const layout=await page.evaluate(()=>({
          overflow:document.documentElement.scrollWidth>innerWidth,
          bad:[...document.querySelectorAll('h1,h2,h3,p,figure,.model,.ownership,.phone,.editor')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&(r.left < -1||r.right>innerWidth+1||e.scrollWidth>e.clientWidth+1);}).map(e=>e.id||e.className||e.tagName),
          overlap:[...document.querySelectorAll('.model')].some(e=>{const[a,b]=[...e.children].map(x=>x.getBoundingClientRect());return a.right>b.left+.5;})
        }));
        check(!layout.overflow&&!layout.bad.length&&!layout.overlap,`${width}/${variant}/${step} overflow: ${layout.bad}`);
        const freed=variant==='broken'&&step>=2;
        check((await page.locator('#buffer-state').innerText())===(freed?'Freed':'Alive'),'Wrong owner lifetime');
        check((await page.locator('#tensor-state').innerText())===(step===0?'Not created yet':freed?'Dangling input':'Valid borrowed input'),'Wrong tensor lifetime');
      }
    }
    await page.locator('summary').focus();await page.keyboard.press('Enter');
    check(await page.locator('.records-body').isVisible(),'Keyboard sources');
    await page.keyboard.press('Enter');
  }
  await page.locator('#play-explanation').click();
  await page.waitForFunction(()=>document.querySelector('#lifetime-figure').dataset.step==='3',null,{timeout:8000});
  check(await page.locator('#play-explanation').getAttribute('aria-pressed')==='false','Bounded explanation should stop');
  await page.locator('#play-explanation').click();
  await page.locator('#lifetime-controls [data-step="1"]').click();
  check(await page.locator('#play-explanation').getAttribute('aria-pressed')==='false','Manual step interrupts');
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('#route-controls [data-route="script"]').click();
  check(await page.locator('.script .packet').first().evaluate(e=>getComputedStyle(e).animationName)==='none','Reduced motion');
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.locator('audio').evaluateAll(es=>es.forEach(e=>{e.muted=true;e.load();}));
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.readyState>=1));
  const durations=await page.locator('audio').evaluateAll(es=>es.map(e=>e.duration));
  check(Math.abs(durations[0]-10.72)<.001&&Math.abs(durations[1]-4.48)<.001,'Exact recording durations');
  await page.locator('audio').nth(0).evaluate(a=>a.play());await page.locator('audio').nth(1).evaluate(a=>a.play());
  check(await page.locator('audio').nth(0).evaluate(a=>a.paused),'No overlapping audio');
  await page.locator('audio').evaluateAll(es=>es.forEach(e=>e.pause()));
  const key=await page.evaluate(()=>`phone-podcast-copy-v3:${location.pathname}`);
  const previous=await page.evaluate(key=>localStorage.getItem(key),key);
  try {
    await page.locator('#edit-copy').click();
    check(await page.locator('[data-edit="intro"]').getAttribute('contenteditable')==='plaintext-only','Inline plain-text edit mode');
    await page.locator('[data-edit="intro"]').fill('My own intro <b>stays plain text</b>.');
    await page.locator('#edit-copy').click();
    await page.reload();
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Local edit restore');
    check(await page.locator('[data-edit="intro"] b').count()===0,'Edits must not inject HTML');
    const download=page.waitForEvent('download');await page.locator('#save-copy').click();
    await(await download).saveAs('/tmp/qoralo-story-v3/phone-podcast-edited.html');
    await page.goto('file:///tmp/qoralo-story-v3/phone-podcast-edited.html');
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Export contains edits');
    check(await page.locator('[contenteditable]').count()===0,'Export strips live edit state');
    check(await page.locator('#edit-copy').isVisible(),'Export keeps working script');
    check(await page.locator('body').evaluate(e=>getComputedStyle(e).color)==='rgb(243, 245, 248)','Export keeps linked styles via base');
    await page.locator('.variant-controls [data-variant="kept"]').click();
    check(await page.locator('#buffer-state').innerText()==='Alive','Export keeps working diagram');
    await page.goto(base);
  } finally {
    if(page.url()!==base)await page.goto(base);
    await page.evaluate(({key,previous})=>{if(previous===null)localStorage.removeItem(key);else localStorage.setItem(key,previous);},{key,previous});
    await page.reload();
  }
  await page.route('**/article.js',route=>route.abort());await page.reload();
  check(await page.locator('#buffer-state').innerText()==='Freed','Static lifetime outcome remains');
  check(!(await page.locator('.editor').isVisible()),'Unavailable editing controls hidden');
  await page.locator('summary').click();check(await page.locator('.records-body').isVisible(),'Native sources without script');
  await page.unroute('**/article.js');await page.reload();
  await page.setViewportSize({width:1440,height:1000});
  if(failures.length)throw new Error(failures.join('\n'));
  return 'PASS: five widths × two scopes × four lifetime stages; keyboard sources; bounded replay/interruption; reduced motion; muted exact WAV decoding; inline editing/local restore; safe HTML export reopened from disk with working assets/controls; script-failure fallback.';
}
