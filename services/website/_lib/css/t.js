(() => {
  const root = document.querySelector('.fm01-features');
  if (!root) return;
  const buttons = [...root.querySelectorAll('.fm01-feature-tabs button')];
  const sections = buttons.map(b => root.querySelector('#' + b.dataset.section)).filter(Boolean);
  buttons.forEach(btn => btn.addEventListener('click', () => {
    root.querySelector('#' + btn.dataset.section)?.scrollIntoView({behavior:'smooth', block:'start'});
  }));
  const io = new IntersectionObserver(entries => {
    const visible = entries.filter(e => e.isIntersecting).sort((a,b) => b.intersectionRatio-a.intersectionRatio)[0];
    if (!visible) return;
    buttons.forEach(b => b.classList.toggle('is-active', b.dataset.section === visible.target.id));
  }, {rootMargin:'-20% 0px -65% 0px', threshold:[0,.15,.5]});
  sections.forEach(s => io.observe(s));
})();
