(() => {
  const scene = document.querySelector('[data-home-scene]');
  const editor = document.querySelector('[data-home-scene-editor]');
  const openButton = document.querySelector('[data-scene-open]');
  const initial = document.getElementById('home-scene-layout');
  if (!scene || !initial) return;

  if (new URLSearchParams(window.location.search).has('scene_preview')) {
    window.addEventListener('message', event => {
      if (event.origin !== window.location.origin || event.source !== window.parent) return;
      if (event.data?.type !== 'home-scene-preview') return;
      for (const [name, value] of Object.entries(event.data.values)) {
        const property = {
          background_height: '--scene-bg-height', background_y: '--scene-bg-y',
          object_x: '--scene-object-x', object_y: '--scene-object-y',
          object_width: '--scene-object-width'
        }[name];
        const unit = name === 'object_x' ? '%' : 'px';
        if (property && Number.isFinite(value)) scene.style.setProperty(property, `${value}${unit}`);
      }
    });
    window.parent.postMessage({ type: 'home-scene-preview-ready' }, window.location.origin);
    window.addEventListener('load', () => {
      const object = scene.querySelector('.home-scene__object');
      const sceneTop = scene.getBoundingClientRect().top + window.scrollY;
      const objectTop = object ? object.getBoundingClientRect().top + window.scrollY : sceneTop;
      window.scrollTo(0, Math.max(0, Math.min(sceneTop, objectTop) - 32));
    });
    return;
  }
  if (!editor || !openButton) return;

  let published = JSON.parse(initial.textContent);
  let draft = structuredClone(published);
  let preset = 'computer';
  const previewWidths = {
    watch: 320, smartphone: 390, shovel: 700,
    tablet: 1024, computer: 1440, tv: 1920
  };
  const units = {
    background_height: 'px', background_y: 'px', object_x: '%',
    object_y: 'px', object_width: 'px'
  };
  const properties = {
    background_height: '--scene-bg-height', background_y: '--scene-bg-y',
    object_x: '--scene-object-x', object_y: '--scene-object-y',
    object_width: '--scene-object-width'
  };
  const message = editor.querySelector('[data-scene-message]');
  const preview = editor.querySelector('[data-scene-preview]');
  const previewViewport = editor.querySelector('[data-scene-preview-viewport]');

  function resizePreview() {
    const width = previewWidths[preset];
    const scale = Math.min(1, previewViewport.clientWidth / width);
    preview.style.width = `${width}px`;
    preview.style.transform = `scale(${scale})`;
    previewViewport.style.height = `${900 * scale}px`;
  }

  window.addEventListener('resize', () => {
    if (!editor.hidden) resizePreview();
  });

  function updatePreview() {
    if (!preview.contentWindow) return;
    preview.contentWindow.postMessage({ type: 'home-scene-preview', values: draft[preset] }, window.location.origin);
  }

  window.addEventListener('message', event => {
    if (event.origin === window.location.origin && event.source === preview.contentWindow &&
        event.data?.type === 'home-scene-preview-ready') updatePreview();
  });

  function apply(values) {
    for (const [name, property] of Object.entries(properties)) {
      scene.style.setProperty(property, `${values[name]}${units[name]}`);
    }
  }

  function restoreResponsiveStyles() {
    for (const property of Object.values(properties)) scene.style.removeProperty(property);
  }

  function showPreset(name) {
    preset = name;
    scene.dataset.preset = name;
    for (const button of editor.querySelectorAll('[data-scene-preset]')) {
      button.setAttribute('aria-pressed', String(button.dataset.scenePreset === name));
    }
    for (const input of editor.querySelectorAll('[data-scene-field]')) {
      input.value = draft[name][input.dataset.sceneField];
      editor.querySelector(`[data-scene-output="${input.dataset.sceneField}"]`).value = input.value + units[input.dataset.sceneField];
    }
    apply(draft[name]);
    resizePreview();
    updatePreview();
  }

  openButton.addEventListener('click', () => {
    draft = structuredClone(published);
    editor.hidden = false;
    openButton.hidden = true;
    scene.classList.add('home-scene--preview');
    if (!preview.src) {
      const url = new URL(window.location.href);
      url.searchParams.set('scene_preview', '1');
      preview.src = url.toString();
    }
    message.textContent = '';
    const width = window.innerWidth;
    showPreset(width <= 360 ? 'watch' : width <= 520 ? 'smartphone' :
      width <= 800 ? 'shovel' : width <= 1199 ? 'tablet' :
      width <= 1699 ? 'computer' : 'tv');
    editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  editor.querySelectorAll('[data-scene-preset]').forEach(button => {
    button.addEventListener('click', () => showPreset(button.dataset.scenePreset));
  });

  editor.querySelectorAll('[data-scene-field]').forEach(input => {
    input.addEventListener('input', () => {
      const field = input.dataset.sceneField;
      draft[preset][field] = Number(input.value);
      editor.querySelector(`[data-scene-output="${field}"]`).value = input.value + units[field];
      apply(draft[preset]);
      updatePreview();
    });
  });

  function close() {
    editor.hidden = true;
    openButton.hidden = false;
    scene.classList.remove('home-scene--preview');
    delete scene.dataset.preset;
    restoreResponsiveStyles();
  }

  editor.querySelector('[data-scene-cancel]').addEventListener('click', close);
  editor.querySelector('[data-scene-save]').addEventListener('click', async () => {
    const saveButton = editor.querySelector('[data-scene-save]');
    saveButton.disabled = true;
    message.textContent = 'Сохраняю…';
    try {
      const csrf = document.cookie.split('; ').find(part => part.startsWith('csrftoken='))?.split('=')[1];
      const response = await fetch(editor.dataset.saveUrl, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf || '') },
        body: JSON.stringify(draft)
      });
      if (!response.ok) throw new Error((await response.json()).error || 'Не удалось сохранить оформление.');
      published = structuredClone(draft);
      // Update responsive rules used after the editor closes without reloading the page.
      const style = document.getElementById('home-scene-published-style');
      if (style) style.textContent = buildPublishedCss(published);
      message.textContent = 'Оформление сохранено.';
      close();
    } catch (error) {
      message.textContent = error.message;
    } finally {
      saveButton.disabled = false;
    }
  });

  function buildPublishedCss(layout) {
    function rules(values) {
      return Object.entries(properties).map(([key, property]) => `${property}:${values[key]}${units[key]};`).join('');
    }
    return `.home-scene{${rules(layout.tv)}}` +
      `@media(max-width:1699px){.home-scene:not(.home-scene--preview){${rules(layout.computer)}}}` +
      `@media(max-width:1199px){.home-scene:not(.home-scene--preview){${rules(layout.tablet)}}}` +
      `@media(max-width:800px){.home-scene:not(.home-scene--preview){${rules(layout.shovel)}}}` +
      `@media(max-width:520px){.home-scene:not(.home-scene--preview){${rules(layout.smartphone)}}}` +
      `@media(max-width:360px){.home-scene:not(.home-scene--preview){${rules(layout.watch)}}}`;
  }
})();
