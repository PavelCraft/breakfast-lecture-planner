document.addEventListener("DOMContentLoaded", () => {
  const tokens = [
    "#Ekadaši",
    "#Pasninkas",
    "#Šventės",
    "#ŠventųjųDienos",
    "#KartikaPradžia",
    "#KartikaPabaiga",
  ];
  const tokenSet = new Set(tokens.map((token) => token.toLocaleLowerCase()));
  const attached = new WeakSet();

  function nodeText(node) {
    if (typeof node?.data === "string") return node.data;
    if (!node?.getChildren) return "";
    return Array.from(node.getChildren(), nodeText).join("");
  }

  function mentionNodes(node, result = []) {
    if (node?.getAttribute && node.getAttribute("mention")) result.push(node);
    if (node?.getChildren) {
      for (const child of node.getChildren()) mentionNodes(child, result);
    }
    return result;
  }

  function makeMentionsPlainText(editor) {
    const mentions = mentionNodes(editor.model.document.getRoot());
    if (!mentions.length) return;
    editor.model.change((writer) => {
      mentions.forEach((node) => writer.removeAttribute("mention", node));
    });
  }

  function exactQueryAtCaret(editor) {
    const position = editor.model.document.selection.getFirstPosition();
    if (!position?.parent) return false;
    const beforeCaret = nodeText(position.parent).slice(0, position.offset);
    const query = beforeCaret.match(/#[^\s#]*$/u)?.[0] || "";
    return tokenSet.has(query.toLocaleLowerCase());
  }

  function finishCompletedMention(editor) {
    if (!exactQueryAtCaret(editor)) return;
    editor.editing?.view?.document?.fire?.("keydown", {
      keyCode: 27,
      preventDefault() {},
    });
  }

  function attach(editor) {
    if (!editor?.model?.document?.on || attached.has(editor)) return;
    attached.add(editor);
    let converting = false;
    const update = () => {
      if (converting) return;
      converting = true;
      makeMentionsPlainText(editor);
      converting = false;
      window.setTimeout(() => finishCompletedMention(editor), 0);
      window.setTimeout(() => finishCompletedMention(editor), 50);
    };
    update();
    editor.model.document.on("change:data", update);
    editor.model.document.selection?.on?.("change:range", update);
  }

  let attempts = 0;
  const findEditors = () => {
    Object.values(window.editors || {}).forEach(attach);
    attempts += 1;
    if (attempts < 100) window.setTimeout(findEditors, 100);
  };
  findEditors();
});
