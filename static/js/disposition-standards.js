(() => {
  const panel = document.querySelector('.ds-panel');
  if (!panel) return;
  const form = panel.querySelector('.ds-filters');
  const query = panel.querySelector('#ds-query');
  const category = panel.querySelector('#ds-category');
  const normalize = value => value.normalize('NFKC').toLowerCase().replace(/\s+/gu, '');
  const cards = [...panel.querySelectorAll('.ds-card')].map(card => ({card, text: normalize(card.dataset.search)}));
  const buttons = [...panel.querySelectorAll('.ds-quick button')];
  function filter() {
    const terms = query.value.trim().split(/\s+/u).filter(Boolean).map(normalize);
    let count = 0;
    for (const {card, text} of cards) {
      card.hidden = !!((category.value && card.dataset.category !== category.value) || !terms.every(term => text.includes(term)));
      if (!card.hidden) count += 1;
    }
    panel.querySelector('#ds-count').textContent = `${count}개 기준`;
    panel.querySelector('#ds-empty').hidden = count !== 0;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.category === category.value)));
  }
  query.addEventListener('input', filter);
  category.addEventListener('change', filter);
  form.addEventListener('submit', event => { event.preventDefault(); filter(); });
  form.addEventListener('reset', event => { event.preventDefault(); query.value = ''; category.value = ''; filter(); query.focus(); });
  buttons.forEach(button => button.addEventListener('click', () => {
    category.value = category.value === button.dataset.category ? '' : button.dataset.category;
    filter();
  }));
  filter();
})();
