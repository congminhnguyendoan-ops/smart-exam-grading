"""
thu_lenh_j.py - Thử bằng TRÌNH DUYỆT THẬT (Playwright Chromium) lệnh J (30/10/2026): trang đích sau đăng xuất / đăng nhập lại + xoá dữ liệu phiên trước.
CHỈ ROLLBACK (tools/thu_dien_thoai.MayChuThu: máy chủ trong tiến trình, MỘT kết nối không commit) -> KHÔNG ghi dòng nào vào CSDL thật.
Dùng đúng tài khoản thật `admin` và `gv_an`: mật khẩu của hai tài khoản chỉ được đặt tạm TRONG giao dịch sẽ ROLLBACK (mật khẩu thật không đổi).

  python tools/thu_lenh_j.py

(a) admin ở #/admin/exams -> Đăng xuất -> đăng nhập gv_an: rơi vào Tải ảnh (#/upload), không có thông báo đỏ.
(b) sau đăng xuất: DOM không còn tên kỳ thi / tên người của phiên trước; khoá lưu trữ của ứng dụng đã xoá, hash = #/.
(c) gv_an gõ trực tiếp #/admin (cả đổi hash lẫn mở trang mới): vẫn thấy thông báo từ chối + nút "Về trang chính" (bấm -> Tải ảnh).
(d) đăng nhập lại đúng admin: vào được trang Quản trị.
(e) phiên hết hạn, đăng nhập lại ĐÚNG người: quay lại đúng trang (#/admin/classes, #/sheet/<id>).
(f) phiên hết hạn, người KHÁC đăng nhập ở #/sheet/<phiếu không thuộc quyền mình>: về trang mặc định, không thông báo lỗi.
Ảnh + ket_qua.json: data/_eval/ui_j/.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"

import thu_dien_thoai as T  # noqa: E402  (MayChuThu)

OUT = ROOT / "data" / "_eval" / "ui_j"
MK = "Thu-Lenh-J-2026"
TEN_KT_RIENG = "[THU-J] Kỳ thi riêng quản trị – không lớp"


def _dang_nhap(pg, user):
    pg.wait_for_selector("#f-login")
    pg.fill("#lg-user", user); pg.fill("#lg-pass", MK); pg.click("#f-login button")
    pg.wait_for_selector("#userbox:not(.hidden)")


def _cho_trang(pg, hash_, chu_h2):
    pg.wait_for_function("([h, t]) => location.hash === h && (document.querySelector('#main h2') || {}).textContent?.includes(t)",
                         arg=[hash_, chu_h2], timeout=30000)


def _dang_xuat(pg):
    pg.click("#logout")
    pg.wait_for_selector("#f-login")
    pg.wait_for_function("() => document.querySelector('#main').textContent.includes('Đã đăng xuất')")


def _con_trong_dom(pg, chuoi):
    """Các chuỗi còn nằm trong DOM (kể cả phần tử ẩn, thuộc tính title của option)."""
    html = pg.evaluate("() => document.body.innerHTML")
    return [s for s in chuoi if s and s in html]


def chay() -> dict:
    from playwright.sync_api import sync_playwright
    from backend import auth, demo, service
    OUT.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}, "ghi_chu": {}}
    k, g = ket["kiem"], ket["ghi_chu"]
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        c = mc.conn
        n = c.execute("UPDATE users SET password_hash = %s WHERE username IN ('admin', 'gv_an')", (auth.bam_mat_khau(MK),)).rowcount
        if n != 2:
            raise SystemExit("Thiếu tài khoản admin / gv_an.")
        ten = {r["username"]: r["full_name"] for r in c.execute("SELECT username, full_name FROM users WHERE username IN ('admin', 'gv_an')").fetchall()}
        id_admin = c.execute("SELECT user_id FROM users WHERE username = 'admin'").fetchone()["user_id"]
        eid_rieng = service.tao_ky_thi(c, {"exam_title": TEN_KT_RIENG, "subject_code": "IT3080", "num_questions": 10, "max_score": 10, "pass_score": 5,
                                           "class_id": None, "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}]}, id_admin)
        # phiếu gv_an KHÔNG có quyền xem: kỳ thi không do gv_an phụ trách và không thuộc lớp gv_an dạy (cùng quy tắc backend/phan_quyen.py)
        # (CSDL thật hiện chỉ có phiếu thuộc quyền gv_an -> nếu không có, tạo MỘT phiếu bị từ chối trong kỳ thi riêng của admin, cũng trong giao dịch ROLLBACK)
        r = c.execute("SELECT max(a.sheet_id) AS s FROM answer_sheets a JOIN exams e USING (exam_id), users u WHERE u.username = 'gv_an' "
                      "AND e.created_by <> u.user_id AND (e.class_id IS NULL OR e.class_id NOT IN (SELECT class_id FROM teacher_classes WHERE user_id = u.user_id))").fetchone()
        phieu_la = r["s"] or c.execute("INSERT INTO answer_sheets (exam_id, image_path, status, reject_code, original_filename, uploaded_by) "
                                       "VALUES (%s, 'thu_lenh_j/khong_co_anh.jpg', 'rejected', 'anh_mo', 'thu_lenh_j.jpg', %s) RETURNING sheet_id",
                                       (eid_rieng, id_admin)).fetchone()["sheet_id"]
        g["phieu_ngoai_quyen_gv_an"] = phieu_la
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="vi-VN")
            pg = ctx.new_page()
            pg.on("dialog", lambda d: d.accept())
            # ---------------- (d0) admin mở /app/ lần đầu, đăng nhập: trang mặc định = Quản trị
            pg.goto(url + "/app/")
            _dang_nhap(pg, "admin")
            _cho_trang(pg, "#/admin", "Quản trị")
            k["d0_admin_dang_nhap_vao_quan_tri"] = pg.locator("#main .alert.bad").count() == 0
            # admin chọn kỳ thi riêng (localStorage examId), lọc danh sách phiếu (sessionStorage loc) -> có dữ liệu phiên để xoá
            # (mỗi thao tác vẽ lại trang: chờ phản hồi API của nó xong rồi mới đổi trang, tránh lượt vẽ cũ đè lên trang mới)
            pg.goto(url + "/app/#/sheets"); pg.wait_for_selector("#loc")
            with pg.expect_response(lambda r: f"/exams/{eid_rieng}/sheets" in r.url):
                pg.select_option("#exam-select", str(eid_rieng))
            pg.wait_for_function("(t) => document.querySelector('#exam-name').textContent === t", arg=TEN_KT_RIENG)
            with pg.expect_response(lambda r: "status=needs_review" in r.url):
                pg.select_option("#loc", "needs_review")
            pg.wait_for_function("() => sessionStorage.getItem('loc') === 'needs_review'")
            pg.wait_for_timeout(300)
            ten_kt_admin = pg.evaluate("() => [...document.querySelectorAll('#exam-select option')].map((o) => o.textContent.split(' · ')[0])")
            g["so_ky_thi_admin_thay"] = len(ten_kt_admin)
            pg.goto(url + "/app/#/admin/exams"); pg.wait_for_selector("#f-qt-tao")
            pg.screenshot(path=str(OUT / "01_admin_truoc_dang_xuat.png"), full_page=True)
            # ---------------- (b) đăng xuất
            _dang_xuat(pg)
            con = _con_trong_dom(pg, [ten["admin"], TEN_KT_RIENG] + ten_kt_admin)
            luu = pg.evaluate("() => ({ examId: localStorage.getItem('examId'), loc: sessionStorage.getItem('loc'), hash: location.hash })")
            g["sau_dang_xuat"] = {"con_trong_dom": con, **luu}
            k["b_dom_khong_con_ten_nguoi_ky_thi_truoc"] = not con
            k["b_khoa_luu_tru_ung_dung_da_xoa"] = luu["examId"] is None and luu["loc"] is None
            k["b_hash_ve_goc"] = luu["hash"] in ("#/", "")
            pg.screenshot(path=str(OUT / "02_sau_dang_xuat.png"), full_page=True)
            # ---------------- (a) đăng nhập gv_an
            _dang_nhap(pg, "gv_an")
            _cho_trang(pg, "#/upload", "Tải ảnh")
            k["a_gv_an_roi_vao_tai_anh"] = True
            k["a_khong_thong_bao_do"] = pg.locator("#main .alert.bad").count() == 0
            con = _con_trong_dom(pg, [ten["admin"], TEN_KT_RIENG])
            g["gv_an_sau_dang_nhap_con_trong_dom"] = con
            k["a_khong_thay_ky_thi_rieng_admin"] = not con and pg.input_value("#exam-select") != str(eid_rieng)
            pg.screenshot(path=str(OUT / "03_gv_an_sau_dang_nhap.png"), full_page=True)
            # ---------------- (c) gv_an gõ trực tiếp #/admin
            pg.evaluate("() => { location.hash = '#/admin'; }")
            pg.wait_for_selector("#ve-trang-chinh")
            k["c_doi_hash_thay_tu_choi"] = "Chỉ quản trị viên dùng được trang này" in pg.inner_text("#main .alert.bad")
            k["c_nut_ve_trang_chinh"] = pg.inner_text("#ve-trang-chinh").strip() == "Về trang chính" and pg.get_attribute("#ve-trang-chinh", "href") == "#/upload"
            pg.screenshot(path=str(OUT / "04_gv_an_go_admin.png"), full_page=True)
            pg.click("#ve-trang-chinh")
            _cho_trang(pg, "#/upload", "Tải ảnh")
            k["c_bam_nut_ve_tai_anh"] = True
            pg.goto(url + "/app/#/admin/users")                                 # mở hẳn trang mới với đường dẫn admin (đã có phiên)
            pg.wait_for_selector("#ve-trang-chinh")
            k["c_mo_trang_moi_thay_tu_choi"] = "Chỉ quản trị viên dùng được trang này" in pg.inner_text("#main .alert.bad") and "#/admin/users" in pg.url
            pg.screenshot(path=str(OUT / "05_gv_an_mo_trang_admin.png"), full_page=True)
            if phieu_la:                                                        # tiền điều kiện của (f): máy chủ thật sự từ chối gv_an
                k["f0_gv_an_get_phieu_la_404"] = pg.evaluate(f"() => fetch('/sheets/{phieu_la}').then((r) => r.status)") == 404
            # ---------------- (d) gv_an đăng xuất -> admin đăng nhập lại: vào Quản trị
            pg.goto(url + "/app/#/sheets"); pg.wait_for_selector("#loc")
            _dang_xuat(pg)
            k["d_dom_khong_con_ten_gv_an"] = not _con_trong_dom(pg, [ten["gv_an"]])
            _dang_nhap(pg, "admin")
            _cho_trang(pg, "#/admin", "Quản trị")
            pg.wait_for_selector("#f-qt-tao")
            k["d_admin_vao_duoc_quan_tri"] = pg.locator("#main .alert.bad").count() == 0
            pg.screenshot(path=str(OUT / "06_admin_dang_nhap_lai.png"), full_page=True)
            # ---------------- (e) phiên hết hạn, đăng nhập lại ĐÚNG người: quay lại đúng chỗ
            pg.goto(url + "/app/#/admin/classes"); pg.wait_for_selector("#f-qt-lop")
            ctx.clear_cookies()                                                 # mô phỏng phiên hết hạn (máy chủ trả 401)
            pg.reload()
            pg.wait_for_selector("#f-login")
            k["e_het_phien_giu_hash"] = pg.evaluate("() => location.hash") == "#/admin/classes"
            _dang_nhap(pg, "admin")
            _cho_trang(pg, "#/admin/classes", "Quản trị")
            pg.wait_for_selector("#f-qt-lop")
            k["e_dung_nguoi_quay_lai_dung_trang"] = True
            if phieu_la:
                pg.goto(url + f"/app/#/sheet/{phieu_la}")
                _cho_trang(pg, f"#/sheet/{phieu_la}", f"Phiếu #{phieu_la}")
                ctx.clear_cookies(); pg.reload(); pg.wait_for_selector("#f-login")
                _dang_nhap(pg, "admin")
                _cho_trang(pg, f"#/sheet/{phieu_la}", f"Phiếu #{phieu_la}")
                k["e_dung_nguoi_quay_lai_dung_phieu"] = True
                # ---------------- (f) phiên hết hạn ở phiếu của người khác -> gv_an đăng nhập: về Tải ảnh, không lỗi đỏ
                ctx.clear_cookies(); pg.reload(); pg.wait_for_selector("#f-login")
                _dang_nhap(pg, "gv_an")
                _cho_trang(pg, "#/upload", "Tải ảnh")
                k["f_nguoi_khac_o_phieu_ngoai_quyen_ve_tai_anh"] = pg.locator("#main .alert.bad").count() == 0
                pg.screenshot(path=str(OUT / "07_gv_an_tu_phieu_ngoai_quyen.png"), full_page=True)
            else:
                g["e_f_phieu"] = "bỏ qua: không có phiếu nào ngoài quyền gv_an"
            b.close()
    ket["dat"] = all(k.values())
    (OUT / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return ket


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kq = chay()
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    sys.exit(0 if kq["dat"] else 1)
