import io
from pathlib import Path
from urllib.parse import urlsplit

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .service import KhongTimThay

FONT_DIR = Path(__file__).resolve().parent.parent / "answer_sheet" / "fonts"
MAY_CUC_BO = ("localhost", "127.0.0.1", "::1", "0.0.0.0", "testserver")
NHAN_TRANG_THAI = {"closed": "ĐÃ ĐÓNG – không nhận ảnh mới"}


def dia_chi_goc(public_base_url: str, base_url_yeu_cau: str) -> str:
    return (public_base_url or str(base_url_yeu_cau)).rstrip("/")


def url_ky_thi(goc: str, exam_id: int) -> str:
    return f"{goc}/m?kythi={int(exam_id)}"


def la_may_cuc_bo(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() in MAY_CUC_BO


def thong_tin(conn, exam_id: int) -> dict:
    e = conn.execute(
        "SELECT e.exam_id, e.exam_title, e.exam_date, e.num_questions, e.status::text AS status, sj.subject_code, sj.subject_name, "
        "c.class_code, c.class_name, u.full_name AS teacher_name, u.username AS teacher_username, "
        "(SELECT string_agg(ec.code, ', ' ORDER BY ec.code) FROM exam_codes ec WHERE ec.exam_id = e.exam_id) AS ma_de "
        "FROM exams e JOIN subjects sj ON sj.subject_id = e.subject_id LEFT JOIN classes c ON c.class_id = e.class_id "
        "JOIN users u ON u.user_id = e.created_by WHERE e.exam_id = %s", (exam_id,)).fetchone()
    if not e:
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    return e


_DA_DANG_KY = False


def _font() -> tuple[str, str]:
    global _DA_DANG_KY
    if not _DA_DANG_KY:
        pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
        _DA_DANG_KY = True
    return "DejaVu", "DejaVu-Bold"


def _dong(c: canvas.Canvas, chu: str, font: str, co: float, x: float, y: float, rong: float) -> float:
    tu, dong = chu.split(), ""
    for t in tu:
        thu = f"{dong} {t}".strip()
        if pdfmetrics.stringWidth(thu, font, co) > rong and dong:
            c.setFont(font, co)
            c.drawString(x, y, dong)
            y -= co * 1.35
            dong = t
        else:
            dong = thu
    if dong:
        c.setFont(font, co)
        c.drawString(x, y, dong)
        y -= co * 1.35
    return y


def tao_pdf(tt: dict, url: str) -> bytes:
    thuong, dam = _font()
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    c.setTitle(f"Trang bìa kỳ thi {tt['exam_id']}")
    w, h = A4
    le, rong = 20 * mm, w - 40 * mm
    y = h - 25 * mm
    c.setFont(dam, 12)
    c.drawString(le, y, "SMART EXAM – TRANG BÌA KỲ THI")
    c.setFont(thuong, 9)
    c.drawRightString(w - le, y, "Kẹp trang này lên trên xấp phiếu trả lời")
    c.line(le, y - 4 * mm, w - le, y - 4 * mm)
    y -= 16 * mm
    y = _dong(c, tt["exam_title"], dam, 20, le, y, rong)
    y -= 2 * mm
    c.setFont(dam, 30)
    c.drawString(le, y - 8 * mm, f"Mã kỳ thi: {tt['exam_id']}")
    y -= 20 * mm
    dong = [("Môn", f"{tt['subject_code']} – {tt['subject_name']}"),
            ("Lớp", f"{tt['class_code']} – {tt['class_name']}" if tt["class_code"] else "(không gắn lớp)"),
            ("Ngày thi", tt["exam_date"].strftime("%d/%m/%Y") if tt["exam_date"] else "(chưa đặt)"),
            ("Giáo viên phụ trách", f"{tt['teacher_name']} ({tt['teacher_username']})"),
            ("Số câu · mã đề", f"{tt['num_questions']} câu · mã đề {tt['ma_de'] or '–'}")]
    if tt["status"] in NHAN_TRANG_THAI:
        dong.append(("Trạng thái", NHAN_TRANG_THAI[tt["status"]]))
    for nhan, gia_tri in dong:
        c.setFont(thuong, 12)
        c.drawString(le, y, f"{nhan}:")
        y = _dong(c, gia_tri, dam, 12, le + 45 * mm, y, rong - 45 * mm) - 1.5 * mm
    canh = 75 * mm
    qr = QrCodeWidget(url, barLevel="M")
    x0, y0, x1, y1 = qr.getBounds()
    d = Drawing(canh, canh, transform=[canh / (x1 - x0), 0, 0, canh / (y1 - y0), 0, 0])
    d.add(qr)
    y_qr = y - canh - 8 * mm
    renderPDF.draw(d, c, (w - canh) / 2, y_qr)
    c.setFont(thuong, 11)
    c.drawCentredString(w / 2, y_qr - 6 * mm, url)
    y = y_qr - 16 * mm
    huong_dan = ["Cách chụp phiếu cho đúng kỳ thi này:",
                 "1. Điện thoại quét mã QR (camera hoặc ứng dụng quét mã) → mở trang chụp phiếu.",
                 "2. Đăng nhập bằng tài khoản giáo viên → kỳ thi này được chọn sẵn, tên hiện ở đầu trang.",
                 "3. Kiểm tra tên kỳ thi ở đầu trang rồi chụp lần lượt từng phiếu trong xấp.",
                 "Ảnh luôn gắn vào kỳ thi đang chọn – hệ thống không tự đoán kỳ thi từ nội dung phiếu."]
    for i, s in enumerate(huong_dan):
        y = _dong(c, s, dam if i == 0 else thuong, 11, le, y, rong)
    if la_may_cuc_bo(url):
        c.setFillColorRGB(0.75, 0, 0)
        _dong(c, "CẢNH BÁO: địa chỉ trên trỏ về chính máy chủ (localhost) – điện thoại KHÔNG mở được. Đặt PUBLIC_BASE_URL "
                 "(vd http://<IP-LAN>:8000) hoặc mở trang quản lý bằng địa chỉ mạng nội bộ rồi in lại.", dam, 10, le, y - 2 * mm, rong)
        c.setFillColorRGB(0, 0, 0)
    c.setFont(thuong, 8)
    c.drawString(le, 12 * mm, "Trang bìa không chứa đáp án. Mã QR chỉ mở trang chụp phiếu – vẫn phải đăng nhập và có quyền với kỳ thi.")
    c.showPage()
    c.save()
    return b.getvalue()
