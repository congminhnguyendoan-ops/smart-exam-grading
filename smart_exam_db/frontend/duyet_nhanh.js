/* Logic THUẦN cho "duyệt nhanh" (lệnh AF, /app/ – màn Duyệt phiếu + Hàng đợi); Node: tests/js/duyet_nhanh.test.js.
   KHÔNG gọi API, KHÔNG đổi dữ liệu. Nguyên tắc: giáo viên vẫn quyết định – máy chỉ gợi ý phím tắt, gom câu để XÁC NHẬN (có hộp hỏi),
   nhãn "máy đọc / dấu hiệu", và sắp xếp hàng đợi. SBD / mã đề KHÔNG BAO GIỜ nằm trong xác nhận hàng loạt.
     phimCau("b", { tag: "BODY" })                 -> { loai: "chon", o: "B" }
     phimCau(" ", { tag: "BODY" })                 -> { loai: "xac_nhan" }      (Space = xác nhận như máy đọc câu đang chọn)
     phimCau("Enter", { tag: "INPUT" })            -> null                       (ô nhập SBD / mã đề giữ phím của lệnh AA)
     cauHangLoat(p.questions)                      -> { duoc: [{question_no, omr, reasons}], tay: [n, …] }   (AF2: duoc = chỉ nhieu_o / to_nhat)
     nhanNutHangLoat(3)                            -> "Xác nhận 3 câu nhiều ô / tô nhạt như máy đọc…"   (0 -> null = ẩn nút)
     tabKeTiep(4, 3, false)                        -> 0   (bẫy Tab trong hộp xác nhận: xoay vòng)
     nhomPhieu(g)                                  -> "dinh_danh" | "trung" | "vi_tri" | "chi_nhieu_o" | "chi_mo" | "khac" */
"use strict";

(function (goc) {
  const LUA_CHON = ["A", "B", "C", "D"];
  const BO_QUA_THE = ["INPUT", "TEXTAREA", "SELECT"];

  /** Phím tắt màn duyệt câu. ctx: { tag, laNut, trongKhungDd, dangMoHop, phu (Ctrl/Alt/Meta) }. null = để trình duyệt / khung khác xử lý.
      Không bắt phím khi: đang gõ trong ô nhập (khung SBD / mã đề của lệnh AA dùng Enter / Tab), đang mở hộp thoại, có phím phụ.
      Space / Enter trên một NÚT đang có tiêu điểm: để trình duyệt bấm nút đó (người dùng bàn phím / trình đọc màn hình). */
  function phimCau(key, ctx = {}) {
    if (ctx.phu || ctx.dangMoHop || ctx.trongKhungDd || BO_QUA_THE.includes(String(ctx.tag || "").toUpperCase())) return null;
    if (key === "Escape") return { loai: "bo_chon" };
    if (key === " " || key === "Spacebar") return ctx.laNut ? null : { loai: "xac_nhan" };
    if (key === "Enter") return ctx.laNut ? null : { loai: "luu" };
    const k = String(key || "");
    if (k.length === 1 && LUA_CHON.includes(k.toUpperCase())) return { loai: "chon", o: k.toUpperCase() };
    if (k === "n" || k === "N") return { loai: "phieu_ke_tiep" };
    return null;
  }

  /** Lệnh AF2: câu được xác nhận hàng loạt = đang cần xem và MỌI lý do ∈ {nhieu_o, to_nhat} (CÙNG điều kiện với máy chủ backend/duyet_nhanh.py –
      máy chủ mới là nơi quyết; ở đây chỉ để hiện nút / hộp). Câu mờ, vết nhỏ, lưng chừng, vị trí -> chọn từng câu bằng mắt.
      Chỉ câu trả lời – SBD / mã đề không phải phần tử của `questions` nên không bao giờ lọt vào. */
  const LY_DO_HANG_LOAT = ["nhieu_o", "to_nhat"];
  const hopLeHangLoat = (q) => !!q.needs_review && (q.reasons || []).length > 0 && (q.reasons || []).every((r) => LY_DO_HANG_LOAT.includes(r));
  function cauHangLoat(questions) {
    const can = (questions || []).filter((q) => q.needs_review);
    const tay = can.filter((q) => !hopLeHangLoat(q)).map((q) => q.question_no);
    const duoc = can.filter((q) => !tay.includes(q.question_no))
      .map((q) => ({ question_no: q.question_no, omr: q.omr_selected_options || "", reasons: (q.reasons || []).slice() }));
    return { duoc, tay };
  }

  /** Nhãn của một câu cần xem: máy đọc gì + dấu hiệu nào. muc: "nhieu" (máy đọc rõ ≥ 2 ô – nếu đúng thì câu tính SAI), "mo" (dấu mờ – người
      quyết có chọn không), "vet" (có vết nhỏ ở ô khác), "nhat" (cả tờ tô nhạt), "tay" (phải chọn tay), "khac". */
  const TEN_DAU_HIEU = { nhieu_o: "nhiều ô", o_mo: "ô mờ", vet_nho: "vết nhỏ ở ô khác", to_nhat: "cả tờ tô nhạt", tin_cay_thap: "sát ngưỡng", vi_tri: "chưa chắc vị trí hàng" };
  function nhanCau(q) {
    const ly = q.reasons || [];
    const doc = q.omr_selected_options || "";
    const muc = ly.includes("vi_tri") ? "tay" : ly.includes("nhieu_o") ? "nhieu" : ly.includes("o_mo") ? "mo"
      : ly.includes("vet_nho") ? "vet" : ly.includes("to_nhat") ? "nhat" : "khac";
    const goiY = muc === "nhieu" ? `Nếu thí sinh thật sự tô ${doc.length} ô thì câu tính SAI – xác nhận như máy đọc.`
      : muc === "mo" ? "Dấu mờ: nhìn ảnh xem là ý chọn hay vết tẩy." : muc === "vet" ? "Có vết nhỏ ở ô khác: nhìn ảnh xem có phải ý chọn không."
      : muc === "nhat" ? "Cả tờ tô nhạt: kiểm nhanh đáp án máy đọc." : muc === "tay" ? "Máy chưa chắc vị trí hàng – chọn tay." : "";
    return { may_doc: doc || "bỏ trống", dau_hieu: ly.map((r) => TEN_DAU_HIEU[r] || r).join(", "), muc, goi_y: goiY };
  }

  /** Nhãn nút hàng loạt; null = ẩn nút (phiếu không có câu hợp lệ). */
  const nhanNutHangLoat = (n) => (n > 0 ? `Xác nhận ${n} câu nhiều ô / tô nhạt như máy đọc…` : null);

  /** Bẫy Tab trong hộp thoại: chỉ số phần tử nhận tiêu điểm kế tiếp (xoay vòng). n = số phần tử, i = chỉ số hiện tại (-1 = tiêu điểm ở ngoài hộp). */
  function tabKeTiep(n, i, lui) {
    if (n <= 0) return -1;
    if (i < 0 || i >= n) return lui ? n - 1 : 0;
    return lui ? (i - 1 + n) % n : (i + 1) % n;
  }

  /** Phím trong hộp xác nhận: Esc -> { loai: "dong" }; Tab / Shift+Tab -> { loai: "tab", j } (j = phần tử nhận tiêu điểm); phím khác -> null.
      n = số phần tử nhận tiêu điểm trong hộp, i = chỉ số phần tử đang có tiêu điểm (-1 nếu ở ngoài hộp). */
  function phimHop(key, lui, n, i) {
    if (key === "Escape" || key === "Esc") return { loai: "dong" };
    if (key === "Tab") return { loai: "tab", j: tabKeTiep(n, i, !!lui) };
    return null;
  }

  /** Các dòng của hộp xác nhận (mỗi câu một dòng: số câu, máy đọc, dấu hiệu). */
  const dongXacNhan = (duoc) => duoc.map((c) => `Câu ${c.question_no}: máy đọc ${c.omr || "bỏ trống"} – ${nhanCau({ reasons: c.reasons, omr_selected_options: c.omr }).dau_hieu}`);

  /** Câu cần xem kế tiếp sau câu `hienTai` (vòng về đầu); null nếu không còn. `ds` = số câu đang cần xem theo thứ tự trên màn hình. */
  function cauKeTiep(ds, hienTai) {
    const con = (ds || []).filter((n) => n !== hienTai);
    if (!con.length) return null;
    return con.find((n) => n > hienTai) ?? con[0];
  }

  /** Nhóm một phiếu trong hàng đợi (thứ tự ưu tiên: trùng SBD > SBD / mã đề > vị trí > chỉ nhiều ô > chỉ mờ > khác). g = một dòng /review-groups. */
  function nhomPhieu(g) {
    if (g.trung_sbd) return "trung";
    if (g.sbd_can_xem || g.ma_de_can_xem || g.chua_ghep) return "dinh_danh";
    const ly = Object.keys(g.ly_do_cau || {});
    if (g.co_vi_tri) return "vi_tri";
    if (ly.length && ly.every((r) => r === "nhieu_o")) return "chi_nhieu_o";
    if (ly.length && ly.every((r) => r === "o_mo")) return "chi_mo";
    return "khac";
  }
  const TEN_NHOM = { chi_nhieu_o: "Chỉ có câu tô nhiều ô", chi_mo: "Chỉ có câu mờ", khac: "Câu hỗn hợp (mờ / vết / sát ngưỡng / tô nhạt)",
    vi_tri: "Có câu phải chọn tay (vị trí)", dinh_danh: "Có SBD / mã đề cần xem", trung: "Trùng SBD" };
  const THU_TU_NHOM = ["chi_nhieu_o", "chi_mo", "khac", "vi_tri", "dinh_danh", "trung"];      // dễ trước

  /** Lọc theo nhóm ("" = tất cả) rồi sắp: nhóm dễ trước, cùng nhóm thì ít câu trước, rồi theo số phiếu. KHÔNG đổi dữ liệu. */
  function locSapHangDoi(ds, nhom = "") {
    return (ds || []).map((g) => ({ ...g, nhom: nhomPhieu(g) })).filter((g) => !nhom || g.nhom === nhom)
      .sort((a, b) => THU_TU_NHOM.indexOf(a.nhom) - THU_TU_NHOM.indexOf(b.nhom) || a.so_cau - b.so_cau || a.sheet_id - b.sheet_id);
  }

  const DuyetNhanh = { phimCau, cauHangLoat, hopLeHangLoat, nhanNutHangLoat, tabKeTiep, phimHop, LY_DO_HANG_LOAT, nhanCau, dongXacNhan, cauKeTiep, nhomPhieu, locSapHangDoi, TEN_NHOM, THU_TU_NHOM };
  if (typeof module !== "undefined" && module.exports) module.exports = { DuyetNhanh };
  else goc.DuyetNhanh = DuyetNhanh;
})(typeof window !== "undefined" ? window : globalThis);
