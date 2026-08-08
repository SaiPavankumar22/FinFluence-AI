const CHART_COLORS = [
  "#4f7cff", "#21c58a", "#d7ae4a", "#f0555a",
  "#9b6bff", "#3ec6d0", "#e88a4a", "#ff6fba",
  "#5fe6b4", "#ff9d45", "#72b9ff", "#c6ff72",
];

const CHART_DEFAULTS = {
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: "#8892a8" }, grid: { color: "#1e2436" } },
    y: { ticks: { color: "#8892a8" }, grid: { color: "#1e2436" } },
  },
};

function barChart(ctx, labels, data, horizontal = true) {
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      ...CHART_DEFAULTS,
    },
  });
}

function emptyNote(wrapId, message) {
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  wrap.innerHTML = `<div class="text-muted text-center py-5" style="font-size:.9rem">${escapeHtml(message)}</div>`;
}

function renderStats(totals) {
  const items = [
    { icon: "bi-check-circle-fill", color: "var(--bull)",    label: "Analyzed Reels",   value: totals.total_analyzed },
    { icon: "bi-collection-play",   color: "var(--accent)",  label: "Total Reels",       value: totals.total_reels },
    { icon: "bi-people-fill",       color: "var(--purple)",  label: "Influencers",       value: totals.total_influencers },
    { icon: "bi-cpu-fill",          color: "var(--neutral)", label: "Processing Now",    value: totals.processing_now },
  ];
  document.getElementById("analytics-stats").innerHTML = items.map(it => `
    <div class="col-6 col-md-3">
      <div class="stat-card h-100">
        <div class="d-flex align-items-center gap-2 mb-1">
          <i class="bi ${it.icon}" style="color:${it.color};font-size:1.1rem"></i>
          <span class="stat-label">${it.label}</span>
        </div>
        <div class="stat-value">${it.value ?? 0}</div>
      </div>
    </div>`).join("");
}

function renderLeaderboard(list) {
  const el = document.getElementById("leaderboard-list");
  if (!list || !list.length) {
    el.innerHTML = `<div class="text-muted text-center py-4">No influencer data yet.</div>`;
    return;
  }
  const max = list[0].count;
  el.innerHTML = list.map((row, i) => {
    const pct = max ? Math.round((row.count / max) * 100) : 0;
    const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}.`;
    return `
      <div class="topic-bar">
        <span style="min-width:2rem;font-size:.9rem">${medal}</span>
        <span class="topic-name">
          <a href="/influencers/${escapeHtml(row.id || "")}" class="text-decoration-none" style="color:var(--text)">
            ${escapeHtml(row.display_name || row.username)}
          </a>
          ${row.display_name && row.username !== row.display_name
            ? `<span class="text-muted ms-1" style="font-size:.78rem">@${escapeHtml(row.username)}</span>`
            : ""}
        </span>
        <div class="topic-track">
          <div class="topic-fill" style="width:${pct}%"></div>
        </div>
        <span class="topic-count">${row.count} reel${row.count !== 1 ? "s" : ""}</span>
      </div>`;
  }).join("");
}

async function loadAnalytics() {
  try {
    const data = await apiGet("/api/analytics/overview");

    renderStats(data.totals || {});

    if (data.top_stocks.length) {
      barChart(document.getElementById("stocksChart"),
        data.top_stocks.map(x => x._id), data.top_stocks.map(x => x.count));
    } else emptyNote("stocksWrap", "No stock mentions analyzed yet.");

    if (data.top_ipos.length) {
      barChart(document.getElementById("iposChart"),
        data.top_ipos.map(x => x._id), data.top_ipos.map(x => x.count));
    } else emptyNote("iposWrap", "No IPO mentions analyzed yet.");

    if (data.top_sectors.length) {
      barChart(document.getElementById("sectorsChart"),
        data.top_sectors.map(x => x._id), data.top_sectors.map(x => x.count));
    } else emptyNote("sectorsWrap", "No sector/topic data yet.");

    if (data.top_economic_events && data.top_economic_events.length) {
      barChart(document.getElementById("econChart"),
        data.top_economic_events.map(x => x._id), data.top_economic_events.map(x => x.count));
    } else emptyNote("econWrap", "No economic events detected yet.");

    if (data.top_geopolitical_events && data.top_geopolitical_events.length) {
      barChart(document.getElementById("geoChart"),
        data.top_geopolitical_events.map(x => x._id), data.top_geopolitical_events.map(x => x.count));
    } else emptyNote("geoWrap", "No geopolitical events detected yet.");

    const sentiment = (data.sentiment_distribution || []).filter(s => s._id);
    if (sentiment.length) {
      new Chart(document.getElementById("sentimentChart"), {
        type: "doughnut",
        data: {
          labels: sentiment.map(s => s._id),
          datasets: [{
            data: sentiment.map(s => s.count),
            backgroundColor: sentiment.map(s =>
              s._id === "Bullish" ? "#21c58a" : s._id === "Bearish" ? "#f0555a" : "#d7ae4a"),
            borderWidth: 2,
            borderColor: "#141820",
          }],
        },
        options: {
          plugins: {
            legend: { position: "bottom", labels: { color: "#e7eaf0", padding: 16 } },
          },
          cutout: "62%",
        },
      });
    } else emptyNote("sentimentWrap", "No sentiment data yet.");

    renderLeaderboard(data.by_influencer || []);

  } catch (e) {
    document.querySelector(".container").innerHTML =
      `<div class="empty-state"><span class="empty-icon"><i class="bi bi-exclamation-triangle"></i></span>Could not load analytics: ${escapeHtml(e.message)}</div>`;
  }
}

loadAnalytics();
