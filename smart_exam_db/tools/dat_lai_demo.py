"""
dat_lai_demo.py - Lệnh U (30/10/2026): ĐẶT LẠI dữ liệu demo trước buổi bảo vệ.

  python tools/dat_lai_demo.py                          # XEM TRƯỚC (mặc định, giao dịch CHỈ ĐỌC): liệt kê đúng phiếu + tệp ảnh sẽ xoá
  python tools/dat_lai_demo.py --xac-nhan DAT_LAI       # sao lưu CSV + ảnh -> xoá trong MỘT giao dịch -> xoá tệp ảnh -> in số trước / sau
  python tools/dat_lai_demo.py --ky-thi xla|ml|dacn [--xac-nhan DAT_LAI]   # lệnh AP: đặt lại RIÊNG MỘT kỳ thi theo môn ([XLA] / [ML] / [ĐACN]) về 0 phiếu;
                                                        #   không đụng kỳ thi nào khác (phạm vi = đúng một exam_id, tìm theo tiêu đề nguyên văn)

Mục tiêu:
- Kỳ thi demo chính 1380, 1381 [DEMO-BV] và 1633 [DEMO-BV-TẬP K22B] về 0 phiếu (XOÁ CẢ phiếu có điểm chính thức – đó là kết quả diễn tập).
- Kỳ thi tập 1632 về NỀN: giữ 3878, 3880, 4270, 4271, 4272 (chính thức) + 6028 (cần xem); xoá phiếu khác tải lên SAU 28/10/2026 09:18:32
  (lúc tải #6028). Phiếu lạ tải lên TRƯỚC mốc đó: chỉ báo, không xoá. Nền đã bị đổi (vd phiếu nền bị thay / duyệt): chỉ cảnh báo – khôi phục bằng bản sao lưu.
- KHÔNG đụng kỳ thi khác, danh sách dự thi, tài khoản, lớp, mã đề, đáp án. Kỳ thi trong phạm vi phải có dấu "[DEMO" trong tên (chốt an toàn).
- Lệnh V (30/10/2026): phạm vi CHỈ là danh sách id cố định ở trên – KHÔNG chọn theo chuỗi "[DEMO" (chuỗi đó chỉ để TỪ CHỐI), nên kỳ thi 6 "[DEMO] …",
  178 "[DEMO-2] …", 115 / 509 "[THU] …" không bao giờ bị đụng. Hậu kiểm: phiếu trong kế hoạch xoá phải thuộc đúng phạm vi; CLI chỉ chạy với bộ id đã chốt.

Tái dùng tools/don_du_lieu_test.py: đếm (SQL_DEM), sao lưu CSV + ảnh (sao_luu), xoá trong MỘT giao dịch + hoàn tác khi lệch số dòng (thuc_hien),
xoá tệp chỉ trong STORAGE_DIR (xoa_tep), kiểm dòng mồ côi (kiem_sau). Chỉ PHẦN CHỌN PHIẾU là riêng: lap_ke_hoach của công cụ đó cố ý GIỮ phiếu có
điểm chính thức, còn ở đây kỳ thi demo chính phải về 0 phiếu. Tệp ảnh mà phiếu KHÁC (ngoài danh sách xoá) cũng dùng thì GIỮ, không xoá.
Hàm lap_ke_hoach / thuc_hien không commit (test chạy trong giao dịch ROLLBACK); chỉ CLI commit sau khi mọi kiểm tra đạt.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import don_du_lieu_test as D  # noqa: E402

KY_THI_XOA_HET = (1380, 1381, 1633)
KY_THI_TAP = 1632
NEN_TAP = {3878: "graded", 3880: "graded", 4270: "graded", 4271: "graded", 4272: "graded", 6028: "needs_review"}
MOC_TAP = datetime(2026, 10, 28, 9, 18, 32, 572328, tzinfo=timezone(timedelta(hours=7)))
KY_THI_DUOC_PHEP = frozenset({*KY_THI_XOA_HET, KY_THI_TAP})
XAC_NHAN = "DAT_LAI"
THU_MUC_SAO_LUU = D.THU_MUC_SAO_LUU


class LoiDatLai(Exception):
    pass


def dem_ky_thi(conn, ky_thi) -> dict:
    out = {}
    for e in ky_thi:
        r = conn.execute("SELECT count(*) AS tong, count(*) FILTER (WHERE status = 'graded') AS chinh_thuc, count(*) FILTER (WHERE status = 'needs_review') AS can_xem, "
                         "count(*) FILTER (WHERE status = 'rejected') AS tu_choi FROM answer_sheets WHERE exam_id = %s", (e,)).fetchone()
        out[e] = dict(r) | {"du_thi": conn.execute("SELECT count(*) AS n FROM exam_students WHERE exam_id = %s", (e,)).fetchone()["n"]}
    return out


def lap_ke_hoach(conn, xoa_het=KY_THI_XOA_HET, tap=KY_THI_TAP, nen=NEN_TAP, moc=MOC_TAP, ten_hop_le=None) -> dict:
    pham_vi = [*xoa_het, tap] if tap is not None else list(xoa_het)
    ten = {r["exam_id"]: r["exam_title"] for r in conn.execute("SELECT exam_id, exam_title FROM exams WHERE exam_id = ANY(%s)", (pham_vi,)).fetchall()}
    thieu = [e for e in pham_vi if e not in ten]
    if thieu:
        raise LoiDatLai(f"không có kỳ thi {thieu}")
    la = [e for e in pham_vi if not (ten_hop_le(ten[e]) if ten_hop_le else "[DEMO" in ten[e])]
    if la:
        raise LoiDatLai(f"kỳ thi {la} không có dấu [DEMO trong tên – công cụ từ chối đụng kỳ thi thật")
    cot = ("a.sheet_id, a.exam_id, a.status::text AS status, a.detected_sbd, a.original_filename, a.uploaded_at, "
           "EXISTS (SELECT 1 FROM results r WHERE r.sheet_id = a.sheet_id AND r.status <> 'void') AS chinh_thuc")
    xoa = conn.execute(f"SELECT {cot} FROM answer_sheets a WHERE a.exam_id = ANY(%s) ORDER BY a.exam_id, a.sheet_id", (list(xoa_het),)).fetchall()
    la_tap = (conn.execute(f"SELECT {cot} FROM answer_sheets a WHERE a.exam_id = %s AND NOT (a.sheet_id = ANY(%s)) ORDER BY a.sheet_id", (tap, list(nen))).fetchall()
              if tap is not None else [])
    xoa += [p for p in la_tap if p["uploaded_at"] > moc]
    bat_thuong = [p for p in la_tap if p["uploaded_at"] <= moc]
    lot = sorted({p["exam_id"] for p in xoa} - set(pham_vi))
    if lot:
        raise LoiDatLai(f"kế hoạch có phiếu của kỳ thi ngoài phạm vi {lot} – từ chối")
    nen_doi = []
    for sid, st in nen.items():
        p = conn.execute(f"SELECT {cot} FROM answer_sheets a WHERE a.sheet_id = %s", (sid,)).fetchone()
        if p is None or p["exam_id"] != tap:
            nen_doi.append(f"#{sid}: không còn trong kỳ thi {tap}")
        elif p["status"] != st or (st == "graded" and not p["chinh_thuc"]):
            nen_doi.append(f"#{sid}: trạng thái {p['status']}{'' if p['chinh_thuc'] else ', không có điểm chính thức hợp lệ'} (nền: {st})")
    ids = sorted(p["sheet_id"] for p in xoa)
    dem = {b: (conn.execute(D.SQL_DEM[b], (ids,)).fetchone()["n"] if ids else 0) for b in D.BANG_XOA}
    tep_tat_ca = D._tep_anh(conn, ids) if ids else []
    dung_chung = set()
    if tep_tat_ca:
        dung_chung = {r["p"] for r in conn.execute(
            "SELECT unnest(ARRAY[image_path, aligned_image_path]) AS p FROM answer_sheets WHERE NOT (sheet_id = ANY(%s)) "
            "UNION SELECT crop_image_path FROM ocr_digits WHERE NOT (sheet_id = ANY(%s))", (ids, ids)).fetchall()} & set(tep_tat_ca)
    return {"pham_vi": pham_vi, "ten": ten, "xoa": xoa, "ids": ids, "dem": dem, "tep": [t for t in tep_tat_ca if t not in dung_chung],
            "tep_dung_chung": sorted(dung_chung), "bat_thuong": bat_thuong, "nen_doi": nen_doi, "truoc": dem_ky_thi(conn, pham_vi), "moc": moc.isoformat(), "co_tap": tap is not None}


def in_xem_truoc(kh: dict) -> str:
    d = []
    w = d.append
    w("== ĐẶT LẠI DEMO – XEM TRƯỚC (chỉ đọc, chưa xoá gì) ==")
    w("\nHiện tại:")
    for e, s in kh["truoc"].items():
        w(f"  #{e} {kh['ten'][e][:60]:<60} {s['tong']} phiếu ({s['chinh_thuc']} chính thức, {s['can_xem']} cần xem, {s['tu_choi']} từ chối); dự thi {s['du_thi']}")
    w(f"\nSẼ XOÁ {len(kh['xoa'])} phiếu:")
    for p in kh["xoa"]:
        w(f"  #{p['sheet_id']:<6} kỳ thi {p['exam_id']}  {p['status']:<13} SBD {p['detected_sbd'] or '-':<8} {D.rut_gon_ten(p['original_filename']):<26} "
          f"tải {p['uploaded_at']:%d/%m %H:%M}{'  [CÓ ĐIỂM CHÍNH THỨC]' if p['chinh_thuc'] else ''}")
    w("\nSố dòng sẽ xoá: " + ", ".join(f"{b} {kh['dem'][b]}" for b in D.BANG_XOA))
    w(f"\nTệp ảnh sẽ xoá ({len(kh['tep'])}, đường dẫn trong STORAGE_DIR):")
    d += [f"  {t}" for t in kh["tep"]]
    if kh["tep_dung_chung"]:
        w(f"\nTệp GIỮ vì phiếu khác cũng dùng ({len(kh['tep_dung_chung'])}):")
        d += [f"  {t}" for t in kh["tep_dung_chung"]]
    if kh.get("co_tap", True):
        w(f"\nKỳ thi tập: giữ nền {sorted(NEN_TAP)}; xoá phiếu khác tải SAU {kh['moc']}.")
    if kh["bat_thuong"]:
        w(f"BẤT THƯỜNG – phiếu lạ trong kỳ thi tập tải TRƯỚC mốc ({len(kh['bat_thuong'])}), KHÔNG xoá: " + ", ".join(f"#{p['sheet_id']}" for p in kh["bat_thuong"]))
    if kh["nen_doi"]:
        w("CẢNH BÁO – nền kỳ thi tập đã đổi (công cụ KHÔNG tự khôi phục; dùng bản sao lưu CSDL nếu cần): " + "; ".join(kh["nen_doi"]))
    return "\n".join(d)


def thuc_hien(conn, kh: dict) -> dict:
    return D.thuc_hien(conn, kh)


KY_THI_BA_MON = {"xla": "[XLA] Xử lý ảnh", "ml": "[ML] Máy học", "dacn": "[ĐACN] Đồ án chuyên ngành"}


def lap_ke_hoach_ky(conn, ma: str) -> dict:
    if ma not in KY_THI_BA_MON:
        raise LoiDatLai(f"kỳ thi '{ma}' không thuộc {sorted(KY_THI_BA_MON)}")
    tieu_de = KY_THI_BA_MON[ma]
    dong = conn.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (tieu_de,)).fetchall()
    if len(dong) != 1:
        raise LoiDatLai(f"cần đúng 1 kỳ thi '{tieu_de}', thấy {len(dong)} – chạy python tools/nap_bo_demo.py --ba-mon --ap-dung")
    kh = lap_ke_hoach(conn, xoa_het=(dong[0]["exam_id"],), tap=None, nen={}, ten_hop_le=lambda t: t == tieu_de)
    if kh["pham_vi"] != [dong[0]["exam_id"]] or {p["exam_id"] for p in kh["xoa"]} - {dong[0]["exam_id"]}:
        raise LoiDatLai("kế hoạch vượt ra ngoài kỳ thi đã chọn – từ chối")
    return kh


def dat_lai_ky(ma: str, xac_nhan: str | None = None, in_ra=print) -> int:
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    kho = lay_cau_hinh().storage_dir
    conn = ket_noi()
    try:
        conn.read_only = True
        try:
            kh = lap_ke_hoach_ky(conn, ma)
        except LoiDatLai as e:
            in_ra(f"LỖI: {e}")
            return 2
        in_ra(in_xem_truoc(kh))
        if not kh["ids"]:
            in_ra(f"\nKỳ thi {KY_THI_BA_MON[ma]}: 0 phiếu – dữ liệu đã ở trạng thái đặt lại.")
            return 0
        if xac_nhan != XAC_NHAN:
            in_ra(f"\n(Chỉ xem trước – không ghi gì. Xoá thật: python tools/dat_lai_demo.py --ky-thi {ma} --xac-nhan {XAC_NHAN})")
            return 0
        conn.rollback()
        conn.read_only = False
        thu_muc = THU_MUC_SAO_LUU / (datetime.now().strftime("%Y%m%d_%H%M%S") + f"_dat_lai_{ma}")
        tep = D.sao_luu(conn, kh, thu_muc, kho)
        in_ra(f"\nĐã SAO LƯU {len(tep)} tệp vào {thu_muc}")
        try:
            da = thuc_hien(conn, kh)
        except D.LoiDon as e:
            conn.rollback()
            in_ra(f"HOÀN TÁC: {e}")
            return 3
        ks = D.kiem_sau(conn, kh["pham_vi"])
        if any(ks["mo_coi"].values()):
            conn.rollback()
            in_ra(f"HOÀN TÁC: còn dòng mồ côi {ks['mo_coi']}")
            return 3
        conn.commit()
        in_ra(f"\nĐÃ XOÁ (commit): {da}")
        in_ra(f"Tệp ảnh: {D.xoa_tep(kho, kh['tep'])}")
        sau = dem_ky_thi(conn, kh["pham_vi"])
        conn.rollback()
        e_id = kh["pham_vi"][0]
        in_ra(f"Trước → sau: #{e_id} {kh['truoc'][e_id]['tong']} → {sau[e_id]['tong']} phiếu")
        return 0
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xac-nhan", default=None, help=f'gõ đúng {XAC_NHAN} để xoá thật (không có = chỉ xem trước)')
    ap.add_argument("--ky-thi", choices=sorted(KY_THI_BA_MON), default=None, help="lệnh AP: chỉ đặt lại MỘT kỳ thi theo môn (không đụng kỳ nào khác)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.ky_thi:
        return dat_lai_ky(a.ky_thi, a.xac_nhan)
    from backend.config import lay_cau_hinh
    from backend.db import ket_noi
    kho = lay_cau_hinh().storage_dir
    conn = ket_noi()
    try:
        conn.read_only = True
        try:
            kh = lap_ke_hoach(conn)
            if sorted(kh["pham_vi"]) != sorted(KY_THI_DUOC_PHEP):
                raise LoiDatLai(f"phạm vi {kh['pham_vi']} khác bộ id đã chốt {sorted(KY_THI_DUOC_PHEP)}")
        except LoiDatLai as e:
            print("LỖI:", e)
            return 2
        print(in_xem_truoc(kh))
        if a.xac_nhan != XAC_NHAN:
            if a.xac_nhan is not None:
                print(f"\n--xac-nhan phải là {XAC_NHAN} – KHÔNG xoá gì.")
            print(f"\n(Chỉ xem trước – không ghi gì. Xoá thật: python tools/dat_lai_demo.py --xac-nhan {XAC_NHAN})")
            return 0 if a.xac_nhan is None else 1
        if not kh["ids"]:
            print("\nKhông có phiếu nào cần xoá – dữ liệu demo đã ở trạng thái đặt lại.")
            return 0
        conn.rollback()
        conn.read_only = False
        thu_muc = THU_MUC_SAO_LUU / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_dat_lai_demo")
        tep = D.sao_luu(conn, kh, thu_muc, kho)
        print(f"\nĐã SAO LƯU {len(tep)} tệp vào {thu_muc}")
        try:
            da = thuc_hien(conn, kh)
        except D.LoiDon as e:
            conn.rollback()
            print("HOÀN TÁC:", e)
            return 3
        ks = D.kiem_sau(conn, kh["pham_vi"])
        if any(ks["mo_coi"].values()):
            conn.rollback()
            print("HOÀN TÁC: còn dòng mồ côi", ks["mo_coi"])
            return 3
        conn.commit()
        print("\nĐÃ XOÁ (commit):", da)
        print("Tệp ảnh:", D.xoa_tep(kho, kh["tep"]))
        sau = dem_ky_thi(conn, kh["pham_vi"])
        conn.rollback()
        print("\nTrước → sau:")
        for e in kh["pham_vi"]:
            t, s = kh["truoc"][e], sau[e]
            print(f"  #{e}: {t['tong']} → {s['tong']} phiếu (chính thức {t['chinh_thuc']} → {s['chinh_thuc']}, cần xem {t['can_xem']} → {s['can_xem']}, "
                  f"từ chối {t['tu_choi']} → {s['tu_choi']}); dự thi {t['du_thi']} → {s['du_thi']}")
        (thu_muc / "truoc_sau.json").write_text(json.dumps({"truoc": kh["truoc"], "sau": sau}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
