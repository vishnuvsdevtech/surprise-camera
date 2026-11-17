/* Surprise camera — live accounting.
 *
 * Decodes the demo clip in the browser, scores every frame against a slowly
 * adapting background model, and JPEG-encodes the frames it decides to keep so
 * the byte counter is real rather than an estimate.
 */
(() => {
  const V = document.createElement('video');
  V.src = 'demo/clip.mp4';
  V.muted = true; V.loop = true; V.playsInline = true; V.preload = 'auto';

  const view = document.getElementById('view');
  const res = document.getElementById('res');
  const curve = document.getElementById('curve');
  const vctx = view.getContext('2d');
  const rctx = res.getContext('2d');
  const cctx = curve.getContext('2d');

  // low-res sample buffer for the maths
  const SW = 160, SH = 90;
  const small = document.createElement('canvas');
  small.width = SW; small.height = SH;
  const sctx = small.getContext('2d', { willReadFrequently: true });

  const el = (id) => document.getElementById(id);
  const FLOOR = 0.055;            // treat sub-noise differences as nothing
  const FPS = 12;

  let bg = null, prev = null;
  let scores = [], stored = [], events = [], lastIdx = -1;
  let encBytes = 0, allBytes = 0, storedCount = 0, allCount = 0;
  let lastEncode = 0;

  function thrNow() { return parseFloat(el('thr').value) * 0.0002; }

  function encodeBytes(frameCanvas) {
    // real JPEG size, throttled — the honest way to count bytes
    const url = frameCanvas.toDataURL('image/jpeg', 0.55);
    return Math.round((url.length - 23) * 0.75);
  }

  function process() {
    if (V.readyState < 2) return;
    const idx = Math.floor(V.currentTime * FPS);
    if (idx === lastIdx) return;

    if (idx < lastIdx) {          // loop wrapped: new pass
      scores = []; stored = []; events = []; bg = null; prev = null;
      encBytes = 0; allBytes = 0; storedCount = 0; allCount = 0;
    }
    lastIdx = idx;

    vctx.drawImage(V, 0, 0, view.width, view.height);
    sctx.drawImage(V, 0, 0, SW, SH);
    const px = sctx.getImageData(0, 0, SW, SH).data;

    const g = new Float32Array(SW * SH);
    for (let i = 0, j = 0; i < px.length; i += 4, j++) {
      g[j] = (px[i] * 0.299 + px[i + 1] * 0.587 + px[i + 2] * 0.114) / 255;
    }

    const model = el('model').value;
    const ref = model === 'bg' ? bg : prev;
    let score = 0;
    const diff = new Float32Array(SW * SH);

    if (ref) {
      for (let i = 0; i < g.length; i++) {
        const d = Math.abs(g[i] - ref[i]);
        diff[i] = d;
        // mass of change above the noise floor, not a mean over the whole frame:
        // a mean lets 95% of wall outvote the one thing that happened
        if (d > FLOOR) score += (d - FLOOR);
      }
      score /= g.length;
    }

    scores.push(score);
    if (scores.length > 400) scores.shift();

    const thr = thrNow();
    const keep = score > thr || idx % parseInt(el('kf').value, 10) === 0 || idx === 0;
    stored.push(keep);

    // event bookkeeping
    if (keep && score > thr) {
      const last = events[events.length - 1];
      if (last && last.end === idx - 1) last.end = idx;
      else events.push({ start: idx, end: idx });
    }

    // bytes: encode every frame for the "record everything" figure (throttled),
    // and every stored frame for the real figure
    const now = performance.now();
    if (now - lastEncode > 55) {
      lastEncode = now;
      const b = encodeBytes(view);
      allBytes += b; allCount++;
      if (keep) { encBytes += b; storedCount++; }
    } else if (keep) {
      // still count the frame, using the running average
      const avg = allCount ? allBytes / allCount : 3500;
      encBytes += avg; storedCount++;
    }

    // residual view
    const out = rctx.createImageData(SW, SH);
    for (let i = 0; i < diff.length; i++) {
      const v = Math.min(255, diff[i] * 255 * 3.2);
      out.data[i * 4] = v; out.data[i * 4 + 1] = v * 0.45; out.data[i * 4 + 2] = v * 0.55; out.data[i * 4 + 3] = 255;
    }
    const tmp = document.createElement('canvas');
    tmp.width = SW; tmp.height = SH;
    tmp.getContext('2d').putImageData(out, 0, 0);
    rctx.imageSmoothingEnabled = false;
    rctx.drawImage(tmp, 0, 0, res.width, res.height);

    // adapt the background only where nothing happened, so events are not
    // quietly absorbed into what the camera considers normal
    if (bg) {
      for (let i = 0; i < g.length; i++) bg[i] = score > thr ? bg[i] : bg[i] * 0.98 + g[i] * 0.02;
    } else bg = g.slice();
    prev = g;

    drawCurve(thr);
    readout(thr);
  }

  function drawCurve(thr) {
    const W = curve.width, H = curve.height;
    cctx.clearRect(0, 0, W, H);
    const n = scores.length || 1;
    const max = Math.max(0.004, ...scores) * 1.15;
    const xOf = (i) => (i / Math.max(1, n - 1)) * W;
    const yOf = (v) => H - 8 - (v / max) * (H - 16);

    // stored frames as a band at the bottom
    cctx.fillStyle = 'rgba(255,93,115,.16)';
    stored.forEach((k, i) => {
      if (!k) return;
      const x = xOf(i);
      cctx.fillRect(x, H - 6, Math.max(1, W / Math.max(1, n - 1) + 0.5), 6);
    });

    // threshold
    const ty = yOf(thr);
    cctx.strokeStyle = 'rgba(232,178,92,.7)';
    cctx.setLineDash([5, 5]);
    cctx.beginPath(); cctx.moveTo(0, ty); cctx.lineTo(W, ty); cctx.stroke();
    cctx.setLineDash([]);

    // curve
    cctx.beginPath();
    scores.forEach((v, i) => (i ? cctx.lineTo(xOf(i), yOf(v)) : cctx.moveTo(xOf(i), yOf(v))));
    cctx.strokeStyle = '#ff5d73';
    cctx.lineWidth = 2;
    cctx.stroke();
    cctx.lineTo(xOf(n - 1), H); cctx.lineTo(0, H); cctx.closePath();
    cctx.fillStyle = 'rgba(255,93,115,.12)';
    cctx.fill();
  }

  function readout(thr) {
    const saved = allCount ? 100 * (1 - encBytes / Math.max(1, allBytes)) : 0;
    const ev = events.length ? events.map((e) => `${e.start}–${e.end}`).join(', ') : 'none yet';
    el('readout').innerHTML =
      `<span>frames <b>${scores.length}</b></span>` +
      `<span>stored <b>${stored.filter(Boolean).length}</b></span>` +
      `<span>saved <b>${saved.toFixed(1)}%</b></span>` +
      `<span>surprise <b>${(scores[scores.length - 1] || 0).toFixed(4)}</b></span>` +
      `<span>threshold <b>${thr.toFixed(4)}</b></span>` +
      `<span>events <b>${ev}</b></span>`;
    el('thrVal').textContent = thr.toFixed(4);
    el('thrLabel').textContent = 'threshold ' + thr.toFixed(4);
    el('kfVal').textContent = el('kf').value;
    const on = stored[stored.length - 1];
    const badge = el('state');
    badge.className = 'badge ' + (on ? 'rec' : '');
    badge.textContent = on ? 'storing frame' : 'skipping — predicted';
  }

  V.addEventListener('loadeddata', () => { V.play().catch(() => {}); });
  ['thr', 'kf', 'model'].forEach((id) => el(id).addEventListener('input', () => { drawCurve(thrNow()); readout(thrNow()); }));
  // the clip is short; nudge play on first interaction in case autoplay is blocked
  document.addEventListener('click', () => { if (V.paused) V.play().catch(() => {}); }, { once: true });

  function tick() { process(); requestAnimationFrame(tick); }
  tick();
})();
