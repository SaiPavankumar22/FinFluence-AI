async function loadInfluencers() {
  const el = document.getElementById("influencer-list");
  try {
    const list = await apiGet("/api/influencers");
    if (!list.length) {
      el.innerHTML = `
        <div class="col-12 empty-state">
          <span class="empty-icon">👥</span>
          No influencers tracked yet. Click <strong>Add Influencer</strong> to start monitoring someone.
        </div>`;
      return;
    }

    el.innerHTML = list.map(inf => {
      const total = inf.reel_count || 0;
      const processed = inf.processed_count || 0;
      const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
      const letter = avatarLetter(inf.username);

      return `
        <div class="col-md-4 col-sm-6">
          <a href="/influencer/${inf.id}" class="influencer-card">
            <div class="d-flex align-items-center gap-3">
              <div class="inf-avatar">${letter}</div>
              <div class="min-width-0">
                <div class="inf-username">@${escapeHtml(inf.username)}</div>
                <div class="inf-name">${escapeHtml(inf.display_name || "")}</div>
              </div>
              <span class="badge-sentiment ms-auto flex-shrink-0 ${inf.active ? "badge-active" : "badge-paused"}">
                ${inf.active ? "Active" : "Paused"}
              </span>
            </div>

            <div class="divider" style="margin:.75rem 0"></div>

            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="text-muted" style="font-size:.78rem">${total} reels tracked</span>
              <span class="text-muted" style="font-size:.78rem">${processed} analyzed</span>
            </div>
            <div class="inf-progress">
              <div class="inf-progress-bar" style="width:${pct}%"></div>
            </div>
            <div class="text-muted mt-1" style="font-size:.72rem; text-align:right">${pct}% analyzed</div>
          </a>
        </div>`;
    }).join("");
  } catch (e) {
    el.innerHTML = `<div class="col-12 empty-state">Could not load influencers: ${escapeHtml(e.message)}</div>`;
  }
}

document.getElementById("add-influencer-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const username = document.getElementById("username-input").value.trim().replace(/^@/, "");
  const displayName = document.getElementById("display-name-input").value.trim();
  const errBox = document.getElementById("add-error");
  const btn = document.getElementById("submit-btn");

  if (!username) return;
  errBox.classList.add("d-none");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Fetching reels…`;

  try {
    await apiPost("/api/influencers", { username, display_name: displayName || null });
    window.location.reload();
  } catch (e) {
    errBox.textContent = e.message;
    errBox.classList.remove("d-none");
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-plus-circle me-1"></i> Add & Fetch Reels`;
  }
});

loadInfluencers();
