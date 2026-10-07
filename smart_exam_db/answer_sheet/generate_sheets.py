"""
generate_sheets.py - Sinh phiếu trả lời PDF + trang thu chữ số + layout.json

Cài đặt:   pip install reportlab
Chạy:      python generate_sheets.py              # 40 phiếu đánh số + 10 trang chữ số
           python generate_sheets.py --count 60 --digit-pages 15

Đầu ra (thư mục output/):
  phieu_trang.pdf          1 phiếu trống (không mã phiếu) - dùng cho kỳ thi thật / in thêm
  phieu_danh_so.pdf        N phiếu, mỗi phiếu in "Mã phiếu: 0001..." - dùng để THU DỮ LIỆU
  trang_chu_so.pdf         trang thu chữ số viết tay (D001, D002...)
  layout.json              toạ độ pixel mọi ô (300 DPI) -> sheet_templates.layout_config
  digit_sheet_layout.json  toạ độ ô trên trang thu chữ số
  phieu_trang_300dpi.png   phieu_trang.pdf render 300 DPI, xám, cắt đúng page_px – MẪU ĐỊNH VỊ của cv_engine/omr.py
  phieu_trang_300dpi.json  SHA-256 điểm ảnh của PNG trên + phiên bản PyMuPDF (omr.py / pytest kiểm khi nạp)

Chỉ sinh lại PNG mẫu từ phieu_trang.pdf hiện có (không ghi lại PDF – PDF reportlab mỗi lần sinh khác byte do ngày giờ):
           python generate_sheets.py --chi-mau-png
"""
import argparse
import os

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import sheet_layout as L

HERE = os.path.dirname(os.path.abspath(__file__))
pdfmetrics.registerFont(TTFont("VN", os.path.join(HERE, "fonts", "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("VNB", os.path.join(HERE, "fonts", "DejaVuSans-Bold.ttf")))

GREY_TEXT = Color(0.55, 0.55, 0.55)      # chữ mờ trong bubble: đủ để người đọc, ít nhiễu cho OMR
LINE = Color(0.25, 0.25, 0.25)


def Y(y_mm):
    """Đổi toạ độ y (gốc trên-trái, mm) sang hệ reportlab (gốc dưới-trái, point)."""
    return (L.PAGE_H_MM - y_mm) * mm


def text(c, x, y, s, size=9, font="VN", align="left", color=black):
    c.setFillColor(color)
    c.setFont(font, size)
    fn = {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align]
    fn(x * mm, Y(y), s)


def rect(c, x, y, w, h, lw=0.6, fill=False, color=LINE):
    c.setLineWidth(lw)
    c.setStrokeColor(color)
    c.setFillColor(black)
    c.rect(x * mm, Y(y + h), w * mm, h * mm, stroke=1, fill=1 if fill else 0)


def bubble(c, cx, cy, d, label=None):
    c.setLineWidth(0.7)
    c.setStrokeColor(LINE)
    c.setFillColor(white)
    c.circle(cx * mm, Y(cy), d / 2 * mm, stroke=1, fill=1)
    if label is not None:
        text(c, cx, cy + d * 0.23, label, size=d * 1.45, align="center", color=GREY_TEXT)


def draw_markers(c):
    s = L.MARKER_SIZE_MM
    for cx, cy in L.MARKER_CENTERS_MM.values():
        rect(c, cx - s / 2, cy - s / 2, s, s, lw=0, fill=True, color=black)


def draw_digit_field(c, title, first_x, n):
    p = L.DIGIT_COL_PITCH_MM
    x_left = first_x - p / 2 - 5.5          # chừa chỗ cho nhãn 0-9
    x_right = first_x + (n - 1) * p + p / 2 + 1
    rect(c, x_left, 45.5, x_right - x_left, 80.5, lw=0.8)
    text(c, (x_left + x_right) / 2, 50, title, size=8, font="VNB", align="center")
    for col in range(n):
        cx = L.digit_col_x(first_x, col)
        rect(c, cx - L.DIGIT_BOX_W_MM / 2, L.DIGIT_BOX_TOP_MM, L.DIGIT_BOX_W_MM, L.DIGIT_BOX_H_MM, lw=0.8)
        for d in range(10):
            bubble(c, cx, L.digit_bubble_y(d), L.DIGIT_BUBBLE_D_MM, str(d))
    for d in range(10):
        text(c, x_left + 2.2, L.digit_bubble_y(d) + 1.1, str(d), size=7, align="center")


def draw_instructions(c):
    x0, y0, w, h = 18, 45.5, 72, 80.5
    rect(c, x0, y0, w, h, lw=0.8)
    text(c, x0 + w / 2, 50.5, "HƯỚNG DẪN", size=9, font="VNB", align="center")
    lines = [
        "1. Dùng bút chì 2B hoặc bút bi xanh/đen.",
        "2. Viết SBD và mã đề vào các ô vuông,",
        "   mỗi ô MỘT chữ số, viết rõ, không chạm viền.",
        "3. Tô ô tròn tương ứng với từng chữ số bên dưới.",
        "4. Mỗi câu chỉ tô MỘT phương án.",
        "5. Tô KÍN hoàn toàn ô tròn.",
        "6. Không gấp, làm bẩn 4 ô vuông đen ở góc phiếu.",
    ]
    for i, s in enumerate(lines):
        text(c, x0 + 3, 57 + i * 5.2, s, size=7.2)
    y = 100
    text(c, x0 + 3, y, "Cách tô:", size=7.5, font="VNB")
    text(c, x0 + 3, y + 7, "Đúng", size=7.5)
    c.setFillColor(black)
    c.circle((x0 + 17) * mm, Y(y + 5.8), 2.5 * mm, stroke=0, fill=1)
    text(c, x0 + 3, y + 16, "Sai", size=7.5)
    for i, kind in enumerate(["tick", "cross", "half", "dot"]):
        cx, cy = x0 + 17 + i * 11, y + 14.8
        c.setFillColor(white)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.7)
        c.circle(cx * mm, Y(cy), 2.5 * mm, stroke=1, fill=0)
        c.setLineWidth(1.1)
        c.setStrokeColor(black)
        if kind == "tick":
            c.line((cx - 1.6) * mm, Y(cy), (cx - 0.4) * mm, Y(cy + 1.4))
            c.line((cx - 0.4) * mm, Y(cy + 1.4), (cx + 1.8) * mm, Y(cy - 1.8))
        elif kind == "cross":
            c.line((cx - 1.7) * mm, Y(cy - 1.7), (cx + 1.7) * mm, Y(cy + 1.7))
            c.line((cx - 1.7) * mm, Y(cy + 1.7), (cx + 1.7) * mm, Y(cy - 1.7))
        elif kind == "half":
            p = c.beginPath()
            p.moveTo(cx * mm, Y(cy - 2.5))
            p.arcTo((cx - 2.5) * mm, Y(cy - 2.5), (cx + 2.5) * mm, Y(cy + 2.5), startAng=90, extent=180)
            p.close()
            c.setFillColor(black)
            c.drawPath(p, stroke=0, fill=1)
        else:
            c.setFillColor(black)
            c.circle(cx * mm, Y(cy), 0.8 * mm, stroke=0, fill=1)


def draw_answer_area(c):
    rect(c, 17, 133, 176, 124, lw=0.8)
    text(c, 105, 138.5, "PHẦN TRẢ LỜI", size=9, font="VNB", align="center")
    for g in range(L.ANSWER_GROUPS):
        gx = L.GROUP_X0_MM + g * L.GROUP_PITCH_MM
        for i, opt in enumerate(L.OPTIONS):
            text(c, gx + L.OPTION_FIRST_OFFSET_MM + i * L.OPTION_PITCH_MM, 145.2, opt,
                 size=8, font="VNB", align="center")
        if g > 0:
            c.setStrokeColor(Color(0.7, 0.7, 0.7))
            c.setLineWidth(0.4)
            c.line((gx - 3) * mm, Y(142), (gx - 3) * mm, Y(255))
    for q in range(1, L.NUM_QUESTIONS + 1):
        g, r = L.question_pos(q)
        gx = L.GROUP_X0_MM + g * L.GROUP_PITCH_MM
        y = L.ANSWER_ROW_TOP_MM + r * L.ANSWER_ROW_PITCH_MM
        text(c, gx + 8, y + 1.2, str(q), size=8.5, font="VNB", align="right")
        for i, opt in enumerate(L.OPTIONS):
            bubble(c, *L.answer_bubble_center(q, i), L.ANSWER_BUBBLE_D_MM, opt)


def draw_answer_sheet(c, sheet_code=None):
    draw_markers(c)
    text(c, 105, 22, "PHIẾU TRẢ LỜI TRẮC NGHIỆM", size=13, font="VNB", align="center")
    if sheet_code:
        text(c, 188, 27.5, f"Mã phiếu: {sheet_code}", size=8, font="VNB", align="right")
    text(c, 22, 33, "Họ và tên: ................................................................", size=9)
    text(c, 130, 33, "Lớp: ......................................", size=9)
    text(c, 22, 40, "Môn thi: ...................................................................", size=9)
    text(c, 130, 40, "Ngày thi: ..................................", size=9)
    draw_instructions(c)
    draw_digit_field(c, "SỐ BÁO DANH", L.SBD_FIRST_COL_X_MM, L.SBD_DIGITS)
    draw_digit_field(c, "MÃ ĐỀ", L.EXAM_CODE_FIRST_COL_X_MM, L.EXAM_CODE_DIGITS)
    draw_answer_area(c)
    text(c, 50, 266, "Chữ ký thí sinh", size=8, align="center")
    text(c, 160, 266, "Chữ ký giám thị", size=8, align="center")
    c.showPage()


def draw_digit_page(c, page_code):
    draw_markers(c)
    text(c, 105, 22, "TRANG THU THẬP CHỮ SỐ VIẾT TAY", size=13, font="VNB", align="center")
    text(c, 188, 27.5, f"Mã trang: {page_code}", size=8, font="VNB", align="right")
    text(c, 22, 33, "Người viết (tên/viết tắt): ...............................    "
                    "Bút: □ chì  □ bi xanh  □ bi đen", size=8.5)
    text(c, 22, 40, "Mỗi hàng: viết lặp lại ĐÚNG chữ số in đậm ở đầu hàng, mỗi ô một chữ số, "
                    "viết tự nhiên như khi ghi SBD.", size=7.5)
    for d in range(10):
        for s in range(L.DS_ROWS_PER_DIGIT):
            x0, y0 = L.digit_sheet_box(d, s, 0)
            text(c, 25, y0 + 6.5, str(d), size=13, font="VNB", align="center")
            for col in range(L.DS_BOXES_PER_ROW):
                x, y = L.digit_sheet_box(d, s, col)
                rect(c, x, y, L.DIGIT_BOX_W_MM, L.DIGIT_BOX_H_MM, lw=0.8)
    c.showPage()


def write_update_sql(path):
    """SQL ghi layout.json vào bảng sheet_templates (database smart_exam)."""
    import json
    lay = L.build_layout()
    with open(path, "w", encoding="utf-8") as f:
        f.write("-- Cập nhật mẫu phiếu theo layout.json (tự sinh bởi generate_sheets.py)\n"
                "-- psql -U smart_exam_app -h localhost -d smart_exam -f output/update_template.sql\n"
                f"UPDATE sheet_templates SET num_questions = {L.NUM_QUESTIONS}, "
                f"options_per_question = {len(L.OPTIONS)}, sbd_digits = {L.SBD_DIGITS}, "
                f"exam_code_digits = {L.EXAM_CODE_DIGITS}, page_width_px = {L.PAGE_W_PX}, "
                f"page_height_px = {L.PAGE_H_PX}, pdf_path = 'answer_sheet/output/phieu_trang.pdf',\n"
                f"  layout_config = $json${json.dumps(lay, ensure_ascii=False)}$json$::jsonb\n"
                f"WHERE template_name = '{lay['template_name']}';\n")


def write_template_png(pdf_path, png_path):
    """Mẫu phiếu trắng cho định vị OMR (Tuần 5): render 300 DPI xám, cắt về page_px (PyMuPDF làm tròn ra 2481 px rộng).
    Ghi kèm <png>.json: SHA-256 điểm ảnh (không phải SHA file PNG – nén PNG có thể khác giữa các phiên bản OpenCV)."""
    import hashlib
    import json

    import cv2
    import numpy as np
    import pymupdf

    page = pymupdf.open(pdf_path)[0]
    pix = page.get_pixmap(dpi=L.DPI, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
    img = np.ascontiguousarray(img[:L.PAGE_H_PX, :L.PAGE_W_PX])
    if img.shape != (L.PAGE_H_PX, L.PAGE_W_PX):
        raise RuntimeError(f"PNG mẫu sai cỡ {img.shape}, cần {(L.PAGE_H_PX, L.PAGE_W_PX)}")
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("không mã hoá được PNG mẫu")
    buf.tofile(png_path)
    meta = {"nguon": os.path.basename(pdf_path), "dpi": L.DPI, "cao_rong": list(img.shape),
            "sha256_diem_anh": hashlib.sha256(img.tobytes()).hexdigest(), "pymupdf": pymupdf.__version__}
    with open(os.path.splitext(png_path)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40, help="số phiếu đánh số để thu dữ liệu")
    ap.add_argument("--digit-pages", type=int, default=10, help="số trang thu chữ số")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--chi-mau-png", action="store_true",
                    help="chỉ sinh lại phieu_trang_300dpi.png (+ .json) từ phieu_trang.pdf hiện có, không ghi lại PDF")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    png = os.path.join(a.out, "phieu_trang_300dpi.png")
    if a.chi_mau_png:
        meta = write_template_png(os.path.join(a.out, "phieu_trang.pdf"), png)
        print(f"Đã tạo {png} (SHA-256 điểm ảnh {meta['sha256_diem_anh'][:16]}…)")
        return

    c = canvas.Canvas(os.path.join(a.out, "phieu_trang.pdf"), pagesize=A4)
    c.setTitle("Phiếu trả lời trắc nghiệm - mẫu trống")
    draw_answer_sheet(c)
    c.save()

    c = canvas.Canvas(os.path.join(a.out, "phieu_danh_so.pdf"), pagesize=A4)
    c.setTitle("Phiếu trả lời - bộ thu dữ liệu")
    for i in range(1, a.count + 1):
        draw_answer_sheet(c, f"{i:04d}")
    c.save()

    c = canvas.Canvas(os.path.join(a.out, "trang_chu_so.pdf"), pagesize=A4)
    c.setTitle("Trang thu chữ số viết tay")
    for i in range(1, a.digit_pages + 1):
        draw_digit_page(c, f"D{i:03d}")
    c.save()

    L.export_layout(os.path.join(a.out, "layout.json"), os.path.join(a.out, "digit_sheet_layout.json"))
    write_update_sql(os.path.join(a.out, "update_template.sql"))
    write_template_png(os.path.join(a.out, "phieu_trang.pdf"), png)
    print(f"Đã tạo trong {a.out}: phieu_trang.pdf, phieu_danh_so.pdf ({a.count} phiếu), "
          f"trang_chu_so.pdf ({a.digit_pages} trang), layout.json, digit_sheet_layout.json, phieu_trang_300dpi.png")


if __name__ == "__main__":
    main()
