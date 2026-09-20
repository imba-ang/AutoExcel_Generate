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

  const savedIdentity = JSON.parse(localStorage.getItem("autoexcel_demo_identity") || "null");
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
    localStorage.setItem("autoexcel_demo_identity", JSON.stringify(current));
    return current;
  }

  function storageKey(studentId, sectionName = section) {
    return `autoexcel_demo_${studentId}_${sectionName}`;
  }

  function readRecord(studentId, sectionName = section) {
    return JSON.parse(localStorage.getItem(storageKey(studentId, sectionName)) || "null");
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

  loadButton.addEventListener("click", () => {
    const current = requireIdentity();
    if (!current) return;
    const record = readRecord(current.student_id);
    setAnswers(record?.answers || {});
    if (section === "shai") {
      updateFormulaCells(readRecord(current.student_id, "kuo")?.answers || {});
    }
    setMessage(
      record ? "已读取本机保存内容，可以继续修改。" : "本机没有旧记录，可以开始填写。",
      "success",
    );
  });

  submitButton.addEventListener("click", () => {
    const current = requireIdentity();
    if (!current) return;
    localStorage.setItem(
      storageKey(current.student_id),
      JSON.stringify({ ...current, answers: collectAnswers(), saved_at: new Date().toISOString() }),
    );
    setMessage("演示保存成功。内容只保存在当前浏览器，没有上传。", "success");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
})();
