// Kiểm thử câu chữ lý do cần xem SBD / mã đề theo cột (frontend/ly_do_cot.js, lệnh V3) – node:test. pytest gọi qua test_dien_thoai.py.
// Dữ liệu cột có đúng dạng CotChuSo của API (backend/schemas.py): vi_tri TỪ 1 (handwriting.pos từ 0), bubble, handwriting.{chu_so, p, o_trong, loi_o}, ly_do.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { LyDoCot } = require(path.join(__dirname, "..", "..", "frontend", "ly_do_cot.js"));

const hw = (chu_so, p = 0.9, them = {}) => ({ pos: 0, chu_so, p, top_k: [], o_trong: false, loi_o: "", ok_vien: true, ...them });
const cot = (vi_tri, bubble, h, ly_do = [], chu_so = bubble) => ({ vi_tri, chu_so, can_xem: ly_do.length > 0, ly_do, do_tin_cay: 0.9, bubble, handwriting: h });

test("ô tô '?' + chữ viết tay có số -> nói rõ cả hai kênh; số cột = vi_tri (từ 1)", () => {
  assert.equal(LyDoCot.cauCot(cot(3, "?", hw("8"), ["thieu_bubble"], "8")),
    "Cột 3: ô tô trống hoặc không đọc được (không tô / tô nhiều ô); chữ viết tay đọc là 8");
  assert.equal(LyDoCot.cauCot(cot(1, "?", hw("?", 0, { o_trong: true }), ["thieu_bubble"], "?")),
    "Cột 1: ô tô trống hoặc không đọc được (không tô / tô nhiều ô); ô viết tay trống");
});

test("hai kênh lệch / cùng số nhưng tin cậy thấp / ô tô chưa chắc / ô viết tay lỗi", () => {
  assert.equal(LyDoCot.cauCot(cot(3, "4", hw("1"), ["lech_bubble"])), "Cột 3: ô tô đọc 4, chữ viết tay đọc 1");
  assert.equal(LyDoCot.cauCot(cot(5, "7", hw("7", 0.38), ["tin_cay_thap"])), "Cột 5: ô tô đọc 7, chữ viết tay cũng đọc 7 nhưng máy chưa chắc (38%)");
  assert.equal(LyDoCot.cauCot(cot(2, "5", hw("5"), ["bubble_cx"])), "Cột 2: ô tô đọc 5 nhưng máy chưa chắc (tô mờ / tô nhiều ô); chữ viết tay đọc là 5");
  assert.equal(LyDoCot.cauCot(cot(1, "3", hw("?", 0, { loi_o: "o_it_muc" }), ["o_it_muc"])), "Cột 1: ô tô đọc 3; ô viết tay quá ít mực, không đọc được");
  assert.equal(LyDoCot.cauCot(cot(1, "3", hw("9"), [])), "");          // cột chắc: không có câu
});

test("lý do cả trường: ô viết tay trống, số không có trong danh sách; mã lạ dùng câu dự phòng", () => {
  const tr = { detected: "220011", can_xem: true, reasons: ["o_trong_ngoai_ds", "ma_moi"], columns: [
    cot(1, "2", hw("2")), cot(2, "2", hw("?", 0, { o_trong: true })), cot(3, "0", hw("?", 0, { o_trong: true })),
    cot(4, "0", hw("0")), cot(5, "1", hw("1")), cot(6, "1", hw("1"))] };
  assert.deepEqual(LyDoCot.moTa(tr, { ma_moi: "câu cũ" }),
    ["Cột 2, 3: ô viết tay trống, chỉ đọc được ô tô (20) – số này không có trong danh sách kỳ thi", "câu cũ"]);
  const tr2 = { reasons: ["thieu_bubble", "o_trong_chua_biet_ds"], columns: [cot(1, "?", hw("6"), ["thieu_bubble"], "6"), cot(2, "1", hw("?", 0, { o_trong: true }))] };
  assert.deepEqual(LyDoCot.moTa(tr2), ["Cột 1: ô tô trống hoặc không đọc được (không tô / tô nhiều ô); chữ viết tay đọc là 6",
    "Cột 2: ô viết tay trống, chỉ đọc được ô tô (1) – chưa kiểm được danh sách kỳ thi"]);
  assert.deepEqual(LyDoCot.moTa(null), []);
});
