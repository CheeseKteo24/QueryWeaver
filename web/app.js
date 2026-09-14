const questionInput = document.querySelector("#question");
const submitButton = document.querySelector("#submit");
const result = document.querySelector("#result");
const errorBox = document.querySelector("#error");
const answer = document.querySelector("#answer");
const routeBadge = document.querySelector("#route-badge");
const latencyBadge = document.querySelector("#latency-badge");
const sqlPanel = document.querySelector("#sql-panel");
const sqlCode = document.querySelector("#sql");
const sqlTable = document.querySelector("#sql-table");
const evidencePanel = document.querySelector("#evidence-panel");
const evidenceList = document.querySelector("#evidence-list");

function clearElement(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function renderTable(sqlResult) {
  clearElement(sqlTable);
  const head = document.createElement("thead");
  const headingRow = document.createElement("tr");
  for (const column of sqlResult.columns) {
    const cell = document.createElement("th");
    cell.textContent = column;
    headingRow.appendChild(cell);
  }
  head.appendChild(headingRow);
  sqlTable.appendChild(head);

  const body = document.createElement("tbody");
  for (const row of sqlResult.rows) {
    const tableRow = document.createElement("tr");
    for (const value of row) {
      const cell = document.createElement("td");
      cell.textContent = value === null ? "NULL" : String(value);
      tableRow.appendChild(cell);
    }
    body.appendChild(tableRow);
  }
  sqlTable.appendChild(body);
}

function renderEvidence(items) {
  clearElement(evidenceList);
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "evidence-card";

    const metadata = document.createElement("div");
    const source = document.createElement("strong");
    source.textContent = item.document_id;
    const score = document.createElement("span");
    score.textContent = `score ${item.score.toFixed(4)}`;
    metadata.append(source, score);

    const text = document.createElement("p");
    text.textContent = item.text;
    const chunk = document.createElement("code");
    chunk.textContent = item.chunk_id;
    card.append(metadata, text, chunk);
    evidenceList.appendChild(card);
  }
}

function renderResponse(payload) {
  routeBadge.textContent = payload.route === "sql" ? "SQL route" : "Document route";
  latencyBadge.textContent = `${payload.latency_ms.toFixed(2)} ms`;
  answer.textContent = payload.answer;

  const hasSql = payload.sql_result !== null;
  sqlPanel.classList.toggle("hidden", !hasSql);
  if (hasSql) {
    sqlCode.textContent = payload.validated_sql;
    renderTable(payload.sql_result);
  }

  const hasEvidence = payload.evidence.length > 0;
  evidencePanel.classList.toggle("hidden", !hasEvidence);
  if (hasEvidence) renderEvidence(payload.evidence);

  result.classList.remove("hidden");
}

async function runQuery() {
  const question = questionInput.value.trim();
  if (!question) {
    errorBox.textContent = "请先输入一个问题。";
    errorBox.classList.remove("hidden");
    return;
  }

  errorBox.classList.add("hidden");
  result.classList.add("hidden");
  submitButton.disabled = true;
  submitButton.firstElementChild.textContent = "正在编排…";

  try {
    const response = await fetch("/v1/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 3 }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "查询失败");
    renderResponse(payload);
  } catch (error) {
    errorBox.textContent = error instanceof Error ? error.message : "查询失败";
    errorBox.classList.remove("hidden");
  } finally {
    submitButton.disabled = false;
    submitButton.firstElementChild.textContent = "运行查询";
  }
}

submitButton.addEventListener("click", runQuery);
questionInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runQuery();
});
for (const button of document.querySelectorAll("[data-question]")) {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.question;
    questionInput.focus();
  });
}
