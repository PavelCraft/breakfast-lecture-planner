const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


test("separate Kartika periods produce separate visible ranges", () => {
  const sandbox = {
    document: { addEventListener() {} },
  };
  const source = fs.readFileSync(path.join(__dirname, "..", "calendar.js"), "utf8");
  vm.runInNewContext(source, sandbox);

  const ranges = sandbox.kartikaRanges([
    { kartikaPeriod: "2026-10-29" },
    { kartikaPeriod: null },
    { kartikaPeriod: "2026-11-03" },
    { kartikaPeriod: "2026-11-03" },
    { kartikaPeriod: "2026-11-03" },
  ]);

  assert.deepEqual(
    JSON.parse(JSON.stringify(ranges)),
    [
      { period: "2026-10-29", first: 0, last: 0 },
      { period: "2026-11-03", first: 2, last: 4 },
    ],
  );
});
