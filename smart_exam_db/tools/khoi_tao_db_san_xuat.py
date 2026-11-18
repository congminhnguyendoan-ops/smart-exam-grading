"""
khoi_tao_db_san_xuat.py - Lệnh AU (T5): khởi tạo CSDL cho bản CÔNG KHAI (chạy từ smart_exam_db/, venv đã bật, cần DATABASE_URL trong .env hoặc môi trường).

Làm đúng MỘT việc: 01_schema + 02_functions_triggers + 03_views, rồi `python -m backend.migrate` (001–006), rồi nạp MẪU PHIẾU CHUẨN (dữ liệu THAM CHIẾU bắt buộc:
không có dòng `sheet_templates` thì không tạo được kỳ thi nào – lỗi "Không tìm thấy mẫu phiếu"; đây không phải dữ liệu mẫu).
KHÔNG chạy 04_seed.sql, KHÔNG chạy 05_demo_workflow.sql, KHÔNG tạo tài khoản mặc định (04_seed có admin / gv_an / gv_binh / sv220001 – bản công khai không được có).
KHÔNG DROP / TRUNCATE / DELETE gì. Role và CSDL do người vận hành tạo trước (docker-compose tạo sẵn; máy thường: CREATE DATABASE + CREATE ROLE bằng quyền postgres).

  python tools/khoi_tao_db_san_xuat.py                         # XEM TRƯỚC (mặc định, chỉ đọc): CSDL đang ở trạng thái nào, sẽ làm gì
  python tools/khoi_tao_db_san_xuat.py --thu-schema-tam        # thử TOÀN BỘ trình tự trong một schema tạm rồi ROLLBACK (không ghi gì vào schema thật)
  python tools/khoi_tao_db_san_xuat.py --ap-dung               # ghi thật: 01–03 (nếu CSDL còn trống) + migration 001–006
  python tools/khoi_tao_db_san_xuat.py --ap-dung --tao-admin TEN [--email E] [--ho-ten H]
                                                               # + tạo quản trị viên đầu tiên; mật khẩu NGẪU NHIÊN in MỘT lần (không ghi đâu khác)
Chạy lại an toàn: CSDL đã có bảng `users` thì bỏ qua 01–03 (không tạo lại) và chỉ áp migration còn thiếu.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)

from backend import auth, migrate  # noqa: E402
from backend.db import ket_noi  # noqa: E402
from backend.tai_khoan import dat_tai_khoan  # noqa: E402

THU_MUC_SQL = ROOT / "database"
FILE_NEN = ["01_schema.sql", "02_functions_triggers.sql", "03_views.sql"]
BANG_BAT_BUOC = ["users", "classes", "students", "exams", "answer_sheets", "results", "review_queue", "schema_migrations",
                 "revoked_tokens", "admin_audit_log", "teacher_classes"]
BANG_PHAI_TRONG = ["users", "students", "classes", "exams", "answer_sheets", "results"]


def da_khoi_tao(conn) -> bool:
    return conn.execute("SELECT to_regclass('users') AS t").fetchone()["t"] is not None


def ap_nen(conn) -> list[str]:
    for ten in FILE_NEN:
        conn.execute((THU_MUC_SQL / ten).read_text(encoding="utf-8"))
    return list(FILE_NEN)


TEN_MAU_PHIEU = "Phiếu chuẩn 40 câu A4"


def ap_mau_phieu(conn) -> bool:
    import json
    from psycopg.types.json import Jsonb
    layout = json.loads((ROOT / "answer_sheet" / "output" / "layout.json").read_text(encoding="utf-8"))
    r = conn.execute(
        "INSERT INTO sheet_templates (template_name, num_questions, options_per_question, sbd_digits, exam_code_digits, page_width_px, page_height_px, layout_config, pdf_path) "
        "VALUES (%s, 40, 4, 6, 3, 2480, 3508, %s, 'answer_sheet/output/phieu_trang.pdf') ON CONFLICT (template_name) DO NOTHING RETURNING template_id",
        (TEN_MAU_PHIEU, Jsonb(layout))).fetchone()
    return r is not None


def ap_migration_trong_giao_dich(conn) -> list[str]:
    xong = migrate.da_ap(conn)
    moi = []
    for f in migrate.ds_file():
        if f.name in xong:
            continue
        conn.execute(f.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (f.name,))
        moi.append(f.name)
    return moi


def kiem_sau_khoi_tao(conn, so_dong_users_mong_doi: int) -> list[tuple[str, bool, str]]:
    kq = []
    thieu = [b for b in BANG_BAT_BUOC if conn.execute("SELECT to_regclass(%s) AS t", (b,)).fetchone()["t"] is None]
    kq.append(("đủ bảng bắt buộc", not thieu, "thiếu: " + ", ".join(thieu) if thieu else f"{len(BANG_BAT_BUOC)} bảng"))
    chua = migrate.chua_ap(conn, ca_tuy_chon=True)
    kq.append(("migration 001–006 đã áp hết", not chua, "chưa áp: " + ", ".join(chua) if chua else f"{len(migrate.ds_file())} tệp"))
    for b in BANG_PHAI_TRONG:
        n = conn.execute(f"SELECT count(*) AS n FROM {b}").fetchone()["n"]
        mong = so_dong_users_mong_doi if b == "users" else 0
        kq.append((f"bảng {b} đúng {mong} dòng (không có dữ liệu mẫu / tài khoản mặc định)", n == mong, f"{n} dòng"))
    n_mau = conn.execute("SELECT count(*) AS n FROM sheet_templates").fetchone()["n"]
    kq.append(("có đúng 1 mẫu phiếu chuẩn (dữ liệu tham chiếu để tạo kỳ thi)", n_mau == 1, f"{n_mau} mẫu"))
    ten_sv = [r["username"] for r in conn.execute("SELECT username FROM users WHERE username IN ('admin', 'gv_an', 'gv_binh', 'sv220001') ORDER BY 1")]
    if so_dong_users_mong_doi == 0:
        kq.append(("không có tài khoản mẫu của 04_seed", not ten_sv, ", ".join(ten_sv) or "không có"))
    return kq


def tao_admin(conn, username: str, email: str | None, ho_ten: str | None) -> str:
    ten = username.strip()
    if not ten or any(c.isspace() for c in ten):
        raise SystemExit("DỪNG: tên quản trị viên không được rỗng hoặc có khoảng trắng.")
    if conn.execute("SELECT 1 FROM users WHERE lower(username) = lower(%s)", (ten,)).fetchone():
        raise SystemExit(f"DỪNG: tài khoản '{ten}' đã có – không ghi đè. Đặt lại mật khẩu bằng: python -m backend.tai_khoan dat-lai-mat-khau {ten}")
    mat_khau = auth.mat_khau_ngau_nhien()
    dat_tai_khoan(conn, ten, email or f"{ten}@localhost.invalid", ho_ten or ten, "admin", mat_khau)
    return mat_khau


def thu_schema_tam() -> dict:
    ten_schema = "tmp_khoi_tao_sx"
    conn = ket_noi()
    trinh_tu: list[str] = []
    kiem: list[tuple[str, bool, str]] = []
    try:
        conn.execute(f"CREATE SCHEMA {ten_schema}")
        conn.execute(f"SET LOCAL search_path = {ten_schema}")
        trinh_tu += ap_nen(conn)
        trinh_tu += ap_migration_trong_giao_dich(conn)
        if ap_mau_phieu(conn):
            trinh_tu.append("mẫu phiếu chuẩn")
        kiem += kiem_sau_khoi_tao(conn, 0)
        mk = tao_admin(conn, "quan_tri_thu", None, None)
        kiem.append(("tạo admin đầu tiên (mật khẩu ngẫu nhiên, hợp lệ, scrypt)", auth.mat_khau_hop_le(mk) is None and len(mk) >= 12, f"{len(mk)} ký tự (không in)"))
        h = conn.execute("SELECT password_hash, role::text AS vai_tro FROM users WHERE username = 'quan_tri_thu'").fetchone()
        kiem.append(("admin có vai trò admin và băm scrypt đăng nhập được", h["vai_tro"] == "admin" and auth.kiem_mat_khau(mk, h["password_hash"]), h["password_hash"].split("$")[0]))
        kiem += [(m, d, c) for m, d, c in kiem_sau_khoi_tao(conn, 1) if m.startswith("bảng users")]
    finally:
        conn.rollback()
        conn.close()
    c2 = ket_noi()
    con_lai = c2.execute("SELECT count(*) AS n FROM pg_namespace WHERE nspname = %s", (ten_schema,)).fetchone()["n"]
    c2.close()
    return {"trinh_tu": trinh_tu, "kiem": kiem, "schema_con_lai_sau_rollback": con_lai, "dat": all(d for _, d, _ in kiem) and con_lai == 0}


def in_kiem(kiem) -> None:
    for muc, dat, ct in kiem:
        print(f"  [{'ĐẠT' if dat else 'KHÔNG ĐẠT'}] {muc} – {ct}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap-dung", action="store_true", help="ghi thật (mặc định chỉ xem trước)")
    ap.add_argument("--thu-schema-tam", action="store_true", help="thử trong schema tạm rồi ROLLBACK")
    ap.add_argument("--tao-admin", metavar="TEN", help="tạo quản trị viên đầu tiên (cần --ap-dung)")
    ap.add_argument("--email")
    ap.add_argument("--ho-ten")
    a = ap.parse_args(argv)
    if a.tao_admin and not a.ap_dung:
        ap.error("--tao-admin cần --ap-dung")

    if a.thu_schema_tam:
        r = thu_schema_tam()
        print("Trình tự đã thử (trong schema tạm): " + " → ".join(r["trinh_tu"]))
        in_kiem(r["kiem"])
        print(f"  [{'ĐẠT' if r['schema_con_lai_sau_rollback'] == 0 else 'KHÔNG ĐẠT'}] ROLLBACK – schema tạm còn lại: {r['schema_con_lai_sau_rollback']}")
        print("KẾT LUẬN:", "ĐẠT" if r["dat"] else "KHÔNG ĐẠT")
        return 0 if r["dat"] else 1

    with ket_noi() as conn:
        co_nen = da_khoi_tao(conn)
        chua = migrate.chua_ap(conn, ca_tuy_chon=True) if conn.execute("SELECT to_regclass('schema_migrations') AS t").fetchone()["t"] else [f.name for f in migrate.ds_file()]
        print(f"CSDL: {'ĐÃ có bảng (bỏ qua 01–03)' if co_nen else 'TRỐNG (sẽ chạy ' + ' + '.join(FILE_NEN) + ')'}; migration chưa áp: {', '.join(chua) or 'không'}")
        if not a.ap_dung:
            print("XEM TRƯỚC – chưa ghi gì. Thêm --ap-dung để ghi thật (hoặc --thu-schema-tam để thử không ghi).")
            return 0
        if not co_nen:
            ap_nen(conn)
            conn.commit()
            print("Đã chạy:", ", ".join(FILE_NEN))
        moi = migrate.ap_dung(conn)
        print("Migration đã áp:", ", ".join(moi) if moi else "không có mới")
        if ap_mau_phieu(conn):
            conn.commit()
            print("Đã nạp mẫu phiếu chuẩn:", TEN_MAU_PHIEU)
        mk = None
        if a.tao_admin:
            mk = tao_admin(conn, a.tao_admin, a.email, a.ho_ten)
            conn.commit()
        so_users = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
        kiem = kiem_sau_khoi_tao(conn, so_users) if so_users <= 1 else [(m, d, c) for m, d, c in kiem_sau_khoi_tao(conn, so_users)
                                                                      if not m.startswith("bảng users")]
        in_kiem(kiem)
    if mk:
        print("\n" + "=" * 70)
        print(f"QUẢN TRỊ VIÊN ĐẦU TIÊN: tên = {a.tao_admin}   mật khẩu = {mk}")
        print("Mật khẩu này CHỈ HIỆN MỘT LẦN – chép vào nơi an toàn ngay. Đổi bằng: python -m backend.tai_khoan dat-lai-mat-khau", a.tao_admin)
        print("=" * 70)
    return 0 if all(d for _, d, _ in kiem) else 1


if __name__ == "__main__":
    sys.exit(main())
