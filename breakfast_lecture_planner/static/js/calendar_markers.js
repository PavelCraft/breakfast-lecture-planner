document.addEventListener("DOMContentLoaded", () => {
  const tokens = {
    ekadashi: "[Экадаши]",
    fast: "[Пост]",
    holiday: "[Праздник]",
    saints: "[Дни святых]",
    kartika_start: "[Картика: начало]",
    kartika_end: "[Картика: конец]",
  };
  const dayPattern = /^\d{1,2}\s*d\s*\.\s*(pirmadienis|antradienis|trečiadienis|ketvirtadienis|penktadienis|šeštadienis|sekmadienis)$/i;

  function nodeText(node) {
    if (typeof node.data === "string") return node.data;
    if (!node.getChildren) return "";
    return Array.from(node.getChildren(), nodeText).join("");
  }

  function markerKind(node) {
    if (!node.is("element", "paragraph")) return null;
    const value = nodeText(node).trim().toLocaleLowerCase();
    return Object.keys(tokens).find((key) => tokens[key].toLocaleLowerCase() === value) || null;
  }

  function getEditor(controls) {
    const id = controls.dataset.markerControls === "main" ? "id_content" : "id_daily-content";
    return window.editors?.[id] || null;
  }

  function selectedDay(editor, controls) {
    const root = editor.model.document.getRoot();
    const blocks = Array.from(root.getChildren());
    if (controls.dataset.markerControls === "daily") {
      const date = controls.closest("form").querySelector("[data-daily-schedule-date]")?.value;
      return date ? { start: 0, end: blocks.length, date, ordinal: 0, blocks, root } : null;
    }

    const position = editor.model.document.selection.getFirstPosition();
    if (!position) return null;
    let ancestor = position.parent;
    while (ancestor && ancestor.parent !== root) ancestor = ancestor.parent;
    const cursorIndex = blocks.indexOf(ancestor);
    if (cursorIndex < 0) return null;

    const headings = blocks
      .map((block, index) => ({ index, text: nodeText(block).trim() }))
      .filter(({ text }) => dayPattern.test(text));
    const ordinal = headings.findLastIndex(({ index }) => index <= cursorIndex);
    if (ordinal < 0) return null;
    const start = headings[ordinal].index;
    if (blocks.slice(start + 1, cursorIndex + 1).some((block) =>
      /^savait[ėe]\s*[-–—№#]/i.test(nodeText(block).trim())
    )) return null;
    const end = ordinal + 1 < headings.length ? headings[ordinal + 1].index : blocks.length;
    const date = window.scheduleMarkerMainContext?.dayDates?.[ordinal] || null;
    return { start, end, date, ordinal, blocks, root };
  }

  function markerIndex(day, kind) {
    for (let index = day.start; index < day.end; index += 1) {
      if (markerKind(day.blocks[index]) === kind) return index;
    }
    return -1;
  }

  function allMarkerIndices(blocks, kind) {
    return blocks.flatMap((block, index) => markerKind(block) === kind ? [index] : []);
  }

  function insertAtDay(editor, day, kind) {
    let offset = day.start + (day.start === 0 ? 0 : 1);
    while (offset < day.end && markerKind(day.blocks[offset])) offset += 1;
    editor.model.change((writer) => {
      const paragraph = writer.createElement("paragraph");
      writer.insert(paragraph, day.root, offset);
      writer.insertText(tokens[kind], paragraph, 0);
      writer.setSelection(paragraph, "end");
    });
  }

  function removeAtDay(editor, day, kind) {
    const index = markerIndex(day, kind);
    if (index < 0) return false;
    editor.model.change((writer) => {
      writer.remove(day.blocks[index]);
      const neighbour = day.root.getChild(Math.min(index, day.root.childCount - 1));
      if (neighbour) writer.setSelection(neighbour, "end");
    });
    return true;
  }

  function periodContext(controls) {
    return controls.dataset.markerControls === "main"
      ? window.scheduleMarkerMainContext || {}
      : window.scheduleMarkerDailyContext || {};
  }

  function toggleKartika(editor, controls, day) {
    if (removeAtDay(editor, day, "kartika_start")) {
      periodContext(controls).kartikaStart = null;
      return;
    }
    if (removeAtDay(editor, day, "kartika_end")) {
      periodContext(controls).kartikaEnd = null;
      return;
    }

    const localStarts = allMarkerIndices(day.blocks, "kartika_start");
    const localEnds = allMarkerIndices(day.blocks, "kartika_end");
    const remote = periodContext(controls);
    const startIndex = localStarts[0];
    const previousPeriodFinished = Boolean(
      day.date && remote.kartikaEnd && remote.kartikaEnd < day.date
    );
    const startDate = startIndex === undefined && !previousPeriodFinished
      ? remote.kartikaStart : null;
    const hasStart = startIndex !== undefined || Boolean(startDate);
    const hasEnd = localEnds.length > 0 || Boolean(
      startIndex === undefined && !previousPeriodFinished && remote.kartikaEnd
    );

    if (!hasStart) {
      insertAtDay(editor, day, "kartika_start");
      return;
    }
    if (hasEnd) {
      alert("У Картики уже указаны начало и конец. Сначала снимите одну из этих отметок.");
      return;
    }
    if (startIndex !== undefined && day.start <= startIndex) {
      alert("Конец Картики должен быть позже её начала.");
      return;
    }
    if (startDate && (!day.date || day.date <= startDate)) {
      alert(day.date ? "Конец Картики должен быть позже её начала." : "Не удалось определить дату этого дня. Проверьте заголовки недель и дней.");
      return;
    }
    insertAtDay(editor, day, "kartika_end");
  }

  function refreshButtons(editor, controls) {
    const day = selectedDay(editor, controls);
    controls.querySelectorAll("[data-marker-button]").forEach((button) => {
      const kind = button.dataset.markerButton;
      const active = Boolean(day && (kind === "kartika"
        ? markerIndex(day, "kartika_start") >= 0 || markerIndex(day, "kartika_end") >= 0
        : markerIndex(day, kind) >= 0));
      button.setAttribute("aria-pressed", String(active));
    });
  }

  document.querySelectorAll("[data-marker-controls]").forEach((controls) => {
    const updateStickyActions = () => {
      const form = controls.closest("form");
      controls.classList.toggle(
        "is-scrolled",
        window.innerWidth <= 720 && !form.closest("[hidden]") && form.getBoundingClientRect().top < -25
      );
    };
    window.addEventListener("scroll", updateStickyActions, { passive: true });
    controls.closest(".main-post-editor")?.addEventListener("scroll", updateStickyActions, { passive: true });
    window.addEventListener("resize", updateStickyActions);
    controls.querySelectorAll("[data-marker-button]").forEach((button) => {
      button.addEventListener("pointerdown", (event) => event.preventDefault());
      button.addEventListener("click", () => {
        const editor = getEditor(controls);
        if (!editor) {
          alert("Редактор ещё загружается. Повторите попытку через секунду.");
          return;
        }
        const day = selectedDay(editor, controls);
        if (!day) {
          alert("Поставьте курсор в текст нужного дня и нажмите кнопку ещё раз.");
          return;
        }
        const kind = button.dataset.markerButton;
        if (kind === "kartika") toggleKartika(editor, controls, day);
        else if (!removeAtDay(editor, day, kind)) insertAtDay(editor, day, kind);
        refreshButtons(editor, controls);
        editor.editing.view.focus();
      });
    });
    controls.closest("form")?.addEventListener("keyup", () => {
      const editor = getEditor(controls);
      if (editor) refreshButtons(editor, controls);
    });
    controls.closest("form")?.addEventListener("click", (event) => {
      if (event.target.closest("[data-marker-button]")) return;
      const editor = getEditor(controls);
      if (editor) refreshButtons(editor, controls);
    });
  });
});
