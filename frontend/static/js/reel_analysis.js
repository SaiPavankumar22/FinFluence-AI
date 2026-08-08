const POLL_INTERVAL_MS = 8000;
const POLL_MAX_ATTEMPTS = 60;

function reelIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts[1];
}

function stageMeta(stage) {
  const stages = {
    queued:           { label: "Queued",              detail: "Your reel is waiting to start." },
    downloading:      { label: "Downloading reel",    detail: "Pulling the video from Instagram before processing starts." },
    extracting_audio: { label: "Preparing audio",     detail: "Converting the reel to a speech-friendly audio track." },
    transcribing:     { label: "Transcribing speech", detail: "Sarvam is turning the full reel audio into text." },
    translating:      { label: "Translating transcript", detail: "Non-English speech is being normalized into English." },
    summarizing:      { label: "Building market summary", detail: "The LLM is extracting signals, risks, and opportunities." },
    completed:        { label: "Completed",            detail: "The reel analysis is ready." },
    failed:           { label: "Failed",               detail: "This run stopped before the analysis completed." },
  };
  return stages[stage] || { label: "Processing", detail: "The pipeline is still running." };
}

// colClass = Bootstrap column class; defaults to 4-wide layout (for full-width areas)
function metricCard(label, value, sub = "", colClass = "col-sm-6 col-xl-3") {
  return `
    <div class="${colClass}">
      <div class="analysis-metric h-100">
        <div class="analysis-metric__label">${escapeHtml(label)}</div>
        <div class="analysis-metric__value">${escapeHtml(value)}</div>
        ${sub ? `<div class="analysis-metric__sub">${escapeHtml(sub)}</div>` : ""}
      </div>
    </div>`;
}

// full=true keeps h-100 (useful when inside a same-height row)
function chipBlock(label, icon, items, tone = "", full = true) {
  if (!items || !items.length) return "";
  return `
    <div class="analysis-section ${full ? "h-100" : ""}">
      <div class="section-label"><i class="bi ${icon} ${tone}"></i> ${escapeHtml(label)}</div>
      <div>${items.map(item => `<span class="tag">${escapeHtml(item)}</span>`).join("")}</div>
    </div>`;
}

function factPill(label, value, tone = "") {
  if (!value) return "";
  return `
    <div class="analysis-fact ${tone}">
      <div class="analysis-fact__label">${escapeHtml(label)}</div>
      <div class="analysis-fact__value">${escapeHtml(value)}</div>
    </div>`;
}

// full=true keeps h-100; pass false for standalone sections (avoids giant empty space)
function bulletSection(label, icon, items, colorVar, full = true) {
  if (!items || !items.length) return "";
  return `
    <div class="analysis-section ${full ? "h-100" : "mb-3"}">
      <div class="section-label"><i class="bi ${icon}" style="color:${colorVar}"></i> ${escapeHtml(label)}</div>
      <ul class="mb-0 ps-3 analysis-list">
        ${items.map(item => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>`;
}

function summaryParagraphs(summary) {
  if (!summary) return `<p class="mb-0">No summary available.</p>`;
  const sentences = summary
    .split(/(?<=[.!?])\s+/)
    .map(part => part.trim())
    .filter(Boolean);
  if (!sentences.length) return `<p class="mb-0">${escapeHtml(summary)}</p>`;
  return sentences.map(sentence => `<p>${escapeHtml(sentence)}</p>`).join("");
}

function firstNonEmpty(items) {
  return (items || []).find(Boolean) || "";
}

function transcriptColumn(title, body) {
  return `
    <div class="col-md-6">
      <div class="fw-semibold mb-2 transcript-heading">${title}</div>
      <div class="transcript-box">${escapeHtml(body || "-")}</div>
    </div>`;
}

function renderProcessingView(reel, analysis) {
  const id = reel.id;
  const stage = stageMeta(reel.processing_stage);
  const attempt = parseInt(sessionStorage.getItem(`poll_${id}`) || "0", 10) + 1;
  sessionStorage.setItem(`poll_${id}`, String(attempt));
  const elapsed = reel.processing_started_at ? fmtRelative(reel.processing_started_at) : "just now";
  const title = reel.title || "(untitled reel)";
  return {
    html: `
      <a href="javascript:history.back()" class="text-muted d-inline-flex align-items-center gap-1 mb-3 analysis-backlink">
        <i class="bi bi-arrow-left"></i> Back
      </a>
      <div class="panel processing-panel">
        <div class="processing-layout">
          <div class="processing-media">
            <img
              src="${thumbFallback(reel.thumbnail)}"
              class="processing-thumb"
              alt="Reel thumbnail"
              onerror="this.src='https://placehold.co/160x284/141820/4f7cff?text=Reel'"
            >
          </div>
          <div class="processing-body">
            <div class="processing-badges">
              <span class="badge-processing">
                <span class="spinner-border spinner-border-sm me-1" style="width:.7rem;height:.7rem;border-width:2px"></span>
                ${escapeHtml(stage.label)}
              </span>
              <span class="tag">Check ${attempt}/${POLL_MAX_ATTEMPTS}</span>
              ${reel.transcript_language
                ? `<span class="tag">${escapeHtml(String(reel.transcript_language).toUpperCase())}</span>`
                : ""}
            </div>

            <h3 class="processing-title" title="${escapeHtml(title)}">${escapeHtml(title)}</h3>
            <p class="processing-detail">${escapeHtml(stage.detail)}</p>

            <div class="pipeline-progress mb-3">
              <div class="pipeline-progress__bar"></div>
            </div>

            <div class="processing-metrics">
              <div class="analysis-metric">
                <div class="analysis-metric__label">Started</div>
                <div class="analysis-metric__value">${escapeHtml(elapsed)}</div>
              </div>
              <div class="analysis-metric">
                <div class="analysis-metric__label">Step</div>
                <div class="analysis-metric__value">${escapeHtml(stage.label)}</div>
              </div>
              <div class="analysis-metric">
                <div class="analysis-metric__label">ETA</div>
                <div class="analysis-metric__value">&lt; 8 min</div>
              </div>
              <div class="analysis-metric">
                <div class="analysis-metric__label">Tone</div>
                <div class="analysis-metric__value">${escapeHtml(analysis.sentiment || "—")}</div>
              </div>
            </div>

            <div class="analysis-inline-note mt-3 mb-3">
              <i class="bi bi-info-circle me-2"></i>
              Re-summarize is running in the background. This page refreshes automatically.
            </div>

            <div class="d-flex flex-wrap gap-2">
              <a href="${reel.reel_url || "#"}" target="_blank" rel="noopener" class="btn btn-outline-secondary btn-sm">
                <i class="bi bi-instagram me-1"></i>Instagram
              </a>
              <button class="btn btn-outline-secondary btn-sm" onclick="window.location.reload()">
                <i class="bi bi-arrow-clockwise me-1"></i>Refresh
              </button>
            </div>
          </div>
        </div>
      </div>`,
    attempt,
  };
}

function renderPendingView(reel, id) {
  return `
    <div class="panel p-4">
      <a href="javascript:history.back()" class="text-muted d-inline-flex align-items-center gap-1 mb-3 analysis-backlink">
        <i class="bi bi-arrow-left"></i> Back
      </a>
      <div class="processing-layout">
        <div class="processing-media">
          <img
            src="${thumbFallback(reel.thumbnail)}"
            class="processing-thumb"
            alt="Reel thumbnail"
            onerror="this.src='https://placehold.co/140x248/141820/4f7cff?text=Reel'"
          >
        </div>
        <div class="processing-body">
          <h5 class="processing-title">${escapeHtml(reel.title || "(untitled reel)")}</h5>
          <div class="text-muted mb-3">${fmtDate(reel.posted_at)}</div>
          ${reel.process_error
            ? `<div class="alert analysis-error">
                 <i class="bi bi-exclamation-triangle me-2"></i><strong>Processing Error:</strong>
                 <div class="mt-1 small">${escapeHtml(reel.process_error)}</div>
               </div>`
            : `<div class="text-muted mb-3">This reel has not been analyzed yet.</div>`}
          <div class="d-flex flex-wrap gap-2">
            <button class="btn btn-primary" id="summarize-btn" onclick="triggerProcess('${id}')">
              <i class="bi bi-cpu me-2"></i>Summarize Now
            </button>
            <a href="${reel.reel_url || "#"}" target="_blank" rel="noopener" class="btn btn-outline-secondary">
              <i class="bi bi-instagram me-1"></i>Instagram
            </a>
          </div>
        </div>
      </div>
    </div>`;
}

function renderAnalyzedView(reel, transcript, analysis) {
  const metrics = reel.processing_metrics || {};
  const headline = analysis.headline || analysis.summary || "Market intelligence summary";
  const language = transcript.language || reel.transcript_language || "unknown";
  const topStock = firstNonEmpty(analysis.stocks);
  const topSector = firstNonEmpty(analysis.sectors);
  const topRisk = firstNonEmpty(analysis.risks);
  const topOpportunity = firstNonEmpty(analysis.opportunities);
  const topTakeaway = firstNonEmpty(analysis.takeaways);

  return `
    <a href="javascript:history.back()" class="text-muted d-inline-flex align-items-center gap-1 mb-3 analysis-backlink">
      <i class="bi bi-arrow-left"></i> Back
    </a>

    <div class="row g-4">
      <!-- ── Left sidebar ── -->
      <div class="col-lg-4 col-xl-3">
        <div class="panel p-3 h-100">
          <img
            src="${thumbFallback(reel.thumbnail)}"
            class="w-100 rounded-4 mb-3 analysis-thumb"
            onerror="this.src='https://placehold.co/300x533/141820/4f7cff?text=Reel'"
          >
          <a class="btn btn-outline-secondary w-100 mb-2 btn-sm" href="${reel.reel_url}" target="_blank" rel="noopener">
            <i class="bi bi-instagram me-1"></i>View on Instagram
          </a>
          <div class="text-muted small text-center mb-2">${fmtDate(reel.posted_at)}</div>
          <div class="divider"></div>
          <!-- Use col-6 (2-per-row) so cards fit in this narrow sidebar -->
          <div class="row g-2">
            ${metricCard("Language", String(language).toUpperCase(), "", "col-6")}
            ${metricCard("Total Time", fmtDuration(metrics.total_seconds), "", "col-6")}
            ${metricCard("Transcript", fmtDuration(metrics.transcription_seconds), "Sarvam", "col-6")}
            ${metricCard("LLM Summary", fmtDuration(metrics.analysis_seconds), "Nebius", "col-6")}
          </div>
          <div class="divider"></div>
          <div class="d-flex flex-column gap-2">
            <button class="btn btn-primary w-100" id="resummarize-btn" onclick="triggerResummarize('${reel.id}')">
              <i class="bi bi-arrow-repeat me-2"></i>Re-summarize
            </button>
            <button class="btn btn-outline-secondary w-100" onclick="openEditModal()" data-reel-id="${reel.id}">
              <i class="bi bi-pencil me-2"></i>Edit Analysis
            </button>
            <button class="btn btn-outline-danger w-100" onclick="triggerDeleteAnalysis('${reel.id}')">
              <i class="bi bi-trash me-2"></i>Delete Summary
            </button>
          </div>
        </div>
      </div>

      <!-- ── Main content ── -->
      <div class="col-lg-8 col-xl-9">
        <div class="analysis-hero mb-3">
          <div class="d-flex align-items-start justify-content-between flex-wrap gap-2 mb-3">
            <div>
              <div class="analysis-hero__eyebrow">Reel Intelligence Brief</div>
              <h2 class="analysis-hero__title">${escapeHtml(reel.title || "(untitled reel)")}</h2>
            </div>
            ${sentimentBadge(analysis.sentiment)}
          </div>
          <div class="analysis-headline">${escapeHtml(headline)}</div>
          <div class="analysis-hero__meta">
            <span><i class="bi bi-clock me-1"></i>${fmtDate(reel.posted_at)}</span>
            <span><i class="bi bi-translate me-1"></i>${escapeHtml(String(language).toUpperCase())}</span>
            <span><i class="bi bi-speedometer2 me-1"></i>${fmtDuration(metrics.total_seconds)} total</span>
          </div>
        </div>

        <div class="analysis-brief-grid mb-3">
          ${factPill("Top Stock", topStock, "is-bull")}
          ${factPill("Main Sector", topSector)}
          ${factPill("Key Risk", topRisk, "is-bear")}
          ${factPill("Best Opportunity", topOpportunity, "is-accent")}
        </div>

        <div class="analysis-section analysis-summary mb-3">
          <div class="section-label"><i class="bi bi-card-text text-accent"></i> Executive Summary</div>
          <div class="analysis-summary__body">
            ${summaryParagraphs(analysis.summary)}
          </div>
        </div>

        <div class="analysis-section analysis-thesis mb-3">
          <div class="section-label"><i class="bi bi-lightning-charge text-accent"></i> Quick Investor Read</div>
          <div class="analysis-thesis__content">
            <div class="analysis-thesis__takeaway">${escapeHtml(topTakeaway || headline)}</div>
            <div class="analysis-thesis__support">This is the fastest way to understand the reel without reading the full transcript.</div>
          </div>
        </div>

        <div class="row g-3 mb-3">
          <div class="col-md-6 col-xl-4">${chipBlock("Stocks Mentioned", "bi-graph-up", analysis.stocks, "text-bull") || `<div class="analysis-section h-100"><div class="section-label text-muted">No stocks mentioned</div></div>`}</div>
          <div class="col-md-6 col-xl-4">${chipBlock("IPOs", "bi-stars", analysis.ipos, "text-accent") || `<div class="analysis-section h-100"><div class="section-label text-muted">No IPOs mentioned</div></div>`}</div>
          <div class="col-md-6 col-xl-4">${chipBlock("Sectors", "bi-layers", analysis.sectors, "text-neutral") || `<div class="analysis-section h-100"><div class="section-label text-muted">No sectors mentioned</div></div>`}</div>
          <div class="col-md-6">${chipBlock("Economic Events", "bi-bank", analysis.economic_events) || `<div class="analysis-section h-100"><div class="section-label text-muted">No economic events</div></div>`}</div>
          <div class="col-md-6">${chipBlock("Geopolitical Events", "bi-globe2", analysis.geopolitical_events) || `<div class="analysis-section h-100"><div class="section-label text-muted">No geopolitical events</div></div>`}</div>
        </div>

        <div class="row g-3 mb-3">
          <div class="col-md-6">
            ${bulletSection("Risks", "bi-exclamation-triangle", analysis.risks, "var(--bear)")
              || `<div class="analysis-section h-100"><div class="section-label text-muted">No risks flagged</div></div>`}
          </div>
          <div class="col-md-6">
            ${bulletSection("Opportunities", "bi-lightbulb", analysis.opportunities, "var(--bull)")
              || `<div class="analysis-section h-100"><div class="section-label text-muted">No opportunities flagged</div></div>`}
          </div>
        </div>

        <!-- Takeaways: standalone — pass full=false to avoid giant empty space -->
        ${bulletSection("Retail Investor Takeaways", "bi-pin-angle", analysis.takeaways, "var(--accent)", false)
          || `<div class="analysis-section mb-3"><div class="section-label text-muted">No key takeaways extracted.</div></div>`}

        <div class="mt-3">
          <button
            class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#transcriptBlock"
          >
            <i class="bi bi-chat-text"></i> Show Transcript
            <i class="bi bi-chevron-down" style="font-size:.7rem"></i>
          </button>
          <div class="collapse mt-3" id="transcriptBlock">
            <div class="row g-3">
              ${transcriptColumn(`Original (${escapeHtml(String(language).toUpperCase())})`, transcript.original_text)}
              ${transcriptColumn("English Translation", transcript.english_translation)}
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

/* ─── Store analysis globally so edit modal can pre-fill ─── */
let _currentAnalysis = null;
let _currentReelId = null;

async function loadReel() {
  const id = reelIdFromPath();
  _currentReelId = id;
  const el = document.getElementById("reel-content");

  try {
    const data = await apiGet(`/api/reels/${id}`);
    const { reel, transcript, analysis } = data;
    _currentAnalysis = analysis;

    if (reel.processing && !reel.processed) {
      const { html, attempt } = renderProcessingView(reel, analysis || {});
      el.innerHTML = html;
      if (attempt < POLL_MAX_ATTEMPTS) {
        setTimeout(() => window.location.reload(), POLL_INTERVAL_MS);
      }
      return;
    }

    sessionStorage.removeItem(`poll_${id}`);

    if (!reel.processed) {
      el.innerHTML = renderPendingView(reel, id);
      return;
    }

    el.innerHTML = renderAnalyzedView(reel, transcript, analysis);
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><span class="empty-icon">!</span>Could not load reel: ${escapeHtml(e.message)}</div>`;
  }
}

async function triggerProcess(reelDbId) {
  const btn = document.getElementById("summarize-btn");
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Queuing...`;
  try {
    await apiPost(`/api/reels/${reelDbId}/process`, null);
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Analyzing...`;
    sessionStorage.removeItem(`poll_${reelDbId}`);
    setTimeout(() => window.location.reload(), 2000);
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-cpu me-2"></i>Summarize Now`;
    alert(`Could not start: ${e.message}`);
  }
}

async function triggerResummarize(reelDbId) {
  const btn = document.getElementById("resummarize-btn");
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Re-queuing...`;
  try {
    await apiPost(`/api/reels/${reelDbId}/resummarize`, null);
    sessionStorage.removeItem(`poll_${reelDbId}`);
    setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-arrow-repeat me-2"></i>Re-summarize`;
    alert(`Could not re-summarize: ${e.message}`);
  }
}

async function triggerDeleteAnalysis(reelDbId) {
  if (!confirm("Delete this summary? The reel will return to the 'pending' state. You can re-summarize it anytime.")) return;
  try {
    await apiDelete(`/api/reels/${reelDbId}/analysis`);
    window.location.reload();
  } catch (e) {
    alert(`Could not delete: ${e.message}`);
  }
}

/* ─── Edit modal ─────────────────────────────────────────── */

function csvToList(str) {
  return str.split(",").map(s => s.trim()).filter(Boolean);
}

function openEditModal() {
  if (!_currentAnalysis) return;
  const a = _currentAnalysis;

  document.getElementById("edit-summary").value   = a.summary || "";
  document.getElementById("edit-headline").value  = a.headline || "";
  document.getElementById("edit-sentiment").value = a.sentiment || "Neutral";
  document.getElementById("edit-stocks").value    = (a.stocks || []).join(", ");
  document.getElementById("edit-ipos").value      = (a.ipos || []).join(", ");
  document.getElementById("edit-sectors").value   = (a.sectors || []).join(", ");
  document.getElementById("edit-economic").value  = (a.economic_events || []).join(", ");
  document.getElementById("edit-geo").value       = (a.geopolitical_events || []).join(", ");
  document.getElementById("edit-risks").value     = (a.risks || []).join("\n");
  document.getElementById("edit-opportunities").value = (a.opportunities || []).join("\n");
  document.getElementById("edit-takeaways").value = (a.takeaways || []).join("\n");

  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById("editModal"));
  modal.show();
}

async function submitEditModal() {
  const id = _currentReelId;
  const saveBtn = document.getElementById("edit-save-btn");
  saveBtn.disabled = true;
  saveBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Saving...`;

  const payload = {
    summary:    document.getElementById("edit-summary").value.trim() || null,
    headline:   document.getElementById("edit-headline").value.trim() || null,
    sentiment:  document.getElementById("edit-sentiment").value || null,
    stocks:     csvToList(document.getElementById("edit-stocks").value),
    ipos:       csvToList(document.getElementById("edit-ipos").value),
    sectors:    csvToList(document.getElementById("edit-sectors").value),
    economic_events:      csvToList(document.getElementById("edit-economic").value),
    geopolitical_events:  csvToList(document.getElementById("edit-geo").value),
    risks:        document.getElementById("edit-risks").value.split("\n").map(s => s.trim()).filter(Boolean),
    opportunities: document.getElementById("edit-opportunities").value.split("\n").map(s => s.trim()).filter(Boolean),
    takeaways:    document.getElementById("edit-takeaways").value.split("\n").map(s => s.trim()).filter(Boolean),
  };

  // Remove null / empty arrays so backend doesn't overwrite with nulls
  Object.keys(payload).forEach(k => {
    if (payload[k] === null) delete payload[k];
    if (Array.isArray(payload[k]) && !payload[k].length) delete payload[k];
  });

  try {
    await apiPatch(`/api/reels/${id}/analysis`, payload);
    bootstrap.Modal.getInstance(document.getElementById("editModal")).hide();
    window.location.reload();
  } catch (e) {
    saveBtn.disabled = false;
    saveBtn.innerHTML = `<i class="bi bi-check2 me-2"></i>Save Changes`;
    alert(`Save failed: ${e.message}`);
  }
}

loadReel();
