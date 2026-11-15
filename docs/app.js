// AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
// The viewer. It draws stacked SPHEREx visits from JSON (see spherex/webdata.py) and does everything else in the
// browser: playing, blinking, subtracting, zooming, overlays and the two charts.
'use strict';

const CONFIG = {
  data: 'data/',
  api: '/api',       // same-origin live-query service (api/main.py); if empty, new positions open in the Streamlit app
  streamlit: '',     // optional external fallback viewer for live queries
};

// The six detectors: wavelength range in micrometres and the colour used for them everywhere on the page.
const BANDS = {
  1: { range: [0.75, 1.12], color: '#ffe08a' },
  2: { range: [1.10, 1.65], color: '#ffb347' },
  3: { range: [1.63, 2.43], color: '#ff8442' },
  4: { range: [2.40, 3.85], color: '#f0544f' },
  5: { range: [3.81, 4.43], color: '#c2387a' },
  6: { range: [4.41, 5.01], color: '#8a3fb0' },
};
const COLORS = { paper: '#ece6d6', dim: '#a3abc0', rule: '#303c5c', amber: '#ffb347', gaia: '#5ac8ff', fast: '#ff62c8', sat: [255, 107, 87] };
const NO_DATA = [27, 35, 56];
const FAST_MAS_PER_YEAR = 100;
const RAD = Math.PI / 180;
const MODE_HELP = {
  play: 'Each frame is one SPHEREx visit. All frames use the same brightness scale, so a change between frames is a real change.',
  blink: 'Flips between two visits. Anything that jumps has moved; anything that flickers has changed brightness.',
  diff: 'One visit minus another: white is brighter than on the comparison visit, black is fainter. An object that moved is half black, half white. One that changed brightness is white or black all over. Steady stars leave small speckles, because two images never line up perfectly.',
  stack: 'The median of all visits. Steady objects get clearer and moving ones fade.',
};

const $ = (id) => document.getElementById(id);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const params = new URLSearchParams(location.search);
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches && !params.has('autoplay');
// ?api=http://localhost:8000 points the viewer at a copy of the service running on this computer, for testing
if (/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(params.get('api') || '')) CONFIG.api = params.get('api');
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const S = {
  index: null, entry: null, target: null, view: null, views: new Map(),
  mode: 'play', frame: 0, ref: 0, blinkOn: true, playing: !reducedMotion, speed: 700,
  gain: 0, smooth: true, marker: true, gaia: false, sat: false, gmag: 16,
  zoom: 1, cx: 0, cy: 0, tf: null, bufKey: '', timer: null, drag: null,
  aladin: null, aladinCat: null, gallery: [],
};
const buf = document.createElement('canvas');
const tint = document.createElement('canvas');

// ---------------------------------------------------------------- numbers

// half-precision floats -> numbers, by table
const HALF = (() => {
  const t = new Float32Array(65536);
  for (let h = 0; h < 65536; h++) {
    const s = h & 0x8000 ? -1 : 1, e = (h >> 10) & 31, f = h & 1023;
    t[h] = e === 0 ? s * Math.pow(2, -14) * (f / 1024) : e === 31 ? (f ? NaN : s * Infinity) : s * Math.pow(2, e - 15) * (1 + f / 1024);
  }
  return t;
})();

function bytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function sortedFinite(a) {
  const out = new Float32Array(a.length);
  let m = 0;
  for (let i = 0; i < a.length; i++) { const v = a[i]; if (v === v && Math.abs(v) !== Infinity) out[m++] = v; }
  return out.subarray(0, m).sort();
}
function quantile(sorted, q) {
  if (!sorted.length) return NaN;
  return sorted[clamp(Math.round(q * (sorted.length - 1)), 0, sorted.length - 1)];
}
function robust(a) {
  const s = sortedFinite(a);
  const median = quantile(s, 0.5);
  const dev = new Float32Array(s.length);
  for (let i = 0; i < s.length; i++) dev[i] = Math.abs(s[i] - median);
  dev.sort();
  return { median, sigma: 1.4826 * quantile(dev, 0.5), sorted: s };
}
const median = (list) => { const s = [...list].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

// Fill small gaps from their brightest neighbour, for display only (the core of a clipped star has no value).
function fillHoles(a, n, passes = 3) {
  let out = a;
  for (let p = 0; p < passes; p++) {
    let changed = false;
    const next = out.slice();
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x;
      if (out[i] === out[i]) continue;
      let best = -Infinity;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const yy = y + dy, xx = x + dx;
        if (yy < 0 || xx < 0 || yy >= n || xx >= n) continue;
        const v = out[yy * n + xx];
        if (v === v && v > best) best = v;
      }
      if (best > -Infinity) { next[i] = best; changed = true; }
    }
    out = next;
    if (!changed) break;
  }
  return out;
}

// Gentle blur (about one grid pixel) that ignores empty pixels. Used before subtracting two visits.
function blur(a, n) {
  const w = [1, 2, 1, 2, 4, 2, 1, 2, 1];
  let src = a;
  for (let pass = 0; pass < 2; pass++) {
    const out = new Float32Array(src.length);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x;
      if (src[i] !== src[i]) { out[i] = NaN; continue; }
      let sum = 0, weight = 0, k = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++, k++) {
        const yy = y + dy, xx = x + dx;
        if (yy < 0 || xx < 0 || yy >= n || xx >= n) continue;
        const v = src[yy * n + xx];
        if (v === v) { sum += w[k] * v; weight += w[k]; }
      }
      out[i] = sum / weight;
    }
    src = out;
  }
  return src;
}

function medianStack(arrays) {
  const size = arrays[0].length, out = new Float32Array(size), col = [];
  for (let i = 0; i < size; i++) {
    col.length = 0;
    for (const a of arrays) { const v = a[i]; if (v === v) col.push(v); }
    out[i] = col.length ? median(col) : NaN;
  }
  return out;
}

function decodeView(doc) {
  const n = doc.n, size = n * n;
  const raw = bytes(doc.data);
  const u16 = new Uint16Array(raw.buffer, raw.byteOffset, raw.byteLength >> 1);
  const rawFrames = doc.frames.map((_, i) => {
    const a = new Float32Array(size);
    for (let k = 0; k < size; k++) a[k] = HALF[u16[i * size + k]];
    return a;
  });
  let sat = null;
  if (doc.sat) { const s = bytes(doc.sat); sat = doc.frames.map((_, i) => s.subarray(i * size, (i + 1) * size)); }
  const data = rawFrames.map((a) => fillHoles(a, n));
  const stats = data.map(robust);
  const sigma = median(stats.map((s) => s.sigma)) || 1e-6;
  const low = median(stats.map((s) => s.median)) - 1.5 * sigma;
  const high = Math.max(...stats.map((s) => quantile(s.sorted, 0.997)), low + 10 * sigma);
  // Brightness scale chosen so that the sky noise is just visible: faint sources show in every field,
  // and the brightest stars are allowed to go white.
  const autoGain = clamp(0.0104 * (high - low) / sigma, 1, 40);
  return {
    band: doc.band, n, frames: doc.frames, meta: doc, raw: rawFrames, data, sat, low, high, sigma, autoGain,
    smoothed: data.map((a) => blur(a, n)), stack: medianStack(data),
  };
}

// ---------------------------------------------------------------- sky geometry (tangent-plane grid centred on the target)

function project(ra, dec) {
  const T = S.target, n = S.view.n;
  const a0 = T.ra * RAD, d0 = T.dec * RAD, a = ra * RAD, d = dec * RAD;
  const cosc = Math.sin(d0) * Math.sin(d) + Math.cos(d0) * Math.cos(d) * Math.cos(a - a0);
  const xi = Math.cos(d) * Math.sin(a - a0) / cosc;
  const eta = (Math.cos(d0) * Math.sin(d) - Math.sin(d0) * Math.cos(d) * Math.cos(a - a0)) / cosc;
  const step = T.arcsec / 3600 * RAD, c = (n - 1) / 2;
  return [c - xi / step, c - eta / step];
}
function unproject(x, y) {
  const T = S.target, n = S.view.n;
  const step = T.arcsec / 3600 * RAD, c = (n - 1) / 2;
  const xi = (c - x) * step, eta = (c - y) * step;
  const a0 = T.ra * RAD, d0 = T.dec * RAD;
  const rho = Math.hypot(xi, eta);
  if (rho === 0) return [T.ra, T.dec];
  const cc = Math.atan(rho);
  const dec = Math.asin(Math.cos(cc) * Math.sin(d0) + eta * Math.sin(cc) * Math.cos(d0) / rho);
  const ra = a0 + Math.atan2(xi * Math.sin(cc), rho * Math.cos(d0) * Math.cos(cc) - eta * Math.sin(d0) * Math.sin(cc));
  return [((ra / RAD) % 360 + 360) % 360, dec / RAD];
}
// linear proper motion, as in spherex/resolve.py
function moved(ra, dec, pmRa, pmDec, fromYear, toYear) {
  const dt = toYear - fromYear;
  const newDec = dec + pmDec * dt / 3.6e6;
  return [ra + pmRa * dt / 3.6e6 / Math.cos((dec + newDec) / 2 * RAD), newDec];
}

function sexagesimal(value, hours) {
  const sign = value < 0 ? '−' : hours ? '' : '+';
  let v = Math.abs(hours ? value / 15 : value);
  const a = Math.floor(v); v = (v - a) * 60;
  const b = Math.floor(v); const c = (v - b) * 60;
  const pad = (x, w) => String(x).padStart(w, '0');
  return hours ? `${pad(a, 2)}h ${pad(b, 2)}m ${pad(c.toFixed(1), 4)}s` : `${sign}${pad(a, 2)}° ${pad(b, 2)}′ ${pad(c.toFixed(0), 2)}″`;
}
const fmtMjy = (v) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toFixed(3));
const mjdToDate = (mjd) => new Date((mjd - 40587) * 86400000);
const isoDate = (mjd) => mjdToDate(mjd).toISOString().slice(0, 10);

// ---------------------------------------------------------------- painting

function gainNow() { return S.view.autoGain * Math.pow(10, 1.5 * S.gain); }

function paintGray(image, a, sat, view, gain) {
  const px = image.data, k = gain / (view.high - view.low), low = view.low, norm = 255 / Math.asinh(8);
  for (let i = 0, j = 0; i < a.length; i++, j += 4) {
    const v = a[i];
    if (sat && sat[i]) { px[j] = px[j + 1] = px[j + 2] = 255; }
    else if (v !== v) { px[j] = NO_DATA[0]; px[j + 1] = NO_DATA[1]; px[j + 2] = NO_DATA[2]; }
    else {
      let x = (v - low) * k;
      x = x < 0 ? 0 : x > 1 ? 1 : x;
      px[j] = px[j + 1] = px[j + 2] = Math.asinh(8 * x) * norm;
    }
    px[j + 3] = 255;
  }
}

// a minus b, on a grey scale that is symmetric around "no change". Saturated pixels carry no information
// about a change, so they are drawn as "no change".
function paintDiff(image, a, b, satA, satB, limit, contrast) {
  const px = image.data;
  for (let i = 0, j = 0; i < a.length; i++, j += 4) {
    const saturated = (satA && satA[i]) || (satB && satB[i]);
    const v = a[i] - b[i];
    if (saturated || ((a[i] === a[i]) !== (b[i] === b[i]))) px[j] = px[j + 1] = px[j + 2] = 128;
    else if (v !== v) { px[j] = NO_DATA[0]; px[j + 1] = NO_DATA[1]; px[j + 2] = NO_DATA[2]; }
    else px[j] = px[j + 1] = px[j + 2] = 127.5 + 127.5 * clamp(contrast * v / limit, -1, 1);
    px[j + 3] = 255;
  }
}

// One scale for every difference against the same comparison visit, so the frames can be compared with each other.
function diffLimit(view, ref) {
  const key = `limit${ref}`;
  if (view[key]) return view[key];
  const all = [];
  view.smoothed.forEach((a, f) => {
    if (f === ref) return;
    const b = view.smoothed[ref], sa = view.sat && view.sat[f], sb = view.sat && view.sat[ref];
    for (let i = 0; i < a.length; i++) { const v = a[i] - b[i]; if (v === v && !(sa && sa[i]) && !(sb && sb[i])) all.push(Math.abs(v)); }
  });
  const sorted = Float32Array.from(all).sort();
  view[key] = quantile(sorted, 0.995) || 1;
  return view[key];
}

function shownFrame() { return S.mode === 'blink' && !S.blinkOn ? S.ref : S.frame; }

function repaint() {
  const v = S.view, f = shownFrame();
  const key = [v.band, S.entry ? S.entry.slug : '', S.mode, f, S.ref, S.gain, S.sat].join('|');
  if (key === S.bufKey) return;
  S.bufKey = key;
  buf.width = buf.height = tint.width = tint.height = v.n;
  const ctx = buf.getContext('2d');
  const image = ctx.createImageData(v.n, v.n);
  if (S.mode === 'diff') {
    paintDiff(image, v.smoothed[S.frame], v.smoothed[S.ref], v.sat && v.sat[S.frame], v.sat && v.sat[S.ref], diffLimit(v, S.ref), Math.pow(10, S.gain));
  } else if (S.mode === 'stack') {
    paintGray(image, v.stack, null, v, gainNow());
  } else {
    paintGray(image, v.data[f], v.sat && v.sat[f], v, gainNow());
  }
  ctx.putImageData(image, 0, 0);

  const tctx = tint.getContext('2d');
  const mask = tctx.createImageData(v.n, v.n);
  if (S.sat && v.sat && S.mode !== 'stack') {
    const masks = S.mode === 'diff' ? [v.sat[S.frame], v.sat[S.ref]] : [v.sat[f]];
    for (let i = 0, j = 0; i < v.n * v.n; i++, j += 4) {
      if (masks.some((m) => m[i])) { mask.data[j] = COLORS.sat[0]; mask.data[j + 1] = COLORS.sat[1]; mask.data[j + 2] = COLORS.sat[2]; mask.data[j + 3] = 170; }
    }
  }
  tctx.putImageData(mask, 0, 0);
}

function sizeCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(canvas.clientWidth * dpr)), h = Math.max(1, Math.round(canvas.clientHeight * dpr));
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  return dpr;
}

function draw() {
  const v = S.view;
  if (!v) return;
  repaint();
  const canvas = $('sky'), dpr = sizeCanvas(canvas), W = canvas.width, ctx = canvas.getContext('2d');
  const span = v.n / S.zoom;
  const sx = clamp(S.cx - span / 2, 0, v.n - span), sy = clamp(S.cy - span / 2, 0, v.n - span);
  const k = W / span;
  S.tf = { sx, sy, k, dpr };
  const at = (x, y) => [(x + 0.5 - sx) * k, (y + 0.5 - sy) * k];

  ctx.clearRect(0, 0, W, W);
  ctx.imageSmoothingEnabled = S.smooth;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(buf, sx, sy, span, span, 0, 0, W, W);
  if (S.sat) { ctx.imageSmoothingEnabled = false; ctx.drawImage(tint, sx, sy, span, span, 0, 0, W, W); }

  const f = shownFrame(), frame = v.frames[f];
  if (S.gaia && S.target.gaia.stars.length) {
    const year = S.mode === 'stack' ? median(v.frames.map((fr) => fr.year)) : frame.year;
    for (const [ra, dec, pmRa, pmDec, g] of S.target.gaia.stars) {
      const fast = Math.hypot(pmRa, pmDec) >= FAST_MAS_PER_YEAR;
      if (g > S.gmag && !fast) continue;
      const [x, y] = at(...project(...moved(ra, dec, pmRa, pmDec, S.target.gaia.epoch, year)));
      if (x < 0 || y < 0 || x > W || y > W) continue;
      ctx.beginPath();
      ctx.arc(x, y, (fast ? 9 : 6) * dpr, 0, 2 * Math.PI);
      ctx.strokeStyle = fast ? COLORS.fast : COLORS.gaia;
      ctx.lineWidth = (fast ? 2 : 1.25) * dpr;
      ctx.stroke();
    }
  }
  if (S.marker) {
    ctx.strokeStyle = COLORS.amber;
    ctx.lineWidth = 2 * dpr;
    if (S.mode === 'stack') { // the path the catalogue motion predicts across all visits
      ctx.beginPath();
      v.frames.forEach((fr, i) => { const [x, y] = at(...fr.marker); if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); });
      ctx.stroke();
    }
    const [x, y] = at(...frame.marker);
    const gap = 9 * dpr, len = 15 * dpr;
    ctx.beginPath();
    ctx.moveTo(x - gap - len, y); ctx.lineTo(x - gap, y);
    ctx.moveTo(x, y - gap - len); ctx.lineTo(x, y - gap);
    ctx.stroke();
  }

  // scale bar and compass
  const arcsec = S.target.arcsec;
  const choices = [300, 120, 60, 30, 10, 5];
  const bar = choices.find((c) => (c / arcsec) * k < W * 0.3) || 5;
  const barPx = (bar / arcsec) * k, m = 14 * dpr;
  ctx.strokeStyle = ctx.fillStyle = COLORS.paper;
  ctx.lineWidth = 2 * dpr;
  ctx.font = `${12.5 * dpr}px "IBM Plex Sans", sans-serif`;
  ctx.textBaseline = 'bottom';
  ctx.beginPath(); ctx.moveTo(m, W - m); ctx.lineTo(m + barPx, W - m); ctx.stroke();
  ctx.textAlign = 'left';
  ctx.fillText(bar >= 60 ? `${bar / 60}′` : `${bar}″`, m, W - m - 4 * dpr);
  const cxp = W - m - 6 * dpr, cyp = W - m, arm = 26 * dpr;
  ctx.lineWidth = 1.5 * dpr;
  ctx.beginPath(); ctx.moveTo(cxp, cyp); ctx.lineTo(cxp, cyp - arm); ctx.moveTo(cxp, cyp); ctx.lineTo(cxp - arm, cyp); ctx.stroke();
  ctx.textAlign = 'center';
  ctx.fillText('N', cxp, cyp - arm - 2 * dpr);
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  ctx.fillText('E', cxp - arm - 4 * dpr, cyp);
}

// ---------------------------------------------------------------- the page around the plate

function shift(i, j) {
  const v = S.view, a = v.frames[i], b = v.frames[j], arcsec = S.target.arcsec;
  const expected = Math.hypot(a.marker[0] - b.marker[0], a.marker[1] - b.marker[1]) * arcsec;
  const measured = a.centroid && b.centroid ? Math.hypot(a.centroid[0] - b.centroid[0], a.centroid[1] - b.centroid[1]) * arcsec : null;
  return { expected, measured };
}
function brightnessText(i) {
  const frames = S.view.frames, b = frames[i].brightness;
  if (!b || b.mjy === null) return 'not measured';
  if (b.kind === 'aperture') return `${fmtMjy(b.mjy)} mJy`;
  const first = frames.find((fr) => fr.brightness && fr.brightness.mjy);
  return first && first !== frames[i] ? `${(b.mjy / first.brightness.mjy).toFixed(2)} times the first visit` : 'first visit (the reference)';
}
const hasMotion = () => Math.hypot(...S.target.pm) > 0;
// true when the catalogue motion carries the target at least a third of a grid pixel across the visits shown
function movesVisibly() {
  const frames = S.view.frames, a = frames[0].marker, b = frames[frames.length - 1].marker;
  return Math.hypot(a[0] - b[0], a[1] - b[1]) * S.target.arcsec >= 1;
}

function updateText() {
  const v = S.view, T = S.target, f = shownFrame(), frame = v.frames[f];
  const [lo, hi] = v.band ? BANDS[v.band].range : [0.75, 5.01];
  const day = (i) => escapeHtml(v.frames[i].date);
  const what = S.mode === 'diff' ? `<strong>${day(S.frame)}</strong> minus ${day(S.ref)}`
    : S.mode === 'stack' ? `<strong>All ${v.frames.length} visits</strong>, ${day(0)} to ${day(v.frames.length - 1)}`
    : `<strong>${day(f)}</strong>, visit ${f + 1} of ${v.frames.length}`;
  $('caption').innerHTML = `${what}. ${v.band ? 'Detector D' + v.band : 'Sum of all six detectors'}, ${lo.toFixed(2)} to ${hi.toFixed(2)} µm. North is up, east is left.`;

  const rows = [];
  rows.push(['Position', `${sexagesimal(T.ra, true)}, ${sexagesimal(T.dec, false)} <small>(${T.ra.toFixed(5)}°, ${T.dec >= 0 ? '+' : ''}${T.dec.toFixed(5)}°${hasMotion() ? ', where it is in ' + T.epoch.toFixed(0) : ''})</small>`]);
  if (hasMotion()) rows.push(['Catalogue motion', `${(Math.hypot(...T.pm) / 1000).toFixed(2)}″ per year <small>(${escapeHtml(T.source.replace(' via CDS Sesame', ''))})</small>`]);
  if (S.mode !== 'stack') {
    rows.push(['This visit', `${frame.images} of ${frame.available} images over ${frame.days < 1 ? 'one day' : frame.days.toFixed(0) + ' days'}, ${frame.wl[0].toFixed(2)} to ${frame.wl[1].toFixed(2)} µm`]);
    const here = S.mode === 'blink' ? S.frame : f;
    // while playing, compare with the earliest visit in which the object is clear enough to locate
    const located = v.frames.findIndex((fr) => fr.centroid);
    const other = S.mode === 'play' ? (located >= 0 && v.frames[here].centroid ? located : 0) : S.ref;
    if (movesVisibly() && here !== other) {
      const s = shift(here, other);
      const measured = s.measured === null ? 'not measurable here (too faint or saturated)' : `<span class="measured">measured ${s.measured.toFixed(1)}″</span>`;
      rows.push([`Moved since ${day(other)}`, `${measured}, catalogue predicts ${s.expected.toFixed(1)}″`]);
    }
    const ring = frame.brightness && frame.brightness.kind === 'ring';
    rows.push([ring ? 'Brightness outside the saturated core' : 'Brightness', brightnessText(f) + (ring ? ' <small>(rough: differences under about 25% mean nothing)</small>' : '')]);
    const flags = Object.entries(frame.flags).map(([name, count]) => `${escapeHtml(name)} (${Number(count)})`).join(', ');
    rows.push(['Flags at the target', flags ? `${flags} <small>number of images</small>` : 'none']);
  }
  $('facts').innerHTML = rows.map(([k, val]) => `<dt>${k}</dt><dd>${val}</dd>`).join('');

  for (const b of document.querySelectorAll('#strip button')) {
    const i = Number(b.dataset.i);
    b.setAttribute('aria-current', String(i === (S.mode === 'blink' ? shownFrame() : S.frame) && S.mode !== 'stack'));
    b.classList.toggle('is-ref', (S.mode === 'blink' || S.mode === 'diff') && i === S.ref);
  }
  for (const tr of document.querySelectorAll('#visits tbody tr')) tr.classList.toggle('is-current', Number(tr.dataset.i) === f && S.mode !== 'stack');
}

function render() { draw(); updateText(); }

function paintThumb(canvas, view, i, crop = 1) {
  const n = view.n;
  const tmp = document.createElement('canvas');
  tmp.width = tmp.height = n;
  const ctx = tmp.getContext('2d'), image = ctx.createImageData(n, n);
  paintGray(image, view.data[i], view.sat && view.sat[i], view, view === S.view ? gainNow() : view.autoGain);
  ctx.putImageData(image, 0, 0);
  const span = n * crop, off = (n - span) / 2, out = canvas.getContext('2d');
  out.imageSmoothingEnabled = true;
  out.drawImage(tmp, off, off, span, span, 0, 0, canvas.width, canvas.height);
}

function buildStrip() {
  const v = S.view, strip = $('strip');
  strip.innerHTML = '';
  v.frames.forEach((frame, i) => {
    const li = document.createElement('li'), b = document.createElement('button'), c = document.createElement('canvas');
    c.width = c.height = 168;
    b.type = 'button';
    b.dataset.i = i;
    b.append(c, frame.date, document.createElement('br'), `${frame.images} images`);
    b.addEventListener('click', () => { S.frame = i; S.blinkOn = true; setPlaying(false); render(); });
    li.append(b);
    strip.append(li);
    paintThumb(c, v, i);
  });
  const ref = $('ref');
  ref.innerHTML = v.frames.map((fr, i) => `<option value="${i}">${escapeHtml(fr.date)}</option>`).join('');
  ref.value = String(S.ref);
}

function buildTable() {
  const v = S.view;
  const moving = movesVisibly();
  const head = ['Visit', 'Days covered', 'Images used', 'Wavelengths (µm)', moving ? 'Moved since first visit' : null, 'Brightness', 'Flags at the target (images)'].filter(Boolean);
  const body = v.frames.map((fr, i) => {
    const cells = [fr.date, fr.days.toFixed(1), `${fr.images} of ${fr.available}`, `${fr.wl[0].toFixed(2)} to ${fr.wl[1].toFixed(2)}`];
    if (moving) {
      const s = shift(i, 0);
      cells.push(i === 0 ? 'reference' : `${s.measured === null ? 'not measurable' : 'measured ' + s.measured.toFixed(1) + '″'}, catalogue ${s.expected.toFixed(1)}″`);
    }
    cells.push(brightnessText(i), Object.entries(fr.flags).map(([name, count]) => `${name} (${count})`).join(', ') || 'none');
    return `<tr data-i="${i}">${cells.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`;
  });
  $('visits').innerHTML = `<thead><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${body.join('')}</tbody>`;
  const notes = [
    v.band === 0
      ? 'Each visit is the average of the six detectors, matched date by date; a pixel is shown as saturated when any detector saturates it.'
      : 'Each visit is the median of up to 12 images from detector D' + v.band + '.',
  ];
  if (v.meta.failures) notes.push(`${v.meta.failures} image(s) could not be downloaded from the archive and were left out.`);
  if (v.meta.skipped) notes.push(`${v.meta.skipped} short visit(s) with fewer than 3 images were left out.`);
  if (v.meta.built) notes.push(`Computed on ${v.meta.built} from ${v.meta.records} images in the archive.`);
  $('visits-note').textContent = notes.join(' ');
}

function buildRuler() {
  const ruler = $('ruler');
  ruler.innerHTML = '';
  for (const [band, info] of Object.entries(BANDS)) {
    const b = document.createElement('button');
    b.type = 'button';
    b.style.flex = `${(info.range[1] - info.range[0]).toFixed(2)} 1 0`;
    b.style.background = info.color;
    if (Number(band) >= 4) b.classList.add('long');
    b.innerHTML = `D${band}<small>${info.range[0].toFixed(2)}–${info.range[1].toFixed(2)}</small>`;
    b.title = `Detector ${band}: ${info.range[0].toFixed(2)} to ${info.range[1].toFixed(2)} µm`;
    b.dataset.band = band;
    b.addEventListener('click', () => chooseBand(Number(band)));
    ruler.append(b);
  }
}
function markRuler() {
  for (const b of document.querySelectorAll('#ruler button')) {
    const band = Number(b.dataset.band);
    b.setAttribute('aria-pressed', String(S.view && band === S.view.band));
    b.disabled = Boolean(S.entry && !S.entry.bands.includes(band));
  }
  const sum = $('ov-sum');
  sum.checked = Boolean(S.view && S.view.band === 0);
  sum.disabled = !S.entry;
  $('sum-help').hidden = !(S.view && S.view.band === 0);
}

function setMode(mode) {
  S.mode = mode;
  for (const b of document.querySelectorAll('.segments button')) b.setAttribute('aria-pressed', String(b.dataset.mode === mode));
  $('mode-help').textContent = MODE_HELP[mode];
  $('compare').hidden = !(mode === 'blink' || mode === 'diff');
  if ((mode === 'blink' || mode === 'diff') && S.view && S.frame === S.ref) S.frame = S.view.frames.length - 1 === S.ref ? 0 : S.view.frames.length - 1;
  S.blinkOn = true;
  restartTimer();
  syncUrl();
  if (S.view) render();
}

function setPlaying(on) {
  S.playing = on;
  $('play').textContent = on ? 'Pause' : 'Play';
  $('bigplay').hidden = on || !reducedMotion || S.started;
  restartTimer();
}
function tick() {
  const v = S.view;
  if (!v || v.frames.length < 2) return;
  if (S.mode === 'blink') S.blinkOn = !S.blinkOn;
  else if (S.mode === 'play') S.frame = (S.frame + 1) % v.frames.length;
  else if (S.mode === 'diff') { do { S.frame = (S.frame + 1) % v.frames.length; } while (S.frame === S.ref); }
  render();
}
function restartTimer() {
  clearInterval(S.timer);
  S.timer = null;
  if (S.playing && S.mode !== 'stack') S.timer = setInterval(tick, S.mode === 'blink' ? Math.max(300, S.speed * 0.7) : S.speed);
}
function step(by) {
  const v = S.view;
  if (!v) return;
  setPlaying(false);
  S.blinkOn = true;
  do { S.frame = (S.frame + by + v.frames.length) % v.frames.length; } while (S.mode === 'diff' && S.frame === S.ref && v.frames.length > 1);
  render();
}

// ---------------------------------------------------------------- charts

function niceTicks(lo, hi, count = 5) {
  const span = hi - lo || 1, raw = span / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const stepSize = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let t = Math.ceil(lo / stepSize) * stepSize; t <= hi + 1e-9; t += stepSize) ticks.push(Number(t.toPrecision(12)));
  return ticks;
}

// spec: {x: {min, max, ticks, fmt, title}, y: {min, max, ticks, fmt, title}, stripes, hline, series: [{color, line, pts}]}
function drawChart(canvas, spec) {
  const dpr = sizeCanvas(canvas), ctx = canvas.getContext('2d');
  const w = canvas.width / dpr, h = canvas.height / dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const box = { l: 62, r: 16, t: spec.stripes ? 30 : 14, b: 44 };
  const X = (x) => box.l + (x - spec.x.min) / (spec.x.max - spec.x.min) * (w - box.l - box.r);
  const Y = (y) => h - box.b - (y - spec.y.min) / (spec.y.max - spec.y.min) * (h - box.t - box.b);
  ctx.font = '12.5px "IBM Plex Sans", sans-serif';

  for (const s of spec.stripes || []) {
    ctx.globalAlpha = s.strong ? 0.2 : 0.08;
    ctx.fillStyle = s.color;
    ctx.fillRect(X(s.x0), box.t, X(s.x1) - X(s.x0), h - box.t - box.b);
    ctx.globalAlpha = 1;
    ctx.fillRect(X(s.x0), box.t - 5, X(s.x1) - X(s.x0), 3);
    ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    ctx.fillStyle = s.strong ? COLORS.paper : COLORS.dim;
    ctx.fillText(s.label, (X(s.x0) + X(s.x1)) / 2, box.t - 8);
  }
  ctx.strokeStyle = COLORS.rule; ctx.lineWidth = 1; ctx.fillStyle = COLORS.dim;
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  for (const t of spec.y.ticks) {
    ctx.beginPath(); ctx.moveTo(box.l, Y(t) + 0.5); ctx.lineTo(w - box.r, Y(t) + 0.5); ctx.stroke();
    ctx.fillText(spec.y.fmt(t), box.l - 8, Y(t));
  }
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  for (const t of spec.x.ticks) {
    ctx.beginPath(); ctx.moveTo(X(t) + 0.5, h - box.b); ctx.lineTo(X(t) + 0.5, h - box.b + 5); ctx.stroke();
    ctx.fillText(spec.x.fmt(t), X(t), h - box.b + 8);
  }
  ctx.fillStyle = COLORS.paper;
  ctx.fillText(spec.x.title, (box.l + w - box.r) / 2, h - 17);
  ctx.save(); ctx.translate(15, (box.t + h - box.b) / 2); ctx.rotate(-Math.PI / 2); ctx.textBaseline = 'middle'; ctx.fillText(spec.y.title, 0, 0); ctx.restore();
  if (spec.hline !== undefined) {
    ctx.setLineDash([5, 4]); ctx.strokeStyle = COLORS.dim;
    ctx.beginPath(); ctx.moveTo(box.l, Y(spec.hline) + 0.5); ctx.lineTo(w - box.r, Y(spec.hline) + 0.5); ctx.stroke();
    ctx.setLineDash([]);
  }

  const hits = [];
  ctx.save();
  ctx.beginPath(); ctx.rect(box.l, box.t, w - box.l - box.r, h - box.t - box.b); ctx.clip();
  for (const s of spec.series) {
    if (s.line && s.pts.length > 1) {
      ctx.strokeStyle = s.color; ctx.lineWidth = 1.5; ctx.globalAlpha = 0.75;
      ctx.beginPath();
      s.pts.forEach((p, i) => (i ? ctx.lineTo(X(p.x), Y(p.y)) : ctx.moveTo(X(p.x), Y(p.y))));
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    for (const p of s.pts) {
      const px = X(p.x), py = Y(p.y), color = p.color || s.color;
      if (p.e) { ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(px, Y(p.y - p.e)); ctx.lineTo(px, Y(p.y + p.e)); ctx.stroke(); }
      ctx.beginPath(); ctx.arc(px, py, s.radius || 3.5, 0, 2 * Math.PI);
      if (p.hollow) { ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke(); } else { ctx.fillStyle = color; ctx.fill(); }
      hits.push({ x: px, y: py, tip: p.tip });
    }
  }
  ctx.restore();
  let lx = box.l + 10;
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  for (const item of spec.legend || []) { // a row of colour keys along the top of the plot
    ctx.fillStyle = item.color;
    ctx.fillRect(lx, box.t + 8, 10, 10);
    ctx.fillStyle = COLORS.paper;
    ctx.fillText(item.label, lx + 14, box.t + 13.5);
    lx += 24 + ctx.measureText(item.label).width;
  }
  canvas.hits = hits;
}

function seasonColor(t) { // early visits blue, late visits amber
  const mix = (a, b, u) => Math.round(a + (b - a) * u);
  const stops = [[90, 200, 255], [236, 230, 214], [255, 179, 71]];
  const u = clamp(t, 0, 1) * 2, i = Math.min(1, Math.floor(u)), f = u - i;
  return `rgb(${mix(stops[i][0], stops[i + 1][0], f)},${mix(stops[i][1], stops[i + 1][1], f)},${mix(stops[i][2], stops[i + 1][2], f)})`;
}

function chartPoints() {
  const pts = S.target.points.map(([mjd, band, wl, flux, err, sat, ring]) => ({ mjd, band, wl, flux, err, sat: Boolean(sat), ring }));
  const ringMode = pts.length > 0 && pts.filter((p) => p.sat).length > pts.length / 2;
  return { pts, ringMode, value: (p) => (ringMode ? p.ring : p.sat ? null : p.flux) };
}

function drawSpectrum() {
  const { pts, ringMode, value } = chartPoints();
  const shown = pts.filter((p) => value(p) !== null);
  const note = $('spectrum-note');
  if (!shown.length) { drawChart($('spectrum'), emptySpec('Wavelength (µm)', 'Brightness (mJy)')); note.textContent = 'No brightness could be measured here.'; return; }
  const t0 = Math.min(...shown.map((p) => p.mjd)), t1 = Math.max(...shown.map((p) => p.mjd));
  const values = shown.map(value).sort((a, b) => a - b);
  const top = values[Math.floor(values.length * 0.98)] * 1.25, bottom = Math.min(0, values[Math.floor(values.length * 0.02)] * 1.25);
  drawChart($('spectrum'), {
    x: { min: 0.65, max: 5.1, ticks: [1, 2, 3, 4, 5], fmt: (t) => t.toFixed(0), title: 'Wavelength (µm)' },
    y: { min: bottom, max: top, ticks: niceTicks(bottom, top), fmt: (t) => fmtAxis(t), title: ringMode ? 'Brightness outside the core (mJy)' : 'Brightness (mJy)' },
    stripes: Object.entries(BANDS).map(([band, info]) => ({ x0: info.range[0], x1: info.range[1], color: info.color, label: `D${band}`, strong: S.view && Number(band) === S.view.band })),
    series: [{
      radius: 3,
      pts: shown.map((p) => ({ x: p.wl, y: value(p), color: seasonColor(t1 > t0 ? (p.mjd - t0) / (t1 - t0) : 0.5), tip: `${isoDate(p.mjd)}, ${p.wl.toFixed(3)} µm: ${fmtMjy(value(p))} mJy` })),
    }],
  });
  const missing = pts.length - shown.length;
  note.innerHTML = `Each dot is one SPHEREx image, measured at the target. Blue dots are the earliest visits (${isoDate(t0)}) and amber the latest (${isoDate(t1)}): where the colours separate at the same wavelength, the object changed. `
    + (ringMode ? 'This star saturates the detector, so the dots show the light in a ring just outside its core. That follows the star up and down but is not its total brightness. ' : '')
    + (missing ? `${missing} image(s) gave no usable value${ringMode ? '' : ' because the target was saturated in them'}.` : '');
}

function fmtAxis(t) { const a = Math.abs(t); return a >= 1000 ? `${(t / 1000).toFixed(a >= 10000 ? 0 : 1)}k` : a >= 10 || a === 0 ? t.toFixed(0) : a >= 1 ? t.toFixed(1) : t.toFixed(2); }
function emptySpec(xTitle, yTitle) { return { x: { min: 0, max: 1, ticks: [], fmt: String, title: xTitle }, y: { min: 0, max: 1, ticks: [], fmt: String, title: yTitle }, series: [] }; }

// Brightness per visit and detector, each divided by that detector's first visit.
function drawLightCurve() {
  const { pts, ringMode, value } = chartPoints();
  const series = [];
  let lo = Infinity, hi = -Infinity, yMax = 1.5;
  for (const [band, info] of Object.entries(BANDS)) {
    const mine = pts.filter((p) => p.band === Number(band) && value(p) !== null).sort((a, b) => a.mjd - b.mjd);
    const groups = [];
    for (const p of mine) {
      const g = groups[groups.length - 1];
      if (g && p.mjd - g[g.length - 1].mjd <= 15 && p.mjd - g[0].mjd <= 30) g.push(p); else groups.push([p]);
    }
    const visits = groups.filter((g) => g.length >= 3).map((g) => {
      const vals = g.map(value), mid = median(vals);
      const sd = Math.sqrt(vals.reduce((s, x) => s + (x - mid) * (x - mid), 0) / vals.length);
      return { mjd: median(g.map((p) => p.mjd)), mid, err: sd / Math.sqrt(vals.length), n: g.length };
    });
    if (visits.length < 2 || !(visits[0].mid > 0)) continue;
    const base = visits[0].mid;
    series.push({
      color: info.color, line: true, radius: 4, label: `D${band}`,
      pts: visits.map((v) => ({ x: v.mjd, y: v.mid / base, e: v.err / base, tip: `D${band}, ${isoDate(v.mjd)}: ${(v.mid / base).toFixed(2)} times the first visit (${v.n} images)` })),
    });
    for (const v of visits) { lo = Math.min(lo, v.mjd); hi = Math.max(hi, v.mjd); yMax = Math.max(yMax, v.mid / base * 1.15); }
  }
  const note = $('lightcurve-note');
  if (!series.length) { drawChart($('lightcurve'), emptySpec('Date', 'Brightness, first visit = 1')); note.textContent = 'Not enough visits to compare.'; return; }
  yMax = Math.min(yMax, 6);
  const pad = (hi - lo) * 0.05 || 10, months = [];
  const start = mjdToDate(lo - pad), every = Math.max(1, Math.ceil((hi - lo) / 30 / 6));
  for (let d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1)); d / 86400000 + 40587 <= hi + pad; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + every, 1))) months.push(d / 86400000 + 40587);
  drawChart($('lightcurve'), {
    x: { min: lo - pad, max: hi + pad, ticks: months, fmt: (t) => mjdToDate(t).toISOString().slice(0, 7), title: 'Date' },
    y: { min: 0, max: yMax, ticks: niceTicks(0, yMax), fmt: (t) => t.toFixed(1), title: 'Brightness, first visit = 1' },
    hline: 1, series, legend: series.map((s) => ({ color: s.color, label: s.label })),
  });
  note.innerHTML = 'One line per detector. Each point is the median of one visit divided by the first visit, so a steady object stays on the dashed line. '
    + (ringMode ? 'Measured outside the saturated core: a steady star (Barnard\'s Star) still wanders by about 20% this way, so only larger changes are real.' : 'Bars show the scatter between the images of a visit.');
}

function drawCharts() { if (S.target) { drawSpectrum(); drawLightCurve(); } }

function chartHover(event) {
  const canvas = event.currentTarget, rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left, y = event.clientY - rect.top;
  let best = null, bestD = 14;
  for (const h of canvas.hits || []) { const d = Math.hypot(h.x - x, h.y - y); if (d < bestD) { bestD = d; best = h; } }
  const tip = $('tip');
  tip.hidden = !best;
  if (best) { tip.textContent = best.tip; tip.style.left = `${Math.min(event.clientX + 14, window.innerWidth - tip.offsetWidth - 8)}px`; tip.style.top = `${event.clientY + 14}px`; }
}

// ---------------------------------------------------------------- other telescopes (Aladin Lite, CDS)

function showElsewhere() {
  const T = S.target;
  if (!window.A || !T) return;
  const place = () => {
    S.aladin.setFoV(T.fov * 2);
    S.aladin.gotoRaDec(T.ra, T.dec);
    if (S.aladinCat) S.aladinCat.removeAll();
    else { S.aladinCat = window.A.catalog({ name: 'Where it is in the SPHEREx images', color: COLORS.amber, sourceSize: 26, shape: 'circle' }); S.aladin.addCatalog(S.aladinCat); }
    S.aladinCat.addSources([window.A.source(T.ra, T.dec, { name: T.label })]);
  };
  if (S.aladin) { place(); return; }
  if (S.aladinStarting) return;
  S.aladinStarting = true;
  window.A.init.then(() => {
    S.aladin = window.A.aladin('#aladin', {
      survey: $('survey').value, fov: T.fov * 2, target: `${T.ra} ${T.dec}`, cooFrame: 'ICRSd',
      showReticle: false, showLayersControl: false, showGotoControl: false, showProjectionControl: false,
      showFullscreenControl: false, showFrame: false, showCooGridControl: false, showSettingsControl: false, showShareControl: false,
    });
    place();
  }).catch((error) => { $('aladin').textContent = 'The sky atlas could not be loaded.'; console.warn(error); });
}

// ---------------------------------------------------------------- loading

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} for ${url}`);
  return response.json();
}
function notice(html, kind) {
  const box = $('notice');
  box.hidden = !html;
  box.className = `notice${kind ? ' ' + kind : ''}`;
  box.innerHTML = html || '';
}
const slugOf = (text) => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
function findEntry(text) {
  const wanted = slugOf(text);
  return S.index.targets.find((t) => [t.slug, slugOf(t.name), slugOf(t.query)].includes(wanted));
}

async function loadView(entry, band) {
  const key = `${entry.slug}|${band}`;
  if (!S.views.has(key)) S.views.set(key, decodeView(await getJSON(`${CONFIG.data}${entry.slug}_d${band}.json`)));
  return S.views.get(key);
}

// ---- summed view: a broadband composite of all six detectors ----
// Each saved detector has the same 3" north-up grid, so visits taken on the
// same dates (matched within a few days) can be averaged pixel by pixel.
// This is the challenge's "summing detector arrays" consideration: more
// signal, one picture from 0.75 to 5 um. Only the saved targets have all six
// detectors on hand, so live queries fall back to single detectors.
const SUM_TOLERANCE_DAYS = 5;

function summarizeSummedFrame(anchor, parts) {
  const flags = {};
  let wl0 = Infinity, wl1 = -Infinity, images = 0, available = Infinity;
  let mx = 0, my = 0, nm = 0, cx = 0, cy = 0, nc = 0;
  for (const { frame } of parts) {
    for (const [name, count] of Object.entries(frame.flags)) flags[name] = (flags[name] || 0) + count;
    wl0 = Math.min(wl0, frame.wl[0]); wl1 = Math.max(wl1, frame.wl[1]);
    images += frame.images; available = Math.min(available, frame.available);
    mx += frame.marker[0]; my += frame.marker[1]; nm++;
    if (frame.centroid) { cx += frame.centroid[0]; cy += frame.centroid[1]; nc++; }
  }
  return {
    date: anchor.date, mjd: anchor.mjd, year: anchor.year, days: anchor.days,
    images, available, wl: [wl0, wl1], flags,
    marker: [mx / nm, my / nm],
    centroid: nc ? [cx / nc, cy / nc] : null,
    brightness: null,
  };
}

async function buildSummedView(entry) {
  const views = await Promise.all(entry.bands.map((b) => loadView(entry, b)));
  const base = views[0], n = base.n, size = n * n;
  if (!views.every((v) => v.n === n)) throw new Error('the saved detectors have different grids');
  const frames = [], data = [], sat = [];
  for (const anchor of base.frames) {
    const parts = [];
    for (const v of views) {
      let best = null, bestD = SUM_TOLERANCE_DAYS;
      for (const f of v.frames) { const d = Math.abs(f.mjd - anchor.mjd); if (d < bestD) { bestD = d; best = f; } }
      if (best) parts.push({ view: v, frame: best });
    }
    if (!parts.length) continue;
    const sum = new Float32Array(size), count = new Float32Array(size);
    let anySat = null;
    for (const { view, frame } of parts) {
      const i = view.frames.indexOf(frame), arr = view.data[i];
      for (let k = 0; k < size; k++) if (arr[k] === arr[k]) { sum[k] += arr[k]; count[k]++; }
      const s = view.sat && view.sat[i];
      if (s) {
        if (!anySat) anySat = new Uint8Array(size);
        for (let k = 0; k < size; k++) if (s[k]) anySat[k] = 1;
      }
    }
    const mean = new Float32Array(size);
    for (let k = 0; k < size; k++) mean[k] = count[k] ? sum[k] / count[k] : NaN;
    frames.push(summarizeSummedFrame(anchor, parts));
    data.push(fillHoles(mean, n));
    sat.push(anySat);
  }
  if (frames.length < 2) throw new Error('the saved visits do not overlap between detectors');
  const stats = data.map(robust);
  const sigma = median(stats.map((s) => s.sigma)) || 1e-6;
  const low = median(stats.map((s) => s.median)) - 1.5 * sigma;
  const high = Math.max(...stats.map((s) => quantile(s.sorted, 0.997)), low + 10 * sigma);
  const autoGain = clamp(0.0104 * (high - low) / sigma, 1, 40);
  return {
    band: 0, n, frames, data, sat,
    raw: data.map((a) => Float32Array.from(a)),
    low, high, sigma, autoGain,
    smoothed: data.map((a) => blur(a, n)), stack: medianStack(data),
    meta: { summed: true, built: base.meta.built, records: base.meta.records, failures: base.meta.failures, skipped: base.meta.skipped },
  };
}

async function openSummed(entry, background = false) {
  if (!background) notice('');
  try {
    const key = `${entry.slug}|sum`;
    if (!S.views.has(key)) S.views.set(key, await buildSummedView(entry));
    show(S.target, S.views.get(key), entry, background);
  } catch (error) {
    console.warn('summed view:', error);
    notice(`The summed view could not be built (${escapeHtml(error.message)}).`, 'error');
  }
}

function chooseSummed() {
  if (!S.view || S.view.band === 0) return;
  if (S.entry) return openSummed(S.entry);
  notice('The sum of all six detectors is available for the five saved test targets. For other positions, pick one detector at a time.');
}

function show(target, view, entry, keepUrl = false) {
  const sameField = S.target === target;
  S.target = target; S.entry = entry; S.view = view;
  if (!sameField) { S.zoom = 1; S.cx = S.cy = view.n / 2; S.ref = 0; S.frame = 0; S.gain = 0; $('gain').value = '0'; }
  S.frame = clamp(S.frame, 0, view.frames.length - 1);
  S.ref = clamp(S.ref, 0, view.frames.length - 1);
  if ((S.mode === 'blink' || S.mode === 'diff') && S.frame === S.ref && view.frames.length > 1) S.frame = view.frames.length - 1 === S.ref ? 0 : view.frames.length - 1;
  S.bufKey = '';
  $('name').textContent = entry ? entry.name : target.label;
  $('about').textContent = entry ? entry.about : (hasMotion() ? 'Found by name in SIMBAD' : 'A position you entered');
  document.title = `${$('name').textContent} | nejma`;
  $('ov-gaia').disabled = !target.gaia.stars.length;
  $('ov-sat').disabled = !view.sat;
  $('ov-marker').closest('label').lastChild.textContent = hasMotion() ? 'Expected position, from the catalogue motion' : 'The position you asked for';
  buildStrip(); buildTable(); markRuler(); restartTimer(); render(); drawCharts();
  if (!keepUrl) syncUrl();
  if (!sameField) showElsewhere();
}

// `background` shows the entry behind a notice about something else, without touching the search box or the address.
async function openEntry(entry, band, background = false) {
  if (!background) { notice(''); $('q').value = entry.query; }
  try {
    const wanted = entry.bands.includes(band) ? band : entry.band;
    const [target, view] = await Promise.all([
      S.entry === entry && S.target ? S.target : getJSON(`${CONFIG.data}${entry.slug}.json`),
      loadView(entry, wanted),
    ]);
    show(target, view, entry, background);
  } catch (error) {
    notice(`The saved images for ${entry.name} could not be loaded (${error.message}).`, 'error');
  }
}

async function chooseBand(band) {
  if (!S.view || band === S.view.band) return;
  if (S.entry) return openEntry(S.entry, band);
  return lookLive($('q').value.trim(), Number($('fov').value), band);
}

function liveLink(text, fov, band) {
  if (!CONFIG.streamlit) return null;
  const q = new URLSearchParams({ target: text, fov: String(fov), band: String(band) });
  return `${CONFIG.streamlit}?${q}`;
}

async function lookLive(text, fov, band) {
  const fallback = liveLink(text, fov, band);
  if (!CONFIG.api) {
    notice(`<strong>${escapeHtml(text)}</strong> is not one of the saved test targets, so its images have to be fetched from the SPHEREx archive, which takes one to three minutes.${fallback ? ` <a href="${fallback}">Fetch it in the live viewer</a>.` : ' Please try again in a few minutes.'}`);
    return;
  }
  notice(`<strong>${escapeHtml(text)}</strong>: <span id="job-message">Waking the server and asking the SPHEREx archive for its images.</span> The first look at a new position takes a few minutes.<progress id="job"></progress>`);
  try {
    const q = new URLSearchParams({ q: text, fov: String(fov), band: String(band) });
    let job = await getJSON(`${CONFIG.api}/view?${q}`);
    while (job.state === 'working') {
      const bar = $('job');
      if (bar && job.total) { bar.max = job.total; bar.value = job.done; }
      if (job.message && $('job-message')) $('job-message').textContent = job.message;
      await new Promise((r) => setTimeout(r, 1500));
      job = await getJSON(`${CONFIG.api}/job/${job.id}`);
    }
    if (job.state !== 'done') throw new Error(job.message || 'the archive did not answer');
    notice('');
    show(S.target && !S.entry && S.target.query === job.target.query ? Object.assign(S.target, { points: mergePoints(S.target.points, job.target.points) }) : job.target, decodeView(job.view), null);
  } catch (error) {
    notice(`That did not work: ${escapeHtml(error.message)}.${fallback ? ` <a href="${fallback}">Try the live viewer instead</a>.` : ' Please try again later.'}`, 'error');
  }
}
function mergePoints(a, b) { const seen = new Set(a.map((p) => p.join())); return a.concat(b.filter((p) => !seen.has(p.join()))); }

function look(text, fov, band) {
  if (!text) return;
  const entry = findEntry(text);
  if (entry && Math.abs(fov - S.index.fov) < 1e-9) return openEntry(entry, band || entry.band);
  return lookLive(text, fov, band || 2);
}

function syncUrl() {
  if (!S.view) return;
  const q = new URLSearchParams();
  q.set('target', S.entry ? S.entry.query : S.target.query);
  q.set('fov', String(S.target.fov));
  q.set('band', S.view.band === 0 ? 'sum' : String(S.view.band));
  q.set('mode', S.mode);
  if (params.has('embed')) q.set('embed', params.get('embed'));
  history.replaceState(null, '', `?${q}`);
}

// ---------------------------------------------------------------- the five test targets, playing side by side

async function buildGallery() {
  const list = $('gallery');
  for (const entry of S.index.targets) {
    const li = document.createElement('li'), b = document.createElement('button'), c = document.createElement('canvas');
    c.width = c.height = 360;
    b.type = 'button';
    b.innerHTML = `<span class="g-name">${escapeHtml(entry.name)}</span><span class="g-about">${escapeHtml(entry.about)}</span><span class="g-result"></span>`;
    b.prepend(c);
    b.addEventListener('click', () => { openEntry(entry, entry.band); window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' }); });
    li.append(b);
    list.append(li);
    try {
      const view = await loadView(entry, entry.band);
      const item = { canvas: c, view, i: 0 };
      S.gallery.push(item);
      paintThumb(c, view, 0, 0.6);
      b.querySelector('.g-result').textContent = galleryResult(view);
    } catch (error) { console.warn(error); }
  }
  setInterval(() => {
    if (document.hidden || reducedMotion) return;
    for (const item of S.gallery) { item.i = (item.i + 1) % item.view.frames.length; paintThumb(item.canvas, item.view, item.i, 0.6); }
  }, 800);
}
function galleryResult(view) {
  const frames = view.frames, first = frames[0], last = frames[frames.length - 1];
  const expected = Math.hypot(last.marker[0] - first.marker[0], last.marker[1] - first.marker[1]) * 3;
  const days = Math.round(last.mjd - first.mjd);
  if (expected >= 1) {
    const seen = frames.filter((f) => f.centroid); // the visits in which the object is clear enough to locate
    if (seen.length >= 2) {
      const a = seen[0], b = seen[seen.length - 1];
      const measured = Math.hypot(b.centroid[0] - a.centroid[0], b.centroid[1] - a.centroid[1]) * 3;
      const predicted = Math.hypot(b.marker[0] - a.marker[0], b.marker[1] - a.marker[1]) * 3;
      return `Measured ${measured.toFixed(1)}″ of motion in ${Math.round(b.mjd - a.mjd)} days; the catalogue predicts ${predicted.toFixed(1)}″.`;
    }
    return `The catalogue predicts ${expected.toFixed(1)}″ of motion in ${days} days; too faint here to measure.`;
  }
  const withValue = frames.filter((f) => f.brightness && f.brightness.mjy > 0);
  if (withValue.length >= 2) {
    const ratios = withValue.map((f) => f.brightness.mjy / withValue[0].brightness.mjy);
    const extreme = ratios.reduce((a, b) => (Math.abs(Math.log(b)) > Math.abs(Math.log(a)) ? b : a), 1);
    const rough = withValue[0].brightness.kind === 'ring' ? ' (rough, outside the saturated core)' : '';
    return `Brightness reached ${extreme.toFixed(2)} times the first visit${rough}.`;
  }
  return '';
}

// ---------------------------------------------------------------- wiring

function pointerToImage(event) {
  const canvas = $('sky'), rect = canvas.getBoundingClientRect(), tf = S.tf;
  const px = (event.clientX - rect.left) * canvas.width / rect.width, py = (event.clientY - rect.top) * canvas.height / rect.height;
  return [tf.sx + px / tf.k - 0.5, tf.sy + py / tf.k - 0.5, px, py];
}
function zoomAt(factor, px, py) {
  const v = S.view, canvas = $('sky');
  if (!v || !S.tf) return;
  if (px === undefined) { px = canvas.width / 2; py = canvas.height / 2; }
  const ix = S.tf.sx + px / S.tf.k, iy = S.tf.sy + py / S.tf.k;
  S.zoom = clamp(S.zoom * factor, 1, 12);
  const span = v.n / S.zoom, k = canvas.width / span;
  S.cx = ix - px / k + span / 2;
  S.cy = iy - py / k + span / 2;
  $('plate').classList.toggle('zoomed', S.zoom > 1);
  draw();
}

function wire() {
  const canvas = $('sky');
  $('search').addEventListener('submit', (event) => { event.preventDefault(); look($('q').value.trim(), Number($('fov').value), S.view ? S.view.band : 0); });
  for (const b of document.querySelectorAll('.segments button')) b.addEventListener('click', () => setMode(b.dataset.mode));
  $('play').addEventListener('click', () => { S.started = true; setPlaying(!S.playing); });
  $('bigplay').addEventListener('click', () => { S.started = true; setPlaying(true); });
  $('prev').addEventListener('click', () => step(-1));
  $('next').addEventListener('click', () => step(1));
  $('speed').addEventListener('input', (e) => { S.speed = 2300 - Number(e.target.value); restartTimer(); });
  $('reset').addEventListener('click', () => { S.zoom = 1; S.cx = S.cy = S.view.n / 2; $('plate').classList.remove('zoomed'); draw(); });
  $('ref').addEventListener('change', (e) => { S.ref = Number(e.target.value); if (S.frame === S.ref) S.frame = (S.ref + 1) % S.view.frames.length; render(); });
  $('ov-marker').addEventListener('change', (e) => { S.marker = e.target.checked; draw(); });
  $('ov-gaia').addEventListener('change', (e) => { S.gaia = e.target.checked; $('gaia-more').hidden = !S.gaia; draw(); });
  $('ov-sat').addEventListener('change', (e) => { S.sat = e.target.checked; draw(); });
  $('ov-sum').addEventListener('change', (e) => { if (e.target.checked) chooseSummed(); else if (S.entry) openEntry(S.entry, S.entry.band); e.target.blur(); });
  $('gmag').addEventListener('input', (e) => { S.gmag = Number(e.target.value); $('gmag-out').textContent = e.target.value; draw(); });
  $('gain').addEventListener('input', (e) => { S.gain = Number(e.target.value); render(); document.querySelectorAll('#strip canvas').forEach((c, i) => paintThumb(c, S.view, i)); });
  $('smooth').addEventListener('change', (e) => { S.smooth = e.target.checked; draw(); });
  $('survey').addEventListener('change', (e) => {
    if (!S.aladin) return;
    if (S.aladin.setBaseImageLayer) S.aladin.setBaseImageLayer(e.target.value); else S.aladin.setImageSurvey(e.target.value);
  });
  $('copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); $('copy').textContent = 'Link copied'; }
    catch { $('copy').textContent = 'Copy it from the address bar'; }
    setTimeout(() => { $('copy').textContent = 'Copy a link to this view'; }, 1800);
  });

  // zoom with the wheel only once the image has been clicked, so that scrolling the page still works
  canvas.addEventListener('wheel', (event) => {
    if (document.activeElement !== canvas || !S.view) return;
    event.preventDefault();
    const [, , px, py] = pointerToImage(event);
    zoomAt(Math.exp(-event.deltaY * 0.0015), px, py);
  }, { passive: false });
  canvas.addEventListener('dblclick', (event) => { const [, , px, py] = pointerToImage(event); zoomAt(2, px, py); });
  canvas.addEventListener('pointerdown', (event) => { if (S.zoom > 1) { S.drag = { x: event.clientX, y: event.clientY, cx: S.cx, cy: S.cy }; canvas.setPointerCapture(event.pointerId); } });
  canvas.addEventListener('pointerup', () => { S.drag = null; });
  canvas.addEventListener('pointermove', (event) => {
    if (!S.view || !S.tf) return;
    if (S.drag) {
      const scale = canvas.width / canvas.getBoundingClientRect().width / S.tf.k, span = S.view.n / S.zoom;
      S.cx = clamp(S.drag.cx - (event.clientX - S.drag.x) * scale, span / 2, S.view.n - span / 2);
      S.cy = clamp(S.drag.cy - (event.clientY - S.drag.y) * scale, span / 2, S.view.n - span / 2);
      draw();
      return;
    }
    const [x, y] = pointerToImage(event), v = S.view, col = Math.round(x), row = Math.round(y), box = $('hover');
    if (col < 0 || row < 0 || col >= v.n || row >= v.n) { box.hidden = true; return; }
    const [ra, dec] = unproject(x, y), f = shownFrame(), i = row * v.n + col;
    const value = S.mode === 'stack' ? v.stack[i] : v.raw[f][i];
    const saturated = S.mode !== 'stack' && v.sat && v.sat[f][i];
    const fromTarget = Math.hypot(x - v.frames[f].marker[0], y - v.frames[f].marker[1]) * S.target.arcsec;
    box.hidden = false;
    box.textContent = `RA ${ra.toFixed(5)}°  Dec ${dec >= 0 ? '+' : ''}${dec.toFixed(5)}°   ${saturated ? 'saturated' : value === value ? value.toFixed(3) + ' MJy/sr' : 'no data'}   ${fromTarget.toFixed(0)}″ from the expected position`;
  });
  canvas.addEventListener('pointerleave', () => { $('hover').hidden = true; });
  document.addEventListener('keydown', (event) => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName) || event.ctrlKey || event.metaKey || event.altKey || !S.view) return;
    const k = event.key;
    if (k === ' ' && event.target.tagName !== 'BUTTON') { event.preventDefault(); S.started = true; setPlaying(!S.playing); }
    else if (k === 'ArrowLeft') step(-1);
    else if (k === 'ArrowRight') step(1);
    else if (k === '+' || k === '=') zoomAt(1.5);
    else if (k === '-') zoomAt(1 / 1.5);
    else if (k >= '1' && k <= '6') chooseBand(Number(k));
  });
  for (const id of ['spectrum', 'lightcurve']) { $(id).addEventListener('mousemove', chartHover); $(id).addEventListener('mouseleave', () => { $('tip').hidden = true; }); }
  window.addEventListener('aladin-ready', showElsewhere);
  let resizing = 0;
  window.addEventListener('resize', () => { clearTimeout(resizing); resizing = setTimeout(() => { draw(); drawCharts(); }, 120); });
}

async function start() {
  if (params.has('embed')) document.body.classList.add('embed');
  buildRuler();
  wire();
  const mode = params.get('mode');
  S.mode = { animation: 'play', difference: 'diff' }[mode] || (MODE_HELP[mode] ? mode : 'play');
  setMode(S.mode);
  setPlaying(S.playing);
  try {
    S.index = await getJSON(`${CONFIG.data}index.json`);
  } catch (error) {
    notice(`The saved test targets could not be loaded (${error.message}).`, 'error');
    return;
  }
  const fov = Number(params.get('fov')) || S.index.fov;
  $('fov').value = [0.05, 0.1, 0.2, 0.3].includes(fov) ? String(fov) : '0.1';
  const asked = params.get('ra') && params.get('dec') ? `${params.get('ra')} ${params.get('dec')}` : params.get('target');
  const wantsSum = params.get('band') === 'sum';
  const band = wantsSum ? 0 : Number(params.get('band')) || 0;
  if (asked && !findEntry(asked)) {
    $('q').value = asked;
    await look(asked, Number($('fov').value), BANDS[band] ? band : 2);
    if (!S.view) await openEntry(S.index.targets[0], S.index.targets[0].band, true); // something to look at meanwhile
  } else {
    const entry = asked ? findEntry(asked) : S.index.targets[0];
    await openEntry(entry, BANDS[band] && !wantsSum ? band : entry.band);
    if (wantsSum) await openSummed(entry);
  }
  // first-visit onboarding: one dismissible tip, remembered for the session
  try {
    if (!document.body.classList.contains('embed') && !sessionStorage.getItem('nejma-onboarded')) {
      notice('Welcome to <strong>nejma</strong>. The image plays one frame per SPHEREx visit — pause and step with the buttons under the picture. <em>Difference</em> (on the right) makes anything that moved or changed pop out; pick a detector, or sum all six, by wavelength. Type any object name or coordinates above to look somewhere else. <button id="onboard-ok" type="button">Got it</button>');
      $('onboard-ok').addEventListener('click', () => { try { sessionStorage.setItem('nejma-onboarded', '1'); } catch { /* noop */ } notice(''); });
    }
  } catch { /* noop */ }
  buildGallery();
}

document.addEventListener('DOMContentLoaded', start);
