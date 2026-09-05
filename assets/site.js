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

   Vera uses flat geometric artwork rather than photography, and that is the
   right call here for reasons beyond style: there is no honest stock photo of
   somebody's brother in a cell, and the ones that exist are all somebody else's
   worst day sold by the download. There are also 66 articles here with more
   arriving most days, so hand-made art per piece would stop happening by week
   three.

   So each card's mark is generated from the article itself. The category picks
   the motif -- what the shape is actually saying -- and a hash of the slug picks
   the proportions, the counts and the accent. Same article, same mark, every
   time, on every device, with no image files to draw, name or ship.

   The marks stay on the indigo ground in both colour schemes, exactly as Vera's
   do: it gives a grid of cards one steady rhythm instead of a wall of competing
   pictures.
   --------------------------------------------------------------------------- */

const THUMB_INK = {
  ground:"#141B33", raised:"#1E2745", rule:"#2B3558",
  sea:"#9BE8D8", gold:"#C6A068", rust:"#B14A30", cream:"#F5F2EC"
};

// FNV-1a. Any stable hash would do; this one is four lines and has no collisions
// across the current slugs.
function slugSeed(slug) {
  let h = 2166136261;
  for (let i = 0; i < slug.length; i++) {
    h ^= slug.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// xorshift32. Deterministic, so a given article's mark never changes.
function seededRandom(seed) {
  let x = seed || 1;
  return function () {
    x ^= x << 13; x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5;  x >>>= 0;
    return x / 4294967296;
  };
}

/* Each motif is drawn into a 320x180 box and returns SVG element strings.
   They are deliberately different silhouettes, not one shape recoloured: at
   thumbnail size the outline is the only thing that survives. */

// Two halves of one diamond, brought back together with the seam still showing.
function motifRestorative(r, acc) {
  const cy = 90;
  const s = 50 + Math.round(r() * 24);
  const w = Math.round(s * 1.05);
  const cx = 148 + Math.round(r() * 34);
  const gap = 5;
  const echo = acc === THUMB_INK.gold ? THUMB_INK.sea : THUMB_INK.gold;
  const d = 12 + Math.round(r() * 8);
  const ox = r() < 0.5 ? 44 : 278;
  const oy = r() < 0.5 ? 40 : 142;
  return [
    `<polygon points="${cx - gap},${cy - s} ${cx - gap},${cy + s} ${cx - gap - w},${cy}" fill="${acc}"/>`,
    `<polygon points="${cx + gap},${cy - s} ${cx + gap},${cy + s} ${cx + gap + w},${cy}" fill="${THUMB_INK.cream}"/>`,
    `<polygon points="${ox},${oy - d} ${ox + d},${oy} ${ox},${oy + d} ${ox - d},${oy}" fill="${echo}"/>`
  ];
}

// A staircase of stages, one of them marked, under a line it never reaches.
function motifProcess(r, acc) {
  const n = 4 + Math.round(r());
  const w = 320 / n;
  const flip = r() < 0.45;
  const mark = Math.floor(r() * n);
  const hs = [];
  for (let i = 0; i < n; i++) hs.push(Math.round(180 * (0.18 + 0.125 * i) + r() * 12));
  if (flip) hs.reverse();
  const crest = 180 - Math.max.apply(null, hs);
  const out = [`<rect x="0" y="${Math.max(14, crest - 30)}" width="320" height="3" fill="${THUMB_INK.cream}" opacity="0.75"/>`];
  for (let i = 0; i < n; i++) {
    out.push(`<rect x="${Math.round(i * w)}" y="${180 - hs[i]}" width="${Math.ceil(w) + 1}" height="${hs[i]}" fill="${i === mark ? acc : THUMB_INK.rule}"/>`);
  }
  return out;
}

// A records grid: the institution as a filing system, a few cells pulled out.
function motifSystem(r, acc) {
  const cols = 7 + Math.round(r() * 2);
  const rows = 3 + Math.round(r());
  const pad = 16, gap = 6;
  const cw = (320 - pad * 2 - gap * (cols - 1)) / cols;
  const ch = (180 - pad * 2 - gap * (rows - 1)) / rows;
  const total = cols * rows;
  const hits = new Set();
  const want = 3 + Math.floor(r() * 3);
  for (let guard = 0; hits.size < want && guard < 60; guard++) hits.add(Math.floor(r() * total));
  const out = [];
  for (let i = 0; i < total; i++) {
    const x = pad + (i % cols) * (cw + gap);
    const y = pad + Math.floor(i / cols) * (ch + gap);
    const fill = hits.has(i) ? (i % 3 === 0 ? THUMB_INK.cream : acc) : THUMB_INK.rule;
    out.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${cw.toFixed(1)}" height="${ch.toFixed(1)}" fill="${fill}"/>`);
  }
  return out;
}

// Two banks, the gap between them, and how far the bridge actually gets.
function motifAccess(r, acc) {
  const cw = 30 + Math.round(r() * 18);
  const top = 34 + Math.round(r() * 20);
  const lx = 30 + Math.round(r() * 14);
  const rx = 290 - Math.round(r() * 14) - cw;
  const gap = rx - (lx + cw);
  const reach = 0.3 + r() * 0.42;
  const deck = top + 14 + Math.round(r() * 22);
  return [
    `<rect x="${lx}" y="${top}" width="${cw}" height="${180 - top}" fill="${THUMB_INK.cream}"/>`,
    `<rect x="${rx}" y="${top}" width="${cw}" height="${180 - top}" fill="${THUMB_INK.cream}"/>`,
    `<rect x="${lx + cw}" y="${deck}" width="${Math.round(gap * reach)}" height="14" fill="${acc}"/>`,
    `<rect x="${rx - Math.round(gap * 0.14)}" y="${deck}" width="${Math.round(gap * 0.14)}" height="14" fill="${THUMB_INK.cream}" opacity="0.3"/>`
  ];
}

// Arcs going out from a corner: something breaks, and it reaches New York.
function motifNews(r, acc) {
  const left = r() < 0.5;
  const ox = left ? 0 : 320, oy = 180;
  const sweep = left ? 1 : 0;
  const out = [`<circle cx="${ox}" cy="${oy}" r="${14 + Math.round(r() * 8)}" fill="${acc}"/>`];
  const band = [THUMB_INK.cream, acc, THUMB_INK.sea, THUMB_INK.gold];
  const n = 3 + Math.round(r());
  let rad = 48;
  for (let i = 0; i < n; i++) {
    rad += 30 + Math.round(r() * 12);
    const end = left ? `${ox + rad},${oy}` : `${ox - rad},${oy}`;
    out.push(
      `<path d="M ${ox},${oy - rad} A ${rad},${rad} 0 0 ${sweep} ${end}" fill="none" ` +
      `stroke="${band[(i + 1) % band.length]}" stroke-width="${7 + Math.round(r() * 5)}" ` +
      `opacity="${(0.95 - i * 0.15).toFixed(2)}"/>`
    );
  }
  return out;
}

const THUMB_MOTIFS = {
  "Restorative Justice": motifRestorative,
  "Rights & Process": motifProcess,
  "System": motifSystem,
  "Access to Justice": motifAccess,
  "Political / News": motifNews
};

function articleThumbSvg(a) {
  const rand = seededRandom(slugSeed(a.slug || a.title || ""));
  const acc = [THUMB_INK.sea, THUMB_INK.gold, THUMB_INK.rust][Math.floor(rand() * 3)];
  // A single large diagonal behind the motif, so the set reads as one family.
  const wedge = rand() < 0.5
    ? `<polygon points="0,0 320,0 0,180" fill="${THUMB_INK.raised}"/>`
    : `<polygon points="320,0 320,180 0,180" fill="${THUMB_INK.raised}"/>`;
  const motif = (THUMB_MOTIFS[a.category] || motifSystem)(rand, acc);
  // Decorative: the card's category, headline and date already say everything
  // this shape is saying, so it stays out of the accessibility tree entirely.
  return `<svg class="thumb-art" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">` +
    `<rect width="320" height="180" fill="${THUMB_INK.ground}"/>${wedge}${motif.join("")}</svg>`;
}

/* `compact` drops the excerpt, leaving label / headline / date over the mark --
   the shape Vera's news cards use. The home page runs compact; the full
   Articles index keeps the excerpts, because that page is for choosing between
   sixty of them. */
/* An article shows a photograph as soon as one exists and the generated mark
   until then, so the grid is never half-empty while the library fills in.

   The whole publishing step is dropping a file into assets/photos/ named after
   the article's slug -- clean-slate-act-explained.jpg for
   articles/clean-slate-act-explained.html. Nothing to edit. The <img> is
   layered over the mark; if the file isn't there the browser errors, the <img>
   removes itself and the mark shows through, so a missing photo costs one small
   404 and nothing else.

   Optional overrides in data.js, per article:
     image        a different path (use this for .png/.webp, or a shared photo)
     imageAlt     what the photo shows, for screen readers and when it fails
     imageCredit  photographer or source; most licences require a visible one
   ------------------------------------------------------------------------- */
function articleThumbHtml(a) {
  const src = a.image || `assets/photos/${a.slug}.jpg`;
  const credit = a.imageCredit ? `<span class="thumb-credit">${escapeHtml(a.imageCredit)}</span>` : "";
  return `<div class="thumb thumb-figure">${articleThumbSvg(a)}` +
    `<img class="thumb-photo-img" src="${escapeHtml(src)}" alt="${escapeHtml(a.imageAlt || "")}" ` +
    `loading="lazy" decoding="async">${credit}</div>`;
}

/* Handlers are attached here rather than written inline, so this keeps working
   under the script-src 'self' CSP the Cloudflare worker is meant to set. */
function attachThumbPhotos(root) {
  root.querySelectorAll("img.thumb-photo-img").forEach(img => {
    const fig = img.closest(".thumb-figure");
    img.addEventListener("load", () => { if (fig) fig.classList.add("has-photo"); });
    img.addEventListener("error", () => {
      if (fig) fig.classList.remove("has-photo");
      img.remove();
    });
    // A cached 404 can have finished before this ran.
    if (img.complete) {
      if (img.naturalWidth > 0) { if (fig) fig.classList.add("has-photo"); }
      else { if (fig) fig.classList.remove("has-photo"); img.remove(); }
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
