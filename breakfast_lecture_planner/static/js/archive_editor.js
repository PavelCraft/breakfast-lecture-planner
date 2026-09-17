(() => {
  const container = document.querySelector("#archive-editor");
  const form = document.querySelector("#archive-editor-form");
  const content = document.querySelector(".post-content");
  if (!container || !form || !content) return;

  let opening = false;

  async function waitForEditor() {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const editor = window.editors?.id_content;
      if (editor) return editor;
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
    throw new Error("Редактор CKEditor не был загружен.");
  }

  async function closeEditor() {
    container.hidden = true;
    content.hidden = false;
    await window.scheduleEditLock.release("archive");
  }

  async function openEditor() {
    if (opening || !container.hidden) return;
    opening = true;
    try {
      await window.scheduleEditLock.acquire("archive");
      const [response, editor] = await Promise.all([
        fetch(window.archiveEditUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          cache: "no-store",
        }),
        waitForEditor(),
      ]);
      if (!response.ok) throw new Error("Не удалось загрузить актуальный архив.");
      editor.setData((await response.json()).content);
      content.hidden = true;
      container.hidden = false;
      editor.editing.view.focus();
    } catch (error) {
      await window.scheduleEditLock.release("archive");
      alert(error.message);
    } finally {
      opening = false;
    }
  }

  document.querySelectorAll("#edit-post-btn-up, #edit-post-btn-down").forEach((button) => {
    button.addEventListener("click", openEditor);
  });
  document.querySelectorAll(".close-archive-editor").forEach((button) => {
    button.addEventListener("click", closeEditor);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const buttons = form.querySelectorAll('[type="submit"]');
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const formData = new FormData(form);
      formData.append("edit_lock_token", window.scheduleEditLock.token);
      const response = await fetch(window.archiveEditUrl, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Не удалось сохранить архив.");
      content.innerHTML = data.content;
      await closeEditor();
    } catch (error) {
      alert(error.message);
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  });
})();
