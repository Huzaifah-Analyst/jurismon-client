// JurisMon Frontend Search & Result Rendering

let activeFilter = 'all';
let searchTimeout = null;

const searchInput = document.getElementById('search-input');
const heroSection = document.getElementById('hero-section');
const resultsContainer = document.getElementById('results-container');
const resultsCount = document.getElementById('results-count');
const resultsList = document.getElementById('results-list');
const filterPills = document.querySelectorAll('.pill');

// Filter button handlers
filterPills.forEach(pill => {
  pill.addEventListener('click', () => {
    filterPills.forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    activeFilter = pill.dataset.filter;
    triggerSearch();
  });
});

// Search input debounced handler
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(triggerSearch, 300);
});

async function triggerSearch() {
  const query = searchInput.value.trim();
  if (!query) {
    heroSection.classList.remove('compact');
    resultsContainer.style.display = 'none';
    return;
  }

  heroSection.classList.add('compact');
  resultsContainer.style.display = 'block';
  resultsCount.textContent = 'Searching...';

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    renderResults(data, query);
  } catch (err) {
    resultsCount.textContent = 'Error fetching search results. Please try again.';
    console.error(err);
  }
}

function renderResults(data, query) {
  const snapshots = data.results?.snapshots || [];
  const diffs = data.results?.diffs || [];

  let items = [];
  if (activeFilter === 'all' || activeFilter === 'diffs') {
    diffs.forEach(d => items.push({ type: 'diff', data: d }));
  }
  if (activeFilter === 'all' || activeFilter === 'snapshots') {
    snapshots.forEach(s => items.push({ type: 'snapshot', data: s }));
  }

  resultsCount.textContent = `Found ${items.length} result(s) for "${query}"`;
  resultsList.innerHTML = '';

  if (items.length === 0) {
    resultsList.innerHTML = `
      <div class="result-card">
        <p style="color: var(--text-muted); text-align: center;">No matching statutory clauses or snapshots found.</p>
      </div>
    `;
    return;
  }

  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'result-card';

    if (item.type === 'diff') {
      const d = item.data;
      const doc = d.documents || {};
      const payload = d.diff_payload || {};
      
      let diffHtml = '';
      if (payload.added && payload.added.length > 0) {
        payload.added.forEach(cl => {
          diffHtml += `<div class="diff-clause-box"><span class="badge badge-added">Added</span> <strong>${cl.identifier}:</strong> ${cl.new_text || ''}</div>`;
        });
      }
      if (payload.removed && payload.removed.length > 0) {
        payload.removed.forEach(cl => {
          diffHtml += `<div class="diff-clause-box"><span class="badge badge-removed">Removed</span> <strong>${cl.identifier}:</strong> ${cl.old_text || ''}</div>`;
        });
      }
      if (payload.modified && payload.modified.length > 0) {
        payload.modified.forEach(cl => {
          diffHtml += `<div class="diff-clause-box"><span class="badge badge-modified">Modified</span> <strong>${cl.identifier}:</strong> ${cl.new_text || ''}</div>`;
        });
      }

      card.innerHTML = `
        <span class="badge badge-modified">Statutory Delta</span>
        <a href="${doc.pdf_url || '#'}" target="_blank" class="doc-title" style="display:block; margin-top:6px;">${doc.title || 'Municipal Notice Update'}</a>
        <div class="doc-meta">Generated: ${new Date(d.generated_at).toLocaleDateString()} | Strategy: ${payload.strategy_used || 'section'}</div>
        <div class="doc-snippet">${payload.summary || ''}</div>
        ${diffHtml}
      `;
    } else {
      const s = item.data;
      const doc = s.documents || {};
      const snippet = s.cleaned_text.length > 300 ? s.cleaned_text.substring(0, 300) + '...' : s.cleaned_text;

      card.innerHTML = `
        <span class="badge" style="background:#e8f0fe; color:#1a73e8;">Snapshot v${s.version}</span>
        <a href="${doc.pdf_url || '#'}" target="_blank" class="doc-title" style="display:block; margin-top:6px;">${doc.title || 'Statutory Snapshot'}</a>
        <div class="doc-meta">Crawled: ${new Date(s.crawled_at).toLocaleDateString()} ${s.ocr_applied ? '| OCR Applied' : ''}</div>
        <div class="doc-snippet">${snippet}</div>
      `;
    }

    resultsList.appendChild(card);
  });
}
