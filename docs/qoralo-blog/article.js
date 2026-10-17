/* Local progressive enhancement. No network services or page telemetry. */
(() => {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const pristine = document.documentElement.outerHTML;
  const fields = $$('[data-edit]');
  const storageKey = `phone-podcast-copy-v3:${location.pathname}`;
  let editing = false;
  function editStatus(text) { if ($('#edit-status').textContent !== text) $('#edit-status').textContent = text; }
  function values() { return Object.fromEntries(fields.map(e => [e.dataset.edit, e.innerText])); }
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
    fields.forEach(e => { if (typeof saved[e.dataset.edit] === 'string') e.textContent = saved[e.dataset.edit]; });
    if (Object.keys(saved).length) editStatus('Your local text edits were restored.');
  } catch { /* A saved HTML copy works even when browser storage is unavailable. */ }
  function setEditing(on) {
    editing = on;
    document.body.classList.toggle('editing', on);
    fields.forEach(e => { if (on) e.setAttribute('contenteditable', 'plaintext-only'); else e.removeAttribute('contenteditable'); });
    $('#edit-copy').textContent = on ? 'Done editing' : 'Edit text';
    $('#edit-copy').setAttribute('aria-pressed', String(on));
    editStatus(on ? 'Click any outlined text to edit. Save an HTML copy when ready.' : '');
  }
  $('#edit-copy').addEventListener('click', () => setEditing(!editing));
  fields.forEach(field => field.addEventListener('input', () => {
    try { localStorage.setItem(storageKey, JSON.stringify(values())); editStatus('Saved in this browser. Save HTML copy to keep a file.'); }
    catch { editStatus('Browser storage unavailable. Use Save HTML copy to keep your changes.'); }
  }));
  function saveCopy() {
    // Start from the original source, not the live DOM's transient diagram/editor state.
    const copy = new DOMParser().parseFromString(pristine, 'text/html');
    const edits = values();
    copy.querySelectorAll('[data-edit]').forEach(e => { e.textContent = edits[e.dataset.edit]; });
    copy.title = edits.title || document.title;
    let base = copy.querySelector('base');
    if (!base) { base = copy.createElement('base'); copy.head.prepend(base); }
    // A copy saved to Downloads still uses the original local scripts/styles/WAVs.
    base.href = new URL('.', document.baseURI).href;
    const url = URL.createObjectURL(new Blob(['<!doctype html>\n' + copy.documentElement.outerHTML], {type:'text/html;charset=utf-8'}));
    const a = document.createElement('a'); a.href = url; a.download = 'phone-podcast-edited.html';
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    editStatus('HTML copy downloaded. It links to this article’s original scripts and audio.');
  }
  $('#save-copy').addEventListener('click', saveCopy);
  document.addEventListener('keydown', e => {
    if (editing && e.key === 'Escape') { setEditing(false); $('#edit-copy').focus(); }
    if (editing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveCopy(); }
  });

  $$('#route-controls button').forEach(button => button.addEventListener('click', () => {
    $('#compute-figure').dataset.route = button.dataset.route;
    $$('#route-controls button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  }));

  const figure = $('#lifetime-figure');
  const code = {
    broken: 'if (step == 0) {\n  std::vector<float> bos(32, NaN);\n  inputs.push_back(TV(mi, bos, {1, 1, 32}));\n} // bos is destroyed here\nRun(main, inputs);',
    kept: 'std::vector<float> bos;\nif (step == 0) {\n  bos.assign(32, NaN);\n  inputs.push_back(TV(mi, bos, {1, 1, 32}));\n}\nRun(main, inputs); // bos is still alive'
  };
  const descriptions = {
    broken: ['A vector owns the 32 start-of-sequence markers.', 'TV() wraps bos.data(). The tensor does not copy or own those floats.', 'Leaving the if-block destroys bos. The tensor still holds its old address.', 'Run() receives a tensor whose backing buffer has already been freed.'],
    kept: ['The vector owns the same 32 markers, with a lifetime outside the if-block.', 'The tensor borrows the same buffer. Ownership still belongs to the vector.', 'Leaving the if-block does not destroy the outer vector.', 'The buffer is still alive when the tensor is consumed. This passes the ownership test.']
  };
  let timer;
  function stop() { clearInterval(timer); timer = undefined; $('#play-explanation').textContent = 'Play'; $('#play-explanation').setAttribute('aria-pressed', 'false'); }
  function render(step = Number(figure.dataset.step), variant = figure.dataset.variant) {
    figure.dataset.step = step; figure.dataset.variant = variant;
    $$('#lifetime-controls [data-step]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.step) === step)));
    $$('.variant-controls button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.variant === variant)));
    $('#scope-code').textContent = code[variant];
    const freed = variant === 'broken' && step >= 2;
    $('#buffer-state').textContent = freed ? 'Freed' : 'Alive';
    $('#tensor-state').textContent = step === 0 ? 'Not created yet' : freed ? 'Dangling input' : 'Valid borrowed input';
    $('#lifetime-status').textContent = descriptions[variant][step];
  }
  $$('#lifetime-controls [data-step]').forEach(b => b.addEventListener('click', () => { stop(); render(Number(b.dataset.step)); }));
  $$('.variant-controls button').forEach(b => b.addEventListener('click', () => { stop(); render(undefined, b.dataset.variant); }));
  $('#play-explanation').addEventListener('click', () => {
    if (timer) return stop();
    render(0); $('#play-explanation').textContent = 'Pause'; $('#play-explanation').setAttribute('aria-pressed', 'true');
    timer = setInterval(() => { const step = Number(figure.dataset.step) + 1; render(step); if (step === 3) stop(); }, 1800);
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  if ('IntersectionObserver' in window) new IntersectionObserver(entries => { if (!entries[0].isIntersecting) stop(); }).observe(figure);
  $$('audio').forEach(audio => {
    audio.addEventListener('play', () => $$('audio').forEach(other => { if (audio !== other) other.pause(); }));
    audio.addEventListener('error', () => { const message = audio.parentElement.querySelector('.audio-status'); message.textContent = 'Playback unavailable. Open the WAV instead.'; message.hidden = false; });
  });
  render();
  $$('.enhanced').forEach(e => { e.hidden = false; });
})();
