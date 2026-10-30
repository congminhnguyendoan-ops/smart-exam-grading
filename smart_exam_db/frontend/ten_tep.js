/* Rút gọn TÊN TỆP ẢNH khi HIỂN THỊ (lệnh G2) – không đổi dữ liệu lưu trong CSDL. Dùng chung cho /app/ (index.html) và /m (m.html); Node: module.exports (tests/js/ten_tep.test.js).
   Tên dài hơn 24 ký tự -> 10 ký tự đầu + "…" + đuôi tệp (vd "att.pc5ziE….jpeg"); tên ngắn, rỗng, null giữ nguyên (null/undefined -> ""). Đầy đủ nằm ở thuộc tính title (rê chuột). */
"use strict";

(function (goc) {
  const TOI_DA = 24, DAU = 10;

  function rutGonTen(ten) {
    if (ten === null || ten === undefined) return "";
    const s = String(ten);
    if (s.length <= TOI_DA) return s;
    const i = s.lastIndexOf(".");
    const duoi = i > 0 && s.length - i <= 8 ? s.slice(i) : "";          // chỉ coi là đuôi khi ngắn (≤ 7 ký tự sau dấu chấm)
    return s.slice(0, DAU) + "…" + duoi;
  }

  const thoat = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /** HTML an toàn: <span class="tentep" title="tên đầy đủ">tên rút gọn</span>. Tên rỗng -> "–". */
  function tenTepHtml(ten) {
    const day = ten === null || ten === undefined ? "" : String(ten);
    if (!day) return "–";
    return `<span class="tentep" title="${thoat(day)}">${thoat(rutGonTen(day))}</span>`;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { rutGonTen, tenTepHtml };
  else { goc.rutGonTen = rutGonTen; goc.tenTepHtml = tenTepHtml; }
})(typeof window !== "undefined" ? window : globalThis);
