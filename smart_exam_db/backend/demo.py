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


def nap_thi_sinh(conn, exam_id: int, ts: list[dict]) -> int:
    """Thêm thí sinh DEMO (nếu chưa có) + đưa vào danh sách dự thi của kỳ thi. Chỉ INSERT. Trả số sinh viên mới."""
    them = 0
    for t in ts:
        sv = conn.execute(
            "INSERT INTO students (student_code, full_name) VALUES (%s, %s) ON CONFLICT (student_code) DO NOTHING "
            "RETURNING student_id", (t["sbd"], f"[DEMO] Thí sinh phiếu {t['phieu']}")).fetchone()
        them += sv is not None
        sid = sv["student_id"] if sv else conn.execute("SELECT student_id FROM students WHERE student_code = %s",
                                                       (t["sbd"],)).fetchone()["student_id"]
        conn.execute("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (exam_id, sid))
    return them


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
    them = nap_thi_sinh(conn, exam_id, ts)
    return {"exam_id": exam_id, "ky_thi_moi": moi, "thi_sinh_moi": them, "thi_sinh": len(ts)}


# ------------------------------------------------------------------------------------------------ [DEMO-2] đáp án = bài làm phiếu 0005
TIEU_DE_2 = "[DEMO-2] Đáp án lấy từ bài làm phiếu 0005 (minh hoạ chấm đúng)"
PHIEU_KHOP = "0005"


def khoa_tu_bai_lam(nhan: list[str], seed: int = SEED) -> tuple[str, dict]:
    """Đáp án = bài làm trong ground_truth.csv: ô tô rõ (chữ hoa) hoặc mờ (chữ thường) 1 ô -> đáp án đúng bằng chữ đó.
    Câu BỎ TRỐNG ('-') hoặc TÔ NHIỀU Ô ('CD'): không có đáp án tự nhiên -> đặt một chữ tất định random.Random(seed-khop-câu);
    bài làm ở các câu đó luôn tính SAI. Trả (chuỗi đáp án, {'bo_trong': [câu], 'nhieu_o': [câu]})."""
    khoa, dac_biet = [], {"bo_trong": [], "nhieu_o": []}
    for q, v in enumerate(nhan, 1):
        v = v.strip().upper()
        if len(v) == 1 and v in "ABCD":
            khoa.append(v)
            continue
        dac_biet["bo_trong" if v in ("", "-") else "nhieu_o"].append(q)
        khoa.append(random.Random(f"{seed}-khop-{q}").choice("ABCD"))
    return "".join(khoa), dac_biet


def doc_bai_lam(phieu: str = PHIEU_KHOP, ground_truth: Path | None = None) -> dict:
    """{'sbd', 'exam_code', 'nhan': [40 ô q1..q40]} của một phiếu train trong ground_truth.csv."""
    if int(phieu) not in PHIEU_TRAIN:
        raise RuntimeError(f"phiếu {phieu} không thuộc tập train 0001–0028")
    gt = ground_truth or ROOT / "data" / "ground_truth.csv"
    with gt.open(encoding="utf-8-sig", newline="") as f:
        r = next(r for r in csv.DictReader(f) if int(r["sheet_id"]) == int(phieu))
    return {"sbd": r["sbd"], "exam_code": r["exam_code"], "nhan": [r[f"q{i}"] for i in range(1, SO_CAU + 1)]}


def diem_mong_doi(nhan: list[str], diem_toi_da: float = 10.0) -> tuple[int, float]:
    """(số câu đúng, điểm) khi giáo viên duyệt theo ground_truth: câu 1 ô (hoa hoặc thường) đúng; trống / nhiều ô sai."""
    dung = sum(len(v.strip()) == 1 and v.strip().upper() in "ABCD" for v in nhan)
    return dung, round(dung * diem_toi_da / len(nhan), 3)


def nap_demo_khop(conn, user_id: int, ground_truth: Path | None = None, tieu_de: str = TIEU_DE_2) -> dict:
    """Tạo (nếu chưa có) kỳ thi [DEMO-2] + cùng 28 thí sinh DEMO. Chỉ INSERT; kỳ thi đã có thì không sửa đáp án."""
    bl = doc_bai_lam(ground_truth=ground_truth)
    khoa, dac_biet = khoa_tu_bai_lam(bl["nhan"])
    ma_de = {m: (khoa if m == bl["exam_code"] else khoa_demo(m)) for m in MA_DE}
    e = conn.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (tieu_de,)).fetchone()
    moi = e is None
    exam_id = e["exam_id"] if e else service.tao_ky_thi(conn, {
        "exam_title": tieu_de, "subject_code": MON[0], "subject_name": MON[1], "num_questions": SO_CAU, "max_score": 10,
        "pass_score": 5, "codes": [{"code": m, "answers": a} for m, a in ma_de.items()]}, user_id)
    them = nap_thi_sinh(conn, exam_id, doc_thi_sinh(ground_truth))
    dung, diem = diem_mong_doi(bl["nhan"])
    return {"exam_id": exam_id, "ky_thi_moi": moi, "thi_sinh_moi": them, "ma_de": bl["exam_code"], "sbd": bl["sbd"], "khoa": khoa,
            "dac_biet": dac_biet, "dung_mong_doi": dung, "diem_mong_doi": diem}
