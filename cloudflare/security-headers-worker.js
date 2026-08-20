// Cloudflare Worker: adds security response headers in front of GitHub Pages.
// GitHub Pages serves static files with no way to set custom HTTP headers,
// so this Worker sits in front (via a Cloudflare route) and adds them to
// every response before it reaches the browser. See ../README-DEPLOY.md
// for the one-time Cloudflare setup steps.

const CSP = [
  "default-src 'self'",
  // Inline <script> (GTM init) and Google Tag Manager/Analytics are used site-wide.
  "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com",
  // Inline style="" attributes are used throughout the site's markup.
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self' data:",
  "connect-src 'self' https://www.google-analytics.com https://region1.google-analytics.com https://www.googletagmanager.com",
  // YouTube embeds (videos.html, articles), plus the Tally intake form on
  // about.html. Note Tally's own embed *script* stays blocked by script-src
  // above, which is why the form is embedded as a plain iframe, not their
  // JS widget.
  "frame-src https://www.youtube.com https://tally.so",
  // Nobody should be able to iframe this site (belt-and-suspenders with X-Frame-Options below).
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join('; ');

const SECURITY_HEADERS = {
  'Content-Security-Policy': CSP,
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=(self)',
};

export default {
  async fetch(request) {
    const response = await fetch(request);
    const headers = new Headers(response.headers);
    for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
      headers.set(name, value);
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
