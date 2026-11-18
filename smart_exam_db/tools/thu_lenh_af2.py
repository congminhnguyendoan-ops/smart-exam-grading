import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"
import thu_dien_thoai as T  # noqa: E402
from thu_lenh_aa import KT, _cho_anh, _cho_h2, _dang_nhap, _tai, dem_phieu  # noqa: E402
from thu_lenh_af import MK, DemThaoTac, cho_con_lai, con_lai, mo_tu_hang_doi  # noqa: E402

OUT = ROOT / "data" / "_eval" / "ui_af2"
TRONG_HOP = "() => !!document.activeElement && !!document.activeElement.closest('#dlg-hl')"


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
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                may_tinh(b, url, k, g, tt)
                b.close()
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
    pg.on("dialog", lambda d: (hop.append(d.message), d.dismiss()))
    pg.goto(url + "/app/"); _dang_nhap(pg, "gv_binh")
    with pg.expect_response(lambda r: r.url.endswith(f"/exams/{KT}")):
        pg.select_option("#exam-select", str(KT))
    ids = {ten: _tai(pg, url, ten)["sheet_id"] for ten in ("BV07.jpg", "BV09.jpg", "BV02.jpg")}
    g["phieu_tai"] = ids
    api = lambda p: pg.request.get(url + p).json()                             # noqa: E731
    ly = {t: [x["reasons"] for x in api(f"/sheets/{s}/review-questions")] for t, s in ids.items()}
    g["ly_do_luc_tai"] = ly
    hop_le = {t: sum(1 for r in v if r and set(r) <= {"nhieu_o", "to_nhat"}) for t, v in ly.items()}
    g["so_cau_hop_le"] = hop_le

    s9, d = ids["BV09.jpg"], DemThaoTac()
    mo_tu_hang_doi(pg, url, s9, d); _cho_anh(pg)
    k["bv09_khong_co_nut_hang_loat"] = hop_le["BV09.jpg"] == 0 and pg.locator("#xn-tat-ca").count() == 0
    k["bv09_co_giai_thich_cau_mo_vet"] = "Câu mờ / vết cần quyết định bằng mắt" in pg.inner_text("#khung-nhanh")
    pg.screenshot(path=str(OUT / "01_bv09_khong_nut.png"), full_page=False)
    n9 = con_lai(pg)
    while con_lai(pg):
        n = con_lai(pg)
        d.bam(pg, '.rcard:not(.done) [data-act="confirm"]', "Xác nhận như máy đọc (1 câu)")
        cho_con_lai(pg, n - 1)
    pg.wait_for_selector("text=Đã chốt điểm chính thức")
    d.phim(pg, "n", "(phiếu kế)")
    tt["bv09"] = {"so_cau_co": n9, "thao_tac": d.n, "chi_tiet": d.nhat_ky}

    s2 = ids["BV02.jpg"]
    pg.goto(url + f"/app/#/review/{s2}"); _cho_h2(pg, f"Duyệt phiếu #{s2}"); pg.wait_for_timeout(300)
    g["bv02_nut"] = pg.inner_text("#xn-tat-ca") if pg.locator("#xn-tat-ca").count() else None
    k["bv02_nut_dem_dung_cau_hop_le"] = (g["bv02_nut"] == f"Xác nhận {hop_le['BV02.jpg']} câu nhiều ô / tô nhạt như máy đọc…") if hop_le["BV02.jpg"] \
        else g["bv02_nut"] is None
    pg.screenshot(path=str(OUT / "02_bv02_nut.png"), full_page=False)

    s7, d = ids["BV07.jpg"], DemThaoTac()
    mo_tu_hang_doi(pg, url, s7, d); _cho_anh(pg)
    n7 = con_lai(pg)
    k["bv07_nhan_nut"] = pg.inner_text("#xn-tat-ca") == f"Xác nhận {n7} câu nhiều ô / tô nhạt như máy đọc…" == f"Xác nhận {hop_le['BV07.jpg']} câu nhiều ô / tô nhạt như máy đọc…"
    pg.focus("#xn-tat-ca"); pg.keyboard.press("Enter")
    pg.wait_for_selector("#dlg-hl")
    k["hop_role_aria"] = pg.evaluate("""() => { const h = document.querySelector('#dlg-hl'); return h.getAttribute('role') === 'dialog'
        && h.getAttribute('aria-modal') === 'true' && !!document.getElementById(h.getAttribute('aria-labelledby'))
        && !!document.getElementById(h.getAttribute('aria-describedby')); }""")
    k["hop_tieu_diem_o_huy"] = pg.evaluate("() => document.activeElement.id") == "hl-huy"
    k["hop_nut_khoa"] = pg.is_disabled("#hl-ok")
    so_phan_tu = pg.evaluate("() => document.querySelectorAll('#dlg-hl a[href], #dlg-hl button:not([disabled]), #dlg-hl input:not([disabled])').length")
    trong = []
    for _ in range(so_phan_tu + 5):
        pg.keyboard.press("Tab"); trong.append(pg.evaluate(TRONG_HOP))
    for _ in range(so_phan_tu + 5):
        pg.keyboard.press("Shift+Tab"); trong.append(pg.evaluate(TRONG_HOP))
    k["bay_tab_va_shift_tab"] = all(trong)
    g["so_buoc_tab_kiem"] = len(trong)
    pg.focus("#hl-huy"); pg.keyboard.press("Tab")
    k["tab_tu_huy_xoay_ve_dau"] = pg.evaluate("() => document.activeElement === document.querySelector('#dlg-hl a[href]')")
    pg.mouse.click(5, 5)
    pg.keyboard.press("Tab")
    k["bay_tab_ca_khi_bam_nen"] = pg.evaluate(TRONG_HOP)
    pg.screenshot(path=str(OUT / "03_hop_bay_tab.png"), full_page=False)
    pg.keyboard.press("Escape")
    pg.wait_for_selector("#dlg-hl", state="detached")
    k["esc_dong_va_tieu_diem_ve_nut"] = pg.evaluate("() => document.activeElement && document.activeElement.id") == "xn-tat-ca"
    k["esc_khong_gui_gi"] = len(api(f"/sheets/{s7}/review-questions")) == n7
    pg.keyboard.press("Enter"); pg.wait_for_selector("#dlg-hl")
    pg.keyboard.press("Enter"); pg.wait_for_selector("#dlg-hl", state="detached")
    k["enter_mac_dinh_la_huy"] = len(api(f"/sheets/{s7}/review-questions")) == n7
    d.bam(pg, "#xn-tat-ca", "Xác nhận … (mở hộp)"); pg.wait_for_selector("#dlg-hl")
    k["hop_canh_bao_khong_hoan_tac"] = "Không hoàn tác được" in pg.inner_text("#dlg-hl")
    k["hop_liet_ke_tung_cau"] = pg.locator("#dlg-hl .ds-hl li").count() == n7
    d.bam(pg, "#hl-da-xem", "tích 'đã nhìn ảnh'")
    d.bam(pg, "#hl-ok", f"Xác nhận {n7} câu")
    pg.wait_for_selector("text=Đã chốt điểm chính thức", timeout=60000)
    v7 = api(f"/sheets/{s7}")
    k["bv07_chot_diem"] = v7["status"] == "graded" and v7["score"]["official"] is not None
    d.phim(pg, "n", "(phiếu kế)")
    tt["bv07"] = {"so_cau_co": n7, "thao_tac": d.n, "chi_tiet": d.nhat_ky}
    k["bv07_van_5_thao_tac"] = d.n == 5
    k["khong_hop_confirm_goc"] = not hop
    ctx.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kq = chay()
    print(json.dumps({"dat": kq["dat"], "kiem": kq["kiem"], "thao_tac": {k: (v["so_cau_co"], v["thao_tac"]) for k, v in kq["thao_tac"].items()},
                      "ghi_chu": {k: kq["ghi_chu"][k] for k in ("so_cau_hop_le", "bv02_nut", "so_phieu_truoc", "so_phieu_sau") if k in kq["ghi_chu"]}},
                     ensure_ascii=False, indent=1, default=str))
    sys.exit(0 if kq["dat"] else 1)
