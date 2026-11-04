"""
ah_thu_dong_thoi.py - Lệnh AH (04/11/2026): THỬ THẬT nhiều giáo viên đăng nhập + chấm ĐỒNG THỜI trên máy chủ thử riêng (cổng 8010, cùng CSDL).

KHÔNG sửa mã hệ thống: chỉ gọi API công khai qua HTTP (httpx) tới một tiến trình uvicorn riêng (AUTH_MODE=on, ANH_XOA_TU_DONG=0,
STORAGE_DIR = data/_eval/ah/kho). Dữ liệu thử RIÊNG, tạo mới, ghi hồ sơ data/_eval/ah/ho_so.json và DỌN trong khối finally (kể cả khi lỗi):
  - 3 tài khoản giáo viên "ah_thu_1..3" (mật khẩu ngẫu nhiên, KHÔNG in ra), 4 lớp "AH-THU-…", môn "AHTHU", kỳ thi "[AH-THU] …",
    thí sinh mã 97xxxx (tên "AH thử …"). Không dùng / không đổi tài khoản thật (admin, gv_an, gv_binh, gv_thu, sv…).
  - Phạm vi dọn = id trong hồ sơ ∪ tiền tố trên (đã kiểm = 0 trước khi chạy); chốt an toàn: không bao giờ đụng kỳ thi 6, 1380, 1381, 1632, 1633.
Ảnh tải lên = ảnh GIẢ HOÁ vẽ trên mẫu phiếu trắng (cùng quy ước tools/thu_bo_demo.py: ô đậm xám 30, ô mờ xám 170, bubble SBD / mã đề đậm, KHÔNG có
chữ viết tay) – chỉ để thử đồng thời / an toàn, KHÔNG phải số đo độ chính xác.

  python tools/ah_thu_dong_thoi.py chay       # dựng -> kịch bản A, B, C, D (+D-ép, D-ảnh trùng, D-lô chéo), E (+ thang tải) -> dọn -> data/_eval/ah/ket_qua.{json,md}
  python tools/ah_thu_dong_thoi.py don        # chỉ dọn (khi lần chạy trước bị ngắt giữa chừng)
  python tools/ah_thu_dong_thoi.py dem        # đếm dữ liệu thử còn sót (chỉ đọc)
"""
import argparse
import ctypes
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")                  # in qua ống trên Windows (cp1252) không vỡ chữ Việt
    except (AttributeError, ValueError):
        pass

OUT = ROOT / "data" / "_eval" / "ah"
HO_SO = OUT / "ho_so.json"
KHO = OUT / "kho"
LOG_MAY_CHU = OUT / "may_chu.log"
LAYOUT = ROOT / "answer_sheet" / "output" / "layout.json"
MAU_PNG = ROOT / "answer_sheet" / "output" / "phieu_trang_300dpi.png"

CONG = 8010
GOC = f"http://127.0.0.1:{CONG}"
TIEN_TO_USER, TIEN_TO_KY_THI, TIEN_TO_LOP, MON = "ah_thu_", "[AH-THU]", "AH-THU-", "AHTHU"
TEN_SV = "AH thử"
CAM = frozenset({6, 1380, 1381, 1632, 1633})            # kỳ thi KHÔNG BAO GIỜ được đụng
SO_CAU, MA_DE = 40, "101"
XAM_DAM, XAM_MO = 30, 170
HAT_GIONG = 20261104


# ------------------------------------------------------------------------------------------------ dữ liệu thử: dựng / dọn
def ma_sv(nhom: int, i: int) -> str:
    """Mã thí sinh 6 chữ số, tiền tố 97: tài khoản k -> 97k0nn; D -> 979nnn (nnn 001..); D-lô chéo -> 9791nn."""
    return f"97{nhom}0{i:02d}" if nhom in (1, 2, 3) else f"979{i:03d}"


def _dap_an() -> str:
    r = random.Random(HAT_GIONG)
    return "".join(r.choice("ABCD") for _ in range(SO_CAU))


DAP_AN = _dap_an()


def dung(conn) -> dict:
    """Tạo dữ liệu thử trong MỘT giao dịch (người gọi commit). Trả hồ sơ (id + mật khẩu chỉ giữ trong bộ nhớ, KHÔNG ghi ra tệp)."""
    from backend import auth, service
    hs = {"luc": datetime.now().isoformat(timespec="seconds"), "users": {}, "classes": {}, "exams": {}, "students": {}, "_mk": {}}
    for k in (1, 2, 3):
        ten = f"{TIEN_TO_USER}{k}"
        mk = auth.mat_khau_ngau_nhien(16)
        uid = conn.execute("INSERT INTO users (username, email, password_hash, full_name, role, is_active) VALUES (%s, %s, %s, %s, 'teacher', TRUE) "
                           "RETURNING user_id", (ten, f"{ten}@ah-thu.invalid", auth.bam_mat_khau(mk), f"GV thử AH {k}")).fetchone()["user_id"]
        hs["users"][ten], hs["_mk"][ten] = uid, mk
    for ma in ("L1", "L2", "L3", "LD"):
        hs["classes"][ma] = conn.execute("INSERT INTO classes (class_code, class_name, academic_year) VALUES (%s, %s, '2026-2027') RETURNING class_id",
                                         (f"{TIEN_TO_LOP}{ma}", f"Lớp thử AH {ma}")).fetchone()["class_id"]
    u = hs["users"]
    for ten, lop in ((f"{TIEN_TO_USER}1", "L1"), (f"{TIEN_TO_USER}2", "L2"), (f"{TIEN_TO_USER}3", "L3"),
                     (f"{TIEN_TO_USER}1", "LD"), (f"{TIEN_TO_USER}2", "LD")):
        conn.execute("INSERT INTO teacher_classes (user_id, class_id) VALUES (%s, %s)", (u[ten], hs["classes"][lop]))

    def sv(ma: str, lop: str) -> int:
        sid = conn.execute("INSERT INTO students (student_code, full_name, class_id) VALUES (%s, %s, %s) RETURNING student_id",
                           (ma, f"{TEN_SV} {ma}", hs["classes"][lop])).fetchone()["student_id"]
        hs["students"][ma] = sid
        return sid

    def ky_thi(khoa: str, tieu_de: str, lop: str, chu: str, ds_sv: list[int]) -> None:
        eid = service.tao_ky_thi(conn, {"exam_title": f"{TIEN_TO_KY_THI} {tieu_de}", "subject_code": MON, "subject_name": "Môn thử AH",
                                        "num_questions": SO_CAU, "max_score": 10, "pass_score": 5, "class_id": hs["classes"][lop],
                                        "codes": [{"code": MA_DE, "answers": DAP_AN}]}, u[chu])
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s)", [(eid, s) for s in ds_sv])
        hs["exams"][khoa] = eid

    for k in (1, 2, 3):
        ids = [sv(ma_sv(k, i), f"L{k}") for i in range(1, 27)]          # 6 (B) + 20 (E)
        ky_thi(f"X{k}", f"GV{k} – đồng thời", f"L{k}", f"{TIEN_TO_USER}{k}", ids)
        ky_thi(f"X{k}s", f"GV{k} – tuần tự (đối chứng)", f"L{k}", f"{TIEN_TO_USER}{k}", ids)
    ids_d = [sv(ma_sv(9, i), "LD") for i in range(1, 61)]                 # D 20 + D-ép 10 + D-lô chéo 20 + dự phòng
    ky_thi("XD", "lớp chung GV1+GV2 – tranh chấp SBD", "LD", f"{TIEN_TO_USER}1", ids_d)
    ky_thi("XR", "GV1 – thang tải", "L1", f"{TIEN_TO_USER}1", [])
    return hs


def luu_ho_so(hs: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    HO_SO.write_text(json.dumps({k: v for k, v in hs.items() if k != "_mk"}, ensure_ascii=False, indent=1), encoding="utf-8")


def pham_vi_don(conn) -> dict:
    """id cần dọn = hồ sơ ∪ tiền tố. Chốt an toàn: mọi kỳ thi phải mang tiền tố [AH-THU] và không nằm trong CAM."""
    hs = json.loads(HO_SO.read_text(encoding="utf-8")) if HO_SO.exists() else {}
    exams = {r["exam_id"]: r["exam_title"] for r in conn.execute(
        "SELECT exam_id, exam_title FROM exams WHERE exam_title LIKE %s OR exam_id = ANY(%s)",
        (TIEN_TO_KY_THI + "%", list(hs.get("exams", {}).values()))).fetchall()}
    for e, t in exams.items():
        if e in CAM or not t.startswith(TIEN_TO_KY_THI):
            raise SystemExit(f"DỪNG: kỳ thi {e} '{t}' không phải dữ liệu thử – không dọn")
    users = {r["user_id"]: r["username"] for r in conn.execute(
        "SELECT user_id, username FROM users WHERE username LIKE %s OR user_id = ANY(%s)",
        (TIEN_TO_USER.replace("_", "\\_") + "%", list(hs.get("users", {}).values()))).fetchall()}
    for i, t in users.items():
        if not t.startswith(TIEN_TO_USER):
            raise SystemExit(f"DỪNG: tài khoản {i} '{t}' không phải tài khoản thử – không dọn")
    classes = [r["class_id"] for r in conn.execute("SELECT class_id FROM classes WHERE class_code LIKE %s", (TIEN_TO_LOP + "%",)).fetchall()]
    students = [r["student_id"] for r in conn.execute("SELECT student_id FROM students WHERE student_code LIKE '97%%' AND full_name LIKE %s",
                                                      (TEN_SV + "%",)).fetchall()]
    return {"exams": sorted(exams), "users": sorted(users), "classes": classes, "students": students}


def dem_con_lai(conn) -> dict:
    pv = pham_vi_don(conn)
    e = pv["exams"]
    return {"users": len(pv["users"]), "classes": len(pv["classes"]), "students": len(pv["students"]), "exams": len(e),
            "answer_sheets": conn.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = ANY(%s)", (e,)).fetchone()["n"],
            "results": conn.execute("SELECT count(*) AS n FROM results WHERE exam_id = ANY(%s)", (e,)).fetchone()["n"],
            "scan_batches": conn.execute("SELECT count(*) AS n FROM scan_batches WHERE exam_id = ANY(%s)", (e,)).fetchone()["n"],
            "subjects": conn.execute("SELECT count(*) AS n FROM subjects WHERE subject_code = %s", (MON,)).fetchone()["n"],
            "teacher_classes": conn.execute("SELECT count(*) AS n FROM teacher_classes WHERE user_id = ANY(%s) OR class_id = ANY(%s)",
                                            (pv["users"], pv["classes"])).fetchone()["n"],
            "admin_audit_log_cua_tai_khoan_thu": conn.execute("SELECT count(*) AS n FROM admin_audit_log WHERE actor_user_id = ANY(%s)",
                                                              (pv["users"],)).fetchone()["n"],
            "tep_trong_kho": sum(1 for p in KHO.rglob("*") if p.is_file()) if KHO.exists() else 0}


def don(conn) -> dict:
    """Xoá đúng dữ liệu thử trong MỘT giao dịch (người gọi commit), theo thứ tự khoá ngoại. Trả số dòng xoá từng bảng."""
    pv = pham_vi_don(conn)
    e, u = pv["exams"], pv["users"]
    so = {}
    for ten, sql, tham in (
            ("score_audit_logs", "DELETE FROM score_audit_logs WHERE result_id IN (SELECT result_id FROM results WHERE exam_id = ANY(%s))", (e,)),
            ("results", "DELETE FROM results WHERE exam_id = ANY(%s)", (e,)),
            ("answer_sheets", "DELETE FROM answer_sheets WHERE exam_id = ANY(%s)", (e,)),      # cascade: sheet_answers, ocr_digits, review_queue
            ("scan_batches", "DELETE FROM scan_batches WHERE exam_id = ANY(%s)", (e,)),
            ("exams", "DELETE FROM exams WHERE exam_id = ANY(%s)", (e,)),                     # cascade: exam_codes, answer_keys, exam_students
            ("students", "DELETE FROM students WHERE student_id = ANY(%s)", (pv["students"],)),
            ("classes", "DELETE FROM classes WHERE class_id = ANY(%s)", (pv["classes"],)),     # cascade: teacher_classes
            ("subjects", "DELETE FROM subjects s WHERE subject_code = %s AND NOT EXISTS (SELECT 1 FROM exams x WHERE x.subject_id = s.subject_id)", (MON,)),
            ("users", "DELETE FROM users WHERE user_id = ANY(%s)", (u,))):
        so[ten] = conn.execute(sql, tham).rowcount
    return so


def don_tep() -> int:
    if not KHO.exists():
        return 0
    if KHO.resolve().parent != OUT.resolve():
        raise SystemExit("DỪNG: thư mục kho không nằm trong data/_eval/ah")
    n = sum(1 for p in KHO.rglob("*") if p.is_file())
    shutil.rmtree(KHO)
    return n


def don_tat_ca() -> dict:
    from backend.db import ket_noi
    with ket_noi() as conn:
        so = don(conn)
    tep = don_tep()
    with ket_noi() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        con = dem_con_lai(conn)
    return {"da_xoa": so, "tep_da_xoa": tep, "con_lai": con, "sach": all(v == 0 for v in con.values())}


# ------------------------------------------------------------------------------------------------ ảnh giả hoá
class Ve:
    def __init__(self):
        import cv2
        import numpy as np
        self.cv2 = cv2
        self.L = json.loads(LAYOUT.read_text(encoding="utf-8"))
        self.mau = cv2.imdecode(np.fromfile(MAU_PNG, np.uint8), cv2.IMREAD_GRAYSCALE)

    def anh(self, cau: list[str], sbd: str, ma: str = MA_DE) -> bytes:
        cv2, L = self.cv2, self.L
        a = self.mau.copy()
        ans, R = L["answers"], L["answers"]["bubble_radius"]
        for q, lab in enumerate(cau, 1):
            for ch in lab:
                c = ans["centers"][str(q)][ch.upper()]
                cv2.circle(a, (int(round(c[0])), int(round(c[1]))), int(round(0.85 * R)), XAM_DAM if ch.isupper() else XAM_MO, -1)
        for key, so in (("sbd", sbd), ("exam_code", ma)):
            for i, ch in enumerate(so):
                c = L[key]["bubbles"][i][int(ch)]
                cv2.circle(a, (int(round(c[0])), int(round(c[1]))), int(round(0.85 * L[key]["bubble_radius"])), XAM_DAM, -1)
        return cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()


def bai_lam(seed: int, loai: str) -> tuple[list[str], int]:
    """(nhãn 40 câu, số câu đúng nếu chấm tự động). loai: 'sach' (mọi câu 1 ô đậm) | 'nhieu' (câu 40 tô 2 ô) | 'mo' (câu 39 tô mờ)."""
    r = random.Random(seed)
    dung_n = r.randint(12, 40)
    vt = set(r.sample(range(SO_CAU), dung_n))
    cau = [DAP_AN[i] if i in vt else r.choice([x for x in "ABCD" if x != DAP_AN[i]]) for i in range(SO_CAU)]
    if loai == "nhieu":
        cau[39] = "".join(sorted({DAP_AN[39], "A" if DAP_AN[39] != "A" else "B"}))
    elif loai == "mo":
        cau[38] = cau[38].lower()
    return cau, sum(1 for i in range(SO_CAU) if cau[i] == DAP_AN[i])


LOAI_B = ["sach", "sach", "nhieu", "sach", "mo", "sach"]


# ------------------------------------------------------------------------------------------------ máy chủ thử + đo bộ nhớ
def _cong_dang_nghe(cong: int) -> int | None:
    """PID tiến trình đang NGHE cổng (netstat -ano, chỉ đọc)."""
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, errors="replace").stdout
    for d in out.splitlines():
        p = d.split()
        if len(p) >= 5 and p[1].endswith(f":{cong}") and p[3].upper() == "LISTENING":
            return int(p[4])
    return None


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def bo_nho_mb(pid: int) -> tuple[float, float] | None:
    """(working set hiện tại, đỉnh working set) MB của tiến trình – Windows API, không cần psutil."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x1000 | 0x0010, False, pid)
    if not h:
        return None
    try:
        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        if not k32.K32GetProcessMemoryInfo(ctypes.c_void_p(h), ctypes.byref(pmc), pmc.cb):
            return None
        return pmc.WorkingSetSize / 2 ** 20, pmc.PeakWorkingSetSize / 2 ** 20
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


class MayChu:
    def __init__(self):
        self.p = None
        self.pid = None

    def bat(self) -> None:
        if _cong_dang_nghe(CONG):
            raise SystemExit(f"DỪNG: cổng {CONG} đang bận")
        env = dict(os.environ, AUTH_MODE="on", ANH_XOA_TU_DONG="0", STORAGE_DIR=str(KHO), PYTHONIOENCODING="utf-8")
        KHO.mkdir(parents=True, exist_ok=True)
        self.log = open(LOG_MAY_CHU, "w", encoding="utf-8")
        self.p = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(CONG),
                                   "--log-level", "warning"], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        import httpx
        for _ in range(240):
            try:
                if httpx.get(f"{GOC}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if self.p.poll() is not None:
                raise SystemExit(f"DỪNG: máy chủ thử thoát sớm – xem {LOG_MAY_CHU}")
            time.sleep(0.5)
        else:
            raise SystemExit("DỪNG: máy chủ thử không lên sau 120 s")
        self.pid = _cong_dang_nghe(CONG)          # venv Windows: python.exe là trình khởi chạy -> tiến trình thật là con; lấy PID theo cổng

    def tat(self) -> None:
        if self.p and self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(15)
            except subprocess.TimeoutExpired:
                self.p.kill()
        if self.pid and _cong_dang_nghe(CONG) == self.pid:           # tiến trình con (python thật) của trình khởi chạy venv
            subprocess.run(["taskkill", "/PID", str(self.pid), "/F"], capture_output=True)
        if getattr(self, "log", None):
            self.log.close()


class LayMau(threading.Thread):
    """Lấy mẫu bộ nhớ máy chủ + số kết nối CSDL của role (pg_stat_activity, chỉ đọc) mỗi 0,25 s."""

    def __init__(self, pid: int):
        super().__init__(daemon=True)
        self.pid, self.dung_lai, self.mau = pid, threading.Event(), []

    def run(self):
        from backend.db import ket_noi
        c = ket_noi()
        c.autocommit = True
        t0 = time.perf_counter()
        while not self.dung_lai.is_set():
            m = bo_nho_mb(self.pid)
            n = c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE usename = current_user AND pid <> pg_backend_pid()").fetchone()["n"]
            self.mau.append({"t": round(time.perf_counter() - t0, 2), "mb": round(m[0], 1) if m else None, "ket_noi_csdl": n})
            time.sleep(0.25)
        c.close()

    def tom_tat(self) -> dict:
        mb = [x["mb"] for x in self.mau if x["mb"] is not None]
        return {"mb_dau": mb[0] if mb else None, "mb_dinh": max(mb) if mb else None, "mb_cuoi": mb[-1] if mb else None,
                "ket_noi_csdl_dinh": max((x["ket_noi_csdl"] for x in self.mau), default=None), "so_mau": len(self.mau)}


# ------------------------------------------------------------------------------------------------ HTTP
def phien(local: str | None = None):
    import httpx
    return httpx.Client(base_url=GOC, timeout=300, transport=httpx.HTTPTransport(local_address=local) if local else None)


def dang_nhap(c, ten: str, mk: str):
    return c.post("/auth/login", json={"username": ten, "password": mk})


def tai(c, exam_id: int, du_lieu: bytes, ten: str) -> dict:
    t0, bat_dau = time.perf_counter(), time.time()
    try:
        r = c.post(f"/exams/{exam_id}/sheets", files={"file": (ten, du_lieu, "image/jpeg")})
        ma, body = r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:300])
    except Exception as e:  # noqa: BLE001 – lỗi mạng / hết giờ: ghi lại, không che
        ma, body = -1, f"{type(e).__name__}: {e}"
    return {"ten": ten, "http": ma, "body": body, "ms": round((time.perf_counter() - t0) * 1000), "bat_dau": bat_dau, "ket_thuc": time.time()}


def tom_tat_phieu(c, sid: int) -> dict:
    v = c.get(f"/sheets/{sid}").json()
    sc = v.get("score") or {}
    return {"status": v["status"], "tam": sc.get("provisional"), "chinh_thuc": sc.get("official"), "kq": sc.get("result_status"),
            "cho": sc.get("pending_questions"), "sbd": (v.get("sbd") or {}).get("detected"), "sbd_cx": (v.get("sbd") or {}).get("can_xem"),
            "ma_de": (v.get("exam_code") or {}).get("detected"), "sv": (v.get("student") or {}).get("student_code"),
            "ly_do": sorted((v.get("review") or {}).get("reasons") or []) if v["status"] == "needs_review" else [],
            "cau": [(q["question_no"], q["selected_options"], q["needs_review"], tuple(q["reasons"] or [])) for q in v["questions"]]}


def tk(xs: list[float]) -> dict:
    if not xs:
        return {}
    s = sorted(xs)
    return {"n": len(s), "trung_vi": round(statistics.median(s)), "p95": round(s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]),
            "max": round(s[-1]), "min": round(s[0])}


# ------------------------------------------------------------------------------------------------ kịch bản
class Thu:
    def __init__(self, hs: dict, mc: MayChu):
        self.hs, self.mc, self.ve = hs, mc, Ve()
        self.mk = hs["_mk"]
        self.u = [f"{TIEN_TO_USER}{k}" for k in (1, 2, 3)]
        self.ss: dict[str, object] = {}                       # phiên chính của mỗi tài khoản (dùng cho B–E)
        self.kq: dict = {}

    def X(self, k: str) -> int:
        return self.hs["exams"][k]

    def phien_dang_nhap(self, ten: str):
        c = phien()
        r = dang_nhap(c, ten, self.mk[ten])
        if r.status_code != 200:
            raise RuntimeError(f"không đăng nhập được {ten}: {r.status_code}")
        return c

    def phien_phu(self, ten: str):
        """Tab / luồng thứ hai của CÙNG phiên (cùng cookie) – như /m gửi 2 ảnh song song."""
        c = phien()
        c.cookies.update(self.ss[ten].cookies)
        return c

    # ---------------------------------------------------------------- A
    def kich_ban_a(self) -> dict:
        u1, u2, u3 = self.u
        self.ss[u3] = self.phien_dang_nhap(u3)                 # tài khoản 3 đã đăng nhập từ trước (phiên S3a)
        rao = threading.Barrier(5)
        nhat_ky: dict[str, list] = {}

        def lam(ten: str, so_lan: int = 5, c=None):
            c = c or phien()
            ghi = nhat_ky.setdefault(ten if c is not self.ss.get(u3) else f"{ten}#S3a", [])
            rao.wait()
            if ten != u3 or c is not self.ss.get(u3):
                r = dang_nhap(c, ten, self.mk[ten])
                ghi.append(("login", r.status_code, (r.json() or {}).get("username") if r.status_code == 200 else None))
            for _ in range(so_lan):
                me = c.get("/me")
                ex = c.get("/exams")
                cl = c.get("/me/classes")
                ghi.append(("me", me.status_code, me.json().get("username") if me.status_code == 200 else None))
                ghi.append(("exams", ex.status_code, sorted(x["exam_id"] for x in ex.json()) if ex.status_code == 200 else None))
                ghi.append(("classes", cl.status_code, sorted(x["class_code"] for x in cl.json()) if cl.status_code == 200 else None))
            return c

        def sai():
            c = phien()
            ghi = nhat_ky.setdefault("sai_mat_khau_" + u3, [])
            rao.wait()
            for i in range(5):
                r = dang_nhap(c, u3, "sai-mat-khau-" + str(i))
                ghi.append(("login_sai", r.status_code, r.json().get("detail")))

        with ThreadPoolExecutor(5) as ex:
            f1 = ex.submit(lam, u1)
            f2 = ex.submit(lam, u2)
            f1b = ex.submit(lam, u1, 3)                          # CÙNG tài khoản 1, "trình duyệt" thứ hai
            f3 = ex.submit(lam, u3, 5, self.ss[u3])              # phiên S3a của tài khoản 3 vẫn làm việc trong lúc bị thử sai
            fs = ex.submit(sai)
            c1, c2, c1b = f1.result(), f2.result(), f1b.result()
            f3.result(), fs.result()
        self.ss[u1], self.ss[u2] = c1, c2

        X = self.hs["exams"]
        mong_exams = {u1: sorted([X["X1"], X["X1s"], X["XD"], X["XR"]]), u2: sorted([X["X2"], X["X2s"], X["XD"]]), u3: sorted([X["X3"], X["X3s"]])}
        mong_lop = {u1: ["AH-THU-L1", "AH-THU-LD"], u2: ["AH-THU-L2", "AH-THU-LD"], u3: ["AH-THU-L3"]}
        kiem = []
        for khoa, ghi in nhat_ky.items():
            ten = khoa.split("#")[0]
            if khoa.startswith("sai_"):
                kiem.append((khoa, all(x[1] == 401 for x in ghi), [x[1] for x in ghi]))
                continue
            sai_lech = [x for x in ghi if x[1] != 200 or (x[0] in ("login", "me") and x[2] != ten)
                        or (x[0] == "exams" and x[2] != mong_exams[ten]) or (x[0] == "classes" and x[2] != mong_lop[ten])]
            kiem.append((khoa, not sai_lech, sai_lech[:3]))

        # Sau khi tài khoản 3 bị sai 5 lần (cùng IP 127.0.0.1):
        sau = {}
        sau["u3_dang_nhap_dung_cung_ip"] = dang_nhap(phien(), u3, self.mk[u3]).status_code                  # mong 429
        sau["u3_phien_cu_S3a_me"] = self.ss[u3].get("/me").status_code                                     # mong 200
        sau["u1_dang_nhap_lai"] = dang_nhap(phien(), u1, self.mk[u1]).status_code                          # mong 200
        sau["u2_dang_nhap_lai"] = dang_nhap(phien(), u2, self.mk[u2]).status_code                          # mong 200
        try:
            sau["u3_dang_nhap_dung_ip_khac_127_0_0_2"] = dang_nhap(phien("127.0.0.2"), u3, self.mk[u3]).status_code   # khoá theo (tên, IP)
        except Exception as e:  # noqa: BLE001
            sau["u3_dang_nhap_dung_ip_khac_127_0_0_2"] = f"không thử được: {type(e).__name__}"
        # Hai trình duyệt cùng tài khoản: đăng xuất ở B không ảnh hưởng A; token của B vẫn dùng được nếu bị chép lại (phiên không lưu máy chủ)
        tok_b = c1b.cookies.get("se_session")
        r = c1b.post("/auth/logout")
        sau["u1_B_dang_xuat"] = r.status_code
        sau["u1_B_sau_dang_xuat_me"] = c1b.get("/me").status_code                                           # cookie bị xoá -> 401
        sau["u1_A_sau_khi_B_dang_xuat_me"] = self.ss[u1].get("/me").status_code                              # mong 200
        sau["u1_token_B_chep_lai_sau_dang_xuat_me"] = phien().get("/me", headers={"Authorization": f"Bearer {tok_b}"}).status_code
        mong = {"u3_dang_nhap_dung_cung_ip": 429, "u3_phien_cu_S3a_me": 200, "u1_dang_nhap_lai": 200, "u2_dang_nhap_lai": 200,
                "u3_dang_nhap_dung_ip_khac_127_0_0_2": 200, "u1_B_dang_xuat": 204, "u1_B_sau_dang_xuat_me": 401, "u1_A_sau_khi_B_dang_xuat_me": 200}
        dat = all(x[1] for x in kiem) and all(sau[k] == v for k, v in mong.items())
        return {"dat": dat, "kiem_luong": kiem, "sau": sau, "mong": mong,
                "ghi_chu": "u1_token_B_chep_lai_sau_dang_xuat_me = 200 nghĩa là đăng xuất KHÔNG thu hồi token (chỉ xoá cookie) – rủi ro, không tính vào đạt/không đạt"}

    # ---------------------------------------------------------------- B
    def anh_tai_khoan(self, k: int, chi_so: range, loai: list[str]) -> list[dict]:
        out = []
        for j, i in enumerate(chi_so):
            lo = loai[j % len(loai)]
            cau, n_dung = bai_lam(HAT_GIONG + 1000 * k + i, lo)
            sbd = ma_sv(k, i)
            out.append({"ten": f"ah_k{k}_{i:02d}_{lo}.jpg", "anh": self.ve.anh(cau, sbd), "loai": lo, "sbd": sbd, "n_dung": n_dung})
        return out

    def chay_song_song(self, viec: dict[str, list[tuple[int, dict]]], luong_moi_tk: int = 2) -> list[dict]:
        """viec: {tài khoản: [(exam_id, ảnh)…]}. Mỗi tài khoản `luong_moi_tk` luồng (như /m: tối đa 2 ảnh song song), bắt đầu cùng lúc."""
        tong = sum(min(luong_moi_tk, len(v)) for v in viec.values())
        rao = threading.Barrier(tong)
        kq, khoa = [], threading.Lock()

        def tho(ten, hang):
            c = self.phien_phu(ten)
            rao.wait()
            while True:
                with khoa:
                    if not hang:
                        return
                    eid, a = hang.pop(0)
                r = tai(c, eid, a["anh"], a["ten"])
                r.update(tai_khoan=ten, exam_id=eid, anh=a)
                with khoa:
                    kq.append(r)

        with ThreadPoolExecutor(tong) as ex:
            fs = [ex.submit(tho, ten, hang) for ten, hang in ((t, list(v)) for t, v in viec.items()) for _ in range(min(luong_moi_tk, len(hang)))]
            for f in fs:
                f.result()
        return kq

    def kich_ban_b(self) -> dict:
        anh = {k: self.anh_tai_khoan(k, range(1, 7), LOAI_B) for k in (1, 2, 3)}
        # 1) đối chứng: TUẦN TỰ từng ảnh, một mình, vào kỳ thi X{k}s
        tuan_tu = []
        for k in (1, 2, 3):
            c = self.ss[self.u[k - 1]]
            for a in anh[k]:
                r = tai(c, self.X(f"X{k}s"), a["anh"], a["ten"])
                r.update(tai_khoan=self.u[k - 1], anh=a)
                tuan_tu.append(r)
        # 2) đồng thời: 3 tài khoản × 6 ảnh, mỗi tài khoản 2 luồng, cùng thời điểm, vào X{k}
        t0 = time.perf_counter()
        dong = self.chay_song_song({self.u[k - 1]: [(self.X(f"X{k}"), a) for a in anh[k]] for k in (1, 2, 3)})
        tuong = round((time.perf_counter() - t0) * 1000)
        # 3) so sánh từng ảnh
        theo_ten = {r["ten"]: r for r in tuan_tu}
        lech, loi = [], []
        for r in dong + tuan_tu:
            if r["http"] != 201:
                loi.append((r["ten"], r["http"], str(r["body"])[:200]))
        for r in dong:
            s = theo_ten[r["ten"]]
            if r["http"] != 201 or s["http"] != 201:
                continue
            c = self.ss[r["tai_khoan"]]
            a, b = tom_tat_phieu(c, r["body"]["sheet_id"]), tom_tat_phieu(c, s["body"]["sheet_id"])
            r["tom_tat"], s["tom_tat"] = a, b
            if a != b:
                lech.append((r["ten"], {k: (a[k], b[k]) for k in a if a[k] != b[k] and k != "cau"}, "cau" if a["cau"] != b["cau"] else ""))
        mong_sai = []                                      # kiểm ĐỘC LẬP theo cách vẽ ảnh: ảnh sạch -> graded, điểm = số câu đúng × 0,25
        for r in dong:
            t = r.get("tom_tat")
            if not t:
                continue
            a = r["anh"]
            if a["loai"] == "sach" and not (t["status"] == "graded" and float(t["chinh_thuc"]) == a["n_dung"] * 0.25 and t["sv"] == a["sbd"]):
                mong_sai.append((r["ten"], t["status"], t["chinh_thuc"], a["n_dung"] * 0.25))
            if a["loai"] != "sach" and t["status"] != "needs_review":
                mong_sai.append((r["ten"], t["status"], "mong needs_review"))
        dat = not loi and not lech and not mong_sai and len(dong) == 18
        return {"dat": dat, "loi_http": loi, "lech_so_voi_tuan_tu": lech, "sai_so_voi_ky_vong": mong_sai,
                "ms_tuan_tu": tk([r["ms"] for r in tuan_tu]), "ms_dong_thoi": tk([r["ms"] for r in dong]), "tuong_ms_dong_thoi": tuong,
                "tuong_ms_tuan_tu": sum(r["ms"] for r in tuan_tu),
                "trang_thai": {s: sum(1 for r in dong if (r.get("tom_tat") or {}).get("status") == s) for s in ("graded", "needs_review", "rejected")},
                "may_chu_ms_tuan_tu": tk([self._ms_may_chu(r) for r in tuan_tu if self._ms_may_chu(r) is not None]),
                "may_chu_ms_dong_thoi": tk([self._ms_may_chu(r) for r in dong if self._ms_may_chu(r) is not None]),
                "_phieu": {"dong": [(r["tai_khoan"], r["exam_id"], (r["body"] or {}).get("sheet_id") if r["http"] == 201 else None) for r in dong]}}

    def _ms_may_chu(self, r) -> int | None:
        """Thời gian xử lý ảnh do máy chủ đo (processing_time_ms: tiền xử lý + OMR + CNN), đọc qua CSDL chỉ đọc."""
        if r["http"] != 201:
            return None
        from backend.db import ket_noi
        with ket_noi() as c:
            c.execute("SET TRANSACTION READ ONLY")
            x = c.execute("SELECT processing_time_ms FROM answer_sheets WHERE sheet_id = %s", (r["body"]["sheet_id"],)).fetchone()
        return x["processing_time_ms"] if x else None

    # ---------------------------------------------------------------- C
    def kich_ban_c(self, phieu_b: list) -> dict:
        X = self.hs["exams"]
        cua = {self.u[0]: {X["X1"], X["X1s"], X["XD"], X["XR"]}, self.u[1]: {X["X2"], X["X2s"], X["XD"]}, self.u[2]: {X["X3"], X["X3s"]}}
        lop = {self.u[0]: {self.hs["classes"]["L1"], self.hs["classes"]["LD"]}, self.u[1]: {self.hs["classes"]["L2"], self.hs["classes"]["LD"]},
               self.u[2]: {self.hs["classes"]["L3"]}}
        phieu = {}                                                 # exam_id -> [sheet_id]
        for _, eid, sid in phieu_b:
            if sid:
                phieu.setdefault(eid, []).append(sid)
        ten_sv = {f"{TEN_SV} {m}" for m in self.hs["students"]}
        thu, sai = 0, []
        for ten in self.u:
            c = self.ss[ten]
            ngoai_exam = sorted(set(X.values()) - cua[ten])
            ngoai_lop = sorted(set(self.hs["classes"].values()) - lop[ten])
            yeu_cau = []
            for e in ngoai_exam:
                yeu_cau += [("GET", f"/exams/{e}"), ("GET", f"/exams/{e}/sheets"), ("GET", f"/exams/{e}/results"), ("GET", f"/exams/{e}/export.xlsx"),
                            ("GET", f"/exams/{e}/cover.pdf"), ("GET", f"/exams/{e}/review-questions"), ("GET", f"/exams/{e}/review-groups"),
                            ("POST_ANH", f"/exams/{e}/sheets")]
                for s in phieu.get(e, [])[:3]:
                    yeu_cau += [("GET", f"/sheets/{s}"), ("GET", f"/sheets/{s}/image?kind=original"), ("GET", f"/sheets/{s}/image?kind=aligned"),
                                ("GET", f"/sheets/{s}/questions/1/image"), ("GET", f"/sheets/{s}/digits/sbd/0/image"),
                                ("GET", f"/sheets/{s}/review-questions"), ("POST_REVIEW", f"/sheets/{s}/questions/40/review"),
                                ("PUT_ID", f"/sheets/{s}/identity"), ("POST", f"/sheets/{s}/duplicate/discard"),
                                ("POST_HL", f"/sheets/{s}/questions/confirm-remaining")]
            for l_ in ngoai_lop:
                yeu_cau.append(("GET", f"/classes/{l_}/students"))
            for loai, url in yeu_cau:
                if loai == "GET":
                    r = c.get(url)
                elif loai == "POST_ANH":
                    r = c.post(url, files={"file": ("x.jpg", b"\xff\xd8 khong-phai-anh", "image/jpeg")})
                elif loai == "POST_REVIEW":
                    r = c.post(url, json={"action": "set", "selected_options": "A"})
                elif loai == "PUT_ID":
                    r = c.put(url, json={"sbd": "000000"})
                elif loai == "POST_HL":
                    r = c.post(url, json={"question_nos": [40], "confirm": True})
                else:
                    r = c.post(url)
                thu += 1
                body = r.content.decode("utf-8", "replace")
                ro = [x for x in ten_sv if x in body] + [m for m in self.hs["students"] if m in body]
                if r.status_code != 404 or ro:
                    sai.append((ten, loai, url, r.status_code, ro[:3], body[:150]))
            ds = {x["exam_id"] for x in c.get("/exams").json()}
            if ds != cua[ten]:
                sai.append((ten, "GET", "/exams", "danh sách lệch", sorted(ds), sorted(cua[ten])))
            thu += 1
        from backend.db import ket_noi
        with ket_noi() as c:                                                 # thử tải ảnh vào kỳ thi người khác KHÔNG được tạo phiếu nào
            c.execute("SET TRANSACTION READ ONLY")
            khong_phieu_la = c.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = ANY(%s) AND original_filename = 'x.jpg'",
                                       (list(X.values()),)).fetchone()["n"]
        return {"dat": not sai and khong_phieu_la == 0, "so_yeu_cau": thu, "sai": sai[:20], "so_sai": len(sai), "phieu_la_tao_ra": khong_phieu_la}

    # ---------------------------------------------------------------- D
    def _ket_qua_sv(self, eid: int, sbd: str) -> dict:
        from backend.db import ket_noi
        with ket_noi() as c:
            c.execute("SET TRANSACTION READ ONLY")
            sid = self.hs["students"][sbd]
            ct = c.execute("SELECT count(*) AS n FROM results WHERE exam_id = %s AND student_id = %s AND status <> 'void'", (eid, sid)).fetchone()["n"]
            ph = c.execute("SELECT sheet_id, status::text AS status FROM answer_sheets WHERE exam_id = %s AND matched_student_id = %s ORDER BY sheet_id",
                           (eid, sid)).fetchall()
            rv = c.execute("SELECT q.reasons::text[] AS r FROM review_queue q JOIN answer_sheets a USING (sheet_id) WHERE a.exam_id = %s "
                           "AND a.detected_sbd = %s AND q.status IN ('pending','in_progress')", (eid, sbd)).fetchall()
        return {"chinh_thuc": ct, "phieu": [(p["sheet_id"], p["status"]) for p in ph], "ly_do_cho": [x["r"] for x in rv]}

    def _cap(self, i: int, sbd: str) -> tuple[dict, dict]:
        out = []
        for j, (lo, nd) in enumerate((("sach", 40), ("sach", 20))):
            r = random.Random(HAT_GIONG + 50000 + 10 * i + j)
            vt = set(r.sample(range(SO_CAU), nd))
            cau = [DAP_AN[q] if q in vt else r.choice([x for x in "ABCD" if x != DAP_AN[q]]) for q in range(SO_CAU)]
            out.append({"ten": f"ah_d_{sbd}_{'ab'[j]}.jpg", "anh": self.ve.anh(cau, sbd), "loai": lo, "sbd": sbd, "n_dung": nd})
        return out[0], out[1]

    def _hai_cung_luc(self, eid: int, a: dict, b: dict, ten_a: str, ten_b: str, truoc_khi_doi=None) -> list[dict]:
        rao = threading.Barrier(2)

        def gui(ten, x):
            c = self.phien_phu(ten)
            rao.wait()
            return tai(c, eid, x["anh"], x["ten"])
        with ThreadPoolExecutor(2) as ex:
            fa, fb = ex.submit(gui, ten_a, a), ex.submit(gui, ten_b, b)
            if truoc_khi_doi:
                truoc_khi_doi()
            return [fa.result(), fb.result()]

    @staticmethod
    def _gon(r: dict) -> tuple:
        b = r["body"] if isinstance(r["body"], dict) else {}
        return (r["http"], b.get("status"), b.get("official_score"), b.get("da_ton_tai"), None if r["http"] in (200, 201) else str(b.get("detail", r["body"]))[:120])

    def kich_ban_d(self, so_lan: int = 20) -> dict:
        eid, u1, u2 = self.X("XD"), self.u[0], self.u[1]
        lan = []
        for i in range(1, so_lan + 1):
            sbd = ma_sv(9, i)
            a, b = self._cap(i, sbd)
            rr = self._hai_cung_luc(eid, a, b, u1, u2)
            k = self._ket_qua_sv(eid, sbd)
            lan.append({"lan": i, "sbd": sbd, "u1": self._gon(rr[0]), "u2": self._gon(rr[1]), "ms": [rr[0]["ms"], rr[1]["ms"]],
                        "lech_bat_dau_ms": round(abs(rr[0]["bat_dau"] - rr[1]["bat_dau"]) * 1000, 1),
                        "lech_ket_thuc_ms": round(abs(rr[0]["ket_thuc"] - rr[1]["ket_thuc"]) * 1000, 1), **k})
        dat = all(x["chinh_thuc"] <= 1 for x in lan) and all(x["u1"][0] not in (-1, 500) and x["u2"][0] not in (-1, 500) for x in lan)
        return {"dat": dat, "so_lan": so_lan, "lan": lan,
                "tong_hop": {"lan_co_2_chinh_thuc": sum(1 for x in lan if x["chinh_thuc"] > 1),
                             "lan_co_dung_1_chinh_thuc": sum(1 for x in lan if x["chinh_thuc"] == 1),
                             "lan_co_409": sum(1 for x in lan if 409 in (x["u1"][0], x["u2"][0])),
                             "lan_co_5xx": sum(1 for x in lan if any(500 <= c < 600 or c == -1 for c in (x["u1"][0], x["u2"][0])))}}

    def kich_ban_d_ep(self, so_lan: int = 5) -> dict:
        """ÉP cuộc đua: một kết nối của công cụ giữ LOCK TABLE results IN SHARE MODE (chặn INSERT, KHÔNG ghi gì) cho tới khi CẢ HAI yêu cầu
        đều đã qua bước kiểm trùng và đang chờ ở INSERT INTO results -> thả khoá. Đây là trường hợp xấu nhất của kịch bản D."""
        from backend.db import ket_noi
        eid, u1, u2 = self.X("XD"), self.u[0], self.u[1]
        lan = []
        for i in range(21, 21 + so_lan):
            sbd = ma_sv(9, i)
            a, b = self._cap(i, sbd)
            khoa = ket_noi()
            khoa.execute("SET lock_timeout = '60s'")
            khoa.execute("LOCK TABLE results IN SHARE MODE")
            nhin = ket_noi()
            nhin.autocommit = True
            thay = {"cho": 0}

            def doi_roi_tha():
                t0 = time.time()
                while time.time() - t0 < 60:
                    n = nhin.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE usename = current_user AND wait_event_type = 'Lock' "
                                     "AND query ILIKE 'INSERT INTO results%%'").fetchone()["n"]
                    thay["cho"] = max(thay["cho"], n)
                    if n >= 2:
                        break
                    time.sleep(0.05)
                khoa.rollback()                                                 # thả khoá (không có gì để ghi)
            try:
                rr = self._hai_cung_luc(eid, a, b, u1, u2, truoc_khi_doi=doi_roi_tha)
            finally:
                khoa.rollback()
                khoa.close()
                nhin.close()
            k = self._ket_qua_sv(eid, sbd)
            lan.append({"lan": i, "sbd": sbd, "so_yeu_cau_cung_cho_insert": thay["cho"], "u1": self._gon(rr[0]), "u2": self._gon(rr[1]), **k})
        dat = all(x["chinh_thuc"] <= 1 for x in lan) and all(x["u1"][0] not in (-1, 500) and x["u2"][0] not in (-1, 500) for x in lan)
        return {"dat": dat, "lan": lan}

    def kich_ban_d_anh_trung(self, so_lan: int = 5) -> dict:
        """Cùng MỘT ảnh (cùng byte) gửi hai lần cùng lúc – như nút "Gửi lại" khi yêu cầu đầu chưa xong, hoặc hai giáo viên cùng tải một tệp."""
        eid, u1, u2 = self.X("XD"), self.u[0], self.u[1]
        lan = []
        for i in range(31, 31 + so_lan):
            sbd = ma_sv(9, i)
            a, _ = self._cap(i, sbd)
            for cap, (ta, tb) in (("2_tai_khoan", (u1, u2)), ("cung_tai_khoan", (u1, u1))):
                b = dict(a)
                if cap == "cung_tai_khoan":                                         # ảnh khác (đổi 1 byte cuối JPEG không đổi nội dung) cho lượt 2
                    a = dict(a, anh=a["anh"] + b"\x00", ten=a["ten"].replace(".jpg", "_2.jpg"))
                    b = a
                rr = self._hai_cung_luc(eid, a, b, ta, tb)
                from backend.db import ket_noi
                with ket_noi() as c:
                    c.execute("SET TRANSACTION READ ONLY")
                    import hashlib
                    n = c.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = %s AND image_hash = %s",
                                  (eid, hashlib.sha256(a["anh"]).hexdigest())).fetchone()["n"]
                lan.append({"lan": i, "cap": cap, "u_a": self._gon(rr[0]), "u_b": self._gon(rr[1]), "so_phieu_cung_anh": n,
                            "chinh_thuc_sv": self._ket_qua_sv(eid, sbd)["chinh_thuc"]})
        dat = all(x["so_phieu_cung_anh"] == 1 and x["chinh_thuc_sv"] <= 1 for x in lan) and \
            all(x["u_a"][0] not in (-1, 500) and x["u_b"][0] not in (-1, 500) for x in lan)
        return {"dat": dat, "lan": lan}

    def kich_ban_d_lo_cheo(self, so_lan: int = 5) -> dict:
        """POST /sheets/batch (MỘT giao dịch cho cả lô): GV1 gửi [p, q], GV2 gửi [q', p'] cùng lúc (p, q = hai thí sinh khác nhau, ảnh khác nhau).
        Thứ tự khoá chéo trên chỉ mục duy nhất uq_results_exam_student -> có thể DEADLOCK giữa hai yêu cầu thật."""
        import httpx
        eid, u1, u2 = self.X("XD"), self.u[0], self.u[1]
        lan = []
        for i in range(41, 41 + 2 * so_lan, 2):
            p, q = ma_sv(9, i), ma_sv(9, i + 1)
            p1, p2 = self._cap(i, p)
            q1, q2 = self._cap(i + 1, q)
            rao = threading.Barrier(2)

            def lo(ten, ds):
                c = self.phien_phu(ten)
                rao.wait()
                t0 = time.perf_counter()
                try:
                    r = c.post(f"/exams/{eid}/sheets/batch", files=[("files", (x["ten"], x["anh"], "image/jpeg")) for x in ds])
                    return r.status_code, r.json(), round((time.perf_counter() - t0) * 1000)
                except httpx.HTTPError as e:
                    return -1, str(e), 0
            with ThreadPoolExecutor(2) as ex:
                fa, fb = ex.submit(lo, u1, [p1, q1]), ex.submit(lo, u2, [q2, p2])
                ra, rb = fa.result(), fb.result()

            def gon(r):
                if r[0] != 201:
                    return r[0], str(r[1])[:200]
                return r[0], [(x.get("status"), x.get("error")) for x in r[1]["results"]], r[2]
            kp, kq_ = self._ket_qua_sv(eid, p), self._ket_qua_sv(eid, q)
            lan.append({"lan": (i - 41) // 2 + 1, "u1_[p,q]": gon(ra), "u2_[q,p]": gon(rb), "chinh_thuc_p": kp["chinh_thuc"], "chinh_thuc_q": kq_["chinh_thuc"]})
        loi_deadlock = sum(1 for x in lan for k in ("u1_[p,q]", "u2_[q,p]") if "Deadlock" in json.dumps(x[k], ensure_ascii=False))
        loi_khac = sum(1 for x in lan for k in ("u1_[p,q]", "u2_[q,p]") if x[k][0] == 201 and any(e for _, e in x[k][1]))
        return {"dat": loi_deadlock == 0 and all(x["chinh_thuc_p"] <= 1 and x["chinh_thuc_q"] <= 1 for x in lan),
                "so_anh_loi_deadlock": loi_deadlock, "so_anh_co_loi": loi_khac, "lan": lan}

    # ---------------------------------------------------------------- E
    def kich_ban_e(self) -> dict:
        anh = {k: self.anh_tai_khoan(k, range(7, 27), ["sach"] * 8 + ["nhieu"] + ["sach"] * 8 + ["mo"] + ["sach"] * 2) for k in (1, 2, 3)}
        mau = LayMau(self.mc.pid)
        mau.start()
        time.sleep(1.0)
        t0 = time.perf_counter()
        kq = self.chay_song_song({self.u[k - 1]: [(self.X(f"X{k}"), a) for a in anh[k]] for k in (1, 2, 3)})
        tuong = round((time.perf_counter() - t0) * 1000)
        time.sleep(1.0)
        mau.dung_lai.set()
        mau.join()
        loi = [(r["ten"], r["http"], str(r["body"])[:200]) for r in kq if r["http"] != 201]
        sai = []
        for r in kq:
            if r["http"] != 201:
                continue
            t = tom_tat_phieu(self.ss[r["tai_khoan"]], r["body"]["sheet_id"])
            a = r["anh"]
            if a["loai"] == "sach" and not (t["status"] == "graded" and float(t["chinh_thuc"]) == a["n_dung"] * 0.25 and t["sv"] == a["sbd"]):
                sai.append((r["ten"], t["status"], t["chinh_thuc"], a["n_dung"] * 0.25))
            if a["loai"] != "sach" and t["status"] != "needs_review":
                sai.append((r["ten"], t["status"]))
        # số yêu cầu đang chạy lúc mỗi yêu cầu bắt đầu -> độ trễ theo mức đồng thời
        theo_muc = {}
        for r in kq:
            m = sum(1 for x in kq if x["bat_dau"] <= r["bat_dau"] < x["ket_thuc"])
            theo_muc.setdefault(m, []).append(r["ms"])
        return {"dat": not loi and not sai and len(kq) == 60, "loi_http": loi, "sai_so_voi_ky_vong": sai, "ms": tk([r["ms"] for r in kq]),
                "tuong_ms": tuong, "anh_moi_giay": round(len(kq) / (tuong / 1000), 2), "bo_nho": mau.tom_tat(),
                "ms_theo_muc_dong_thoi": {m: tk(v) for m, v in sorted(theo_muc.items())},
                "may_chu_ms": tk([self._ms_may_chu(r) for r in kq if self._ms_may_chu(r) is not None])}

    def thang_tai(self, muc: tuple = (1, 2, 4, 6, 8, 12)) -> dict:
        """Một tài khoản, N yêu cầu cùng lúc (N luồng), 2N ảnh mỗi mức -> độ trễ + thông lượng theo N. Tìm điểm bắt đầu chậm."""
        eid, ten = self.X("XR"), self.u[0]
        out, sbd_i = {}, 0
        mau = LayMau(self.mc.pid)
        mau.start()
        for n in muc:
            ds = []
            for _ in range(2 * n):
                sbd_i += 1
                cau, _ = bai_lam(HAT_GIONG + 90000 + sbd_i, "sach")
                ds.append({"ten": f"ah_r_{n}_{sbd_i}.jpg", "anh": self.ve.anh(cau, f"9795{sbd_i:02d}")})   # SBD không có trong bảng students (vùng 97… chỉ có thí sinh thử 9710xx–9790xx): chỉ đo thời gian
            t0 = time.perf_counter()
            kq = self.chay_song_song({ten: [(eid, a) for a in ds]}, luong_moi_tk=n)
            tuong = (time.perf_counter() - t0)
            out[n] = {"ms": tk([r["ms"] for r in kq]), "anh_moi_giay": round(len(kq) / tuong, 2),
                      "loi": [(r["ten"], r["http"]) for r in kq if r["http"] != 201]}
        mau.dung_lai.set()
        mau.join()
        return {"muc": out, "bo_nho": mau.tom_tat(), "dat": all(not v["loi"] for v in out.values())}


# ------------------------------------------------------------------------------------------------ chạy
def _quet_log() -> dict:
    if not LOG_MAY_CHU.exists():
        return {}
    t = LOG_MAY_CHU.read_text(encoding="utf-8", errors="replace")
    return {"traceback": t.count("Traceback"), "deadlock": t.count("DeadlockDetected"), "unique": t.count("UniqueViolation"),
            "permission": t.count("PermissionError"), "dong_cuoi": t.splitlines()[-15:]}


def chay(args) -> int:
    from backend.db import ket_noi
    OUT.mkdir(parents=True, exist_ok=True)
    with ket_noi() as c:
        c.execute("SET TRANSACTION READ ONLY")
        truoc = dem_con_lai(c)
    if any(v for k, v in truoc.items() if k != "tep_trong_kho") or truoc["tep_trong_kho"]:
        print("DỪNG: còn dữ liệu thử từ lần trước:", truoc, "– chạy: python tools/ah_thu_dong_thoi.py don")
        return 2
    ket_qua = {"ngay": datetime.now().isoformat(timespec="seconds"), "cpu": os.cpu_count(), "python": sys.version.split()[0]}
    mc = MayChu()
    hs = None
    try:
        with ket_noi() as c:                    # thoát khối = commit
            hs = dung(c)
        luu_ho_so(hs)
        print("Đã dựng dữ liệu thử:", {k: len(v) for k, v in hs.items() if isinstance(v, dict) and k != "_mk"})
        mc.bat()
        ket_qua["may_chu"] = {"pid": mc.pid, "bo_nho_luc_bat": bo_nho_mb(mc.pid) if mc.pid else None}
        t = Thu(hs, mc)
        for ten, ham in (("A", t.kich_ban_a), ("B", t.kich_ban_b)):
            print(f"Kịch bản {ten}…", flush=True)
            ket_qua[ten] = ham()
            print(f"  -> {'ĐẠT' if ket_qua[ten]['dat'] else 'KHÔNG ĐẠT'}", flush=True)
        print("Kịch bản C…", flush=True)
        ket_qua["C"] = t.kich_ban_c(ket_qua["B"].pop("_phieu")["dong"])
        print(f"  -> {'ĐẠT' if ket_qua['C']['dat'] else 'KHÔNG ĐẠT'}", flush=True)
        for ten, ham in (("D", lambda: t.kich_ban_d(args.lap_d)), ("D_ep", t.kich_ban_d_ep), ("D_anh_trung", t.kich_ban_d_anh_trung),
                         ("D_lo_cheo", t.kich_ban_d_lo_cheo), ("E", t.kich_ban_e), ("E_thang_tai", t.thang_tai)):
            print(f"Kịch bản {ten}…", flush=True)
            try:
                ket_qua[ten] = ham()
            except Exception as e:  # noqa: BLE001 – ghi lại, không che; các kịch bản sau vẫn chạy
                ket_qua[ten] = {"dat": False, "loi_cong_cu": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1500:]}
            print(f"  -> {'ĐẠT' if ket_qua[ten]['dat'] else 'KHÔNG ĐẠT'}", flush=True)
        ket_qua["may_chu"]["bo_nho_cuoi"] = bo_nho_mb(mc.pid) if mc.pid else None
    except Exception as e:  # noqa: BLE001
        ket_qua["loi_cong_cu"] = f"{type(e).__name__}: {e}"
        ket_qua["tb"] = traceback.format_exc()[-3000:]
        print("LỖI CÔNG CỤ:", ket_qua["loi_cong_cu"])
    finally:
        mc.tat()
        time.sleep(1)
        ket_qua["log_may_chu"] = _quet_log()
        ket_qua["don"] = don_tat_ca()
        print("Dọn:", ket_qua["don"]["da_xoa"], "tệp", ket_qua["don"]["tep_da_xoa"], "->", "SẠCH" if ket_qua["don"]["sach"] else f"CÒN {ket_qua['don']['con_lai']}")
        (OUT / "ket_qua.json").write_text(json.dumps(ket_qua, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        if ket_qua["don"]["sach"] and HO_SO.exists():
            HO_SO.unlink()
    print(f"Kết quả: {OUT / 'ket_qua.json'}")
    return 0 if all(ket_qua.get(k, {}).get("dat") for k in ("A", "B", "C", "D", "E")) and ket_qua["don"]["sach"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lenh", required=True)
    p = sub.add_parser("chay")
    p.add_argument("--lap-d", type=int, default=20)
    sub.add_parser("don")
    sub.add_parser("dem")
    a = ap.parse_args()
    if a.lenh == "chay":
        return chay(a)
    if a.lenh == "don":
        r = don_tat_ca()
        print(json.dumps(r, ensure_ascii=False, indent=1))
        if r["sach"] and HO_SO.exists():
            HO_SO.unlink()
        return 0 if r["sach"] else 1
    from backend.db import ket_noi
    with ket_noi() as c:
        c.execute("SET TRANSACTION READ ONLY")
        print(json.dumps(dem_con_lai(c), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
