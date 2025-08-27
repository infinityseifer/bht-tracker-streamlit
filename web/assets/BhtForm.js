document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('BhtForm');
  if (!form) return; // safety if script loads before DOM

  const previewBtn     = document.getElementById('previewBtn');
  const confirmBtn     = document.getElementById('confirmSubmitBtn');
  const resetBtn       = document.getElementById('resetBtn');
  const previewSection = document.getElementById('previewSection');
  const previewContent = document.getElementById('previewContent');
  const iframe         = document.getElementsByName('bht_hidden_iframe')[0];

  // Character counter
  const observationField = document.getElementById('Observation');
  const observationCounter = document.getElementById('ObservationCounter');
  if (observationField && observationCounter) {
    observationCounter.textContent = '0 / 5000';
    observationField.addEventListener('input', () => {
      observationCounter.textContent = `${observationField.value.length} / 5000`;
    });
  }
 
  // PREVIEW
  if (previewBtn && previewSection && previewContent) {
    previewBtn.addEventListener('click', () => {
      const data = Object.fromEntries(new FormData(form));

      // Collect checkbox groups (for preview only)
      const collect = name =>
        Array.from(document.querySelectorAll(`input[name="${name}"]:checked`))
          .map(x => x.value);

      data.StudentStrength = collect('StudentStrength');
      data.TierOne         = collect('TierOne');
      data.TierTwo         = collect('TierTwo');
      data.TierThree       = collect('TierThree');

      // Render preview
      let html = "<ul style='list-style:none;padding-left:0;margin:0'>";
      for (const [k, v] of Object.entries(data)) {
        const key = k.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase());
        html += `<li style="margin:8px 0"><strong>${key}:</strong> <span>${
          Array.isArray(v) ? v.join(', ') : (v ?? '')
        }</span></li>`;
      }
      html += '</ul>';

      previewContent.innerHTML = html;
      previewSection.style.display = 'block';
      window.previewFormData = data; // optional stash
    });
  }

  // CONFIRM & SUBMIT (native POST to Apps Script via hidden iframe)
  let isSubmitting = false;
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      // Quick required check (optional; native validation won’t run on unchecked boxes)
      const required = [
        'Role','StudentInitial','StudentID','StudentStatus','TeacherName','TeacherEmail',
        'ParentNotified','MainConcern','AdditionalConcern','Observation',
        'FBA','BehaviorData','BehaviorTime','BehaviorSubject'
      ];
      const fd = new FormData(form);
      for (const f of required) {
        if (!fd.get(f)) {
          alert(`Missing required field: ${f}`);
          return;
        }
      }

      isSubmitting = true;
      confirmBtn.disabled = true;
      // requestSubmit runs built-in validation if you use "required" on inputs
      // form.submit() skips native validation; either is fine here
      form.requestSubmit();
    });
  }

  // Detect Apps Script response (cross-origin iframes still fire load)
  if (iframe) {
    iframe.addEventListener('load', () => {
      if (!isSubmitting) return; // ignore first load
      isSubmitting = false;
      confirmBtn && (confirmBtn.disabled = false);

      alert('Form submitted to Google Sheets!');
      form.reset();
      previewSection && (previewSection.style.display = 'none');
      // reset counter
      if (observationCounter) observationCounter.textContent = '0 / 5000';
    });
  }

  // RESET
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      form.reset();
      previewSection && (previewSection.style.display = 'none');
      if (observationCounter) observationCounter.textContent = '0 / 5000';
    });
  }

  // Save Preview as PDF
  const savePdfBtn = document.getElementById('savePdfBtn');
  if (savePdfBtn) {
    savePdfBtn.addEventListener('click', async () => {
      if (!previewSection || previewSection.style.display === 'none') {
        alert('Preview must be visible to save as PDF.');
        return;
      }
      const { jsPDF } = window.jspdf;
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
      const canvas = await html2canvas(previewSection);
      const img = canvas.toDataURL('image/png');
      const props = pdf.getImageProperties(img);
      const w = pdf.internal.pageSize.getWidth();
      const h = (props.height * w) / props.width;
      pdf.addImage(img, 'PNG', 20, 20, w - 40, h);
      pdf.save('bht-preview.pdf');
    });
  }
});
