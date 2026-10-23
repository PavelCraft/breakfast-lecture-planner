(() => {
  const container = document.querySelector("#text-post-editor");
  const form = document.querySelector("#text-post-editor-form");
  const content = document.querySelector(".text-post-content");
  const pageTitle = document.querySelector(".text-post-title");
  const openButtons = document.querySelectorAll("[data-open-text-post-editor]");
  if (!container || !form || !content || !openButtons.length) return;

  const editorOwner = "text-post-editor";
  let opening = false;

  async function waitForEditor() {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const editor = window.editors?.id_content;
      if (editor) return editor;
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
    throw new Error("Редактор CKEditor не был загружен.");
  }

  function setEditButtonsHidden(hidden) {
    openButtons.forEach((button) => { button.hidden = hidden; });
  }

  async function closeEditor() {
    container.hidden = true;
    content.hidden = false;
    setEditButtonsHidden(false);
    await window.scheduleEditLock.release(editorOwner);
  }

  async function openEditor() {
    if (opening || !container.hidden) return;
    opening = true;
    try {
      await window.scheduleEditLock.acquire(editorOwner);
      const [response, editor] = await Promise.all([
        fetch(window.textPostEditUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          cache: "no-store",
        }),
        waitForEditor(),
      ]);
      if (!response.ok) throw new Error("Не удалось загрузить актуальный текст страницы.");
      editor.setData((await response.json()).content);
      content.hidden = true;
      setEditButtonsHidden(true);
      container.hidden = false;
      editor.editing.view.focus();
    } catch (error) {
      await window.scheduleEditLock.release(editorOwner);
      alert(error.message);
    } finally {
      opening = false;
    }
  }

  openButtons.forEach((button) => button.addEventListener("click", openEditor));
  document.querySelectorAll(".close-text-post-editor").forEach((button) => {
    button.addEventListener("click", closeEditor);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const buttons = form.querySelectorAll('[type="submit"]');
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const formData = new FormData(form);
      formData.append("edit_lock_token", window.scheduleEditLock.token);
      const response = await fetch(window.textPostEditUrl, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Не удалось сохранить текст страницы.");
      content.innerHTML = data.content;
      if (pageTitle) pageTitle.hidden = Boolean(content.querySelector("h1, h2, h3"));
      await closeEditor();
    } catch (error) {
      alert(error.message);
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  });
})();
