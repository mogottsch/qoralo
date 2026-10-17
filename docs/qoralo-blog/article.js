/* Readable static figures first. Controls enhance them; no telemetry or dependencies. */
(() => {
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];

  const route = $('#compute-figure');
  const routeCopy = {
    script: 'Gemma generates the script through LiteRT-LM on the GPU. CPU work still includes app control and input preparation.',
    speech: 'Supertonic synthesizes speech through ONNX Runtime + QNN on the NPU’s HTP backend. The CPU assembles and writes the audio.'
  };
  $$('#route-controls button').forEach(button => button.addEventListener('click', () => {
    route.dataset.route = button.dataset.route;
    $$('#route-controls button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    $('#route-status').textContent = routeCopy[button.dataset.route];
  }));

  const trace = $('#state-figure');
  const explanations = [
    'Same weights, text tokens, Alba voice state and saved random noise. The desktop and original Android runs use the dynamic ONNX graph. Recovery uses a different, fixed-cache graph.',
    'The first autoregressive step already differs: raw end-of-speech scores are −9.8847 on desktop and −10.2709 on Android. These are logits, not probabilities. This is before the first sampled audio latent.',
    'Desktop stops at step 53. The original Android run never reaches end-of-speech before the 134-frame limit. The fixed-cache Android route stops at step 53 and its recording was accepted in listening.'
  ];
  let timer;
  function showStage(stage) {
    trace.dataset.stage = stage;
    $$('#stage-controls [data-stage]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.stage) === stage)));
    $('#state-status').textContent = explanations[stage];
  }
  function stopExplanation() {
    clearInterval(timer);
    timer = undefined;
    $('#play-explanation').textContent = 'Play explanation';
    $('#play-explanation').setAttribute('aria-pressed', 'false');
  }
  $$('#stage-controls [data-stage]').forEach(button => button.addEventListener('click', () => {
    stopExplanation();
    showStage(Number(button.dataset.stage));
  }));
  $('#play-explanation').addEventListener('click', () => {
    if (timer) return stopExplanation();
    showStage(0);
    $('#play-explanation').textContent = 'Pause explanation';
    $('#play-explanation').setAttribute('aria-pressed', 'true');
    timer = setInterval(() => {
      const stage = Number(trace.dataset.stage);
      if (stage >= 2) return stopExplanation();
      showStage(stage + 1);
      if (stage + 1 === 2) stopExplanation();
    }, 2400);
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopExplanation(); });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => { if (!entries[0].isIntersecting) stopExplanation(); }).observe(trace);
  }
  // Reduced motion changes still preserve manual stepping; no automatic tour is started.
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  function motionPreference() { if (reduced.matches) stopExplanation(); }
  reduced.addEventListener('change', motionPreference);

  const pieces = $$('.segment');
  $('#segment-picker').addEventListener('input', event => {
    const index = Number(event.target.value) - 1;
    pieces.forEach((piece, i) => piece.classList.toggle('is-selected', i === index));
    const seconds = Number(pieces[index].dataset.frames) / 44100;
    $('#segment-status').textContent = `Piece ${index + 1} of 15 · ${seconds.toFixed(2)} s of speech${index < 14 ? ' + 0.30 s gap' : ' · no final gap'}`;
  });
  $('#segment-picker').dispatchEvent(new Event('input'));

  $$('audio').forEach(audio => {
    audio.addEventListener('play', () => $$('audio').forEach(other => { if (other !== audio) other.pause(); }));
    audio.addEventListener('error', () => {
      const status = audio.parentElement.querySelector('.audio-status');
      status.textContent = 'Playback unavailable here. Open the WAV file below in your audio player.';
      status.hidden = false;
    });
  });
  $$('.enhanced').forEach(element => { element.hidden = false; });
})();
