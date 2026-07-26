/* Case Analytica — shared render logic. Requires data.js loaded first. */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function videoCardHtml(v) {
  const thumb = v.published && v.youtubeId
    ? `<div class="thumb" style="background-image:url('https://i.ytimg.com/vi/${escapeHtml(v.youtubeId)}/hqdefault.jpg')"><span class="fmt-badge">${escapeHtml(v.format)}</span></div>`
    : `<div class="thumb placeholder"><span>COMING SOON</span><span class="fmt-badge">${escapeHtml(v.format)}</span></div>`;
  const href = v.published && v.youtubeId ? `https://www.youtube.com/watch?v=${escapeHtml(v.youtubeId)}` : "#";
  const target = v.published && v.youtubeId ? ' target="_blank" rel="noopener"' : "";
  return `
    <a class="card" href="${href}"${target} style="text-decoration:none;color:inherit;">
      ${thumb}
      <div class="body">
        <span class="cat">${escapeHtml(v.category)}</span>
        <h3>${escapeHtml(v.title)}</h3>
        <p>${escapeHtml(v.description)}</p>
      </div>
    </a>`;
}

function articleCardHtml(a) {
  return `
    <a class="card" href="articles/${escapeHtml(a.slug)}.html" style="text-decoration:none;color:inherit;">
      <div class="body">
        <span class="cat">${escapeHtml(a.category)}</span>
        <h3>${escapeHtml(a.title)}</h3>
        <p>${escapeHtml(a.excerpt)}</p>
        <span class="meta">${escapeHtml(a.date)}</span>
      </div>
    </a>`;
}

function renderVideoGrid(targetId, list) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = list.map(videoCardHtml).join("");
}

function renderArticleGrid(targetId, list) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = list.map(articleCardHtml).join("");
}

function initVideoFilters() {
  const chipsEl = document.getElementById("video-chips");
  if (!chipsEl) return;
  const categories = ["All", ...Array.from(new Set(VIDEOS.map(v => v.category)))];
  chipsEl.innerHTML = categories.map((c, i) =>
    `<button class="chip${i === 0 ? " active" : ""}" data-cat="${escapeHtml(c)}">${escapeHtml(c)}</button>`
  ).join("");
  chipsEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    chipsEl.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    const cat = btn.dataset.cat;
    const filtered = cat === "All" ? VIDEOS : VIDEOS.filter(v => v.category === cat);
    renderVideoGrid("video-grid", filtered);
  });
}
