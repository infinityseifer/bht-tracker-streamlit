// wwwroot/admin.js
(function () {
  function q(id) { return document.getElementById(id); }
  function log(...a) { console.log("[admin]", ...a); }

  document.addEventListener("DOMContentLoaded", () => {
    const frame   = q("frame");
    const spinner = q("spinner");
    const wrap    = q("sheetEmbed");
    const eda     = q("edaPanel");

    const btnDR   = q("btn-dr");
    const btnBHT  = q("btn-bht");
    const btnEDA  = q("btn-eda");
    const btnRef  = q("btn-refresh");
    const btnOpen = q("btn-open");

    if (!frame || !spinner || !wrap || !eda) {
      console.error("Required DOM nodes missing. Check IDs in admin.html.");
      return;
    }

    // Small helpers
    const setActive = (btn) => {
      [btnDR, btnBHT, btnEDA].forEach(b => b && b.classList.remove("active"));
      btn && btn.classList.add("active");
    };
    const showSpinner = (on) => spinner.style.display = on ? "grid" : "none";

    const showEmbed = (url, sourceBtn) => {
      if (!url) {
        alert("No embed URL configured for this view.");
        return;
      }
      eda.classList.add("hidden");
      wrap.classList.remove("hidden");
      setActive(sourceBtn);
      showSpinner(true);
      frame.src = url;
      // update "Open in new tab"
      if (btnOpen) {
        btnOpen.href = url;
        btnOpen.classList.remove("hidden");
      }
    };

    const showEDA = () => {
      wrap.classList.add("hidden");
      eda.classList.remove("hidden");
      setActive(btnEDA);
      if (btnOpen) {
        btnOpen.href = "about:blank";
        btnOpen.classList.add("hidden");
      }
    };

    // Frame load hides spinner
    frame.addEventListener("load", () => showSpinner(false));

    // Wire buttons
    btnDR?.addEventListener("click", () => {
      log("DR clicked");
      const url = (window.ADMIN_EMBEDS && window.ADMIN_EMBEDS.DR) || "";
      showEmbed(url, btnDR);
    });

    btnBHT?.addEventListener("click", () => {
      log("BHT clicked");
      const url = (window.ADMIN_EMBEDS && window.ADMIN_EMBEDS.BHT) || "";
      showEmbed(url, btnBHT);
    });

    btnEDA?.addEventListener("click", () => {
      log("EDA clicked");
      showEDA();
    });

    btnRef?.addEventListener("click", () => {
      log("Refresh clicked");
      if (!wrap.classList.contains("hidden")) {
        try {
          // reload iframe content
          frame.contentWindow ? frame.contentWindow.location.reload() : (frame.src = frame.src);
          showSpinner(true);
        } catch {
          frame.src = frame.src;
          showSpinner(true);
        }
      } else {
        // EDA panel – nothing to refresh (client-side)
      }
    });

    // --- EDA (CSV) logic ---
    const drop = q("edaDrop");
    const fileInput = q("edaFile");
    const meta = q("edaMeta");
    const summary = q("edaSummary");
    const preview = q("edaPreview");
    const btnReport = q("btn-download-report");

    const parseCSV = (file) => new Promise((resolve, reject) => {
      if (!window.Papa) return reject(new Error("PapaParse not loaded"));
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: results => resolve(results),
        error: err => reject(err)
      });
    });

    const makeSummary = (rows) => {
      if (!rows.length) return "<p>No rows found.</p>";
      const cols = Object.keys(rows[0]);
      const counts = rows.length;
      const missing = {};
      cols.forEach(c => missing[c] = rows.filter(r => r[c] === "" || r[c] == null).length);

      let html = `<p><strong>Rows:</strong> ${counts} &nbsp; <strong>Columns:</strong> ${cols.length}</p>`;
      html += `<table><thead><tr><th>Column</th><th>Missing</th></tr></thead><tbody>`;
      cols.forEach(c => {
        html += `<tr><td>${c}</td><td>${missing[c]}</td></tr>`;
      });
      html += `</tbody></table>`;
      return html;
    };

    const makePreview = (rows) => {
      const cols = rows.length ? Object.keys(rows[0]) : [];
      const view = rows.slice(0, 20);
      if (!cols.length) return "<p>No preview.</p>";
      let html = `<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join("")}</tr></thead><tbody>`;
      view.forEach(r => {
        html += `<tr>${cols.map(c=>`<td>${(r[c] ?? "").toString()}</td>`).join("")}</tr>`;
      });
      html += "</tbody></table>";
      return html;
    };

    const handleFile = async (file) => {
      if (!file) return;
      meta.textContent = "Parsing…";
      summary.innerHTML = "";
      preview.innerHTML = "";
      try {
        const { data } = await parseCSV(file);
        meta.textContent = `${file.name} • ${data.length} rows`;
        summary.innerHTML = makeSummary(data);
        preview.innerHTML = makePreview(data);
      } catch (err) {
        console.error(err);
        meta.textContent = "Failed to parse file.";
      }
    };

    drop?.addEventListener("dragover", e => {
      e.preventDefault(); drop.classList.add("drag");
    });
    drop?.addEventListener("dragleave", () => drop.classList.remove("drag"));
    drop?.addEventListener("drop", e => {
      e.preventDefault(); drop.classList.remove("drag");
      const f = e.dataTransfer.files?.[0];
      handleFile(f);
    });
    fileInput?.addEventListener("change", e => handleFile(e.target.files?.[0]));

    btnReport?.addEventListener("click", () => {
      const html = `
<!DOCTYPE html><meta charset="utf-8">
<title>EDA Report</title>
<style>
  body{font-family:Arial,Helvetica,sans-serif;padding:16px}
  table{border-collapse:collapse;width:100%}
  th,td{border:1px solid #ddd;padding:8px;font-size:14px}
  th{background:#f8fafc}
</style>
<h2>Summary</h2>${summary.innerHTML}
<h2 style="margin-top:16px">Preview (first 20 rows)</h2>${preview.innerHTML}`;
      const blob = new Blob([html], {type:"text/html"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "eda-report.html";
      a.click();
      URL.revokeObjectURL(url);
    });

    // Optional: auto-select a default view if you want
    // const embeds = window.ADMIN_EMBEDS || {};
    // if (embeds.DR) btnDR.click();
  });
})();
