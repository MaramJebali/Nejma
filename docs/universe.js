// nejma — the landing / navbar / living-background layer.
// The viewer itself (app.js) is untouched; this only orchestrates the
// "universe" chrome around it. Background scenes come from the film engine
// (long-way-home/lwh-main.js), served as ES modules.
'use strict';

import { mountStaticBackground, mountFinaleBackground } from './long-way-home/lwh-main.js';

const landing = document.getElementById('landing');
const landingBg = document.getElementById('landing-bg');
const universeBg = document.getElementById('universe-bg');
const params = new URLSearchParams(location.search);

/* The film's opening keyframe (movement i of The Long Way Home): the lone
   warm star over a faint horizon — the look of the nejma landing. */
const OPENING_FRAME = {
  px: 0, py: -4, pz: 140, rx: 0.26, ry: 0, rz: 0, fov: 72,
  nebula: 0.0, horizon: 0.0, bloom: 0.35, warm: 1.0,
  wx: 6, wy: -10, wz: 60, arc: 0, pl: 0.0,
};

/* ---------- when to skip the landing ---------- */
function skipLanding() {
  if (document.body.classList.contains('embed')) return true;      // ?embed=1
  if (params.has('target') || params.has('q') || params.has('ra')) return true; // deep link to a target
  try {
    return sessionStorage.getItem('nejma-entered') === '1';        // already entered this visit
  } catch { return false; }
}

/* ---------- the living backdrop of the universe page ---------- */
let disposeUniverse = null;
function openUniverse() {
  if (disposeUniverse) return;
  disposeUniverse = mountFinaleBackground(universeBg) || null;
}

function enterUniverse(fromClick) {
  landing.classList.add('entered');
  document.body.classList.add('universe');
  openUniverse();
  if (fromClick) {
    try { sessionStorage.setItem('nejma-entered', '1'); } catch { /* noop */ }
  }
}

function backToLanding() {
  if (!landing.isConnected) return; // landing was skipped (deep link / embed)
  landing.classList.remove('entered');
  document.body.classList.remove('universe');
  try { sessionStorage.removeItem('nejma-entered'); } catch { /* noop */ }
  window.scrollTo({ top: 0, behavior: 'auto' });
}

/* ---------- boot ---------- */
if (skipLanding()) {
  enterUniverse(false);
  landing.remove();
} else {
  mountStaticBackground(landingBg, OPENING_FRAME);
  document.getElementById('start').addEventListener('click', () => enterUniverse(true));
  // the in-page link to a target (e.g. "?target=R Dra&mode=diff") skips the film
  for (const a of landing.querySelectorAll('a[href*="target="]')) {
    a.addEventListener('click', (e) => {
      // navigation reloads the page; remember that the landing was seen
      try { sessionStorage.setItem('nejma-entered', '1'); } catch { /* noop */ }
    });
  }
}
document.getElementById('to-landing').addEventListener('click', backToLanding);

/* ---------- navbar: scroll to sections, track the active one ---------- */
const navLinks = Array.from(document.querySelectorAll('.nejma-capsule .nav-link'));
const sections = navLinks
  .map((b) => document.getElementById('sec-' + b.dataset.section))
  .filter(Boolean);

for (const button of navLinks) {
  button.addEventListener('click', () => {
    const section = document.getElementById('sec-' + button.dataset.section);
    if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

const setActive = (id) => {
  for (const button of navLinks) {
    button.setAttribute('aria-current', button.dataset.section === id ? 'true' : 'false');
  }
};
const observer = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) setActive(entry.target.id.replace('sec-', ''));
    }
  },
  { rootMargin: '-35% 0px -55% 0px' },
);
for (const section of sections) observer.observe(section);
