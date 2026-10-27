"""
thu_dien_thoai.py - Thử trang điện thoại /m (CHỤP LIÊN TỤC) bằng GIẢ LẬP (Playwright, Pixel 7: màn nhỏ, cảm ứng) + đo thời gian.

  python tools/thu_dien_thoai.py tao-anh        # ảnh ~12 MP giống ảnh chụp (3024×4032, phối cảnh, nền bàn), 5 bản / phiếu -> data/_eval/demo_bv/gia_12mp/
  python tools/thu_dien_thoai.py chay           # KHÔNG GHI THẬT: máy chủ trong tiến trình (127.0.0.1), MỘT kết nối không commit -> ROLLBACK;
                                                #   giáo viên tạm + kỳ thi gộp 4 mã đề (sao E1 + E2, dự thi 220001–220009) tạo trong giao dịch đó; ảnh vào thư mục tạm
Kịch bản: B) chụp bằng camera 20 tờ liên tiếp, mỗi 2 s một tờ (không chờ kết quả) · A) "Chọn nhiều ảnh" 20 tờ một lần · lỗi mạng -> Gửi lại ·
ảnh bị từ chối -> Chụp lại · ảnh trùng. Ảnh màn hình -> data/_eval/ui_m/lien_tuc/; số đo -> data/_eval/ui_m/lien_tuc/thoi_gian.json.
Thời gian đo qua loopback (127.0.0.1): KHÔNG gồm thời gian truyền ảnh qua Wi‑Fi. Không bao giờ chạy trên kỳ thi 1380 / 1381.
(Bản trước – chụp từng tờ, ảnh ở data/_eval/ui_m/ và ui_m/tap/ – là của giao diện cũ, giữ làm lịch sử.)
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
UI = ROOT / "data" / "_eval" / "ui_m" / "lien_tuc"
MK_TAM = "MatKhau-Thu-Dien-Thoai-1"
SO_BAN = 5                                              # v1, v2: chụp camera · v3, v4: chọn nhiều ảnh · v5: chụp lại tờ bị từ chối
NHIP_GIAY = 2.0                                         # chụp camera: một tờ mỗi 2 s (nhanh hơn thực tế: lật tờ + căn khung thường 3–5 s)


# ------------------------------------------------------------------------------------------------ ảnh ~12 MP
def tao_anh(vong: int = SO_BAN) -> None:
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


# ------------------------------------------------------------------------------------------------ máy chủ trong tiến trình (ROLLBACK)
def cong_trong() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class MayChuThu:
    """uvicorn ở 127.0.0.1 trong luồng nền; mọi yêu cầu dùng chung MỘT kết nối không commit -> ROLLBACK khi tắt; ảnh vào thư mục tạm."""

    def __init__(self):
        import uvicorn

        from backend.config import lay_cau_hinh
        from backend.db import ket_noi
        from backend.main import app, get_cau_hinh, get_conn
        self.app = app
        self.cfg = replace(lay_cau_hinh(), storage_dir=Path(tempfile.mkdtemp(prefix="kho_dien_thoai_")))
        self.conn = ket_noi()

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
        self.conn.rollback()                                                 # KHÔNG ghi thật
        self.conn.close()


def dung_du_lieu_tam(conn) -> dict:
    """Trong giao dịch sẽ ROLLBACK: giáo viên tạm (mật khẩu biết trước) phụ trách K22A, MỘT kỳ thi gộp 4 mã đề 101–104 (đáp án E1 + E2),
    dự thi 220001–220009 (220010 cố ý ngoài danh sách như BV10) – để 20 tờ chụp liền một phiên như một lớp thật."""
    from backend import auth, service
    from nap_bo_demo import DU_THI
    uid = conn.execute("INSERT INTO users (username, email, password_hash, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'teacher', TRUE) "
                       "RETURNING user_id", ("gv_thu_dt", "gv_thu_dt@test.local", auth.bam_mat_khau(MK_TAM), "GV thử điện thoại")).fetchone()["user_id"]
    lop = conn.execute("SELECT class_id FROM classes WHERE class_code = 'CNTT-K22A'").fetchone()["class_id"]
    conn.execute("INSERT INTO teacher_classes (user_id, class_id) VALUES (%s, %s)", (uid, lop))
    eid = service.tao_ky_thi(conn, {"exam_title": "Giữa kỳ – chụp liên tục [THỬ ĐIỆN THOẠI]", "subject_code": "IT3080", "num_questions": 40, "max_score": 10,
                                    "pass_score": 5, "class_id": lop, "codes": [{"code": r["exam_code"], "answers": r["answers"]} for r in K.doc(K.DAP_AN)]}, uid)
    conn.execute("INSERT INTO exam_students (exam_id, student_id) SELECT %s, student_id FROM students WHERE student_code = ANY(%s)",
                 (eid, DU_THI["E1"] + DU_THI["E2"]))
    return {"username": "gv_thu_dt", "mat_khau": MK_TAM, "exam_id": eid}


# ------------------------------------------------------------------------------------------------ kịch bản trình duyệt
JS_TO = """() => window.__hangDoi.ds.map(t => ({stt: t.stt, soTo: t.soTo, ten: t.ten, trangThai: t.trangThai, lanGui: t.lanGui, an: t.an,
  tChup: t.tChup, tBatDau: t.tBatDau, tXong: t.tXong, status: t.ketQua && t.ketQua.status, sheet: t.ketQua && t.ketQua.sheet_id,
  daTonTai: t.ketQua && t.ketQua.da_ton_tai, thayCho: t.thayCho, thayBang: t.thayBang}))"""


def pct(g: list[float], q: float) -> float:
    g = sorted(g)
    return round(g[min(len(g) - 1, int(round(q * (len(g) - 1))))], 2)


def thong_ke(ds: list[dict], ten: str) -> dict:
    xu_ly = [(t["tXong"] - t["tBatDau"]) / 1000 for t in ds if t["tXong"]]
    tre = [(t["tXong"] - t["tChup"]) / 1000 for t in ds if t["tXong"]]
    tong = (max(t["tXong"] for t in ds if t["tXong"]) - min(t["tChup"] for t in ds)) / 1000
    return {"kich_ban": ten, "so_to": len(ds), "tong_giay": round(tong, 1), "loi": sum(t["trangThai"] == "loi" for t in ds),
            "xu_ly_moi_to_p50": round(statistics.median(xu_ly), 2), "xu_ly_moi_to_p95": pct(xu_ly, 0.95),
            "chup_den_ket_qua_p50": round(statistics.median(tre), 2), "chup_den_ket_qua_p95": pct(tre, 0.95), "chup_den_ket_qua_max": round(max(tre), 2),
            "trang_thai": {s: sum((t["status"] or t["trangThai"]) == s for t in ds) for s in {t["status"] or t["trangThai"] for t in ds}}}


def chay() -> dict:
    from playwright.sync_api import sync_playwright
    if not all((GIA_12 / f"BV{i:02d}_v{SO_BAN}.jpg").exists() for i in range(1, 11)):
        tao_anh()
    UI.mkdir(parents=True, exist_ok=True)
    ket = {"che_do": "rollback", "anh": "3024×4032 JPEG q92 giả hoá (data/_eval/demo_bv/gia_12mp), ~2,3 MB", "mang": "loopback 127.0.0.1 (không gồm Wi‑Fi)",
           "thiet_bi": "Playwright Chromium, giả lập Pixel 7", "song_song": 2, "ghi_chu": []}
    with MayChuThu() as mc:
        url = f"http://127.0.0.1:{mc.cong}"
        dl = dung_du_lieu_tam(mc.conn)
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            dt = b.new_context(**pw.devices["Pixel 7"], locale="vi-VN")
            pg = dt.new_page()

            def chup(ten, dau=False):
                if dau:
                    pg.evaluate("() => window.scrollTo(0, 0)")
                pg.wait_for_timeout(400)
                pg.screenshot(path=str(UI / ten))

            def cho_het(gioi_han=300):
                pg.wait_for_function("() => !window.__hangDoi.dangBan()", timeout=gioi_han * 1000)

            ds_moi = lambda tu: [t for t in pg.evaluate(JS_TO) if t["stt"] > tu]     # noqa: E731
            stt_cuoi = lambda: max([t["stt"] for t in pg.evaluate(JS_TO)] or [0])    # noqa: E731

            pg.goto(url + "/m")
            pg.wait_for_selector("#v-login:not(.hidden)")
            pg.fill("#lg-user", dl["username"]); pg.fill("#lg-pass", dl["mat_khau"]); pg.tap("#f-login button")
            pg.wait_for_selector(f".exam[data-id='{dl['exam_id']}']")
            pg.click(f".exam[data-id='{dl['exam_id']}']")
            pg.wait_for_selector("#v-cap:not(.hidden)")
            pg.fill("#tong-to", "40"); pg.dispatch_event("#tong-to", "change")
            chup("01_bat_dau.png")

            # B) chụp bằng camera: 20 tờ, mỗi NHIP_GIAY giây một tờ, KHÔNG chờ kết quả tờ trước
            tu = stt_cuoi()
            anh_b = [GIA_12 / f"BV{i:02d}_v{v}.jpg" for v in (1, 2) for i in range(1, 11)]
            t0 = time.perf_counter()
            for k, a in enumerate(anh_b):
                pg.set_input_files("#cam", str(a))
                if k == 5:
                    chup("02_dang_chup_lien_tuc.png")                         # đang chụp: tờ đã chấm / đang chấm / đang gửi / chờ
                time.sleep(NHIP_GIAY)
            ket["thoi_gian_chup_20_to_giay"] = round(time.perf_counter() - t0, 1)
            cho_het()
            ket["B_camera_moi_2s"] = thong_ke(ds_moi(tu), "B: camera, 20 tờ, mỗi 2 s một tờ")
            chup("03_xong_20_to_dau.png", dau=True)
            pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)"); chup("04_xong_20_to_cuoi.png")

            # A) chọn nhiều ảnh: 20 tờ một lần (dồn tải nặng nhất)
            tu = stt_cuoi()
            pg.set_input_files("#nhieu", [str(GIA_12 / f"BV{i:02d}_v{v}.jpg") for v in (3, 4) for i in range(1, 11)])
            pg.wait_for_timeout(1500); chup("05_chon_nhieu_dang_gui.png", dau=True)
            cho_het()
            ket["A_chon_nhieu_20"] = thong_ke(ds_moi(tu), "A: chọn nhiều ảnh, 20 tờ một lần")

            # lỗi mạng -> Gửi lại (ảnh giữ trên máy, không chụp lại)
            tu = stt_cuoi()
            dt.set_offline(True)
            pg.set_input_files("#cam", str(GIA_12 / "BV01_v5.jpg"))
            pg.set_input_files("#cam", str(GIA_12 / "BV02_v5.jpg"))
            pg.wait_for_function(f"() => window.__hangDoi.ds.filter(t => t.stt > {tu} && t.trangThai === 'loi').length === 2", timeout=30000)
            pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)"); chup("06_loi_mang.png")
            dt.set_offline(False)
            for nut in pg.query_selector_all("[data-gui-lai]"):
                nut.click()
            cho_het()
            lai = ds_moi(tu)
            ket["loi_mang_gui_lai"] = {"to": len(lai), "sau_gui_lai": [t["status"] for t in lai], "lan_gui": [t["lanGui"] for t in lai]}
            pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)"); chup("07_sau_gui_lai.png")

            # ảnh bị từ chối -> Chụp lại (đúng ô chọn tệp trong dòng đó)
            import cv2
            import numpy as np
            trang = UI / "_anh_trang.jpg"
            cv2.imencode(".jpg", np.full((4032, 3024, 3), 228, np.uint8))[1].tofile(trang)
            tu = stt_cuoi()
            pg.set_input_files("#cam", str(trang)); cho_het()
            pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)"); chup("08_tu_choi.png")
            o = pg.query_selector("[data-chup-lai]")
            o.set_input_files(str(GIA_12 / "BV03_v5.jpg")); cho_het()
            pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)"); chup("09_chup_lai.png")
            ket["tu_choi_chup_lai"] = [{k: t[k] for k in ("soTo", "status", "thayCho", "thayBang")} for t in ds_moi(tu)]
            trang.unlink(missing_ok=True)

            # ảnh trùng (gửi lại đúng tệp tờ 1): không lặp dòng, không tính chấm được
            truoc = pg.evaluate("() => window.__hangDoi.tong()")
            tu = stt_cuoi()
            pg.set_input_files("#cam", str(anh_b[0])); cho_het()
            sau = pg.evaluate("() => window.__hangDoi.tong()")
            chup("10_anh_trung.png")
            ket["anh_trung"] = {"truoc": truoc, "sau": sau, "dong": ds_moi(tu)}
            chup("11_tong_ket.png", dau=True)
            ket["tong_ket_phien"] = sau
            b.close()
        so = mc.conn.execute("SELECT a.status::text AS s, count(*) AS n FROM answer_sheets a WHERE a.exam_id = %s GROUP BY 1 ORDER BY 1", (dl["exam_id"],)).fetchall()
        ket["phieu_trong_giao_dich"] = {r["s"]: r["n"] for r in so}
    (UI / "thoi_gian.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1), encoding="utf-8")
    return ket


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["tao-anh", "chay"])
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.lenh == "tao-anh":
        tao_anh()
        return 0
    kq = chay()
    print(json.dumps({k: v for k, v in kq.items() if k not in ("anh_trung",)}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
