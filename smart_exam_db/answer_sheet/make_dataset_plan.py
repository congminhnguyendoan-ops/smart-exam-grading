"""
make_dataset_plan.py - Sinh "kịch bản tô" cho từng phiếu => NHÃN ĐÚNG (ground truth) có sẵn
trước khi tô, không phải gán nhãn tay sau này.

Chạy:  python make_dataset_plan.py              (mặc định 40 phiếu, khớp generate_sheets.py)
       python make_dataset_plan.py --count 60 --seed 7

Đầu ra (output/):
  ground_truth.csv     1 dòng / phiếu: SBD, mã đề (viết tay), sbd_bubble, exam_code_bubble (ô tô),
                       40 câu, bút, điều kiện chụp
  cell_labels.csv      1 dòng / ô tròn + nhãn blank/filled/faint:
                       - ô đáp án: question = 1..40, option = A..D  (40 x 4 ô / phiếu)
                       - ô SBD/mã đề: question = sbd1..sbd6 / exam_code1..exam_code3, option = 0..9
                         (10 ô / chữ số); question_state = filled, hoặc blank nếu chữ số đó không tô
                       Lọc ô đáp án cho OMR: question là số.
  phieu_giao_viec.pdf  in ra, đặt cạnh phiếu cùng mã khi tô (2 phiếu giao việc / trang A4)

sbd_bubble / exam_code_bubble: chữ số được TÔ ở từng cột bubble; '-' = cột đó không tô ô nào (người tô
quên, vd 0001 SBD chữ số 6, 0035 cả mã đề - 03/10/2026). Phiếu bình thường: giống số viết tay.

Ký hiệu trong kịch bản:
  B   = tô KÍN ô B                     (filled)
  b   = tô MỜ ô B: tô nhẹ tay, ~50-70% (faint)
  AC  = tô kín CẢ HAI ô A và C         (multiple)
  -   = bỏ trống câu đó                (blank)
"""
import argparse
import csv
import os
import random

from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import sheet_layout as L

HERE = os.path.dirname(os.path.abspath(__file__))
pdfmetrics.registerFont(TTFont("VN", os.path.join(HERE, "fonts", "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("VNB", os.path.join(HERE, "fonts", "DejaVuSans-Bold.ttf")))

# Tỉ lệ trạng thái mỗi câu. faint & multiple được "cố tình" nhiều hơn thực tế
# để classifier có đủ mẫu của lớp hiếm (chống mất cân bằng dữ liệu).
STATE_WEIGHTS = {"filled": 0.64, "faint": 0.18, "multiple": 0.08, "blank": 0.10}
EXAM_CODES = ["101", "102", "103", "104"]
PENS = ["Bút chì 2B", "Bút bi xanh", "Bút bi đen"]
CONDITIONS = {
    "C1": "Đủ sáng, chụp thẳng từ trên xuống",
    "C2": "Thiếu sáng (phòng tối / buổi tối, không bật flash)",
    "C3": "Nghiêng 15-25 độ, phiếu đặt trên bàn",
    "C4": "Đèn vàng / có bóng tay, bóng điện thoại đổ lên phiếu",
}


def balanced_digit_stream(rng):
    """Sinh chữ số sao cho 0-9 xuất hiện đều nhau (mỗi 10 chữ số là 1 hoán vị)."""
    while True:
        block = list(range(10))
        rng.shuffle(block)
        yield from block


def make_plan(n, seed):
    rng = random.Random(seed)
    digits = balanced_digit_stream(rng)
    states, weights = zip(*STATE_WEIGHTS.items())
    cond_keys = list(CONDITIONS)
    plan, seen_sbd = [], set()
    for i in range(1, n + 1):
        while True:
            sbd = "".join(str(next(digits)) for _ in range(L.SBD_DIGITS))
            if sbd not in seen_sbd:
                seen_sbd.add(sbd)
                break
        code = EXAM_CODES[(i - 1) % len(EXAM_CODES)]
        answers = []
        for _ in range(L.NUM_QUESTIONS):
            st = rng.choices(states, weights)[0]
            if st == "blank":
                answers.append("-")
            elif st == "multiple":
                answers.append("".join(sorted(rng.sample(L.OPTIONS, 2))))
            else:
                o = rng.choice(L.OPTIONS)
                answers.append(o if st == "filled" else o.lower())
        plan.append({
            "sheet_id": f"{i:04d}",
            "sbd": sbd,
            "exam_code": code,
            "sbd_bubble": sbd,              # kịch bản: tô đúng số viết tay
            "exam_code_bubble": code,
            "pen": PENS[(i - 1) % len(PENS)],
            "conditions": f"{cond_keys[(i - 1) % 4]}+{cond_keys[i % 4]}",   # mỗi phiếu chụp 2 lần
            "answers": answers,
        })
    return plan


def answer_state(a):
    if a == "-":
        return "blank"
    if len(a) == 2:
        return "multiple"
    return "faint" if a.islower() else "filled"


def cell_label(a, opt):
    if a == "-":
        return "blank"
    if len(a) == 2:
        return "filled" if opt in a else "blank"
    if a.upper() != opt:
        return "blank"
    return "faint" if a.islower() else "filled"


def bubble_rows(p):
    """Dòng cell_labels cho bubble SBD/mã đề: ô của chữ số được tô = filled, còn lại blank."""
    for field in ("sbd", "exam_code"):
        bubbles = p[f"{field}_bubble"]
        if len(bubbles) != len(p[field]) or any(ch not in "0123456789-" for ch in bubbles):
            raise ValueError(f"phiếu {p['sheet_id']}: {field}_bubble '{bubbles}' sai định dạng")
        for i, ch in enumerate(bubbles, 1):
            for digit in "0123456789":
                yield [p["sheet_id"], f"{field}{i}", digit, "filled" if ch == digit else "blank",
                       "blank" if ch == "-" else "filled"]


def write_csvs(plan, out):
    with open(os.path.join(out, "ground_truth.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sheet_id", "sbd", "exam_code", "sbd_bubble", "exam_code_bubble", "pen", "conditions"]
                   + [f"q{q}" for q in range(1, 41)])
        for p in plan:
            w.writerow([p["sheet_id"], p["sbd"], p["exam_code"], p["sbd_bubble"], p["exam_code_bubble"],
                        p["pen"], p["conditions"]] + p["answers"])
    with open(os.path.join(out, "cell_labels.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sheet_id", "question", "option", "cell_label", "question_state"])
        for p in plan:
            for q, a in enumerate(p["answers"], 1):
                for opt in L.OPTIONS:
                    w.writerow([p["sheet_id"], q, opt, cell_label(a, opt), answer_state(a)])
        for p in plan:                      # sau toàn bộ ô đáp án: các dòng cũ giữ nguyên thứ tự
            w.writerows(bubble_rows(p))


def draw_task(c, p, top_mm):
    """Vẽ 1 phiếu giao việc, cao ~140mm, bắt đầu từ top_mm."""
    def T(x, y, s, size=9, font="VN", align="left", color=black):
        c.setFillColor(color)
        c.setFont(font, size)
        {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align](
            x * mm, (297 - y) * mm, s)

    y0 = top_mm
    c.setStrokeColor(Color(.3, .3, .3))
    c.setLineWidth(.8)
    c.rect(12 * mm, (297 - y0 - 136) * mm, 186 * mm, 136 * mm)
    T(16, y0 + 8, f"PHIẾU GIAO VIỆC  –  dùng cho phiếu trả lời MÃ PHIẾU {p['sheet_id']}", 11, "VNB")
    T(16, y0 + 16, f"Số báo danh cần viết + tô:  {'  '.join(p['sbd'])}", 10, "VNB")
    T(120, y0 + 16, f"Mã đề:  {'  '.join(p['exam_code'])}", 10, "VNB")
    conds = " và ".join(f"{k} ({CONDITIONS[k]})" for k in p["conditions"].split("+"))
    T(16, y0 + 23, f"Bút: {p['pen']}", 8.5)
    T(16, y0 + 29, f"Chụp 2 lần: {conds}", 7.2)
    T(16, y0 + 35, "Ký hiệu:  B = tô kín ô B   |   b (chữ thường) = tô MỜ, nhẹ tay ô B   |   "
                   "AC = tô kín cả A và C   |   –  = bỏ trống", 7.8)
    for q, a in enumerate(p["answers"], 1):
        g, r = L.question_pos(q)
        x = 18 + g * 46
        y = y0 + 45 + r * 9
        shown = "–" if a == "-" else a
        st = answer_state(a)
        font = "VNB" if st in ("filled", "multiple") else "VN"
        T(x, y, f"Câu {q:>2}:", 9)
        T(x + 17, y, shown, 11, font, color=Color(.45, .45, .45) if st == "faint" else black)
        if st == "faint":
            T(x + 24, y, "(mờ)", 7, color=Color(.45, .45, .45))
    T(16, y0 + 133, "Tô xong: ☐     Chụp lần 1: ☐     Chụp lần 2: ☐     Người tô: ...........................", 8.5)


def write_task_pdf(plan, out):
    c = canvas.Canvas(os.path.join(out, "phieu_giao_viec.pdf"), pagesize=A4)
    c.setTitle("Phiếu giao việc - kịch bản tô")
    for i in range(0, len(plan), 2):
        draw_task(c, plan[i], 8)
        if i + 1 < len(plan):
            draw_task(c, plan[i + 1], 152)
        c.showPage()
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--from-csv", action="store_true",
                    help="đọc ground_truth.csv ĐÃ SỬA tay và chỉ sinh lại cell_labels.csv")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.from_csv:
        with open(os.path.join(a.out, "ground_truth.csv"), encoding="utf-8-sig") as f:
            # ground_truth.csv cũ (trước 03/10/2026) chưa có cột *_bubble -> coi như tô đúng số viết tay
            plan = [{"sbd_bubble": r["sbd"], "exam_code_bubble": r["exam_code"], **r,
                     "answers": [r[f"q{q}"] for q in range(1, 41)]} for r in csv.DictReader(f)]
        write_csvs(plan, a.out)
        print(f"Đã sinh lại cell_labels.csv từ ground_truth.csv ({len(plan)} phiếu)")
        return
    plan = make_plan(a.count, a.seed)
    write_csvs(plan, a.out)
    write_task_pdf(plan, a.out)

    from collections import Counter
    st = Counter(answer_state(x) for p in plan for x in p["answers"])
    cl = Counter(cell_label(x, o) for p in plan for x in p["answers"] for o in L.OPTIONS)
    dg = Counter(d for p in plan for d in p["sbd"] + p["exam_code"])
    print(f"{a.count} phiếu | trạng thái câu: {dict(st)}")
    print(f"nhãn ô: {dict(cl)}")
    print(f"chữ số viết tay trên phiếu: {sum(dg.values())} ({dict(sorted(dg.items()))})")


if __name__ == "__main__":
    main()
