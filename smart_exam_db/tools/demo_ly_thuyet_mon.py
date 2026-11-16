"""
demo_ly_thuyet_mon.py - Lệnh AP: trang "LÝ THUYẾT CÁC MÔN" cho buổi demo đồ án chuyên ngành: ánh xạ TÍNH NĂNG THẬT của hệ thống sang kiến thức từng môn học.

  python tools/demo_ly_thuyet_mon.py --ra data/_eval/demo_3_phien/ly_thuyet_cac_mon.html

GIẢ ĐỊNH (ghi cả trên trang): chưa biết nhóm đã học những môn nào, nên danh sách môn được SUY RA từ chính hệ thống (cơ sở dữ liệu, lập trình web / API,
an toàn thông tin, kiểm thử phần mềm, phân tích thiết kế, xử lý ảnh, học máy). Môn nào nhóm chưa học thì bỏ mục đó khi trình bày.
Mọi khẳng định về hệ thống đều có nguồn trong mã / tài liệu của repo; số đếm (số bảng, số đường dẫn API) được đếm lúc dựng trang nếu có thể
(không có CSDL / không import được backend thì ghi "chưa đếm được", KHÔNG điền số bịa). Trang tự chứa, không tải gì từ mạng.
"""
import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAU_CSS = ROOT / "frontend" / "mau.css"


def e(s) -> str:
    return html.escape(str(s))


def dem_thong_so() -> dict:
    """Số liệu đếm lúc dựng trang; mỗi số tự None nếu không đếm được (không bịa)."""
    kq = {"so_duong_dan_api": None, "so_bang": None, "so_view": None}
    try:
        import os
        os.environ.setdefault("AUTH_MODE", "demo")
        from backend.main import app
        kq["so_duong_dan_api"] = len({(r.path, m) for r in app.routes if getattr(r, "methods", None) for m in r.methods if m not in ("HEAD", "OPTIONS")})
    except Exception:                                                                    # noqa: BLE001 – chỉ để bỏ qua số đếm
        pass
    try:
        from backend.db import ket_noi
        with ket_noi() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            kq["so_bang"] = conn.execute("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'").fetchone()["n"]
            kq["so_view"] = conn.execute("SELECT count(*) AS n FROM information_schema.views WHERE table_schema = 'public'").fetchone()["n"]
            conn.rollback()
    except Exception:                                                                    # noqa: BLE001
        pass
    return kq


def so(v, mac_dinh="chưa đếm được") -> str:
    return str(v) if v is not None else mac_dinh


def mon(tieu_de: str, y: str, hang: list[tuple[str, str, str]]) -> str:
    h = "".join(f"<tr><td class='trai'><b>{e(a)}</b></td><td class='trai'>{b}</td><td class='trai'>{c}</td></tr>" for a, b, c in hang)
    return (f"<section><h2>{e(tieu_de)}</h2><p class='mut'>{y}</p><div class='cuon'><table><tr><th>Kiến thức trong môn</th><th>Ở đâu trong hệ thống (thật)</th><th>Chỉ trong demo / tệp</th></tr>{h}</table></div></section>")


def dung_trang(ts: dict | None = None) -> str:
    ts = ts or dem_thong_so()
    css = MAU_CSS.read_text(encoding="utf-8") if MAU_CSS.exists() else ""
    cac_mon = [
        mon("1. Cơ sở dữ liệu", "Thiết kế lược đồ, ràng buộc, giao dịch, truy vấn, sao lưu.", [
            ("Mô hình quan hệ, khoá ngoại, CHECK, ENUM", f"PostgreSQL 17, {so(ts['so_bang'])} bảng trong lược đồ public (20 bảng thiết kế ban đầu + bảng thêm bởi migration, vd. <code>admin_audit_log</code>; 10 kiểu ENUM) – người dùng, lớp, đề thi, nhận diện, kết quả", "<code>database/01_schema.sql</code>; <code>docs/ERD.png</code>"),
            ("Chỉ mục duy nhất = luật nghiệp vụ", "mỗi thí sinh chỉ một điểm chính thức mỗi kỳ thi: chỉ mục <code>uq_results_exam_student</code>; hai người cùng ghi → bên thua nhận 409 (đã đo ở lệnh AH, 0/40 lần có hai điểm)", "tải cùng một SBD hai lần ở kỳ [ĐACN]"),
            ("Hàm, trigger, view", f"<code>fn_grade_sheet</code> (chấm), trigger ghi nhật ký sửa điểm (<code>score_audit_logs</code>), {so(ts['so_view'], '8 (thiết kế)')} view báo cáo (điểm, phân bố, độ khó câu)", "<code>database/02_functions_triggers.sql</code>, <code>03_views.sql</code>"),
            ("Giao dịch (ACID), ROLLBACK", "mỗi lần chấm / duyệt / thay phiếu trùng là MỘT giao dịch; test chạy trong giao dịch ROLLBACK nên không để lại dữ liệu", "<code>tests/conftest.py</code>; <code>tools/dat_lai_demo.py</code> (xoá trong một giao dịch, lệch số dòng thì hoàn tác)"),
            ("Migration, sao lưu, phục hồi", "migration 001–005 chỉ THÊM cột / bảng, chạy lại an toàn; sao lưu CSV + ảnh trước mọi lần xoá", "<code>backend/migrations/</code>; <code>data/_eval/sao_luu_don_du_lieu/</code>"),
            ("Ảnh lưu đĩa, CSDL lưu đường dẫn", "tránh phình CSDL; dọn ảnh tạm theo hạn giữ (mặc định tắt)", "<code>backend/don_anh.py</code>")]),
        mon("2. Lập trình web / API", "REST, tách frontend – backend, định dạng dữ liệu, mã lỗi HTTP.", [
            ("API REST, JSON, mã trạng thái", f"FastAPI + uvicorn, {so(ts['so_duong_dan_api'])} cặp (đường dẫn, phương thức); lỗi dùng đúng mã: 401 chưa đăng nhập, 404 ngoài quyền, 409 xung đột, 422 dữ liệu sai", "<code>/docs</code> (Swagger) khi server chạy"),
            ("Kiểm tra dữ liệu vào (schema)", "mô hình pydantic cho mọi yêu cầu / phản hồi; ảnh tải lên bị từ chối có mã lý do + lời khuyên chụp lại", "<code>backend/schemas.py</code>; <code>GET /meta/reject-reasons</code>"),
            ("Frontend HTML + JS thuần", "một trang quản lý (<code>/app/</code>) và một trang điện thoại (<code>/m</code>, camera gốc, chụp liên tục, gửi lại khi rớt mạng)", "<code>frontend/</code>"),
            ("Xử lý bất đồng bộ phía trình duyệt", "hàng đợi tải ảnh tối đa 2 lượt song song, phân biệt lỗi mạng (gửi lại) và bị từ chối (không gửi lại)", "<code>frontend/m_hang_doi.js</code>; <code>frontend/loi_tai.js</code>"),
            ("Xuất báo cáo", "bảng điểm Excel hai sheet, trang bìa PDF có mã QR", "<code>GET /exams/{id}/export.xlsx</code>, <code>/exams/{id}/cover.pdf</code>")]),
        mon("3. An toàn thông tin / bảo mật ứng dụng", "Xác thực, phân quyền, lưu mật khẩu, nhật ký, giảm thiểu rò rỉ.", [
            ("Lưu mật khẩu an toàn", "băm bằng scrypt có muối; không có mật khẩu trong mã nguồn; mật khẩu nhập bằng getpass khi tạo tài khoản", "<code>python -m backend.tai_khoan</code>"),
            ("Phiên và cookie", "cookie <code>se_session</code> HttpOnly + SameSite=Lax (hoặc Bearer); hạn phiên cấu hình được", "<code>docs/thiet_ke_dang_nhap.md</code>"),
            ("Chống dò mật khẩu", "5 lần sai trong 15 phút → 429, khoá theo (tên, IP) nên người khác cùng IP không bị khoá; mọi lỗi đăng nhập cùng một thông báo (không lộ tài khoản có tồn tại)", "đăng nhập sai nhiều lần ở demo (cẩn thận bị khoá)"),
            ("Phân quyền theo vai trò và theo lớp", "admin / teacher / student; giáo viên chỉ thấy kỳ thi của lớp mình; ngoài quyền trả 404 như không tồn tại (không lộ sự có mặt)", "đăng nhập gv_binh rồi mở kỳ thi của gv_an → 404"),
            ("Nhật ký quản trị", "bảng <code>admin_audit_log</code> chỉ ghi thao tác thành công, không ghi mật khẩu", "Quản trị → Nhật ký"),
            ("Dữ liệu riêng tư", "SBD là số ngẫu nhiên, không dùng tên / MSSV thật; ảnh phiếu xoá theo hạn giữ", "<code>CLAUDE.md</code> mục 4")]),
        mon("4. Kiểm thử và đảm bảo chất lượng phần mềm", "Kiểm thử đơn vị / tích hợp, tiêu chí đặt trước, hồi quy.", [
            ("Kiểm thử tự động", "pytest (571 đạt, 1 bỏ qua có chủ đích tại 16/11/2026) + kiểm thử JavaScript bằng Node; test API chạy trên CSDL thật trong giao dịch ROLLBACK", "<code>python -m pytest tests</code>"),
            ("Kiểm thử đầu-cuối và âm tính", "56 ảnh dev qua backend thật: 0 câu chấm sai mà không gắn “cần xem”; có cả ca ép lỗi (ảnh giả, thiếu marker, trùng SBD)", "<code>tools/kiem_backend_dau_cuoi.py</code>"),
            ("Tiêu chí đặt TRƯỚC, đo SAU", "mọi so sánh (CNN, thuật toán, thay mô hình) viết tiêu chí rồi commit trước khi đo; tập test chỉ mở một lần", "<code>docs/tieu_chi_*.md</code>"),
            ("Quản lý cấu hình / phiên bản", "git theo nhánh, commit nhỏ có mô tả; SHA mô hình ghim và kiểm trước demo", "<code>tools/kiem_truoc_demo.py</code>")]),
        mon("5. Phân tích thiết kế hệ thống", "Use case, DFD, trình tự, ERD, quyết định thiết kế.", [
            ("Sơ đồ", "use case, kiến trúc, DFD mức 0 và 1, trình tự chấm / duyệt / import, ERD 20 bảng, 6 wireframe", "<code>docs/diagrams/</code>, <code>docs/wireframes/</code>"),
            ("Quyết định thiết kế có lý do", "mọi toạ độ phiếu chỉ ở một tệp (<code>sheet_layout.py</code>) → PDF, JSON, SQL luôn khớp; hai kênh SBD để tránh ghi nhầm điểm", "<code>CLAUDE.md</code> mục 4")]),
        mon("6. Xử lý ảnh / thị giác máy tính", "Biến đổi hình học, ngưỡng, lọc, phát hiện đặc trưng.", [
            ("Phát hiện 4 ô vuông đen, biến đổi phối cảnh (homography)", "nắn ảnh chụp nghiêng về A4 chuẩn 2480×3508 @300 DPI", "chế độ <code>xla</code> bước 3–4"),
            ("Chuẩn hoá ánh sáng", "chia ảnh cho nền ước lượng (cửa sổ ≈ 15 mm) để bỏ bóng đổ", "chế độ <code>xla</code> bước 4b"),
            ("Đo độ nét, từ chối ảnh xấu", "đo độ mờ theo hướng; quá ngưỡng thì từ chối kèm mã lý do (nắn sai mà vẫn chấm là lỗi nguy hiểm nhất)", "chế độ <code>xla</code> bước 2"),
            ("OMR: đo độ đậm ô tô, dò lại từng hàng", "đặc trưng độ tối của ô + dò lại vị trí từng hàng chịu giấy cong 2–3 mm", "chế độ <code>xla</code> bước 5–6")]),
        mon("7. Học máy / trí tuệ nhân tạo", "Phân loại, đánh giá, quá khớp, hiệu chỉnh xác suất.", [
            ("Hồi quy logistic (ô tô) và CNN (chữ số)", "M1 40 tham số; CNN sâu 467 818 tham số chạy bằng NumPy", "chế độ <code>ml</code>"),
            ("Chia dữ liệu, tránh rò rỉ", "chia theo MÃ PHIẾU và theo NGƯỜI VIẾT; test chỉ mở một lần", "chế độ <code>ml</code> mục dữ liệu"),
            ("So sánh thuật toán, kiểm định", "11 thuật toán cùng giao thức; chênh nhỏ giữa mạng tích chập chưa chắc có ý nghĩa vì chỉ 5 người viết", "chế độ <code>ml</code> mục 11 thuật toán"),
            ("Kết quả âm tính", "thêm 300 000 mẫu chỉ +0,36 điểm → không dùng", "chế độ <code>ml</code> mục “không đạt”")]),
    ]
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lý thuyết các môn – đồ án</title>
<style>{css}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Segoe UI",system-ui,sans-serif}} main{{max-width:1100px;margin:0 auto;padding:20px 16px 60px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:21px;margin:0 0 6px}} section{{background:var(--card);border:1px solid var(--line);border-radius:var(--r-lon);box-shadow:var(--bong);padding:16px 22px;margin:16px 0}}
.mut{{color:var(--mut)}} table{{border-collapse:collapse;width:100%;font-size:15px}} th,td{{border:1px solid var(--line);padding:6px 9px;vertical-align:top}} th{{background:var(--th)}} td.trai{{text-align:left}} .cuon{{overflow-x:auto}}
code{{background:var(--xam-nen);padding:1px 5px;border-radius:4px;font-size:14px}} .canh-bao{{border-left:6px solid var(--warn-vien);background:var(--warnbg);border-radius:var(--r-nho);padding:10px 16px;margin:12px 0}}
</style></head><body><main><h1>Lý thuyết các môn trong đồ án</h1>
<p class="mut">Mỗi dòng nối một kiến thức trong môn với một chỗ có thật trong hệ thống và một cách chỉ ra trong buổi demo. Số đếm ở trang này được đếm lúc dựng trang.</p>
<div class="canh-bao"><b>GIẢ ĐỊNH:</b> chưa biết nhóm đã học những môn nào. Danh sách 7 môn dưới đây được <b>suy ra từ chính hệ thống</b> (cơ sở dữ liệu, lập trình web / API, an toàn thông tin, kiểm thử, phân tích thiết kế, xử lý ảnh, học máy).
Môn nào nhóm chưa học thì bỏ mục đó khi trình bày; tên môn thật có thể khác tên ở đây.</div>
{''.join(cac_mon)}
<p class="mut">Sinh bởi <code>tools/demo_ly_thuyet_mon.py</code> (lệnh AP). Không ghi CSDL.</p></main></body></html>"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Dựng trang lý thuyết các môn (chỉ đọc).")
    ap.add_argument("--ra", type=Path, default=ROOT / "data" / "_eval" / "demo_3_phien" / "ly_thuyet_cac_mon.html")
    a = ap.parse_args()
    a.ra.parent.mkdir(parents=True, exist_ok=True)
    a.ra.write_text(dung_trang(), encoding="utf-8")
    print(f"Đã ghi {a.ra}")


if __name__ == "__main__":
    main()
