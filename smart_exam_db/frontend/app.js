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
const LY_DO_CAU = LyDoCau.DAI;
const LY_DO_CAU_NGAN = LyDoCau.NGAN;
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

/* Số phiên phía trình duyệt: tăng mỗi lần xoá dữ liệu phiên (đăng xuất / hết phiên). Yêu cầu gửi từ phiên trước mà trả về muộn
   thì bỏ kết quả (không vẽ dữ liệu của người trước lên màn của người sau). */
let soPhien = 0;
async function api(path, opts = {}) {
  const { khongChuyen, ...fo } = opts;                 // khongChuyen: lỗi 401 của chính màn đăng nhập thì KHÔNG quay về đăng nhập
  const phien = soPhien;
  let r;
  try { r = await fetch(path, { credentials: "same-origin", ...fo }); }
  catch (_) { throw Object.assign(new Error("Không kết nối được máy chủ (mất mạng hoặc máy chủ đã tắt)."), { ma: 0 }); }   // V1: lỗi mạng mang mã 0
  let body = null;
  try { body = await r.json(); } catch (_) { /* ảnh / rỗng */ }
  if (phien !== soPhien) { const e = new Error("Phiên đăng nhập đã thay đổi."); e.dangNhap = true; throw e; }
  if (!r.ok) {
    if (r.status === 401 && !khongChuyen) {
      state.me = null; manDangNhap("Chưa đăng nhập hoặc phiên đã hết hạn – hãy đăng nhập lại.");
      const e = new Error("Cần đăng nhập."); e.dangNhap = true; throw e;
    }
    let d = body && body.detail;
    if (Array.isArray(d)) d = d.map((x) => x.msg).join("; ");
    throw Object.assign(new Error(d || `Lỗi ${r.status}`), { ma: r.status });
  }
  return body;
}
const post = (p, data) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const patch = (p, data) => api(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const put = (p, data) => api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

/* ------------------------------------------------------------------ kỳ thi */
/* Nhãn ô chọn kỳ thi: số phiếu PHẢI làm mới sau mỗi lần tải / duyệt (trước F3 chỉ nạp một lần nên hiện "(0 phiếu)" dù đã có phiếu). */
const nhanKyThi = (e, soPhieu) => `${esc(e.exam_title)} · ${esc(e.class_code || "không lớp")} (${soPhieu} phiếu)${e.status === "closed" ? " · ĐÃ ĐÓNG" : ""}`;
function lamMoiNhanKyThi(e) {
  const dm = state.exams.find((x) => x.exam_id === e.exam_id);
  if (dm) { dm.so_phieu = e.sheets.tong; dm.status = e.status; }
  const opt = [...$("#exam-select").options].find((o) => Number(o.value) === e.exam_id);
  if (opt && dm) opt.innerHTML = nhanKyThi(dm, e.sheets.tong);
}
async function napKyThi() {
  state.exams = await api("/exams");
  let saved = null; try { saved = localStorage.getItem("examId"); } catch (_) { /* bỏ qua */ }
  // V2: kỳ thi đã đóng ẩn khỏi ô chọn (trừ khi bật "Hiện cả kỳ thi đã đóng"); kỳ thi đã lưu vẫn giữ nếu người dùng đang xem nó.
  const hienThi = KyThiDong.loc(state.exams, KyThiDong.doc());
  state.examId = state.exams.some((e) => String(e.exam_id) === saved) ? Number(saved)
    : (hienThi.find((e) => e.exam_title.startsWith("[DEMO]")) || hienThi[hienThi.length - 1] || {}).exam_id || null;
  veOChonKyThi();
  await napChiTietKyThi();
}
/* Vẽ ô chọn kỳ thi theo bộ lọc V2 (chỉ hiển thị – quyền do máy chủ kiểm). Kỳ thi đang chọn luôn có trong danh sách. */
function veOChonKyThi() {
  const sel = $("#exam-select"), hien = KyThiDong.doc(), soDong = KyThiDong.soDong(state.exams);
  // Tên kỳ thi đứng ĐẦU: ô chọn trong thanh bên hẹp cắt phần cuối; đủ "Môn – Lớp – tên" ở title (rê chuột) và ở #exam-name (xuống dòng).
  sel.innerHTML = KyThiDong.loc(state.exams, hien, state.examId).map((e) => `<option value="${e.exam_id}" title="${esc(e.subject_name)} – ${esc(e.class_code || "không lớp")} – ${esc(e.exam_title)}">` +
    `${nhanKyThi(e, e.so_phieu)}</option>`).join("");
  sel.value = state.examId ?? "";
  $("#hien-dong").checked = hien;
  $("#so-dong").textContent = soDong ? `(${soDong})` : "";
  $("#hien-dong-wrap").classList.toggle("hidden", !soDong && !hien);
}
$("#hien-dong").addEventListener("change", (ev) => { KyThiDong.luu(ev.target.checked); veOChonKyThi(); });
async function napChiTietKyThi() {
  state.exam = state.examId ? await api(`/exams/${state.examId}`) : null;
  const e = state.exam;
  if (e) lamMoiNhanKyThi(e);
  $("#exam-name").textContent = e ? e.exam_title : "";
  $("#exam-select").title = e ? `${e.subject_name} – ${e.class_code || "không lớp"} – ${e.exam_title}` : "";
  $("#exam-info").textContent = e ? `${e.status === "closed" ? "ĐÃ ĐÓNG (không nhận ảnh mới) · " : ""}Môn ${e.subject_name} · lớp ${e.class_code || "(không gắn lớp)"} · ${e.num_questions} câu · ${e.max_score} điểm · mã đề ${e.codes.map((c) => c.code).join(", ")} · ` +
    `${e.sheets.tong} phiếu (${e.sheets.da_cham} chính thức, ${e.sheets.can_xem} cần xem, ${e.sheets.bi_tu_choi} từ chối)` : "Chưa có kỳ thi.";
  const bia = $("#trang-bia");
  bia.classList.toggle("hidden", !e);
  if (e) bia.href = `/exams/${e.exam_id}/cover.pdf`;
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
    else if (r === "review") { if (id) await manDuyet(Number(id), { datTieuDiem: true }); else await manHangDoi(); }
    else if (r === "results") await manBangDiem();
    else if (r === "classes") { if (id) await manSinhVienLop(Number(id)); else await manLop(); }
    else if (r === "profile") await manHoSo();
    else if (r === "admin") await manQuanTri(id);
    else main.innerHTML = '<p class="muted">Không có trang này.</p>';
  } catch (e) { if (!e.dangNhap) main.innerHTML = `<div class="alert bad">${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------------ đăng nhập / hồ sơ / lớp của tôi */
const NHAN_VAI_TRO = { admin: "Quản trị viên", teacher: "Giáo viên", student: "Sinh viên" };
const TRANG_MAC_DINH = { admin: "#/admin", teacher: "#/upload" };
const trangMacDinh = () => TRANG_MAC_DINH[state.me && state.me.role] || "#/upload";
const datHash = (h) => history.replaceState(null, "", location.pathname + location.search + h);   // đổi hash KHÔNG phát hashchange (tự gọi route sau)

/* Khoá lưu trữ của ỨNG DỤNG (app.js + m.js, cùng gốc) – chỉ xoá đúng các khoá này, không đụng khoá khác. */
const KHOA_LUU_TRU = { local: ["examId", KyThiDong.KHOA], session: ["loc", "m_hang_doi", "m_tong", "m_exam"] };
function xoaLuuTru() {
  for (const [kho, ds] of [[() => localStorage, KHOA_LUU_TRU.local], [() => sessionStorage, KHOA_LUU_TRU.session]])
    for (const k of ds) { try { kho().removeItem(k); } catch (_) { /* bỏ qua */ } }
}
/* Xoá mọi dữ liệu của phiên trước khỏi bộ nhớ + DOM (thanh bên, hộp thoại, thông báo) – người sau không thấy, kể cả thoáng qua. */
function xoaDuLieuPhien() {
  soPhien++;
  Object.assign(state, { examId: null, exams: [], exam: null, me: null, biet: null, chuKy: "" });
  state.moi.clear();
  for (const k of Object.keys(daXem)) delete daXem[k];
  if (typeof qtKyThi === "function") delete qtKyThi.lops;
  const sel = $("#exam-select"); sel.innerHTML = ""; sel.title = "";
  $("#hien-dong-wrap").classList.add("hidden"); $("#hien-dong").checked = false; $("#so-dong").textContent = "";
  $("#exam-name").textContent = ""; $("#exam-info").textContent = "";
  const n = $("#nav-count"); n.textContent = ""; n.classList.add("hidden");
  const bia = $("#trang-bia"); bia.classList.add("hidden"); bia.removeAttribute("href");
  $("#u-name").textContent = ""; $("#u-role").textContent = "";
  $("#dlg-dt").classList.add("hidden"); $("#dlg-dt-body").innerHTML = "";
  const t = $("#toast"); t.textContent = ""; t.classList.add("hidden");
  main.innerHTML = "";
}
/* Sau đăng nhập: hash là trang người này KHÔNG có quyền (giáo viên vào #/admin, phiếu / lớp của người khác – máy chủ trả 404)
   hoặc trống -> trang mặc định của vai trò. Hash hợp lệ thì giữ (phiên hết hạn, đăng nhập lại đúng người -> quay lại đúng chỗ).
   Chỉ chọn trang ĐÍCH – quyền thật vẫn do máy chủ kiểm ở từng API. */
const coQuyen = (p) => api(p, { khongChuyen: true }).then(() => true, (e) => { if (e.dangNhap) throw e; return false; });
async function chinhHash() {
  const [r, id] = location.hash.replace(/^#\/?/, "").split("/");
  let hop = !!r;
  if (r === "admin") hop = state.me.role === "admin";
  else if ((r === "sheet" || r === "review") && id) hop = await coQuyen(`/sheets/${Number(id)}`);
  else if (r === "classes" && id) hop = await coQuyen(`/classes/${Number(id)}/students?q=&page=1&page_size=50`);
  if (!hop) datHash(trangMacDinh());
}
function hienNguoiDung() {
  const me = state.me;
  $("#userbox").classList.toggle("hidden", !me);
  document.body.classList.toggle("logged-out", !me);
  $("#nav-admin").classList.toggle("hidden", !me || me.role !== "admin");      // chỉ ẩn / hiện – máy chủ vẫn trả 403 cho người không phải admin
  if (me) { $("#u-name").textContent = me.full_name; $("#u-role").textContent = `${NHAN_VAI_TRO[me.role] || me.role} · ${me.username}`; }
}
function manDangNhap(thongBao) {
  xoaDuLieuPhien(); hienNguoiDung();
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
      await khoiDong(true);
    } catch (e) { const er = $("#lg-err"); er.textContent = e.message; er.classList.remove("hidden"); btn.disabled = false; }
  });
}
$("#logout").addEventListener("click", async () => {
  // Xoá NGAY (trước khi chờ máy chủ): dữ liệu phiên, khoá lưu trữ của ứng dụng, hash (#/ – người sau vào trang mặc định của mình).
  xoaDuLieuPhien(); hienNguoiDung(); xoaLuuTru(); datHash("#/");
  main.innerHTML = '<p class="muted">Đang đăng xuất…</p>';
  try { await api("/auth/logout", { method: "POST", khongChuyen: true }); } catch (_) { /* bỏ qua */ }
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
      <label class="chon-tep btn"><input type="file" id="files" accept="image/*,.heic" multiple aria-describedby="sel">📁 Chọn ảnh</label>
      <div class="small muted">Chọn được nhiều ảnh một lần.</div></div>
      <div class="row"><button class="pri" id="go" disabled>Bắt đầu chấm</button><span id="sel" class="muted small" aria-live="polite">${esc(moTaTepChon([]))}</span></div>
      <div class="progress hidden" id="bar"><div></div></div><div id="st" class="muted small"></div></div>
    <div class="card hidden" id="kq"><h3>Kết quả lô vừa chấm</h3>
      <table><thead><tr><th>Ảnh</th><th>Trạng thái</th><th>Chi tiết</th><th>Điểm</th><th></th></tr></thead><tbody id="rows"></tbody></table></div>`;
  let danhSach = [];
  const dat = (fl) => {
    danhSach = [...fl].filter((f) => f.type.startsWith("image/") || /\.(heic|jpe?g|png)$/i.test(f.name));
    $("#sel").textContent = moTaTepChon(danhSach.map((f) => f.name));             // AB2: tiếng Việt + tên tệp (title = đầy đủ)
    $("#sel").title = danhSach.map((f) => f.name).join("\n");
    $("#go").disabled = !danhSach.length;
  };
  $("#files").addEventListener("change", (e) => dat(e.target.files));
  const drop = $("#drop");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); dat(e.dataTransfer.files); });
  const examId = state.examId;
  /* Một ảnh vào MỘT dòng; lỗi mạng / máy chủ -> nút Gửi lại (gửi lại đúng ảnh này vào đúng kỳ thi lúc chọn), bị từ chối rõ -> chỉ lý do (V1). */
  async function taiMot(f, tr) {
    tr.innerHTML = `<td>${tenTepHtml(f.name)}</td><td colspan="4" class="muted">Đang xử lý…</td>`;
    try {
      const fd = new FormData(); fd.append("file", f, f.name);
      const r = await api(`/exams/${examId}/sheets`, { method: "POST", body: fd });
      tr.innerHTML = hangKetQuaTai(f.name, r);
    } catch (e) {
      if (e.dangNhap) throw e;
      tr.innerHTML = hangLoiTai(f.name, e);
      const b = tr.querySelector("[data-gui-lai]");
      if (b) b.addEventListener("click", async () => {
        try { await taiMot(f, tr); await napChiTietKyThi(); } catch (e2) { if (!e2.dangNhap) toast(e2.message, true); }
      });
    }
  }
  $("#go").addEventListener("click", async () => {
    const go = $("#go"); go.disabled = true; $("#kq").classList.remove("hidden"); $("#bar").classList.remove("hidden");
    const rows = $("#rows"); rows.innerHTML = "";
    for (let i = 0; i < danhSach.length; i++) {
      const f = danhSach[i];
      $("#st").textContent = `Đang xử lý ảnh ${i + 1}/${danhSach.length}: ${rutGonTen(f.name)} …`;
      $("#bar > div").style.width = `${(i / danhSach.length) * 100}%`;
      const tr = document.createElement("tr"); rows.prepend(tr);
      try { await taiMot(f, tr); } catch (e) { if (e.dangNhap) return; }
    }
    $("#bar > div").style.width = "100%"; $("#st").textContent = `Xong ${danhSach.length} ảnh.`;
    go.disabled = false; await napChiTietKyThi();
  });
}
/* V1: phân biệt lỗi mạng (Gửi lại) với máy chủ từ chối rõ (409 kỳ thi đóng, 404 …: không Gửi lại) – frontend/loi_tai.js. */
function hangLoiTai(ten, e) {
  const loai = LoiTai.phanLoai(e.ma);
  if (loai === "tu_choi") {
    const goiY = e.ma === 409 ? "Ảnh chưa được lưu. Chọn kỳ thi khác hoặc nhờ quản trị viên mở lại kỳ thi." : "Ảnh chưa được lưu.";
    return `<td>${tenTepHtml(ten)}</td><td><span class="tag bad">Bị từ chối</span></td>` +
      `<td colspan="3"><b>${esc(LoiTai.tieuDeTuChoi(e.ma))}:</b> ${esc(e.message)}<div class="muted small">${goiY}</div></td>`;
  }
  if (loai === "anh_lon") return `<td>${tenTepHtml(ten)}</td><td><span class="tag bad">Ảnh quá lớn</span></td><td colspan="3">${esc(e.message)}</td>`;
  return `<td>${tenTepHtml(ten)}</td><td><span class="tag bad">${e.ma >= 500 ? "Lỗi máy chủ" : "Lỗi mạng"}</span></td>` +
    `<td colspan="2">${esc(e.message)}</td><td><button class="pri" type="button" data-gui-lai>↻ Gửi lại</button></td>`;
}
function hangKetQuaTai(ten, r) {
  let chiTiet = "";
  if (r.status === "rejected") {
    const ly = state.reasons[r.reject_code] || {};
    chiTiet = `<div class="alert bad"><b>${esc(r.reject_message || ly.message)}</b><br>Lời khuyên: ${esc(ly.advice || "chụp lại phiếu rõ nét, đủ sáng, thấy đủ 4 góc.")}</div>`;
  } else if (r.status === "needs_review") chiTiet = `<span class="tag warn">${r.pending_questions} câu cần xem</span>`;
  else if (r.status === "graded") chiTiet = r.auto_graded_pending ? `Đã chấm. <span class="tag warn">${r.auto_graded_pending} câu tô nhiều ô đã chấm sai, chờ xem lại</span>` : "Máy tự chốt, không còn mục cần xem.";
  if (r.da_ton_tai) chiTiet += ' <span class="muted small">(ảnh đã tải trước đó – trả phiếu cũ)</span>';
  const diem = r.status === "rejected" ? "–" : r.official_score !== null ? `<b>${fmt(r.official_score)}</b>`
    : r.provisional_score !== null ? `<b>${fmt(r.provisional_score)}</b> <span class="tag warn">tạm</span>` : "–";
  const lien = r.status === "needs_review" ? `<a class="btn pri" href="#/review/${r.sheet_id}">Duyệt</a>`
    : r.status === "rejected" ? `<a class="btn" href="#/sheet/${r.sheet_id}">Chi tiết</a>` : `<a class="btn" href="#/sheet/${r.sheet_id}">Xem</a>`;
  return `<td>${tenTepHtml(ten)}</td><td>${tag(r.status)}</td><td>${chiTiet}</td><td>${diem}</td><td>${lien}</td>`;
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
    ${ds.map((p) => `<tr class="row-link${state.moi.has(p.sheet_id) ? " moi" : ""}" data-id="${p.sheet_id}"><td>${p.sheet_id}${state.moi.has(p.sheet_id) ? ' <span class="tag ok">mới</span>' : ""}</td><td>${tenTepHtml(p.original_filename)}</td>
      <td>${p.status === "rejected" ? "–" : esc(p.detected_sbd || "–")}</td><td>${p.status === "rejected" ? "–" : esc(p.detected_exam_code || "–")}</td>
      <td>${esc(p.student_name || "–")}</td>
      <td>${tag(p.status)}${p.status === "needs_review" ? ` <span class="muted small">${p.pending_questions} câu</span>` : ""}${p.auto_graded_pending ? ` <span class="tag warn">${p.auto_graded_pending} câu nhiều ô chờ xem lại</span>` : ""}
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
  if (tr.co_chi_tiet === false)                                                   // W2: phiếu mẫu cũ không có chi tiết từng cột
    return `${esc(tr.detected || "–")} <span class="muted small">(không có chi tiết từng cột – dữ liệu mẫu cũ)</span>`;
  return `<span class="cols">${tr.columns.map((c) => `<span class="col ${c.can_xem || c.chu_so === "?" ? "bad" : ""}" title="cột ${c.vi_tri}: tin cậy ${fmt(c.do_tin_cay)}">${esc(c.chu_so)}</span>`).join("")}</span>`;
}
/* Hai kênh cạnh nhau: ô tô (bubble) ↔ chữ viết tay (ảnh ô + chữ số máy đọc + độ tin cậy). Cột lệch / không chắc tô nổi bật ("lech"),
   cột đã khớp làm nhạt ("khop") để mắt giáo viên đi thẳng tới chỗ cần nhìn (AA2 b). */
function haiKenhHtml(sheetId, field, tr) {
  if (!tr || !tr.columns.some((c) => c.handwriting)) return "";
  const hang = (ten, f) => `<tr><th>${ten}</th>${tr.columns.map((c) => `<td class="${DuyetDinhDanh.cotCanNhin(c, tr) ? "lech" : "khop"}">${f(c)}</td>`).join("")}</tr>`;
  const ly = LyDoCot.moTa(tr, LY_DO_CHU_SO);                                     // V3: câu theo từng cột (chỉ câu chữ, dữ liệu API không đổi)
  return `<table class="haikenh"><tbody>
    ${hang("Ô tô (bubble)", (c) => `<b>${esc(c.bubble ?? c.chu_so)}</b>`)}
    ${hang("Chữ viết tay", (c) => c.handwriting && c.handwriting.has_crop
      ? `<img src="/sheets/${sheetId}/digits/${field}/${c.handwriting.pos}/image" alt="ô viết tay ${c.vi_tri}">` : "–")}
    ${hang("Máy đọc", (c) => { const h = c.handwriting; if (!h) return "–";
      if (h.o_trong) return '<span class="muted">ô trống</span>';
      if (h.chu_so === "?") return `<span class="muted">không đọc được</span>`;
      return `<b>${esc(h.chu_so)}</b> <span class="muted small">${Math.round(h.p * 100)}%</span>`; })}
    ${hang("GV đã chốt", (c) => (c.handwriting && c.handwriting.corrected) ? `<b>${esc(c.handwriting.corrected)}</b>` : "")}
    </tbody></table>${ly.length ? `<div class="small muted ly-do-cot">Lý do cần xem:<ul>${ly.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>` : ""}`;
}
function cauHtml(q, dapAn, phieu) {
  const cls = q.needs_review ? "review" : q.is_correct === true ? "good" : q.is_correct === false ? "wrong" : "";
  const doc = q.selected_options || (q.state === "blank" ? "—" : "?");
  const ketQua = q.needs_review ? "?" : q.is_correct === true ? "✓" : q.is_correct === false ? "✗" : "";
  const ly = q.needs_review ? `<small>${esc(LyDoCau.chuoi(q.reasons, LY_DO_CAU_NGAN))}</small>` : q.tu_cham_can_xem ? "<small>tô nhiều ô – tự chấm sai, chờ xem lại</small>"
    : q.manually_edited ? '<small style="color:var(--mut)">GV đã sửa</small>' : "";
  return `<div class="q ${cls}" title="Máy đọc: ${esc(q.omr_selected_options || "bỏ trống")}${dapAn ? " · đáp án: " + dapAn : ""}"><span>Câu ${q.question_no}: <b>${esc(doc)}</b>${ly}</span><span>${ketQua}</span>${phieu ? HoanTac.nutHtml(q, phieu) : ""}</div>`;
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
      <p class="small"><a href="/sheets/${id}/image?kind=original" target="_blank">Xem ảnh gốc</a> · ${tenTepHtml(p.original_filename)}</p></div>
    <div><div class="card">${rejected ? await khoiTuChoi(p) : `
      <div class="score">${diemHtml(p.score, p.status)}</div>
      ${p.score && p.score.official === null && p.score.pending_questions ? `<p class="muted small">Điểm tạm chỉ tính các câu máy chắc chắn. Điểm chính thức có sau khi giáo viên xem hết ${p.score.pending_questions} câu cần xem.</p>` : ""}
      ${p.score && p.score.result_status ? `<p class="muted small">Chốt bởi: ${{ confirmed: "giáo viên (đã duyệt)", manual_edited: "giáo viên (đã sửa điểm)" }[p.score.result_status] || "máy (tự động)"} · đúng ${p.score.num_correct ?? "–"} câu</p>` : ""}
      ${p.score && p.score.auto_graded_pending ? `<div class="alert warn" id="canh-bao-tu-cham">Còn ${p.score.auto_graded_pending} câu tô nhiều ô đã chấm sai, chờ xem lại. <a class="btn" href="#/review/${id}">Xem lại →</a></div>` : ""}
      <dl class="kv"><dt>SBD</dt><dd>${cotsHtml(p.sbd)} <span class="muted small">${p.sbd && p.sbd.can_xem ? "cần xem" : ""}</span></dd>
        <dt>Mã đề</dt><dd>${cotsHtml(p.exam_code)} ${maKhop ? "" : '<span class="tag warn">chưa xác định</span>'}</dd>
        <dt>Sinh viên</dt><dd>${p.student ? esc(p.student.full_name) + ` (${esc(p.student.student_code)})` : '<span class="muted">chưa ghép được</span>'}</dd></dl>
      <h3>SBD: ô tô ↔ chữ viết tay</h3>${haiKenhHtml(p.sheet_id, "sbd", p.sbd)}
      <h3>Mã đề: ô tô ↔ chữ viết tay</h3>${haiKenhHtml(p.sheet_id, "exam_code", p.exam_code)}
      ${rv && p.status === "needs_review" ? `<div class="alert warn">Lý do vào hàng đợi duyệt: ${rv.reasons.map((r) => LY_DO_PHIEU[r] || r).join("; ")}</div>` : ""}
      ${p.status === "needs_review" ? `<a class="btn pri" href="#/review/${id}">Duyệt các mục cần xem →</a>` : ""}`}</div></div></div>
    ${rejected ? "" : `<div class="card"><h3>Bảng ${p.questions.length} câu</h3>
      <p class="small muted">Xanh = đúng · đỏ = sai · vàng viền đậm = cần xem (chưa tính vào điểm chính thức). Chỉ chấm khi đã biết mã đề.</p>
      <div class="qgrid">${p.questions.map((q) => cauHtml(q, dapAn ? dapAn[q.question_no - 1] : null, p)).join("")}</div></div>
    ${khoiCauSai(p)}`}`;
  if (!rejected) ganCauSai(id, p, () => manChiTiet(id));
  if (!rejected) main.querySelectorAll(".qgrid [data-undo]").forEach((b) => b.addEventListener("click", () => { const n = Number(b.dataset.undo); b.disabled = true; hoanTacCau(id, n, p, p.questions.find((x) => x.question_no === n), () => manChiTiet(id)).finally(() => { b.disabled = false; }); }));
}
const cauCanCuon = {};
function khoiCauSai(p) {
  const qs = p.questions;
  const tt = CauSai.tomTat(qs);
  const sai = CauSai.danhSachSai(qs);
  const cho = CauSai.chuaCham(qs);
  const dong = sai.map((q) => {
    const h = CauSai.hanhDong(q, p);
    return `<details class="cau-sai" data-q="${q.question_no}"><summary>Câu ${q.question_no} · ${esc(CauSai.moTaChon(q))} · đáp án đúng <b>${esc(q.correct_option || "?")}</b> · <span class="tag bad">${esc(CauSai.lyDo(q))}</span></summary>
      <div class="cau-sai-than"><img data-src="/sheets/${p.sheet_id}/questions/${q.question_no}/image" alt="ảnh câu ${q.question_no}">
        <div class="row">${h.sua ? `<button type="button" data-sua="${q.question_no}">Sửa lại</button>` : '<span class="muted small">Máy đọc chắc chắn nên không có thẻ để sửa.</span>'}
          ${h.hoan_tac ? HoanTac.nutHtml(q, p) : ""}${h.giu ? `<button type="button" data-giu="${q.question_no}">Giữ như máy chấm</button>` : ""}</div></div></details>`;
  }).join("");
  return `<div class="card" id="khoi-cau-sai"><h3>Câu bị tính sai (${sai.length})</h3>
    <p class="small" id="tom-tat-cau-sai"><b>${esc(tt.chuoi)}</b>${tt.chua_cham ? ` · ${tt.chua_cham} chưa chấm` : ""}</p>
    ${sai.length ? dong : '<p class="muted" id="khong-cau-sai">Không có câu nào bị tính sai</p>'}
    ${cho.length ? `<h4 id="cau-chua-cham">Chưa chấm (chờ duyệt) (${cho.length})</h4><p class="small">Câu ${cho.join(", ")}</p>` : ""}</div>`;
}
function ganCauSai(id, p, lamMoi) {
  const khoi = $("#khoi-cau-sai");
  if (!khoi) return;
  khoi.querySelectorAll("details.cau-sai").forEach((d) => d.addEventListener("toggle", () => {
    const img = d.querySelector("img[data-src]");
    if (d.open && img) { img.src = img.dataset.src; img.removeAttribute("data-src"); }
  }));
  khoi.querySelectorAll("[data-sua]").forEach((b) => b.addEventListener("click", () => {
    const n = Number(b.dataset.sua);
    const q = p.questions.find((x) => x.question_no === n);
    cauHT[id] = n;
    cauCanCuon[id] = n;
    if (!q.needs_review && !q.tu_cham_can_xem) (daXem[id] = daXem[id] || new Set()).add(n);
    if (location.hash === `#/review/${id}`) manDuyet(id); else location.hash = `#/review/${id}`;
  }));
  khoi.querySelectorAll("[data-undo]").forEach((b) => b.addEventListener("click", () => {
    const n = Number(b.dataset.undo);
    b.disabled = true;
    hoanTacCau(id, n, p, p.questions.find((x) => x.question_no === n), lamMoi).finally(() => { b.disabled = false; });
  }));
  khoi.querySelectorAll("[data-giu]").forEach((b) => b.addEventListener("click", async () => {
    const n = Number(b.dataset.giu);
    b.disabled = true;
    try {
      await post(`/sheets/${id}/questions/${n}/auto-review`, { action: "keep" });
      (daXemTuCham[id] = daXemTuCham[id] || new Set()).add(n);
      toast(`Câu ${n}: giữ như máy chấm.`);
      await lamMoi();
    } catch (e) { toast(e.message, true); b.disabled = false; }
  }));
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
/* AF4: hàng đợi lọc / nhóm theo lý do chính (GET /exams/{id}/review-groups) – CHỈ hiển thị, không đổi trạng thái phiếu nào. */
const LY_DO_NGAN = { o_mo: "chưa chắc đặc", nhieu_o: "nhiều ô", vet_nho: "vết nhỏ", to_nhat: "tô nhạt", tin_cay_thap: "sát ngưỡng", vi_tri: "vị trí" };
async function manHangDoi() {
  const ds = await api(`/exams/${state.examId}/review-groups`);
  const dem = {};
  ds.forEach((g) => { const k = DuyetNhanh.nhomPhieu(g); dem[k] = (dem[k] || 0) + 1; });
  if (state.locNhom && !dem[state.locNhom]) state.locNhom = "";
  const hien = DuyetNhanh.locSapHangDoi(ds, state.locNhom || "");
  const lyDo = (g) => Object.entries(g.ly_do_cau || {}).map(([r, n]) => `${LY_DO_NGAN[r] || esc(r)} ${n}`).join(" · ");
  const dd = (g) => [g.sbd_can_xem && "SBD", g.ma_de_can_xem && "mã đề", g.chua_ghep && !g.sbd_can_xem && !g.ma_de_can_xem && "chưa ghép"].filter(Boolean).join(", ");
  main.innerHTML = `<h2>Hàng đợi duyệt (${ds.length})</h2><div class="card">
    <div class="row"><label>Lọc theo lý do <select id="loc-nhom"><option value="">Tất cả – nhóm dễ trước</option>
      ${DuyetNhanh.THU_TU_NHOM.filter((k) => dem[k]).map((k) => `<option value="${k}" ${k === state.locNhom ? "selected" : ""}>${DuyetNhanh.TEN_NHOM[k]} (${dem[k]})</option>`).join("")}</select></label>
      <span class="muted small">Chỉ sắp xếp / lọc để hiển thị – không đổi trạng thái phiếu nào.</span></div>
    <table><thead><tr><th>#</th><th>Ảnh</th><th>SBD</th><th>Nhóm</th><th>Câu cần xem</th><th>SBD / mã đề</th><th>Điểm tạm</th><th></th></tr></thead><tbody>
    ${hien.map((g) => `<tr class="${state.moi.has(g.sheet_id) ? "moi" : ""}" data-nhom="${g.nhom}"><td>${g.sheet_id}${state.moi.has(g.sheet_id) ? ' <span class="tag ok">mới</span>' : ""}</td><td>${tenTepHtml(g.original_filename)}</td><td>${esc(g.detected_sbd || "–")}</td>
      <td><span class="tag nhom-${g.nhom}">${DuyetNhanh.TEN_NHOM[g.nhom]}</span></td><td>${g.so_cau}${g.so_cau ? ` <span class="muted small">(${lyDo(g)})</span>` : ""}</td>
      <td>${dd(g) ? `<span class="tag warn">${dd(g)}</span>` : '<span class="muted">–</span>'}</td><td>${g.provisional === null || g.provisional === undefined ? "–" : fmt(g.provisional)}</td>
      <td><a class="btn pri" href="#/review/${g.sheet_id}">Duyệt</a></td></tr>`).join("")
      || '<tr><td colspan="8" class="muted">Không còn phiếu nào cần duyệt.</td></tr>'}</tbody></table></div>
    <div id="muc-tu-cham"></div>`;
  $("#loc-nhom").addEventListener("change", (e) => { state.locNhom = e.target.value; manHangDoi(); });
  await mucTuCham();
}
/* Lệnh BA: câu tô nhiều ô đã TỰ CHẤM SAI (phiếu đã có điểm) nhưng chờ giáo viên xem lại – mục riêng, không chặn điểm. */
async function mucTuCham() {
  const ds = await api(`/exams/${state.examId}/auto-graded-review`);
  const cho = $("#muc-tu-cham");
  if (!cho) return;
  if (!ds.length) { cho.innerHTML = ""; return; }
  cho.innerHTML = `<h2 id="tieu-de-tu-cham">Đã chấm tự động – cần xem lại (${ds.length} câu)</h2><div class="card">
    <p class="muted small">Các câu thí sinh tô từ 2 ô trở lên: máy đã tính SAI nên phiếu có điểm chính thức ngay. Nhìn ảnh rồi giữ như máy chấm hoặc chọn lại đáp án thật.</p>
    <div class="row"><button type="button" id="giu-tat-ca">Giữ như máy chấm tất cả (${ds.length} câu)</button>
      <span class="small muted">Chỉ ghi "đã xem lại", điểm KHÔNG đổi. Sẽ hỏi lại trước khi làm.</span></div>
    <table><thead><tr><th>Phiếu</th><th>Ảnh</th><th>SBD</th><th>Thí sinh</th><th>Câu</th><th>Máy đọc</th><th>Điểm</th><th></th></tr></thead><tbody>
    ${ds.map((c) => `<tr><td>#${c.sheet_id}</td><td>${tenTepHtml(c.original_filename)}</td><td>${esc(c.detected_sbd || "–")}</td><td>${esc(c.student_name || "–")}</td>
      <td>${c.question_no}</td><td><b>${esc(c.omr_reading || "bỏ trống")}</b></td><td>${c.official_score === null ? '<span class="muted">tạm</span>' : fmt(c.official_score)}</td>
      <td><a class="btn pri" href="#/review/${c.sheet_id}">Xem lại</a></td></tr>`).join("")}</tbody></table></div>`;
  $("#giu-tat-ca").addEventListener("click", async () => {
    if (!confirm(`Giữ như máy chấm ${ds.length} câu tô nhiều ô? Điểm không đổi; các câu này sẽ không còn ở mục cần xem lại.`)) return;
    try {
      const r = await post(`/exams/${state.examId}/auto-graded-review/keep-all`, { confirm: true, items: ds.map((c) => ({ sheet_id: c.sheet_id, question_no: c.question_no })) });
      toast(`Đã giữ ${r.da_giu} câu như máy chấm.${r.bo_qua ? ` ${r.bo_qua} câu đã có người xử lý.` : ""}`);
      await napChiTietKyThi(); await manHangDoi();
    } catch (e) { toast(e.message, true); }
  });
}

const daXemTuCham = {};   // sheet_id -> Set(question_no) câu "đã chấm tự động" đã xem lại trong phiên này
const daXem = {};   // sheet_id -> Set(question_no) đã duyệt trong phiên này (hiện thẻ "đã chốt" thay vì biến mất)
/* datTieuDiem: vừa mở phiếu (từ hàng đợi / nút kế tiếp) -> đặt con trỏ vào ô SBD / mã đề cần chốt (không chọn gì thay giáo viên).
   daLuu: vừa lưu SBD / mã đề -> hiện ngay tại chỗ nút "Phiếu cần xem kế tiếp" (AA2 d). */
async function manDuyet(id, { datTieuDiem = false, daLuu = false } = {}) {
  const p = await api(`/sheets/${id}`);
  if (p.status === "rejected") { location.hash = `#/sheet/${id}`; return; }
  const xong = (daXem[id] = daXem[id] || new Set());
  const xongTc = (daXemTuCham[id] = daXemTuCham[id] || new Set());
  const tuCham = (q) => HoanTac.laNhieuOThuan(q) && !q.needs_review;
  const the = p.questions.filter((q) => q.needs_review || (xong.has(q.question_no) && !xongTc.has(q.question_no) && !tuCham(q)));
  const theTuCham = p.questions.filter((q) => q.tu_cham_can_xem || xongTc.has(q.question_no) || (tuCham(q) && q.da_xem));
  const dinhDanhCan = p.status === "needs_review" && p.sbd && p.exam_code &&
    (p.sbd.can_xem || p.exam_code.can_xem || !p.exam_code.matched_code || !p.student);
  const rv = p.review;
  const trung = p.status === "needs_review" && rv && rv.reasons.includes("duplicate_sbd") && rv.details && rv.details.duplicate_with_sheet_id ? rv.details.duplicate_with_sheet_id : null;
  let phieuCu = null;
  if (trung) { try { phieuCu = await api(`/sheets/${trung}`); } catch (_) { /* không đọc được: vẫn cho xử lý, chỉ thiếu thông tin so sánh */ } }
  let keTiep = null;                                                              // phiếu cần xem kế tiếp, theo thứ tự hàng đợi
  try { keTiep = DuyetDinhDanh.keTiep((await api(`/exams/${state.examId}/sheets?status=needs_review`)).map((x) => x.sheet_id), id); } catch (e) { if (e.dangNhap) throw e; }
  let dsSbd = [];                                                                 // SBD của danh sách dự thi – chỉ để kiểm ô nhập (AA2 e)
  if (dinhDanhCan) { try { dsSbd = (await api(`/exams/${state.examId}/results`)).rows.map((r) => r.sbd); } catch (e) { if (e.dangNhap) throw e; dsSbd = null; } }
  const nutKeTiep = (idEl, cls) => keTiep ? `<a class="btn ${cls}" id="${idEl}" href="#/review/${keTiep}">Phiếu cần xem kế tiếp (#${keTiep}) →</a>` : "";
  const baoDaLuu = daLuu ? `<div class="alert ok" id="da-luu-dd">Đã lưu SBD / mã đề.${dinhDanhCan ? " Phiếu vẫn còn mục SBD / mã đề cần xem (xem dưới)." : ""}
      ${nutKeTiep("ke-tiep-sau-luu", "pri") || '<a class="btn" href="#/review">Về hàng đợi</a> <span class="muted small">(không còn phiếu cần xem khác)</span>'}</div>` : "";
  main.innerHTML = `<p class="row nav-duyet"><a href="#/review">← Hàng đợi</a> · <a href="#/sheet/${id}">Chi tiết phiếu</a>${keTiep ? " · " + nutKeTiep("ke-tiep", "") : ""}</p>
    <h2>Duyệt phiếu #${id} ${tag(p.status)}</h2>
    <div class="card"><div class="score">${diemHtml(p.score, p.status)}</div>
      ${p.status === "graded" ? `<div class="alert ok">Đã chốt điểm chính thức – ${p.score && p.score.auto_graded_pending ? "còn câu tô nhiều ô chờ xem lại (xem dưới)." : "phiếu duyệt xong."} ${keTiep ? `<a href="#/review/${keTiep}">Sang phiếu cần xem kế tiếp (#${keTiep}) →</a>` : '<a href="#/review">Về hàng đợi (không còn phiếu cần xem khác) →</a>'}</div>` : ""}
      ${rv && p.status === "needs_review" ? `<div class="alert warn">Còn lại: ${rv.reasons.map((r) => LY_DO_PHIEU[r] || r).join("; ")}</div>` : ""}
      <p class="muted small">Sinh viên: ${p.student ? esc(p.student.full_name) + " (" + esc(p.student.student_code) + ")" : "chưa ghép được"} · Mã đề: ${esc((p.exam_code && p.exam_code.matched_code) || "chưa xác định")}</p></div>
    ${trung ? khungTrung(p, trung, phieuCu) : ""}
    ${baoDaLuu}
    ${dinhDanhCan ? khungDinhDanh(p) : ""}
    <h3>Câu cần xem (${p.questions.filter((q) => q.needs_review).length} còn lại)</h3>
    ${p.status === "needs_review" ? khungNhanh(p) : ""}
    ${the.map((q) => theCau(id, q, p)).join("") || '<p class="muted">Không có câu nào cần xem.</p>'}
    ${theTuCham.length ? `<h3 id="tieu-de-tu-cham">Đã chấm tự động – cần xem lại (${theTuCham.filter((q) => q.tu_cham_can_xem).length} còn lại)</h3>
      <p class="muted small">Thí sinh tô từ 2 ô trở lên nên máy đã tính câu SAI. Điểm của phiếu đã tính theo cách đó; nhìn ảnh rồi giữ như máy chấm hoặc chọn lại đáp án thật (điểm sẽ được tính lại và ghi vết).</p>
      ${theTuCham.map((q) => theCauTuCham(id, q, p)).join("")}` : ""}
    ${khoiCauSai(p)}`;
  ganCauSai(id, p, () => manDuyet(id));
  if (trung) {
    $("#trung-bo").addEventListener("click", () => boPhieuTrung(id, trung));
    $("#trung-thay").addEventListener("click", () => thayPhieuCu(id, trung, phieuCu));
  }
  if (dinhDanhCan) ganDinhDanh(id, p, dsSbd, datTieuDiem);
  if (daLuu) $("#da-luu-dd").scrollIntoView({ block: "center" });
  main.querySelectorAll(".rcard").forEach((el) => gan(el, id, p));
  const nut = $("#xn-tat-ca");
  if (nut) nut.addEventListener("click", () => moXacNhanHangLoat(id, p, { dinhDanhCan, trung }));
  datHienTai(id, cauHT[id], !(dinhDanhCan && datTieuDiem));                     // không giành tiêu điểm của ô SBD / mã đề (AA2)
  if (cauCanCuon[id]) {
    const the = $(`#the-cau-${cauCanCuon[id]}`);
    delete cauCanCuon[id];
    if (the) the.scrollIntoView({ block: "center" });
  }
  await napChiTietKyThi();
}

/* ------------------------------------------------------------------ AF: duyệt nhanh (phím tắt, xác nhận hàng loạt) */
const cauHT = {};   // sheet_id -> số câu đang chọn (phím tắt tác động lên câu này)
const PHIM_GOI_Y = `Phím tắt: <kbd>A</kbd>–<kbd>D</kbd> chọn đáp án · <kbd>Space</kbd> xác nhận như máy đọc · <kbd>Enter</kbd> lưu lựa chọn và sang câu kế ·
  <kbd>N</kbd> phiếu cần xem kế tiếp · <kbd>Esc</kbd> bỏ chọn <span class="muted">(không tác dụng khi đang gõ trong ô SBD / mã đề)</span>`;
function khungNhanh(p) {
  const hl = DuyetNhanh.cauHangLoat(p.questions);
  if (!hl.duoc.length && !hl.tay.length) return "";
  const nhan = DuyetNhanh.nhanNutHangLoat(hl.duoc.length);                      // AF2: chỉ đếm câu nhiều ô / tô nhạt; 0 câu -> ẩn nút
  return `<div class="card" id="khung-nhanh">
    ${nhan ? `<div class="row"><button type="button" id="xn-tat-ca" aria-haspopup="dialog">${esc(nhan)}</button>
      <span class="small muted">Chỉ câu trả lời "tô nhạt cả tờ" bên dưới. SBD / mã đề KHÔNG nằm trong thao tác này. Sẽ hỏi lại trước khi làm.</span></div>` : ""}
    ${hl.tay.length ? `<p class="small" id="giai-thich-tay">Câu mờ / vết cần quyết định bằng mắt – ${hl.tay.length} câu (${hl.tay.join(", ")}) chọn từng câu.</p>` : ""}
    <p class="small muted phim-goi-y" id="goi-y-phim">${PHIM_GOI_Y}</p></div>`;
}
const cauConLai = () => [...main.querySelectorAll(".rcard:not(.done)")].map((el) => Number(el.dataset.q));
function datHienTai(id, n, layTieuDiem = false) {
  const con = cauConLai();
  if (!con.length) { delete cauHT[id]; return; }
  cauHT[id] = con.includes(n) ? n : con[0];
  main.querySelectorAll(".rcard").forEach((el) => el.classList.toggle("hien-tai", Number(el.dataset.q) === cauHT[id]));
  const el = main.querySelector(`.rcard[data-q="${cauHT[id]}"]`);
  if (layTieuDiem && el) el.focus({ preventScroll: false });
}
/* AF2: hộp xác nhận – liệt kê từng câu + đáp án máy đọc, ô "đã nhìn ảnh" phải tích, tiêu điểm mặc định ở "Huỷ", nút xác nhận KHÔNG bấm sẵn. */
function moXacNhanHangLoat(id, p, { dinhDanhCan, trung }) {
  const hl = DuyetNhanh.cauHangLoat(p.questions);
  if (!hl.duoc.length) return;
  const seChot = !dinhDanhCan && !trung && !hl.tay.length;
  const cu = $("#dlg-hl"); if (cu) cu.remove();
  const moTu = document.activeElement;                                            // AF2: đóng hộp -> trả tiêu điểm về nút đã mở hộp
  const dlg = document.createElement("div");
  dlg.id = "dlg-hl"; dlg.className = "modal"; dlg.setAttribute("role", "dialog"); dlg.setAttribute("aria-modal", "true");
  dlg.setAttribute("aria-labelledby", "dlg-hl-h"); dlg.setAttribute("aria-describedby", "dlg-hl-canh-bao");
  dlg.innerHTML = `<div class="modal-box"><h2 id="dlg-hl-h">Xác nhận ${hl.duoc.length} câu tô nhạt cả tờ như máy đọc?</h2>
    <p>Phiếu #${id}. Mỗi câu dưới đây được chốt ĐÚNG như máy đọc – giống bấm "Xác nhận như máy đọc" từng câu:</p>
    <ul class="ds-hl">${DuyetNhanh.dongXacNhan(hl.duoc).map((t, i) => `<li><a href="#" data-xem="${hl.duoc[i].question_no}">${esc(t)}</a></li>`).join("")}</ul>
    <div class="alert warn" id="dlg-hl-canh-bao"><b>Không hoàn tác được</b>: câu đã xác nhận không mở lại được trên hệ thống hiện tại.
      ${seChot ? "Sau thao tác này phiếu hết mục cần xem nên sẽ <b>chốt điểm chính thức</b>." : "Phiếu vẫn còn mục khác chờ bạn (SBD / mã đề, câu chọn tay hoặc trùng SBD) – chưa có điểm chính thức."}
      SBD / mã đề không bị thay đổi.</div>
    <label class="hl-tich"><input type="checkbox" id="hl-da-xem"> Tôi đã nhìn ảnh từng câu ở trên và đồng ý máy đọc đúng</label>
    <div class="row"><button type="button" id="hl-huy">Huỷ</button><button type="button" class="pri" id="hl-ok" disabled>Xác nhận ${hl.duoc.length} câu</button></div></div>`;
  document.body.appendChild(dlg);
  /* AF2: bẫy Tab (Tab / Shift+Tab xoay vòng trong hộp) + Esc đóng – nghe ở document (pha capture) để bắt cả khi tiêu điểm đã rơi ra ngoài hộp. */
  const coTheNhan = () => [...dlg.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])')];
  const phimHop = (e) => {
    const ds = coTheNhan();
    const a = DuyetNhanh.phimHop(e.key, e.shiftKey, ds.length, ds.indexOf(document.activeElement));
    if (!a) return;
    e.preventDefault(); e.stopPropagation();
    if (a.loai === "dong") dong();
    else if (a.j >= 0) ds[a.j].focus();
  };
  document.addEventListener("keydown", phimHop, true);
  const go = () => { document.removeEventListener("keydown", phimHop, true); dlg.remove(); };
  const dong = () => {
    go();
    const el = moTu && moTu.isConnected ? moTu : main.querySelector(`.rcard[data-q="${cauHT[id]}"]`);
    if (el) el.focus();
  };
  $("#hl-da-xem", dlg).addEventListener("change", (e) => { $("#hl-ok", dlg).disabled = !e.target.checked; });
  $("#hl-huy", dlg).addEventListener("click", dong);
  dlg.querySelectorAll("[data-xem]").forEach((a) => a.addEventListener("click", (e) => {     // xem lại câu: đóng hộp, cuộn tới thẻ câu đó
    e.preventDefault(); go(); datHienTai(id, Number(a.dataset.xem), true);
    const el = main.querySelector(`.rcard[data-q="${a.dataset.xem}"]`); if (el) el.scrollIntoView({ block: "center" });
  }));
  $("#hl-ok", dlg).addEventListener("click", async () => {
    if (!$("#hl-da-xem", dlg).checked) return;
    $("#hl-ok", dlg).disabled = true;
    try {
      const r = await post(`/sheets/${id}/questions/confirm-remaining`, { question_nos: hl.duoc.map((c) => c.question_no), confirm: true });
      r.da_xac_nhan.forEach((n) => daXem[id].add(n));
      go();
      toast(`Đã xác nhận ${r.da_xac_nhan.length} câu như máy đọc.${r.status === "graded" ? " Phiếu đã chốt điểm chính thức." : ""}`);
      await manDuyet(id);
    } catch (e) { toast(e.message, true); $("#hl-ok", dlg).disabled = !$("#hl-da-xem", dlg).checked; }
  });
  $("#hl-huy", dlg).focus();
}
/* AF1: phím tắt màn duyệt câu (logic: DuyetNhanh.phimCau). Không bắt phím trong ô nhập / khung SBD–mã đề / hộp thoại. */
document.addEventListener("keydown", (ev) => {
  const m = /^#\/review\/(\d+)/.exec(location.hash);
  if (!m || ev.isComposing) return;
  const id = Number(m[1]), t = ev.target;
  const dt = $("#dlg-dt");
  const a = DuyetNhanh.phimCau(ev.key, { tag: t && t.tagName, laNut: !!(t && t.closest && t.closest("button, a, label")),
    trongKhungDd: !!(t && t.closest && t.closest("#khung-dd, #khung-trung")), phu: ev.ctrlKey || ev.altKey || ev.metaKey,
    dangMoHop: !!$("#dlg-hl") || !!(dt && !dt.classList.contains("hidden")) });
  if (!a) return;
  const el = main.querySelector(`.rcard[data-q="${cauHT[id]}"]:not(.done)`);
  if (a.loai === "phieu_ke_tiep") {
    ev.preventDefault();
    const k = $("#ke-tiep") || $("#ke-tiep-sau-luu");
    if (k) location.hash = k.getAttribute("href"); else toast("Không còn phiếu cần xem khác.");
    return;
  }
  if (!el) return;
  ev.preventDefault();
  if (a.loai === "chon") { const b = el.querySelector(`.opts button[data-o="${a.o}"]`); if (b) b.classList.toggle("sel"); }
  else if (a.loai === "bo_chon") el.querySelectorAll(".opts .sel").forEach((b) => b.classList.remove("sel"));
  else if (a.loai === "xac_nhan") {
    const b = el.querySelector('[data-act="confirm"], [data-act="keep"]');
    if (b && !b.disabled) b.click(); else toast("Câu này phải chọn tay (máy chưa chắc vị trí hàng): bấm A–D rồi Enter.", true);
  } else if (a.loai === "luu") {
    if (el.querySelector(".opts .sel")) el.querySelector('[data-act="set"]').click();
    else toast("Chọn đáp án bằng A–D trước, hoặc bấm Space để xác nhận như máy đọc.", true);
  }
});
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
  return `<div class="card" id="khung-dd"><h3>Chốt số báo danh / mã đề</h3>
    <p class="small muted">Nhìn ảnh ô viết tay cạnh ô tô; cột tô nổi bật là chỗ hai kênh lệch hoặc máy không chắc, cột nhạt là hai kênh đã khớp. Máy KHÔNG tự chọn thay giáo viên.</p>
    ${phongToHtml(p)}
    <div class="grid2"><div class="clip"><img src="/sheets/${p.sheet_id}/image?kind=aligned" alt="đầu phiếu"></div>
    <div><h3>SBD</h3>${haiKenhHtml(p.sheet_id, "sbd", p.sbd) || cotsHtml(p.sbd)}
      <h3>Mã đề</h3>${haiKenhHtml(p.sheet_id, "exam_code", p.exam_code) || cotsHtml(p.exam_code)}
      <div class="row"><label>SBD đúng <input type="text" id="in-sbd" inputmode="numeric" autocomplete="off" aria-describedby="bao-sbd" value="${esc(sbdDoc)}"></label>
        ${nut("in-sbd", p.sbd, (c) => c.bubble, "Lấy theo ô tô")} ${nut("in-sbd", p.sbd, (c) => c.handwriting && c.handwriting.chu_so, "Lấy theo chữ viết tay")}</div>
      <div class="o-bao" id="bao-sbd" aria-live="polite"></div>
      <div class="row"><label>Mã đề đúng <input type="text" id="in-ma" inputmode="numeric" autocomplete="off" aria-describedby="bao-ma" value="${esc(maDoc)}"></label>
        ${nut("in-ma", p.exam_code, (c) => c.bubble, "Lấy theo ô tô")} ${nut("in-ma", p.exam_code, (c) => c.handwriting && c.handwriting.chu_so, "Lấy theo chữ viết tay")}</div>
      <div class="o-bao" id="bao-ma" aria-live="polite"></div>
      <p class="small muted">Mã đề của kỳ thi: ${esc(ma)}</p>
      <div class="row"><button class="pri" id="luu-dd">Lưu SBD / mã đề</button>
        <span class="small muted phim-goi-y">Phím tắt: <kbd>Tab</kbd> từ ô SBD sang ô mã đề · <kbd>Enter</kbd> lưu</span></div></div></div></div>`;
}
/* AA2 a: phóng to ảnh ô viết tay của các cột đang lệch / chưa chắc, ngay cạnh chữ số ô tô – giáo viên không phải nheo mắt nhìn ảnh 56 px. */
function phongToHtml(p) {
  const o = [["sbd", "SBD", p.sbd], ["exam_code", "Mã đề", p.exam_code]].flatMap(([field, ten, tr]) => (tr && tr.columns || [])
    .filter((c) => DuyetDinhDanh.cotCanNhin(c, tr)).map((c) => {
      const h = c.handwriting;
      const anh = h && h.has_crop ? `<img src="/sheets/${p.sheet_id}/digits/${field}/${h.pos}/image" alt="${ten} cột ${c.vi_tri} – ô viết tay">` : '<span class="muted small">(không có ảnh ô viết tay)</span>';
      const doc = !h ? "–" : h.o_trong ? "ô trống" : h.chu_so === "?" ? "không đọc được" : `${esc(h.chu_so)} (${Math.round(h.p * 100)}%)`;
      return `<figure class="pt-cot"><figcaption>${ten} · cột ${Number(c.vi_tri)}</figcaption>
        <div class="pt-o"><div><span class="small muted">Ô tô</span><b class="pt-to">${esc(c.bubble ?? c.chu_so)}</b></div>${anh}</div>
        <div class="small muted" title="Máy đọc chữ viết tay">Máy đọc: ${doc}</div></figure>`;
    }));
  return o.length ? `<div class="phong-to" id="phong-to">${o.join("")}</div>` : "";
}
/* AA2 c + e: phím tắt, kiểm tại ô (SBD ngoài danh sách / mã đề ngoài kỳ thi) + gợi ý giá trị hợp lệ. Gợi ý CHỈ điền khi giáo viên bấm. */
function ganDinhDanh(id, p, dsSbd, datTieuDiem) {
  const khung = $("#khung-dd"), maHopLe = state.exam ? state.exam.codes.map((c) => c.code) : [];
  const ctx = { dsSbd, maHopLe, tuGoiY: {} };
  const ve = (idBao, idO, kq) => {
    const o = $("#" + idO), bao = $("#" + idBao);
    o.classList.toggle("sai", kq.muc === "loi"); o.classList.toggle("can-hoi", kq.muc === "canh_bao");
    o.setAttribute("aria-invalid", kq.muc === "loi" ? "true" : "false");
    const lop = kq.muc === "loi" ? "bad" : kq.muc === "canh_bao" ? "warn" : "muted";
    const goi = kq.goi_y.length ? `<span class="goi-y-ds">${idO === "in-sbd" ? "SBD gần giống trong danh sách (chỉ để đối chiếu – so với ảnh trước khi chọn):" : "Mã đề hợp lệ của kỳ thi:"}
      ${kq.goi_y.map((v) => `<button type="button" class="goi-y" data-fill="${idO}" data-val="${esc(v)}" data-goi-y="1">${esc(v)}</button>`).join(" ")}</span>` : "";
    bao.innerHTML = kq.thong_bao || goi ? `<div class="${lop}">${esc(kq.thong_bao)}</div>${goi}` : "";
  };
  ctx.kiem = () => {
    const kS = DuyetDinhDanh.kiemSbd($("#in-sbd").value, dsSbd), kM = DuyetDinhDanh.kiemMaDe($("#in-ma").value, maHopLe);
    ve("bao-sbd", "in-sbd", kS); ve("bao-ma", "in-ma", kM);
    return [kS, kM];
  };
  khung.addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-fill]");
    if (!b) return;
    const o = $("#" + b.dataset.fill);
    o.value = b.dataset.val;
    ctx.tuGoiY[b.dataset.fill === "in-sbd" ? "sbd" : "ma"] = b.dataset.goiY ? b.dataset.val : undefined;
    ctx.kiem(); o.focus();
  });
  for (const idO of ["in-sbd", "in-ma"]) $("#" + idO).addEventListener("input", ctx.kiem);
  khung.addEventListener("keydown", (ev) => {
    if (ev.isComposing) return;
    const a = DuyetDinhDanh.phim(ev.key, ev.shiftKey, ev.target.id);
    if (!a) return;
    ev.preventDefault();
    if (a === "luu") luuDinhDanh(id, ctx); else $("#" + a).focus();
  });
  $("#luu-dd").addEventListener("click", () => luuDinhDanh(id, ctx));
  ctx.kiem();
  if (datTieuDiem) {
    const o = $(p.sbd.can_xem || !p.student ? "#in-sbd" : "#in-ma");
    khung.scrollIntoView({ block: "start" }); o.focus({ preventScroll: true });
  }
}
let dangLuuDd = false;
async function luuDinhDanh(id, ctx) {
  if (dangLuuDd) return;                                                          // Enter giữ lâu / bấm hai lần: chỉ gửi một lần
  const sbd = $("#in-sbd").value.trim(), ma = $("#in-ma").value.trim();
  const [kS, kM] = ctx.kiem();
  if (DuyetDinhDanh.chanLuu(kS, kM)) { toast(kS.muc === "trong" && kM.muc === "trong" ? "Nhập SBD và / hoặc mã đề." : "Sửa ô báo đỏ trước khi lưu.", true); return; }
  const hoi = DuyetDinhDanh.canXacNhan(sbd, ma, kS, kM, ctx.tuGoiY);
  if (hoi.length && !confirm(`${hoi.join("\n\n")}\n\nVẫn lưu SBD / mã đề này?`)) return;
  const body = {}; if (sbd) body.sbd = sbd; if (ma) body.exam_code = ma;
  dangLuuDd = true; $("#luu-dd").disabled = true;
  try { await put(`/sheets/${id}/identity`, body); toast("Đã lưu SBD / mã đề."); await manDuyet(id, { daLuu: true }); }
  catch (e) { toast(e.message, true); const b = $("#luu-dd"); if (b) b.disabled = false; }
  finally { dangLuuDd = false; }
}
function theCau(id, q, p) {
  const xong = !q.needs_review;
  const viTri = q.reasons.includes("vi_tri");
  const dacMay = q.omr_selected_options || "bỏ trống";
  const nh = DuyetNhanh.nhanCau(q);                                               // AF5: "máy đọc X · dấu hiệu Y" + gợi ý quyết nhanh
  return `<div class="rcard ${xong ? "done" : ""}" data-q="${q.question_no}" id="the-cau-${q.question_no}" ${xong ? "" : 'tabindex="0"'} aria-label="Câu ${q.question_no}">
    <div><img src="/sheets/${id}/questions/${q.question_no}/image" alt="câu ${q.question_no}" loading="lazy"></div>
    <div><h3>Câu ${q.question_no} ${xong ? '<span class="tag ok">đã chốt</span>' : ""}</h3>
      ${xong ? "" : `<p class="nhan-cau muc-${nh.muc}"><span class="tag">Máy đọc: <b>${esc(nh.may_doc)}</b></span> <span class="tag dau-hieu">Dấu hiệu: ${esc(nh.dau_hieu || "–")}</span>
        ${nh.goi_y ? `<span class="small muted">${esc(nh.goi_y)}</span>` : ""}</p>`}
      <p>Máy đọc: <b>${esc(dacMay)}</b> · lý do: ${esc(LyDoCau.chuoi(q.reasons) || "–")}${LyDoCau.doTinCay(q) ? ` · <span class="muted">${esc(LyDoCau.doTinCay(q))}</span>` : ""}</p>
      ${xong ? `<p>Đáp án đã chốt: <b>${esc(q.selected_options || "bỏ trống")}</b>${q.manually_edited ? " (giáo viên sửa)" : " (xác nhận như máy đọc)"}</p>
      <div class="row">${HoanTac.nutHtml(q, p)}</div>` : `
      <div class="opts row">${["A", "B", "C", "D"].map((o) => `<button type="button" data-o="${o}">${o}</button>`).join("")}<span class="muted small">(chọn nhiều ô nếu thực sự tô 2 ô)</span></div>
      <div class="row"><button class="pri" data-act="set">Lưu lựa chọn</button><button data-act="blank">Bỏ trống</button>
        <button data-act="confirm" ${viTri ? 'disabled title="Chưa chắc vị trí hàng – phải chọn thủ công"' : ""}>Xác nhận như máy đọc (${esc(dacMay)})</button></div>
      ${viTri ? '<p class="small muted">Máy chưa chắc vị trí hàng này nên không cho xác nhận nhanh – hãy nhìn ảnh rồi chọn.</p>' : ""}`}
    </div></div>`;
}
function theCauTuCham(id, q, p) {
  const xong = !q.tu_cham_can_xem;
  const dacMay = q.omr_selected_options || "bỏ trống";
  return `<div class="rcard tc ${xong ? "done" : ""}" data-q="${q.question_no}" data-tc="1" id="the-cau-${q.question_no}" ${xong ? "" : 'tabindex="0"'} aria-label="Câu ${q.question_no} đã chấm tự động">
    <div><img src="/sheets/${id}/questions/${q.question_no}/image" alt="câu ${q.question_no}" loading="lazy"></div>
    <div><h3>Câu ${q.question_no} ${xong ? '<span class="tag ok">đã xem lại</span>' : '<span class="tag warn">tự chấm sai</span>'}</h3>
      <p>Máy đọc: <b>${esc(dacMay)}</b> · ${xong ? `đáp án hiện tại: <b>${esc(q.selected_options || "bỏ trống")}</b>${q.manually_edited ? " (giáo viên sửa)" : " (giữ như máy chấm)"}` : "tô nhiều ô nên tính SAI (0 điểm)"}</p>
      ${xong ? `<div class="row">${HoanTac.nutHtml(q, p)}</div>` : `<div class="opts row">${["A", "B", "C", "D"].map((o) => `<button type="button" data-o="${o}">${o}</button>`).join("")}</div>
      <div class="row"><button class="pri" data-act="set">Lưu lựa chọn</button><button data-act="blank">Bỏ trống</button>
        <button data-act="keep">Giữ như máy chấm (${esc(dacMay)} – tính sai)</button></div>`}
    </div></div>`;
}
async function hoanTacCau(id, n, p, q, lamMoi) {
  const hoi = HoanTac.loiHoi(q, p);
  if (hoi && !confirm(hoi)) return;
  try {
    await post(`/sheets/${id}/questions/${n}/review/undo`, {});
    if (daXem[id]) daXem[id].delete(n);
    if (daXemTuCham[id]) daXemTuCham[id].delete(n);
    toast(`Câu ${n} đã hoàn tác.`); await lamMoi();
  } catch (e) { toast(e.message, true); }
}
function ganHoanTac(el, id, p, lamMoi) {
  const b = el.querySelector("[data-undo]");
  if (!b) return;
  const n = Number(b.dataset.undo);
  b.addEventListener("click", () => { b.disabled = true; hoanTacCau(id, n, p, p.questions.find((x) => x.question_no === n), lamMoi).finally(() => { b.disabled = false; }); });
}
function gan(el, id, p) {
  const n = Number(el.dataset.q);
  if (!el.dataset.tc && el.classList.contains("done")) ganHoanTac(el, id, p, () => manDuyet(id));
  if (el.dataset.tc) return ganTuCham(el, id, n, p);
  if (!el.classList.contains("done")) el.addEventListener("focusin", () => datHienTai(id, n));    // bấm / Tab vào thẻ -> phím tắt tác động lên câu này
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
    const keTiepCau = DuyetNhanh.cauKeTiep(cauConLai(), n);                       // lưu xong sang câu kế (AF1: Enter = lưu và sang câu kế)
    try { await post(`/sheets/${id}/questions/${n}/review`, body); daXem[id].add(n); cauHT[id] = keTiepCau; toast(`Câu ${n} đã chốt.`); await manDuyet(id); }
    catch (e) { toast(e.message, true); el.querySelectorAll("button").forEach((x) => (x.disabled = false)); }
  }));
}

function ganTuCham(el, id, n, p) {
  if (el.classList.contains("done")) ganHoanTac(el, id, p, () => manDuyet(id));
  if (!el.classList.contains("done")) el.addEventListener("focusin", () => datHienTai(id, n));
  el.querySelectorAll(".opts button").forEach((b) => b.addEventListener("click", () => b.classList.toggle("sel")));
  el.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
    const act = b.dataset.act;
    let body;
    if (act === "keep") body = { action: "keep" };
    else if (act === "blank") body = { action: "set", selected_options: "" };
    else {
      const ch = [...el.querySelectorAll(".opts .sel")].map((x) => x.dataset.o).join("");
      if (!ch) { toast("Chọn ít nhất một đáp án, hoặc bấm 'Bỏ trống'.", true); return; }
      body = { action: "set", selected_options: ch };
    }
    el.querySelectorAll("button").forEach((x) => (x.disabled = true));
    try {
      await post(`/sheets/${id}/questions/${n}/auto-review`, body);
      daXemTuCham[id].add(n); toast(act === "keep" ? `Câu ${n}: giữ như máy chấm.` : `Câu ${n} đã sửa, điểm được tính lại.`); await manDuyet(id);
    } catch (e) { toast(e.message, true); el.querySelectorAll("button").forEach((x) => (x.disabled = false)); }
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
    const canhBao = (d.duplicate_pending ? `<span class="tag bad">Còn ${d.duplicate_pending} phiếu trùng chờ duyệt</span> ${d.duplicate_sheet_ids.map((s) => `<a href="#/review/${s}">#${s}</a>`).join(" ")}` : "")
      + (d.auto_graded_pending ? `<span class="tag warn">Còn ${d.auto_graded_pending} câu tô nhiều ô đã chấm sai, chờ xem lại</span> <a href="#/review/${d.sheet_id}">#${d.sheet_id}</a>` : "");
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
      ${k.auto_graded_pending_questions ? `<span class="tag warn">Câu tô nhiều ô chờ xem lại: ${k.auto_graded_pending_questions}</span>` : ""}
      <a class="btn pri" href="/exams/${state.examId}/export.xlsx" download>Xuất Excel</a></div>
      ${k.auto_graded_pending_questions ? `<div class="alert warn" id="canh-bao-tu-cham-bd">Còn ${k.auto_graded_pending_questions} câu tô nhiều ô (${k.students_auto_graded_pending} thí sinh) đã chấm sai tự động, chờ giáo viên xem lại. Điểm ở bảng đã tính các câu này là sai; xem lại ở <a href="#/review">Hàng đợi</a>.</div>` : ""}
      ${k.students_duplicate_pending ? `<div class="alert warn">${k.students_duplicate_pending} thí sinh còn phiếu <b>trùng SBD</b> đang chờ duyệt. Điểm ở bảng là của phiếu đã chính thức; hãy xử lý các phiếu trùng ở cột "Cảnh báo" trước khi xuất Excel chốt.</div>` : ""}
      <p class="muted small">Cột <b>Điểm</b> chỉ có điểm chính thức. Điểm của phiếu chưa duyệt xong nằm ở cột <b>Điểm tạm</b> và chưa phải điểm chính thức.
        Phiếu bị từ chối là ảnh không dùng được nên không biết của thí sinh nào (chụp lại).</p>
      <table><thead><tr><th>STT</th><th>SBD</th><th>Họ tên</th><th>Mã đề</th><th>Số câu đúng</th><th>Điểm</th><th>Điểm tạm</th><th>Trạng thái</th><th>Phiếu</th><th>Cảnh báo</th></tr></thead>
      <tbody>${b.rows.map(hang).join("") || '<tr><td colspan="10" class="muted">Kỳ thi chưa có danh sách thí sinh.</td></tr>'}</tbody></table></div>
    ${b.unmatched.length ? `<div class="card"><h3>Phiếu chưa ghép được thí sinh (${b.unmatched.length})</h3><table><thead><tr><th>Phiếu</th><th>Ảnh</th><th>Trạng thái</th><th>Lý do</th></tr></thead><tbody>
      ${b.unmatched.map((p) => `<tr><td><a href="#/sheet/${p.sheet_id}">#${p.sheet_id}</a></td><td>${tenTepHtml(p.original_filename)}</td><td>${tag(p.status)}</td>
        <td>${p.status === "rejected" ? esc(p.reject_message || p.reject_code) : esc(p.reject_message || ("SBD đọc: " + (p.detected_sbd || "–") + " – chưa ghép được thí sinh"))}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
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
/* sauDangNhap: vừa đăng nhập bằng form -> chỉnh trang đích (chinhHash). Mở trang khi đã có phiên: giữ hash như gõ (gõ #/admin mà không phải admin
   thì thấy thông báo từ chối + nút "Về trang chính"). */
async function khoiDong(sauDangNhap = false) {
  try { state.me = await api("/me"); } catch (e) { if (!e.dangNhap) main.innerHTML = `<div class="alert bad">Không nối được API: ${esc(e.message)}</div>`; return; }
  hienNguoiDung();
  try { await napKyThi(); if (sauDangNhap) await chinhHash(); } catch (e) { if (e.dangNhap) return; main.innerHTML = `<div class="alert bad">Không nối được API: ${esc(e.message)}</div>`; return; }
  route();
}
khoiDong();
