(() => {
  const table = document.querySelector(".excel-grid[data-section]");
  if (!table) return;

  const section = table.dataset.section;
  const message = document.querySelector("#message");
  const submitButton = document.querySelector("#submit-form");
  const cellInputs = [...document.querySelectorAll("[data-cell]")];

  function setMessage(text, kind = "info") {
    message.textContent = text;
    message.className = `message ${text ? `message-${kind}` : ""}`;
  }

  function storageKey(sectionName = section) {
    return `autoexcel_demo_${sectionName}`;
  }

  function readRecord(sectionName = section) {
    return JSON.parse(localStorage.getItem(storageKey(sectionName)) || "null");
  }

  function setAnswers(answers) {
    for (const input of cellInputs) input.value = answers[input.dataset.cell] || "";
  }

  function updateFormulaCells(contextAnswers) {
    for (const cell of document.querySelectorAll("[data-formula-source]")) {
      const value = contextAnswers[cell.dataset.formulaSource] || cell.dataset.default || "";
      const target = cell.querySelector(".cell-value");
      if (target) target.textContent = value;
    }
  }

  function collectAnswers() {
    return Object.fromEntries(cellInputs.map((input) => [input.dataset.cell, input.value.trim()]));
  }

  const savedRecord = readRecord();
  setAnswers(savedRecord?.answers || {});
  if (section === "shai") updateFormulaCells(readRecord("kuo")?.answers || {});

  submitButton.addEventListener("click", () => {
    localStorage.setItem(
      storageKey(),
      JSON.stringify({ answers: collectAnswers(), saved_at: new Date().toISOString() }),
    );
    setMessage("保存成功。", "success");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
})();
