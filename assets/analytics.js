document.addEventListener("click", function (e) {
  var link = e.target.closest("a[href]");
  if (!link) return;

  if (link.href.indexOf("paypal.me/DeanMustaphalli") !== -1) {
    if (typeof gtag === "function") {
      gtag("event", "donate_click", {
        link_text: link.textContent.trim(),
        page_path: window.location.pathname
      });
    }
    return;
  }

  if (link.href.indexOf("case-analytica-guide.pdf") !== -1) {
    if (typeof gtag === "function") {
      gtag("event", "guide_download", {
        page_path: window.location.pathname
      });
    }
  }
});
