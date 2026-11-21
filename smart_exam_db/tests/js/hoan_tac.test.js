"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { HoanTac: H } = require(path.join(__dirname, "..", "..", "frontend", "hoan_tac.js"));

const cauXong = { question_no: 7, needs_review: false, da_xem: true, reasons: ["o_mo"] };
const cauTuCham = { question_no: 9, needs_review: false, da_xem: true, reasons: ["nhieu_o"] };
const graded = { status: "graded", score: { official: 9.5 } };
const cho = { status: "needs_review", score: { official: null } };

test("nút chỉ hiện cho câu đã xem trên phiếu graded / needs_review", () => {
  assert.equal(H.coTheHoanTac(cauXong, graded), true);
  assert.equal(H.coTheHoanTac({ ...cauXong, da_xem: false }, graded), false);
  assert.equal(H.coTheHoanTac({ ...cauXong, needs_review: true }, graded), false);
  assert.equal(H.coTheHoanTac(cauXong, { status: "rejected", score: null }), false);
  assert.equal(H.nutHtml({ ...cauXong, da_xem: false }, graded), "");
  assert.match(H.nutHtml(cauXong, graded), /data-undo="7"/);
});

test("phân loại câu: nhiều ô thuần là tự chấm, còn lại là câu chờ", () => {
  assert.equal(H.loaiHoanTac(cauTuCham), "tu_cham");
  assert.equal(H.loaiHoanTac(cauXong), "cho");
  assert.equal(H.loaiHoanTac({ reasons: ["nhieu_o", "to_nhat"] }), "cho");
});

test("chỉ hỏi xác nhận khi câu chờ đã có điểm chính thức", () => {
  assert.match(H.loiHoi(cauXong, graded), /Điểm chính thức sẽ bị rút về điểm tạm/);
  assert.equal(H.loiHoi(cauXong, cho), null);
  assert.equal(H.loiHoi(cauTuCham, graded), null);
});

test("nhãn nút theo loại", () => {
  assert.match(H.nhanNut(cauTuCham), /tự chấm sai/);
  assert.match(H.nhanNut(cauXong), /chờ xem/);
});
