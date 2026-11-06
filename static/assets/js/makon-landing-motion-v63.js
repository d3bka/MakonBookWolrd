/* MakonBook v63 landing navigation & progressive motion.
   Native anchors and all Django URL routes are preserved. */
(function () {
  'use strict';
  const root = document.documentElement;
  const body = document.body;
  if (!body || !body.classList.contains('mb56-page')) return;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  // No blocking introduction. Decorative motion runs only after content is available.
  const sections = [...document.querySelectorAll('.mb56-section, .mb56-metric-rail')];
  const navLinks = [...document.querySelectorAll('.mb56-nav-links a[href^="#"]')];
  if ('IntersectionObserver' in window && !reduceMotion.matches) {
    sections.forEach(section => section.setAttribute('data-mb63-reveal', ''));
    const reveal = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          reveal.unobserve(entry.target);
        }
      });
    }, {threshold:0.07, rootMargin:'0px 0px 20px 0px'});
    // Only hide elements after observer is ready: prevents blank sections in older browsers.
    sections.forEach(section => reveal.observe(section));
    root.classList.add('mb63-motion-ready');
  }
  navLinks.forEach(link => {
    link.addEventListener('click', event => {
      const target = document.getElementById(link.hash.slice(1));
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({behavior:reduceMotion.matches ? 'instant' : 'smooth', block:'start'});
      window.history.pushState(null, '', link.hash);
    });
  });
  if ('IntersectionObserver' in window && navLinks.length) {
    const linksById = new Map(navLinks.map(link => [link.hash.slice(1), link]));
    const active = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        navLinks.forEach(link => link.classList.remove('is-current'));
        const link = linksById.get(entry.target.id);
        if (link) link.classList.add('is-current');
      });
    }, {rootMargin:'-25% 0px -55% 0px'});
    linksById.forEach((_, id) => {
      const section = document.getElementById(id);
      if (section) active.observe(section);
    });
  }
})();
