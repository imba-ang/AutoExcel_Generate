(() => {
  const table = document.querySelector(".excel-grid[data-section]");
  if (!table) return;

  const section = table.dataset.section;
  const nameInput = document.querySelector("#student-name");
  const idInput = document.querySelector("#student-id");
  const message = document.querySelector("#message");
  const loadButton = document.querySelector("#load-existing");
  const submitButton = document.querySelector("#submit-form");
  const cellInputs = [...document.querySelectorAll("[data-cell]")];

  const savedIdentity = JSON.parse(localStorage.getItem("autoexcel_identity") || "null");
  if (savedIdentity) {
    nameInput.value = savedIdentity.student_name || "";
    idInput.value = savedIdentity.student_id || "";
  }

  function setMessage(text, kind = "info") {
    message.textContent = text;
    message.className = `message ${text ? `message-${kind}` : ""}`;
  }

  function identity() {
    return {
      student_name: nameInput.value.trim(),
      student_id: idInput.value.trim(),
    };
  }

  function requireIdentity() {
    const current = identity();
    if (!current.student_name || !current.student_id) {
      setMessage("请先填写姓名和学号。", "error");
      return null;
    }
    localStorage.setItem("autoexcel_identity", JSON.stringify(current));
    return current;
  }

  function setAnswers(answers) {
    for (const input of cellInputs) input.value = answers[input.dataset.cell] || "";
  }

  function updateFormulaCells(contextAnswers) {
    for (const cell of document.querySelectorAll("[data-formula-source]")) {
      const source = cell.dataset.formulaSource;
      const value = contextAnswers[source] || cell.dataset.default || "";
      const target = cell.querySelector(".cell-value");
      if (target) target.textContent = value;
    }
  }

  function collectAnswers() {
    return Object.fromEntries(cellInputs.map((input) => [input.dataset.cell, input.value.trim()]));
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "操作失败，请稍后重试。");
    return data;
  }

  loadButton.addEventListener("click", async () => {
    const current = requireIdentity();
    if (!current) return;
    loadButton.disabled = true;
    setMessage("正在读取…");
    try {
      const data = await postJson(`/api/submissions/${section}/load`, { ...current, answers: {} });
      setAnswers(data.answers || {});
      updateFormulaCells(data.context_answers || {});
      setMessage(data.exists ? "已读取上次提交内容，可以继续修改。" : "未找到旧记录，可以开始填写。", "success");
    } catch (error) {
      setMessage(error.message, "error");
    } finally {
      loadButton.disabled = false;
    }
  });

  submitButton.addEventListener("click", async () => {
    const current = requireIdentity();
    if (!current) return;
    submitButton.disabled = true;
    setMessage("正在提交…");
    try {
      await postJson(`/api/submissions/${section}`, { ...current, answers: collectAnswers() });
      setMessage("提交成功。以后可用相同姓名和学号读取并修改。", "success");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setMessage(error.message, "error");
    } finally {
      submitButton.disabled = false;
    }
  });
})();
