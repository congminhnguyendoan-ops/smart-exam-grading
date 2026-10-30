"""
kiem_truoc_demo.py - Lệnh U (30/10/2026): KIỂM TRA TRƯỚC NGÀY DEMO bằng một lệnh. CHỈ ĐỌC: không ghi gì vào CSDL (kết nối read_only;
phép đo tốc độ tải ảnh chạy trong MỘT giao dịch ROLLBACK + kho ảnh tạm, xoá ngay sau đó). Không chạy lệnh mạng / tường lửa nào có tác dụng ghi:
chỉ ĐỌC luật tường lửa (Get-NetFirewallRule).

  python tools/kiem_truoc_demo.py                 # in bảng ĐẠT / CẢNH BÁO / KHÔNG ĐẠT / KHÔNG KIỂM ĐƯỢC; mã thoát 1 nếu có mục KHÔNG ĐẠT
  python tools/kiem_truoc_demo.py --bo-qua-toc-do # bỏ phép đo tải ảnh (nhanh hơn ~10 s)
  python tools/kiem_truoc_demo.py --json          # thêm bản JSON (cho máy đọc)

Không in mật khẩu, DATABASE_URL hay AUTH_SECRET.
"""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

DAT, CANH_BAO, KHONG_DAT, KHONG_KIEM = "ĐẠT", "CẢNH BÁO", "KHÔNG ĐẠT", "KHÔNG KIỂM ĐƯỢC"
def migration_can() -> list[str]:
    """MỌI tệp trong backend/migrations/ (lệnh Y: không ghi cứng danh sách – thêm 006 thì tự đòi 006, nhãn tự đổi)."""
    from backend import migrate
    return [f.name for f in migrate.ds_file()]
BANG_CHINH = ["users", "classes", "teacher_classes", "students", "subjects", "sheet_templates", "exams", "exam_students", "exam_codes", "answer_keys",
              "answer_sheets", "sheet_answers", "ocr_digits", "results", "review_queue", "score_audit_logs", "schema_migrations"]
TAI_KHOAN = ["admin", "gv_an", "gv_binh"]
KY_THI_CHINH = (1380, 1381, 1633)                     # phải TRỐNG trước buổi demo
KY_THI_TAP = 1632                                     # kỳ thi tập: có phiếu nền (5 chính thức + #6028)
DU_THI_THEO_KY_THI = {1380: "E1", 1381: "E2", 1632: "E1", 1633: "E2"}
SO_DANG_KY = ROOT / "docs" / "dong_bang_ma_dot2.json"
TEP_MO_HINH = ["models/omr_m1.json", "models/ocr_cnn.json", "answer_sheet/output/layout.json", "answer_sheet/output/phieu_trang_300dpi.png"]
DEMO_BV = ROOT / "answer_sheet" / "demo_bv"
ANH_BV = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia"
TEP_DEMO = [DEMO_BV / "phieu_demo_in.pdf", DEMO_BV / "phieu_giao_viec_demo.pdf"] + [ANH_BV / f"BV{i:02d}.jpg" for i in range(1, 11)]
ANH_DO_TOC_DO = [ROOT / "data" / "_eval" / "demo_bv" / "gia_12mp" / "BV01_v1.jpg", ROOT / "data" / "_eval" / "demo_bv" / "gia_12mp" / "BV02_v1.jpg"]
DIA_TOI_THIEU_GB = 5
TOC_DO_TOI_DA_S = 5.0
CONG = 8000


@dataclass
class Muc:
    nhom: str
    ten: str
    ket_qua: str
    chi_tiet: str = ""


def sha_hoa(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


# ------------------------------------------------------------------------------------------------ từng nhóm kiểm (mỗi hàm trả list[Muc])
def kiem_csdl(conn) -> list[Muc]:
    from backend import migrate
    r = conn.execute("SELECT current_database() AS d, split_part(version(), ' ', 2) AS v, current_user AS u").fetchone()
    out = [Muc("CSDL", "Kết nối PostgreSQL", DAT, f"CSDL {r['d']}, PostgreSQL {r['v']}, người dùng {r['u']}")]
    chua = migrate.chua_ap(conn, ca_tuy_chon=True)              # CHỈ ĐỌC (migrate.da_ap có CREATE TABLE – không dùng ở đây)
    da = {f.name for f in migrate.ds_file()} - set(chua)
    can = migration_can()
    thieu = [m for m in can if m not in da]
    nhan = f"Migration đã áp ({can[0][:3]} → {can[-1][:3]})" if can else "Migration đã áp"
    out.append(Muc("CSDL", nhan, KHONG_DAT if thieu else DAT, f"thiếu {thieu}" if thieu else f"{len(da)} migration: {', '.join(sorted(da))}"))
    co = {r["table_name"] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'").fetchall()}
    thieu_b = [b for b in BANG_CHINH if b not in co]
    out.append(Muc("CSDL", f"{len(BANG_CHINH)} bảng chính tồn tại", KHONG_DAT if thieu_b else DAT, f"thiếu {thieu_b}" if thieu_b else ""))
    return out


def kiem_mo_hinh(goc: Path = ROOT, tep: list[str] = TEP_MO_HINH, so_dang_ky: Path = SO_DANG_KY) -> list[Muc]:
    out = []
    dk = json.loads(so_dang_ky.read_text(encoding="utf-8")).get("sha256", {}) if so_dang_ky.exists() else {}
    for t in tep:
        p = goc / t
        if not p.is_file():
            out.append(Muc("Mô hình", t, KHONG_DAT, "THIẾU tệp"))
        elif t in dk:
            ok = sha_hoa(p) == dk[t].upper()
            out.append(Muc("Mô hình", t, DAT if ok else KHONG_DAT, f"SHA {'khớp' if ok else 'KHÁC'} {so_dang_ky.name}"))
        else:
            out.append(Muc("Mô hình", t, DAT, "có tệp (sổ đăng ký không ghi SHA tệp này)"))
    om = os.environ.get("OMR_MODEL")
    if om:
        p = Path(om) if Path(om).is_absolute() else goc / om
        out.append(Muc("Mô hình", "OMR_MODEL trong .env", DAT if p.is_file() else KHONG_DAT, "trỏ tới tệp có thật" if p.is_file() else f"không thấy tệp {om}"))
    return out


def kiem_tai_khoan(conn) -> list[Muc]:
    out = []
    for u in TAI_KHOAN:
        r = conn.execute("SELECT role::text AS role, is_active FROM users WHERE username = %s", (u,)).fetchone()
        if r is None:
            out.append(Muc("Tài khoản", u, KHONG_DAT, "không tồn tại"))
        else:
            out.append(Muc("Tài khoản", u, DAT if r["is_active"] else KHONG_DAT, f"vai trò {r['role']}, {'đang hoạt động' if r['is_active'] else 'BỊ KHOÁ'}"))
    return out


def kiem_ky_thi(conn) -> list[Muc]:
    from nap_bo_demo import DU_THI
    out = []
    for e in (*KY_THI_CHINH, KY_THI_TAP):
        r = conn.execute("SELECT exam_title, status::text AS status, (SELECT count(*) FROM answer_sheets a WHERE a.exam_id = e.exam_id) AS so_phieu, "
                         "(SELECT count(*) FILTER (WHERE status = 'graded') FROM answer_sheets a WHERE a.exam_id = e.exam_id) AS chinh_thuc, "
                         "(SELECT count(*) FILTER (WHERE status = 'needs_review') FROM answer_sheets a WHERE a.exam_id = e.exam_id) AS can_xem "
                         "FROM exams e WHERE exam_id = %s", (e,)).fetchone()
        if r is None:
            out.append(Muc("Kỳ thi", f"#{e}", KHONG_DAT, "không tồn tại"))
            continue
        ten = f"#{e} {r['exam_title']}"
        if r["status"] == "closed":
            out.append(Muc("Kỳ thi", ten, KHONG_DAT, "ĐÃ ĐÓNG – không nhận ảnh mới (mở lại ở Quản trị → Quản lý kỳ thi)"))
            continue
        dem = f"{r['so_phieu']} phiếu ({r['chinh_thuc']} chính thức, {r['can_xem']} cần xem)"
        if e in KY_THI_CHINH:
            out.append(Muc("Kỳ thi", ten, CANH_BAO if r["so_phieu"] else DAT, f"đang mở; {dem}" + (" – kỳ thi demo chính KHÔNG trống: chạy tools/dat_lai_demo.py" if r["so_phieu"] else "")))
        else:
            out.append(Muc("Kỳ thi", ten, DAT, f"đang mở; {dem} (kỳ thi tập)"))
        mong = set(DU_THI[DU_THI_THEO_KY_THI[e]])
        co = {x["student_code"] for x in conn.execute("SELECT s.student_code FROM exam_students es JOIN students s USING (student_id) WHERE es.exam_id = %s", (e,)).fetchall()}
        ok = co == mong
        out.append(Muc("Kỳ thi", f"#{e} danh sách dự thi", DAT if ok else KHONG_DAT,
                       f"{len(co)} thí sinh {min(co) if co else ''}–{max(co) if co else ''}" if ok else f"lệch: thiếu {sorted(mong - co)}, thừa {sorted(co - mong)}"))
    return out


def _cong_dang_nghe(host: str, cong: int) -> bool:
    try:
        with socket.create_connection((host, cong), timeout=0.8):
            return True
    except OSError:
        return False


def kiem_mang(cfg) -> list[Muc]:
    from backend import mang
    out = []
    if _cong_dang_nghe("127.0.0.1", CONG):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{CONG}/health", timeout=3) as r:
                st = f"đang có server chạy, /health trả {r.status}"
        except Exception as e:  # noqa: BLE001
            st = f"cổng ĐANG BẬN nhưng /health không trả lời ({type(e).__name__}) – có thể là chương trình khác"
        out.append(Muc("Mạng", f"Cổng {CONG}", DAT if "/health trả 200" in st else CANH_BAO, st))
    else:
        out.append(Muc("Mạng", f"Cổng {CONG}", DAT, "rảnh (chưa chạy server) – chạy: python tools/chay_server_lan.py --khong-xoa-anh"))
    uv = mang.ung_vien_ip()
    chinh = next((u for u in uv if not u.ao), uv[0] if uv else None)
    if chinh is None:
        out.append(Muc("Mạng", "IP mạng nội bộ", KHONG_DAT, "không tìm thấy IP LAN – máy chưa nối Wi‑Fi / LAN?"))
    else:
        khac = ", ".join(u.ip for u in uv if u is not chinh)
        lan = _cong_dang_nghe(chinh.ip, CONG)
        out.append(Muc("Mạng", "IP mạng nội bộ", DAT, f"{chinh.ip} ({chinh.card}) → điện thoại mở {mang.url_dien_thoai(chinh.ip, CONG)}"
                       + (f"; IP khác: {khac}" if khac else "") + (f"; server {'ĐANG' if lan else 'KHÔNG'} nghe trên IP này" if _cong_dang_nghe('127.0.0.1', CONG) else "")))
    pb = cfg.public_base_url
    if not pb:
        out.append(Muc("Mạng", "PUBLIC_BASE_URL", CANH_BAO, "chưa đặt: QR trang bìa lấy theo địa chỉ trình duyệt – in trang bìa khi đang mở web qua "
                       f"http://<IP LAN>:{CONG}/, KHÔNG qua 127.0.0.1"))
    elif chinh and chinh.ip not in pb:
        out.append(Muc("Mạng", "PUBLIC_BASE_URL", CANH_BAO, f"{pb} KHÁC IP LAN hiện tại {chinh.ip} (đổi Wi‑Fi?) – QR trang bìa sẽ trỏ sai; sửa .env rồi khởi động lại server"))
    else:
        out.append(Muc("Mạng", "PUBLIC_BASE_URL", DAT, f"{pb} khớp IP LAN"))
    ten = mang.TEN_LUAT_TUONG_LUA.format(cong=CONG)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            f"$r = Get-NetFirewallRule -DisplayName '{ten}' -ErrorAction SilentlyContinue; if ($r) {{ $r | ForEach-Object {{ \"$($_.Enabled)|$($_.Profile)\" }} }} else {{ 'KHONG_CO' }}"],
                           capture_output=True, text=True, timeout=30)
        kq = r.stdout.strip()
        if r.returncode != 0 or not kq:
            out.append(Muc("Mạng", f"Luật tường lửa {ten}", KHONG_KIEM, (r.stderr.strip() or "không có kết quả")[:120]))
        elif kq == "KHONG_CO":
            out.append(Muc("Mạng", f"Luật tường lửa {ten}", KHONG_DAT, "KHÔNG có – điện thoại không vào được. PowerShell quản trị: " + mang.lenh_tuong_lua(CONG)["mo"]))
        else:
            bat = all(x.split("|")[0] == "True" for x in kq.splitlines())
            out.append(Muc("Mạng", f"Luật tường lửa {ten}", DAT if bat else KHONG_DAT, f"có ({kq.replace(chr(10), '; ')})" + ("" if bat else " – luật đang TẮT")))
    except (OSError, subprocess.TimeoutExpired) as e:
        out.append(Muc("Mạng", f"Luật tường lửa {ten}", KHONG_KIEM, f"{type(e).__name__}"))
    return out


def kiem_tep_demo(tep: list[Path] = TEP_DEMO, goc: Path = ROOT) -> list[Muc]:
    thieu = [p for p in tep if not p.is_file()]
    ten = lambda p: p.relative_to(goc).as_posix() if goc in p.parents else str(p)   # noqa: E731
    return [Muc("Tệp demo", f"{len(tep)} tệp (PDF in phiếu, giao việc, ảnh BV01–BV10)", KHONG_DAT if thieu else DAT,
                ("THIẾU: " + ", ".join(ten(p) for p in thieu)) if thieu else f"đủ ({ten(tep[0].parent)}, {ten(tep[-1].parent)})")]


def kiem_git(goc: Path = ROOT.parent) -> list[Muc]:
    g = lambda *a: subprocess.run(["git", *a], cwd=goc, capture_output=True, text=True, encoding="utf-8")   # noqa: E731
    head = g("log", "-1", "--format=%h %s").stdout.strip()
    nhanh = g("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    the = g("describe", "--tags", "--abbrev=0").stdout.strip() or "(không có)"
    sua = [x for x in g("status", "--porcelain", "--untracked-files=no").stdout.splitlines() if x.strip()]
    moi = [x for x in g("status", "--porcelain").stdout.splitlines() if x.startswith("??")]
    return [Muc("Git", "HEAD / nhánh / thẻ gần nhất", DAT, f"{nhanh} @ {head[:80]} · thẻ {the}"),
            Muc("Git", "Cây làm việc", CANH_BAO if sua else DAT, (f"BẨN: {len(sua)} tệp đã sửa chưa commit" if sua else "sạch") + (f"; {len(moi)} tệp chưa theo dõi" if moi else ""))]


def kiem_dia(goc: Path = ROOT) -> list[Muc]:
    t = shutil.disk_usage(goc)
    gb = t.free / 1024 ** 3
    return [Muc("Máy", f"Dung lượng trống ổ {goc.drive or goc.anchor}", CANH_BAO if gb < DIA_TOI_THIEU_GB else DAT, f"{gb:.1f} GB trống / {t.total / 1024 ** 3:.0f} GB")]


def kiem_toc_do(anh: list[Path] = ANH_DO_TOC_DO) -> list[Muc]:
    """Tải 2 ảnh ~12 MP qua API thật (TestClient) vào kỳ thi tạo trong MỘT giao dịch ROLLBACK; kho ảnh tạm, xoá ngay. Ngưỡng cảnh báo tính trên ảnh 2."""
    thieu = [p.name for p in anh if not p.is_file()]
    if thieu:
        return [Muc("Tốc độ", "Tải thử ảnh qua API", KHONG_KIEM, f"thiếu ảnh {thieu} (tạo: python tools/thu_dien_thoai.py tao-anh)")]
    cu = {k: os.environ.get(k) for k in ("AUTH_MODE", "ANH_XOA_TU_DONG")}
    os.environ["AUTH_MODE"] = "demo"                          # TestClient trong tiến trình: bỏ đăng nhập; khôi phục ở finally
    os.environ["ANH_XOA_TU_DONG"] = "0"
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from backend import demo
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    from backend.main import app, get_cau_hinh, get_conn
    kho = Path(tempfile.mkdtemp(prefix="kiem_truoc_demo_"))
    cfg = replace(lay_cau_hinh(), storage_dir=kho)
    conn = ket_noi()

    def _conn():
        yield conn                                           # một giao dịch, KHÔNG commit -> rollback ở finally

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_cau_hinh] = lambda: cfg
    giay, trang_thai = [], []
    try:
        with TestClient(app) as client:
            r = client.post("/exams", json={"exam_title": "[KIỂM TRƯỚC DEMO – ROLLBACK]", "subject_code": "KTD", "num_questions": 40,
                                            "codes": [{"code": m, "answers": demo.khoa_demo(m)} for m in ("101", "102")]})
            assert r.status_code == 201, r.text
            eid = r.json()["exam_id"]
            for p in anh:
                t0 = time.perf_counter()
                r = client.post(f"/exams/{eid}/sheets", files={"file": (p.name, p.read_bytes(), "image/jpeg")})
                giay.append(time.perf_counter() - t0)
                trang_thai.append(r.json().get("status") if r.status_code == 201 else f"HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        return [Muc("Tốc độ", "Tải thử ảnh qua API", KHONG_DAT, f"lỗi {type(e).__name__}: {str(e)[:150]}")]
    finally:
        app.dependency_overrides.clear()
        conn.rollback()
        conn.close()
        shutil.rmtree(kho, ignore_errors=True)
        for k, v in cu.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    nong = giay[-1]
    return [Muc("Tốc độ", "Tải thử ảnh 12 MP qua API (ROLLBACK)", CANH_BAO if nong > TOC_DO_TOI_DA_S else DAT,
                f"ảnh 1: {giay[0]:.2f} s, ảnh 2: {nong:.2f} s (từ lúc gửi tới khi API trả kết quả chấm); trạng thái {trang_thai}" + (f" – CHẬM hơn {TOC_DO_TOI_DA_S:.0f} s" if nong > TOC_DO_TOI_DA_S else ""))]


# ------------------------------------------------------------------------------------------------ tổng hợp
def ma_thoat(muc: list[Muc]) -> int:
    return 1 if any(m.ket_qua == KHONG_DAT for m in muc) else 0


def in_bang(muc: list[Muc]) -> str:
    dong = [f"{'Nhóm':<10} {'Mục':<46} {'Kết quả':<16} Chi tiết", "-" * 120]
    dong += [f"{m.nhom:<10} {m.ten[:46]:<46} {m.ket_qua:<16} {m.chi_tiet}" for m in muc]
    dem = {k: sum(m.ket_qua == k for m in muc) for k in (DAT, CANH_BAO, KHONG_DAT, KHONG_KIEM)}
    dong += ["-" * 120, " · ".join(f"{k}: {v}" for k, v in dem.items()),
             "KẾT LUẬN: " + ("CÓ MỤC KHÔNG ĐẠT – sửa trước khi demo." if ma_thoat(muc) else "không có mục KHÔNG ĐẠT" + (" (xem các CẢNH BÁO)." if dem[CANH_BAO] else "."))]
    return "\n".join(dong)


def chay(toc_do: bool = True) -> list[Muc]:
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    muc: list[Muc] = []
    cfg = None
    try:
        cfg = lay_cau_hinh()
        conn = ket_noi()
        conn.read_only = True                                  # mọi kiểm CSDL ở đây: giao dịch CHỈ ĐỌC
        try:
            muc += kiem_csdl(conn)
            muc += kiem_tai_khoan(conn)
            muc += kiem_ky_thi(conn)
        finally:
            conn.rollback()
            conn.close()
    except Exception as e:  # noqa: BLE001
        muc.append(Muc("CSDL", "Kết nối PostgreSQL / cấu hình", KHONG_DAT, f"{type(e).__name__}: {str(e).splitlines()[0][:150]}"))
    muc += kiem_mo_hinh()
    if cfg is not None:
        muc += kiem_mang(cfg)
    muc += kiem_tep_demo() + kiem_git() + kiem_dia()
    if toc_do and cfg is not None:
        muc += kiem_toc_do()
    return muc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bo-qua-toc-do", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    muc = chay(not a.bo_qua_toc_do)
    print(in_bang(muc))
    if a.json:
        print(json.dumps([m.__dict__ for m in muc], ensure_ascii=False, indent=1))
    return ma_thoat(muc)


if __name__ == "__main__":
    sys.exit(main())
