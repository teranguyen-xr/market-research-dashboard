let state = {
  rows: [],
  filteredRows: [],
  histories: {},
  sortKey: 'rank',
  sortDir: 'asc',
  selectedKey: null,
};

const PLATFORM_ORDER = ['statbot', 'roblox', 'steam', 'twitch'];

let creatorMomentum = null;

const els = {
  latestSnapshot: document.getElementById('latestSnapshot'),
  generatedAt: document.getElementById('generatedAt'),
  summaryCards: document.getElementById('summaryCards'),
  creatorMomentumCards: document.getElementById('creatorMomentumCards'),
  creatorCoverageBody: document.getElementById('creatorCoverageBody'),
  tiktokTrendBody: document.getElementById('tiktokTrendBody'),
  creatorSignalChips: document.getElementById('creatorSignalChips'),
  searchInput: document.getElementById('searchInput'),
  tableBodies: {
    statbot: document.getElementById('tableBody-statbot'),
    roblox: document.getElementById('tableBody-roblox'),
    steam: document.getElementById('tableBody-steam'),
    twitch: document.getElementById('tableBody-twitch'),
  },
  chartTitle: document.getElementById('chartTitle'),
  chartSvg: document.getElementById('trendChart'),
  chartEmpty: document.getElementById('chartEmpty'),
  chartFootnote: document.getElementById('chartFootnote'),
  sortHeaders: Array.from(document.querySelectorAll('th[data-sort]')),
};

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function loadData() {
  return fetch('./data/dashboard-data.json').then((response) => response.json());
}

function buildCards(cards) {
  els.summaryCards.innerHTML = cards.map((card) => `
    <article class="summary-card" data-focus-platform="${card.id}">
      <div class="summary-title">${escapeHtml(card.title)}</div>
      <h3 class="summary-game">${escapeHtml(card.game)}</h3>
      <div class="summary-meta">
        <span>${escapeHtml(card.currentMetric)}</span>
        <span>${escapeHtml(card.delta)}</span>
      </div>
    </article>
  `).join('');

  els.summaryCards.querySelectorAll('.summary-card').forEach((card) => {
    card.addEventListener('click', () => {
      const platform = card.dataset.focusPlatform;
      const nextRow = sortRows(state.filteredRows).find((row) => row.platform === platform);
      if (!nextRow) return;
      state.selectedKey = nextRow.key;
      renderTables();
      renderChart();
      document.querySelector(`[data-row-key="${CSS.escape(nextRow.key)}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
}

function renderCreatorMomentum() {
  if (!creatorMomentum) {
    return;
  }
  els.creatorMomentumCards.innerHTML = creatorMomentum.cards.map((card) => `
    <article class="creator-summary-card">
      <div class="summary-title">${escapeHtml(card.title)}</div>
      <h3 class="creator-summary-primary">${escapeHtml(card.primary)}</h3>
      <div class="creator-summary-meta">${escapeHtml(card.meta)}</div>
      <div class="creator-summary-detail">${escapeHtml(card.detail)}</div>
    </article>
  `).join('');

  els.creatorCoverageBody.innerHTML = creatorMomentum.coverage.map((row) => {
    const gameCell = row.gameUrl
      ? `<a class="game-link" href="${row.gameUrl}" target="_blank" rel="noreferrer">${escapeHtml(row.game)}</a>`
      : `<span class="${row.game === 'No tracked game yet' ? 'muted' : ''}">${escapeHtml(row.game)}</span>`;
    const statusCell = row.status === 'NEW'
      ? '<span class="badge-new">NEW</span>'
      : row.status === 'Watch'
        ? '<span class="status-watch">Watch</span>'
        : '<span class="status-muted">Repeat</span>' ;
    return `
    <tr>
      <td><a class="game-link" href="${row.creatorUrl}" target="_blank" rel="noreferrer">${escapeHtml(row.creator)}</a></td>
      <td><span class="segment-pill">${escapeHtml(row.segment)}</span></td>
      <td>${gameCell}</td>
      <td>${escapeHtml(row.platform)}</td>
      <td><a class="subtle-link" href="${row.videoUrl}" target="_blank" rel="noreferrer">${escapeHtml(row.video)}</a></td>
      <td>${escapeHtml(row.subscribers)}</td>
      <td>${escapeHtml(row.views)}</td>
      <td>${escapeHtml(row.posted)}</td>
      <td>${statusCell}</td>
    </tr>
  `;
  }).join('');

  els.tiktokTrendBody.innerHTML = creatorMomentum.trends.map((row) => `
    <tr>
      <td><span class="trend-pill">${escapeHtml(row.bucket)}</span></td>
      <td>${escapeHtml(row.game)}</td>
      <td><a class="subtle-link" href="${row.url}" target="_blank" rel="noreferrer">${escapeHtml(row.caption)}</a></td>
      <td>${escapeHtml(row.creator)}</td>
      <td>${escapeHtml(row.views)}</td>
      <td>${escapeHtml(row.posted)}</td>
      <td>${row.status === 'NEW' ? '<span class="badge-new">NEW</span>' : '<span class="status-muted">Repeat</span>'}</td>
    </tr>
  `).join('');

  els.creatorSignalChips.innerHTML = creatorMomentum.signals.map((signal) => `
    <div class="signal-chip">${escapeHtml(signal)}</div>
  `).join('');
}

function compareValues(a, b) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), undefined, { sensitivity: 'base' });
}

function sortRows(rows) {
  const { sortKey, sortDir } = state;
  return [...rows].sort((left, right) => {
    const result = compareValues(left[sortKey], right[sortKey]);
    if (result !== 0) return sortDir === 'asc' ? result : -result;
    return compareValues(left.rank, right.rank);
  });
}

function renderPlatformTable(platform, rows) {
  const body = els.tableBodies[platform];
  if (!body) return;

  if (rows.length === 0) {
    body.innerHTML = `
      <tr>
        <td colspan="4" class="empty-table">No matching games for this source.</td>
      </tr>
    `;
    return;
  }

  body.innerHTML = rows.map((row) => {
    const deltaClass = row.deltaValue == null ? 'muted' : row.deltaValue >= 0 ? 'delta-positive' : 'delta-negative';
    return `
      <tr data-row-key="${row.key}" class="${state.selectedKey === row.key ? 'is-selected' : ''}">
        <td>
          <a class="game-link" href="${row.url || '#'}" target="_blank" rel="noreferrer">${escapeHtml(row.title)}</a>
          ${row.isNew ? '<span class="badge-new">NEW</span>' : ''}
        </td>
        <td>#${row.rank}</td>
        <td>${escapeHtml(row.currentMetric)}</td>
        <td class="${deltaClass}">${escapeHtml(row.delta)}</td>
      </tr>
    `;
  }).join('');

  body.querySelectorAll('tr[data-row-key]').forEach((rowEl) => {
    rowEl.addEventListener('click', () => {
      state.selectedKey = rowEl.dataset.rowKey;
      renderTables();
      renderChart();
    });
  });
}

function renderTables() {
  const sorted = sortRows(state.filteredRows);
  PLATFORM_ORDER.forEach((platform) => {
    const rows = sorted.filter((row) => row.platform === platform);
    renderPlatformTable(platform, rows);
  });

  if (!state.selectedKey && sorted[0]) {
    state.selectedKey = sorted[0].key;
    renderTables();
    renderChart();
  }
}

function applyFilters() {
  const query = els.searchInput.value.trim().toLowerCase();
  state.filteredRows = state.rows.filter((row) => {
    return !query || [row.title, row.platformLabel].join(' ').toLowerCase().includes(query);
  });

  if (!state.filteredRows.find((row) => row.key === state.selectedKey)) {
    state.selectedKey = state.filteredRows[0]?.key || null;
  }

  renderTables();
  renderChart();
}

function renderChart() {
  const history = state.histories[state.selectedKey] || [];
  const row = state.rows.find((item) => item.key === state.selectedKey);
  els.chartTitle.textContent = row ? `${row.title} • ${row.platformLabel}` : 'Choose a game row';

  if (!row || history.length === 0) {
    els.chartSvg.innerHTML = '';
    els.chartEmpty.style.display = 'grid';
    els.chartEmpty.textContent = 'Select a row to see movement over time.';
    els.chartFootnote.textContent = '';
    return;
  }

  const points = history
    .map((item) => ({
      date: item.date,
      value: item.metric,
    }))
    .filter((item) => item.value != null);

  if (points.length < 2) {
    els.chartSvg.innerHTML = '';
    els.chartEmpty.style.display = 'grid';
    els.chartEmpty.textContent = 'Metric history is not available for this source yet.';
    els.chartFootnote.textContent = '';
    return;
  }

  els.chartEmpty.style.display = 'none';
  const width = 760;
  const height = 320;
  const padding = { top: 20, right: 24, bottom: 38, left: 46 };
  const values = points.map((p) => Number(p.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const xFor = (index) => padding.left + (index * (width - padding.left - padding.right)) / (points.length - 1);
  const yFor = (value) => {
    const normalized = (value - min) / range;
    return height - padding.bottom - normalized * (height - padding.top - padding.bottom);
  };

  const linePoints = points.map((point, index) => `${xFor(index)},${yFor(Number(point.value))}`).join(' ');

  const grid = Array.from({ length: 4 }, (_, idx) => {
    const y = padding.top + ((height - padding.top - padding.bottom) * idx) / 3;
    return `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="rgba(24,33,45,0.08)" stroke-width="1" />`;
  }).join('');

  const labels = points.map((point, index) => {
    const x = xFor(index);
    return `<text x="${x}" y="${height - 12}" text-anchor="middle" fill="#5c6775" font-size="11">${point.date.slice(5)}</text>`;
  }).join('');

  const dots = points.map((point, index) => {
    const x = xFor(index);
    const y = yFor(Number(point.value));
    return `<g>
      <circle cx="${x}" cy="${y}" r="4" fill="#b44d12" />
      <title>${point.date}: ${point.value}</title>
    </g>`;
  }).join('');

  els.chartSvg.innerHTML = `
    ${grid}
    <polyline fill="none" stroke="#b44d12" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${linePoints}" />
    ${dots}
    ${labels}
  `;

  const latest = points[points.length - 1];
  const oldest = points[0];
  const direction = Number(latest.value) - Number(oldest.value);
  const footnoteMetric = `${row.metricLabel} history`;
  const directionText = direction > 0 ? 'rising' : direction < 0 ? 'falling' : 'flat';
  els.chartFootnote.textContent = `${row.title} ${footnoteMetric} is ${directionText} across ${points.length} snapshots.`;
}

function updateSortHeaders() {
  els.sortHeaders.forEach((header) => {
    const isActive = header.dataset.sort === state.sortKey;
    header.classList.toggle('is-active-sort', isActive);
    header.dataset.sortDir = isActive ? state.sortDir : '';
  });
}

function attachEvents() {
  els.searchInput.addEventListener('input', applyFilters);
  els.sortHeaders.forEach((header) => {
    header.addEventListener('click', () => {
      const key = header.dataset.sort;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = key;
        state.sortDir = key === 'rank' ? 'asc' : 'desc';
      }
      updateSortHeaders();
      renderTables();
    });
  });
}

loadData().then((data) => {
  els.latestSnapshot.textContent = data.latestSnapshotDate;
  els.generatedAt.textContent = formatDate(data.generatedAt);
  state.rows = data.rows;
  state.histories = data.histories;
  state.filteredRows = data.rows;
  buildCards(data.cards);
  creatorMomentum = data.creatorMomentum || null;
  renderCreatorMomentum();
  attachEvents();
  updateSortHeaders();
  applyFilters();
}).catch((error) => {
  console.error(error);
  document.body.innerHTML = '<div style="padding:24px;font-family:sans-serif">Failed to load dashboard data. Run <code>generate_dashboard_data.py</code> first.</div>';
});
