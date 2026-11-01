"""
thu_lenh_aa.py - Thử bằng TRÌNH DUYỆT THẬT (Playwright Chromium) lệnh AA (31/10/2026): duyệt SBD / mã đề nhanh hơn, hướng dẫn chụp thẳng (/m), bảng màu mới.
CHỈ ROLLBACK (tools/thu_dien_thoai.MayChuThu: máy chủ trong tiến trình, MỘT kết nối không commit, ảnh vào thư mục tạm) -> KHÔNG ghi dòng nào vào CSDL thật.
Tài khoản thật `admin`, `gv_binh`: mật khẩu chỉ đặt tạm TRONG giao dịch sẽ ROLLBACK (mật khẩu thật không đổi).

  python tools/thu_lenh_aa.py --giai-doan sau      # nhánh ui-sau-bv: chụp ảnh + KIỂM hành vi mới
  python tools/thu_lenh_aa.py --giai-doan truoc    # chạy khi đang ở nhánh cai-tien-b (bản bảo vệ): chỉ chụp ảnh các màn để so sánh

Kịch bản (trong giao dịch): gv_binh tải BV10 (SBD 220010 ngoài danh sách), BV06, BV08 vào kỳ thi TẬP 1633 -> chụp các màn máy tính
(đăng nhập, tải ảnh, danh sách, hàng đợi, duyệt BV10, chi tiết, bảng điểm, hồ sơ) + admin (Quản trị: kỳ thi, tài khoản, lớp, nhật ký)
+ Pixel 7 /m (đăng nhập, chọn kỳ thi, màn chụp, thẻ kết quả).
Giai đoạn "sau" kiểm thêm: con trỏ đặt sẵn ở ô SBD, khối phóng to cột cần nhìn, lỗi tại ô + gợi ý, Tab sang ô mã đề, Enter -> hỏi xác nhận
(Huỷ thì KHÔNG gửi), đồng ý -> lưu + nút "Phiếu cần xem kế tiếp" -> sang phiếu khác; /m có hướng dẫn chụp thu gọn được; nền trang = --bg mới.
Trước và sau giao dịch đếm phiếu của 1380, 1381, 1632, 1633 bằng kết nối RIÊNG -> phải không đổi.
Ảnh + ket_qua.json: data/_eval/ui_aa/<giai_doan>/.
"""
import argparse
import json
import os
import sys
from pathlib import Path

# AA_ROOT: chạy BẢN SAO của công cụ này khi đang ở nhánh cai-tien-b (nhánh đó không có tệp này) để chụp ảnh "trước"
ROOT = Path(os.environ.get("AA_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"

import thu_dien_thoai as T  # noqa: E402  (MayChuThu)

ANH = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia"
MK = "Thu-Lenh-AA-2026"
KT = 1633                                    # kỳ thi TẬP của gv_binh (K22B, mã đề 103 / 104)
KY_THI_KIEM = (1380, 1381, 1632, 1633)


def dem_phieu() -> dict[int, int]:
    """Đếm phiếu bằng kết nối RIÊNG (thấy đúng dữ liệu đã commit, không thấy giao dịch thử)."""
    from backend.db import ket_noi
    c = ket_noi()
    try:
        r = c.execute("SELECT exam_id, count(*) AS n FROM answer_sheets WHERE exam_id = ANY(%s) GROUP BY exam_id", (list(KY_THI_KIEM),)).fetchall()
        return {k: next((x["n"] for x in r if x["exam_id"] == k), 0) for k in KY_THI_KIEM}
    finally:
        c.rollback(); c.close()


def _dang_nhap(pg, user):
    pg.wait_for_selector("#f-login")
    pg.fill("#lg-user", user); pg.fill("#lg-pass", MK); pg.click("#f-login button")
    pg.wait_for_selector("#userbox:not(.hidden)")


def _cho_h2(pg, chu, timeout=30000):
    pg.wait_for_function("(t) => (document.querySelector('#main h2') || {}).textContent?.includes(t)", arg=chu, timeout=timeout)


def _cho_anh(pg):
    """Chờ ảnh (đầu phiếu, ô viết tay, câu) tải xong trước khi chụp màn hình; ảnh lazy ngoài khung có thể không tải -> tối đa 8 s."""
    try:
        pg.wait_for_function("() => [...document.images].filter((i) => i.loading !== 'lazy').every((i) => i.complete)", timeout=8000)
    except Exception:  # noqa: BLE001 – chỉ ảnh hưởng ảnh chụp, không ảnh hưởng kết luận
        pass


def _tai(pg, url, ten) -> dict:
    """Tải một ảnh qua API bằng phiên của trang (cookie) – như giao diện tải ảnh làm."""
    r = pg.request.post(f"{url}/exams/{KT}/sheets", multipart={"file": {"name": ten, "mimeType": "image/jpeg", "buffer": (ANH / ten).read_bytes()}})
    assert r.status == 201, (r.status, r.text())
    return r.json()


def may_tinh(b, url, out, sau, k, g):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="vi-VN")
    pg = ctx.new_page()
    hop_thoai = []
    def _hop(d):                                                               # noqa: E306
        hop_thoai.append(d.message)
        (d.dismiss() if g.get("_huy_lan_toi") else d.accept())
        g["_huy_lan_toi"] = False
    pg.on("dialog", _hop)
    pg.goto(url + "/app/"); pg.wait_for_selector("#f-login")
    pg.screenshot(path=str(out / "01_dang_nhap.png"), full_page=True)
    _dang_nhap(pg, "gv_binh")
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT}")):
        pg.select_option("#exam-select", str(KT))
    ids = {ten: _tai(pg, url, ten)["sheet_id"] for ten in ("BV10.jpg", "BV06.jpg", "BV08.jpg")}
    g["phieu_tai"] = ids
    if sau:
        k["nen_trang_mau_moi"] = pg.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(243, 248, 248)"
        k["muc_dang_chon_mau_chu_dao"] = pg.evaluate("() => getComputedStyle(document.querySelector('#nav a.on')).backgroundColor") == "rgb(31, 122, 140)"
    pg.goto(url + "/app/#/upload"); _cho_h2(pg, "Tải ảnh")
    pg.screenshot(path=str(out / "02_tai_anh.png"), full_page=True)
    if sau:                                                                    # lệnh AB: ô chọn tệp tiếng Việt (KHÔNG bấm "Bắt đầu chấm")
        k["ab_chon_tep_chua_chon"] = pg.inner_text("#sel") == "Chưa chọn ảnh." and pg.is_visible("label.chon-tep")
        hop = pg.locator("#files").bounding_box()
        k["ab_o_goc_tieng_anh_an"] = hop is None or (hop["width"] <= 2 and hop["height"] <= 2)
        pg.set_input_files("#files", [str(ANH / "BV06.jpg"), str(ANH / "BV08.jpg")])
        g["ab_sel_chon_nhieu"] = pg.inner_text("#sel")
        k["ab_chon_nhieu_hien_ten"] = g["ab_sel_chon_nhieu"] == "Đã chọn 2 ảnh: BV06.jpg, BV08.jpg" and pg.is_enabled("#go")
        pg.screenshot(path=str(out / "02b_tai_anh_da_chon.png"), full_page=True)
        pg.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(["x"], "keo_tha.jpg", { type: "image/jpeg" }));
                       document.querySelector("#drop").dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true })); }""")
        k["ab_keo_tha_van_chay"] = pg.inner_text("#sel") == "Đã chọn 1 ảnh: keo_tha.jpg"
        pg.focus("#files")
        k["ab_o_chon_tep_nhan_tab"] = pg.evaluate("() => document.activeElement.id") == "files"
    pg.goto(url + "/app/#/sheets"); _cho_h2(pg, "Danh sách phiếu"); pg.wait_for_selector("tr.row-link")
    pg.screenshot(path=str(out / "03_danh_sach.png"), full_page=True)
    pg.goto(url + "/app/#/review"); _cho_h2(pg, "Hàng đợi duyệt")
    pg.screenshot(path=str(out / "04_hang_doi.png"), full_page=True)
    # ---------------- duyệt BV10: SBD 220010 không có trong danh sách
    s10 = ids["BV10.jpg"]
    pg.goto(url + f"/app/#/review/{s10}"); _cho_h2(pg, f"Duyệt phiếu #{s10}"); pg.wait_for_selector("#in-sbd"); _cho_anh(pg)
    pg.screenshot(path=str(out / "05_duyet_mo_phieu.png"), full_page=True)
    if sau:
        k["con_tro_dat_san_o_sbd"] = pg.evaluate("() => document.activeElement && document.activeElement.id") == "in-sbd"
        k["co_khoi_phong_to_cot_can_nhin"] = pg.locator("#phong-to .pt-cot").count() >= 1
        g["so_cot_phong_to"] = pg.locator("#phong-to .pt-cot").count()
        k["cot_khop_lam_nhat"] = pg.locator("#khung-dd .haikenh td.khop").count() >= 1
        k["goi_y_phim_tat"] = "Enter" in pg.inner_text("#khung-dd .phim-goi-y")
    pg.fill("#in-sbd", "220010")
    if sau:
        bao = pg.inner_text("#bao-sbd")
        g["loi_tai_o_sbd"] = bao
        k["loi_tai_o_sbd_ngoai_danh_sach"] = "220010 không có trong danh sách" in bao
        k["goi_y_sbd_hop_le"] = pg.locator("#bao-sbd button.goi-y").count() >= 1
        g["goi_y_sbd"] = pg.evaluate("() => [...document.querySelectorAll('#bao-sbd button.goi-y')].map((b) => b.dataset.val)")
        k["goi_y_khong_tu_dien"] = pg.input_value("#in-sbd") == "220010"
    pg.locator(".card", has=pg.locator("#in-sbd")).screenshot(path=str(out / "06_duyet_khung_sbd.png"))   # bản cũ không có #khung-dd
    if sau:
        pg.focus("#in-sbd"); pg.keyboard.press("Tab")
        k["tab_sang_o_ma_de"] = pg.evaluate("() => document.activeElement.id") == "in-ma"
        ma_cu = pg.input_value("#in-ma")
        pg.fill("#in-ma", "105")
        bm = pg.inner_text("#bao-ma"); g["loi_tai_o_ma_de"] = bm
        k["loi_tai_o_ma_de_ngoai_ky_thi"] = "105 không thuộc kỳ thi" in bm and "103" in bm and "104" in bm
        pg.locator("#khung-dd").screenshot(path=str(out / "07_duyet_ma_de_sai.png"))
        pg.fill("#in-ma", ma_cu or "103")
        # Enter -> hỏi xác nhận; HUỶ thì không gửi PUT
        put = []
        pg.on("request", lambda r: put.append(r.url) if r.method == "PUT" and "/identity" in r.url else None)
        g["_huy_lan_toi"] = True
        pg.focus("#in-sbd"); pg.keyboard.press("Enter")
        pg.wait_for_timeout(800)
        k["enter_hoi_xac_nhan"] = bool(hop_thoai) and "không có trong danh sách" in hop_thoai[-1]
        k["huy_xac_nhan_khong_gui"] = not put
        # Enter lần nữa, đồng ý -> lưu -> nút phiếu kế tiếp ngay tại chỗ
        with pg.expect_response(lambda r: r.request.method == "PUT" and "/identity" in r.url) as rr:
            pg.focus("#in-sbd"); pg.keyboard.press("Enter")
        k["dong_y_thi_luu_200"] = rr.value.status == 200
        pg.wait_for_selector("#da-luu-dd #ke-tiep-sau-luu"); _cho_anh(pg)
        k["sau_luu_co_nut_ke_tiep"] = True
        g["hop_thoai"] = hop_thoai[:]
        pg.screenshot(path=str(out / "08_duyet_sau_luu.png"), full_page=False)
        href = pg.get_attribute("#ke-tiep-sau-luu", "href")
        pg.click("#ke-tiep-sau-luu")
        pg.wait_for_function("(h) => location.hash === h", arg=href)
        sid2 = int(href.rsplit("/", 1)[1]); _cho_h2(pg, f"Duyệt phiếu #{sid2}")
        k["ke_tiep_sang_phieu_khac_trong_hang_doi"] = sid2 != s10 and sid2 in ids.values()
        pg.screenshot(path=str(out / "09_phieu_ke_tiep.png"), full_page=True)
    pg.goto(url + f"/app/#/sheet/{s10}"); _cho_h2(pg, f"Phiếu #{s10}"); _cho_anh(pg)
    pg.screenshot(path=str(out / "10_chi_tiet.png"), full_page=True)
    pg.goto(url + "/app/#/results"); _cho_h2(pg, "Bảng điểm")
    pg.screenshot(path=str(out / "11_bang_diem.png"), full_page=True)
    pg.goto(url + "/app/#/profile"); _cho_h2(pg, "Hồ sơ")
    pg.screenshot(path=str(out / "12_ho_so.png"), full_page=True)
    pg.click("#logout"); pg.wait_for_selector("#f-login")
    # ---------------- admin: Quản trị
    _dang_nhap(pg, "admin"); _cho_h2(pg, "Quản trị")
    for i, (tab, cho) in enumerate((("exams", "#qt table"), ("users", "#qt table"), ("classes", "#qt table"), ("audit", "#qt")), 13):
        pg.goto(url + f"/app/#/admin/{tab}"); pg.wait_for_selector(cho); pg.wait_for_timeout(300)
        pg.screenshot(path=str(out / f"{i}_quan_tri_{tab}.png"), full_page=True)
    pg.click("#logout"); pg.wait_for_selector("#f-login")
    ctx.close()


def dien_thoai(b, pw, url, out, sau, k, g):
    ctx = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
    pg = ctx.new_page()
    pg.on("dialog", lambda d: d.accept())
    pg.goto(url + "/m"); pg.wait_for_selector("#f-login")
    pg.screenshot(path=str(out / "20_m_dang_nhap.png"), full_page=True)
    pg.fill("#lg-user", "gv_binh"); pg.fill("#lg-pass", MK); pg.click("#f-login button")
    pg.wait_for_selector("#v-exams:not(.hidden)")
    pg.screenshot(path=str(out / "21_m_chon_ky_thi.png"), full_page=True)
    pg.click(f'#exam-list .exam[data-id="{KT}"]'); pg.wait_for_selector("#v-cap:not(.hidden)")
    pg.screenshot(path=str(out / "22_m_man_chup.png"), full_page=True)
    if sau:
        k["m_huong_dan_mac_dinh_thu_gon"] = pg.evaluate("() => !document.querySelector('#hd-chup').open")
        pg.click("#hd-chup summary")
        k["m_huong_dan_mo_ra_duoc"] = pg.evaluate("() => document.querySelector('#hd-chup').open") and "4 ô vuông đen" in pg.inner_text("#hd-chup")
        pg.screenshot(path=str(out / "23_m_huong_dan_mo.png"), full_page=True)
        k["m_thanh_dau_mau_chu_dao"] = pg.evaluate("() => getComputedStyle(document.querySelector('.top')).backgroundColor") == "rgb(31, 122, 140)"
    pg.set_input_files("#nhieu", str(ANH / "BV09.jpg"))
    pg.wait_for_selector("#ds-to li.xong", timeout=90000)
    pg.wait_for_function("() => document.querySelector('#ds-to li.xong').textContent.includes('SBD')", timeout=30000)
    k["m_tai_anh_co_ket_qua"] = "phiếu #" in pg.inner_text("#ds-to li.xong")
    pg.screenshot(path=str(out / "24_m_ket_qua.png"), full_page=True)
    pg.click("#logout"); pg.wait_for_selector("#v-login:not(.hidden)")
    ctx.close()


def chay(giai_doan: str) -> dict:
    from playwright.sync_api import sync_playwright
    from backend import auth
    sau = giai_doan == "sau"
    out = ROOT / "data" / "_eval" / "ui_aa" / giai_doan
    out.mkdir(parents=True, exist_ok=True)
    ket = {"giai_doan": giai_doan, "che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}, "ghi_chu": {}}
    k, g = ket["kiem"], ket["ghi_chu"]
    g["so_phieu_truoc"] = truoc = dem_phieu()
    with T.MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        c = mc.conn
        if c.execute("UPDATE users SET password_hash = %s WHERE username IN ('admin', 'gv_binh')", (auth.bam_mat_khau(MK),)).rowcount != 2:
            raise SystemExit("Thiếu tài khoản admin / gv_binh.")
        st = c.execute("SELECT status::text AS s FROM exams WHERE exam_id = %s", (KT,)).fetchone()
        if not st or st["s"] != "draft":
            raise SystemExit(f"DỪNG: cần kỳ thi {KT} đang mở, có: {st}")
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            may_tinh(b, url, out, sau, k, g)
            dien_thoai(b, pw, url, out, sau, k, g)
            b.close()
    g["so_phieu_sau"] = sau_gd = dem_phieu()
    k["so_phieu_4_ky_thi_khong_doi"] = truoc == sau_gd
    g.pop("_huy_lan_toi", None)
    ket["dat"] = all(k.values())
    (out / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return ket


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--giai-doan", choices=["truoc", "sau"], required=True)
    kq = chay(ap.parse_args().giai_doan)
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    sys.exit(0 if kq["dat"] else 1)
