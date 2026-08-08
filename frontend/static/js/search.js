const form = document.getElementById("search-form");
const input = document.getElementById("search-input");
const resultsEl = document.getElementById("search-results");

function paramFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("q") || "";
}

async function runSearch(q) {
  if (!q) return;
  resultsEl.innerHTML = `<div class="text-center text-muted py-4">Searching…</div>`;
  try {
    const data = await apiGet(`/api/search?q=${encodeURIComponent(q)}`);
    render(data, q);
  } catch (e) {
    resultsEl.innerHTML = `<div class="empty-state">Search failed: ${escapeHtml(e.message)}</div>`;
  }
}

function render(data, q) {
  const hasReels = data.reels && data.reels.length;
  const hasInfluencers = data.influencers && data.influencers.length;

  if (!hasReels && !hasInfluencers) {
    resultsEl.innerHTML = `<div class="empty-state">No results found for "${escapeHtml(q)}".</div>`;
    return;
  }

  let html = "";

  if (hasInfluencers) {
    html += `<div class="section-title mt-0">Influencers</div><div class="row g-3 mb-4">`;
    html += data.influencers.map(inf => `
      <div class="col-md-4">
        <a href="/influencer/${inf.id}" class="reel-card d-block p-3">
          <div class="title">@${escapeHtml(inf.username)}</div>
        </a>
      </div>
    `).join("");
    html += `</div>`;
  }

  if (hasReels) {
    html += `<div class="section-title">Reels & Analyses</div><div class="row g-3">`;
    html += data.reels.map(r => `
      <div class="col-md-4">
        <a href="/reel/${r.reel_db_id}" class="reel-card d-block">
          <img src="${thumbFallback(r.thumbnail)}" onerror="this.src='https://placehold.co/400x300/1e2330/97a1b3?text=Reel'">
          <div class="body">
            <div class="title">${escapeHtml(r.title || "(untitled)")}</div>
            <div class="meta mb-2">${r.influencer_username ? "@" + escapeHtml(r.influencer_username) : ""}</div>
            <div class="mb-2">${sentimentBadge(r.sentiment)}</div>
            ${r.summary ? `<div class="meta">${escapeHtml(r.summary).slice(0, 100)}…</div>` : ""}
          </div>
        </a>
      </div>
    `).join("");
    html += `</div>`;
  }

  resultsEl.innerHTML = html;
}

form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const q = input.value.trim();
  const url = new URL(window.location);
  url.searchParams.set("q", q);
  window.history.replaceState({}, "", url);
  runSearch(q);
});

const initial = paramFromUrl();
if (initial) {
  input.value = initial;
  runSearch(initial);
}
