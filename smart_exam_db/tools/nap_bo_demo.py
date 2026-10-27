"""
nap_bo_demo.py - Nạp bộ DEMO BẢO VỆ [DEMO-BV] (answer_sheet/demo_bv/): 2 kỳ thi 40 câu có đáp án thật, gắn môn + lớp + giáo viên, danh sách dự thi.
Mặc định XEM TRƯỚC (giao dịch CHỈ ĐỌC, không ghi gì); chỉ --ap-dung mới ghi. Chỉ INSERT; chạy lại không tạo trùng (nhận biết theo tiêu đề kỳ thi;
exam_students ON CONFLICT DO NOTHING). Không sửa / xoá kỳ thi [DEMO], [DEMO-2], kỳ thi seed hay sinh viên có sẵn; không tạo sinh viên mới.

  E1 'Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV]'      : gv_an,   IT3080, CNTT-K22A, mã đề 101/102, dự thi 220001–220005
  E2 'Giữa kỳ Trí tuệ nhân tạo – K22B [DEMO-BV]'   : gv_binh, IT4040, CNTT-K22B, mã đề 103/104, dự thi 220006–220009
  220010 KHÔNG thuộc kỳ thi nào (phiếu BV10 minh hoạ "SBD không thuộc kỳ thi").

  python tools/kiem_bo_demo.py              # kiểm kịch bản trước
  python tools/nap_bo_demo.py               # xem trước
  python tools/nap_bo_demo.py --ap-dung     # GHI vào CSDL
  python tools/nap_bo_demo.py --ban-tap [--ap-dung]   # BẢN TẬP: 2 kỳ thi "[DEMO-BV-TẬP]" giống hệt E1 / E2 (đáp án, môn, lớp, GV, dự thi)
                                                      #   để diễn tập chụp bằng điện thoại mà không làm bẩn kỳ thi demo 1380 / 1381
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("AUTH_MODE", "demo")      # công cụ trong tiến trình: không cần đăng nhập

import kiem_bo_demo as K  # noqa: E402

NHAN = "[DEMO-BV]"
NHAN_TAP = "[DEMO-BV-TẬP]"
DU_THI = {"E1": [str(s) for s in range(220001, 220006)], "E2": [str(s) for s in range(220006, 220010)]}   # 220010 cố ý KHÔNG dự thi
SO_CAU, THANG, DAT = 40, 10, 5


def ke_hoach(ban_tap: bool = False) -> list[dict]:
    """Kỳ thi cần nạp, dựng từ demo_bv_dap_an.csv (đã kiểm bằng kiem_bo_demo). ban_tap: chỉ đổi nhãn tiêu đề [DEMO-BV] -> [DEMO-BV-TẬP]."""
    loi, _ = K.kiem(K.doc(K.DAP_AN), K.doc(K.KICH_BAN))
    if loi:
        raise SystemExit("DỪNG: kịch bản demo sai – chạy python tools/kiem_bo_demo.py:\n  " + "\n  ".join(loi))
    kt: dict[str, dict] = {}
    for r in K.doc(K.DAP_AN):
        e = kt.setdefault(r["exam"], {"ma": r["exam"], "exam_title": r["exam_title"], "subject_code": r["subject_code"], "class_code": r["class_code"],
                                      "teacher": r["teacher"], "codes": [], "du_thi": DU_THI[r["exam"]]})
        e["codes"].append({"code": r["exam_code"], "answers": r["answers"]})
    for e in kt.values():
        assert NHAN in e["exam_title"], e["exam_title"]
        if ban_tap:
            e["exam_title"] = e["exam_title"].replace(NHAN, NHAN_TAP)
    return list(kt.values())


def doi_chieu(conn, kh: list[dict]) -> list[dict]:
    """Tra (chỉ đọc) id môn / lớp / giáo viên / sinh viên + kỳ thi đã có. Thiếu thứ gì thì DỪNG (không tự tạo)."""
    ra = []
    for e in kh:
        mon = conn.execute("SELECT subject_id, subject_name FROM subjects WHERE subject_code = %s", (e["subject_code"],)).fetchone()
        lop = conn.execute("SELECT class_id, class_name FROM classes WHERE class_code = %s", (e["class_code"],)).fetchone()
        gv = conn.execute("SELECT user_id, full_name FROM users WHERE username = %s AND role = 'teacher' AND is_active", (e["teacher"],)).fetchone()
        sv = conn.execute("SELECT student_id, student_code, full_name FROM students WHERE student_code = ANY(%s) ORDER BY student_code",
                          (e["du_thi"],)).fetchall()
        thieu = ([f"môn {e['subject_code']}"] if not mon else []) + ([f"lớp {e['class_code']}"] if not lop else []) + \
                ([f"giáo viên {e['teacher']}"] if not gv else []) + [f"sinh viên {s}" for s in sorted(set(e["du_thi"]) - {x["student_code"] for x in sv})]
        if thieu:
            raise SystemExit(f"DỪNG: {e['ma']} thiếu dữ liệu có sẵn: {', '.join(thieu)} (công cụ không tự tạo).")
        if gv and not conn.execute("SELECT 1 FROM teacher_classes WHERE user_id = %s AND class_id = %s", (gv["user_id"], lop["class_id"])).fetchone():
            raise SystemExit(f"DỪNG: {e['teacher']} chưa được gán lớp {e['class_code']} (chạy tools/nap_giao_vien_demo.py --ap-dung).")
        cu = conn.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (e["exam_title"],)).fetchall()
        if len(cu) > 1:
            raise SystemExit(f"DỪNG: có {len(cu)} kỳ thi cùng tiêu đề '{e['exam_title']}'.")
        ra.append({**e, "mon": mon, "lop": lop, "gv": gv, "sv": sv, "exam_id": cu[0]["exam_id"] if cu else None})
    return ra


def nap(conn, ap_dung: bool, ban_tap: bool = False) -> list[dict]:
    """Trả tóm tắt từng kỳ thi (số dòng sẽ / đã INSERT mỗi bảng). ap_dung=False: chỉ đọc. KHÔNG commit (người gọi quyết định)."""
    from backend import service
    tom = []
    for e in doi_chieu(conn, ke_hoach(ban_tap)):
        moi = e["exam_id"] is None
        da_du_thi = set() if moi else {r["student_id"] for r in conn.execute("SELECT student_id FROM exam_students WHERE exam_id = %s",
                                                                                 (e["exam_id"],)).fetchall()}
        can_du_thi = [s for s in e["sv"] if s["student_id"] not in da_du_thi]
        dong = {"exams": int(moi), "exam_codes": len(e["codes"]) if moi else 0, "answer_keys": SO_CAU * len(e["codes"]) if moi else 0,
                "exam_students": len(can_du_thi)}
        if ap_dung:
            eid = e["exam_id"]
            if moi:
                eid = service.tao_ky_thi(conn, {"exam_title": e["exam_title"], "subject_code": e["subject_code"], "subject_name": e["mon"]["subject_name"],
                                                "num_questions": SO_CAU, "max_score": THANG, "pass_score": DAT, "class_id": e["lop"]["class_id"],
                                                "codes": e["codes"]}, e["gv"]["user_id"])
            with conn.cursor() as cur:
                cur.executemany("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                [(eid, s["student_id"]) for s in can_du_thi])
            e["exam_id"] = eid
        tom.append({"ma": e["ma"], "exam_id": e["exam_id"], "exam_title": e["exam_title"], "mon": f"{e['subject_code']} – {e['mon']['subject_name']}",
                    "lop": f"{e['class_code']} – {e['lop']['class_name']}", "giao_vien": f"{e['teacher']} ({e['gv']['full_name']})",
                    "ma_de": [c["code"] for c in e["codes"]], "du_thi": [s["student_code"] for s in e["sv"]], "insert": dong})
    return tom


def in_tom_tat(tom: list[dict], ap_dung: bool) -> None:
    for t in tom:
        print(f"\n{t['ma']}: {t['exam_title']}  (exam_id {t['exam_id'] or 'mới'})")
        print(f"  môn {t['mon']} · lớp {t['lop']} · giáo viên {t['giao_vien']} · mã đề {', '.join(t['ma_de'])} · 40 câu, thang 10, đạt 5")
        print(f"  dự thi ({len(t['du_thi'])}): {', '.join(t['du_thi'])}")
        print("  INSERT " + ("đã ghi" if ap_dung else "sẽ ghi") + ": " + ", ".join(f"{k} {v}" for k, v in t["insert"].items()))
    tong = {k: sum(t["insert"][k] for t in tom) for k in tom[0]["insert"]}
    print("\nTỔNG INSERT " + ("đã ghi" if ap_dung else "sẽ ghi") + ": " + ", ".join(f"{k} {v}" for k, v in tong.items()) + "  (không UPDATE / DELETE nào)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap-dung", action="store_true", help="GHI vào CSDL (mặc định chỉ xem trước)")
    ap.add_argument("--ban-tap", action="store_true", help="bản TẬP [DEMO-BV-TẬP] (diễn tập, không đụng kỳ thi demo)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from backend.db import ket_noi
    print("CHẾ ĐỘ:", "ÁP DỤNG (ghi CSDL)" if a.ap_dung else "XEM TRƯỚC (giao dịch chỉ đọc, không ghi)", "· BẢN TẬP" if a.ban_tap else "")
    with ket_noi() as conn:
        if not a.ap_dung:
            conn.execute("SET TRANSACTION READ ONLY")
        tom = nap(conn, a.ap_dung, a.ban_tap)
        if a.ap_dung:
            conn.commit()
        else:
            conn.rollback()
    in_tom_tat(tom, a.ap_dung)
    if not a.ap_dung:
        print("Chưa ghi gì. Thêm --ap-dung để ghi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
