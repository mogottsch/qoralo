async (page) => {
  const failures = [];
  const errors = [];
  const external = [];
  const check = (ok, message) => { if (!ok) failures.push(message); };
  const origin = await page.evaluate(() => location.origin);
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (/^https?:/.test(r.url()) && !r.url().startsWith(origin + '/')) external.push(r.url()); });
  await page.reload();
  check(await page.locator('main figure').count() === 3, 'Article needs three custom visualizations');
  check(await page.locator('h1').count() === 1, 'One article heading');
  check(await page.locator('script, audio, video, iframe').count() === 0, 'No runtime script, recording or embedded external surface');
  const words = (await page.locator('main').innerText()).trim().split(/\s+/).length;
  check(words <= 330, `Keep the main article very short; got ${words} words`);
  for (const [width, height] of [[1440, 1000], [1280, 800], [768, 1024], [390, 844], [320, 740]]) {
    await page.setViewportSize({width, height});
    await page.evaluate(() => document.querySelector('details').open = false);
    const layout = await page.evaluate(() => {
      const bad = [...document.querySelectorAll('h1,h2,p,figure,.model,.phone,.data-object,.measure-heading,figcaption')].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width && (r.left < -1 || r.right > innerWidth + 1 || e.scrollWidth > e.clientWidth + 1);
      }).map(e => e.className || e.tagName);
      const models = [...document.querySelectorAll('.model')].map(e => {
        const [a,b] = [...e.children].map(x=>x.getBoundingClientRect());
        return a.right <= b.left + .5;
      });
      const setup = [...document.querySelectorAll('[data-seconds]')];
      const expectedSetup = Number(setup[1].dataset.seconds) / Number(setup[0].dataset.seconds);
      const observedSetup = setup[1].getBoundingClientRect().width / setup[0].getBoundingClientRect().width;
      const total = Number(document.querySelector('#chapter-figure').dataset.totalFrames);
      const trackWidth = document.querySelector('.segments').getBoundingClientRect().width;
      const pieces = [...document.querySelectorAll('.segment,.gap')];
      const frameSum = pieces.reduce((s,x)=>s+Number(x.dataset.frames),0);
      const exactWidths = pieces.every(x => Math.abs(x.getBoundingClientRect().width / trackWidth - Number(x.dataset.frames) / total) < .0001);
      const whole = document.querySelector('.whole .bar');
      const wholeRatio = whole.getBoundingClientRect().width / whole.parentElement.getBoundingClientRect().width;
      return {bad, models, expectedSetup, observedSetup, frameSum, total, exactWidths, wholeRatio, expectedWhole:Number(whole.dataset.frames)/total,
        scrolls:document.documentElement.scrollWidth > innerWidth, segments:document.querySelectorAll('.segment').length, gaps:document.querySelectorAll('.gap').length};
    });
    check(!layout.scrolls && !layout.bad.length, `${width}: horizontal overflow ${layout.bad.join(',')}`);
    check(layout.models.every(Boolean), `${width}: model name overlaps hardware label`);
    check(Math.abs(layout.expectedSetup - layout.observedSetup) < .0001, `${width}: setup bars not proportional`);
    check(layout.frameSum === layout.total && layout.exactWidths && layout.segments === 15 && layout.gaps === 14, `${width}: audio segment/gap geometry differs from sample counts`);
    check(Math.abs(layout.wholeRatio - layout.expectedWhole) < .0001, `${width}: whole-input bar not on the same audio scale`);
    await page.locator('#records summary').focus();
    await page.keyboard.press('Enter');
    check(await page.locator('#records').getAttribute('open') !== null, `${width}: keyboard cannot open sources`);
    check(await page.locator('.records-body').isVisible(), `${width}: sources not visible`);
    check(await page.locator('#records').evaluate(e=>e.scrollWidth <= e.clientWidth + 1), `${width}: sources overflow`);
    await page.keyboard.press('Enter');
  }
  const text = await page.locator('main').innerText();
  check(text.includes('GPU') && text.includes('NPU') && text.includes('CPU'), 'Compute placement must retain all three roles');
  check(text.includes('We changed the generation settings too'), 'Do not present segmentation alone as the isolated fix');
  check(text.includes('final app demo') && text.includes('listen to its output'), 'Final demonstration and listening review must remain pending');
  check((await page.locator('#chapter-caption').innerText()).includes('Both recordings: CPU'), 'Audio chart needs explicit CPU provenance');
  check((await page.locator('#chapter-caption').innerText()).includes('not generation time'), 'Audio extent is not synthesis latency');
  check(!/[—–]/.test(text), 'Keep the consulted plain-language punctuation');
  await page.context().setOffline(true);
  try {
    check(await page.locator('main figure').count() === 3, 'Loaded article loses figures offline');
    await page.locator('#records summary').click();
    check(await page.locator('.records-body').isVisible(), 'Native source disclosure should work offline');
  } finally { await page.context().setOffline(false); }
  await page.emulateMedia({media:'print'});
  check(await page.locator('main figure').count() === 3 && await page.locator('main').isVisible(), 'Print loses article or figures');
  await page.emulateMedia({media:'screen', reducedMotion:'reduce'});
  await page.locator('#records').evaluate(e=>e.open=false);
  await page.setViewportSize({width:1440,height:1000});
  check(errors.length === 0, `Page errors: ${errors.join('; ')}`);
  check(external.length === 0, `External runtime requests: ${external.join('; ')}`);
  if (failures.length) throw new Error(failures.join('\n'));
  return `PASS: three custom figures; ${words} main-article words; five viewport sizes; exact setup/audio geometry; native keyboard sources; offline; print; no horizontal overflow, label overlap or external runtime requests.`;
}
