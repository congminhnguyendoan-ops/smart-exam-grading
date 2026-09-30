"""
sheet_layout.py - NGUỒN SỰ THẬT DUY NHẤT về hình học của phiếu trả lời.

Mọi toạ độ được định nghĩa bằng milimét (gốc ở GÓC TRÊN-TRÁI trang A4 210x297mm).
- generate_sheets.py dùng file này để VẼ phiếu PDF.
- export_layout() xuất ra layout.json bằng PIXEL ở 300 DPI (ảnh chuẩn 2480x3508),
  đây chính là nội dung cột sheet_templates.layout_config trong database.
- Module OpenCV (Tuần 4-5) đọc layout.json để biết ô nào nằm ở đâu sau khi nắn ảnh.

=> Muốn đổi bố cục phiếu: chỉ sửa các hằng số ở đây rồi chạy lại generate_sheets.py.
"""
import json

# ----------------------------- Trang & độ phân giải -----------------------------
PAGE_W_MM, PAGE_H_MM = 210.0, 297.0
DPI = 300
PX_PER_MM = DPI / 25.4                       # 11.811 px / mm
PAGE_W_PX = round(PAGE_W_MM * PX_PER_MM)     # 2480
PAGE_H_PX = round(PAGE_H_MM * PX_PER_MM)     # 3508

# ----------------------------- 4 marker góc -------------------------------------
# Hình vuông đen đặc, dùng để tìm 4 góc và nắn phối cảnh (perspective transform).
MARKER_SIZE_MM = 8.0
MARKER_CENTERS_MM = {           # thứ tự: TL, TR, BR, BL (chiều kim đồng hồ)
    "tl": (14.0, 14.0),
    "tr": (196.0, 14.0),
    "br": (196.0, 283.0),
    "bl": (14.0, 283.0),
}

# ----------------------------- Vùng SBD & mã đề ---------------------------------
DIGIT_COL_PITCH_MM = 7.0        # khoảng cách giữa 2 cột chữ số
DIGIT_BOX_W_MM, DIGIT_BOX_H_MM = 6.0, 9.0      # ô viết tay 1 chữ số (dữ liệu cho OCR)
DIGIT_BOX_TOP_MM = 53.0
DIGIT_BUBBLE_TOP_MM = 68.0      # tâm bubble của chữ số 0
DIGIT_BUBBLE_PITCH_MM = 5.8     # khoảng cách dọc giữa bubble 0..9
DIGIT_BUBBLE_D_MM = 4.4

SBD_DIGITS = 6
SBD_FIRST_COL_X_MM = 104.0      # tâm cột chữ số đầu tiên của SBD
EXAM_CODE_DIGITS = 3
EXAM_CODE_FIRST_COL_X_MM = 159.0

# ----------------------------- Vùng trả lời -------------------------------------
NUM_QUESTIONS = 40
OPTIONS = ["A", "B", "C", "D"]
ANSWER_GROUPS = 4               # 4 cột, mỗi cột 10 câu
ROWS_PER_GROUP = 10
GROUP_X0_MM = 20.0
GROUP_PITCH_MM = 43.0
OPTION_FIRST_OFFSET_MM = 14.0   # từ mép trái nhóm tới tâm bubble A
OPTION_PITCH_MM = 7.0
ANSWER_ROW_TOP_MM = 152.0       # tâm hàng câu đầu tiên
ANSWER_ROW_PITCH_MM = 11.0
ANSWER_BUBBLE_D_MM = 5.0

# ----------------------------- Trang thu chữ số ---------------------------------
DS_ROWS_PER_DIGIT = 2
DS_BOXES_PER_ROW = 20
DS_FIRST_BOX_X_MM = 32.0        # mép trái ô đầu tiên
DS_BOX_PITCH_X_MM = 8.0
DS_FIRST_ROW_TOP_MM = 48.0
DS_ROW_PITCH_MM = 11.2


# ================================================================================
def mm2px(v):
    return round(v * PX_PER_MM, 1)


def digit_col_x(first_x, col):
    return first_x + col * DIGIT_COL_PITCH_MM


def digit_bubble_y(d):
    return DIGIT_BUBBLE_TOP_MM + d * DIGIT_BUBBLE_PITCH_MM


def question_pos(q):
    """q: 1..40 -> (group, row). Đánh số theo cột: cột 1 = câu 1-10, cột 2 = 11-20..."""
    g, r = divmod(q - 1, ROWS_PER_GROUP)
    return g, r


def answer_bubble_center(q, opt_idx):
    g, r = question_pos(q)
    x = GROUP_X0_MM + g * GROUP_PITCH_MM + OPTION_FIRST_OFFSET_MM + opt_idx * OPTION_PITCH_MM
    y = ANSWER_ROW_TOP_MM + r * ANSWER_ROW_PITCH_MM
    return x, y


def digit_sheet_box(digit, sub_row, col):
    """Ô viết tay trên trang thu chữ số: trả về (x_left, y_top) mm."""
    row = digit * DS_ROWS_PER_DIGIT + sub_row
    return (DS_FIRST_BOX_X_MM + col * DS_BOX_PITCH_X_MM,
            DS_FIRST_ROW_TOP_MM + row * DS_ROW_PITCH_MM)


def _digit_field(first_x, n):
    boxes, bubbles = [], []
    for c in range(n):
        cx = digit_col_x(first_x, c)
        x0 = cx - DIGIT_BOX_W_MM / 2
        boxes.append([mm2px(x0), mm2px(DIGIT_BOX_TOP_MM),
                      mm2px(DIGIT_BOX_W_MM), mm2px(DIGIT_BOX_H_MM)])       # x, y, w, h
        bubbles.append([[mm2px(cx), mm2px(digit_bubble_y(d))] for d in range(10)])
    return {"digits": n, "handwriting_boxes": boxes, "bubbles": bubbles,
            "bubble_radius": mm2px(DIGIT_BUBBLE_D_MM / 2)}


def build_layout():
    """Layout của phiếu trả lời, đơn vị PIXEL trên ảnh chuẩn 300 DPI."""
    answers = {}
    for q in range(1, NUM_QUESTIONS + 1):
        answers[str(q)] = {opt: [mm2px(v) for v in answer_bubble_center(q, i)]
                           for i, opt in enumerate(OPTIONS)}
    return {
        "template_name": "Phiếu chuẩn 40 câu A4",
        "version": "1.0",
        "dpi": DPI,
        "page_px": [PAGE_W_PX, PAGE_H_PX],
        "markers": {"size": mm2px(MARKER_SIZE_MM),
                    "centers": {k: [mm2px(x), mm2px(y)] for k, (x, y) in MARKER_CENTERS_MM.items()}},
        "sbd": _digit_field(SBD_FIRST_COL_X_MM, SBD_DIGITS),
        "exam_code": _digit_field(EXAM_CODE_FIRST_COL_X_MM, EXAM_CODE_DIGITS),
        "answers": {"num_questions": NUM_QUESTIONS, "options": OPTIONS,
                    "bubble_radius": mm2px(ANSWER_BUBBLE_D_MM / 2), "centers": answers},
    }


def build_digit_sheet_layout():
    boxes = []
    for d in range(10):
        for s in range(DS_ROWS_PER_DIGIT):
            for c in range(DS_BOXES_PER_ROW):
                x, y = digit_sheet_box(d, s, c)
                boxes.append({"label": d, "row": d * DS_ROWS_PER_DIGIT + s, "col": c,
                              "rect": [mm2px(x), mm2px(y), mm2px(DIGIT_BOX_W_MM), mm2px(DIGIT_BOX_H_MM)]})
    return {"template_name": "Trang thu chữ số viết tay", "dpi": DPI, "page_px": [PAGE_W_PX, PAGE_H_PX],
            "markers": {"size": mm2px(MARKER_SIZE_MM),
                        "centers": {k: [mm2px(x), mm2px(y)] for k, (x, y) in MARKER_CENTERS_MM.items()}},
            "boxes": boxes}


def export_layout(path="output/layout.json", digit_path="output/digit_sheet_layout.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_layout(), f, ensure_ascii=False, indent=1)
    with open(digit_path, "w", encoding="utf-8") as f:
        json.dump(build_digit_sheet_layout(), f, ensure_ascii=False, indent=1)
