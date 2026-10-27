"""
thu_dien_thoai.py - Thử trang điện thoại /m bằng GIẢ LẬP (Playwright, Pixel 7: màn nhỏ, cảm ứng) + đo thời gian bấm tải → hiện kết quả.

  python tools/thu_dien_thoai.py tao-anh                 # ảnh ~12 MP giống ảnh chụp (3024×4032, phối cảnh, nền bàn) -> data/_eval/demo_bv/gia_12mp/
  python tools/thu_dien_thoai.py chay                    # MẶC ĐỊNH KHÔNG GHI THẬT: máy chủ trong tiến trình (127.0.0.1), MỘT kết nối không commit -> ROLLBACK;
                                                         #   giáo viên tạm + 2 kỳ thi sao E1/E2 tạo trong giao dịch đó; ảnh lưu thư mục tạm
  python tools/thu_dien_thoai.py chay --ky-thi-tap 1500 1501 --ghi-that   # (sau khi người dùng đồng ý) trên kỳ thi TẬP [DEMO-BV-TẬP], ghi thật
Ảnh chụp màn hình -> data/_eval/ui_m/; số đo -> data/_eval/ui_m/thoi_gian.json. Không bao giờ chạy trên kỳ thi 1380 / 1381 (demo bảo vệ).
Thời gian đo qua loopback (127.0.0.1): KHÔNG gồm thời gian truyền ảnh qua Wi‑Fi của điện thoại thật.
"""
import argparse
import json
import os
import socket
import statistics
import sys
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"
os.environ["ANH_XOA_TU_DONG"] = "0"                     # thử nghiệm không bao giờ dọn ảnh thật

import kiem_bo_demo as K  # noqa: E402

GIA = ROOT / "data" / "_eval" / "demo_bv" / "gia"
GIA_12 = ROOT / "data" / "_eval" / "demo_bv" / "gia_12mp"
UI = ROOT / "data" / "_eval" / "ui_m"
CAM = {"1380", "1381"}
MK_TAM = "MatKhau-Thu-Dien-Thoai-1"


# ------------------------------------------------------------------------------------------------ ảnh ~12 MP
def tao_anh(vong: int = 2) -> None:
    """Mỗi phiếu BVxx: `vong` ảnh 3024×4032 khác nhau (góc nghiêng / ánh sáng / nhiễu khác -> SHA khác, không bị coi là ảnh trùng)."""
    import cv2
    import numpy as np
    if not all((GIA / f"{p['sheet_id']}.jpg").exists() for p in K.doc(K.KICH_BAN)):
        raise SystemExit("Thiếu ảnh phẳng – chạy python tools/thu_bo_demo.py tao-anh trước.")
    GIA_12.mkdir(parents=True, exist_ok=True)
    W, H = 3024, 4032
    for p in K.doc(K.KICH_BAN):
        phang = cv2.imdecode(np.fromfile(GIA / f"{p['sheet_id']}.jpg", np.uint8), cv2.IMREAD_GRAYSCALE)
        h0, w0 = phang.shape
        for v in range(vong):
            rng = np.random.default_rng(2026 * 100 + int(p["sheet_id"][2:]) * 10 + v)      # xác định: chạy lại ra cùng ảnh
            nen = (rng.normal(118, 9, (H, W)).astype(np.float32))
            nen = cv2.GaussianBlur(nen, (0, 0), 6)
            le = 230 + rng.integers(-40, 40)
            dich = lambda: rng.uniform(-70, 70)   # noqa: E731
            dst = np.float32([[le + dich(), 330 + dich()], [W - le + dich(), 300 + dich()], [W - le + 40 + dich(), H - 300 + dich()], [le - 30 + dich(), H - 330 + dich()]])
            M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w0, 0], [w0, h0], [0, h0]]), dst)
            giay = cv2.warpPerspective(phang.astype(np.float32), M, (W, H), flags=cv2.INTER_LINEAR, borderValue=-1)
            mat = cv2.warpPerspective(np.ones_like(phang, np.float32), M, (W, H), flags=cv2.INTER_NEAREST)
            anh = np.where(mat > 0, giay, nen)
            gx = np.linspace(rng.uniform(0.82, 0.92), rng.uniform(0.98, 1.05), W, dtype=np.float32)
            anh = anh * gx[None, :]                                          # ánh sáng không đều
            anh = cv2.GaussianBlur(anh, (0, 0), rng.uniform(0.8, 1.4))       # hơi mờ (ống kính / rung tay nhẹ)
            anh = np.clip(anh + rng.normal(0, 3.0, anh.shape), 0, 255).astype(np.uint8)
            bgr = cv2.cvtColor(anh, cv2.COLOR_GRAY2BGR)
            cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(GIA_12 / f"{p['sheet_id']}_v{v + 1}.jpg")
    print(f"Đã ghi {vong * 10} ảnh 3024×4032 ở {GIA_12}")


# ------------------------------------------------------------------------------------------------ máy chủ trong tiến trình
def cong_trong() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class MayChuThu:
    """uvicorn ở 127.0.0.1 trong luồng nền. ghi_that=False: mọi yêu cầu dùng chung MỘT kết nối không commit (ROLLBACK khi tắt)."""

    def __init__(self, ghi_that: bool):
        import uvicorn

        from backend.config import lay_cau_hinh
        from backend.db import ket_noi
        from backend.main import app, get_cau_hinh, get_conn
        self.app, self.ghi_that = app, ghi_that
        self.cfg = lay_cau_hinh() if ghi_that else replace(lay_cau_hinh(), storage_dir=Path(tempfile.mkdtemp(prefix="kho_dien_thoai_")))
        self.conn = None if ghi_that else ket_noi()
        if not ghi_that:
            def _conn():
                yield self.conn
            app.dependency_overrides[get_conn] = _conn
            app.dependency_overrides[get_cau_hinh] = lambda: self.cfg
        self.cong = cong_trong()
        self.sv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.cong, log_level="warning"))
        self.t = threading.Thread(target=self.sv.run, daemon=True)

    def __enter__(self):
        self.t.start()
        for _ in range(300):
            if self.sv.started:
                return self
            time.sleep(0.1)
        raise RuntimeError("máy chủ thử không khởi động")

    def __exit__(self, *a):
        self.sv.should_exit = True
        self.t.join(10)
        self.app.dependency_overrides.clear()
        if self.conn is not None:
            self.conn.rollback()                                             # KHÔNG ghi thật
            self.conn.close()


def dung_du_lieu_tam(conn) -> dict:
    """Trong giao dịch sẽ ROLLBACK: giáo viên tạm (mật khẩu biết trước) phụ trách K22A + K22B, 2 kỳ thi sao từ E1 / E2 + danh sách dự thi."""
    from backend import auth, service
    from nap_bo_demo import DU_THI
    u = "gv_thu_dt"
    uid = conn.execute("INSERT INTO users (username, email, password_hash, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'teacher', TRUE) "
                       "RETURNING user_id", (u, "gv_thu_dt@test.local", auth.bam_mat_khau(MK_TAM), "GV thử điện thoại")).fetchone()["user_id"]
    ky_thi = {}
    for e in ("E1", "E2"):
        rows = [r for r in K.doc(K.DAP_AN) if r["exam"] == e]
        r0 = rows[0]
        lop = conn.execute("SELECT class_id FROM classes WHERE class_code = %s", (r0["class_code"],)).fetchone()["class_id"]
        conn.execute("INSERT INTO teacher_classes (user_id, class_id) VALUES (%s, %s)", (uid, lop))
        eid = service.tao_ky_thi(conn, {"exam_title": r0["exam_title"].replace("[DEMO-BV]", "[THỬ ĐIỆN THOẠI]"), "subject_code": r0["subject_code"],
                                        "num_questions": 40, "max_score": 10, "pass_score": 5, "class_id": lop,
                                        "codes": [{"code": r["exam_code"], "answers": r["answers"]} for r in rows]}, uid)
        conn.execute("INSERT INTO exam_students (exam_id, student_id) SELECT %s, student_id FROM students WHERE student_code = ANY(%s)", (eid, DU_THI[e]))
        ky_thi[e] = eid
    return {"username": u, "mat_khau": MK_TAM, "user_id": uid, "ky_thi": ky_thi}


# ------------------------------------------------------------------------------------------------ kịch bản trình duyệt
def chay(ghi_that: bool, ky_thi_tap: list[int] | None) -> dict:
    from playwright.sync_api import sync_playwright

    from backend import auth
    if not all((GIA_12 / f"BV{i:02d}_v1.jpg").exists() for i in range(1, 11)):
        tao_anh()
    ui = UI / "tap" if ghi_that else UI                              # ghi thật: thư mục con, không đè ảnh của lần thử ROLLBACK
    ui.mkdir(parents=True, exist_ok=True)
    kb = {p["sheet_id"]: p for p in K.doc(K.KICH_BAN)}
    so_do, ghi_chu = [], []
    with MayChuThu(ghi_that) as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        if ghi_that:
            from backend.db import ket_noi
            with ket_noi() as c:
                rows = c.execute("SELECT e.exam_id, e.exam_title, e.created_by, u.username, u.password_hash FROM exams e JOIN users u ON u.user_id = e.created_by "
                                 "WHERE e.exam_id = ANY(%s) ORDER BY e.exam_id", (ky_thi_tap,)).fetchall()
            if len(rows) != 2 or any(str(r["exam_id"]) in CAM or "TẬP" not in r["exam_title"] for r in rows):
                raise SystemExit("DỪNG: --ghi-that chỉ chạy trên đúng 2 kỳ thi TẬP ([DEMO-BV-TẬP]), không bao giờ 1380 / 1381.")
            ky_thi = {"E1": next(r["exam_id"] for r in rows if "K22A" in r["exam_title"]), "E2": next(r["exam_id"] for r in rows if "K22B" in r["exam_title"])}
            gv = {r["exam_id"]: r for r in rows}
            dl = None
        else:
            dl = dung_du_lieu_tam(mc.conn)
            ky_thi = dl["ky_thi"]
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            dt = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
            pg = dt.new_page()
            pc = b.new_context(viewport={"width": 1280, "height": 860}, locale="vi-VN")

            def cookie_cho(ctx, uid, bam):
                ctx.add_cookies([{"name": auth.COOKIE, "value": auth.tao_token(mc.cfg.auth_secret, uid, bam, 1), "url": url}])

            def chup(ten):
                """Khung nhìn THẬT (đúng cái giáo viên thấy): ảnh cả trang làm nút cố định ở đáy đè lên nội dung."""
                pg.wait_for_timeout(700)                                     # để cuộn mượt của trang (lên đầu) chạy xong
                pg.screenshot(path=str(ui / ten))

            def tai(ten_anh: str, cho_ket_qua: bool = True) -> float:
                pg.evaluate("() => { const k = document.querySelector('#ket-qua'); k.innerHTML = ''; k.classList.add('hidden'); }")
                t0 = time.perf_counter()
                pg.set_input_files("#cam", str(ten_anh))
                if cho_ket_qua:
                    pg.wait_for_function("() => { const k = document.querySelector('#ket-qua'); return !k.classList.contains('hidden') && k.innerHTML.length > 0; }",
                                         timeout=120000)
                return time.perf_counter() - t0

            def chon(e):
                pg.click("#doi-ky-thi") if pg.is_visible("#doi-ky-thi") else None
                pg.wait_for_selector(f".exam[data-id='{ky_thi[e]}']")
                pg.click(f".exam[data-id='{ky_thi[e]}']")
                pg.wait_for_selector("#v-cap:not(.hidden)")

            # 1. đăng nhập (THẬT ở chế độ rollback: tài khoản tạm; ghi thật: cookie của giáo viên phụ trách kỳ thi)
            pg.goto(url + "/m")
            pg.wait_for_selector("#v-login:not(.hidden)")
            chup("01_dang_nhap.png")
            if dl:
                pg.fill("#lg-user", dl["username"]); pg.fill("#lg-pass", dl["mat_khau"]); pg.tap("#f-login button")
                cookie_cho(pc, dl["user_id"], mc.conn.execute("SELECT password_hash FROM users WHERE user_id = %s", (dl["user_id"],)).fetchone()["password_hash"])
            else:
                r1 = gv[ky_thi["E1"]]
                cookie_cho(dt, r1["created_by"], r1["password_hash"]); cookie_cho(pc, r1["created_by"], r1["password_hash"])
                pg.goto(url + "/m")
            pg.wait_for_selector("#v-exams:not(.hidden) .exam")
            chup("02_chon_ky_thi.png")
            chon("E1")
            chup("03_chup_trong.png")

            # máy tính: danh sách phiếu của E1 (tự làm mới) + hộp thoại kết nối
            mt = pc.new_page()
            mt.goto(url + "/app/#/sheets")
            mt.wait_for_selector("#exam-select option", state="attached")
            mt.select_option("#exam-select", str(ky_thi["E1"]))
            mt.wait_for_timeout(1500)
            mt.click("#ket-noi-dt"); mt.wait_for_selector("#dlg-dt-body .url-big, #dlg-dt-body .alert")
            mt.screenshot(path=str(ui / "12_may_tinh_ket_noi_dien_thoai.png")); mt.click("#dlg-dt-x")
            mt.goto(url + "/app/#/sheets"); mt.wait_for_timeout(5000)       # lượt thăm dò đầu = mốc

            # 2. chụp BV01 (chụp màn "đang chấm" ngay sau khi chọn ảnh)
            pg.evaluate("() => { const k = document.querySelector('#ket-qua'); k.innerHTML = ''; k.classList.add('hidden'); }")
            t0 = time.perf_counter()
            pg.set_input_files("#cam", str(GIA_12 / "BV01_v1.jpg"))
            try:
                pg.wait_for_selector("#dang-cham:not(.hidden)", timeout=3000); chup("04_dang_cham.png")
            except Exception:  # noqa: BLE001 – quá nhanh, không kịp chụp
                ghi_chu.append("không kịp chụp màn 'Đang chấm…'")
            pg.wait_for_function("() => !document.querySelector('#ket-qua').classList.contains('hidden')", timeout=120000)
            so_do.append({"anh": "BV01_v1", "giay": time.perf_counter() - t0})
            chup("05_ket_qua_BV01.png")
            mt.wait_for_selector("tr.moi", timeout=15000)                    # máy tính tự hiện phiếu mới (≤ 4 s + chấm)
            mt.screenshot(path=str(ui / "11_may_tinh_phieu_moi.png"))
            ghi_chu.append("máy tính tự hiện phiếu mới (tr.moi) không cần tải lại")

            for m in ("BV02", "BV03", "BV04", "BV05"):
                so_do.append({"anh": f"{m}_v1", "giay": tai(GIA_12 / f"{m}_v1.jpg")})
            # ảnh trùng
            tai(GIA_12 / "BV01_v1.jpg"); chup("09_anh_trung.png")
            # ảnh bị từ chối (ảnh trắng: không có marker)
            import cv2
            import numpy as np
            trang = ui / "_anh_trang.jpg"
            cv2.imencode(".jpg", np.full((4032, 3024, 3), 228, np.uint8))[1].tofile(trang)
            tai(trang); chup("08_tu_choi.png")
            chon("E2")
            for m in ("BV06", "BV07", "BV08", "BV09", "BV10"):
                so_do.append({"anh": f"{m}_v1", "giay": tai(GIA_12 / f"{m}_v1.jpg")})
                if m == "BV07":
                    chup("06_to_nhat_BV07.png")
                if m == "BV10":
                    chup("07_sbd_ngoai_ds_BV10.png")
            # vòng 2 (ảnh khác SHA) – thêm mẫu đo
            chon("E1")
            for i in range(1, 11):
                m = f"BV{i:02d}"
                if i == 6:
                    chon("E2")
                so_do.append({"anh": f"{m}_v2", "giay": tai(GIA_12 / f"{m}_v2.jpg")})
            chup("10_bo_dem_phien.png")
            # mất mạng
            dt.set_offline(True)
            tai(GIA_12 / "BV01_v2.jpg"); chup("13_mat_mang.png")
            dt.set_offline(False)
            trang.unlink(missing_ok=True)
            b.close()
        if dl:                                                              # tóm tắt kết quả CSDL trong giao dịch (trước rollback)
            ket = mc.conn.execute("SELECT a.status::text AS s, count(*) AS n FROM answer_sheets a WHERE a.exam_id = ANY(%s) GROUP BY 1 ORDER BY 1",
                                  (list(ky_thi.values()),)).fetchall()
            ghi_chu.append("phiếu trong giao dịch: " + ", ".join(f"{r['s']} {r['n']}" for r in ket))
    g = sorted(x["giay"] for x in so_do)
    kq = {"che_do": "ghi_that" if ghi_that else "rollback", "n": len(g), "p50_giay": round(statistics.median(g), 2),
          "p95_giay": round(g[min(len(g) - 1, int(round(0.95 * (len(g) - 1))))], 2), "max_giay": round(g[-1], 2), "min_giay": round(g[0], 2),
          "anh": "3024×4032 JPEG q92 giả hoá (data/_eval/demo_bv/gia_12mp)", "mang": "loopback 127.0.0.1 (không gồm Wi‑Fi)",
          "thiet_bi": "Playwright Chromium, giả lập Pixel 7", "ghi_chu": ghi_chu, "mau": so_do}
    (ui / "thoi_gian.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    return kq


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["tao-anh", "chay"])
    ap.add_argument("--ghi-that", action="store_true", help="ghi THẬT vào kỳ thi tập (cần --ky-thi-tap)")
    ap.add_argument("--ky-thi-tap", type=int, nargs=2, metavar=("E1_TAP", "E2_TAP"))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.lenh == "tao-anh":
        tao_anh()
        return 0
    if a.ghi_that != bool(a.ky_thi_tap):
        raise SystemExit("--ghi-that đi cùng --ky-thi-tap E1_TAP E2_TAP (và ngược lại).")
    kq = chay(a.ghi_that, a.ky_thi_tap)
    print(json.dumps({k: v for k, v in kq.items() if k != "mau"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
