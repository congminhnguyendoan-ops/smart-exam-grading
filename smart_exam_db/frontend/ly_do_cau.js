"use strict";

(function (goc) {
  const DAI = {
    o_mo: "Máy chưa chắc ô này đã được tô đặc (nét tô nhạt, hoặc tô gạch chéo / có bóng đổ) – hãy nhìn ảnh rồi xác nhận",
    nhieu_o: "tô nhiều ô",
    khong_o_nao: "không thấy ô nào",
    tin_cay_thap: "máy chưa chắc",
    vi_tri: "chưa chắc vị trí hàng",
    vet_nho: "vết nhỏ trong ô không chọn",
    to_nhat: "phiếu tô nhạt cả tờ",
  };
  const NGAN = { ...DAI, o_mo: "ô chưa chắc đã tô đặc" };
  const GOI_Y_O_MO = DAI.o_mo + ".";

  const chuoi = (reasons, bang) => (reasons || []).map((r) => (bang || DAI)[r] || r).join(", ");
  const doTinCay = (q) => (q && typeof q.confidence === "number" ? `độ tin cậy của máy ${Math.round(q.confidence * 100)}%` : "");

  const LyDoCau = { DAI, NGAN, GOI_Y_O_MO, chuoi, doTinCay };
  if (typeof module !== "undefined" && module.exports) module.exports = { LyDoCau };
  else goc.LyDoCau = LyDoCau;
})(typeof window !== "undefined" ? window : globalThis);
