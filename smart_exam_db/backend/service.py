"""
service.py - Lớp dịch vụ chấm phiếu: ảnh (byte) -> preprocess_anh -> doc_phieu (OMR) -> tra đáp án theo mã đề -> chấm
-> lưu CSDL (phiếu, từng câu, trạng thái "cần xem", ảnh bị từ chối kèm mã + thông báo) -> luồng giáo viên xem lại.

Nguyên tắc:
  - KHÔNG tự commit (db.giao_dich / API quyết định) – pytest chạy trong giao dịch rồi rollback.
  - Câu "cần xem" của OMR không bao giờ được chấm như câu chắc chắn (grading.py). Phiếu còn câu / SBD / mã đề cần xem
    KHÔNG có điểm chính thức: status = needs_review, điểm tạm (câu chắc chắn) ở answer_sheets.raw_score, kèm mục review_queue.
  - Điểm chính thức chỉ ghi vào `results` khi không còn gì cần xem; trước khi ghi đối chiếu với fn_grade_sheet của CSDL.
  - Lỗi lập trình (exception lạ) vẫn ném ra; chỉ ảnh hỏng / bị từ chối mới thành "từ chối có lý do".
"""
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
from psycopg.types.json import Jsonb

from cv_engine import ocr as ocr_cnn
from cv_engine import omr
from cv_engine.preprocessing import (MA_LY_DO, KetQuaTienXuLy, LoiDocAnh, doc_anh, nap_layout,
                                     preprocess_anh)

from . import grading
from .config import ROOT, CauHinh, LoiCauHinh

log = logging.getLogger("smart_exam.service")

DUOI_ANH = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
LY_DO_OMR_CAU = {"o_mo", "tin_cay_thap", "vi_tri", "vet_nho", "to_nhat"}          # -> review_reason low_omr_confidence
# (nhieu_o -> multiple_marks; khong_o_nao chỉ có ở cột chữ số. Mã câu MỚI của MA_LY_DO_OMR phải vào đây, nếu không câu cần xem bị bỏ qua
#  ở danh_gia_phieu -> "hết lý do" -> RuntimeError chốt an toàn; tests/test_backend_ly_do_omr.py kiểm)
PRIORITY = {"duplicate_sbd": 1, "sbd_not_found": 1, "low_ocr_confidence": 2, "exam_code_not_found": 2}


class LoiDichVu(Exception):
    """Lỗi nghiệp vụ (API đổi thành mã HTTP)."""
    ma_http = 400


class KhongTimThay(LoiDichVu):
    ma_http = 404


class XungDot(LoiDichVu):
    ma_http = 409


class DuLieuSai(LoiDichVu):
    ma_http = 422


class AnhDaXoa(LoiDichVu):
    """Ảnh của phiếu đã chốt bị xoá theo chính sách ảnh tạm (backend/don_anh.py) – không phải lỗi máy chủ."""
    ma_http = 410


THONG_BAO_ANH_DA_XOA = "Ảnh đã được xoá sau khi chốt phiếu (chính sách giữ ảnh tạm). Điểm, đáp án và lý do vẫn được giữ."


def anh_da_xoa_luc(conn, sheet_id: int):
    """Thời điểm ảnh của phiếu bị xoá, None nếu còn. Đọc qua to_jsonb để KHÔNG lỗi khi CSDL chưa áp migration 003 (chưa có cột)."""
    r = conn.execute("SELECT to_jsonb(a) -> 'image_deleted_at' AS x FROM answer_sheets a WHERE sheet_id = %s", (sheet_id,)).fetchone()
    return r["x"] if r else None


# ------------------------------------------------------------------------------------------------ mô hình OMR
@dataclass
class MoHinhDichVu:
    du_lieu: dict
    sha256: str
    duong_dan: Path
    ocr: ocr_cnn.MoHinhOCR | None = None          # CNN chữ số viết tay (kênh thứ hai của SBD / mã đề)
    ocr_sha256: str = ""
    ocr_duong_dan: Path | None = None

    @property
    def phien_ban(self) -> str:
        return f"{self.du_lieu.get('phien_ban', 'omr')}-{self.sha256[:8]}"

    @property
    def phien_ban_ocr(self) -> str:
        return f"ocr_cnn-{self.ocr_sha256[:8]}"


def nap_mo_hinh(cfg: CauHinh) -> MoHinhDichVu:
    """Nạp mô hình OMR + CNN chữ số một lần (khi khởi động). Kèm SHA-256 file để ghi vào ml_models.
    Thiếu mô hình chữ số thì KHÔNG chạy: SBD / mã đề cần cả hai kênh (không lặng lẽ quay về chỉ-bubble)."""
    if not cfg.mo_hinh_ocr.exists():
        raise LoiCauHinh(f"Chưa có mô hình chữ số viết tay: {cfg.mo_hinh_ocr} (xem OCR_MODEL trong .env, tools/xuat_ocr.py).")
    return MoHinhDichVu(omr.nap_mo_hinh(cfg.mo_hinh_omr), hashlib.sha256(cfg.mo_hinh_omr.read_bytes()).hexdigest(),
                        cfg.mo_hinh_omr, ocr_cnn.nap_mo_hinh_ocr(cfg.mo_hinh_ocr),
                        hashlib.sha256(cfg.mo_hinh_ocr.read_bytes()).hexdigest(), cfg.mo_hinh_ocr)


def mo_hinh_id(conn, mh: MoHinhDichVu) -> int:
    """id của bản ghi ml_models (loại omr_classifier) ứng với file mô hình; tạo mới (is_active = FALSE) nếu chưa có."""
    r = conn.execute("SELECT model_id FROM ml_models WHERE model_type = 'omr_classifier' AND version = %s",
                     (mh.phien_ban,)).fetchone()
    if r:
        return r["model_id"]
    try:
        rel = str(mh.duong_dan.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(mh.duong_dan)
    sd = mh.du_lieu.get("sieu_du_lieu", {})
    return conn.execute(
        "INSERT INTO ml_models (model_name, model_type, version, framework, file_path, train_dataset, metrics, is_active, notes) "
        "VALUES (%s, 'omr_classifier', %s, 'sklearn -> NumPy JSON', %s, %s, %s, FALSE, %s) RETURNING model_id",
        (mh.du_lieu.get("phien_ban", "omr"), mh.phien_ban, rel, sd.get("tap_huan_luyen"), Jsonb({}),
         f"sha256 {mh.sha256}; git {sd.get('git_head', '')}; nguồn ảnh {mh.du_lieu.get('nguon_anh', '')}")).fetchone()["model_id"]


def mo_hinh_ocr_id(conn, mh: MoHinhDichVu) -> int:
    """id của bản ghi ml_models (loại ocr_digit) ứng với file CNN chữ số; tạo mới (is_active = FALSE) nếu chưa có."""
    r = conn.execute("SELECT model_id FROM ml_models WHERE model_type = 'ocr_digit' AND version = %s", (mh.phien_ban_ocr,)).fetchone()
    if r:
        return r["model_id"]
    try:
        rel = str(mh.ocr_duong_dan.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(mh.ocr_duong_dan)
    sd = mh.ocr.sieu_du_lieu
    return conn.execute(
        "INSERT INTO ml_models (model_name, model_type, version, framework, file_path, train_dataset, metrics, is_active, notes) "
        "VALUES (%s, 'ocr_digit', %s, 'PyTorch -> NumPy JSON', %s, %s, %s, FALSE, %s) RETURNING model_id",
        ("ocr_cnn", mh.phien_ban_ocr, rel, str(sd.get("tap_huan_luyen", ""))[:200] or None, Jsonb(sd.get("do_luong", {})),
         f"sha256 {mh.ocr_sha256}; git {sd.get('git_head', '')}; cấu hình {sd.get('cau_hinh', '')}")).fetchone()["model_id"]


# ------------------------------------------------------------------------------------------------ người dùng
def lay_nguoi_dung(conn, username: str) -> int:
    r = conn.execute("SELECT user_id FROM users WHERE lower(username) = lower(%s) AND is_active", (username,)).fetchone()
    if not r:
        raise KhongTimThay(f"Không có người dùng '{username}' (đặt DEMO_USER trong .env).")
    return r["user_id"]


# ------------------------------------------------------------------------------------------------ đề thi + đáp án
def tao_ky_thi(conn, d: dict, user_id: int) -> int:
    """d: exam_title, subject_code, subject_name?, exam_date?, duration_min?, num_questions, max_score, pass_score,
    template_name?, codes: [{code, answers}] với answers là chuỗi num_questions chữ cái (vd 'ABCD…')."""
    tpl = (conn.execute("SELECT * FROM sheet_templates WHERE template_name = %s", (d["template_name"],)).fetchone()
           if d.get("template_name") else conn.execute("SELECT * FROM sheet_templates ORDER BY template_id LIMIT 1").fetchone())
    if not tpl:
        raise DuLieuSai("Không tìm thấy mẫu phiếu (sheet_templates).")
    n = d["num_questions"]
    if n > tpl["num_questions"]:
        raise DuLieuSai(f"Đề {n} câu nhưng mẫu phiếu '{tpl['template_name']}' chỉ có {tpl['num_questions']} câu.")
    codes = d.get("codes") or []
    if not codes:
        raise DuLieuSai("Cần ít nhất một mã đề kèm đáp án.")
    if len({c["code"] for c in codes}) != len(codes):
        raise DuLieuSai("Mã đề bị trùng trong yêu cầu.")
    for c in codes:
        if not (c["code"].isdigit() and 1 <= len(c["code"]) <= 6):
            raise DuLieuSai(f"Mã đề '{c['code']}' phải gồm 1–6 chữ số.")
        if len(c["answers"]) != n:
            raise DuLieuSai(f"Mã đề {c['code']}: có {len(c['answers'])} đáp án, cần đúng {n}.")
        try:
            for ch in c["answers"]:
                if len(grading.chuan_hoa_lua_chon(ch, tpl["options_per_question"])) != 1:
                    raise ValueError("mỗi câu đúng một chữ cái")
        except ValueError as e:
            raise DuLieuSai(f"Mã đề {c['code']}: {e}") from e
    sub = conn.execute("SELECT subject_id FROM subjects WHERE subject_code = %s", (d["subject_code"],)).fetchone()
    if not sub:
        sub = conn.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, %s) RETURNING subject_id",
                           (d["subject_code"], d.get("subject_name") or d["subject_code"])).fetchone()
    exam_id = conn.execute(
        "INSERT INTO exams (exam_title, subject_id, template_id, exam_date, duration_min, num_questions, max_score, pass_score, created_by, class_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING exam_id",
        (d["exam_title"], sub["subject_id"], tpl["template_id"], d.get("exam_date"), d.get("duration_min"), n,
         d.get("max_score", 10), d.get("pass_score", 5), user_id, d.get("class_id"))).fetchone()["exam_id"]
    for c in codes:
        cid = conn.execute("INSERT INTO exam_codes (exam_id, code) VALUES (%s, %s) RETURNING exam_code_id",
                           (exam_id, c["code"])).fetchone()["exam_code_id"]
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO answer_keys (exam_code_id, question_no, correct_option) VALUES (%s, %s, %s)",
                            [(cid, i + 1, ch) for i, ch in enumerate(c["answers"].upper())])
    return exam_id


def doc_ky_thi(conn, exam_id: int) -> dict:
    e = conn.execute("SELECT e.*, s.subject_code, s.subject_name, c.class_code, c.class_name FROM exams e JOIN subjects s USING (subject_id) "
                     "LEFT JOIN classes c ON c.class_id = e.class_id WHERE e.exam_id = %s", (exam_id,)).fetchone()
    if not e:
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    codes = []
    for c in conn.execute("SELECT exam_code_id, code FROM exam_codes WHERE exam_id = %s ORDER BY code", (exam_id,)).fetchall():
        ks = conn.execute("SELECT question_no, correct_option FROM answer_keys WHERE exam_code_id = %s ORDER BY question_no",
                          (c["exam_code_id"],)).fetchall()
        codes.append({"code": c["code"], "answers": "".join(k["correct_option"] for k in ks)})
    th = conn.execute("""SELECT count(*) AS tong,
                                count(*) FILTER (WHERE status = 'graded') AS da_cham,
                                count(*) FILTER (WHERE status = 'needs_review') AS can_xem,
                                count(*) FILTER (WHERE status = 'rejected') AS bi_tu_choi
                         FROM answer_sheets WHERE exam_id = %s""", (exam_id,)).fetchone()
    return {"exam_id": e["exam_id"], "exam_title": e["exam_title"], "subject_code": e["subject_code"],
            "subject_name": e["subject_name"], "class_id": e["class_id"], "class_code": e["class_code"], "class_name": e["class_name"],
            "exam_date": e["exam_date"], "num_questions": e["num_questions"],
            "max_score": e["max_score"], "pass_score": e["pass_score"], "status": str(e["status"]), "codes": codes, "sheets": dict(th)}


def ds_ky_thi(conn, dieu_kien: str = "TRUE", tham_so: tuple = ()) -> list[dict]:
    """`dieu_kien` + `tham_so` do phan_quyen.dieu_kien_ky_thi sinh (mệnh đề có tham số, KHÔNG nối dữ liệu người dùng)."""
    return conn.execute(
        "SELECT e.exam_id, e.exam_title, e.num_questions, e.max_score, e.exam_date, e.status::text AS status, sj.subject_code, sj.subject_name, "
        "e.class_id, c.class_code, c.class_name, "
        "(SELECT count(*) FROM answer_sheets a WHERE a.exam_id = e.exam_id) AS so_phieu "
        "FROM exams e JOIN subjects sj ON sj.subject_id = e.subject_id LEFT JOIN classes c ON c.class_id = e.class_id "
        f"WHERE {dieu_kien} ORDER BY e.exam_id DESC", tham_so).fetchall()


# ------------------------------------------------------------------------------------------------ lưu ảnh
def _ghi_file(duong_dan: Path, du_lieu: bytes) -> None:
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    tam = duong_dan.with_name(duong_dan.name + f".{os.getpid()}.tmp")
    tam.write_bytes(du_lieu)
    tam.replace(duong_dan)


def _duoi_file(ten: str | None) -> str:
    d = Path(ten or "").suffix.lower()
    return d if d in DUOI_ANH else ".jpg"


# ------------------------------------------------------------------------------------------------ nhận ảnh -> chấm
def _truong_json(om_cot, hv_cot, dc_cot, ly_truong, chac) -> dict:
    """Một trường (SBD / mã đề) sau khi đối chiếu hai kênh: bubble (OMR) ↔ chữ viết tay (CNN). `chu_so` của cột = chữ số đọc từ
    BUBBLE ('?' nếu không đọc được; gợi ý của CNN chỉ nằm ở `handwriting`, không lẫn vào số "đã đọc"); `can_xem` của trường = KHÔNG chắc
    (còn cột lệch / không chắc / chưa kiểm được danh sách thi)."""
    cot = []
    for b, h, d in zip(om_cot, hv_cot, dc_cot):
        doc_duoc = h.chu_so != "?"
        cot.append({"vi_tri": b.vi_tri, "chu_so": b.chu_so, "can_xem": not d.chac, "ly_do": list(d.ly_do),
                    "do_tin_cay": min(b.do_tin_cay, h.p) if doc_duoc else b.do_tin_cay, "bubble": b.chu_so,
                    "handwriting": {"pos": h.vi_tri, "chu_so": h.chu_so, "p": round(float(h.p), 4), "o_trong": h.o_trong, "loi_o": h.loi_o,
                                    "top_k": [{"d": str(k), "p": round(float(v), 4)} for k, v in h.top_k], "ok_vien": bool(h.ok_vien)}})
    return {"can_xem": not chac, "ly_do": list(ly_truong), "cot": cot}


def _ghi_ocr_digits(conn, cfg: CauHinh, exam_id: int, sha: str, sheet_id: int, hv) -> None:
    """9 dòng `ocr_digits` (SBD 6 + mã đề 3) + ảnh cắt từng ô viết tay lưu trên đĩa (như ảnh phiếu, CSDL chỉ giữ đường dẫn)."""
    dong = []
    for truong, cots in (("sbd", hv.sbd), ("exam_code", hv.ma_de)):
        for c in cots:
            rel = f"ocr/{exam_id}/{sha[:2]}/{sha}_{truong}{c.vi_tri}.png"
            ok, png = cv2.imencode(".png", c.anh_o)
            if not ok:
                raise RuntimeError("không mã hoá được ảnh ô viết tay")
            _ghi_file(cfg.storage_dir / rel, png.tobytes())
            doc = c.chu_so != "?"
            dong.append((sheet_id, truong, c.vi_tri, c.chu_so if doc else None, round(float(c.p), 4) if doc else None,
                         Jsonb([{"d": str(k), "p": round(float(v), 4)} for k, v in c.top_k]), rel))
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO ocr_digits (sheet_id, field, position, predicted_digit, confidence, top_k, crop_image_path) "
                        "VALUES (%s, %s::ocr_field, %s, %s, %s, %s, %s)", dong)


def nhan_anh(conn, cfg: CauHinh, mh: MoHinhDichVu, exam_id: int, du_lieu: bytes, ten_file: str | None, user_id: int,
             batch_id: int | None = None) -> tuple[int, bool]:
    """Nhận một ảnh phiếu của kỳ thi. Trả (sheet_id, da_ton_tai). Cùng ảnh (SHA-256) đã tải cho kỳ thi này -> trả phiếu cũ."""
    ex = conn.execute("SELECT exam_id, num_questions FROM exams WHERE exam_id = %s", (exam_id,)).fetchone()
    if not ex:
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    if not du_lieu:
        raise DuLieuSai("File ảnh rỗng.")
    if len(du_lieu) > cfg.gioi_han_anh_mb * 1024 * 1024:
        raise DuLieuSai(f"Ảnh lớn hơn {cfg.gioi_han_anh_mb} MB.")
    sha = hashlib.sha256(du_lieu).hexdigest()
    cu = conn.execute("SELECT sheet_id FROM answer_sheets WHERE exam_id = %s AND image_hash = %s", (exam_id, sha)).fetchone()
    if cu:
        return cu["sheet_id"], True

    rel = f"uploads/{exam_id}/{sha[:2]}/{sha}{_duoi_file(ten_file)}"
    duong_dan = cfg.storage_dir / rel
    _ghi_file(duong_dan, du_lieu)
    ten = (Path(ten_file).name[:255] if ten_file else None)

    layout = nap_layout("phieu")
    t0 = time.perf_counter()
    try:
        xam, exif = doc_anh(duong_dan)
        kq = preprocess_anh(xam, layout, exif)
    except LoiDocAnh:
        kq = KetQuaTienXuLy(ly_do="khong_doc_duoc")
    t_pre = (time.perf_counter() - t0) * 1000

    chung = dict(exam_id=exam_id, batch_id=batch_id, image_path=rel, image_hash=sha, filename=ten, user_id=user_id)
    if not kq.ok:                                    # ảnh bị từ chối: có mã + thông báo, KHÔNG có điểm
        thong_bao = MA_LY_DO.get(kq.ly_do, kq.ly_do)
        return conn.execute(
            "INSERT INTO answer_sheets (exam_id, batch_id, image_path, image_hash, original_filename, uploaded_by, status, "
            "reject_code, error_message, omr_detail, processing_time_ms, processed_at) "
            "VALUES (%(exam_id)s, %(batch_id)s, %(image_path)s, %(image_hash)s, %(filename)s, %(user_id)s, 'rejected', %(ma)s, %(tb)s, "
            "%(detail)s, %(ms)s, now()) RETURNING sheet_id",
            {**chung, "ma": kq.ly_do, "tb": thong_bao, "ms": round(t_pre),
             "detail": Jsonb({"preprocess": {"ly_do": kq.ly_do, "huong_xoay": kq.huong_xoay, "exif": kq.exif_orientation,
                                             "blur_score": None if kq.blur_score is None else float(kq.blur_score)}})}
        ).fetchone()["sheet_id"], False

    rel_nan = f"aligned/{exam_id}/{sha[:2]}/{sha}.jpg"
    ok_jpg, jpg = cv2.imencode(".jpg", kq.anh_nan, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok_jpg:
        raise RuntimeError("không mã hoá được ảnh nắn")
    _ghi_file(cfg.storage_dir / rel_nan, jpg.tobytes())

    t1 = time.perf_counter()
    res = omr.doc_phieu(kq, layout, mh.du_lieu)
    t_omr = (time.perf_counter() - t1) * 1000
    n = ex["num_questions"]
    if n > len(res.cau):
        raise RuntimeError(f"kỳ thi {n} câu nhưng OMR chỉ đọc {len(res.cau)} câu")

    # Kênh thứ hai: chữ số viết tay (CNN) + đối chiếu với bubble. Luật Q3: ô viết tay trống chỉ được nhận theo bubble khi bubble chắc
    # VÀ SBD (mã đề) có trong danh sách thí sinh (các mã đề) của kỳ thi; chưa kiểm được (bubble có '?') -> cần xem.
    t2 = time.perf_counter()
    hv = ocr_cnn.doc_chu_so(kq, layout, mh.ocr)
    t_ocr = (time.perf_counter() - t2) * 1000
    sbd_trong = None if "?" in res.sbd else tim_sinh_vien(conn, exam_id, res.sbd) is not None
    ma_trong = None if "?" in res.ma_de else conn.execute(
        "SELECT 1 FROM exam_codes WHERE exam_id = %s AND code = %s", (exam_id, res.ma_de)).fetchone() is not None
    dc = ocr_cnn.doi_chieu_dinh_danh(res, hv, sbd_trong, ma_trong, mo_hinh=mh.ocr)
    sbd_j = _truong_json(res.sbd_cot, hv.sbd, dc["cot"]["sbd"], dc["sbd"][2], dc["sbd"][1])
    ma_j = _truong_json(res.ma_de_cot, hv.ma_de, dc["cot"]["ma_de"], dc["ma_de"][2], dc["ma_de"][1])

    detail = {"nguon_anh": res.nguon_anh, "phien_ban_mo_hinh": res.phien_ban_mo_hinh, "sbd": sbd_j,
              "ma_de": ma_j, "dich_chuyen_mm": {k: list(v) for k, v in res.dich_chuyen_mm.items()},
              "ocr": {"phien_ban_mo_hinh": mh.phien_ban_ocr, "sbd_trong_ds": sbd_trong, "ma_de_trong_ds": ma_trong,
                      "tau_khop": mh.ocr.tau_khop},
              "preprocess": {"huong_xoay": kq.huong_xoay, "exif": kq.exif_orientation,
                             "blur_score": None if kq.blur_score is None else float(kq.blur_score)},
              "ms": {"tien_xu_ly": round(t_pre), "omr": round(t_omr), "ocr": round(t_ocr)}}
    sheet_id = conn.execute(
        "INSERT INTO answer_sheets (exam_id, batch_id, image_path, aligned_image_path, image_hash, original_filename, uploaded_by, "
        "status, detected_sbd, sbd_confidence, detected_exam_code, exam_code_confidence, omr_model_id, ocr_model_id, omr_detail, "
        "processing_time_ms) "
        "VALUES (%(exam_id)s, %(batch_id)s, %(image_path)s, %(nan)s, %(image_hash)s, %(filename)s, %(user_id)s, 'processing', "
        "%(sbd)s, %(sbd_c)s, %(ma)s, %(ma_c)s, %(model)s, %(ocr_model)s, %(detail)s, %(ms)s) RETURNING sheet_id",
        {**chung, "nan": rel_nan, "sbd": res.sbd, "sbd_c": min(c["do_tin_cay"] for c in sbd_j["cot"]),
         "ma": res.ma_de, "ma_c": min(c["do_tin_cay"] for c in ma_j["cot"]), "model": mo_hinh_id(conn, mh),
         "ocr_model": mo_hinh_ocr_id(conn, mh), "detail": Jsonb(detail), "ms": round(t_pre + t_omr + t_ocr)}).fetchone()["sheet_id"]
    _ghi_ocr_digits(conn, cfg, exam_id, sha, sheet_id, hv)
    # blur_score KHÔNG ghi vào cột answer_sheets.blur_score: system_settings.min_blur_score (100) là thang Laplacian cũ,
    # khác thang blur_score của preprocess() – ghi vào sẽ làm mọi phiếu bị coi là mờ (nợ kỹ thuật).
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO sheet_answers (sheet_id, question_no, state, selected_options, confidence, option_probs, needs_review, "
            "review_reasons, omr_state, omr_selected_options) VALUES (%s, %s, %s::bubble_state, %s, %s, %s, %s, %s, %s::bubble_state, %s)",
            [(sheet_id, c.cau, omr.sang_bubble_state(c.trang_thai), c.dap_an, c.do_tin_cay, Jsonb(c.xac_suat),
              c.can_xem and not la_nhieu_o_thuan(c.ly_do), list(c.ly_do), omr.sang_bubble_state(c.trang_thai), c.dap_an)
             for c in res.cau[:n]])
    danh_gia_phieu(conn, sheet_id, user_id)
    return sheet_id, False


def la_nhieu_o_thuan(ly_do) -> bool:
    return set(ly_do or ()) == {"nhieu_o"}


# ------------------------------------------------------------------------------------------------ quyết định
def tim_sinh_vien(conn, exam_id: int, sbd: str):
    """SV có student_code = sbd, trong danh sách dự thi của kỳ thi nếu kỳ thi có danh sách (như fn_process_sheet)."""
    return conn.execute(
        "SELECT s.student_id, s.student_code, s.full_name FROM students s WHERE s.student_code = %(sbd)s AND "
        "(NOT EXISTS (SELECT 1 FROM exam_students WHERE exam_id = %(e)s) OR EXISTS "
        "(SELECT 1 FROM exam_students es WHERE es.exam_id = %(e)s AND es.student_id = s.student_id))",
        {"sbd": sbd, "e": exam_id}).fetchone()


def _dap_an(conn, exam_code_id: int, n: int) -> dict:
    return {r["question_no"]: (r["correct_option"], r["points"]) for r in conn.execute(
        "SELECT question_no, correct_option, points FROM answer_keys WHERE exam_code_id = %s AND question_no <= %s",
        (exam_code_id, n)).fetchall()}


def danh_gia_phieu(conn, sheet_id: int, user_id: int, ghi_chu: str | None = None) -> dict:
    """MỘT đường duy nhất quyết định số phận phiếu, gọi sau khi nhận ảnh và sau MỖI lần giáo viên sửa:
    chấm các câu chắc chắn -> gom lý do -> còn lý do: needs_review + mục review_queue; hết lý do: ghi `results`."""
    conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(user_id),))
    sh = conn.execute("SELECT * FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] == "rejected":
        raise XungDot("Phiếu đã bị từ chối (ảnh không dùng được) – hãy tải ảnh mới.")
    ex = conn.execute("SELECT * FROM exams WHERE exam_id = %s", (sh["exam_id"],)).fetchone()
    n = ex["num_questions"]
    rows = conn.execute("SELECT question_no, selected_options, state, needs_review, review_reasons FROM sheet_answers "
                        "WHERE sheet_id = %s AND question_no <= %s ORDER BY question_no", (sheet_id, n)).fetchall()
    det = sh["omr_detail"]
    sbd_cx, ma_cx = det["sbd"]["can_xem"], det["ma_de"]["can_xem"]

    code_id = None
    ma = sh["detected_exam_code"]
    if not ma_cx and ma and "?" not in ma:
        r = conn.execute("SELECT exam_code_id FROM exam_codes WHERE exam_id = %s AND code = %s", (sh["exam_id"], ma)).fetchone()
        code_id = r["exam_code_id"] if r else None
    kq = grading.cham_diem(rows, _dap_an(conn, code_id, n), Decimal(ex["max_score"]) / Decimal(n)) if code_id else None

    ly_do, chi_tiet = [], {"cau_can_xem": {str(r["question_no"]): r["review_reasons"] for r in rows if r["needs_review"]}}
    cho = [r for r in rows if r["needs_review"]]
    if any(set(r["review_reasons"]) & LY_DO_OMR_CAU for r in cho):
        ly_do.append("low_omr_confidence")
    if any("nhieu_o" in r["review_reasons"] for r in cho):
        ly_do.append("multiple_marks")
    if sbd_cx or ma_cx:
        ly_do.append("low_ocr_confidence")
        chi_tiet.update(sbd_can_xem=sbd_cx, ma_de_can_xem=ma_cx)
        if sbd_cx:
            chi_tiet["sbd_ly_do"] = det["sbd"].get("ly_do", [])
        if ma_cx:
            chi_tiet["ma_de_ly_do"] = det["ma_de"].get("ly_do", [])
    if not ma_cx and code_id is None:
        ly_do.append("exam_code_not_found")
        chi_tiet["detected_exam_code"] = ma
    sv = None
    if not sbd_cx:
        sv = tim_sinh_vien(conn, sh["exam_id"], sh["detected_sbd"])
        if sv is None:
            ly_do.append("sbd_not_found")
            chi_tiet["detected_sbd"] = sh["detected_sbd"]
        else:
            trung = conn.execute("SELECT sheet_id FROM results WHERE exam_id = %s AND student_id = %s AND status <> 'void' "
                                 "AND sheet_id <> %s", (sh["exam_id"], sv["student_id"], sheet_id)).fetchone()
            if trung:
                ly_do.append("duplicate_sbd")
                chi_tiet["duplicate_with_sheet_id"] = trung["sheet_id"]

    if kq is not None:                               # is_correct: NULL cho câu cần xem
        with conn.cursor() as cur:
            cur.executemany("UPDATE sheet_answers SET is_correct = %s WHERE sheet_id = %s AND question_no = %s",
                            [(c.is_correct, sheet_id, c.question_no) for c in kq.cau])
    conn.execute("UPDATE answer_sheets SET exam_code_id = %s, matched_student_id = %s, num_correct = %s, raw_score = %s, "
                 "processed_at = now() WHERE sheet_id = %s",
                 (code_id, sv["student_id"] if sv else None, kq.num_correct if kq else None,
                  kq.diem_tam if kq else None, sheet_id))

    if ly_do:
        rv = conn.execute(
            "INSERT INTO review_queue (sheet_id, reasons, details, priority) VALUES (%s, %s::review_reason[], %s, %s) "
            "ON CONFLICT (sheet_id) WHERE status IN ('pending','in_progress') "
            "DO UPDATE SET reasons = EXCLUDED.reasons, details = EXCLUDED.details, priority = EXCLUDED.priority "
            "RETURNING review_id",
            (sheet_id, ly_do, Jsonb(chi_tiet), min(PRIORITY.get(x, 3) for x in ly_do))).fetchone()
        conn.execute("UPDATE answer_sheets SET status = 'needs_review' WHERE sheet_id = %s", (sheet_id,))
        return {"status": "needs_review", "ly_do": ly_do, "review_id": rv["review_id"], "result_id": None}

    # --- hết lý do: chốt điểm chính thức. Đối chiếu chéo với fn_grade_sheet của CSDL.
    diem_db = conn.execute("SELECT fn_grade_sheet(%s) AS s", (sheet_id,)).fetchone()["s"]
    if Decimal(diem_db) != kq.diem_tam or kq.so_cau_can_xem:
        raise RuntimeError(f"phiếu {sheet_id}: điểm Python {kq.diem_tam} ≠ fn_grade_sheet {diem_db} "
                           f"(cần xem còn lại {kq.so_cau_can_xem}) – dừng, không ghi điểm")
    da_review = conn.execute("SELECT 1 FROM review_queue WHERE sheet_id = %s LIMIT 1", (sheet_id,)).fetchone() is not None
    conn.execute("SELECT set_config('app.change_reason', %s, true)",
                 (ghi_chu or ("Giáo viên đã xem lại phiếu" if da_review else "Chấm tự động (OMR, không còn mục cần xem)"),))
    rid = conn.execute(
        "INSERT INTO results (exam_id, student_id, sheet_id, exam_code_id, num_correct, score, status, confirmed_by, confirmed_at) "
        "VALUES (%(e)s, %(s)s, %(sh)s, %(c)s, %(n)s, %(d)s, %(st)s::result_status, %(by)s, "
        "CASE WHEN %(st)s = 'confirmed' THEN now() END) "
        "ON CONFLICT (sheet_id) DO UPDATE SET student_id = EXCLUDED.student_id, exam_code_id = EXCLUDED.exam_code_id, "
        "num_correct = EXCLUDED.num_correct, score = EXCLUDED.score, status = EXCLUDED.status, "
        "confirmed_by = EXCLUDED.confirmed_by, confirmed_at = EXCLUDED.confirmed_at RETURNING result_id",
        {"e": sh["exam_id"], "s": sv["student_id"], "sh": sheet_id, "c": code_id, "n": kq.num_correct, "d": kq.diem_tam,
         "st": "confirmed" if da_review else "auto", "by": user_id if da_review else None}).fetchone()["result_id"]
    conn.execute("UPDATE review_queue SET status = 'resolved', resolved_by = %s, resolution_note = %s, resolved_at = now() "
                 "WHERE sheet_id = %s AND status IN ('pending','in_progress')",
                 (user_id, ghi_chu or "Đã xem hết các mục cần xem", sheet_id))
    conn.execute("UPDATE answer_sheets SET status = 'graded' WHERE sheet_id = %s", (sheet_id,))
    return {"status": "graded", "ly_do": [], "review_id": None, "result_id": rid}


# ------------------------------------------------------------------------------------------------ giáo viên sửa / xác nhận
def xu_ly_cau(conn, sheet_id: int, question_no: int, hanh_dong: str, lua_chon: str | None, user_id: int,
              ghi_chu: str | None = None) -> dict:
    """hanh_dong 'confirm': chấp nhận cách máy đọc; 'set': giáo viên chốt lựa chọn ('' = bỏ trống). Chỉ cho câu đang cần xem.
    Câu cần xem vì định vị (vi_tri) KHÔNG được 'confirm' – máy chưa chắc nó đọc đúng hàng, phải chọn thủ công."""
    sh = conn.execute("SELECT sheet_id, status, exam_id FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] != "needs_review":
        raise XungDot(f"Phiếu {sheet_id} đang ở trạng thái '{sh['status']}', không có câu nào chờ xem.")
    r = conn.execute("SELECT * FROM sheet_answers WHERE sheet_id = %s AND question_no = %s FOR UPDATE",
                     (sheet_id, question_no)).fetchone()
    if not r or not r["needs_review"]:
        raise XungDot(f"Câu {question_no} của phiếu {sheet_id} không ở trạng thái cần xem.")
    if hanh_dong == "confirm":
        if "vi_tri" in r["review_reasons"]:
            raise DuLieuSai("Câu này cần xem vì không chắc vị trí hàng trên ảnh – hãy chọn đáp án thủ công (action = 'set').")
        chon = r["omr_selected_options"] or ""
    elif hanh_dong == "set":
        if lua_chon is None:
            raise DuLieuSai("Thiếu selected_options (chuỗi rỗng = bỏ trống).")
        try:
            chon = grading.chuan_hoa_lua_chon(lua_chon, 4)
        except ValueError as e:
            raise DuLieuSai(str(e)) from e
    else:
        raise DuLieuSai("action chỉ nhận 'confirm' hoặc 'set'.")
    conn.execute("UPDATE sheet_answers SET selected_options = %s, state = %s::bubble_state, needs_review = FALSE, "
                 "manually_edited = %s, reviewed_by = %s, reviewed_at = now() WHERE sheet_id = %s AND question_no = %s",
                 (chon, grading.trang_thai_tu_lua_chon(chon), chon != (r["omr_selected_options"] or ""), user_id, sheet_id,
                  question_no))
    return danh_gia_phieu(conn, sheet_id, user_id, ghi_chu)


def sua_dinh_danh(conn, sheet_id: int, sbd: str | None, ma_de: str | None, user_id: int, ghi_chu: str | None = None) -> dict:
    """Giáo viên chốt SBD và / hoặc mã đề (khi máy gắn cần xem hoặc đọc không khớp danh sách). Ghi vết trong omr_detail."""
    sh = conn.execute("SELECT * FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] != "needs_review":
        raise XungDot(f"Phiếu {sheet_id} đang ở trạng thái '{sh['status']}', không sửa được SBD / mã đề.")
    if sbd is None and ma_de is None:
        raise DuLieuSai("Cần sbd và / hoặc exam_code.")
    for ten, v in (("sbd", sbd), ("exam_code", ma_de)):
        if v is not None and not (v.isdigit() and 1 <= len(v) <= 20):
            raise DuLieuSai(f"{ten} phải gồm các chữ số.")
    det = sh["omr_detail"]
    det.setdefault("giao_vien_sua", []).append({"sbd": sbd, "ma_de": ma_de, "boi": user_id, "cu": [sh["detected_sbd"], sh["detected_exam_code"]]})
    if sbd is not None:
        det["sbd"]["can_xem"] = False
    if ma_de is not None:
        det["ma_de"]["can_xem"] = False
    conn.execute("UPDATE answer_sheets SET detected_sbd = COALESCE(%s, detected_sbd), detected_exam_code = COALESCE(%s, detected_exam_code), "
                 "sbd_confidence = CASE WHEN %s::text IS NULL THEN sbd_confidence ELSE 1 END, "
                 "exam_code_confidence = CASE WHEN %s::text IS NULL THEN exam_code_confidence ELSE 1 END, omr_detail = %s "
                 "WHERE sheet_id = %s", (sbd, ma_de, sbd, ma_de, Jsonb(det), sheet_id))
    # Dữ liệu cho lần tinh chỉnh sau (human-in-the-loop; KHÔNG tự huấn luyện lại): chữ số giáo viên chốt theo từng ô viết tay.
    # Chỉ ghi khi độ dài khớp số ô trên phiếu (SBD 6, mã đề 3); sai độ dài thì không biết chữ số nào ứng với ô nào.
    for truong, v, cols in (("sbd", sbd, det["sbd"]["cot"]), ("exam_code", ma_de, det["ma_de"]["cot"])):
        if v is not None and len(v) == len(cols):
            with conn.cursor() as cur:
                cur.executemany("UPDATE ocr_digits SET corrected_digit = %s WHERE sheet_id = %s AND field = %s::ocr_field AND position = %s",
                                [(d, sheet_id, truong, i) for i, d in enumerate(v)])
    return danh_gia_phieu(conn, sheet_id, user_id, ghi_chu)


def _tu_cham_can_xem(r) -> bool:
    return (not r["needs_review"]) and "nhieu_o" in (r["review_reasons"] or []) and r["reviewed_at"] is None


def ghi_dap_an_va_cham_lai(conn, sheet_id: int, question_no: int, chon: str, user_id: int, danh_dau_da_xem: bool,
                           ly_do_sua: str | None = None, hoan_tac: bool = False) -> dict:
    sh = conn.execute("SELECT * FROM answer_sheets WHERE sheet_id = %s", (sheet_id,)).fetchone()
    ex = conn.execute("SELECT * FROM exams WHERE exam_id = %s", (sh["exam_id"],)).fetchone()
    n = ex["num_questions"]
    cu = conn.execute("SELECT selected_options, omr_selected_options FROM sheet_answers WHERE sheet_id = %s AND question_no = %s",
                      (sheet_id, question_no)).fetchone()
    conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(user_id),))
    conn.execute("UPDATE sheet_answers SET selected_options = %s, state = %s::bubble_state, manually_edited = %s, "
                 "reviewed_by = CASE WHEN %s THEN %s ELSE reviewed_by END, reviewed_at = CASE WHEN %s THEN now() ELSE reviewed_at END "
                 "WHERE sheet_id = %s AND question_no = %s",
                 (chon, grading.trang_thai_tu_lua_chon(chon), chon != (cu["omr_selected_options"] or ""), danh_dau_da_xem, user_id,
                  danh_dau_da_xem, sheet_id, question_no))
    rows = conn.execute("SELECT question_no, selected_options, state, needs_review, review_reasons FROM sheet_answers "
                        "WHERE sheet_id = %s AND question_no <= %s ORDER BY question_no", (sheet_id, n)).fetchall()
    if not sh["exam_code_id"]:
        return {"status": sh["status"], "score": None}
    kq = grading.cham_diem(rows, _dap_an(conn, sh["exam_code_id"], n), Decimal(ex["max_score"]) / Decimal(n))
    with conn.cursor() as cur:
        cur.executemany("UPDATE sheet_answers SET is_correct = %s WHERE sheet_id = %s AND question_no = %s",
                        [(c.is_correct, sheet_id, c.question_no) for c in kq.cau])
    conn.execute("UPDATE answer_sheets SET num_correct = %s, raw_score = %s WHERE sheet_id = %s",
                 (kq.num_correct, kq.diem_tam, sheet_id))
    res = conn.execute("SELECT result_id FROM results WHERE sheet_id = %s AND status <> 'void' FOR UPDATE", (sheet_id,)).fetchone()
    if res is not None:
        if kq.so_cau_can_xem:
            raise RuntimeError(f"phiếu {sheet_id} đã có điểm chính thức nhưng còn {kq.so_cau_can_xem} câu cần xem – dừng")
        diem_db = conn.execute("SELECT fn_grade_sheet(%s) AS s", (sheet_id,)).fetchone()["s"]
        if Decimal(diem_db) != kq.diem_tam:
            raise RuntimeError(f"phiếu {sheet_id}: điểm Python {kq.diem_tam} ≠ fn_grade_sheet {diem_db} – dừng, không ghi điểm")
        conn.execute("SELECT set_config('app.change_reason', %s, true)",
                     (ly_do_sua or f"Giáo viên sửa câu {question_no}: {cu['selected_options'] or 'trống'} → {chon or 'trống'}",))
        trang = "manual_edited"
        if hoan_tac and not conn.execute("SELECT 1 FROM sheet_answers WHERE sheet_id = %s AND manually_edited", (sheet_id,)).fetchone():
            da_review = conn.execute("SELECT 1 FROM review_queue WHERE sheet_id = %s LIMIT 1", (sheet_id,)).fetchone() is not None
            trang = "confirmed" if da_review else "auto"
        conn.execute("UPDATE results SET num_correct = %s, score = %s, status = %s::result_status, "
                     "confirmed_by = CASE WHEN %s = 'auto' THEN NULL ELSE %s END, "
                     "confirmed_at = CASE WHEN %s = 'auto' THEN NULL ELSE now() END WHERE result_id = %s",
                     (kq.num_correct, kq.diem_tam, trang, trang, user_id, trang, res["result_id"]))
    return {"status": sh["status"], "score": kq.diem_tam}


def xem_lai_cau_tu_cham(conn, sheet_id: int, question_no: int, hanh_dong: str, lua_chon: str | None, user_id: int,
                        ghi_chu: str | None = None) -> dict:
    sh = conn.execute("SELECT sheet_id, status FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] not in ("graded", "needs_review"):
        raise XungDot(f"Phiếu {sheet_id} đang ở trạng thái '{sh['status']}', không có câu nào đã chấm tự động để xem lại.")
    r = conn.execute("SELECT * FROM sheet_answers WHERE sheet_id = %s AND question_no = %s FOR UPDATE", (sheet_id, question_no)).fetchone()
    if not r or not _tu_cham_can_xem(r):
        raise XungDot(f"Câu {question_no} của phiếu {sheet_id} không ở trạng thái 'đã chấm tự động – cần xem lại'.")
    if hanh_dong == "keep":
        chon = r["selected_options"] or ""
    elif hanh_dong == "set":
        if lua_chon is None:
            raise DuLieuSai("Thiếu selected_options (chuỗi rỗng = bỏ trống).")
        try:
            chon = grading.chuan_hoa_lua_chon(lua_chon, 4)
        except ValueError as e:
            raise DuLieuSai(str(e)) from e
    else:
        raise DuLieuSai("action chỉ nhận 'keep' hoặc 'set'.")
    if chon == (r["selected_options"] or ""):
        conn.execute("UPDATE sheet_answers SET reviewed_by = %s, reviewed_at = now() WHERE sheet_id = %s AND question_no = %s",
                     (user_id, sheet_id, question_no))
        return {"status": sh["status"], "da_sua": False}
    ghi_dap_an_va_cham_lai(conn, sheet_id, question_no, chon, user_id, True, ghi_chu)
    return {"status": sh["status"], "da_sua": True}


def hoan_tac_cau(conn, sheet_id: int, question_no: int, user_id: int) -> dict:
    sh = conn.execute("SELECT sheet_id, status FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] == "rejected":
        raise XungDot("Phiếu đang ở trạng thái 'rejected' (ảnh bị từ chối) – không hoàn tác được.")
    if sh["status"] not in ("graded", "needs_review"):
        raise XungDot(f"Phiếu {sheet_id} đang ở trạng thái '{sh['status']}', không có câu nào để hoàn tác.")
    r = conn.execute("SELECT * FROM sheet_answers WHERE sheet_id = %s AND question_no = %s FOR UPDATE", (sheet_id, question_no)).fetchone()
    if not r or r["reviewed_at"] is None:
        raise XungDot(f"Câu {question_no} của phiếu {sheet_id} chưa được giáo viên xem – không có gì để hoàn tác.")
    conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(user_id),))
    if la_nhieu_o_thuan(r["review_reasons"]):
        ghi_dap_an_va_cham_lai(conn, sheet_id, question_no, r["omr_selected_options"] or "", user_id, False,
                               f"Giáo viên hoàn tác xem lại câu {question_no}", hoan_tac=True)
        conn.execute("UPDATE sheet_answers SET state = COALESCE(omr_state, state), needs_review = FALSE, manually_edited = FALSE, "
                     "reviewed_by = NULL, reviewed_at = NULL WHERE sheet_id = %s AND question_no = %s", (sheet_id, question_no))
        return {"status": sh["status"], "loai": "tu_cham"}
    conn.execute("SELECT set_config('app.change_reason', %s, true)", (f"Giáo viên hoàn tác xác nhận câu {question_no}",))
    conn.execute("UPDATE sheet_answers SET selected_options = COALESCE(omr_selected_options, ''), state = COALESCE(omr_state, state), "
                 "needs_review = TRUE, manually_edited = FALSE, reviewed_by = NULL, reviewed_at = NULL, is_correct = NULL "
                 "WHERE sheet_id = %s AND question_no = %s", (sheet_id, question_no))
    res = conn.execute("SELECT result_id FROM results WHERE sheet_id = %s AND status <> 'void' FOR UPDATE", (sheet_id,)).fetchone()
    if res is not None:
        conn.execute("UPDATE results SET status = 'void' WHERE result_id = %s", (res["result_id"],))
        conn.execute("UPDATE answer_sheets SET status = 'needs_review' WHERE sheet_id = %s", (sheet_id,))
    kq = danh_gia_phieu(conn, sheet_id, user_id, f"Giáo viên hoàn tác xác nhận câu {question_no}")
    return {"status": kq["status"], "loai": "cho"}


def giu_nhu_may_cham(conn, muc: list[tuple[int, int]], user_id: int) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    da, bo_qua = [], []
    for sheet_id, question_no in sorted(set(muc)):
        sh = conn.execute("SELECT status FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
        r = conn.execute("SELECT * FROM sheet_answers WHERE sheet_id = %s AND question_no = %s FOR UPDATE",
                         (sheet_id, question_no)).fetchone()
        if not sh or sh["status"] not in ("graded", "needs_review") or not r or not _tu_cham_can_xem(r):
            bo_qua.append((sheet_id, question_no))
            continue
        conn.execute("UPDATE sheet_answers SET reviewed_by = %s, reviewed_at = now() WHERE sheet_id = %s AND question_no = %s",
                     (user_id, sheet_id, question_no))
        da.append((sheet_id, question_no))
    return da, bo_qua


def cau_tu_cham_can_xem(conn, exam_id: int, gioi_han: int = 500) -> list[dict]:
    if not conn.execute("SELECT 1 FROM exams WHERE exam_id = %s", (exam_id,)).fetchone():
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    return conn.execute(
        "SELECT q.sheet_id, q.question_no, q.omr_selected_options AS omr_reading, q.selected_options, a.original_filename, a.detected_sbd, "
        "s.full_name AS student_name, r.score AS official_score, r.status::text AS result_status, a.status::text AS sheet_status "
        "FROM sheet_answers q JOIN answer_sheets a USING (sheet_id) LEFT JOIN students s ON s.student_id = a.matched_student_id "
        "LEFT JOIN results r ON r.sheet_id = a.sheet_id AND r.status <> 'void' "
        "WHERE a.exam_id = %s AND a.status IN ('graded', 'needs_review') AND NOT q.needs_review AND 'nhieu_o' = ANY(q.review_reasons) "
        "AND q.reviewed_at IS NULL ORDER BY q.sheet_id, q.question_no LIMIT %s", (exam_id, gioi_han)).fetchall()


# ------------------------------------------------------------------------------------------------ đọc kết quả
def xem_phieu(conn, sheet_id: int) -> dict:
    sh = conn.execute("SELECT * FROM answer_sheets WHERE sheet_id = %s", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    ex = conn.execute("SELECT * FROM exams WHERE exam_id = %s", (sh["exam_id"],)).fetchone()
    rows = conn.execute("SELECT * FROM sheet_answers WHERE sheet_id = %s ORDER BY question_no", (sheet_id,)).fetchall()
    kq = None
    if sh["exam_code_id"]:
        kq = grading.cham_diem(rows, _dap_an(conn, sh["exam_code_id"], ex["num_questions"]),
                               Decimal(ex["max_score"]) / Decimal(ex["num_questions"]))
    res = conn.execute("SELECT result_id, score, num_correct, status FROM results WHERE sheet_id = %s AND status <> 'void'",
                       (sheet_id,)).fetchone()
    sv = conn.execute("SELECT student_id, student_code, full_name FROM students WHERE student_id = %s",
                      (sh["matched_student_id"],)).fetchone() if sh["matched_student_id"] else None
    rv = conn.execute("SELECT review_id, reasons::text[] AS reasons, status::text AS status, priority, details FROM review_queue WHERE sheet_id = %s "
                      "ORDER BY review_id DESC LIMIT 1", (sheet_id,)).fetchone()
    code = conn.execute("SELECT code FROM exam_codes WHERE exam_code_id = %s", (sh["exam_code_id"],)).fetchone() if sh["exam_code_id"] else None
    det = sh["omr_detail"] or {}
    ocr_rows = {(r["field"], r["position"]): r for r in conn.execute(
        "SELECT field::text AS field, position, corrected_digit, crop_image_path IS NOT NULL AS co_anh FROM ocr_digits WHERE sheet_id = %s",
        (sheet_id,)).fetchall()}

    def cot_ra(truong: str, khoa: str) -> list[dict]:
        """Cột của omr_detail + chữ viết tay (phiếu cũ trước Tuần 6 không có `handwriting`) + chữ số giáo viên chốt / có ảnh cắt."""
        ra = []
        for c in det[khoa]["cot"]:
            c = dict(c)
            hw = c.get("handwriting")
            if hw is not None:
                r = ocr_rows.get((truong, hw["pos"]))
                hw = {**hw, "corrected": r["corrected_digit"] if r else None, "has_crop": bool(r and r["co_anh"])}
            c["handwriting"] = hw
            ra.append(c)
        return ra

    def truong_ra(truong: str, khoa: str, detected) -> dict:
        """Lệnh W2: phiếu KHÔNG có chi tiết đọc (omr_detail NULL / thiếu khoá – vd phiếu mẫu của database/04_seed.sql, chèn thẳng trước khi có backend)
        -> giá trị đọc được vẫn trả (cột detected_*), không có cột, không có cờ / lý do nào, co_chi_tiet = False. KHÔNG sửa dữ liệu."""
        d = det.get(khoa)
        if not isinstance(d, dict):
            return {"detected": detected, "can_xem": False, "reasons": [], "columns": [], "co_chi_tiet": False}
        return {"detected": detected, "can_xem": d["can_xem"], "reasons": d.get("ly_do", []), "columns": cot_ra(truong, khoa), "co_chi_tiet": True}
    return {
        "sheet_id": sheet_id, "exam_id": sh["exam_id"], "status": sh["status"], "original_filename": sh["original_filename"],
        "uploaded_at": sh["uploaded_at"], "reject_code": sh["reject_code"], "reject_message": sh["error_message"],
        "sbd": None if sh["status"] == "rejected" else truong_ra("sbd", "sbd", sh["detected_sbd"]),
        "exam_code": None if sh["status"] == "rejected" else {**truong_ra("exam_code", "ma_de", sh["detected_exam_code"]),
                                                              "matched_code": code["code"] if code else None},
        "student": dict(sv) if sv else None,
        "score": None if sh["status"] == "rejected" else {
            "official": res["score"] if res else None, "result_status": res["status"] if res else None,
            "provisional": kq.diem_tam if kq else None, "max_possible": kq.diem_toi_da if kq else None,
            "num_correct": (res["num_correct"] if res else (kq.num_correct if kq else None)),
            "pending_questions": sum(1 for r in rows if r["needs_review"]),
            "auto_graded_pending": sum(1 for r in rows if _tu_cham_can_xem(r)), "max_score": ex["max_score"]},
        "review": dict(rv) if rv else None,
        "questions": [{"question_no": r["question_no"], "selected_options": r["selected_options"], "state": r["state"],
                       "needs_review": r["needs_review"], "reasons": r["review_reasons"], "is_correct": r["is_correct"],
                       "manually_edited": r["manually_edited"], "omr_selected_options": r["omr_selected_options"],
                       "confidence": r["confidence"], "tu_cham_can_xem": _tu_cham_can_xem(r),
                       "da_xem": r["reviewed_at"] is not None} for r in rows],
        "image_deleted_at": anh_da_xoa_luc(conn, sheet_id),
    }


def ds_phieu_ky_thi(conn, exam_id: int, status: str | None = None, gioi_han: int = 200) -> list[dict]:
    if not conn.execute("SELECT 1 FROM exams WHERE exam_id = %s", (exam_id,)).fetchone():
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    return conn.execute(
        "SELECT a.sheet_id, a.status, a.original_filename, a.detected_sbd, a.detected_exam_code, a.reject_code, a.error_message AS reject_message, "
        "a.raw_score, r.score AS official_score, r.status::text AS result_status, s.full_name AS student_name, "
        "(SELECT count(*) FROM sheet_answers q WHERE q.sheet_id = a.sheet_id AND q.needs_review) AS pending_questions, "
        "(SELECT count(*) FROM sheet_answers q WHERE q.sheet_id = a.sheet_id AND NOT q.needs_review AND 'nhieu_o' = ANY(q.review_reasons) "
        "AND q.reviewed_at IS NULL) AS auto_graded_pending "
        "FROM answer_sheets a LEFT JOIN results r ON r.sheet_id = a.sheet_id AND r.status <> 'void' "
        "LEFT JOIN students s ON s.student_id = a.matched_student_id "
        "WHERE a.exam_id = %s AND (%s::text IS NULL OR a.status::text = %s) ORDER BY a.sheet_id LIMIT %s",
        (exam_id, status, status, gioi_han)).fetchall()


def cau_can_xem(conn, sheet_id: int | None = None, exam_id: int | None = None, gioi_han: int = 500) -> list[dict]:
    """Danh sách câu OMR gắn 'cần xem' còn chờ giáo viên (của một phiếu hoặc cả kỳ thi)."""
    if sheet_id is not None and not conn.execute("SELECT 1 FROM answer_sheets WHERE sheet_id = %s", (sheet_id,)).fetchone():
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    return conn.execute(
        "SELECT q.sheet_id, q.question_no, q.omr_selected_options AS omr_reading, q.omr_state::text AS omr_state, "
        "q.review_reasons AS reasons, q.confidence, q.option_probs FROM sheet_answers q JOIN answer_sheets a USING (sheet_id) "
        "WHERE q.needs_review AND a.status = 'needs_review' AND (%s::bigint IS NULL OR q.sheet_id = %s) "
        "AND (%s::bigint IS NULL OR a.exam_id = %s) ORDER BY q.sheet_id, q.question_no LIMIT %s",
        (sheet_id, sheet_id, exam_id, exam_id, gioi_han)).fetchall()


def duong_dan_anh(conn, cfg: CauHinh, sheet_id: int, loai: str) -> Path:
    """loai 'goc' | 'nan' -> đường dẫn file trên đĩa (kiểm không thoát khỏi thư mục lưu trữ)."""
    r = conn.execute("SELECT image_path, aligned_image_path FROM answer_sheets WHERE sheet_id = %s", (sheet_id,)).fetchone()
    if not r:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    if anh_da_xoa_luc(conn, sheet_id):
        raise AnhDaXoa(THONG_BAO_ANH_DA_XOA)
    rel = r["image_path"] if loai == "goc" else r["aligned_image_path"]
    if not rel:
        raise KhongTimThay("Phiếu không có ảnh đã nắn (ảnh bị từ chối).")
    p = (cfg.storage_dir / rel).resolve()
    if cfg.storage_dir.resolve() not in p.parents or not p.exists():
        raise KhongTimThay("Không thấy file ảnh trên đĩa.")
    return p


def cat_anh_cau(conn, cfg: CauHinh, sheet_id: int, question_no: int) -> bytes:
    """PNG cắt hàng câu từ ảnh đã nắn (tại vị trí OMR đã dò), vẽ vòng quanh 4 ô – để giáo viên xem câu cần xem."""
    sh = conn.execute("SELECT omr_detail, status FROM answer_sheets WHERE sheet_id = %s", (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    p = duong_dan_anh(conn, cfg, sheet_id, "nan")
    layout = nap_layout("phieu")
    ans = layout["answers"]
    if str(question_no) not in ans["centers"]:
        raise KhongTimThay(f"Không có câu {question_no} trên mẫu phiếu.")
    anh = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
    px = layout["dpi"] / 25.4
    dx, dy = (v * px for v in (sh["omr_detail"]["dich_chuyen_mm"].get(f"q{question_no}") or (0, 0)))   # mm -> px
    c = ans["centers"][str(question_no)]
    xs = [c[o][0] + dx for o in ans["options"]]
    cy = c["A"][1] + dy
    for o in ans["options"]:
        cv2.circle(anh, (int(c[o][0] + dx), int(cy)), int(ans["bubble_radius"] * 1.25), (0, 140, 255), 2)
    x0, y0, x1, y1 = int(min(xs) - 12 * px), int(cy - 5 * px), int(max(xs) + 5 * px), int(cy + 5 * px)
    crop = cv2.resize(anh[max(y0, 0):y1, max(x0, 0):x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return cv2.imencode(".png", crop)[1].tobytes()


def anh_chu_so(conn, cfg: CauHinh, sheet_id: int, truong: str, vi_tri: int) -> Path:
    """Đường dẫn PNG ô viết tay (truong 'sbd' | 'exam_code') – để giáo viên so với chữ số bubble."""
    r = conn.execute("SELECT crop_image_path FROM ocr_digits WHERE sheet_id = %s AND field = %s::ocr_field AND position = %s",
                     (sheet_id, truong, vi_tri)).fetchone()
    if anh_da_xoa_luc(conn, sheet_id):
        raise AnhDaXoa(THONG_BAO_ANH_DA_XOA)
    if not r or not r["crop_image_path"]:
        raise KhongTimThay("Không có ảnh ô viết tay này (phiếu cũ hoặc bị từ chối).")
    p = (cfg.storage_dir / r["crop_image_path"]).resolve()
    if cfg.storage_dir.resolve() not in p.parents or not p.exists():
        raise KhongTimThay("Không thấy file ảnh trên đĩa.")
    return p
