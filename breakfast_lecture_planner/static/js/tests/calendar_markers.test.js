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
  return node;
}

function setup() {
  const listeners = {};
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
    insertText(value, node) { node.children = [{ data: value }]; },
    remove(node) { root.children.splice(root.children.indexOf(node), 1); },
    setSelection(node) { selected = node; },
  };
  const editor = {
    model: {
      document: {
        getRoot() { return root; },
        selection: { getFirstPosition() { return { parent: selected }; } },
      },
      change(callback) { callback(writer); },
    },
    editing: { view: { focus() {} } },
  };
  const sandbox = {
    document: {
      addEventListener(name, callback) { listeners[name] = callback; },
      querySelectorAll() { return [controls]; },
    },
    window: {
      editors: { id_content: editor },
      scheduleMarkerMainContext: {
        dayDates: ["2026-09-17", "2026-09-18"],
        kartikaStart: null,
        kartikaEnd: null,
      },
      addEventListener() {},
      innerWidth: 1200,
    },
    alert(message) { alerts.push(message); },
  };
  const source = fs.readFileSync(path.join(__dirname, "..", "calendar_markers.js"), "utf8");
  vm.runInNewContext(source, sandbox);
  listeners.DOMContentLoaded();
  return { buttons, root, alerts, setDay(index) { selected = root.children[index]; } };
}

function values(root) {
  return root.children.map((node) => node.children.map((child) => child.data).join(""));
}

test("category buttons insert into the selected day and toggle off", () => {
  const ui = setup();
  ui.buttons.get("ekadashi").click();
  assert.deepEqual(values(ui.root).slice(1, 4), [
    "17 d. Ketvirtadienis", "[Экадаши]", "First day",
  ]);
  ui.buttons.get("fast").click();
  assert.equal(values(ui.root).filter((value) => value === "[Пост]").length, 1);
  ui.buttons.get("ekadashi").click();
  assert.equal(values(ui.root).includes("[Экадаши]"), false);
});

test("Kartika starts in the selected day and ends only in a later one", () => {
  const ui = setup();
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("[Картика: начало]"), true);
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("[Картика: начало]"), false);
  ui.buttons.get("kartika").click();
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "Second day"));
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("[Картика: конец]"), true);
  assert.equal(ui.alerts.length, 0);
});

test("Kartika cannot end before its start", () => {
  const ui = setup();
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "Second day"));
  ui.buttons.get("kartika").click();
  ui.setDay(ui.root.children.findIndex((node) => node.children[0].data === "First day"));
  ui.buttons.get("kartika").click();
  assert.equal(values(ui.root).includes("[Картика: конец]"), false);
  assert.equal(ui.alerts.length, 1);
});
