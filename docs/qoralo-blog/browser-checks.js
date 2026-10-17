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
  check(await page.locator('[data-edit="question"]').evaluate(q=>q.compareDocumentPosition(document.querySelector('#demo-figure'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#demo-figure').evaluate(d=>d.compareDocumentPosition(document.querySelector('#tried-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0,'Demo video sits between the question and the first section');
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
  check(await page.locator('#fix-heading,pre,.takeaway,[data-edit="fix-copy"],[data-edit="lesson"],[data-edit="why-cause"]').count()===0&&!/The fix we applied|freed before|undefined behavior|bos is freed|One different input/.test(await page.locator('main').innerText()),'No code excerpt, cause paragraph, fix section or takeaway');
  check(await page.locator('#why-figure').evaluate(f=>f.closest('section').nextElementSibling===null||f.closest('section').nextElementSibling.classList.contains('closing')),'Why it went wrong is the last section before the closing line');

  // 'Where it ends up': the system diagram says only what the app really does.
  const sys=await page.evaluate(()=>{
    const f=document.querySelector('#system-figure');
    const node=id=>f.querySelector('#'+id);
    const info=id=>{const n=node(id);return {title:n.querySelector('.qflow-title').textContent.trim(),tag:n.querySelector('.qflow-tag').textContent.trim(),detail:n.querySelector('.qflow-detail').textContent.trim(),cls:n.className};};
    const ids=[...f.querySelectorAll('.qflow-node')].map(n=>n.id);
    const visible=[...f.querySelectorAll('.qflow-node,.qflow-grid ~ *,h3,.qflow-bridge-label,.qflow-mobile-transfer,figcaption')].filter(e=>!e.classList.contains('sr-only')).map(e=>e.textContent).join(' ');
    return {ids,nodes:Object.fromEntries(ids.map(i=>[i,info(i)])),lanes:[...f.querySelectorAll('h3')].map(h=>h.textContent.trim()),caption:f.querySelector('figcaption').textContent.trim(),alt:f.querySelector('#qflow-alt')?.textContent||'',described:f.getAttribute('aria-describedby'),visible,order:(()=>{const pos=id=>f.querySelector('#'+id);const a=['qflow-h1','qflow-h2','qflow-p1','qflow-p2','qflow-p3','qflow-p4','qflow-p5','qflow-p6','qflow-p7','qflow-p8'].map(pos);return a.every((e,i)=>i===0||(a[i-1].compareDocumentPosition(e)&Node.DOCUMENT_POSITION_FOLLOWING)>0);})()};
  });
  check(sys.ids.length===10&&sys.order,'System diagram has ten nodes in flow order: '+sys.ids.join(','));
  check(Object.values(sys.nodes).every(n=>n.title.split(/\s+/).length<=4),'Node titles are four words or fewer');
  const tg=Object.fromEntries(Object.entries(sys.nodes).map(([k,v])=>[k,v.tag]));
  check(tg['qflow-p2']==='GPU'&&tg['qflow-p5']==='NPU (HTP)'&&tg['qflow-p6']==='NPU (HTP)'&&tg['qflow-p3']==='CPU \u00b7 app UI'&&['qflow-h1','qflow-h2','qflow-p1','qflow-p4','qflow-p7','qflow-p8'].every(k=>tg[k]==='CPU'),'Processor tags: one GPU step, two NPU steps, the rest CPU, review is app UI: '+JSON.stringify(tg));
  check(/Your review \u00b7 optional/.test(sys.nodes['qflow-p3'].detail)&&/optional/.test(sys.nodes['qflow-p3'].cls+' qflow-optional'),'Review is shown as a human, optional step');
  check(sys.lanes.join('|')==='Speech preparation \u00b7 computer|Episode generation \u00b7 phone','Computer preparation and phone generation are separate lanes: '+sys.lanes);
  check(sys.caption==='Speech models are prepared on a computer; episodes are generated on the phone. GPU and NPU labels mark the model routes, with CPU preparation and app code around them.','Caption is the reviewed two sentences');
  check(!/PDF|URL|web|transcri|retriev|conversation|two voices|\b300\b|native|four|1\.5|FP16|INT8/i.test(sys.visible),'Diagram has no invented ingestion, no meaningless numbers and no jargon: '+(sys.visible.match(/PDF|URL|web|transcri|retriev|conversation|two voices|\b300\b|native|four/i)||[''])[0]);
  check(/Paste, TXT, Markdown, JSON/.test(sys.visible)&&/Gemma 4 E2B/.test(sys.visible)&&/Whole sentences/.test(sys.visible),'Diagram shows the real inputs, the real script model and whole-sentence grouping');
  check(/qflow-caption/.test(sys.described)&&/qflow-alt/.test(sys.described)&&/computer/.test(sys.alt)&&/phone/.test(sys.alt)&&/GPU/.test(sys.alt)&&/NPU/.test(sys.alt)||/HTP/.test(sys.alt),'Diagram has a screen-reader description');
  check(await page.locator('#system-figure details').count()===0,'No visible collapsible in the diagram');
  check(await page.locator('#system-figure script,#system-figure img,#system-figure link').count()===0,'Diagram has no scripts or external assets');

  // 'What I tried': the tables must equal the evidence packet, in both directions.
  const mainText=await page.locator('main').innerText();
  const tbl=await getJson('evidence/benchmark-table.json');
  const byId=Object.fromEntries(tbl.rows.map(r=>[r.id,r]));
  const shown=await page.locator('.bench:not(.llm) tbody tr').evaluateAll(trs=>trs.map(tr=>({model:tr.querySelector('th').textContent,cells:[...tr.querySelectorAll('td')].map(td=>({text:td.textContent.trim(),rtf:td.dataset.rtf===undefined?null:Number(td.dataset.rtf),cls:td.className}))})));
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
  const notes0=await page.locator('#records').evaluate(e=>e.textContent);
  const lt=await getJson('evidence/llm-table.json');
  const lrows=await page.locator('.bench.llm tbody tr').evaluateAll(trs=>trs.map(tr=>({model:tr.querySelector('th').textContent,cells:[...tr.querySelectorAll('td')].map(td=>({text:td.textContent.trim(),prefill:td.dataset.prefill===undefined?null:Number(td.dataset.prefill),decode:td.dataset.decode===undefined?null:Number(td.dataset.decode),cls:td.className}))})));
  const pkey=r=>r.model.split(' (')[0].replace(' IT','')+'/'+(r.backend==='NPU(HTP)'?'NPU':r.backend);
  const packet=Object.fromEntries(lt.rows.map(r=>[pkey(r),r]));
  check(lrows.length===7&&new Set(lrows.map(r=>r.model+'/'+r.cells[0].text)).size===7&&lrows.every(r=>packet[r.model+'/'+r.cells[0].text]),'LLM table has the seven packet routes, each once: '+lrows.map(r=>r.model+'/'+r.cells[0].text));
  lrows.forEach(r=>{const k=r.model+'/'+r.cells[0].text,pk=packet[k],pf=r.cells[1],dc=r.cells[2];
    check(pf.prefill!==null&&Math.abs(pf.prefill-pk.reads)<1e-9&&pf.text===pk.reads.toFixed(0),`LLM ${k} prefill equals the packet: ${pf.text}`);
    if(pk.writes===null)check(dc.decode===null&&/not comparable/.test(dc.text)&&!/\d/.test(dc.text),`LLM ${k} decode is words, never a number: ${dc.text}`);
    else check(dc.decode!==null&&Math.abs(dc.decode-pk.writes)<1e-9&&dc.text===pk.writes.toFixed(1),`LLM ${k} decode equals the packet: ${dc.text}`);});
  const lheads=await page.locator('.bench.llm thead th').allInnerTexts();
  check(lheads.join('|')==='Model|Backend|Prefill, tokens/s|Decode, tokens/s|Note','LLM column headers say prefill and decode: '+lheads.join('|'));
  check(await page.locator('.bench.llm td[data-prefill]').evaluateAll(t=>t.every(x=>x.dataset.label==='Prefill'))&&await page.locator('.bench.llm td[data-decode]').evaluateAll(t=>t.every(x=>x.dataset.label==='Decode')),'Mobile labels say Prefill and Decode');
  check(!/\b(reads|writes)\b/i.test(await page.locator('[aria-labelledby=tried-heading]').innerText()),'The page says prefill and decode, not reads and writes');
  // Sorting rule: models grouped (contiguous), the app model first, the others by name; inside a model fastest decode first, no-rate last.
  const order=lrows.map(r=>r.model), uniq=[...new Set(order)];
  check(uniq.length===3&&uniq[0]==='Gemma 4 E2B'&&uniq.slice(1).join('|')==='LFM2.5-2.6B|Qwen3.5-2B'&&order.every((m,i)=>i===0||m===order[i-1]||!order.slice(0,i).includes(m)),'LLM models are grouped, the app model first, then by name: '+uniq);
  const inside=uniq.every(m=>{const d=lrows.filter(r=>r.model===m).map(r=>r.cells[2].decode);const nn=d.filter(v=>v!==null);return d.slice(nn.length).every(v=>v===null)&&nn.every((v,i)=>i===0||nn[i-1]>=v);});
  check(inside,'Inside each model: fastest decode first, a route without a decode rate last: '+lrows.map(r=>r.model+'/'+r.cells[0].text+':'+r.cells[2].text).join(' | '));
  check(lt.rows.find(r=>pkey(r)==='Gemma 4 E2B/NPU').writes===null&&/mobile QAT/i.test(lt.rows.find(r=>pkey(r)==='Gemma 4 E2B/NPU').model)&&lt.htp_registry_audit[0].registry_attempt_status==='ran'&&/repetition collapse/.test(lt.htp_registry_audit[0].recorded_outcome),'Packet agrees: the NPU row is a different (mobile QAT) build that ran, has no normalized decode rate, and failed with repetition');
  const npuRow=lrows.find(r=>r.cells[0].text==='NPU'), gpuApp=lrows.find(r=>r.model==='Gemma 4 E2B'&&r.cells[0].text==='GPU');
  check(npuRow.cells[3].text==='Different build. Repeated itself on long prompts'&&gpuApp.cells[3].text==='What the app uses','NPU row shows its different build and its repetition failure; the app row says what the app uses');
  check(/I also tried it on the NPU, where it ran but repeated itself on long prompts/.test(mainText)&&/The app uses Gemma 4 E2B on the GPU/.test(mainText),'Script-writing intro states the app route and the NPU outcome');
  check(!/\b\d+(\.\d+)?\s*(\u00d7|x|times)\b|faster than on the CPU|fastest|winner/i.test(await page.locator('[aria-labelledby=tried-heading]').innerText()),'No ratio headline, winner or ranking in the section');
  check(/Prefill is how fast the model takes in the prompt, decode is how fast it produces text\. Both in tokens per second, higher is faster; a token is a piece of text, not a word\./.test(mainText),'LLM note explains prefill, decode and tokens in one line');
  check(!/Generic long-text tests|Medians of five requests|compare backends within a model, since tokenizers differ/.test(mainText),'The LLM footnote is gone from the page body');
  check(/generic long-text tests, not the app's script pipeline and not script quality/.test(notes0)&&/the median of five loaded long-prompt requests|Each row is the median of five loaded long-prompt requests/.test(notes0)&&/sorted by decode speed inside each model/.test(notes0),'The LLM caveats live in the technical notes');
  check(await page.locator('.bench:not(.llm)').evaluate(t=>t.compareDocumentPosition(document.querySelector('.bench.llm'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('[data-edit="llm-title"]').evaluate(h=>h.compareDocumentPosition(document.querySelector('.bench.llm'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('.note-box').first().evaluate(f=>f.compareDocumentPosition(document.querySelector('[data-edit="llm-title"]'))&Node.DOCUMENT_POSITION_FOLLOWING)>0,'Speech and script-writing tables are separate: speech first, then the script-writing subsection');
  check(!/RTF/.test(await page.evaluate(()=>[document.querySelector('.bench.llm').closest('.table-wrap'),...document.querySelectorAll('[data-edit="llm-copy"],[data-edit="llm-note"],[data-edit="llm-foot"],[data-edit="llm-title"]')].map(e=>e.textContent).join(' '))),'The script-writing section never mentions RTF');
  check(!/RTF.{0,40}(Gemma|tokens)/.test(mainText.replace(/\n/g,' '))&&!/tokens.{0,60}RTF/.test(mainText.replace(/\n/g,' ')),'LLM rate and TTS RTF are not mixed');
  const heads=await page.locator('.bench:not(.llm) thead th').allInnerTexts();
  check(heads.join('|')==='Model|CPU RTF|NPU RTF|What happened','Column headers say RTF: '+heads.join('|'));
  check(await page.locator('.bench:not(.llm) td[data-rtf]').evaluateAll(tds=>tds.every(td=>/RTF$/.test(td.dataset.label))),'Mobile labels say RTF too');
  const fm=await page.evaluate(()=>{const f=document.querySelector('.formula'),m=f.querySelector('math'),t=[...m.querySelectorAll('mtext')].map(e=>e.getBoundingClientRect()),r=m.getBoundingClientRect();return {w:r.width,h:r.height,numeratorAbove:t.length===2&&t[0].bottom<=t[1].top+1,sameCentre:t.length===2&&Math.abs((t[0].left+t[0].right)/2-(t[1].left+t[1].right)/2)<6,label:f.getAttribute('aria-label'),mathHidden:m.getAttribute('aria-hidden'),isMath:m.namespaceURI,txt:m.textContent.replace(/\s+/g,' ').trim(),noteLen:document.querySelector('.note-box').textContent.replace(/\s+/g,' ').trim().length,color:getComputedStyle(f).color};});
  check(fm.isMath==='http://www.w3.org/1998/Math/MathML'&&fm.w>60&&fm.h>24&&fm.numeratorAbove&&fm.sameCentre,'RTF formula renders as a fraction: '+JSON.stringify(fm));
  check(/RTF equals generation time divided by audio length/.test(fm.label)&&fm.mathHidden==='true'&&/RTF\s*=\s*generation time\s*audio length/.test(fm.txt),'Formula has one accessible name and reads RTF = generation time over audio length: '+fm.txt);
  check(fm.noteLen<140,'RTF note box is short: '+fm.noteLen+' characters');
  check(/Below 1 is faster than playback: at 0\.5, ten seconds of speech takes five\./.test(mainText),'One-line RTF example');
  check(!/Warm medians without setup|compare across a row|rewritten graphs, checked by ear|Pocket's samples differ/.test(mainText),'The speech footnote is gone from the page body');
  check(/Speech table: warm medians of five runs after setup/.test(notes0)&&/rewritten graphs/.test(notes0)&&/not the clips in the next section/.test(notes0)&&/sorted by how far each model got/.test(notes0),'The speech caveats live in the technical notes');
  const tier=r=>r.cells[1].rtf!==null?0:(r.cells[0].rtf!==null?1:2);
  const rowKey=r=>[tier(r),tier(r)===0?r.cells[1].rtf:tier(r)===1?r.cells[0].rtf:0];
  check(shown.every((r,i)=>i===0||(rowKey(shown[i-1])[0]<rowKey(r)[0]||(rowKey(shown[i-1])[0]===rowKey(r)[0]&&rowKey(shown[i-1])[1]<=rowKey(r)[1]))),'Speech rows sort by how far the model got (NPU, CPU only, no speech), then by speed inside the group: '+shown.map(r=>r.model+':'+tier(r)+':'+rowKey(r)[1].toFixed(2)).join(' | '));
  check(!/generation time divided by audio length/.test(mainText),'No long prose definition of RTF');
  check(/In these warm short-input tests, the prepared HTP versions were over twice as fast/.test(mainText)&&!/NPU is (about )?(2|two)/.test(mainText),'Speed claim is qualified to these tests');
  check(!/bug hunt|after the bug/.test(mainText),'Table does not borrow the Pocket bug story');
  check(shown[3].cells[2].text==='The HTP runtime failed to initialize on the phone'&&/Both tested samples sounded good/.test(shown[1].cells[2].text),'MOSS and Pocket notes use the reviewed wording');
  check(await page.locator('.note-box').first().evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=12&&parseFloat(getComputedStyle(n).fontSize)<=14),'RTF note box is small');
  check(await page.locator('[data-edit="tried-copy"]').evaluate(g=>g.compareDocumentPosition(document.querySelector('.bench'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#demo-figure').evaluate(d=>d.compareDocumentPosition(document.querySelector('#tried-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#tried-heading').evaluate(h=>h.compareDocumentPosition(document.querySelector('#system-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#system-heading').evaluate(h=>h.compareDocumentPosition(document.querySelector('#pocket-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0&&await page.locator('#pocket-heading').evaluate(h=>h.compareDocumentPosition(document.querySelector('#why-heading'))&Node.DOCUMENT_POSITION_FOLLOWING)>0,'Order: demo, what we tried, where it ends up, the Pocket clips, why it went wrong');

  check(await page.locator('#tried-heading').textContent()==='What I tried'&&/I tried five speech models on my phone/.test(mainText)&&/For the script I need a language model/.test(mainText),'The tried section is written from Moritz\'s perspective');
  check(!/\b(we|our|ours|us)\b/i.test(mainText),'No "we" or "our" anywhere in the article text: '+(mainText.match(/.{20}\b(we|our|us)\b.{20}/i)||[''])[0]);
  check(/My phone code freed that buffer too early/.test(mainText)&&/until I cut it off/.test(mainText)&&/The second is my first port/.test(mainText),'The Pocket story is also first person');

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
        bad:[...document.querySelectorAll('h1,h2,h3,p,figure,.qflow-node,.qflow-bridge,.chart,.legend,.editor,.axis-name,.note,.demo video,.demo-status,.closing,.bench,.note-box,.table-wrap')].filter(e=>{const r=box(e);return r.width&&(r.left<-1||r.right>innerWidth+1);}).map(e=>e.id||e.className||e.tagName),
        flow:(()=>{
          const nodes=[...document.querySelectorAll('#system-figure .qflow-node')], r=nodes.map(box);
          const lane=n=>n.closest('.qflow-host')?'host':'phone';
          const overlap=r.some((a,i)=>r.some((b,j)=>j>i&&overlaps(a,b)));
          const clipped=nodes.some(n=>[...n.querySelectorAll('.qflow-title,.qflow-tag,.qflow-detail')].some(e=>e.scrollWidth>e.clientWidth+1||e.getBoundingClientRect().right>n.getBoundingClientRect().right+0.5||e.getBoundingClientRect().left<n.getBoundingClientRect().left-0.5));
          const small=[...document.querySelectorAll('#system-figure *')].filter(e=>e.children.length===0&&e.textContent.trim()&&!e.closest('.sr-only')&&getComputedStyle(e).display!=='none').some(e=>parseFloat(getComputedStyle(e).fontSize)<11.99);
          const hostBottom=Math.max(...nodes.filter(n=>lane(n)==='host').map(n=>box(n).bottom)), phoneTop=Math.min(...nodes.filter(n=>lane(n)==='phone').map(n=>box(n).top));
          const horizontal=innerWidth>=1000;
          let bridgeOk=true;
          if(horizontal){const svg=box(document.querySelector('.qflow-bridge > svg')),p5=box(document.querySelector('#qflow-p5')),p6=box(document.querySelector('#qflow-p6'));const x1=svg.left+svg.width*450/800,x2=svg.left+svg.width*550/800;bridgeOk=x1>p5.left&&x1<p5.right&&x2>p6.left&&x2<p6.right;}
          else {bridgeOk=getComputedStyle(document.querySelector('.qflow-mobile-transfer')).display!=='none'&&/Predict \+ encode/.test(document.querySelector('.qflow-mobile-transfer').textContent);}
          const rows=new Set(nodes.filter(n=>lane(n)==='phone').map(n=>Math.round(box(n).top)));
          return {overlap,clipped,small,lanesOrdered:hostBottom<phoneTop,bridgeOk,rows:rows.size,minNodeW:Math.min(...r.map(x=>x.width)),horizontal};
        })(),
        tickOverlap:xt.some((a,i)=>xt.some((b,j)=>j>i&&overlaps(a,b)))||xt.some(a=>[...document.querySelectorAll('.axis-name')].some(n=>overlaps(a,box(n))))||xt.some(a=>a.height>20),
        noteOverlap:notes.some((a,i)=>notes.some((b,j)=>j>i&&overlaps(a,b))),
        notesInChart:notes.every(n=>n.left>=chart.left-1&&n.right<=chart.right+2),
        neverBetween:never.top>=thr.top-1&&never.bottom<=orig.top+2,
        axisInside:[...document.querySelectorAll('.axis-name')].every(n=>{const r=box(n);return r.left>=-1&&r.right<=innerWidth+1;}),
        chartW:chart.width, chartH:chart.height,
        legendVisible:box(document.querySelector('.legend')).height>0,
        tableFits:[...document.querySelectorAll('.table-wrap')].every(w=>w.scrollWidth<=w.clientWidth+1),
        tableCellsClipped:[...document.querySelectorAll('.bench td,.bench th')].some(e=>{const r=box(e);return r.width>0&&(r.right>innerWidth+1||r.left<-1);})
      };
    });
    check(!layout.overflow&&!layout.bad.length,`${width} overflow: ${layout.bad}`);
    check(!layout.flow.overlap&&!layout.flow.clipped&&!layout.flow.small&&layout.flow.lanesOrdered,`${width} system diagram overlap/clipping/size/lane order: ${JSON.stringify(layout.flow)}`);
    check(layout.flow.bridgeOk,`${width} the computer-to-NPU dependency lands on the two NPU steps (or is stated in text on narrow screens)`);
    check(layout.flow.horizontal?layout.flow.rows===1&&layout.flow.minNodeW>=100:layout.flow.rows===8,`${width} diagram layout: ${layout.flow.horizontal?'one row on wide screens':'vertical list on narrow screens'} ${JSON.stringify(layout.flow)}`);
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
  check(/not thermally normalized/.test(notes)&&/different mobile-QAT build/.test(notes)&&/separate issue from the repetition/.test(notes)&&/no NPU rows for Qwen or LFM/.test(notes),'Script-writing limits stay in the notes');
  check(!/the allocator (zeroes|zeros|clears)/i.test(body+notes),'No invented allocator explanation');
  const replay=await getJson('evidence/bos-zero-replay.json'), dr=replay.frame_drift;
  check([dr.hidden_state_c.frame0,dr.hidden_state_c.median,dr.latent_frame.frame0,dr.latent_frame.median].every(v=>notes.includes(v.toFixed(2))),'Notes quote the replay drift numbers');
  check(Math.abs(replay.step0_logit.all_zeros-orig[0])<2e-3&&replay.full_trajectory.all_zero_bos_vs_android_original.max_abs<0.08,'Replay agrees with the phone run the chart shows');

  await page.emulateMedia({reducedMotion:'reduce'});
  check(await page.evaluate(()=>document.getAnimations().length)===0,'Nothing animates, including under reduced motion');
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
    const triedBefore=await page.locator('[data-edit="tried-copy"]').innerHTML();
    await page.locator('#edit-copy').click();
    check(await page.locator('[data-edit="intro"]').getAttribute('contenteditable')==='plaintext-only','Inline plain-text edit mode');
    check(await page.locator('[data-edit]').count()>=17,'Prose and headings are editable');
    await page.locator('[data-edit="intro"]').fill('My own intro <b>stays plain text</b>.');
    await page.locator('#edit-copy').click();
    await page.reload();
    check((await page.locator('[data-edit="intro"]').innerText())==='My own intro <b>stays plain text</b>.','Local edit restore');
    check(await page.locator('[data-edit="intro"] b').count()===0,'Edits must not inject HTML');
    check((await page.locator('[data-edit="tried-copy"]').innerHTML())===triedBefore,'Untouched paragraphs are unchanged after an edit and reload');
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
