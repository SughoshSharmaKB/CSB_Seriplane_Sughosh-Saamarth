let pipelineExecuted = false;
let requestToken = 0;
let evennessData = null;
let neatnessData = null;
let currentView = null;

// ── Generate report live-editing state ────────────────────────
let generateState = { evennessResults: [], neatnessResults: null, data: null };
let editState     = { cell: null, panel: null, field: null, originalValue: null, newValue: null };

const HIDE_KEYWORDS = ["time", "date", "path", "output_image_path"];

// ================= EXECUTE PIPELINE =================
function executePipeline() {
    // 🔥 Remove generate UI and print button if present
    const genUI = document.getElementById("generateUI");
    if (genUI) genUI.remove();

    const printBtn = document.getElementById("generatePrintBtn");
    if (printBtn) printBtn.remove();

    setButtons({
        evenness: false,
        neatness: false,
        execute: false,
        home: false,
        print: false,
        generate: false
    });

    showStatus("Processing...");

    fetch("/execute", { method: "POST" })
        .then(res => res.json())
        .then(() => {
            pipelineExecuted = true;
            showStatus("Execution completed.");

            Promise.all([
                new Promise(resolve =>
                    waitForCSV("evenness", csv => resolve({ type: "evenness", csv }))
                ),
                new Promise(resolve =>
                    waitForCSV("neatness", csv => resolve({ type: "neatness", csv }))
                )
            ])
            .then(results => {
                results.forEach(r => {
                    if (r.type === "evenness") evennessData = parseCSV(r.csv);
                    if (r.type === "neatness") neatnessData = parseCSV(r.csv);
                });

                currentView = "evenness";
                renderFromMemory();

                setButtons({
                    evenness: true,
                    neatness: true,
                    execute: false,
                    home: true,
                    print: true,
                    generate: true
                });
            });
        })
        .catch(err => {
            console.error(err);
            showStatus("Execution failed");
            setButtons({
                evenness: false,
                neatness: false,
                execute: true,
                home: false,
                print: false,
                generate: true
            });
        });
}


function waitForCSV(type, callback) {
    fetch(`/csv/${type}`)
        .then(res => {
            if (res.status === 204) {
                setTimeout(() => waitForCSV(type, callback), 1000);
                return null;
            }
            return res.text();
        })
        .then(text => {
            if (!text) return;
            callback(text);
        });
}


function parseCSV(text) {
    return text.trim().split("\n").map(row => row.split(","));
}


function goHome() {
    saveCurrentEdits();

    // 🔥 Clean up generate UI
    const genUI = document.getElementById("generateUI");
    if (genUI) genUI.remove();

    const printBtn = document.getElementById("generatePrintBtn");
    if (printBtn) printBtn.remove();

    fetch("/home", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            evenness: evennessData.map(r => r.join(",")).join("\n"),
            neatness: neatnessData.map(r => r.join(",")).join("\n")
        })
    })
    .then(() => {
        evennessData = null;
        neatnessData = null;
        currentView = null;

        clearTable();
        showStatus("");

        setButtons({
            evenness: false,
            neatness: false,
            execute: true,
            home: false,
            print: false,
            generate: true
        });
    });
}


function printTable() {
    if (!pipelineExecuted) return;
    window.print();
}


// ================= SERIPLANE WORKSHEET PRINT =================
function printWorksheet(reportData) {
    const evResults  = computeEvenness(reportData.evenness, reportData.neatness);
    const neatResult = computeNeatness(reportData.neatness);

    // Map panel number -> row data
    const panelMap = {};
    evResults.forEach(r => { panelMap[r.panel] = r; });

    // 100 rows always
    const rows = [];
    for (let i = 1; i <= 100; i++) {
        const r = panelMap["panel" + i];
        rows.push({
            no:   i,
            ev1:  r ? r.v1.toFixed(0)         : "",
            ev2:  r ? r.v2.toFixed(0)         : "",
            ev3:  r ? r.v3.toFixed(0)         : "",
            neat: r ? r.neatAvg               : "",
            sm:   r ? r.supermajor.toFixed(0) : "",
            maj:  r ? r.major.toFixed(0)      : "",
            min:  r ? r.minor.toFixed(0)      : ""
        });
    }

    function buildPanelHTML(start, end) {
        let html = `<table class="pt"><thead><tr>
            <th>No.</th><th>EV1</th><th>EV2</th><th>EV3</th>
            <th>Neat</th><th>SM</th><th>M</th><th>Min</th>
        </tr></thead><tbody>`;
        for (let i = start; i <= end; i++) {
            const r = rows[i-1];
            html += `<tr><td class="no">${r.no}</td><td>${r.ev1}</td><td>${r.ev2}</td>
                <td>${r.ev3}</td><td>${r.neat}</td><td>${r.sm}</td>
                <td>${r.maj}</td><td>${r.min}</td></tr>`;
        }
        return html + "</tbody></table>";
    }

    const totalEV1 = evResults.reduce((s,r) => s+r.v1, 0);
    const totalEV2 = evResults.reduce((s,r) => s+r.v2, 0);
    const totalEV3 = evResults.reduce((s,r) => s+r.v3, 0);

    // Grade breakdown
    const allNeat = [];
    reportData.neatness.forEach(entry => {
        const headers = entry.rows[0].split(",").map(h => h.trim());
        const ni = headers.indexOf("Neatness_Grade");
        for (let i = 1; i < entry.rows.length; i++) {
            const v = parseFloat(entry.rows[i].split(",")[ni]) || 0;
            if (v > 0) allNeat.push(v);
        }
    });
    const gradeCounts = {};
    allNeat.forEach(v => { gradeCounts[v] = (gradeCounts[v]||0)+1; });
    const gradeBreakdown = [100,95,90,85,80,75,70]
        .filter(g => gradeCounts[g])
        .map(g => `${gradeCounts[g]}x${g}`)
        .join("+");

    const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Seriplane Work Sheet</title>
<style>
@page { size:A4 landscape; margin:6mm; }
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;}
body{font-family:Arial,sans-serif;font-size:8px;display:flex;flex-direction:column;height:100%;}

/* HEADER */
.hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;flex-shrink:0;}
.hdr-center{flex:1;text-align:center;}
.hdr-center h2{font-size:12px;font-weight:bold;letter-spacing:1px;}
.hdr-center p{font-size:9px;}
.hdr-right{font-size:9px;white-space:nowrap;text-align:right;}
.hdr-right div{margin-bottom:2px;}

/* BODY: panels left + summary right — fills remaining height */
.body-wrap{display:flex;gap:4px;align-items:stretch;flex:1;min-height:0;}

/* 4 panel columns */
.panels{display:grid;grid-template-columns:repeat(4,1fr);gap:3px;flex:1;align-items:start;}
.panel-block{border:1px solid #000;}
.panel-title{background:#eee;text-align:center;font-weight:bold;font-size:8px;border-bottom:1px solid #000;padding:1px;}
.pt{border-collapse:collapse;width:100%;font-size:7px;}
.pt th,.pt td{border:1px solid #000;padding:0 2px;height:15px;text-align:center;white-space:nowrap;}
.pt th{font-weight:bold;background:#f5f5f5;height:13px;}
.pt td.no{text-align:left;}

/* SUMMARY — full height flex column */
.summary-wrap{
    width:145px;flex-shrink:0;
    display:flex;flex-direction:column;
    border:1px solid #000;
}
.summary-inner{flex:1;display:flex;flex-direction:column;}

/* Test info block at top */
.sum-top{
    padding:5px 6px;
    border-bottom:1px solid #000;
    font-size:8.5px;
    flex-shrink:0;
}
.sum-top .field-row{
    display:flex;justify-content:space-between;
    margin-bottom:4px;
    padding-bottom:2px;
    border-bottom:1px dotted #aaa;
}
.sum-top .field-label{font-weight:bold;}

/* Data rows in middle — grows to fill */
.sum-data{flex:1;}
.stbl{border-collapse:collapse;width:100%;}
.stbl tr th{background:#eee;border:1px solid #000;padding:2px 4px;text-align:left;font-size:8px;}
.stbl tr td{border:1px solid #000;padding:2px 4px;font-size:8px;}
.stbl td.val{text-align:right;font-weight:bold;}
.stbl .section-hdr td{background:#1a3a6b;color:#fff;text-align:center;font-weight:bold;font-size:8px;padding:2px;}

/* Signature block at bottom */
.sum-bot{
    padding:5px 6px;
    border-top:1px solid #000;
    font-size:8.5px;
    flex-shrink:0;
}
.sig-line{
    border-bottom:1px solid #000;
    margin-top:14px;
    margin-bottom:2px;
}
.sig-label{font-size:7.5px;color:#555;}

@media print{
    body{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
}
</style></head><body>

<!-- HEADER -->
<div class="hdr">
  <div style="width:90px;"></div>
  <div class="hdr-center">
    <h2>SERIPLANE WORK SHEET</h2>
    <p>Silk Testing Laboratory, Bangalore</p>
  </div>
  <div class="hdr-right">
    <div>CSB — Central Silk Board</div>
  </div>
</div>

<!-- BODY -->
<div class="body-wrap">

  <!-- 4 panel columns -->
  <div class="panels">
    <div class="panel-block"><div class="panel-title">1 – 25</div>${buildPanelHTML(1,25)}</div>
    <div class="panel-block"><div class="panel-title">26 – 50</div>${buildPanelHTML(26,50)}</div>
    <div class="panel-block"><div class="panel-title">51 – 75</div>${buildPanelHTML(51,75)}</div>
    <div class="panel-block"><div class="panel-title">76 – 100</div>${buildPanelHTML(76,100)}</div>
  </div>

  <!-- SUMMARY column — full height -->
  <div class="summary-wrap">
    <div class="summary-inner">

      <!-- TOP: Test info -->
      <div class="sum-top">
        <div class="field-row">
          <span class="field-label">Test No.</span>
          <span style="border-bottom:1px solid #000;width:70px;">&nbsp;</span>
        </div>
        <div class="field-row">
          <span class="field-label">Date</span>
          <span style="border-bottom:1px solid #000;width:80px;">&nbsp;</span>
        </div>
        <div class="field-row">
          <span class="field-label">Lot No.</span>
          <span style="border-bottom:1px solid #000;width:72px;">&nbsp;</span>
        </div>
      </div>

      <!-- MIDDLE: Data table -->
      <div class="sum-data">
        <table class="stbl">
          <tr class="section-hdr"><td colspan="2">EVENNESS</td></tr>
          <tr><th>Total EV1</th><td class="val">${totalEV1.toFixed(0)}</td></tr>
          <tr><th>Total EV2</th><td class="val">${totalEV2.toFixed(0)}</td></tr>
          <tr><th>Total EV3</th><td class="val">${totalEV3.toFixed(0)}</td></tr>
          <tr><th>Total EV</th><td class="val">${(totalEV1+totalEV2+totalEV3).toFixed(0)}</td></tr>
          <tr class="section-hdr"><td colspan="2">CLEANLINESS</td></tr>
          <tr><th>Super Major</th><td class="val">${neatResult.supermajorTotal.toFixed(0)}</td></tr>
          <tr><th>Major</th><td class="val">${neatResult.majorTotal.toFixed(0)}</td></tr>
          <tr><th>Minor</th><td class="val">${neatResult.minorTotal.toFixed(0)}</td></tr>
          <tr><th>Cleanness %</th><td class="val">${neatResult.cleanlinessPercent.toFixed(2)}%</td></tr>
          <tr class="section-hdr"><td colspan="2">NEATNESS</td></tr>
          <tr><th colspan="2" style="font-size:6.5px;font-weight:normal;word-break:break-word;">${gradeBreakdown}</th></tr>
          <tr><th>Neatness %</th><td class="val">${neatResult.neatnessPercent.toFixed(2)}%</td></tr>
          <tr><th>Low Neatness %</th><td class="val">${neatResult.lowNeatnessPercent.toFixed(2)}%</td></tr>
          <tr><th>Low Neat (n)</th><td class="val">${neatResult.bottomCount}/${neatResult.totalEntries}</td></tr>
        </table>
      </div>

      <!-- BOTTOM: Signature -->
      <div class="sum-bot">
        <div style="font-weight:bold;margin-bottom:6px;">Inspected By</div>
        <div class="sig-line"></div>
        <div class="sig-label">Signature</div>
        <div class="sig-line" style="margin-top:18px;"></div>
        <div class="sig-label">Name &amp; Designation</div>
      </div>

    </div>
  </div>

</div>

<script>window.onload=function(){window.print();}<\/script>
</body></html>`;

    const win = window.open("","_blank");
    win.document.write(html);
    win.document.close();
}


function clearTable() {
    const thead = document.querySelector("#csvTable thead");
    const tbody = document.querySelector("#csvTable tbody");
    thead.innerHTML = "<tr><th>Result</th></tr>";
    tbody.innerHTML = "";
}


// ================= GENERATE =================

let totalPanelCount = 0;

function generateLogs() {
    // First fetch total panel count to show range UI
    fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "all" })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) { 
            showStatus(data.error); 
            return; 
        }
        
        totalPanelCount = data.panels.length;

        if (totalPanelCount === 0) {
            showStatus("No panels found in logs.");
            return;
        }

        showGenerateUI(totalPanelCount);
    })
    .catch(err => {
        console.error(err);
        showStatus("Failed to load logs: " + err.message);
    });
}


function showGenerateUI(total) {
    // Remove existing UI if any
    const existing = document.getElementById("generateUI");
    if (existing) existing.remove();

    const container = document.createElement("div");
    container.id = "generateUI";
    container.style.cssText = "margin:10px 0; padding:10px; border:1px solid #ccc; background:#f9f9f9; display:flex; gap:10px; align-items:center; flex-wrap:wrap;";

    container.innerHTML = `
        <label><input type="radio" name="genMode" value="all" checked> All Panels (1 - ${total})</label>
        <label><input type="radio" name="genMode" value="range"> Range:</label>
        <label>From Panel: <input type="number" id="genFrom" min="1" max="${total}" value="1" style="width:60px"></label>
        <label>To Panel: <input type="number" id="genTo" min="1" max="${total}" value="${total}" style="width:60px"></label>
        <button onclick="fetchAndRenderGenerate()" style="padding:5px 12px; cursor:pointer;">Generate Report</button>
    `;

    document.querySelector(".content").prepend(container);
}


function fetchAndRenderGenerate() {
    const mode = document.querySelector('input[name="genMode"]:checked').value;
    const from = parseInt(document.getElementById("genFrom").value);
    const to   = parseInt(document.getElementById("genTo").value);

    if (mode === "range" && from > to) {
        showStatus("Invalid range: From must be <= To.");
        return;
    }

    // 🔥 Hide the panel selector UI after Generate Report is clicked
    const ui = document.getElementById("generateUI");
    if (ui) ui.remove();

    fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, from, to })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) { 
            showStatus(data.error); 
            return; 
        }
        renderGenerateReport(data);
    })
    .catch(err => {
        showStatus("Failed: " + err.message);
    });
}


function computeEvenness(evennessPanels, neatnessPanels) {
    const neatByPanel = {};
    if (neatnessPanels) {
        neatnessPanels.forEach(entry => {
            const headers = entry.rows[0].split(",").map(h => h.trim());
            const minorI      = headers.indexOf("Cleanliness_minor");
            const majorI      = headers.indexOf("Cleanliness_major");
            const supermajorI = headers.indexOf("Cleanliness_supermajor");
            const neatI       = headers.indexOf("Neatness_Grade");
            let minor = 0, major = 0, supermajor = 0, neatSum = 0, neatCount = 0;
            for (let i = 1; i < entry.rows.length; i++) {
                const cols = entry.rows[i].split(",");
                minor      += parseFloat(cols[minorI])      || 0;
                major      += parseFloat(cols[majorI])      || 0;
                supermajor += parseFloat(cols[supermajorI]) || 0;
                const nv    = parseFloat(cols[neatI])       || 0;
                if (nv > 0) { neatSum += nv; neatCount++; }
            }
            neatByPanel[entry.panel] = {
                minor, major, supermajor,
                neatAvg: neatCount > 0 ? (neatSum / neatCount).toFixed(2) : "—"
            };
        });
    }
    return evennessPanels.map(entry => {
        const headers = entry.rows[0].split(",").map(h => h.trim());
        const v1i = headers.indexOf("v1_Count");
        const v2i = headers.indexOf("v2_Count");
        const v3i = headers.indexOf("v3_Count");
        let v1 = 0, v2 = 0, v3 = 0;
        for (let i = 1; i < entry.rows.length; i++) {
            const cols = entry.rows[i].split(",");
            v1 += parseFloat(cols[v1i]) || 0;
            v2 += parseFloat(cols[v2i]) || 0;
            v3 += parseFloat(cols[v3i]) || 0;
        }
        const neat = neatByPanel[entry.panel] || { minor: 0, major: 0, supermajor: 0, neatAvg: "—" };
        return { panel: entry.panel, v1, v2, v3, minor: neat.minor, major: neat.major, supermajor: neat.supermajor, neatAvg: neat.neatAvg };
    });
}


function computeNeatness(panels) {
    // Collect all individual neatness values across all panels
    let allNeatnessValues = [];
    let supermajorTotal = 0, majorTotal = 0, minorTotal = 0;

    panels.forEach(entry => {
        const headers = entry.rows[0].split(",").map(h => h.trim());
        const minorI  = headers.indexOf("Cleanliness_minor");
        const supermajorI = headers.indexOf("Cleanliness_supermajor");
        const majorI  = headers.indexOf("Cleanliness_major");
        const neatI   = headers.indexOf("Neatness_Grade");

        for (let i = 1; i < entry.rows.length; i++) {
            const cols = entry.rows[i].split(",");
            supermajorTotal += parseFloat(cols[supermajorI]) || 0;
            majorTotal      += parseFloat(cols[majorI])      || 0;
            minorTotal      += parseFloat(cols[minorI])      || 0;

            const nv = parseFloat(cols[neatI]) || 0;
            allNeatnessValues.push(nv);
        }
    });

    // Cleanliness
    const error = supermajorTotal * 1.0 + majorTotal * 0.4 + minorTotal * 0.1;
    const cleanlinessPercent = 100 - error;

    // Overall neatness: weighted average = sum(count * grade) / total_count
    // Count occurrences of each grade value
    const gradeCounts = {};
    allNeatnessValues.forEach(val => {
        gradeCounts[val] = (gradeCounts[val] || 0) + 1;
    });

    let weightedSum = 0;
    let totalCount = 0;
    for (const [grade, count] of Object.entries(gradeCounts)) {
        weightedSum += parseFloat(grade) * count;
        totalCount += count;
    }

    const neatnessPercent = totalCount > 0 ? weightedSum / totalCount : 0;

    // Low neatness: bottom 20% of individual entries in descending order
    // Sort all values descending: [90, 90, 90, 90, 90, 90, 80, 80, ..., 70, 70, 70]
    const sortedDesc = [...allNeatnessValues].sort((a, b) => b - a);
    
    // Take bottom 20% of entries
    const bottomCount = Math.max(1, Math.ceil(sortedDesc.length * 0.2));
    const bottomValues = sortedDesc.slice(-bottomCount);  // last N elements (lowest values)

    const lowNeatnessPercent = bottomValues.length > 0
        ? bottomValues.reduce((sum, v) => sum + v, 0) / bottomValues.length
        : 0;

    // For display: show which panels contributed to bottom 20%
    let bottomPanelNames = [];
    panels.forEach(entry => {
        const headers = entry.rows[0].split(",").map(h => h.trim());
        const neatI = headers.indexOf("Neatness_Grade");
        for (let i = 1; i < entry.rows.length; i++) {
            const cols = entry.rows[i].split(",");
            const nv = parseFloat(cols[neatI]) || 0;
            if (bottomValues.includes(nv) && !bottomPanelNames.includes(entry.panel)) {
                bottomPanelNames.push(entry.panel);
                break;
            }
        }
    });

    return {
        supermajorTotal, majorTotal, minorTotal,
        cleanlinessPercent,
        neatnessPercent,
        lowNeatnessPercent,
        bottomPanels: bottomPanelNames,
        bottomCount: bottomCount,
        totalEntries: allNeatnessValues.length
    };
}


function renderGenerateReport(data) {
    const thead = document.querySelector("#csvTable thead");
    const tbody = document.querySelector("#csvTable tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    if (!data.evenness || data.evenness.length === 0) { showStatus("No evenness data found for selected panels."); return; }
    if (!data.neatness || data.neatness.length === 0)  { showStatus("No neatness data found for selected panels.");  return; }

    const evennessResults = computeEvenness(data.evenness, data.neatness);
    const neatnessResults = computeNeatness(data.neatness);

    // Store in module-level state so live edits can recalculate
    generateState.evennessResults = evennessResults;
    generateState.neatnessResults = neatnessResults;
    generateState.data            = data;

    const COLS        = 9;
    const FIELD_NAMES = ["Panel","EV1","EV2","EV3","EV Total","Super Major","Major","Minor","Neatness Avg"];
    const EDITABLE    = new Set(["EV1","EV2","EV3","Super Major","Major","Minor"]);

    // ── Title row ──────────────────────────────────────────────
    const titleRow = document.createElement("tr");
    const titleTd  = document.createElement("td");
    titleTd.colSpan = COLS;
    titleTd.textContent = "EVENNESS CLEANNESS NEATNESS VARIATION TABLE";
    titleTd.style.cssText = "font-weight:bold;background:#1a3a6b;color:#fff;padding:8px;text-align:center;font-size:13px;letter-spacing:1px;";
    titleRow.appendChild(titleTd);
    tbody.appendChild(titleRow);

    // ── Header row ─────────────────────────────────────────────
    const evHead = document.createElement("tr");
    FIELD_NAMES.forEach(h => {
        const th = document.createElement("th");
        th.textContent = h;
        th.style.cssText = "background:#eef4ff;text-align:center;padding:4px 6px;";
        if (EDITABLE.has(h)) {
            th.title = "Click any cell in this column to edit";
            th.style.borderBottom = "2px solid #1a3a6b";
        }
        evHead.appendChild(th);
    });
    thead.appendChild(evHead);

    // ── Data rows ──────────────────────────────────────────────
    let totalV1=0, totalV2=0, totalV3=0, totalSM=0, totalMaj=0, totalMin=0;

    evennessResults.forEach(row => {
        const tr = document.createElement("tr");
        totalV1 += row.v1; totalV2 += row.v2; totalV3 += row.v3;
        totalSM += row.supermajor; totalMaj += row.major; totalMin += row.minor;

        const values = [
            row.panel,
            row.v1,
            row.v2,
            row.v3,
            row.v1 + row.v2 + row.v3,
            row.supermajor,
            row.major,
            row.minor,
            row.neatAvg
        ];

        values.forEach((val, colIdx) => {
            const td        = document.createElement("td");
            const fieldName = FIELD_NAMES[colIdx];
            const displayVal = (typeof val === "number") ? val.toFixed(0) : val;
            td.textContent   = displayVal;
            td.style.textAlign = "center";

            if (colIdx === 0) {
                // Panel name — clickable for image preview
                td.classList.add("panel-link");
                td.title = "Click to view panel images";
                td.addEventListener("click", () => openPanelImages(row.panel));

            } else if (EDITABLE.has(fieldName)) {
                // Editable numeric cell
                makeEditableCell(td, row.panel, fieldName, parseFloat(displayVal) || 0);

            } else if (fieldName === "EV Total") {
                // Auto-calculated from EV1+EV2+EV3; not directly editable
                td.dataset.panel = row.panel;
                td.dataset.field = "EV Total";
                td.style.background = "#f8f8f8";
                td.title = "Auto-calculated: EV1 + EV2 + EV3";
            }

            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });

    // ── Total row ──────────────────────────────────────────────
    const evTotalRow = document.createElement("tr");
    evTotalRow.style.fontWeight = "bold";
    const totalVals = ["Total",totalV1,totalV2,totalV3,totalV1+totalV2+totalV3,totalSM,totalMaj,totalMin,"—"];
    const totalIDs  = [null,"genTotalV1","genTotalV2","genTotalV3","genTotalEV","genTotalSM","genTotalMaj","genTotalMin",null];
    totalVals.forEach((val, i) => {
        const td = document.createElement("td");
        td.textContent = (typeof val === "number") ? val.toFixed(0) : val;
        td.style.cssText = "background:#dce8ff;text-align:center;";
        if (totalIDs[i]) td.id = totalIDs[i];
        evTotalRow.appendChild(td);
    });
    tbody.appendChild(evTotalRow);

    // ── Gap ────────────────────────────────────────────────────
    const gap = document.createElement("tr");
    const gapTd = document.createElement("td");
    gapTd.colSpan = COLS; gapTd.style.padding = "10px";
    gap.appendChild(gapTd); tbody.appendChild(gap);

    // ── Summary header ─────────────────────────────────────────
    const neatLabelRow = document.createElement("tr");
    const neatLabelTd  = document.createElement("td");
    neatLabelTd.colSpan = COLS;
    neatLabelTd.textContent = "EVENNESS CLEANNESS NEATNESS SUMMARY";
    neatLabelTd.style.cssText = "font-weight:bold;background:#d4f4dd;padding:6px;text-align:center;";
    neatLabelRow.appendChild(neatLabelTd); tbody.appendChild(neatLabelRow);

    // [label, initialValue, elementId-for-live-update]
    const summaryDefs = [
        ["Total EV1",            totalV1.toFixed(0),                              "sumEV1"],
        ["Total EV2",            totalV2.toFixed(0),                              "sumEV2"],
        ["Total EV3",            totalV3.toFixed(0),                              "sumEV3"],
        ["Total EV",             (totalV1+totalV2+totalV3).toFixed(0),            "sumEV" ],
        ["Super Major Defects",  neatnessResults.supermajorTotal.toFixed(0),      "sumSM" ],
        ["Major Defects",        neatnessResults.majorTotal.toFixed(0),           "sumMaj"],
        ["Minor Defects",        neatnessResults.minorTotal.toFixed(0),           "sumMin"],
        ["Cleanliness %",        neatnessResults.cleanlinessPercent.toFixed(2)+" %", "sumClean"],
        ["Neatness %",           neatnessResults.neatnessPercent.toFixed(2)+" %",  null],
        [`Low Neatness % (bottom ${neatnessResults.bottomCount} of ${neatnessResults.totalEntries} entries)`,
                                 neatnessResults.lowNeatnessPercent.toFixed(2)+" %", null]
    ];

    summaryDefs.forEach(([label, value, id]) => {
        const tr = document.createElement("tr");
        const tdLabel = document.createElement("td");
        tdLabel.textContent = label; tdLabel.colSpan = COLS-1; tdLabel.style.fontWeight = "bold";
        const tdVal = document.createElement("td");
        tdVal.textContent = value;
        tdVal.style.cssText = "font-weight:bold;color:#1a5c2a;text-align:center;";
        if (id) tdVal.id = id;
        tr.appendChild(tdLabel); tr.appendChild(tdVal); tbody.appendChild(tr);
    });

    // ── Print button ───────────────────────────────────────────
    const existing = document.getElementById("generatePrintBtn");
    if (existing) existing.remove();
    const printBtn = document.createElement("button");
    printBtn.id = "generatePrintBtn";
    printBtn.textContent = "🖨 Print Worksheet";
    printBtn.style.cssText = "margin:10px 0;padding:6px 14px;cursor:pointer;font-weight:bold;";
    printBtn.onclick = () => printWorksheet(data);
    document.querySelector(".content").prepend(printBtn);

    showStatus("Report generated.");
}


// ================= GENERATE EDIT HELPERS =================

function initModals() {
    // ── Edit confirmation modal ─────────────────────────────
    if (!document.getElementById("editConfirmModal")) {
        const m = document.createElement("div");
        m.id = "editConfirmModal";
        m.innerHTML = `
            <div>
                <div style="background:#000080;color:#fff;padding:4px 10px;font-weight:bold;display:flex;justify-content:space-between;align-items:center;">
                    <span>&#128190; Save Change</span>
                    <button id="editConfirmClose" style="background:none;border:1px solid #aaa;color:#fff;cursor:pointer;padding:1px 7px;font-size:11px;font-family:inherit;">&#10005;</button>
                </div>
                <div style="padding:16px 20px;">
                    <div id="editConfirmMsg" style="margin-bottom:18px;font-size:13px;line-height:1.6;"></div>
                    <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
                        <button id="editConfirmCSV"    style="padding:5px 14px;border:2px outset #fff;background:#D3D3D3;cursor:pointer;font-family:inherit;font-size:12px;font-weight:bold;">&#128190; Save to CSV</button>
                        <button id="editConfirmWindow" style="padding:5px 14px;border:2px outset #fff;background:#D3D3D3;cursor:pointer;font-family:inherit;font-size:12px;font-weight:bold;">&#128421; Window Only</button>
                        <button id="editConfirmCancel" style="padding:5px 14px;border:2px outset #fff;background:#D3D3D3;cursor:pointer;font-family:inherit;font-size:12px;">&#10005; Cancel</button>
                    </div>
                </div>
            </div>`;
        m.addEventListener("click", e => { if (e.target === m) cancelEdit(); });
        document.body.appendChild(m);
        document.getElementById("editConfirmClose").onclick  = cancelEdit;
        document.getElementById("editConfirmCancel").onclick = cancelEdit;
    }

    // ── Image preview modal ─────────────────────────────────
    if (!document.getElementById("imageModal")) {
        const m = document.createElement("div");
        m.id = "imageModal";
        m.innerHTML = `
            <div>
                <div style="background:#000080;color:#fff;padding:4px 10px;font-weight:bold;display:flex;justify-content:space-between;align-items:center;">
                    <span id="imageModalTitle">Panel Images</span>
                    <button onclick="closeImageModal()" style="background:none;border:1px solid #aaa;color:#fff;cursor:pointer;padding:1px 7px;font-size:11px;font-family:inherit;">&#10005; Close</button>
                </div>
                <div style="padding:10px;">
                    <div id="imageModalContent" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;max-height:78vh;overflow:auto;padding:4px;"></div>
                </div>
            </div>`;
        m.addEventListener("click", e => { if (e.target === m) closeImageModal(); });
        document.body.appendChild(m);
    }
}


function makeEditableCell(td, panel, fieldName, numericValue) {
    td.contentEditable = "true";
    td.spellcheck      = false;
    td.classList.add("editable-cell");
    td.dataset.panel         = panel;
    td.dataset.field         = fieldName;
    td.dataset.originalValue = String(numericValue);

    td.addEventListener("focus", () => {
        td.dataset.originalValue = td.textContent.trim();
    });

    td.addEventListener("keydown", e => {
        if (e.key === "Enter")  { e.preventDefault(); td.blur(); }
        if (e.key === "Escape") { td.textContent = td.dataset.originalValue; td.blur(); }
    });

    td.addEventListener("blur", () => {
        const orig   = parseFloat(td.dataset.originalValue) || 0;
        const newVal = parseFloat(td.textContent.trim());
        if (isNaN(newVal)) { td.textContent = String(Math.round(orig)); return; }
        if (Math.abs(newVal - orig) < 0.001) return;   // no real change

        editState = {
            cell: td, panel: td.dataset.panel, field: td.dataset.field,
            originalValue: orig, newValue: newVal
        };
        showEditConfirmModal(td.dataset.panel, td.dataset.field, orig, newVal);
    });
}


function showEditConfirmModal(panel, field, oldVal, newVal) {
    const modal = document.getElementById("editConfirmModal");
    document.getElementById("editConfirmMsg").innerHTML =
        `<strong>${panel}</strong> &mdash; <strong>${field}</strong><br>` +
        `Old: <span style="color:#a00;">${Math.round(oldVal)}</span> &nbsp;&rarr;&nbsp; ` +
        `New: <span style="color:#060;font-weight:bold;">${Math.round(newVal)}</span><br><br>` +
        `Where should this change be applied?`;
    modal.style.display = "flex";
    document.getElementById("editConfirmCSV").onclick    = () => applyEdit(true);
    document.getElementById("editConfirmWindow").onclick = () => applyEdit(false);
}


function cancelEdit() {
    if (editState.cell) {
        editState.cell.textContent           = String(Math.round(editState.originalValue));
        editState.cell.dataset.originalValue = String(editState.originalValue);
    }
    document.getElementById("editConfirmModal").style.display = "none";
    editState = { cell: null, panel: null, field: null, originalValue: null, newValue: null };
}


function applyEdit(saveToCSV) {
    const { cell, panel, field, originalValue, newValue } = editState;
    document.getElementById("editConfirmModal").style.display = "none";

    // Confirm the cell display
    cell.textContent           = Math.round(newValue).toFixed(0);
    cell.dataset.originalValue = String(newValue);

    // Update generateState so recalculation is correct
    const row = generateState.evennessResults.find(r => r.panel === panel);
    if (row) {
        if      (field === "EV1")        row.v1        = newValue;
        else if (field === "EV2")        row.v2        = newValue;
        else if (field === "EV3")        row.v3        = newValue;
        else if (field === "Super Major") row.supermajor = newValue;
        else if (field === "Major")      row.major     = newValue;
        else if (field === "Minor")      row.minor     = newValue;

        // Auto-update EV Total cell for this row
        const evTotalCell = document.querySelector(`[data-panel="${panel}"][data-field="EV Total"]`);
        if (evTotalCell) evTotalCell.textContent = (row.v1 + row.v2 + row.v3).toFixed(0);
    }

    // Refresh the Total row and Summary section
    updateTotalsAndSummary();

    if (saveToCSV) {
        fetch("/update-panel-csv", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ panel, field, value: newValue, oldValue: originalValue })
        })
        .then(res => res.json())
        .then(resp => {
            if (resp.error) showStatus("\u274C CSV update failed: " + resp.error);
            else            showStatus(`\u2705 ${panel} \u2014 ${field} saved to CSV`);
        })
        .catch(err => showStatus("\u274C CSV update error: " + err.message));
    } else {
        showStatus(`\u2705 ${panel} \u2014 ${field} updated (window only)`);
    }

    editState = { cell: null, panel: null, field: null, originalValue: null, newValue: null };
}


function updateTotalsAndSummary() {
    const results = generateState.evennessResults;
    let tV1=0, tV2=0, tV3=0, tSM=0, tMaj=0, tMin=0;
    results.forEach(r => {
        tV1 += r.v1; tV2 += r.v2; tV3 += r.v3;
        tSM += r.supermajor; tMaj += r.major; tMin += r.minor;
    });

    const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = (typeof val === "number") ? val.toFixed(0) : val;
    };

    // Totals row
    set("genTotalV1",  tV1);
    set("genTotalV2",  tV2);
    set("genTotalV3",  tV3);
    set("genTotalEV",  tV1 + tV2 + tV3);
    set("genTotalSM",  tSM);
    set("genTotalMaj", tMaj);
    set("genTotalMin", tMin);

    // Summary section
    set("sumEV1",  tV1);
    set("sumEV2",  tV2);
    set("sumEV3",  tV3);
    set("sumEV",   tV1 + tV2 + tV3);
    set("sumSM",   tSM);
    set("sumMaj",  tMaj);
    set("sumMin",  tMin);

    const error = tSM * 1.0 + tMaj * 0.4 + tMin * 0.1;
    const cpEl  = document.getElementById("sumClean");
    if (cpEl) cpEl.textContent = (100 - error).toFixed(2) + " %";
}


// ================= PANEL IMAGE POPUP =================

function openPanelImages(panel) {
    initModals();
    const modal   = document.getElementById("imageModal");
    const title   = document.getElementById("imageModalTitle");
    const content = document.getElementById("imageModalContent");

    title.textContent    = `${panel} \u2014 Images`;
    content.innerHTML    = `<div style="padding:20px;text-align:center;color:#555;grid-column:1/-1;">Loading images\u2026</div>`;
    modal.style.display  = "block";

    fetch(`/panel-images/${panel}`)
        .then(res => res.json())
        .then(resp => {
            content.innerHTML = "";
            if (resp.error || !resp.images || resp.images.length === 0) {
                content.innerHTML = `
                    <div style="padding:24px;text-align:center;color:#666;grid-column:1/-1;">
                        <div style="font-size:32px;margin-bottom:8px;">&#128247;</div>
                        <strong>No images available for ${panel}.</strong><br>
                        <span style="font-size:11px;">Images are captured and stored when the pipeline runs.</span>
                    </div>`;
                return;
            }
            resp.images.forEach(img => {
                const card = document.createElement("div");
                card.style.cssText = "border:2px inset #fff;background:#fff;padding:4px;";
                card.innerHTML = `
                    <div style="font-size:10px;color:#000080;padding:2px 4px;background:#eee;border-bottom:1px solid #aaa;margin-bottom:4px;font-weight:bold;">
                        &#128193; ${img.folder} / ${img.filename}
                    </div>
                    <img src="/panel-image/${panel}/${img.folder}/${encodeURIComponent(img.filename)}"
                         style="width:100%;height:auto;display:block;"
                         alt="${img.filename}" loading="lazy">`;
                content.appendChild(card);
            });
        })
        .catch(err => {
            content.innerHTML = `<div style="padding:20px;text-align:center;color:#c00;grid-column:1/-1;">&#9888; Error: ${err.message}</div>`;
        });
}


function closeImageModal() {
    const m = document.getElementById("imageModal");
    if (m) m.style.display = "none";
}



// ================= LOAD CSV =================
function loadCSV(type) {
    saveCurrentEdits();
    currentView = type;
    renderFromMemory();
}

function renderFromMemory() {
    if (currentView === "evenness" && evennessData) renderTable(evennessData);
    if (currentView === "neatness" && neatnessData) renderTable(neatnessData);
}


function saveCurrentEdits() {
    if (!currentView) return;

    const table = document.getElementById("csvTable");
    let updated = [];

    for (let r of table.rows) {
        let row = [];
        for (let c of r.cells) {
            row.push(c.innerText.trim());
        }
        updated.push(row);
    }

    if (currentView === "evenness") evennessData = updated;
    if (currentView === "neatness") neatnessData = updated;
}


// ================= HELPERS =================
function setButtons(state) {
    document.getElementById("btnEvenness").disabled = !state.evenness;
    document.getElementById("btnNeatness").disabled = !state.neatness;
    document.getElementById("btnExecute").disabled = !state.execute;
    document.getElementById("btnHome").disabled = !state.home;
    document.getElementById("btnPrint").disabled = !state.print;
    const genBtn = document.getElementById("btnGenerate");
    if (genBtn) genBtn.disabled = state.generate === false;
}

function shouldHide(header) {
    return HIDE_KEYWORDS.some(k => header.toLowerCase().includes(k));
}

function showStatus(msg) {
    let status = document.getElementById("status");
    if (!status) {
        status = document.createElement("div");
        status.id = "status";
        status.style.padding = "5px";
        status.style.fontWeight = "bold";
        document.querySelector(".content").prepend(status);
    }
    status.textContent = msg;
}

function formatNum(val) {
    if (val === undefined || val === null) return "0";
    const n = Number(val);
    return isNaN(n) ? "0" : (Number.isInteger(n) ? n : n.toFixed(2));
}


// ================= TABLE RENDER =================
function renderZeroTable() {
    const thead = document.querySelector("#csvTable thead");
    thead.innerHTML = "<tr><th>Result</th></tr>";
    showStatus("");
}

function renderTable(data) {
    const thead = document.querySelector("#csvTable thead");
    const tbody = document.querySelector("#csvTable tbody");

    thead.innerHTML = "";
    tbody.innerHTML = "";

    const headers = data[0];
    const visibleCols = headers
        .map((h, i) => ({ h, i }))
        .filter(c => !shouldHide(c.h))
        .map(c => c.i);

    const headerRow = document.createElement("tr");
    visibleCols.forEach(i => {
        const th = document.createElement("th");
        th.textContent = headers[i];
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    for (let r = 1; r < data.length; r++) {
        const tr = document.createElement("tr");
        visibleCols.forEach(i => {
            const td = document.createElement("td");
            td.textContent = data[r][i] || "";
            td.contentEditable = "true";
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
}


function getTableCSV() {
    const table = document.getElementById("csvTable");
    let csv = [];
    for (let row of table.rows) {
        let cols = [];
        for (let cell of row.cells) {
            cols.push(cell.innerText.replace(/,/g, ""));
        }
        csv.push(cols.join(","));
    }
    return csv.join("\n");
}


// ================= INITIAL STATE =================
setButtons({
    evenness: false,
    neatness: false,
    execute: true,
    home: false,
    print: false,
    generate: true
});

clearTable();
renderZeroTable();
initModals();
