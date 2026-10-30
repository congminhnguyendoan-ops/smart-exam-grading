/* Smart Exam – trang điện thoại /m, CHỤP LIÊN TỤC: đăng nhập → chọn kỳ thi → chụp tờ này rồi tờ kế (camera gốc, input capture) KHÔNG chờ kết quả;
   ảnh GỐC (không nén) vào hàng đợi frontend/m_hang_doi.js, gửi nền tối đa 2 yêu cầu song song (POST /exams/{id}/sheets như cũ).
   Phiên = cookie HttpOnly do máy chủ đặt (KHÔNG lưu token ở localStorage). Điện thoại KHÔNG duyệt câu: việc duyệt làm trên máy tính.
   docs/thiet_ke_chup_dien_thoai.md mục 2 + 9. */
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(2).replace(/\.?0+$/, ""));
const HET_GIO_MS = 120000;
const SONG_SONG = 2;
const st = { me: null, exams: [], exam: null, reasons: {}, gioiHanMb: 25, kyThiUrl: MKyThi.docThamSo(location.search) };
/* ?kythi=<id> (QR trang bìa): giữ trong URL cho tới khi ĐÃ đăng nhập và chọn xong -> đăng nhập (kể cả tải lại trang) vẫn quay về đúng kỳ thi.
   Chỉ id lấy từ URL được hiện trước khi đăng nhập; TÊN kỳ thi chỉ hiện khi máy chủ trả nó trong GET /exams (có quyền). */
function boThamSoKyThi() {
  st.kyThiUrl = null;
  try { history.replaceState(null, "", location.pathname); } catch (_) { /* bỏ qua */ }
}

const LY_DO_SBD = { lech_bubble: "chữ viết tay khác ô tô", tin_cay_thap: "chữ viết tay khó đọc", thieu_bubble: "cột ô tô không đọc được",
  bubble_cx: "ô tô chưa chắc", o_trong_ngoai_ds: "không có trong danh sách kỳ thi", o_trong_chua_biet_ds: "chưa kiểm được danh sách",
  o_it_muc: "ô viết tay quá ít mực", khong_phai_chu_so: "ô viết tay không giống chữ số" };

let toastT;
function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.add("hidden"), 4000); }
function hien(id) { document.querySelectorAll(".view").forEach((v) => v.classList.toggle("hidden", v.id !== id)); window.scrollTo(0, 0); }

class LoiApi extends Error { constructor(msg, ma) { super(msg); this.ma = ma; } }

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
  if (ma >= 500) return "Máy chủ gặp lỗi khi chấm ảnh này. Gửi lại; nếu lặp lại, báo người quản trị.";
  return d || `Lỗi ${ma}`;
}

/* ------------------------------------------------------------ hàng đợi (gửi nền) */
function taiLen(to, baoTienTrinh) {
  /* XMLHttpRequest: có tiến trình tải lên (fetch không có). Gửi tệp GỐC – không nén, không đổi kích thước. */
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", `/exams/${to.examId}/sheets`);
    x.timeout = HET_GIO_MS;
    x.upload.onprogress = (e) => { if (e.lengthComputable) baoTienTrinh(e.loaded / e.total); };
    x.upload.onload = () => baoTienTrinh(1);
    x.onload = () => {
      let body = null; try { body = JSON.parse(x.responseText); } catch (_) { /* rỗng */ }
      if (x.status >= 200 && x.status < 300) resolve(body); else reject(new LoiApi(thongBaoLoi(x.status, body), x.status));
    };
    x.onerror = () => reject(new LoiApi("Mất kết nối khi gửi ảnh – ảnh vẫn giữ trên máy, bấm Gửi lại.", 0));
    x.ontimeout = () => reject(new LoiApi("Quá thời gian chờ (2 phút) – bấm Gửi lại.", 0));
    const fd = new FormData(); fd.append("file", to.file, to.file.name || `to_${to.soTo}.jpg`);
    x.send(fd);
  });
}
async function guiMotTo(to, baoTienTrinh) {
  if (to.file.size > st.gioiHanMb * 1024 * 1024) throw new LoiApi(`Ảnh ${(to.file.size / 1048576).toFixed(1)} MB lớn hơn giới hạn ${st.gioiHanMb} MB – giảm độ phân giải camera rồi chụp lại.`, 413);
  const r = await taiLen(to, baoTienTrinh);
  if (r.status !== "rejected") {
    try { r.chiTiet = await api(`/sheets/${r.sheet_id}`); }
    catch (e) { if (e.ma === 401) throw e; /* chi tiết lỗi tạm thời: vẫn có điểm tạm từ kết quả tải */ }
  }
  return r;
}

let veHen = 0;
const hd = new HangDoi({ gui: guiMotTo, toiDa: SONG_SONG, khiDoi: () => { if (!veHen) veHen = requestAnimationFrame(() => { veHen = 0; veHangDoi(); }); } });
window.__hangDoi = hd;                                                  // cho công cụ đo tools/thu_dien_thoai.py đọc thời gian từng tờ

function themAnh(files) {
  if (!st.exam || !files.length) return;
  const moi = hd.them([...files], { examId: st.exam.exam_id });
  if (moi.length > 1) toast(`Đã thêm ${moi.length} ảnh vào hàng đợi.`);
  requestAnimationFrame(() => { const el = document.querySelector(`[data-stt="${moi[moi.length - 1].stt}"]`); if (el) el.scrollIntoView({ block: "nearest" }); });
}
$("#cam").addEventListener("change", (ev) => { const f = [...(ev.target.files || [])]; ev.target.value = ""; themAnh(f); });
$("#nhieu").addEventListener("change", (ev) => { const f = [...(ev.target.files || [])]; ev.target.value = ""; themAnh(f); });

/* ------------------------------------------------------------ vẽ */
function tongTo() { const n = Number($("#tong-to").value); return n > 0 ? n : null; }
$("#tong-to").addEventListener("change", () => { try { sessionStorage.setItem("m_tong", $("#tong-to").value); } catch (_) { /* bỏ qua */ } veHangDoi(); });

function nhanTrangThai(t) {
  const k = t.ketQua;
  if (t.trangThai === "mat") return ['<span class="tag bad">chưa gửi xong · mất khi tải lại</span>', ""];
  if (t.trangThai === "cho") return ['<span class="tag gray">chờ gửi</span>', ""];
  if (t.trangThai === "gui") return [`<span class="tag blue">đang gửi ${Math.round(t.tienTrinh * 100)}%</span>`, ""];
  if (t.trangThai === "cham") return ['<span class="tag blue">đang chấm…</span>', ""];
  if (t.trangThai === "loi") return [`<span class="tag bad">${t.maLoi >= 500 ? "lỗi máy chủ" : t.maLoi === 413 ? "ảnh quá lớn" : "lỗi mạng"}</span>`, ""];
  if (t.trangThai === "tuchoi") return ['<span class="tag bad">bị từ chối</span>', ""];
  if (t.trangThai === "trung") return ['<span class="tag gray">đã tải trước đó</span>', ""];
  if (k.status === "rejected") return ['<span class="tag bad">bị từ chối</span>', ""];
  if (k.status === "graded") return [`<span class="tag ok">đã chấm ${fmt(k.official_score)}</span>`, ""];
  return [`<span class="tag warn">cần xem ${k.pending_questions} câu</span>`, ""];
}
function canhBao(v) {
  if (!v) return [];
  const ly = (v.review && v.status === "needs_review" && v.review.reasons) || [], ra = [];
  if (v.sbd && v.sbd.can_xem) ra.push(`SBD cần xem: ${(v.sbd.reasons || []).map((m) => LY_DO_SBD[m] || m).join(", ") || "máy chưa chắc"}`);
  else if (ly.includes("sbd_not_found")) ra.push(`SBD ${esc(v.sbd && v.sbd.detected)} không có trong danh sách kỳ thi – chưa ghi điểm`);
  if (ly.includes("duplicate_sbd")) ra.push("SBD trùng với một phiếu khác");
  if (v.exam_code && v.exam_code.can_xem) ra.push("Mã đề cần xem");
  else if (!(v.exam_code && v.exam_code.matched_code)) ra.push(`Mã đề ${esc(v.exam_code && v.exam_code.detected)} không thuộc kỳ thi`);
  if (v.questions.some((q) => q.needs_review && (q.reasons || []).includes("to_nhat"))) ra.push("Tờ tô nhạt cả tờ – kiểm tra lại các câu");
  return ra;
}
function dongTo(t) {
  const [nhan] = nhanTrangThai(t), k = t.ketQua, v = k && k.chiTiet;
  const daKhoiPhuc = t.khoiPhuc ? ' <span class="small muted">(khôi phục)</span>' : "";
  let giua = "", duoi = "";
  if (k && k.status !== "rejected" && t.trangThai === "xong") {
    const ten = v && v.student ? `${esc(v.student.full_name)} · SBD ${esc(v.student.student_code)}` : `Chưa ghép SV · SBD ${esc((v && v.sbd && v.sbd.detected) || "?")}`;
    const diem = k.official_score !== null && k.official_score !== undefined ? `<b>${fmt(k.official_score)}</b> chính thức` : `<b>${fmt(k.provisional_score)}</b> điểm TẠM`;
    giua = `<div class="ten">${ten}</div><div class="diem">${diem} · phiếu #${k.sheet_id}</div>`;
    duoi = canhBao(v).map((c) => `<div class="cb">⚠ ${c}</div>`).join("");
  } else if (k && k.status === "rejected") {
    const ly = st.reasons[k.reject_code] || {};
    giua = `<div class="ten">${esc(k.reject_message || ly.message || k.reject_code)}</div>`;
    duoi = `<div class="cb">Cách chụp lại: ${esc(ly.advice || "chụp rõ nét, đủ sáng, thấy đủ 4 ô vuông đen.")}</div>` +
      (t.thayBang ? `<div class="small muted">→ đã chụp lại</div>` : `<label class="nut-dong pri">📷 Chụp lại tờ ${t.soTo}<input type="file" accept="image/*" capture="environment" data-chup-lai="${t.stt}"></label>`);
  } else if (t.trangThai === "mat") {
    giua = `<div class="ten">${tenTepHtml(t.ten || "ảnh")} · ${esc(t.loi)}</div>`;
    duoi = t.thayBang ? `<div class="small muted">→ đã chụp lại</div>`
      : `<div class="cb">Ảnh chưa gửi xong nên không khôi phục được – phải chụp lại tờ này.</div><label class="nut-dong pri">📷 Chụp lại tờ ${t.soTo}<input type="file" accept="image/*" capture="environment" data-chup-lai="${t.stt}"></label>`;
  } else if (t.trangThai === "tuchoi") {                               // V1: máy chủ trả lời rõ – gửi lại cũng hỏng, KHÔNG có nút Gửi lại
    giua = `<div class="ten"><b>${esc(LoiTai.tieuDeTuChoi(t.maLoi))}:</b> ${esc(t.loi)}</div>`;
    duoi = `<div class="cb">${t.maLoi === 409 ? "Ảnh chưa được lưu. Chọn kỳ thi khác (nút “Đổi kỳ thi”) hoặc nhờ quản trị viên mở lại kỳ thi rồi chụp lại."
      : "Ảnh chưa được lưu. Kiểm tra lại kỳ thi đang chọn hoặc tài khoản."}</div>`;
  } else if (t.trangThai === "loi") {
    giua = `<div class="ten">${esc(t.loi)}</div>`;
    duoi = t.maLoi === 413 ? `<label class="nut-dong pri">📷 Chụp lại tờ ${t.soTo}<input type="file" accept="image/*" capture="environment" data-chup-lai="${t.stt}"></label>`
      : `<button type="button" class="nut-dong pri" data-gui-lai="${t.stt}">↻ Gửi lại</button>`;
  } else if (t.trangThai === "trung") {
    giua = `<div class="ten">Ảnh này đã tải trước đó – phiếu #${k.sheet_id}, không chấm lại.</div>`;
  } else {
    giua = `<div class="ten muted">${tenTepHtml(t.ten || "ảnh")} · ${(t.kichThuoc / 1048576).toFixed(1)} MB</div>`;
  }
  return `<li class="to ${t.trangThai}${t.thayBang ? " da-thay" : ""}" data-stt="${t.stt}"><div class="dau"><b>Tờ ${t.soTo}</b>${t.thayCho ? ' <span class="small muted">(chụp lại)</span>' : ""}${daKhoiPhuc}${nhan}</div>${giua}${duoi}</li>`;
}
function veHangDoi() {
  const k = hd.tong(), tong = tongTo();
  $("#tk-so").innerHTML = `<span><b>${k.daChup}</b>${tong ? `/${tong}` : ""} đã chụp</span><span class="ok"><b>${k.chamDuoc}</b> chấm được</span>
    <span class="warn"><b>${k.canXem}</b> cần xem</span><span class="bad"><b>${k.tuChoi}</b> từ chối</span>`;
  $("#tk-cho").textContent = [hd.soMat() ? `${hd.soMat()} tờ mất khi tải lại (chụp lại)` : "", k.dangCho ? `${k.dangCho} đang chờ` : "", k.loi ? `${k.loi} lỗi mạng` : "", k.trung ? `${k.trung} ảnh trùng` : "",
    hd.tamDung ? "tạm dừng – cần đăng nhập" : ""].filter(Boolean).join(" · ") || "Không có tờ nào đang chờ.";
  const n = hd.soToKeTiep();
  $("#cam-txt").textContent = `📷 Chụp tiếp · Tờ ${n}${tong ? `/${tong}` : ""}`;
  veDanhSach();
  luuPhien();
  $("#goi-y").classList.toggle("hidden", hd.ds.length > 0);
}
/* Vẽ TỪNG DÒNG: chỉ thay dòng có nội dung đổi. Không vẽ lại cả danh sách – nếu không, ô "Chụp lại" của một dòng bị thay giữa lúc camera đang mở
   (tờ khác báo tiến trình) và ảnh chụp lại bị mất (sự kiện 'change' rơi vào phần tử đã bị gỡ). */
const daVe = new Map();                                                 // stt -> { html, el }
function veDanhSach() {
  const ol = $("#ds-to"), ds = hd.ds.filter((t) => !t.an), con = new Set(ds.map((t) => t.stt));
  for (const [stt, v] of daVe) if (!con.has(stt)) { v.el.remove(); daVe.delete(stt); }
  let truoc = null;
  for (const t of ds) {
    const html = dongTo(t), cu = daVe.get(t.stt);
    if (!cu || cu.html !== html) {
      const tmp = document.createElement("ol"); tmp.innerHTML = html;
      const el = tmp.firstElementChild;
      if (cu) cu.el.replaceWith(el); else if (truoc) truoc.after(el); else ol.prepend(el);
      daVe.set(t.stt, { html, el });
    }
    truoc = daVe.get(t.stt).el;
  }
}
$("#ds-to").addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-gui-lai]");
  if (b) hd.guiLai(Number(b.dataset.guiLai));
});
$("#ds-to").addEventListener("change", (ev) => {
  const i = ev.target.closest("[data-chup-lai]");
  if (!i || !i.files || !i.files[0]) return;
  hd.chupLai(Number(i.dataset.chupLai), i.files[0], { examId: st.exam.exam_id });
});

/* F4 – tải lại trang không làm mất danh sách tờ: siêu dữ liệu (số tờ, tên tệp, mã phiếu) lưu ở sessionStorage của TAB này, KHÔNG có ảnh, KHÔNG có token;
   sau đăng nhập hỏi lại trạng thái từng phiếu qua GET /sheets/{id}. Tờ chưa gửi xong thì ảnh đã mất (nằm trong bộ nhớ trang) → hiện "mất khi tải lại", phải chụp lại. */
const KHOA_PHIEN = "m_hang_doi";
let daKhoiPhucPhien = false;
function luuPhien() {
  if (!daKhoiPhucPhien || !st.me) return;                              // chưa khôi phục xong: KHÔNG ghi đè bản đã lưu bằng danh sách rỗng
  try { sessionStorage.setItem(KHOA_PHIEN, JSON.stringify({ nguoi: st.me.username, ds: hd.xuatSieuDuLieu() })); } catch (_) { /* bỏ qua */ }
}
async function traCuuPhieu(id, meta) {
  const p = await api(`/sheets/${id}`);
  const sc = p.score || {};
  return { sheet_id: p.sheet_id, da_ton_tai: !!meta.daTonTai, status: p.status, reject_code: p.reject_code, reject_message: p.reject_message,
    pending_questions: sc.pending_questions || 0, provisional_score: sc.provisional ?? null, official_score: sc.official ?? null, chiTiet: p };
}
async function khoiPhucPhien() {
  let p = null;
  try { p = JSON.parse(sessionStorage.getItem(KHOA_PHIEN) || "null"); } catch (_) { p = null; }
  if (p && p.nguoi !== st.me.username) { try { sessionStorage.removeItem(KHOA_PHIEN); } catch (_) { /* bỏ qua */ } p = null; }   // người khác đăng nhập: bỏ
  if (p && Array.isArray(p.ds) && p.ds.length && !hd.ds.length) {
    const kq = await hd.khoiPhuc(p.ds, traCuuPhieu);
    if (kq.mat) toast(`${kq.mat} tờ chưa gửi xong khi tải lại trang – ảnh không còn, hãy chụp lại.`);
    else toast(`Đã khôi phục danh sách ${kq.phucHoi} tờ.`);
  }
  daKhoiPhucPhien = true;
}

/* Hết phiên (401) giữa chừng: hàng đợi TẠM DỪNG, giữ nguyên các tờ; đăng nhập lại thì tiếp tục gửi. */
setInterval(() => {
  if (hd.tamDung && st.me) { st.me = null; manDangNhap("Phiên đăng nhập đã hết – đăng nhập lại để gửi tiếp các tờ đang chờ (ảnh vẫn giữ trên máy)."); }
}, 500);
window.addEventListener("beforeunload", (e) => { if (hd.dangBan() || hd.tong().loi) { e.preventDefault(); e.returnValue = ""; } });

/* ------------------------------------------------------------ đăng nhập */
function manDangNhap(thongBao) {
  $("#who").textContent = ""; $("#logout").classList.add("hidden");
  const er = $("#lg-err"); er.textContent = thongBao || ""; er.classList.toggle("hidden", !thongBao);
  const kt = $("#lg-kythi");
  kt.textContent = st.kyThiUrl ? `Đăng nhập để chụp phiếu cho kỳ thi mã ${st.kyThiUrl} (quét từ trang bìa).` : "";
  kt.classList.toggle("hidden", !st.kyThiUrl);
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
  if (hd.dangBan() && !confirm("Còn tờ đang gửi / đang chấm. Đăng xuất sẽ dừng gửi. Vẫn đăng xuất?")) return;
  try { await api("/auth/logout", { method: "POST" }); } catch (_) { /* bỏ qua */ }
  try { sessionStorage.removeItem(KHOA_PHIEN); } catch (_) { /* bỏ qua */ }
  KyThiDong.xoa();                                                       // V2: lựa chọn "Hiện cả kỳ thi đã đóng" không sang người sau
  st.me = null; manDangNhap("Đã đăng xuất.");
});

/* ------------------------------------------------------------ chọn kỳ thi */
async function manKyThi(thongBao) {
  st.exams = await api("/exams");
  const msg = $("#exam-msg"); msg.textContent = thongBao || ""; msg.classList.toggle("hidden", !thongBao);
  veDsKyThi();
  hien("v-exams");
}
/* V2: kỳ thi đã đóng (không nhận ảnh) ẩn mặc định – CHỈ lọc hiển thị (frontend/ky_thi_dong.js); QR trang bìa vẫn tra trong danh sách đầy đủ st.exams. */
function veDsKyThi() {
  const hienDong = KyThiDong.doc(), soDong = KyThiDong.soDong(st.exams), xem = KyThiDong.loc(st.exams, hienDong);
  const ds = $("#exam-list");
  ds.innerHTML = xem.length ? xem.map((e) => `<button type="button" class="exam" data-id="${e.exam_id}">
      <span class="sub">${esc(e.subject_name)} · ${esc(e.class_code || "không lớp")} · mã ${e.exam_id}</span><b>${esc(e.exam_title)}</b>
      <span class="sub">${e.so_phieu} phiếu${e.status === "closed" ? " · ĐÃ ĐÓNG" : ""}</span></button>`).join("")
    : st.exams.length ? `<p class="muted">Không có kỳ thi đang mở (${soDong} kỳ thi đã đóng – bật "Hiện cả kỳ thi đã đóng" để xem).</p>`
      : '<p class="muted">Bạn chưa có kỳ thi nào. Tạo kỳ thi trên máy tính trước.</p>';
  ds.querySelectorAll(".exam").forEach((b) => b.addEventListener("click", () => chonKyThi(Number(b.dataset.id))));
  $("#hien-dong").checked = hienDong;
  $("#so-dong").textContent = soDong ? `(${soDong})` : "";
  $("#hien-dong-wrap").classList.toggle("hidden", !soDong && !hienDong);
}
$("#hien-dong").addEventListener("change", (ev) => { KyThiDong.luu(ev.target.checked); veDsKyThi(); });
function chonKyThi(id) {
  const e = st.exams.find((x) => x.exam_id === id);
  if (!e) return;
  st.exam = e;
  try { sessionStorage.setItem("m_exam", String(id)); } catch (_) { /* bỏ qua */ }
  $("#cap-sub").textContent = `Kỳ thi mã ${e.exam_id} · ${e.subject_name} · ${e.class_code || "không lớp"}`;
  $("#cap-title").textContent = e.exam_title;
  $("#cap-dong").classList.toggle("hidden", e.status !== "closed");
  $("#lk-duyet").textContent = `${location.origin}/app/#/review`;
  veHangDoi();
  hien("v-cap");
}
$("#doi-ky-thi").addEventListener("click", () => {
  if (hd.dangBan()) { toast("Đang gửi các tờ của kỳ thi này – chờ gửi xong rồi mới đổi kỳ thi."); return; }
  manKyThi().catch((e) => { if (e.ma === 401) manDangNhap(e.message); else toast(e.message); });
});

/* ------------------------------------------------------------ khởi động */
async function khoiDong() {
  try { st.me = await api("/me"); }
  catch (e) { manDangNhap(e.ma === 401 ? "" : e.message); return; }
  $("#who").textContent = st.me.full_name; $("#logout").classList.remove("hidden");
  try { const t = sessionStorage.getItem("m_tong"); if (t) $("#tong-to").value = t; } catch (_) { /* bỏ qua */ }
  try {
    st.reasons = await api("/meta/reject-reasons");
    try { st.gioiHanMb = (await api("/meta/ket-noi")).gioi_han_anh_mb || st.gioiHanMb; } catch (_) { /* giữ mặc định */ }
    if (st.exam && hd.ds.length) { daKhoiPhucPhien = true; hien("v-cap"); hd.tiepTuc(); veHangDoi(); return; }     // đăng nhập lại giữa phiên: gửi tiếp
    await khoiPhucPhien();                                                              // tải lại trang: dựng lại danh sách tờ
    await manKyThi();
    if (st.kyThiUrl) {                                                                  // mở từ QR trang bìa: chọn sẵn kỳ thi nếu có quyền
      const kq = MKyThi.chonTuDanhSach(st.exams, st.kyThiUrl);
      boThamSoKyThi();
      if (kq.exam && !(hd.dangBan() && st.exam && st.exam.exam_id !== kq.exam.exam_id)) { chonKyThi(kq.exam.exam_id); return; }
      if (kq.loi) { await manKyThi(thongBaoLoi(404)); return; }                        // như 404 của API: không lộ tên / sự tồn tại kỳ thi
    }
    let id = null; try { id = Number(sessionStorage.getItem("m_exam")); } catch (_) { /* bỏ qua */ }
    if (id && st.exams.some((e) => e.exam_id === id)) chonKyThi(id);
  } catch (e) { if (e.ma === 401) manDangNhap(e.message); else toast(e.message); }
}
khoiDong();
