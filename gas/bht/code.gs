/*** CONFIG ***/
const SHEET_ID = '1AMMfzbKreprRrhzJwMeQq9_2spdEvDLfGtEYnEMyF_8';
const RESPONSES_TAB = 'BHT_Responses';  // change if your tab name differs

function doGet() {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setTitle('BHT Referral Form')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL); // so you can open from Streamlit
}

/** Provide options to the form (could be moved to a Config sheet later) */
function getFormOptions() {
  return {
    grades: ['K','1','2','3','4','5','6','7','8'],
    proactiveConcerns: [
      'Attendance','Work Completion','Peer Conflict','Self-Management','Organization'
    ],
    teacherInterventions: [
      'Re-teach Expectation','Parent Contact','Seat Change','Break/Calming','Restorative Chat'
    ],
    minorProblems: [
      'Off-task','Talking Out','Non-compliance','Unprepared','Tardy'
    ],
    majorProblems: [
      'Fighting','Bullying/Harassment','Threats','Property Damage','Elopement'
    ],
    tier3Interventions: [
      'Check-in/Check-out','Mentoring','FBA/BIP','Counseling','Small Group',
      'SAS' // 👈 added per your request
    ]
  };
}

/** Receive submission and write to the sheet */
function submitBHT(payload) {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sh = ss.getSheetByName(RESPONSES_TAB) || ss.insertSheet(RESPONSES_TAB);

  // Ensure header exists once
  const header = [
    'Timestamp',
    'StudentFirst','StudentLast','Grade',
    'ProactiveConcerns','TeacherInterventions',
    'MinorProblems','MajorProblems','Tier3Interventions',
    'Notes','Referrer'
  ];
  if (sh.getLastRow() === 0) sh.appendRow(header);

  const safe = v => (Array.isArray(v) ? v.join('; ') : (v ?? '')).toString().trim();
  const row = [
    new Date(),
    safe(payload.StudentFirst),
    safe(payload.StudentLast),
    safe(payload.Grade),
    safe(payload.ProactiveConcerns),
    safe(payload.TeacherInterventions),
    safe(payload.MinorProblems),
    safe(payload.MajorProblems),
    safe(payload.Tier3Interventions),
    safe(payload.Notes),
    safe(payload.Referrer),
  ];
  sh.appendRow(row);
  return { ok: true };
}

/** Allow including HTML partials if you ever split the UI */
function include_(fn) { return HtmlService.createHtmlOutputFromFile(fn).getContent(); }
