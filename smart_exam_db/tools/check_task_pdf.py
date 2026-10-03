"""
check_task_pdf.py - So phiếu giao việc (bản người tô cầm trên tay) với ground_truth.csv. KHÔNG sửa gì.

Trích chữ trong answer_sheet/output/phieu_giao_viec.pdf bằng PyMuPDF (PDF vẽ bằng chữ thật, không phải ảnh):
mã phiếu, SBD, mã đề, bút, điều kiện chụp, 40 câu (chữ xám + "(mờ)" = tô mờ). So 3 chiều:
  1. PDF  <-> ground_truth.csv hiện tại      (chỗ lệch = nhãn đã sửa theo giấy, hoặc nhãn bị sai)
  2. PDF  <-> kịch bản sinh lại make_plan()  (PDF có đúng là kịch bản gốc seed 2026 không)
  3. ground_truth.csv ở commit đầu 399d48c <-> PDF (lệch có từ đầu hay do lần sửa sau)

Chạy (từ thư mục smart_exam_db/):
  python tools/check_task_pdf.py
"""
import csv
import io
import re
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent          # smart_exam_db/
ANSWER_SHEET = ROOT / "answer_sheet"
sys.path.insert(0, str(ANSWER_SHEET))
from make_dataset_plan import CONDITIONS, make_plan  # noqa: E402

PT_MM = 72 / 25.4
FIELDS = ["sbd", "exam_code", "pen", "conditions"] + [f"q{q}" for q in range(1, 41)]
FIRST_COMMIT = "399d48c"


def is_gray(color: int) -> bool:
    r, g, b = (color >> 16) & 255, (color >> 8) & 255, color & 255
    return r == g == b and 60 < r < 200                 # Color(.45,.45,.45) ~ 115; đen = 0


def spans(page) -> list[dict]:
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                if s["text"].strip():
                    out.append({"text": s["text"], "x": s["bbox"][0] / PT_MM, "y": s["origin"][1] / PT_MM,
                                "gray": is_gray(s["color"])})
    return out


def parse_task(sp: list[dict]) -> dict:
    """1 phiếu giao việc (các span thuộc nửa trang của nó)."""
    full = {s["text"] for s in sp}
    get = lambda pat: next(re.search(pat, t).group(1) for t in full if re.search(pat, t))  # noqa: E731
    rec = {
        "sheet_id": get(r"MÃ PHIẾU (\d{4})"),
        "sbd": get(r"Số báo danh cần viết \+ tô:\s*([\d ]+)").replace(" ", ""),
        "exam_code": get(r"Mã đề:\s*([\d ]+)").replace(" ", ""),
        "pen": get(r"Bút: (.+)$").strip(),
    }
    conds = get(r"Chụp 2 lần: (.+)$")
    rec["conditions"] = "+".join(re.findall(r"\b(C[1-4]) \(", conds))
    labels = [s for s in sp if re.fullmatch(r"Câu\s+\d+:", s["text"].strip())]
    for lab in labels:
        q = int(re.search(r"\d+", lab["text"]).group())
        # chữ đáp án vẽ tại x + 17 mm, cùng dòng; "(mờ)" tại x + 24 mm
        row = [s for s in sp if abs(s["y"] - lab["y"]) < 1.0 and 14 < s["x"] - lab["x"] < 23]
        if len(row) != 1:
            raise ValueError(f"phiếu {rec['sheet_id']} câu {q}: tìm thấy {len(row)} ô đáp án")
        a = row[0]["text"].strip()
        faint_note = any(abs(s["y"] - lab["y"]) < 1.0 and 21 < s["x"] - lab["x"] < 30
                         and s["text"].strip() == "(mờ)" for s in sp)       # 4 cột câu cùng dòng
        if a == "–":
            a = "-"
        elif faint_note or row[0]["gray"]:
            if not (faint_note and row[0]["gray"] and len(a) == 1):
                raise ValueError(f"phiếu {rec['sheet_id']} câu {q}: '{a}' ký hiệu mờ không nhất quán")
        rec[f"q{q}"] = a
    if len(labels) != 40:
        raise ValueError(f"phiếu {rec['sheet_id']}: đọc được {len(labels)}/40 câu")
    return rec


def read_pdf(path: Path) -> dict:
    out = {}
    for page in pymupdf.open(path):
        sp = spans(page)
        for half in (lambda s: s["y"] < 148, lambda s: s["y"] >= 148):   # 2 phiếu / trang: top 8 và 152 mm
            part = [s for s in sp if half(s)]
            if part:
                rec = parse_task(part)
                out[rec["sheet_id"]] = rec
    return out


def read_csv_text(text: str) -> dict:
    return {r["sheet_id"]: r for r in csv.DictReader(io.StringIO(text.lstrip("﻿")))}


def compare(name_a: str, a: dict, name_b: str, b: dict) -> list[tuple]:
    diffs = []
    for sid in sorted(set(a) | set(b)):
        if sid not in a or sid not in b:
            diffs.append((sid, "(cả phiếu)", "có" if sid in a else "thiếu", "có" if sid in b else "thiếu"))
            continue
        diffs += [(sid, f, a[sid][f], b[sid][f]) for f in FIELDS if a[sid][f] != b[sid][f]]
    print(f"\n{name_a} <-> {name_b}: {len(diffs)} chỗ lệch")
    for sid, f, va, vb in diffs:
        print(f"  {sid} {f:10s} {name_a}: {va!r:16} {name_b}: {vb!r}")
    return diffs


def main() -> None:
    pdf = read_pdf(ANSWER_SHEET / "output" / "phieu_giao_viec.pdf")
    n_faint = sum(v.islower() and len(v) == 1 for r in pdf.values() for k, v in r.items() if k.startswith("q"))
    print(f"Trích từ phieu_giao_viec.pdf: {len(pdf)} phiếu, {len(pdf) * 40} câu ({n_faint} câu mờ)")
    assert set(CONDITIONS) >= {c for r in pdf.values() for c in r["conditions"].split("+")}

    gt_now = read_csv_text((ANSWER_SHEET / "output" / "ground_truth.csv").read_text(encoding="utf-8-sig"))
    plan = {p["sheet_id"]: {**{k: p[k] for k in ("sheet_id", "sbd", "exam_code", "pen", "conditions")},
                            **{f"q{q}": a for q, a in enumerate(p["answers"], 1)}}
            for p in make_plan(40, 2026)}
    first = subprocess.run(["git", "show", f"{FIRST_COMMIT}:smart_exam_db/answer_sheet/output/ground_truth.csv"],
                           cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")

    compare("PDF", pdf, "make_plan", plan)
    compare("PDF", pdf, f"gt@{FIRST_COMMIT}", read_csv_text(first))
    compare("PDF", pdf, "gt hiện tại", gt_now)


if __name__ == "__main__":
    main()
