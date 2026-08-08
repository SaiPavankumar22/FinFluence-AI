/* ── State ───────────────────────────────────────────────── */
let allReels = [];
let activeFilter = "all";
const pollingTimers = {};
const pollingAttempts = {};
const POLL_INTERVAL_MS = 8000;   // poll every 8 s
const POLL_MAX_ATTEMPTS = 45;    // give up after 45 × 8 s = 6 min

/* ── Helpers ─────────────────────────────────────────────── */
function influencerIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts[1];
}

function filteredReels() {
  switch (activeFilter) {
    case "processed": return allReels.filter(r => r.processed);
    case "pending":   return allReels.filter(r => !r.processed && !r.processing && !r.process_error);
    case "error":     return allReels.filter(r => r.process_error && !r.processed);
    default:          return allReels;
  }
}

/* ── Render header ───────────────────────────────────────── */
function renderHeader(inf) {
  const total     = inf.reel_count || 0;
  const processed = inf.processed_count || 0;
  const pending   = total - processed;
  const letter    = avatarLetter(inf.username);

  document.getElementById("influencer-header").innerHTML = `
    <div class="d-flex align-items-start gap-3 flex-wrap">
      <div class="avatar-circle">${letter}</div>
      <div class="flex-grow-1">
        <div class="d-flex align-items-center flex-wrap gap-2 mb-1">
          <h4 class="mb-0 fw-bold">@${escapeHtml(inf.username)}</h4>
          <span class="badge-sentiment ${inf.active ? "badge-active" : "badge-paused"} ms-1">
            <i class="bi bi-${inf.active ? "broadcast" : "pause-circle"} me-1"></i>
            ${inf.active ? "Auto-Monitoring" : "Paused"}
          </span>
        </div>
        ${inf.display_name ? `<div class="text-muted mb-2">${escapeHtml(inf.display_name)}</div>` : ""}
        <div class="d-flex flex-wrap gap-2">
          <span class="stat-pill"><span class="val">${total}</span><span class="lbl">reels</span></span>
          <span class="stat-pill" style="color:var(--bull)"><span class="val" style="color:var(--bull)">${processed}</span><span class="lbl">analyzed</span></span>
          <span class="stat-pill" style="color:var(--neutral)"><span class="val" style="color:var(--neutral)">${pending}</span><span class="lbl">pending</span></span>
          <span class="stat-pill"><span class="lbl">since</span><span class="val">${fmtDate(inf.created_at)}</span></span>
        </div>
      </div>
    </div>`;
}

/* ── Render single reel card ─────────────────────────────── */
function reelCardHtml(r) {
  const isProcessed  = r.processed;
  const isProcessing = r.processing && !r.processed;
  const hasError     = r.process_error && !r.processed;

  let statusBadge = "";
  if (isProcessed)  statusBadge = sentimentBadge(r.sentiment);
  else if (isProcessing) statusBadge = `<span class="badge-processing"><span class="spinner-border spinner-border-sm" style="width:8px;height:8px"></span> Analyzing…</span>`;
  else if (hasError)     statusBadge = `<span class="badge-error"><i class="bi bi-exclamation-triangle me-1"></i>Failed</span>`;
  else statusBadge = `<span class="badge-pending"><i class="bi bi-clock me-1"></i>Pending</span>`;

  let footerHtml = "";
  if (isProcessed) {
    footerHtml = `
      <div class="card-footer-area">
        ${r.topics && r.topics.length ? `<div class="mb-2">${tags(r.topics, 4)}</div>` : ""}
        <a href="/reel/${r.id}" class="btn-view-analysis">
          <i class="bi bi-bar-chart-line me-1"></i>View Full Analysis
        </a>
      </div>`;
  } else if (isProcessing) {
    footerHtml = `
      <div class="card-footer-area">
        <button class="btn-summarize" disabled>
          <span class="spinner-border spinner-border-sm me-2" style="width:12px;height:12px"></span>
          Analyzing… (this may take a few minutes)
        </button>
      </div>`;
  } else if (hasError) {
    footerHtml = `
      <div class="card-footer-area">
        <div class="text-muted mb-2" style="font-size:.74rem">
          <i class="bi bi-exclamation-circle me-1 text-bear"></i>${escapeHtml((r.process_error || "").slice(0, 120))}
        </div>
        <button class="btn-retry" onclick="startProcessing('${r.id}', this)">
          <i class="bi bi-arrow-clockwise me-1"></i>Retry Analysis
        </button>
      </div>`;
  } else {
    footerHtml = `
      <div class="card-footer-area">
        <button class="btn-summarize" onclick="startProcessing('${r.id}', this)">
          <i class="bi bi-cpu me-1"></i>Summarize this Reel
        </button>
      </div>`;
  }

  return `
    <div class="col-md-4 col-sm-6 reel-item" data-id="${r.id}"
         data-state="${isProcessed ? "processed" : isProcessing ? "processing" : hasError ? "error" : "pending"}">
      <div class="reel-card ${isProcessing ? "is-processing" : ""}">
        <div class="thumb-wrapper">
          <img src="${thumbFallback(r.thumbnail)}"
               onerror="this.src='https://placehold.co/640x360/141820/4f7cff?text=Reel'"
               loading="lazy">
          <div class="thumb-overlay"></div>
          <div class="thumb-status">${statusBadge}</div>
        </div>
        <div class="body">
          <div class="title">${escapeHtml(r.title || "(untitled reel)")}</div>
          <div class="meta d-flex align-items-center gap-2 mb-2">
            <i class="bi bi-calendar3 opacity-50"></i>${fmtDate(r.posted_at)}
          </div>
          ${footerHtml}
        </div>
      </div>
    </div>`;
}

/* ── Render reel grid ────────────────────────────────────── */
function renderReels() {
  const list = filteredReels();
  const el = document.getElementById("reel-list");
  const countLabel = document.getElementById("reel-count-label");

  const totalFiltered = list.length;
  countLabel.textContent = totalFiltered
    ? `Showing ${totalFiltered} of ${allReels.length} reels`
    : "";

  if (!list.length) {
    const msgs = {
      processed: "No analyzed reels yet. Click <strong>Summarize</strong> on any pending reel.",
      pending: "No pending reels! All reels have been analyzed.",
      error: "No failed reels.",
      all: "No reels found for this influencer.",
    };
    el.innerHTML = `
      <div class="col-12 empty-state">
        <span class="empty-icon">🎬</span>
        ${msgs[activeFilter] || msgs.all}
      </div>`;
    return;
  }

  el.innerHTML = list.map(reelCardHtml).join("");

  // Resume polling for any reels that are currently processing
  list.filter(r => r.processing && !r.processed).forEach(r => {
    if (!pollingTimers[r.id]) {
      pollProcessingStatus(r.id);
    }
  });
}

/* ── Start processing ────────────────────────────────────── */
async function startProcessing(reelDbId, buttonEl) {
  buttonEl.disabled = true;
  buttonEl.innerHTML = `<span class="spinner-border spinner-border-sm me-2" style="width:12px;height:12px"></span>Starting…`;

  try {
    const result = await apiPost(`/api/reels/${reelDbId}/process`, null);

    if (result.status === "already_processed") {
      window.location.href = `/reel/${reelDbId}`;
      return;
    }

    // Optimistically update local state
    const reel = allReels.find(r => r.id === reelDbId);
    if (reel) {
      reel.processing = true;
      reel.process_error = null;
    }
    renderReels();
    pollProcessingStatus(reelDbId);
  } catch (e) {
    buttonEl.disabled = false;
    buttonEl.innerHTML = `<i class="bi bi-cpu me-1"></i>Summarize this Reel`;
    alert(`Could not start processing: ${e.message}`);
  }
}

/* ── Poll for processing completion ──────────────────────── */
function stopPolling(reelDbId) {
  if (pollingTimers[reelDbId]) {
    clearInterval(pollingTimers[reelDbId]);
    delete pollingTimers[reelDbId];
  }
  delete pollingAttempts[reelDbId];
}

function pollProcessingStatus(reelDbId) {
  if (pollingTimers[reelDbId]) return;
  pollingAttempts[reelDbId] = 0;

  pollingTimers[reelDbId] = setInterval(async () => {
    pollingAttempts[reelDbId] = (pollingAttempts[reelDbId] || 0) + 1;

    // Give up after max attempts
    if (pollingAttempts[reelDbId] > POLL_MAX_ATTEMPTS) {
      stopPolling(reelDbId);
      const local = allReels.find(r => r.id === reelDbId);
      if (local) {
        local.processing = false;
        local.process_error = "Timed out waiting for result — click Retry to try again";
        renderReels();
      }
      return;
    }

    try {
      const data = await apiGet(`/api/reels/${reelDbId}`);
      const reel = data.reel;
      const local = allReels.find(r => r.id === reelDbId);

      if (!local) { stopPolling(reelDbId); return; }

      if (reel.processed) {
        stopPolling(reelDbId);
        local.processed  = true;
        local.processing = false;
        local.sentiment  = reel.sentiment || "Neutral";
        // Re-fetch full detail to get topics
        const full = await apiGet(`/api/influencers/${influencerIdFromPath()}`);
        const updated = (full.reels || []).find(r => r.id === reelDbId);
        if (updated) Object.assign(local, updated);
        renderReels();
      } else if (!reel.processing && reel.process_error) {
        stopPolling(reelDbId);
        local.processing    = false;
        local.process_error = reel.process_error;
        renderReels();
      }
    } catch (_) {
      // network blip — retry next tick
    }
  }, POLL_INTERVAL_MS);
}

// Stop all polling when the tab is closed or navigated away
window.addEventListener("beforeunload", () => {
  Object.keys(pollingTimers).forEach(stopPolling);
});
// Pause polling when tab goes background, resume when visible
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    Object.keys(pollingTimers).forEach(id => {
      clearInterval(pollingTimers[id]);
      delete pollingTimers[id];
    });
  } else {
    // Resume polling for any still-processing reels
    allReels.filter(r => r.processing && !r.processed).forEach(r => {
      pollProcessingStatus(r.id);
    });
  }
});

/* ── Load page ───────────────────────────────────────────── */
async function loadInfluencerDetail() {
  const id = influencerIdFromPath();
  const headerEl = document.getElementById("influencer-header");
  const reelsEl = document.getElementById("reel-list");

  try {
    const data = await apiGet(`/api/influencers/${id}`);
    allReels = data.reels || [];
    renderHeader(data.influencer);
    renderReels();
  } catch (e) {
    headerEl.innerHTML = `<div class="empty-state">Could not load influencer: ${escapeHtml(e.message)}</div>`;
    reelsEl.innerHTML = "";
  }
}

/* ── Filter tabs ─────────────────────────────────────────── */
document.getElementById("filter-tabs").addEventListener("click", (ev) => {
  const tab = ev.target.closest(".filter-tab");
  if (!tab) return;
  activeFilter = tab.dataset.filter;
  document.querySelectorAll(".filter-tab").forEach(t => t.classList.remove("active"));
  tab.classList.add("active");
  renderReels();
});

loadInfluencerDetail();
