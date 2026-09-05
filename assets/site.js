/* Case Analytica: shared render logic. Requires data.js loaded first. */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function videoCardHtml(v) {
  // Self-hosted video: plays inline, so the card is not a link (no nested controls).
  if (v.published && v.videoFile) {
    const poster = v.poster ? ` poster="${escapeHtml(v.poster)}"` : "";
    return `
      <div class="card">
        <video class="thumb-video" controls preload="none" playsinline${poster}
               src="${escapeHtml(v.videoFile)}"></video>
        <div class="body">
          <span class="cat">${escapeHtml(v.category)}</span>
          <h3>${escapeHtml(v.title)}</h3>
          <p>${escapeHtml(v.description)}</p>
        </div>
      </div>`;
  }
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

/* ---------------------------------------------------------------------------
   Hero headline rotator.

   The <h1> keeps its real, crawlable text. The first phrase is authored
   directly in index.html and is what search engines, no-JS readers and the
   reduced-motion path all see; the remaining phrases live in a <template> and
   are purely decorative. Nothing about the page's meaning depends on this
   running. (Vera does the opposite -- their <h1> is the logo and the rotating
   phrases are plain divs. They can afford that; this site earns its traffic on
   long-tail search, so the headline has to stay a real heading.)

   Deliberately no carousel library: the site's CSP is script-src 'self', so a
   CDN bundle would be blocked outright, and this is about forty lines.
   --------------------------------------------------------------------------- */
function initHeroRotator() {
  const h1 = document.querySelector(".hero-rotator");
  const tpl = document.getElementById("hero-rotator-lines");
  const first = h1 && h1.querySelector(".rot-line");
  if (!h1 || !tpl || !first) return;

  // People land on this page in the middle of the worst week of their life.
  // Movement is a nicety; if the OS asks for less of it, they keep the static
  // headline and nothing else about the page changes.
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const extras = Array.from(tpl.content.querySelectorAll(".rot-line"));
  if (!extras.length) return;

  const stack = document.createElement("span");
  stack.className = "rot-stack";
  h1.insertBefore(stack, first);
  stack.appendChild(first);
  extras.forEach(node => {
    const clone = node.cloneNode(true);
    // Only the authored first line is the heading's accessible name. The rest
    // are decoration, so screen readers should not announce them at all.
    clone.setAttribute("aria-hidden", "true");
    stack.appendChild(clone);
  });

  const lines = Array.from(stack.querySelectorAll(".rot-line"));
  lines[0].classList.add("is-active");

  // Every line is absolutely positioned, so the block would collapse without an
  // explicit height. Reserve the tallest phrase's height up front: at phone
  // widths these wrap to different line counts and the page would otherwise
  // jump on every swap.
  function reserveHeight() {
    stack.style.minHeight = "0px";
    const tallest = lines.reduce((max, el) => Math.max(max, el.offsetHeight), 0);
    stack.style.minHeight = tallest + "px";
  }
  reserveHeight();
  // Fraunces swaps in after first paint and changes the metrics, so measure
  // again once it has actually landed.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(reserveHeight);

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(reserveHeight, 150);
  });

  let index = 0;
  let timer = null;
  const HOLD = 5200;

  function advance() {
    const current = lines[index];
    index = (index + 1) % lines.length;
    const next = lines[index];
    current.classList.remove("is-active");
    current.classList.add("is-leaving");
    next.classList.add("is-active");
    setTimeout(() => current.classList.remove("is-leaving"), 700);
  }

  function play() {
    if (!timer) timer = setInterval(advance, HOLD);
  }
  function pause() {
    clearInterval(timer);
    timer = null;
  }

  // WCAG 2.2.2: auto-advancing content needs a way to stop. Hovering or
  // keyboard-focusing the hero halts it, and it never runs in a background tab.
  h1.addEventListener("mouseenter", pause);
  h1.addEventListener("mouseleave", play);
  h1.closest(".hero").addEventListener("focusin", pause);
  h1.closest(".hero").addEventListener("focusout", play);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause(); else play();
  });

  play();
}
