"""
chay_demo.py - Lệnh AP (16/11/2026): MỘT LỆNH cho mỗi buổi demo theo môn.

  python tools/chay_demo.py xla     # Xử lý ảnh: công cụ đơn giản (không đăng nhập, không CSDL): chọn ảnh phiếu -> từng bước xử lý ảnh, câu cần xem + lý do, điểm tạm, CNN là gì
  python tools/chay_demo.py ml      # Máy học: dựng + mở trang demo_may_hoc (dữ liệu, lý thuyết CNN / CNN sâu, hai cấu trúc + mã, 11 thuật toán, chạy trực tiếp)
  python tools/chay_demo.py dacn    # Đồ án chuyên ngành: mở máy chủ như chay_server_lan.py (đăng nhập, kỳ [ĐACN], tải ảnh, duyệt, điểm, báo cáo) + trang "lý thuyết các môn"

Mỗi chế độ làm đủ: (1) kiểm nhánh git + SHA mô hình; (2) đặt lại dữ liệu CỦA ĐÚNG KỲ THI chế độ đó (tools/dat_lai_demo.py --ky-thi; sao lưu trước khi xoá);
(3) mở máy chủ / dựng trang; (4) tự mở trình duyệt; (5) in hướng dẫn "bấm gì, nói gì".
Tuỳ chọn: --chi-in (chỉ kiểm tra + in hướng dẫn, không đặt lại / không mở máy chủ / không mở trình duyệt) · --khong-dat-lai · --khong-mo · --bo-qua-kiem-tra · --cong N.
KHÔNG ghi mật khẩu: tài khoản demo do bạn đặt (docs/chay_server_va_tai_khoan.md mục 3). Chạy từ smart_exam_db\\ với venv gốc.
"""
import argparse
import email.parser
import email.policy
import hashlib
import html
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

NHANH_DUNG = ("main", "cnn-sau")       # CNN sâu có trên cả hai (gộp lệnh AS, 17/11/2026); điều quyết định là SHA mô hình
SHA_MO_HINH_OCR = "a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8"       # CNN sâu (lệnh AN)
XAC_NHAN = "DAT_LAI"
CHE_DO = ("xla", "ml", "dacn")
CONG_XLA, CONG_DACN = 8765, 8000
RA = ROOT / "data" / "_eval" / "demo_3_phien"
ANH_BV = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia"
ANH_THEM = [("T05_thuong.JPG", "ảnh chụp THẬT, chữ viết tay thật"), ("T03_kho.JPG", "ảnh chụp THẬT, điều kiện khó"),
            ("T05_mo_phong_nhe.jpg", "MÔ PHỎNG mờ nhẹ (không phải ảnh chụp mờ thật)"), ("T05_mo_phong_nang.jpg", "MÔ PHỎNG mờ nặng → bị từ chối")]
KICH_BAN_BV = ROOT / "answer_sheet" / "demo_bv" / "demo_bv_kich_ban.csv"
GIOI_HAN_TAI_LEN = 40 * 1024 * 1024


def e(s) -> str:
    return html.escape(str(s))


# ----------------------------------------------------------------------------------------------- (1) kiểm tra nhánh + mô hình
@dataclass
class Muc:
    ten: str
    dat: bool
    chi_tiet: str


def nhanh_hien_tai() -> str:
    return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def sha_mo_hinh(duong_dan: Path | None = None) -> str:
    p = duong_dan or ROOT / "models" / "ocr_cnn.json"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def kiem_truoc(nhanh: str | None = None, sha: str | None = None) -> list[Muc]:
    nhanh = nhanh_hien_tai() if nhanh is None else nhanh
    sha = sha_mo_hinh() if sha is None else sha
    return [Muc("Nhánh git", nhanh in NHANH_DUNG, f"đang ở '{nhanh}'" + ("" if nhanh in NHANH_DUNG else f" – demo này dùng CNN sâu nên phải ở nhánh '{NHANH_DUNG[0]}' hoặc '{NHANH_DUNG[1]}' (git switch {NHANH_DUNG[0]})")),
            Muc("Mô hình models/ocr_cnn.json", sha == SHA_MO_HINH_OCR,
                f"SHA {sha[:12] or 'THIẾU TỆP'}… " + ("khớp CNN sâu (lệnh AN)" if sha == SHA_MO_HINH_OCR else f"KHÁC {SHA_MO_HINH_OCR[:12]}… (không phải CNN sâu đã đo)"))]


# ----------------------------------------------------------------------------------------------- (2) đặt lại dữ liệu kỳ thi của chế độ
def dat_lai(che_do: str, in_ra=print) -> bool:
    """Đặt lại RIÊNG kỳ thi của chế độ về 0 phiếu (dat_lai_demo.dat_lai_ky: sao lưu CSV + ảnh trước khi xoá). True = ổn."""
    import dat_lai_demo as DL
    try:
        ma = DL.dat_lai_ky(che_do, DL.XAC_NHAN, in_ra=lambda s: in_ra("   " + str(s).replace("\n", "\n   ")))
    except Exception as ex:                                                                  # noqa: BLE001 – báo rõ nguyên nhân (thường: không nối được CSDL)
        in_ra(f"   Không đặt lại được ({type(ex).__name__}: {str(ex)[:160]})")
        return False
    return ma == 0


# ----------------------------------------------------------------------------------------------- (5) hướng dẫn
def huong_dan(che_do: str, url: str, url_phu: str = "") -> list[str]:
    """8–10 dòng 'bấm gì, nói gì'."""
    if che_do == "xla":
        return [f"1. Trang {url} đã mở: 'Chọn ảnh phiếu'. NÓI: công cụ này chạy ngoại tuyến, đúng hàm của hệ thống, không đăng nhập, không CSDL.",
                "2. BẤM BV01 (phiếu tốt). Cuộn bước 1–4: ảnh gốc → độ mờ → 4 góc → nắn về A4. NÓI: máy tìm 4 ô vuông đen rồi nắn phiếu về khung chuẩn.",
                "3. Cuộn bước 4b và 5: chuẩn hoá ánh sáng (bỏ bóng) và lưới ô. NÓI: nhờ lưới, toạ độ mọi ô biết trước; giấy cong thì dò lại từng hàng.",
                "4. Bước 6 (OMR): màu xanh = rõ, cam = mờ, khung đỏ = máy KHÔNG chắc. NÓI: câu không chắc không bao giờ được chấm tự động.",
                "5. Quay lại, BẤM BV03 (bỏ trống + tô hai ô): xem khung cảnh báo trên đầu trang, bảng câu cần xem + LÝ DO, bước 9 điểm tạm. NÓI: điểm tạm chưa phải điểm chính thức.",
                "6. BẤM BV07 (tô nhạt cả tờ) để thấy cờ 'tờ nhạt'; BV10 để thấy SBD ngoài danh sách (ảnh BV là giả hoá, không có chữ viết tay).",
                "7. Cuộn bước 10 'CNN là gì?' (hình + lời ngắn). Bước 7–8: ô chữ số thật + hai kênh bubble ↔ chữ viết tay (dùng ảnh T05_thuong cho chữ viết tay thật).",
                "8. BẤM 'Chọn tệp ảnh…' → data\\_eval\\demo_3_phien\\T05_mo_phong_nang.jpg: ảnh mờ bị TỪ CHỐI kèm lý do. NÓI: nắn sai mà vẫn chấm = ghi nhầm điểm.",
                "9. Dừng: Ctrl+C ở cửa sổ này."]
    if che_do == "ml":
        return [f"1. Trang {url} đã mở. Mục 1 'Dữ liệu': NÓI: MNIST 55 000 / 5 000 / 10 000, 3 872 ô thật từ 10 trang, 504 ô phiếu để đo, chỉ 5 người viết.",
                "2. Mục 2 'Hai mô hình': ô tô = hồi quy logistic 40 tham số; chữ số = CNN sâu 467 818 tham số.",
                "3. Mục 3 'CNN và CNN sâu – giải thích bằng lời': đọc ý chính: kính lúp (tích chập) → gộp → cộng điểm → 10 xác suất; học = chỉnh trọng số.",
                "4. Mục 4 'Hai mạng cạnh nhau': chỉ hai bảng kiến trúc và khối mã NumPy THẬT (rẽ nhánh a1w / c1w).",
                "5. Mục 5 'Vì sao chuyển sang CNN sâu': dev 83,63% so với 67,56%, val+test 41/48 so với 39/48. NÓI RÕ: 48 trường chưa có ý nghĩa thống kê; dev lạc quan; lỗi im lặng 0 nhờ hai kênh.",
                "6. Mục 'Chạy CNN sâu thật' (chạy lúc dựng trang): 485/504 ô; 24 ô ngẫu nhiên và 8 ô sai CHỌN CÓ CHỦ Ý. Mục 'So sánh TRỰC TIẾP': các thuật toán đọc cùng một ô.",
                "7. Mục '11 thuật toán' và 'Kích thước và tốc độ'. NÓI: mạng tích chập tốt nhất trong tập đã thử, không phải 'tối ưu'.",
                "8. Mục 'Kết quả không đạt': thêm 300 000 mẫu chỉ +0,36 điểm nên không dùng. Mục 'Giới hạn': đọc to.",
                "9. Dừng: không có máy chủ; chỉ cần đóng tab."]
    return [f"1. Trang web {url} đã mở (cùng một máy chủ cho điện thoại: chạy lại với tuỳ chọn trong tools/chay_server_lan.py nếu cần QR). Tab thứ hai: 'Lý thuyết các môn'.",
            "2. ĐĂNG NHẬP gv_an (mật khẩu do bạn đặt, docs/chay_server_va_tai_khoan.md mục 3). NÓI: phân quyền theo lớp; sai 5 lần bị khoá.",
            "3. Chọn kỳ thi '[ĐACN] Đồ án chuyên ngành' (0 phiếu). NÓI: 40 câu, mã đề 101–104 có đáp án, 9 thí sinh dự thi, môn DACN, lớp CNTT-K22A.",
            "4. TẢI ẢNH: chọn BV01…BV05 trong data\\_eval\\demo_bv\\anh_gia (nhiều ảnh một lượt). NÓI: ảnh → nắn → OMR + CNN → chấm; câu không chắc không chấm.",
            "5. Danh sách phiếu: phiếu 'cần xem' hiện điểm TẠM. Mở BV03: DUYỆT từng câu (phím A–D, Enter). NÓI: điểm chính thức chỉ có khi giáo viên xem hết.",
            "6. Bảng điểm: điểm chính thức chỉ từ phiếu đã duyệt; BẤM 'Xuất Excel' (2 sheet). Tải lại BV01 để thấy cảnh báo phiếu trùng SBD.",
            "7. Điện thoại (tuỳ chọn): quét mã QR của chay_server_lan, trang /m, chụp tờ in từ phieu_demo_in.pdf. Đăng nhập admin → Quản trị → Nhật ký.",
            "8. Sang tab 'Lý thuyết các môn': chỉ từng môn (CSDL, web/API, bảo mật, kiểm thử, xử lý ảnh, máy học) ↔ chỗ thật trong hệ thống.",
            "9. Dừng: Ctrl+C ở cửa sổ này. Muốn làm lại từ đầu: chạy lại lệnh (tự đặt lại kỳ [ĐACN] về 0 phiếu)."]


# ----------------------------------------------------------------------------------------------- (3) xla: công cụ ngoại tuyến đơn giản
def ghi_chu_bv() -> dict[str, str]:
    import csv
    if not KICH_BAN_BV.exists():
        return {}
    with KICH_BAN_BV.open(encoding="utf-8-sig", newline="") as f:
        return {r["sheet_id"]: f"SBD {r['sbd']}, mã đề {r['exam_code']} – {r['ghi_chu']}" for r in csv.DictReader(f)}


def trang_chon_anh(co_bv: list[str] | None = None, co_them: list[str] | None = None) -> str:
    css = (ROOT / "frontend" / "mau.css").read_text(encoding="utf-8") if (ROOT / "frontend" / "mau.css").exists() else ""
    co_bv = [f"BV{i:02d}" for i in range(1, 11) if (ANH_BV / f"BV{i:02d}.jpg").exists()] if co_bv is None else co_bv
    co_them = [t for t, _ in ANH_THEM if (RA / t).exists()] if co_them is None else co_them
    gc = ghi_chu_bv()
    nut_bv = "".join(f'<a class="nut" href="/bv/{b}"><b>{b}</b><small>{e(gc.get(b, ""))}</small></a>' for b in co_bv) or "<p>Không thấy ảnh BV01–BV10 (data/_eval/demo_bv/anh_gia).</p>"
    mo_ta = dict(ANH_THEM)
    nut_them = "".join(f'<a class="nut" href="/them/{t}"><b>{e(Path(t).stem)}</b><small>{e(mo_ta[t])}</small></a>' for t in co_them)
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo xử lý ảnh – chọn phiếu</title>
<style>{css}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.5 "Segoe UI",system-ui,sans-serif}} main{{max-width:980px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:28px;margin:0 0 6px}} h2{{font-size:20px;margin:24px 0 8px}} .mut{{color:var(--mut)}} .luoi{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}}
.nut{{display:block;text-decoration:none;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:10px 14px}} .nut:hover,.nut:focus{{border-color:var(--pri);background:var(--hover)}}
.nut b{{display:block;font-size:19px}} .nut small{{color:var(--mut)}} form{{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:14px}}
button{{background:var(--pri);color:var(--tren-pri);border:0;border-radius:var(--r-nho);padding:9px 18px;font-size:16px;cursor:pointer}}
</style></head><body><main><h1>Xử lý ảnh phiếu trả lời – từng bước</h1>
<p class="mut">Công cụ ngoại tuyến (không đăng nhập, không CSDL, chỉ chạy trên máy này). Chọn một ảnh phiếu: máy sẽ cho xem từng bước xử lý.</p>
<h2>Phiếu demo (BV01–BV10)</h2><div class="luoi">{nut_bv}</div>
<h2>Ảnh khác trong thư mục demo</h2><div class="luoi">{nut_them or '<p class="mut">(không có)</p>'}</div>
<h2>Chọn tệp ảnh của bạn</h2>
<form method="post" action="/tai" enctype="multipart/form-data"><input type="file" name="anh" accept="image/*" required> <button type="submit">Xử lý ảnh</button>
<p class="mut">Ảnh JPG / PNG chụp phiếu. Ảnh không được lưu: xử lý xong là xoá tệp tạm.</p></form></main></body></html>"""


def doc_tep_tai_len(content_type: str, body: bytes) -> tuple[str, bytes] | None:
    """Lấy (tên tệp, nội dung) của trường 'anh' trong multipart/form-data. Không dùng cgi (đã bỏ khỏi Python 3.13)."""
    msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    if not msg.is_multipart():
        return None
    for ph in msg.iter_parts():
        if ph.get_param("name", header="content-disposition") == "anh":
            nd = ph.get_payload(decode=True)
            if nd:
                return (ph.get_filename() or "anh.jpg", nd)
    return None


_KHOA = threading.Lock()


def xu_ly_anh(duong_dan: Path, ra_html: Path) -> str:
    import demo_xu_ly_anh as X
    nav = '<p><a href="/" style="font-size:18px">← Chọn ảnh khác</a></p>'
    with _KHOA:
        X.chay(duong_dan, ra_html, dung_ds=True, dau_trang=nav, ds=X.DANH_SACH_XLA)
    return ra_html.read_text(encoding="utf-8")


def xu_ly_yeu_cau(phuong_thuc: str, duong: str, content_type: str = "", body: bytes = b"") -> tuple[int, str, bytes]:
    """Hàm THUẦN cho máy chủ xla (test gọi trực tiếp, không cần mở cổng). Trả (mã, content-type, nội dung)."""
    def trang(nd: str, ma: int = 200):
        return ma, "text/html; charset=utf-8", nd.encode("utf-8")
    try:
        if phuong_thuc == "GET" and duong in ("/", "/index.html"):
            return trang(trang_chon_anh())
        if phuong_thuc == "GET" and duong.startswith(("/bv/", "/them/")):
            ten = duong.split("/", 2)[2]
            if "/" in ten or "\\" in ten or ".." in ten:
                return trang("<p>Tên ảnh không hợp lệ.</p>", 400)
            if duong.startswith("/bv/"):
                p = ANH_BV / f"{ten}.jpg"
                ok = ten.startswith("BV") and ten[2:].isdigit()
            else:
                p = RA / ten
                ok = ten in {t for t, _ in ANH_THEM}
            if not ok or not p.is_file():
                return trang("<p>Không thấy ảnh. <a href='/'>← Chọn lại</a></p>", 404)
            return trang(xu_ly_anh(p, RA / "xla" / f"{p.stem}.html"))
        if phuong_thuc == "POST" and duong == "/tai":
            if len(body) > GIOI_HAN_TAI_LEN:
                return trang("<p>Ảnh quá lớn (tối đa 40 MB). <a href='/'>← Chọn lại</a></p>", 413)
            tep = doc_tep_tai_len(content_type, body)
            if tep is None:
                return trang("<p>Chưa chọn ảnh. <a href='/'>← Chọn lại</a></p>", 400)
            ten, nd = tep
            with tempfile.TemporaryDirectory(prefix="xla_") as tmp:
                p = Path(tmp) / ("anh" + (Path(ten).suffix.lower() if Path(ten).suffix.lower() in (".jpg", ".jpeg", ".png", ".heic") else ".jpg"))
                p.write_bytes(nd)
                try:
                    return trang(xu_ly_anh(p, Path(tmp) / "kq.html"))
                except Exception as ex:                                                      # noqa: BLE001 – hiện lỗi dễ hiểu, không làm sập máy chủ
                    return trang(f"<p>Không xử lý được ảnh này ({e(type(ex).__name__)}). <a href='/'>← Chọn lại</a></p>", 422)
    except Exception as ex:                                                                  # noqa: BLE001
        return trang(f"<p>Lỗi: {e(type(ex).__name__)}: {e(str(ex)[:200])}</p>", 500)
    return trang("<p>Không có trang này. <a href='/'>← Chọn ảnh</a></p>", 404)


class XlaHandler(BaseHTTPRequestHandler):
    def _tra_loi(self, ket):
        ma, ct, nd = ket
        self.send_response(ma)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(nd)))
        self.end_headers()
        self.wfile.write(nd)

    def do_GET(self):                                                                        # noqa: N802
        self._tra_loi(xu_ly_yeu_cau("GET", self.path.split("?")[0]))

    def do_POST(self):                                                                       # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n <= GIOI_HAN_TAI_LEN else b"x" * (GIOI_HAN_TAI_LEN + 1)
        self._tra_loi(xu_ly_yeu_cau("POST", self.path.split("?")[0], self.headers.get("Content-Type", ""), body))

    def log_message(self, *a):                                                               # noqa: D401 – im lặng
        pass


def chay_xla(cong: int, mo: bool, mo_trinh_duyet=webbrowser.open, may_chu=ThreadingHTTPServer) -> int:
    srv = may_chu(("127.0.0.1", cong), XlaHandler)          # CHỈ 127.0.0.1: công cụ này không mở ra mạng
    url = f"http://127.0.0.1:{cong}/"
    for d in huong_dan("xla", url):
        print(d)
    if mo:
        mo_trinh_duyet(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    finally:
        srv.server_close()
    return 0


# ----------------------------------------------------------------------------------------------- (3) ml
def chay_ml(mo: bool, da_tinh_san: bool = False, mo_trinh_duyet=webbrowser.open) -> int:
    import demo_may_hoc as M
    print("Dựng trang máy học (chạy CNN sâu thật trên 504 ô + so sánh trực tiếp các thuật toán, vài giây)…", flush=True)
    tt = M.chay_truc_tiep()
    try:
        ss = M.chay_so_sanh_truc_tiep(da_tinh_san)
    except Exception as ex:                                                                  # noqa: BLE001
        print(f"   (không chạy trực tiếp được bảng so sánh: {type(ex).__name__}; dùng kết quả ĐÃ TÍNH SẴN, trang sẽ ghi rõ)")
        ss = M.chay_so_sanh_truc_tiep(True)
    ra = RA / "may_hoc_chay_demo.html"
    ra.parent.mkdir(parents=True, exist_ok=True)
    ra.write_text(M.dung_trang(tt, ss), encoding="utf-8")
    url = ra.resolve().as_uri()
    print(f"CNN sâu trên 504 ô dev: {tt['dung']}/{tt['n']} = {100 * tt['dung'] / tt['n']:.1f}%   → {ra}")
    for d in huong_dan("ml", url):
        print(d)
    if mo:
        mo_trinh_duyet(url)
    return 0


# ----------------------------------------------------------------------------------------------- (3) dacn
def dung_ly_thuyet() -> Path:
    import demo_ly_thuyet_mon as T
    ra = RA / "ly_thuyet_cac_mon.html"
    ra.parent.mkdir(parents=True, exist_ok=True)
    ra.write_text(T.dung_trang(), encoding="utf-8")
    return ra


def may_chu_dang_chay(cong: int, cho_s: float = 0.0, hoi=urllib.request.urlopen) -> bool:
    han = time.time() + cho_s
    while True:
        try:
            with hoi(f"http://127.0.0.1:{cong}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        if time.time() >= han:
            return False
        time.sleep(0.5)


def chay_dacn(cong: int, mo: bool, mo_trinh_duyet=webbrowser.open, mo_tien_trinh=subprocess.Popen, hoi=urllib.request.urlopen, cho_s: float = 60.0) -> int:
    lt = dung_ly_thuyet()
    url = f"http://127.0.0.1:{cong}/"
    proc = None
    if may_chu_dang_chay(cong, 0.0, hoi):
        print(f"(đã có máy chủ chạy ở cổng {cong} – dùng lại; nếu vừa đổi mã hãy tắt rồi chạy lại lệnh này)")
    else:
        print(f"Khởi động máy chủ (tools/chay_server_lan.py, cổng {cong}, dọn ảnh tạm TẮT)…", flush=True)
        proc = mo_tien_trinh([sys.executable, str(ROOT / "tools" / "chay_server_lan.py"), "--cong", str(cong)], cwd=str(ROOT))
        if not may_chu_dang_chay(cong, cho_s, hoi):
            print(f"LỖI: máy chủ không trả lời ở {url}health sau {cho_s:.0f} giây (xem cửa sổ lỗi ở trên; kiểm .env và CSDL).")
            if proc is not None:
                proc.terminate()
            return 1
    for d in huong_dan("dacn", url):
        print(d)
    if mo:
        mo_trinh_duyet(url)
        mo_trinh_duyet(lt.resolve().as_uri())
    if proc is None:
        return 0
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nĐang dừng máy chủ…")
        proc.terminate()
    return 0


# ----------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("che_do", choices=CHE_DO)
    ap.add_argument("--chi-in", action="store_true", help="chỉ kiểm tra + in hướng dẫn: không đặt lại dữ liệu, không mở máy chủ / trình duyệt")
    ap.add_argument("--khong-dat-lai", action="store_true", help="không đặt lại dữ liệu kỳ thi")
    ap.add_argument("--khong-mo", action="store_true", help="không tự mở trình duyệt")
    ap.add_argument("--bo-qua-kiem-tra", action="store_true", help="vẫn chạy khi sai nhánh / SHA mô hình (CHỈ để thử)")
    ap.add_argument("--da-tinh-san", action="store_true", help="ml: dùng kết quả so sánh đã tính sẵn (không chờ ~6 s)")
    ap.add_argument("--cong", type=int, default=None, help=f"cổng (xla {CONG_XLA}, dacn {CONG_DACN})")
    a = ap.parse_args(argv)
    print(f"=== DEMO {a.che_do.upper()} ===")
    sai = 0
    for m in kiem_truoc():
        print(f"  [{'ĐẠT' if m.dat else 'KHÔNG ĐẠT'}] {m.ten}: {m.chi_tiet}")
        sai += not m.dat
    if sai and not a.bo_qua_kiem_tra:
        print("DỪNG: kiểm tra nhánh / mô hình không đạt (thêm --bo-qua-kiem-tra nếu chỉ muốn thử).")
        return 2
    cong = a.cong or (CONG_XLA if a.che_do == "xla" else CONG_DACN)
    if a.chi_in:
        url = {"xla": f"http://127.0.0.1:{cong}/", "ml": str((RA / "may_hoc_chay_demo.html").resolve().as_uri()), "dacn": f"http://127.0.0.1:{cong}/"}[a.che_do]
        print("(--chi-in: không đặt lại, không mở máy chủ, không mở trình duyệt)")
        for d in huong_dan(a.che_do, url):
            print(d)
        return 0
    if not a.khong_dat_lai:
        print(f"Đặt lại dữ liệu kỳ thi '{__import__('dat_lai_demo').KY_THI_BA_MON[a.che_do]}' (sao lưu rồi xoá phiếu của ĐÚNG kỳ này):")
        ok = dat_lai(a.che_do)
        if not ok and a.che_do == "dacn":
            print("DỪNG: chế độ dacn cần CSDL và kỳ thi sạch. Kiểm PostgreSQL / .env, hoặc chạy: python tools/nap_bo_demo.py --ba-mon --ap-dung")
            return 1
        if not ok:
            print(f"   (chế độ {a.che_do} không ghi CSDL nên vẫn chạy tiếp)")
    mo = not a.khong_mo
    if a.che_do == "xla":
        return chay_xla(cong, mo)
    if a.che_do == "ml":
        return chay_ml(mo, a.da_tinh_san)
    return chay_dacn(cong, mo)


if __name__ == "__main__":
    sys.exit(main())
