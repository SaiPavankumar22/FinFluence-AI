async function loadDashboard() {
  try {
    const stats = await apiGet("/api/dashboard/stats");
    renderStats(stats);
    renderPipelineStatus(stats);
    renderLatest(stats.latest_analyses);
    renderTrending(stats.trending_topics);
  } catch (e) {
    document.getElementById("stats-row").innerHTML =
      `<div class="col-12 empty-state"><span class="empty-icon">⚠️</span>Could not load dashboard: ${escapeHtml(e.message)}</div>`;
  }
}

function renderStats(stats) {
  const processed = stats.processed_reels ?? 0;
  const total = stats.total_reels ?? 0;
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  const cards = [
    {
      label: "Influencers",
      value: stats.total_influencers ?? 0,
      icon: "bi-people-fill",
      color: "var(--accent)",
      glow: "rgba(79,124,255,.08)",
      link: "/influencers",
    },
    {
      label: "Total Reels",
      value: total,
      icon: "bi-collection-play-fill",
      color: "var(--purple)",
      glow: "rgba(155,107,255,.08)",
    },
    {
      label: "Analyzed",
      value: processed,
      sub: total > 0 ? `${pct}% complete` : "0% complete",
      icon: "bi-check-circle-fill",
      color: "var(--bull)",
      glow: "rgba(33,197,138,.08)",
    },
    {
      label: "Pending Review",
      value: stats.pending_reels ?? 0,
      sub: stats.processing_now > 0 ? `${stats.processing_now} processing now` : "Click Summarize to analyze",
      icon: "bi-clock-fill",
      color: "var(--neutral)",
      glow: "rgba(215,174,74,.08)",
    },
  ];

  document.getElementById("stats-row").innerHTML = cards.map(c => `
    <div class="col-6 col-md-3">
      <${c.link ? `a href="${c.link}"` : "div"} class="stat-card d-block text-decoration-none"
           style="--accent-glow:radial-gradient(circle, ${c.glow} 0%, transparent 70%)">
        <i class="bi ${c.icon} stat-icon" style="color:${c.color}"></i>
        <div class="stat-value" style="color:${c.color}">${c.value}</div>
        <div class="stat-label">${c.label}</div>
        ${c.sub ? `<div class="text-muted mt-1" style="font-size:.75rem">${c.sub}</div>` : ""}
      </${c.link ? "a" : "div"}>
    </div>
  `).join("");
}

function renderPipelineStatus(stats) {
  const bar = document.getElementById("pipeline-status-bar");
  if (!bar) return;

  if (stats.processing_now > 0) {
    bar.classList.remove("d-none");
    bar.innerHTML = `
      <div class="pipeline-status">
        <span class="pipeline-dot yellow is-processing"></span>
        <span>
          <strong>${stats.processing_now}</strong> reel${stats.processing_now > 1 ? "s" : ""} are being analyzed right now…
        </span>
        <span class="spinner-border spinner-border-sm text-accent ms-auto" style="width:14px;height:14px"></span>
      </div>`;
  } else if (stats.failed_reels > 0) {
    bar.classList.remove("d-none");
    bar.innerHTML = `
      <div class="pipeline-status">
        <span class="pipeline-dot" style="background:var(--bear)"></span>
        <span class="text-muted">
          ${stats.failed_reels} reel${stats.failed_reels > 1 ? "s" : ""} failed to process.
          Open each influencer to retry.
        </span>
      </div>`;
  } else {
    bar.classList.add("d-none");
  }
}

function renderLatest(latest) {
  const el = document.getElementById("latest-reels");
  if (!latest || !latest.length) {
    el.innerHTML = `
      <div class="col-12 empty-state">
        <span class="empty-icon">📊</span>
        No analyzed reels yet. Add an influencer and click <strong>Summarize</strong> on a reel to get started.
      </div>`;
    return;
  }

  el.innerHTML = latest.map(r => `
    <div class="col-md-6">
      <a href="/reel/${r.reel_db_id}" class="reel-card d-flex flex-column text-decoration-none">
        <div class="thumb-wrapper">
          <img src="${thumbFallback(r.thumbnail)}"
               onerror="this.src='https://placehold.co/640x360/141820/4f7cff?text=Reel'">
          <div class="thumb-overlay"></div>
          <div class="thumb-status">${r.sentiment ? sentimentBadge(r.sentiment) : ""}</div>
        </div>
        <div class="body">
          <div class="title">${escapeHtml(r.title || "(untitled reel)")}</div>
          <div class="meta mb-2">${fmtRelative(r.posted_at)}</div>
          ${r.summary ? `<div class="summary-snippet">${escapeHtml(r.summary)}</div>` : ""}
          ${r.stocks && r.stocks.length ? `<div class="mt-2">${tags(r.stocks, 3)}</div>` : ""}
        </div>
      </a>
    </div>
  `).join("");
}

function renderTrending(topics) {
  const el = document.getElementById("trending-topics");
  if (!topics || !topics.length) {
    el.innerHTML = `<div class="text-muted small text-center py-3">No topics analyzed yet.</div>`;
    return;
  }
  const max = Math.max(...topics.map(t => t.count));
  el.innerHTML = topics.map(t => `
    <div class="topic-bar">
      <span class="topic-name">${escapeHtml(t._id)}</span>
      <div class="topic-track">
        <div class="topic-fill" style="width:${(t.count / max) * 100}%"></div>
      </div>
      <span class="topic-count">${t.count}</span>
    </div>
  `).join("");
}

loadDashboard();
