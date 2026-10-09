// Email signup box at the end of every article. Posts to the same Apps Script
// web app as the guide and checklist forms (email-capture-sheets/Code.gs),
// which adds the address to the Subscribers sheet and emails the guide.
(function () {
  var ENDPOINT = "https://script.google.com/macros/s/AKfycbx-cq6QGDsWt3ooU1gzGRrNVFbCuanJW58KmVP5QK5vVEQ8X4O_JjAoJmfRyEgY_oBxcg/exec";
  var form = document.getElementById("article-signup-form");
  if (!form) return;
  var input = form.querySelector('input[type="email"]');
  var hp = form.querySelector('input[name="hp"]');
  var btn = form.querySelector('button[type="submit"]');
  var status = document.getElementById("article-signup-status");
  var label = btn.textContent;

  function say(msg, ok) {
    status.textContent = msg;
    status.className = "signup-status " + (ok ? "success" : "error");
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = input.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      say("Enter a valid email address.", false);
      return;
    }
    btn.disabled = true;
    btn.textContent = "Sending...";
    // text/plain avoids a CORS preflight, which Apps Script doesn't handle.
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify({ email: email, hp: hp.value, source: "article-signup:" + location.pathname.split("/").pop().replace(".html", "").slice(0, 45) })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.ok) {
          say("You're on the list. The guide is on its way to your inbox.", true);
          form.reset();
          if (typeof gtag === "function") gtag("event", "article_signup", { page_path: location.pathname });
        } else {
          say((data && data.error) || "Something went wrong. Try again in a minute.", false);
        }
      })
      .catch(function () { say("Something went wrong. Try again in a minute.", false); })
      .then(function () { btn.disabled = false; btn.textContent = label; });
  });
})();
