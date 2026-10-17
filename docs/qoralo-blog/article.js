/* Local progressive enhancement. No network services or page telemetry. */
(() => {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const pristine = document.documentElement.outerHTML;
  const fields = $$('[data-edit]');
  const storageKey = `phone-podcast-copy-v3:${location.pathname}`;
  let editing = false;
  function editStatus(text) { if ($('#edit-status').textContent !== text) $('#edit-status').textContent = text; }
  // Only paragraphs you actually change are stored or exported, so untouched text keeps its inline formatting.
  let edited = {};
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
    fields.forEach(e => { if (typeof saved[e.dataset.edit] === 'string') { edited[e.dataset.edit] = saved[e.dataset.edit]; e.textContent = saved[e.dataset.edit]; } });
    if (Object.keys(edited).length) editStatus('Your local text edits were restored.');
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
    edited[field.dataset.edit] = field.innerText;
    try { localStorage.setItem(storageKey, JSON.stringify(edited)); editStatus('Saved in this browser. Save HTML copy to keep a file.'); }
    catch { editStatus('Browser storage unavailable. Use Save HTML copy to keep your changes.'); }
  }));
  function saveCopy() {
    // Start from the original source, not the live DOM's transient diagram/editor state.
    const copy = new DOMParser().parseFromString(pristine, 'text/html');
    copy.querySelectorAll('[data-edit]').forEach(e => { if (e.dataset.edit in edited) e.textContent = edited[e.dataset.edit]; });
    copy.title = edited.title || document.title;
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

  $$('audio').forEach(audio => {
    audio.addEventListener('play', () => $$('audio').forEach(other => { if (audio !== other) other.pause(); }));
    audio.addEventListener('error', () => { const message = audio.parentElement.querySelector('.audio-status'); message.textContent = 'Playback unavailable. Open the WAV instead.'; message.hidden = false; });
  });
  $$('.enhanced').forEach(e => { e.hidden = false; });
})();
