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


/* ---------- modals (credits & how-to-use guide) ---------- */

const openModal = (id) => {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
};
const closeModal = (modal) => {
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  if (!document.querySelector('.modal:not([hidden])')) document.body.style.overflow = '';
};
for (const trigger of document.querySelectorAll('[data-open]')) {
  trigger.addEventListener('click', () => openModal(trigger.dataset.open));
}
for (const modal of document.querySelectorAll('.modal')) {
  modal.addEventListener('click', (event) => {
    if (event.target.closest('[data-close]')) closeModal(modal);
  });
}
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  for (const modal of document.querySelectorAll('.modal')) closeModal(modal);
});

/* ---------- internationalisation: en / fr / es / ar ---------- */

const I18N = {
  en: {
    eyebrow: 'NASA SPHEREx · a sky that moves',
    sub: "A little window on the infrared sky. Pick a star, a brown dwarf or any point you like, and watch NASA's SPHEREx images of it play back through time — so that anything that moved or changed stands out.",
    start: 'Start exploring',
    guide: 'How to use',
    creditsBtn: 'Credits & acknowledgements',
    hintHTML: 'Prefer to jump straight in? The five challenge targets are <a href="?target=R%20Dra&amp;mode=diff">already playing here</a>.',
    footLineHTML: 'Data: NASA SPHEREx spectral images (NASA/IPAC IRSA) · Gaia (ESA) · SIMBAD (CDS). <button type="button" class="tbtn" data-open="credits-modal">Credits &amp; acknowledgements</button>.',
    contactLineHTML: 'Found something in the sky? Reach the NASA/IPAC IRSA help desk: <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>.',
    creditsTitle: 'Credits & acknowledgements',
    officialNote: 'The notices below are quoted in their official (English) form, as the data providers require.',
    thirdPartyHTML: 'See <a href="https://github.com/MaramJebali/Nejma/blob/main/THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</a> for third-party license information.',
    guideTitle: 'How to use nejma',
    guideIntro: 'Nejma plays NASA SPHEREx images of one patch of sky in time order, so anything that moved or changed stands out. Four steps:',
    guideStepsHTML: '<li><strong>Choose a place.</strong> Type an object name (for example <em>R Dra</em>) or coordinates (<em>248.167 66.755</em> or <em>16:32:40 +66:45:18</em>) in the search box, pick a field of view, and press <em>Look</em>.</li>' +
      '<li><strong>Watch time pass.</strong> The image plays one frame per SPHEREx visit (about every six months). Use <em>Back</em>/<em>Forward</em>, the speed slider, or the play button under the picture.</li>' +
      '<li><strong>Make movers pop.</strong> In the panel on the right, try <em>Blink two</em> (flip between visits) and <em>Difference</em> (one visit minus another). <em>All stacked</em> shows what stays still.</li>' +
      '<li><strong>Change the wavelength.</strong> Pick one of the six detectors on the wavelength ruler, or tick <em>Sum all six detectors</em> for the five saved targets.</li>',
    discoveryHTML: "Found something you didn't expect — a mover, a flare, anything odd? Write to the NASA/IPAC IRSA help desk: <a href=\"mailto:irsa@ipac.caltech.edu\">irsa@ipac.caltech.edu</a>. They can connect you with the SPHEREx science team.",
  },
  fr: {
    eyebrow: 'NASA SPHEREx · un ciel qui bouge',
    sub: "Une petite fenêtre sur le ciel infrarouge. Choisissez une étoile, une naine brune ou n'importe quel point du ciel, et regardez les images SPHEREx de la NASA se rejouer dans le temps — tout ce qui a bougé ou changé ressort.",
    start: 'Commencer l’exploration',
    guide: 'Mode d’emploi',
    creditsBtn: 'Crédits & remerciements',
    hintHTML: 'Vous préférez entrer directement ? Les cinq cibles du défi <a href="?target=R%20Dra&amp;mode=diff">jouent déjà ici</a>.',
    footLineHTML: 'Données : images spectrales SPHEREx (NASA/IPAC IRSA) · Gaia (ESA) · SIMBAD (CDS). <button type="button" class="tbtn" data-open="credits-modal">Crédits &amp; remerciements</button>.',
    contactLineHTML: 'Vous avez trouvé quelque chose dans le ciel ? Écrivez au bureau d’aide NASA/IPAC IRSA : <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>.',
    creditsTitle: 'Crédits & remerciements',
    officialNote: 'Les mentions ci-dessous sont citées dans leur forme officielle (anglaise), comme l’exigent les fournisseurs de données.',
    thirdPartyHTML: 'Voir <a href="https://github.com/MaramJebali/Nejma/blob/main/THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</a> pour les licences tierces.',
    guideTitle: 'Comment utiliser nejma',
    guideIntro: 'Nejma rejoue les images SPHEREx de la NASA d’une même zone du ciel dans l’ordre du temps, si bien que tout objet qui bouge ou change ressort. Quatre étapes :',
    guideStepsHTML: '<li><strong>Choisissez un endroit.</strong> Tapez un nom d’objet (par exemple <em>R Dra</em>) ou des coordonnées (<em>248.167 66.755</em>) dans la boîte de recherche, choisissez un champ de vue et appuyez sur <em>Look</em>.</li>' +
      '<li><strong>Regardez le temps passer.</strong> L’image joue une image par passage de SPHEREx (environ tous les six mois). Utilisez <em>Back</em>/<em>Forward</em>, le curseur de vitesse ou le bouton lecture.</li>' +
      '<li><strong>Faites ressortir les objets mobiles.</strong> Dans le panneau de droite, essayez <em>Blink two</em> (alterner entre deux passages) et <em>Difference</em> (un passage moins un autre). <em>All stacked</em> montre ce qui reste fixe.</li>' +
      '<li><strong>Changez de longueur d’onde.</strong> Choisissez l’un des six détecteurs sur la règle, ou cochez <em>Sum all six detectors</em> pour les cinq cibles enregistrées.</li>',
    discoveryHTML: 'Vous avez repéré quelque chose d’inattendu — un objet mobile, une flare, quoi que ce soit d’étrange ? Écrivez au bureau d’aide NASA/IPAC IRSA : <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>. Ils vous mettront en contact avec l’équipe scientifique SPHEREx.',
  },
  es: {
    eyebrow: 'NASA SPHEREx · un cielo que se mueve',
    sub: 'Una pequeña ventana al cielo infrarrojo. Elige una estrella, una enana marrón o cualquier punto que te guste, y mira cómo las imágenes SPHEREx de la NASA se reproducen en el tiempo: todo lo que se movió o cambió destaca.',
    start: 'Comenzar a explorar',
    guide: 'Cómo usar',
    creditsBtn: 'Créditos y agradecimientos',
    hintHTML: '¿Prefieres entrar directo? Los cinco objetivos del desafío <a href="?target=R%20Dra&amp;mode=diff">ya se están reproduciendo aquí</a>.',
    footLineHTML: 'Datos: imágenes espectrales SPHEREx (NASA/IPAC IRSA) · Gaia (ESA) · SIMBAD (CDS). <button type="button" class="tbtn" data-open="credits-modal">Créditos y agradecimientos</button>.',
    contactLineHTML: '¿Encontraste algo en el cielo? Escríbele al servicio de ayuda de NASA/IPAC IRSA: <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>.',
    creditsTitle: 'Créditos y agradecimientos',
    officialNote: 'Los avisos siguientes se citan en su forma oficial (en inglés), tal como exigen los proveedores de datos.',
    thirdPartyHTML: 'Consulta <a href="https://github.com/MaramJebali/Nejma/blob/main/THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</a> para las licencias de terceros.',
    guideTitle: 'Cómo usar nejma',
    guideIntro: 'Nejma reproduce las imágenes SPHEREx de la NASA de una zona del cielo en orden temporal, así que todo lo que se movió o cambió destaca. Cuatro pasos:',
    guideStepsHTML: '<li><strong>Elige un lugar.</strong> Escribe el nombre de un objeto (por ejemplo <em>R Dra</em>) o coordenadas (<em>248.167 66.755</em>) en el buscador, elige el campo de visión y pulsa <em>Look</em>.</li>' +
      '<li><strong>Mira pasar el tiempo.</strong> La imagen reproduce un fotograma por visita de SPHEREx (cada seis meses aproximadamente). Usa <em>Back</em>/<em>Forward</em>, el control de velocidad o el botón de reproducción.</li>' +
      '<li><strong>Haz resaltar los objetos en movimiento.</strong> En el panel de la derecha prueba <em>Blink two</em> (alternar entre visitas) y <em>Difference</em> (una visita menos otra). <em>All stacked</em> muestra lo que permanece fijo.</li>' +
      '<li><strong>Cambia de longitud de onda.</strong> Elige uno de los seis detectores en la regla, o marca <em>Sum all six detectors</em> para los cinco objetivos guardados.</li>',
    discoveryHTML: '¿Encontraste algo inesperado — un objeto en movimiento, un destello, cualquier cosa extraña? Escribe al servicio de ayuda de NASA/IPAC IRSA: <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>. Ellos te pondrán en contacto con el equipo científico de SPHEREx.',
  },
  ar: {
    eyebrow: 'ناسا سْفيركس · سماءٌ تتحرك',
    sub: 'نافذة صغيرة على السماء تحت الحمراء. اختر نجمًا أو قزمًا بنيًا أو أي نقطة تعجبك، وشاهد صور ناسا من SPHEREx تُعاد عبر الزمن — فبرز كل ما تحرك أو تغيّر.',
    start: 'ابدأ الاستكشاف',
    guide: 'كيف تستعمل',
    creditsBtn: 'الشكر والاعتمادات',
    hintHTML: 'تفضّل الدخول مباشرة؟ الأهداف الخمسة <a href="?target=R%20Dra&amp;mode=diff">تُعرض هنا بالفعل</a>.',
    footLineHTML: 'البيانات: صور SPHEREx الطيفية (NASA/IPAC IRSA) · Gaia (ESA) · SIMBAD (CDS). <button type="button" class="tbtn" data-open="credits-modal">الشكر والاعتمادات</button>.',
    contactLineHTML: 'هل وجدت شيئًا في السماء؟ راسل مكتب مساعدة NASA/IPAC IRSA: <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>.',
    creditsTitle: 'الشكر والاعتمادات',
    officialNote: 'الإشارات أدناه منقولة بصيغتها الرسمية (الإنجليزية) كما تشترط جهات توفير البيانات.',
    thirdPartyHTML: 'انظر <a href="https://github.com/MaramJebali/Nejma/blob/main/THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</a> لتراخيص الطرف الثالث.',
    guideTitle: 'كيف تستعمل نجمى',
    guideIntro: 'نجمى يعرض صور SPHEREx من ناسا لمنطقة واحدة من السماء بترتيب زمني، فيبرز كل ما تحرك أو تغيّر. أربع خطوات:',
    guideStepsHTML: '<li><strong>اختر المكان.</strong> اكتب اسم جرم (مثل <em>R Dra</em>) أو إحداثيات (<em>248.167 66.755</em>) في خانة البحث، واختر مجال الرؤية، ثم اضغط <em>Look</em>.</li>' +
      '<li><strong>شاهد الزمن يمر.</strong> تُعرض صورة واحدة لكل زيارة من زيارات SPHEREx (نحو كل ستة أشهر). استعمل <em>Back</em>/<em>Forward</em> أو مؤشر السرعة أو زر التشغيل.</li>' +
      '<li><strong>أبرز المتحركات.</strong> في اللوحة على اليمين جرّب <em>Blink two</em> (التبديل بين زيارتين) و <em>Difference</em> (زيارة ناقص أخرى). و<em>All stacked</em> يُظهر ما يثبت.</li>' +
      '<li><strong>غيّر الطول الموجي.</strong> اختر أحد الحسّاسات الستة على المسطرة، أو ضع علامة على <em>Sum all six detectors</em> للأهداف الخمسة المحفوظة.</li>',
    discoveryHTML: 'وجدت شيئًا غير متوقع — جرمًا متحركًا أو وميضًا أو أي غرابة؟ راسل مكتب مساعدة NASA/IPAC IRSA: <a href="mailto:irsa@ipac.caltech.edu">irsa@ipac.caltech.edu</a>، وسيصلونك بفريق علم SPHEREx.',
  },
};

const applyLang = (lang) => {
  const dict = I18N[lang] || I18N.en;
  for (const el of document.querySelectorAll('[data-i18n]')) {
    const value = dict[el.dataset.i18n];
    if (typeof value === 'string') el.textContent = value;
  }
  for (const el of document.querySelectorAll('[data-i18n-html]')) {
    const value = dict[el.dataset.i18nHtml];
    if (typeof value === 'string') el.innerHTML = value;
  }
  document.documentElement.lang = lang;
  const rtl = lang === 'ar';
  for (const el of document.querySelectorAll('#landing, .modal-card')) {
    el.dir = rtl ? 'rtl' : 'ltr';
  }
  for (const button of document.querySelectorAll('#lang-switch button')) {
    button.setAttribute('aria-pressed', String(button.dataset.lang === lang));
  }
  try { localStorage.setItem('nejma-lang', lang); } catch { /* private mode */ }
};
let lang = 'en';
try { lang = localStorage.getItem('nejma-lang') || (navigator.language || 'en').slice(0, 2); } catch { /* private mode */ }
applyLang(I18N[lang] ? lang : 'en');
for (const button of document.querySelectorAll('#lang-switch button')) {
  button.addEventListener('click', () => applyLang(button.dataset.lang));
}
