'use strict';

const runSelect = document.getElementById('run-select');
const runSummary = document.getElementById('run-summary');
const articlesEl = document.getElementById('articles');
const errorBox = document.getElementById('error-box');

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// The flags that decide whether an article can be published as-is. Each one
// is a thing the pipeline could not fix on its own.
function flagNotes(a) {
  const notes = [];
  const f = a.flags || {};
  const trim = a.trim || {};

  if (!f.review_ran) notes.push('Phase 5 ishlamadi');
  if (trim.thin_lead) notes.push('kirish qismi juda qisqa');
  if ((f.leftover_refs || []).length) {
    notes.push(`${f.leftover_refs.length} ta manba xom qoldi: ${f.leftover_refs.join(', ')}`);
  }
  if ((f.failed_titles || []).length) {
    notes.push(`${f.failed_titles.length} ta havolada API xatosi — inglizcha qolgan boʻlishi mumkin`);
  }
  if ((f.label_mismatches || []).length) {
    const pairs = f.label_mismatches.map(([t, l]) => `[[${t}|${l}]]`).join(' ');
    notes.push(`${f.label_mismatches.length} ta havola nomi mos emas (2-qoida): ${pairs}`);
  }
  (f.warnings || []).forEach((w) => notes.push(w.trim()));
  if ((trim.refs_inlined || []).length) {
    notes.push(`${trim.refs_inlined.length} ta nomli manba kesilgan boʻlimdan koʻchirildi`);
  }
  return notes;
}

function summaryLine(a) {
  const parts = [a.mode];
  if (a.mode === 'trim') parts.push(`${a.original_size} → ${a.output_size} bayt`);
  else parts.push(`${a.output_size} bayt`);
  parts.push((a.flags || {}).review_ran ? 'Phase 5 ✓' : 'Phase 5 ✗');
  if (a.category) parts.push(a.category.replace(/^Category:/, ''));
  return parts.join(' · ');
}

function renderArticle(a) {
  const panel = el('section', 'panel article-panel');

  const heading = el('h2');
  heading.appendChild(document.createTextNode(a.title + ' '));
  if (a.url) {
    const link = el('a', 'en-link', 'en ↗');
    link.href = a.url;
    link.target = '_blank';
    link.rel = 'noopener';
    heading.appendChild(link);
  }
  panel.appendChild(heading);

  if (a.status !== 'ok') {
    panel.appendChild(el('div', 'error-box', a.error || 'Nomaʼlum xato'));
    return panel;
  }

  panel.appendChild(el('div', 'stats-box', summaryLine(a)));

  const notes = flagNotes(a);
  if (notes.length) {
    const box = el('div', 'flag-box');
    notes.forEach((n) => box.appendChild(el('div', null, '• ' + n)));
    panel.appendChild(box);
  }

  const box = el('textarea', 'article-text');
  box.readOnly = true;
  box.value = a.text || '';
  panel.appendChild(box);

  const actions = el('div', 'result-actions');

  const copyBtn = el('button', null, 'Nusxalash');
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(a.text || '');
      copyBtn.textContent = 'Nusxalandi';
      setTimeout(() => { copyBtn.textContent = 'Nusxalash'; }, 1500);
    } catch (e) {
      showError('Nusxalab boʻlmadi: ' + e);
    }
  });
  actions.appendChild(copyBtn);

  const label = el('label', 'switch-label');
  const box2 = document.createElement('input');
  box2.type = 'checkbox';
  box2.checked = !!a.published;
  box2.addEventListener('change', async () => {
    try {
      const resp = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: a.title, published: box2.checked }),
      });
      if (!resp.ok) throw new Error((await resp.json()).error || resp.status);
      panel.classList.toggle('published', box2.checked);
    } catch (e) {
      box2.checked = !box2.checked;
      showError('Saqlab boʻlmadi: ' + e.message);
    }
  });
  label.appendChild(box2);
  label.appendChild(document.createTextNode(' Nashr qilindi'));
  actions.appendChild(label);

  panel.appendChild(actions);
  if (a.published) panel.classList.add('published');
  return panel;
}

async function loadRun(runId) {
  errorBox.hidden = true;
  articlesEl.textContent = '';
  const resp = await fetch('/api/run/' + encodeURIComponent(runId));
  const data = await resp.json();
  if (!resp.ok) {
    showError(data.error || 'Paketni yuklab boʻlmadi');
    return;
  }
  runSummary.textContent =
    `${data.ok} tayyor, ${data.failed} xato` + (data.review_enabled ? '' : ' — Phase 5 oʻchiq edi');
  data.articles.forEach((a) => articlesEl.appendChild(renderArticle(a)));
}

async function init() {
  const resp = await fetch('/api/runs');
  const rows = await resp.json();
  if (!rows.length) {
    showError('Hali birorta paket ishga tushmagan. `python batch_translate.py` ni ishga tushiring.');
    return;
  }
  rows.forEach((r) => {
    const opt = document.createElement('option');
    opt.value = r.run_id;
    opt.textContent = `${r.run_id} (${r.ok}/${r.ok + r.failed})`;
    runSelect.appendChild(opt);
  });
  runSelect.addEventListener('change', () => loadRun(runSelect.value));
  loadRun(rows[0].run_id);
}

init();
