"""
nap_giao_vien_demo.py - Dữ liệu mẫu cho phân quyền theo lớp (idempotent). Mặc định chỉ XEM TRƯỚC (in câu lệnh, không ghi); ghi khi có --ap-dung.

  gv_an   -> lớp CNTT-K22A, môn IT3080 (Cơ sở dữ liệu)
  gv_binh -> lớp CNTT-K22B, môn IT4040 (Trí tuệ nhân tạo)
  kỳ thi demo hiện có ('[DEMO…' / '[THU…') do gv_an tạo và CHƯA có lớp -> gắn CNTT-K22A (chỉ đặt class_id khi đang NULL; không đổi môn, tên, điểm)

Cần migration 002 (python -m backend.migrate) trước khi --ap-dung. Chạy lại an toàn (ON CONFLICT / chỉ cập nhật khi NULL).
  python tools/nap_giao_vien_demo.py                # xem trước
  python tools/nap_giao_vien_demo.py --ap-dung      # ghi vào CSDL
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTH_MODE", "demo")

GAN = [("gv_an", "CNTT-K22A", "IT3080"), ("gv_binh", "CNTT-K22B", "IT4040")]
SQL_GAN = ("INSERT INTO teacher_classes (user_id, class_id, subject_id) "
           "SELECT u.user_id, c.class_id, s.subject_id FROM users u, classes c, subjects s "
           "WHERE u.username = %s AND c.class_code = %s AND s.subject_code = %s "
           "ON CONFLICT (user_id, class_id) DO UPDATE SET subject_id = EXCLUDED.subject_id")
SQL_KY_THI = ("UPDATE exams e SET class_id = (SELECT class_id FROM classes WHERE class_code = %s) "
              "WHERE e.class_id IS NULL AND (e.exam_title LIKE '[DEMO%%' OR e.exam_title LIKE '[THU%%') "
              "AND e.created_by = (SELECT user_id FROM users WHERE username = %s)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap-dung", action="store_true", help="GHI vào CSDL (mặc định chỉ xem trước)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print("CHẾ ĐỘ:", "ÁP DỤNG (ghi CSDL)" if a.ap_dung else "XEM TRƯỚC (không ghi)")
    for u, lop, mon in GAN:
        print(f"  teacher_classes: {u} -> {lop} (môn {mon})")
    print(f"  exams.class_id: kỳ thi '[DEMO…' / '[THU…' của gv_an chưa có lớp -> CNTT-K22A")
    if not a.ap_dung:
        from backend.db import ket_noi
        try:
            with ket_noi() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                ds = conn.execute("SELECT e.exam_id, e.exam_title FROM exams e WHERE (e.exam_title LIKE '[DEMO%%' OR e.exam_title LIKE '[THU%%') "
                                  "AND e.created_by = (SELECT user_id FROM users WHERE username = 'gv_an') ORDER BY e.exam_id").fetchall()
                print(f"  (chỉ đọc) {len(ds)} kỳ thi sẽ được gắn lớp:", "; ".join(f"{r['exam_id']}: {r['exam_title']}" for r in ds))
        except Exception as e:  # noqa: BLE001 – xem trước không được làm hỏng vì CSDL
            print(f"  (không đọc được CSDL để liệt kê kỳ thi: {type(e).__name__})")
        print("Chưa ghi gì. Thêm --ap-dung để ghi.")
        return 0
    from backend.db import ket_noi
    with ket_noi() as conn:
        for u, lop, mon in GAN:
            cur = conn.execute(SQL_GAN, (u, lop, mon))
            print(f"  teacher_classes {u}: {cur.rowcount} dòng")
        n = conn.execute(SQL_KY_THI, ("CNTT-K22A", "gv_an")).rowcount
        print(f"  exams: gắn lớp cho {n} kỳ thi")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
