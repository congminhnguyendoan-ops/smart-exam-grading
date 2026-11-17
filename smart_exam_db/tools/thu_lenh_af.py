"""
thu_lenh_af.py - Thử bằng TRÌNH DUYỆT THẬT (Playwright Chromium) lệnh AF (01/11/2026): duyệt nhanh – phím tắt, xác nhận hàng loạt (có hộp hỏi),
hàng đợi lọc theo lý do, nhãn "máy đọc / dấu hiệu". CHỈ ROLLBACK (tools/thu_dien_thoai.MayChuThu: MỘT kết nối không commit) -> 0 dòng ghi vào CSDL
thật; thư mục ảnh tạm của máy chủ thử bị XOÁ khi xong. Mật khẩu gv_binh chỉ đặt tạm TRONG giao dịch sẽ rollback.

  python tools/thu_lenh_af.py          # -> data/_eval/ui_af/ (ảnh màn hình + ket_qua.json)

Kịch bản (kỳ thi TẬP 1633, gv_binh): tải BV07 (tô nhạt cả tờ – nhiều câu cờ), BV09, BV06, BV10 (SBD ngoài danh sách).
  ĐO THAO TÁC (mỗi lần bấm chuột / phím = 1):  BV09 duyệt theo CÁCH CŨ (bấm "Xác nhận như máy đọc" từng câu)  ·  BV07 bằng XÁC NHẬN HÀNG LOẠT
  ·  BV06 chỉ bằng BÀN PHÍM (Esc, C, Enter cho câu đầu – sửa tay; Space cho câu còn lại; N sang phiếu kế).
  KIỂM: hộp xác nhận (nút xác nhận khoá tới khi tích, tiêu điểm ở "Huỷ", Enter = Huỷ, không gửi gì), danh sách câu + đáp án máy đọc, cảnh báo
  không hoàn tác; BV10: hàng loạt KHÔNG đụng SBD (vẫn cần xem, ô SBD trống, chưa có điểm chính thức); phím tắt không cướp phím trong ô SBD; hàng đợi lọc.
Trước / sau: số phiếu của 1380, 1381, 1632, 1633 đếm bằng kết nối RIÊNG phải không đổi.
"""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import os  # noqa: E402

os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"
import thu_dien_thoai as T  # noqa: E402
from thu_lenh_aa import ANH, KT, _cho_anh, _cho_h2, _dang_nhap, _tai, dem_phieu  # noqa: E402

MK = "Thu-Lenh-AA-2026"           # thu_lenh_aa._dang_nhap dùng hằng này
OUT = ROOT / "data" / "_eval" / "ui_af"


class DemThaoTac:
    def __init__(self):
        self.n = 0
        self.nhat_ky = []

    def bam(self, pg, sel, ghi=""):
        pg.click(sel)
        self.n += 1
        self.nhat_ky.append(f"bấm {ghi or sel}")

    def phim(self, pg, key, ghi=""):
        pg.keyboard.press(key)
        self.n += 1
        self.nhat_ky.append(f"phím {key} {ghi}".strip())


def con_lai(pg) -> int:
    return pg.locator(".rcard:not(.done)").count()


def cho_con_lai(pg, n, timeout=30000):
    pg.wait_for_function("(n) => document.querySelectorAll('.rcard:not(.done)').length === n && !document.querySelector('.rcard button:disabled[data-act=\"set\"]')",
                         arg=n, timeout=timeout)


def mo_tu_hang_doi(pg, url, sid, d: DemThaoTac):
    pg.goto(url + "/app/#/review"); _cho_h2(pg, "Hàng đợi duyệt")
    d.bam(pg, f'a.btn[href="#/review/{sid}"]', "Duyệt (hàng đợi)")
    _cho_h2(pg, f"Duyệt phiếu #{sid}")
    pg.wait_for_timeout(300)


def chay() -> dict:
    from playwright.sync_api import sync_playwright
    from backend import auth
    OUT.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback (0 dòng ghi vào CSDL thật)", "kiem": {}, "ghi_chu": {}, "thao_tac": {}}
    k, g, tt = ket["kiem"], ket["ghi_chu"], ket["thao_tac"]
    g["so_phieu_truoc"] = truoc = dem_phieu()
    kho = None
    try:
        with T.MayChuThu() as mc:
            kho = mc.cfg.storage_dir
            url = f"http://127.0.0.1:{mc.cong}"
            c = mc.conn
            if c.execute("UPDATE users SET password_hash = %s WHERE username = 'gv_binh'", (auth.bam_mat_khau(MK),)).rowcount != 1:
                raise SystemExit("Thiếu tài khoản gv_binh.")
            st = c.execute("SELECT status::text AS s FROM exams WHERE exam_id = %s", (KT,)).fetchone()
            if not st or st["s"] != "draft":
                raise SystemExit(f"DỪNG: cần kỳ thi {KT} đang mở, có: {st}")
            nk0 = c.execute("SELECT count(*) AS n FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat'").fetchone()["n"]
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                may_tinh(b, url, k, g, tt)
                man_nho(b, url, k, g)
                b.close()
            # máy chủ đã rảnh: đọc nhật ký trên chính giao dịch thử (sẽ rollback)
            nk = c.execute("SELECT details FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat' ORDER BY log_id").fetchall()[nk0:]
            g["nhat_ky_hang_loat"] = [r["details"] for r in nk]
            k["nhat_ky_moi_lan_hang_loat_mot_dong"] = len(nk) == g.get("so_lan_hang_loat")
    finally:
        if kho and Path(kho).exists():
            shutil.rmtree(kho, ignore_errors=True)
        g["thu_muc_tam_da_xoa"] = bool(kho) and not Path(kho).exists()
    g["so_phieu_sau"] = sau = dem_phieu()
    k["so_phieu_4_ky_thi_khong_doi"] = truoc == sau
    k["thu_muc_tam_da_xoa"] = g["thu_muc_tam_da_xoa"]
    ket["dat"] = all(k.values())
    (OUT / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return ket


def may_tinh(b, url, k, g, tt):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="vi-VN")
    pg = ctx.new_page()
    hop = []
    pg.on("dialog", lambda d: (hop.append(d.message), d.dismiss()))           # hộp confirm() gốc của trình duyệt: không ngờ tới -> từ chối
    pg.goto(url + "/app/"); _dang_nhap(pg, "gv_binh")
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT}")):
        pg.select_option("#exam-select", str(KT))
    ids = {ten: _tai(pg, url, ten)["sheet_id"] for ten in ("BV07.jpg", "BV09.jpg", "BV06.jpg", "BV10.jpg")}
    g["phieu_tai"] = ids
    api = lambda p: pg.request.get(url + p).json()                             # noqa: E731
    g["cau_can_xem_luc_tai"] = {t: len(api(f"/sheets/{s}/review-questions")) for t, s in ids.items()}

    # ---------------- AF4 hàng đợi lọc / nhóm
    pg.goto(url + "/app/#/review"); _cho_h2(pg, "Hàng đợi duyệt"); pg.wait_for_selector("#loc-nhom")
    pg.screenshot(path=str(OUT / "01_hang_doi_nhom.png"), full_page=True)
    g["nhom_hang_doi"] = pg.evaluate("() => [...document.querySelectorAll('#main tbody tr')].map((r) => [r.cells[0].innerText.trim(), r.dataset.nhom])")
    k["hang_doi_co_loc_theo_ly_do"] = pg.locator("#loc-nhom option").count() >= 2
    pg.select_option("#loc-nhom", "dinh_danh")                                 # chờ bảng VẼ LẠI (bảng cũ cũng có dòng dinh_danh)
    pg.wait_for_function("() => { const r = [...document.querySelectorAll('#main tbody tr')]; return r.length && r.every((x) => x.dataset.nhom === 'dinh_danh'); }")
    k["loc_dinh_danh_chi_con_bv10"] = pg.evaluate("() => [...document.querySelectorAll('#main tbody tr')].map((r) => parseInt(r.cells[0].innerText, 10))") == [ids["BV10.jpg"]]
    pg.screenshot(path=str(OUT / "02_hang_doi_loc_sbd.png"), full_page=True)
    pg.select_option("#loc-nhom", "")

    # ---------------- TRƯỚC: BV09 theo cách cũ (bấm "Xác nhận như máy đọc" từng câu)
    s9, d = ids["BV09.jpg"], DemThaoTac()
    mo_tu_hang_doi(pg, url, s9, d)
    n9 = con_lai(pg)
    while con_lai(pg):
        n = con_lai(pg)
        d.bam(pg, '.rcard:not(.done) [data-act="confirm"]', "Xác nhận như máy đọc (1 câu)")
        cho_con_lai(pg, n - 1)
    pg.wait_for_selector("text=Đã chốt điểm chính thức")
    tt["cu_bv09"] = {"so_cau_co": n9, "thao_tac": d.n + 1, "chi_tiet": d.nhat_ky + ["bấm Phiếu cần xem kế tiếp"]}
    g["bv09_sau"] = {"status": api(f"/sheets/{s9}")["status"]}

    # ---------------- SAU: BV07 bằng xác nhận hàng loạt
    s7, d = ids["BV07.jpg"], DemThaoTac()
    mo_tu_hang_doi(pg, url, s7, d)
    _cho_anh(pg)
    n7 = con_lai(pg)
    k["co_goi_y_phim_tat"] = "Space" in pg.inner_text("#goi-y-phim") and "Enter" in pg.inner_text("#goi-y-phim")
    nhan = pg.locator(".rcard:not(.done) .nhan-cau").first.inner_text()
    g["nhan_cau_vi_du"] = nhan
    k["nhan_may_doc_dau_hieu"] = "Máy đọc:" in nhan and "Dấu hiệu:" in nhan
    pg.screenshot(path=str(OUT / "03_duyet_bv07_truoc_hang_loat.png"), full_page=False)
    truoc7 = api(f"/sheets/{s7}/review-questions")
    pg.click("#xn-tat-ca")                                                     # lần mở hộp này chỉ để KIỂM "Enter = Huỷ" – không tính thao tác
    d.nhat_ky.append("(kiểm thử) mở hộp lần 1 – không tính")
    pg.wait_for_selector("#dlg-hl")
    k["hop_nut_xac_nhan_khoa_ban_dau"] = pg.is_disabled("#hl-ok")
    k["hop_tieu_diem_o_huy"] = pg.evaluate("() => document.activeElement && document.activeElement.id") == "hl-huy"
    k["hop_liet_ke_dung_so_cau"] = pg.locator("#dlg-hl .ds-hl li").count() == n7 == len(truoc7)
    k["hop_canh_bao_khong_hoan_tac"] = "Không hoàn tác được" in pg.inner_text("#dlg-hl")
    g["hop_dong_dau"] = pg.locator("#dlg-hl .ds-hl li").first.inner_text()
    pg.screenshot(path=str(OUT / "04_hop_xac_nhan.png"), full_page=False)
    pg.keyboard.press("Enter")                                                 # Enter khi tiêu điểm ở "Huỷ" -> đóng, KHÔNG gửi
    pg.wait_for_selector("#dlg-hl", state="detached")
    k["enter_trong_hop_la_huy_khong_gui"] = len(api(f"/sheets/{s7}/review-questions")) == len(truoc7)
    d.nhat_ky.append("(kiểm thử) Enter trong hộp = Huỷ – không tính vào số thao tác")
    d.bam(pg, "#xn-tat-ca", "Xác nhận tất cả … (mở hộp)")
    pg.wait_for_selector("#dlg-hl")
    d.bam(pg, "#hl-da-xem", "tích 'Tôi đã nhìn ảnh từng câu'")
    k["hop_tich_xong_moi_mo_nut"] = pg.is_enabled("#hl-ok")
    pg.screenshot(path=str(OUT / "05_hop_da_tich.png"), full_page=False)
    d.bam(pg, "#hl-ok", f"Xác nhận {n7} câu")
    pg.wait_for_selector("text=Đã chốt điểm chính thức", timeout=60000)
    v7 = api(f"/sheets/{s7}")
    k["bv07_chot_diem_chinh_thuc"] = v7["status"] == "graded" and v7["score"]["official"] is not None
    k["bv07_moi_cau_nhu_may_doc"] = all(q["selected_options"] == (q["omr_selected_options"] or "") and not q["manually_edited"]
                                         for q in v7["questions"] if q["question_no"] in {c["question_no"] for c in truoc7})
    pg.screenshot(path=str(OUT / "06_bv07_da_chot.png"), full_page=False)
    d.phim(pg, "n", "(phiếu cần xem kế tiếp)")
    pg.wait_for_function("(s) => !location.hash.endsWith('/' + s)", arg=str(s7))
    k["phim_n_sang_phieu_ke"] = pg.evaluate("() => location.hash").startswith("#/review/")
    tt["moi_bv07_hang_loat"] = {"so_cau_co": n7, "thao_tac": d.n, "chi_tiet": d.nhat_ky}
    g["so_lan_hang_loat"] = 1

    # ---------------- SAU: BV06 chỉ bằng bàn phím
    s6, d = ids["BV06.jpg"], DemThaoTac()
    pg.goto(url + f"/app/#/review/{s6}"); _cho_h2(pg, f"Duyệt phiếu #{s6}"); pg.wait_for_timeout(300)
    d.n += 1; d.nhat_ky.append("(mở phiếu: tính 1 như các cách khác)")
    n6 = con_lai(pg)
    ds6 = [c["question_no"] for c in api(f"/sheets/{s6}/review-questions")]
    k["the_hien_tai_la_cau_dau"] = pg.evaluate("() => (document.querySelector('.rcard.hien-tai') || {}).dataset?.q") == str(ds6[0])
    d.phim(pg, "Escape"); d.phim(pg, "c", "(chọn C)")
    k["phim_c_chon_o_c"] = pg.locator(".rcard.hien-tai .opts button.sel").all_inner_texts() == ["C"]
    d.phim(pg, "Enter", "(lưu C, sang câu kế)")
    cho_con_lai(pg, n6 - 1)
    q0 = next(q for q in api(f"/sheets/{s6}")["questions"] if q["question_no"] == ds6[0])
    k["enter_luu_lua_chon_tay"] = q0["selected_options"] == "C" and not q0["needs_review"]
    if n6 > 1:
        k["sau_enter_sang_cau_ke"] = pg.evaluate("() => (document.querySelector('.rcard.hien-tai') || {}).dataset?.q") == str(ds6[1])
    while con_lai(pg):
        n = con_lai(pg)
        d.phim(pg, " ", "(Space: xác nhận như máy đọc)")
        cho_con_lai(pg, n - 1)
    v6 = api(f"/sheets/{s6}")
    k["space_xac_nhan_nhu_may_doc"] = all(q["selected_options"] == (q["omr_selected_options"] or "") for q in v6["questions"] if q["question_no"] in ds6[1:])
    d.phim(pg, "n", "(phiếu kế)")
    tt["moi_bv06_ban_phim"] = {"so_cau_co": n6, "thao_tac": d.n, "chi_tiet": d.nhat_ky}

    # ---------------- BV10: hàng loạt KHÔNG đụng SBD; phím tắt không cướp phím trong ô SBD
    s10 = ids["BV10.jpg"]
    pg.goto(url + f"/app/#/review/{s10}"); _cho_h2(pg, f"Duyệt phiếu #{s10}"); pg.wait_for_selector("#in-sbd")
    v0 = api(f"/sheets/{s10}")
    pg.focus("#in-sbd"); pg.keyboard.type("2n")
    k["phim_trong_o_sbd_khong_bi_cuop"] = pg.evaluate("() => location.hash") == f"#/review/{s10}" and pg.input_value("#in-sbd").endswith("2n")
    pg.fill("#in-sbd", "")
    if pg.locator("#xn-tat-ca").count():
        pg.click("#xn-tat-ca"); pg.wait_for_selector("#dlg-hl")
        g["bv10_hop"] = pg.inner_text("#dlg-hl")
        k["bv10_hop_bao_con_muc_khac"] = "chưa có điểm chính thức" in g["bv10_hop"]
        pg.click("#hl-da-xem"); pg.click("#hl-ok")
        pg.wait_for_selector("#dlg-hl", state="detached"); pg.wait_for_selector("#in-sbd")
        g["so_lan_hang_loat"] += 1
    v10 = api(f"/sheets/{s10}")
    k["bv10_sbd_khong_doi"] = v10["sbd"] == v0["sbd"] and v10["exam_code"] == v0["exam_code"] and v10["student"] == v0["student"]
    k["bv10_van_can_xem_chua_diem"] = v10["status"] == "needs_review" and v10["score"]["official"] is None
    k["bv10_o_sbd_van_trong_va_con_khung"] = pg.input_value("#in-sbd") == "" and pg.locator("#khung-dd").count() == 1
    pg.screenshot(path=str(OUT / "07_bv10_sau_hang_loat.png"), full_page=True)
    k["khong_hop_confirm_goc_bat_ngo"] = not hop
    g["hop_confirm_goc"] = hop
    ctx.close()


def man_nho(b, url, k, g):
    """Chromium giả lập màn 393×851 (Pixel 7) – CHỈ chụp màn duyệt + hộp xác nhận để xem bằng mắt (không phải Safari iPhone)."""
    ctx = b.new_context(viewport={"width": 393, "height": 851}, device_scale_factor=2.75, is_mobile=True, has_touch=True, locale="vi-VN")
    pg = ctx.new_page()
    pg.goto(url + "/app/"); _dang_nhap(pg, "gv_binh")
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT}")):
        pg.select_option("#exam-select", str(KT))
    s = _tai(pg, url, "BV08.jpg")["sheet_id"]
    pg.goto(url + f"/app/#/review/{s}"); _cho_h2(pg, f"Duyệt phiếu #{s}"); time.sleep(0.5)
    pg.screenshot(path=str(OUT / "08_man_nho_duyet.png"), full_page=True)
    if pg.locator("#xn-tat-ca").count():
        pg.click("#xn-tat-ca"); pg.wait_for_selector("#dlg-hl")
        bb = pg.locator("#dlg-hl .modal-box").bounding_box()
        k["man_nho_hop_vua_ngang"] = bb is not None and bb["x"] >= 0 and bb["x"] + bb["width"] <= 393 + 1
        k["man_nho_khong_cuon_ngang"] = pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        pg.screenshot(path=str(OUT / "09_man_nho_hop.png"), full_page=False)
        pg.click("#hl-huy")
    ctx.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kq = chay()
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    sys.exit(0 if kq["dat"] else 1)
