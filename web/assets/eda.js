(async function () {
  const fileInput = document.getElementById('csvFile');
  const runBtn = document.getElementById('runEdaBtn');
  const status = document.getElementById('status');
  const report = document.getElementById('report');

  const el = (tag, html='') => {
    const n = document.createElement(tag);
    n.innerHTML = html;
    return n;
  };

  const renderTable = (rows, headers) => {
    if (!rows || rows.length === 0) return el('div', '<em>No data</em>');
    const table = el('table');
    const thead = el('thead');
    const trh = el('tr');
    (headers || Object.keys(rows[0])).forEach(h => trh.appendChild(el('th', h)));
    thead.appendChild(trh);
    table.appendChild(thead);
    const tb = el('tbody');
    rows.forEach(r => {
      const tr = el('tr');
      (headers || Object.keys(r)).forEach(k => tr.appendChild(el('td', String(r[k] ?? ''))));
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    return table;
  };

  const setHTML = (id, html) => {
    const node = document.getElementById(id);
    node.innerHTML = '';
    node.appendChild(typeof html === 'string' ? el('div', html) : html);
  };

  runBtn.addEventListener('click', async () => {
    status.textContent = '';
    report.style.display = 'none';

    const f = fileInput.files && fileInput.files[0];
    if (!f) { status.textContent = 'Please choose a CSV file first.'; return; }
    if (!f.name.toLowerCase().endsWith('.csv')) {
      status.textContent = 'Only .csv files are supported.'; return;
    }

    const form = new FormData();
    form.append('file', f, f.name);

    try {
      status.textContent = 'Uploading and analyzing...';
      const res = await fetch('/api/eda', { method: 'POST', body: form });
      if (!res.ok) { throw new Error(`Server responded ${res.status}`); }
      const json = await res.json();

      // Overview
      setHTML('overview', renderTable([
        { Metric: 'Rows', Value: json.shape?.rows ?? '' },
        { Metric: 'Columns', Value: json.shape?.cols ?? '' },
        { Metric: 'Memory (approx)', Value: json.memory ?? '' },
      ]));

      // Columns
      setHTML('columns', renderTable(json.columns));

      // Missing
      setHTML('missing', renderTable(json.missing));

      // Numeric
      setHTML('numeric', renderTable(json.numeric));

      // Categorical
      // Flatten: [{column, category, count, pct}]
      setHTML('categorical', renderTable(json.categorical));

      // Correlations
      setHTML('corr', renderTable(json.correlation));

      report.style.display = 'block';
      status.textContent = 'Done.';
    } catch (err) {
      console.error(err);
      status.textContent = `Error: ${err.message}`;
    }
  });
})();
