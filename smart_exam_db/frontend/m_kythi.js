/* Tham số ?kythi=<id> của trang điện thoại /m (mã QR trên trang bìa kỳ thi – backend/trang_bia.py). Thuần logic (không DOM):
   trình duyệt dùng window.MKyThi, Node dùng module.exports để kiểm thử (tests/js/m_kythi.test.js).
   - docThamSo(search): id (số nguyên dương) hoặc null – giá trị lạ bị bỏ qua (không dùng để dựng URL / HTML).
   - chonTuDanhSach(exams, id): kỳ thi trong danh sách GET /exams của người đang đăng nhập (đã lọc theo quyền ở máy chủ).
     Không có trong danh sách -> loi "khong_thay": KHÔNG phân biệt "không tồn tại" với "không có quyền", không lộ tên kỳ thi (như 404 của API). */
"use strict";

(function (goc) {
  function docThamSo(search) {
    let v = null;
    try { v = new URLSearchParams(search || "").get("kythi"); } catch (_) { v = null; }
    return v && /^[1-9]\d{0,11}$/.test(v) ? Number(v) : null;
  }

  function chonTuDanhSach(exams, id) {
    if (id === null || id === undefined) return { exam: null, loi: null };
    const e = (exams || []).find((x) => x.exam_id === id);
    return e ? { exam: e, loi: null } : { exam: null, loi: "khong_thay" };
  }

  const api = { docThamSo, chonTuDanhSach };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else goc.MKyThi = api;
})(typeof window !== "undefined" ? window : globalThis);
