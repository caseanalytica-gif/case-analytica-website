/* Small SVG chart helpers for the data hub. No libraries: the site's security
   headers block third-party scripts. Every chart sits beside an HTML table with
   the same numbers, and every mark carries a <title> for hover and screen readers. */
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  function el(n, a, t) {
    var e = document.createElementNS(NS, n);
    for (var k in a) e.setAttribute(k, a[k]);
    if (t != null) e.textContent = t;
    return e;
  }
  function fmt(n) { return Number(n).toLocaleString('en-US'); }
  /* Tick step from a short list of round numbers, so the axis ends just above the data. */
  function scale(max) {
    var raw = max / 4, p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), m = raw / p, pick = 10;
    [1, 1.5, 2, 2.5, 5, 10].some(function (c) { if (m <= c + 1e-9) { pick = c; return true; } });
    var step = pick * p, ticks = Math.max(1, Math.ceil(max / step - 1e-9));
    return { top: step * ticks, ticks: ticks };
  }
  function frame(svg, W, H, L, R, T, B, sc, labelFmt) {
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.textContent = '';
    var y = function (v) { return T + (1 - v / sc.top) * (H - T - B); };
    for (var g = 0; g <= sc.ticks; g++) {
      var v = sc.top * g / sc.ticks;
      svg.appendChild(el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), 'class': 'grid' }));
      svg.appendChild(el('text', { x: L - 8, y: y(v) + 4, 'text-anchor': 'end' }, (labelFmt || fmt)(v)));
    }
    return y;
  }

  /* points: [{x: year, y: number}], series: [{name, cls, pts}] */
  function line(svg, series, opts) {
    opts = opts || {};
    var W = 680, H = opts.h || 280, L = 88, R = 28, T = 20, B = 34;
    var xs = series[0].pts.map(function (p) { return p.x; });
    var mx = 0;
    series.forEach(function (s) { s.pts.forEach(function (p) { if (p.y > mx) mx = p.y; }); });
    var y = frame(svg, W, H, L, R, T, B, scale(mx), opts.fmt);
    var n = xs.length, x = function (i) { return L + i * (W - L - R) / Math.max(1, n - 1); };
    var step = Math.ceil(n / 8);
    xs.forEach(function (v, i) {
      if (i % step === 0 || i === n - 1) svg.appendChild(el('text', { x: x(i), y: H - 12, 'text-anchor': 'middle' }, v));
    });
    series.forEach(function (s) {
      svg.appendChild(el('polyline', {
        points: s.pts.map(function (p, i) { return x(i) + ',' + y(p.y); }).join(' '),
        fill: 'none', 'stroke-width': 2.5, 'stroke-linejoin': 'round', 'class': 'ln ' + s.cls
      }));
      s.pts.forEach(function (p, i) {
        var c = el('circle', { cx: x(i), cy: y(p.y), r: n > 20 ? 2.5 : 3.5, 'class': 'dot ' + s.cls });
        c.appendChild(el('title', {}, s.name + ' ' + p.x + ': ' + fmt(p.y)));
        svg.appendChild(c);
      });
      var last = s.pts[s.pts.length - 1];
      svg.appendChild(el('text', { x: x(n - 1), y: y(last.y) - 10, 'text-anchor': 'end', 'class': 'v' }, fmt(last.y)));
    });
  }

  /* rows: [{label, a:number, b:number...}], keys: [{k, name, cls}] stacked vertically */
  function stacked(svg, rows, keys, opts) {
    opts = opts || {};
    var W = 680, H = opts.h || 300, L = 88, R = 16, T = 16, B = 34;
    var mx = Math.max.apply(null, rows.map(function (r) { return keys.reduce(function (a, k) { return a + r[k.k]; }, 0); }));
    var y = frame(svg, W, H, L, R, T, B, scale(mx));
    var bw = (W - L - R) / rows.length, step = Math.ceil(rows.length / 9);
    rows.forEach(function (r, i) {
      var acc = 0;
      keys.forEach(function (k) {
        var h = y(acc) - y(acc + r[k.k]);
        if (h <= 0) return;
        var rc = el('rect', { x: L + i * bw + bw * 0.15, y: y(acc + r[k.k]), width: bw * 0.7, height: h, 'class': k.cls });
        rc.appendChild(el('title', {}, r.label + ' ' + k.name + ': ' + fmt(r[k.k])));
        svg.appendChild(rc);
        acc += r[k.k];
      });
      if (i % step === 0 || i === rows.length - 1) svg.appendChild(el('text', { x: L + i * bw + bw / 2, y: H - 12, 'text-anchor': 'middle' }, r.label));
    });
  }

  /* rows: [{label, value}] horizontal bars */
  function hbars(svg, rows, opts) {
    opts = opts || {};
    var W = 680, rowH = 34, L = 170, R = 90, T = 8, H = T + rows.length * rowH + 8;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.textContent = '';
    var mx = Math.max.apply(null, rows.map(function (r) { return r.value; })) || 1;
    rows.forEach(function (r, i) {
      var yy = T + i * rowH, w = (W - L - R) * r.value / mx;
      svg.appendChild(el('text', { x: L - 10, y: yy + rowH / 2 + 4, 'text-anchor': 'end' }, r.label));
      var rc = el('rect', { x: L, y: yy + 6, width: Math.max(1, w), height: rowH - 12, 'class': 's1' });
      rc.appendChild(el('title', {}, r.label + ': ' + fmt(r.value)));
      svg.appendChild(rc);
      svg.appendChild(el('text', { x: L + w + 8, y: yy + rowH / 2 + 4, 'class': 'v' }, fmt(r.value)));
    });
  }

  window.CAChart = { line: line, stacked: stacked, hbars: hbars, fmt: fmt };
})();
