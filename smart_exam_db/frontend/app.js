/* Smart Exam – giao diện demo (HTML + JS thuần, gọi API FastAPI cùng gốc). Màn hình: F1 tải ảnh, F2 danh sách phiếu,
   F3 chi tiết phiếu, F4 duyệt câu cần xem + chốt SBD / mã đề, F5 bảng điểm + xuất Excel. Chưa có đăng nhập (nợ kỹ thuật). */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const main = $("#main");
const state = { examId: null, exams: [], exam: null, reasons: {} };

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(2).replace(/\.00$/, ""));

const NHAN_TRANG_THAI = { graded: ["Chính thức", "ok"], needs_review: ["Cần xem", "warn"], rejected: ["Bị từ chối", "bad"],
  processing: ["Đang xử lý", "gray"], uploaded: ["Đã tải lên", "gray"], processed: ["Đã xử lý", "gray"], error: ["Lỗi", "bad"] };
const LY_DO_CAU = { o_mo: "ô tô mờ", nhieu_o: "tô nhiều ô", khong_o_nao: "không thấy ô nào", tin_cay_thap: "máy chưa chắc", vi_tri: "chưa chắc vị trí hàng", vet_nho: "vết nhỏ trong ô không chọn", to_nhat: "phiếu tô nhạt cả tờ" };
const LY_DO_CHU_SO = { lech_bubble: "chữ viết tay khác chữ số bubble", tin_cay_thap: "chữ viết tay khó đọc (máy chưa chắc)",
  thieu_bubble: "cột bubble không đọc được (không tô / tô nhiều ô)", bubble_cx: "cột bubble máy chưa chắc",
  o_trong_ngoai_ds: "ô viết tay trống và số này không có trong danh sách", o_trong_chua_biet_ds: "ô viết tay trống, chưa kiểm được danh sách",
  o_it_muc: "ô viết tay quá ít mực", khong_phai_chu_so: "ô viết tay không giống chữ số" };
const LY_DO_PHIEU = { low_omr_confidence: "có câu máy chưa chắc", multiple_marks: "có câu tô nhiều ô", low_ocr_confidence: "SBD / mã đề chưa chắc",
  exam_code_not_found: "mã đề không có trong kỳ thi", sbd_not_found: "SBD không có trong danh sách", duplicate_sbd: "trùng SBD với phiếu khác" };

function tag(status) { const [t, c] = NHAN_TRANG_THAI[status] || [status, "gray"]; return `<span class="tag ${c}">${esc(t)}</span>`; }

function diemHtml(sc, status) {
  if (!sc || status === "rejected") return '<span class="muted">không có điểm</span>';
  if (sc.official !== null && sc.official !== undefined) return `<b>${fmt(sc.official)}</b> / ${fmt(sc.max_score)}`;
  if (sc.provisional === null || sc.provisional === undefined) return '<span class="muted">chưa chấm</span>';
  return `<b>${fmt(sc.provisional)}</b> <span class="tag warn">tạm</span> <span class="muted small">(tối đa ${fmt(sc.max_possible)})</span>`;
}
function diemTomTat(p) {
  if (p.status === "rejected") return '<span class="muted">–</span>';
  if (p.official_score !== null) return `<b>${fmt(p.official_score)}</b>`;
  if (p.raw_score !== null) return `<b>${fmt(p.raw_score)}</b> <span class="tag warn">tạm</span>`;
  return '<span class="muted">–</span>';
}

let toastT;
function toast(msg, err = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.add("hidden"), err ? 7000 : 3000);
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) { /* ảnh / rỗng */ }
  if (!r.ok) {
    let d = body && body.detail;
    if (Array.isArray(d)) d = d.map((x) => x.msg).join("; ");
    throw new Error(d || `Lỗi ${r.status}`);
  }
  return body;
}
const post = (p, data) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const put = (p, data) => api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

/* ------------------------------------------------------------------ kỳ thi */
async function napKyThi() {
  state.exams = await api("/exams");
  const sel = $("#exam-select");
  sel.innerHTML = state.exams.map((e) => `<option value="${e.exam_id}">${esc(e.exam_title)} (${e.so_phieu} phiếu)</option>`).join("");
  let saved = null; try { saved = localStorage.getItem("examId"); } catch (_) { /* bỏ qua */ }
  state.examId = state.exams.some((e) => String(e.exam_id) === saved) ? Number(saved)
    : (state.exams.find((e) => e.exam_title.startsWith("[DEMO]")) || state.exams[state.exams.length - 1] || {}).exam_id || null;
  sel.value = state.examId ?? "";
  await napChiTietKyThi();
}
async function napChiTietKyThi() {
  state.exam = state.examId ? await api(`/exams/${state.examId}`) : null;
  const e = state.exam;
  $("#exam-info").textContent = e ? `${e.num_questions} câu · ${e.max_score} điểm · mã đề ${e.codes.map((c) => c.code).join(", ")} · ` +
    `${e.sheets.tong} phiếu (${e.sheets.da_cham} chính thức, ${e.sheets.can_xem} cần xem, ${e.sheets.bi_tu_choi} từ chối)` : "Chưa có kỳ thi.";
  const n = $("#nav-count");
  n.textContent = e ? e.sheets.can_xem : ""; n.classList.toggle("hidden", !e || !e.sheets.can_xem);
}
$("#exam-select").addEventListener("change", async (ev) => {
  state.examId = Number(ev.target.value);
  try { localStorage.setItem("examId", state.examId); } catch (_) { /* bỏ qua */ }
  await napChiTietKyThi(); route();
});

/* ------------------------------------------------------------------ định tuyến */
async function route() {
  const h = location.hash.replace(/^#\/?/, "") || "upload";
  const [r, id] = h.split("/");
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.r === (r === "sheet" ? "sheets" : r)));
  window.scrollTo(0, 0);
  try {
    if (!state.examId && ["upload", "sheets", "review", "results"].includes(r)) { main.innerHTML = '<div class="alert warn">Chưa có kỳ thi. Chạy <code>python tools/nap_demo.py</code> để nạp dữ liệu demo.</div>'; return; }
    if (r === "upload") await manUpload();
    else if (r === "sheets") await manDanhSach();
    else if (r === "sheet") await manChiTiet(Number(id));
    else if (r === "review") { if (id) await manDuyet(Number(id)); else await manHangDoi(); }
    else if (r === "results") await manBangDiem();
    else main.innerHTML = '<p class="muted">Không có trang này.</p>';
  } catch (e) { main.innerHTML = `<div class="alert bad">${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------------ F1: tải ảnh */
async function manUpload() {
  if (!Object.keys(state.reasons).length) state.reasons = await api("/meta/reject-reasons");
  main.innerHTML = `<h2>Tải ảnh &amp; chấm phiếu</h2>
    <div class="card"><div class="drop" id="drop">Kéo thả ảnh phiếu (JPG / PNG / HEIC) vào đây hoặc
      <input type="file" id="files" accept="image/*,.heic" multiple></div>
      <div class="row"><button class="pri" id="go" disabled>Bắt đầu chấm</button><span id="sel" class="muted small">Chưa chọn ảnh.</span></div>
      <div class="progress hidden" id="bar"><div></div></div><div id="st" class="muted small"></div></div>
    <div class="card hidden" id="kq"><h3>Kết quả lô vừa chấm</h3>
      <table><thead><tr><th>Ảnh</th><th>Trạng thái</th><th>Chi tiết</th><th>Điểm</th><th></th></tr></thead><tbody id="rows"></tbody></table></div>`;
  let danhSach = [];
  const dat = (fl) => {
    danhSach = [...fl].filter((f) => f.type.startsWith("image/") || /\.(heic|jpe?g|png)$/i.test(f.name));
    $("#sel").textContent = danhSach.length ? `Đã chọn ${danhSach.length} ảnh.` : "Chưa chọn ảnh.";
    $("#go").disabled = !danhSach.length;
  };
  $("#files").addEventListener("change", (e) => dat(e.target.files));
  const drop = $("#drop");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); dat(e.dataTransfer.files); });
  $("#go").addEventListener("click", async () => {
    const go = $("#go"); go.disabled = true; $("#kq").classList.remove("hidden"); $("#bar").classList.remove("hidden");
    const rows = $("#rows"); rows.innerHTML = "";
    for (let i = 0; i < danhSach.length; i++) {
      const f = danhSach[i];
      $("#st").textContent = `Đang xử lý ảnh ${i + 1}/${danhSach.length}: ${f.name} …`;
      $("#bar > div").style.width = `${(i / danhSach.length) * 100}%`;
      const tr = document.createElement("tr"); tr.innerHTML = `<td>${esc(f.name)}</td><td colspan="4" class="muted">Đang xử lý…</td>`; rows.prepend(tr);
      try {
        const fd = new FormData(); fd.append("file", f, f.name);
        const r = await api(`/exams/${state.examId}/sheets`, { method: "POST", body: fd });
        tr.innerHTML = hangKetQuaTai(f.name, r);
      } catch (e) { tr.innerHTML = `<td>${esc(f.name)}</td><td>${tag("error")}</td><td colspan="3">${esc(e.message)}</td>`; }
    }
    $("#bar > div").style.width = "100%"; $("#st").textContent = `Xong ${danhSach.length} ảnh.`;
    go.disabled = false; await napChiTietKyThi();
  });
}
function hangKetQuaTai(ten, r) {
  let chiTiet = "";
  if (r.status === "rejected") {
    const ly = state.reasons[r.reject_code] || {};
    chiTiet = `<div class="alert bad"><b>${esc(r.reject_message || ly.message)}</b><br>Lời khuyên: ${esc(ly.advice || "chụp lại phiếu rõ nét, đủ sáng, thấy đủ 4 góc.")}</div>`;
  } else if (r.status === "needs_review") chiTiet = `<span class="tag warn">${r.pending_questions} câu cần xem</span>`;
  else if (r.status === "graded") chiTiet = "Máy tự chốt, không còn mục cần xem.";
  if (r.da_ton_tai) chiTiet += ' <span class="muted small">(ảnh đã tải trước đó – trả phiếu cũ)</span>';
  const diem = r.status === "rejected" ? "–" : r.official_score !== null ? `<b>${fmt(r.official_score)}</b>`
    : r.provisional_score !== null ? `<b>${fmt(r.provisional_score)}</b> <span class="tag warn">tạm</span>` : "–";
  const lien = r.status === "needs_review" ? `<a class="btn pri" href="#/review/${r.sheet_id}">Duyệt</a>`
    : r.status === "rejected" ? `<a class="btn" href="#/sheet/${r.sheet_id}">Chi tiết</a>` : `<a class="btn" href="#/sheet/${r.sheet_id}">Xem</a>`;
  return `<td>${esc(ten)}</td><td>${tag(r.status)}</td><td>${chiTiet}</td><td>${diem}</td><td>${lien}</td>`;
}

/* ------------------------------------------------------------------ F2: danh sách phiếu */
async function manDanhSach() {
  let loc = ""; try { loc = sessionStorage.getItem("loc") || ""; } catch (_) { /* bỏ qua */ }
  const qs = loc ? "?status=" + loc : "";
  const ds = await api(`/exams/${state.examId}/sheets${qs}`);
  main.innerHTML = `<h2>Danh sách phiếu</h2><div class="card">
    <div class="row" style="margin:0 0 10px"><label>Lọc: <select id="loc">
      ${[["", "Tất cả"], ["graded", "Chính thức"], ["needs_review", "Cần xem"], ["rejected", "Bị từ chối"]].map(([v, t]) => `<option value="${v}" ${v === loc ? "selected" : ""}>${t}</option>`).join("")}
    </select></label><span class="muted small">${ds.length} phiếu</span></div>
    <table><thead><tr><th>#</th><th>Ảnh</th><th>SBD</th><th>Mã đề</th><th>Sinh viên</th><th>Trạng thái</th><th>Điểm</th><th></th></tr></thead><tbody>
    ${ds.map((p) => `<tr class="row-link" data-id="${p.sheet_id}"><td>${p.sheet_id}</td><td>${esc(p.original_filename)}</td>
      <td>${p.status === "rejected" ? "–" : esc(p.detected_sbd || "–")}</td><td>${p.status === "rejected" ? "–" : esc(p.detected_exam_code || "–")}</td>
      <td>${esc(p.student_name || "–")}</td>
      <td>${tag(p.status)}${p.status === "needs_review" ? ` <span class="muted small">${p.pending_questions} câu</span>` : ""}
        ${p.status === "rejected" ? `<div class="muted small">${esc(p.reject_message || p.reject_code)}</div>` : ""}</td>
      <td>${diemTomTat(p)}</td><td>${p.status === "needs_review" ? `<a class="btn pri" href="#/review/${p.sheet_id}">Duyệt</a>` : ""}</td></tr>`).join("")
      || '<tr><td colspan="8" class="muted">Chưa có phiếu nào. Vào "Tải ảnh &amp; chấm".</td></tr>'}
    </tbody></table></div>`;
  $("#loc").addEventListener("change", (e) => { try { sessionStorage.setItem("loc", e.target.value); } catch (_) { /* bỏ qua */ } route(); });
  main.querySelectorAll("tr.row-link").forEach((tr) => tr.addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    location.hash = `#/sheet/${tr.dataset.id}`;
  }));
}

/* ------------------------------------------------------------------ F3: chi tiết phiếu */
function cotsHtml(tr) {
  if (!tr) return "–";
  return `<span class="cols">${tr.columns.map((c) => `<span class="col ${c.can_xem || c.chu_so === "?" ? "bad" : ""}" title="cột ${c.vi_tri}: tin cậy ${fmt(c.do_tin_cay)}">${esc(c.chu_so)}</span>`).join("")}</span>`;
}
/* Hai kênh cạnh nhau: ô tô (bubble) ↔ chữ viết tay (ảnh ô + chữ số máy đọc + độ tin cậy). Cột lệch / không chắc tô đỏ. */
function haiKenhHtml(sheetId, field, tr) {
  if (!tr || !tr.columns.some((c) => c.handwriting)) return "";
  const hang = (ten, f) => `<tr><th>${ten}</th>${tr.columns.map((c) => `<td class="${c.can_xem ? "lech" : ""}">${f(c)}</td>`).join("")}</tr>`;
  const ly = [...new Set(tr.columns.flatMap((c) => c.ly_do).concat(tr.reasons || []))];
  return `<table class="haikenh"><tbody>
    ${hang("Ô tô (bubble)", (c) => `<b>${esc(c.bubble ?? c.chu_so)}</b>`)}
    ${hang("Chữ viết tay", (c) => c.handwriting && c.handwriting.has_crop
      ? `<img src="/sheets/${sheetId}/digits/${field}/${c.handwriting.pos}/image" alt="ô viết tay ${c.vi_tri}">` : "–")}
    ${hang("Máy đọc", (c) => { const h = c.handwriting; if (!h) return "–";
      if (h.o_trong) return '<span class="muted">ô trống</span>';
      if (h.chu_so === "?") return `<span class="muted">không đọc được</span>`;
      return `<b>${esc(h.chu_so)}</b> <span class="muted small">${Math.round(h.p * 100)}%</span>`; })}
    ${hang("GV đã chốt", (c) => (c.handwriting && c.handwriting.corrected) ? `<b>${esc(c.handwriting.corrected)}</b>` : "")}
    </tbody></table>${ly.length ? `<p class="small muted">Lý do cần xem: ${ly.map((m) => LY_DO_CHU_SO[m] || m).join("; ")}</p>` : ""}`;
}
function cauHtml(q, dapAn) {
  const cls = q.needs_review ? "review" : q.is_correct === true ? "good" : q.is_correct === false ? "wrong" : "";
  const doc = q.selected_options || (q.state === "blank" ? "—" : "?");
  const ketQua = q.needs_review ? "?" : q.is_correct === true ? "✓" : q.is_correct === false ? "✗" : "";
  const ly = q.needs_review ? `<small>${q.reasons.map((r) => LY_DO_CAU[r] || r).join(", ")}</small>` : q.manually_edited ? '<small style="color:var(--mut)">GV đã sửa</small>' : "";
  return `<div class="q ${cls}" title="Máy đọc: ${esc(q.omr_selected_options || "bỏ trống")}${dapAn ? " · đáp án: " + dapAn : ""}"><span>Câu ${q.question_no}: <b>${esc(doc)}</b>${ly}</span><span>${ketQua}</span></div>`;
}
async function manChiTiet(id) {
  const p = await api(`/sheets/${id}`);
  const e = state.exam;
  const maKhop = p.exam_code && p.exam_code.matched_code;
  const dapAn = maKhop && e ? (e.codes.find((c) => c.code === maKhop) || {}).answers : null;
  const rv = p.review;
  const rejected = p.status === "rejected";
  main.innerHTML = `<p><a href="#/sheets">← Danh sách phiếu</a></p>
    <h2>Phiếu #${p.sheet_id} ${tag(p.status)}</h2>
    <div class="grid2"><div class="card"><h3>Ảnh đã nắn phẳng</h3>
      ${rejected ? '<p class="muted">Ảnh bị từ chối nên không có ảnh nắn.</p>' : `<a href="/sheets/${id}/image?kind=aligned" target="_blank"><img class="sheetimg" src="/sheets/${id}/image?kind=aligned" alt="ảnh đã nắn"></a>`}
      <p class="small"><a href="/sheets/${id}/image?kind=original" target="_blank">Xem ảnh gốc</a> · ${esc(p.original_filename)}</p></div>
    <div><div class="card">${rejected ? await khoiTuChoi(p) : `
      <div class="score">${diemHtml(p.score, p.status)}</div>
      ${p.score && p.score.official === null && p.score.pending_questions ? `<p class="muted small">Điểm tạm chỉ tính các câu máy chắc chắn. Điểm chính thức có sau khi giáo viên xem hết ${p.score.pending_questions} câu cần xem.</p>` : ""}
      ${p.score && p.score.result_status ? `<p class="muted small">Chốt bởi: ${p.score.result_status === "confirmed" ? "giáo viên (đã duyệt)" : "máy (tự động)"} · đúng ${p.score.num_correct ?? "–"} câu</p>` : ""}
      <dl class="kv"><dt>SBD</dt><dd>${cotsHtml(p.sbd)} <span class="muted small">${p.sbd && p.sbd.can_xem ? "cần xem" : ""}</span></dd>
        <dt>Mã đề</dt><dd>${cotsHtml(p.exam_code)} ${maKhop ? "" : '<span class="tag warn">chưa xác định</span>'}</dd>
        <dt>Sinh viên</dt><dd>${p.student ? esc(p.student.full_name) + ` (${esc(p.student.student_code)})` : '<span class="muted">chưa ghép được</span>'}</dd></dl>
      <h3>SBD: ô tô ↔ chữ viết tay</h3>${haiKenhHtml(p.sheet_id, "sbd", p.sbd)}
      <h3>Mã đề: ô tô ↔ chữ viết tay</h3>${haiKenhHtml(p.sheet_id, "exam_code", p.exam_code)}
      ${rv && p.status === "needs_review" ? `<div class="alert warn">Lý do vào hàng đợi duyệt: ${rv.reasons.map((r) => LY_DO_PHIEU[r] || r).join("; ")}</div>` : ""}
      ${p.status === "needs_review" ? `<a class="btn pri" href="#/review/${id}">Duyệt các mục cần xem →</a>` : ""}`}</div></div></div>
    ${rejected ? "" : `<div class="card"><h3>Bảng ${p.questions.length} câu</h3>
      <p class="small muted">Xanh = đúng · đỏ = sai · vàng viền đậm = cần xem (chưa tính vào điểm chính thức). Chỉ chấm khi đã biết mã đề.</p>
      <div class="qgrid">${p.questions.map((q) => cauHtml(q, dapAn ? dapAn[q.question_no - 1] : null)).join("")}</div></div>`}`;
}
async function khoiTuChoi(p) {
  if (!Object.keys(state.reasons).length) state.reasons = await api("/meta/reject-reasons");
  const ly = state.reasons[p.reject_code] || {};
  return `<div class="alert bad"><b>Ảnh bị từ chối – không có điểm.</b><br>${esc(p.reject_message || ly.message)}<br>
    <b>Lời khuyên chụp lại:</b> ${esc(ly.advice || "chụp rõ nét, đủ sáng, thấy đủ 4 góc.")}</div>
    <p class="muted small">Mã: ${esc(p.reject_code)} · <a href="/sheets/${p.sheet_id}/image?kind=original" target="_blank">xem ảnh gốc</a></p>`;
}

/* ------------------------------------------------------------------ F4: duyệt */
async function manHangDoi() {
  const ds = await api(`/exams/${state.examId}/sheets?status=needs_review`);
  main.innerHTML = `<h2>Hàng đợi duyệt (${ds.length})</h2><div class="card"><table><thead><tr><th>#</th><th>Ảnh</th><th>SBD</th><th>Mã đề</th><th>Câu cần xem</th><th>Điểm tạm</th><th></th></tr></thead><tbody>
    ${ds.map((p) => `<tr><td>${p.sheet_id}</td><td>${esc(p.original_filename)}</td><td>${esc(p.detected_sbd || "–")}</td><td>${esc(p.detected_exam_code || "–")}</td>
      <td>${p.pending_questions}</td><td>${diemTomTat(p)}</td><td><a class="btn pri" href="#/review/${p.sheet_id}">Duyệt</a></td></tr>`).join("")
      || '<tr><td colspan="7" class="muted">Không còn phiếu nào cần duyệt.</td></tr>'}</tbody></table></div>`;
}

const daXem = {};   // sheet_id -> Set(question_no) đã duyệt trong phiên này (hiện thẻ "đã chốt" thay vì biến mất)
async function manDuyet(id) {
  const p = await api(`/sheets/${id}`);
  if (p.status === "rejected") { location.hash = `#/sheet/${id}`; return; }
  const xong = (daXem[id] = daXem[id] || new Set());
  const the = p.questions.filter((q) => q.needs_review || xong.has(q.question_no));
  const dinhDanhCan = p.status === "needs_review" && p.sbd && p.exam_code &&
    (p.sbd.can_xem || p.exam_code.can_xem || !p.exam_code.matched_code || !p.student);
  const rv = p.review;
  main.innerHTML = `<p><a href="#/review">← Hàng đợi</a> · <a href="#/sheet/${id}">Chi tiết phiếu</a></p>
    <h2>Duyệt phiếu #${id} ${tag(p.status)}</h2>
    <div class="card"><div class="score">${diemHtml(p.score, p.status)}</div>
      ${p.status === "graded" ? '<div class="alert ok">Đã chốt điểm chính thức – phiếu duyệt xong. <a href="#/review">Sang phiếu tiếp theo →</a></div>' : ""}
      ${rv && p.status === "needs_review" ? `<div class="alert warn">Còn lại: ${rv.reasons.map((r) => LY_DO_PHIEU[r] || r).join("; ")}</div>` : ""}
      <p class="muted small">Sinh viên: ${p.student ? esc(p.student.full_name) + " (" + esc(p.student.student_code) + ")" : "chưa ghép được"} · Mã đề: ${esc((p.exam_code && p.exam_code.matched_code) || "chưa xác định")}</p></div>
    ${dinhDanhCan ? khungDinhDanh(p) : ""}
    <h3>Câu cần xem (${p.questions.filter((q) => q.needs_review).length} còn lại)</h3>
    ${the.map((q) => theCau(id, q)).join("") || '<p class="muted">Không có câu nào cần xem.</p>'}`;
  if (dinhDanhCan) {
    $("#luu-dd").addEventListener("click", () => luuDinhDanh(id));
    main.querySelectorAll("button[data-fill]").forEach((b) => b.addEventListener("click", () => { $("#" + b.dataset.fill).value = b.dataset.val; }));
  }
  main.querySelectorAll(".rcard").forEach((el) => gan(el, id));
  await napChiTietKyThi();
}
const chuoiCot = (tr, f) => { const v = tr.columns.map(f); return v.every((d) => /^\d$/.test(d || "")) ? v.join("") : ""; };
function khungDinhDanh(p) {
  const ma = state.exam ? state.exam.codes.map((c) => c.code).join(", ") : "";
  // Trường đang cần xem: KHÔNG điền sẵn (máy không chắc → giáo viên nhìn ảnh rồi tự chọn). Trường đã chắc: điền chữ số máy chốt.
  const sbdDoc = p.sbd.can_xem ? "" : (/^\d+$/.test(p.sbd.detected || "") ? p.sbd.detected : "");
  const maDoc = p.exam_code.can_xem ? "" : (p.exam_code.matched_code || (/^\d+$/.test(p.exam_code.detected || "") ? p.exam_code.detected : ""));
  const nut = (id, tr, f, ten) => `<button type="button" data-fill="${id}" data-val="${esc(chuoiCot(tr, f))}" ${chuoiCot(tr, f) ? "" : "disabled"}>${ten}</button>`;
  return `<div class="card"><h3>Chốt số báo danh / mã đề</h3>
    <p class="small muted">Nhìn ảnh ô viết tay cạnh ô tô; cột đỏ là chỗ hai kênh lệch hoặc máy không chắc. Máy KHÔNG tự chọn thay giáo viên.</p>
    <div class="grid2"><div class="clip"><img src="/sheets/${p.sheet_id}/image?kind=aligned" alt="đầu phiếu"></div>
    <div><h3>SBD</h3>${haiKenhHtml(p.sheet_id, "sbd", p.sbd) || cotsHtml(p.sbd)}
      <h3>Mã đề</h3>${haiKenhHtml(p.sheet_id, "exam_code", p.exam_code) || cotsHtml(p.exam_code)}
      <div class="row"><label>SBD đúng <input type="text" id="in-sbd" inputmode="numeric" value="${esc(sbdDoc)}"></label>
        ${nut("in-sbd", p.sbd, (c) => c.bubble, "Lấy theo ô tô")} ${nut("in-sbd", p.sbd, (c) => c.handwriting && c.handwriting.chu_so, "Lấy theo chữ viết tay")}</div>
      <div class="row"><label>Mã đề đúng <input type="text" id="in-ma" inputmode="numeric" value="${esc(maDoc)}"></label>
        ${nut("in-ma", p.exam_code, (c) => c.bubble, "Lấy theo ô tô")} ${nut("in-ma", p.exam_code, (c) => c.handwriting && c.handwriting.chu_so, "Lấy theo chữ viết tay")}</div>
      <p class="small muted">Mã đề của kỳ thi: ${esc(ma)}</p>
      <div class="row"><button class="pri" id="luu-dd">Lưu SBD / mã đề</button></div></div></div></div>`;
}
async function luuDinhDanh(id) {
  const sbd = $("#in-sbd").value.trim(), ma = $("#in-ma").value.trim();
  const body = {}; if (sbd) body.sbd = sbd; if (ma) body.exam_code = ma;
  if (!Object.keys(body).length) { toast("Nhập SBD và / hoặc mã đề.", true); return; }
  try { await put(`/sheets/${id}/identity`, body); toast("Đã lưu SBD / mã đề."); await manDuyet(id); }
  catch (e) { toast(e.message, true); }
}
function theCau(id, q) {
  const xong = !q.needs_review;
  const viTri = q.reasons.includes("vi_tri");
  const dacMay = q.omr_selected_options || "bỏ trống";
  return `<div class="rcard ${xong ? "done" : ""}" data-q="${q.question_no}">
    <div><img src="/sheets/${id}/questions/${q.question_no}/image" alt="câu ${q.question_no}" loading="lazy"></div>
    <div><h3>Câu ${q.question_no} ${xong ? '<span class="tag ok">đã chốt</span>' : ""}</h3>
      <p>Máy đọc: <b>${esc(dacMay)}</b> · lý do: ${q.reasons.map((r) => LY_DO_CAU[r] || r).join(", ") || "–"}</p>
      ${xong ? `<p>Đáp án đã chốt: <b>${esc(q.selected_options || "bỏ trống")}</b>${q.manually_edited ? " (giáo viên sửa)" : " (xác nhận như máy đọc)"}</p>` : `
      <div class="opts row">${["A", "B", "C", "D"].map((o) => `<button type="button" data-o="${o}">${o}</button>`).join("")}<span class="muted small">(chọn nhiều ô nếu thực sự tô 2 ô)</span></div>
      <div class="row"><button class="pri" data-act="set">Lưu lựa chọn</button><button data-act="blank">Bỏ trống</button>
        <button data-act="confirm" ${viTri ? 'disabled title="Chưa chắc vị trí hàng – phải chọn thủ công"' : ""}>Xác nhận như máy đọc (${esc(dacMay)})</button></div>
      ${viTri ? '<p class="small muted">Máy chưa chắc vị trí hàng này nên không cho xác nhận nhanh – hãy nhìn ảnh rồi chọn.</p>' : ""}`}
    </div></div>`;
}
function gan(el, id) {
  const n = Number(el.dataset.q);
  el.querySelectorAll(".opts button").forEach((b) => b.addEventListener("click", () => b.classList.toggle("sel")));
  el.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
    const act = b.dataset.act;
    let body;
    if (act === "confirm") body = { action: "confirm" };
    else if (act === "blank") body = { action: "set", selected_options: "" };
    else {
      const ch = [...el.querySelectorAll(".opts .sel")].map((x) => x.dataset.o).join("");
      if (!ch) { toast("Chọn ít nhất một đáp án, hoặc bấm 'Bỏ trống'.", true); return; }
      body = { action: "set", selected_options: ch };
    }
    el.querySelectorAll("button").forEach((x) => (x.disabled = true));
    try { await post(`/sheets/${id}/questions/${n}/review`, body); daXem[id].add(n); toast(`Câu ${n} đã chốt.`); await manDuyet(id); }
    catch (e) { toast(e.message, true); el.querySelectorAll("button").forEach((x) => (x.disabled = false)); }
  }));
}

/* ------------------------------------------------------------------ F5: bảng điểm */
const NHAN_BD = { official: ["Chính thức", "ok"], pending: ["Chưa duyệt xong – điểm tạm", "warn"], rejected: ["Bị từ chối", "bad"], no_sheet: ["Chưa có phiếu", "gray"] };
async function manBangDiem() {
  const b = await api(`/exams/${state.examId}/results`);
  const k = b.counts;
  const hang = (d) => {
    const [t, c] = NHAN_BD[d.status];
    const diem = d.score !== null ? `<b>${fmt(d.score)}</b>` : '<span class="muted">–</span>';
    const tam = d.provisional_score !== null ? `${fmt(d.provisional_score)} <span class="muted small">(${d.pending_questions} câu chờ)</span>` : '<span class="muted">–</span>';
    return `<tr><td>${d.stt}</td><td>${esc(d.sbd)}</td><td>${esc(d.full_name)}</td><td>${esc(d.exam_code || "–")}</td>
      <td>${d.num_correct ?? "–"}</td><td>${diem}</td><td>${tam}</td><td><span class="tag ${c}">${esc(t)}</span></td>
      <td>${d.sheet_id ? `<a href="#/sheet/${d.sheet_id}">#${d.sheet_id}</a>` : "–"}</td></tr>`;
  };
  main.innerHTML = `<h2>Bảng điểm</h2>
    <div class="card"><div class="row" style="margin:0 0 10px">
      <span class="tag ok">Chính thức: ${k.official}</span><span class="tag warn">Chưa duyệt xong: ${k.pending}</span>
      <span class="tag bad">Bị từ chối: ${k.rejected}</span><span class="tag gray">Chưa có phiếu: ${k.no_sheet}</span>
      <a class="btn pri" href="/exams/${state.examId}/export.xlsx" download>Xuất Excel</a></div>
      <p class="muted small">Cột <b>Điểm</b> chỉ có điểm chính thức. Điểm của phiếu chưa duyệt xong nằm ở cột <b>Điểm tạm</b> và chưa phải điểm chính thức.
        Phiếu bị từ chối là ảnh không dùng được nên không biết của thí sinh nào (chụp lại).</p>
      <table><thead><tr><th>STT</th><th>SBD</th><th>Họ tên</th><th>Mã đề</th><th>Số câu đúng</th><th>Điểm</th><th>Điểm tạm</th><th>Trạng thái</th><th>Phiếu</th></tr></thead>
      <tbody>${b.rows.map(hang).join("") || '<tr><td colspan="9" class="muted">Kỳ thi chưa có danh sách thí sinh.</td></tr>'}</tbody></table></div>
    ${b.unmatched.length ? `<div class="card"><h3>Phiếu chưa ghép được thí sinh (${b.unmatched.length})</h3><table><thead><tr><th>Phiếu</th><th>Ảnh</th><th>Trạng thái</th><th>Lý do</th></tr></thead><tbody>
      ${b.unmatched.map((p) => `<tr><td><a href="#/sheet/${p.sheet_id}">#${p.sheet_id}</a></td><td>${esc(p.original_filename)}</td><td>${tag(p.status)}</td>
        <td>${p.status === "rejected" ? esc(p.reject_message || p.reject_code) : "SBD đọc: " + esc(p.detected_sbd || "–") + " – chưa khớp danh sách"}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
}

/* ------------------------------------------------------------------ khởi động */
napKyThi().then(route).catch((e) => { main.innerHTML = `<div class="alert bad">Không nối được API: ${esc(e.message)}</div>`; });
