"""
eval_he_thong.py - Đánh giá CẢ HỆ THỐNG (nắn ảnh -> OMR -> CNN chữ số + đối chiếu -> chấm điểm -> giáo viên) – docs/ke_hoach_test_cuoi.md.

ĐỘC LẬP với mã được chấm: chỉ đi qua API công khai của backend (TestClient, CSDL thật trong giao dịch ROLLBACK, ảnh tạm); KHÔNG import
cv_engine.omr / ocr (luật, ngưỡng, đặc trưng). Kết quả "đúng thật" tính riêng từ data/ground_truth.csv (nhãn người tô + chữ số viết tay):
    câu đúng ⇔ người tô ĐÚNG MỘT ô và ô đó = đáp án chuẩn (ô mờ cũng tính); mỗi câu 10/40 = 0,25 điểm.
Phép kiểm nhất quán nắn ảnh (cần cv_engine.preprocessing – chỉ để so với số Tuần 4 đã lưu, không dùng để chấm): marker / hướng xoay / blur của
từng ảnh phải trùng data/_eval/v6_api/diem_<tap>.csv.

  python tools/eval_he_thong.py run --tap dev [--xem]                      # 56 ảnh 0001–0028: thử công cụ (phải ra lại số đã biết)
  python tools/eval_he_thong.py run --tap test --xac-nhan-test --xem       # 12 ảnh 0035–0040: MỘT LẦN, sau đăng ký trước (dang_ky_test_he_thong.json)
Chốt chặn test: --xac-nhan-test + chan_test + bản đăng ký khớp (commit mã, diff mã rỗng, SHA mô hình / ngưỡng / layout / preprocessing) + file khoá
data/_eval/he_thong/da_chay_test.lock (tạo NGAY khi bắt đầu; có rồi thì từ chối, kể cả lần trước bị lỗi giữa chừng).
"""
import argparse
import base64
import csv
import hashlib
import html
import json
import subprocess
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AUTH_MODE", "demo")      # công cụ chạy trong tiến trình: bỏ đăng nhập (backend: AUTH_MODE=on là mặc định)
from cv_engine.tap_du_lieu import PHIEU_TEST, PHIEU_TRAIN, chan_test, ma_phieu  # noqa: E402  (chỉ ranh giới tập, không phải luật chấm)

DATA = ROOT / "data"
OUT = DATA / "_eval" / "he_thong"
KHOA = OUT / "da_chay_test.lock"
DANG_KY = ROOT / "docs" / "dang_ky_test_he_thong.json"
TAP = {"dev": PHIEU_TRAIN, "test": PHIEU_TEST}
DIEM_CAU = Decimal("0.25")
MA_DE = ("101", "102", "103", "104")
SEED, SO_BOOT = 2026, 1000
# 8 mục rõ / mờ của tập test (nhãn đã so giấy 07/10/2026): (phiếu, câu, nhãn người)
TAM_MUC_TEST = [(36, 2), (36, 10), (36, 13), (37, 1), (37, 15), (37, 31), (40, 5), (40, 10)]
# các đường dẫn mã được khoá bởi đăng ký (docs/ và CLAUDE.md được đổi sau đăng ký)
DUONG_DAN_MA = ["smart_exam_db/cv_engine", "smart_exam_db/models", "smart_exam_db/tools", "smart_exam_db/backend",
                "smart_exam_db/answer_sheet", "smart_exam_db/frontend"]
FILE_SHA = ["smart_exam_db/models/omr_m1.json", "smart_exam_db/models/ocr_cnn.json", "smart_exam_db/data/_eval/nguong.json",
            "smart_exam_db/answer_sheet/output/layout.json", "smart_exam_db/answer_sheet/output/phieu_trang_300dpi.png",
            "smart_exam_db/cv_engine/preprocessing.py"]


# ------------------------------------------------------------------------------------------------ thước đo (độc lập)
def cp_tren(k: int, n: int) -> float:
    """Cận trên 95% Clopper–Pearson (hai phía) của tỉ lệ k/n."""
    from scipy.stats import beta
    return 1.0 if n == 0 or k >= n else float(beta.ppf(0.975, k + 1, n - k))


def cp_khoang(k: int, n: int) -> tuple[float, float]:
    from scipy.stats import beta
    return (0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1)), cp_tren(k, n))


def tap_chon(nhan_cau: str) -> str:
    """Tập ô người tô: '-' -> '', 'b' -> 'B', 'AC' -> 'AC'."""
    return "" if nhan_cau == "-" else "".join(sorted(nhan_cau.upper()))


def trang_thai_that(nhan_cau: str) -> str:
    if nhan_cau == "-":
        return "trong"
    if len(nhan_cau) > 1:
        return "nhieu"
    return "ro" if nhan_cau.isupper() else "mo"


def dung_that(nhan_cau: str, dap_an: str) -> bool:
    return len(nhan_cau) == 1 and nhan_cau.upper() == dap_an


def doc_nhan(tap) -> dict:
    """{'0035': {...}} CHỈ phiếu thuộc `tap`; dòng phiếu khác bỏ ngay khi đọc."""
    out = {}
    with (DATA / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if int(r["sheet_id"]) in tap:
                out[r["sheet_id"]] = {"q": {q: r[f"q{q}"] for q in range(1, 41)}, "sbd": r["sbd"], "ma_de": r["exam_code"],
                                      "sbd_bubble": r["sbd_bubble"], "ma_de_bubble": r["exam_code_bubble"]}
    return out


def f1_mo(rows: list[dict]) -> float:
    tp = sum(r["that"] == "mo" and r["doc"] == "faint" for r in rows)
    fp = sum(r["that"] != "mo" and r["doc"] == "faint" for r in rows)
    fn = sum(r["that"] == "mo" and r["doc"] != "faint" for r in rows)
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")


# ------------------------------------------------------------------------------------------------ chốt chặn đăng ký
def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT.parent, capture_output=True, text=True, encoding="utf-8")


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def kiem_dang_ky(dang_ky: Path = DANG_KY, goc: Path = ROOT.parent) -> dict:
    """Từ chối nếu: chưa có bản đăng ký; mã khác commit đăng ký (git diff / file sửa chưa commit); SHA file khác bản đăng ký."""
    if not dang_ky.exists():
        raise SystemExit(f"DỪNG: chưa có bản đăng ký trước {dang_ky} – test cuối chỉ chạy sau đăng ký (docs/ke_hoach_test_cuoi.md mục 4).")
    d = json.loads(dang_ky.read_text(encoding="utf-8"))
    ma = d["ma_commit"]
    chinh = subprocess.run(["git", "diff", "--stat", ma, "HEAD", "--", *DUONG_DAN_MA], cwd=goc, capture_output=True, text=True, encoding="utf-8")
    if chinh.returncode != 0 or chinh.stdout.strip():
        raise SystemExit(f"DỪNG: mã khác commit đăng ký {ma[:8]} (git diff không rỗng):\n{chinh.stdout or chinh.stderr}")
    ban = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", *DUONG_DAN_MA], cwd=goc, capture_output=True, text=True, encoding="utf-8")
    if ban.stdout.strip():
        raise SystemExit(f"DỪNG: mã có thay đổi chưa commit:\n{ban.stdout}")
    sai = [f for f, h in d["sha256"].items() if sha_file(goc / f) != h]
    if sai:
        raise SystemExit(f"DỪNG: SHA-256 khác bản đăng ký: {sai}")
    return d


# ------------------------------------------------------------------------------------------------ phiên làm việc (rollback)
@contextmanager
def phien():
    from fastapi.testclient import TestClient

    from backend import migrate
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    from backend.main import app, get_cau_hinh, get_conn
    migrate.ap_dung()
    cfg = replace(lay_cau_hinh(), storage_dir=Path(tempfile.mkdtemp(prefix="kho_he_thong_")))
    conn = ket_noi()

    def _conn():
        yield conn

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_cau_hinh] = lambda: cfg
    try:
        with TestClient(app) as client:
            yield client, conn
    finally:
        app.dependency_overrides.clear()
        conn.rollback()
        conn.close()


def tao_ky_thi(client, tieu_de: str):
    from backend import demo                                   # chỉ sinh đáp án mẫu (dữ liệu)
    r = client.post("/exams", json={"exam_title": tieu_de, "subject_code": "HT" + tieu_de[-1], "num_questions": 40,
                                    "codes": [{"code": m, "answers": demo.khoa_demo(m)} for m in MA_DE]})
    assert r.status_code == 201, r.text
    eid = r.json()["exam_id"]
    return eid, {c["code"]: c["answers"] for c in client.get(f"/exams/{eid}").json()["codes"]}


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


# ------------------------------------------------------------------------------------------------ một ảnh
def chay_phieu(client, conn, exam_id: int, dap_an: dict, ten: str, nhan: dict, xem: bool) -> dict:
    ms = f"{ma_phieu(ten):04d}"
    t = nhan[ms]
    key = dap_an[t["ma_de"]]
    that = {q: dung_that(t["q"][q], key[q - 1]) for q in range(1, 41)}
    diem_that = DIEM_CAU * sum(that.values())
    conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV đánh giá hệ thống') ON CONFLICT DO NOTHING", (t["sbd"],))
    anh_bytes = (DATA / "raw" / f"{ten}.jpg").read_bytes()
    t0 = time.perf_counter()
    r = client.post(f"/exams/{exam_id}/sheets", files={"file": (f"{ten}.jpg", anh_bytes, "image/jpeg")})
    giay = time.perf_counter() - t0
    assert r.status_code == 201, r.text
    sid = r.json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    row = {"anh": ten, "phieu": int(ms), "sheet_id": sid, "dieu_kien": ten.split("_")[1], "status_tai": v["status"], "giay": round(giay, 3),
           "diem_that": float(diem_that), "tu_choi": v.get("reject_code") or "", "cau": [], "cot": [], "cx_thua": 0, "cx_thua_trong": 0,
           "n_ro": 0, "n_trong": 0, "nang_cau": 0, "nhe_cau": 0, "nang_cot": 0, "cham_sai_khong_co": 0, "tu_chot_sai": 0, "vi_pham_can": 0,
           "sbd_sai_im_lang": 0, "ma_sai_im_lang": 0, "cuoi_dung": None, "chu_so_dung": 0, "chu_so_n": 0, "cx_cau": 0,
           "sbd_can_xem": None, "ma_can_xem": None, "ma_ly_do": [], "sbd_ly_do": []}
    if v["status"] == "rejected":
        row["ghi_chu"] = f"bị từ chối {v['reject_code']}"
        return row
    code_ok = v["exam_code"]["matched_code"] == t["ma_de"]
    for q in v["questions"]:
        n = q["question_no"]
        lab = t["q"][n]
        tt = trang_thai_that(lab)
        doc_o = "".join(sorted(q["omr_selected_options"] or ""))
        cx = bool(q["needs_review"])
        row["cx_cau"] += cx
        row["n_ro"] += tt == "ro"
        row["n_trong"] += tt == "trong"
        row["cx_thua"] += cx and tt == "ro"
        row["cx_thua_trong"] += cx and tt == "trong"
        if not cx:
            row["nang_cau"] += doc_o != tap_chon(lab)
            row["nhe_cau"] += doc_o == tap_chon(lab) and tt == "mo" and q["state"] == "filled"
            if code_ok and q["is_correct"] is not None and q["is_correct"] != that[n]:
                row["cham_sai_khong_co"] += 1
        else:
            assert q["is_correct"] is None, f"{ten} câu {n}: cần xem mà vẫn bị chấm"
        row["cau"].append({"n": n, "that": tt, "nhan": lab, "doc": q["state"], "doc_o": doc_o, "cx": cx, "ly_do": q["reasons"]})
    for truong, khoa, nhan_b in (("sbd", "sbd", t["sbd_bubble"]), ("exam_code", "ma", t["ma_de_bubble"])):
        f = v["sbd"] if truong == "sbd" else v["exam_code"]
        viet = t["sbd"] if truong == "sbd" else t["ma_de"]
        for i, c in enumerate(f["columns"]):
            that_b = "?" if nhan_b[i] == "-" else nhan_b[i]
            nang = c["bubble"] != that_b and c["bubble"] != "?" and "bubble_cx" not in c["ly_do"]
            row["nang_cot"] += nang
            hw = c["handwriting"]
            row["chu_so_n"] += 1
            row["chu_so_dung"] += hw["chu_so"] == viet[i]
            row["cot"].append({"truong": truong, "i": i, "bubble": c["bubble"], "that_bubble": that_b, "viet": viet[i], "may": hw["chu_so"],
                               "p": hw["p"], "cx": c["can_xem"], "ly_do": c["ly_do"]})
        row[f"{khoa}_can_xem"] = bool(f["can_xem"])
        row[f"{khoa}_ly_do"] = list(f["reasons"])
        if not f["can_xem"] and f["detected"] != viet:
            row["sbd_sai_im_lang" if khoa == "sbd" else "ma_sai_im_lang"] = 1
    sc = v["score"]
    if code_ok:
        row["vi_pham_can"] = int(not (Decimal(str(sc["provisional"])) <= diem_that <= Decimal(str(sc["max_possible"]))))
    if v["status"] == "graded":
        row["tu_chot_sai"] = int(code_ok is False or Decimal(str(sc["official"])) != diem_that or v["student"]["student_code"] != t["sbd"])
    row["can_xem_cot_khong_to"] = [c["truong"] for c in row["cot"] if c["that_bubble"] == "?"]
    if xem:                                                     # ảnh cho HTML (chụp TRƯỚC khi giáo viên sửa)
        row["_anh_nan"] = client.get(f"/sheets/{sid}/image?kind=aligned").content
        row["_o_chu"] = {(c["truong"], c["i"]): client.get(f"/sheets/{sid}/digits/{c['truong']}/{c['i']}/image").content for c in row["cot"]}
        muc = {n for n, tt_ in ((q["n"], q["that"]) for q in row["cau"]) if tt_ in ("mo", "nhieu")} | {c for p, c in TAM_MUC_TEST if p == int(ms)}
        row["_cau_anh"] = {n: client.get(f"/sheets/{sid}/questions/{n}/image").content for n in sorted(muc)}
    # --- pha 2: giáo viên oracle chốt đúng như giấy
    if v["status"] == "graded":
        row["cuoi_dung"] = int(not row["tu_chot_sai"])
        return row
    for c in client.get(f"/sheets/{sid}/review-questions").json():
        rr = client.post(f"/sheets/{sid}/questions/{c['question_no']}/review", json={"action": "set", "selected_options": tap_chon(t["q"][c["question_no"]])})
        assert rr.status_code == 200, rr.text
    v2 = client.get(f"/sheets/{sid}").json()
    if v2["status"] == "needs_review":
        rr = client.put(f"/sheets/{sid}/identity", json={"sbd": t["sbd"], "exam_code": t["ma_de"]})
        assert rr.status_code == 200, rr.text
        v2 = rr.json()
    row["cuoi_dung"] = int(v2["status"] == "graded" and v2["score"]["result_status"] == "confirmed" and Decimal(str(v2["score"]["official"])) == diem_that
                           and v2["student"]["student_code"] == t["sbd"])
    row["status_cuoi"] = v2["status"]
    return row


# ------------------------------------------------------------------------------------------------ nhất quán nắn ảnh với Tuần 4
def nhat_quan_tuan4(anhs: list[str], tap: str) -> dict:
    """So marker / hướng xoay / blur của preprocess() hiện tại với số Tuần 4 đã lưu (data/_eval/v6_api/diem_<tap>.csv)."""
    from cv_engine.preprocessing import nap_layout, preprocess
    ref = {}
    with (DATA / "_eval" / "v6_api" / f"diem_{tap}.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            ref[r["anh"]] = r
    L = nap_layout("phieu")
    khop, lech = 0, []
    for ten in anhs:
        r = ref.get(ten)
        kq = preprocess(DATA / "raw" / f"{ten}.jpg", L)
        if r is None:
            lech.append((ten, "không có số Tuần 4"))
            continue
        ok_t4 = r["tra_anh"] == "co"
        if kq.ok != ok_t4:
            lech.append((ten, f"ok {kq.ok} ≠ Tuần 4 {ok_t4}"))
            continue
        if kq.ok:
            mk = [float(r[f"marker_{c}_{a}"]) for c in ("tl", "tr", "br", "bl") for a in ("x", "y")]
            now = [float(v) for p in kq.marker for v in p]
            d = max(abs(a - b) for a, b in zip(mk, now))
            if d > 0.01 or int(r["huong_xoay"]) != kq.huong_xoay or abs(float(r["blur_score"]) - float(kq.blur_score)) > 1e-4:
                lech.append((ten, f"marker lệch {d:.4f} px / hướng / blur"))
                continue
        khop += 1
    return {"khop": khop, "n": len(anhs), "lech": lech}


# ------------------------------------------------------------------------------------------------ tổng hợp + báo cáo
def tom_tat(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["status_tai"] != "rejected"]
    cau = [c | {"phieu": r["phieu"]} for r in ok for c in r["cau"]]
    s = {"anh": len(rows), "tu_choi": len(rows) - len(ok), "tu_choi_ly_do": {r["anh"]: r["tu_choi"] for r in rows if r["tu_choi"]}}
    n_cau, n_cot = 40 * len(ok), 9 * len(ok)
    s["H2_nang"] = sum(r["nang_cau"] + r["nang_cot"] for r in ok)
    s["H2_n"] = n_cau + n_cot
    s["H3_sbd"], s["H3_ma"] = sum(r["sbd_sai_im_lang"] for r in ok), sum(r["ma_sai_im_lang"] for r in ok)
    s["H3_n"] = len(ok)
    s["H4_cham_sai_khong_co"] = sum(r["cham_sai_khong_co"] for r in ok)
    s["H4_vi_pham_can"] = sum(r["vi_pham_can"] for r in ok)
    s["H4_tu_chot_sai"] = sum(r["tu_chot_sai"] for r in ok)
    s["H5_dung"], s["H5_n"] = sum(r["cuoi_dung"] or 0 for r in ok), len(ok)
    s["chi_bao"] = {
        "nhe_cau": sum(r["nhe_cau"] for r in ok), "cx_thua": sum(r["cx_thua"] for r in ok), "n_ro": sum(r["n_ro"] for r in ok),
        "cx_thua_trong": sum(r["cx_thua_trong"] for r in ok), "n_trong": sum(r["n_trong"] for r in ok),
        "cau_can_xem": sum(r["cx_cau"] for r in ok), "n_cau": n_cau,
        "T3_dung": sum(r["chu_so_dung"] for r in ok), "T3_n": sum(r["chu_so_n"] for r in ok),
        "T4_gan": sum(bool(r["sbd_can_xem"] or r["ma_can_xem"]) for r in ok), "T4_n": len(ok),
        "giay_trung_vi": sorted(r["giay"] for r in ok)[len(ok) // 2] if ok else None,
        "tu_chot_khi_tai": sum(r["status_tai"] == "graded" for r in ok)}
    cb = s["chi_bao"]
    cb["cx_thua_ti_le"] = cb["cx_thua"] / cb["n_ro"] if cb["n_ro"] else None
    cb["T3_ci95"] = cp_khoang(cb["T3_n"] - cb["T3_dung"], cb["T3_n"]) if cb["T3_n"] else None      # CI của tỉ lệ SAI (CP)
    cb["T4_ci95"] = cp_khoang(cb["T4_gan"], cb["T4_n"]) if cb["T4_n"] else None
    cb["cx_thua_ci95"] = cp_khoang(cb["cx_thua"], cb["n_ro"]) if cb["n_ro"] else None
    import numpy as np
    rng = np.random.default_rng(SEED)
    ph = sorted({c["phieu"] for c in cau})
    if ph:
        theo = {p: [c for c in cau if c["phieu"] == p] for p in ph}
        bs = []
        for _ in range(SO_BOOT):
            x = [c for p in rng.choice(ph, len(ph), replace=True) for c in theo[p]]
            bs.append(f1_mo(x))
        cb["F1_mo_cau"] = f1_mo(cau)
        cb["F1_mo_ci95_bootstrap_phieu"] = [float(v) for v in np.nanpercentile(bs, [2.5, 97.5])]
        cb["n_mo"] = sum(c["that"] == "mo" for c in cau)
        for dk in ("C1", "C2", "C3", "C4"):
            x = [c for r in ok if r["dieu_kien"] == dk for c in r["cau"]]
            cb[f"F1_mo_{dk}"] = (f1_mo(x), sum(c["that"] == "mo" for c in x)) if x else None
    # cận trên Clopper–Pearson cho các số đếm bắt buộc (= 0)
    for k, tu, mau in (("H2_nang", "H2_nang", "H2_n"), ("H3_sbd", "H3_sbd", "H3_n"), ("H3_ma", "H3_ma", "H3_n")):
        s[f"{k}_cp_tren"] = cp_tren(s[tu], s[mau])
    s["H4_cp_tren"] = cp_tren(s["H4_cham_sai_khong_co"], max(1, sum(1 for c in cau if not c["cx"])))
    return s


def dat_bat_buoc(s: dict) -> dict:
    h = {"H1": "chờ kết luận mắt (xem mù) + nhất quán Tuần 4", "H2": s["H2_nang"] == 0, "H3": s["H3_sbd"] == 0 and s["H3_ma"] == 0,
         "H4": s["H4_cham_sai_khong_co"] == 0 and s["H4_vi_pham_can"] == 0 and s["H4_tu_chot_sai"] == 0, "H5": s["H5_dung"] == s["H5_n"]}
    return h


def ca_thu(rows: list[dict], tap: str) -> list[str]:
    out = []
    for r in rows:
        if r["status_tai"] == "rejected":
            continue
        for tr in r["can_xem_cot_khong_to"]:
            f_cx = r["sbd_can_xem"] if tr == "sbd" else r["ma_can_xem"]
            ly = r["sbd_ly_do"] if tr == "sbd" else r["ma_ly_do"]
            out.append(f"{r['anh']}: cột {tr} KHÔNG tô bubble → trường {'CẦN XEM' if f_cx else 'ĐƯỢC NHẬN (VI PHẠM)'} {ly}")
    if tap == "test":
        for p, n in TAM_MUC_TEST:
            for r in rows:
                if r["phieu"] == p and r["status_tai"] != "rejected":
                    c = next(x for x in r["cau"] if x["n"] == n)
                    out.append(f"{r['anh']} câu {n}: nhãn {c['nhan']} ({c['that']}) → máy {c['doc']} '{c['doc_o'] or '-'}', cần xem {c['cx']} {c['ly_do']}")
    return out


def html_trang(rows: list[dict], may: bool) -> str:
    h = [f"<meta charset=utf-8><title>{'KẾT QUẢ MÁY' if may else 'XEM MÙ'}</title><style>body{{font:14px sans-serif;margin:14px}}.a{{border:1px solid #bbb;padding:8px;margin:10px 0}}"
         "img{{border:1px solid #888}}td{{border:1px solid #ccc;text-align:center;padding:3px}}.cx{{background:#fff1d6}}</style>",
         f"<h2>{'KẾT QUẢ MÁY – mở SAU khi đã kết luận bằng mắt' if may else 'XEM MÙ – chưa có kết luận của máy'}</h2>",
         "<p>Với mỗi ảnh: (1) ảnh nắn có đúng (4 góc, chữ không méo) không? (2) đọc SBD / mã đề viết tay; (3) đọc các câu liệt kê (tô rõ / mờ / nhiều ô / trống).</p>"]
    for r in rows:
        if "_anh_nan" not in r:
            continue
        h.append(f"<div class=a><h3>{html.escape(r['anh'])}</h3>")
        import cv2
        import numpy as np
        a = cv2.imdecode(np.frombuffer(r["_anh_nan"], np.uint8), cv2.IMREAD_GRAYSCALE)
        h.append(f"<img src='data:image/jpeg;base64,{_b64(cv2.imencode('.jpg', cv2.resize(a, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA))[1].tobytes())}'><br>")
        for tr in ("sbd", "exam_code"):
            cs = [c for c in r["cot"] if c["truong"] == tr]
            h.append(f"<p><b>{tr}</b></p><table><tr>" + "".join(f"<td{' class=cx' if may and c['cx'] else ''}><img style='height:60px' src='data:image/png;base64,{_b64(r['_o_chu'][(tr, c['i'])])}'>"
                     + (f"<br>ô tô <b>{c['bubble']}</b> · máy <b>{c['may']}</b> {c['p']:.0%}" if may else "<br>…") + "</td>" for c in cs) + "</tr></table>")
        h.append("<p><b>Các câu cần đọc</b></p>")
        for n, png in r["_cau_anh"].items():
            c = next(x for x in r["cau"] if x["n"] == n)
            h.append(f"<div><b>câu {n}</b> " + (f"– máy: {c['doc']} '{c['doc_o'] or '-'}' cần xem {c['cx']} {c['ly_do']}" if may else "– kết luận của bạn: …")
                     + f"<br><img src='data:image/png;base64,{_b64(png)}'></div>")
        h.append("</div>")
    return "\n".join(h)


def chay(ten_tap: str, xem: bool, tien_do=print, danh_sach: list[str] | None = None) -> dict:
    tap = TAP[ten_tap]
    nhan = doc_nhan(tap)
    ds = danh_sach or sorted(p.stem for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in tap)
    for ten in ds:
        assert ma_phieu(ten) in tap, f"{ten} ngoài tập {ten_tap}"
    with phien() as (client, conn):
        a, dap_an = tao_ky_thi(client, "Đánh giá hệ thống A")
        b, _ = tao_ky_thi(client, "Đánh giá hệ thống B")
        da, rows = set(), []
        for ten in ds:
            ms = ma_phieu(ten)
            eid = b if ms in da else a
            da.add(ms)
            rows.append(chay_phieu(client, conn, eid, dap_an, ten, nhan, xem))
            r = rows[-1]
            tien_do(f"{ten}: {r['status_tai']} → {r.get('status_cuoi', r['status_tai'])}, cần xem {r['cx_cau']}, nặng {r['nang_cau'] + r['nang_cot']}, "
                    f"chấm sai không cờ {r['cham_sai_khong_co']}, SBD {'cần xem' if r['sbd_can_xem'] else 'nhận'}, mã đề {'cần xem' if r['ma_can_xem'] else 'nhận'}")
    return {"rows": rows, "nhat_quan": nhat_quan_tuan4(ds, ten_tap)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["run"])
    ap.add_argument("--tap", choices=list(TAP), required=True)
    ap.add_argument("--xac-nhan-test", action="store_true")
    ap.add_argument("--xem", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.tap == "test":
        ds_test = sorted(p.stem for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in PHIEU_TEST)
        chan_test(ds_test, a.xac_nhan_test, "eval_he_thong")
        if KHOA.exists():
            sys.exit(f"TỪ CHỐI: test hệ thống đã chạy (hoặc đã bắt đầu) – {KHOA.read_text(encoding='utf-8')}. Không chạy lại (docs/ke_hoach_test_cuoi.md mục 6).")
        kiem_dang_ky()
        KHOA.write_text(f"bắt đầu {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    kq = chay(a.tap, a.xem)
    rows = kq["rows"]
    s = tom_tat(rows)
    thu = ca_thu(rows, a.tap)
    d = OUT / a.tap
    d.mkdir(parents=True, exist_ok=True)
    if a.xem:
        (d / "xem_mu.html").write_text(html_trang(rows, False), encoding="utf-8")
        (d / "xem_may.html").write_text(html_trang(rows, True), encoding="utf-8")
    for r in rows:
        for k in [k for k in r if k.startswith("_")]:
            r.pop(k)
    res = {"tom_tat": s, "dat_bat_buoc": dat_bat_buoc(s), "ca_thu": thu, "nhat_quan_tuan4": kq["nhat_quan"], "anh": rows}
    (d / "ket_qua.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "anh"}, ensure_ascii=False, indent=1, default=str))
    if a.tap == "test":
        KHOA.write_text(f"đã chạy xong {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    ok = res["dat_bat_buoc"]
    sys.exit(0 if ok["H2"] is True and ok["H3"] is True and ok["H4"] is True and ok["H5"] is True and not kq["nhat_quan"]["lech"] else 1)


if __name__ == "__main__":
    main()
