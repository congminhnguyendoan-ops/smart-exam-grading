/* Smart Exam – giao diện demo (HTML + JS thuần, gọi API FastAPI cùng gốc). Màn hình: F1 tải ảnh, F2 danh sách phiếu,
   F3 chi tiết phiếu, F4 duyệt câu cần xem + chốt SBD / mã đề, F5 bảng điểm + xuất Excel; đăng nhập, Hồ sơ, Lớp của tôi.
   Phiên đăng nhập là cookie HttpOnly do máy chủ đặt – KHÔNG lưu token ở localStorage (chỉ nhớ kỳ thi đang chọn). */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const main = $("#main");
const state = { examId: null, exams: [], exam: null, reasons: {}, me: null, biet: null, moi: new Set(), chuKy: "" };

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
  const { khongChuyen, ...fo } = opts;                 // khongChuyen: lỗi 401 của chính màn đăng nhập thì KHÔNG quay về đăng nhập
  const r = await fetch(path, { credentials: "same-origin", ...fo });
  let body = null;
  try { body = await r.json(); } catch (_) { /* ảnh / rỗng */ }
  if (!r.ok) {
    if (r.status === 401 && !khongChuyen) {
      state.me = null; manDangNhap("Chưa đăng nhập hoặc phiên đã hết hạn – hãy đăng nhập lại.");
      const e = new Error("Cần đăng nhập."); e.dangNhap = true; throw e;
    }
    let d = body && body.detail;
    if (Array.isArray(d)) d = d.map((x) => x.msg).join("; ");
    throw new Error(d || `Lỗi ${r.status}`);
  }
  return body;
}
const post = (p, data) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const patch = (p, data) => api(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const put = (p, data) => api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

/* ------------------------------------------------------------------ kỳ thi */
/* Nhãn ô chọn kỳ thi: số phiếu PHẢI làm mới sau mỗi lần tải / duyệt (trước F3 chỉ nạp một lần nên hiện "(0 phiếu)" dù đã có phiếu). */
const nhanKyThi = (e, soPhieu) => `${esc(e.exam_title)} · ${esc(e.class_code || "không lớp")} (${soPhieu} phiếu)`;
function lamMoiNhanKyThi(e) {
  const dm = state.exams.find((x) => x.exam_id === e.exam_id);
  if (dm) dm.so_phieu = e.sheets.tong;
  const opt = [...$("#exam-select").options].find((o) => Number(o.value) === e.exam_id);
  if (opt && dm) opt.innerHTML = nhanKyThi(dm, e.sheets.tong);
}
async function napKyThi() {
  state.exams = await api("/exams");
  const sel = $("#exam-select");
  // Tên kỳ thi đứng ĐẦU: ô chọn trong thanh bên hẹp cắt phần cuối; đủ "Môn – Lớp – tên" ở title (rê chuột) và ở #exam-name (xuống dòng).
  sel.innerHTML = state.exams.map((e) => `<option value="${e.exam_id}" title="${esc(e.subject_name)} – ${esc(e.class_code || "không lớp")} – ${esc(e.exam_title)}">` +
    `${nhanKyThi(e, e.so_phieu)}</option>`).join("");
  let saved = null; try { saved = localStorage.getItem("examId"); } catch (_) { /* bỏ qua */ }
  state.examId = state.exams.some((e) => String(e.exam_id) === saved) ? Number(saved)
    : (state.exams.find((e) => e.exam_title.startsWith("[DEMO]")) || state.exams[state.exams.length - 1] || {}).exam_id || null;
  sel.value = state.examId ?? "";
  await napChiTietKyThi();
}
async function napChiTietKyThi() {
  state.exam = state.examId ? await api(`/exams/${state.examId}`) : null;
  const e = state.exam;
  if (e) lamMoiNhanKyThi(e);
  $("#exam-name").textContent = e ? e.exam_title : "";
  $("#exam-select").title = e ? `${e.subject_name} – ${e.class_code || "không lớp"} – ${e.exam_title}` : "";
  $("#exam-info").textContent = e ? `Môn ${e.subject_name} · lớp ${e.class_code || "(không gắn lớp)"} · ${e.num_questions} câu · ${e.max_score} điểm · mã đề ${e.codes.map((c) => c.code).join(", ")} · ` +
    `${e.sheets.tong} phiếu (${e.sheets.da_cham} chính thức, ${e.sheets.can_xem} cần xem, ${e.sheets.bi_tu_choi} từ chối)` : "Chưa có kỳ thi.";
  const n = $("#nav-count");
  n.textContent = e ? e.sheets.can_xem : ""; n.classList.toggle("hidden", !e || !e.sheets.can_xem);
}
$("#exam-select").addEventListener("change", async (ev) => {
  state.examId = Number(ev.target.value); state.biet = null; state.moi.clear();
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
    if (!state.me) { manDangNhap(); return; }
    if (!state.examId && ["upload", "sheets", "review", "results"].includes(r)) { main.innerHTML = '<div class="alert warn">Chưa có kỳ thi. Chạy <code>python tools/nap_demo.py</code> để nạp dữ liệu demo.</div>'; return; }
    if (r === "upload") await manUpload();
    else if (r === "sheets") await manDanhSach();
    else if (r === "sheet") await manChiTiet(Number(id));
    else if (r === "review") { if (id) await manDuyet(Number(id)); else await manHangDoi(); }
    else if (r === "results") await manBangDiem();
    else if (r === "classes") { if (id) await manSinhVienLop(Number(id)); else await manLop(); }
    else if (r === "profile") await manHoSo();
    else main.innerHTML = '<p class="muted">Không có trang này.</p>';
  } catch (e) { if (!e.dangNhap) main.innerHTML = `<div class="alert bad">${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------------ đăng nhập / hồ sơ / lớp của tôi */
const NHAN_VAI_TRO = { admin: "Quản trị viên", teacher: "Giáo viên", student: "Sinh viên" };
function hienNguoiDung() {
  const me = state.me;
  $("#userbox").classList.toggle("hidden", !me);
  document.body.classList.toggle("logged-out", !me);
  if (me) { $("#u-name").textContent = me.full_name; $("#u-role").textContent = `${NHAN_VAI_TRO[me.role] || me.role} · ${me.username}`; }
}
function manDangNhap(thongBao) {
  state.me = null; hienNguoiDung();
  main.innerHTML = `<div class="card login"><h2>Đăng nhập</h2>
    ${thongBao ? `<div class="alert warn">${esc(thongBao)}</div>` : ""}
    <form id="f-login"><label>Tên đăng nhập<input type="text" id="lg-user" autocomplete="username" required></label>
      <label>Mật khẩu<input type="password" id="lg-pass" autocomplete="current-password" required></label>
      <button class="pri" type="submit">Đăng nhập</button><div id="lg-err" class="alert bad hidden"></div></form></div>`;
  $("#f-login").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = $("#f-login button"); btn.disabled = true;
    try {
      await api("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, khongChuyen: true,
        body: JSON.stringify({ username: $("#lg-user").value, password: $("#lg-pass").value }) });
      await khoiDong();
    } catch (e) { const er = $("#lg-err"); er.textContent = e.message; er.classList.remove("hidden"); btn.disabled = false; }
  });
}
$("#logout").addEventListener("click", async () => {
  try { await api("/auth/logout", { method: "POST", khongChuyen: true }); } catch (_) { /* bỏ qua */ }
  state.examId = null; state.exams = []; state.exam = null; state.biet = null; state.moi.clear();
  manDangNhap("Đã đăng xuất.");
});
async function manHoSo() {
  const me = await api("/me"); state.me = me; hienNguoiDung();
  const ln = me.last_login_at ? new Date(me.last_login_at).toLocaleString("vi-VN") : "chưa có";
  main.innerHTML = `<h2>Hồ sơ</h2><div class="card"><h3>Thông tin cá nhân</h3>
      <dl class="kv"><dt>Tên đăng nhập</dt><dd>${esc(me.username)}</dd><dt>Vai trò</dt><dd>${esc(NHAN_VAI_TRO[me.role] || me.role)}</dd>
        <dt>Đăng nhập gần nhất</dt><dd>${esc(ln)}</dd></dl>
      <form id="f-ho-so" class="formcol"><label>Họ tên<input type="text" id="hs-ten" value="${esc(me.full_name)}" required></label>
        <label>Email<input type="text" id="hs-mail" value="${esc(me.email)}" required></label>
        <button class="pri" type="submit">Lưu thông tin</button></form></div>
    <div class="card"><h3>Đổi mật khẩu</h3><form id="f-mk" class="formcol">
        <label>Mật khẩu hiện tại<input type="password" id="mk-cu" autocomplete="current-password" required></label>
        <label>Mật khẩu mới (tối thiểu 8 ký tự)<input type="password" id="mk-moi" autocomplete="new-password" required></label>
        <button class="pri" type="submit">Đổi mật khẩu</button></form>
      <p class="muted small">Sau khi đổi mật khẩu bạn cần đăng nhập lại.</p></div>`;
  $("#f-ho-so").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { state.me = await patch("/me", { full_name: $("#hs-ten").value, email: $("#hs-mail").value }); hienNguoiDung(); toast("Đã lưu thông tin."); }
    catch (e) { toast(e.message, true); }
  });
  $("#f-mk").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await post("/me/password", { old_password: $("#mk-cu").value, new_password: $("#mk-moi").value }); manDangNhap("Đã đổi mật khẩu – hãy đăng nhập lại."); }
    catch (e) { toast(e.message, true); }
  });
}
async function manLop() {
  const ds = await api("/me/classes");
  main.innerHTML = `<h2>Lớp của tôi</h2><div class="card">${ds.length ? `<table><thead><tr><th>Mã lớp</th><th>Tên lớp</th><th>Năm học</th><th>Môn tôi dạy</th><th>Sinh viên</th></tr></thead><tbody>
    ${ds.map((c) => `<tr class="row-link" data-id="${c.class_id}"><td><a href="#/classes/${c.class_id}">${esc(c.class_code)}</a></td><td>${esc(c.class_name)}</td>
      <td>${esc(c.academic_year || "–")}</td><td>${c.subject_name ? esc(c.subject_code + " – " + c.subject_name) : '<span class="muted">–</span>'}</td><td>${c.so_sinh_vien}</td></tr>`).join("")}
    </tbody></table>` : '<p class="muted">Bạn chưa được phân công lớp nào. Nhờ quản trị viên gán lớp.</p>'}</div>`;
  main.querySelectorAll("tr.row-link").forEach((tr) => tr.addEventListener("click", () => { location.hash = `#/classes/${tr.dataset.id}`; }));
}
async function manSinhVienLop(id, q = "", trang = 1) {
  const r = await api(`/classes/${id}/students?q=${encodeURIComponent(q)}&page=${trang}&page_size=50`);
  const tongTrang = Math.max(1, Math.ceil(r.tong / r.co_trang));
  main.innerHTML = `<h2>Lớp ${esc(r.lop.class_code)} – ${esc(r.lop.class_name)}</h2><div class="card">
    <div class="row" style="margin:0 0 10px"><a href="#/classes">← Lớp của tôi</a>
      <form id="f-tim" class="row" style="margin:0"><input type="text" id="tim" placeholder="Tìm theo mã hoặc họ tên" value="${esc(q)}"><button type="submit">Tìm</button></form>
      <span class="muted small">${r.tong} sinh viên</span></div>
    <table><thead><tr><th>Mã SV</th><th>Họ tên</th><th>Ngày sinh</th><th>Giới tính</th><th>Email</th></tr></thead><tbody>
    ${r.sinh_vien.map((s) => `<tr><td>${esc(s.student_code)}</td><td>${esc(s.full_name)}</td><td>${esc(s.date_of_birth || "–")}</td><td>${esc(s.gender || "–")}</td><td>${esc(s.email || "–")}</td></tr>`).join("")
      || '<tr><td colspan="5" class="muted">Không có sinh viên phù hợp.</td></tr>'}</tbody></table>
    <div class="pager"><button id="truoc" ${trang <= 1 ? "disabled" : ""}>‹ Trước</button><span class="small">Trang ${trang} / ${tongTrang}</span>
      <button id="sau" ${trang >= tongTrang ? "disabled" : ""}>Sau ›</button></div></div>`;
  $("#f-tim").addEventListener("submit", (ev) => { ev.preventDefault(); manSinhVienLop(id, $("#tim").value, 1).catch((e) => toast(e.message, true)); });
  $("#truoc").addEventListener("click", () => manSinhVienLop(id, q, trang - 1).catch((e) => toast(e.message, true)));
  $("#sau").addEventListener("click", () => manSinhVienLop(id, q, trang + 1).catch((e) => toast(e.message, true)));
}

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
    ${ds.map((p) => `<tr class="row-link${state.moi.has(p.sheet_id) ? " moi" : ""}" data-id="${p.sheet_id}"><td>${p.sheet_id}${state.moi.has(p.sheet_id) ? ' <span class="tag ok">mới</span>' : ""}</td><td>${esc(p.original_filename)}</td>
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
      ${p.image_deleted_at ? `<div class="alert warn">Ảnh đã được xoá lúc ${esc(new Date(p.image_deleted_at).toLocaleString("vi-VN"))} sau khi chốt phiếu (chính sách giữ ảnh tạm). Điểm, đáp án và lý do vẫn được giữ.</div>` : ""}
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
  if (p.reject_code === "bi_thay_the" || p.reject_code === "chup_lai_bi_bo")      // phiếu trùng SBD đã xử lý (không phải lỗi ảnh)
    return `<div class="alert warn"><b>${p.reject_code === "bi_thay_the" ? "Phiếu cũ đã bị thay bằng phiếu khác (trùng SBD)." : "Ảnh chụp lại đã bị bỏ (giữ phiếu cũ, trùng SBD)."}</b><br>${esc(p.reject_message)}</div>`;
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
    ${ds.map((p) => `<tr class="${state.moi.has(p.sheet_id) ? "moi" : ""}"><td>${p.sheet_id}${state.moi.has(p.sheet_id) ? ' <span class="tag ok">mới</span>' : ""}</td><td>${esc(p.original_filename)}</td><td>${esc(p.detected_sbd || "–")}</td><td>${esc(p.detected_exam_code || "–")}</td>
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
  const trung = p.status === "needs_review" && rv && rv.reasons.includes("duplicate_sbd") && rv.details && rv.details.duplicate_with_sheet_id ? rv.details.duplicate_with_sheet_id : null;
  let phieuCu = null;
  if (trung) { try { phieuCu = await api(`/sheets/${trung}`); } catch (_) { /* không đọc được: vẫn cho xử lý, chỉ thiếu thông tin so sánh */ } }
  main.innerHTML = `<p><a href="#/review">← Hàng đợi</a> · <a href="#/sheet/${id}">Chi tiết phiếu</a></p>
    <h2>Duyệt phiếu #${id} ${tag(p.status)}</h2>
    <div class="card"><div class="score">${diemHtml(p.score, p.status)}</div>
      ${p.status === "graded" ? '<div class="alert ok">Đã chốt điểm chính thức – phiếu duyệt xong. <a href="#/review">Sang phiếu tiếp theo →</a></div>' : ""}
      ${rv && p.status === "needs_review" ? `<div class="alert warn">Còn lại: ${rv.reasons.map((r) => LY_DO_PHIEU[r] || r).join("; ")}</div>` : ""}
      <p class="muted small">Sinh viên: ${p.student ? esc(p.student.full_name) + " (" + esc(p.student.student_code) + ")" : "chưa ghép được"} · Mã đề: ${esc((p.exam_code && p.exam_code.matched_code) || "chưa xác định")}</p></div>
    ${trung ? khungTrung(p, trung, phieuCu) : ""}
    ${dinhDanhCan ? khungDinhDanh(p) : ""}
    <h3>Câu cần xem (${p.questions.filter((q) => q.needs_review).length} còn lại)</h3>
    ${the.map((q) => theCau(id, q)).join("") || '<p class="muted">Không có câu nào cần xem.</p>'}`;
  if (trung) {
    $("#trung-bo").addEventListener("click", () => boPhieuTrung(id, trung));
    $("#trung-thay").addEventListener("click", () => thayPhieuCu(id, trung, phieuCu));
  }
  if (dinhDanhCan) {
    $("#luu-dd").addEventListener("click", () => luuDinhDanh(id));
    main.querySelectorAll("button[data-fill]").forEach((b) => b.addEventListener("click", () => { $("#" + b.dataset.fill).value = b.dataset.val; }));
  }
  main.querySelectorAll(".rcard").forEach((el) => gan(el, id));
  await napChiTietKyThi();
}
/* Phiếu bị giữ vì trùng SBD với một phiếu đã có điểm chính thức: giáo viên chọn giữ phiếu cũ hay dùng phiếu này. Không bao giờ tự động. */
function khungTrung(p, cu, pc) {
  const diemCu = pc && pc.score && pc.score.official !== null ? `${fmt(pc.score.official)} / ${fmt(pc.score.max_score)}` : "–";
  return `<div class="card" id="khung-trung"><h3>Trùng SBD với phiếu #${cu}</h3>
    <div class="alert warn">Thí sinh <b>${p.student ? esc(p.student.full_name) + " (" + esc(p.student.student_code) + ")" : "?"}</b> đã có phiếu <a href="#/sheet/${cu}">#${cu}</a>
      với điểm chính thức <b>${diemCu}</b>. Mỗi thí sinh chỉ được MỘT điểm chính thức, nên phiếu này đang bị giữ lại. Hãy chọn:</div>
    <div class="row"><button id="trung-bo">Bỏ phiếu chụp lại (giữ phiếu cũ #${cu})</button>
      <button class="pri" id="trung-thay">Dùng phiếu này thay phiếu cũ #${cu}</button></div>
    <p class="small muted">"Bỏ phiếu chụp lại": phiếu này bị loại, điểm của phiếu cũ không đổi. "Dùng phiếu này thay phiếu cũ": điểm chính thức của phiếu cũ bị rút
      (ghi vào nhật ký điểm: ai, lúc nào, phiếu nào thay phiếu nào), phiếu này duyệt tiếp rồi mới có điểm chính thức.</p></div>`;
}
async function boPhieuTrung(id, cu) {
  if (!confirm(`Bỏ phiếu #${id} (ảnh chụp lại) và GIỮ phiếu cũ #${cu}?
Điểm của phiếu cũ không đổi.`)) return;
  try { await post(`/sheets/${id}/duplicate/discard`, {}); toast(`Đã bỏ phiếu #${id}, giữ phiếu cũ #${cu}.`); await napChiTietKyThi(); location.hash = "#/review"; }
  catch (e) { toast(e.message, true); }
}
async function thayPhieuCu(id, cu, pc) {
  const diem = pc && pc.score && pc.score.official !== null ? ` (điểm chính thức ${fmt(pc.score.official)})` : "";
  if (!confirm(`DÙNG phiếu #${id} THAY phiếu cũ #${cu}${diem}?

Điểm chính thức của phiếu #${cu} sẽ bị RÚT và phiếu #${cu} không còn được tính.
Việc này được ghi vào nhật ký điểm (người làm, thời điểm).`)) return;
  try { await post(`/sheets/${id}/duplicate/replace`, { old_sheet_id: cu, confirm: true }); toast(`Đã thay phiếu #${cu} bằng phiếu #${id}.`); await manDuyet(id); }
  catch (e) { toast(e.message, true); }
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
    const canhBao = d.duplicate_pending ? `<span class="tag bad">Còn ${d.duplicate_pending} phiếu trùng chờ duyệt</span> ${d.duplicate_sheet_ids.map((s) => `<a href="#/review/${s}">#${s}</a>`).join(" ")}` : "";
    return `<tr><td>${d.stt}</td><td>${esc(d.sbd)}</td><td>${esc(d.full_name)}</td><td>${esc(d.exam_code || "–")}</td>
      <td>${d.num_correct ?? "–"}</td><td>${diem}</td><td>${tam}</td><td><span class="tag ${c}">${esc(t)}</span></td>
      <td>${d.sheet_id ? `<a href="#/sheet/${d.sheet_id}">#${d.sheet_id}</a>` : "–"}</td><td>${canhBao}</td></tr>`;
  };
  main.innerHTML = `<h2>Bảng điểm</h2>
    <p><b>Môn:</b> ${esc(b.subject_code)} – ${esc(b.subject_name)} · <b>Lớp:</b> ${b.class_code ? esc(b.class_code + " – " + b.class_name) : "(không gắn lớp)"} · <b>Kỳ thi:</b> ${esc(b.exam_title)}</p>
    <div class="card"><div class="row" style="margin:0 0 10px">
      <span class="tag ok">Chính thức: ${k.official}</span><span class="tag warn">Chưa duyệt xong: ${k.pending}</span>
      <span class="tag bad">Bị từ chối: ${k.rejected}</span><span class="tag gray">Chưa có phiếu: ${k.no_sheet}</span>
      ${k.students_duplicate_pending ? `<span class="tag bad">Thí sinh có phiếu trùng SBD chờ duyệt: ${k.students_duplicate_pending}</span>` : ""}
      <a class="btn pri" href="/exams/${state.examId}/export.xlsx" download>Xuất Excel</a></div>
      ${k.students_duplicate_pending ? `<div class="alert warn">${k.students_duplicate_pending} thí sinh còn phiếu <b>trùng SBD</b> đang chờ duyệt. Điểm ở bảng là của phiếu đã chính thức; hãy xử lý các phiếu trùng ở cột "Cảnh báo" trước khi xuất Excel chốt.</div>` : ""}
      <p class="muted small">Cột <b>Điểm</b> chỉ có điểm chính thức. Điểm của phiếu chưa duyệt xong nằm ở cột <b>Điểm tạm</b> và chưa phải điểm chính thức.
        Phiếu bị từ chối là ảnh không dùng được nên không biết của thí sinh nào (chụp lại).</p>
      <table><thead><tr><th>STT</th><th>SBD</th><th>Họ tên</th><th>Mã đề</th><th>Số câu đúng</th><th>Điểm</th><th>Điểm tạm</th><th>Trạng thái</th><th>Phiếu</th><th>Cảnh báo</th></tr></thead>
      <tbody>${b.rows.map(hang).join("") || '<tr><td colspan="10" class="muted">Kỳ thi chưa có danh sách thí sinh.</td></tr>'}</tbody></table></div>
    ${b.unmatched.length ? `<div class="card"><h3>Phiếu chưa ghép được thí sinh (${b.unmatched.length})</h3><table><thead><tr><th>Phiếu</th><th>Ảnh</th><th>Trạng thái</th><th>Lý do</th></tr></thead><tbody>
      ${b.unmatched.map((p) => `<tr><td><a href="#/sheet/${p.sheet_id}">#${p.sheet_id}</a></td><td>${esc(p.original_filename)}</td><td>${tag(p.status)}</td>
        <td>${p.status === "rejected" ? esc(p.reject_message || p.reject_code) : "SBD đọc: " + esc(p.detected_sbd || "–") + " – chưa khớp danh sách"}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
}

/* ------------------------------------------------------------------ tự làm mới (phiếu chụp từ điện thoại) */
/* Mỗi 4 s, CHỈ khi tab đang hiện: lấy danh sách phiếu của kỳ thi; có phiếu mới / đổi trạng thái thì báo + vẽ lại F2 / hàng đợi (không cuộn trang). */
const CHU_KY_THAM_DO_MS = 4000;
async function thamDo() {
  if (document.hidden || !state.me || !state.examId) return;
  const examId = state.examId;
  let ds;
  try { ds = await api(`/exams/${examId}/sheets`); } catch (_) { return; }        // lỗi mạng tạm thời: bỏ qua lượt này
  if (examId !== state.examId) return;
  const ids = ds.map((p) => p.sheet_id);
  const chuKy = ds.map((p) => `${p.sheet_id}:${p.status}:${p.raw_score}:${p.official_score}`).join("|");
  if (state.biet === null) { state.biet = new Set(ids); state.chuKy = chuKy; return; }   // lượt đầu: chỉ lấy mốc
  const moi = ids.filter((i) => !state.biet.has(i));
  moi.forEach((i) => { state.biet.add(i); state.moi.add(i); setTimeout(() => state.moi.delete(i), 30000); });
  if (chuKy === state.chuKy) return;
  state.chuKy = chuKy;
  if (moi.length) toast(`${moi.length} phiếu mới vừa được chấm (phiếu #${moi.join(", #")}).`);
  await napChiTietKyThi();
  const [r, id] = (location.hash.replace(/^#\/?/, "") || "upload").split("/");
  try {
    if (r === "sheets") await manDanhSach();
    else if (r === "review" && !id) await manHangDoi();
  } catch (_) { /* bỏ qua */ }
}
setInterval(thamDo, CHU_KY_THAM_DO_MS);

/* Ảnh của phiếu đã chốt có thể đã bị xoá (chính sách ảnh tạm – API trả 410): thay ảnh hỏng bằng dòng chữ, không vỡ bố cục. */
document.addEventListener("error", (e) => {
  const t = e.target;
  if (t.tagName !== "IMG" || !/^\/sheets\//.test(t.getAttribute("src") || "")) return;
  const s = document.createElement("span"); s.className = "muted small"; s.textContent = "(ảnh không còn – đã xoá sau khi chốt phiếu)";
  t.replaceWith(s);
}, true);
document.addEventListener("visibilitychange", () => { if (!document.hidden) thamDo(); });

/* ------------------------------------------------------------------ kết nối điện thoại */
async function moKetNoi() {
  const dlg = $("#dlg-dt"), body = $("#dlg-dt-body");
  dlg.classList.remove("hidden"); body.innerHTML = '<p class="muted">Đang lấy địa chỉ…</p>';
  try {
    const k = await api("/meta/ket-noi");
    const khac = k.ung_vien.filter((u) => u.url !== k.url);
    body.innerHTML = `${k.lan_bat ? "" : `<div class="alert warn"><b>Máy chủ đang chỉ nghe trên máy này (127.0.0.1)</b> – điện thoại chưa vào được.
        Tắt máy chủ rồi chạy <code>python tools/chay_server_lan.py</code> (mở cho mạng nội bộ).</div>`}
      ${k.url ? `<div class="qr">${k.qr_svg}</div><div class="url-big">${esc(k.url)}</div>` : '<div class="alert bad">Không tìm thấy địa chỉ mạng nội bộ (máy chưa nối Wi‑Fi / mạng LAN?).</div>'}
      <ol><li>Điện thoại nối <b>cùng Wi‑Fi</b> với máy tính này.</li>
        <li>Mở camera điện thoại, quét mã QR (hoặc gõ địa chỉ trên vào trình duyệt).</li>
        <li>Đăng nhập → chọn kỳ thi → bấm <b>Chụp phiếu</b>. Phiếu mới tự hiện ở "Danh sách phiếu" trên máy tính.</li></ol>
      ${khac.length ? `<p class="small muted">Địa chỉ khác (nếu mã trên không vào được): ${khac.map((u) => `<code>${esc(u.url)}</code> (${esc(u.card)}${u.ao ? ", card ảo" : ""}${u.hotspot ? ", điểm phát sóng" : ""})`).join(" · ")}</p>` : ""}
      <p class="small muted">Không vào được dù cùng Wi‑Fi: tường lửa Windows chưa mở cổng ${k.cong} (lệnh in ra khi chạy <code>tools/chay_server_lan.py</code>),
        hoặc Wi‑Fi chặn thiết bị nói chuyện với nhau → dùng điểm phát sóng (hotspot) của điện thoại (xem <code>docs/thiet_ke_chup_dien_thoai.md</code> mục 4).</p>`;
  } catch (e) { if (!e.dangNhap) body.innerHTML = `<div class="alert bad">${esc(e.message)}</div>`; }
}
$("#ket-noi-dt").addEventListener("click", moKetNoi);
$("#dlg-dt-x").addEventListener("click", () => $("#dlg-dt").classList.add("hidden"));
$("#dlg-dt").addEventListener("click", (e) => { if (e.target.id === "dlg-dt") $("#dlg-dt").classList.add("hidden"); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#dlg-dt").classList.add("hidden"); });

/* ------------------------------------------------------------------ khởi động */
async function khoiDong() {
  try { state.me = await api("/me"); } catch (e) { if (!e.dangNhap) main.innerHTML = `<div class="alert bad">Không nối được API: ${esc(e.message)}</div>`; return; }
  hienNguoiDung();
  try { await napKyThi(); } catch (e) { if (e.dangNhap) return; main.innerHTML = `<div class="alert bad">Không nối được API: ${esc(e.message)}</div>`; return; }
  route();
}
khoiDong();
