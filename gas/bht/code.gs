/************ CONFIG (global) ************/
const SHEET_ID_BHT = '1SYlCYxERDcI-PaQggyTOPgw4Ll5JIHPhQhJcjnD5ih0';
const BHT_SHEET    = 'BHT_Responses';
const SENDER_NAME  = 'BHT Tracker Alerts';

/** Optional: if you want a default group receipt recipient, add it here (or leave blank) */
const DEFAULT_RECEIPT_CC = ''; // e.g., 'counselor@cps.edu'
/******************************************/

/************ HEADERS (includes new fields) ************/
const HEADERS_BHT = [
  'Timestamp','Role','StudentLast','StudentFirst','StudentID','StudentStatus',
  'TeacherName','TeacherEmail','ParentNotified','MainConcern','AdditionalConcern',
  'Observation','StudentStrength','TierOne','TierTwo','TierThree',
  'FBA','BehaviorData','BehaviorTime','BehaviorSubject',
  'NextSteps','ReceiptEmails'
];
/*******************************************************/

/***** UI *****/
function doGet(e) {
  if (e?.parameter?.ping === '1') {
    return HtmlService.createHtmlOutput('BHT endpoint is up');
  }
  return HtmlService
    .createHtmlOutputFromFile('BhtForm')
    .setTitle('BHT Referral Form');
}

/***** POST (web form fallback) *****/
function doPost(e) {
  try {
    const p1 = e?.parameter  || {};
    const pN = e?.parameters || {}; // arrays for checkbox-style fields (if ever used)

    const list = k => (pN[k] ? [].concat(pN[k]).map(safe_).join('; ') : safe_(p1[k]));

    const rec = {
      Role:              safe_(p1.Role),
      StudentLast:       safe_(p1.StudentLast),
      StudentFirst:      safe_(p1.StudentFirst),
      StudentID:         asText_(p1.StudentID),     // keep as text
      StudentStatus:     safe_(p1.StudentStatus),
      TeacherName:       safe_(p1.TeacherName),
      TeacherEmail:      safe_(p1.TeacherEmail),
      ParentNotified:    safe_(p1.ParentNotified),
      MainConcern:       safe_(p1.MainConcern),
      AdditionalConcern: safe_(p1.AdditionalConcern),
      Observation:       safe_(p1.Observation),

      // If submitted as checkbox arrays, still works; if submitted as text, still works.
      StudentStrength:   list('StudentStrength'),
      TierOne:           list('TierOne'),
      TierTwo:           list('TierTwo'),
      TierThree:         list('TierThree'),

      FBA:               safe_(p1.FBA),
      BehaviorData:      safe_(p1.BehaviorData),
      BehaviorTime:      safe_(p1.BehaviorTime),
      BehaviorSubject:   safe_(p1.BehaviorSubject),

      // NEW
      NextSteps:         safe_(p1.NextSteps),
      ReceiptEmails:     safe_(p1.ReceiptEmails),
    };

    validateRequired_(rec);
    const ts = appendBht_(rec);
    sendTeacherReceipt_(rec, ts);

    return HtmlService.createHtmlOutput('OK');
  } catch (err) {
    return jsonError_(err?.message || String(err));
  }
}

/***** RPC from HTML via google.script.run *****/
function submitBht(data) {
  const get  = (P, c) => (data && (data[P] ?? data[c])) || '';
  const list = (P, c) => {
    const v = data && (data[P] ?? data[c]);
    return Array.isArray(v) ? v.map(safe_).join('; ') : safe_(v);
  };

  const rec = {
    Role:              safe_(get('Role','role')),
    StudentLast:       safe_(get('StudentLast','studentLast')),
    StudentFirst:      safe_(get('StudentFirst','studentFirst')),
    StudentID:         asText_(get('StudentID','studentId')), // keep as text
    StudentStatus:     safe_(get('StudentStatus','studentStatus')),
    TeacherName:       safe_(get('TeacherName','teacherName')),
    TeacherEmail:      safe_(get('TeacherEmail','teacherEmail')),
    ParentNotified:    safe_(get('ParentNotified','parentNotified')),
    MainConcern:       safe_(get('MainConcern','mainConcern')),
    AdditionalConcern: safe_(get('AdditionalConcern','additionalConcern')),
    Observation:       safe_(get('Observation','observation')),

    // Multi-selects (Choices.js sends arrays)
    StudentStrength:   list('StudentStrength','studentStrength'),
    TierOne:           list('TierOne','tierOne'),
    TierTwo:           list('TierTwo','tierTwo'),
    TierThree:         list('TierThree','tierThree'),

    FBA:               safe_(get('FBA','fba')),
    BehaviorData:      safe_(get('BehaviorData','behaviorData')),
    BehaviorTime:      safe_(get('BehaviorTime','behaviorTime')),
    BehaviorSubject:   safe_(get('BehaviorSubject','behaviorSubject')),

    // NEW
    NextSteps:         safe_(get('NextSteps','nextSteps')),
    ReceiptEmails:     safe_(get('ReceiptEmails','receiptEmails')),
  };

  validateRequired_(rec);

  const ts = appendBht_(rec);
  sendTeacherReceipt_(rec, ts);

  return { ok: true, ts };
}

/***** Append with header auto-upgrade (non-destructive) *****/
function appendBht_(rec) {
  const { sh, map } = ensureSheetAndHeaderMap_(SHEET_ID_BHT, BHT_SHEET, HEADERS_BHT);

  const tz = Session.getScriptTimeZone();
  const ts = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm:ss');

  const lock = LockService.getScriptLock();
  lock.tryLock(3000);
  try {
    const lastCol = sh.getLastColumn();
    const row = Array(lastCol).fill('');

    // Always set Timestamp first
    if (map.Timestamp) row[map.Timestamp - 1] = ts;

    // Fill known columns by header name
    for (const [k, v] of Object.entries(rec)) {
      const idx = map[k];
      if (idx) row[idx - 1] = v;
    }

    const nextR = sh.getLastRow() + 1;
    sh.getRange(nextR, 1, 1, row.length).setValues([row]);
  } finally {
    lock.releaseLock();
  }
  return ts;
}

/***** Sheet/Header utilities *****/
function ensureSheetAndHeaderMap_(sheetId, sheetName, headers) {
  const ss = SpreadsheetApp.openById(sheetId);
  const sh = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);

  // If empty, write headers fresh
  if (sh.getLastRow() === 0) {
    sh.appendRow(headers);
  }

  // Build existing header list
  const firstRow = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  let existing = firstRow.map(v => String(v || '').trim());

  // Add any missing headers at the end (preserve existing data layout)
  for (const h of headers) {
    if (!existing.includes(h)) {
      sh.getRange(1, existing.length + 1).setValue(h);
      existing.push(h);
    }
  }

  // Ensure StudentID column is plain text (keeps leading zeros; prevents commas)
  const studentIdIdx = existing.indexOf('StudentID');
  if (studentIdIdx >= 0) {
    sh.getRange(1, studentIdIdx + 1, sh.getMaxRows(), 1).setNumberFormat('@');
  }

  // Build name→index map (1-based)
  const map = {};
  existing.forEach((name, i) => { if (name) map[name] = i + 1; });

  return { sh, map };
}

/***** Validation *****/
function validateRequired_(rec) {
  const required = [
    'Role','StudentLast','StudentFirst','StudentID','StudentStatus',
    'TeacherName','TeacherEmail','ParentNotified','MainConcern',
    'AdditionalConcern','Observation','FBA','BehaviorData',
    'BehaviorTime','BehaviorSubject',
    'NextSteps' // NEW: required
  ];
  for (const k of required) {
    if (isBlank_(rec[k])) throw new Error(`Missing required field: ${k}`);
  }
}

/***** Teacher Receipt Email *****/
function sendTeacherReceipt_(rec, ts) {
  // Always send to TeacherEmail; optionally add ReceiptEmails (comma-separated) and DEFAULT_RECEIPT_CC
  const toSet = new Set();

  const teacherEmail = String(rec.TeacherEmail || '').trim();
  if (teacherEmail) toSet.add(teacherEmail);

  const extra = String(rec.ReceiptEmails || '').trim();
  if (extra) {
    extra.split(',')
      .map(e => e.trim())
      .filter(e => e && e.includes('@'))
      .forEach(e => toSet.add(e));
  }

  const cc = String(DEFAULT_RECEIPT_CC || '').trim();
  if (cc) {
    cc.split(',')
      .map(e => e.trim())
      .filter(e => e && e.includes('@'))
      .forEach(e => toSet.add(e));
  }

  const to = [...toSet].join(',');
  if (!to) return;

  const subject = `BHT Teacher Receipt — ${rec.StudentLast}, ${rec.StudentFirst}`;

  const html = `
  <div style="font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;">
    <h2 style="margin:0 0 6px;">BHT Teacher Receipt</h2>
    <div style="color:#666;margin:0 0 14px;">Submitted: <b>${escapeHtml_(ts || '')}</b></div>

    <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;min-width:520px;">
      <tbody>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Role</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.Role)}</td></tr>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Student</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.StudentLast)}, ${escapeHtml_(rec.StudentFirst)}</td></tr>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Teacher/POC</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.TeacherName)}</td></tr>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Parent/Guardian notified</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.ParentNotified)}</td></tr>

        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Main concern</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.MainConcern)}</td></tr>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Additional concern</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.AdditionalConcern)}</td></tr>

        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Observation</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;white-space:pre-wrap;">${escapeHtml_(rec.Observation)}</td></tr>

        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Student strength</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.StudentStrength)}</td></tr>

        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Tier I</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.TierOne)}</td></tr>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Tier II</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.TierTwo)}</td></tr>
        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Tier III</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;">${escapeHtml_(rec.TierThree)}</td></tr>

        <tr><td style="padding:6px 10px;border-bottom:1px solid #eee;"><b>Next steps</b></td><td style="padding:6px 10px;border-bottom:1px solid #eee;white-space:pre-wrap;">${escapeHtml_(rec.NextSteps)}</td></tr>
      </tbody>
    </table>

    <div style="color:#888;margin-top:14px;">This is an automated message from the BHT Tracker.</div>
  </div>`;

  MailApp.sendEmail({
    to,
    subject,
    htmlBody: html,
    name: SENDER_NAME,
    noReply: true
  });
}

/***** Helpers *****/
// Keep value as plain text (prevents commas/num formatting & preserves leading zeros)
function asText_(v) {
  v = String(v ?? '').trim();
  return v ? (v[0] === "'" ? v : "'" + v) : '';
}

// Trim + prevent formula injection
function safe_(v) {
  v = String(v ?? '').trim();
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}

function isBlank_(v) {
  return String(v ?? '').trim() === '';
}

function escapeHtml_(s) {
  return String(s || '')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#39;');
}

function jsonError_(message) {
  return ContentService
    .createTextOutput(JSON.stringify({ result: 'error', message }))
    .setMimeType(ContentService.MimeType.JSON);
}
