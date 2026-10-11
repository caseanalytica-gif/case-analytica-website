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

    // Course signups (source "course:<key>") go to the Course tab, not the
    // article list. See the email course section at the bottom of this file.
    if (source.indexOf('course:') === 0) {
      return respond(enrollInCourse(email, source.slice(7)));
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
    '<p>Dean</p>';
  var plainBody = "Here is your copy of the guide:\n" + PDF_URL +
    "\n\nDean";

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
    '<p>' + DIGEST_FROM_NAME + ' (<a href="https://www.caseanalytica.com">caseanalytica.com</a>)</p>' +
    '<p style="font-size:12px; color:#888;"><a href="' + unsubUrl + '">Unsubscribe</a> from these emails.</p>';
}

function buildDigestPlain(newArticles, unsubUrl) {
  var items = newArticles.map(function (a) {
    var url = ARTICLES_BASE_URL + a.slug + '.html' + DIGEST_UTM;
    return a.title + '\n' + url + (a.excerpt ? '\n' + a.excerpt : '');
  }).join('\n\n');
  return 'New on Case Analytica:\n\n' + items + '\n\n' + DIGEST_FROM_NAME + ' (https://www.caseanalytica.com)' +
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
  stopCourseFor(email);
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

/* ==========================================================================
   One-time donation appeal (approved by ANF under 3(c), 2026-10-08)
   ==========================================================================
   1) Run sendDonationAppealTest -- it emails only the account that owns
      this script, so you can read it first.
   2) Run sendDonationAppeal -- it emails every subscriber once. Each address
      is logged in an AppealSent tab as it goes, so a second run skips
      everyone already sent. If Google's daily mail limit stops it partway,
      run it again tomorrow and it picks up where it left off.
   ========================================================================== */

var APPEAL_SUBJECT = 'Case Analytica needs your help to keep going';
var APPEAL_DONATE_URL = 'https://donate.stripe.com/6oU28s2Hg2mggdyet62Ji00';
var APPEAL_PARAGRAPHS = [
  "Every article on Case Analytica is free. There's no paywall and no sign-up, and I check every legal claim against the statute itself before it goes up. Since July I've published 78 of them, written for people facing the New York system and the families trying to help.",
  "I've paid for all of it myself so far. That can't last, and I'm asking for help now.",
  'My next project: New York law says someone with an Earned Eligibility Certificate "shall be granted parole release" unless the Parole Board makes two specific findings. In six months of 2025, the Board turned down certificate holders 369 times. I want to find out whether it gave the reasons the law requires.',
  'If this site has helped you or someone you love, please give what you can:'
];
var APPEAL_AFTER_LINK = "Any amount helps. If you can't give, forward this to one person who might.";
var APPEAL_SIGNATURE = ['Dean Mustaphalli', 'Case Analytica'];
var APPEAL_SPONSOR_LINE = 'Case Analytica is fiscally sponsored by the Alternative Newsweekly Foundation, EIN 30-0100369. All donations are tax-deductible to the extent allowed by law.';

function sendDonationAppealTest() {
  var me = 'caseanalytica@gmail.com';
  sendAppealTo(me);
  console.log('Appeal test sent to ' + me);
}

function sendDonationAppeal() {
  var sheet = getAppealSentSheet();
  var done = {};
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues().forEach(function (row) {
      done[(row[0] || '').toString().trim().toLowerCase()] = true;
    });
  }
  var pending = getSubscriberEmails().filter(function (email) { return !done[email]; });
  var sentCount = 0;
  for (var i = 0; i < pending.length; i++) {
    if (MailApp.getRemainingDailyQuota() < 1) {
      console.log('Daily mail limit reached. Run sendDonationAppeal again tomorrow to finish.');
      break;
    }
    try {
      sendAppealTo(pending[i]);
      sheet.appendRow([pending[i], new Date()]);
      sentCount++;
    } catch (err) {
      console.error('Appeal send failed for ' + pending[i] + ': ' + err.message);
    }
  }
  console.log('Appeal: sent ' + sentCount + ', still pending ' + (pending.length - sentCount) +
    ', already sent before this run ' + Object.keys(done).length + '.');
}

function sendAppealTo(email) {
  // Run from the editor, getUrl() returns the owner-only /dev link, so point at the live web app.
  var unsubUrl = liveUnsubscribeUrl(email);
  var html = APPEAL_PARAGRAPHS.map(function (p) { return '<p>' + escapeHtml(p) + '</p>'; }).join('') +
    '<p><a href="' + APPEAL_DONATE_URL + '">' + APPEAL_DONATE_URL + '</a></p>' +
    '<p>' + escapeHtml(APPEAL_AFTER_LINK) + '</p>' +
    '<p>' + APPEAL_SIGNATURE.map(escapeHtml).join('<br>') + '</p>' +
    '<p style="font-size:12px; color:#888;">' + escapeHtml(APPEAL_SPONSOR_LINE) + '</p>' +
    '<p style="font-size:12px; color:#888;"><a href="' + unsubUrl + '">Unsubscribe</a> from these emails.</p>';
  var plain = APPEAL_PARAGRAPHS.join('\n\n') + '\n\n' + APPEAL_DONATE_URL + '\n\n' + APPEAL_AFTER_LINK +
    '\n\n' + APPEAL_SIGNATURE.join('\n') + '\n\n' + APPEAL_SPONSOR_LINE + '\n\nUnsubscribe: ' + unsubUrl;
  MailApp.sendEmail({ to: email, subject: APPEAL_SUBJECT, body: plain, htmlBody: html, name: DIGEST_FROM_NAME });
}

function getAppealSentSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('AppealSent');
  if (!sheet) {
    sheet = ss.insertSheet('AppealSent');
    sheet.appendRow(['email', 'sent_at']);
  }
  return sheet;
}

// Run from the editor or a trigger, ScriptApp.getService().getUrl() can return
// the owner-only /dev link, so unsubscribe links always point at the live app.
var LIVE_EXEC_URL = 'https://script.google.com/macros/s/AKfycbx-cq6QGDsWt3ooU1gzGRrNVFbCuanJW58KmVP5QK5vVEQ8X4O_JjAoJmfRyEgY_oBxcg/exec';

function liveUnsubscribeUrl(email) {
  return LIVE_EXEC_URL + '?unsubscribe=' + encodeURIComponent(email) + '&sig=' + signEmail(email);
}

function fetchSiteJson(url) {
  var res = UrlFetchApp.fetch(url + (url.indexOf('?') < 0 ? '?' : '&') + 'x=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    console.error('fetchSiteJson: HTTP ' + res.getResponseCode() + ' for ' + url);
    return null;
  }
  try { return JSON.parse(res.getContentText()); }
  catch (err) { console.error('fetchSiteJson: bad JSON at ' + url + ': ' + err.message); return null; }
}

function isUnsubscribed(email) {
  var sheet = getUnsubscribedSheet();
  if (sheet.getLastRow() < 2) return false;
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues();
  for (var i = 0; i < rows.length; i++) {
    if ((rows[i][0] || '').toString().trim().toLowerCase() === email) return true;
  }
  return false;
}

/* ==========================================================================
   Email course ("After an arrest in New York")
   ==========================================================================
   The lessons live on the site, in assets/course/<key>.json, so editing a
   lesson never needs a redeploy. Signup sends lesson 1 at once; a daily
   trigger sends each later lesson once its "day" (days since signup) arrives.
   Setup, once, after pasting this file in and deploying a new version:
     1) run sendCourseTest  (emails all lessons to this account to read)
     2) run createCourseTrigger
   Course tab columns: email | started | lastSent | course | status
   ========================================================================== */

var COURSE_BASE_URL = 'https://www.caseanalytica.com/assets/course/';
var SITE_URL = 'https://www.caseanalytica.com/';

function getCourseSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Course');
  if (!sheet) {
    sheet = ss.insertSheet('Course');
    sheet.appendRow(['email', 'started', 'lastSent', 'course', 'status']);
  }
  return sheet;
}

function enrollInCourse(email, key) {
  key = (key || '').replace(/[^a-z0-9-]/g, '');
  var course = fetchSiteJson(COURSE_BASE_URL + key + '.json');
  if (!course || !course.lessons || !course.lessons.length) {
    return { ok: false, error: 'That course is not available right now. Try again later.' };
  }
  var sheet = getCourseSheet();
  var last = sheet.getLastRow();
  if (last >= 2) {
    var rows = sheet.getRange(2, 1, last - 1, 5).getValues();
    for (var i = 0; i < rows.length; i++) {
      if ((rows[i][0] || '').toString().toLowerCase() === email && rows[i][3] === key && rows[i][4] === 'active') {
        return { ok: true, duplicate: true };
      }
    }
  }
  sheet.appendRow([email, new Date(), 0, key, 'active']);
  var row = sheet.getLastRow();
  try {
    sendLesson(email, course, 0);
    sheet.getRange(row, 3).setValue(1);
  } catch (err) {
    // The daily trigger retries lesson 1 tomorrow.
    console.error('Course lesson 1 failed for ' + email + ': ' + err.message);
  }
  return { ok: true };
}

function sendCourseLessons() {
  var sheet = getCourseSheet();
  var last = sheet.getLastRow();
  if (last < 2) return;
  var rows = sheet.getRange(2, 1, last - 1, 5).getValues();
  var cache = {};
  var now = new Date();
  var sent = 0;
  for (var i = 0; i < rows.length; i++) {
    var email = (rows[i][0] || '').toString().toLowerCase();
    var key = rows[i][3];
    var lastSent = Number(rows[i][2]) || 0;
    if (rows[i][4] !== 'active' || !email) continue;
    if (isUnsubscribed(email)) { sheet.getRange(i + 2, 5).setValue('unsubscribed'); continue; }
    var course = cache[key] || (cache[key] = fetchSiteJson(COURSE_BASE_URL + key + '.json'));
    if (!course || !course.lessons) continue;
    if (lastSent >= course.lessons.length) { sheet.getRange(i + 2, 5).setValue('finished'); continue; }
    var days = Math.floor((now - new Date(rows[i][1])) / 86400000);
    if (days < (course.lessons[lastSent].day || 0)) continue;
    if (MailApp.getRemainingDailyQuota() < 1) {
      console.log('Course: daily mail limit reached, the rest go tomorrow.');
      break;
    }
    try {
      sendLesson(email, course, lastSent);
      sheet.getRange(i + 2, 3).setValue(lastSent + 1);
      if (lastSent + 1 >= course.lessons.length) sheet.getRange(i + 2, 5).setValue('finished');
      sent++;
    } catch (err) {
      console.error('Course lesson ' + (lastSent + 1) + ' failed for ' + email + ': ' + err.message);
    }
  }
  console.log('Course: sent ' + sent + ' lesson(s).');
}

function stopCourseFor(email) {
  var sheet = getCourseSheet();
  var last = sheet.getLastRow();
  if (last < 2) return;
  var rows = sheet.getRange(2, 1, last - 1, 5).getValues();
  for (var i = 0; i < rows.length; i++) {
    if ((rows[i][0] || '').toString().toLowerCase() === email && rows[i][4] === 'active') {
      sheet.getRange(i + 2, 5).setValue('unsubscribed');
    }
  }
}

function sendLesson(email, course, index) {
  var L = course.lessons[index];
  var unsub = liveUnsubscribeUrl(email);
  var utm = '?utm_source=newsletter&utm_medium=email&utm_campaign=course_' + course.course;
  var link = function (u) { return SITE_URL + u + utm; };
  var html = '<p>' + escapeHtml(L.intro) + '</p><p><strong>Questions to ask:</strong></p><ul>' +
    L.questions.map(function (q) {
      return '<li style="margin-bottom:10px;">' + escapeHtml(q.q) + '<br><span style="font-size:13px;">From: <a href="' +
        link(q.url) + '">' + escapeHtml(q.title) + '</a></span></li>';
    }).join('') + '</ul>' +
    '<p><a href="' + link(L.stage.url) + '">' + escapeHtml(L.stage.text) + '</a></p>' +
    (L.closing ? '<p>' + escapeHtml(L.closing) + ' <a href="' + link('checklist.html') + '">The checklist</a>.</p>' : '') +
    '<p>Dean</p>' +
    '<p style="font-size:12px; color:#888;">' + escapeHtml(course.footer) + '<br><a href="' + unsub + '">Unsubscribe</a></p>';
  var plain = L.intro + '\n\nQuestions to ask:\n\n' +
    L.questions.map(function (q) { return '- ' + q.q + '\n  From: ' + q.title + '\n  ' + link(q.url); }).join('\n\n') +
    '\n\n' + L.stage.text + ': ' + link(L.stage.url) +
    (L.closing ? '\n\n' + L.closing + ' ' + link('checklist.html') : '') +
    '\n\nDean\n\n' + course.footer + '\nUnsubscribe: ' + unsub;
  MailApp.sendEmail({ to: email, subject: L.subject, body: plain, htmlBody: html, name: DIGEST_FROM_NAME });
}

// Sends every lesson of a course to this script's own account, to read first.
function sendCourseTest() {
  var course = fetchSiteJson(COURSE_BASE_URL + 'after-arrest.json');
  if (!course) { console.log('Course file not found on the site.'); return; }
  for (var i = 0; i < course.lessons.length; i++) sendLesson('caseanalytica@gmail.com', course, i);
  console.log('Sent ' + course.lessons.length + ' test lessons to caseanalytica@gmail.com');
}

function createCourseTrigger() {
  var exists = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'sendCourseLessons'; });
  if (exists) { console.log('Course trigger already exists, skipping.'); return; }
  ScriptApp.newTrigger('sendCourseLessons').timeBased().everyDays(1).atHour(8).create();
  console.log('Course trigger created: runs once a day around 8am, script timezone.');
}

/* ==========================================================================
   Weekly roundup (links to other New York newsrooms)
   ==========================================================================
   Each issue is published to the site as assets/roundups/latest.json. Nothing
   sends on its own: run sendRoundupTest, read it, then run sendRoundup. Each
   address is logged per issue in the RoundupSent tab, so a second run, or a
   run the next day after the mail limit, skips anyone already sent.
   ========================================================================== */

var ROUNDUP_URL = 'https://www.caseanalytica.com/assets/roundups/latest.json';

function sendRoundupTest() {
  var r = fetchSiteJson(ROUNDUP_URL);
  if (!r) { console.log('No roundup file on the site.'); return; }
  sendRoundupTo('caseanalytica@gmail.com', r);
  console.log('Roundup ' + r.issue + ' test sent to caseanalytica@gmail.com');
}

function sendRoundup() {
  var r = fetchSiteJson(ROUNDUP_URL);
  if (!r) { console.log('No roundup file on the site.'); return; }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var log = ss.getSheetByName('RoundupSent') || ss.insertSheet('RoundupSent');
  if (log.getLastRow() === 0) log.appendRow(['issue', 'email', 'sent_at']);
  var done = {};
  if (log.getLastRow() > 1) {
    log.getRange(2, 1, log.getLastRow() - 1, 2).getValues().forEach(function (row) {
      if (row[0] === r.issue) done[(row[1] || '').toString().toLowerCase()] = true;
    });
  }
  var pending = getSubscriberEmails().filter(function (e) { return !done[e]; });
  var sent = 0;
  for (var i = 0; i < pending.length; i++) {
    if (MailApp.getRemainingDailyQuota() < 1) { console.log('Mail limit reached. Run sendRoundup again tomorrow.'); break; }
    try { sendRoundupTo(pending[i], r); log.appendRow([r.issue, pending[i], new Date()]); sent++; }
    catch (err) { console.error('Roundup send failed for ' + pending[i] + ': ' + err.message); }
  }
  console.log('Roundup ' + r.issue + ': sent ' + sent + ', still pending ' + (pending.length - sent));
}

function sendRoundupTo(email, r) {
  var unsub = liveUnsubscribeUrl(email);
  var html = '<p>' + escapeHtml(r.intro) + '</p>' +
    r.items.map(function (it) {
      return '<p><strong><a href="' + it.url + '">' + escapeHtml(it.title) + '</a></strong><br>' +
        '<span style="font-size:13px;">' + escapeHtml(it.outlet + ', ' + it.date + ', ' + it.by) + '</span><br>' +
        escapeHtml(it.summary) + '</p>';
    }).join('') +
    (r.ours ? '<p><strong>From Case Analytica:</strong> <a href="' + r.ours.url + '">' + escapeHtml(r.ours.title) + '</a></p>' : '') +
    '<p>' + escapeHtml(r.signoff || 'Dean') + '</p>' +
    '<p style="font-size:12px; color:#888;"><a href="' + unsub + '">Unsubscribe</a></p>';
  var plain = r.intro + '\n\n' +
    r.items.map(function (it) { return it.title + '\n' + it.outlet + ', ' + it.date + ', ' + it.by + '\n' + it.summary + '\n' + it.url; }).join('\n\n') +
    (r.ours ? '\n\nFrom Case Analytica: ' + r.ours.title + '\n' + r.ours.url : '') +
    '\n\n' + (r.signoff || 'Dean') + '\n\nUnsubscribe: ' + unsub;
  MailApp.sendEmail({ to: email, subject: r.subject, body: plain, htmlBody: html, name: DIGEST_FROM_NAME });
}
