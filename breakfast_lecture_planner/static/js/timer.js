(() => {
  const source = document.querySelector("#elem1");
  const timers = [...document.querySelectorAll(".countdown-timer")];
  if (!source || !timers.length) return;

  const initialRemaining = Math.max(0, Number(source.dataset.registrationRemainingMs) || 0);
  const startedAt = performance.now();
  const circumference = 2 * Math.PI * 41;
  let intervalId;
  let expired = false;

  function update() {
    const remaining = Math.max(0, initialRemaining - (performance.now() - startedAt));
    const secondsLeft = Math.ceil(remaining / 1000);
    const values = [
      Math.floor(secondsLeft / 86400),
      Math.floor((secondsLeft % 86400) / 3600),
      Math.floor((secondsLeft % 3600) / 60),
      secondsLeft % 60,
    ];

    timers.forEach((timer) => {
      const units = timer.querySelectorAll(".time-unit");
      units.forEach((unit, index) => {
        const number = unit.querySelector(".number");
        const circle = unit.querySelector(".fg-circle");
        if (number) number.textContent = values[index];
        if (circle) {
          const maximum = index === 0 ? 7 : index === 1 ? 24 : 60;
          const progress = 1 - Math.min(values[index] / maximum, 1);
          circle.style.strokeDasharray = `${progress * circumference} ${circumference}`;
        }
      });
    });

    if (remaining <= 0 && !expired) {
      expired = true;
      if (intervalId) clearInterval(intervalId);
      window.dispatchEvent(new Event("lunch-registration-expired"));
    }
  }

  update();
  if (!expired) intervalId = window.setInterval(update, 250);
})();
