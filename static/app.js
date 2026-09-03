const state = { analysis: null, filter: "all", lastPayload: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const INTENTS = {
  confirmed: "подтверждение", cancellation: "отмена", reschedule: "перенос",
  payment_issue: "вопрос оплаты", contact_problem: "проблема со связью",
  complaint: "жалоба", neutral: "обычный комментарий",
};
const ACTIONS = { "Review now": "Проверить сейчас", "Check today": "Проверить сегодня", Monitor: "Наблюдать" };
const STATUSES = { new: "новая", pending: "ожидает", confirmed: "подтверждена", rescheduled: "перенесена", cancelled: "отменена" };
const REASONS = {
  "Client name is missing": "Не указано имя клиента",
  "No valid contact channel": "Нет телефона или электронной почты",
  "Scheduled date cannot be parsed": "Не удалось распознать дату",
  "Possible repeat request for the same person": "Возможная повторная заявка того же клиента",
  "Amount is an unusual statistical outlier": "Сумма заметно отличается от остальных",
  "Cancelled record still contains a positive amount": "В отменённой записи осталась положительная сумма",
  "Structured status may conflict with the client note": "Статус может противоречить комментарию клиента",
  "No material issues detected": "Существенных проблем не найдено",
};

function humanIntent(value) { return INTENTS[value] || String(value || "neutral").replaceAll("_", " "); }
function humanAction(value) { return ACTIONS[value] || value || "Проверить"; }
function humanReason(value) {
  if (REASONS[value]) return REASONS[value];
  if (String(value).startsWith("Note classified as ")) {
    return `Комментарий распознан как «${humanIntent(String(value).slice(19).replaceAll(" ", "_"))}»`;
  }
  return value;
}
function toast(message, type = "info") {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show ${type}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (element.className = "toast"), 3600);
}
function matchesFilter(record) {
  if (state.filter === "all") return true;
  if (state.filter === "attention") return record.priority !== "normal";
  if (state.filter === "duplicate") return record.flags.includes("duplicate");
  if (state.filter === "anomaly") return record.flags.includes("amount_outlier");
  return true;
}
function renderMetrics(summary) {
  $("#metricTotal").textContent = summary.total;
  $("#metricAttention").textContent = summary.attention;
  $("#metricDuplicates").textContent = summary.duplicate_groups;
  $("#metricAnomalies").textContent = summary.anomalies;
  $("#metricTime").textContent = summary.processing_ms;
}
function renderQueue(records) {
  const visible = records.filter(matchesFilter);
  $("#visibleCount").textContent = visible.length;
  $("#actionQueue").innerHTML = visible.length ? visible.map((record) => `
    <article class="queue-item" data-priority="${record.priority}">
      <div class="risk-orb">${record.risk_score}</div>
      <div class="queue-copy"><strong>${escapeHtml(record.client_name)} · ${escapeHtml(record.service)}</strong><p>${record.reasons.slice(0, 2).map(humanReason).map(escapeHtml).join(" · ")}</p></div>
      <span class="queue-action">${escapeHtml(humanAction(record.recommended_action))}</span>
    </article>`).join("") : '<div class="empty-state">По выбранному фильтру строк нет.</div>';
}
function renderTable(records) {
  const visible = records.filter(matchesFilter);
  $("#recordsTable").innerHTML = visible.map((record) => `
    <tr data-priority="${record.priority}">
      <td class="risk-cell">${record.risk_score}</td>
      <td><span class="record-name"><strong>${escapeHtml(record.client_name)}</strong><small>${escapeHtml(record.id)} · ${escapeHtml(record.source)}</small></span></td>
      <td>${escapeHtml(record.service)}</td><td><span class="status-chip">${escapeHtml(STATUSES[record.status] || record.status)}</span></td>
      <td><span class="intent-chip">${escapeHtml(humanIntent(record.intent.label))} · ${Math.round(record.intent.confidence * 100)}%</span></td>
      <td>${escapeHtml(humanAction(record.recommended_action))}</td>
    </tr>`).join("");
}
function renderDistribution(distribution) {
  const entries = Object.entries(distribution);
  const maximum = Math.max(1, ...entries.map(([, count]) => count));
  $("#intentBars").innerHTML = entries.map(([label, count]) => `
    <div class="intent-row"><span>${escapeHtml(humanIntent(label))}</span><div class="intent-track"><div class="intent-fill" style="width:${(count / maximum) * 100}%"></div></div><b>${count}</b></div>`).join("");
}
function renderAnalysis(analysis) {
  state.analysis = analysis;
  renderMetrics(analysis.summary); renderQueue(analysis.records); renderTable(analysis.records); renderDistribution(analysis.intent_distribution);
  const source = analysis.import_info?.source_format?.toUpperCase() || "пример";
  const ignored = analysis.import_info?.ignored_columns?.length || 0;
  $("#resultMeta").textContent = `Проверка №${analysis.run_id} · ${source} · строк: ${analysis.records.length} · пропущено незнакомых столбцов: ${ignored}`;
  $("#workspace").hidden = false;
  $("#workspace").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function analyze(payload, contentType = "application/json") {
  const button = $("#demoButton"); const previous = button.innerHTML;
  button.disabled = true; button.textContent = "Проверяю…";
  try {
    const response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": contentType }, body: contentType === "application/json" ? JSON.stringify(payload) : payload });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Не удалось выполнить проверку");
    state.lastPayload = { payload, contentType }; renderAnalysis(result); toast(`Проверка №${result.run_id} завершена`);
  } catch (error) { toast(error.message, "error"); }
  finally { button.disabled = false; button.innerHTML = previous; }
}
async function runDemo() {
  try { const response = await fetch("/api/sample"); await analyze(await response.json()); }
  catch (error) { toast(`Не удалось загрузить пример: ${error.message}`, "error"); }
}
async function handleFile(file) {
  if (!file) return;
  if (file.size > 15_000_000) { toast("Размер файла не должен превышать 15 МБ", "error"); return; }
  const name = file.name.toLowerCase();
  if (name.endsWith(".xlsx")) { await analyze(await file.arrayBuffer(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); return; }
  const value = await file.text();
  if (name.endsWith(".json")) {
    try { await analyze(JSON.parse(value)); } catch (error) { toast(`Ошибка в JSON: ${error.message}`, "error"); }
    return;
  }
  await analyze(value, "text/csv");
}
async function loadModelHealth() {
  try {
    const response = await fetch("/api/model"); const model = await response.json();
    $("#modelAccuracy").textContent = `${Math.round(model.accuracy * 100)}%`;
    $("#modelDetails").innerHTML = `<dt>Способ</dt><dd>Статистическая классификация текста</dd><dt>Учебных примеров</dt><dd>${model.training_examples}</dd><dt>Контрольных примеров</dt><dd>${model.evaluation_examples}</dd><dt>Тем</dt><dd>${model.classes.length}</dd><dt>Обращений в облако</dt><dd>${model.cloud_calls}</dd>`;
  } catch { $("#modelAccuracy").textContent = "нет связи"; }
}
function escapeHtml(value) { const div = document.createElement("div"); div.textContent = String(value ?? ""); return div.innerHTML; }

$("#demoButton").addEventListener("click", runDemo);
$("#rerunButton").addEventListener("click", () => { if (state.lastPayload) analyze(state.lastPayload.payload, state.lastPayload.contentType); });
$("#fileInput").addEventListener("change", (event) => handleFile(event.target.files[0]));
$$('[data-filter]').forEach((button) => button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  $$('[data-filter]').forEach((candidate) => candidate.classList.toggle("active", candidate === button));
  if (state.analysis) { renderQueue(state.analysis.records); renderTable(state.analysis.records); }
}));
document.addEventListener("keydown", (event) => { if (event.key === "Enter" && !state.analysis && event.target.tagName !== "BUTTON") runDemo(); });
loadModelHealth();
