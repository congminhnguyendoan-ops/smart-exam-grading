/* Dòng trạng thái của Ô CHỌN TỆP tiếng Việt (lệnh AB) – thay chữ mặc định tiếng Anh của trình duyệt ("Choose Files / No file chosen").
   /app/ màn Tải ảnh (index.html); Node: tests/js/chon_tep.test.js. Chỉ câu chữ hiển thị – không đổi tệp nào được gửi.
     []                         -> "Chưa chọn ảnh."
     ["0001_C1.jpg"]            -> "Đã chọn 1 ảnh: 0001_C1.jpg"
     ["a.jpg", "b.jpg", …]      -> "Đã chọn 5 ảnh: a.jpg, b.jpg, c.jpg và 2 ảnh khác"   (tên dài rút gọn bằng rutGonTen của ten_tep.js) */
"use strict";

(function (goc) {
  const HIEN_TOI_DA = 3;
  const rut = (t) => (typeof goc.rutGonTen === "function" ? goc.rutGonTen(t) : String(t ?? ""));

  function moTaTepChon(ten, rutGon = rut) {
    const ds = (ten || []).map(String);
    if (!ds.length) return "Chưa chọn ảnh.";
    const dau = ds.slice(0, HIEN_TOI_DA).map(rutGon).join(", ");
    const con = ds.length - HIEN_TOI_DA;
    return `Đã chọn ${ds.length} ảnh: ${dau}${con > 0 ? ` và ${con} ảnh khác` : ""}`;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { moTaTepChon };
  else goc.moTaTepChon = moTaTepChon;
})(typeof window !== "undefined" ? window : globalThis);
