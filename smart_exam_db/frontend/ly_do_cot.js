/* Câu chữ LÝ DO CẦN XEM của SBD / mã đề, theo TỪNG CỘT (lệnh V3) – dùng chung cho /app/ (chi tiết + duyệt phiếu) và /m (cảnh báo); Node: tests/js/ly_do_cot.test.js.
   CHỈ ĐỔI CÂU CHỮ HIỂN THỊ: dữ liệu lấy nguyên từ GET /sheets/{id} (sbd / exam_code: columns[].vi_tri (TỪ 1, như omr.py; handwriting.pos mới tính từ 0), bubble, handwriting.{chu_so, p, o_trong, loi_o},
   ly_do; reasons của cả trường). Logic phát hiện (cv_engine/ocr.py doi_chieu_cot / doi_chieu_truong) KHÔNG đổi.
     thieu_bubble + chữ viết tay có số -> "Cột 3: ô tô trống hoặc không đọc được; chữ viết tay đọc là 8"
     lech_bubble                       -> "Cột 3: ô tô đọc 4, chữ viết tay đọc 1"
     tin_cay_thap                      -> "Cột 3: ô tô đọc 4, chữ viết tay cũng đọc 4 nhưng máy chưa chắc (38%)"
     o_trong_ngoai_ds / o_trong_chua_biet_ds (của cả trường) -> các cột ô viết tay trống + "số này không có trong danh sách kỳ thi" / "chưa kiểm được danh sách" */
"use strict";

(function (goc) {
  const CUA_COT = new Set(["thieu_bubble", "bubble_cx", "lech_bubble", "tin_cay_thap", "o_it_muc", "khong_phai_chu_so"]);
  const DS = { o_trong_ngoai_ds: "số này không có trong danh sách kỳ thi", o_trong_chua_biet_ds: "chưa kiểm được danh sách kỳ thi" };
  const pt = (p) => `${Math.round((Number(p) || 0) * 100)}%`;

  function veTo(c, ly) {
    const b = c.bubble ?? c.chu_so;
    if (b === null || b === undefined || b === "?" || ly.has("thieu_bubble")) return "ô tô trống hoặc không đọc được (không tô / tô nhiều ô)";
    return ly.has("bubble_cx") ? `ô tô đọc ${b} nhưng máy chưa chắc (tô mờ / tô nhiều ô)` : `ô tô đọc ${b}`;
  }
  function veViet(c, ly) {
    const h = c.handwriting;
    if (!h) return "";
    if (ly.has("o_it_muc") || h.loi_o === "o_it_muc") return "ô viết tay quá ít mực, không đọc được";
    if (ly.has("khong_phai_chu_so") || h.loi_o === "khong_phai_chu_so") return "ô viết tay không giống chữ số";
    if (h.o_trong) return "ô viết tay trống";
    if (!h.chu_so || h.chu_so === "?") return "chữ viết tay không đọc được";
    return `chữ viết tay đọc là ${h.chu_so}`;
  }

  /** Một câu cho một cột có lý do cần xem (rỗng nếu cột không có lý do của cột). */
  function cauCot(c) {
    const ly = new Set((c.ly_do || []).filter((m) => CUA_COT.has(m)));
    if (!ly.size) return "";
    const n = `Cột ${Number(c.vi_tri)}`, h = c.handwriting, b = c.bubble ?? c.chu_so;
    if (ly.has("lech_bubble") && h && h.chu_so && h.chu_so !== "?" && !h.o_trong) return `${n}: ô tô đọc ${b}, chữ viết tay đọc ${h.chu_so}`;
    if (ly.has("tin_cay_thap") && h && h.chu_so === b) return `${n}: ô tô đọc ${b}, chữ viết tay cũng đọc ${h.chu_so} nhưng máy chưa chắc (${pt(h.p)})`;
    if (ly.has("tin_cay_thap") && h) return `${n}: ô tô đọc ${b}, chữ viết tay đọc ${h.chu_so} nhưng máy chưa chắc (${pt(h.p)})`;
    const viet = veViet(c, ly);
    return `${n}: ${veTo(c, ly)}${viet ? `; ${viet}` : ""}`;
  }

  /** Danh sách câu cho cả trường (SBD / mã đề). `duPhong` = bảng mã -> câu cũ cho mã không thuộc các trường hợp trên. */
  function moTa(truong, duPhong = {}) {
    if (!truong || !Array.isArray(truong.columns)) return [];
    const ra = truong.columns.map(cauCot).filter(Boolean);
    const da = new Set(truong.columns.flatMap((c) => c.ly_do || []).filter((m) => CUA_COT.has(m)));
    for (const m of new Set(truong.reasons || [])) {
      if (da.has(m)) continue;
      if (DS[m]) {
        const trong = truong.columns.filter((c) => c.handwriting && c.handwriting.o_trong && !(c.ly_do || []).length);
        ra.push(trong.length ? `${trong.length === truong.columns.length ? "Mọi cột" : `Cột ${trong.map((c) => Number(c.vi_tri)).join(", ")}`}: ô viết tay trống, chỉ đọc được ô tô ` +
          `(${trong.map((c) => c.bubble ?? c.chu_so).join("")}) – ${DS[m]}` : `Ô viết tay trống – ${DS[m]}`);
      } else ra.push(duPhong[m] || m);
    }
    return ra;
  }

  const LyDoCot = { cauCot, moTa };
  if (typeof module !== "undefined" && module.exports) module.exports = { LyDoCot };
  else goc.LyDoCot = LyDoCot;
})(typeof window !== "undefined" ? window : globalThis);
