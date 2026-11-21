// Lệnh AF2: hàng loạt chỉ "nhiều ô" / "tô nhạt cả tờ", nhãn nút, ẩn nút, bẫy Tab + Esc trong hộp xác nhận (frontend/duyet_nhanh.js) – node:test.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { DuyetNhanh: D } = require(path.join(__dirname, "..", "..", "frontend", "duyet_nhanh.js"));

const cau = (n, reasons, omr = "A", needs_review = true) => ({ question_no: n, reasons, omr_selected_options: omr, needs_review });

test("hợp lệ hàng loạt: MỌI lý do thuộc {nhieu_o, to_nhat} – cùng điều kiện máy chủ", () => {
  assert.deepEqual(D.LY_DO_HANG_LOAT, ["nhieu_o", "to_nhat"]);
  for (const ly of [["to_nhat"], ["nhieu_o", "to_nhat"]]) assert.ok(D.hopLeHangLoat(cau(1, ly)), ly.join("+"));
  for (const ly of [["nhieu_o"], [], ["o_mo"], ["vet_nho"], ["tin_cay_thap"], ["vi_tri"], ["nhieu_o", "o_mo"], ["to_nhat", "vet_nho"], ["nhieu_o", "vi_tri"]])
    assert.ok(!D.hopLeHangLoat(cau(1, ly)), ly.join("+") || "(rỗng)");
  assert.ok(!D.hopLeHangLoat(cau(1, ["nhieu_o"], "AB", false)), "câu không còn cờ");
});

test("nhãn nút: đếm đúng câu hợp lệ; 0 câu -> ẩn nút (null)", () => {
  const q = [cau(1, ["nhieu_o"], "AB"), cau(2, ["o_mo"]), cau(3, ["to_nhat"], "C"), cau(4, ["vet_nho"], ""), cau(5, ["nhieu_o", "to_nhat"], "BD"),
    cau(6, ["tin_cay_thap"]), cau(7, ["nhieu_o"], "AC", false)];
  const { duoc, tay } = D.cauHangLoat(q);
  assert.deepEqual(duoc.map((c) => c.question_no), [3, 5]);
  assert.deepEqual(tay, [1, 2, 4, 6]);
  assert.equal(D.nhanNutHangLoat(duoc.length), "Xác nhận 2 câu tô nhạt cả tờ như máy đọc…");
  assert.equal(D.nhanNutHangLoat(1), "Xác nhận 1 câu tô nhạt cả tờ như máy đọc…");
  assert.equal(D.nhanNutHangLoat(0), null);
  assert.equal(D.nhanNutHangLoat(D.cauHangLoat([cau(2, ["o_mo"]), cau(4, ["vet_nho"])]).duoc.length), null);   // phiếu chỉ có mờ / vết -> ẩn
  assert.equal(D.nhanNutHangLoat(D.cauHangLoat([]).duoc.length), null);
});

test("bẫy Tab: Tab / Shift+Tab xoay vòng trong hộp; tiêu điểm ở ngoài hộp -> về đầu / cuối", () => {
  assert.equal(D.tabKeTiep(4, 0, false), 1);
  assert.equal(D.tabKeTiep(4, 3, false), 0);                                           // cuối -> đầu
  assert.equal(D.tabKeTiep(4, 0, true), 3);                                            // đầu, Shift+Tab -> cuối
  assert.equal(D.tabKeTiep(4, 2, true), 1);
  assert.equal(D.tabKeTiep(4, -1, false), 0);                                          // tiêu điểm đã rơi ra ngoài (bấm nền hộp)
  assert.equal(D.tabKeTiep(4, -1, true), 3);
  assert.equal(D.tabKeTiep(1, 0, false), 0);
  assert.equal(D.tabKeTiep(0, -1, false), -1);
  assert.deepEqual(D.phimHop("Tab", false, 5, 4), { loai: "tab", j: 0 });
  assert.deepEqual(D.phimHop("Tab", true, 5, 0), { loai: "tab", j: 4 });
});

test("Esc đóng hộp; phím khác (Enter, Space, chữ) để trình duyệt xử lý (Enter trên nút Huỷ = Huỷ)", () => {
  assert.deepEqual(D.phimHop("Escape", false, 3, 1), { loai: "dong" });
  assert.deepEqual(D.phimHop("Esc", false, 3, 1), { loai: "dong" });
  for (const k of ["Enter", " ", "a", "ArrowDown"]) assert.equal(D.phimHop(k, false, 3, 0), null, k);
});
