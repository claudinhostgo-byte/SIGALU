/* ============================================================
   SIGALU — site behaviour
   ============================================================ */
(function () {
  'use strict';

  /* ---------- sticky / transparent header ---------- */
  const header = document.querySelector('.site-header');
  if (header && !header.classList.contains('static-solid')) {
    const onScroll = () => {
      if (window.scrollY > 40) header.classList.add('solid');
      else header.classList.remove('solid');
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- mobile menu ---------- */
  const toggle = document.querySelector('.menu-toggle');
  const drawer = document.querySelector('.mobile-nav');
  if (toggle && drawer) {
    toggle.addEventListener('click', () => {
      drawer.classList.toggle('open');
      document.body.style.overflow = drawer.classList.contains('open') ? 'hidden' : '';
    });
    drawer.querySelectorAll('a').forEach((a) =>
      a.addEventListener('click', () => {
        drawer.classList.remove('open');
        document.body.style.overflow = '';
      })
    );
  }

  /* ---------- language toggle (ES default, EN via data-en) ---------- */
  const STORE = 'sigalu-lang';
  const i18nEls = Array.from(document.querySelectorAll('[data-en]'));
  // cache original ES markup
  i18nEls.forEach((el) => { el.dataset.es = el.innerHTML; });
  const phEls = Array.from(document.querySelectorAll('[data-en-ph]'));
  phEls.forEach((el) => { el.dataset.esPh = el.getAttribute('placeholder') || ''; });

  function setLang(lang) {
    const en = lang === 'en';
    i18nEls.forEach((el) => { el.innerHTML = en ? el.dataset.en : el.dataset.es; });
    phEls.forEach((el) => { el.setAttribute('placeholder', en ? el.dataset.enPh : el.dataset.esPh); });
    document.documentElement.lang = lang;
    document.querySelectorAll('.lang button').forEach((b) =>
      b.classList.toggle('active', b.dataset.lang === lang)
    );
    try { localStorage.setItem(STORE, lang); } catch (e) {}
  }
  document.querySelectorAll('.lang button').forEach((b) =>
    b.addEventListener('click', () => setLang(b.dataset.lang))
  );
  let saved = 'es';
  try { saved = localStorage.getItem(STORE) || 'es'; } catch (e) {}
  setLang(saved);

  /* ---------- reveal on scroll ---------- */
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && reveals.length) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
    );
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add('in'));
  }

  /* ---------- KPI count-up ---------- */
  function animateCount(el) {
    const target = parseFloat(el.dataset.count);
    const dec = parseInt(el.dataset.dec || '0', 10);
    const dur = 1500;
    const sep = el.dataset.sep === '1';
    const start = performance.now();
    function fmt(n) {
      let s = n.toFixed(dec);
      if (sep) {
        const parts = s.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        s = parts.join(',');
      }
      return s;
    }
    function step(now) {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = fmt(target);
    }
    requestAnimationFrame(step);
  }
  const counters = document.querySelectorAll('[data-count]');
  if ('IntersectionObserver' in window && counters.length) {
    const cio = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) { animateCount(e.target); cio.unobserve(e.target); }
        });
      },
      { threshold: 0.6 }
    );
    counters.forEach((el) => cio.observe(el));
  } else {
    counters.forEach((el) => { el.textContent = el.dataset.count; });
  }

  /* ---------- goals chart grow ---------- */
  const goalsBox = document.querySelector('.goals');
  if (goalsBox && 'IntersectionObserver' in window) {
    const gio = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            goalsBox.querySelectorAll('.goal-col .bar').forEach((bar) => {
              bar.style.height = bar.dataset.h + '%';
            });
            gio.unobserve(goalsBox);
          }
        });
      },
      { threshold: 0.4 }
    );
    gio.observe(goalsBox);
  } else if (goalsBox) {
    goalsBox.querySelectorAll('.goal-col .bar').forEach((bar) => { bar.style.height = bar.dataset.h + '%'; });
  }

  /* ---------- hero: play clips sequentially (1 → 2 → 1 …) ---------- */
  const vids = document.querySelectorAll('.hero__video video');
  if (vids.length === 2) {
    let active = 0;
    vids.forEach((v) => {
      v.loop = false;            // let 'ended' fire so we can chain clips
      v.muted = true;
      v.style.transition = 'opacity 1.4s ease';
    });
    vids[0].style.opacity = 1;
    vids[1].style.opacity = 0;

    function playNext(e) {
      if (e && e.target !== vids[active]) return; // only the visible clip drives the chain
      const next = active === 0 ? 1 : 0;
      vids[next].currentTime = 0;
      const p = vids[next].play();
      if (p && p.catch) p.catch(() => {});
      vids[next].style.opacity = 1;
      vids[active].style.opacity = 0;
      const prev = active;
      active = next;
      setTimeout(() => { try { vids[prev].pause(); } catch (err) {} }, 1600);
    }
    // start clip 1
    const first = vids[0].play();
    if (first && first.catch) first.catch(() => {});
    vids.forEach((v) => v.addEventListener('ended', playNext));
  }

  /* ---------- contact form (demo) ---------- */
  const form = document.querySelector('form[data-demo]');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      const original = btn.textContent;
      btn.textContent = document.documentElement.lang === 'en' ? 'Message sent ✓' : 'Mensaje enviado ✓';
      btn.disabled = true;
      btn.style.background = 'var(--green-700)';
      setTimeout(() => { btn.textContent = original; btn.disabled = false; form.reset(); }, 2600);
    });
  }
})();
