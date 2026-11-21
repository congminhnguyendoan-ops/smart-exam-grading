"use strict";

(function (goc) {
  function laNhieuOThuan(q) {
    return Array.isArray(q.reasons) && q.reasons.length === 1 && q.reasons[0] === "nhieu_o";
  }

  function coTheHoanTac(q, phieu) {
    return Boolean(q && q.da_xem && !q.needs_review && phieu && (phieu.status === "graded" || phieu.status === "needs_review"));
  }

  function loaiHoanTac(q) {
    return laNhieuOThuan(q) ? "tu_cham" : "cho";
  }

  function canHoiXacNhan(q, phieu) {
    const diem = phieu && phieu.score ? phieu.score.official : null;
    return loaiHoanTac(q) === "cho" && diem !== null && diem !== undefined;
  }

  function loiHoi(q, phieu) {
    if (!canHoiXacNhan(q, phieu)) return null;
    return `Hoàn tác câu ${q.question_no}? Điểm chính thức sẽ bị rút về điểm tạm cho tới khi duyệt xong lại.`;
  }

  function nhanNut(q) {
    return loaiHoanTac(q) === "tu_cham" ? "Hoàn tác (về tự chấm sai, chưa xem)" : "Hoàn tác (về chờ xem)";
  }

  function nutHtml(q, phieu) {
    if (!coTheHoanTac(q, phieu)) return "";
    return `<button type="button" class="nut-hoan-tac" data-undo="${q.question_no}">${nhanNut(q)}</button>`;
  }

  const HoanTac = { laNhieuOThuan, coTheHoanTac, loaiHoanTac, canHoiXacNhan, loiHoi, nhanNut, nutHtml };
  if (typeof module !== "undefined" && module.exports) module.exports = { HoanTac };
  else goc.HoanTac = HoanTac;
})(typeof window !== "undefined" ? window : globalThis);
