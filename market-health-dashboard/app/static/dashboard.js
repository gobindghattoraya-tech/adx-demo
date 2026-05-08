/**
 * Good Book Certified™ Dashboard — Client-side logic
 *
 * Architecture: one function, one job (Single Responsibility Principle).
 *   loadMarketSummary()        → KPI row
 *   loadSymbolUniverse(f)      → Symbol list (with filters)
 *   selectSymbol(ticker)       → Detail panel + charts
 *   renderIntradayChart(data)  → Chart.js line chart
 *   renderDepthChart(data)     → Chart.js horizontal bar chart
 *   applyFilters()             → Collect filter state → reload list
 *   buildTierBadge(tier)       → Returns badge HTML string
 *   buildProgressBar(brs)      → Returns bar HTML string
 *   fmtNum(n)                  → Human-friendly number format
 */

"use strict";

// ── Chart.js instances (kept for destroy/re-render) ────────────────────────────
let intradayChart = null;
let depthChart    = null;

// ── State ──────────────────────────────────────────────────────────────────────
let currentTicker = null;

// ── Utility ────────────────────────────────────────────────────────────────────
function fmtNum(n) {
  if (n === null || n === undefined) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K";
  return Number(n).toLocaleString();
}

function brsColourClass(brs) {
  if (brs >= 65) return "brs-bar--high";
  if (brs >= 50) return "brs-bar--mid";
  return "brs-bar--low";
}

/** Build a coloured tier badge HTML string. */
function buildTierBadge(tier) {
  const icons = { Gold: "🟢", Silver: "🔵", Watchlist: "🟡", Disqualified: "🔴" };
  const icon = icons[tier] || "";
  return `<span class="tier-badge tier-badge--${tier}">${icon} ${tier}</span>`;
}

/** Build a trend badge HTML string. */
function buildTrendBadge(trend) {
  const arrows = { Improving: "↑", Stable: "→", Deteriorating: "↓" };
  const arrow = arrows[trend] || "";
  return `<span class="trend-badge trend--${trend}">${arrow} ${trend}</span>`;
}

/** Set a progress bar width and colour class. */
function setBar(barEl, pct, colourClass) {
  barEl.style.width = `${Math.min(100, pct)}%`;
  barEl.className = barEl.className.replace(/brs-bar--\w+|subscore-bar|dkpi-bar/g, "").trim();
  barEl.classList.add(colourClass || "subscore-bar");
}

// ── Market Summary KPI Row ─────────────────────────────────────────────────────
async function loadMarketSummary() {
  const grid = document.getElementById("kpi-grid");
  try {
    const res  = await fetch("/api/v1/market/summary");
    if (!res.ok) throw new Error(res.statusText);
    const d = await res.json();

    const brsPct = d.market_avg_brs;
    grid.innerHTML = `
      <div class="kpi-card" role="listitem">
        <span class="kpi-label">Total Symbols</span>
        <span class="kpi-value">${d.total_symbols}</span>
        <span class="kpi-sub">ADX primary market</span>
      </div>
      <div class="kpi-card" role="listitem">
        <span class="kpi-label">Certified</span>
        <span class="kpi-value">${d.certified_count}</span>
        <span class="kpi-sub">Gold + Silver</span>
      </div>
      <div class="kpi-card" role="listitem">
        <span class="kpi-label">Watchlist</span>
        <span class="kpi-value">${d.watchlist_count}</span>
        <span class="kpi-sub">${d.disqualified_count} disqualified</span>
      </div>
      <div class="kpi-card" role="listitem">
        <span class="kpi-label">Market Avg BRS</span>
        <span class="kpi-value">${d.market_avg_brs}</span>
        <div class="kpi-brs-bar-wrap">
          <div class="kpi-brs-bar ${brsColourClass(brsPct)}" style="width:${brsPct}%"></div>
        </div>
        <span class="kpi-target">Target ≥ 70</span>
      </div>`;
  } catch (e) {
    grid.innerHTML = `<div class="kpi-card kpi-skeleton"><span class="kpi-loader">⚠ Failed to load KPIs</span></div>`;
    console.error("loadMarketSummary:", e);
  }
}

// ── Symbol Universe List ────────────────────────────────────────────────────────
async function loadSymbolUniverse(filters = {}) {
  const list  = document.getElementById("symbol-list");
  const label = document.getElementById("symbol-count-label");
  list.innerHTML = `<li class="symbol-list__loading">Loading…</li>`;

  try {
    const params = new URLSearchParams();
    if (filters.sector)  params.set("sector",  filters.sector);
    if (filters.tier)    params.set("tier",     filters.tier);
    if (filters.min_brs) params.set("min_brs",  filters.min_brs);

    const search = filters.search ? filters.search.toLowerCase() : "";
    const res    = await fetch(`/api/v1/symbols?${params}`);
    if (!res.ok) throw new Error(res.statusText);
    let symbols  = await res.json();

    // Client-side search filter (ticker or company name)
    if (search) {
      symbols = symbols.filter(
        s => s.ticker.toLowerCase().includes(search) ||
             s.full_name.toLowerCase().includes(search)
      );
    }

    label.textContent = `${symbols.length} symbol${symbols.length !== 1 ? "s" : ""} · Ranked by BRS`;

    if (symbols.length === 0) {
      list.innerHTML = `<li class="symbol-list__empty">No symbols match the current filters.</li>`;
      return;
    }

    list.innerHTML = symbols.map(s => `
      <li class="symbol-item${s.ticker === currentTicker ? " active" : ""}"
          data-ticker="${s.ticker}"
          role="listitem"
          tabindex="0"
          aria-label="${s.ticker} BRS ${s.brs} ${s.tier}">
        <span class="si-badge">${buildTierBadge(s.tier)}</span>
        <span class="si-ticker">${s.ticker}
          <span class="si-sector">${s.sector}</span>
        </span>
        <span class="si-trend trend--${s.trend}">${s.trend === "Improving" ? "↑" : s.trend === "Deteriorating" ? "↓" : "→"} ${s.trend}</span>
        <span class="si-name">${s.full_name}</span>
        <span class="si-spread">Spread: ${s.spread}</span>
        <div class="si-brs-row">
          <span class="si-brs-score">${s.brs}</span>
          <div class="si-brs-bar-wrap">
            <div class="si-brs-bar ${brsColourClass(s.brs)}" style="width:${s.brs}%"></div>
          </div>
        </div>
      </li>`).join("");

    // Click + keyboard handlers
    list.querySelectorAll(".symbol-item").forEach(el => {
      el.addEventListener("click",   () => selectSymbol(el.dataset.ticker));
      el.addEventListener("keydown", e => { if (e.key === "Enter") selectSymbol(el.dataset.ticker); });
    });

    // Auto-select first symbol if none selected yet
    if (!currentTicker && symbols.length > 0) {
      selectSymbol(symbols[0].ticker);
    }

  } catch (e) {
    list.innerHTML = `<li class="symbol-list__loading">⚠ Failed to load symbols</li>`;
    console.error("loadSymbolUniverse:", e);
  }
}

// ── Symbol Detail Panel ─────────────────────────────────────────────────────────
async function selectSymbol(ticker) {
  currentTicker = ticker;

  // Highlight active in list
  document.querySelectorAll(".symbol-item").forEach(el => {
    el.classList.toggle("active", el.dataset.ticker === ticker);
  });

  const placeholder = document.getElementById("detail-placeholder");
  const content     = document.getElementById("detail-content");
  placeholder.hidden = true;
  content.hidden     = false;

  try {
    const [detailRes, intradayRes, depthRes] = await Promise.all([
      fetch(`/api/v1/symbols/${ticker}`),
      fetch(`/api/v1/symbols/${ticker}/intraday`),
      fetch(`/api/v1/symbols/${ticker}/depth`),
    ]);
    const d   = await detailRes.json();
    const intraday = await intradayRes.json();
    const depth    = await depthRes.json();

    // Header
    document.getElementById("d-ticker").textContent    = d.ticker;
    document.getElementById("d-name").textContent      = d.full_name;
    document.getElementById("d-tier-badge").outerHTML  =
      `<span class="tier-badge tier-badge--${d.tier}" id="d-tier-badge">${buildTierBadge(d.tier)}</span>`;
    document.getElementById("d-trend-badge").outerHTML =
      `<span class="trend-badge trend--${d.trend}" id="d-trend-badge">${buildTrendBadge(d.trend)}</span>`;
    document.getElementById("d-sector").textContent    = d.sector;
    document.getElementById("d-best-bid").textContent  = d.best_bid ? d.best_bid.toFixed(2) : "—";
    document.getElementById("d-best-offer").textContent= d.best_offer ? d.best_offer.toFixed(2) : "—";
    document.getElementById("d-spread").textContent    = d.spread;

    // KPI strip
    document.getElementById("d-brs").textContent    = d.brs;
    document.getElementById("d-trades").textContent = fmtNum(d.trades_count);
    document.getElementById("d-volume").textContent = fmtNum(d.volume_aed);
    document.getElementById("d-value").textContent  = fmtNum(d.value_aed);

    const brsBar = document.getElementById("d-brs-bar");
    brsBar.style.width = `${d.brs}%`;
    brsBar.className   = `dkpi-bar ${brsColourClass(d.brs)}`;

    // Sub-scores
    [["dc","d-dc","d-dc-bar"], ["tf","d-tf","d-tf-bar"],
     ["ir","d-ir","d-ir-bar"], ["plc","d-plc","d-plc-bar"]].forEach(([key, valId, barId]) => {
      document.getElementById(valId).textContent = `${d[key]}/100`;
      const bar = document.getElementById(barId);
      bar.style.width = `${d[key]}%`;
    });

    // Charts
    renderIntradayChart(intraday);
    renderDepthChart(depth);

  } catch (e) {
    content.innerHTML = `<p style="padding:24px;color:#dc2626">⚠ Failed to load detail for ${ticker}</p>`;
    console.error("selectSymbol:", e);
  }
}

// ── Chart.js: BRS Intraday Line ─────────────────────────────────────────────────
function renderIntradayChart(data) {
  const ctx = document.getElementById("chart-intraday").getContext("2d");
  if (intradayChart) intradayChart.destroy();
  intradayChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        data: data.map(d => d.brs),
        borderColor: "#2563eb",
        backgroundColor: "rgba(37,99,235,.08)",
        fill: true,
        tension: 0.4,
        pointBackgroundColor: "#2563eb",
        pointRadius: 4,
        pointHoverRadius: 6,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { font: { size: 11 } }, grid: { color: "#f3f4f6" } },
        x: { ticks: { font: { size: 11 } }, grid: { display: false } },
      }
    }
  });
}

// ── Chart.js: Displayed Depth Bar ───────────────────────────────────────────────
function renderDepthChart(data) {
  const ctx = document.getElementById("chart-depth").getContext("2d");
  if (depthChart) depthChart.destroy();

  const bids   = data.filter(r => r.side === "BID").sort((a, b) => b.price - a.price).slice(0, 10);
  const offers = data.filter(r => r.side === "OFFER").sort((a, b) => a.price - b.price).slice(0, 10);

  const labels   = [...bids.map(r => r.price.toFixed(2)), ...offers.map(r => r.price.toFixed(2))];
  const bidQtys  = [...bids.map(r => r.quantity), ...Array(offers.length).fill(0)];
  const offerQtys= [...Array(bids.length).fill(0), ...offers.map(r => r.quantity)];

  depthChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "BID",
          data: bidQtys,
          backgroundColor: "rgba(22,163,74,.7)",
          borderColor: "#16a34a",
          borderWidth: 1,
        },
        {
          label: "OFFER",
          data: offerQtys,
          backgroundColor: "rgba(220,38,38,.7)",
          borderColor: "#dc2626",
          borderWidth: 1,
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "top", labels: { font: { size: 11 }, boxWidth: 12 } }
      },
      scales: {
        x: { stacked: false, ticks: { font: { size: 10 }, maxRotation: 45 }, grid: { display: false } },
        y: { ticks: { font: { size: 11 } }, grid: { color: "#f3f4f6" } },
      }
    }
  });
}

// ── Filters ─────────────────────────────────────────────────────────────────────
function collectFilters() {
  return {
    search:  document.getElementById("filter-search").value.trim(),
    sector:  document.getElementById("filter-sector").value,
    tier:    document.getElementById("filter-tier").value,
    min_brs: parseInt(document.getElementById("filter-minbrs").value, 10) || 0,
  };
}

function applyFilters() {
  loadSymbolUniverse(collectFilters());
}

function resetFilters() {
  document.getElementById("filter-search").value  = "";
  document.getElementById("filter-sector").value  = "";
  document.getElementById("filter-tier").value    = "";
  document.getElementById("filter-minbrs").value  = "0";
  currentTicker = null;
  loadSymbolUniverse();
}

// ── Event wiring ─────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Initial load
  loadMarketSummary();
  loadSymbolUniverse();

  // Filter controls
  document.getElementById("btn-apply-filter").addEventListener("click", applyFilters);
  document.getElementById("btn-reset-filter").addEventListener("click", resetFilters);
  document.getElementById("filter-minbrs").addEventListener("keydown", e => { if (e.key === "Enter") applyFilters(); });
  document.getElementById("filter-search").addEventListener("input",
    () => { if (document.getElementById("filter-search").value === "") loadSymbolUniverse(collectFilters()); }
  );

  // Refresh button
  document.getElementById("btn-refresh").addEventListener("click", () => {
    loadMarketSummary();
    loadSymbolUniverse(collectFilters());
  });

  // Methodology placeholder
  document.getElementById("btn-methodology").addEventListener("click", () => {
    alert(
      "Book Resilience Score (BRS) = round((DC + TF + IR + PLC) / 4)\n\n" +
      "• DC  — Depth Distribution: bid/offer quantity balance\n" +
      "• TF  — 1-Tick Shock: price concentration near best bid/offer\n" +
      "• IR  — Interaction Rate: open order ratio\n" +
      "• PLC — Ladder Convexity: evenness of price ladder\n\n" +
      "Tiers: Gold ≥80 · Silver 65–79 · Watchlist 50–64 · Disqualified <50"
    );
  });
});
