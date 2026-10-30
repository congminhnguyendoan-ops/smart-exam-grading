"""
eval_h3_mo_phong.py - Lệnh T (30/10/2026): đánh giá MỘT LẦN phép thử mô phỏng H3 "ô tô trống, chữ viết tay có" (docs/dang_ky_h3_mo_phong.md).

  python tools/eval_h3_mo_phong.py dien-tap [--bien-the hang|cot]   # DIỄN TẬP trên ảnh dev (tools/h3_mo_phong.py dien-tap trước); không khoá
  python tools/eval_h3_mo_phong.py run --xac-nhan-h3                # CHÍNH THỨC: MỘT LẦN, sau đăng ký + tag dang-ky-h3-mo-phong
  python tools/eval_h3_mo_phong.py bao-cao                          # data/_eval/h3/ket_qua.json -> docs/ket_qua_h3_mo_phong.{json,md}

Cùng khuôn eval_dot2.py: chỉ đi qua API công khai (TestClient, CSDL thật trong giao dịch ROLLBACK, kho ảnh tạm); KHÔNG import cv_engine.omr / ocr /
backend.service. Chỉ IMPORT eval_dot2 / eval_he_thong / h3_mo_phong (không sửa). Ảnh đợt 2 chỉ được đọc (SHA kiểm theo docs/sha_anh_dot2.txt).
T1: trường bị xoá bubble mà hệ thống NHẬN (không cần xem) = 0 (ảnh bị từ chối khi nắn tính riêng).
T2: phiếu tự chốt sai hoặc điểm chính thức sai sau giáo viên oracle (chốt câu theo nhãn, SBD / mã đề theo chữ viết tay đúng) = 0.
T3 (đối chứng): trường KHÔNG sửa giống kết quả đợt 2 (data/_eval/dot2/that/ket_qua.json): từng cột (bubble, chữ số CNN, cần xem, lý do) + cần xem
và lý do của trường. KT0 (kiểm công cụ, không phải tiêu chí): ảnh gốc lưu PNG không mất mát, KHÔNG sửa, cho cả hai trường giống đợt 2.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import eval_he_thong as H  # noqa: E402  (đặt AUTH_MODE=demo; phiên TestClient ROLLBACK, tạo kỳ thi, dung_that)
import eval_dot2 as E  # noqa: E402  (nhãn đợt 2, tap_chon, thứ tự ảnh – CHỈ import, không sửa)
import h3_mo_phong as M  # noqa: E402

OUT = M.OUT_EVAL
KHOA = OUT / "da_chay.lock"
KQ = OUT / "ket_qua.json"
DANG_KY = ROOT / "docs" / "dang_ky_h3_mo_phong.json"
DOCS_KQ_JSON, DOCS_KQ_MD = ROOT / "docs" / "ket_qua_h3_mo_phong.json", ROOT / "docs" / "ket_qua_h3_mo_phong.md"
DUONG_DAN_MA = ["smart_exam_db/cv_engine", "smart_exam_db/models", "smart_exam_db/backend", "smart_exam_db/answer_sheet/output"]
CONG_CU = ["smart_exam_db/tools/h3_mo_phong.py", "smart_exam_db/tools/eval_h3_mo_phong.py"]
LY_DO = {"lech_bubble": "chữ viết tay khác chữ số bubble", "tin_cay_thap": "chữ viết tay khó đọc (máy chưa chắc)",
         "thieu_bubble": "cột bubble không đọc được (không tô / tô nhiều ô)", "bubble_cx": "cột bubble máy chưa chắc",
         "o_trong_ngoai_ds": "ô viết tay trống và số này không có trong danh sách", "o_trong_chua_biet_ds": "ô viết tay trống, chưa kiểm được danh sách",
         "o_it_muc": "ô viết tay quá ít mực", "khong_phai_chu_so": "ô viết tay không giống chữ số"}


def sha_hoa(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


# ------------------------------------------------------------------------------------------------ chuẩn hoá trường để so sánh
def truong_api(v: dict, truong: str) -> dict:
    f = v["sbd"] if truong == "sbd" else v["exam_code"]
    return {"can_xem": bool(f["can_xem"]), "ly_do": sorted(f["reasons"]), "detected": f["detected"],
            "cot": [{"i": c["vi_tri"] - 1 if "vi_tri" in c else k, "bubble": c["bubble"], "may": c["handwriting"]["chu_so"],
                     "p": c["handwriting"]["p"], "cx": bool(c["can_xem"]), "ly_do": sorted(c["ly_do"])} for k, c in enumerate(f["columns"])]}


def truong_dot2(r: dict, truong: str) -> dict:
    k = "sbd" if truong == "sbd" else "ma"
    return {"can_xem": bool(r[f"{k}_can_xem"]), "ly_do": sorted(r[f"{k}_ly_do"]),
            "cot": [{"i": c["i"], "bubble": c["bubble"], "may": c["may"], "cx": bool(c["cx"]), "ly_do": sorted(c["ly_do"])}
                    for c in r["cot"] if c["truong"] == truong]}


def chu_ky(f: dict) -> tuple:
    """Phần dùng để so T3 / KT0: cần xem + lý do của trường, từng cột (bubble, chữ số CNN, cần xem, lý do). Không so p (số thực)."""
    return (f["can_xem"], tuple(f["ly_do"]), tuple((c["bubble"], c["may"], c["cx"], tuple(c["ly_do"])) for c in f["cot"]))


# ------------------------------------------------------------------------------------------------ một ảnh qua API
def tai(client, conn, eid: int, dap_an: dict, png: Path, t: dict, oracle: bool) -> dict:
    key = dap_an[t["ma_de"]]
    diem_that = H.DIEM_CAU * sum(H.dung_that(t["q"][q], key[q - 1]) for q in range(1, 41))
    conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV H3') ON CONFLICT DO NOTHING", (t["sbd"],))
    r = client.post(f"/exams/{eid}/sheets", files={"file": (png.name, png.read_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    sid = r.json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    out = {"sheet_id": sid, "status_tai": v["status"], "tu_choi": v.get("reject_code") or "", "diem_that": float(diem_that)}
    if v["status"] == "rejected":
        return out
    out["truong"] = {tr: truong_api(v, tr) for tr in ("sbd", "exam_code")}
    sc = v["score"]
    out["tu_chot"] = v["status"] == "graded"
    out["tu_chot_sai"] = bool(out["tu_chot"] and (H.Decimal(str(sc["official"])) != diem_that or (v["student"] or {}).get("student_code") != t["sbd"]))
    if not oracle:
        return out
    if v["status"] != "graded":                                 # giáo viên oracle: câu theo nhãn; SBD / mã đề theo chữ viết tay đúng
        for c in client.get(f"/sheets/{sid}/review-questions").json():
            rr = client.post(f"/sheets/{sid}/questions/{c['question_no']}/review", json={"action": "set", "selected_options": E.tap_chon(t["q"][c["question_no"]])})
            assert rr.status_code == 200, rr.text
        v = client.get(f"/sheets/{sid}").json()
        if v["status"] == "needs_review":
            rr = client.put(f"/sheets/{sid}/identity", json={"sbd": t["sbd"], "exam_code": t["ma_de"]})
            assert rr.status_code == 200, rr.text
            v = rr.json()
    out["status_cuoi"] = v["status"]
    out["diem_chinh_thuc"] = None if v["score"]["official"] is None else float(v["score"]["official"])
    out["chinh_thuc_dung"] = bool(v["status"] == "graded" and H.Decimal(str(v["score"]["official"])) == diem_that
                                  and (v["student"] or {}).get("student_code") == t["sbd"])
    return out


def danh_gia_ca(dong: dict, kq: dict, ref: dict | None) -> dict:
    """Một ca: dòng bảng tạo ảnh + kết quả API (+ trường tham chiếu chuẩn hoá) -> bản ghi T1–T3."""
    ca = {k: dong.get(k) for k in ("anh", "truong", "cot", "chu_so_xoa", "bien_the", "o_nguon", "truong_da_can_xem_o_dot2", "sha_anh_chinh",
                                   "do_toi_truoc", "do_toi_sau", "do_toi_o_trong_cot_trung_vi")}
    ca.update({k: kq[k] for k in ("sheet_id", "status_tai", "tu_choi")})
    if kq["status_tai"] == "rejected":
        ca["ket_luan"] = "bị từ chối khi nắn (tính riêng, không phải 'nhận')"
        return ca
    f = kq["truong"][dong["truong"]]
    c = f["cot"][dong["cot"] - 1]
    khac = "exam_code" if dong["truong"] == "sbd" else "sbd"
    ca.update({"kenh_bubble": c["bubble"], "kenh_cnn": c["may"], "p_cnn": c["p"], "cot_can_xem": c["cx"], "cot_ly_do": c["ly_do"],
               "truong_can_xem": f["can_xem"], "truong_ly_do": f["ly_do"], "ly_do_hien_thi": [LY_DO.get(x, x) for x in f["ly_do"]],
               "truong_detected": f["detected"], "status_cuoi": kq.get("status_cuoi"), "diem_chinh_thuc": kq.get("diem_chinh_thuc"),
               "diem_that": kq["diem_that"], "T1_nhan": not f["can_xem"], "T2_vi_pham": bool(kq["tu_chot_sai"] or kq.get("chinh_thuc_dung") is False),
               "tu_chot": kq["tu_chot"]})
    if ref is not None:
        ca["T3_khop"] = chu_ky(kq["truong"][khac]) == chu_ky(ref[khac])
        if not ca["T3_khop"]:
            ca["T3_khac"] = {"anh_chinh": kq["truong"][khac], "tham_chieu": ref[khac]}
    return ca


def tong(ca: list[dict], kt0: list[dict] | None) -> dict:
    ok = [c for c in ca if c["status_tai"] != "rejected"]
    t3 = [c for c in ok if "T3_khop" in c]
    s = {"n": len(ca), "bi_tu_choi": len(ca) - len(ok), "T1_nhan": sum(c["T1_nhan"] for c in ok), "T1_can_xem": sum(not c["T1_nhan"] for c in ok),
         "T2_vi_pham": sum(c["T2_vi_pham"] for c in ok), "tu_chot": sum(c["tu_chot"] for c in ok),
         "T3_khop": sum(c["T3_khop"] for c in t3), "T3_n": len(t3)}
    s["dat"] = {"T1": s["T1_nhan"] == 0, "T2": s["T2_vi_pham"] == 0, "T3_du_doan_ge_19": s["T3_khop"] >= 19 if s["T3_n"] == 20 else None}
    if kt0 is not None:
        s["KT0_khop"], s["KT0_n"] = sum(k["khop"] for k in kt0), len(kt0)
    return s


# ------------------------------------------------------------------------------------------------ diễn tập (dev)
def dien_tap(bien_the: str) -> dict:
    """Ảnh dev đã chỉnh (h3_mo_phong dien-tap) + ảnh gốc PNG không sửa làm tham chiếu T3 (dev không có kết quả đợt 2). Không khoá."""
    from cv_engine.preprocessing import doc_anh
    from cv_engine.tap_du_lieu import PHIEU_TRAIN
    nhan = H.doc_nhan(PHIEU_TRAIN)
    thu = M.DIEN_TAP / bien_the
    bang = json.loads((thu / "bang.json").read_text(encoding="utf-8"))
    goc = M.DIEN_TAP / "goc_png"
    ca = []
    with H.phien() as (client, conn):
        for dong in bang:
            t = nhan[dong["anh"].split("_")[0]]
            p0 = goc / f"{dong['anh']}.png"
            M.ghi_png(doc_anh(M.RAW_DEV / dong["anh_goc"])[0], p0)
            e1, da = H.tao_ky_thi(client, f"H3 dien tap {dong['anh']} 1")
            e2, _ = H.tao_ky_thi(client, f"H3 dien tap {dong['anh']} 2")
            ref = tai(client, conn, e2, da, p0, t, False)
            kq = tai(client, conn, e1, da, thu / f"{dong['anh']}.png", t, True)
            ca.append(danh_gia_ca(dong, kq, ref.get("truong")))
    res = {"che_do": f"dien_tap_dev_{bien_the}", "tom_tat": tong(ca, None), "ca": ca}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"dien_tap_{bien_the}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


# ------------------------------------------------------------------------------------------------ chính thức
def kiem_dang_ky(goc: Path = ROOT.parent) -> dict:
    if not DANG_KY.exists():
        raise SystemExit(f"DỪNG: chưa có bản đăng ký {DANG_KY}.")
    d = json.loads(DANG_KY.read_text(encoding="utf-8"))
    for lenh, ten in ((["git", "diff", "--stat", d["ma_commit_kiem"], "HEAD", "--", *DUONG_DAN_MA], "mã được kiểm khác commit đăng ký"),
                      (["git", "status", "--porcelain", "--untracked-files=no", "--", *DUONG_DAN_MA, *CONG_CU], "có thay đổi chưa commit")):
        r = subprocess.run(lenh, cwd=goc, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0 or r.stdout.strip():
            raise SystemExit(f"DỪNG: {ten}:\n{r.stdout or r.stderr}")
    sai = [f for f, h in d["sha256_tep"].items() if sha_hoa(goc / f) != h]
    if sai:
        raise SystemExit(f"DỪNG: SHA-256 khác bản đăng ký: {sai}")
    anh = M.kiem_sha_dot2()
    if anh != d["sha256_anh_goc"]:
        raise SystemExit("DỪNG: SHA ảnh gốc đợt 2 khác bản đăng ký.")
    return d


def chay_chinh_thuc() -> dict:
    from cv_engine.preprocessing import doc_anh
    if KHOA.exists():
        raise SystemExit(f"TỪ CHỐI: phép thử H3 mô phỏng đã chạy (hoặc đã bắt đầu) – {KHOA.read_text(encoding='utf-8')}. Không chạy lại.")
    d = kiem_dang_ky()
    nhan = E.doc_nhan()
    ref_rows = {r["anh"]: r for r in json.loads(M.KQ_DOT2.read_text(encoding="utf-8"))["anh"]}
    ds = E.ten_anh(nhan)
    OUT.mkdir(parents=True, exist_ok=True)
    KHOA.write_text(f"bắt đầu {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    bang = M.tao(ds, M.RAW_DOT2, nhan, ref_rows, d["bien_the"], d["chi_truong_nhan"], M.OUT_DOT2)
    by = {b["anh"]: b for b in bang}
    goc = M.OUT_DOT2 / "goc_png"
    ca, kt0 = [], []
    with H.phien() as (client, conn):
        a, dap_an = H.tao_ky_thi(client, "H3 mo phong A")
        b, _ = H.tao_ky_thi(client, "H3 mo phong B")
        c0, _ = H.tao_ky_thi(client, "H3 doi chung C")
        d0, _ = H.tao_ky_thi(client, "H3 doi chung D")
        da = set()
        for ten in ds:                                          # cùng thứ tự + cùng cách chia kỳ thi A/B như đợt 2
            ms = ten.split("_")[0]
            lan2 = ms in da
            da.add(ms)
            t, dong, ref = nhan[ms], by[ten], {tr: truong_dot2(ref_rows[ten], tr) for tr in ("sbd", "exam_code")}
            if "sha_anh_chinh" not in dong:
                ca.append({**dong, "status_tai": "rejected", "tu_choi": "khi_tao", "sheet_id": None})
                continue
            kq = tai(client, conn, b if lan2 else a, dap_an, M.OUT_DOT2 / f"{ten}.png", t, True)
            ca.append(danh_gia_ca(dong, kq, ref))
            if d.get("kt0", True):
                p0 = goc / f"{ten}.png"
                M.ghi_png(doc_anh(M.RAW_DOT2 / dong["anh_goc"])[0], p0)
                k0 = tai(client, conn, d0 if lan2 else c0, dap_an, p0, t, False)
                kt0.append({"anh": ten, "khop": k0["status_tai"] != "rejected" and all(chu_ky(k0["truong"][tr]) == chu_ky(ref[tr]) for tr in ("sbd", "exam_code"))})
            x = ca[-1]
            print(f"{ten}: {x['truong']} cột {x['cot']} (xoá {x['chu_so_xoa']}) -> bubble '{x.get('kenh_bubble')}', CNN '{x.get('kenh_cnn')}', "
                  f"trường {'CẦN XEM' if x.get('truong_can_xem') else 'NHẬN'} {x.get('truong_ly_do')}, T3 {x.get('T3_khop')}, KT0 {kt0[-1]['khop'] if kt0 else '-'}")
    res = {"che_do": "chinh_thuc", "dang_ky": {"tag": d.get("tag"), "ma_commit_kiem": d["ma_commit_kiem"], "bien_the": d["bien_the"],
                                               "chi_truong_nhan": d["chi_truong_nhan"]},
           "thoi_gian": time.strftime("%Y-%m-%d %H:%M:%S"), "tom_tat": tong(ca, kt0 if d.get("kt0", True) else None), "ca": ca, "kt0": kt0}
    KQ.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    KHOA.write_text(f"đã chạy xong {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
    return res


def bao_cao() -> None:
    """data/_eval/h3/ket_qua.json -> docs/ket_qua_h3_mo_phong.json (bản sao + SHA nguồn) và .md (bảng 20 ca, T1–T3, Giới hạn)."""
    res = json.loads(KQ.read_text(encoding="utf-8"))
    s = res["tom_tat"]
    DOCS_KQ_JSON.write_text(json.dumps({"nguon": "data/_eval/h3/ket_qua.json", "sha256_nguon": sha_hoa(KQ), **res}, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    d = ["# Kết quả phép thử mô phỏng H3 – \"ô tô trống, chữ viết tay có\"", "",
         f"Chạy MỘT lần {res['thoi_gian']} theo đăng ký `docs/dang_ky_h3_mo_phong.md` (tag `{res['dang_ky']['tag']}`, mã được kiểm "
         f"`{res['dang_ky']['ma_commit_kiem'][:8]}`, biến thể ô nguồn `{res['dang_ky']['bien_the']}`, chỉ chọn trường đợt 2 đã nhận: "
         f"{res['dang_ky']['chi_truong_nhan']}). Nguồn: `data/_eval/h3/ket_qua.json` (SHA-256 `{sha_hoa(KQ)}`), bản sao `docs/ket_qua_h3_mo_phong.json`.", "",
         "## Tiêu chí", "", "| Tiêu chí | Kết quả | Dự đoán | Đạt |", "|---|---|---|---|",
         f"| T1 – trường bị xoá bubble mà hệ thống NHẬN | {s['T1_nhan']} / {s['n'] - s['bi_tu_choi']} (bị từ chối khi nắn: {s['bi_tu_choi']}) | 0 (20/20 cần xem) | "
         f"{'ĐẠT' if s['dat']['T1'] else 'KHÔNG ĐẠT'} |",
         f"| T2 – tự chốt sai / điểm chính thức sai sau oracle | {s['T2_vi_pham']} (tự chốt khi tải: {s['tu_chot']}) | 0 | {'ĐẠT' if s['dat']['T2'] else 'KHÔNG ĐẠT'} |",
         f"| T3 – trường không sửa giống đợt 2 | {s['T3_khop']} / {s['T3_n']} | ≥ 19 / 20 | {'ĐẠT' if s['dat']['T3_du_doan_ge_19'] else 'KHÔNG ĐẠT'} |"]
    if "KT0_n" in s:
        d.append(f"| KT0 – ảnh gốc PNG không sửa giống đợt 2 (kiểm công cụ, không phải tiêu chí) | {s['KT0_khop']} / {s['KT0_n']} | 20 / 20 | – |")
    d += ["", "## 20 ca", "", "| Ảnh | Trường | Cột | Chữ số xoá | Ô nguồn (cột, hàng) | Bubble đọc | CNN đọc (p) | Trường | Lý do hiển thị | Phiếu tải → cuối | Điểm CT / thật | T3 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in res["ca"]:
        if c["status_tai"] == "rejected":
            d.append(f"| {c['anh']} | {c['truong']} | {c['cot']} | {c['chu_so_xoa']} | {c.get('o_nguon')} | – | – | BỊ TỪ CHỐI {c['tu_choi']} | – | rejected | – | – |")
            continue
        d.append(f"| {c['anh']} | {c['truong']} | {c['cot']} | {c['chu_so_xoa']} | {c['o_nguon']} | {c['kenh_bubble']} | {c['kenh_cnn']} ({c['p_cnn']:.2f}) | "
                 f"{'cần xem' if c['truong_can_xem'] else '**NHẬN**'} | {'; '.join(c['ly_do_hien_thi']) or '–'} | {c['status_tai']} → {c['status_cuoi']} | "
                 f"{c['diem_chinh_thuc']} / {c['diem_that']} | {'khớp' if c.get('T3_khop') else '**khác**'} |")
    la = [c for c in res["ca"] if c["status_tai"] == "rejected" or c.get("T1_nhan") or c.get("T2_vi_pham") or c.get("T3_khop") is False
          or c.get("truong_da_can_xem_o_dot2")]
    d += ["", "## Ca bất thường / cần lưu ý", ""] + ([f"- {c['anh']}: " + json.dumps({k: c.get(k) for k in ("status_tai", "tu_choi", "T1_nhan", "T2_vi_pham", "T3_khop",
                                                                                                           "truong_da_can_xem_o_dot2", "T3_khac")}, ensure_ascii=False)
                                                     for c in la] or ["- Không có."])
    d += ["", "## Giới hạn", "",
          "- Ảnh chỉnh bằng phần mềm (chép điểm ảnh của một ô trống thật trên chính ảnh sang vị trí ô đã tô), KHÔNG phải ô để trống trên giấy: "
          "không phản ánh đặc tính quang học thật của ô chưa từng tô (vết tẩy, lõm giấy, bóng bút chì còn sót).",
          "- Chỉ kiểm LOGIC hai kênh (bubble ↔ chữ viết tay) khi một cột bubble trống; không đo lại độ chính xác OMR / CNN.",
          "- Một điện thoại (bộ ảnh đợt 2), 5 người viết.",
          "- 20 ca KHÔNG độc lập: hai ảnh của cùng một phiếu (cùng nét viết, cùng tờ giấy).",
          "- Chưa thay thế phép thử bằng giấy thật (để trống một cột bubble khi tô)."]
    DOCS_KQ_MD.write_text("\n".join(d) + "\n", encoding="utf-8")
    print(f"Đã ghi {DOCS_KQ_MD} và {DOCS_KQ_JSON}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["dien-tap", "run", "bao-cao"])
    ap.add_argument("--bien-the", choices=["hang", "cot"], default="hang")
    ap.add_argument("--xac-nhan-h3", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.lenh == "dien-tap":
        r = dien_tap(a.bien_the)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    elif a.lenh == "bao-cao":
        bao_cao()
    else:
        if not a.xac_nhan_h3:
            sys.exit("TỪ CHỐI: chạy chính thức cần --xac-nhan-h3 (MỘT lần, sau đăng ký + tag dang-ky-h3-mo-phong).")
        r = chay_chinh_thuc()
        print(json.dumps(r["tom_tat"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
