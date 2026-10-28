"""
thu_lenh_f.py - Thử bằng TRÌNH DUYỆT THẬT (Playwright) các việc của lệnh F (28/10/2026). CHỈ ROLLBACK: máy chủ trong tiến trình, MỘT kết nối không commit,
ảnh vào thư mục tạm, giáo viên + kỳ thi tạo trong giao dịch → KHÔNG ghi dòng nào vào CSDL thật (kể cả kỳ thi 1632 / 1633; không đụng kỳ thi nào khác).

  python tools/thu_lenh_f.py f4      # /m (Pixel 7): chụp 2 tờ chấm được + 1 tờ lỗi mạng → TẢI LẠI TRANG → danh sách còn (2 khôi phục + 1 "mất") → chụp lại → tải lại
  python tools/thu_lenh_f.py f23     # /app/ (máy tính): F3 ô chọn kỳ thi "(0 phiếu)" → "(1 phiếu)" sau khi tải; F2 phiếu trùng: cảnh báo ở Bảng điểm, hộp xác nhận, thay phiếu cũ

Ảnh màn hình: data/_eval/ui_m/f4/ (F4) và data/_eval/ui_f/ (F2, F3); số đo / kiểm: ket_qua.json cùng thư mục.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"

import thu_dien_thoai as T  # noqa: E402  (MayChuThu, dung_du_lieu_tam, GIA_12, tao_anh)

RAW = ROOT / "data" / "raw"
OUT_F4 = ROOT / "data" / "_eval" / "ui_m" / "f4"
OUT_F = ROOT / "data" / "_eval" / "ui_f"
SBD_0002 = "795125"


def f4() -> dict:
    from playwright.sync_api import sync_playwright
    if not all((T.GIA_12 / f"BV{i:02d}_v1.jpg").exists() for i in (1, 2, 3)):
        T.tao_anh()
    OUT_F4.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "thiet_bi": "Playwright Chromium, giả lập Pixel 7", "kiem": {}}
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        dl = T.dung_du_lieu_tam(mc.conn)
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
            pg = ctx.new_page()
            chup = lambda ten: (pg.wait_for_timeout(400), pg.screenshot(path=str(OUT_F4 / ten), full_page=True))   # noqa: E731
            cho_het = lambda: pg.wait_for_function("() => !window.__hangDoi.dangBan()", timeout=300000)            # noqa: E731
            dong = lambda: pg.evaluate("() => [...document.querySelectorAll('#ds-to .to')].map(e => ({stt: e.dataset.stt, cls: e.className, txt: e.innerText.replace(/\\s+/g,' ').trim().slice(0,140)}))")   # noqa: E731

            pg.goto(url + "/m")
            pg.wait_for_selector("#v-login:not(.hidden)")
            pg.fill("#lg-user", dl["username"]); pg.fill("#lg-pass", dl["mat_khau"]); pg.tap("#f-login button")
            pg.wait_for_selector(f".exam[data-id='{dl['exam_id']}']")
            pg.click(f".exam[data-id='{dl['exam_id']}']")
            pg.wait_for_selector("#v-cap:not(.hidden)")
            for i in (1, 2):
                pg.set_input_files("#cam", str(T.GIA_12 / f"BV{i:02d}_v1.jpg"))
            cho_het()
            # tờ 3: ngắt đường tải ảnh -> lỗi mạng (ảnh còn trong bộ nhớ trang, CHƯA tới máy chủ)
            pg.route("**/exams/*/sheets", lambda r: r.abort())
            pg.set_input_files("#cam", str(T.GIA_12 / "BV03_v1.jpg"))
            pg.wait_for_function("() => window.__hangDoi.ds.some(t => t.trangThai === 'loi')", timeout=30000)
            truoc = dong()
            chup("01_truoc_khi_tai_lai.png")
            ket["truoc_khi_tai_lai"] = truoc
            assert len(truoc) == 3 and "lỗi mạng" in truoc[0]["txt"] or any("lỗi mạng" in d["txt"] for d in truoc)
            pg.unroute("**/exams/*/sheets")

            # ---- TẢI LẠI TRANG ----
            pg.reload()
            pg.wait_for_selector("#v-cap:not(.hidden)", timeout=30000)
            pg.wait_for_selector("#ds-to .to", timeout=30000)
            pg.wait_for_function("() => document.querySelectorAll('#ds-to .to').length === 3", timeout=30000)
            sau = dong()
            chup("02_sau_khi_tai_lai.png")
            ket["sau_khi_tai_lai"] = sau
            ket["tong_ket_sau_tai_lai"] = pg.inner_text("#tk-so").replace("\n", " ")
            ket["ghi_chu_cho"] = pg.inner_text("#tk-cho")
            tim = lambda so: next(d for d in sau if f"Tờ {so}" in d["txt"])        # noqa: E731
            ket["kiem"]["hai_to_dau_duoc_khoi_phuc"] = all("khôi phục" in tim(i)["txt"] and ("cần xem" in tim(i)["txt"] or "đã chấm" in tim(i)["txt"]) for i in (1, 2))
            ket["kiem"]["to_3_bao_mat_phai_chup_lai"] = "mất khi tải lại" in tim(3)["txt"] and pg.query_selector("[data-chup-lai]") is not None
            ket["kiem"]["so_to_ke_tiep_dung"] = "Tờ 4" in pg.inner_text("#cam-txt")

            # ---- chụp lại tờ 3 (giữ số tờ) rồi tải lại lần nữa: cả 3 tờ đều còn ----
            pg.set_input_files("[data-chup-lai]", str(T.GIA_12 / "BV03_v2.jpg"))
            cho_het()
            chup("03_sau_khi_chup_lai_to_3.png")
            pg.reload()
            pg.wait_for_function("() => document.querySelectorAll('#ds-to .to').length >= 3", timeout=30000)
            cuoi = dong()
            chup("04_tai_lai_lan_hai.png")
            ket["sau_tai_lai_lan_hai"] = cuoi
            ket["kiem"]["khong_con_to_mat_chua_thay"] = pg.evaluate("() => window.__hangDoi.soMat()") == 0
            ket["kiem"]["sessionStorage_khong_co_anh_hay_token"] = pg.evaluate(
                "() => { const s = sessionStorage.getItem('m_hang_doi') || ''; return !/token|data:image|Authorization/i.test(s) && s.length < 4000; }")
            # đăng xuất: xoá siêu dữ liệu
            pg.click("#logout")
            pg.wait_for_selector("#v-login:not(.hidden)")
            ket["kiem"]["dang_xuat_xoa_sieu_du_lieu"] = pg.evaluate("() => sessionStorage.getItem('m_hang_doi') === null")
            b.close()
        so = mc.conn.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = %s", (dl["exam_id"],)).fetchone()["n"]
        ket["phieu_trong_giao_dich"] = so
    ket["dat"] = all(ket["kiem"].values())
    (OUT_F4 / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1), encoding="utf-8")
    return ket


def f23() -> dict:
    from playwright.sync_api import sync_playwright
    from backend import demo, service
    OUT_F.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}}
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        dl = T.dung_du_lieu_tam(mc.conn)                                  # giáo viên gv_thu_dt + kỳ thi gộp (không dùng ở đây)
        uid = mc.conn.execute("SELECT user_id FROM users WHERE username = %s", (dl["username"],)).fetchone()["user_id"]
        lop = mc.conn.execute("SELECT class_id FROM classes WHERE class_code = 'CNTT-K22A'").fetchone()["class_id"]
        mc.conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV thử trùng SBD') ON CONFLICT DO NOTHING", (SBD_0002,))
        eid = service.tao_ky_thi(mc.conn, {"exam_title": "Thử F2-F3 [THỬ TRÌNH DUYỆT]", "subject_code": "IT3080", "num_questions": 40, "max_score": 10,
                                           "pass_score": 5, "class_id": lop, "codes": [{"code": m, "answers": demo.khoa_demo(m, 40)} for m in ("101", "102", "103", "104")]}, uid)
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="vi-VN")
            pg = ctx.new_page()
            pg.on("dialog", lambda d: (ket.setdefault("hop_xac_nhan", []).append(d.message), d.accept()))
            chup = lambda ten: (pg.wait_for_timeout(500), pg.screenshot(path=str(OUT_F / ten), full_page=True))   # noqa: E731
            pg.goto(url + "/app/")
            pg.wait_for_selector("#lg-user")
            pg.fill("#lg-user", dl["username"]); pg.fill("#lg-pass", dl["mat_khau"]); pg.click("#f-login button")
            pg.wait_for_selector("#exam-select")
            pg.select_option("#exam-select", str(eid))
            pg.wait_for_function(f"() => document.querySelector('#exam-select').selectedOptions[0].value === '{eid}'")
            nhan = lambda: pg.evaluate("() => document.querySelector('#exam-select').selectedOptions[0].innerText")   # noqa: E731

            # ---- F3: nhãn ô chọn kỳ thi theo số phiếu thật ----
            ket["F3_truoc_khi_tai"] = nhan()
            pg.goto(url + "/app/#/upload")
            pg.wait_for_selector("#files", state="attached")
            chup("F3_01_truoc_khi_tai.png")
            pg.set_input_files("#files", str(RAW / "0002_C2.jpg"))
            pg.click("#go")
            pg.wait_for_function("() => /Xong/.test(document.querySelector('#st').textContent)", timeout=120000)
            pg.wait_for_timeout(600)
            ket["F3_sau_khi_tai"] = nhan()
            chup("F3_02_sau_khi_tai.png")
            ket["kiem"]["F3_nhan_tu_0_len_1_phieu"] = "(0 phiếu)" in ket["F3_truoc_khi_tai"] and "(1 phiếu)" in ket["F3_sau_khi_tai"]

            # ---- F2: phiếu A chính thức, phiếu B (chụp lại) trùng SBD bị giữ ----
            api = ctx.request

            def giai_quyet_het(sid):
                for c in api.get(f"{url}/sheets/{sid}/review-questions").json():
                    body = {"action": "set", "selected_options": c["omr_reading"] or ""} if "vi_tri" in c["reasons"] else {"action": "confirm"}
                    assert api.post(f"{url}/sheets/{sid}/questions/{c['question_no']}/review", data=body).ok
                return api.get(f"{url}/sheets/{sid}").json()

            a = int(mc.conn.execute("SELECT max(sheet_id) AS s FROM answer_sheets WHERE exam_id = %s", (eid,)).fetchone()["s"])
            va = giai_quyet_het(a)
            if va["status"] != "graded":
                va = api.put(f"{url}/sheets/{a}/identity", data={"sbd": SBD_0002}).json()
            ket["phieu_cu"] = {"sheet_id": a, "status": va["status"], "diem": va["score"]["official"]}
            pg.goto(url + "/app/#/upload"); pg.wait_for_selector("#files", state="attached")
            pg.set_input_files("#files", str(RAW / "0002_C3.jpg")); pg.click("#go")
            pg.wait_for_function("() => /Xong/.test(document.querySelector('#st').textContent)", timeout=120000)
            bsid = int(mc.conn.execute("SELECT max(sheet_id) AS s FROM answer_sheets WHERE exam_id = %s", (eid,)).fetchone()["s"])
            vb = giai_quyet_het(bsid)
            ket["phieu_moi"] = {"sheet_id": bsid, "status": vb["status"], "ly_do": vb["review"]["reasons"] if vb["review"] else None}
            ket["kiem"]["B_bi_giu_vi_trung_sbd"] = vb["status"] == "needs_review" and "duplicate_sbd" in vb["review"]["reasons"]

            pg.goto(url + "/app/#/results"); pg.wait_for_selector("text=Bảng điểm")
            pg.wait_for_selector("text=phiếu trùng chờ duyệt")
            chup("F2_01_bang_diem_canh_bao.png")
            ket["kiem"]["F2_bang_diem_co_canh_bao"] = pg.locator("text=Thí sinh có phiếu trùng SBD chờ duyệt: 1").count() == 1

            pg.goto(url + f"/app/#/review/{bsid}"); pg.wait_for_selector("#khung-trung")
            chup("F2_02_man_duyet_hai_lua_chon.png")
            ket["kiem"]["F2_man_duyet_co_hai_nut"] = pg.locator("#trung-bo").count() == 1 and pg.locator("#trung-thay").count() == 1
            pg.click("#trung-thay")                                           # hộp xác nhận tự chấp nhận (ghi nội dung vào ket["hop_xac_nhan"])
            pg.wait_for_function("() => /Đã thay phiếu/.test(document.querySelector('#toast').textContent)", timeout=60000)
            pg.wait_for_timeout(800)
            chup("F2_03_sau_khi_thay.png")
            n_chinh_thuc = mc.conn.execute("SELECT count(*) AS n FROM results r JOIN students s USING (student_id) WHERE r.exam_id = %s AND s.student_code = %s AND r.status <> 'void'",
                                           (eid, SBD_0002)).fetchone()["n"]
            nk = mc.conn.execute("SELECT l.changed_by, l.changed_at, l.reason, l.new_status::text AS n FROM score_audit_logs l JOIN results r USING (result_id) WHERE r.sheet_id = %s ORDER BY audit_id DESC",
                                 (a,)).fetchall()
            ket["nhat_ky_phieu_cu"] = [{"changed_by": x["changed_by"], "changed_at": str(x["changed_at"]), "new_status": x["n"], "reason": x["reason"]} for x in nk]
            ket["so_diem_chinh_thuc_cua_thi_sinh"] = n_chinh_thuc
            ket["kiem"]["F2_dung_mot_diem_chinh_thuc"] = n_chinh_thuc == 1
            ket["kiem"]["F2_nhat_ky_ghi_phieu_nao_thay_phieu_nao"] = any(f"#{a}" in (x["reason"] or "") and f"#{bsid}" in (x["reason"] or "") and x["n"] == "void" for x in nk)
            pg.goto(url + "/app/#/results"); pg.wait_for_selector("text=Bảng điểm"); pg.wait_for_timeout(600)
            chup("F2_04_bang_diem_sau_khi_thay.png")
            ket["kiem"]["F2_het_canh_bao_sau_khi_thay"] = pg.locator("text=phiếu trùng chờ duyệt").count() == 0
            b.close()
        ket["dong_da_ghi_vao_csdl_that"] = 0
    ket["dat"] = all(ket["kiem"].values())
    (OUT_F / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return ket


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("viec", choices=["f4", "f23"])
    kq = {"f4": f4, "f23": f23}[ap.parse_args().viec]()
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str)[:4000])
    sys.exit(0 if kq["dat"] else 1)
