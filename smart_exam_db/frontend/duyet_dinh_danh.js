/* Logic THUẦN cho khung "Chốt số báo danh / mã đề" (lệnh AA, /app/ – màn Duyệt phiếu); Node: tests/js/duyet_dinh_danh.test.js.
   CHỈ GIAO DIỆN: không gọi API, không đổi dữ liệu. Nguyên tắc bất biến: máy KHÔNG tự chọn thay giáo viên – các hàm ở đây chỉ
   KIỂM giá trị giáo viên đã gõ / đã bấm, đưa GỢI Ý (giáo viên phải bấm mới điền) và hỏi XÁC NHẬN khi giá trị dễ sai.
     kiemSbd("220010", ["220001", …]) -> { muc: "canh_bao", thong_bao: "SBD 220010 không có trong danh sách …", goi_y: ["220009", …] }
     kiemMaDe("105", ["103", "104"])  -> { muc: "canh_bao", thong_bao: "Mã đề 105 không thuộc kỳ thi …", goi_y: ["103", "104"] }
     keTiep([12, 15, 18], 15)         -> 18   (phiếu cần xem kế tiếp trong hàng đợi, theo thứ tự hàng đợi)
     phim("Enter", false, "in-sbd")   -> "luu" · phim("Tab", false, "in-sbd") -> "in-ma" */
"use strict";

(function (goc) {
  const SO = /^\d+$/;
  const khoangCach = (a, b) => { let d = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) d++; return d; };

  /** SBD trong danh sách CÙNG độ dài, khác tối đa `toiDa` chữ số; gần nhất trước, cùng khoảng cách thì theo số. */
  function goiYGan(v, ds, soLuong = 5, toiDa = 2) {
    return [...new Set(ds || [])].filter((s) => s.length === v.length && s !== v)
      .map((s) => [khoangCach(s, v), s]).filter(([d]) => d <= toiDa)
      .sort((x, y) => x[0] - y[0] || (x[1] < y[1] ? -1 : 1)).slice(0, soLuong).map(([, s]) => s);
  }

  /** muc: "trong" (chưa gõ) | "loi" (không lưu được) | "canh_bao" (lưu được nhưng phải xác nhận) | "ok" | "chua_kiem" (kỳ thi chưa có danh sách). */
  function kiemSbd(v, dsSbd) {
    v = String(v ?? "").trim();
    if (!v) return { muc: "trong", thong_bao: "", goi_y: [] };
    if (!SO.test(v)) return { muc: "loi", thong_bao: "SBD chỉ gồm chữ số (0–9).", goi_y: [] };
    if (dsSbd === null) return { muc: "chua_kiem", thong_bao: "Không tải được danh sách dự thi – chưa kiểm được SBD này.", goi_y: [] };
    const ds = dsSbd || [];
    if (!ds.length) return { muc: "chua_kiem", thong_bao: "Kỳ thi chưa có danh sách dự thi – chưa kiểm được SBD này.", goi_y: [] };
    if (ds.includes(v)) return { muc: "ok", thong_bao: "", goi_y: [] };
    return { muc: "canh_bao", thong_bao: `SBD ${v} không có trong danh sách dự thi của kỳ thi – lưu vẫn được nhưng phiếu tiếp tục chờ duyệt, KHÔNG ghi điểm.`,
      goi_y: goiYGan(v, ds) };
  }

  function kiemMaDe(v, dsMa) {
    v = String(v ?? "").trim();
    const ds = dsMa || [];
    if (!v) return { muc: "trong", thong_bao: "", goi_y: [] };
    if (!SO.test(v)) return { muc: "loi", thong_bao: "Mã đề chỉ gồm chữ số (0–9).", goi_y: ds.slice() };
    if (ds.includes(v)) return { muc: "ok", thong_bao: "", goi_y: [] };
    return { muc: "canh_bao", thong_bao: `Mã đề ${v} không thuộc kỳ thi (mã đề hợp lệ: ${ds.join(", ") || "chưa có"}) – lưu vẫn được nhưng phiếu không chấm được.`,
      goi_y: ds.slice() };
  }

  /** Các câu phải hỏi XÁC NHẬN trước khi lưu (rỗng = lưu ngay). `tuGoiY` = {sbd, ma}: giá trị giáo viên điền bằng nút GỢI Ý (không phải máy đọc). */
  function canXacNhan(sbd, ma, kqSbd, kqMa, tuGoiY = {}) {
    const ra = [];
    if (kqSbd.muc === "canh_bao") ra.push(kqSbd.thong_bao);
    if (kqMa.muc === "canh_bao") ra.push(kqMa.thong_bao);
    if (sbd && tuGoiY.sbd === sbd) ra.push(`SBD ${sbd} lấy từ GỢI Ý danh sách, KHÔNG phải chữ số máy đọc trên phiếu – chỉ chọn khi đã so với ảnh.`);
    return ra;
  }

  /** Có lỗi chặn lưu (chữ không phải số) hay không – hai trường đều trống cũng chặn. */
  const chanLuu = (kqSbd, kqMa) => kqSbd.muc === "loi" || kqMa.muc === "loi" || (kqSbd.muc === "trong" && kqMa.muc === "trong");

  /** Phiếu cần xem kế tiếp theo thứ tự hàng đợi; phiếu hiện tại đã ra khỏi hàng đợi thì lấy phiếu đầu. null nếu không còn phiếu khác. */
  function keTiep(ids, hienTai) {
    const ds = (ids || []).filter((i) => i !== hienTai);
    if (!ds.length) return null;
    const i = (ids || []).indexOf(hienTai);
    if (i < 0) return ds[0];
    return ids.slice(i + 1).find((x) => x !== hienTai) ?? ds[0];
  }

  /** Phím tắt trong hai ô nhập: Enter -> "luu"; Tab ở ô SBD -> "in-ma"; Shift+Tab ở ô mã đề -> "in-sbd"; còn lại null (để trình duyệt xử lý). */
  function phim(key, shift, idO) {
    if (idO !== "in-sbd" && idO !== "in-ma") return null;
    if (key === "Enter") return "luu";
    if (key === "Tab" && !shift && idO === "in-sbd") return "in-ma";
    if (key === "Tab" && shift && idO === "in-ma") return "in-sbd";
    return null;
  }

  /** Cột cần nhìn kỹ (tô nổi bật + phóng to ảnh): máy gắn cần xem, ô tô không đọc được, hoặc – khi CẢ TRƯỜNG bị giữ vì ô viết tay trống
      (o_trong_ngoai_ds / o_trong_chua_biet_ds, cùng quy ước với ly_do_cot.js) – chính các cột có ô viết tay trống. */
  const LY_DO_O_TRONG = ["o_trong_ngoai_ds", "o_trong_chua_biet_ds"];
  const cotCanNhin = (c, truong) => !!(c && (c.can_xem || c.chu_so === "?" || c.bubble === "?" ||
    (truong && (truong.reasons || []).some((m) => LY_DO_O_TRONG.includes(m)) && c.handwriting && c.handwriting.o_trong)));

  const DuyetDinhDanh = { goiYGan, kiemSbd, kiemMaDe, canXacNhan, chanLuu, keTiep, phim, cotCanNhin };
  if (typeof module !== "undefined" && module.exports) module.exports = { DuyetDinhDanh };
  else goc.DuyetDinhDanh = DuyetDinhDanh;
})(typeof window !== "undefined" ? window : globalThis);
