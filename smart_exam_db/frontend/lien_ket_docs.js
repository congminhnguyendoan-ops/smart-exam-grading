/* Lệnh AV (V7): liên kết "API (Swagger)" ở thanh bên CHỈ hiện khi máy chủ thật sự phục vụ tài liệu (DOCS_ENABLED=1).
   DOCS_ENABLED=0 (mặc định) -> /openapi.json trả 404 -> liên kết giữ nguyên ẩn (không để liên kết cụt). Mọi lỗi mạng -> vẫn ẩn. Node: module.exports (tests/js/lien_ket_docs.test.js). */
"use strict";

(function (goc) {
  /** `fetchFn` (mặc định fetch) + `wrap` (phần tử bọc liên kết). Trả true nếu đã hiện. */
  async function capNhatLienKetDocs(fetchFn, wrap) {
    if (!wrap) return false;
    try {
      const r = await fetchFn("/openapi.json", { credentials: "same-origin" });
      if (r && r.ok) { wrap.classList.remove("hidden"); return true; }
    } catch (e) { /* mạng lỗi: giữ ẩn */ }
    return false;
  }

  const LienKetDocs = { capNhatLienKetDocs };
  if (typeof module !== "undefined" && module.exports) module.exports = { LienKetDocs };
  else {
    goc.LienKetDocs = LienKetDocs;
    capNhatLienKetDocs(goc.fetch.bind(goc), goc.document.getElementById("lk-docs-wrap"));
  }
})(typeof window !== "undefined" ? window : globalThis);
