// Kiểm thử hàm rút gọn tên tệp (frontend/ten_tep.js) – node:test. Chạy: node --test tests/js
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { rutGonTen, tenTepHtml } = require(path.join(__dirname, "..", "..", "frontend", "ten_tep.js"));

test("tên ngắn (≤ 24 ký tự) giữ nguyên", () => {
  assert.equal(rutGonTen("image.jpg"), "image.jpg");
  assert.equal(rutGonTen("a".repeat(24)), "a".repeat(24));         // đúng ngưỡng: giữ
});

test("tên dài: 10 ký tự đầu + … + đuôi tệp", () => {
  assert.equal(rutGonTen("att.pc5ziEjVdDSu9zNPSpp9Llr1udeCi1EQjzdpGAIhgWQ.jpeg"), "att.pc5ziE….jpeg");
  assert.equal(rutGonTen("a".repeat(25) + ".png"), "a".repeat(10) + "….png");
});

test("tên dài không có đuôi (hoặc 'đuôi' quá dài): chỉ 10 ký tự đầu + …", () => {
  assert.equal(rutGonTen("a".repeat(40)), "a".repeat(10) + "…");
  assert.equal(rutGonTen("tenrathaidai" + ".phandaiquadai".repeat(2)), "tenrathaid…");
  assert.equal(rutGonTen(".htaccess" + "x".repeat(30)), ".htaccessx…");   // dấu chấm ở đầu không phải đuôi
});

test("rỗng / null / undefined / số", () => {
  assert.equal(rutGonTen(""), ""); assert.equal(rutGonTen(null), ""); assert.equal(rutGonTen(undefined), "");
  assert.equal(rutGonTen(12345), "12345");
});

test("tenTepHtml: title = tên đầy đủ, thoát HTML, rỗng -> –", () => {
  const dai = "att.pc5ziEjVdDSu9zNPSpp9Llr1udeCi1EQjzdpGAIhgWQ.jpeg";
  assert.equal(tenTepHtml(dai), `<span class="tentep" title="${dai}">att.pc5ziE….jpeg</span>`);
  assert.equal(tenTepHtml(null), "–"); assert.equal(tenTepHtml(""), "–");
  assert.ok(!tenTepHtml('"><img src=x onerror=1>' + "a".repeat(30)).includes("<img"));      // không chèn được thẻ qua tên tệp
  assert.equal(tenTepHtml("a.jpg"), '<span class="tentep" title="a.jpg">a.jpg</span>');
});
