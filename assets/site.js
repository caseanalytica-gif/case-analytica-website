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
   Article thumbnails: the case document.

   A sheet of paper on a desk, a folder behind it, and a stamp across it. The
   stamp is the article -- SEALED, DENIED, DISMISSED, VACATED -- so the mark
   says what the piece is about instead of decorating around it.

   Drawn rather than photographed, for the same reasons as before: there are 66
   of these with more arriving most days, and the stock-photo version of this
   scene is somebody else's licence and somebody else's desk. A photograph still
   wins whenever there is one -- drop assets/photos/<slug>.jpg in and it takes
   over. This is what stands in until then.

   Stamp wording comes from `stamp` on the article if it's set, otherwise from
   the slug, otherwise from the category. Green reads as an outcome that helped,
   rust as one that didn't, gold as neither.
   --------------------------------------------------------------------------- */

const THUMB_INK = {
  ground:"#141B33", raised:"#1E2745", desk:"#0F1528",
  folder:"#C9A97A", folderDark:"#A98A5E",
  sheet:"#F7F4EE", sheetEdge:"#DAD5C9", rule:"#C9C3B6", ruleDark:"#8A8578",
  gold:"#C6A068", green:"#3E8E6E", rust:"#B14A30"
};

// Ordered: first match wins, so put the specific ahead of the general.
const STAMP_RULES = [
  [/clean-slate|sealing|sealed|160-50|160-59|expungement|mrta|background-check/, "SEALED",       "green"],
  [/parole-board|parole-hearing|denial|denied|racial-disparity/,                 "DENIED",       "rust"],
  [/what-is-an-acd|acd-|dismiss/,                                                "DISMISSED",    "green"],
  [/440-10|vacate|unjust-conviction|compensation/,                               "VACATED",      "green"],
  [/second-look|resentenc|dvsja|60-12|medical-parole|shock-incarceration/,       "RESENTENCED",  "green"],
  [/30-30|30-20|speedy-trial/,                                                   "SPEEDY TRIAL", "gold"],
  [/bail|180-80|release|desk-appearance|project-reset/,                          "RELEASED",     "green"],
  [/restorative|diversion|mental-health-court|veterans-treatment|judicial-diversion/, "DIVERTED", "green"],
  [/violation|vop|410-70|259-i|post-release-supervision/,                        "VIOLATION",   "rust"],
  [/suppress|stop-and-frisk|140-50|phone-search|warrant/,                        "SUPPRESSED",  "green"],
  [/grand-jury|190-50|testify/,                                                  "TESTIMONY",   "gold"],
  [/order-of-protection|extreme-risk|erpo/,                                      "ORDER",       "rust"],
  [/forfeiture|13-a|seiz/,                                                       "SEIZED",      "rust"],
  [/730|competency/,                                                             "730 EXAM",    "gold"],
  [/solitary|halt-act|rikers|jail|incarcerat/,                                   "CUSTODY",     "rust"],
  [/housing|fair-chance/,                                                        "HOUSING",     "green"],
  [/employment|23-a|certificate-of-relief/,                                      "RELIEF",      "green"],
  [/youthful-offender|raise-the-age/,                                            "Y.O.",        "green"],
  [/immigration|deport|protect-our-courts/,                                      "NOTICE",      "rust"],
  [/counsel|public-defender|right-to-counsel|cost-of-a-criminal/,                "COUNSEL",     "gold"],
  [/discovery|work-product/,                                                     "DISCLOSURE",  "gold"],
  [/plea|guilty/,                                                                "PLEA",        "rust"],
  [/language-access|interpreter/,                                                "ACCESS",      "gold"],
  [/arrest|arraign|court-logistics|navigation/,                                  "PENDING",     "gold"]
];

const STAMP_BY_CATEGORY = {
  "Restorative Justice": ["DIVERTED", "green"],
  "Rights & Process":    ["ON RECORD", "gold"],
  "System":              ["PENDING", "gold"],
  "Access to Justice":   ["ACCESS", "gold"],
  "Political / News":    ["FILED", "gold"]
};

/* Plenty of these pieces are about a remedy that ISN'T working -- the sealing
   bug stuck in committee, the funding that never came, the appeal nobody wins.
   A green SEALED on those would tell the reader the opposite of the article. So
   when the slug or headline says the thing failed, green drops back to gold:
   still the right subject, no claim about the outcome. */
const STAMP_SETBACK = /stuck|\bbug\b|gap\b|fail|crisis|disparit|watered-down|almost-passed|doesn-?t|didn-?t|never|denied|denial|backlog|delay|unmet|shortfall|no-money|not-need/;

function stampFor(a) {
  const hay = ((a.slug || "") + " " + (a.title || "")).toLowerCase();
  for (const [re, word, tone] of STAMP_RULES) {
    if (re.test(hay)) {
      return [word, tone === "green" && STAMP_SETBACK.test(hay) ? "gold" : tone];
    }
  }
  return STAMP_BY_CATEGORY[a.category] || ["ON FILE", "gold"];
}

function articleThumbSvg(a) {
  const rand = seededRandom(slugSeed(a.slug || a.title || ""));
  const pair = a.stamp ? [String(a.stamp).toUpperCase(), a.stampTone || "gold"] : stampFor(a);
  const word = pair[0];
  const ink = THUMB_INK[pair[1]] || THUMB_INK.gold;

  // Small seeded variation so a wall of these doesn't look rubber-stamped
  // (which, given the subject, would be a bit on the nose).
  const tilt   = (-6 + rand() * 4).toFixed(1);        // the sheet
  const sTilt  = (-11 + rand() * 8).toFixed(1);       // the stamp
  const sx     = 128 + Math.round(rand() * 26);
  const sy     = 104 + Math.round(rand() * 10);
  const lines  = 3 + Math.round(rand());
  const P = THUMB_INK;

  const ruled = [];
  for (let i = 0; i < lines; i++) {
    const w = 96 - Math.round(rand() * 34);
    ruled.push(`<rect x="78" y="${72 + i * 11}" width="${w}" height="4" rx="2" fill="${P.rule}"/>`);
  }

  return `<svg class="thumb-art" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
  <rect width="320" height="180" fill="${P.ground}"/>
  <polygon points="0,124 320,86 320,180 0,180" fill="${P.desk}"/>

  <g transform="rotate(${(Number(tilt) + 5).toFixed(1)} 160 96)">
    <rect x="82" y="34" width="184" height="132" rx="3" fill="${P.folderDark}"/>
    <rect x="82" y="26" width="66" height="14" rx="3" fill="${P.folder}"/>
    <rect x="76" y="38" width="190" height="130" rx="3" fill="${P.folder}"/>
  </g>

  <g transform="rotate(${tilt} 160 96)">
    <rect x="60" y="20" width="196" height="148" rx="2" fill="${P.sheetEdge}"/>
    <rect x="58" y="18" width="196" height="148" rx="2" fill="${P.sheet}"/>
    <rect x="58" y="18" width="6" height="148" fill="${ink}"/>
    <rect x="78" y="36" width="118" height="8" rx="2" fill="${P.ruleDark}"/>
    <rect x="78" y="52" width="76" height="5" rx="2" fill="${P.rule}"/>
    ${ruled.join("")}
  </g>

  <g transform="rotate(${sTilt} ${sx} ${sy})" opacity="0.92">
    <rect x="${sx - 76}" y="${sy - 21}" width="152" height="42" rx="4"
          fill="none" stroke="${ink}" stroke-width="4"/>
    <text x="${sx}" y="${sy + 7}" text-anchor="middle" textLength="126" lengthAdjust="spacingAndGlyphs"
          font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
          font-size="23" font-weight="700" letter-spacing="1" fill="${ink}">${escapeHtml(word)}</text>
  </g>
</svg>`;
}

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
