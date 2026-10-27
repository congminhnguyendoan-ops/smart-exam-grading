"""
thu_bo_demo.py - Chạy thử ĐẦU-CUỐI 10 phiếu demo bảo vệ BV01–BV10 trên 2 kỳ thi [DEMO-BV] đã nạp (tools/nap_bo_demo.py --ap-dung),
bằng ẢNH GIẢ HOÁ vẽ theo kịch bản. KHÔNG GHI THẬT: mọi yêu cầu API dùng chung MỘT kết nối, cuối cùng ROLLBACK; ảnh lưu vào thư mục tạm.

Độc lập với mã được chấm: chỉ đi qua API công khai (TestClient, AUTH_MODE=on, token của gv_an / gv_binh dựng từ hash trong CSDL);
không import cv_engine.omr / ocr / backend.service / grading. Điểm mong đợi + câu đúng lấy từ kịch bản (tools/kiem_bo_demo.py).
Ảnh giả hoá (cùng quy ước eval_dot2.py tao-gia): mẫu phiếu trắng, ô đậm xám 30, ô mờ xám 170 (BV07 "tô nhạt cả tờ": xám 150), bubble SBD /
mã đề đậm; KHÔNG vẽ chữ viết tay (ô viết tay trống → SBD / mã đề chỉ "chắc" khi có trong danh sách kỳ thi). Ảnh vẽ phẳng: CHỈ minh hoạ luồng,
không phải số đo độ chính xác.

  python tools/thu_bo_demo.py tao-anh     # 10 ảnh -> data/_eval/demo_bv/gia/BVxx.jpg
  python tools/thu_bo_demo.py chay        # chấm + giáo viên duyệt đúng như kịch bản, ROLLBACK -> data/_eval/demo_bv/ket_qua_thu.{md,json}
"""
import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["AUTH_MODE"] = "on"                     # kiểm cả phân quyền: mỗi kỳ thi do đúng giáo viên của lớp chấm

import kiem_bo_demo as K  # noqa: E402

OUT = ROOT / "data" / "_eval" / "demo_bv"
GIA = OUT / "gia"
LAYOUT = ROOT / "answer_sheet" / "output" / "layout.json"
MAU_PNG = ROOT / "answer_sheet" / "output" / "phieu_trang_300dpi.png"
XAM = {"dam": 30, "mo": 170, "mo_nhat_ca_to": 150}
NHAT_CA_TO = {"BV07"}
NHAN = "[DEMO-BV]"


def kich_ban() -> tuple[dict, dict]:
    """({BVxx: dòng kịch bản}, {(exam, mã đề): đáp án}); kịch bản sai thì DỪNG."""
    loi, _ = K.kiem(K.doc(K.DAP_AN), K.doc(K.KICH_BAN))
    if loi:
        raise SystemExit("DỪNG: kịch bản demo sai – chạy python tools/kiem_bo_demo.py")
    return {p["sheet_id"]: p for p in K.doc(K.KICH_BAN)}, {(r["exam"], r["exam_code"]): r for r in K.doc(K.DAP_AN)}


def tao_anh() -> None:
    import cv2
    import numpy as np
    L = json.loads(LAYOUT.read_text(encoding="utf-8"))
    mau = cv2.imdecode(np.fromfile(MAU_PNG, np.uint8), cv2.IMREAD_GRAYSCALE)
    ans, R = L["answers"], L["answers"]["bubble_radius"]
    GIA.mkdir(parents=True, exist_ok=True)

    def cham(anh, c, r, g):
        cv2.circle(anh, (int(round(c[0])), int(round(c[1]))), int(round(r)), int(g), -1)
    for ma, p in kich_ban()[0].items():
        anh = mau.copy()
        for q in range(1, K.SO_CAU + 1):
            lab = p[f"q{q}"]
            for ch in ("" if lab == "-" else lab):
                g = XAM["dam"] if ch.isupper() else XAM["mo_nhat_ca_to" if ma in NHAT_CA_TO else "mo"]
                cham(anh, ans["centers"][str(q)][ch.upper()], 0.85 * R, g)
        for key, so in (("sbd", p["sbd"]), ("exam_code", p["exam_code"])):
            for i, ch in enumerate(so):
                cham(anh, L[key]["bubbles"][i][int(ch)], 0.85 * L[key]["bubble_radius"], XAM["dam"])
        cv2.imencode(".jpg", anh, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(GIA / f"{ma}.jpg")
    print(f"Đã ghi 10 ảnh giả hoá ở {GIA}")


def chay() -> list[dict]:
    from fastapi.testclient import TestClient

    from backend import auth
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    from backend.main import app, get_cau_hinh, get_conn
    kb, dap_an = kich_ban()
    if not all((GIA / f"{m}.jpg").exists() for m in kb):
        tao_anh()
    cfg = replace(lay_cau_hinh(), storage_dir=Path(tempfile.mkdtemp(prefix="kho_demo_bv_")))
    conn = ket_noi()
    rows = []
    try:
        from backend import migrate
        thieu = migrate.chua_ap(conn)
        if thieu:                                                  # chỉ KIỂM, không áp (quy tắc: công cụ / test không áp migration lên CSDL thật)
            raise SystemExit(f"DỪNG: migration chưa áp {sorted(thieu)} – chạy python -m backend.migrate (người dùng quyết).")
        ky_thi = {}
        for e in ("E1", "E2"):
            r0 = next(r for (ee, _), r in dap_an.items() if ee == e)
            x = conn.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (r0["exam_title"],)).fetchall()
            if len(x) != 1:
                raise SystemExit(f"DỪNG: cần đúng 1 kỳ thi '{r0['exam_title']}' (có {len(x)}) – chạy tools/nap_bo_demo.py --ap-dung trước.")
            u = conn.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (r0["teacher"],)).fetchone()
            ky_thi[e] = (x[0]["exam_id"], {"Authorization": "Bearer " + auth.tao_token(cfg.auth_secret, u["user_id"], u["password_hash"], 1)})

        def _conn():
            yield conn
        app.dependency_overrides[get_conn] = _conn
        app.dependency_overrides[get_cau_hinh] = lambda: cfg
        with TestClient(app) as cl:
            for ma, p in kb.items():
                eid, h = ky_thi[p["exam"]]
                key = dap_an[(p["exam"], p["exam_code"])]["answers"]
                r = cl.post(f"/exams/{eid}/sheets", headers=h, files={"file": (f"{ma}.jpg", (GIA / f"{ma}.jpg").read_bytes(), "image/jpeg")})
                assert r.status_code == 201, r.text
                sid = r.json()["sheet_id"]
                v = cl.get(f"/sheets/{sid}", headers=h).json()
                row = {"phieu": ma, "sbd": p["sbd"], "ky_thi": p["exam"], "ma_de": p["exam_code"], "ghi_chu": p["ghi_chu"],
                       "trang_thai_tai": v["status"], "diem_mong_doi": str(Decimal(p["diem_mong_doi"]))}
                if v["status"] == "rejected":
                    rows.append(row | {"tu_choi": v.get("reject_code")})
                    continue
                cx = [q for q in v["questions"] if q["needs_review"]]
                sai_khong_co = [q["question_no"] for q in v["questions"] if not q["needs_review"] and q["is_correct"] is not None
                                and q["is_correct"] != K.dung(p[f"q{q['question_no']}"], key[q["question_no"] - 1])]
                ly_do_cau = sorted({x for q in cx for x in q["reasons"]})
                row |= {"diem_tam": str(v["score"]["provisional"]), "toi_da_co_the": str(v["score"]["max_possible"]),
                        "cau_can_xem": [q["question_no"] for q in cx], "ly_do_cau": ly_do_cau,
                        "sbd_doc": v["sbd"]["detected"], "sbd_can_xem": bool(v["sbd"]["can_xem"]), "sbd_ly_do": list(v["sbd"]["reasons"]),
                        "ma_de_doc": v["exam_code"]["detected"], "ma_de_can_xem": bool(v["exam_code"]["can_xem"]),
                        "cham_sai_khong_co": sai_khong_co}
                # giáo viên duyệt ĐÚNG NHƯ GIẤY (kịch bản): câu cần xem -> đặt tập ô đã tô; SBD / mã đề -> nhập đúng
                for q in cl.get(f"/sheets/{sid}/review-questions", headers=h).json():
                    lab = p[f"q{q['question_no']}"]
                    rr = cl.post(f"/sheets/{sid}/questions/{q['question_no']}/review", headers=h,
                                 json={"action": "set", "selected_options": "" if lab == "-" else "".join(sorted(lab.upper()))})
                    assert rr.status_code == 200, rr.text
                v2 = cl.get(f"/sheets/{sid}", headers=h).json()
                if v2["status"] == "needs_review":
                    rr = cl.put(f"/sheets/{sid}/identity", headers=h, json={"sbd": p["sbd"], "exam_code": p["exam_code"]})
                    row["sua_dinh_danh"] = f"{rr.status_code} {rr.json().get('detail', '') if rr.status_code != 200 else ''}".strip()
                    if rr.status_code == 200:
                        v2 = rr.json()
                sc = v2["score"]
                row |= {"trang_thai_cuoi": v2["status"], "result_status": sc.get("result_status"),
                        "diem_chinh_thuc": None if sc.get("official") is None else str(sc["official"]),
                        "diem_tam_sau_duyet": str(sc["provisional"]), "ly_do_con_lai": list((v2.get("review") or {}).get("reasons") or [])
                        if v2["status"] == "needs_review" else [], "sv_cuoi": (v2.get("student") or {}).get("student_code")}
                # Kỳ vọng theo danh sách dự thi THẬT trong CSDL: trong danh sách -> điểm chính thức = điểm mong đợi;
                # ngoài danh sách (BV10) -> KHÔNG có điểm chính thức, phiếu còn chờ vì sbd_not_found, điểm tạm sau duyệt = điểm mong đợi.
                row["trong_ds"] = conn.execute("SELECT 1 FROM exam_students es JOIN students s USING (student_id) WHERE es.exam_id = %s "
                                               "AND s.student_code = %s", (eid, p["sbd"])).fetchone() is not None
                if row["trong_ds"]:
                    row["ky_vong"] = f"chính thức {row['diem_mong_doi']}"
                    row["khop"] = row["diem_chinh_thuc"] is not None and Decimal(row["diem_chinh_thuc"]) == Decimal(p["diem_mong_doi"]) \
                        and row["sv_cuoi"] == p["sbd"]
                else:
                    row["ky_vong"] = f"KHÔNG ghi điểm (SBD ngoài danh sách); tạm {row['diem_mong_doi']}"
                    row["khop"] = row["diem_chinh_thuc"] is None and v2["status"] == "needs_review" and "sbd_not_found" in row["ly_do_con_lai"] \
                        and Decimal(row["diem_tam_sau_duyet"]) == Decimal(p["diem_mong_doi"])
                rows.append(row)
                print(f"{ma}: {v['status']} → {v2['status']}, tạm {row['diem_tam']} → {row['diem_tam_sau_duyet']}, cần xem {len(cx)} câu, "
                      f"chính thức {row['diem_chinh_thuc']}, kỳ vọng {row['ky_vong']}, {'KHỚP' if row['khop'] else 'KHÔNG KHỚP'}")
    finally:
        app.dependency_overrides.clear()
        conn.rollback()                                            # KHÔNG ghi thật
        conn.close()
    return rows


def ghi_bao_cao(rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ket_qua_thu.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    d = ["| Phiếu | SBD | Kỳ thi / mã đề | Sau tải | Điểm tạm | Câu cần xem | SBD / mã đề | Sau duyệt | Mong đợi | Khớp |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["trang_thai_tai"] == "rejected":
            d.append(f"| {r['phieu']} | {r['sbd']} | {r['ky_thi']}/{r['ma_de']} | từ chối `{r['tu_choi']}` | – | – | – | – | {r['diem_mong_doi']} | ✗ |")
            continue
        cx = r["cau_can_xem"]
        cau = f"{len(cx)}" + ("" if not cx else f" (cả 40; {', '.join(r['ly_do_cau'])})" if len(cx) == K.SO_CAU
                              else f" ({', '.join(map(str, cx))}; {', '.join(r['ly_do_cau'])})")
        dd = ("SBD cần xem " + ",".join(r["sbd_ly_do"]) if r["sbd_can_xem"] else "SBD chắc") + " · " + ("mã đề cần xem" if r["ma_de_can_xem"] else "mã đề chắc")
        sau = (f"chính thức {r['diem_chinh_thuc']} ({r['result_status']})" if r["diem_chinh_thuc"] is not None
               else f"KHÔNG ghi điểm, chờ `{','.join(r['ly_do_con_lai'])}` (tạm {r['diem_tam_sau_duyet']})")
        d.append(f"| {r['phieu']} | {r['sbd']} | {r['ky_thi']}/{r['ma_de']} | {r['trang_thai_tai']} | {r['diem_tam']} | {cau} | {dd} | "
                 f"{sau} | {r['ky_vong']} | {'✓' if r['khop'] else '✗'} |")
    n = sum(bool(r.get("khop")) for r in rows)
    sai = sum(len(r.get("cham_sai_khong_co", [])) for r in rows)
    d += ["", f"Khớp {n}/{len(rows)} · câu chấm sai mà không gắn cần xem: {sai} · ROLLBACK (không ghi CSDL).",
          "Ảnh giả hoá vẽ phẳng, không chữ viết tay: CHỈ minh hoạ luồng, không phải số đo độ chính xác."]
    (OUT / "ket_qua_thu.md").write_text("\n".join(d) + "\n", encoding="utf-8")
    print("\n" + "\n".join(d))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["tao-anh", "chay"])
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.lenh == "tao-anh":
        tao_anh()
        return 0
    rows = chay()
    ghi_bao_cao(rows)
    return 0 if all(r.get("khop") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
