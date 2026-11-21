"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { CauSai } = require("../../frontend/cau_sai.js");

const q = (n, o = {}) => ({ question_no: n, selected_options: "A", needs_review: false, is_correct: true, manually_edited: false,
  tu_cham_can_xem: false, da_xem: false, correct_option: "A", ...o });

const bai = [
  q(1), q(2),
  q(3, { selected_options: "B", is_correct: false }),
  q(4, { selected_options: "", is_correct: false }),
  q(5, { selected_options: "AC", is_correct: false, tu_cham_can_xem: true }),
  q(6, { selected_options: "D", is_correct: false, manually_edited: true, da_xem: true }),
  q(7, { selected_options: "", is_correct: null, needs_review: true }),
  q(8, { selected_options: "BC", is_correct: false, da_xem: true }),
  q(9, { selected_options: "C", is_correct: false }),
];

test("thứ tự: tô nhiều ô, rồi bỏ trống, rồi chọn sai; cùng loại theo số câu", () => {
  assert.deepEqual(CauSai.danhSachSai(bai).map((x) => x.question_no), [5, 8, 4, 3, 6, 9]);
});

test("tóm tắt tách rời và câu chưa chấm riêng", () => {
  const t = CauSai.tomTat(bai);
  assert.deepEqual([t.tong, t.dung, t.sai, t.trong, t.nhieu, t.chua_cham], [9, 2, 3, 1, 2, 1]);
  assert.equal(t.chuoi, "2/9 đúng · 3 sai · 1 bỏ trống · 2 tô nhiều ô");
  assert.deepEqual(CauSai.chuaCham(bai), [7]);
});

test("không có câu sai", () => {
  const ok = [q(1), q(2)];
  assert.deepEqual(CauSai.danhSachSai(ok), []);
  assert.equal(CauSai.tomTat(ok).chuoi, "2/2 đúng · 0 sai · 0 bỏ trống · 0 tô nhiều ô");
});

test("lý do và mô tả lựa chọn", () => {
  assert.equal(CauSai.lyDo(bai[2]), "Chọn sai");
  assert.equal(CauSai.lyDo(bai[3]), "Bỏ trống");
  assert.equal(CauSai.lyDo(bai[4]), "Tô nhiều ô – tự chấm sai");
  assert.equal(CauSai.lyDo(bai[5]), "Giáo viên đã sửa");
  assert.equal(CauSai.moTaChon(bai[2]), "thí sinh chọn B");
  assert.equal(CauSai.moTaChon(bai[3]), "thí sinh bỏ trống");
  assert.equal(CauSai.moTaChon(bai[4]), "thí sinh tô nhiều ô AC");
});

test("nút theo câu: sửa lại / hoàn tác / giữ như máy chấm", () => {
  const phieu = { status: "graded" };
  assert.deepEqual(CauSai.hanhDong(bai[2], phieu), { sua: false, hoan_tac: false, giu: false });
  assert.deepEqual(CauSai.hanhDong(bai[4], phieu), { sua: true, hoan_tac: false, giu: true });
  assert.deepEqual(CauSai.hanhDong(bai[5], phieu), { sua: true, hoan_tac: true, giu: false });
  assert.deepEqual(CauSai.hanhDong(bai[5], { status: "rejected" }), { sua: true, hoan_tac: false, giu: false });
});
