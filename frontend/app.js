/**
 * Hindsight Sales Agent Frontend Client
 * Communicates exclusively with the FastAPI backend.
 * Contains zero hardcoded demo data.
 */

const API_BASE = window.location.origin;

let prospectsList = [];
let trajectoryChartInstance = null;
let angleMixChartInstance = null;
let pollInterval = null;

// Initialize on page load
window.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  setInterval(checkHealth, 10000);
  initApp();
});

async function checkHealth() {
  const badge = document.getElementById("connectionBadge");
  const text = document.getElementById("connectionText");
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      badge.className = "status-badge online";
      text.textContent = "Backend connected";
    } else {
      badge.className = "status-badge offline";
      text.textContent = "Backend offline";
    }
  } catch (err) {
    badge.className = "status-badge offline";
    text.textContent = "Backend offline";
  }
}

async function initApp() {
  await loadProspects();
  await loadMetrics();
}

async function loadProspects() {
  try {
    const res = await fetch(`${API_BASE}/api/prospects`);
    if (!res.ok) return;
    prospectsList = await res.json();

    const compareSelect = document.getElementById("compareSelect");
    const draftSelect = document.getElementById("draftProspectSelect");

    compareSelect.innerHTML = "";
    draftSelect.innerHTML = "";

    prospectsList.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.company}) - ${p.role || p.persona_type}`;
      compareSelect.appendChild(opt);

      const dOpt = opt.cloneNode(true);
      draftSelect.appendChild(dOpt);
    });

    if (prospectsList.length > 0) {
      onDraftProspectChange();
      onCompareChange();
    }
  } catch (err) {
    console.error("Failed to load prospects:", err);
  }
}

async function loadMetrics() {
  try {
    const res = await fetch(`${API_BASE}/api/metrics`);
    if (!res.ok) return;
    const data = await res.json();

    const emptyBox = document.getElementById("emptyStateBox");
    const dashboard = document.getElementById("dashboardContainer");

    const batchKeys = Object.keys(data.rate_by_batch || {});

    // If data/log.json is missing or empty -> blue empty state
    if (batchKeys.length === 0) {
      emptyBox.style.display = "block";
      dashboard.style.display = "none";
      return;
    }

    emptyBox.style.display = "none";
    dashboard.style.display = "block";

    // Set KPI card values using textContent
    document.getElementById("kpiFirstRate").textContent = `${data.first_rate.toFixed(1)}%`;
    document.getElementById("kpiLastRate").textContent = `${data.last_rate.toFixed(1)}%`;
    document.getElementById("kpiDeltaPts").textContent = `${data.delta_pts >= 0 ? "+" : ""}${data.delta_pts.toFixed(1)} pts`;
    document.getElementById("kpiDeltaSub").textContent = `${data.delta_pts >= 0 ? "+" : ""}${data.delta_pts.toFixed(1)} points over Batch 1`;
    document.getElementById("kpiBestAngle").textContent = data.most_improved_angle || "N/A";

    renderCharts(data);
    onCompareChange();
  } catch (err) {
    console.error("Failed to load metrics:", err);
  }
}

function renderCharts(metricsData) {
  const rates = metricsData.rate_by_batch || {};
  const mix = metricsData.angle_mix_by_batch || {};

  const batches = Object.keys(rates).sort((a, b) => Number(a) - Number(b));
  const batchLabels = batches.map(b => `Batch ${b}`);
  const rateValues = batches.map(b => rates[b]);

  // 1. Trajectory Chart
  const trajCtx = document.getElementById("trajectoryChart");
  if (trajectoryChartInstance) {
    trajectoryChartInstance.destroy();
  }

  trajectoryChartInstance = new Chart(trajCtx, {
    type: "line",
    data: {
      labels: batchLabels,
      datasets: [{
        label: "Response Rate (%)",
        data: rateValues,
        borderColor: "#2563EB",
        backgroundColor: "rgba(37, 99, 235, 0.1)",
        borderWidth: 3,
        fill: true,
        tension: 0.2,
        pointRadius: 6,
        pointBackgroundColor: "#1D4ED8"
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          suggestedMax: 100,
          ticks: { callback: v => v + "%" }
        }
      }
    }
  });

  // 2. Angle Distribution Chart
  const mixCtx = document.getElementById("angleMixChart");
  if (angleMixChartInstance) {
    angleMixChartInstance.destroy();
  }

  const metricPct = batches.map(b => (mix[b] && mix[b].referenced_metric) || 0);
  const opinionPct = batches.map(b => (mix[b] && mix[b].referenced_opinion) || 0);
  const genericPct = batches.map(b => (mix[b] && mix[b].generic) || 0);

  angleMixChartInstance = new Chart(mixCtx, {
    type: "bar",
    data: {
      labels: batchLabels,
      datasets: [
        {
          label: "Referenced Metric",
          data: metricPct,
          backgroundColor: "#3B82F6"
        },
        {
          label: "Referenced Opinion",
          data: opinionPct,
          backgroundColor: "#10B981"
        },
        {
          label: "Generic",
          data: genericPct,
          backgroundColor: "#94A3B8"
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        x: { stacked: true },
        y: {
          stacked: true,
          beginAtZero: true,
          max: 100,
          ticks: { callback: v => v + "%" }
        }
      }
    }
  });

  // Render Batch Performance & Angle Mix Breakdown Table
  const tableBody = document.getElementById("batchTableBody");
  if (tableBody) {
    tableBody.innerHTML = "";
    batches.forEach(b => {
      const tr = document.createElement("tr");
      tr.style.borderBottom = "1px solid var(--border)";
      tr.style.cursor = "pointer";
      tr.className = "qa-row";
      tr.title = `Click to inspect Batch ${b} details`;
      tr.onclick = () => { onCompareChange(); };

      const tdBatch = document.createElement("td");
      tdBatch.style.padding = "10px 12px";
      tdBatch.style.fontWeight = "600";
      tdBatch.textContent = `Batch ${b}`;
      tr.appendChild(tdBatch);

      const tdRate = document.createElement("td");
      tdRate.style.padding = "10px 12px";
      tdRate.textContent = `${(rates[b] || 0).toFixed(1)}%`;
      tr.appendChild(tdRate);

      const tdMetric = document.createElement("td");
      tdMetric.style.padding = "10px 12px";
      tdMetric.textContent = `${((mix[b] && mix[b].referenced_metric) || 0).toFixed(1)}%`;
      tr.appendChild(tdMetric);

      const tdOpinion = document.createElement("td");
      tdOpinion.style.padding = "10px 12px";
      tdOpinion.textContent = `${((mix[b] && mix[b].referenced_opinion) || 0).toFixed(1)}%`;
      tr.appendChild(tdOpinion);

      const tdGeneric = document.createElement("td");
      tdGeneric.style.padding = "10px 12px";
      tdGeneric.textContent = `${((mix[b] && mix[b].generic) || 0).toFixed(1)}%`;
      tr.appendChild(tdGeneric);

      tableBody.appendChild(tr);
    });
  }
}

async function tagProspects() {
  const btn = document.getElementById("tagProspectsBtn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Tagging...";
  }
  try {
    const res = await fetch(`${API_BASE}/api/tag-prospects`, { method: "POST" });
    if (res.ok) {
      await loadProspects();
    }
  } catch (err) {
    console.error("Tagging error:", err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Tag prospects";
    }
  }
}

function runSingleBatchAsync(batchNumber, size) {
  return new Promise(async (resolve, reject) => {
    const progressBox = document.getElementById("progressBox");
    const progressBarFill = document.getElementById("progressBarFill");
    const progressText = document.getElementById("progressText");

    if (progressBox) progressBox.style.display = "block";
    if (progressBarFill) progressBarFill.style.width = "0%";
    if (progressText) progressText.textContent = `Batch ${batchNumber}: Starting job (0/${size})...`;

    try {
      const res = await fetch(`${API_BASE}/api/batch/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_number: batchNumber, size: size })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start batch");
      }

      const { job_id } = await res.json();

      const poll = setInterval(async () => {
        try {
          const sRes = await fetch(`${API_BASE}/api/batch/status/${job_id}`);
          if (!sRes.ok) return;
          const statusData = await sRes.json();

          const done = statusData.done || 0;
          const total = statusData.total || size;
          const pct = Math.round((done / total) * 100);

          if (progressBarFill) progressBarFill.style.width = `${pct}%`;
          if (progressText) progressText.textContent = `Batch ${batchNumber}: Processed ${done}/${total} prospects (${pct}%)...`;

          if (statusData.status === "done" || statusData.status === "error") {
            clearInterval(poll);
            if (statusData.status === "error") {
              reject(new Error(statusData.error));
            } else {
              resolve(statusData);
            }
          }
        } catch (pollErr) {
          clearInterval(poll);
          reject(pollErr);
        }
      }, 300);
    } catch (err) {
      reject(err);
    }
  });
}

async function runBatch() {
  const batchNumInput = document.getElementById("batchNumInput");
  const batchSizeInput = document.getElementById("batchSizeInput");
  const runBtn = document.getElementById("runBatchBtn");
  const runBtnText = document.getElementById("runBatchBtnText");
  const progressBox = document.getElementById("progressBox");

  const batchNumber = parseInt(batchNumInput.value, 10) || 1;
  const size = parseInt(batchSizeInput.value, 10) || 12;

  runBtn.disabled = true;
  runBtnText.textContent = "Running...";

  try {
    await runSingleBatchAsync(batchNumber, size);
    batchNumInput.value = batchNumber + 1;
    await loadMetrics();
  } catch (err) {
    console.error("Batch run error:", err);
  } finally {
    runBtn.disabled = false;
    runBtnText.textContent = "Run Batch";
    setTimeout(() => { if (progressBox) progressBox.style.display = "none"; }, 1500);
  }
}

async function runAllBatches() {
  const runAllBtn = document.getElementById("runAllBatchesBtn");
  const runBtn = document.getElementById("runBatchBtn");
  const batchSizeInput = document.getElementById("batchSizeInput");
  const size = parseInt(batchSizeInput.value, 10) || 12;

  if (runAllBtn) runAllBtn.disabled = true;
  if (runBtn) runBtn.disabled = true;

  try {
    for (let b = 1; b <= 3; b++) {
      document.getElementById("batchNumInput").value = b;
      await runSingleBatchAsync(b, size);
      await loadMetrics();
    }
  } catch (err) {
    console.error("Run all batches error:", err);
  } finally {
    if (runAllBtn) runAllBtn.disabled = false;
    if (runBtn) runBtn.disabled = false;
    const progressBox = document.getElementById("progressBox");
    setTimeout(() => { if (progressBox) progressBox.style.display = "none"; }, 1500);
  }
}

async function resetData() {
  try {
    const res = await fetch(`${API_BASE}/api/reset`, { method: "POST" });
    if (res.ok) {
      document.getElementById("batchNumInput").value = 1;
      await loadMetrics();
    }
  } catch (err) {
    console.error("Reset error:", err);
  }
}

function onDraftProspectChange() {
  const select = document.getElementById("draftProspectSelect");
  const infoBox = document.getElementById("draftProspectInfo");
  const p = prospectsList.find(x => x.id === select.value);

  if (!p) {
    infoBox.textContent = "No prospect selected.";
    return;
  }

  infoBox.textContent = `${p.name} — ${p.role || p.persona_type} at ${p.company}. Bio: ${p.bio || 'N/A'}. Post Summary: ${p.post_summary || p.content_summary || 'N/A'}`;
}

async function generateLiveDraft() {
  const select = document.getElementById("draftProspectSelect");
  const reflectionToggle = document.getElementById("reflectionToggle");
  const btn = document.getElementById("draftBtn");
  const btnText = document.getElementById("draftBtnText");

  const outputBox = document.getElementById("draftOutputBox");
  const subjectInput = document.getElementById("draftSubjectOutput");
  const bodyInput = document.getElementById("draftBodyOutput");
  const angleBadge = document.getElementById("draftAngleBadge");
  const reflectionNote = document.getElementById("reflectionNote");
  const wordCountNote = document.getElementById("wordCountNote");

  btn.disabled = true;
  btnText.innerHTML = '<span class="spinner"></span> Drafting...';

  try {
    const res = await fetch(`${API_BASE}/api/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prospect_id: select.value,
        use_reflection: reflectionToggle.checked
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Drafting failed");
    }

    const data = await res.json();

    subjectInput.value = data.subject || "";
    bodyInput.value = data.body || "";

    angleBadge.textContent = data.angle_used || "generic";
    angleBadge.className = "badge " + (
      data.angle_used === "referenced_metric" ? "badge-metric" :
      data.angle_used === "referenced_opinion" ? "badge-opinion" : "badge-generic"
    );

    const words = (data.body || "").trim().split(/\s+/).filter(Boolean).length;
    wordCountNote.textContent = `${words} words`;

    if (data.reflection_applied) {
      reflectionNote.textContent = `Applied insight: "${data.reflection_applied}"`;
    } else {
      reflectionNote.textContent = "No reflection applied (exploration mode)";
    }

    outputBox.style.display = "block";
  } catch (err) {
    alert(`Draft error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btnText.textContent = "Generate Cold Email";
  }
}

async function onCompareChange() {
  const select = document.getElementById("compareSelect");
  const prospectId = select.value;
  if (!prospectId) return;

  const col1 = document.getElementById("compareBatch1Col");
  const colLatest = document.getElementById("compareLatestCol");

  try {
    const res = await fetch(`${API_BASE}/api/compare/${prospectId}`);
    if (!res.ok) return;
    const data = await res.json();

    renderComparisonCard(col1, "Batch 1 (Initial Cold Run)", data.batch1);
    renderComparisonCard(colLatest, "Latest Batch (Adapted Run)", data.latest);
  } catch (err) {
    console.error("Error loading comparison:", err);
  }
}

function renderComparisonCard(container, title, entry) {
  // Clear container
  container.innerHTML = "";

  const heading = document.createElement("h3");
  heading.style.fontSize = "0.95rem";
  heading.style.marginBottom = "8px";
  heading.textContent = title;
  container.appendChild(heading);

  if (!entry) {
    const emptyNotice = document.createElement("p");
    emptyNotice.style.fontSize = "0.85rem";
    emptyNotice.style.color = "var(--text-muted)";
    emptyNotice.style.fontStyle = "italic";
    emptyNotice.textContent = "No records logged for this batch.";
    container.appendChild(emptyNotice);
    return;
  }

  // Header row with badges
  const headerRow = document.createElement("div");
  headerRow.style.display = "flex";
  headerRow.style.justifyContent = "space-between";
  headerRow.style.alignItems = "center";
  headerRow.style.marginBottom = "8px";

  const batchInfo = document.createElement("span");
  batchInfo.style.fontSize = "0.85rem";
  batchInfo.style.fontWeight = "600";
  batchInfo.textContent = `Batch ${entry.batch}`;
  headerRow.appendChild(batchInfo);

  const badgeWrapper = document.createElement("div");
  badgeWrapper.style.display = "flex";
  badgeWrapper.style.gap = "6px";

  const angleBadge = document.createElement("span");
  angleBadge.className = "badge " + (
    entry.angle === "referenced_metric" ? "badge-metric" :
    entry.angle === "referenced_opinion" ? "badge-opinion" : "badge-generic"
  );
  angleBadge.textContent = entry.angle || "generic";
  badgeWrapper.appendChild(angleBadge);

  const outcomeBadge = document.createElement("span");
  outcomeBadge.className = "badge " + (
    entry.outcome === "interested" ? "badge-interested" :
    entry.outcome === "reply" ? "badge-reply" : "badge-no_reply"
  );
  outcomeBadge.textContent = entry.outcome || "no_reply";
  badgeWrapper.appendChild(outcomeBadge);

  headerRow.appendChild(badgeWrapper);
  container.appendChild(headerRow);

  // Subject
  const subjElem = document.createElement("div");
  subjElem.style.fontSize = "0.85rem";
  subjElem.style.fontWeight = "600";
  subjElem.style.marginBottom = "4px";
  subjElem.textContent = `Subject: ${entry.subject || '(None)'}`;
  container.appendChild(subjElem);

  // Message body safely escaped with textContent
  const msgBox = document.createElement("div");
  msgBox.className = "msg-box";
  msgBox.textContent = entry.email || "";
  container.appendChild(msgBox);

  // Simulated Reply safely escaped with textContent
  const replyBox = document.createElement("div");
  replyBox.className = "reply-box";
  if (entry.reply) {
    replyBox.textContent = `Simulated Reply: "${entry.reply}"`;
  } else {
    replyBox.textContent = "Simulated Reply: (No reply received)";
  }
  container.appendChild(replyBox);
}
