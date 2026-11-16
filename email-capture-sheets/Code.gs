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
var ROUNDUP_FROM_NAME = 'Case Analytica';

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

// ---------------------------------------------------------------------------
// Roundup email layout: black stage, one huge number, grey lines, blue links.
// Built as nested tables with inline styles because Gmail and Outlook ignore
// most modern CSS. Every block after the header is optional and only renders
// when the issue JSON has the field:
//   hero     {kicker, number, line, url, link_text}
//   ours_week [{title, url, category, date, excerpt, image, credit}]
//   stat     {number, line, url, link_text}
//   question "the exact question to ask"
//   items    [{outlet, date, by, title, url, summary}]
//   give     {url, label, line, ways[], sponsor} bottom donation block; false turns it off
//   giveMid  {url, label, heading, line} box midway through the other-newsroom stories; false turns it off
// Both default to RD_GIVE / RD_GIVE_MID below (Julie, 2026-11-15: a box midway and one at the bottom, different referral codes).
// ---------------------------------------------------------------------------
var RD_FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif";
var RD_SERIF = "'New York',Georgia,'Times New Roman',serif";
var RD_MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
var RD_DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

// Donation blocks. Gift wording: "Your gift is tax-deductible." is the cleared short line; the sponsor line is Ellen's, verbatim (2026-10-08).
// Each placement has its own FundRazr referral code so gifts can be traced. The bottom code is empty until it is created
// (FundRazr > Engage > Referrals); with it empty the bottom block is skipped, never sent with a wrong link.
var RD_REF_MID = 'https://fundrazr.com/CaseAnalytica?ref=cr_dFFMM9';
var RD_REF_BOTTOM = '';
var RD_SPONSOR_LINE = 'Case Analytica is fiscally sponsored by the Alternative Newsweekly Foundation, EIN 30-0100369. All donations are tax-deductible to the extent allowed by law.';
var RD_GIVE_MID = {
  url: RD_REF_MID,
  heading: 'Enjoy our free stories?',
  line: 'Case Analytica is free to read and runs on reader gifts. Your gift is tax-deductible.',
  label: 'Donate today'
};
var RD_GIVE = {
  url: RD_REF_BOTTOM,
  label: 'Donate today',
  line: 'If this reporting helps you, help keep it free. Your gift is tax-deductible.',
  ways: [
    { text: 'Donor-advised fund: contact your fund manager and designate a gift for Case Analytica using the Alternative Newsweekly Foundation EIN, 30-0100369.' },
    { text: 'Stock: write to stock@altnewsfoundation.org.' },
    { text: 'Crypto: ', url: 'https://altnewsfoundation.org/caseanalytica/' }
  ],
  sponsor: RD_SPONSOR_LINE
};

function roundupGive(r) { if (r.give === false) return null; var g = r.give || RD_GIVE; return g && g.url ? g : null; }
function roundupGiveMid(r) { if (r.giveMid === false) return null; var g = r.giveMid || RD_GIVE_MID; return g && g.url ? g : null; }

function roundupOurs(r) {
  if (r.ours_week && r.ours_week.length) return r.ours_week;
  return r.ours ? [r.ours] : [];
}

function roundupDateLabel(issue) {
  var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(issue || '');
  if (!m) return '';
  var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return RD_DAYS[d.getUTCDay()] + ', ' + RD_MONTHS[d.getUTCMonth()] + ' ' + (+m[3]) + ', ' + m[1];
}

function rdLink(url, text, size) {
  return '<a href="' + url + '" style="color:#2997ff;text-decoration:none;font-size:' + (size || 18) + 'px;">' + escapeHtml(text) + ' &rsaquo;</a>';
}

function rdRow(inner, extraTdStyle) {
  return '<tr><td class="pad" style="padding:' + (extraTdStyle || '0 28px') + ';font-family:' + RD_FONT + ';color:#f5f5f7;">' + inner + '</td></tr>';
}

function rdLabel(text) {
  return rdRow('<div style="font-size:15px;font-weight:600;color:#86868b;padding:10px 0 14px;">' + escapeHtml(text) + '</div>');
}

function rdHeroHtml(h) {
  return '<tr><td class="pad" align="center" style="padding:70px 28px 74px;font-family:' + RD_FONT + ';">' +
    (h.kicker ? '<div style="font-size:19px;font-weight:600;color:#f5f5f7;">' + escapeHtml(h.kicker) + '</div>' : '') +
    '<div class="big" style="font-size:132px;font-weight:700;letter-spacing:-4px;line-height:1.05;color:#f5f5f7;margin:6px 0;">' + escapeHtml(h.number) + '</div>' +
    '<div style="font-size:22px;line-height:1.3;color:#86868b;margin:0 auto 22px;max-width:430px;">' + escapeHtml(h.line) + '</div>' +
    (h.url ? rdLink(h.url, h.link_text || 'Read the story') : '') +
    '</td></tr>';
}

function rdTileHtml(a) {
  var img = a.image
    ? '<tr><td style="font-size:0;line-height:0;"><a href="' + a.url + '"><img src="' + a.image + '" width="552" alt="" style="display:block;width:100%;max-width:552px;height:auto;border:0;"></a></td></tr>'
    : '';
  var ey = [a.category, a.date].filter(function (x) { return x; }).join('  ·  ');
  return '<tr><td class="pad" style="padding:0 20px 18px;">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#161618" style="background:#161618;border-radius:22px;overflow:hidden;">' + img +
    '<tr><td style="padding:20px 24px 26px;font-family:' + RD_FONT + ';">' +
    (ey ? '<div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#86868b;">' + escapeHtml(ey) + '</div>' : '') +
    '<div class="h3" style="font-size:25px;line-height:1.16;font-weight:700;color:#f5f5f7;margin:9px 0 10px;"><a href="' + a.url + '" style="color:#f5f5f7;text-decoration:none;">' + escapeHtml(a.title) + '</a></div>' +
    (a.excerpt ? '<div style="font-size:16px;line-height:1.45;color:#a1a1a6;margin:0 0 14px;">' + escapeHtml(a.excerpt) + '</div>' : '') +
    rdLink(a.url, 'Read the story') +
    (a.credit ? '<div style="font-size:11px;color:#6e6e73;margin-top:14px;">' + escapeHtml(a.credit) + '</div>' : '') +
    '</td></tr></table></td></tr>';
}

function rdStatHtml(s) {
  return '<tr><td class="pad" align="center" style="padding:84px 28px;font-family:' + RD_FONT + ';">' +
    '<div class="big" style="font-size:120px;font-weight:700;letter-spacing:-4px;line-height:1.05;color:#f5f5f7;">' + escapeHtml(s.number) + '</div>' +
    '<div style="font-size:20px;line-height:1.35;color:#86868b;margin:10px auto 18px;max-width:440px;">' + escapeHtml(s.line) + '</div>' +
    (s.url ? rdLink(s.url, s.link_text || 'See the data') : '') +
    '</td></tr>';
}

function rdQuestionHtml(q) {
  return '<tr><td class="pad" style="padding:6px 20px 18px;">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#161618" style="background:#161618;border-radius:22px;">' +
    '<tr><td align="center" style="padding:34px 28px;font-family:' + RD_FONT + ';">' +
    '<div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#2997ff;">The exact question to ask</div>' +
    '<div style="font-family:' + RD_SERIF + ';font-size:25px;line-height:1.3;font-style:italic;color:#f5f5f7;margin-top:12px;">&ldquo;' + escapeHtml(q) + '&rdquo;</div>' +
    '</td></tr></table></td></tr>';
}

function rdItemHtml(it) {
  return '<tr><td class="pad" style="padding:0 28px;">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:1px solid #2a2a2d;padding:18px 0;font-family:' + RD_FONT + ';">' +
    '<div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#86868b;">' + escapeHtml(it.outlet + '  ·  ' + it.date + '  ·  ' + it.by) + '</div>' +
    '<div style="font-size:19px;font-weight:600;line-height:1.25;margin:6px 0;"><a href="' + it.url + '" style="color:#f5f5f7;text-decoration:none;">' + escapeHtml(it.title) + '</a></div>' +
    '<div style="font-size:15px;line-height:1.5;color:#a1a1a6;">' + escapeHtml(it.summary) + '</div>' +
    '</td></tr></table></td></tr>';
}

function rdGiveMidHtml(g) {
  return '<tr><td class="pad" style="padding:8px 28px 8px;font-family:' + RD_FONT + ';">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="center" style="background:#1c1c1e;border-radius:18px;padding:30px 24px;">' +
    '<div style="font-size:26px;line-height:1.15;font-weight:700;letter-spacing:-.5px;color:#f5f5f7;margin:0 0 8px;">' + escapeHtml(g.heading || 'Enjoy our free stories?') + '</div>' +
    '<div style="font-size:16px;line-height:1.45;color:#a1a1a6;margin:0 auto 18px;max-width:400px;">' + escapeHtml(g.line) + '</div>' +
    '<a href="' + g.url + '" style="display:inline-block;background:#2997ff;color:#ffffff;font-size:16px;text-decoration:none;padding:11px 24px;border-radius:980px;">' + escapeHtml(g.label || 'Donate today') + '</a>' +
    '</td></tr></table></td></tr>';
}

function rdGiveHtml(g) {
  var ways = '';
  if (g.ways && g.ways.length) {
    ways = '<div style="font-size:13px;line-height:1.6;color:#86868b;margin:26px auto 0;max-width:440px;text-align:left;">' +
      '<div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#86868b;margin-bottom:6px;">Other ways to give</div>' +
      g.ways.map(function (w) {
        return '<div style="margin:0 0 5px;">' + escapeHtml(w.text) + (w.url ? '<a href="' + w.url + '" style="color:#2997ff;text-decoration:none;">' + escapeHtml(w.url.replace(/^https?:\/\//, '')) + '</a>' : '') + '</div>';
      }).join('') + '</div>';
  }
  return '<tr><td class="pad" align="center" style="padding:56px 28px 44px;font-family:' + RD_FONT + ';">' +
    '<div style="font-size:38px;line-height:1.1;font-weight:700;letter-spacing:-1px;color:#f5f5f7;margin:0 0 10px;">Reporting that stays free.</div>' +
    '<div style="font-size:18px;line-height:1.4;color:#86868b;margin:0 auto 22px;max-width:420px;">' + escapeHtml(g.line || 'If this reporting helps you, help keep it free. Your gift is tax-deductible.') + '</div>' +
    '<a href="' + g.url + '" style="display:inline-block;background:#2997ff;color:#ffffff;font-size:17px;text-decoration:none;padding:12px 26px;border-radius:980px;">' + escapeHtml(g.label || 'Donate today') + '</a>' +
    ways +
    '<div style="font-size:12px;line-height:1.5;color:#6e6e73;margin:22px auto 0;max-width:440px;">' + escapeHtml(g.sponsor || RD_SPONSOR_LINE) + '</div>' +
    '</td></tr>';
}

function buildRoundupHtml(r, unsub) {
  var ours = roundupOurs(r);
  var rows = '';
  rows += '<tr><td class="pad" style="padding:26px 28px 0;font-family:' + RD_FONT + ';">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>' +
    '<td style="font-size:17px;font-weight:600;color:#f5f5f7;">Case<span style="color:#c6a068;">Analytica</span></td>' +
    '<td align="right" style="font-size:13px;color:#86868b;">' + escapeHtml(roundupDateLabel(r.issue)) + '</td>' +
    '</tr></table></td></tr>';
  if (r.hero) rows += rdHeroHtml(r.hero);
  if (ours.length) {
    rows += rdLabel('From Case Analytica this week');
    rows += ours.map(rdTileHtml).join('');
  }
  if (r.stat) rows += rdStatHtml(r.stat);
  if (r.question) rows += rdQuestionHtml(r.question);
  if (r.items && r.items.length) {
    rows += rdRow('<div style="font-size:15px;font-weight:600;color:#86868b;padding:44px 0 14px;">Worth your time, from other New York newsrooms</div>');
    var mid = roundupGiveMid(r), half = Math.ceil(r.items.length / 2);
    r.items.forEach(function (it, i) {
      rows += rdItemHtml(it);
      if (mid && i === half - 1 && i < r.items.length - 1) rows += rdGiveMidHtml(mid);
    });
  }
  var give = roundupGive(r);
  if (give) rows += rdGiveHtml(give);
  rows += '<tr><td align="center" style="padding:28px 28px 8px;font-family:' + RD_FONT + ';font-size:17px;font-weight:600;color:#f5f5f7;">' + escapeHtml(r.signoff || 'Case Analytica') + '</td></tr>';
  var link = function (u, t) { return '<a href="' + u + '" style="color:#86868b;text-decoration:none;">' + t + '</a>'; };
  rows += '<tr><td align="center" style="padding:22px 28px 40px;font-family:' + RD_FONT + ';font-size:12px;line-height:1.8;color:#6e6e73;">' +
    link('https://www.caseanalytica.com', 'caseanalytica.com') + ' &nbsp;&middot;&nbsp; ' +
    link('https://bsky.app/profile/caseanalytica.bsky.social', 'Bluesky') + ' &nbsp;&middot;&nbsp; ' +
    link('https://www.youtube.com/@caseanalytica', 'YouTube') + ' &nbsp;&middot;&nbsp; ' +
    link('https://www.tiktok.com/@case.analytica', 'TikTok') + ' &nbsp;&middot;&nbsp; ' +
    link('https://www.instagram.com/caseanalytica/', 'Instagram') + ' &nbsp;&middot;&nbsp; ' +
    link('https://www.linkedin.com/company/caseanalytica', 'LinkedIn') + '<br>' +
    'General information, not legal advice.<br>' +
    link(unsub, '<u>Unsubscribe</u>') + '</td></tr>';
  return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">' +
    '<style>@media only screen and (max-width:620px){.w{width:100%!important}.big{font-size:84px!important;letter-spacing:-3px!important}.pad{padding-left:20px!important;padding-right:20px!important}.h3{font-size:22px!important}}</style></head>' +
    '<body bgcolor="#000000" style="margin:0;padding:0;background:#000000;">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#000000" style="background:#000000;"><tr><td align="center">' +
    '<table role="presentation" class="w" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#000000" style="width:600px;max-width:100%;background:#000000;">' +
    rows + '</table></td></tr></table></body></html>';
}

function buildRoundupPlain(r, unsub) {
  var out = [];
  if (r.hero) out.push(r.hero.number + '\n' + r.hero.line + (r.hero.url ? '\n' + r.hero.url : ''));
  var ours = roundupOurs(r);
  if (ours.length) out.push('From Case Analytica this week\n\n' + ours.map(function (a) { return a.title + (a.excerpt ? '\n' + a.excerpt : '') + '\n' + a.url; }).join('\n\n'));
  if (r.stat) out.push(r.stat.number + '\n' + r.stat.line + (r.stat.url ? '\n' + r.stat.url : ''));
  if (r.question) out.push('The exact question to ask:\n"' + r.question + '"');
  if (r.items && r.items.length) {
    var mid = roundupGiveMid(r), half = Math.ceil(r.items.length / 2);
    var blocks = r.items.map(function (it) { return it.title + '\n' + it.outlet + ', ' + it.date + ', ' + it.by + '\n' + it.summary + '\n' + it.url; });
    if (mid && half < blocks.length) blocks.splice(half, 0, (mid.heading || 'Enjoy our free stories?') + '\n' + mid.line + '\n' + mid.url);
    out.push('Worth your time, from other New York newsrooms\n\n' + blocks.join('\n\n'));
  }
  var give = roundupGive(r);
  if (give) {
    var gw = (give.ways || []).map(function (w) { return w.text + (w.url || ''); }).join('\n');
    out.push((give.line || '') + '\n' + give.url + (gw ? '\n\nOther ways to give:\n' + gw : '') + '\n\n' + (give.sponsor || RD_SPONSOR_LINE));
  }
  out.push(r.signoff || 'Case Analytica');
  out.push('Unsubscribe: ' + unsub);
  return out.join('\n\n');
}

function sendRoundupTo(email, r) {
  var unsub = liveUnsubscribeUrl(email);
  MailApp.sendEmail({ to: email, subject: r.subject, body: buildRoundupPlain(r, unsub), htmlBody: buildRoundupHtml(r, unsub), name: ROUNDUP_FROM_NAME });
}
