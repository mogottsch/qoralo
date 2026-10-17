async (page) => {
  const failures=[];
  const check=(ok,text)=>{if(!ok)failures.push(text);};
  const base=page.url();
  const origin=base.match(/^https?:\/\/[^/]+/)[0];
  const dir=base.split('#')[0].replace(/index\.html$/,'');
  const getJson=async p=>await (await page.request.get(dir+p)).json();
  const external=[],errors=[];
  page.on('request',r=>{const u=r.url();if(!u.startsWith(origin)&&!u.startsWith('data:')&&!u.startsWith('blob:')&&!u.startsWith('file:'))external.push(u);});
  page.on('pageerror',e=>errors.push(e.message));
  await page.reload();
  check(await page.locator('figure').count()===3,'Three figures: demo video, processor route and the stop-score chart');
  check(await page.locator('details.more,#step-figure,.variant-controls,.scrub,.readout,.input-path,#trajectories').count()===0,'Removed the collapsible, step diagram, toggles, scrubber and NaN/zero rows');
  check(await page.locator('audio[autoplay]').count()===0,'No autoplay audio');

  // Moritz's approved opening is frozen: title, intro and question must not drift.
  const frozen={title:'Building a NotebookLM-like podcast on my phone',intro:"You've probably heard of NotebookLM. Feed it a few sources and it makes a podcast-style conversation. The output isn't as good as a real podcast, and it gives me some AI slop vibes. But it's still pretty impressive.",question:'So I wondered: how good could this be with all inference running on my phone?'};
  for(const [k,v] of Object.entries(frozen)) check((await page.locator(`[data-edit="${k}"]`).textContent())===v,`Frozen opening text changed: ${k}`);
  check(await page.locator('[data-edit="question"]').evaluate(q=>q.compareDocumentPosition(document.querySelector('#demo-figure'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#demo-figure').evaluate(d=>d.compareDocumentPosition(document.querySelector('#phone-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0,'Demo video sits between the question and the first section');
  // Demo video: it plays if the file exists; otherwise the page says where to put it. Never a silent broken player.
  await page.waitForTimeout(800);
  const demoState=await page.evaluate(()=>{const v=document.querySelector('#demo-video'),s=document.querySelector('.demo-status');return {loaded:v.readyState>=1&&!v.hidden,duration:v.duration,statusShown:!s.hidden,videoHidden:v.hidden,autoplay:v.autoplay};});
  check(demoState.loaded!==demoState.statusShown,'Demo: exactly one of player or missing-file notice is shown: '+JSON.stringify(demoState));
  check(!demoState.autoplay,'Demo video does not autoplay');
  if(demoState.loaded)check(demoState.duration>0&&demoState.duration<180,'Demo video is a short clip: '+demoState.duration);
  // Closing line.
  check((await page.locator('[data-edit="closing"]').textContent())==='If you wanna take a look,'&&await page.locator('.closing a').textContent()==='here it is'&&(await page.locator('.closing a').getAttribute('href'))==='https://github.com/mogottsch/vibevoice-android-spike','Closing: "If you wanna take a look, here it is" linking the repository');
  check(await page.locator('.closing').evaluate(c=>c===document.querySelector('article').lastElementChild),'Closing is the last thing in the article');
  check(!/What.s left|one voice instead|final demo/i.test(await page.locator('main').innerText()),'No "what is left" section');

  // 'What we tried': the table must equal the evidence packet, in both directions.
  const mainText=await page.locator('main').innerText();
  const tbl=await getJson('evidence/benchmark-table.json');
  const byId=Object.fromEntries(tbl.rows.map(r=>[r.id,r]));
  const shown=await page.locator('.bench tbody tr').evaluateAll(trs=>trs.map(tr=>({model:tr.querySelector('th').textContent,cells:[...tr.querySelectorAll('td')].map(td=>({text:td.textContent.trim(),rtf:td.dataset.rtf===undefined?null:Number(td.dataset.rtf),cls:td.className}))})));
  check(shown.length===5&&shown.map(r=>r.model).join('|')==='Supertonic 3|Pocket TTS|Kokoro|MOSS-TTS-Nano|VibeVoice 1.5B','Table has the five models in order: '+shown.map(r=>r.model));
  const expect={'Supertonic 3':['supertonic-short-cpu','supertonic-short-htp'],'Pocket TTS':['pocket-short-cpu','pocket-short-htp'],'Kokoro':['kokoro-fixed-cpu',null],'MOSS-TTS-Nano':['moss-short-cpu',null]};
  for(const r of shown){
    const ids=expect[r.model]; if(!ids)continue;
    ids.forEach((id,i)=>{const c=r.cells[i];
      if(id){const j=byId[id].speed.rtf; check(c.rtf!==null&&Math.abs(c.rtf-j)<1e-9&&c.text===j.toFixed(2),`${r.model} ${i?'NPU':'CPU'} equals the packet (${id}): ${c.text}`); check(/warm$/.test(byId[id].speed.display),`${id} is a warm median`);}
      else check(c.rtf===null&&/blocked/.test(c.text),`${r.model} NPU is shown as a word, never a number: ${c.text}`);});
  }
  const vv=shown[4]; check(vv.cells[0].rtf===null&&vv.cells[1].rtf===null&&/no speech/.test(vv.cells[0].text),'VibeVoice shows no speed, only words');
  check(byId['moss-htp-blocked'].speed.rtf===null&&byId['vibevoice-incomplete'].speed.rtf===null,'Packet agrees: blocked and incomplete rows have no RTF');
  const ratio=(a,b)=>byId[a].speed.rtf/byId[b].speed.rtf;
  check(ratio('supertonic-short-cpu','supertonic-short-htp')>2&&ratio('pocket-short-cpu','pocket-short-htp')>2,'"More than twice as fast" holds within the two rows that ran on the NPU');
  const llm=tbl.llm_side_separate_from_tts.lines[0];
  check(/12\.3\u201316\.3/.test(llm)&&/Separate text benchmarks measured Gemma 4 E2B at 12\u201316 tokens per second on the GPU; the app uses it to write the scripts/.test(mainText),'Gemma line matches the packet (12.3-16.3 shown as 12-16) and does not claim app throughput');
  check(!/RTF.{0,40}(Gemma|tokens)/.test(mainText.replace(/\n/g,' '))&&!/tokens.{0,60}RTF/.test(mainText.replace(/\n/g,' ')),'LLM rate and TTS RTF are not mixed');
  check(/generation time divided by audio length/.test(mainText)&&/below 1 is faster than playback/.test(mainText)&&/warm medians with setup excluded/.test(mainText)&&/Workloads differ between models, so compare across a row, not down a column/.test(mainText)&&/rewritten graphs/.test(mainText)&&/checked by ear/.test(mainText)&&/table samples differ from the Pocket clips below/.test(mainText),'RTF note states the definition, the limits and that the Pocket samples differ');
  check(/In these warm short-input tests, the prepared HTP versions were over twice as fast/.test(mainText)&&!/NPU is (about )?(2|two)/.test(mainText),'Speed claim is qualified to these tests');
  check(!/bug hunt|after the bug/.test(mainText),'Table does not borrow the Pocket bug story');
  check(shown[3].cells[2].text==='The HTP runtime failed to initialize on the phone'&&/Both tested samples sounded good/.test(shown[1].cells[2].text),'MOSS and Pocket notes use the reviewed wording');
  check(await page.locator('.note-box').evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=12&&parseFloat(getComputedStyle(n).fontSize)<=14),'RTF note box is small');
  check(await page.locator('[data-edit="tried-copy"]').evaluate(g=>g.compareDocumentPosition(document.querySelector('.bench'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#demo-figure').evaluate(d=>d.compareDocumentPosition(document.querySelector('#tried-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#tried-heading').evaluate(h=>h.compareDocumentPosition(document.querySelector('#phone-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0,'Order: demo, what we tried (text, table), then the phone section');

  // Gist first, plain, and free of numbers nobody needs.
  const body=await page.locator('main').innerText();
  check(/swaps in its learned start vector/.test(body)&&/freed that buffer too early/.test(body)&&/never found the end/.test(body)&&/the voice went wrong too/i.test(body),'Gist states the cause, the missing stop and the changed voice');
  check(await page.locator('[data-edit="why-gist"]').evaluate(g=>g.compareDocumentPosition(document.querySelector('#why-figure'))&Node.DOCUMENT_POSITION_FOLLOWING)>0,'Gist comes before the chart');
  check(!/\b134\b|frame cap|\u22124|0\.00\d|256|compounds|inferred|instrumented|IsNaN|bos_emb/.test(body),'No meaningless numbers or bloat in the main text');
  check(!/10\.72 seconds instead of 4\.48 \u00b7|frames? \u00d7 80/.test(body),'No frame arithmetic in the main text');

  // Chart data comes from the phone raw results and keeps its meaning.
  const orig=(await getJson('evidence/phone-bos-check/raw/runner_orig-1.json')).eos_logits;
  const kept=(await getJson('evidence/phone-bos-check/raw/runner_fixed-1.json')).eos_logits.slice(0,56);
  const pts=await page.evaluate(()=>['orig','kept'].map(n=>document.querySelector('.series.'+n).getAttribute('points').split(' ').map(p=>p.split(',').map(Number))));
  check(pts[0].length===134&&pts[1].length===56,'Series lengths '+pts.map(a=>a.length));
  check(pts[0].every(([x,y],i)=>x===i+1&&Math.abs((9-y)-orig[i])<6e-4)&&pts[1].every(([x,y],i)=>x===i+1&&Math.abs((9-y)-kept[i])<6e-4),'Drawn points equal the phone raw stop scores');
  check(Math.max(...orig)<-4&&Math.max(...kept)>-4&&kept.findIndex(v=>v>-4)===53,'Original never reaches the stop line; buffer-kept-alive does');
  const ticks=await page.locator('.tick.x').allInnerTexts();
  check(ticks.join('|')==='0 s|4.5 s|10.7 s','Axis ticks are seconds: '+ticks.join('|'));
  check(Math.round(56*0.08*10)/10===4.5&&Math.round(134*0.08*10)/10===10.7,'Tick seconds match frame counts');
  const label=await page.locator('.chart').getAttribute('aria-label');
  check(/10\.7 seconds/.test(label)&&/4\.5 seconds/.test(label),'Chart text alternative names the two durations');

  for(const [width,height] of [[1440,1000],[1280,800],[768,1024],[390,844],[320,740]]) {
    await page.setViewportSize({width,height});
    const layout=await page.evaluate(()=>{
      const box=e=>e.getBoundingClientRect();
      const overlaps=(a,b)=>!(a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top);
      const chart=box(document.querySelector('.chart'));
      const xt=[...document.querySelectorAll('.tick.x')].map(box);
      const notes=['.threshold-note','.stop-note','.never-note'].map(s=>box(document.querySelector(s)));
      const thr=box(document.querySelector('.threshold')), orig=box(document.querySelector('.series.orig')), never=box(document.querySelector('.never-note'));
      return {
        overflow:document.documentElement.scrollWidth>innerWidth,
        bad:[...document.querySelectorAll('h1,h2,h3,p,figure,.model,.model-path,.chart,.legend,.phone,.editor,pre,.axis-name,.note,.demo video,.demo-status,.closing,.bench,.note-box,.table-wrap')].filter(e=>{const r=box(e);return r.width&&(r.left<-1||r.right>innerWidth+1);}).map(e=>e.id||e.className||e.tagName),
        preOverflow:[...document.querySelectorAll('pre')].some(p=>p.scrollWidth>p.clientWidth+1),
        modelOverlap:[...document.querySelectorAll('.model')].some(e=>{const[a,b]=[...e.children].map(x=>x.getBoundingClientRect());return a.right>b.left+.5;}),
        tickOverlap:xt.some((a,i)=>xt.some((b,j)=>j>i&&overlaps(a,b)))||xt.some(a=>[...document.querySelectorAll('.axis-name')].some(n=>overlaps(a,box(n))))||xt.some(a=>a.height>20),
        noteOverlap:notes.some((a,i)=>notes.some((b,j)=>j>i&&overlaps(a,b))),
        notesInChart:notes.every(n=>n.left>=chart.left-1&&n.right<=chart.right+2),
        neverBetween:never.top>=thr.top-1&&never.bottom<=orig.top+2,
        axisInside:[...document.querySelectorAll('.axis-name')].every(n=>{const r=box(n);return r.left>=-1&&r.right<=innerWidth+1;}),
        chartW:chart.width, chartH:chart.height,
        legendVisible:box(document.querySelector('.legend')).height>0,
        tableFits:(()=>{const w=document.querySelector('.table-wrap');return w.scrollWidth<=w.clientWidth+1;})(),
        tableCellsClipped:[...document.querySelectorAll('.bench td,.bench th')].some(e=>{const r=box(e);return r.width>0&&(r.right>innerWidth+1||r.left<-1);})
      };
    });
    check(!layout.overflow&&!layout.bad.length,`${width} overflow: ${layout.bad}`);
    check(!layout.preOverflow||width<=390,`${width} code excerpt overflows (horizontal scroll is acceptable only on phones)`);
    check(!layout.modelOverlap,`${width} model label overlap`);
    check(!layout.tickOverlap&&!layout.noteOverlap,`${width} tick/annotation overlap`);
    check(layout.notesInChart,`${width} annotation leaves the chart`);
    check(layout.neverBetween,`${width} "never reaches" label is not between the stop line and the original line`);
    check(layout.tableFits&&!layout.tableCellsClipped,`${width} benchmark table fits without sideways scrolling or clipped cells`);
    check(layout.axisInside&&layout.legendVisible&&layout.chartW>200&&layout.chartH>200,`${width} axis names/legend/chart size`);
    await page.locator('#records > summary').focus();await page.keyboard.press('Enter');
    check(await page.locator('.records-body').isVisible(),`${width} keyboard sources`);
    await page.keyboard.press('Enter');
  }

  // Receipts must match what the notes state, in both directions.
  const notes=await page.locator('#records').evaluate(e=>e.textContent);
  const phone=await getJson('evidence/phone-bos-check/results.json');
  const ob=phone.observations;
  check(ob.original_lifetime_bos_all_zero_runs===2&&ob.fixed_lifetime_bos_all_nan_runs===2,'Receipt: dump builds show zeros 2/2 and NaN 2/2');
  check(ob.unmodified_original_run1_wav_identical_to_retained_failure===true&&ob.unmodified_original_run2_wav_identical_to_retained_failure===false&&ob.unmodified_original_runs_differ,'Receipt: orig run 1 byte-identical, run 2 different');
  check(phone.runs.filter(r=>/fixed/.test(r.run)).length===4&&ob.fixed_runs_all_stop_at_53&&ob.fixed_runs_identical_wav,'Receipt: four fixed runs stop at 53 with identical audio');
  check(phone.runs.length===8&&phone.runs.every(r=>r.exit===0),'Receipt: eight planned runs, all exited 0');
  check(/prints the 32 start values/.test(notes)&&/all zero, 2 of 2 runs/.test(notes)&&/all NaN, 2 of 2/.test(notes)&&/four kept-alive runs/.test(notes),'Notes state the observation with its counts');
  check(/not retained/.test(notes)&&/may change allocation/.test(notes)&&/not deterministic/.test(notes)&&/no explanation for why this allocator/i.test(notes)&&/same-size reconstruction/.test(notes),'Limits stay in the notes');
  check(/62 inputs/.test(notes)&&!/65 /.test(body+notes),'Pattern-scan count is exact');
  check(/I made no new listening judgment/.test(notes),'No listening claim');
  check(!/the allocator (zeroes|zeros|clears)/i.test(body+notes),'No invented allocator explanation');
  const replay=await getJson('evidence/bos-zero-replay.json'), dr=replay.frame_drift;
  check([dr.hidden_state_c.frame0,dr.hidden_state_c.median,dr.latent_frame.frame0,dr.latent_frame.median].every(v=>notes.includes(v.toFixed(2))),'Notes quote the replay drift numbers');
  check(Math.abs(replay.step0_logit.all_zeros-orig[0])<2e-3&&replay.full_trajectory.all_zero_bos_vs_android_original.max_abs<0.08,'Replay agrees with the phone run the chart shows');

  await page.locator('#route-controls [data-route="script"]').click();
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('#route-controls [data-route="speech"]').click();
  check(await page.locator('.speech .packet').first().evaluate(e=>getComputedStyle(e).animationName)==='none','Reduced motion');
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
    check(await page.locator('[data-edit]').count()>=15,'Prose and headings are editable');
    await page.locator('[data-edit="intro"]').fill('My own intro <b>stays plain text</b>.');
    await page.locator('#edit-copy').click();
    await page.reload();
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Local edit restore');
    check(await page.locator('[data-edit="intro"] b').count()===0,'Edits must not inject HTML');
    check((await page.locator('[data-edit="why-cause"] code').count())===2,'Untouched paragraphs keep inline code');
    const download=page.waitForEvent('download');await page.locator('#save-copy').click();
    await(await download).saveAs('/tmp/qoralo-story-v3/phone-podcast-edited.html');
    await page.goto('file:///tmp/qoralo-story-v3/phone-podcast-edited.html');
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Export contains edits');
    check(await page.locator('[contenteditable]').count()===0,'Export strips live edit state');
    check(await page.locator('#edit-copy').isVisible(),'Export keeps working script');
    check(await page.locator('body').evaluate(e=>getComputedStyle(e).color)==='rgb(243, 245, 248)','Export keeps linked styles via base');
    check(await page.locator('.series').count()===2&&await page.locator('.chart').isVisible(),'Export keeps the chart');
    await page.goto(base);
  } finally {
    if(page.url()!==base)await page.goto(base);
    await page.evaluate(({key,previous})=>{if(previous===null)localStorage.removeItem(key);else localStorage.setItem(key,previous);},{key,previous});
    await page.reload();
  }

  await page.emulateMedia({media:'print'});
  check(await page.locator('.chart').isVisible()&&!(await page.locator('.editor').isVisible()),'Print keeps chart and hides editor');
  await page.emulateMedia({media:'screen'});
  await page.route('**/article.js',route=>route.abort());await page.reload();
  check(await page.locator('.chart').isVisible()&&await page.locator('.series').count()===2,'Static chart remains without script');
  check(!(await page.locator('.editor').isVisible()),'Unavailable controls hidden');
  await page.locator('#records > summary').click();check(await page.locator('.records-body').isVisible(),'Native sources without script');
  await page.unroute('**/article.js');await page.reload();
  await page.setViewportSize({width:1440,height:1000});
  check(!external.length,'External runtime requests: '+external.join(','));
  check(!errors.length,'Page errors: '+errors.join(' | '));
  if(failures.length)throw new Error(failures.join('\n'));
  return 'PASS: gist first and free of meaningless numbers; chart equals the phone raw stop scores with a seconds axis; five widths of chart/tick/annotation geometry; receipts match the notes in both directions; reduced motion; exact WAV order, decoding and exclusive play; inline editing, restore and exported copy with the chart; print; script-failure fallback; no external requests or page errors.';
}
