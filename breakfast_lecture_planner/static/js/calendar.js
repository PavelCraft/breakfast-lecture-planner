document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-schedule-calendar]").forEach((calendar) => {
    const monthSelect = calendar.querySelector("[data-calendar-month]");
    const yearSelect = calendar.querySelector("[data-calendar-year]");
    const week = calendar.querySelector("[data-calendar-week]");
    const kartikaBar = calendar.querySelector("[data-calendar-kartika-bar]");
    const schedules = calendar.querySelector("[data-calendar-schedules]");
    const categories = Array.from(calendar.querySelectorAll("[data-calendar-category]"));
    const scheduleUrl = calendar.dataset.scheduleUrl;
    const editIconUrl = calendar.dataset.editIcon;
    const canEdit = calendar.dataset.canEdit === "true";
    const dailyEditorContainer = calendar.querySelector("[data-daily-schedule-editor]");
    const dailyScheduleForm = calendar.querySelector("[data-daily-schedule-form]");
    const dailyScheduleDate = calendar.querySelector("[data-daily-schedule-date]");
    const dailyScheduleError = calendar.querySelector("[data-daily-schedule-error]");
    const scheduleCache = new Map();

    const locale = calendar.dataset.locale || "en";
    const weekdayNames = calendar.dataset.weekdaysShort.split("|");
    const weekdayNamesLong = calendar.dataset.weekdaysLong.split("|");
    const emptyMessage = locale.startsWith("lt")
      ? "Šiai dienai programa dar nepaskelbta."
      : "The schedule for this day has not been published yet.";
    const categoryColors = {
      ekadashi: "#c92f35",
      fast: "#c98a24",
      holiday: "#3da44a",
      saints: "#2d8884",
    };
    const softCategoryColors = {
      ekadashi: "#f9dfdf",
      fast: "#f7ead3",
      holiday: "#e2f2e5",
      saints: "#dcefee",
    };
    const categoryNames = locale.startsWith("lt") ? {
      ekadashi: "Ekadašis", fast: "Pasninkas", holiday: "Šventė", saints: "Šventųjų dienos",
    } : {
      ekadashi: "Ekadashi", fast: "Fasting", holiday: "Holiday", saints: "Saints' days",
    };

    let selectedDate = new Date();
    let editingCard = null;
    let weekVersion = 0;
    let renderVersion = 0;
    let cacheGeneration = 0;
    let lastRenderedDate = null;
    let navigationAnimations = [];
    let navigationOverlays = [];
    selectedDate.setHours(12, 0, 0, 0);

    const copyDate = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12);
    const shiftedDate = (date, days) => {
      const shifted = copyDate(date);
      shifted.setDate(shifted.getDate() + days);
      return shifted;
    };
    const dateKey = (date) => [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, "0"),
      String(date.getDate()).padStart(2, "0"),
    ].join("-");

    const initialDateKey = new URL(window.location.href).searchParams.get("calendar_date");
    if (/^\d{4}-\d{2}-\d{2}$/.test(initialDateKey || "")) {
      const [year, month, day] = initialDateKey.split("-").map(Number);
      const requestedDate = new Date(year, month - 1, day, 12);
      if (dateKey(requestedDate) === initialDateKey) selectedDate = requestedDate;
    }

    function rememberSelectedDate() {
      const url = new URL(window.location.href);
      url.searchParams.set("calendar_date", dateKey(selectedDate));
      window.history.replaceState(window.history.state, "", url);
      document.querySelectorAll('.language-switcher form input[name="next"]').forEach(input => {
        input.value = url.pathname + url.search + url.hash;
      });
    }

    async function loadSchedule(date, forceRefresh = false) {
      const key = dateKey(date);
      if (!forceRefresh && scheduleCache.has(key)) return scheduleCache.get(key);
      const generation = cacheGeneration;
      try {
        const response = await fetch(`${scheduleUrl}?date=${encodeURIComponent(key)}`, {
          cache: "no-store",
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) throw new Error("Не удалось загрузить расписание");
        const data = await response.json();
        if (generation === cacheGeneration) scheduleCache.set(key, data);
        return data;
      } catch (error) {
        console.error(error);
        return { date: key, content: "", exists: false, error: error.message };
      }
    }

    function createDateButton(date, index) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "schedule-calendar__date";
      button.dataset.date = dateKey(date);
      button.setAttribute("aria-label", date.toLocaleDateString(locale, { dateStyle: "full" }));
      button.setAttribute("aria-pressed", String(dateKey(date) === dateKey(selectedDate)));
      const distance = Math.round((date - selectedDate) / 86400000);
      if (distance === 0) button.classList.add("is-selected");
      if (Math.abs(distance) === 1) button.classList.add("is-neighbour");
      button.innerHTML = `
        <span class="schedule-calendar__weekday">${weekdayNames[index % 7]}</span>
        <span class="schedule-calendar__date-number">${date.getDate()}</span>
      `;
      if (dateKey(date) === dateKey(new Date())) {
        button.classList.add("is-today");
      }
      button.addEventListener("click", () => {
        selectedDate = copyDate(date);
        render(true);
      });
      return button;
    }

    function renderWeek() {
      const version = ++weekVersion;
      week.replaceChildren();
      kartikaBar.hidden = true;
      const requests = [];
      for (let offset = -3; offset <= 3; offset += 1) {
        const date = shiftedDate(selectedDate, offset);
        const button = createDateButton(date, (date.getDay() + 6) % 7);
        week.append(button);
        requests.push(loadSchedule(date).then((data) => {
          if (!button.isConnected || version !== weekVersion) return false;
          const colors = (data.categories || []).map((kind) => categoryColors[kind]).filter(Boolean);
          if (colors.length === 1) {
            button.style.setProperty("--date-ring", `linear-gradient(${colors[0]}, ${colors[0]})`);
          } else if (colors.length > 1) {
            const step = 100 / colors.length;
            button.style.setProperty("--date-ring", `conic-gradient(from 270deg, ${colors.map((color, i) => `${color} ${i * step}% ${(i + 1) * step}%`).join(", ")})`);
          }
          if (colors.length) {
            const dots = document.createElement("span");
            dots.className = "schedule-calendar__date-dots";
            colors.forEach((color) => {
              const dot = document.createElement("span");
              dot.className = "schedule-calendar__date-dot";
              dot.style.setProperty("--dot-color", color);
              dots.append(dot);
            });
            button.append(dots);
          }
          return Boolean(data.kartika);
        }));
      }
      Promise.all(requests).then((active) => {
        if (version !== weekVersion) return;
        const visible = window.matchMedia("(max-width: 800px)").matches ? active.slice(1, 6) : active;
        const first = visible.indexOf(true);
        const last = visible.lastIndexOf(true);
        kartikaBar.hidden = first < 0;
        if (first >= 0) {
          kartikaBar.style.left = `${((first + 0.5) / visible.length) * 100}%`;
          kartikaBar.style.right = `${((visible.length - last - 0.5) / visible.length) * 100}%`;
        }
      });
    }

    async function hydrateScheduleCard(card, date) {
      const data = await loadSchedule(date);
      if (!card.isConnected || schedules.querySelector(".schedule-calendar__schedule-card") !== card) return;
      const body = card.querySelector(".schedule-calendar__schedule-body");
      body.classList.remove("schedule-calendar__schedule-body--empty");
      body.innerHTML = data.exists && data.content.trim() ? data.content : "";
      if (!body.innerHTML) {
        body.textContent = data.error || emptyMessage;
        body.classList.add("schedule-calendar__schedule-body--empty");
      }
      const header = card.querySelector(".schedule-calendar__schedule-header");
      const priorLabels = header.querySelector(".schedule-calendar__event-labels");
      priorLabels?.remove();
      const kinds = (data.categories || []).filter((kind) => categoryColors[kind]);
      if (kinds.length === 1) {
        header.style.setProperty("--schedule-header-background", softCategoryColors[kinds[0]]);
      } else if (kinds.length > 1) {
        const stripe = 48;
        header.style.setProperty(
          "--schedule-header-background",
          `repeating-linear-gradient(135deg, ${kinds.map((kind, index) => `${softCategoryColors[kind]} ${index * stripe}px ${(index + 1) * stripe}px`).join(", ")})`
        );
      }
      if (kinds.length) {
        const labels = document.createElement("span");
        labels.className = "schedule-calendar__event-labels";
        kinds.forEach((kind) => {
          const label = document.createElement("span");
          label.className = "schedule-calendar__event-label";
          label.style.setProperty("--event-color", categoryColors[kind]);
          label.textContent = categoryNames[kind];
          labels.append(label);
        });
        header.append(labels);
      }
    }

    function waitForDailyEditor() {
      return new Promise((resolve) => {
        let attempts = 0;
        const findEditor = () => {
          const editor = window.editors?.["id_daily-content"];
          if (editor || attempts >= 40) {
            resolve(editor || null);
            return;
          }
          attempts += 1;
          window.setTimeout(findEditor, 50);
        };
        findEditor();
      });
    }

    async function closeDailyEditor() {
      if (!dailyEditorContainer) return;
      dailyEditorContainer.hidden = true;
      dailyScheduleError.hidden = true;
      if (editingCard?.isConnected) {
        editingCard.querySelector(".schedule-calendar__schedule-content").hidden = false;
      }
      schedules.after(dailyEditorContainer);
      editingCard = null;
      try {
        await window.scheduleEditLock?.release("daily-schedule");
      } catch (error) {
        console.error("Could not release schedule edit lock", error);
      }
    }

    async function openDailyEditor(card, date) {
      if (!dailyEditorContainer) return;
      try {
        await window.scheduleEditLock.acquire("daily-schedule");
      } catch (error) {
        alert(error.message);
        return;
      }
      const editor = await waitForDailyEditor();
      if (!editor || !card.isConnected) {
        console.error("CKEditor для дневного расписания не инициализирован");
        await window.scheduleEditLock.release("daily-schedule");
        return;
      }
      const data = await loadSchedule(date, true);
      if (data.error) {
        await window.scheduleEditLock.release("daily-schedule");
        alert(data.error);
        return;
      }
      const body = card.querySelector(".schedule-calendar__schedule-body");
      body.innerHTML = data.exists ? data.content : "";
      editor.setData(data.exists ? data.raw_content : "");
      dailyScheduleDate.value = dateKey(date);
      window.scheduleMarkerDailyContext = {
        kartikaStart: data.kartika_start,
        kartikaEnd: data.kartika_end,
      };
      dailyScheduleError.hidden = true;
      card.querySelector(".schedule-calendar__schedule-content").hidden = true;
      card.querySelector(".schedule-calendar__schedule-header").after(dailyEditorContainer);
      dailyEditorContainer.hidden = false;
      editingCard = card;
      editor.editing.view.focus();
    }

    function createScheduleCard(date) {
      const article = document.createElement("article");
      article.className = "schedule-calendar__schedule-card";
      article.dataset.date = dateKey(date);
      const editButton = canEdit
        ? `<button class="schedule-calendar__edit-button" type="button" data-daily-schedule-edit aria-label="Редактировать расписание" title="Редактировать"><img src="${editIconUrl}" alt=""></button>`
        : "";
      article.innerHTML = `
        <header class="schedule-calendar__schedule-header">
          <h3>${date.getDate()} d. ${weekdayNamesLong[date.getDay()]}</h3>
          ${editButton}
        </header>
        <div class="schedule-calendar__schedule-content">
          <div class="schedule-calendar__schedule-body"></div>
        </div>
      `;
      article.querySelector("[data-daily-schedule-edit]")?.addEventListener("click", () => {
        openDailyEditor(article, date);
      });
      hydrateScheduleCard(article, date);
      return article;
    }

    function renderSchedules() {
      if (editingCard) closeDailyEditor();
      const selectedCard = createScheduleCard(selectedDate);
      schedules.replaceChildren(selectedCard);
    }

    function slideReplacement(container, incoming, outgoing, distance) {
      if (!incoming || !outgoing) return;
      outgoing.setAttribute("aria-hidden", "true");
      outgoing.inert = true;
      Object.assign(outgoing.style, {
        position: "absolute",
        left: `${incoming.offsetLeft}px`,
        top: `${incoming.offsetTop}px`,
        width: `${incoming.offsetWidth}px`,
        height: `${incoming.offsetHeight}px`,
        margin: "0",
        pointerEvents: "none",
        zIndex: "2",
      });
      container.append(outgoing);
      navigationOverlays.push(outgoing);
      const options = { duration: 1000, easing: "cubic-bezier(.42, 0, .58, 1)" };
      navigationAnimations.push(incoming.animate([
        { transform: `translateX(${distance}px)`, opacity: 0.8 },
        { transform: "translateX(0)", opacity: 1 },
      ], options));
      const outgoingAnimation = outgoing.animate([
        { transform: "translateX(0)", opacity: 1 },
        { transform: `translateX(${-distance}px)`, opacity: 0 },
      ], options);
      navigationAnimations.push(outgoingAnimation);
      outgoingAnimation.finished.then(() => outgoing.remove(), () => outgoing.remove());
    }

    function render(updateAddress = false) {
      const version = ++renderVersion;
      const daysMoved = lastRenderedDate
        ? Math.round((selectedDate - lastRenderedDate) / 86400000)
        : 0;
      const animateNavigation = daysMoved && updateAddress &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches && !editingCard;
      navigationAnimations.forEach((animation) => animation.cancel());
      navigationOverlays.forEach((overlay) => overlay.remove());
      navigationAnimations = [];
      navigationOverlays = [];
      const outgoingWeek = animateNavigation ? week.cloneNode(true) : null;
      const outgoingCard = animateNavigation
        ? schedules.querySelector(".schedule-calendar__schedule-card")?.cloneNode(true)
        : null;
      lastRenderedDate = copyDate(selectedDate);
      if (updateAddress) rememberSelectedDate();
      monthSelect.value = String(selectedDate.getMonth());
      if (!Array.from(yearSelect.options).some((option) => Number(option.value) === selectedDate.getFullYear())) {
        yearSelect.add(new Option(String(selectedDate.getFullYear()), String(selectedDate.getFullYear())));
      }
      yearSelect.value = String(selectedDate.getFullYear());
      renderWeek();
      loadSchedule(selectedDate).then((data) => {
        if (version !== renderVersion || dateKey(selectedDate) !== data.date) return;
        categories.forEach((category) => {
          category.classList.toggle("is-active", (data.categories || []).includes(category.dataset.calendarCategory));
        });
      });
      renderSchedules();
      if (animateNavigation) {
        const direction = Math.sign(daysMoved);
        const weekDistance = direction * Math.min(Math.abs(daysMoved), 7) * week.clientWidth / 7;
        slideReplacement(week.parentElement, week, outgoingWeek, weekDistance);
        const card = schedules.querySelector(".schedule-calendar__schedule-card");
        slideReplacement(schedules, card, outgoingCard, direction * Math.min(150, schedules.clientWidth / 4));
      }
    }

    function changeDate(days) {
      selectedDate = shiftedDate(selectedDate, days);
      render(true);
    }

    dailyScheduleForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitButton = dailyScheduleForm.querySelector('[type="submit"]');
      submitButton.disabled = true;
      dailyScheduleError.hidden = true;
      try {
        const formData = new FormData(dailyScheduleForm);
        formData.append("edit_lock_token", window.scheduleEditLock.token);
        const response = await fetch(scheduleUrl, {
          method: "POST",
          body: formData,
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Не удалось сохранить расписание");
        scheduleCache.set(data.date, { ...data, exists: true });
        if (editingCard?.isConnected) {
          const body = editingCard.querySelector(".schedule-calendar__schedule-body");
          body.classList.remove("schedule-calendar__schedule-body--empty");
          body.innerHTML = data.content;
        }
        await closeDailyEditor();
        window.notifyScheduleUpdated({ mainContent: data.main_content });
      } catch (error) {
        dailyScheduleError.textContent = error.message;
        dailyScheduleError.hidden = false;
      } finally {
        submitButton.disabled = false;
      }
    });
    calendar.querySelector("[data-daily-schedule-cancel]")?.addEventListener("click", closeDailyEditor);
    calendar.querySelector("[data-calendar-week-previous]").addEventListener("click", () => changeDate(-7));
    calendar.querySelector("[data-calendar-week-next]").addEventListener("click", () => changeDate(7));
    calendar.querySelector("[data-calendar-day-previous]").addEventListener("click", () => changeDate(-1));
    calendar.querySelector("[data-calendar-day-next]").addEventListener("click", () => changeDate(1));
    monthSelect.addEventListener("change", () => {
      selectedDate = new Date(selectedDate.getFullYear(), Number(monthSelect.value), 1, 12);
      render(true);
    });
    yearSelect.addEventListener("change", () => {
      const year = Number(yearSelect.value);
      const day = Math.min(selectedDate.getDate(), new Date(year, selectedDate.getMonth() + 1, 0).getDate());
      selectedDate = new Date(year, selectedDate.getMonth(), day, 12);
      render(true);
    });

    let swipeStartX = null;
    week.addEventListener("touchstart", (event) => {
      swipeStartX = event.changedTouches[0].screenX;
    }, { passive: true });
    week.addEventListener("touchend", (event) => {
      if (swipeStartX === null) return;
      const movement = event.changedTouches[0].screenX - swipeStartX;
      swipeStartX = null;
      if (Math.abs(movement) > 45) changeDate(movement < 0 ? 1 : -1);
    }, { passive: true });

    const refreshScheduleData = () => {
      cacheGeneration += 1;
      scheduleCache.clear();
      render();
    };
    window.addEventListener("schedule-data-updated", refreshScheduleData);
    window.addEventListener("storage", (event) => {
      if (event.key === "schedule-data-updated") refreshScheduleData();
    });
    window.matchMedia("(max-width: 800px)").addEventListener("change", renderWeek);

    render();
  });
});
