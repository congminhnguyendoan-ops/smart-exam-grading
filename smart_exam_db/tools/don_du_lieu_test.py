"""
don_du_lieu_test.py - Dọn phiếu TEST thừa trong hai kỳ thi demo [DEMO-BV-TẬP] (1632 của gv_an, 1633 của gv_binh). Lệnh G1, 28/10/2026.

  python tools/don_du_lieu_test.py                      # XEM TRƯỚC (mặc định): CHỈ ĐỌC, không ghi gì
  python tools/don_du_lieu_test.py --ids 5001 5002      # thêm phiếu cụ thể (kỳ thi khác) vào danh sách xoá – CHỈ khi kỳ thi có dấu [DEMO / [THU
  python tools/don_du_lieu_test.py --giu 3881           # thêm phiếu cần GIỮ (mặc định giữ mọi phiếu có điểm chính thức hợp lệ)
  python tools/don_du_lieu_test.py --thuc-hien          # sao lưu -> gõ "XOA" -> xoá trong MỘT giao dịch (lệch số dòng so với xem trước = ROLLBACK) -> xoá tệp ảnh
  python tools/don_du_lieu_test.py --chi-ids --ids 6883 6884   # (lệnh J) CHỈ đúng các phiếu --ids, KHÔNG xét 1632 / 1633 (thêm --thuc-hien để xoá)

Phiếu GIỮ = phiếu `graded` có dòng results status <> 'void' (điểm chính thức hợp lệ) + các phiếu --giu. Mọi phiếu còn lại của 1632 / 1633 là ứng viên xoá.
Bảng con (dò từ pg_constraint, không đoán): sheet_answers, review_queue, ocr_digits (ON DELETE CASCADE) và results (KHÔNG cascade) → score_audit_logs (cascade theo results).
KHÔNG xoá kỳ thi, sinh viên, lớp, tài khoản, mã đề, đáp án, scan_batches. Không đụng ảnh / dữ liệu dev, test, đợt 2 (data/raw*): chỉ tệp ảnh của chính phiếu bị xoá, trong STORAGE_DIR.
Hàm lap_ke_hoach / thuc_hien KHÔNG tự commit (CLI commit sau khi mọi kiểm tra đạt) → test chạy trong giao dịch ROLLBACK.
"""
import argparse
import csv
import io
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PHAM_VI = (1632, 1633)
DAU_KY_THI_TEST = ("[DEMO", "[THU")             # kỳ thi ngoài phạm vi mặc định chỉ được xoá phiếu qua --ids khi tên có dấu này
THU_MUC_SAO_LUU = Path(os.environ["SAO_LUU_DIR"]) if os.environ.get("SAO_LUU_DIR") else ROOT / "data" / "_eval" / "sao_luu_don_du_lieu"   # Lệnh AW: image công khai không ghi được vào data/ -> đặt SAO_LUU_DIR (vd /app/storage/sao_luu)
# thứ tự xoá (con trước, cha sau); results có FK KHÔNG cascade, score_audit_logs cascade theo results nhưng xoá tường minh để đếm
BANG_XOA = ("score_audit_logs", "results", "ocr_digits", "sheet_answers", "review_queue", "answer_sheets")
SQL_DEM = {
    "score_audit_logs": "SELECT count(*) AS n FROM score_audit_logs WHERE result_id IN (SELECT result_id FROM results WHERE sheet_id = ANY(%s))",
    "results": "SELECT count(*) AS n FROM results WHERE sheet_id = ANY(%s)",
    "ocr_digits": "SELECT count(*) AS n FROM ocr_digits WHERE sheet_id = ANY(%s)",
    "sheet_answers": "SELECT count(*) AS n FROM sheet_answers WHERE sheet_id = ANY(%s)",
    "review_queue": "SELECT count(*) AS n FROM review_queue WHERE sheet_id = ANY(%s)",
    "answer_sheets": "SELECT count(*) AS n FROM answer_sheets WHERE sheet_id = ANY(%s)",
}
SQL_XOA = {
    "score_audit_logs": "DELETE FROM score_audit_logs WHERE result_id IN (SELECT result_id FROM results WHERE sheet_id = ANY(%s))",
    "results": "DELETE FROM results WHERE sheet_id = ANY(%s)",
    "ocr_digits": "DELETE FROM ocr_digits WHERE sheet_id = ANY(%s)",
    "sheet_answers": "DELETE FROM sheet_answers WHERE sheet_id = ANY(%s)",
    "review_queue": "DELETE FROM review_queue WHERE sheet_id = ANY(%s)",
    "answer_sheets": "DELETE FROM answer_sheets WHERE sheet_id = ANY(%s)",
}
SQL_SAO_LUU = {                                  # dòng sắp xoá -> CSV
    "answer_sheets": "SELECT * FROM answer_sheets WHERE sheet_id = ANY(%s) ORDER BY sheet_id",
    "sheet_answers": "SELECT * FROM sheet_answers WHERE sheet_id = ANY(%s) ORDER BY sheet_id, question_no",
    "review_queue": "SELECT * FROM review_queue WHERE sheet_id = ANY(%s) ORDER BY review_id",
    "ocr_digits": "SELECT * FROM ocr_digits WHERE sheet_id = ANY(%s) ORDER BY sheet_id, field, position",
    "results": "SELECT * FROM results WHERE sheet_id = ANY(%s) ORDER BY result_id",
    "score_audit_logs": "SELECT * FROM score_audit_logs WHERE result_id IN (SELECT result_id FROM results WHERE sheet_id = ANY(%s)) ORDER BY audit_id",
}


class LoiDon(Exception):
    pass


def rut_gon_ten(ten, toi_da=24, dau=10):
    """Cùng quy tắc với hàm hiển thị ở giao diện (frontend/ten_tep.js): dài hơn 24 ký tự -> 10 ký tự đầu + '…' + đuôi tệp."""
    ten = ten or ""
    if len(ten) <= toi_da:
        return ten
    i = ten.rfind(".")
    duoi = ten[i:] if 0 < i and len(ten) - i <= 8 else ""
    return ten[:dau] + "…" + duoi


def _tep_anh(conn, ids: list[int]) -> list[str]:
    """Đường dẫn TƯƠNG ĐỐI (so với STORAGE_DIR) của mọi tệp ảnh thuộc các phiếu: ảnh gốc, ảnh nắn, ô viết tay."""
    ra = []
    for r in conn.execute("SELECT image_path, aligned_image_path FROM answer_sheets WHERE sheet_id = ANY(%s)", (ids,)).fetchall():
        ra += [p for p in (r["image_path"], r["aligned_image_path"]) if p]
    ra += [r["crop_image_path"] for r in conn.execute("SELECT crop_image_path FROM ocr_digits WHERE sheet_id = ANY(%s) AND crop_image_path IS NOT NULL", (ids,)).fetchall()]
    return sorted(set(ra))


def lap_ke_hoach(conn, pham_vi=PHAM_VI, ids_them=(), giu_them=()) -> dict:
    """CHỈ ĐỌC. Trả: giu (phiếu giữ), xoa (phiếu xoá + thông tin), dem (số dòng mỗi bảng), tep (ảnh), ngoai_pham_vi (chỉ liệt kê)."""
    pham_vi, ids_them, giu_them = list(pham_vi), set(ids_them), set(giu_them)
    cot = ("a.sheet_id, a.exam_id, e.exam_title, a.status::text AS status, a.detected_sbd, a.original_filename, a.matched_student_id, "
           "r.status::text AS ket_qua, r.score, (r.result_id IS NOT NULL AND r.status <> 'void') AS chinh_thuc")
    tu = "FROM answer_sheets a JOIN exams e USING (exam_id) LEFT JOIN results r ON r.sheet_id = a.sheet_id AND r.status <> 'void'"
    trong = conn.execute(f"SELECT {cot} {tu} WHERE a.exam_id = ANY(%s) ORDER BY a.exam_id, a.sheet_id", (pham_vi,)).fetchall()
    giu, xoa = [], []
    for p in trong:
        (giu if (p["chinh_thuc"] and p["status"] == "graded") or p["sheet_id"] in giu_them else xoa).append(p)
    if ids_them:
        co = {p["sheet_id"] for p in trong}
        them = conn.execute(f"SELECT {cot} {tu} WHERE a.sheet_id = ANY(%s) ORDER BY a.sheet_id", (sorted(ids_them - co),)).fetchall()
        thieu = ids_them - co - {p["sheet_id"] for p in them}
        if thieu:
            raise LoiDon(f"--ids: không có phiếu {sorted(thieu)}.")
        for p in them:
            if not any(d in (p["exam_title"] or "") for d in DAU_KY_THI_TEST):
                raise LoiDon(f"--ids: phiếu #{p['sheet_id']} thuộc kỳ thi '{p['exam_title']}' (không có dấu {DAU_KY_THI_TEST}) – công cụ từ chối xoá phiếu của kỳ thi thật.")
            if p["chinh_thuc"] and p["sheet_id"] not in giu_them:
                raise LoiDon(f"--ids: phiếu #{p['sheet_id']} đang có điểm chính thức hợp lệ – không xoá. (Muốn xoá thật sự, hãy rút điểm bằng giao diện trước.)")
            if p["sheet_id"] not in giu_them:
                xoa.append(p)
    ids = sorted(p["sheet_id"] for p in xoa)
    dem = {b: (conn.execute(SQL_DEM[b], (ids,)).fetchone()["n"] if ids else 0) for b in BANG_XOA}
    ngoai = conn.execute(
        "SELECT a.sheet_id, a.exam_id, e.exam_title, a.status::text AS status, a.detected_sbd, a.original_filename FROM answer_sheets a JOIN exams e USING (exam_id) "
        "WHERE a.exam_id <> ALL(%s) AND (e.exam_title LIKE '%%[DEMO%%' OR e.exam_title LIKE '%%[THU%%') ORDER BY a.exam_id, a.sheet_id", (pham_vi,)).fetchall()
    ngoai = [p for p in ngoai if p["sheet_id"] not in set(ids)]
    return {"pham_vi": pham_vi, "giu": giu, "xoa": xoa, "ids": ids, "dem": dem, "tep": _tep_anh(conn, ids) if ids else [], "ngoai_pham_vi": ngoai}


def in_xem_truoc(kh: dict) -> str:
    d = io.StringIO()
    w = lambda *a: print(*a, file=d)                                       # noqa: E731
    dong = lambda p: f"  #{p['sheet_id']:<6} kỳ thi {p['exam_id']}  {p['status']:<13} SBD {p['detected_sbd'] or '-':<8} {rut_gon_ten(p['original_filename']):<26}"   # noqa: E731
    w(f"== XEM TRƯỚC (chỉ đọc) – phạm vi kỳ thi {kh['pham_vi']} ==")
    w(f"\nGIỮ ({len(kh['giu'])} phiếu):")
    for p in kh["giu"]:
        w(dong(p) + (f" điểm chính thức {p['score']} ({p['ket_qua']})" if p["chinh_thuc"] else " (giữ theo --giu)"))
    w(f"\nXOÁ ({len(kh['xoa'])} phiếu):")
    for p in kh["xoa"]:
        w(dong(p))
    w("\nSố dòng sẽ xoá:")
    for b in BANG_XOA:
        w(f"  {b:<17} {kh['dem'][b]}")
    w(f"  tệp ảnh trên đĩa (tối đa) {len(kh['tep'])}")
    w(f"\nNGOÀI PHẠM VI – KHÔNG xoá, chỉ liệt kê ({len(kh['ngoai_pham_vi'])} phiếu ở kỳ thi [DEMO]/[THU] khác; muốn xoá hãy thêm --ids):")
    for p in kh["ngoai_pham_vi"]:
        w(dong(p) + f" | {p['exam_title']}")
    return d.getvalue()


def sao_luu(conn, kh: dict, thu_muc: Path, kho: Path) -> list[Path]:
    """Ghi dòng sắp xoá ra CSV (UTF-8) + sao chép tệp ảnh (chỉ của các phiếu này) vào thu_muc. Trả danh sách tệp đã ghi."""
    thu_muc.mkdir(parents=True, exist_ok=True)
    ra = []
    for b, sql in SQL_SAO_LUU.items():
        rows = conn.execute(sql, (kh["ids"],)).fetchall()
        p = thu_muc / f"{b}.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                for r in rows:
                    w.writerow({k: (json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
        ra.append(p)
    (thu_muc / "ke_hoach.json").write_text(json.dumps({"thoi_gian": datetime.now().isoformat(timespec="seconds"), "pham_vi": kh["pham_vi"], "ids": kh["ids"],
                                                       "dem": kh["dem"], "tep": kh["tep"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    ra.append(thu_muc / "ke_hoach.json")
    for rel in kh["tep"]:
        nguon = (kho / rel).resolve()
        if kho.resolve() in nguon.parents and nguon.is_file():
            dich = thu_muc / "anh" / rel
            dich.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(nguon, dich)
            ra.append(dich)
    return ra


def thuc_hien(conn, kh: dict) -> dict:
    """Xoá trong MỘT giao dịch con (savepoint): mỗi bảng phải xoá ĐÚNG số dòng như xem trước, lệch -> LoiDon + rollback phần đã xoá. KHÔNG commit."""
    if not kh["ids"]:
        return {b: 0 for b in BANG_XOA}
    da = {}
    with conn.transaction():                                              # savepoint: ném lỗi = hoàn tác toàn bộ phần xoá
        for b in BANG_XOA:
            n = conn.execute(SQL_XOA[b], (kh["ids"],)).rowcount
            da[b] = n
            if n != kh["dem"][b]:
                raise LoiDon(f"bảng {b}: xoá {n} dòng, xem trước là {kh['dem'][b]} → HOÀN TÁC.")
        con = conn.execute("SELECT count(*) AS n FROM answer_sheets WHERE sheet_id = ANY(%s)", (kh["ids"],)).fetchone()["n"]
        if con:
            raise LoiDon(f"còn {con} phiếu sau khi xoá → HOÀN TÁC.")
    return da


def xoa_tep(kho: Path, tep: list[str]) -> dict:
    """Xoá tệp ảnh (đường dẫn tương đối): chỉ trong `kho`; không tồn tại thì bỏ qua; không bao giờ thoát khỏi `kho`."""
    kho_r = kho.resolve()
    ket = {"da_xoa": 0, "khong_ton_tai": 0, "bo_qua_ngoai_kho": 0}
    for rel in tep:
        p = (kho / rel).resolve()
        if kho_r not in p.parents:
            ket["bo_qua_ngoai_kho"] += 1
        elif p.is_file():
            p.unlink()
            ket["da_xoa"] += 1
        else:
            ket["khong_ton_tai"] += 1
    return ket


def kiem_sau(conn, pham_vi) -> dict:
    """Thống kê hai kỳ thi + dòng mồ côi + API đọc được (hàm dịch vụ mà endpoint gọi)."""
    from backend import bang_diem, service
    tk = {}
    for e in pham_vi:
        r = conn.execute("SELECT count(*) AS tong, count(*) FILTER (WHERE status = 'graded') AS chinh_thuc, count(*) FILTER (WHERE status = 'needs_review') AS can_xem, "
                         "count(*) FILTER (WHERE status = 'rejected') AS tu_choi FROM answer_sheets WHERE exam_id = %s", (e,)).fetchone()
        tk[e] = dict(r)
        tk[e]["ds_phieu_api"] = len(service.ds_phieu_ky_thi(conn, e))
        tk[e]["bang_diem_api_dong"] = len(bang_diem.bang_diem(conn, e)["rows"])
    mo_coi = {t: conn.execute(f"SELECT count(*) AS n FROM {t} x WHERE NOT EXISTS (SELECT 1 FROM answer_sheets a WHERE a.sheet_id = x.sheet_id)").fetchone()["n"]
              for t in ("sheet_answers", "review_queue", "ocr_digits", "results")}
    return {"thong_ke": tk, "mo_coi": mo_coi}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", type=int, nargs="*", default=[], help="thêm phiếu cụ thể vào danh sách xoá (kỳ thi phải có dấu [DEMO / [THU)")
    ap.add_argument("--giu", type=int, nargs="*", default=[], help="thêm phiếu cần GIỮ")
    ap.add_argument("--thuc-hien", action="store_true", help="xoá thật (mặc định: chỉ xem trước)")
    ap.add_argument("--xac-nhan", default=None, help='gõ XOA (nếu không có sẽ hỏi trên màn hình)')
    ap.add_argument("--chi-ids", action="store_true", help="phạm vi = CHỈ các phiếu --ids (không gộp mọi phiếu chưa chính thức của 1632 / 1633)")
    a = ap.parse_args()
    if a.chi_ids and not a.ids:
        print("LỖI: --chi-ids cần --ids.")
        return 2
    pham_vi = () if a.chi_ids else PHAM_VI
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    kho = lay_cau_hinh().storage_dir
    conn = ket_noi()
    try:
        if not a.thuc_hien:
            conn.read_only = True                                         # xem trước: giao dịch CHỈ ĐỌC
        try:
            kh = lap_ke_hoach(conn, pham_vi, a.ids, a.giu)
        except LoiDon as e:
            print("LỖI:", e)
            return 2
        print(in_xem_truoc(kh))
        if not a.thuc_hien:
            print("\n(Chỉ xem trước – không ghi gì. Chạy thật: python tools/don_du_lieu_test.py --thuc-hien)")
            return 0
        if not kh["ids"]:
            print("Không có gì để xoá.")
            return 0
        conn.rollback()                                                    # kết thúc giao dịch đọc; sao lưu + xoá trong giao dịch mới
        thu_muc = THU_MUC_SAO_LUU / datetime.now().strftime("%Y%m%d_%H%M%S")
        tep = sao_luu(conn, kh, thu_muc, kho)
        print(f"\nĐã SAO LƯU {len(tep)} tệp vào {thu_muc}")
        for p in tep[:12]:
            print("  ", p.relative_to(thu_muc))
        xn = a.xac_nhan if a.xac_nhan is not None else input('\nGõ đúng chữ "XOA" để xoá thật (khác = huỷ): ')
        if xn.strip() != "XOA":
            conn.rollback()
            print("Đã huỷ, không xoá gì.")
            return 1
        try:
            da = thuc_hien(conn, kh)
        except LoiDon as e:
            conn.rollback()
            print("HOÀN TÁC:", e)
            return 3
        ks = kiem_sau(conn, pham_vi or sorted({p["exam_id"] for p in kh["xoa"]}))
        if any(ks["mo_coi"].values()):
            conn.rollback()
            print("HOÀN TÁC: còn dòng mồ côi", ks["mo_coi"])
            return 3
        conn.commit()
        print("\nĐÃ XOÁ (commit):", da)
        print("Tệp ảnh:", xoa_tep(kho, kh["tep"]))
        print("Sau khi xoá:", json.dumps(ks, ensure_ascii=False, indent=1))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
