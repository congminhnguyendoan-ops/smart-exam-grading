/* Phân loại LỖI KHI TẢI ẢNH (lệnh V1) – dùng chung cho /app/ (màn Tải ảnh, index.html) và /m (hàng đợi m_hang_doi.js); Node: module.exports (tests/js/loi_tai.test.js).
   Mục đích: chỉ hiện nút "Gửi lại" khi gửi lại CÓ THỂ thành công.
     - "mang"     : không tới được máy chủ (mã 0), quá giờ (408), quá tải (429), lỗi máy chủ (5xx) -> GIỮ ảnh, có nút Gửi lại.
     - "anh_lon"  : 413 – gửi lại vẫn hỏng, phải chụp lại nhỏ hơn.
     - "het_phien": 401 – đăng nhập lại rồi gửi tiếp (hàng đợi /m tạm dừng).
     - "tu_choi"  : máy chủ TRẢ LỜI RÕ là không nhận (409 kỳ thi đã đóng, 404 ngoài phạm vi / không có, 403, 400, 422, 410 …) -> KHÔNG có nút Gửi lại.
   Lý do hiển thị là thông báo tiếng Việt của máy chủ (detail); chỉ thêm tiêu đề ngắn theo mã. */
"use strict";

(function (goc) {
  const MANG = new Set([0, 408, 429]);

  function phanLoai(ma) {
    const m = Number(ma) || 0;
    if (MANG.has(m) || m >= 500) return "mang";
    if (m === 413) return "anh_lon";
    if (m === 401) return "het_phien";
    return "tu_choi";
  }

  const TIEU_DE = { 409: "Kỳ thi không nhận ảnh", 404: "Ngoài phạm vi", 403: "Không có quyền", 410: "Không còn", 400: "Yêu cầu không hợp lệ", 422: "Tệp không hợp lệ" };

  /** Tiêu đề ngắn cho thẻ "bị từ chối" (không thay lý do của máy chủ). */
  function tieuDeTuChoi(ma) { return TIEU_DE[Number(ma)] || "Máy chủ từ chối"; }

  const LoiTai = { phanLoai, tieuDeTuChoi, guiLaiDuoc: (ma) => phanLoai(ma) === "mang" };
  if (typeof module !== "undefined" && module.exports) module.exports = { LoiTai };
  else goc.LoiTai = LoiTai;
})(typeof window !== "undefined" ? window : globalThis);
