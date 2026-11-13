const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function paragraph(value, name = "paragraph") {
  const node = {
    name,
    children: [{ data: value }],
    is(type, expected) { return type === "element" && expected === this.name; },
    getChildren() { return this.children.values(); },
  };
  node.children.forEach((child) => { child.parent = node; });
  return node;
}

function setup({ kartikaStart = null, kartikaEnd = null } = {}) {
  const listeners = {};
  let modelChangeListener = null;
  const buttons = new Map();
  const alerts = [];
  const form = {
    addEventListener() {},
    closest() { return null; },
    getBoundingClientRect() { return { top: 100 }; },
  };
  for (const kind of ["ekadashi", "fast", "holiday", "saints", "kartika"]) {
    const callbacks = {};
    buttons.set(kind, {
      dataset: { markerButton: kind },
      addEventListener(name, callback) { callbacks[name] = callback; },
      setAttribute() {},
      click() { callbacks.click(); },
    });
  }
  const controls = {
    dataset: { markerControls: "main" },
    querySelectorAll() { return Array.from(buttons.values()); },
    closest(selector) { return selector === "form" ? form : null; },
  };
  const root = {
    children: [
      paragraph("savaitė — 38", "heading2"),
      paragraph("17 d. Ketvirtadienis", "heading6"),
      paragraph("First day"),
      paragraph("18 d. Penktadienis", "heading6"),
      paragraph("Second day"),
      paragraph("19 d. Šeštadienis", "heading6"),
      paragraph("Third day"),
      paragraph("20 d. Sekmadienis", "heading6"),
      paragraph("Fourth day"),
    ],
    getChildren() { return this.children.values(); },
    getChild(index) { return this.children[index]; },
    get childCount() { return this.children.length; },
  };
  root.children.forEach((node) => { node.parent = root; });
  let selected = root.children[2];
  const writer = {
    createElement(name) { return paragraph("", name); },
    insert(node, parent, index) { node.parent = parent; parent.children.splice(index, 0, node); },
    insertText(value, node) {
      const child = { data: value, parent: node };
      node.children = [child];
    },
    remove(node) {
      if (node.parent === root) {
        root.children.splice(root.children.indexOf(node), 1);
      } else if (node.parent?.children) {
        node.parent.children.splice(node.parent.children.indexOf(node), 1);
      }
    },
    removeAttribute(name, node) {
      if (name === "mention") node.removeMention?.();
    },
    setSelection(node) { selected = node; },
  };
  const editor = {
    model: {
      document: {
        getRoot() { return root; },
        selection: { getFirstPosition() { return { parent: selected }; } },
        on(name, callback) { if (name === "change:data") modelChangeListener = callback; },
      },
      change(callback) { callback(writer); },
    },
    editing: { view: { focus() {} } },
  };
  const sandbox = {
    document: {
      addEventListener(name, callback) { listeners[name] = callback; },
      querySelectorAll(selector) { return selector === ".ck-balloon-panel" ? [] : [controls]; },
    },
    window: {
      editors: { id_content: editor },
      scheduleMarkerMainContext: {
        dayDates: ["2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20"],
        kartikaStart,
        kartikaEnd,
      },
      addEventListener() {},
      innerWidth: 1200,
      setTimeout(callback) { callback(); },
    },
    alert(message) { alerts.push(message); },
  };
  const source = fs.readFileSync(path.join(__dirname, "..", "calendar_markers.js"), "utf8");
  vm.runInNewContext(source, sandbox);
  listeners.DOMContentLoaded();
  return {
    buttons,
    root,
    alerts,
    setDay(index) { selected = root.children[index]; },
    insertMention(value) {
      let mentionData = { id: value };
      const mention = {
        data: value,
        parent: selected,
        getAttribute(name) { return name === "mention" ? mentionData : null; },
        removeMention() { mentionData = null; },
      };
      selected.children.push(mention);
      modelChangeListener();
      return mention;
    },
    addMentionTo(blockText, value) {
      const block = root.children.find((node) => node.children[0]?.data === blockText);
      block.children.push({
        data: value,
        parent: block,
        getAttribute(name) { return name === "mention" ? { id: value } : null; },
      });
    },
    triggerChange() { modelChangeListener(); },
  };
}

function values(root) {
  return root.children.map((node) => node.children.map((child) => child.data).join(""));
}

test("category buttons insert into the selected day and toggle off", () => {
  const ui = setup();
  ui.buttons.get("ekadashi").click();
  assert.deepEqual(values(ui.root).slice(1, 4), [
    "17 d. Ketvirtadienis", "#Ekadaši", "First day",
  ]);
  ui.buttons.get("fast").click();
  assert.equal(values(ui.root).filter((value) => value === "#Pasninkas").length, 1);
  ui.buttons.get("ekadashi").click();
  assert.equal(values(ui.root).includes("#Ekadaši"), false);
});

test("a hashtag selected in day content stays editable at the insertion point", () => {
  const ui = setup();
  const mention = ui.insertMention("#Šventės");
  assert.equal(values(ui.root).find((value) => value.includes("First day")), "First day#Šventės");
  assert.equal(mention.getAttribute("mention"), null);
});

test("several hashtags can be entered on the same line", () => {
  const ui = setup();
  const first = ui.insertMention("#Pasninkas");
  first.data += " ";
  const second = ui.insertMention("#Šventės");
  assert.equal(
    values(ui.root).find((value) => value.includes("First day")),
    "First day#Pasninkas #Šventės",
  );
  assert.equal(first.getAttribute("mention"), null);
  assert.equal(second.getAttribute("mention"), null);
});

test("a hashtag selected in a day heading is still moved into that day", () => {
  const ui = setup();
  ui.setDay(1);
  ui.insertMention("#Pasninkas");
  assert.deepEqual(values(ui.root).slice(1, 4), [
    "17 d. Ketvirtadienis", "#Pasninkas", "First day",
  ]);
});

test("an existing mention in another day is not moved after an unrelated edit", () => {
  const ui = setup();
  ui.addMentionTo("First day", "#Ekadaši");
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "Second day"));
  ui.triggerChange();
  assert.equal(values(ui.root).filter((value) => value.includes("#Ekadaši")).length, 1);
  assert.equal(values(ui.root).find((value) => value.includes("#Ekadaši")), "First day#Ekadaši");
});

test("Kartika starts in the selected day and ends only in a later one", () => {
  const ui = setup();
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("#KartikaPradžia"), true);
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("#KartikaPradžia"), false);
  ui.buttons.get("kartika").click();
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "Second day"));
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("#KartikaPabaiga"), true);
  assert.equal(ui.alerts.length, 0);
});

test("Kartika cannot end before its start", () => {
  const ui = setup();
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "Second day"));
  ui.buttons.get("kartika").click();
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "First day"));
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("#KartikaPabaiga"), false);
  assert.equal(ui.alerts.length, 1);
});

test("multiple non-overlapping Kartika periods can be added", () => {
  const ui = setup();
  for (const day of ["First day", "Second day", "Third day", "Fourth day"]) {
    ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === day));
    ui.buttons.get("kartika").click();
  }
  assert.equal(values(ui.root).filter((value) => value === "#KartikaPradžia").length, 2);
  assert.equal(values(ui.root).filter((value) => value === "#KartikaPabaiga").length, 2);
  assert.equal(ui.alerts.length, 0);
});

test("Kartika click sets a start when only a later remote start is present", () => {
  const ui = setup({ kartikaStart: "2026-09-18" });
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("#KartikaPradžia"), true);
  assert.equal(ui.alerts.length, 0);
});
