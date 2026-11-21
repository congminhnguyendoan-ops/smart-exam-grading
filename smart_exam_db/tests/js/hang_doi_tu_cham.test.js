"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const mod = require(path.join(__dirname, "..", "..", "frontend", "m_hang_doi.js"));

const { HangDoi } = mod;

function tao() {
  return new HangDoi({ gui: async () => ({}) });
}

function to(stt, ketQua, extra = {}) {
  return { stt, soTo: stt, trangThai: "xong", ketQua, thayBang: false, ...extra };
}

test("demTuCham: chỉ tờ đã chấm chính thức còn câu nhiều ô chờ xem lại", () => {
  const hd = tao();
  hd.ds = [
    to(1, { status: "graded", auto_graded_pending: 2 }),
    to(2, { status: "graded", auto_graded_pending: 0 }),
    to(3, { status: "needs_review", auto_graded_pending: 5 }),
    to(4, { status: "graded", chiTiet: { score: { auto_graded_pending: 1 } } }),
    to(5, { status: "graded", auto_graded_pending: 3 }, { thayBang: true }),
    to(6, { status: "rejected" }),
    to(7, { status: "graded", auto_graded_pending: 4 }, { trangThai: "loi" }),
  ];
  assert.deepEqual(hd.demTuCham(), { soTo: 2, soCau: 3 });
});

test("demTuCham: hàng đợi rỗng -> 0; tong() không đổi hình dạng", () => {
  const hd = tao();
  assert.deepEqual(hd.demTuCham(), { soTo: 0, soCau: 0 });
  assert.deepEqual(Object.keys(hd.tong()), ["daChup", "chamDuoc", "canXem", "tuChoi", "dangCho", "loi", "trung"]);
});
