/* Ẩn KỲ THI ĐÃ ĐÓNG khỏi ô chọn kỳ thi (lệnh V2) – dùng chung cho thanh bên /app/ (index.html) và "Chọn kỳ thi" ở /m; Node: module.exports (tests/js/ky_thi_dong.test.js).
   CHỈ LỌC HIỂN THỊ: danh sách vẫn lấy đủ từ GET /exams, quyền do máy chủ kiểm. Trang Quản trị không dùng module này (luôn hiện đủ).
   Lựa chọn "Hiện cả kỳ thi đã đóng" nhớ ở localStorage, khoá DUY NHẤT `hienKyThiDong` (giá trị "1"); đăng xuất thì xoá (xoaLuuTru ở app.js, nút Đăng xuất ở m.js). */
"use strict";

(function (goc) {
  const KHOA = "hienKyThiDong";

  function doc() {
    try { return !!goc.localStorage && goc.localStorage.getItem(KHOA) === "1"; } catch (_) { return false; }
  }
  function luu(hien) {
    try { if (hien) goc.localStorage.setItem(KHOA, "1"); else goc.localStorage.removeItem(KHOA); } catch (_) { /* bỏ qua */ }
  }
  function xoa() { luu(false); }

  /** Danh sách để HIỂN THỊ: bỏ kỳ thi `closed` trừ khi `hien`; kỳ thi `giu` (đang chọn) luôn giữ để không tự đổi kỳ thi người dùng đang xem. */
  function loc(exams, hien, giu = null) {
    return (exams || []).filter((e) => hien || e.status !== "closed" || (giu !== null && e.exam_id === giu));
  }
  const soDong = (exams) => (exams || []).filter((e) => e.status === "closed").length;

  const KyThiDong = { KHOA, doc, luu, xoa, loc, soDong };
  if (typeof module !== "undefined" && module.exports) module.exports = { KyThiDong };
  else goc.KyThiDong = KyThiDong;
})(typeof window !== "undefined" ? window : globalThis);
