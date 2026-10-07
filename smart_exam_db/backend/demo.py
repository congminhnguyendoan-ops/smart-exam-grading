"""
demo.py - Dữ liệu mẫu cho demo (CHẠY LẠI ĐƯỢC): kỳ thi "[DEMO] ..." cho bộ ảnh thu dữ liệu 0001–0028 (CHỈ train, không đụng
0029–0040), 4 mã đề 101–104 (khớp ground_truth.csv), đáp án DEMO sinh giả lập tất định, danh sách thí sinh DEMO lấy SBD viết tay
từ ground_truth.csv. Mọi bản ghi mang nhãn "[DEMO]" để phân biệt với dữ liệu thật.

Đáp án này KHÔNG phải đề thật (phiếu thu dữ liệu chỉ ghi cách người tô, không có đề): sinh bằng random.Random(seed) để mỗi
lần chạy ra cùng đáp án; điểm chấm ra chỉ có ý nghĩa kiểm thử hệ thống.
"""
import csv
import random
from pathlib import Path

from cv_engine.tap_du_lieu import PHIEU_TRAIN

from . import service
from .config import ROOT

TIEU_DE = "[DEMO] Phiếu thu dữ liệu 0001–0028 (đáp án giả lập)"
MON = ("DEMO", "[DEMO] Môn thử nghiệm")
MA_DE = ("101", "102", "103", "104")
SEED = 2026
SO_CAU = 40


def khoa_demo(ma_de: str, n: int = SO_CAU, seed: int = SEED) -> str:
    """Chuỗi đáp án DEMO của một mã đề (tất định theo seed + mã đề)."""
    rng = random.Random(f"{seed}-{ma_de}")
    return "".join(rng.choice("ABCD") for _ in range(n))


def doc_thi_sinh(ground_truth: Path | None = None) -> list[dict]:
    """[{phieu, sbd}] của phiếu train 0001–0028 – dòng phiếu khác bị bỏ ngay khi đọc."""
    gt = ground_truth or ROOT / "data" / "ground_truth.csv"
    with gt.open(encoding="utf-8-sig", newline="") as f:
        return [{"phieu": r["sheet_id"], "sbd": r["sbd"]} for r in csv.DictReader(f) if int(r["sheet_id"]) in PHIEU_TRAIN]


def nap_demo(conn, user_id: int, ground_truth: Path | None = None) -> dict:
    """Tạo (nếu chưa có) kỳ thi DEMO + đáp án + thí sinh + danh sách dự thi. Không xoá / sửa gì đã có. Trả thống kê."""
    ts = doc_thi_sinh(ground_truth)
    if len({t["sbd"] for t in ts}) != len(ts):
        raise RuntimeError("ground_truth.csv có SBD trùng giữa các phiếu train – không nạp danh sách DEMO")
    e = conn.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (TIEU_DE,)).fetchone()
    moi = e is None
    if moi:
        exam_id = service.tao_ky_thi(conn, {
            "exam_title": TIEU_DE, "subject_code": MON[0], "subject_name": MON[1], "num_questions": SO_CAU, "max_score": 10,
            "pass_score": 5, "codes": [{"code": m, "answers": khoa_demo(m)} for m in MA_DE]}, user_id)
    else:
        exam_id = e["exam_id"]
        hien = {c["code"]: c["answers"] for c in service.doc_ky_thi(conn, exam_id)["codes"]}
        if any(hien.get(m) != khoa_demo(m) for m in MA_DE):
            print("CẢNH BÁO: đáp án kỳ thi DEMO hiện có khác bản sinh (đã bị sửa?) – giữ nguyên, không ghi đè.")
    them = 0
    for t in ts:
        sv = conn.execute(
            "INSERT INTO students (student_code, full_name) VALUES (%s, %s) ON CONFLICT (student_code) DO NOTHING "
            "RETURNING student_id", (t["sbd"], f"[DEMO] Thí sinh phiếu {t['phieu']}")).fetchone()
        them += sv is not None
        sid = sv["student_id"] if sv else conn.execute("SELECT student_id FROM students WHERE student_code = %s",
                                                       (t["sbd"],)).fetchone()["student_id"]
        conn.execute("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (exam_id, sid))
    return {"exam_id": exam_id, "ky_thi_moi": moi, "thi_sinh_moi": them, "thi_sinh": len(ts)}
