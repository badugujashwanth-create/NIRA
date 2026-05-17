const state = {
  events: [],
  runtimeDelayMs: 3000,
  eventDelayMs: 3000,
};

const $ = (id) => document.getElementById(id);

function addMessage(role, text, target = $("chatLog")) {
  const item = document.createElement("div");
  item.className = "message";
  item.innerHTML = `<span class="role">${role}</span>${escapeHtml(text)}`;
  target.appendChild(item);
  target.scrollTop = target.scrollHeight;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[ch]));
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

function showStatus(text, level = "ok") {
  $("statusLine").textContent = text;
  $("statusLine").dataset.level = level;
}

function showError(target, error) {
  addMessage("Error", error.message || String(error), target);
  showStatus("A subsystem reported an error. NIRA stayed online.", "warn");
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      $(tab.dataset.tab).classList.add("active");
    });
  });
}

function setupForms() {
  $("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = $("chatInput").value.trim();
    if (!message) return;
    const submit = event.submitter || $("chatForm").querySelector("button[type='submit']");
    $("chatInput").value = "";
    addMessage("You", message);
    addMessage("NIRA", "Working...");
    submit.disabled = true;
    showStatus("Orchestrating request...", "busy");
    try {
      const result = await postJson("/chat", { message, task_type: $("taskType").value || null });
      const last = $("chatLog").lastChild;
      last.innerHTML = `<span class="role">NIRA</span>${escapeHtml(result.answer || result.text || "")}`;
      showStatus("Ready", "ok");
    } catch (error) {
      showError($("chatLog"), error);
    } finally {
      submit.disabled = false;
    }
  });

  $("workflowForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const goal = $("workflowGoal").value.trim();
    if (!goal) return;
    $("workflowOutput").innerHTML = "";
    addMessage("Workflow", "Running...", $("workflowOutput"));
    const type = $("workflowType").value;
    showStatus(`Running ${type} workflow...`, "busy");
    try {
      const result = await postJson(`/workflows/${type}`, { goal });
      $("workflowOutput").innerHTML = "";
      addMessage("Result", result.answer, $("workflowOutput"));
      result.steps.forEach((step) => addMessage(step.status, `${step.name}: ${step.details}`, $("workflowOutput")));
      showStatus("Workflow completed", "ok");
    } catch (error) {
      showError($("workflowOutput"), error);
    }
  });

  $("memorySearch").addEventListener("click", loadMemorySearch);
  $("memoryRefresh").addEventListener("click", loadMemoryTimeline);
  $("voiceButton").addEventListener("click", recordVoice);
}

async function recordVoice() {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    addMessage("Voice", "Voice recording is not available in this browser.");
    return;
  }
  const button = $("voiceButton");
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (event) => chunks.push(event.data);
  recorder.onstop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    button.textContent = "Voice";
    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    const response = await fetch("/voice/transcribe", { method: "POST", body: blob, headers: { "Content-Type": blob.type } });
    const result = await response.json();
    if (result.ok && result.text) {
      $("chatInput").value = result.text;
    } else {
      addMessage("Voice", result.error || "Transcription failed.");
    }
  };
  button.textContent = "Recording";
  recorder.start();
  setTimeout(() => recorder.state === "recording" && recorder.stop(), 6000);
}

async function loadMemoryTimeline() {
  const data = await getJson("/memory/timeline?limit=30");
  renderMemory(data.items || []);
}

async function loadMemorySearch() {
  const query = $("memoryQuery").value.trim();
  if (!query) return loadMemoryTimeline();
  const data = await postJson("/memory/search", { query, limit: 12 });
  renderMemory((data.results || []).map((item) => ({
    id: item.id,
    kind: item.metadata?.kind || item.source || "semantic",
    content: item.text,
    importance: item.score,
    pinned: false,
  })));
}

function renderMemory(items) {
  $("memoryList").innerHTML = "";
  items.forEach((item) => {
    const node = document.createElement("div");
    node.className = "item";
    node.innerHTML = `
      <strong>${escapeHtml(item.kind || "memory")} ${item.pinned ? " pinned" : ""}</strong>
      <p>${escapeHtml(item.content || item.summary || "")}</p>
      ${Number.isInteger(item.id) ? `<button data-pin="${item.id}">Pin</button> <button data-archive="${item.id}">Archive</button> <button data-delete="${item.id}">Delete</button>` : ""}
    `;
    $("memoryList").appendChild(node);
  });
  document.querySelectorAll("[data-pin]").forEach((button) => button.addEventListener("click", async () => {
    await postJson(`/memory/${button.dataset.pin}/pin`, { pinned: true });
    await loadMemoryTimeline();
  }));
  document.querySelectorAll("[data-archive]").forEach((button) => button.addEventListener("click", async () => {
    await postJson(`/memory/${button.dataset.archive}/archive`, {});
    await loadMemoryTimeline();
  }));
  document.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", async () => {
    await fetch(`/memory/${button.dataset.delete}`, { method: "DELETE" });
    await loadMemoryTimeline();
  }));
}

async function refreshRuntime() {
  const [health, models, stateData, telemetry, analytics] = await Promise.all([
    getJson("/health"),
    getJson("/models"),
    getJson("/state"),
    getJson("/telemetry"),
    getJson("/analytics/summary"),
  ]);
  const ram = Math.round(health.ram_used_mb);
  const level = ram > health.ram_limit_mb ? "warn" : "ok";
  showStatus(`API ready, RAM ${ram} MB of ${health.ram_limit_mb} MB target`, level);
  $("modelPill").textContent = `model: ${models.current_heavy_model || "none resident"}`;
  $("ramMetric").textContent = Math.round(stateData.ram_usage_mb || 0);
  $("cpuMetric").textContent = Math.round(stateData.cpu_usage || 0);
  $("compressionMetric").textContent = Number(stateData.compression_ratio || 0).toFixed(2);
  $("retrievalMetric").textContent = Number(stateData.retrieval_precision || 0).toFixed(2);
  const workflows = analytics.workflow_learning?.workflows || [];
  const avgSuccess = workflows.length
    ? workflows.reduce((sum, item) => sum + Number(item.avg_success_score || 0), 0) / workflows.length
    : 0;
  $("routeMetric").textContent = Number(analytics.routing?.confidence || 0).toFixed(2);
  $("workflowMetric").textContent = avgSuccess.toFixed(2);
  $("cacheMetric").textContent = analytics.workflow_learning?.cache?.hits || 0;
  $("recallMetric").textContent = Number(analytics.context?.useful_recall_percent || 0).toFixed(2);
  $("telemetryJson").textContent = JSON.stringify({ analytics, telemetry }, null, 2);
  renderList("activeTasks", stateData.active_tasks || [], (item) => `${item.kind}: ${item.metadata?.task || item.id}`);
  renderList("queues", Object.entries(stateData.queue_depth || {}).map(([name, depth]) => ({ name, depth })), (item) => `${item.name}: ${item.depth}`);
  const active = (stateData.active_tasks || []).length > 0;
  const queueDepth = Object.values(stateData.queue_depth || {}).reduce((sum, value) => sum + Number(value || 0), 0);
  state.runtimeDelayMs = active || queueDepth ? 1500 : 5000;
}

function renderList(id, items, format) {
  const root = $(id);
  root.innerHTML = "";
  if (!items.length) {
    root.innerHTML = `<div class="item"><p>None</p></div>`;
    return;
  }
  items.forEach((item) => {
    const node = document.createElement("div");
    node.className = "item";
    node.innerHTML = `<p>${escapeHtml(format(item))}</p>`;
    root.appendChild(node);
  });
}

async function refreshEvents() {
  const data = await getJson("/events/replay?limit=25");
  $("events").innerHTML = "";
  (data.events || []).reverse().forEach((event) => {
    const node = document.createElement("div");
    node.className = "item";
    node.innerHTML = `<strong>${escapeHtml(event.type)}</strong><p>${escapeHtml(JSON.stringify(event.payload))}</p>`;
    $("events").appendChild(node);
  });
}

setupTabs();
setupForms();
loadMemoryTimeline().catch(() => {});
pollRuntime();
pollEvents();

async function pollRuntime() {
  try {
    await refreshRuntime();
  } catch {
    showStatus("Runtime view is reconnecting...", "warn");
    state.runtimeDelayMs = 6000;
  } finally {
    setTimeout(pollRuntime, state.runtimeDelayMs);
  }
}

async function pollEvents() {
  try {
    await refreshEvents();
    state.eventDelayMs = state.runtimeDelayMs;
  } catch {
    state.eventDelayMs = 6000;
  } finally {
    setTimeout(pollEvents, state.eventDelayMs);
  }
}
