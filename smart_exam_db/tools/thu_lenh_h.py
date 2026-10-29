"""
thu_lenh_h.py - Thử bằng TRÌNH DUYỆT THẬT (Playwright Chromium) lệnh H (29/10/2026). CHỈ ROLLBACK: máy chủ trong tiến trình (tools/thu_dien_thoai.MayChuThu),
MỘT kết nối không commit; tài khoản + kỳ thi tạo trong giao dịch -> KHÔNG ghi dòng nào vào CSDL thật.

  python tools/thu_lenh_h.py

Kịch bản:
  1. /app/ (máy tính) – admin: mục "Quản trị" chỉ hiện cho admin; tạo tài khoản giáo viên bằng form; tạo kỳ thi + gán giáo viên; đóng kỳ thi; tải trang bìa.
  2. /m?kythi=<id> (Pixel 7) – giáo viên phụ trách: đăng nhập xong kỳ thi được chọn sẵn, tên ở đầu trang, ?kythi bị bỏ khỏi URL.
  3. /m?kythi=<id> – giáo viên KHÔNG có quyền: thông báo như 404, trang không chứa tên kỳ thi.
  4. Admin vô hiệu hoá giáo viên đang mở /m -> lần gọi kế tiếp bị đưa về màn đăng nhập; đăng nhập lại bị từ chối.
Ảnh màn hình + ket_qua.json: data/_eval/ui_h/.
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

OUT = ROOT / "data" / "_eval" / "ui_h"
MK = "Thu-Lenh-H-2026"


def _tao_user(conn, username: str, vai_tro: str) -> int:
    from backend import auth
    return conn.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, %s::user_role) RETURNING user_id",
                        (username, f"{username}@test.local", auth.bam_mat_khau(MK), f"Người thử {username}", vai_tro)).fetchone()["user_id"]


def chay() -> dict:
    from playwright.sync_api import sync_playwright
    from backend import demo
    OUT.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}}
    k = ket["kiem"]
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        _tao_user(mc.conn, "qt_thu_h", "admin")
        _tao_user(mc.conn, "gv_ngoai_h", "teacher")
        dap_an = demo.khoa_demo("101", 10)
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            # ---------------- 1. admin trên máy tính
            may = b.new_context(viewport={"width": 1400, "height": 1000}, locale="vi-VN")
            pg = may.new_page()
            pg.on("dialog", lambda d: d.accept())
            pg.goto(url + "/app/")
            pg.wait_for_selector("#f-login")
            pg.fill("#lg-user", "qt_thu_h"); pg.fill("#lg-pass", MK); pg.click("#f-login button")
            pg.wait_for_selector("#userbox:not(.hidden)")
            k["admin_thay_muc_quan_tri"] = pg.is_visible("#nav-admin")
            pg.goto(url + "/app/#/admin/users")
            pg.wait_for_selector("#f-qt-tk")
            pg.fill("#tk-user", "gv_moi_h"); pg.fill("#tk-ten", "Giáo viên Mới H"); pg.fill("#tk-mk", MK)
            pg.click("#f-qt-tk button[type=submit]")
            pg.wait_for_selector("text=gv_moi_h")
            k["tao_tai_khoan_bang_form"] = mc.conn.execute("SELECT count(*) AS n FROM users WHERE username = 'gv_moi_h' AND role = 'teacher'").fetchone()["n"] == 1
            k["trang_khong_hien_mat_khau"] = MK not in pg.content()
            pg.screenshot(path=str(OUT / "01_tai_khoan.png"), full_page=True)
            id_gv = mc.conn.execute("SELECT user_id FROM users WHERE username = 'gv_moi_h'").fetchone()["user_id"]
            pg.goto(url + "/app/#/admin/exams")
            pg.wait_for_selector("#f-qt-tao")
            pg.fill("#qt-ten", "Giữa kỳ thử lệnh H"); pg.fill("#qt-mon", "IT3080"); pg.fill("#qt-ngay", "2026-11-20"); pg.fill("#qt-so-cau", "10")
            pg.select_option("#qt-gv", str(id_gv)); pg.fill("#qt-dap-an", f"101: {dap_an}")
            pg.click("#f-qt-tao button[type=submit]")
            pg.wait_for_selector("#qt td:has-text('Giữa kỳ thử lệnh H')")
            e = mc.conn.execute("SELECT exam_id, created_by FROM exams WHERE exam_title = 'Giữa kỳ thử lệnh H'").fetchone()
            eid = e["exam_id"]
            k["tao_ky_thi_gan_giao_vien"] = e["created_by"] == id_gv
            r = pg.request.get(f"{url}/exams/{eid}/cover.pdf")
            k["trang_bia_tai_duoc"] = r.status == 200 and r.headers["content-type"] == "application/pdf"
            (OUT / "trang_bia.pdf").write_bytes(r.body())
            pg.screenshot(path=str(OUT / "02_ky_thi.png"), full_page=True)

            # ---------------- 2. giáo viên phụ trách mở /m?kythi
            dt = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
            m = dt.new_page()
            m.goto(f"{url}/m?kythi={eid}")
            m.wait_for_selector("#v-login:not(.hidden)")
            k["man_dang_nhap_nhac_ma_ky_thi"] = str(eid) in m.inner_text("#lg-kythi") and "Giữa kỳ thử lệnh H" not in m.content()
            m.screenshot(path=str(OUT / "03_m_dang_nhap.png"), full_page=True)
            m.fill("#lg-user", "gv_moi_h"); m.fill("#lg-pass", MK); m.tap("#f-login button")
            m.wait_for_selector("#v-cap:not(.hidden)", timeout=30000)
            k["chon_san_dung_ky_thi"] = m.inner_text("#cap-title") == "Giữa kỳ thử lệnh H" and f"mã {eid}" in m.inner_text("#cap-sub")
            k["bo_kythi_khoi_url"] = "kythi" not in m.url
            m.screenshot(path=str(OUT / "04_m_chon_san.png"), full_page=True)

            # ---------------- 3. giáo viên KHÔNG có quyền
            dt2 = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
            m2 = dt2.new_page()
            m2.goto(f"{url}/m?kythi={eid}")
            m2.wait_for_selector("#v-login:not(.hidden)")
            m2.fill("#lg-user", "gv_ngoai_h"); m2.fill("#lg-pass", MK); m2.tap("#f-login button")
            m2.wait_for_selector("#exam-msg:not(.hidden)", timeout=30000)
            k["ngoai_quyen_thong_bao_nhu_404"] = "Không tìm thấy kỳ thi" in m2.inner_text("#exam-msg")
            k["ngoai_quyen_khong_lo_ten"] = "Giữa kỳ thử lệnh H" not in m2.content() and m2.is_visible("#v-exams")
            m2.screenshot(path=str(OUT / "05_m_ngoai_quyen.png"), full_page=True)

            # ---------------- 1b. đóng kỳ thi -> /m báo đã đóng sau khi chọn lại
            pg.click(f"[data-dong='{eid}']")
            pg.wait_for_selector(f"[data-dong='{eid}'][data-closed='0']")
            k["dong_ky_thi"] = mc.conn.execute("SELECT status::text AS s FROM exams WHERE exam_id = %s", (eid,)).fetchone()["s"] == "closed"
            m.goto(f"{url}/m?kythi={eid}")
            m.wait_for_selector("#v-cap:not(.hidden)", timeout=30000)
            k["m_bao_ky_thi_da_dong"] = m.is_visible("#cap-dong")
            m.screenshot(path=str(OUT / "06_m_da_dong.png"), full_page=True)

            # ---------------- 4. vô hiệu hoá giáo viên đang mở /m
            pg.goto(url + "/app/#/admin/users")
            pg.wait_for_selector(f"[data-hd='{id_gv}']")
            pg.click(f"[data-hd='{id_gv}']")
            pg.wait_for_selector(f"[data-hd='{id_gv}'][data-bat='1']")
            m.click("#doi-ky-thi")                                             # lần gọi API kế tiếp của giáo viên
            m.wait_for_selector("#v-login:not(.hidden)", timeout=30000)
            k["vo_hieu_hoa_dua_ve_dang_nhap"] = "hết" in m.inner_text("#lg-err")              # "Phiên đăng nhập đã hết – hãy đăng nhập lại."
            ket["thong_bao_khi_bi_vo_hieu_hoa"] = m.inner_text("#lg-err")
            m.fill("#lg-user", "gv_moi_h"); m.fill("#lg-pass", MK); m.tap("#f-login button")
            m.wait_for_function("() => document.querySelector('#lg-err').textContent.includes('Sai tên đăng nhập')", timeout=30000)
            k["vo_hieu_hoa_khong_dang_nhap_lai"] = m.is_visible("#lg-err") and m.is_visible("#v-login")
            m.screenshot(path=str(OUT / "07_m_bi_vo_hieu_hoa.png"), full_page=True)
            b.close()
    ket["dat"] = all(k.values())
    (OUT / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1), encoding="utf-8")
    return ket


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kq = chay()
    print(json.dumps(kq, ensure_ascii=False, indent=1))
    sys.exit(0 if kq["dat"] else 1)
