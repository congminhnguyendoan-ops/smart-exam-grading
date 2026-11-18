import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"

import thu_dien_thoai as T  # noqa: E402  (MayChuThu)
from thu_lenh_h import MK, _tao_user  # noqa: E402

OUT = ROOT / "data" / "_eval" / "ui_i"


def chay() -> dict:
    from playwright.sync_api import sync_playwright
    from backend import demo
    OUT.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}}
    k = ket["kiem"]
    ma = "THU-I-" + uuid.uuid4().hex[:4].upper()
    ten_kt = "Cuối kỳ thử lệnh I"
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        _tao_user(mc.conn, "qt_thu_i", "admin")
        _tao_user(mc.conn, "gv_ngoai_i", "teacher")
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            may = b.new_context(viewport={"width": 1400, "height": 1000}, locale="vi-VN")
            pg = may.new_page()
            pg.on("dialog", lambda d: d.accept())
            pg.goto(url + "/app/")
            pg.wait_for_selector("#f-login")
            pg.fill("#lg-user", "qt_thu_i"); pg.fill("#lg-pass", MK); pg.click("#f-login button")
            pg.wait_for_selector("#userbox:not(.hidden)")
            pg.goto(url + "/app/#/admin/classes")
            pg.wait_for_selector("#f-qt-lop")
            pg.fill("#lop-ma", ma); pg.fill("#lop-ten", "Lớp thử lệnh I"); pg.fill("#lop-nam", "2026-2027")
            pg.click("#f-qt-lop button[type=submit]")
            pg.wait_for_selector(f"#qt td:has-text('{ma}')")
            cid = mc.conn.execute("SELECT class_id FROM classes WHERE class_code = %s", (ma,)).fetchone()["class_id"]
            k["tao_lop_bang_form"] = True
            pg.fill("#lop-ma", ma.lower()); pg.fill("#lop-ten", "Trùng"); pg.click("#f-qt-lop button[type=submit]")
            pg.wait_for_function("() => document.querySelector('#toast').textContent.includes('đã có')", timeout=30000)
            k["trung_ma_lop_bi_tu_choi"] = mc.conn.execute("SELECT count(*) AS n FROM classes WHERE lower(class_code) = lower(%s)", (ma,)).fetchone()["n"] == 1
            pg.screenshot(path=str(OUT / "01_lop.png"), full_page=True)
            pg.goto(url + "/app/#/admin/users")
            pg.wait_for_selector("#f-qt-tk")
            pg.fill("#tk-user", "gv_lop_i"); pg.fill("#tk-ten", "Giáo viên Lớp I"); pg.fill("#tk-mk", MK)
            pg.check(f"#tk-lop input[value='{cid}']")
            pg.click("#f-qt-tk button[type=submit]")
            pg.wait_for_selector("#qt td:has-text('gv_lop_i')")
            id_gv = mc.conn.execute("SELECT user_id FROM users WHERE username = 'gv_lop_i'").fetchone()["user_id"]
            k["tao_gv_kem_lop"] = mc.conn.execute("SELECT count(*) AS n FROM teacher_classes WHERE user_id = %s AND class_id = %s",
                                                  (id_gv, cid)).fetchone()["n"] == 1
            pg.screenshot(path=str(OUT / "02_tai_khoan.png"), full_page=True)
            pg.goto(url + "/app/#/admin/exams")
            pg.wait_for_selector("#f-qt-tao")
            pg.fill("#qt-ten", ten_kt); pg.fill("#qt-mon", "IT3080"); pg.fill("#qt-so-cau", "10")
            pg.select_option("#qt-lop", str(cid)); pg.fill("#qt-dap-an", f"101: {demo.khoa_demo('101', 10)}")
            pg.click("#f-qt-tao button[type=submit]")
            pg.wait_for_selector(f"#qt td:has-text('{ten_kt}')")
            e = mc.conn.execute("SELECT exam_id, class_id, created_by FROM exams WHERE exam_title = %s", (ten_kt,)).fetchone()
            eid = e["exam_id"]
            k["ky_thi_gan_lop_tu_danh_sach"] = e["class_id"] == cid and e["created_by"] != id_gv
            pg.screenshot(path=str(OUT / "03_ky_thi.png"), full_page=True)
            dt = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
            m = dt.new_page()
            m.goto(f"{url}/m?kythi={eid}")
            m.wait_for_selector("#v-login:not(.hidden)")
            m.fill("#lg-user", "gv_lop_i"); m.fill("#lg-pass", MK); m.tap("#f-login button")
            m.wait_for_selector("#v-cap:not(.hidden)", timeout=30000)
            k["gv_cua_lop_chon_san_ky_thi"] = m.inner_text("#cap-title") == ten_kt and ma in m.inner_text("#cap-sub")
            m.screenshot(path=str(OUT / "04_m_qua_lop.png"), full_page=True)
            pg.goto(url + "/app/#/admin/classes")
            pg.wait_for_selector(f"[data-lop-gv='{cid}']")
            pg.click(f"[data-lop-gv='{cid}']")
            pg.wait_for_selector(f"[data-bo-gv='{id_gv}']")
            pg.click(f"[data-bo-gv='{id_gv}']")
            pg.wait_for_function(f"() => !document.querySelector(\"[data-bo-gv='{id_gv}']\")", timeout=30000)
            k["bo_gv_khoi_lop_bang_giao_dien"] = mc.conn.execute("SELECT count(*) AS n FROM teacher_classes WHERE user_id = %s", (id_gv,)).fetchone()["n"] == 0
            pg.screenshot(path=str(OUT / "05_bo_khoi_lop.png"), full_page=True)
            m.goto(f"{url}/m?kythi={eid}")
            m.wait_for_selector("#exam-msg:not(.hidden)", timeout=30000)
            k["bo_gan_mat_quyen_ngay"] = "Không tìm thấy kỳ thi" in m.inner_text("#exam-msg") and ten_kt not in m.content()
            m.screenshot(path=str(OUT / "06_m_sau_bo_gan.png"), full_page=True)
            m2 = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN").new_page()
            m2.goto(f"{url}/m?kythi={eid}")
            m2.wait_for_selector("#v-login:not(.hidden)")
            m2.fill("#lg-user", "gv_ngoai_i"); m2.fill("#lg-pass", MK); m2.tap("#f-login button")
            m2.wait_for_selector("#exam-msg:not(.hidden)", timeout=30000)
            k["gv_ngoai_lop_khong_thay"] = "Không tìm thấy kỳ thi" in m2.inner_text("#exam-msg") and ten_kt not in m2.content()
            b.close()
    ket["dat"] = all(k.values())
    (OUT / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1), encoding="utf-8")
    return ket


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kq = chay()
    print(json.dumps(kq, ensure_ascii=False, indent=1))
    sys.exit(0 if kq["dat"] else 1)
