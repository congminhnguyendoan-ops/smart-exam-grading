"""
ah_thu_dong_thoi.py - Lệnh AH (04/11/2026): THỬ THẬT nhiều giáo viên đăng nhập + chấm ĐỒNG THỜI trên máy chủ thử riêng (cổng 8010, cùng CSDL).

KHÔNG sửa mã hệ thống: chỉ gọi API công khai qua HTTP (httpx) tới một tiến trình uvicorn riêng (AUTH_MODE=on, ANH_XOA_TU_DONG=0,
STORAGE_DIR = data/_eval/ah/kho). Dữ liệu thử RIÊNG, tạo mới, ghi hồ sơ data/_eval/ah/ho_so.json và DỌN trong khối finally (kể cả khi lỗi):
  - 3 tài khoản giáo viên "ah_thu_1..3" (mật khẩu ngẫu nhiên, KHÔNG in ra), 4 lớp "AH-THU-…", môn "AHTHU", kỳ thi "[AH-THU] …",
    thí sinh mã 97xxxx (tên "AH thử …"). Không dùng / không đổi tài khoản thật (admin, gv_an, gv_binh, gv_thu, sv…).
  - Phạm vi dọn = id trong hồ sơ ∪ tiền tố trên (đã kiểm = 0 trước khi chạy); chốt an toàn: không bao giờ đụng kỳ thi 6, 1380, 1381, 1632, 1633.
Ảnh tải lên = ảnh GIẢ HOÁ vẽ trên mẫu phiếu trắng (cùng quy ước tools/thu_bo_demo.py: ô đậm xám 30, ô mờ xám 170, bubble SBD / mã đề đậm, KHÔNG có
chữ viết tay) – chỉ để thử đồng thời / an toàn, KHÔNG phải số đo độ chính xác.

  python tools/ah_thu_dong_thoi.py chay       # dựng -> kịch bản A, B, C, D (+D-ép, D-ảnh trùng, D-lô chéo), E (+ thang tải) + R1–R5 (lệnh AR) -> dọn -> data/_eval/ah/ket_qua.json
  python tools/ah_thu_dong_thoi.py chay --chi-ar   # CHỈ R1–R5 (kịch bản tái hiện 5 rủi ro, tiêu chí docs/tieu_chi_sua_ah.md); --khong-ar: chỉ A–E như lệnh AH
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
        _s.reconfigure(encoding="utf-8")
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
CAM = frozenset({6, 1380, 1381, 1632, 1633})
SO_CAU, MA_DE = 40, "101"
XAM_DAM, XAM_MO = 30, 170
HAT_GIONG = 20261104


def ma_sv(nhom: int, i: int) -> str:
    return f"97{nhom}0{i:02d}" if nhom in (1, 2, 3) else f"979{i:03d}"


def ma_ar(k: int, i: int) -> str:
    return f"96{k}{i:03d}"


def _dap_an() -> str:
    r = random.Random(HAT_GIONG)
    return "".join(r.choice("ABCD") for _ in range(SO_CAU))


DAP_AN = _dap_an()


def dung(conn, ar: bool = True) -> dict:
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
        ids = [sv(ma_sv(k, i), f"L{k}") for i in range(1, 27)]
        ky_thi(f"X{k}", f"GV{k} – đồng thời", f"L{k}", f"{TIEN_TO_USER}{k}", ids)
        ky_thi(f"X{k}s", f"GV{k} – tuần tự (đối chứng)", f"L{k}", f"{TIEN_TO_USER}{k}", ids)
    ids_d = [sv(ma_sv(9, i), "LD") for i in range(1, 61)]
    ky_thi("XD", "lớp chung GV1+GV2 – tranh chấp SBD", "LD", f"{TIEN_TO_USER}1", ids_d)
    ky_thi("XR", "GV1 – thang tải", "L1", f"{TIEN_TO_USER}1", [])
    if ar:
        for khoa, k, so in (("XA1", 1, 70), ("XA2", 2, 70), ("XA3", 3, 200), ("XA5", 5, 20)):
            ky_thi(khoa, f"AR {khoa}", "LD", f"{TIEN_TO_USER}1", [sv(ma_ar(k, i), "LD") for i in range(1, so + 1)])
    return hs


def luu_ho_so(hs: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    HO_SO.write_text(json.dumps({k: v for k, v in hs.items() if k != "_mk"}, ensure_ascii=False, indent=1), encoding="utf-8")


def pham_vi_don(conn) -> dict:
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
    students = [r["student_id"] for r in conn.execute("SELECT student_id FROM students WHERE (student_code LIKE '97%%' OR student_code LIKE '96%%') "
                                                      "AND full_name LIKE %s", (TEN_SV + "%",)).fetchall()]
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


def dem_thu_hoi_token(conn) -> int | None:
    try:
        return conn.execute("SELECT count(*) AS n FROM revoked_tokens WHERE user_id IN (SELECT user_id FROM users WHERE username LIKE %s)",
                            (TIEN_TO_USER.replace("_", "\\_") + "%",)).fetchone()["n"]
    except Exception:  # noqa: BLE001
        conn.rollback()
        return None


def don(conn) -> dict:
    pv = pham_vi_don(conn)
    e, u = pv["exams"], pv["users"]
    so = {}
    for ten, sql, tham in (
            ("score_audit_logs", "DELETE FROM score_audit_logs WHERE result_id IN (SELECT result_id FROM results WHERE exam_id = ANY(%s))", (e,)),
            ("results", "DELETE FROM results WHERE exam_id = ANY(%s)", (e,)),
            ("answer_sheets", "DELETE FROM answer_sheets WHERE exam_id = ANY(%s)", (e,)),
            ("scan_batches", "DELETE FROM scan_batches WHERE exam_id = ANY(%s)", (e,)),
            ("exams", "DELETE FROM exams WHERE exam_id = ANY(%s)", (e,)),
            ("students", "DELETE FROM students WHERE student_id = ANY(%s)", (pv["students"],)),
            ("classes", "DELETE FROM classes WHERE class_id = ANY(%s)", (pv["classes"],)),
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


def _cong_dang_nghe(cong: int) -> int | None:
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

    def bat(self, env_them: dict | None = None) -> None:
        if _cong_dang_nghe(CONG):
            raise SystemExit(f"DỪNG: cổng {CONG} đang bận")
        env = dict(os.environ, AUTH_MODE="on", ANH_XOA_TU_DONG="0", STORAGE_DIR=str(KHO), PYTHONIOENCODING="utf-8", **(env_them or {}))
        KHO.mkdir(parents=True, exist_ok=True)
        self.log = open(LOG_MAY_CHU, "a" if env_them else "w", encoding="utf-8")
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
        self.pid = _cong_dang_nghe(CONG)

    def tat(self) -> None:
        if self.p and self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(15)
            except subprocess.TimeoutExpired:
                self.p.kill()
        if self.pid and _cong_dang_nghe(CONG) == self.pid:
            subprocess.run(["taskkill", "/PID", str(self.pid), "/F"], capture_output=True)
        if getattr(self, "log", None):
            self.log.close()


class LayMau(threading.Thread):

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


class Thu:
    def __init__(self, hs: dict, mc: MayChu):
        self.hs, self.mc, self.ve = hs, mc, Ve()
        self.mk = hs["_mk"]
        self.u = [f"{TIEN_TO_USER}{k}" for k in (1, 2, 3)]
        self.ss: dict[str, object] = {}
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
        c = phien()
        c.cookies.update(self.ss[ten].cookies)
        return c

    def kich_ban_a(self) -> dict:
        u1, u2, u3 = self.u
        self.ss[u3] = self.phien_dang_nhap(u3)
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
            f1b = ex.submit(lam, u1, 3)
            f3 = ex.submit(lam, u3, 5, self.ss[u3])
            fs = ex.submit(sai)
            c1, c2, c1b = f1.result(), f2.result(), f1b.result()
            f3.result(), fs.result()
        self.ss[u1], self.ss[u2] = c1, c2

        X = self.hs["exams"]
        xa = [X[k] for k in ("XA1", "XA2", "XA3", "XA5") if k in X]
        mong_exams = {u1: sorted([X["X1"], X["X1s"], X["XD"], X["XR"], *xa]), u2: sorted([X["X2"], X["X2s"], X["XD"], *xa]), u3: sorted([X["X3"], X["X3s"]])}
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

        sau = {}
        sau["u3_dang_nhap_dung_cung_ip"] = dang_nhap(phien(), u3, self.mk[u3]).status_code
        sau["u3_phien_cu_S3a_me"] = self.ss[u3].get("/me").status_code
        sau["u1_dang_nhap_lai"] = dang_nhap(phien(), u1, self.mk[u1]).status_code
        sau["u2_dang_nhap_lai"] = dang_nhap(phien(), u2, self.mk[u2]).status_code
        try:
            sau["u3_dang_nhap_dung_ip_khac_127_0_0_2"] = dang_nhap(phien("127.0.0.2"), u3, self.mk[u3]).status_code
        except Exception as e:  # noqa: BLE001
            sau["u3_dang_nhap_dung_ip_khac_127_0_0_2"] = f"không thử được: {type(e).__name__}"
        tok_b = c1b.cookies.get("se_session")
        r = c1b.post("/auth/logout")
        sau["u1_B_dang_xuat"] = r.status_code
        sau["u1_B_sau_dang_xuat_me"] = c1b.get("/me").status_code
        sau["u1_A_sau_khi_B_dang_xuat_me"] = self.ss[u1].get("/me").status_code
        sau["u1_token_B_chep_lai_sau_dang_xuat_me"] = phien().get("/me", headers={"Authorization": f"Bearer {tok_b}"}).status_code
        mong = {"u3_dang_nhap_dung_cung_ip": 429, "u3_phien_cu_S3a_me": 200, "u1_dang_nhap_lai": 200, "u2_dang_nhap_lai": 200,
                "u3_dang_nhap_dung_ip_khac_127_0_0_2": 200, "u1_B_dang_xuat": 204, "u1_B_sau_dang_xuat_me": 401, "u1_A_sau_khi_B_dang_xuat_me": 200}
        dat = all(x[1] for x in kiem) and all(sau[k] == v for k, v in mong.items())
        return {"dat": dat, "kiem_luong": kiem, "sau": sau, "mong": mong,
                "ghi_chu": "u1_token_B_chep_lai_sau_dang_xuat_me = 200 nghĩa là đăng xuất KHÔNG thu hồi token (chỉ xoá cookie) – rủi ro, không tính vào đạt/không đạt"}

    def anh_tai_khoan(self, k: int, chi_so: range, loai: list[str]) -> list[dict]:
        out = []
        for j, i in enumerate(chi_so):
            lo = loai[j % len(loai)]
            cau, n_dung = bai_lam(HAT_GIONG + 1000 * k + i, lo)
            sbd = ma_sv(k, i)
            out.append({"ten": f"ah_k{k}_{i:02d}_{lo}.jpg", "anh": self.ve.anh(cau, sbd), "loai": lo, "sbd": sbd, "n_dung": n_dung})
        return out

    def chay_song_song(self, viec: dict[str, list[tuple[int, dict]]], luong_moi_tk: int = 2) -> list[dict]:
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
        tuan_tu = []
        for k in (1, 2, 3):
            c = self.ss[self.u[k - 1]]
            for a in anh[k]:
                r = tai(c, self.X(f"X{k}s"), a["anh"], a["ten"])
                r.update(tai_khoan=self.u[k - 1], anh=a)
                tuan_tu.append(r)
        t0 = time.perf_counter()
        dong = self.chay_song_song({self.u[k - 1]: [(self.X(f"X{k}"), a) for a in anh[k]] for k in (1, 2, 3)})
        tuong = round((time.perf_counter() - t0) * 1000)
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
        mong_sai = []
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
        if r["http"] != 201:
            return None
        from backend.db import ket_noi
        with ket_noi() as c:
            c.execute("SET TRANSACTION READ ONLY")
            x = c.execute("SELECT processing_time_ms FROM answer_sheets WHERE sheet_id = %s", (r["body"]["sheet_id"],)).fetchone()
        return x["processing_time_ms"] if x else None

    def kich_ban_c(self, phieu_b: list) -> dict:
        X = self.hs["exams"]
        xa = {X[k] for k in ("XA1", "XA2", "XA3", "XA5") if k in X}
        cua = {self.u[0]: {X["X1"], X["X1s"], X["XD"], X["XR"]} | xa, self.u[1]: {X["X2"], X["X2s"], X["XD"]} | xa, self.u[2]: {X["X3"], X["X3s"]}}
        lop = {self.u[0]: {self.hs["classes"]["L1"], self.hs["classes"]["LD"]}, self.u[1]: {self.hs["classes"]["L2"], self.hs["classes"]["LD"]},
               self.u[2]: {self.hs["classes"]["L3"]}}
        phieu = {}
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
        with ket_noi() as c:
            c.execute("SET TRANSACTION READ ONLY")
            khong_phieu_la = c.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = ANY(%s) AND original_filename = 'x.jpg'",
                                       (list(X.values()),)).fetchone()["n"]
        return {"dat": not sai and khong_phieu_la == 0, "so_yeu_cau": thu, "sai": sai[:20], "so_sai": len(sai), "phieu_la_tao_ra": khong_phieu_la}

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
                khoa.rollback()
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
        eid, u1, u2 = self.X("XD"), self.u[0], self.u[1]
        lan = []
        for i in range(31, 31 + so_lan):
            sbd = ma_sv(9, i)
            a, _ = self._cap(i, sbd)
            for cap, (ta, tb) in (("2_tai_khoan", (u1, u2)), ("cung_tai_khoan", (u1, u1))):
                b = dict(a)
                if cap == "cung_tai_khoan":
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

    def _cap_ar(self, hat: int, sbd: str) -> tuple[dict, dict]:
        out = []
        for j, nd in enumerate((40, 20)):
            r = random.Random(HAT_GIONG + 70000 + 10 * hat + j)
            vt = set(r.sample(range(SO_CAU), nd))
            cau = [DAP_AN[q] if q in vt else r.choice([x for x in "ABCD" if x != DAP_AN[q]]) for q in range(SO_CAU)]
            out.append({"ten": f"ar_{sbd}_{'ab'[j]}.jpg", "anh": self.ve.anh(cau, sbd), "sbd": sbd, "n_dung": nd})
        return out[0], out[1]

    def _chu_ky_sbd(self, eid: int, sbd: str) -> tuple:
        k = self._ket_qua_sv(eid, sbd)
        return (len(k["phieu"]), k["chinh_thuc"], tuple(sorted(st for _, st in k["phieu"])), sum(1 for r in k["ly_do_cho"] if "duplicate_sbd" in r))

    def _dua_ep(self, eid: int, a: dict, b: dict, ta: str, tb: str) -> list[dict]:
        from backend.db import ket_noi
        khoa = ket_noi()
        khoa.execute("SET lock_timeout = '60s'")
        khoa.execute("LOCK TABLE results IN SHARE MODE")
        nhin = ket_noi()
        nhin.autocommit = True

        def doi_roi_tha():
            t0 = time.time()
            while time.time() - t0 < 25:
                n = nhin.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE usename = current_user AND wait_event_type = 'Lock' "
                                 "AND query ILIKE 'INSERT INTO results%%'").fetchone()["n"]
                if n >= 2:
                    break
                time.sleep(0.05)
            khoa.rollback()
        try:
            return self._hai_cung_luc(eid, a, b, ta, tb, truoc_khi_doi=doi_roi_tha)
        finally:
            khoa.rollback()
            khoa.close()
            nhin.close()

    def kich_ban_r1(self, n_tu_nhien: int = 50, n_ep: int = 10, n_tuan_tu: int = 10) -> dict:
        eid, u1, u2 = self.X("XA1"), self.u[0], self.u[1]
        tt = []
        for i in range(1, n_tuan_tu + 1):
            sbd = ma_ar(1, i)
            a, b = self._cap_ar(i, sbd)
            r1, r2 = tai(self.phien_phu(u1), eid, a["anh"], a["ten"]), tai(self.phien_phu(u2), eid, b["anh"], b["ten"])
            tt.append({"sbd": sbd, "http": [r1["http"], r2["http"]], "ky": self._chu_ky_sbd(eid, sbd)})
        mau = tt[0]["ky"]
        lan = []
        for j in range(n_tu_nhien + n_ep):
            i = n_tuan_tu + 1 + j
            sbd = ma_ar(1, i)
            a, b = self._cap_ar(i, sbd)
            ep = j >= n_tu_nhien
            t0 = time.perf_counter()
            rr = self._dua_ep(eid, a, b, u1, u2) if ep else self._hai_cung_luc(eid, a, b, u1, u2)
            lan.append({"lan": j + 1, "ep": ep, "sbd": sbd, "http": [rr[0]["http"], rr[1]["http"]], "ky": self._chu_ky_sbd(eid, sbd),
                        "ms": round((time.perf_counter() - t0) * 1000), "chi_tiet": [str(r["body"])[:120] for r in rr if r["http"] != 201]})
        tt_dat = all(x["http"] == [201, 201] and x["ky"] == mau for x in tt)
        dua_dat = [x for x in lan if x["http"] == [201, 201] and x["ky"] == mau]
        return {"dat": tt_dat and len(dua_dat) == len(lan) and len(lan) >= 60, "chu_ky_tuan_tu": mau, "tuan_tu_dat": tt_dat,
                "so_lan": len(lan), "so_lan_dat": len(dua_dat), "lan_co_409": sum(1 for x in lan if 409 in x["http"]),
                "lan_co_5xx_hoac_mang": sum(1 for x in lan if any(h == -1 or 500 <= h < 600 for h in x["http"])),
                "lan_co_2_chinh_thuc": sum(1 for x in lan if x["ky"][1] > 1), "lan_mat_phieu": sum(1 for x in lan if x["ky"][0] < 2),
                "ms_moi_cuoc_dua": tk([x["ms"] for x in lan]), "lan_loi": [x for x in lan if x not in dua_dat][:6]}

    def kich_ban_r2(self, n_hai_tk: int = 30, n_cung_tk: int = 30, n_tuan_tu: int = 10) -> dict:
        import hashlib
        from backend.db import ket_noi
        eid, u1, u2 = self.X("XA2"), self.u[0], self.u[1]

        def n_phieu(anh: bytes) -> int:
            with ket_noi() as c:
                c.execute("SET TRANSACTION READ ONLY")
                return c.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = %s AND image_hash = %s", (eid, hashlib.sha256(anh).hexdigest())).fetchone()["n"]
        tt = []
        for i in range(1, n_tuan_tu + 1):
            a, _ = self._cap_ar(100 + i, ma_ar(2, i))
            c = self.phien_phu(u1)
            r1, r2 = tai(c, eid, a["anh"], a["ten"]), tai(c, eid, a["anh"], a["ten"])
            tt.append(bool(r1["http"] == 201 and r2["http"] == 201 and r1["body"]["da_ton_tai"] is False and r2["body"]["da_ton_tai"] is True
                           and r1["body"]["sheet_id"] == r2["body"]["sheet_id"]))
        lan = []
        for j in range(n_hai_tk + n_cung_tk):
            i = n_tuan_tu + 1 + j
            a, _ = self._cap_ar(100 + i, ma_ar(2, i))
            cap = "hai_tai_khoan" if j < n_hai_tk else "cung_tai_khoan"
            rr = self._hai_cung_luc(eid, a, dict(a), u1, u2 if cap == "hai_tai_khoan" else u1)
            gon = [(r["http"], (r["body"] or {}).get("da_ton_tai") if isinstance(r["body"], dict) else None, (r["body"] or {}).get("sheet_id") if isinstance(r["body"], dict) else None) for r in rr]
            ok = (all(g[0] == 201 for g in gon) and sorted(g[1] for g in gon) == [False, True] and gon[0][2] == gon[1][2] and n_phieu(a["anh"]) == 1)
            lan.append({"lan": j + 1, "cap": cap, "gon": gon, "ok": ok})
        return {"dat": all(tt) and all(x["ok"] for x in lan), "so_lan": len(lan), "so_lan_dat": sum(1 for x in lan if x["ok"]), "tuan_tu_dat": all(tt),
                "lan_co_500_hoac_mang": sum(1 for x in lan if any(g[0] == -1 or 500 <= g[0] < 600 for g in x["gon"])),
                "lan_co_409": sum(1 for x in lan if any(g[0] == 409 for g in x["gon"])), "lan_loi": [x for x in lan if not x["ok"]][:6]}

    def kich_ban_r3(self, so_lan: int = 100) -> dict:
        import httpx
        eid, u1, u2 = self.X("XA3"), self.u[0], self.u[1]
        dl_truoc = _dem_log("DeadlockDetected")
        lan = []
        for rep in range(so_lan):
            p, q = ma_ar(3, 2 * rep + 1), ma_ar(3, 2 * rep + 2)
            p1, p2 = self._cap_ar(200 + 2 * rep, p)
            q1, q2 = self._cap_ar(200 + 2 * rep + 1, q)
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

            def loi_anh(r):
                return [x.get("error") for x in r[1]["results"] if x.get("error")] if r[0] == 201 else [str(r[1])[:150]]
            kp, kq_ = self._ket_qua_sv(eid, p), self._ket_qua_sv(eid, q)
            lan.append({"lan": rep + 1, "http": [ra[0], rb[0]], "loi": loi_anh(ra) + loi_anh(rb), "ms": [ra[2], rb[2]], "chinh_thuc": [kp["chinh_thuc"], kq_["chinh_thuc"]]})
        dl_sau = _dem_log("DeadlockDetected")
        dl_than = sum(1 for x in lan if any("eadlock" in e for e in x["loi"]))
        ok = [x for x in lan if x["http"] == [201, 201] and not x["loi"] and max(x["chinh_thuc"]) <= 1]
        return {"dat": len(ok) == len(lan) == so_lan and dl_than == 0 and dl_sau == dl_truoc, "so_lan": len(lan), "so_lan_dat": len(ok), "deadlock_trong_than": dl_than,
                "deadlock_trong_log": dl_sau - dl_truoc, "lan_co_500_hoac_mang": sum(1 for x in lan if any(h == -1 or 500 <= h < 600 for h in x["http"])),
                "ms_moi_lo": tk([m for x in lan for m in x["ms"]]), "lan_loi": [x for x in lan if x not in ok][:5]}

    def kich_ban_r4(self, so_luot: int = 3) -> dict:
        import httpx
        from backend.db import ket_noi
        ten, eid = self.u[1], self.X("X2")

        def dem_thu_hoi():
            try:
                with ket_noi() as c:
                    c.execute("SET TRANSACTION READ ONLY")
                    return c.execute("SELECT count(*) AS n FROM revoked_tokens").fetchone()["n"]
            except Exception:  # noqa: BLE001 – bảng chưa có (mã cũ / chưa áp migration 006)
                return None
        DUONG = [("GET", "/me", None), ("GET", "/me/classes", None), ("GET", "/exams", None), ("GET", f"/exams/{eid}/sheets", None), ("GET", f"/exams/{eid}/results", None),
                 ("GET", "/sheets/1", None), ("GET", "/meta/ket-noi", None), ("PATCH", "/me", {"full_name": "AH thử R4"}), ("POST", "/me/password", {})]

        def goi(token: str | None, cach: str) -> list[int]:
            c = httpx.Client(base_url=GOC, timeout=60)
            if token and cach == "cookie":
                c.cookies.set("se_session", token)
            h = {"Authorization": f"Bearer {token}"} if token and cach == "bearer" else {}
            out = []
            for m, d, js in DUONG:
                try:
                    out.append(c.request(m, d, json=js, headers=h).status_code)
                except httpx.HTTPError:
                    out.append(-1)
            c.close()
            return out
        luot = []
        for k in range(so_luot):
            c1, c2 = self.phien_dang_nhap(ten), self.phien_dang_nhap(ten)
            t1, t2 = c1.cookies.get("se_session"), c2.cookies.get("se_session")
            truoc = {"t1_cookie": goi(t1, "cookie"), "t2_cookie": goi(t2, "cookie")}
            n0 = dem_thu_hoi()
            r_out = c1.post("/auth/logout")
            sau = {"t1_cookie": goi(t1, "cookie"), "t1_bearer": goi(t1, "bearer"), "t2_cookie": goi(t2, "cookie"), "t2_bearer": goi(t2, "bearer")}
            gia = {"ngau_nhien": goi("v1.abc.def", "bearer"), "sai_chu_ky": goi(t2[:-3] + ("AAA" if not t2.endswith("AAA") else "BBB"), "cookie"), "khong_co": goi(None, "cookie")}
            n1 = dem_thu_hoi()
            r_gia = httpx.post(f"{GOC}/auth/logout", cookies={"se_session": "v1.abc.def"}, timeout=60)
            r_lai = httpx.post(f"{GOC}/auth/logout", headers={"Authorization": f"Bearer {t1}"}, timeout=60)
            r_khong = httpx.post(f"{GOC}/auth/logout", timeout=60)
            n2 = dem_thu_hoi()
            c1.close()
            c2.close()
            ok_a = all(x == 401 for x in sau["t1_cookie"] + sau["t1_bearer"])
            ok_b = all(x not in (401, -1) for x in sau["t2_cookie"] + sau["t2_bearer"])
            ok_c = all(x == 401 for v in gia.values() for x in v) and r_gia.status_code == 204 and (n1 is None or n2 == n1)
            ok_d = r_out.status_code == 204 and r_lai.status_code == 204 and r_khong.status_code == 204
            ok_e = n0 is not None and n1 is not None and n1 == n0 + 1
            luot.append({"luot": k + 1, "truoc_logout_ok": all(x != 401 for v in truoc.values() for x in v), "a_t1_bi_401_moi_duong": ok_a, "b_t2_van_dung_duoc": ok_b,
                         "c_token_gia_401_khong_ghi": ok_c, "d_logout_lap_lai_204": ok_d, "e_ghi_dung_1_dong": ok_e, "sau": sau, "gia": gia,
                         "revoked_truoc_sau_gia_sau": [n0, n1, n2]})
        dat = all(x["truoc_logout_ok"] and x["a_t1_bi_401_moi_duong"] and x["b_t2_van_dung_duoc"] and x["c_token_gia_401_khong_ghi"] and x["d_logout_lap_lai_204"] and x["e_ghi_dung_1_dong"]
                  for x in luot)
        return {"dat": dat, "so_luot": so_luot, "so_duong_dan": len(DUONG), "luot": luot}

    def kich_ban_r5(self, n: int = 20) -> dict:
        eid = self.X("XA5")
        ds = []
        for i in range(1, n + 1):
            sbd = ma_ar(5, i)
            cau, nd = bai_lam(HAT_GIONG + 120000 + i, "sach")
            ds.append({"ten": f"ar5_{i}.jpg", "anh": self.ve.anh(cau, sbd), "sbd": sbd, "n_dung": nd})
        mau = LayMau(self.mc.pid)
        mau.start()
        time.sleep(1.0)
        rao = threading.Barrier(n)

        def gui(i):
            c = self.phien_phu(self.u[i % 2])
            rao.wait()
            t0 = time.perf_counter()
            try:
                r = c.post(f"/exams/{eid}/sheets", files={"file": (ds[i]["ten"], ds[i]["anh"], "image/jpeg")})
                return {"i": i, "http": r.status_code, "retry_after": r.headers.get("retry-after"), "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200],
                        "ms": round((time.perf_counter() - t0) * 1000)}
            except Exception as e:  # noqa: BLE001
                return {"i": i, "http": -1, "retry_after": None, "body": f"{type(e).__name__}: {e}", "ms": round((time.perf_counter() - t0) * 1000)}
        with ThreadPoolExecutor(n) as ex:
            kq = list(ex.map(gui, range(n)))
        time.sleep(1.0)
        mau.dung_lai.set()
        mau.join()
        bm = mau.tom_tat()
        sai_ma = [(r["i"], r["http"]) for r in kq if r["http"] not in (201, 503)]
        thieu_ra = [r["i"] for r in kq if r["http"] == 503 and not (r["retry_after"] or "").strip().isdigit()]
        sai_cham = []
        for r in kq:
            if r["http"] == 201:
                t = tom_tat_phieu(self.phien_phu(self.u[r["i"] % 2]), r["body"]["sheet_id"])
                if not (t["status"] == "graded" and float(t["chinh_thuc"]) == ds[r["i"]]["n_dung"] * 0.25 and t["sv"] == ds[r["i"]]["sbd"]):
                    sai_cham.append((r["i"], t["status"], t["chinh_thuc"]))
        return {"dat": not sai_ma and not thieu_ra and not sai_cham and bm["mb_dinh"] is not None and bm["mb_dinh"] <= 1500, "so_yeu_cau": n,
                "dem_ma": {str(m): sum(1 for r in kq if r["http"] == m) for m in sorted({r["http"] for r in kq})}, "ma_la": sai_ma, "503_thieu_retry_after": thieu_ra,
                "retry_after": sorted({r["retry_after"] for r in kq if r["retry_after"]}), "sai_cham": sai_cham, "bo_nho": bm, "gioi_han_mb": 1500,
                "ms": tk([r["ms"] for r in kq if r["http"] == 201])}

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
        theo_muc = {}
        for r in kq:
            m = sum(1 for x in kq if x["bat_dau"] <= r["bat_dau"] < x["ket_thuc"])
            theo_muc.setdefault(m, []).append(r["ms"])
        return {"dat": not loi and not sai and len(kq) == 60, "loi_http": loi, "sai_so_voi_ky_vong": sai, "ms": tk([r["ms"] for r in kq]),
                "tuong_ms": tuong, "anh_moi_giay": round(len(kq) / (tuong / 1000), 2), "bo_nho": mau.tom_tat(),
                "ms_theo_muc_dong_thoi": {m: tk(v) for m, v in sorted(theo_muc.items())},
                "may_chu_ms": tk([self._ms_may_chu(r) for r in kq if self._ms_may_chu(r) is not None])}

    def thang_tai(self, muc: tuple = (1, 2, 4, 6, 8, 12)) -> dict:
        eid, ten = self.X("XR"), self.u[0]
        out, sbd_i = {}, 0
        mau = LayMau(self.mc.pid)
        mau.start()
        for n in muc:
            ds = []
            for _ in range(2 * n):
                sbd_i += 1
                cau, _ = bai_lam(HAT_GIONG + 90000 + sbd_i, "sach")
                ds.append({"ten": f"ah_r_{n}_{sbd_i}.jpg", "anh": self.ve.anh(cau, f"9795{sbd_i:02d}")})
            t0 = time.perf_counter()
            kq = self.chay_song_song({ten: [(eid, a) for a in ds]}, luong_moi_tk=n)
            tuong = (time.perf_counter() - t0)
            out[n] = {"ms": tk([r["ms"] for r in kq]), "anh_moi_giay": round(len(kq) / tuong, 2),
                      "loi": [(r["ten"], r["http"]) for r in kq if r["http"] != 201]}
        mau.dung_lai.set()
        mau.join()
        return {"muc": out, "bo_nho": mau.tom_tat(), "dat": all(not v["loi"] for v in out.values())}


def _dem_log(khoa: str) -> int:
    try:
        return LOG_MAY_CHU.read_text(encoding="utf-8", errors="replace").count(khoa)
    except OSError:
        return 0


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
        with ket_noi() as c:
            hs = dung(c, ar=not args.khong_ar)
        luu_ho_so(hs)
        print("Đã dựng dữ liệu thử:", {k: len(v) for k, v in hs.items() if isinstance(v, dict) and k != "_mk"})
        mc.bat()
        ket_qua["may_chu"] = {"pid": mc.pid, "bo_nho_luc_bat": bo_nho_mb(mc.pid) if mc.pid else None}
        t = Thu(hs, mc)
        if not args.chi_ar:
            for ten, ham in (("A", t.kich_ban_a), ("B", t.kich_ban_b)):
                print(f"Kịch bản {ten}…", flush=True)
                ket_qua[ten] = ham()
                print(f"  -> {'ĐẠT' if ket_qua[ten]['dat'] else 'KHÔNG ĐẠT'}", flush=True)
            print("Kịch bản C…", flush=True)
            ket_qua["C"] = t.kich_ban_c(ket_qua["B"].pop("_phieu")["dong"])
            print(f"  -> {'ĐẠT' if ket_qua['C']['dat'] else 'KHÔNG ĐẠT'}", flush=True)
        else:
            t.ss[t.u[0]], t.ss[t.u[1]], t.ss[t.u[2]] = (t.phien_dang_nhap(x) for x in t.u)
        ds_kb = [] if args.chi_ar else [("D", lambda: t.kich_ban_d(args.lap_d)), ("D_ep", t.kich_ban_d_ep), ("D_anh_trung", t.kich_ban_d_anh_trung),
                                        ("D_lo_cheo", t.kich_ban_d_lo_cheo), ("E", t.kich_ban_e), ("E_thang_tai", t.thang_tai)]
        if not args.khong_ar:
            ds_kb += [("R1", t.kich_ban_r1), ("R2", t.kich_ban_r2), ("R3", t.kich_ban_r3), ("R4", t.kich_ban_r4)]
        chon = {x.strip().upper() for x in (args.chon or "").split(",") if x.strip()}
        ds_kb = [(ten, ham) for ten, ham in ds_kb if not chon or ten.upper() in chon]
        for ten, ham in ds_kb:
            print(f"Kịch bản {ten}…", flush=True)
            try:
                ket_qua[ten] = ham()
            except Exception as e:  # noqa: BLE001 – ghi lại, không che; các kịch bản sau vẫn chạy
                ket_qua[ten] = {"dat": False, "loi_cong_cu": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1500:]}
            print(f"  -> {'ĐẠT' if ket_qua[ten]['dat'] else 'KHÔNG ĐẠT'}", flush=True)
        ket_qua["may_chu"]["bo_nho_cuoi"] = bo_nho_mb(mc.pid) if mc.pid else None
        if not args.khong_ar and (not chon or "R5" in chon):
            print("Kịch bản R5 (khởi động lại máy chủ với CHAM_DONG_THOI=3, CHAM_CHO_GIAY=8)…", flush=True)
            mc.tat()
            time.sleep(2)
            mc.bat({"CHAM_DONG_THOI": "3", "CHAM_CHO_GIAY": "8"})
            ket_qua["may_chu"]["pid_r5"] = mc.pid
            try:
                ket_qua["R5"] = t.kich_ban_r5()
            except Exception as e:  # noqa: BLE001
                ket_qua["R5"] = {"dat": False, "loi_cong_cu": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1500:]}
            print(f"  -> {'ĐẠT' if ket_qua['R5']['dat'] else 'KHÔNG ĐẠT'}", flush=True)
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
    bat_buoc = tuple(k for k in ((() if args.chi_ar else ("A", "B", "C", "D", "E")) + (() if args.khong_ar else ("R1", "R2", "R3", "R4", "R5")))
                     if k in ket_qua)
    return 0 if all(ket_qua.get(k, {}).get("dat") for k in bat_buoc) and ket_qua["don"]["sach"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lenh", required=True)
    p = sub.add_parser("chay")
    p.add_argument("--lap-d", type=int, default=20)
    p.add_argument("--chi-ar", action="store_true", help="CHỈ R1–R5 (lệnh AR)")
    p.add_argument("--chon", default="", help="chỉ chạy các kịch bản R này (vd R1,R3); cần --chi-ar")
    p.add_argument("--khong-ar", action="store_true", help="CHỈ A–E (như lệnh AH)")
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
