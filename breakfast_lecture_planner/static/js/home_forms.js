(() => {
  const dialog = document.querySelector('[data-home-form-dialog]');
  if (!dialog) return;

  const forms = {
    lunch: dialog.querySelector('[data-home-form="lunch"]'),
    feedback: dialog.querySelector('[data-home-form="feedback"]'),
  };
  const panels = Object.fromEntries(
    [...dialog.querySelectorAll('[data-home-form-panel]')].map(panel => [panel.dataset.homeFormPanel, panel])
  );
  const registrationDeadlineAt = performance.now() +
    Math.max(0, Number(dialog.dataset.registrationRemainingMs) || 0);
  let registrationClosedByServer = false;
  let previousBodyOverflow = '';

  function syncLunchAvailability() {
    const closed = registrationClosedByServer || performance.now() >= registrationDeadlineAt;
    const notice = dialog.querySelector('[data-home-lunch-closed-notice]');
    if (notice) notice.hidden = !closed;
    if (forms.lunch) forms.lunch.hidden = closed;
    return closed;
  }

  window.addEventListener('lunch-registration-expired', () => {
    registrationClosedByServer = true;
    syncLunchAvailability();
  });
  syncLunchAvailability();

  function showPanel(name) {
    for (const [key, panel] of Object.entries(panels)) panel.hidden = key !== name;
    const title = panels[name].querySelector('h2');
    if (title) {
      title.id ||= `home-form-title-${name}`;
      dialog.setAttribute('aria-labelledby', title.id);
    }
  }

  function openForm(name) {
    if (!panels[name]) return;
    if (name === 'lunch') syncLunchAvailability();
    showPanel(name);
    if (!dialog.open) {
      previousBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      dialog.showModal();
    }
  }

  function closeForm() {
    if (dialog.open) dialog.close();
  }

  dialog.addEventListener('close', () => {
    document.body.style.overflow = previousBodyOverflow;
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) closeForm();
  });
  dialog.querySelectorAll('[data-home-form-close]').forEach(button => {
    button.addEventListener('click', closeForm);
  });
  dialog.querySelectorAll('[data-home-form-switch]').forEach(button => {
    button.addEventListener('click', () => openForm(button.dataset.homeFormSwitch));
  });

  const paths = {
    [new URL(dialog.dataset.lunchUrl, window.location.href).pathname]: 'lunch',
    [new URL(dialog.dataset.feedbackUrl, window.location.href).pathname]: 'feedback',
  };
  document.addEventListener('click', event => {
    const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (!link || event.defaultPrevented || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, window.location.href);
    const name = url.origin === window.location.origin ? paths[url.pathname] : null;
    if (!name) return;
    event.preventDefault();
    openForm(name);
  });

  const portions = forms.lunch?.querySelector('[name="lunch-portions"]');
  function syncPortions() {
    if (!portions) return;
    const value = Math.max(1, Math.min(15, Number(portions.value) || 1));
    portions.value = value;
    dialog.querySelector('[data-portions-minus]').disabled = value <= 1;
    dialog.querySelector('[data-portions-plus]').disabled = value >= 15;
  }
  dialog.querySelector('[data-portions-minus]')?.addEventListener('click', () => {
    portions.value = Number(portions.value) - 1;
    syncPortions();
  });
  dialog.querySelector('[data-portions-plus]')?.addEventListener('click', () => {
    portions.value = Number(portions.value) + 1;
    syncPortions();
  });
  portions?.addEventListener('change', syncPortions);
  syncPortions();

  function clearErrors(form) {
    const box = form.querySelector('[data-form-errors]');
    box.hidden = true;
    box.replaceChildren();
    form.querySelectorAll('[aria-invalid="true"]').forEach(field => field.removeAttribute('aria-invalid'));
  }

  function showErrors(form, errors) {
    const box = form.querySelector('[data-form-errors]');
    const list = document.createElement('ul');
    for (const [name, messages] of Object.entries(errors)) {
      const field = form.elements.namedItem(`${form.dataset.homeForm}-${name}`);
      if (field && field instanceof HTMLElement) field.setAttribute('aria-invalid', 'true');
      for (const message of messages) {
        const item = document.createElement('li');
        item.textContent = name === 'captcha' ? dialog.dataset.captchaError : message;
        list.append(item);
      }
    }
    box.append(list);
    box.hidden = false;
    box.scrollIntoView({ block: 'nearest' });
  }

  function captchaToken(action) {
    return new Promise((resolve, reject) => {
      if (!window.grecaptcha || !dialog.dataset.captchaKey) {
        reject(new Error(dialog.dataset.captchaError));
        return;
      }
      window.grecaptcha.ready(() => {
        window.grecaptcha.execute(dialog.dataset.captchaKey, { action }).then(resolve, reject);
      });
    });
  }

  for (const [name, form] of Object.entries(forms)) {
    if (!form) continue;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (name === 'lunch' && syncLunchAvailability()) return;
      clearErrors(form);
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const action = name === 'lunch' ? 'lunch_registration' : 'feedback';
        form.querySelector('[data-captcha-token]').value = await captchaToken(action);
        const response = await fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: new FormData(form),
        });
        const result = await response.json();
        if (response.ok && result.success) {
          form.reset();
          if (name === 'lunch') syncPortions();
          showPanel('success');
          dialog.querySelectorAll('[data-home-form-success]').forEach(message => {
            message.hidden = message.dataset.homeFormSuccess !== name;
          });
        } else if (result.closed) {
          registrationClosedByServer = true;
          syncLunchAvailability();
        } else {
          showErrors(form, result.errors || { __all__: [dialog.dataset.networkError] });
        }
      } catch (error) {
        showErrors(form, { __all__: [error.message || dialog.dataset.networkError] });
      } finally {
        form.querySelector('[data-captcha-token]').value = '';
        submit.disabled = false;
      }
    });
  }

  const requested = new URL(window.location.href).searchParams.get('open_form');
  if (requested === 'lunch' || requested === 'feedback') openForm(requested);
})();
