// DR.gs
const SHEET_ID_DR = '1AMMfzbKreprRrhzJwMeQq9_2spdEvDLfGtEYnEMyF_8';
const DR_SHEET    = 'DR_Responses';

function doPost(e) {
  try {
    const p = e.parameter || {};
    const headers = [
      'Timestamp','StudentLast','StudentFirst','Grade','DateTime','HomeroomTeacher',
      'TeacherIntervention','ProactiveConcern','Narrative','MinorProblemBehavior',
      'MajorProblemBehavior','NextSteps','SELCompetency'
    ];
    const sh = ensureSheetWithHeaders_(SHEET_ID_DR, DR_SHEET, headers);

    sh.appendRow([
      new Date(),
      p.StudentLast || '',
      p.StudentFirst || '',
      p.Grade || '',
      p.DateTime || '',
      p.HomeroomTeacher || '',
      p.TeacherIntervention || '',
      p.ProactiveConcern || '',
      p.Narrative || '',
      p.MinorProblemBehavior || '',
      p.MajorProblemBehavior || '',
      p.NextSteps || '',
      p.SELCompetency || ''
    ]);

    return HtmlService.createHtmlOutput('OK'); // minimal response for hidden iframe
  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ error: err.message })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return HtmlService.createHtmlOutput('DR endpoint is up');
}

function ensureSheetWithHeaders_(sheetId, sheetName, headers) {
  const ss = SpreadsheetApp.openById(sheetId);
  const sh = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
  if (sh.getLastRow() === 0) sh.appendRow(headers);
  return sh;
}
