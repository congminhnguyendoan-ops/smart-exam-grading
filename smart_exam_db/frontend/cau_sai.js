"use strict";

(function (goc) {
  const hoanTacDung = () => (typeof HoanTac !== "undefined" ? HoanTac : require("./hoan_tac.js").HoanTac);

  const chon = (q) => q.selected_options || "";
  const daCham = (q) => !q.needs_review && (q.is_correct === true || q.is_correct === false);
  const loaiSai = (q) => (chon(q).length > 1 ? "nhieu" : chon(q).length === 0 ? "trong" : "sai");
  const THU_TU = { nhieu: 0, trong: 1, sai: 2 };

  function lyDo(q) {
    if (q.manually_edited) return "Giáo viên đã sửa";
    const l = loaiSai(q);
    return l === "nhieu" ? "Tô nhiều ô – tự chấm sai" : l === "trong" ? "Bỏ trống" : "Chọn sai";
  }

  function moTaChon(q) {
    const l = loaiSai(q);
    return l === "nhieu" ? `thí sinh tô nhiều ô ${chon(q)}` : l === "trong" ? "thí sinh bỏ trống" : `thí sinh chọn ${chon(q)}`;
  }

  const chuaCham = (qs) => qs.filter((q) => !daCham(q)).map((q) => q.question_no);

  function danhSachSai(qs) {
    return qs.filter((q) => daCham(q) && q.is_correct === false)
      .sort((a, b) => THU_TU[loaiSai(a)] - THU_TU[loaiSai(b)] || a.question_no - b.question_no);
  }

  function tomTat(qs) {
    const sai = danhSachSai(qs);
    const dem = (l) => sai.filter((q) => loaiSai(q) === l).length;
    const dung = qs.filter((q) => daCham(q) && q.is_correct === true).length;
    const r = { tong: qs.length, dung, sai: dem("sai"), trong: dem("trong"), nhieu: dem("nhieu"), chua_cham: chuaCham(qs).length };
    r.chuoi = `${r.dung}/${r.tong} đúng · ${r.sai} sai · ${r.trong} bỏ trống · ${r.nhieu} tô nhiều ô`;
    return r;
  }

  function hanhDong(q, phieu) {
    return {
      sua: Boolean(q.needs_review || q.tu_cham_can_xem || q.da_xem),
      hoan_tac: hoanTacDung().coTheHoanTac(q, phieu),
      giu: Boolean(q.tu_cham_can_xem),
    };
  }

  const CauSai = { loaiSai, lyDo, moTaChon, chuaCham, danhSachSai, tomTat, hanhDong };
  if (typeof module !== "undefined" && module.exports) module.exports = { CauSai };
  else goc.CauSai = CauSai;
})(typeof window !== "undefined" ? window : globalThis);
