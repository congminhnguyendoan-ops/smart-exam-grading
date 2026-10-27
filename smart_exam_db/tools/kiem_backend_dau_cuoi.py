"""
kiem_backend_dau_cuoi.py - Kiểm chứng ĐẦU-CUỐI backend trên ảnh dev 0001–0028 (B4, docs/ke_hoach_demo.md).

Chạy trên CSDL thật nhưng trong MỘT giao dịch luôn ROLLBACK (không để lại dòng nào) + thư mục ảnh tạm. Gọi API qua TestClient.

ĐỘC LẬP với code chấm của backend: điểm "đúng" tính lại từ data/ground_truth.csv (nhãn người tô) + đáp án đọc từ API
GET /exams/{id} (chuỗi đáp án trong CSDL), bằng luật riêng ở đây (KHÔNG import backend.grading / service):
    câu đúng ⇔ người tô ĐÚNG MỘT ô và ô đó = đáp án chuẩn (ô mờ cũng tính – chính sách faint_counts_as_answer = true);
    mỗi câu 10 / 40 = 0,25 điểm.

Mỗi ảnh đi 2 pha:
  1. TẢI ẢNH (không can thiệp): với các câu KHÔNG gắn "cần xem" so is_correct của hệ thống với đúng/sai thật
     -> "câu chấm sai mà không gắn cần xem" (PHẢI = 0); so cách đọc, SBD, mã đề tương tự; điểm tạm ≤ điểm thật ≤ điểm tối đa;
     phiếu tự chốt (không cần xem) phải có điểm chính thức = điểm thật.
  2. GIÁO VIÊN ĐẦU TIÊN (oracle): chốt từng câu cần xem đúng như tờ giấy (nhãn), chốt SBD / mã đề nếu cần
     -> điểm chính thức cuối cùng phải = điểm thật, đúng sinh viên.
Ảnh giả (data/_eval/_gia_v4, layout phiếu): ca mong đợi từ chối phải bị từ chối (không điểm); ca mong đợi 'ok' không bị từ chối.

  python tools/kiem_backend_dau_cuoi.py                 # 56 ảnh train + ảnh giả -> data/_eval/backend/
  python tools/kiem_backend_dau_cuoi.py --phieu 0002_C2 0014_C2 --khong-gia
"""
import argparse
import csv
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AUTH_MODE", "demo")      # công cụ chạy trong tiến trình: bỏ đăng nhập (backend: AUTH_MODE=on là mặc định)
from cv_engine.tap_du_lieu import PHIEU_TRAIN, ma_phieu  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "_eval" / "backend"
GIA = DATA / "_eval" / "_gia_v4"
DIEM_CAU = Decimal("0.25")                 # 10 điểm / 40 câu
NHOM_MA = {"khong_du_marker": {"thieu_marker", "marker_khong_dat"}}
SAI_MA_DA_BIET = {"mo_cheo30_0001_C1", "mo_cheo15_0015_C3", "mo_toi_nhieu_0001_C1", "mo_toi_nhieu_0008_C4"}   # như eval Tuần 4
MA_DE = ("101", "102", "103", "104")


# ------------------------------------------------------------------------------------------------ nhãn (độc lập)
def doc_nhan() -> dict:
    """{'0001': {'q': {1: 'd', ...}, 'sbd': '062384', 'sbd_bubble': '06238-', 'ma_de': '101', 'ma_de_bubble': '101'}} – CHỈ phiếu train."""
    out = {}
    with (DATA / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if int(r["sheet_id"]) in PHIEU_TRAIN:          # dòng phiếu val / test bỏ ngay khi đọc
                out[r["sheet_id"]] = {"q": {q: r[f"q{q}"] for q in range(1, 41)}, "sbd": r["sbd"], "sbd_bubble": r["sbd_bubble"],
                                      "ma_de": r["exam_code"], "ma_de_bubble": r["exam_code_bubble"]}
    return out


def dung_that(nhan_cau: str, dap_an: str) -> bool:
    return len(nhan_cau) == 1 and nhan_cau.upper() == dap_an


def chon_that(nhan_cau: str) -> str:
    return "" if nhan_cau == "-" else nhan_cau.upper()


# ------------------------------------------------------------------------------------------------ phiên làm việc (rollback)
@contextmanager
def phien():
    """(client, conn): API thật trên CSDL thật, một giao dịch ROLLBACK, thư mục ảnh tạm."""
    from fastapi.testclient import TestClient

    from backend import migrate
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    from backend.main import app, get_cau_hinh, get_conn
    migrate.ap_dung()
    cfg = replace(lay_cau_hinh(), storage_dir=Path(tempfile.mkdtemp(prefix="kho_dau_cuoi_")))
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


def tao_ky_thi(client, tieu_de: str) -> tuple[int, dict]:
    from backend import demo                                  # chỉ để sinh đáp án mẫu (dữ liệu), không phải code chấm
    r = client.post("/exams", json={"exam_title": tieu_de, "subject_code": "KTDC" + tieu_de[-1], "num_questions": 40,
                                    "codes": [{"code": m, "answers": demo.khoa_demo(m)} for m in MA_DE]})
    assert r.status_code == 201, r.text
    eid = r.json()["exam_id"]
    return eid, {c["code"]: c["answers"] for c in client.get(f"/exams/{eid}").json()["codes"]}     # đáp án ĐỌC TỪ CSDL qua API


# ------------------------------------------------------------------------------------------------ một ảnh phiếu
def chay_phieu(client, conn, exam_id: int, dap_an: dict, ten: str, nhan: dict) -> dict:
    ma_so = f"{ma_phieu(ten):04d}"
    t = nhan[ma_so]
    key = dap_an[t["ma_de"]]
    that = {q: dung_that(t["q"][q], key[q - 1]) for q in range(1, 41)}
    diem_that = DIEM_CAU * sum(that.values())
    conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV kiểm đầu-cuối') ON CONFLICT DO NOTHING", (t["sbd"],))

    r = client.post(f"/exams/{exam_id}/sheets", files={"file": (f"{ten}.jpg", (DATA / "raw" / f"{ten}.jpg").read_bytes(), "image/jpeg")})
    assert r.status_code == 201, r.text
    sid = r.json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    row = {"anh": ten, "sheet_id": sid, "dieu_kien": ten.split("_")[1], "status_tai": v["status"], "cau_can_xem": 0, "cau_chac_chan": 0,
           "cham_sai_khong_gan_can_xem": 0, "doc_sai_khong_gan_can_xem": 0, "sai_im_lang_sbd": 0, "sai_im_lang_ma_de": 0,
           "cau_doc_sai_co_gan_can_xem": 0, "vi_pham_can": 0, "tu_chot_sai_diem": 0, "diem_that": float(diem_that),
           "diem_tam": v["score"]["provisional"], "diem_toi_da": v["score"]["max_possible"]}
    if v["status"] == "rejected":
        row["ghi_chu"] = f"bị từ chối {v['reject_code']}"
        return row
    code_ok = v["exam_code"]["matched_code"] == t["ma_de"]
    for q in v["questions"]:
        lab = t["q"][q["question_no"]]
        doc_dung = q["selected_options"] == chon_that(lab)
        if q["needs_review"]:
            row["cau_can_xem"] += 1
            row["cau_doc_sai_co_gan_can_xem"] += not doc_dung
            assert q["is_correct"] is None, f"{ten} câu {q['question_no']}: cần xem mà vẫn bị chấm"
            continue
        row["cau_chac_chan"] += 1
        row["doc_sai_khong_gan_can_xem"] += not doc_dung
        if code_ok and q["is_correct"] is not None and q["is_correct"] != that[q["question_no"]]:
            row["cham_sai_khong_gan_can_xem"] += 1
    # Tuần 6 Phần C: SBD / mã đề được nhận (hai kênh bubble + chữ viết tay khớp) phải = chữ VIẾT TAY thật (nhãn người viết), không chỉ = bubble
    if not v["sbd"]["can_xem"] and v["sbd"]["detected"] != t["sbd"]:
        row["sai_im_lang_sbd"] = 1
    if not v["exam_code"]["can_xem"] and v["exam_code"]["detected"] != t["ma_de"]:
        row["sai_im_lang_ma_de"] = 1
    row["sbd_can_xem"], row["ma_de_can_xem"] = int(v["sbd"]["can_xem"]), int(v["exam_code"]["can_xem"])
    row["dinh_danh_can_xem"] = int(v["sbd"]["can_xem"] or v["exam_code"]["can_xem"])
    row["dinh_danh_can_xem_thua"] = int(row["dinh_danh_can_xem"] and v["sbd"]["detected"] == t["sbd"] and v["exam_code"]["detected"] == t["ma_de"])
    sc = v["score"]
    if code_ok:
        row["vi_pham_can"] = int(not (Decimal(str(sc["provisional"])) <= diem_that <= Decimal(str(sc["max_possible"]))))
    if v["status"] == "graded":
        row["tu_chot_sai_diem"] = int(code_ok is False or Decimal(str(sc["official"])) != diem_that
                                      or v["student"]["student_code"] != t["sbd"])
        row["status_cuoi"], row["diem_cuoi"] = "graded", sc["official"]
        return row

    # --- pha 2: giáo viên đầu tiên (oracle) chốt đúng như tờ giấy
    for c in client.get(f"/sheets/{sid}/review-questions").json():
        lab = t["q"][c["question_no"]]
        rr = client.post(f"/sheets/{sid}/questions/{c['question_no']}/review",
                         json={"action": "set", "selected_options": chon_that(lab)})
        assert rr.status_code == 200, rr.text
    v = client.get(f"/sheets/{sid}").json()
    if v["status"] == "needs_review":
        rr = client.put(f"/sheets/{sid}/identity", json={"sbd": t["sbd"], "exam_code": t["ma_de"]})
        assert rr.status_code == 200, rr.text
        v = rr.json()
    row["status_cuoi"] = v["status"]
    row["diem_cuoi"] = v["score"]["official"]
    row["cuoi_dung"] = int(v["status"] == "graded" and v["score"]["result_status"] == "confirmed"
                           and Decimal(str(v["score"]["official"])) == diem_that and v["student"]["student_code"] == t["sbd"])
    return row


# ------------------------------------------------------------------------------------------------ ảnh giả
def ds_gia() -> list[dict]:
    p = GIA / "danh_sach.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r["layout"] == "phieu" and r["mong_doi"] in ("tu_choi", "ok")]


def chay_gia(client, conn, exam_id: int, r: dict) -> dict:
    p = GIA / f"{r['ten']}.jpg"
    out = {"ten": r["ten"], "mong_doi": r["mong_doi"], "ly_do_mong_doi": r["ly_do_mong_doi"]}
    if not p.exists():
        return {**out, "ket_qua": "bo_qua_thieu_file"}
    j = client.post(f"/exams/{exam_id}/sheets", files={"file": (p.name, p.read_bytes(), "image/jpeg")})
    assert j.status_code == 201, j.text
    j = j.json()
    co_diem = conn.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s", (j["sheet_id"],)).fetchone()["n"]
    out.update(status=j["status"], reject_code=j["reject_code"], official=j["official_score"])
    if r["mong_doi"] == "tu_choi":
        if j["status"] != "rejected" or co_diem or j["official_score"] is not None:
            out["ket_qua"] = "LOI_IM_LANG"                        # lẽ ra phải từ chối mà vẫn nhận
        else:
            mong = set().union(*[NHOM_MA.get(m, {m}) for m in r["ly_do_mong_doi"].split("|")]) if r["ly_do_mong_doi"] else set()
            out["ket_qua"] = ("tu_choi_dung" if j["reject_code"] in mong or not mong else
                              "sai_ma_da_biet" if r["ten"] in SAI_MA_DA_BIET else "sai_ma")
    else:
        out["ket_qua"] = "tu_choi_nham" if j["status"] == "rejected" else "nhan_dung"
    return out


# ------------------------------------------------------------------------------------------------ báo cáo
def chay(ds_anh: list[str], voi_gia: bool, tien_do=print, gia_toi_da: int | None = None) -> dict:
    nhan = doc_nhan()
    with phien() as (client, conn):
        # hai kỳ thi cùng đáp án: ảnh thứ nhất của phiếu vào A, ảnh thứ hai vào B (tránh trùng SBD làm lệch phép kiểm điểm)
        a, dap_an = tao_ky_thi(client, "Kiểm đầu-cuối A")
        b, _ = tao_ky_thi(client, "Kiểm đầu-cuối B")
        da = set()
        rows = []
        for ten in ds_anh:
            ms = ma_phieu(ten)
            assert ms in PHIEU_TRAIN, f"{ten}: ngoài tập train 0001–0028 – KHÔNG chạy"
            eid = b if ms in da else a
            da.add(ms)
            rows.append(chay_phieu(client, conn, eid, dap_an, ten, nhan))
            tien_do(f"{ten}: {rows[-1]['status_tai']} → {rows[-1].get('status_cuoi', rows[-1]['status_tai'])}, cần xem {rows[-1]['cau_can_xem']}, "
                    f"chấm sai không cờ {rows[-1]['cham_sai_khong_gan_can_xem']}")
        gia = []
        if voi_gia:
            for r in ds_gia()[:gia_toi_da]:
                gia.append(chay_gia(client, conn, a, r))
        return {"phieu": rows, "gia": gia}


def tom_tat(kq: dict) -> dict:
    rows = [r for r in kq["phieu"] if r["status_tai"] != "rejected"]
    s = {"anh": len(kq["phieu"]), "anh_bi_tu_choi": len(kq["phieu"]) - len(rows)}
    for k in ("cau_can_xem", "cau_chac_chan", "cham_sai_khong_gan_can_xem", "doc_sai_khong_gan_can_xem", "sai_im_lang_sbd",
              "sai_im_lang_ma_de", "cau_doc_sai_co_gan_can_xem", "vi_pham_can", "tu_chot_sai_diem"):
        s[k] = sum(r[k] for r in rows)
    for k in ("sbd_can_xem", "ma_de_can_xem", "dinh_danh_can_xem", "dinh_danh_can_xem_thua"):
        s[k] = sum(r.get(k, 0) for r in rows)
    s["tu_chot_khi_tai"] = sum(r["status_tai"] == "graded" for r in rows)
    s["can_xem_khi_tai"] = sum(r["status_tai"] == "needs_review" for r in rows)
    s["cuoi_graded"] = sum(r.get("status_cuoi") == "graded" for r in rows)
    s["cuoi_dung_diem"] = sum(r.get("cuoi_dung", 0) for r in rows) + sum(r["status_tai"] == "graded" and not r["tu_chot_sai_diem"] for r in rows)
    s["diem_tam_vi_pham"] = s["vi_pham_can"]
    g = {}
    for r in kq["gia"]:
        g[r["ket_qua"]] = g.get(r["ket_qua"], 0) + 1
    s["gia"] = g
    return s


def theo_dieu_kien(kq: dict) -> dict:
    out = {}
    for dk in ("C1", "C2", "C3", "C4"):
        rs = [r for r in kq["phieu"] if r["dieu_kien"] == dk and r["status_tai"] != "rejected"]
        out[dk] = {"anh": len(rs), "cau": 40 * len(rs), "cau_can_xem": sum(r["cau_can_xem"] for r in rs),
                   "cham_sai_khong_gan_can_xem": sum(r["cham_sai_khong_gan_can_xem"] for r in rs),
                   "doc_sai_khong_gan_can_xem": sum(r["doc_sai_khong_gan_can_xem"] for r in rs),
                   "tu_chot": sum(r["status_tai"] == "graded" for r in rs),
                   "cuoi_dung": sum(r.get("cuoi_dung", 0) for r in rs) + sum(r["status_tai"] == "graded" and not r["tu_chot_sai_diem"] for r in rs)}
    return out


def ghi_bao_cao(kq: dict) -> str:
    s, dk = tom_tat(kq), theo_dieu_kien(kq)
    L = ["# Kiểm chứng đầu-cuối backend (B4) – ảnh dev 0001–0028", "",
         f"- Ảnh phiếu: **{s['anh']}** (bị từ chối {s['anh_bi_tu_choi']}); chạy trong giao dịch ROLLBACK, không để lại dòng nào.",
         f"- **Câu chấm sai mà KHÔNG gắn cần xem: {s['cham_sai_khong_gan_can_xem']}** (trên {s['cau_chac_chan']} câu chắc chắn)",
         f"- Câu đọc sai mà không gắn cần xem: {s['doc_sai_khong_gan_can_xem']} · SBD sai im lặng: {s['sai_im_lang_sbd']} · mã đề sai im lặng: "
         f"{s['sai_im_lang_ma_de']} · điểm tạm / điểm tối đa không bao điểm thật: {s['vi_pham_can']} · phiếu tự chốt sai điểm: {s['tu_chot_sai_diem']}",
         f"- Câu cần xem: {s['cau_can_xem']} / {40 * s['anh']} ({100 * s['cau_can_xem'] / max(1, 40 * s['anh']):.1f}%); trong đó máy đọc sai "
         f"(nhưng có cờ, an toàn): {s['cau_doc_sai_co_gan_can_xem']}",
         f"- SBD / mã đề cần xem khi tải: SBD {s['sbd_can_xem']} · mã đề {s['ma_de_can_xem']} · ảnh có SBD hoặc mã đề cần xem "
         f"{s['dinh_danh_can_xem']} / {s['anh'] - s['anh_bi_tu_choi']} ({100 * s['dinh_danh_can_xem'] / max(1, s['anh'] - s['anh_bi_tu_choi']):.1f}%; T4)",
         f"- Khi tải ảnh: tự chốt (không cần xem) {s['tu_chot_khi_tai']} phiếu, cần xem {s['can_xem_khi_tai']} phiếu",
         f"- Sau giáo viên (oracle): chốt {s['cuoi_graded']} / {s['anh'] - s['anh_bi_tu_choi']} phiếu; **điểm chính thức = điểm tính độc lập và đúng "
         f"sinh viên: {s['cuoi_dung_diem']} / {s['anh'] - s['anh_bi_tu_choi']} phiếu**", "",
         "| Điều kiện | Ảnh | Câu | Cần xem | Chấm sai không cờ | Đọc sai không cờ | Tự chốt khi tải | Điểm cuối đúng |", "|---|---|---|---|---|---|---|---|"]
    for k, v in dk.items():
        L.append(f"| {k} | {v['anh']} | {v['cau']} | {v['cau_can_xem']} | {v['cham_sai_khong_gan_can_xem']} | {v['doc_sai_khong_gan_can_xem']} | "
                 f"{v['tu_chot']} | {v['cuoi_dung']} / {v['anh']} |")
    if kq["gia"]:
        L += ["", f"Ảnh giả (layout phiếu, {len(kq['gia'])} ảnh): " + ", ".join(f"{k} {v}" for k, v in sorted(s["gia"].items())),
              "(LOI_IM_LANG = lẽ ra phải từ chối mà vẫn nhận; tu_choi_nham = ảnh mong đợi chấp nhận nhưng bị từ chối; sai_ma = từ chối với mã khác mong đợi.)"]
    bad = [r for r in kq["phieu"] if r["cham_sai_khong_gan_can_xem"] or r["doc_sai_khong_gan_can_xem"] or r["sai_im_lang_sbd"]
           or r["sai_im_lang_ma_de"] or r["vi_pham_can"] or r["tu_chot_sai_diem"] or r.get("cuoi_dung") == 0]
    if bad:
        L += ["", "## Phiếu có bất thường"] + [f"- {r['anh']}: {json.dumps({k: v for k, v in r.items() if v and k not in ('anh', 'sheet_id')}, ensure_ascii=False)}"
                                              for r in bad]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Kiểm đầu-cuối backend trên ảnh dev 0001–0028")
    ap.add_argument("--phieu", nargs="*", help="tên ảnh (vd 0002_C2); bỏ trống = cả 56 ảnh train")
    ap.add_argument("--khong-gia", action="store_true", help="bỏ qua ảnh giả _gia_v4")
    a = ap.parse_args()
    ds = a.phieu or sorted(p.stem for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in PHIEU_TRAIN)
    kq = chay(ds, not a.khong_gia)
    OUT.mkdir(parents=True, exist_ok=True)
    for ten, rows in (("phieu_dau_cuoi.csv", kq["phieu"]), ("gia_dau_cuoi.csv", kq["gia"])):
        if rows:
            keys = list({k: 0 for r in rows for k in r})
            with (OUT / ten).open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
    md = ghi_bao_cao(kq)
    (OUT / "bao_cao_dau_cuoi.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    s = tom_tat(kq)
    sys.exit(0 if (s["cham_sai_khong_gan_can_xem"] == 0 and s["doc_sai_khong_gan_can_xem"] == 0 and s["gia"].get("LOI_IM_LANG", 0) == 0) else 1)


if __name__ == "__main__":
    main()
