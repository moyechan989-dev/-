(() => {
  const form = document.getElementById('guide-ai-form');
  if (!form) return;
  const input = form.querySelector('input');
  const submit = form.querySelector('[type=submit]');
  const error = document.getElementById('guide-ai-error');
  const progress = document.getElementById('guide-ai-progress');
  const result = document.getElementById('guide-ai-result');
  const fallback = 'AI 분석을 사용할 수 없습니다. 아래 행정처분 기준을 확인해 주세요.';
  let busy = false;
  document.querySelectorAll('.guide-ai-quick [data-question]').forEach(button => button.addEventListener('click', () => {
    if (!busy) { input.value = button.dataset.question; input.focus(); }
  }));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || submit.disabled || !input.value.trim()) return;
    busy = true; submit.disabled = true; input.readOnly = true;
    error.hidden = true; result.hidden = true; result.replaceChildren(); progress.hidden = false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(form.action, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: input.value.trim()}), signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok || !['matched', 'needs_more_information', 'no_match'].includes(data.result_status) || typeof data.html !== 'string') throw new Error('AI 확인 실패');
      // HTML은 서버의 autoescape 템플릿과 검증된 기준 데이터로만 생성된다.
      result.innerHTML = data.html;
      result.hidden = false;
    } catch (_) {
      error.textContent = fallback; error.hidden = false;
    } finally {
      clearTimeout(timer); busy = false; submit.disabled = false; input.readOnly = false; progress.hidden = true;
    }
  });
})();
