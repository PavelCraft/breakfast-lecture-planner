const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function mentionText(value) {
  let mention = { id: value };
  return {
    data: value,
    getAttribute(name) { return name === "mention" ? mention : null; },
    removeMention() { mention = null; },
  };
}

test("a selected hashtag becomes ordinary text and completes the current mention", () => {
  const domListeners = {};
  let changeListener = null;
  let selectionListener = null;
  let selectionOffset = "13 Lapkričio Įvykis #Pasninkas".length;
  const text = mentionText("13 Lapkričio Įvykis #Pasninkas");
  const paragraph = {
    children: [text],
    getChildren() { return this.children.values(); },
  };
  const root = {
    children: [paragraph],
    getChildren() { return this.children.values(); },
  };
  text.parent = paragraph;
  paragraph.parent = root;
  let completedMentions = 0;
  const editor = {
    model: {
      document: {
        getRoot() { return root; },
        selection: {
          getFirstPosition() { return { parent: paragraph, offset: selectionOffset }; },
          on(name, callback) { if (name === "change:range") selectionListener = callback; },
        },
        on(name, callback) { if (name === "change:data") changeListener = callback; },
      },
      change(callback) {
        callback({ removeAttribute(name, node) { if (name === "mention") node.removeMention(); } });
      },
    },
    editing: {
      view: {
        document: {
          fire(name, data) {
            if (name === "keydown" && data.keyCode === 27) completedMentions += 1;
          },
        },
      },
    },
  };
  const sandbox = {
    document: {
      addEventListener(name, callback) { domListeners[name] = callback; },
    },
    window: {
      editors: { id_content: editor },
      setTimeout(callback) { callback(); },
    },
    WeakSet,
    Set,
  };
  const source = fs.readFileSync(path.join(__dirname, "..", "hashtag_mentions.js"), "utf8");
  vm.runInNewContext(source, sandbox);
  domListeners.DOMContentLoaded();

  assert.equal(text.getAttribute("mention"), null);
  assert.equal(text.data, "13 Lapkričio Įvykis #Pasninkas");
  assert.ok(completedMentions > 0);

  const completedBeforeUnknownHashtag = completedMentions;
  text.data = "13 Lapkričio Įvykis #Pasninkass";
  selectionOffset = text.data.length;
  changeListener();
  selectionListener();
  assert.equal(completedMentions, completedBeforeUnknownHashtag);

  text.data = "13 Lapkričio Įvykis #Pasninkas #";
  selectionOffset = text.data.length;
  changeListener();
  selectionListener();
  assert.equal(completedMentions, completedBeforeUnknownHashtag);
});
