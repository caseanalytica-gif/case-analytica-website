/* Case Analytica: shared render logic. Requires data.js loaded first. */

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/* "Finished" means the file or the YouTube id is actually there, not just that
   the entry is marked published -- a published flag with no source still
   renders a COMING SOON placeholder, and those belong in the dropdown. */
function isVideoLive(v) {
  return !!(v.published && (v.videoFile || v.youtubeId));
}

function videoCardHtml(v, opts) {
  const compact = !!(opts && opts.compact);
  // Self-hosted video: plays inline, so the card is not a link (no nested controls).
  if (v.published && v.videoFile) {
    const poster = v.poster ? ` poster="${escapeHtml(v.poster)}"` : "";
    return `
      <div class="card${compact ? " card-compact" : ""}">
        <video class="thumb-video" controls preload="none" playsinline${poster}
               src="${escapeHtml(v.videoFile)}"></video>
        <div class="body">
          <span class="cat">${escapeHtml(v.category)}</span>
          <h3>${escapeHtml(v.title)}</h3>
          ${compact ? "" : `<p>${escapeHtml(v.description)}</p>`}
        </div>
      </div>`;
  }
  const thumb = v.published && v.youtubeId
    ? `<div class="thumb" style="background-image:url('https://i.ytimg.com/vi/${escapeHtml(v.youtubeId)}/hqdefault.jpg')"><span class="fmt-badge">${escapeHtml(v.format)}</span></div>`
    : `<div class="thumb placeholder"><span>COMING SOON</span><span class="fmt-badge">${escapeHtml(v.format)}</span></div>`;
  const href = v.published && v.youtubeId ? `https://www.youtube.com/watch?v=${escapeHtml(v.youtubeId)}` : "#";
  const target = v.published && v.youtubeId ? ' target="_blank" rel="noopener"' : "";
  return `
    <a class="card${compact ? " card-compact" : ""}" href="${href}"${target} style="text-decoration:none;color:inherit;">
      ${thumb}
      <div class="body">
        <span class="cat">${escapeHtml(v.category)}</span>
        <h3>${escapeHtml(v.title)}</h3>
        ${compact ? "" : `<p>${escapeHtml(v.description)}</p>`}
      </div>
    </a>`;
}

/* ---------------------------------------------------------------------------
   Article thumbnails.

   Nothing is drawn any more. Each card tries real images in order and takes the
   first that loads:

     1. `image` on the article in data.js   -- a specific photo, shareable
                                               between articles
     2. assets/photos/<slug>.jpg            -- drop-in per article, no editing
     3. assets/social/thumbs/<slug>.jpg     -- the article's own social card,
                                               resized for display

   If none of them exist the card simply has no picture, which is what it looked
   like before any of this and is better than a placeholder.

   The social cards are the stand-in until real photographs arrive. They are
   display copies, not the originals: the full cards run to 713KB each because
   they are built at 2400x1254 for LinkedIn, and shipping those to a phone to
   show them 300px wide would cost 10MB a page.
   --------------------------------------------------------------------------- */
function articleThumbSources(a) {
  const list = [];
  if (a.image) list.push(a.image);
  if (a.slug) {
    list.push("assets/photos/" + a.slug + ".jpg");
    list.push("assets/social/thumbs/" + a.slug + ".jpg");
  }
  return list;
}

function articleThumbHtml(a) {
  const srcs = articleThumbSources(a);
  if (!srcs.length) return "";
  const credit = a.imageCredit
    ? `<span class="thumb-credit">${escapeHtml(a.imageCredit)}</span>`
    : "";
  return `<div class="thumb thumb-figure">` +
    `<img class="thumb-photo-img" src="${escapeHtml(srcs[0])}" ` +
    `data-fallbacks="${escapeHtml(srcs.slice(1).join("|"))}" ` +
    `alt="${escapeHtml(a.imageAlt || "")}" loading="lazy" decoding="async">` +
    `${credit}</div>`;
}

/* Handlers are attached here rather than written inline, so this keeps working
   under the script-src 'self' CSP the Cloudflare worker is meant to set. */
function attachThumbPhotos(root) {
  root.querySelectorAll("img.thumb-photo-img").forEach(img => {
    const fig = img.closest(".thumb-figure");

    function next() {
      const queue = (img.dataset.fallbacks || "").split("|").filter(Boolean);
      if (!queue.length) {
        // Nothing left to try: drop the picture area entirely rather than
        // leaving an empty box above the headline.
        if (fig) fig.remove(); else img.remove();
        return;
      }
      img.dataset.fallbacks = queue.slice(1).join("|");
      img.src = queue[0];
    }

    img.addEventListener("load", () => { if (fig) fig.classList.add("has-photo"); });
    img.addEventListener("error", next);
    if (img.complete) {
      if (img.naturalWidth > 0) { if (fig) fig.classList.add("has-photo"); }
      else next();
    }
  });
}

function articleCardHtml(a, opts) {
  const compact = !!(opts && opts.compact);
  const excerpt = compact ? "" : `<p>${escapeHtml(a.excerpt)}</p>`;
  return `
    <a class="card${compact ? " card-compact" : ""}" href="articles/${escapeHtml(a.slug)}.html" style="text-decoration:none;color:inherit;">
      ${articleThumbHtml(a)}
      <div class="body">
        <span class="cat">${escapeHtml(a.category)}</span>
        <h3>${escapeHtml(a.title)}</h3>
        ${excerpt}
        <span class="meta">${escapeHtml(a.date)}</span>
      </div>
    </a>`;
}

function renderVideoGrid(targetId, list, opts) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = list.map(v => videoCardHtml(v, opts)).join("");
  // An empty grid should take up no room at all, not leave a gap.
  el.hidden = !list.length;
}

/* Videos that aren't shot and uploaded yet go behind a disclosure instead of
   filling the front page with COMING SOON boxes. Titles only: it reads as a
   list of what's coming, which is what it is. */
function renderUpcomingVideos(targetId, list) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.hidden = !list.length;
  if (!list.length) { el.innerHTML = ""; return; }
  el.innerHTML =
    `<summary>${list.length} more in the works</summary>` +
    `<ul class="upcoming-list">` +
    list.map(v => `<li><span class="cat">${escapeHtml(v.category)}</span>${escapeHtml(v.title)}</li>`).join("") +
    `</ul>`;
}

function renderArticleGrid(targetId, list, opts) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = list.map(a => articleCardHtml(a, opts)).join("");
  attachThumbPhotos(el);
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
   CDN bundle would be blocked outright.
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

  // Caption cadence. Words land one at a time, the underline is drawn under the
  // key phrase once that phrase has finished arriving, then the whole line
  // holds long enough to actually be read before it goes.
  const STEP = 105;            // gap between one word landing and the next
  const WORD_IN = 340;         // must match the .cc-w transition in style.css
  const RULE_LAG = 420;        // beat between the key phrase landing and the rule
  const RULE_DRAW = 560;       // must match the .cc-key transition in style.css
  const HOLD = 2600;           // dwell on the finished line
  const EXIT = 460;            // must match the .rot-line fade in style.css

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

  // Split every line into per-word spans so they can be staggered. Element
  // children (the .cc-key wrapper) are recursed into rather than flattened, so
  // the underlined phrase stays one inline box and its rule can span it.
  function splitWords(node, out) {
    Array.from(node.childNodes).forEach(kid => {
      if (kid.nodeType === 3) {
        const frag = document.createDocumentFragment();
        kid.textContent.split(/(\s+)/).forEach(chunk => {
          if (!chunk) return;
          if (/^\s+$/.test(chunk)) { frag.appendChild(document.createTextNode(" ")); return; }
          const w = document.createElement("span");
          w.className = "cc-w";
          w.textContent = chunk;
          out.push(w);
          frag.appendChild(w);
        });
        node.replaceChild(frag, kid);
      } else if (kid.nodeType === 1) {
        splitWords(kid, out);
      }
    });
    return out;
  }

  lines.forEach(line => {
    const words = splitWords(line, []);
    words.forEach((w, i) => { w.style.transitionDelay = (i * STEP) + "ms"; });

    // The rule starts drawing a beat after the last word of the phrase it sits
    // under has landed, not after the whole line has.
    let ruleEnd = 0;
    line.querySelectorAll(".cc-key").forEach(key => {
      const kw = key.querySelectorAll(".cc-w");
      const lastIdx = kw.length ? words.indexOf(kw[kw.length - 1]) : 0;
      const start = lastIdx * STEP + WORD_IN + RULE_LAG;
      key.style.transitionDelay = start + "ms";
      ruleEnd = Math.max(ruleEnd, start + RULE_DRAW);
    });

    const wordsEnd = words.length ? (words.length - 1) * STEP + WORD_IN : 0;
    line.dataset.ccDwell = Math.max(wordsEnd, ruleEnd) + HOLD;
  });

  // Every line is absolutely positioned, so the block would collapse without an
  // explicit height. Reserve the tallest phrase's height up front: at phone
  // widths these wrap to different line counts and the page would otherwise
  // jump on every swap. (Words are hidden with opacity, not display, so they
  // still measure correctly while invisible.)
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

  // A single pending step at a time, with its remaining time banked on pause so
  // hovering mid-caption doesn't cost the reader the rest of the line.
  let index = 0;
  let timer = null;
  let pendingFn = null;
  let pendingDelay = 0;
  let startedAt = 0;
  let paused = false;

  function after(ms, fn) {
    pendingFn = fn;
    pendingDelay = ms;
    startedAt = Date.now();
    if (paused) return;
    timer = setTimeout(() => {
      timer = null;
      const f = pendingFn;
      pendingFn = null;
      f();
    }, ms);
  }

  function show() {
    const line = lines[index];
    line.classList.remove("is-leaving");
    line.classList.add("is-active");
    after(Number(line.dataset.ccDwell) || 4000, hide);
  }

  function hide() {
    const line = lines[index];
    line.classList.remove("is-active");
    line.classList.add("is-leaving");
    after(EXIT, () => {
      line.classList.remove("is-leaving");
      index = (index + 1) % lines.length;
      show();
    });
  }

  // WCAG 2.2.2: auto-advancing content needs a way to stop. Hovering or
  // keyboard-focusing the hero halts it, and it never runs in a background tab.
  function pause() {
    if (paused) return;
    paused = true;
    if (timer) {
      clearTimeout(timer);
      timer = null;
      pendingDelay = Math.max(0, pendingDelay - (Date.now() - startedAt));
    }
  }
  function play() {
    if (!paused) return;
    paused = false;
    if (pendingFn) after(pendingDelay, pendingFn);
  }

  h1.addEventListener("mouseenter", pause);
  h1.addEventListener("mouseleave", play);
  h1.closest(".hero").addEventListener("focusin", pause);
  h1.closest(".hero").addEventListener("focusout", play);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause(); else play();
  });

  show();
}
