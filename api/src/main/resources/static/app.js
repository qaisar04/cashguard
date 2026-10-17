const API_BASE = "/api/v1";
const API_KEY_HEADER = "X-API-Key";
const API_KEY_STORAGE = "cashguard.apiKey";
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 6 * 60 * 1000;
const STATUS = { PROCESSING: "processing", DONE: "done", FAILED: "failed" };
const VERDICT = { VIOLATION: "violation", NO_VIOLATION: "no_violation" };
const STATUS_TEXT = {
  uploading: "Загрузка видео...",
  processing: "Анализ видео, это может занять несколько минут...",
  done: "Готово",
  failed: "Обработка завершилась ошибкой",
};

const el = (id) => document.getElementById(id);
const apiKeyInput = el("apiKey");
const fileInput = el("file");
const drop = el("drop");
const sendBtn = el("send");

apiKeyInput.value = sessionStorage.getItem(API_KEY_STORAGE) || "";
apiKeyInput.addEventListener("input", () => {
  sessionStorage.setItem(API_KEY_STORAGE, apiKeyInput.value);
  updateButton();
});
fileInput.addEventListener("change", () => {
  el("fileName").textContent = fileInput.files[0] ? fileInput.files[0].name : "";
  updateButton();
});
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
sendBtn.addEventListener("click", analyze);

function updateButton() {
  sendBtn.disabled = !(apiKeyInput.value && fileInput.files[0]);
}

function headers() {
  return { [API_KEY_HEADER]: apiKeyInput.value };
}

function show(id, visible) {
  el(id).classList.toggle("hidden", !visible);
}

function setStatus(key, running) {
  show("statusCard", true);
  el("statusText").textContent = STATUS_TEXT[key] || key;
  el("spinner").classList.toggle("hidden", !running);
}

function showError(message) {
  show("errorCard", true);
  el("errorText").textContent = message;
  el("spinner").classList.add("hidden");
}

async function analyze() {
  sendBtn.disabled = true;
  show("resultCard", false);
  show("errorCard", false);
  el("violations").innerHTML = "";
  setStatus("uploading", true);
  try {
    const form = new FormData();
    form.append("file", fileInput.files[0]);
    const res = await fetch(`${API_BASE}/analyze`, { method: "POST", headers: headers(), body: form });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    el("jobId").textContent = body.job_id;
    setStatus("processing", true);
    const job = await poll(body.job_id);
    render(job);
  } catch (e) {
    showError(e.message);
  } finally {
    updateButton();
  }
}

async function poll(jobId) {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`, { headers: headers() });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    if (body.status !== STATUS.PROCESSING) return body;
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  throw new Error("Превышено время ожидания результата");
}

function render(job) {
  if (job.status === STATUS.FAILED) {
    setStatus("failed", false);
    showError(job.error || "unknown error");
    return;
  }
  setStatus("done", false);
  show("resultCard", true);
  const verdict = el("verdict");
  const bad = job.verdict === VERDICT.VIOLATION;
  verdict.className = `verdict ${bad ? "bad" : "ok"}`;
  verdict.textContent = bad
    ? `Обнаружены признаки возможных нарушений: ${job.violations.length}`
    : "Нарушение не обнаружено";
  const container = el("violations");
  (job.violations || []).forEach((v, i) => container.appendChild(violationCard(v, i + 1)));
}

function violationCard(v, index) {
  const card = document.createElement("div");
  card.className = "violation";
  const frames = (v.evidence_frames || []).map((f) => `
    <div class="frame">
      <img src="data:image/jpeg;base64,${f.image_base64}" alt="кадр ${fmt(f.timestamp_sec)}">
      <span>${fmt(f.timestamp_sec)}</span>
    </div>`).join("");
  const rule = v.rule ? `
    <div class="rule">
      <b>Нормативный источник:</b> ${esc(v.rule.document)}${v.rule.clause ? `, ${esc(v.rule.clause)}` : ""}
      ${v.rule.url ? ` — <a href="${esc(v.rule.url)}" target="_blank" rel="noopener">adilet.zan.kz</a>` : ""}
    </div>` : "";
  card.innerHTML = `
    <h3>${index}. ${esc(v.type)}</h3>
    <div class="meta">Таймкод: <b>${fmt(v.timecode_sec)}</b> · код типа: <code>${esc(v.type_id)}</code></div>
    <p class="desc">${esc(v.description)}</p>
    <div class="frames">${frames}</div>
    ${rule}`;
  return card;
}

function fmt(sec) {
  const s = Number(sec) || 0;
  const m = Math.floor(s / 60);
  const r = (s - m * 60).toFixed(1).padStart(4, "0");
  return `${m}:${r} (${s.toFixed(1)} с)`;
}

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
