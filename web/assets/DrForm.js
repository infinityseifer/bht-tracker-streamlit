// DrForm.js (mirrors BHT flow)
document.addEventListener('DOMContentLoaded', () => {
  const form           = document.getElementById('DrForm');
  const iframe         = document.getElementsByName('dr_hidden_iframe')[0];
  const previewBtn     = document.getElementById('previewBtn');
  const confirmBtn     = document.getElementById('confirmSubmitBtn');
  const resetBtn       = document.getElementById('resetBtn');
  const savePdfBtn     = document.getElementById('savePdfBtn');
  const previewSection = document.getElementById('previewSection');
  const previewContent = document.getElementById('previewContent');

  // Narrative counter
  const narrative = document.getElementById('Narrative');
  const counter   = document.getElementById('narrativeCounter');
  if (narrative && counter) {
    narrative.addEventListener('input', () => {
      counter.textContent = `${narrative.value.length} / 2500`;
    });
  }
 
  // Preview
  if (previewBtn) {
    previewBtn.addEventListener('click', () => {
      const data = Object.fromEntries(new FormData(form).entries());

      // Optional: nicer datetime in preview (doesn't affect submission)
      const display = { ...data };
      if (display.DateTime) {
        try { display.DateTime = new Date(display.DateTime).toISOString(); } catch {}
      }

      let html = "<ul style='list-style:none;padding-left:0'>";
      for (const [k, v] of Object.entries(display)) {
        const key = k.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase());
        html += `<li><strong>${key}:</strong> ${Array.isArray(v) ? v.join(', ') : v}</li>`;
      }
      html += "</ul>";

      previewContent.innerHTML = html;
      previewSection.style.display = 'block';
    });
  }

  // Submit to GAS via hidden iframe
  let isSubmitting = false;
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      isSubmitting = true;
      form.submit(); // posts to Apps Script /exec
    });
  }

  // Success callback when iframe loads
  if (iframe) {
    iframe.addEventListener('load', () => {
      if (!isSubmitting) return;
      isSubmitting = false;
      alert('Form submitted to Google Sheets!');
      form.reset();
      previewSection.style.display = 'none';
    });
  }

  // Reset
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      form.reset();
      previewSection.style.display = 'none';
    });
  }

  // Save Preview as PDF
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
      pdf.save('dr-preview.pdf');
    });
  }
});
