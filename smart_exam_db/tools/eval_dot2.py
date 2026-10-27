"""
eval_dot2.py - Đánh giá CẢ HỆ THỐNG trên ĐỢT 2 (phiếu 0101–0110, chụp bằng điện thoại) – docs/ke_hoach_test_dot2.md.

Cùng khuôn eval_he_thong.py: ĐỘC LẬP với mã được chấm – chỉ đi qua API công khai của backend (TestClient, CSDL thật trong giao dịch
ROLLBACK, ảnh tạm); KHÔNG import cv_engine.omr / ocr / backend.service / grading. Tái dùng thước đo + phiên + tạo kỳ thi từ eval_he_thong.
Kết quả "đúng thật" tính riêng từ nhãn đợt 2 (answer_sheet/dot2/ground_truth_dot2.csv + cell_labels_dot2.csv, hoặc bản đã sửa theo giấy):
    ký hiệu ô: 'B' đậm · 'b' mờ · '*B' CHẤM NHỎ (vết, KHÔNG phải đáp án: tập ô thật = trống) · '-' trống.
    câu đúng ⇔ người tô ĐÚNG MỘT ô và ô đó = đáp án chuẩn (đậm hay mờ đều là "được tô"); mỗi câu 10/40 = 0,25 điểm.
    Lỗi nặng = tập ô đọc ≠ tập ô thật mà KHÔNG gắn cần xem (gồm: chấm nhỏ bị đọc thành đáp án chắc). "Bỏ sót vết" (vết đọc trống chắc,
    không cờ) là CHỈ BÁO, không phải lỗi nặng (điểm không đổi).

  python tools/eval_dot2.py kiem-nhan                         # nhãn: cell_labels khớp ground_truth (đối chiếu chéo) – lệch thì DỪNG
  python tools/eval_dot2.py tao-gia                           # 20 ảnh giả hoá -> data/_eval/dot2/thu_gia/ (CHỈ để thử công cụ)
  python tools/eval_dot2.py run --thu-gia [--xem]             # chạy thử công cụ trên ảnh giả hoá (không khoá, không đăng ký)
  python tools/eval_dot2.py ap-dung-sua                       # data/dot2/sua_nhan.csv -> bản nhãn đã sửa theo giấy
  python tools/eval_dot2.py run --xac-nhan-dot2 --xem         # ĐỢT 2 THẬT: MỘT LẦN, sau đăng ký (docs/dang_ky_test_dot2.json)
Chốt chặn chạy thật: --xac-nhan-dot2 + bản đăng ký khớp (mã khoá không đổi, SHA) + data/_eval/dot2/da_chay_dot2.lock (tạo NGAY khi bắt đầu;
có rồi thì từ chối, kể cả lần trước lỗi giữa chừng). Ảnh: data/raw_dot2/NNNN_Ck.jpg (data/ nằm trong .gitignore).
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import eval_he_thong as H  # noqa: E402  (thước đo, phiên TestClient, tạo kỳ thi, HTML xem mù – không phải luật chấm)
from cv_engine.tap_du_lieu import PHIEU_TEST, PHIEU_TRAIN, PHIEU_VAL  # noqa: E402  (chỉ để kiểm đợt 2 không trùng tập khác)

PHIEU_DOT2 = range(101, 111)
DATA = ROOT / "data"
DOT2_GOC = ROOT / "answer_sheet" / "dot2"
GT, CELL = DOT2_GOC / "ground_truth_dot2.csv", DOT2_GOC / "cell_labels_dot2.csv"
DOT2_DATA = DATA / "dot2"
GT_SUA, CELL_SUA, SUA_NHAN = DOT2_DATA / "ground_truth_dot2_da_sua.csv", DOT2_DATA / "cell_labels_dot2_da_sua.csv", DOT2_DATA / "sua_nhan.csv"
RAW_DOT2 = DATA / "raw_dot2"
OUT = DATA / "_eval" / "dot2"
THU_GIA = OUT / "thu_gia"
KHOA = OUT / "da_chay_dot2.lock"
DANG_KY = ROOT / "docs" / "dang_ky_test_dot2.json"
LAYOUT = ROOT / "answer_sheet" / "output" / "layout.json"
MAU_PNG = ROOT / "answer_sheet" / "output" / "phieu_trang_300dpi.png"
DUONG_DAN_MA = ["smart_exam_db/cv_engine", "smart_exam_db/models", "smart_exam_db/backend", "smart_exam_db/answer_sheet/output"]
FILE_SHA_GOC = ["smart_exam_db/tools/eval_dot2.py", "smart_exam_db/answer_sheet/dot2/ground_truth_dot2.csv", "smart_exam_db/answer_sheet/dot2/cell_labels_dot2.csv"]
LOAI_CAU = ("dam", "mo", "hai_dam", "dam_mo", "hai_mo", "ba_dam", "ba_mo", "cham_nho", "trong")
TEN_LOAI = {"dam": "1 đậm", "mo": "1 mờ", "hai_dam": "hai đậm", "dam_mo": "đậm + mờ", "hai_mo": "hai mờ", "ba_dam": "ba đậm", "ba_mo": "ba mờ",
            "cham_nho": "vết (chấm nhỏ)", "trong": "trống"}
XAM_THU_GIA = {"dam": 30, "mo": 170, "mo_0105": 150, "vet": 30}


# ------------------------------------------------------------------------------------------------ nhãn (độc lập)
def tap_chon(lab: str) -> str:
    """Tập ô thật: '-' hoặc chấm nhỏ ('*B') -> '' ; 'bD' -> 'BD'."""
    return "" if lab == "-" or lab.startswith("*") else "".join(sorted(lab.upper()))


def trang_thai_that(lab: str) -> str:
    if lab == "-":
        return "trong"
    if lab.startswith("*"):
        return "vet"
    if len(lab) > 1:
        return "nhieu"
    return "ro" if lab.isupper() else "mo"


def loai_cau(lab: str) -> str:
    if lab == "-":
        return "trong"
    if lab.startswith("*"):
        return "cham_nho"
    n, hoa = len(lab), sum(c.isupper() for c in lab)
    if n == 1:
        return "dam" if hoa else "mo"
    ten = {2: ("hai_dam", "dam_mo", "hai_mo"), 3: ("ba_dam", None, "ba_mo")}[n]
    return ten[0] if hoa == n else ten[2] if hoa == 0 else ten[1] or "ba_hon_hop"


def nhan_o(lab: str, o: str) -> str:
    """Nhãn cấp ô của ô `o` trong câu có ký hiệu `lab`: filled / faint / vet / blank."""
    if lab.startswith("*"):
        return "vet" if lab[1:] == o else "blank"
    for c in ("-" if lab == "-" else lab):
        if c.upper() == o:
            return "filled" if c.isupper() else "faint"
    return "blank"


def sinh_cell_labels(gt_rows: list[dict]) -> list[tuple]:
    """(sheet_id, question, option, cell_label, question_state) sinh từ ground_truth – cùng quy ước cell_labels_dot2.csv."""
    out = []
    for r in gt_rows:
        for q in range(1, 41):
            lab = r[f"q{q}"]
            for o in "ABCD":
                out.append((r["sheet_id"], str(q), o, nhan_o(lab, o), loai_cau(lab)))
        for truong, khoa, ten in (("sbd_bubble", 6, "sbd"), ("exam_code_bubble", 3, "exam_code")):
            for i in range(khoa):
                ch = r[truong][i]
                for d in "0123456789":
                    out.append((r["sheet_id"], f"{ten}{i + 1}", d, "filled" if ch == d else "blank", "blank" if ch == "-" else "filled"))
    return out


def doc_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nguon_nhan(dung_sua: bool | None = None) -> tuple[Path, Path]:
    """(ground_truth, cell_labels): bản đã sửa theo giấy nếu có (data/dot2/), không thì bản gốc answer_sheet/dot2/."""
    sua = GT_SUA.exists() and CELL_SUA.exists() if dung_sua is None else dung_sua
    return (GT_SUA, CELL_SUA) if sua else (GT, CELL)


def doc_nhan(gt: Path | None = None, cell: Path | None = None) -> dict:
    """{'0101': {q, loai, sbd, ma_de, sbd_bubble, ma_de_bubble, writer, pen, dk}}. Đối chiếu CHÉO ground_truth ↔ cell_labels: lệch thì DỪNG."""
    g, c = nguon_nhan() if gt is None else (gt, cell)
    rows = [r for r in doc_csv(g) if int(r["sheet_id"]) in PHIEU_DOT2]
    sinh = {(a, b, d): (e, f) for a, b, d, e, f in sinh_cell_labels(rows)}
    that = {(r["sheet_id"], r["question"], r["option"]): (r["cell_label"], r["question_state"]) for r in doc_csv(c)}
    khac = [k for k in sinh if that.get(k) != sinh[k]] + [k for k in that if k not in sinh]
    if khac:
        raise SystemExit(f"DỪNG: cell_labels lệch ground_truth ở {len(khac)} ô (vd {khac[:3]}) – sửa nhãn phải qua `ap-dung-sua`, không sửa tay.")
    out = {}
    for r in rows:
        ms = r["sheet_id"]
        out[ms] = {"q": {q: r[f"q{q}"] for q in range(1, 41)}, "loai": {q: loai_cau(r[f"q{q}"]) for q in range(1, 41)}, "sbd": r["sbd"],
                   "ma_de": r["exam_code"], "sbd_bubble": r["sbd_bubble"], "ma_de_bubble": r["exam_code_bubble"], "writer": r["writer"],
                   "pen": r["pen"], "dk": r["conditions"].split("+")}
    return out


def ten_anh(nhan: dict) -> list[str]:
    return [f"{ms}_{c}" for ms, t in sorted(nhan.items()) for c in t["dk"]]


# ------------------------------------------------------------------------------------------------ sửa nhãn theo giấy
def ap_dung_sua() -> None:
    """data/dot2/sua_nhan.csv (phieu, muc, nhan_cu, nhan_moi, ly_do, ngay) -> ground_truth_dot2_da_sua.csv + cell_labels_dot2_da_sua.csv.
    muc: q1..q40 | sbd | exam_code | sbd_bubble | exam_code_bubble | pen | writer. Chỉ khi người dùng xác nhận bằng GIẤY THẬT; không đọc kết quả máy."""
    if not SUA_NHAN.exists():
        raise SystemExit(f"DỪNG: chưa có {SUA_NHAN} (cột: phieu, muc, nhan_cu, nhan_moi, ly_do, ngay).")
    rows = doc_csv(GT)
    cot = {"sheet_id", "phieu"}
    for s in doc_csv(SUA_NHAN):
        r = next((x for x in rows if x["sheet_id"] == s["phieu"].zfill(4)), None)
        if r is None or s["muc"] not in r or s["muc"] in cot:
            raise SystemExit(f"DỪNG: dòng sửa không hợp lệ: {s}")
        if r[s["muc"]] != s["nhan_cu"]:
            raise SystemExit(f"DỪNG: {s['phieu']} {s['muc']} nhãn hiện tại '{r[s['muc']]}' ≠ nhan_cu '{s['nhan_cu']}'")
        if not s["ly_do"].strip() or not s["ngay"].strip():
            raise SystemExit(f"DỪNG: thiếu lý do / ngày: {s}")
        r[s["muc"]] = s["nhan_moi"]
    DOT2_DATA.mkdir(parents=True, exist_ok=True)
    with GT_SUA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with CELL_SUA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sheet_id", "question", "option", "cell_label", "question_state"])
        w.writerows(sinh_cell_labels(rows))
    print(f"Đã ghi {GT_SUA} và {CELL_SUA}; hash ghi vào đăng ký bổ sung TRƯỚC khi chạy.")


# ------------------------------------------------------------------------------------------------ ảnh giả hoá (chỉ thử công cụ)
def tao_gia() -> None:
    """Vẽ 20 ảnh lên mẫu phiếu trắng: đậm xám 30; mờ xám 170 (0105: 150); vết 0,3r xám 30; bubble đậm; KHÔNG vẽ chữ viết tay."""
    import cv2
    L = json.loads(LAYOUT.read_text(encoding="utf-8"))
    mau = cv2.imdecode(__import__("numpy").fromfile(MAU_PNG, __import__("numpy").uint8), cv2.IMREAD_GRAYSCALE)
    ans = L["answers"]
    R = ans["bubble_radius"]
    THU_GIA.mkdir(parents=True, exist_ok=True)
    nhan = doc_nhan(GT, CELL)

    def cham(anh, c, r, g):
        cv2.circle(anh, (int(round(c[0])), int(round(c[1]))), int(round(r)), int(g), -1)
    for ms, t in nhan.items():
        anh = mau.copy()
        for q, lab in t["q"].items():
            if lab == "-":
                continue
            if lab.startswith("*"):
                cham(anh, ans["centers"][str(q)][lab[1:]], 0.3 * R, XAM_THU_GIA["vet"])
                continue
            for ch in lab:
                g = XAM_THU_GIA["dam"] if ch.isupper() else XAM_THU_GIA["mo_0105" if ms == "0105" else "mo"]
                cham(anh, ans["centers"][str(q)][ch.upper()], 0.85 * R, g)
        for truong, key, nb in (("sbd", "sbd", t["sbd_bubble"]), ("exam_code", "exam_code", t["ma_de_bubble"])):
            for i, ch in enumerate(nb):
                if ch != "-":
                    cham(anh, L[key]["bubbles"][i][int(ch)], 0.85 * L[key]["bubble_radius"], XAM_THU_GIA["dam"])
        for c in t["dk"]:
            cv2.imencode(".jpg", anh, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(THU_GIA / f"{ms}_{c}.jpg")
    print(f"Đã ghi {2 * len(nhan)} ảnh giả hoá ở {THU_GIA}")


# ------------------------------------------------------------------------------------------------ một ảnh
def chay_phieu(client, conn, exam_id: int, dap_an: dict, ten: str, thu_muc: Path, nhan: dict, xem: bool, co_chu_so: bool) -> dict:
    ms = ten.split("_")[0]
    t = nhan[ms]
    key = dap_an[t["ma_de"]]
    that = {q: H.dung_that(t["q"][q], key[q - 1]) for q in range(1, 41)}
    diem_that = H.DIEM_CAU * sum(that.values())
    conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV đợt 2') ON CONFLICT DO NOTHING", (t["sbd"],))
    anh_bytes = (thu_muc / f"{ten}.jpg").read_bytes()
    t0 = time.perf_counter()
    r = client.post(f"/exams/{exam_id}/sheets", files={"file": (f"{ten}.jpg", anh_bytes, "image/jpeg")})
    giay = time.perf_counter() - t0
    assert r.status_code == 201, r.text
    sid = r.json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    row = {"anh": ten, "phieu": int(ms), "sheet_id": sid, "dieu_kien": ten.split("_")[1], "nguoi": t["writer"], "but": t["pen"], "status_tai": v["status"],
           "giay": round(giay, 3), "diem_that": float(diem_that), "tu_choi": v.get("reject_code") or "", "cau": [], "cot": [], "cx_thua": 0,
           "cx_thua_trong": 0, "n_ro": 0, "n_trong": 0, "nang_cau": 0, "nhe_cau": 0, "nang_cot": 0, "cham_sai_khong_co": 0, "tu_chot_sai": 0,
           "vi_pham_can": 0, "sbd_sai_im_lang": 0, "ma_sai_im_lang": 0, "cuoi_dung": None, "chu_so_dung": 0, "chu_so_n": 0, "cx_cau": 0,
           "sbd_can_xem": None, "ma_can_xem": None, "ma_ly_do": [], "sbd_ly_do": [], "vet_n": 0, "vet_gan_co": 0, "vet_bo_sot": 0, "vet_doc_dap_an_chac": 0}
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
        nang = (not cx) and doc_o != tap_chon(lab)
        nhe = (not cx) and doc_o == tap_chon(lab) and tt == "mo" and q["state"] == "filled"
        row["cx_cau"] += cx
        row["n_ro"] += tt == "ro"
        row["n_trong"] += tt == "trong"
        row["cx_thua"] += cx and tt == "ro"
        row["cx_thua_trong"] += cx and tt == "trong"
        row["nang_cau"] += nang
        row["nhe_cau"] += nhe
        if tt == "vet":
            row["vet_n"] += 1
            row["vet_gan_co"] += cx
            row["vet_bo_sot"] += (not cx) and doc_o == ""
            row["vet_doc_dap_an_chac"] += (not cx) and doc_o != ""
        if not cx:
            if code_ok and q["is_correct"] is not None and q["is_correct"] != that[n]:
                row["cham_sai_khong_co"] += 1
        else:
            assert q["is_correct"] is None, f"{ten} câu {n}: cần xem mà vẫn bị chấm"
        row["cau"].append({"n": n, "that": tt, "nhan": lab, "loai": t["loai"][n], "doc": q["state"], "doc_o": doc_o, "cx": cx, "ly_do": q["reasons"],
                           "nang": nang, "nhe": nhe})
    for truong, khoa, nhan_b in (("sbd", "sbd", t["sbd_bubble"]), ("exam_code", "ma", t["ma_de_bubble"])):
        f = v["sbd"] if truong == "sbd" else v["exam_code"]
        viet = t["sbd"] if truong == "sbd" else t["ma_de"]
        for i, c in enumerate(f["columns"]):
            that_b = "?" if nhan_b[i] == "-" else nhan_b[i]
            row["nang_cot"] += c["bubble"] != that_b and c["bubble"] != "?" and "bubble_cx" not in c["ly_do"]
            hw = c["handwriting"]
            if co_chu_so:
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
        row["vi_pham_can"] = int(not (H.Decimal(str(sc["provisional"])) <= diem_that <= H.Decimal(str(sc["max_possible"]))))
    if v["status"] == "graded":
        row["tu_chot_sai"] = int(code_ok is False or H.Decimal(str(sc["official"])) != diem_that or v["student"]["student_code"] != t["sbd"])
    row["can_xem_cot_khong_to"] = [c["truong"] for c in row["cot"] if c["that_bubble"] == "?"]
    if xem:                                                     # ảnh cho HTML (chụp TRƯỚC khi giáo viên sửa)
        row["_anh_nan"] = client.get(f"/sheets/{sid}/image?kind=aligned").content
        row["_o_chu"] = {(c["truong"], c["i"]): client.get(f"/sheets/{sid}/digits/{c['truong']}/{c['i']}/image").content for c in row["cot"]}
        muc = {c["n"] for c in row["cau"] if c["that"] in ("mo", "nhieu", "vet")}
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
    row["cuoi_dung"] = int(v2["status"] == "graded" and v2["score"]["result_status"] == "confirmed" and H.Decimal(str(v2["score"]["official"])) == diem_that
                           and v2["student"]["student_code"] == t["sbd"])
    row["status_cuoi"] = v2["status"]
    return row


# ------------------------------------------------------------------------------------------------ tổng hợp
def gop(cau: list[dict]) -> dict:
    n = len(cau)
    cx = sum(c["cx"] for c in cau)
    return {"n": n, "can_xem": cx, "ti_le_can_xem": cx / n if n else None, "nang": sum(c["nang"] for c in cau), "nhe": sum(c["nhe"] for c in cau),
            "bo_sot_vet": sum(c["that"] == "vet" and not c["cx"] and c["doc_o"] == "" for c in cau)}


def phan_tich(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["status_tai"] != "rejected"]
    cau = [c | {"r": r} for r in ok for c in r["cau"]]
    out = {"theo_loai": {TEN_LOAI[k]: gop([c for c in cau if c["loai"] == k]) for k in LOAI_CAU}}
    out["theo_phieu"] = {f"{p:04d}": gop([c for c in cau if c["r"]["phieu"] == p]) for p in sorted({r["phieu"] for r in ok})}
    out["theo_dieu_kien"] = {dk: gop([c for c in cau if c["r"]["dieu_kien"] == dk]) for dk in ("C1", "C2", "C3", "C4")}
    out["theo_nguoi_viet"] = {w: gop([c for c in cau if c["r"]["nguoi"] == w]) for w in sorted({r["nguoi"] for r in ok})}
    vet_n, vet_cx = sum(r["vet_n"] for r in ok), sum(r["vet_gan_co"] for r in ok)
    out["vet"] = {"n": vet_n, "gan_co": vet_cx, "ti_le_gan_co": vet_cx / vet_n if vet_n else None,
                  "ci95_gan_co": H.cp_khoang(vet_cx, vet_n) if vet_n else None, "bo_sot_chi_bao": sum(r["vet_bo_sot"] for r in ok),
                  "doc_thanh_dap_an_chac_LOI_NANG": sum(r["vet_doc_dap_an_chac"] for r in ok)}
    p0107 = [r for r in ok if r["phieu"] == 107]
    out["phieu_0107_sbd_can_xem"] = {r["anh"]: bool(r["sbd_can_xem"]) for r in p0107}
    return out


def dat_bat_buoc(s: dict, rows: list[dict]) -> dict:
    h = H.dat_bat_buoc(s)
    h["H1"] = "chờ kết luận mắt (xem mù); nhất quán Tuần 4 không áp dụng (đợt 2 chưa có số tham chiếu)"
    ok = [r for r in rows if r["status_tai"] != "rejected"]
    h["H3_0107_thieu_bubble_phai_can_xem"] = all(r["sbd_can_xem"] for r in ok if r["phieu"] == 107)
    h["H3"] = bool(h["H3"] and h["H3_0107_thieu_bubble_phai_can_xem"])
    h["H2"] = bool(h["H2"] and sum(r["vet_doc_dap_an_chac"] for r in ok) == 0)
    return h


def ca_thu(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        if r["status_tai"] == "rejected":
            continue
        for tr in r["can_xem_cot_khong_to"]:
            f_cx = r["sbd_can_xem"] if tr == "sbd" else r["ma_can_xem"]
            ly = r["sbd_ly_do"] if tr == "sbd" else r["ma_ly_do"]
            out.append(f"{r['anh']}: cột {tr} KHÔNG tô bubble → trường {'CẦN XEM' if f_cx else 'ĐƯỢC NHẬN (VI PHẠM H3)'} {ly}")
        for c in r["cau"]:
            if c["that"] == "vet":
                out.append(f"{r['anh']} câu {c['n']}: vết {c['nhan']} → máy {c['doc']} '{c['doc_o'] or '-'}', cần xem {c['cx']} {c['ly_do']}")
    return out


# ------------------------------------------------------------------------------------------------ chốt chặn đăng ký
def kiem_dang_ky(dang_ky: Path = DANG_KY, goc: Path = ROOT.parent) -> dict:
    """Từ chối nếu: chưa có bản đăng ký; mã khoá (cv_engine / models / backend / answer_sheet/output) khác commit khoá hoặc có sửa chưa commit;
    SHA file khác đăng ký; có nhãn đã sửa mà chưa có đăng ký bổ sung khớp SHA."""
    if not dang_ky.exists():
        raise SystemExit(f"DỪNG: chưa có bản đăng ký trước {dang_ky} – đợt 2 chỉ chạy sau đăng ký (docs/ke_hoach_test_dot2.md).")
    d = json.loads(dang_ky.read_text(encoding="utf-8"))
    ma = d["ma_commit"]
    chinh = subprocess.run(["git", "diff", "--stat", ma, "HEAD", "--", *DUONG_DAN_MA], cwd=goc, capture_output=True, text=True, encoding="utf-8")
    if chinh.returncode != 0 or chinh.stdout.strip():
        raise SystemExit(f"DỪNG: mã khoá khác commit {ma[:8]} (git diff không rỗng):\n{chinh.stdout or chinh.stderr}")
    ban = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", *DUONG_DAN_MA], cwd=goc, capture_output=True, text=True, encoding="utf-8")
    if ban.stdout.strip():
        raise SystemExit(f"DỪNG: mã có thay đổi chưa commit:\n{ban.stdout}")
    sai = [f for f, h in d["sha256"].items() if H.sha_file(goc / f) != h]
    if sai:
        raise SystemExit(f"DỪNG: SHA-256 khác bản đăng ký: {sai}")
    if GT_SUA.exists() or CELL_SUA.exists():
        bs = d.get("bo_sung", {})
        for p in (GT_SUA, CELL_SUA, SUA_NHAN):
            if not p.exists() or bs.get(p.name) != H.sha_file(p):
                raise SystemExit(f"DỪNG: nhãn đã sửa {p.name} chưa có trong đăng ký bổ sung (hoặc SHA khác) – ghi vào 'bo_sung' TRƯỚC khi chạy.")
    return d


# ------------------------------------------------------------------------------------------------ chạy
def chay(thu_muc: Path, xem: bool, co_chu_so: bool, tien_do=print, danh_sach: list[str] | None = None, nhan: dict | None = None) -> dict:
    nhan = nhan or doc_nhan()
    ds = danh_sach or ten_anh(nhan)
    thieu = [t for t in ds if not (thu_muc / f"{t}.jpg").exists()]
    if thieu:
        raise SystemExit(f"DỪNG: thiếu {len(thieu)} ảnh trong {thu_muc}: {thieu[:5]}…")
    with H.phien() as (client, conn):
        a, dap_an = H.tao_ky_thi(client, "Đánh giá đợt 2 A")
        b, _ = H.tao_ky_thi(client, "Đánh giá đợt 2 B")
        da, rows = set(), []
        for ten in ds:
            ms = ten.split("_")[0]
            eid = b if ms in da else a
            da.add(ms)
            rows.append(chay_phieu(client, conn, eid, dap_an, ten, thu_muc, nhan, xem, co_chu_so))
            r = rows[-1]
            tien_do(f"{ten}: {r['status_tai']} → {r.get('status_cuoi', r['status_tai'])}, cần xem {r['cx_cau']}, nặng {r['nang_cau'] + r['nang_cot']}, "
                    f"vết gắn cờ {r['vet_gan_co']}/{r['vet_n']}, SBD {'cần xem' if r['sbd_can_xem'] else 'nhận'}, mã đề {'cần xem' if r['ma_can_xem'] else 'nhận'}")
    return {"rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["run", "kiem-nhan", "tao-gia", "ap-dung-sua"])
    ap.add_argument("--xac-nhan-dot2", action="store_true")
    ap.add_argument("--thu-gia", action="store_true")
    ap.add_argument("--xem", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.lenh == "kiem-nhan":
        n = doc_nhan()
        print(f"Nhãn đợt 2 khớp: {len(n)} phiếu, nguồn {nguon_nhan()[0].name}")
        return
    if a.lenh == "tao-gia":
        return tao_gia()
    if a.lenh == "ap-dung-sua":
        return ap_dung_sua()
    if a.thu_gia == a.xac_nhan_dot2:
        sys.exit("TỪ CHỐI: chọn đúng một: --thu-gia (ảnh giả hoá, thử công cụ) hoặc --xac-nhan-dot2 (đợt 2 thật, một lần, sau đăng ký).")
    assert not (set(PHIEU_DOT2) & (set(PHIEU_TRAIN) | set(PHIEU_VAL) | set(PHIEU_TEST)))
    OUT.mkdir(parents=True, exist_ok=True)
    if a.thu_gia:
        thu_muc, d, co_chu_so = THU_GIA, THU_GIA / "ket_qua", False
    else:
        thu_muc, d, co_chu_so = RAW_DOT2, OUT / "that", True
        if KHOA.exists():
            sys.exit(f"TỪ CHỐI: đợt 2 đã chạy (hoặc đã bắt đầu) – {KHOA.read_text(encoding='utf-8')}. Không chạy lại (docs/ke_hoach_test_dot2.md).")
        kiem_dang_ky()
        nhan = doc_nhan()
        thieu = [t for t in ten_anh(nhan) if not (RAW_DOT2 / f"{t}.jpg").exists()]
        if thieu:
            sys.exit(f"DỪNG (chưa tạo khoá): thiếu {len(thieu)} ảnh trong {RAW_DOT2}: {thieu[:5]}…")
        KHOA.write_text(f"bắt đầu {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    kq = chay(thu_muc, a.xem, co_chu_so)
    rows = kq["rows"]
    s = H.tom_tat(rows)
    d.mkdir(parents=True, exist_ok=True)
    if a.xem:
        (d / "xem_mu.html").write_text(H.html_trang(rows, False), encoding="utf-8")
        (d / "xem_may.html").write_text(H.html_trang(rows, True), encoding="utf-8")
    for r in rows:
        for k in [k for k in r if k.startswith("_")]:
            r.pop(k)
    res = {"che_do": "thu_gia" if a.thu_gia else "dot2_that", "tom_tat": s, "dat_bat_buoc": dat_bat_buoc(s, rows), "phan_tich": phan_tich(rows),
           "ca_thu": ca_thu(rows), "anh": rows}
    (d / "ket_qua.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "anh"}, ensure_ascii=False, indent=1, default=str))
    if not a.thu_gia:
        KHOA.write_text(f"đã chạy xong {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    ok = res["dat_bat_buoc"]
    sys.exit(0 if all(ok[k] is True for k in ("H2", "H3", "H4", "H5")) else 1)


if __name__ == "__main__":
    main()
