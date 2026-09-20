async (page) => {
  const failures = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const check = (condition, message) => { if (!condition) failures.push(message); };
  const deckURL = page.url() === 'about:blank' ? 'http://127.0.0.1:8766/docs/presentation/' : page.url().split('#')[0];
  await page.goto(deckURL);
  await page.waitForFunction(() => !!window.presentation);
  const config = await page.evaluate(() => ({ routes: window.presentation.routes, branchMeta: window.presentation.branchMeta, branchPoint: window.presentation.branchPoint, resumePoint: window.presentation.resumePoint }));
  const main = config.routes.main;
  const hardware = config.routes.hardware;
  const backends = config.routes.backends;
  const supertonic = config.routes.supertonic;
  const gemma = config.routes.gemma;
  const longform = config.routes['supertonic-length'];
  const htpOverview = config.routes['supertonic-htp'];
  const htpSteps = config.routes['supertonic-htp-steps'];
  const deployment = await page.locator('.deployment-slide').getAttribute('id');
  const models = await page.locator('.models-slide').getAttribute('id');
  const ids = await page.locator('.slide').evaluateAll(slides => slides.map(slide => slide.id));
  const current = () => page.evaluate(() => window.presentation.state.id);
  const go = id => page.evaluate(id => window.presentation.navigate(id), id);
  const wordCount = selector => page.locator(selector).innerText().then(text => text.trim().split(/\s+/).length);
  check(ids.length === 23, 'Expected six main slides, five original details, one HTP overview and eleven walkthrough slides');
  check(JSON.stringify(main) === JSON.stringify(['slide-1', 'slide-2', 'slide-3', 'slide-4', 'slide-5', 'slide-models']), 'Default story must continue from deployment to models and benchmark links');
  check(await page.locator('#slide-6, .experiment-slide').count() === 0, 'Removed experiment-questions slide must not remain in the deck');
  check(hardware.length === 1 && backends.length === 1 && supertonic.length === 1 && gemma.length === 1 && longform.length === 1 && Object.keys(config.routes).length === 8, 'Preserve the five original detours and add two HTP routes');
  check(htpOverview.length === 1 && htpSteps.length === 11, 'HTP needs one optional overview and eleven detail slides');
  check(config.branchMeta['supertonic-htp'].origin === deployment && config.branchMeta['supertonic-htp'].resume === deployment, 'HTP overview returns to deployment at both boundaries');
  check(config.branchMeta['supertonic-htp-steps'].origin === htpOverview[0] && config.branchMeta['supertonic-htp-steps'].resume === htpOverview[0], 'Both walkthrough boundaries must return to its overview');
  check(config.branchMeta['supertonic-length'].origin === supertonic[0] && config.branchMeta['supertonic-length'].resume === supertonic[0], 'Both nested long-input boundaries must return to Supertonic architecture');
  check(config.branchMeta.supertonic.origin === models && config.branchMeta.supertonic.resume === models, 'Supertonic must return to Models & results at either boundary');
  check(config.branchMeta.gemma.origin === models && config.branchMeta.gemma.resume === models, 'Gemma must return to Models & results at either boundary');
  check(await page.locator('#slide-9, [data-enter-branch="specialization"]').count() === 0, 'The specialization deep dive and its entry must remain removed');
  check(config.resumePoint === deployment, 'Hardware must rejoin before deployment, not after it');
  check(config.branchMeta.hardware.origin === config.branchPoint && config.branchMeta.hardware.resume === deployment, 'Hardware branch boundaries are wrong');
  check(config.branchMeta.backends.origin === deployment && config.branchMeta.backends.resume === deployment, 'Backend branch boundaries are wrong');
  check(await page.locator('.deployment-slide').getAttribute('data-branch') === null, 'Deployment must not be marked as a detour');
  check(new Set(Object.values(config.routes).flat()).size === ids.length, 'Every slide must belong to a route');

  for (const [width, height] of [[1600, 1000], [1920, 1080], [1280, 720], [390, 844], [360, 800], [320, 740]]) {
    await page.setViewportSize({ width, height });
    // Measure intrinsic layout, not the existing benchmark-link hover arrow's 3px translation.
    // Pointer position survives viewport changes and otherwise makes this sweep state-dependent.
    await page.mouse.move(0, 0);
    for (const id of ids) {
      await go(id);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const layout = await page.evaluate(() => {
        const slide = document.querySelector('.slide.active');
        const bounds = slide.getBoundingClientRect();
        const protruding = [...slide.querySelectorAll('article, h1, h2, h3, p, button, table, td, th, .slide-footer, .soc-boundary, .memory-block, .hexagon-units, .workflow-lane, .workflow-node, .deploy-bridge, .journey-step, .branch-choices, .detour-actions, .local-memory, .backend-catalog-grid, .backend-tool-grid, .models-grid, .model-results, .model-list li, .supertonic-diagram, .st-module > rect, .gemma-architecture-visual, .htp-body, .htp-svg, .htp-node, .htp-position, .htp-source-link, .htp-keyline')]
          .filter(element => {
            const rect = element.getBoundingClientRect();
            return rect.width && (rect.left < bounds.left - 1 || rect.right > bounds.right + 1 || rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1);
          }).map(element => element.className || element.tagName);
        const overflowing = [...slide.querySelectorAll('.processor-column, td, th, .quadrant-name, p, h1, h2, h3, .compute-block, .memory-block, .workflow-node, .hexagon-units, .journey-step, .branch-choices button, .detour-actions button, .hexagon-worker, .qnn-backend-card, .backend-tool-card, .model-family, .model-list li, .model-results, .htp-body, .htp-node, .htp-column, .htp-proof-list li, .htp-position')]
          .filter(element => element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)
          .map(element => element.className || element.tagName);
        const panels = [...slide.querySelectorAll('.processor-column, tbody td, .compute-block, .memory-block, .workflow-node, .journey-step, .hexagon-worker, .branch-choices button, .detour-actions button, .qnn-backend-card, .backend-tool-card, .model-family, .gemma-architecture-visual, .htp-node')].map(element => element.getBoundingClientRect());
        const overlaps = panels.some((a, i) => panels.slice(i + 1).some(b =>
          Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
          Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1));
        return {
          protruding, overflowing, overlaps,
          ratio: bounds.width / bounds.height,
          designWidth: slide.offsetWidth, designHeight: slide.offsetHeight,
          withinViewport: bounds.left >= -1 && bounds.right <= innerWidth + 1 && bounds.top >= -1 && bounds.bottom <= innerHeight - 63,
          documentWidth: document.documentElement.scrollWidth, documentHeight: document.documentElement.scrollHeight,
          viewportWidth: innerWidth, viewportHeight: innerHeight,
          activeCount: document.querySelectorAll('.slide.active').length,
        };
      });
      const label = `${width}×${height}, ${id}`;
      check(layout.documentWidth <= layout.viewportWidth && layout.documentHeight <= layout.viewportHeight, `${label}: page scrolls`);
      check(layout.designWidth === 1920 && layout.designHeight === 1080, `${label}: wrong canvas`);
      check(Math.abs(layout.ratio - 16 / 9) < .001 && layout.withinViewport, `${label}: stage not fitted at 16:9`);
      check(layout.activeCount === 1, `${label}: exactly one slide must be active`);
      check(!layout.protruding.length, `${label}: content outside slide: ${layout.protruding}`);
      check(!layout.overflowing.length, `${label}: overflowing content: ${layout.overflowing}`);
      check(!layout.overlaps, `${label}: overlapping panels`);
    }
    // The overview is outside the fixed stage and must fit a phone too.
    await page.locator('#overview-button').click();
    check(await page.locator('#overview-dialog').evaluate(element => element.scrollWidth <= element.clientWidth + 1), `${width}px: overview has horizontal overflow`);
    await page.keyboard.press('Escape');
    await go(backends[0]);
    await page.locator('[data-backend-detail="htp"]').click();
    const detailLayout = await page.locator('#backend-dialog').evaluate(element => {
      const rect = element.getBoundingClientRect();
      return {
        horizontalOverflow: element.scrollWidth > element.clientWidth + 1,
        withinViewport: rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight,
      };
    });
    check(!detailLayout.horizontalOverflow && detailLayout.withinViewport, `${width}px: backend detail dialog does not fit`);
    await page.keyboard.press('Escape');
  }

  await page.setViewportSize({ width: 1600, height: 1000 });
  // Notes must follow every destination, including optional slides.
  for (const id of ids) {
    await go(id);
    await page.keyboard.press('n');
    check(await page.locator('#notes-dialog').isVisible(), `${id}: N should open notes`);
    const title = await page.locator(`#${id}`).getAttribute('data-title');
    check((await page.locator('#notes-title').innerText()).includes(title), `${id}: notes title mismatch`);
    check(await page.locator('.notes-body a').count() >= 3, `${id}: references missing`);
    await page.keyboard.press('ArrowRight');
    check(await current() === id, 'Notes must block navigation');
    await page.keyboard.press('Escape');
  }

  await go(main[0]);
  check(await page.locator('.journey-step').count() === 5, 'Journey must retain the five-step timeline');
  check((await page.locator('.journey-step h2').first().innerText()).replace(/\s+/g, ' ') === 'VibeVoice → smaller TTS', 'Journey must start with VibeVoice, then smaller TTS');
  check(await wordCount('.journey-slide') <= 85, 'Keep the opening timeline concise');
  check(await page.locator('.journey-step > p').count() === 5, 'Each phase should have one short detail');
  check(await page.locator('.journey-step > p').evaluateAll(captions => captions.every(caption =>
    caption.textContent.trim().split(/\s+/).length <= 10 && caption.clientHeight <= parseFloat(getComputedStyle(caption).lineHeight) * 3 + 1)), 'Phase details must stay within ten words and three rendered lines');
  check((await page.locator('.journey-slide').innerText()).toLowerCase().includes('prototype'), 'Opening must qualify the app as a prototype');
  for (let i = 0; i < main.length; i++) {
    check(await current() === main[i], 'Arrow path must follow the main story, not DOM order');
    check(await page.locator('#counter').innerText() === `${i + 1} / ${main.length}`, 'Main counter should exclude optional slides');
    check(await page.locator('#previous').isDisabled() === (i === 0), 'Previous boundary state incorrect');
    check(await page.locator('#next').isDisabled() === (i === main.length - 1), 'Next boundary state incorrect');
    if (i < main.length - 1) await page.keyboard.press('ArrowRight');
  }
  await page.keyboard.press('Home');
  check(await current() === main[0], 'Home should reach the first main slide');
  await page.keyboard.press('End');
  check(await current() === main.at(-1), 'End should reach the last main slide, not a detour');
  check(await current() === models && await page.locator('#next').isDisabled(), 'Models and results must close the main story');
  await page.keyboard.press('ArrowRight');
  check(await current() === models, 'Right at the end must stay on the models slide');
  check(await page.locator('.models-slide .model-family').count() === 2, 'Closing slide needs separate TTS and LLM columns');
  check(await wordCount('.models-slide') <= 70, 'Keep the model/results slide short');
  check(await page.locator('.models-slide .model-lead .model-deep-dive').count() === 2, 'Both architecture entries must stay prominent');
  check(await page.locator('.models-slide .model-family-art[aria-hidden="true"]').count() === 2, 'Keep speech/text artwork decorative');
  check(await page.locator('.models-slide .model-name').evaluateAll(labels => labels.every(label => label.scrollWidth <= label.clientWidth + 1 && label.clientHeight <= parseFloat(getComputedStyle(label).lineHeight) * 1.1)), 'Primary model names must remain on one line');
  check(await page.locator('.model-results').evaluateAll(links => Math.abs(links[0].getBoundingClientRect().top - links[1].getBoundingClientRect().top) < 1), 'Result links should align across both collections');
  check(await page.locator('.models-slide .model-family').evaluateAll(families => families.every(family => {
    const items = [...family.querySelectorAll('header, .model-list > li, .model-results')].map(element => element.getBoundingClientRect());
    return items.every((a, i) => items.slice(i + 1).every(b => Math.min(a.right, b.right) - Math.max(a.left, b.left) <= 1 || Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) <= 1));
  })), 'Collection headers, models and result links must not overlap');
  const modelText = await page.locator('.models-slide').innerText();
  for (const name of ['Supertonic 3', 'Pocket TTS', 'Kokoro', 'MOSS-TTS-Nano', 'VibeVoice', 'Gemma 4 E2B IT', 'Qwen3.5-2B', 'LFM2.5-2.6B']) {
    check(modelText.includes(name), `Model list missing ${name}`);
  }
  for (const [kind, path] of [['tts', '../android-benchmarks/index.html'], ['llm', '../android-llm-benchmarks/index.html']]) {
    const link = page.locator(`[data-benchmark="${kind}"]`);
    check(await link.getAttribute('href') === path, `${kind}: wrong benchmark destination`);
    check(await link.getAttribute('target') === '_blank' && (await link.getAttribute('rel')).includes('noopener'), `${kind}: results should open safely in a new tab`);
    await link.focus();
    const [results] = await Promise.all([page.waitForEvent('popup'), page.keyboard.press('Enter')]);
    try {
      await results.waitForLoadState('domcontentloaded');
      const expectedURL = await page.evaluate(path => new URL(path, location.href).href, path);
      check(results.url() === expectedURL, `${kind}: result page URL mismatch`);
      check((await results.locator('h1').innerText()).toLowerCase().includes('benchmark'), `${kind}: benchmark page did not load`);
      check(await results.locator('#routes tbody tr').count() > 0, `${kind}: result table is missing`);
    } finally { await results.close(); }
    await page.bringToFront();
    check(await current() === models, 'Opening results must preserve the presentation position');
  }
  await page.keyboard.press('ArrowLeft');
  check(await current() === deployment, 'Back from models should return to deployment');
  await page.locator('.deployment-slide [data-resume-story="slide-models"]').click();
  check(await current() === models, 'Explicit Models & results button must reach the closing slide');

  const supertonicEntry = page.locator('#slide-models [data-enter-branch="supertonic"]');
  await supertonicEntry.focus();
  await page.keyboard.press('Enter');
  check(await current() === supertonic[0], 'Model-name keyboard activation should open Supertonic architecture');
  check(await wordCount('.supertonic-slide') <= 115, 'Keep Supertonic architecture speaker-led');
  check(await page.locator('.supertonic-diagram [data-module]').count() === 4, 'The architecture should show exactly four inference graphs');
  check(await page.locator('.supertonic-diagram').evaluate(svg => [...svg.querySelectorAll('text')].every(text => {
    const box = text.getBBox();
    return box.x >= 0 && box.y >= 0 && box.x + box.width <= svg.viewBox.baseVal.width && box.y + box.height <= svg.viewBox.baseVal.height;
  })), 'Supertonic SVG labels must fit the diagram');
  check((await page.locator('.supertonic-takeaway').innerText()).includes('Not token-by-token'), 'Explain whole-latent refinement rather than autoregressive tokens');
  await page.keyboard.press('ArrowRight');
  check(await current() === models, 'Next from Supertonic returns to models');
  await supertonicEntry.click();
  await page.keyboard.press('ArrowLeft');
  check(await current() === models, 'Previous from Supertonic returns to models');
  await supertonicEntry.click();
  await page.goBack();
  check(await current() === models, 'Browser Back restores the model index');
  await page.goForward();
  await page.reload();
  check(await current() === supertonic[0] && (await page.evaluate(() => window.presentation.state.route)) === 'supertonic', 'Forward and reload preserve the Supertonic deep link');
  await page.locator('#fullscreen').click();
  check(await page.locator('.supertonic-slide [data-back-story]').isVisible(), 'Architecture needs a visible fullscreen return control');
  await page.locator('.supertonic-slide [data-back-story]').click();
  check(await current() === models, 'Explicit architecture return restores models');
  await page.keyboard.press('f');
  await page.context().setOffline(true);
  try {
    await supertonicEntry.click();
    await page.locator('.supertonic-slide [data-back-story]').click();
    check(await current() === models, 'Architecture detour must work offline');
  } finally { await page.context().setOffline(false); }

  // An optional detour inside an optional detour; never inserted into the architecture arrow path.
  await go(supertonic[0]);
  const longEntry = page.locator('.supertonic-slide [data-enter-branch="supertonic-length"]');
  await longEntry.focus();
  await page.keyboard.press('Enter');
  check(await current() === longform[0], 'Architecture button opens the long-input detour');
  check(await page.locator('.longform-slide h1').evaluate(e => document.activeElement === e), 'Nested destination heading receives focus');
  check(await page.locator('#counter').innerText() === '1 / 1', 'Nested route has its own counter');
  check(await wordCount('.longform-slide') <= 160, 'Keep the long-input slide concise');
  const longText = await page.locator('.longform-slide').innerText();
  check(longText.includes('Original release') && longText.includes('19 Nov 2025') && longText.includes('Exact v3 training cutoff: not confirmed.'), 'The original training quote must not become a claimed v3 cutoff');
  check(longText.includes('not a segmentation-only experiment'), 'Visible causal qualification is required');
  check(await page.locator('.longform-chart .lf-segment').count() === 15, 'Chart needs exactly fifteen measured native segments');
  check(await page.locator('.longform-chart').evaluate(svg => {
    const scale = 940 / Number(svg.dataset.totalFrames), gap = Number(svg.dataset.gapFrames);
    let cursor = 250, frames = 0;
    for (const rect of svg.querySelectorAll('.lf-segment')) {
      const n = Number(rect.dataset.frames);
      if (Math.abs(rect.x.baseVal.value - cursor) > .001 || Math.abs(rect.width.baseVal.value - n * scale) > .001) return false;
      cursor += (n + gap) * scale; frames += n;
    }
    return frames + 14 * gap === Number(svg.dataset.totalFrames) && Math.abs(cursor - gap * scale - 1190) < .001 &&
      Math.abs(svg.querySelector('.lf-whole').width.baseVal.value - 1304030 * scale) < .001 &&
      [...svg.querySelectorAll('text')].every(text => { const b = text.getBBox(); return b.x >= 0 && b.y >= 0 && b.x + b.width <= 1472 && b.y + b.height <= 290; });
  }), 'Audio bars and gaps must use exact sample-count proportions and labels must fit');
  await page.keyboard.press('ArrowRight');
  check(await current() === supertonic[0], 'Right returns to architecture, not the main story');
  await longEntry.click();
  await page.keyboard.press('ArrowLeft');
  check(await current() === supertonic[0], 'Left returns to architecture');
  await longEntry.click();
  await page.goBack();
  check(await current() === supertonic[0], 'Browser Back restores architecture');
  await page.goForward(); await page.reload();
  check(await current() === longform[0] && (await page.evaluate(() => window.presentation.state.route)) === 'supertonic-length', 'Nested deep link survives history and reload');
  await page.locator('#overview-button').click();
  check(await page.locator('#overview-routes [aria-current="step"]').getAttribute('data-go-slide') === longform[0], 'Map marks the nested detail');
  await page.keyboard.press('Escape');
  await page.locator('#fullscreen').click();
  await page.locator('.longform-slide [data-back-story]').click();
  check(await current() === supertonic[0], 'Fullscreen nested exit remains usable');
  await page.keyboard.press('f');
  await page.context().setOffline(true);
  try {
    await longEntry.click(); await page.locator('.longform-slide [data-back-story]').click();
    check(await current() === supertonic[0], 'Nested route works offline');
  } finally { await page.context().setOffline(false); }
  check(await page.locator('.supertonic-explorer-link').getAttribute('href') === '../explainers/supertonic-3.html', 'Preserve the independent computation explorer link');
  check(await page.locator('.longform-note-link').getAttribute('href') === '../wiki/concepts/supertonic-long-form-synthesis.md', 'Long-input slide links the owning wiki note');
  await go(models);

  const gemmaEntry = page.locator('#slide-models [data-enter-branch="gemma"]');
  await gemmaEntry.focus();
  await page.keyboard.press('Space');
  check(await current() === gemma[0], 'Model-name Space activation should open Gemma architecture');
  check(await page.locator('.gemma-architecture-slide h1').evaluate(element => document.activeElement === element), 'Gemma destination heading should receive focus');
  check(await page.locator('#route-label').innerText() === 'Gemma architecture', 'Gemma route needs a friendly label');
  check(await page.locator('#counter').innerText() === '1 / 1', 'Gemma counter is relative to its branch');
  check(await wordCount('.gemma-architecture-slide') <= 115, 'Keep Gemma architecture speaker-led');
  check(await page.locator('.gemma-architecture-visual use[data-layer-group]').count() === 7, 'Show seven groups of five layers');
  check(await page.locator('#gemma-five-layers [data-attention]').evaluateAll(tiles => tiles.map(tile => tile.dataset.attention).join(',')) === 'local,local,local,local,full', 'Each group must show four local layers followed by one full layer');
  check(await page.locator('.gemma-architecture-visual use[data-kv="producer"]').count() === 3 && await page.locator('.gemma-architecture-visual use[data-kv="reuse"]').count() === 4, 'First fifteen layers produce KV, final twenty reuse it');
  check(await page.locator('.gemma-architecture-visual').evaluate(svg => {
    const boxes = [...svg.querySelectorAll('text')].map(text => text.getBBox());
    return boxes.every(box => box.x >= 0 && box.y >= 0 && box.x + box.width <= svg.viewBox.baseVal.width && box.y + box.height <= svg.viewBox.baseVal.height) &&
      !boxes.some((a, i) => boxes.slice(i + 1).some(b => Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > 1 && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > 1));
  }), 'Gemma SVG labels must fit without overlaps');
  check((await page.locator('.gemma-architecture-slide .subtitle').innerText()).includes('35 layers still execute'), 'KV sharing must not imply skipped layers');
  await page.keyboard.press('n');
  check((await page.locator('.notes-body').innerText()).includes('attention_k_eq_v=false'), 'Preserve the E2B-specific K/V distinction');
  check(await page.locator('.notes-body a[href="../wiki/models/gemma-4-e2b.md"]').count() === 1, 'Gemma notes must link the prior architecture note');
  await page.keyboard.press('Escape');
  await page.keyboard.press('ArrowRight');
  check(await current() === models, 'Next from Gemma returns to models');
  await gemmaEntry.click();
  await page.keyboard.press('ArrowLeft');
  check(await current() === models, 'Previous from Gemma returns to models');
  await gemmaEntry.click();
  await page.goBack();
  check(await current() === models, 'Browser Back from Gemma restores models');
  await page.goForward();
  await page.reload();
  check(await current() === gemma[0] && (await page.evaluate(() => window.presentation.state.route)) === 'gemma', 'Gemma forward/reload preserves the branch');
  await page.locator('#overview-button').click();
  check(await page.locator('#overview-routes [aria-current="step"]').getAttribute('data-go-slide') === gemma[0], 'Map must mark Gemma as the active destination');
  await page.locator(`#overview-routes [data-go-slide="${gemma[0]}"]`).click();
  check(await current() === gemma[0] && !await page.locator('#overview-dialog').isVisible(), 'Map must support a Gemma jump');
  await page.locator('#fullscreen').click();
  check(await page.locator('.gemma-architecture-slide [data-resume-story]').isVisible(), 'Gemma return must remain visible in fullscreen');
  await page.locator('.gemma-architecture-slide [data-resume-story]').click();
  check(await current() === models, 'Gemma explicit return restores models');
  await page.keyboard.press('f');
  await page.context().setOffline(true);
  try {
    await gemmaEntry.click();
    await page.locator('.gemma-architecture-slide [data-resume-story]').click();
    check(await current() === models, 'Gemma branch works offline');
  } finally { await page.context().setOffline(false); }

  // One optional one-pager and an eleven-slide nested route; the main story stays six slides.
  await go(deployment);
  const htpEntry = page.locator('.deployment-slide [data-enter-branch="supertonic-htp"]');
  await htpEntry.focus(); await page.keyboard.press('Enter');
  check(await current() === htpOverview[0], 'Deployment opens the HTP one-pager');
  check(await page.locator('#counter').innerText() === '1 / 1', 'HTP overview owns a one-slide route');
  check(await page.locator('.htp-overview .htp-source-link').getAttribute('href') === '../supertonic-android-htp-reconstruction.md', 'One-pager links the source Markdown');
  await page.keyboard.press('ArrowRight');
  check(await current() === deployment, 'Overview right returns to deployment, never forces details');
  await htpEntry.click(); await page.keyboard.press('ArrowLeft');
  check(await current() === deployment, 'Overview left returns to deployment');
  await htpEntry.click();
  const walkthroughEntry = page.locator('.htp-overview [data-enter-branch="supertonic-htp-steps"]');
  await walkthroughEntry.focus(); await page.keyboard.press('Space');
  for (let i = 0; i < htpSteps.length; i++) {
    check(await current() === htpSteps[i], `Walkthrough arrow path: step ${i + 1}`);
    check(await page.locator('#counter').innerText() === `${i + 1} / 11`, 'Walkthrough counter must be route-relative');
    check(await page.locator('.slide.active').getAttribute('data-reconstruction-step') === String(i + 1), 'Each slide maps to the same numbered Markdown step');
    check(await page.locator('.slide.active h1').evaluate(e => e === document.activeElement), 'Walkthrough heading receives focus');
    check(await wordCount(`#${htpSteps[i]}`) <= 180, 'Keep walkthrough slides speaker-led');
    const boundaries = await page.locator('.slide.active').evaluate(slide => {
      const blocks = [...slide.querySelectorAll('h1, .subtitle, .htp-body, .htp-takeaway, .htp-nav, .slide-footer')].map(e => e.getBoundingClientRect());
      return blocks.every((a, n) => blocks.slice(n + 1).every(b => Math.min(a.right, b.right) - Math.max(a.left, b.left) <= 1 || Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) <= 1));
    });
    check(boundaries, `${htpSteps[i]}: diagram, takeaway, controls and footer must not overlap`);
    await page.keyboard.press('ArrowRight');
  }
  check(await current() === htpOverview[0], 'Last walkthrough arrow returns to the one-pager');
  await walkthroughEntry.click(); await page.keyboard.press('ArrowLeft');
  check(await current() === htpOverview[0], 'First walkthrough left returns to the one-pager');
  for (const [i, id] of htpSteps.entries()) {
    await go(id);
    const previous = page.locator('.slide.active .htp-step-controls [data-go-slide]').first();
    if (i > 0) { await previous.click(); check(await current() === htpSteps[i - 1], 'Visible Previous follows the walkthrough'); await go(id); }
    const next = page.locator('.slide.active .htp-step-controls button').last();
    await next.click();
    check(await current() === (htpSteps[i + 1] || htpOverview[0]), 'Visible Next/Finish follows the walkthrough');
    await go(id); await page.locator('.slide.active [data-back-story]').first().click();
    check(await current() === htpOverview[0], 'Every walkthrough slide has a direct exit');
  }
  for (const id of [htpOverview[0], ...htpSteps]) {
    await go(id);
    const graphics = page.locator('.slide.active .htp-svg');
    if (await graphics.count()) check(await graphics.evaluate(svg => {
      const boxes = [...svg.querySelectorAll('text')].map(e => e.getBBox());
      const { width, height } = svg.viewBox.baseVal;
      return boxes.every(b => b.x >= -.5 && b.y >= -.5 && b.x + b.width <= width + .5 && b.y + b.height <= height + .5) &&
        boxes.every((a, i) => boxes.slice(i + 1).every(b => Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) <= 1 || Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) <= 1));
    }), `${id}: SVG labels must fit without overlap`);
  }
  await go('slide-htp-contexts');
  check(await page.locator('[data-setup-seconds]').evaluateAll(bars => {
    const expected = Number(bars[1].dataset.setupSeconds) / Number(bars[0].dataset.setupSeconds);
    return Math.abs(bars[1].getBoundingClientRect().width / bars[0].getBoundingClientRect().width - expected) < .0001;
  }), 'Startup bars must preserve the measured ratio, not a minimum decorative width');
  for (const [id, text, message] of [
    ['slide-htp-int8', 'Numerical gate failed', 'Preserve hybrid numerical failure'],
    ['slide-htp-proof', 'Numerical policy: failed', 'Preserve all-HTP numerical failure'],
    ['slide-htp-recipe', 'does not prove segmentation alone', 'Keep the multifactor causal boundary visible'],
  ]) {
    await go(id);
    check((await page.locator(`#${id}`).innerText()).includes(text), message);
  }
  check(await page.locator('#slide-htp-capacity').evaluate(e => e.textContent.includes('Both WAVs rejected.')), 'The whole-input attempt must stay rejected');
  check(await page.locator('#slide-htp-recipe').evaluate(e => e.textContent.includes('Strict source numerical gate still failed')), 'Preserve the provider source-gate failure');
  check(await page.locator('#slide-htp-reusable').evaluate(e => e.textContent.includes('New app WAV: not reviewed') && e.textContent.includes('zero new model calls')), 'App quality and publication recovery must stay distinct');
  await page.goto(`${deckURL}#${htpSteps[6]}`); await page.reload();
  check(await current() === htpSteps[6], 'Middle-of-walkthrough deep link survives reload');
  await page.keyboard.press('ArrowRight'); await page.goBack();
  check(await current() === htpSteps[6], 'Browser Back restores the nested step');
  await page.goForward();
  check(await current() === htpSteps[7], 'Browser Forward restores the nested step');
  await page.keyboard.press('m');
  check(await page.locator('#overview-routes [aria-current="step"]').getAttribute('data-go-slide') === htpSteps[7], 'Map marks the current nested step');
  await page.locator(`#overview-routes [data-go-slide="${htpSteps[10]}"]`).click();
  check(await current() === htpSteps[10], 'Map can jump to a late walkthrough step');
  await page.locator('#fullscreen').click();
  check(await page.locator('.slide.active .htp-nav').isVisible(), 'Walkthrough controls remain visible in fullscreen');
  await page.locator('.slide.active [data-back-story]').first().click();
  check(await current() === htpOverview[0], 'Fullscreen exit reaches the overview');
  await page.keyboard.press('f');
  await page.context().setOffline(true);
  try { await walkthroughEntry.click(); await page.keyboard.press('ArrowRight'); await page.locator('.slide.active [data-back-story]').first().click(); check(await current() === htpOverview[0], 'Nested walkthrough works offline'); }
  finally { await page.context().setOffline(false); }
  await page.locator('.htp-overview [data-back-story]').click();
  check(await current() === deployment, 'One-pager return reaches the original model path');

  await go('slide-2');
  check(await wordCount('#slide-2') <= 80, 'The GPU/NPU overview should remain concise');
  check(await page.locator('#slide-2 .processor-column').count() === 2, 'Compare GPU and NPU directly');
  check(await page.locator('#slide-2 svg.processor-visual').count() === 2, 'Keep the GPU work-array and NPU data-reuse graphics');
  check(await page.locator('#npu-dialog, #explore-npu-main').count() === 0, 'Inside the AI specialist popup and its trigger must remain removed');
  check(await page.locator('#slide-2 .tensor-diagram').evaluate(element => !element.closest('button, a') && getComputedStyle(element).cursor !== 'pointer'), 'The NPU illustration must be static');
  check(!(await page.locator('#slide-2').innerText()).includes('Explore the NPU'), 'Remove the obsolete interaction prompt');
  await page.locator('#slide-2 .tensor-diagram').click();
  check(await current() === 'slide-2' && await page.locator('dialog[open]').count() === 0, 'Clicking the static NPU graphic must not open a dialog or navigate');
  check(await page.locator('#slide-2 .backends, #slide-2 .qnn-strip, #slide-2 .route').count() === 0, 'Do not restore the three-card overview or Snapdragon route');
  check(!(await page.locator('#slide-2').innerText()).includes('Our Snapdragon route'), 'Snapdragon route text must remain removed');
  check((await page.locator('.comparison-takeaway').innerText()).includes('≠ automatically faster'), 'Specialization is not a speed guarantee');
  check((await page.locator('.comparison-shared').innerText()).includes('exist in both'), 'Matrix units and low precision are not NPU-exclusive');
  check(await page.locator('#slide-2 .branch-choices').count() === 0, 'GPU/NPU slide no longer needs branch choices');
  await page.keyboard.press('ArrowRight');
  check(await current() === 'slide-3', 'GPU/NPU comparison should continue directly to architecture');
  await page.keyboard.press('ArrowLeft');
  check(await current() === 'slide-2', 'Previous should return to the graphical comparison');

  await go('slide-3');
  check(await page.locator('.quadrant-example').count() === 8 && await wordCount('.matrix-slide') <= 100, 'Keep the concise quadrant examples');
  await go(config.branchPoint);
  check(await page.locator('.soc-boundary .compute-block').count() === 3, 'Keep the three chip blocks');
  check(await page.locator('.soc-boundary .memory-block').count() === 0, 'System RAM must remain outside the SoC');
  await page.locator('.hardware-slide .compute-block[data-enter-branch="hardware"]').focus();
  await page.keyboard.press('Enter');
  check(await current() === hardware[0], 'Keyboard-activating Hexagon should enter its detail');
  check((await page.locator('#route-label').innerText()).includes('Hardware'), 'Show the active detour');
  check(await page.locator('#counter').innerText() === '1 / 1', 'Counter should be scoped to the detour');
  await page.keyboard.press('ArrowLeft');
  check(await current() === config.branchPoint, 'Left from first detour slide returns to choices');

  check(await page.locator('.hardware-slide .branch-choices button').count() === 2, 'Phone offers hardware detail or continuation, not a deployment skip');
  for (const branch of ['hardware']) {
    await go(config.branchPoint);
    await page.locator(`.branch-choices [data-enter-branch="${branch}"]`).click();
    check(await current() === config.routes[branch][0], `${branch}: branch choice failed`);
    await page.locator('.slide.active [data-back-story]').click();
    check(await current() === config.branchPoint, `${branch}: Back to choices failed`);
    await page.locator(`.branch-choices [data-enter-branch="${branch}"]`).click();
    await page.keyboard.press('ArrowRight');
    check(await current() === config.resumePoint, `${branch}: Right should rejoin the story`);
    await page.keyboard.press('ArrowLeft');
    check(await current() === config.branchPoint, 'Main path should not force replaying a detour');
  }
  await page.locator('.hardware-slide .branch-choices [data-resume-story]').click();
  check(await current() === deployment, 'Skipping hardware details must still show deployment');
  check(await page.locator('#counter').innerText() === '5 / 6', 'Deployment must remain before models on the main path');
  check(!(await page.locator('.deployment-slide').innerText()).includes('Optional'), 'Deployment must not carry an optional label');
  await page.keyboard.press('ArrowRight');
  check(await current() === models, 'Right from deployment should reach models and results');
  await page.keyboard.press('ArrowLeft');
  check(await current() === deployment, 'Left from models returns to deployment');
  check(await page.locator('.deployment-slide .branch-choices button').count() === 3, 'Deployment offers the optional backend catalog, HTP reconstruction or unchanged models continuation');
  await page.locator('.deployment-slide [data-enter-branch="backends"]').click();
  check(await current() === backends[0], 'Backend catalog branch choice failed');
  check((await page.locator('#route-label').innerText()).includes('QNN backend'), 'Show the backend detour label');
  check(await page.locator('.backend-catalog-slide .qnn-backend-card').count() === 6, 'Backend catalog must show six hardware targets');
  check(await page.locator('.backend-catalog-slide .backend-tool-card').count() === 4, 'Backend catalog must show four special-purpose backends');
  const backendKeys = ['cpu', 'gpu', 'dsp', 'htp', 'hta', 'lpai', 'genai', 'saver', 'ir', 'qemu'];
  const detailTitles = [];
  for (const key of backendKeys) {
    const trigger = page.locator(`[data-backend-detail="${key}"]`);
    await trigger.click();
    check(await page.locator('#backend-dialog').isVisible(), `${key}: detail dialog did not open`);
    detailTitles.push(await page.locator('#backend-detail-title').innerText());
    check((await page.locator('#backend-detail-summary').innerText()).length > 40, `${key}: summary is too short`);
    check(await page.locator('#backend-dialog .backend-detail-panel').count() === 2, `${key}: detail view must have exactly two focus panels`);
    check(await page.locator('#backend-execution-points li').count() === 3, `${key}: execution bullets missing`);
    check(await page.locator('#backend-use-case-points li').count() === 3, `${key}: use-case bullets missing`);
    check((await page.locator('#backend-execution-detail').innerText()).length > 80, `${key}: execution explanation is too short`);
    check(await page.locator('#backend-detail-link').getAttribute('href') !== null, `${key}: wiki link missing`);
    await page.keyboard.press('ArrowRight');
    check(await current() === backends[0], `${key}: dialog must block deck navigation`);
    await page.keyboard.press('Escape');
    check(await trigger.evaluate(element => document.activeElement === element), `${key}: detail dialog should restore focus`);
  }
  check(new Set(detailTitles).size === backendKeys.length, 'Each backend card needs distinct detail content');
  await page.keyboard.press('ArrowLeft');
  check(await current() === deployment, 'Left from backend catalog returns to deployment');
  await page.locator('.deployment-slide [data-enter-branch="backends"]').click();
  await page.keyboard.press('ArrowRight');
  check(await current() === deployment, 'Right from backend catalog returns to deployment');
  await page.locator('.deployment-slide [data-enter-branch="backends"]').click();
  await page.locator('.slide.active [data-back-story]').click();
  check(await current() === deployment, 'Backend return button must return to deployment');
  await page.locator('#previous').click();
  check(await current() === config.branchPoint, 'Previous from deployment returns to the phone');

  // Direct links and refresh infer main-story vs optional context from the destination.
  await page.goto(`${deckURL}#${hardware[0]}`);
  await page.reload();
  check((await page.evaluate(() => window.presentation.state.route)) === 'hardware' && await current() === hardware[0], 'Hardware deep link and reload should retain the detour');
  await page.goto(`${deckURL}#${deployment}`);
  check((await page.evaluate(() => window.presentation.state.route)) === 'main', 'Deployment deep link must infer the main story');
  await page.reload();
  check(await current() === deployment, 'Reload should preserve deployment');
  await page.keyboard.press('ArrowLeft');
  check(await current() === config.branchPoint, 'Previous from deployment returns to the phone');
  await page.locator('.branch-choices [data-enter-branch="hardware"]').click();
  await page.goBack();
  check(await current() === config.branchPoint, 'Browser Back should restore the branch point');
  await page.goForward();
  check(await current() === hardware[0], 'Browser Forward should restore the detour');
  await page.locator('.slide.active [data-resume-story]').click();
  check(await current() === config.resumePoint, 'Explicit continuation should rejoin');

  await page.locator('#overview-button').click();
  check(await page.locator('#overview-dialog').isVisible(), 'Map button should open overview');
  check(await page.locator('#overview-routes [data-go-slide]').count() === ids.length, 'Every slide should appear in the map');
  check(await page.locator('#overview-routes [data-go-slide="slide-6"], #overview-routes [data-go-slide="slide-9"]').count() === 0, 'Removed slides must not appear in the map');
  check(await page.locator('#overview-routes [aria-current="step"]').getAttribute('data-go-slide') === config.resumePoint, 'Map must mark current location');
  await page.keyboard.press('ArrowLeft');
  check(await current() === config.resumePoint, 'Map must block deck arrow navigation');
  await page.keyboard.press('Escape');
  check(await page.locator('#overview-button').evaluate(element => document.activeElement === element), 'Map should restore focus');
  await page.keyboard.press('m');
  const deploymentEntry = page.locator(`#overview-routes [data-go-slide="${deployment}"]`);
  check(await deploymentEntry.evaluate(button => button.closest('.overview-section').querySelector('h3').textContent.startsWith('Main story')), 'Map must list deployment in the main story');
  await deploymentEntry.click();
  check(!await page.locator('#overview-dialog').isVisible() && await current() === deployment, 'Map jump should close and navigate');
  check(await page.locator('.slide.active h1').evaluate(element => document.activeElement === element), 'Destination heading should receive focus');
  check(await page.locator('.deployment-slide .workflow-lane').count() === 2, 'Preparation and execution must stay separate');
  await page.keyboard.press('n');
  check((await page.locator('.notes-body').innerText()).includes('not the only QNN workflow'), 'Offline-context caveat missing');
  await page.keyboard.press('Escape');

  await go(hardware[0]);
  await page.locator('#fullscreen').click();
  check(await page.evaluate(() => !!document.fullscreenElement), 'Fullscreen should work');
  check(!await page.locator('.controls').isVisible(), 'Controls should hide in fullscreen');
  check(await page.locator('.slide.active [data-back-story]').isVisible(), 'Detours need a visible exit in fullscreen');
  await page.locator('.slide.active [data-back-story]').click();
  await page.keyboard.press('m');
  check(await page.locator('#overview-dialog').isVisible(), 'Map shortcut should work in fullscreen');
  await page.keyboard.press('Escape');
  await page.keyboard.press('f');
  check(await page.evaluate(() => !document.fullscreenElement), 'F should exit fullscreen');

  await page.context().setOffline(true);
  try {
    await page.locator('.branch-choices [data-enter-branch="hardware"]').click();
    await page.locator('.slide.active [data-resume-story]').click();
    check(await current() === config.resumePoint, 'Branches must work offline');
    const external = await page.evaluate(() => [...document.querySelectorAll('script[src], link[rel="stylesheet"], img[src]')].filter(e => /^https?:/.test(e.getAttribute('src') || e.getAttribute('href') || '')).length);
    check(external === 0, 'No external runtime assets');
  } finally { await page.context().setOffline(false); }

  for (const removed of ['slide-6', 'slide-9']) {
    await page.goto(`${deckURL}#${removed}`);
    check(await current() === main[0], `A stale link to ${removed} should recover safely`);
  }
  await page.goto(`${deckURL}#missing-slide`);
  check(await current() === main[0], 'Invalid hash should recover to the main story');
  await page.emulateMedia({ media: 'print' });
  check(await page.locator('.slide:visible').count() === ids.length, 'Print should include main slides and detours');
  check(await page.locator('.detour-actions:visible, .branch-choices:visible').count() === 0, 'Print should omit navigation buttons');
  await page.emulateMedia({ media: 'screen', reducedMotion: 'reduce' });
  check(await page.locator('.slide:visible').count() === 1, 'Screen should show only one slide');
  check(!errors.length, `JavaScript errors: ${errors.join('; ')}`);
  if (failures.length) throw new Error(failures.join('\n'));
  await go(config.branchPoint);
  return 'PASS: 23 slides × six viewport sizes; unchanged six-slide main story; optional Supertonic HTP overview and eleven-step nested walkthrough with working controls, exact startup ratio and preserved failure/causality boundaries; existing architecture and long-input detours; benchmarks; map; notes; keyboard/focus; deep links/history/reload; fullscreen; offline; print; no overflow, overlap or JS errors.';
}
