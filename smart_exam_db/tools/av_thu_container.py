"""
av_thu_container.py - Lệnh AV (V4 / V5): lái một bản triển khai ĐANG CHẠY (docker compose, sau Caddy) qua HTTP để chấm thật + đo RAM. Chạy từ smart_exam_db/.
KHÔNG chứa bí mật: mật khẩu quản trị lấy từ biến môi trường AV_ADMIN_PW (không in). Chỉ dùng cho môi trường THỬ (tạo lớp / giáo viên / kỳ thi thử qua API quản trị).

  AV_ADMIN_PW=... python tools/av_thu_container.py bv  --goc http://localhost:8080 --admin quan_tri_av          # V4: JPG BV01 + HEIC thật + lô 5 ảnh, so điểm kỳ vọng
  AV_ADMIN_PW=... python tools/av_thu_container.py ram --goc http://localhost:8080 --admin quan_tri_av --ten smart-exam-app-1 --nhan cd1
                                                                                                                  # V5: docker stats lúc nghỉ / 1 ảnh / lô 5 / 5 ảnh đồng thời
Điều kiện: đã có sinh viên 220001–220009 và 823451 trong bảng students (bản triển khai sạch KHÔNG có đường nhập sinh viên qua web – xem docs/trien_khai_public.md).
"""
import argparse
import csv
import os
import re
import secrets
import string
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KB = ROOT / "answer_sheet" / "demo_bv" / "demo_bv_kich_ban.csv"
DAP_AN = ROOT / "answer_sheet" / "demo_bv" / "demo_bv_dap_an.csv"
ANH = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia"
HEIC = ROOT / "data" / "raw_heic" / "IMG_4223.HEIC"          # = phiếu 0005_C1 (data/_prepare/mapping.csv)
LOP = "CNTT-K22A"


def doc_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dang_nhap(goc: str, ten: str, mk: str) -> dict:
    r = httpx.post(f"{goc}/auth/login", json={"username": ten, "password": mk}, timeout=30)
    r.raise_for_status()
    m = re.search(r"se_session=([^;]+)", r.headers.get("set-cookie", ""))       # COOKIE_SECURE=1 + HTTP: cookie không lưu được -> dùng Bearer
    return {"Authorization": "Bearer " + m.group(1)}


def api(cl: httpx.Client, ptt: str, url: str, **kw):
    r = cl.request(ptt, url, **kw)
    if r.status_code >= 400:
        raise SystemExit(f"DỪNG: {ptt} {url} -> {r.status_code} {r.text[:200]}")
    return r.json() if r.content else None


def chuan_bi(goc: str, admin: str) -> tuple[httpx.Client, dict, dict]:
    """Tạo (nếu chưa có) lớp + giáo viên thử; trả (client, header admin, header giáo viên)."""
    cl = httpx.Client(base_url=goc, timeout=120)
    ha = dang_nhap(goc, admin, os.environ["AV_ADMIN_PW"])
    lop = next((x for x in api(cl, "GET", "/admin/classes", headers=ha) if x["class_code"] == LOP), None) \
        or api(cl, "POST", "/admin/classes", headers=ha, json={"class_code": LOP, "class_name": "Lớp thử AV"})
    mk = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
    gv = next((u for u in api(cl, "GET", "/admin/users", headers=ha) if u["username"] == "gv_thu_av"), None)
    if gv is None:
        gv = api(cl, "POST", "/admin/users", headers=ha, json={"username": "gv_thu_av", "full_name": "Giáo viên thử AV", "password": mk, "class_ids": [lop["class_id"]]})
    else:
        api(cl, "POST", f"/admin/users/{gv['user_id']}/password", headers=ha, json={"password": mk})
    return cl, ha, dang_nhap(goc, "gv_thu_av", mk) | {"_gv": gv["user_id"]}


def tao_ky_thi(cl, ha, gv_id: int, tieu_de: str, ma_de: dict[str, str]) -> int:
    body = {"exam_title": tieu_de, "subject_code": "AVTHU", "subject_name": "Môn thử AV", "num_questions": 40, "class_code": LOP,
            "teacher_user_id": gv_id, "codes": [{"code": m, "answers": a} for m, a in ma_de.items()]}
    return api(cl, "POST", "/admin/exams", headers=ha, json=body)["exam_id"]


def duyet_dung_giay(cl, h, sid: int, nhan: list[str], sbd: str, ma_de: str) -> dict:
    """Giáo viên duyệt ĐÚNG NHƯ GIẤY (cùng quy tắc tools/thu_bo_demo.py): câu cần xem -> đặt tập ô đã tô; SBD / mã đề -> nhập đúng. Trả phiếu sau duyệt."""
    for q in api(cl, "GET", f"/sheets/{sid}/review-questions", headers=h):
        lab = nhan[q["question_no"] - 1]
        api(cl, "POST", f"/sheets/{sid}/questions/{q['question_no']}/review", headers=h,
            json={"action": "set", "selected_options": "" if lab == "-" else "".join(sorted(lab.upper()))})
    v = api(cl, "GET", f"/sheets/{sid}", headers=h)
    if v["status"] == "needs_review":
        r = cl.put(f"/sheets/{sid}/identity", headers=h, json={"sbd": sbd, "exam_code": ma_de})
        if r.status_code == 200:
            v = api(cl, "GET", f"/sheets/{sid}", headers=h)
    return v


def tai(cl, h, eid: int, duong_dan: Path, mime: str) -> dict:
    hd = {k: v for k, v in h.items() if not k.startswith("_")}
    r = cl.post(f"/exams/{eid}/sheets", headers=hd, files={"file": (duong_dan.name, duong_dan.read_bytes(), mime)})
    return {"http": r.status_code, **(r.json() if r.headers.get("content-type", "").startswith("application/json") else {})}


# ------------------------------------------------------------------------------------------------ V4
def chay_bv(a) -> int:
    from backend import demo
    cl, ha, hg = chuan_bi(a.goc, a.admin)
    gv = hg["_gv"]
    kb = {r["sheet_id"]: r for r in doc_csv(KB)}
    e1 = {r["exam_code"]: r["answers"] for r in doc_csv(DAP_AN) if r["exam"] == "E1"}
    ket_qua = []

    def kiem(ten, dat, ct):
        ket_qua.append(dat)
        print(f"  [{'ĐẠT' if dat else 'KHÔNG ĐẠT'}] {ten} – {ct}")

    # (1) một ảnh JPG BV01
    eid = tao_ky_thi(cl, ha, gv, "[AV] E1 BV01", e1)
    p = kb["BV01"]
    r = tai(cl, hg, eid, ANH / "BV01.jpg", "image/jpeg")
    nhan = [p[f"q{i}"] for i in range(1, 41)]
    v = duyet_dung_giay(cl, hg, r["sheet_id"], nhan, p["sbd"], p["exam_code"])
    off = v["score"]["official"]
    kiem("JPG BV01: tải 201, SBD đọc đúng, điểm chính thức = điểm mong đợi", r["http"] == 201 and v["sbd"]["detected"] == p["sbd"]
         and off is not None and Decimal(str(off)) == Decimal(p["diem_mong_doi"]), f"tải {r['http']}, trạng thái lúc tải {r.get('status')}, tạm {r.get('provisional_score')}, cuối {off}, mong đợi {p['diem_mong_doi']}")

    # (2) HEIC thật (iPhone) = phiếu 0005_C1
    bl = demo.doc_bai_lam()
    khoa, _ = demo.khoa_tu_bai_lam(bl["nhan"])
    ma = {m: (khoa if m == bl["exam_code"] else demo.khoa_demo(m)) for m in demo.MA_DE}
    eid2 = tao_ky_thi(cl, ha, gv, "[AV] E2 HEIC 0005", ma)
    dung, diem = demo.diem_mong_doi(bl["nhan"])
    r = tai(cl, hg, eid2, HEIC, "image/heic")
    v = duyet_dung_giay(cl, hg, r["sheet_id"], bl["nhan"], bl["sbd"], bl["exam_code"]) if r["http"] == 201 and "sheet_id" in r else {"score": {"official": None}, "sbd": {"detected": None}}
    off = v["score"]["official"]
    kiem(f"HEIC thật ({HEIC.name}, {HEIC.stat().st_size // 1024} KB): tải 201, điểm chính thức = {dung}/40 = {diem}", r["http"] == 201 and off is not None
         and Decimal(str(off)) == Decimal(str(diem)), f"tải {r['http']}, trạng thái {r.get('status')}, SBD đọc {v['sbd']['detected']}, cuối {off}, mong đợi {diem}")

    # (3) lô 5 ảnh (BV01–BV05) trong kỳ thi mới
    eid3 = tao_ky_thi(cl, ha, gv, "[AV] E3 lô 5", e1)
    hd = {k: x for k, x in hg.items() if not k.startswith("_")}
    files = [("files", (f"BV0{i}.jpg", (ANH / f"BV0{i}.jpg").read_bytes(), "image/jpeg")) for i in range(1, 6)]
    t0 = time.time()
    r = cl.post(f"/exams/{eid3}/sheets/batch", headers=hd, files=files)
    dt = time.time() - t0
    j = r.json()
    kiem("lô 5 ảnh: 201, 5 kết quả không lỗi", r.status_code == 201 and j["tong"] == 5 and all("error" not in x for x in j["results"]), f"{dt:.1f} s, trạng thái {[x['status'] for x in j['results']]}")
    sai = []
    for x in j["results"]:
        ma_p = x["filename"].split(".")[0]
        q = kb[ma_p]
        vv = duyet_dung_giay(cl, hg, x["sheet_id"], [q[f"q{i}"] for i in range(1, 41)], q["sbd"], q["exam_code"])
        o = vv["score"]["official"]
        if o is None or Decimal(str(o)) != Decimal(q["diem_mong_doi"]):
            sai.append((ma_p, o, q["diem_mong_doi"]))
    kiem("lô 5 ảnh: điểm chính thức sau duyệt đúng giấy = điểm mong đợi cả 5", not sai, "khớp 5/5" if not sai else f"lệch: {sai}")
    print("KẾT LUẬN V4:", "ĐẠT" if all(ket_qua) else "KHÔNG ĐẠT")
    return 0 if all(ket_qua) else 1


# ------------------------------------------------------------------------------------------------ V5
def doc_ram(ten: str) -> float:
    s = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", ten], capture_output=True, text=True).stdout.split("/")[0].strip()
    m = re.match(r"([\d.]+)\s*([KMG]i?B)", s)
    if not m:
        return 0.0
    return float(m.group(1)) * {"KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0, "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}[m.group(2)]


class LayMau(threading.Thread):
    """Lấy mẫu RAM container liên tục (mỗi lần ~1 s) cho tới khi dừng; giữ giá trị lớn nhất."""

    def __init__(self, ten):
        super().__init__(daemon=True)
        self.ten, self.dung, self.cao, self.n = ten, False, 0.0, 0

    def run(self):
        while not self.dung:
            self.cao = max(self.cao, doc_ram(self.ten))
            self.n += 1


def chay_ram(a) -> int:
    cl, ha, hg = chuan_bi(a.goc, a.admin)
    gv = hg["_gv"]
    hd = {k: x for k, x in hg.items() if not k.startswith("_")}
    e1 = {r["exam_code"]: r["answers"] for r in doc_csv(DAP_AN) if r["exam"] == "E1"}
    anh = [(f"BV{i:02d}.jpg", (ANH / f"BV{i:02d}.jpg").read_bytes()) for i in range(1, 11)]

    def do(ten_pha, fn):
        m = LayMau(a.ten)
        m.start()
        t0 = time.time()
        fn()
        dt = time.time() - t0
        m.dung = True
        m.join(timeout=10)
        print(f"{a.nhan} | {ten_pha} | đỉnh RAM {m.cao:.0f} MiB ({m.n} mẫu) | {dt:.1f} s")

    time.sleep(8)
    print(f"{a.nhan} | nghỉ (sau khởi động) | RAM {doc_ram(a.ten):.0f} MiB")
    e = tao_ky_thi(cl, ha, gv, f"[AV] RAM {a.nhan} 1 ảnh", e1)
    do("chấm 1 ảnh", lambda: cl.post(f"/exams/{e}/sheets", headers=hd, files={"file": anh[0]}).raise_for_status())
    e = tao_ky_thi(cl, ha, gv, f"[AV] RAM {a.nhan} lô 5", e1)
    do("lô 5 ảnh (1 yêu cầu /batch)", lambda: cl.post(f"/exams/{e}/sheets/batch", headers=hd, files=[("files", x) for x in anh[:5]]).raise_for_status())
    e = tao_ky_thi(cl, ha, gv, f"[AV] RAM {a.nhan} 5 song song", e1)

    def song_song():
        with ThreadPoolExecutor(5) as ex:
            rs = list(ex.map(lambda x: httpx.post(f"{a.goc}/exams/{e}/sheets", headers=hd, files={"file": x}, timeout=180), anh[:5]))
        print(f"{a.nhan} |   mã HTTP của 5 yêu cầu song song: {[r.status_code for r in rs]}")
    do("5 ảnh gửi SONG SONG (5 yêu cầu)", song_song)
    print(f"{a.nhan} | nghỉ (sau tải) | RAM {doc_ram(a.ten):.0f} MiB")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["bv", "ram"])
    ap.add_argument("--goc", default="http://localhost:8080")
    ap.add_argument("--admin", required=True)
    ap.add_argument("--ten", default="smart-exam-app-1", help="tên container app (docker stats)")
    ap.add_argument("--nhan", default="thu", help="nhãn cấu hình in ở bảng V5 (vd cd1, cd2)")
    a = ap.parse_args()
    if not os.environ.get("AV_ADMIN_PW"):
        raise SystemExit("DỪNG: đặt biến môi trường AV_ADMIN_PW (mật khẩu quản trị của bản thử).")
    return chay_bv(a) if a.lenh == "bv" else chay_ram(a)


if __name__ == "__main__":
    sys.exit(main())
