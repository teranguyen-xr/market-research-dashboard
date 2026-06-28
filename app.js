let state = {
  rows: [],
  filteredRows: [],
  histories: {},
  sortKey: 'platformLabel',
  sortDir: 'asc',
  chartMode: 'rank',
  selectedKey: null,
};

const els = {
  latestSnapshot: document.getElementById('latestSnapshot'),
  generatedAt: document.getElementById('generatedAt'),
  summaryCards: document.getElementById('summaryCards'),
  searchInput: document.getElementById('searchInput'),
  platformFilter: document.getElementById('platformFilter'),
  tableBody: document.getElementById('tableBody'),
  chartTitle: document.getElementById('chartTitle'),
  chartSvg: document.getElementById('trendChart'),
  chartEmpty: document.getElementById('chartEmpty'),
  chartFootnote: document.getElementById('chartFootnote'),
  toggles: Array.from(document.querySelectorAll('.toggle')),
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
      els.platformFilter.value = platform;
      applyFilters();
    });
  });
}

function buildPlatformOptions(sources) {
  els.platformFilter.innerHTML = '<option value="all">All</option>' + sources.map((source) => (
    `<option value="${source.id}">${escapeHtml(source.label)}</option>`
  )).join('');
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
    return sortDir === 'asc' ? result : -result;
  });
}

function renderTable() {
  const rows = sortRows(state.filteredRows);
  els.tableBody.innerHTML = rows.map((row) => {
    const deltaClass = row.deltaValue == null ? 'muted' : row.deltaValue >= 0 ? 'delta-positive' : 'delta-negative';
    return `
      <tr data-key="${row.key}" class="${state.selectedKey === row.key ? 'is-selected' : ''}">
        <td>
          <a class="game-link" href="${row.url || '#'}" target="_blank" rel="noreferrer">${escapeHtml(row.title)}</a>
          ${row.isNew ? '<span class="badge-new">NEW</span>' : ''}
        </td>
        <td>${escapeHtml(row.platformLabel)}</td>
        <td>#${row.rank}</td>
        <td>${escapeHtml(row.currentMetric)}</td>
        <td class="${deltaClass}">${escapeHtml(row.delta)}</td>
      </tr>
    `;
  }).join('');

  els.tableBody.querySelectorAll('tr').forEach((row) => {
    row.addEventListener('click', () => {
      state.selectedKey = row.dataset.key;
      renderTable();
      renderChart();
    });
  });

  if (!state.selectedKey && rows[0]) {
    state.selectedKey = rows[0].key;
    renderTable();
    renderChart();
  }
}

function applyFilters() {
  const query = els.searchInput.value.trim().toLowerCase();
  const platform = els.platformFilter.value;
  state.filteredRows = state.rows.filter((row) => {
    const matchesQuery = !query || [row.title, row.platformLabel].join(' ').toLowerCase().includes(query);
    const matchesPlatform = platform === 'all' || row.platform === platform;
    return matchesQuery && matchesPlatform;
  });
  if (!state.filteredRows.find((row) => row.key === state.selectedKey)) {
    state.selectedKey = state.filteredRows[0]?.key || null;
  }
  renderTable();
}

function renderChart() {
  const history = state.histories[state.selectedKey] || [];
  const row = state.rows.find((item) => item.key === state.selectedKey);
  els.chartTitle.textContent = row ? `${row.title} • ${row.platformLabel}` : 'Choose a game row';

  if (!row || history.length === 0) {
    els.chartSvg.innerHTML = '';
    els.chartEmpty.style.display = 'grid';
    els.chartFootnote.textContent = '';
    return;
  }

  const points = history
    .map((item) => ({
      date: item.date,
      value: state.chartMode === 'metric' ? item.metric : item.rank,
    }))
    .filter((item) => item.value != null);

  if (points.length < 2) {
    els.chartSvg.innerHTML = '';
    els.chartEmpty.style.display = 'grid';
    els.chartEmpty.textContent = state.chartMode === 'metric'
      ? 'Metric history is not available for this source yet.'
      : 'Not enough history points yet.';
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
    const normalized = state.chartMode === 'rank'
      ? (value - min) / range
      : (value - min) / range;
    const y = height - padding.bottom - normalized * (height - padding.top - padding.bottom);
    return state.chartMode === 'rank' ? y : y;
  };

  const rankMode = state.chartMode === 'rank';
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
      <title>${point.date}: ${rankMode ? '#' + point.value : point.value}</title>
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
  const footnoteMetric = rankMode ? 'rank history' : `${row.metricLabel} history`;
  const directionText = rankMode
    ? (direction < 0 ? 'improving' : direction > 0 ? 'slipping' : 'flat')
    : (direction > 0 ? 'rising' : direction < 0 ? 'falling' : 'flat');
  els.chartFootnote.textContent = `${row.title} ${footnoteMetric} is ${directionText} across ${points.length} snapshots.`;
}

function attachEvents() {
  els.searchInput.addEventListener('input', applyFilters);
  els.platformFilter.addEventListener('change', applyFilters);
  document.querySelectorAll('th[data-sort]').forEach((header) => {
    header.addEventListener('click', () => {
      const key = header.dataset.sort;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = key;
        state.sortDir = key === 'rank' ? 'asc' : 'desc';
      }
      renderTable();
    });
  });
  els.toggles.forEach((toggle) => {
    toggle.addEventListener('click', () => {
      els.toggles.forEach((button) => button.classList.remove('is-active'));
      toggle.classList.add('is-active');
      state.chartMode = toggle.dataset.chartMode;
      renderChart();
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
  buildPlatformOptions(data.sources);
  attachEvents();
  applyFilters();
}).catch((error) => {
  console.error(error);
  document.body.innerHTML = '<div style="padding:24px;font-family:sans-serif">Failed to load dashboard data. Run <code>generate_dashboard_data.py</code> first.</div>';
});
