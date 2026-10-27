/* Smart Exam – trang điện thoại /m: đăng nhập → chọn kỳ thi → chụp bằng CAMERA GỐC (input capture) → tải lên ảnh GỐC (không nén) → chấm → kết quả.
   Phiên = cookie HttpOnly do máy chủ đặt (KHÔNG lưu token ở localStorage). Điện thoại KHÔNG duyệt câu: việc duyệt làm trên máy tính.
   docs/thiet_ke_chup_dien_thoai.md mục 2. */
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(2).replace(/\.?0+$/, ""));
const HET_GIO_MS = 120000;
const st = { me: null, exams: [], exam: null, reasons: {}, gioiHanMb: 25, dangGui: false, dem: { tong: 0, cham: 0, tuChoi: 0, trung: 0, loi: 0 }, ganDay: [] };

const LY_DO_SBD = { lech_bubble: "chữ viết tay khác ô tô", tin_cay_thap: "chữ viết tay khó đọc", thieu_bubble: "cột ô tô không đọc được",
  bubble_cx: "ô tô chưa chắc", o_trong_ngoai_ds: "không có trong danh sách kỳ thi", o_trong_chua_biet_ds: "chưa kiểm được danh sách",
  o_it_muc: "ô viết tay quá ít mực", khong_phai_chu_so: "ô viết tay không giống chữ số" };

let toastT;
function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.add("hidden"), 4000); }
function hien(id) { document.querySelectorAll(".view").forEach((v) => v.classList.toggle("hidden", v.id !== id)); window.scrollTo(0, 0); }

class LoiApi extends Error { constructor(msg, ma) { super(msg); this.ma = ma; } }

/* Lời gọi JSON. 401 -> màn đăng nhập. Mọi lỗi đổi thành câu dễ hiểu. */
async function api(path, opts = {}) {
  let r;
  try { r = await fetch(path, { credentials: "same-origin", ...opts }); }
  catch (_) { throw new LoiApi("Không kết nối được máy chủ. Kiểm tra điện thoại và máy tính cùng mạng Wi‑Fi.", 0); }
  let body = null; try { body = await r.json(); } catch (_) { /* rỗng */ }
  if (!r.ok) throw new LoiApi(thongBaoLoi(r.status, body), r.status);
  return body;
}
function thongBaoLoi(ma, body) {
  let d = body && body.detail; if (Array.isArray(d)) d = d.map((x) => x.msg).join("; ");
  if (ma === 401) return "Phiên đăng nhập đã hết – hãy đăng nhập lại.";
  if (ma === 403) return d || "Tài khoản này không dùng được chức năng chấm.";
  if (ma === 404) return "Không tìm thấy kỳ thi (hoặc bạn không phụ trách lớp này).";
  if (ma === 413) return `Ảnh quá lớn (giới hạn ${st.gioiHanMb} MB).`;
  if (ma >= 500) return "Máy chủ gặp lỗi khi chấm ảnh này. Thử chụp lại; nếu lặp lại, báo người quản trị.";
  return d || `Lỗi ${ma}`;
}
function xuLyLoi(e) {
  if (e.ma === 401) { st.me = null; manDangNhap(e.message); return true; }
  return false;
}

/* ------------------------------------------------------------ đăng nhập */
function manDangNhap(thongBao) {
  $("#who").textContent = ""; $("#logout").classList.add("hidden");
  const er = $("#lg-err"); er.textContent = thongBao || ""; er.classList.toggle("hidden", !thongBao);
  hien("v-login");
}
$("#f-login").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const b = ev.submitter || $("#f-login button"); b.disabled = true;
  try {
    await api("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("#lg-user").value.trim(), password: $("#lg-pass").value }) });
    $("#lg-pass").value = "";
    await khoiDong();
  } catch (e) {
    const er = $("#lg-err"); er.textContent = e.ma === 401 ? "Sai tên đăng nhập hoặc mật khẩu." : e.message; er.classList.remove("hidden");
  } finally { b.disabled = false; }
});
$("#logout").addEventListener("click", async () => {
  try { await api("/auth/logout", { method: "POST" }); } catch (_) { /* bỏ qua */ }
  st.me = null; st.exam = null; manDangNhap("Đã đăng xuất.");
});

/* ------------------------------------------------------------ chọn kỳ thi */
async function manKyThi() {
  st.exams = await api("/exams");
  const ds = $("#exam-list");
  ds.innerHTML = st.exams.length ? st.exams.map((e) => `<button type="button" class="exam" data-id="${e.exam_id}">
      <span class="sub">${esc(e.subject_name)} · ${esc(e.class_code || "không lớp")}</span><b>${esc(e.exam_title)}</b>
      <span class="sub">${e.so_phieu} phiếu</span></button>`).join("")
    : '<p class="muted">Bạn chưa có kỳ thi nào. Tạo kỳ thi trên máy tính trước.</p>';
  ds.querySelectorAll(".exam").forEach((b) => b.addEventListener("click", () => chonKyThi(Number(b.dataset.id))));
  hien("v-exams");
}
function chonKyThi(id) {
  st.exam = st.exams.find((e) => e.exam_id === id) || null;
  if (!st.exam) return;
  try { sessionStorage.setItem("m_exam", String(id)); } catch (_) { /* bỏ qua */ }
  $("#cap-sub").textContent = `${st.exam.subject_name} · ${st.exam.class_code || "không lớp"}`;
  $("#cap-title").textContent = st.exam.exam_title;
  $("#ket-qua").classList.add("hidden");
  veBoDem();
  hien("v-cap");
}
$("#doi-ky-thi").addEventListener("click", () => { if (!st.dangGui) manKyThi().catch((e) => { if (!xuLyLoi(e)) toast(e.message); }); });

/* ------------------------------------------------------------ chụp + tải lên */
$("#cam").addEventListener("change", (ev) => {
  const f = ev.target.files && ev.target.files[0];
  ev.target.value = "";                           // chụp lại cùng tệp vẫn kích hoạt 'change'
  if (f) guiAnh(f);
});

function taiLen(f) {
  /* XMLHttpRequest để có tiến trình tải lên (fetch không báo upload progress). Gửi tệp GỐC – không nén, không đổi kích thước. */
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", `/exams/${st.exam.exam_id}/sheets`);
    x.timeout = HET_GIO_MS;
    x.upload.onprogress = (e) => { if (e.lengthComputable) { $("#dc-bar").style.width = `${Math.round((e.loaded / e.total) * 100)}%`;
      if (e.loaded >= e.total) $("#dc-txt").textContent = "Đang chấm…"; } };
    x.onload = () => {
      let body = null; try { body = JSON.parse(x.responseText); } catch (_) { /* rỗng */ }
      if (x.status >= 200 && x.status < 300) resolve(body); else reject(new LoiApi(thongBaoLoi(x.status, body), x.status));
    };
    x.onerror = () => reject(new LoiApi("Mất kết nối khi gửi ảnh. Kiểm tra Wi‑Fi rồi chụp lại.", 0));
    x.ontimeout = () => reject(new LoiApi("Quá thời gian chờ (2 phút). Mạng chậm hoặc máy chủ bận – chụp lại.", 0));
    const fd = new FormData(); fd.append("file", f, f.name || "anh.jpg");
    x.send(fd);
  });
}

async function guiAnh(f) {
  if (st.dangGui || !st.exam) return;
  if (f.size > st.gioiHanMb * 1024 * 1024) { veLoi(`Ảnh ${(f.size / 1048576).toFixed(1)} MB lớn hơn giới hạn ${st.gioiHanMb} MB. Giảm độ phân giải camera rồi chụp lại.`); return; }
  st.dangGui = true; $("#cam-btn").classList.add("off");
  $("#ket-qua").classList.add("hidden"); $("#dang-cham").classList.remove("hidden");
  $("#dc-txt").textContent = `Đang tải ảnh (${(f.size / 1048576).toFixed(1)} MB)…`; $("#dc-bar").style.width = "0";
  const t0 = performance.now();
  try {
    const r = await taiLen(f);
    let v = null;
    if (r.status !== "rejected") v = await api(`/sheets/${r.sheet_id}`);
    st.dem.tong++; if (r.da_ton_tai) st.dem.trung++; else if (r.status === "rejected") st.dem.tuChoi++; else st.dem.cham++;
    veKetQua(r, v, Math.round(performance.now() - t0));
  } catch (e) {
    if (xuLyLoi(e)) return;
    st.dem.tong++; st.dem.loi++;
    veLoi(e.message);
  } finally {
    st.dangGui = false; $("#cam-btn").classList.remove("off"); $("#dang-cham").classList.add("hidden");
  }
}

/* ------------------------------------------------------------ kết quả */
function nutChup(nhan) { return `<button type="button" class="big pri" data-chup>${nhan}</button>`; }
function ganNut() { document.querySelectorAll("[data-chup]").forEach((b) => b.addEventListener("click", () => $("#cam").click())); }

function veKetQua(r, v, ms) {
  const k = $("#ket-qua"); let html = "", nhan = "";
  if (r.da_ton_tai) html += '<div class="msg warn">Ảnh này đã tải trước đó – hiển thị phiếu cũ, không chấm lại.</div>';
  if (r.status === "rejected") {
    const ly = st.reasons[r.reject_code] || {};
    html += `<h2>Ảnh không dùng được</h2><div class="msg bad"><b>${esc(r.reject_message || ly.message || r.reject_code)}</b></div>
      <p><b>Cách chụp lại:</b> ${esc(ly.advice || "Chụp rõ nét, đủ sáng, thấy đủ 4 ô vuông đen ở 4 góc.")}</p>
      <p class="muted small">Phiếu #${r.sheet_id} · không có điểm.</p>${nutChup("📷 Chụp lại")}`;
    nhan = '<span class="tag bad">từ chối</span>';
  } else {
    const sc = v.score || {}, sv = v.student, chinhThuc = sc.official !== null && sc.official !== undefined;
    const lyPhieu = (v.review && v.status === "needs_review" && v.review.reasons) || [];
    const canhBao = [];
    if (v.sbd && v.sbd.can_xem) canhBao.push(`SBD cần xem: ${(v.sbd.reasons || []).map((m) => LY_DO_SBD[m] || m).join(", ") || "máy chưa chắc"}`);
    else if (lyPhieu.includes("sbd_not_found")) canhBao.push(`SBD ${esc(v.sbd && v.sbd.detected)} không có trong danh sách kỳ thi – chưa ghi điểm.`);
    if (lyPhieu.includes("duplicate_sbd")) canhBao.push("SBD trùng với một phiếu khác của kỳ thi.");
    if (v.exam_code && v.exam_code.can_xem) canhBao.push("Mã đề cần xem (máy chưa chắc).");
    else if (lyPhieu.includes("exam_code_not_found") || !(v.exam_code && v.exam_code.matched_code)) canhBao.push(`Mã đề ${esc(v.exam_code && v.exam_code.detected)} không thuộc kỳ thi.`);
    const toNhat = v.questions.some((q) => q.needs_review && (q.reasons || []).includes("to_nhat"));
    html += `<h2>${sv ? esc(sv.full_name) : "Chưa ghép được sinh viên"}</h2>
      <p class="muted">${sv ? "SBD " + esc(sv.student_code) : "SBD đọc được: " + esc((v.sbd && v.sbd.detected) || "–")} · Phiếu #${v.sheet_id}</p>
      <div class="score">${chinhThuc ? `${fmt(sc.official)}<small> / ${fmt(sc.max_score)} – chính thức</small>`
        : `${fmt(sc.provisional)}<small> điểm TẠM</small>`}</div>
      ${chinhThuc ? '<div class="msg ok">Máy tự chốt: không còn mục nào cần xem.</div>'
        : `<p class="small muted">Điểm tạm chỉ tính các câu máy chắc chắn – <b>chưa phải điểm chính thức</b>.</p>`}
      <div class="kv"><div><span>Câu cần giáo viên xem</span><span>${sc.pending_questions ?? 0}</span></div>
        <div><span>Mã đề</span><span>${esc((v.exam_code && (v.exam_code.matched_code || v.exam_code.detected)) || "–")}</span></div></div>
      ${toNhat ? '<div class="msg warn">Phiếu tô nhạt cả tờ – mọi câu đã chọn cần giáo viên kiểm tra lại.</div>' : ""}
      ${canhBao.map((c) => `<div class="msg warn">${c}</div>`).join("")}
      ${v.status === "needs_review" ? `<p class="small">Duyệt trên máy tính: <b>Hàng đợi duyệt → phiếu #${v.sheet_id}</b><br><code>${esc(location.origin)}/app/#/review/${v.sheet_id}</code></p>` : ""}
      <p class="muted small">${(ms / 1000).toFixed(1)} giây</p>${nutChup("📷 Chụp tiếp")}`;
    nhan = chinhThuc ? `<span class="tag ok">${fmt(sc.official)}</span>` : `<span class="tag warn">${fmt(sc.provisional)} tạm · ${sc.pending_questions ?? 0} câu</span>`;
  }
  k.innerHTML = html; k.classList.remove("hidden"); ganNut();
  st.ganDay = st.ganDay.filter((g) => g.id !== r.sheet_id);          // ảnh trùng: đưa phiếu cũ lên đầu, không lặp dòng
  st.ganDay.unshift({ id: r.sheet_id, ten: (v && v.student && v.student.full_name) || (r.status === "rejected" ? "Ảnh bị từ chối" : "Chưa ghép SV"), nhan });
  st.ganDay = st.ganDay.slice(0, 5); veBoDem();
  window.scrollTo({ top: 0, behavior: "smooth" });                 // thẻ kết quả nằm ngay dưới tên kỳ thi: đầu trang = thấy trọn thẻ
}
function veLoi(msg) {
  const k = $("#ket-qua");
  k.innerHTML = `<h2>Chưa gửi được ảnh</h2><div class="msg bad">${esc(msg)}</div>${nutChup("📷 Chụp lại")}`;
  k.classList.remove("hidden"); ganNut(); veBoDem();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function veBoDem() {
  const d = st.dem;
  $("#counter").textContent = d.tong ? `Phiên này: đã chụp ${d.tong} · ${d.cham} chấm được · ${d.tuChoi} bị từ chối${d.trung ? ` · ${d.trung} ảnh trùng` : ""}${d.loi ? ` · ${d.loi} lỗi gửi` : ""}` : "Chưa chụp phiếu nào trong phiên này.";
  $("#recent").innerHTML = st.ganDay.map((g) => `<li><span>#${g.id} ${esc(g.ten)}</span>${g.nhan}</li>`).join("");
}

/* ------------------------------------------------------------ khởi động */
async function khoiDong() {
  try { st.me = await api("/me"); }
  catch (e) { if (e.ma === 401) { manDangNhap(); return; } manDangNhap(e.message); return; }
  $("#who").textContent = st.me.full_name; $("#logout").classList.remove("hidden");
  try {
    st.reasons = await api("/meta/reject-reasons");
    try { st.gioiHanMb = (await api("/meta/ket-noi")).gioi_han_anh_mb || st.gioiHanMb; } catch (_) { /* giữ mặc định */ }
    await manKyThi();
    let id = null; try { id = Number(sessionStorage.getItem("m_exam")); } catch (_) { /* bỏ qua */ }
    if (id && st.exams.some((e) => e.exam_id === id)) chonKyThi(id);
  } catch (e) { if (!xuLyLoi(e)) toast(e.message); }
}
khoiDong();
