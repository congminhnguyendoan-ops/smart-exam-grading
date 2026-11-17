"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { LienKetDocs } = require("../../frontend/lien_ket_docs.js");

const wrap = () => { const c = new Set(["hidden"]); return { classList: { remove: (x) => c.delete(x), has: (x) => c.has(x) } }; };

test("DOCS_ENABLED=0: /openapi.json 404 -> liên kết vẫn ẩn", async () => {
  const w = wrap();
  assert.strictEqual(await LienKetDocs.capNhatLienKetDocs(async () => ({ ok: false, status: 404 }), w), false);
  assert.ok(w.classList.has("hidden"));
});
test("DOCS_ENABLED=1: /openapi.json 200 -> liên kết hiện", async () => {
  const w = wrap();
  assert.strictEqual(await LienKetDocs.capNhatLienKetDocs(async () => ({ ok: true, status: 200 }), w), true);
  assert.ok(!w.classList.has("hidden"));
});
test("lỗi mạng -> vẫn ẩn, không ném lỗi", async () => {
  const w = wrap();
  assert.strictEqual(await LienKetDocs.capNhatLienKetDocs(async () => { throw new Error("mang"); }, w), false);
  assert.ok(w.classList.has("hidden"));
});
test("không có phần tử -> false", async () => {
  assert.strictEqual(await LienKetDocs.capNhatLienKetDocs(async () => ({ ok: true }), null), false);
});
