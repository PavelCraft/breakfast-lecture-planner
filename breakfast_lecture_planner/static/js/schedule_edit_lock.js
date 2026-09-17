(() => {
  const token = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  const scope = window.scheduleEditLockScope || "schedule";
  let owner = null;
  let heartbeat = null;
  const csrfToken = () => document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";

  async function request(action) {
    const body = new FormData();
    body.append("csrfmiddlewaretoken", csrfToken());
    body.append("action", action);
    body.append("token", token);
    body.append("scope", scope);
    const response = await fetch(window.scheduleEditLockUrl, {
      method: "POST", body, headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось изменить блокировку редактирования.");
    return data;
  }

  window.scheduleEditLock = {
    token,
    async acquire(nextOwner) {
      if (owner && owner !== nextOwner) throw new Error("Сначала сохраните изменения или выйдите из уже открытого режима редактирования.");
      await request("acquire");
      owner = nextOwner;
      window.clearInterval(heartbeat);
      heartbeat = window.setInterval(() => request("acquire").catch(console.error), 5 * 60 * 1000);
    },
    async release(currentOwner) {
      if (owner && owner !== currentOwner) return;
      try { await request("release"); } finally {
        owner = null;
        window.clearInterval(heartbeat);
        heartbeat = null;
      }
    },
  };

  window.notifyScheduleUpdated = (details = {}) => {
    const updatedAt = String(Date.now());
    window.dispatchEvent(new CustomEvent("schedule-data-updated", {
      detail: { updatedAt, ...details },
    }));
    localStorage.setItem("schedule-data-updated", updatedAt);
  };

  window.addEventListener("pagehide", () => {
    if (!owner) return;
    const body = new FormData();
    body.append("csrfmiddlewaretoken", csrfToken());
    body.append("action", "release");
    body.append("token", token);
    body.append("scope", scope);
    navigator.sendBeacon(window.scheduleEditLockUrl, body);
  });
})();
