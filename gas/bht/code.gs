/***** CONFIG *****/
const SHEET_ID_BHT = '1SYlCYxERDcI-PaQggyTOPgw4Ll5JIHPhQhJcjnD5ih0';
const BHT_SHEET    = 'BHT_Responses';

/***** HEADERS (new: StudentLast, StudentFirst) *****/
const HEADERS_BHT = [
  'Timestamp','Role','StudentLast','StudentFirst','StudentID','StudentStatus',
  'TeacherName','TeacherEmail','ParentNotified','MainConcern','AdditionalConcern',
  'Observation','StudentStrength','TierOne','TierTwo','TierThree',
  'FBA','BehaviorData','BehaviorTime','BehaviorSubject'
];

/***** UI *****/
function doGet(e) {
  if (e?.parameter?.ping === '1') {
    return HtmlService.createHtmlOutput('BHT endpoint is up');
  }
  return HtmlService.createHtmlOutputFromFile('BhtForm').setTitle('BHT Referral Form');
}

/***** POST (web form fallback) *****/
function doPost(e) {
  try {
    const p1 = e?.parameter  || {};
    const pN = e?.parameters || {}; // arrays for checkboxes

    const list = k => (pN[k] ? [].concat(pN[k]).map(safe).join('; ') : safe(p1[k]));

    const rec = {
      Role:              safe(p1.Role),
      StudentLast:       safe(p1.StudentLast),
      StudentFirst:      safe(p1.StudentFirst),
      StudentID:         asText(p1.StudentID),    // keep as text
      StudentStatus:     safe(p1.StudentStatus),
      TeacherName:       safe(p1.TeacherName),
      TeacherEmail:      safe(p1.TeacherEmail),
      ParentNotified:    safe(p1.ParentNotified),
      MainConcern:       safe(p1.MainConcern),
      AdditionalConcern: safe(p1.AdditionalConcern),
      Observation:       safe(p1.Observation),
      StudentStrength:   list('StudentStrength'),
      TierOne:           list('TierOne'),
      TierTwo:           list('TierTwo'),
      TierThree:         list('TierThree'),
      FBA:               safe(p1.FBA),
      BehaviorData:      safe(p1.BehaviorData),
      BehaviorTime:      safe(p1.BehaviorTime),
      BehaviorSubject:   safe(p1.BehaviorSubject),
    };

    _validateRequired(rec);
    _appendBht(rec);
    return HtmlService.createHtmlOutput('OK');
  } catch (err) {
    return _jsonError(err.message || String(err));
  }
}

/***** RPC from HTML via google.script.run *****/
function submitBht(data) {
  const get  = (P, c) => (data && (data[P] ?? data[c])) || '';
  const list = (P, c) => {
    const v = data && (data[P] ?? data[c]);
    return Array.isArray(v) ? v.map(safe).join('; ') : safe(v);
  };

  const rec = {
    Role:              safe(get('Role','role')),
    StudentLast:       safe(get('StudentLast','studentLast')),
    StudentFirst:      safe(get('StudentFirst','studentFirst')),
    StudentID:         asText(get('StudentID','studentId')), // keep as text
    StudentStatus:     safe(get('StudentStatus','studentStatus')),
    TeacherName:       safe(get('TeacherName','teacherName')),
    TeacherEmail:      safe(get('TeacherEmail','teacherEmail')),
    ParentNotified:    safe(get('ParentNotified','parentNotified')),
    MainConcern:       safe(get('MainConcern','mainConcern')),
    AdditionalConcern: safe(get('AdditionalConcern','additionalConcern')),
    Observation:       safe(get('Observation','observation')),
    StudentStrength:   list('StudentStrength','studentStrength'),
    TierOne:           list('TierOne','tierOne'),
    TierTwo:           list('TierTwo','tierTwo'),
    TierThree:         list('TierThree','tierThree'),
    FBA:               safe(get('FBA','fba')),
    BehaviorData:      safe(get('BehaviorData','behaviorData')),
    BehaviorTime:      safe(get('BehaviorTime','behaviorTime')),
    BehaviorSubject:   safe(get('BehaviorSubject','behaviorSubject')),
  };

  _validateRequired(rec);
  const ts = _appendBht(rec);
  return { ok: true, ts };
}

/***** Append with header auto-upgrade (non-destructive) *****/
function _appendBht(rec) {
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

  // Ensure StudentID column is plain text (no commas, keep leading zeros)
  const idx = existing.indexOf('StudentID');
  if (idx >= 0) {
    sh.getRange(1, idx + 1, sh.getMaxRows(), 1).setNumberFormat('@');
  }

  // Build name→index map (1-based)
  const map = {};
  existing.forEach((name, i) => { if (name) map[name] = i + 1; });

  return { sh, map };
}

/***** Helpers *****/
// Keep value as plain text (prevents commas/num formatting & preserves leading zeros)
function asText(v) {
  v = String(v ?? '').trim();
  return v ? (v[0] === "'" ? v : "'" + v) : '';
}

// Trim + prevent formula injection
function safe(v) {
  v = String(v ?? '').trim();
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}

function isBlank(v) {
  return String(v ?? '').trim() === '';
}

function _validateRequired(rec) {
  const required = [
    'Role','StudentLast','StudentFirst','StudentID','StudentStatus',
    'TeacherName','TeacherEmail','ParentNotified','MainConcern',
    'AdditionalConcern','Observation','FBA','BehaviorData',
    'BehaviorTime','BehaviorSubject'
  ];
  for (const k of required) {
    if (isBlank(rec[k])) throw new Error(`Missing required field: ${k}`);
  }
}

function _jsonError(message) {
  return ContentService
    .createTextOutput(JSON.stringify({ result: 'error', message }))
    .setMimeType(ContentService.MimeType.JSON);
}
