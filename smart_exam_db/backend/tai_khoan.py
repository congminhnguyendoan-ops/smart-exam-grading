"""
tai_khoan.py - Công cụ quản lý tài khoản (chạy từ smart_exam_db/). Mật khẩu nhập bằng getpass (KHÔNG nhận qua tham số dòng lệnh, không vào lịch sử shell).

  python -m backend.tai_khoan tao <username> --email a@b.vn --ho-ten "Nguyễn Văn A" [--vai-tro teacher|admin|student]
  python -m backend.tai_khoan dat-lai-mat-khau <username>
  python -m backend.tai_khoan khoa <username>          # is_active = FALSE (không đăng nhập được, phiên cũ vô hiệu ngay)
  python -m backend.tai_khoan mo-khoa <username>
  python -m backend.tai_khoan --mau                    # tạo / cập nhật gv_an, gv_binh, admin với mật khẩu NGẪU NHIÊN, in MỘT lần

GHI vào CSDL (users). Không in / không ghi log mật khẩu, trừ tài khoản mẫu `--mau` (in một lần ra màn hình để người vận hành chép đi).
"""
import argparse
import getpass
import sys

from . import auth
from .db import ket_noi

MAU = [("admin", "admin@smartexam.local", "Quản trị hệ thống", "admin"),
       ("gv_an", "an.nguyen@smartexam.local", "Nguyễn Văn An", "teacher"),
       ("gv_binh", "binh.tran@smartexam.local", "Trần Thị Bình", "teacher")]


def _nhap_mat_khau() -> str:
    while True:
        a = getpass.getpass("Mật khẩu mới: ")
        loi = auth.mat_khau_hop_le(a)
        if loi:
            print(loi)
            continue
        if a != getpass.getpass("Nhập lại: "):
            print("Hai lần nhập không khớp.")
            continue
        return a


def dat_tai_khoan(conn, username: str, email: str, ho_ten: str, vai_tro: str, mat_khau: str) -> str:
    bam = auth.bam_mat_khau(mat_khau)
    r = conn.execute("SELECT user_id FROM users WHERE lower(username) = lower(%s)", (username,)).fetchone()
    if r:
        conn.execute("UPDATE users SET password_hash = %s, full_name = %s, role = %s::user_role, is_active = TRUE WHERE user_id = %s",
                     (bam, ho_ten, vai_tro, r["user_id"]))
        return "cap_nhat"
    conn.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, %s::user_role)",
                 (username, email, bam, ho_ten, vai_tro))
    return "tao"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", nargs="?", choices=["tao", "dat-lai-mat-khau", "khoa", "mo-khoa"])
    ap.add_argument("username", nargs="?")
    ap.add_argument("--email")
    ap.add_argument("--ho-ten")
    ap.add_argument("--vai-tro", choices=["admin", "teacher", "student"], default="teacher")
    ap.add_argument("--mau", action="store_true", help="tạo / cập nhật admin, gv_an, gv_binh với mật khẩu ngẫu nhiên (in một lần)")
    a = ap.parse_args(argv)
    with ket_noi() as conn:
        if a.mau:
            print("TÀI KHOẢN MẪU (mật khẩu chỉ hiện MỘT lần – hãy chép lại):")
            for username, email, ho_ten, vai_tro in MAU:
                mk = auth.mat_khau_ngau_nhien()
                kq = dat_tai_khoan(conn, username, email, ho_ten, vai_tro, mk)
                print(f"  {username:8s} ({vai_tro:7s}) [{kq}]  mật khẩu: {mk}")
            conn.commit()
            return 0
        if not a.lenh or not a.username:
            ap.error("cần lệnh + username (hoặc --mau)")
        r = conn.execute("SELECT user_id FROM users WHERE lower(username) = lower(%s)", (a.username,)).fetchone()
        if a.lenh == "tao":
            if r:
                sys.exit(f"Đã có tài khoản '{a.username}' (dùng dat-lai-mat-khau).")
            if not a.email or not a.ho_ten:
                ap.error("tao cần --email và --ho-ten")
            dat_tai_khoan(conn, a.username, a.email, a.ho_ten, a.vai_tro, _nhap_mat_khau())
        elif not r:
            sys.exit(f"Không có tài khoản '{a.username}'.")
        elif a.lenh == "dat-lai-mat-khau":
            conn.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (auth.bam_mat_khau(_nhap_mat_khau()), r["user_id"]))
        else:
            conn.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (a.lenh == "mo-khoa", r["user_id"]))
        conn.commit()
        print("Xong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
