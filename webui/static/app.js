const inputBox = document.getElementById('input-box');
const translateBtn = document.getElementById('translate-btn');
const progressEl = document.getElementById('progress');
const progressLabel = document.getElementById('progress-label');
const errorBox = document.getElementById('error-box');
const outputBox = document.getElementById('output-box');
const copyBtn = document.getElementById('copy-btn');
const downloadLink = document.getElementById('download-link');
const statsBox = document.getElementById('stats-box');
const reviewToggle = document.getElementById('review-toggle');

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.hidden = true;
  errorBox.textContent = '';
}

function setBusy(busy) {
  translateBtn.disabled = busy;
  inputBox.disabled = busy;
}

async function loadSettings() {
  const res = await fetch('/api/settings');
  const data = await res.json();
  reviewToggle.checked = !!data.review_enabled;
}

reviewToggle.addEventListener('change', async () => {
  await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ review_enabled: reviewToggle.checked }),
  });
});

function formatStats(stats) {
  const lines = [];
  lines.push(`Hajm: ${stats.input_size} -> ${stats.output_size} belgi`);
  lines.push(`Havolalar: ${stats.counts.links}, Kategoriyalar: ${stats.counts.categories}, Andozalar: ${stats.counts.templates}`);
  const t = stats.timings;
  lines.push(`Vaqt: tayyorlash ${t.prepare}s, tarjima ${t.translate}s, finalizatsiya ${t.finalize}s, lokalizatsiya ${t.localize}s, tahrir ${t.review}s, jami ${t.total}s`);
  lines.push(`Tarjima modeli: ${stats.translator.model}, tokenlar: ${stats.translator.tokens_used} (cache: ${stats.translator.cache_hits})`);
  if (stats.reviewer) {
    lines.push(`Tahrir modeli: ${stats.reviewer.model}, tokenlar: ${stats.reviewer.tokens_used} (cache: ${stats.reviewer.cache_hits})`);
  } else {
    lines.push("Tahrir (Phase 5): o'tkazib yuborildi");
  }
  lines.push(`Lokalizatsiya: ${stats.localization.replacements}/${stats.localization.patterns_count} qoida ishlatildi`);
  if (stats.failed_titles.length) {
    lines.push(`Aniqlanmagan sarlavhalar (${stats.failed_titles.length}): ${stats.failed_titles.join(', ')}`);
  }
  if (stats.label_mismatches.length) {
    lines.push(`Havola/nom mos kelmasligi (${stats.label_mismatches.length}): ` +
      stats.label_mismatches.map(([target, label]) => `[[${target}|${label}]]`).join(', '));
  }
  return lines.join('\n');
}

async function renderResult() {
  const res = await fetch('/api/result');
  if (!res.ok) return;
  const result = await res.json();
  outputBox.value = result.text;
  copyBtn.disabled = false;
  downloadLink.classList.remove('disabled');
  downloadLink.href = '/download';
  statsBox.hidden = false;
  statsBox.textContent = formatStats(result.stats);
}

async function poll() {
  const res = await fetch('/api/status');
  const data = await res.json();

  if (data.status === 'running') {
    progressEl.hidden = false;
    progressLabel.textContent = data.phase_label || data.phase;
    setTimeout(poll, 1500);
    return;
  }

  progressEl.hidden = true;
  setBusy(false);

  if (data.status === 'error') {
    showError(data.error || "Noma'lum xato");
    return;
  }

  if (data.status === 'done') {
    await renderResult();
  }
}

translateBtn.addEventListener('click', async () => {
  hideError();
  const value = inputBox.value.trim();
  if (!value) {
    showError('Matn kiritilmagan');
    return;
  }

  outputBox.value = '';
  copyBtn.disabled = true;
  downloadLink.classList.add('disabled');
  statsBox.hidden = true;
  setBusy(true);
  progressEl.hidden = false;
  progressLabel.textContent = 'Boshlanmoqda...';

  const res = await fetch('/api/translate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input: value }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    showError(data.error || 'Xato yuz berdi');
    setBusy(false);
    progressEl.hidden = true;
    return;
  }

  poll();
});

copyBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(outputBox.value);
    const original = copyBtn.textContent;
    copyBtn.textContent = 'Nusxalandi!';
    setTimeout(() => { copyBtn.textContent = original; }, 1500);
  } catch (e) {
    showError("Nusxalab bo'lmadi: " + e);
  }
});

// Resume polling / show the last result if a job was already running or
// finished before this page load (e.g. the page was reloaded mid-translate).
async function checkExistingJob() {
  const res = await fetch('/api/status');
  const data = await res.json();
  if (data.status === 'running') {
    setBusy(true);
    progressEl.hidden = false;
    progressLabel.textContent = data.phase_label || data.phase;
    poll();
  } else if (data.status === 'done') {
    await renderResult();
  }
}

loadSettings();
checkExistingJob();
