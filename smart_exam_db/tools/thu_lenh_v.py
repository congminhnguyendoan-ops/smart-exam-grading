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

OUT = ROOT / "data" / "_eval" / "ui_v"
ANH = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia"
MK = "Thu-Lenh-V-2026"
KT_DONG, KT_MO, PHIEU_V3 = 1381, 1633, 1091


def _dang_nhap(pg, user):
    pg.wait_for_selector("#f-login")
    pg.fill("#lg-user", user); pg.fill("#lg-pass", MK); pg.click("#f-login button")
    pg.wait_for_selector("#userbox:not(.hidden)")


def _cho_trang(pg, hash_, chu_h2):
    pg.wait_for_function("([h, t]) => location.hash === h && (document.querySelector('#main h2') || {}).textContent?.includes(t)",
                         arg=[hash_, chu_h2], timeout=30000)


def _ds_chon(pg) -> list[int]:
    return [int(v) for v in pg.evaluate("() => [...document.querySelectorAll('#exam-select option')].map((o) => o.value)")]


def may_tinh(b, url, k, g):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="vi-VN")
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.accept())
    pg.goto(url + "/app/")
    _dang_nhap(pg, "admin")
    _cho_trang(pg, "#/admin", "Quản trị")
    pg.goto(url + "/app/#/admin/exams"); pg.wait_for_selector(f'[data-dong="{KT_DONG}"]')
    with pg.expect_response(lambda r: f"/admin/exams/{KT_DONG}/status" in r.url) as rr:
        pg.click(f'[data-dong="{KT_DONG}"]')
    k["v4_dong_ky_thi_200"] = rr.value.status == 200
    pg.goto(url + "/app/#/admin/audit"); pg.wait_for_selector("#qt table")
    dong1 = pg.inner_text("#qt tbody tr:first-child")
    g["v4_dong_dau_nhat_ky"] = dong1
    k["v4_nhat_ky_co_dong_dong_ky_thi"] = "Đóng kỳ thi" in dong1 and f"Kỳ thi #{KT_DONG}" in dong1 and "admin" in dong1 and "draft → closed" in dong1
    k["v4_trang_nhat_ky_khong_chua_mat_khau"] = MK not in pg.content()
    pg.screenshot(path=str(OUT / "01_v4_nhat_ky.png"), full_page=True)
    pg.goto(url + f"/app/#/sheet/{PHIEU_V3}"); _cho_trang(pg, f"#/sheet/{PHIEU_V3}", f"Phiếu #{PHIEU_V3}")
    pg.wait_for_selector(".ly-do-cot")
    ly = pg.inner_text(".ly-do-cot")
    g["v3_ly_do_chi_tiet"] = ly
    k["v3_chi_tiet_noi_ro_cot"] = "Cột 6: ô tô trống hoặc không đọc được" in ly and "chữ viết tay đọc là 4" in ly
    k["v3_khong_con_cau_cu"] = "cột bubble không đọc được (không tô / tô nhiều ô)" not in ly
    pg.locator(".ly-do-cot").first.screenshot(path=str(OUT / "02_v3_ly_do_cot.png"))
    pg.screenshot(path=str(OUT / "02b_v3_chi_tiet.png"), full_page=True)
    pg.click("#logout"); pg.wait_for_selector("#f-login")
    _dang_nhap(pg, "gv_binh")
    _cho_trang(pg, "#/upload", "Tải ảnh")
    ds = _ds_chon(pg)
    g["v2_o_chon_mac_dinh"] = ds
    k["v2_mac_dinh_an_ky_thi_dong"] = KT_DONG not in ds and KT_MO in ds
    k["v2_hien_tuy_chon_va_so_ky_thi_dong"] = pg.is_visible("#hien-dong-wrap") and pg.inner_text("#so-dong") == "(1)"
    pg.screenshot(path=str(OUT / "03_v2_mac_dinh_an.png"), full_page=True)
    pg.check("#hien-dong")
    ds2 = _ds_chon(pg)
    k["v2_bat_hien_ky_thi_dong"] = KT_DONG in ds2 and "ĐÃ ĐÓNG" in pg.inner_text(f'#exam-select option[value="{KT_DONG}"]')
    k["v2_nho_trong_localstorage"] = pg.evaluate("() => localStorage.getItem('hienKyThiDong')") == "1"
    pg.reload(); pg.wait_for_selector("#userbox:not(.hidden)"); pg.wait_for_selector(f'#exam-select option[value="{KT_DONG}"]', state="attached")
    k["v2_tai_lai_van_nho"] = pg.is_checked("#hien-dong")
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT_DONG}")):
        pg.select_option("#exam-select", str(KT_DONG))
    pg.goto(url + "/app/#/upload"); pg.wait_for_selector("#files")
    pg.set_input_files("#files", str(ANH / "BV06.jpg")); pg.click("#go")
    pg.wait_for_function("() => document.querySelector('#st').textContent.startsWith('Xong')", timeout=60000)
    hang = pg.inner_text("#rows tr:first-child")
    g["v1_may_tinh_ky_thi_dong"] = hang
    k["v1_may_tinh_bi_tu_choi_co_ly_do"] = "Bị từ chối" in hang and "Kỳ thi đã đóng" in hang
    k["v1_may_tinh_tu_choi_khong_gui_lai"] = pg.locator("#rows tr:first-child [data-gui-lai]").count() == 0
    pg.screenshot(path=str(OUT / "04_v1_may_tinh_tu_choi.png"), full_page=True)
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT_MO}")):
        pg.select_option("#exam-select", str(KT_MO))
    pg.goto(url + "/app/#/upload"); pg.wait_for_selector("#files")
    cat = f"**/exams/{KT_MO}/sheets"
    pg.route(cat, lambda r: r.abort())
    pg.set_input_files("#files", str(ANH / "BV06.jpg")); pg.click("#go")
    pg.wait_for_selector("#rows tr:first-child [data-gui-lai]", timeout=60000)
    hang = pg.inner_text("#rows tr:first-child")
    k["v1_may_tinh_loi_mang_co_gui_lai"] = "Lỗi mạng" in hang
    pg.screenshot(path=str(OUT / "05_v1_may_tinh_loi_mang.png"), full_page=True)
    pg.unroute(cat)
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT_MO}/sheets") and r.request.method == "POST", timeout=60000) as rr:
        pg.click("#rows tr:first-child [data-gui-lai]")
    pg.wait_for_function("() => !document.querySelector('#rows tr:first-child [data-gui-lai]') && !document.querySelector('#rows tr:first-child').textContent.includes('Đang xử lý')",
                         timeout=60000)
    hang = pg.inner_text("#rows tr:first-child")
    g["v1_may_tinh_sau_gui_lai"] = hang
    k["v1_may_tinh_gui_lai_thanh_cong"] = rr.value.status == 201 and ("Cần xem" in hang or "Chính thức" in hang)
    pg.screenshot(path=str(OUT / "06_v1_may_tinh_gui_lai.png"), full_page=True)
    pg.click("#logout"); pg.wait_for_selector("#f-login")
    k["v2_dang_xuat_xoa_khoa"] = pg.evaluate("() => localStorage.getItem('hienKyThiDong')") is None
    ctx.close()


def dien_thoai(b, pw, url, k, g):
    ctx = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.accept())
    pg.goto(url + "/m")
    pg.wait_for_selector("#f-login")
    pg.fill("#lg-user", "gv_binh"); pg.fill("#lg-pass", MK); pg.click("#f-login button")
    pg.wait_for_selector("#v-exams:not(.hidden)")
    ids = [int(x) for x in pg.evaluate("() => [...document.querySelectorAll('#exam-list .exam')].map((b) => b.dataset.id)")]
    g["m_v2_danh_sach_mac_dinh"] = ids
    k["m_v2_mac_dinh_an_ky_thi_dong"] = KT_DONG not in ids and KT_MO in ids
    k["m_v2_co_tuy_chon"] = pg.is_visible("#hien-dong-wrap")
    pg.screenshot(path=str(OUT / "07_m_v2_mac_dinh_an.png"), full_page=True)
    pg.check("#hien-dong")
    pg.wait_for_selector(f'#exam-list .exam[data-id="{KT_DONG}"]')
    k["m_v2_bat_hien_ky_thi_dong"] = "ĐÃ ĐÓNG" in pg.inner_text(f'#exam-list .exam[data-id="{KT_DONG}"]')
    pg.screenshot(path=str(OUT / "08_m_v2_hien_ca_dong.png"), full_page=True)
    pg.click(f'#exam-list .exam[data-id="{KT_DONG}"]'); pg.wait_for_selector("#v-cap:not(.hidden)")
    pg.set_input_files("#nhieu", str(ANH / "BV07.jpg"))
    pg.wait_for_selector("#ds-to li.tuchoi", timeout=60000)
    the = pg.inner_text("#ds-to li.tuchoi")
    g["m_v1_the_tu_choi"] = the
    k["m_v1_the_bi_tu_choi_co_ly_do"] = "bị từ chối" in the and "Kỳ thi không nhận ảnh" in the and "đã đóng" in the
    k["m_v1_tu_choi_khong_gui_lai"] = pg.locator("#ds-to li.tuchoi [data-gui-lai]").count() == 0
    k["m_v1_dem_tu_choi"] = "1 từ chối" in pg.inner_text("#tk-so").replace("\n", " ")
    pg.screenshot(path=str(OUT / "09_m_v1_tu_choi.png"), full_page=True)
    pg.click("#doi-ky-thi"); pg.wait_for_selector(f'#exam-list .exam[data-id="{KT_MO}"]')
    pg.click(f'#exam-list .exam[data-id="{KT_MO}"]'); pg.wait_for_selector("#v-cap:not(.hidden)")
    cat = f"**/exams/{KT_MO}/sheets"
    pg.route(cat, lambda r: r.abort())
    pg.set_input_files("#nhieu", str(ANH / "BV10.jpg"))
    pg.wait_for_selector("#ds-to li.loi [data-gui-lai]", timeout=60000)
    k["m_v1_loi_mang_co_gui_lai"] = "lỗi mạng" in pg.inner_text("#ds-to li.loi")
    pg.screenshot(path=str(OUT / "10_m_v1_loi_mang.png"), full_page=True)
    pg.unroute(cat)
    pg.click("#ds-to li.loi [data-gui-lai]")
    pg.wait_for_selector("#ds-to li.xong", timeout=90000)
    pg.wait_for_function("() => document.querySelector('#ds-to li.xong').textContent.includes('SBD')", timeout=30000)
    the = pg.inner_text("#ds-to li.xong")
    g["m_sau_gui_lai"] = the
    k["m_v1_gui_lai_thanh_cong"] = "phiếu #" in the
    k["m_v3_canh_bao_sbd_theo_cot"] = "SBD cần xem" in the and "ô viết tay trống" in the and "không có trong danh sách kỳ thi" in the
    pg.screenshot(path=str(OUT / "11_m_v1_v3_gui_lai_canh_bao.png"), full_page=True)
    pg.click("#logout"); pg.wait_for_selector("#v-login:not(.hidden)")
    k["m_v2_dang_xuat_xoa_khoa"] = pg.evaluate("() => localStorage.getItem('hienKyThiDong')") is None
    ctx.close()


def chay() -> dict:
    from playwright.sync_api import sync_playwright
    from backend import auth
    OUT.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}, "ghi_chu": {}}
    k, g = ket["kiem"], ket["ghi_chu"]
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        c = mc.conn
        if c.execute("SELECT to_regclass('admin_audit_log') AS t").fetchone()["t"] is None:
            raise SystemExit("DỪNG: migration 005 chưa áp (python -m backend.migrate).")
        if c.execute("UPDATE users SET password_hash = %s WHERE username IN ('admin', 'gv_binh')", (auth.bam_mat_khau(MK),)).rowcount != 2:
            raise SystemExit("Thiếu tài khoản admin / gv_binh.")
        st = {r["exam_id"]: r["status"] for r in c.execute("SELECT exam_id, status::text AS status FROM exams WHERE exam_id = ANY(%s)", ([KT_DONG, KT_MO],)).fetchall()}
        if st != {KT_DONG: "draft", KT_MO: "draft"}:
            raise SystemExit(f"DỪNG: cần kỳ thi {KT_DONG} và {KT_MO} đang mở, có: {st}")
        g["dong_nhat_ky_truoc"] = c.execute("SELECT count(*) AS n FROM admin_audit_log").fetchone()["n"]
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            may_tinh(b, url, k, g)
            dien_thoai(b, pw, url, k, g)
            b.close()
        g["dong_nhat_ky_trong_giao_dich"] = c.execute("SELECT count(*) AS n FROM admin_audit_log").fetchone()["n"]
    ket["dat"] = all(k.values())
    (OUT / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return ket


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kq = chay()
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    sys.exit(0 if kq["dat"] else 1)
