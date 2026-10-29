/* Smart Exam – trang QUẢN TRỊ (#/admin), chỉ hiện cho vai trò admin (máy chủ vẫn kiểm: /admin/... trả 403 cho giáo viên).
   Dùng các hàm chung của app.js ($, main, api, post, patch, esc, toast). Mật khẩu KHÔNG bao giờ được vẽ ra trang hay lưu ở trình duyệt. */
"use strict";

const NHAN_TT_KY_THI = { closed: ["Đã đóng", "bad"], draft: ["Đang mở", "ok"], published: ["Đang mở", "ok"], grading: ["Đang mở", "ok"] };
const tagKyThi = (s) => { const [t, c] = NHAN_TT_KY_THI[s] || [s, "gray"]; return `<span class="tag ${c}">${esc(t)}</span>`; };

/* "101: ABCD…" mỗi dòng một mã đề -> [{code, answers}] (bỏ khoảng trắng; máy chủ kiểm độ dài + chữ cái như POST /exams). */
function docMaDe(txt) {
  return txt.split(/\r?\n/).map((d) => d.trim()).filter(Boolean).map((d) => {
    const m = d.match(/^(\d{1,6})\s*[:=\-]\s*([A-Za-z\s]+)$/);
    if (!m) throw new Error(`Dòng "${d}" không đúng dạng "101: ABCD…".`);
    return { code: m[1], answers: m[2].replace(/\s+/g, "").toUpperCase() };
  });
}

async function manQuanTri(tab) {
  if (!state.me || state.me.role !== "admin") { main.innerHTML = '<div class="alert bad">Chỉ quản trị viên dùng được trang này.</div>'; return; }
  const t = ["users", "classes"].includes(tab) ? tab : "exams";
  main.innerHTML = `<h2>Quản trị</h2><div class="row" style="margin:0 0 12px">
      <a class="btn ${t === "exams" ? "pri" : ""}" href="#/admin/exams">Quản lý kỳ thi</a>
      <a class="btn ${t === "classes" ? "pri" : ""}" href="#/admin/classes">Lớp học</a>
      <a class="btn ${t === "users" ? "pri" : ""}" href="#/admin/users">Tài khoản giáo viên</a></div><div id="qt"></div>`;
  if (t === "exams") await qtKyThi(); else if (t === "classes") await qtLop(); else await qtTaiKhoan();
}

/* ------------------------------------------------------------------ lớp học (lệnh I) – chỉ lớp + giáo viên của lớp, KHÔNG quản lý sinh viên */
async function qtLop() {
  const ds = await api("/admin/classes");
  const qt = $("#qt");
  qt.innerHTML = `<div class="card"><h3>Tạo lớp</h3><form id="f-qt-lop" class="formcol"><div class="row">
      <label>Mã lớp<input id="lop-ma" required minlength="2" maxlength="30" placeholder="CNTT-K23A"></label>
      <label>Tên lớp<input id="lop-ten" required maxlength="150" placeholder="Công nghệ thông tin K23 - Lớp A"></label>
      <label>Năm học<input id="lop-nam" maxlength="20" placeholder="2026-2027"></label></div>
      <button class="pri" type="submit">Tạo lớp</button></form></div>
    <div class="card" id="lop-khung"></div>
    <div class="card"><h3>Lớp (${ds.length})</h3><table><thead><tr><th>Mã lớp</th><th>Tên lớp</th><th>Năm học</th><th>Giáo viên</th>
      <th>Sinh viên</th><th>Kỳ thi</th><th>Trạng thái</th><th></th></tr></thead><tbody>
      ${ds.map((l) => `<tr><td>${esc(l.class_code)}</td><td>${esc(l.class_name)}</td><td>${esc(l.academic_year || "–")}</td>
        <td>${l.so_giao_vien} <span class="muted small">${esc(l.giao_vien || "")}</span></td><td>${l.so_sinh_vien}</td><td>${l.so_ky_thi}</td>
        <td>${l.is_active ? '<span class="tag ok">hoạt động</span>' : '<span class="tag bad">vô hiệu hoá</span>'}</td>
        <td class="nowrap"><button type="button" data-lop-gv="${l.class_id}">Giáo viên</button>
          <button type="button" data-lop-sua="${l.class_id}">Sửa</button>
          <button type="button" data-lop-hd="${l.class_id}" data-bat="${l.is_active ? "0" : "1"}" class="${l.is_active ? "bad" : ""}">${l.is_active ? "Vô hiệu hoá" : "Kích hoạt lại"}</button>
          ${l.so_ky_thi || l.so_sinh_vien ? "" : `<button type="button" class="bad" data-lop-xoa="${l.class_id}">Xoá</button>`}</td></tr>`).join("")
      || '<tr><td colspan="8" class="muted">Chưa có lớp.</td></tr>'}</tbody></table>
      <p class="muted small">Số sinh viên chỉ để xem (không quản lý sinh viên ở đây). Lớp đã gắn kỳ thi hoặc có sinh viên không xoá được – chỉ vô hiệu hoá.
        Lớp vô hiệu hoá không chọn được cho kỳ thi / gán giáo viên mới; giáo viên đã gán vẫn xem được kỳ thi cũ của lớp.</p></div>`;
  $("#lop-khung").classList.add("hidden");
  const tim = (id) => ds.find((l) => l.class_id === Number(id));
  $("#f-qt-lop").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const l = await post("/admin/classes", { class_code: $("#lop-ma").value.trim(), class_name: $("#lop-ten").value.trim(), academic_year: $("#lop-nam").value.trim() || null });
      toast(`Đã tạo lớp ${l.class_code}.`); await qtLop();
    } catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  qt.querySelectorAll("[data-lop-sua]").forEach((b) => b.addEventListener("click", () => qtSuaLop(tim(b.dataset.lopSua))));
  qt.querySelectorAll("[data-lop-hd]").forEach((b) => b.addEventListener("click", async () => {
    const bat = b.dataset.bat === "1", l = tim(b.dataset.lopHd);
    if (!bat && !confirm(`Vô hiệu hoá lớp ${l.class_code}? Lớp không chọn được cho kỳ thi / gán giáo viên mới (kích hoạt lại được).`)) return;
    try { await post(`/admin/classes/${l.class_id}/status`, { is_active: bat }); toast(bat ? "Đã kích hoạt lại lớp." : "Đã vô hiệu hoá lớp."); await qtLop(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
  qt.querySelectorAll("[data-lop-xoa]").forEach((b) => b.addEventListener("click", async () => {
    const l = tim(b.dataset.lopXoa);
    if (!confirm(`Xoá hẳn lớp ${l.class_code}? Giáo viên của lớp bị bỏ gán. Không hoàn tác được.`)) return;
    try { await api(`/admin/classes/${l.class_id}`, { method: "DELETE" }); toast("Đã xoá lớp."); await qtLop(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
  qt.querySelectorAll("[data-lop-gv]").forEach((b) => b.addEventListener("click", () => qtGiaoVienLop(tim(b.dataset.lopGv)).catch((e) => toast(e.message, true))));
}
function qtSuaLop(l) {
  const k = $("#lop-khung");
  k.classList.remove("hidden");
  k.innerHTML = `<h3>Sửa lớp ${esc(l.class_code)}</h3><form id="f-lop-sua" class="formcol">
      <label>Tên lớp<input id="ls-ten" value="${esc(l.class_name)}" required maxlength="150"></label>
      <label>Năm học (để trống = xoá)<input id="ls-nam" value="${esc(l.academic_year || "")}" maxlength="20"></label>
      <p class="muted small">Mã lớp không đổi được (kỳ thi và trang bìa đang dùng).</p>
      <div class="row"><button class="pri" type="submit">Lưu</button><button type="button" id="ls-huy">Huỷ</button></div></form>`;
  $("#ls-huy").addEventListener("click", () => { k.innerHTML = ""; k.classList.add("hidden"); });
  $("#f-lop-sua").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await patch(`/admin/classes/${l.class_id}`, { class_name: $("#ls-ten").value.trim(), academic_year: $("#ls-nam").value.trim() || null }); toast("Đã lưu."); await qtLop(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  k.scrollIntoView({ block: "nearest" });
}
async function qtGiaoVienLop(l) {
  const [ds, users] = await Promise.all([api(`/admin/classes/${l.class_id}/teachers`), api("/admin/users")]);
  const co = new Set(ds.map((u) => u.user_id));
  const chon = users.filter((u) => u.role === "teacher" && u.is_active && !co.has(u.user_id));
  const k = $("#lop-khung");
  k.classList.remove("hidden");
  k.innerHTML = `<h3>Giáo viên của lớp ${esc(l.class_code)} – ${esc(l.class_name)}</h3>
    <table><thead><tr><th>Tên đăng nhập</th><th>Họ tên</th><th>Trạng thái</th><th>Môn dạy</th><th></th></tr></thead><tbody>
    ${ds.map((u) => `<tr><td>${esc(u.username)}</td><td>${esc(u.full_name)}</td>
      <td>${u.is_active ? '<span class="tag ok">hoạt động</span>' : '<span class="tag bad">vô hiệu hoá</span>'}</td><td>${esc(u.subject_code || "–")}</td>
      <td><button type="button" data-bo-gv="${u.user_id}">Bỏ khỏi lớp</button></td></tr>`).join("") || '<tr><td colspan="5" class="muted">Lớp chưa có giáo viên.</td></tr>'}
    </tbody></table>
    ${l.is_active ? (chon.length ? `<form id="f-them-gv" class="row"><select id="them-gv">${chon.map((u) => `<option value="${u.user_id}">${esc(u.full_name)} (${esc(u.username)})</option>`).join("")}</select>
      <button class="pri" type="submit">Thêm vào lớp</button></form>` : '<p class="muted small">Không còn giáo viên đang hoạt động nào để thêm.</p>')
      : '<p class="muted small">Lớp đang bị vô hiệu hoá – kích hoạt lại trước khi thêm giáo viên.</p>'}
    <p class="muted small">Giáo viên của lớp thấy mọi kỳ thi gắn lớp này (cùng với kỳ thi mình phụ trách). Bỏ khỏi lớp: mất quyền ngay ở thao tác kế tiếp.
      "Môn dạy" không sửa trên web.</p>
    <button type="button" id="gvl-dong">Đóng</button>`;
  $("#gvl-dong").addEventListener("click", () => { k.innerHTML = ""; k.classList.add("hidden"); });
  const f = $("#f-them-gv");
  if (f) f.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await api(`/admin/classes/${l.class_id}/teachers/${$("#them-gv").value}`, { method: "PUT" }); toast("Đã thêm giáo viên vào lớp."); await qtLop(); await qtGiaoVienLop(l); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  k.querySelectorAll("[data-bo-gv]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Bỏ giáo viên này khỏi lớp? Họ mất quyền xem kỳ thi của lớp (trừ kỳ thi họ phụ trách).")) return;
    try { await api(`/admin/classes/${l.class_id}/teachers/${b.dataset.boGv}`, { method: "DELETE" }); toast("Đã bỏ khỏi lớp."); await qtLop(); await qtGiaoVienLop(l); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
  k.scrollIntoView({ block: "nearest" });
}
/* Ô tick lớp: lớp đang hoạt động tick tự do; lớp vô hiệu hoá chỉ hiện nếu đã gán (bỏ tick được, không tick mới được). */
function oTickLop(lops, daCo) {
  const hien = lops.filter((l) => l.is_active || daCo.has(l.class_id));
  return hien.length ? `<div class="tick-lop">${hien.map((l) => `<label class="small"><input type="checkbox" name="lop" value="${l.class_id}"
      ${daCo.has(l.class_id) ? "checked" : ""} ${!l.is_active && !daCo.has(l.class_id) ? "disabled" : ""}> ${esc(l.class_code)}${l.is_active ? "" : " (vô hiệu)"}</label>`).join(" ")}</div>`
    : '<p class="muted small">Chưa có lớp nào – tạo ở thẻ Lớp học.</p>';
}
const lopDaTick = (goc) => [...goc.querySelectorAll('input[name="lop"]:checked')].map((x) => Number(x.value));

/* ------------------------------------------------------------------ kỳ thi */
async function qtKyThi() {
  const [ds, users] = await Promise.all([api("/admin/exams"), api("/admin/users")]);
  const gv = users.filter((u) => u.role === "teacher" && u.is_active);
  const qt = $("#qt");
  qt.innerHTML = `<div class="card"><h3>Tạo kỳ thi</h3><form id="f-qt-tao" class="formcol">
      <label>Tên kỳ thi<input id="qt-ten" required minlength="3" maxlength="200"></label>
      <div class="row"><label>Mã môn<input id="qt-mon" required maxlength="20" placeholder="IT3080"></label>
        <label>Tên môn<input id="qt-ten-mon" maxlength="150" placeholder="Cơ sở dữ liệu"></label>
        <label>Ngày thi<input id="qt-ngay" type="date"></label></div>
      <div class="row"><label>Số câu<input id="qt-so-cau" type="number" min="1" max="40" value="40" required></label>
        <label>Mã lớp (tuỳ chọn)<input id="qt-lop" maxlength="30" placeholder="CNTT-K22A"></label>
        <label>Giáo viên phụ trách<select id="qt-gv"><option value="">(chính tôi – admin)</option>
          ${gv.map((u) => `<option value="${u.user_id}">${esc(u.full_name)} (${esc(u.username)})</option>`).join("")}</select></label></div>
      <label>Đáp án theo mã đề – mỗi dòng một mã đề, dạng <code>101: ABCD…</code> (đủ số câu)
        <textarea id="qt-dap-an" rows="4" required placeholder="101: ABCDABCDAB…&#10;102: BCDABCDABC…"></textarea></label>
      <button class="pri" type="submit">Tạo kỳ thi</button></form></div>
    <div class="card" id="qt-sua-khung"></div>
    <div class="card"><h3>Mọi kỳ thi (${ds.length})</h3><table><thead><tr><th>#</th><th>Kỳ thi</th><th>Ngày</th><th>Môn · lớp</th><th>Mã đề</th>
      <th>Giáo viên phụ trách</th><th>Trạng thái</th><th>Phiếu</th><th></th></tr></thead><tbody>
      ${ds.map((e) => `<tr data-id="${e.exam_id}"><td>${e.exam_id}</td><td>${esc(e.exam_title)}</td><td>${esc(e.exam_date || "–")}</td>
        <td>${esc(e.subject_code)} · ${esc(e.class_code || "không lớp")}</td><td>${esc(e.ma_de || "–")}</td>
        <td>${esc(e.teacher_name)} <span class="muted small">(${esc(e.teacher_username)})</span></td><td>${tagKyThi(e.status)}</td><td>${e.so_phieu}</td>
        <td class="nowrap"><a class="btn" href="/exams/${e.exam_id}/cover.pdf" target="_blank" rel="noopener">Trang bìa</a>
          <button type="button" data-sua="${e.exam_id}">Sửa</button>
          <button type="button" data-dong="${e.exam_id}" data-closed="${e.status === "closed" ? "0" : "1"}">${e.status === "closed" ? "Mở lại" : "Đóng"}</button>
          ${e.so_phieu || /\[DEMO/i.test(e.exam_title) ? "" : `<button type="button" class="bad" data-xoa="${e.exam_id}">Xoá</button>`}</td></tr>`).join("")
      || '<tr><td colspan="9" class="muted">Chưa có kỳ thi.</td></tr>'}</tbody></table>
      <p class="muted small">Kỳ thi đã có phiếu, đã có danh sách dự thi hoặc là kỳ thi [DEMO…] không xoá được – chỉ đóng (đóng = không nhận ảnh mới; duyệt và bảng điểm vẫn dùng được).</p></div>`;
  $("#qt-sua-khung").classList.add("hidden");
  $("#f-qt-tao").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const lop = $("#qt-lop").value.trim(), gvId = $("#qt-gv").value;
      const e = await post("/admin/exams", { exam_title: $("#qt-ten").value.trim(), subject_code: $("#qt-mon").value.trim(),
        subject_name: $("#qt-ten-mon").value.trim() || null, exam_date: $("#qt-ngay").value || null, num_questions: Number($("#qt-so-cau").value),
        class_code: lop || null, teacher_user_id: gvId ? Number(gvId) : null, codes: docMaDe($("#qt-dap-an").value) });
      toast(`Đã tạo kỳ thi #${e.exam_id}.`); await qtKyThi(); await napKyThi();
    } catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  qt.querySelectorAll("[data-sua]").forEach((b) => b.addEventListener("click", () => qtSuaKyThi(ds.find((e) => e.exam_id === Number(b.dataset.sua)))));
  qt.querySelectorAll("[data-dong]").forEach((b) => b.addEventListener("click", async () => {
    const dong = b.dataset.closed === "1";
    if (dong && !confirm(`Đóng kỳ thi #${b.dataset.dong}? Sau khi đóng không tải thêm ảnh được (mở lại được).`)) return;
    try { await post(`/admin/exams/${b.dataset.dong}/status`, { closed: dong }); toast(dong ? "Đã đóng kỳ thi." : "Đã mở lại kỳ thi."); await qtKyThi(); await napKyThi(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
  qt.querySelectorAll("[data-xoa]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm(`Xoá hẳn kỳ thi #${b.dataset.xoa} (chưa có phiếu)? Không hoàn tác được.`)) return;
    try { await api(`/admin/exams/${b.dataset.xoa}`, { method: "DELETE" }); toast("Đã xoá kỳ thi."); await qtKyThi(); await napKyThi(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
}
function qtSuaKyThi(e) {
  const k = $("#qt-sua-khung");
  k.classList.remove("hidden");
  k.innerHTML = `<h3>Sửa kỳ thi #${e.exam_id}</h3><form id="f-qt-sua" class="formcol">
      <label>Tên kỳ thi<input id="qs-ten" value="${esc(e.exam_title)}" required minlength="3" maxlength="200"></label>
      <label>Ngày thi (để trống = xoá ngày)<input id="qs-ngay" type="date" value="${esc(e.exam_date || "")}"></label>
      <div class="row"><button class="pri" type="submit">Lưu</button><button type="button" id="qs-huy">Huỷ</button></div></form>`;
  $("#qs-huy").addEventListener("click", () => k.classList.add("hidden"));
  $("#f-qt-sua").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await patch(`/admin/exams/${e.exam_id}`, { exam_title: $("#qs-ten").value.trim(), exam_date: $("#qs-ngay").value || null }); toast("Đã lưu."); await qtKyThi(); await napKyThi(); }
    catch (er) { if (!er.dangNhap) toast(er.message, true); }
  });
  k.scrollIntoView({ block: "nearest" });
}

/* ------------------------------------------------------------------ tài khoản giáo viên */
function matKhauNgauNhien() {
  const bang = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789", so = new Uint32Array(14);
  crypto.getRandomValues(so);
  return [...so].map((x) => bang[x % bang.length]).join("");
}
async function qtTaiKhoan() {
  const [ds, lops] = await Promise.all([api("/admin/users"), api("/admin/classes")]);
  const qt = $("#qt");
  qt.innerHTML = `<div class="card"><h3>Tạo tài khoản giáo viên</h3><form id="f-qt-tk" class="formcol" autocomplete="off">
      <div class="row"><label>Tên đăng nhập<input id="tk-user" required minlength="3" maxlength="50" pattern="[A-Za-z0-9._\\-]+" autocomplete="off"></label>
        <label>Họ tên<input id="tk-ten" required maxlength="150"></label><label>Email (tuỳ chọn)<input id="tk-mail" maxlength="255"></label></div>
      <div class="row"><label>Mật khẩu ban đầu (≥ 8 ký tự)<input id="tk-mk" type="password" required minlength="8" autocomplete="new-password"></label>
        <button type="button" id="tk-sinh">Sinh ngẫu nhiên</button><label class="small"><input type="checkbox" id="tk-hien"> hiện</label></div>
      <div id="tk-lop"><span class="small">Lớp (tuỳ chọn, tick nhiều lớp):</span> ${oTickLop(lops, new Set())}</div>
      <p class="muted small">Đưa mật khẩu ban đầu cho giáo viên qua kênh riêng; giáo viên đổi ngay ở trang Hồ sơ. Hệ thống không lưu / không hiện lại mật khẩu.</p>
      <button class="pri" type="submit">Tạo tài khoản</button></form></div>
    <div class="card" id="tk-khung"></div>
    <div class="card"><h3>Tài khoản (${ds.length})</h3><table><thead><tr><th>Tên đăng nhập</th><th>Họ tên</th><th>Vai trò</th><th>Trạng thái</th>
      <th>Lớp</th><th>Kỳ thi phụ trách</th><th>Đăng nhập gần nhất</th><th></th></tr></thead><tbody>
      ${ds.map((u) => `<tr><td>${esc(u.username)}</td><td>${esc(u.full_name)}</td><td>${esc(NHAN_VAI_TRO[u.role] || u.role)}</td>
        <td>${u.is_active ? '<span class="tag ok">hoạt động</span>' : '<span class="tag bad">vô hiệu hoá</span>'}</td><td>${esc(u.lop || "–")}</td><td>${u.so_ky_thi}</td>
        <td class="small">${u.last_login_at ? esc(new Date(u.last_login_at).toLocaleString("vi-VN")) : "chưa"}</td>
        <td class="nowrap">${u.role === "teacher" ? `<button type="button" data-lop-tk="${u.user_id}">Lớp</button>
          <button type="button" data-kt="${u.user_id}">Kỳ thi</button>
          <button type="button" data-mk="${u.user_id}">Đặt lại mật khẩu</button>
          <button type="button" data-hd="${u.user_id}" data-bat="${u.is_active ? "0" : "1"}" class="${u.is_active ? "bad" : ""}">${u.is_active ? "Vô hiệu hoá" : "Kích hoạt lại"}</button>`
          : '<span class="muted small">quản lý bằng backend.tai_khoan</span>'}</td></tr>`).join("")}
      </tbody></table></div>`;
  $("#tk-khung").classList.add("hidden");
  $("#tk-sinh").addEventListener("click", () => { $("#tk-mk").value = matKhauNgauNhien(); $("#tk-mk").type = "text"; $("#tk-hien").checked = true; });
  $("#tk-hien").addEventListener("change", (e) => { $("#tk-mk").type = e.target.checked ? "text" : "password"; });
  $("#f-qt-tk").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const u = await post("/admin/users", { username: $("#tk-user").value.trim(), full_name: $("#tk-ten").value.trim(),
        email: $("#tk-mail").value.trim() || null, password: $("#tk-mk").value, class_ids: lopDaTick($("#tk-lop")) });
      $("#tk-mk").value = ""; toast(`Đã tạo tài khoản ${u.username}.`); await qtTaiKhoan();
    } catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  const tim = (id) => ds.find((u) => u.user_id === Number(id));
  qt.querySelectorAll("[data-hd]").forEach((b) => b.addEventListener("click", async () => {
    const bat = b.dataset.bat === "1", u = tim(b.dataset.hd);
    if (!bat && !confirm(`Vô hiệu hoá ${u.username}? Tài khoản không đăng nhập được nữa và phiên đang mở bị đăng xuất ngay.`)) return;
    try { await post(`/admin/users/${u.user_id}/active`, { is_active: bat }); toast(bat ? "Đã kích hoạt lại." : "Đã vô hiệu hoá."); await qtTaiKhoan(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
  qt.querySelectorAll("[data-mk]").forEach((b) => b.addEventListener("click", () => qtDatLaiMatKhau(tim(b.dataset.mk))));
  qt.querySelectorAll("[data-kt]").forEach((b) => b.addEventListener("click", () => qtKyThiCuaGv(tim(b.dataset.kt)).catch((e) => toast(e.message, true))));
  qt.querySelectorAll("[data-lop-tk]").forEach((b) => b.addEventListener("click", () => qtLopCuaGv(tim(b.dataset.lopTk), lops).catch((e) => toast(e.message, true))));
}
async function qtLopCuaGv(u, lops) {
  const ds = await api(`/admin/users/${u.user_id}/classes`);
  const k = $("#tk-khung");
  k.classList.remove("hidden");
  k.innerHTML = `<h3>Lớp của ${esc(u.full_name)} (${esc(u.username)})</h3><form id="f-lop-gv" class="formcol">
      ${oTickLop(lops, new Set(ds.map((l) => l.class_id)))}
      <p class="muted small">Tick / bỏ tick rồi Lưu. Bỏ tick: giáo viên mất quyền xem kỳ thi của lớp đó ngay ở thao tác kế tiếp (trừ kỳ thi họ phụ trách).</p>
      <div class="row"><button class="pri" type="submit">Lưu</button><button type="button" id="lgv-huy">Huỷ</button></div></form>`;
  $("#lgv-huy").addEventListener("click", () => { k.innerHTML = ""; k.classList.add("hidden"); });
  $("#f-lop-gv").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await put(`/admin/users/${u.user_id}/classes`, { class_ids: lopDaTick($("#f-lop-gv")) }); toast("Đã lưu lớp."); await qtTaiKhoan(); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  k.scrollIntoView({ block: "nearest" });
}
function qtDatLaiMatKhau(u) {
  const k = $("#tk-khung");
  k.classList.remove("hidden");
  k.innerHTML = `<h3>Đặt lại mật khẩu – ${esc(u.username)}</h3><form id="f-tk-mk" class="formcol" autocomplete="off">
      <div class="row"><label>Mật khẩu mới (≥ 8 ký tự)<input id="tkm-mk" type="password" required minlength="8" autocomplete="new-password"></label>
        <button type="button" id="tkm-sinh">Sinh ngẫu nhiên</button></div>
      <p class="muted small">Mọi phiên đang mở của ${esc(u.username)} sẽ bị đăng xuất.</p>
      <div class="row"><button class="pri" type="submit">Đặt lại</button><button type="button" id="tkm-huy">Huỷ</button></div></form>`;
  $("#tkm-sinh").addEventListener("click", () => { $("#tkm-mk").value = matKhauNgauNhien(); $("#tkm-mk").type = "text"; });
  $("#tkm-huy").addEventListener("click", () => { k.innerHTML = ""; k.classList.add("hidden"); });
  $("#f-tk-mk").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await post(`/admin/users/${u.user_id}/password`, { new_password: $("#tkm-mk").value }); k.innerHTML = ""; k.classList.add("hidden"); toast(`Đã đặt lại mật khẩu cho ${u.username}.`); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  k.scrollIntoView({ block: "nearest" });
}
async function qtKyThiCuaGv(u) {
  const [ds, tatCa] = await Promise.all([api(`/admin/users/${u.user_id}/exams`), api("/admin/exams")]);
  const daCo = new Set(ds.filter((e) => e.nguon === "phu_trach").map((e) => e.exam_id));
  const k = $("#tk-khung");
  k.classList.remove("hidden");
  k.innerHTML = `<h3>Kỳ thi của ${esc(u.full_name)} (${esc(u.username)})</h3>
    <table><thead><tr><th>#</th><th>Kỳ thi</th><th>Lớp</th><th>Trạng thái</th><th>Vì sao thấy</th><th></th></tr></thead><tbody>
    ${ds.map((e) => `<tr><td>${e.exam_id}</td><td>${esc(e.exam_title)}</td><td>${esc(e.class_code || "–")}</td><td>${tagKyThi(e.status)}</td>
      <td>${e.nguon === "phu_trach" ? "được gán phụ trách" : "dạy lớp của kỳ thi"}</td>
      <td>${e.nguon === "phu_trach" ? `<button type="button" data-bo="${e.exam_id}">Bỏ gán</button>` : ""}</td></tr>`).join("")
      || '<tr><td colspan="6" class="muted">Chưa có kỳ thi nào.</td></tr>'}</tbody></table>
    ${u.is_active ? `<form id="f-gan" class="row"><select id="gan-kt">${tatCa.filter((e) => !daCo.has(e.exam_id)).map((e) =>
      `<option value="${e.exam_id}">#${e.exam_id} ${esc(e.exam_title)} (đang: ${esc(e.teacher_username)})</option>`).join("")}</select>
      <button class="pri" type="submit">Gán phụ trách</button></form>
      <p class="muted small">Mỗi kỳ thi có MỘT giáo viên phụ trách: gán cho người này thì người cũ thôi phụ trách (họ vẫn thấy nếu dạy lớp của kỳ thi). Bỏ gán: quyền phụ trách về admin.</p>`
      : '<p class="muted small">Tài khoản đang bị vô hiệu hoá – kích hoạt lại trước khi gán kỳ thi.</p>'}
    <button type="button" id="gan-dong">Đóng</button>`;
  $("#gan-dong").addEventListener("click", () => { k.innerHTML = ""; k.classList.add("hidden"); });
  const f = $("#f-gan");
  if (f) f.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await api(`/admin/users/${u.user_id}/exams/${$("#gan-kt").value}`, { method: "PUT" }); toast("Đã gán."); await qtKyThiCuaGv(u); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  });
  k.querySelectorAll("[data-bo]").forEach((b) => b.addEventListener("click", async () => {
    try { await api(`/admin/users/${u.user_id}/exams/${b.dataset.bo}`, { method: "DELETE" }); toast("Đã bỏ gán."); await qtKyThiCuaGv(u); }
    catch (e) { if (!e.dangNhap) toast(e.message, true); }
  }));
  k.scrollIntoView({ block: "nearest" });
}
