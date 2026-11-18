"""
nap_demo_cong_khai.py - Lệnh AW (W1–W4): nạp DỮ LIỆU DEMO vào CSDL CÔNG KHAI đã khởi tạo bằng tools/khoi_tao_db_san_xuat.py (chạy từ smart_exam_db/).

Nạp: 2 lớp, 10 sinh viên GIẢ (in ra đầy đủ để người vận hành kiểm), 3 kỳ thi theo môn ([XLA] Xử lý ảnh, [ML] Máy học, [ĐACN] Đồ án chuyên ngành; 40 câu,
mã đề 101–104, 9 thí sinh dự thi) và 3 tài khoản: 1 admin + 2 giáo viên với TÊN DO NGƯỜI VẬN HÀNH CHỌN (không dùng admin / gv_an / gv_binh / sv220001).
KHÔNG nạp ảnh bài làm, KHÔNG đọc data/, KHÔNG tạo tài khoản sinh viên, KHÔNG UPDATE / DELETE: chỉ INSERT, chạy lại không tạo trùng.
Tài khoản đã có thì GIỮ NGUYÊN (không đổi mật khẩu). Mật khẩu của tài khoản MỚI tạo là ngẫu nhiên (20 ký tự), in MỘT lần ra màn hình sau khi đã commit,
không ghi log / tệp. (Chạy bằng `docker compose run --rm`, không chạy nền: nếu không, đầu ra có thể nằm lại trong log của container.)

  python tools/nap_demo_cong_khai.py --admin QT --giao-vien GV1 GV2                                          # XEM TRƯỚC (mặc định, giao dịch chỉ đọc)
  python tools/nap_demo_cong_khai.py --admin QT --giao-vien GV1 GV2 --xac-nhan NAP_DEMO_CONG_KHAI            # GHI thật
GV1 phụ trách lớp CNTT-K22A và là người tạo cả 3 kỳ thi; GV2 phụ trách lớp CNTT-K22B (để minh hoạ phân quyền theo lớp: GV2 không thấy kỳ thi của GV1).
Đặt lại giữa các lần trình bày: python tools/dat_lai_demo.py --ky-thi xla|ml|dacn --xac-nhan DAT_LAI (docs/trien_khai_public.md mục "Nạp dữ liệu demo").
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

XAC_NHAN = "NAP_DEMO_CONG_KHAI"
TEN_CAM = {"admin", "gv_an", "gv_binh", "sv220001"}             # tài khoản mẫu của 04_seed.sql – bản công khai không được dùng
MK_DO_DAI = 20                                                  # ≥ 16 (W3)
SO_CAU, THANG, DAT = 40, 10, 5

# Môn / tiêu đề: PHẢI trùng nap_bo_demo.BA_MON và dat_lai_demo.KY_THI_BA_MON (test tests/test_nap_demo_cong_khai.py kiểm) để dat_lai_demo tìm đúng kỳ thi.
BA_MON = (("xla", "[XLA] Xử lý ảnh", "XLA", "Xử lý ảnh"), ("ml", "[ML] Máy học", "ML", "Máy học"),
          ("dacn", "[ĐACN] Đồ án chuyên ngành", "DACN", "Đồ án chuyên ngành"))
# Đáp án 4 mã đề = answer_sheet/demo_bv/demo_bv_dap_an.csv (ảnh demo BV01–BV10 chấm theo đúng các đáp án này). Nhúng sẵn vì tools/ và answer_sheet/demo_bv/ không nằm trong image.
DAP_AN = {"101": "ADDBABDCADBACDDCBBCDBBACCACCBDBAACAADBDC", "102": "CBBCCADADCADBBCCBDCBACDBDABABAABDDDDAACC",
          "103": "BACAACCACBBCDCDABDBBDBDADCCADABCADBDDCAB", "104": "DBDADDACACADDABCADCCBABBCABDABBCACCBDCDB"}
LOP = {"CNTT-K22A": "Công nghệ thông tin K22A (dữ liệu demo)", "CNTT-K22B": "Công nghệ thông tin K22B (dữ liệu demo)"}
LOP_GV = ("CNTT-K22A", "CNTT-K22B")                             # GV1 -> K22A, GV2 -> K22B
# SINH VIÊN GIẢ: MSSV = SBD in trên phiếu demo BV01–BV10 (tuần tự, không phải mã thật); họ tên bịa, lấy từ database/04_seed.sql (dữ liệu mẫu của dự án).
SINH_VIEN = (("220001", "Lê Minh Khoa", "CNTT-K22A"), ("220002", "Phạm Thu Hà", "CNTT-K22A"), ("220003", "Đỗ Quang Huy", "CNTT-K22A"),
             ("220004", "Vũ Ngọc Lan", "CNTT-K22A"), ("220005", "Hoàng Đức Minh", "CNTT-K22A"), ("220006", "Ngô Thanh Tâm", "CNTT-K22B"),
             ("220007", "Bùi Gia Bảo", "CNTT-K22B"), ("220008", "Trịnh Mai Anh", "CNTT-K22B"), ("220009", "Lý Hoài Nam", "CNTT-K22B"),
             ("220010", "Đặng Khánh Linh", "CNTT-K22B"))
DU_THI = tuple(s[0] for s in SINH_VIEN[:9])                     # 220010 cố ý KHÔNG dự thi (phiếu BV10 minh hoạ "SBD ngoài danh sách")


class LoiNap(SystemExit):
    pass


def dung(msg: str):
    raise LoiNap(f"DỪNG: {msg}")


def muc_tieu(url: str) -> str:
    """Chỉ host + tên CSDL (+ schema nếu có); KHÔNG BAO GIỜ trả người dùng / mật khẩu / cổng."""
    if "://" in url:
        u = urlsplit(url)
        host, db = u.hostname or "?", u.path.lstrip("/") or "?"
        opt = " ".join(parse_qs(u.query).get("options", []))
    else:                                                       # dạng "host=… dbname=…" của libpq
        kv = dict(p.split("=", 1) for p in url.split() if "=" in p)
        host, db, opt = kv.get("host", "?"), kv.get("dbname", "?"), kv.get("options", "")
    m = re.search(r"search_path[=\s]*([\w,]+)", opt)
    return f"host = {host} · CSDL = {db}" + (f" · schema = {m.group(1)}" if m else "")


def kiem_tham_so(admin: str, gv: list[str]) -> list[str]:
    loi = []
    ten = [admin, *gv]
    for t in ten:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", t):
            loi.append(f"tên '{t}' không hợp lệ (3–40 ký tự: chữ, số, _ . -)")
        if t.lower() in TEN_CAM:
            loi.append(f"tên '{t}' là tài khoản mẫu của 04_seed.sql – hãy chọn tên khác")
    if len({t.lower() for t in ten}) != len(ten):
        loi.append("admin và hai giáo viên phải có tên khác nhau")
    return loi


def ke_hoach_ky_thi() -> list[dict]:
    codes = [{"code": c, "answers": a} for c, a in DAP_AN.items()]
    return [{"ma": ma, "exam_title": td, "subject_code": mm, "subject_name": tm, "codes": codes} for ma, td, mm, tm in BA_MON]


def kiem_nen(conn) -> None:
    from backend import migrate
    if conn.execute("SELECT to_regclass('users') AS t").fetchone()["t"] is None:
        dung("CSDL chưa khởi tạo – chạy trước: python tools/khoi_tao_db_san_xuat.py --ap-dung")
    chua = migrate.chua_ap(conn, ca_tuy_chon=True)
    if chua:
        dung(f"migration chưa áp: {', '.join(chua)} – chạy python tools/khoi_tao_db_san_xuat.py --ap-dung")
    if conn.execute("SELECT count(*) AS n FROM sheet_templates").fetchone()["n"] == 0:
        dung("chưa có mẫu phiếu (sheet_templates) – chạy lại python tools/khoi_tao_db_san_xuat.py --ap-dung")


def nap(conn, admin: str, gv: list[str], ap_dung: bool) -> dict:
    """Trả {'dong': {bảng: số dòng mới (sẽ / đã) INSERT}, 'mat_khau': {tên: mật khẩu} (chỉ tài khoản MỚI, chỉ khi ap_dung), 'tai_khoan': [(tên, vai trò, mới?)]}.
    KHÔNG commit (người gọi quyết định). Tài khoản / sinh viên / kỳ thi có sẵn mà khác dữ liệu demo → DỪNG (không ghi đè, không đoán)."""
    kiem_nen(conn)
    from backend import auth
    dong = dict.fromkeys(("users", "classes", "teacher_classes", "students", "subjects", "exams", "exam_codes", "answer_keys", "exam_students"), 0)
    mat_khau: dict[str, str] = {}
    tk: list[tuple[str, str, bool]] = []
    id_gv: dict[str, int | None] = {}

    for ten, vai in [(admin, "admin"), (gv[0], "teacher"), (gv[1], "teacher")]:
        r = conn.execute("SELECT user_id, role::text AS vai, is_active FROM users WHERE lower(username) = lower(%s)", (ten,)).fetchone()
        if r:
            if r["vai"] != vai or not r["is_active"]:
                dung(f"tài khoản '{ten}' đã có nhưng vai trò = {r['vai']}, hoạt động = {r['is_active']} (cần {vai}, đang hoạt động) – không sửa, hãy chọn tên khác.")
            tk.append((ten, vai, False))
            id_gv[ten] = r["user_id"]
            continue
        dong["users"] += 1
        tk.append((ten, vai, True))
        id_gv[ten] = None
        if ap_dung:
            mk = auth.mat_khau_ngau_nhien(MK_DO_DAI)
            conn.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, %s::user_role)",
                         (ten, f"{ten.lower()}@demo.invalid", auth.bam_mat_khau(mk), ten, vai))
            id_gv[ten] = conn.execute("SELECT user_id FROM users WHERE username = %s", (ten,)).fetchone()["user_id"]
            mat_khau[ten] = mk

    id_lop: dict[str, int | None] = {}
    for ma, ten_lop in LOP.items():
        r = conn.execute("SELECT class_id FROM classes WHERE class_code = %s", (ma,)).fetchone()
        if r:
            id_lop[ma] = r["class_id"]
            continue
        dong["classes"] += 1
        id_lop[ma] = (conn.execute("INSERT INTO classes (class_code, class_name, academic_year) VALUES (%s, %s, '2026-2027') RETURNING class_id",
                                   (ma, ten_lop)).fetchone()["class_id"] if ap_dung else None)

    for ten, ma in zip(gv, LOP_GV):
        if id_gv[ten] is not None and id_lop[ma] is not None:
            if conn.execute("SELECT 1 FROM teacher_classes WHERE user_id = %s AND class_id = %s", (id_gv[ten], id_lop[ma])).fetchone():
                continue
        dong["teacher_classes"] += 1
        if ap_dung:
            conn.execute("INSERT INTO teacher_classes (user_id, class_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (id_gv[ten], id_lop[ma]))

    id_sv: dict[str, int | None] = {}
    for ma, ten, lop in SINH_VIEN:
        r = conn.execute("SELECT student_id, full_name FROM students WHERE student_code = %s", (ma,)).fetchone()
        if r:
            if r["full_name"] != ten:
                dung(f"MSSV {ma} đã có trong CSDL với tên khác ('{r['full_name']}' ≠ '{ten}') – có thể là dữ liệu thật; công cụ KHÔNG ghi đè và không tiếp tục.")
            id_sv[ma] = r["student_id"]
            continue
        dong["students"] += 1
        id_sv[ma] = (conn.execute("INSERT INTO students (student_code, full_name, class_id) VALUES (%s, %s, %s) RETURNING student_id",
                                  (ma, ten, id_lop[lop])).fetchone()["student_id"] if ap_dung else None)

    for e in ke_hoach_ky_thi():
        cu = conn.execute("SELECT exam_id, created_by FROM exams WHERE exam_title = %s", (e["exam_title"],)).fetchall()
        if len(cu) > 1:
            dung(f"có {len(cu)} kỳ thi cùng tiêu đề '{e['exam_title']}'.")
        if cu and id_gv[gv[0]] is not None and cu[0]["created_by"] != id_gv[gv[0]]:
            dung(f"kỳ thi '{e['exam_title']}' đã có nhưng do người khác tạo – không đụng.")
        eid = cu[0]["exam_id"] if cu else None
        if eid is None:
            dong["exams"] += 1
            dong["exam_codes"] += len(e["codes"])
            dong["answer_keys"] += SO_CAU * len(e["codes"])
            dong["subjects"] += conn.execute("SELECT 1 FROM subjects WHERE subject_code = %s", (e["subject_code"],)).fetchone() is None
            if ap_dung:
                from backend import service
                eid = service.tao_ky_thi(conn, {"exam_title": e["exam_title"], "subject_code": e["subject_code"], "subject_name": e["subject_name"],
                                                "num_questions": SO_CAU, "max_score": THANG, "pass_score": DAT, "class_id": id_lop[LOP_GV[0]],
                                                "codes": e["codes"]}, id_gv[gv[0]])
        da = ({r["student_id"] for r in conn.execute("SELECT student_id FROM exam_students WHERE exam_id = %s", (eid,)).fetchall()} if eid else set())
        moi = [s for s in DU_THI if id_sv[s] is None or id_sv[s] not in da]
        dong["exam_students"] += len(moi)
        if ap_dung:
            with conn.cursor() as cur:
                cur.executemany("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", [(eid, id_sv[s]) for s in moi])
    return {"dong": dong, "mat_khau": mat_khau, "tai_khoan": tk}


def in_ke_hoach(admin: str, gv: list[str]) -> None:
    print("\nSINH VIÊN SẼ NẠP – TOÀN BỘ LÀ DỮ LIỆU GIẢ (MSSV = SBD in trên phiếu demo; họ tên bịa, lấy từ database/04_seed.sql):")
    print(f"  {'MSSV/SBD':<9} {'Họ tên':<20} {'Lớp':<10} Dự thi 3 kỳ")
    for ma, ten, lop in SINH_VIEN:
        print(f"  {ma:<9} {ten:<20} {lop:<10} {'có' if ma in DU_THI else 'KHÔNG (cố ý, phiếu BV10)'}")
    print("\nTÀI KHOẢN: " + f"{admin} (admin) · {gv[0]} (giáo viên, lớp CNTT-K22A, tạo 3 kỳ thi) · {gv[1]} (giáo viên, lớp CNTT-K22B) · KHÔNG có tài khoản sinh viên")
    print("KỲ THI: " + " · ".join(f"{td} (môn {mm}, {SO_CAU} câu, mã đề {', '.join(DAP_AN)}, 0 phiếu)" for _, td, mm, _ in BA_MON))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--admin", required=True, metavar="TEN", help="tên quản trị viên (tạo nếu chưa có)")
    ap.add_argument("--giao-vien", required=True, nargs=2, metavar=("GV1", "GV2"), help="tên 2 giáo viên demo (tạo nếu chưa có)")
    ap.add_argument("--xac-nhan", default=None, help=f"gõ đúng {XAC_NHAN} để GHI (không có = chỉ xem trước)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    loi = kiem_tham_so(a.admin, a.giao_vien)
    if loi:
        print("DỪNG: " + "; ".join(loi))
        return 2
    if a.xac_nhan is not None and a.xac_nhan != XAC_NHAN:
        print(f"DỪNG: --xac-nhan phải là {XAC_NHAN} – KHÔNG ghi gì.")
        return 1
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from backend.config import lay_database_url
    from backend.db import ket_noi
    ghi = a.xac_nhan == XAC_NHAN
    print("ĐÍCH NẠP:", muc_tieu(lay_database_url()))
    print("CHẾ ĐỘ:", "GHI THẬT (đã xác nhận)" if ghi else "XEM TRƯỚC (giao dịch chỉ đọc, không ghi gì)")
    in_ke_hoach(a.admin, a.giao_vien)
    with ket_noi() as conn:
        if not ghi:
            conn.execute("SET TRANSACTION READ ONLY")
        try:
            kq = nap(conn, a.admin, a.giao_vien, ghi)
        except LoiNap as e:
            conn.rollback()
            print(e)
            return 2
        if ghi:
            conn.commit()
        else:
            conn.rollback()
    moi = [t for t in kq["tai_khoan"] if t[2]]
    print("\nTÀI KHOẢN: " + (", ".join(f"{t[0]} ({t[1]})" for t in moi) + " – " + ("sẽ tạo" if not ghi else "đã tạo") if moi else "không tạo mới (đã có – giữ nguyên mật khẩu)"))
    print(("ĐÃ INSERT: " if ghi else "SẼ INSERT: ") + ", ".join(f"{k} {v}" for k, v in kq["dong"].items()) + "  (không UPDATE / DELETE nào)")
    if not ghi:
        print(f"Chưa ghi gì. Ghi thật: thêm --xac-nhan {XAC_NHAN}")
        return 0
    if kq["mat_khau"]:
        print("\n" + "=" * 70 + "\nMẬT KHẨU CHỈ HIỆN MỘT LẦN – chép vào nơi an toàn ngay (không lưu ở đâu khác):")
        for ten, mk in kq["mat_khau"].items():
            print(f"  {ten:<20} {mk}")
        print("=" * 70)
    else:
        print("Không có tài khoản mới nên không có mật khẩu để in (chạy lại không đổi gì).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
