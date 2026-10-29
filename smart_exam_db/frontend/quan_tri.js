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
  const t = tab === "users" ? "users" : "exams";
  main.innerHTML = `<h2>Quản trị</h2><div class="row" style="margin:0 0 12px">
      <a class="btn ${t === "exams" ? "pri" : ""}" href="#/admin/exams">Quản lý kỳ thi</a>
      <a class="btn ${t === "users" ? "pri" : ""}" href="#/admin/users">Tài khoản giáo viên</a></div><div id="qt"></div>`;
  if (t === "exams") await qtKyThi(); else await qtTaiKhoan();
}

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
        <td class="nowrap"><button type="button" data-sua="${e.exam_id}">Sửa</button>
          <button type="button" data-dong="${e.exam_id}" data-closed="${e.status === "closed" ? "0" : "1"}">${e.status === "closed" ? "Mở lại" : "Đóng"}</button>
          ${e.so_phieu ? "" : `<button type="button" class="bad" data-xoa="${e.exam_id}">Xoá</button>`}</td></tr>`).join("")
      || '<tr><td colspan="9" class="muted">Chưa có kỳ thi.</td></tr>'}</tbody></table>
      <p class="muted small">Kỳ thi đã có phiếu không xoá được – chỉ đóng (đóng = không nhận ảnh mới; duyệt và bảng điểm vẫn dùng được).</p></div>`;
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

/* ------------------------------------------------------------------ tài khoản (chỉ xem ở Việc 1; thao tác thêm ở Việc 2) */
async function qtTaiKhoan() {
  const ds = await api("/admin/users");
  $("#qt").innerHTML = `<div class="card"><h3>Tài khoản (${ds.length})</h3><table><thead><tr><th>Tên đăng nhập</th><th>Họ tên</th><th>Vai trò</th>
      <th>Trạng thái</th><th>Lớp</th><th>Kỳ thi phụ trách</th></tr></thead><tbody>
      ${ds.map((u) => `<tr><td>${esc(u.username)}</td><td>${esc(u.full_name)}</td><td>${esc(NHAN_VAI_TRO[u.role] || u.role)}</td>
        <td>${u.is_active ? '<span class="tag ok">hoạt động</span>' : '<span class="tag bad">vô hiệu hoá</span>'}</td><td>${esc(u.lop || "–")}</td><td>${u.so_ky_thi}</td></tr>`).join("")}
      </tbody></table></div>`;
}
