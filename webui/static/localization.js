const tbody = document.getElementById('loc-tbody');
const filterBox = document.getElementById('filter-box');
const addRowBtn = document.getElementById('add-row-btn');
const saveBtn = document.getElementById('save-btn');
const saveStatus = document.getElementById('save-status');
const errorBox = document.getElementById('error-box');

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.hidden = true;
  errorBox.textContent = '';
}

function makeRow(en, uz) {
  const tr = document.createElement('tr');

  const enTd = document.createElement('td');
  const enInput = document.createElement('input');
  enInput.value = en;
  enInput.dataset.field = 'en';
  enTd.appendChild(enInput);

  const uzTd = document.createElement('td');
  const uzInput = document.createElement('input');
  uzInput.value = uz;
  uzInput.dataset.field = 'uz';
  uzTd.appendChild(uzInput);

  const actionTd = document.createElement('td');
  const delBtn = document.createElement('button');
  delBtn.textContent = "O'chirish";
  delBtn.addEventListener('click', () => {
    tr.remove();
  });
  actionTd.appendChild(delBtn);

  tr.appendChild(enTd);
  tr.appendChild(uzTd);
  tr.appendChild(actionTd);
  return tr;
}

// All rows always stay in the DOM/tbody, filter or no filter - the filter
// only toggles `hidden` on the ones that don't match. Save reads every
// <tr> in tbody regardless of visibility, so a save made while filtered
// can never silently drop the rows that are just scrolled out of view.
function applyFilter() {
  const q = filterBox.value.trim().toLowerCase();
  for (const tr of tbody.querySelectorAll('tr')) {
    if (!q) {
      tr.hidden = false;
      continue;
    }
    const en = tr.querySelector('input[data-field="en"]').value.toLowerCase();
    const uz = tr.querySelector('input[data-field="uz"]').value.toLowerCase();
    tr.hidden = !(en.includes(q) || uz.includes(q));
  }
}

async function load() {
  const res = await fetch('/api/localization');
  const rows = await res.json();
  tbody.innerHTML = '';
  for (const { en, uz } of rows) {
    tbody.appendChild(makeRow(en, uz));
  }
  applyFilter();
}

filterBox.addEventListener('input', applyFilter);

addRowBtn.addEventListener('click', () => {
  const tr = makeRow('', '');
  tbody.insertBefore(tr, tbody.firstChild);
  tr.querySelector('input[data-field="en"]').focus();
  applyFilter();
});

saveBtn.addEventListener('click', async () => {
  hideError();
  saveStatus.textContent = '';

  const entries = [];
  for (const tr of tbody.querySelectorAll('tr')) {
    // Leading/trailing whitespace can be load-bearing in "en" (matched
    // literally against wikitext) and "uz" may legitimately be empty (a
    // delete rule) - kept as typed, .trim() below is only to detect and
    // skip a fully-blank row. Hidden (filtered-out) rows are included too.
    const en = tr.querySelector('input[data-field="en"]').value;
    const uz = tr.querySelector('input[data-field="uz"]').value;
    if (!en.trim() && !uz.trim()) continue; // skip fully-empty rows silently
    entries.push({ en, uz });
  }

  const res = await fetch('/api/localization', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entries }),
  });
  const data = await res.json();

  if (!res.ok) {
    showError(data.error || 'Saqlashda xato');
    return;
  }

  saveStatus.textContent = `Saqlandi (${data.count} ta yozuv)`;
  await load();
});

load();
