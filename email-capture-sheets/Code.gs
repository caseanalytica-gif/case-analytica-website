/**
 * Case Analytica — email capture (Google Sheets version)
 *
 * Bind this script to the Google Sheet you want emails saved into:
 * open the Sheet -> Extensions -> Apps Script -> paste this in, replacing
 * the boilerplate -> Deploy as a Web App. See SETUP.md for exact steps.
 *
 * No tokens, no third-party services -- just your Google account.
 */

// Direct link to the hosted PDF. Update if the guide is ever renamed/moved.
var PDF_URL = 'https://www.caseanalytica.com/assets/guide/case-analytica-guide.pdf';

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var email = (data.email || '').toString().trim().toLowerCase();
    var honeypot = (data.hp || '').toString().trim();
    var source = (data.source || 'guide-download').toString().trim().slice(0, 64);

    // Bots fill hidden fields. Pretend success, do nothing.
    if (honeypot) {
      return respond({ ok: true });
    }

    if (!isValidEmail(email)) {
      return respond({ ok: false, error: 'Please enter a valid email address.' });
    }

    var sheet = getSubscribersSheet();
    ensureHeader(sheet);

    var duplicate = isDuplicate(sheet, email);
    if (!duplicate) {
      sheet.appendRow([email, new Date(), source]);
    }

    // Best-effort: a mail quota error or send failure should not break the
    // lead capture, which already succeeded above.
    var emailSent = true;
    var mailError = '';
    try {
      sendGuideEmail(email);
    } catch (mailErr) {
      emailSent = false;
      mailError = (mailErr && mailErr.message) ? mailErr.message : String(mailErr);
      console.error('sendGuideEmail failed: ' + mailError);
    }

    return respond({ ok: true, duplicate: duplicate, emailSent: emailSent, mailError: mailError });

  } catch (err) {
    return respond({ ok: false, error: 'Server error: ' + err.message });
  }
}

function sendGuideEmail(email) {
  var subject = "Your guide: What New York Doesn't Tell You After an Arrest";
  var htmlBody =
    '<p>Here is your copy of the guide:</p>' +
    '<p><a href="' + PDF_URL + '">Download the PDF</a></p>' +
    '<p>Everything on the site pulled into one place: rights and process, ' +
    'diversion programs, the Clean Slate Act, and the exact questions to ' +
    'ask any attorney before a plea gets entered.</p>' +
    '<p>&mdash; Dean</p>';
  var plainBody = "Here is your copy of the guide:\n" + PDF_URL +
    "\n\n— Dean";

  MailApp.sendEmail({
    to: email,
    subject: subject,
    body: plainBody,
    htmlBody: htmlBody,
    name: 'Dean'
  });
}

// Lets you hit the /exec URL directly in a browser to sanity-check it's alive.
// Also handles unsubscribe links clicked from a digest email (?unsubscribe=<email>&sig=<token>).
function doGet(e) {
  var email = e && e.parameter && e.parameter.unsubscribe;
  if (email) {
    return handleUnsubscribeRequest(email, e.parameter.sig || '');
  }
  return respond({ ok: true, message: 'Case Analytica email capture is running.' });
}

function getSubscribersSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName('Subscribers') || ss.getActiveSheet();
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function ensureHeader(sheet) {
  var firstCell = sheet.getRange(1, 1).getValue();
  if (firstCell !== 'email') {
    sheet.insertRowBefore(1);
    sheet.getRange(1, 1, 1, 3).setValues([['email', 'timestamp', 'source']]);
  }
}

function isDuplicate(sheet, email) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return false;
  var emails = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  for (var i = 0; i < emails.length; i++) {
    if ((emails[i][0] || '').toString().trim().toLowerCase() === email) return true;
  }
  return false;
}

function respond(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/* ==========================================================================
   Daily article digest
   ==========================================================================
   Reads the live ARTICLES list straight off the site (assets/data.js),
   compares it against a running "already sent" log kept in this same
   Spreadsheet (SentArticles tab), and emails everyone in Subscribers
   whenever a genuinely new article shows up. Runs once a day off a
   time-based trigger. See SETUP.md for the one-time setup order:
   1) paste this whole file in, 2) run markAllCurrentArticlesAsSent once
   so the existing archive doesn't blast out all at once, 3) run
   createDailyArticleTrigger once to turn the daily job on.
   ========================================================================== */

var ARTICLES_DATA_URL = 'https://www.caseanalytica.com/assets/data.js';
var ARTICLES_BASE_URL = 'https://www.caseanalytica.com/articles/';
var DIGEST_FROM_NAME = 'Dean';
var DIGEST_UTM = '?utm_source=newsletter&utm_medium=email&utm_campaign=daily_digest';

// Anti-abuse obfuscation for unsubscribe links, not a real secret -- this list
// is a small personal one, not a high-value target. Change this string and
// every previously-sent unsubscribe link stops working (acceptable tradeoff,
// just don't change it casually).
var UNSUB_SALT = 'case-analytica-unsub-2026';

function sendDailyArticleDigest() {
  var articles = fetchLiveArticles();
  if (!articles || !articles.length) {
    console.log('Daily digest: could not load articles.js, skipping this run.');
    return;
  }

  var sentSheet = getSentArticlesSheet();
  var sentSlugs = getAlreadySentSlugs(sentSheet);

  var newArticles = articles.filter(function (a) {
    return a && a.slug && sentSlugs.indexOf(a.slug) === -1;
  });

  if (newArticles.length === 0) {
    console.log('Daily digest: nothing new today.');
    return;
  }

  var recipients = getSubscriberEmails();
  if (recipients.length > 0) {
    var subject = newArticles.length === 1
      ? 'New on Case Analytica: ' + newArticles[0].title
      : newArticles.length + ' new articles on Case Analytica';

    var sentCount = 0;
    recipients.forEach(function (email) {
      try {
        var unsubUrl = buildUnsubscribeUrl(email);
        var htmlBody = buildDigestHtml(newArticles, unsubUrl);
        var plainBody = buildDigestPlain(newArticles, unsubUrl);
        MailApp.sendEmail({ to: email, subject: subject, body: plainBody, htmlBody: htmlBody, name: DIGEST_FROM_NAME });
        sentCount++;
      } catch (err) {
        console.error('Digest send failed for ' + email + ': ' + err.message);
      }
    });
    console.log('Daily digest: sent ' + sentCount + ' of ' + recipients.length +
      ' emails for ' + newArticles.length + ' new article(s).');
  } else {
    console.log('Daily digest: no subscribers yet, marking articles sent without emailing.');
  }

  markArticlesSent(sentSheet, newArticles.map(function (a) { return a.slug; }));
}

// Pulls the ARTICLES array directly off the live site's assets/data.js so
// this never has to be kept in sync by hand -- publishing an article on
// the site is the only step needed for it to show up here too.
function fetchLiveArticles() {
  var res = UrlFetchApp.fetch(ARTICLES_DATA_URL, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    console.error('fetchLiveArticles: HTTP ' + res.getResponseCode() + ' fetching data.js');
    return [];
  }
  var text = res.getContentText();
  var match = text.match(/const\s+ARTICLES\s*=\s*(\[[\s\S]*?\]);/);
  if (!match) {
    console.error('fetchLiveArticles: could not find ARTICLES array in data.js');
    return [];
  }
  try {
    return Function('"use strict"; return (' + match[1] + ');')();
  } catch (parseErr) {
    console.error('fetchLiveArticles: parse error: ' + parseErr.message);
    return [];
  }
}

function getSentArticlesSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('SentArticles');
  if (!sheet) {
    sheet = ss.insertSheet('SentArticles');
    sheet.getRange(1, 1, 1, 2).setValues([['slug', 'dateSent']]);
  }
  return sheet;
}

function getAlreadySentSlugs(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  return values.map(function (row) { return (row[0] || '').toString().trim(); });
}

function markArticlesSent(sheet, slugs) {
  if (!slugs || !slugs.length) return;
  var now = new Date();
  var rows = slugs.map(function (slug) { return [slug, now]; });
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, 2).setValues(rows);
}

// De-duplicated list of every address currently in Subscribers.
function getSubscriberEmails() {
  var sheet = getSubscribersSheet();
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  var seen = {};
  var out = [];
  values.forEach(function (row) {
    var email = (row[0] || '').toString().trim().toLowerCase();
    if (email && !seen[email]) {
      seen[email] = true;
      out.push(email);
    }
  });
  return out;
}

function buildDigestHtml(newArticles, unsubUrl) {
  var items = newArticles.map(function (a) {
    var url = ARTICLES_BASE_URL + a.slug + '.html' + DIGEST_UTM;
    return '<p><strong><a href="' + url + '">' + escapeHtml(a.title) + '</a></strong><br>' +
      escapeHtml(a.excerpt || '') + '</p>';
  }).join('');
  return '<p>New on Case Analytica:</p>' + items +
    '<p>&mdash; ' + DIGEST_FROM_NAME + ' (<a href="https://www.caseanalytica.com">caseanalytica.com</a>)</p>' +
    '<p style="font-size:12px; color:#888;"><a href="' + unsubUrl + '">Unsubscribe</a> from these emails.</p>';
}

function buildDigestPlain(newArticles, unsubUrl) {
  var items = newArticles.map(function (a) {
    var url = ARTICLES_BASE_URL + a.slug + '.html' + DIGEST_UTM;
    return a.title + '\n' + url + (a.excerpt ? '\n' + a.excerpt : '');
  }).join('\n\n');
  return 'New on Case Analytica:\n\n' + items + '\n\n— ' + DIGEST_FROM_NAME + ' (https://www.caseanalytica.com)' +
    '\n\nUnsubscribe: ' + unsubUrl;
}

function escapeHtml(str) {
  return (str || '').toString()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---- One-time setup helpers (run each of these manually, once) ----

// Run this FIRST, before turning on the daily trigger. It marks every
// article currently on the site as "already sent" so the very first daily
// run doesn't email the entire back catalog at once. After this, only
// articles added to data.js from this point forward will go out.
function markAllCurrentArticlesAsSent() {
  var articles = fetchLiveArticles();
  var sentSheet = getSentArticlesSheet();
  var alreadySent = getAlreadySentSlugs(sentSheet);
  var toMark = articles
    .map(function (a) { return a.slug; })
    .filter(function (slug) { return alreadySent.indexOf(slug) === -1; });
  markArticlesSent(sentSheet, toMark);
  console.log('Marked ' + toMark.length + ' existing article(s) as already sent.');
}

// Run this SECOND, once, to turn the daily job on. Safe to run more than
// once -- it checks for an existing trigger first instead of stacking
// duplicates.
function createDailyArticleTrigger() {
  var existing = ScriptApp.getProjectTriggers().filter(function (t) {
    return t.getHandlerFunction() === 'sendDailyArticleDigest';
  });
  if (existing.length > 0) {
    console.log('Daily trigger already exists, skipping.');
    return;
  }
  ScriptApp.newTrigger('sendDailyArticleDigest')
    .timeBased()
    .everyDays(1)
    .atHour(9)
    .create();
  console.log('Daily article digest trigger created: runs once a day around 9am, script timezone.');
}

/* ==========================================================================
   Unsubscribe
   ==========================================================================
   Every digest email carries a per-recipient link back to this same /exec
   URL: ?unsubscribe=<email>&sig=<token>. The token is a short signature so
   a stranger can't unsubscribe an arbitrary address just by guessing it --
   see UNSUB_SALT above. Clicking the link removes the row from Subscribers
   and logs it in a new "Unsubscribed" tab (kept for a record, not deleted
   outright), then shows a plain confirmation page.
   ========================================================================== */

function buildUnsubscribeUrl(email) {
  var base = ScriptApp.getService().getUrl();
  return base + '?unsubscribe=' + encodeURIComponent(email) + '&sig=' + signEmail(email);
}

function signEmail(email) {
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, email.toLowerCase().trim() + UNSUB_SALT);
  return raw.map(function (b) { return ((b + 256) % 256).toString(16).padStart(2, '0'); }).join('').slice(0, 16);
}

function handleUnsubscribeRequest(email, sig) {
  email = (email || '').toString().trim().toLowerCase();
  if (!email || sig !== signEmail(email)) {
    return htmlPage('Unsubscribe link not recognized. If you followed a link from an actual Case Analytica email, ' +
      'reply to that email directly and it will be handled manually.');
  }
  removeSubscriber(email);
  return htmlPage('You have been unsubscribed. You will not receive any more emails from Case Analytica at ' + escapeHtml(email) + '.');
}

function removeSubscriber(email) {
  var sheet = getSubscribersSheet();
  var lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    var emails = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (var i = 0; i < emails.length; i++) {
      if ((emails[i][0] || '').toString().trim().toLowerCase() === email) {
        sheet.deleteRow(i + 2);
        break;
      }
    }
  }
  var unsubSheet = getUnsubscribedSheet();
  unsubSheet.appendRow([email, new Date()]);
}

function getUnsubscribedSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Unsubscribed');
  if (!sheet) {
    sheet = ss.insertSheet('Unsubscribed');
    sheet.getRange(1, 1, 1, 2).setValues([['email', 'dateUnsubscribed']]);
  }
  return sheet;
}

function htmlPage(message) {
  var html = '<div style="font-family:sans-serif; max-width:480px; margin:80px auto; text-align:center;">' +
    '<p style="font-size:16px; line-height:1.5;">' + message + '</p>' +
    '<p><a href="https://www.caseanalytica.com">caseanalytica.com</a></p></div>';
  return HtmlService.createHtmlOutput(html);
}
