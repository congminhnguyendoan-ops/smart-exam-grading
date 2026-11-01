// Kiểm thử logic "duyệt nhanh" (frontend/duyet_nhanh.js, lệnh AF) – node:test. pytest gọi qua test_ui_af.py.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { DuyetNhanh: D } = require(path.join(__dirname, "..", "..", "frontend", "duyet_nhanh.js"));

const Q = [
  { question_no: 3, needs_review: true, reasons: ["o_mo"], omr_selected_options: "D" },
  { question_no: 5, needs_review: false, reasons: [], omr_selected_options: "A" },
  { question_no: 7, needs_review: true, reasons: ["nhieu_o"], omr_selected_options: "AB" },
  { question_no: 9, needs_review: true, reasons: ["vi_tri", "o_mo"], omr_selected_options: "C" },
  { question_no: 12, needs_review: true, reasons: ["vet_nho", "tin_cay_thap"], omr_selected_options: "" },
];

test("phím tắt: A–D (hoa / thường), Space, Enter, N, Esc", () => {
  const b = { tag: "BODY" };
  assert.deepEqual(D.phimCau("a", b), { loai: "chon", o: "A" });
  assert.deepEqual(D.phimCau("D", b), { loai: "chon", o: "D" });
  assert.deepEqual(D.phimCau(" ", b), { loai: "xac_nhan" });
  assert.deepEqual(D.phimCau("Enter", { tag: "DIV" }), { loai: "luu" });
  assert.deepEqual(D.phimCau("n", b), { loai: "phieu_ke_tiep" });
  assert.deepEqual(D.phimCau("N", b), { loai: "phieu_ke_tiep" });
  assert.deepEqual(D.phimCau("Escape", b), { loai: "bo_chon" });
  assert.equal(D.phimCau("e", b), null);
  assert.equal(D.phimCau("x", b), null);
  assert.equal(D.phimCau("Tab", b), null);
});

test("phím tắt KHÔNG cướp phím: ô nhập (khung SBD / mã đề của lệnh AA), hộp thoại, phím phụ, Space / Enter trên nút", () => {
  for (const tag of ["INPUT", "TEXTAREA", "SELECT", "input"]) {
    assert.equal(D.phimCau("a", { tag }), null, tag);
    assert.equal(D.phimCau("Enter", { tag }), null, tag);
  }
  assert.equal(D.phimCau("Enter", { tag: "BUTTON", trongKhungDd: true }), null);         // khung AA: Enter = lưu SBD / mã đề (của AA)
  assert.equal(D.phimCau("b", { tag: "DIV", trongKhungDd: true }), null);
  assert.equal(D.phimCau(" ", { tag: "BODY", dangMoHop: true }), null);                  // hộp xác nhận hàng loạt đang mở
  assert.equal(D.phimCau("Enter", { tag: "BODY", dangMoHop: true }), null);
  assert.equal(D.phimCau("a", { tag: "BODY", phu: true }), null);                        // Ctrl+A …
  assert.equal(D.phimCau(" ", { tag: "BUTTON", laNut: true }), null);                    // để trình duyệt bấm nút đang có tiêu điểm
  assert.equal(D.phimCau("Enter", { tag: "A", laNut: true }), null);
  assert.deepEqual(D.phimCau("a", { tag: "BUTTON", laNut: true }), { loai: "chon", o: "A" });
});

test("hàng loạt: chỉ câu đang cần xem, loại câu vi_tri, giữ đáp án máy đọc", () => {
  const { duoc, tay } = D.cauHangLoat(Q);
  assert.deepEqual(duoc.map((c) => c.question_no), [3, 7, 12]);
  assert.deepEqual(tay, [9]);
  assert.deepEqual(duoc.map((c) => c.omr), ["D", "AB", ""]);
  assert.deepEqual(D.cauHangLoat([]), { duoc: [], tay: [] });
  assert.deepEqual(D.cauHangLoat(Q.filter((q) => !q.needs_review)).duoc, []);
});

test("hàng loạt không có SBD / mã đề: chỉ đọc mảng questions, phần tử lạ (không có question_no câu) bị bỏ", () => {
  const p = { sbd: { can_xem: true }, exam_code: { can_xem: true }, questions: Q };
  const { duoc } = D.cauHangLoat(p.questions);
  assert.ok(duoc.every((c) => Number.isInteger(c.question_no) && c.question_no >= 1 && c.question_no <= 40));
  assert.ok(!JSON.stringify(duoc).includes("sbd") && !JSON.stringify(duoc).includes("exam_code"));
});

test("hộp xác nhận: mỗi câu một dòng – số câu, máy đọc, dấu hiệu", () => {
  const dong = D.dongXacNhan(D.cauHangLoat(Q).duoc);
  assert.equal(dong.length, 3);
  assert.equal(dong[0], "Câu 3: máy đọc D – ô mờ");
  assert.equal(dong[1], "Câu 7: máy đọc AB – nhiều ô");
  assert.equal(dong[2], "Câu 12: máy đọc bỏ trống – vết nhỏ ở ô khác, sát ngưỡng");
});

test("nhãn câu: máy đọc + dấu hiệu + mức", () => {
  const n7 = D.nhanCau(Q[2]);
  assert.equal(n7.may_doc, "AB");
  assert.equal(n7.dau_hieu, "nhiều ô");
  assert.equal(n7.muc, "nhieu");
  assert.match(n7.goi_y, /tô 2 ô thì câu tính SAI/);
  assert.equal(D.nhanCau(Q[0]).muc, "mo");
  assert.equal(D.nhanCau(Q[3]).muc, "tay");                                               // vi_tri thắng mọi lý do khác
  assert.equal(D.nhanCau(Q[4]).may_doc, "bỏ trống");
  assert.equal(D.nhanCau({ reasons: ["to_nhat"], omr_selected_options: "B" }).muc, "nhat");
});

test("câu kế tiếp: sau câu hiện tại, vòng về đầu, null khi hết", () => {
  assert.equal(D.cauKeTiep([3, 7, 12], 3), 7);
  assert.equal(D.cauKeTiep([3, 7, 12], 12), 3);
  assert.equal(D.cauKeTiep([3, 7, 12], 5), 7);
  assert.equal(D.cauKeTiep([3], 3), null);
  assert.equal(D.cauKeTiep([], 3), null);
});

test("hàng đợi: nhóm theo lý do chính, lọc, nhóm dễ trước rồi ít câu trước – không đổi dữ liệu", () => {
  const ds = [
    { sheet_id: 1, so_cau: 3, ly_do_cau: { o_mo: 3 } },
    { sheet_id: 2, so_cau: 1, ly_do_cau: { nhieu_o: 1 } },
    { sheet_id: 3, so_cau: 0, ly_do_cau: {}, sbd_can_xem: true },
    { sheet_id: 4, so_cau: 2, ly_do_cau: { o_mo: 1, vet_nho: 1 } },
    { sheet_id: 5, so_cau: 1, ly_do_cau: { vi_tri: 1 }, co_vi_tri: true },
    { sheet_id: 6, so_cau: 1, ly_do_cau: { o_mo: 1 } },
    { sheet_id: 7, so_cau: 1, ly_do_cau: { o_mo: 1 }, trung_sbd: true, sbd_can_xem: true },
  ];
  const goc = JSON.stringify(ds);
  assert.deepEqual(ds.map(D.nhomPhieu), ["chi_mo", "chi_nhieu_o", "dinh_danh", "khac", "vi_tri", "chi_mo", "trung"]);
  assert.deepEqual(D.locSapHangDoi(ds).map((g) => g.sheet_id), [2, 6, 1, 4, 5, 3, 7]);
  assert.deepEqual(D.locSapHangDoi(ds, "chi_mo").map((g) => g.sheet_id), [6, 1]);
  assert.deepEqual(D.locSapHangDoi(ds, "dinh_danh").map((g) => g.sheet_id), [3]);
  assert.equal(JSON.stringify(ds), goc);
  for (const k of D.THU_TU_NHOM) assert.ok(D.TEN_NHOM[k], k);
});
