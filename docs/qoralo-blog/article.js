/* Local progressive enhancement. No network services or page telemetry. */
(() => {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const pristine = document.documentElement.outerHTML;
  const fields = $$('[data-edit]');
  const storageKey = `phone-podcast-copy-v3:${location.pathname}`;
  let editing = false;
  function editStatus(text) { if ($('#edit-status').textContent !== text) $('#edit-status').textContent = text; }
  // Links survive editing: an edited paragraph is stored as text with [label](https://link) and rebuilt with real anchors.
  // Only http(s) links are rebuilt, with DOM nodes (never innerHTML), so typed text cannot inject markup.
  const LINK = /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g;
  function serialize(el) {
    const walk = node => [...node.childNodes].map(n =>
      n.nodeType === 3 ? n.nodeValue.replace(/\s+/g, ' ')
      : n.nodeName === 'BR' ? '\n'
      : n.nodeName === 'A' && n.getAttribute('href') ? `[${n.textContent}](${n.getAttribute('href')})`
      : walk(n)).join('');
    return walk(el).trim();
  }
  function fill(el, text) {
    const doc = el.ownerDocument; el.textContent = '';
    let last = 0, m; LINK.lastIndex = 0;
    while ((m = LINK.exec(text))) {
      if (m.index > last) el.append(doc.createTextNode(text.slice(last, m.index)));
      const a = doc.createElement('a'); a.href = m[2]; a.className = 'ref'; a.rel = 'noopener noreferrer'; a.textContent = m[1]; el.append(a);
      last = LINK.lastIndex;
    }
    if (last < text.length) el.append(doc.createTextNode(text.slice(last)));
  }
  // Only paragraphs you actually change are stored or exported, so untouched text keeps its inline formatting.
  let edited = {};
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
    fields.forEach(e => { if (typeof saved[e.dataset.edit] === 'string') { edited[e.dataset.edit] = saved[e.dataset.edit]; fill(e, saved[e.dataset.edit]); } });
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
    edited[field.dataset.edit] = serialize(field);
    try { localStorage.setItem(storageKey, JSON.stringify(edited)); editStatus('Saved in this browser. Save HTML copy to keep a file.'); }
    catch { editStatus('Browser storage unavailable. Use Save HTML copy to keep your changes.'); }
  }));
  function saveCopy() {
    // Start from the original source, not the live DOM's transient diagram/editor state.
    const copy = new DOMParser().parseFromString(pristine, 'text/html');
    copy.querySelectorAll('[data-edit]').forEach(e => { if (e.dataset.edit in edited) fill(e, edited[e.dataset.edit]); });
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

  const demo = $('#demo-video');
  if (demo) {
    const showMissing = () => { demo.hidden = true; $('.demo-status').hidden = false; };
    demo.querySelector('source').addEventListener('error', showMissing);
    // A missing file normally fires the source's error event. As a fallback, judge "missing" only after the page has settled and only if
    // nothing was ever loaded: right at start-up (and briefly while the browser picks a source) networkState is 3 even when the file exists.
    const checkMissing = () => { if (demo.readyState === 0 && (demo.networkState === 3 || demo.error)) showMissing(); };
    window.addEventListener('load', () => setTimeout(checkMissing, 1500));
    demo.addEventListener('play', () => $$('audio').forEach(a => a.pause()));
  }
  $$('audio').forEach(audio => {
    audio.addEventListener('play', () => { $$('audio').forEach(other => { if (audio !== other) other.pause(); }); if (demo) demo.pause(); });
    audio.addEventListener('error', () => { const message = audio.parentElement.querySelector('.audio-status'); message.textContent = 'Playback unavailable. Open the audio file instead.'; message.hidden = false; });
  });
  $$('.enhanced').forEach(e => { e.hidden = false; });
})();
