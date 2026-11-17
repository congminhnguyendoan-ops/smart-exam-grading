"""Kiểm thử API backend (B4). Chạy trên CSDL thật trong giao dịch ROLLBACK + thư mục ảnh tạm (xem conftest.py: conn_thu, client).
Chỉ dùng ảnh dev 0001–0028 và ảnh giả sinh từ ảnh dev; không đụng 0029–0040."""
import io
import uuid

import cv2
import numpy as np
import pytest

from backend import demo
from cv_engine.preprocessing import MA_LY_DO
from conftest import ROOT, can_file

RAW = ROOT / "data" / "raw"


def ma_mon() -> str:
    return "T" + uuid.uuid4().hex[:8].upper()


def tao_de(client, n=40, ma_de=("101", "102", "103", "104")) -> int:
    r = client.post("/exams", json={"exam_title": "Đề thử (pytest)", "subject_code": ma_mon(), "num_questions": n,
                                    "codes": [{"code": m, "answers": demo.khoa_demo(m, n)} for m in ma_de]})
    assert r.status_code == 201, r.text
    return r.json()["exam_id"]


def them_sv(conn, code: str) -> None:
    conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV thử') ON CONFLICT DO NOTHING", (code,))


def tai(client, exam_id, ten, du_lieu=None, url=None):
    du_lieu = du_lieu if du_lieu is not None else (RAW / f"{ten}.jpg").read_bytes()
    return client.post(url or f"/exams/{exam_id}/sheets", files={"file": (f"{ten}.jpg", du_lieu, "image/jpeg")})


def anh_trang() -> bytes:
    return cv2.imencode(".jpg", np.full((1200, 900), 235, np.uint8))[1].tobytes()


def can_anh(*ten):
    can_file(*[RAW / f"{t}.jpg" for t in ten], ROOT / "data" / "ground_truth.csv")


def dem_results(conn, sheet_id) -> int:
    return conn.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s", (sheet_id,)).fetchone()["n"]


def giai_quyet_het(client, sheet_id) -> dict:
    """Giáo viên 'confirm' mọi câu cần xem (câu cần xem vì vị trí thì 'set' theo máy đọc) cho tới khi hết."""
    for c in client.get(f"/sheets/{sheet_id}/review-questions").json():
        if "vi_tri" in c["reasons"]:
            body = {"action": "set", "selected_options": c["omr_reading"] or ""}
        else:
            body = {"action": "confirm"}
        r = client.post(f"/sheets/{sheet_id}/questions/{c['question_no']}/review", json=body)
        assert r.status_code == 200, r.text
    return client.get(f"/sheets/{sheet_id}").json()


# ------------------------------------------------------------------------------------------------ hệ thống / đề thi
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["db"] == "ok" and r.json()["omr_model"].startswith("omr_m1-")


def test_tao_xem_ky_thi(client):
    eid = tao_de(client, n=10, ma_de=("101", "102"))
    d = client.get(f"/exams/{eid}").json()
    assert d["num_questions"] == 10 and {c["code"] for c in d["codes"]} == {"101", "102"}
    assert d["codes"][0]["answers"] == demo.khoa_demo("101", 10) and d["sheets"] == {"tong": 0, "da_cham": 0, "can_xem": 0, "bi_tu_choi": 0}
    assert eid in {e["exam_id"] for e in client.get("/exams").json()}
    assert client.get("/exams/999999").status_code == 404


@pytest.mark.parametrize("sua", [
    {"codes": [{"code": "101", "answers": "ABC"}]},                          # sai độ dài
    {"codes": [{"code": "101", "answers": "ABCDEABCDE"}]},                   # đáp án E
    {"codes": [{"code": "10a", "answers": "ABCDABCDAB"}]},                   # mã đề không phải số
    {"codes": [{"code": "101", "answers": "ABCDABCDAB"}, {"code": "101", "answers": "ABCDABCDAB"}]},   # trùng mã đề
    {"num_questions": 41}, {"num_questions": 0}, {"codes": []}, {"max_score": 0},
])
def test_tao_ky_thi_sai_bi_tu_choi(client, sua):
    body = {"exam_title": "Đề thử", "subject_code": ma_mon(), "num_questions": 10,
            "codes": [{"code": "101", "answers": "ABCDABCDAB"}], **sua}
    assert client.post("/exams", json=body).status_code == 422


# ------------------------------------------------------------------------------------------------ ảnh bị từ chối
# Lệnh AU (T3): tệp KHÔNG phải ảnh nay bị từ chối sớm bằng 422 (kiem_anh.py, test_trien_khai.py) thay vì lưu rồi báo `khong_doc_duoc`;
# mã `khong_doc_duoc` vẫn còn cho tệp đúng chữ ký ảnh nhưng hỏng bên trong. Ảnh thiếu marker vẫn 201 + rejected như cũ.
@pytest.mark.parametrize("du_lieu,ma", [pytest.param(anh_trang(), "thieu_marker", id="thieu_marker")])
def test_anh_hong_bi_tu_choi_dung_ma(client, conn_thu, du_lieu, ma):
    eid = tao_de(client)
    r = tai(client, eid, "hong", du_lieu)
    assert r.status_code == 201
    j = r.json()
    assert (j["status"], j["reject_code"], j["reject_message"]) == ("rejected", ma, MA_LY_DO[ma])
    assert j["official_score"] is None and j["provisional_score"] is None
    assert dem_results(conn_thu, j["sheet_id"]) == 0
    v = client.get(f"/sheets/{j['sheet_id']}").json()
    assert v["score"] is None and v["questions"] == [] and v["reject_code"] == ma
    assert client.post(f"/sheets/{j['sheet_id']}/questions/1/review", json={"action": "confirm"}).status_code == 409
    assert client.put(f"/sheets/{j['sheet_id']}/identity", json={"sbd": "123456"}).status_code == 409
    assert client.get(f"/sheets/{j['sheet_id']}/image?kind=aligned").status_code == 404       # không có ảnh nắn
    assert client.get(f"/sheets/{j['sheet_id']}/image?kind=original").status_code == 200


def test_anh_gia_anh_mo_bi_tu_choi(client):
    mo = ROOT / "data" / "_eval" / "_gia_v4"
    ds = sorted(mo.glob("mo_*0001_C1*.jpg")) if mo.exists() else []
    if not ds:
        pytest.skip("không có ảnh giả mờ (_gia_v4)")
    eid = tao_de(client)
    r = tai(client, eid, ds[-1].stem, ds[-1].read_bytes()).json()                              # mờ nặng nhất
    assert r["status"] == "rejected" and r["reject_code"] in ("anh_mo", "khong_khop_bo_cuc") and r["official_score"] is None


# ------------------------------------------------------------------------------------------------ ảnh thật: cần xem -> giáo viên -> chốt
def test_phieu_can_xem_khong_co_diem_chinh_thuc_roi_chot(client, conn_thu):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    t = tai(client, eid, "0002_C2").json()
    sid = t["sheet_id"]
    assert t["status"] == "needs_review" and t["pending_questions"] > 0 and t["official_score"] is None
    v = client.get(f"/sheets/{sid}").json()
    assert dem_results(conn_thu, sid) == 0 and v["score"]["official"] is None            # CHƯA có điểm chính thức
    assert v["sbd"]["detected"] == "795125" and v["student"]["student_code"] == "795125"
    sc = v["score"]
    assert sc["provisional"] <= sc["max_possible"] and sc["pending_questions"] == t["pending_questions"]
    cx = [q for q in v["questions"] if q["needs_review"]]
    assert len(cx) == sc["pending_questions"] and all(q["is_correct"] is None for q in cx)    # câu cần xem: chưa chấm
    assert all(q["is_correct"] is not None for q in v["questions"] if not q["needs_review"])
    assert v["review"]["status"] == "pending" and set(v["review"]["reasons"]) & {"low_omr_confidence", "multiple_marks"}
    ds = client.get(f"/sheets/{sid}/review-questions").json()
    assert {c["question_no"] for c in ds} == {q["question_no"] for q in cx}
    assert {c["question_no"] for c in client.get(f"/exams/{eid}/review-questions").json()} == {c["question_no"] for c in ds}
    img = client.get(f"/sheets/{sid}/questions/{ds[0]['question_no']}/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"

    # sửa 1 câu: điểm tạm thay đổi, vẫn chưa có điểm chính thức
    q0 = ds[0]["question_no"]
    r = client.post(f"/sheets/{sid}/questions/{q0}/review", json={"action": "set", "selected_options": "A"})
    assert r.status_code == 200 and r.json()["score"]["pending_questions"] == sc["pending_questions"] - 1
    assert r.json()["score"]["official"] is None and dem_results(conn_thu, sid) == 0
    assert client.post(f"/sheets/{sid}/questions/{q0}/review", json={"action": "confirm"}).status_code == 409   # đã xử lý rồi

    fin = giai_quyet_het(client, sid)
    assert fin["status"] == "graded" and fin["score"]["official"] is not None and fin["score"]["result_status"] == "confirmed"
    assert fin["score"]["pending_questions"] == 0 and fin["review"]["status"] == "resolved"
    assert dem_results(conn_thu, sid) == 1
    assert fin["score"]["official"] == fin["score"]["provisional"] == fin["score"]["max_possible"]
    assert conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs a JOIN results r USING (result_id) WHERE r.sheet_id = %s",
                            (sid,)).fetchone()["n"] >= 1                                       # trigger audit hoạt động


def test_tai_lai_cung_anh_tra_phieu_cu(client):
    can_anh("0002_C2")
    eid = tao_de(client)
    a = tai(client, eid, "0002_C2").json()
    b = tai(client, eid, "0002_C2").json()
    assert b["da_ton_tai"] and b["sheet_id"] == a["sheet_id"] and not a["da_ton_tai"]
    assert len(client.get(f"/exams/{eid}/sheets").json()) == 1


def test_confirm_khong_duoc_cho_cau_vi_tri(client, conn_thu):
    """Câu cần xem vì vị trí: 'confirm' bị từ chối (máy chưa chắc đọc đúng hàng) – phải 'set' thủ công."""
    can_anh("0002_C2")
    eid = tao_de(client)
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    q = client.get(f"/sheets/{sid}/review-questions").json()[0]["question_no"]
    conn_thu.execute("UPDATE sheet_answers SET review_reasons = ARRAY['vi_tri'] WHERE sheet_id = %s AND question_no = %s", (sid, q))
    assert client.post(f"/sheets/{sid}/questions/{q}/review", json={"action": "confirm"}).status_code == 422
    assert client.post(f"/sheets/{sid}/questions/{q}/review", json={"action": "set", "selected_options": "B"}).status_code == 200


@pytest.mark.parametrize("body", [{"action": "set"}, {"action": "set", "selected_options": "E"}, {"action": "xoa"}])
def test_review_yeu_cau_sai(client, body):
    can_anh("0002_C2")
    eid = tao_de(client)
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    q = client.get(f"/sheets/{sid}/review-questions").json()[0]["question_no"]
    assert client.post(f"/sheets/{sid}/questions/{q}/review", json=body).status_code == 422


def test_sbd_thieu_cot_can_xem_va_giao_vien_chot(client, conn_thu, monkeypatch):
    """0001_C1: cột SBD 6 không tô -> SBD '06238?' cần xem (dù chữ viết tay đọc được 062384: không tự nhận một kênh duy nhất);
    giáo viên chốt SBD thật rồi xem hết câu -> phiếu được chốt."""
    can_anh("0001_C1")
    ocr_khop(monkeypatch, ("062384", "101"))
    them_sv(conn_thu, "062384")
    eid = tao_de(client)
    sid = tai(client, eid, "0001_C1").json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    assert v["sbd"]["detected"] == "06238?" and v["sbd"]["can_xem"] and v["student"] is None
    assert "low_ocr_confidence" in v["review"]["reasons"]
    assert client.put(f"/sheets/{sid}/identity", json={}).status_code == 422
    assert client.put(f"/sheets/{sid}/identity", json={"sbd": "12ab"}).status_code == 422
    v = client.put(f"/sheets/{sid}/identity", json={"sbd": "062384"}).json()
    assert v["student"]["student_code"] == "062384" and not v["sbd"]["can_xem"] and v["status"] == "needs_review"
    fin = giai_quyet_het(client, sid)
    assert fin["status"] == "graded" and fin["student"]["student_code"] == "062384"
    assert conn_thu.execute("SELECT status::text AS s FROM results WHERE sheet_id = %s", (sid,)).fetchone()["s"] == "confirmed"


def test_sbd_khong_co_trong_danh_sach(client, conn_thu):
    """Giáo viên chốt SBD không có trong danh sách -> sbd_not_found; xem hết câu cần xem vẫn KHÔNG có điểm chính thức."""
    can_anh("0002_C2")
    eid = tao_de(client)
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    v = client.put(f"/sheets/{sid}/identity", json={"sbd": "987654321"}).json()
    assert v["student"] is None and "sbd_not_found" in v["review"]["reasons"] and v["review"]["priority"] == 1
    fin = giai_quyet_het(client, sid)
    assert fin["status"] == "needs_review" and fin["score"]["official"] is None and dem_results(conn_thu, sid) == 0


def test_trung_sbd_phieu_thu_hai_vao_review(client, conn_thu):
    can_anh("0002_C2", "0002_C3")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    a = tai(client, eid, "0002_C2").json()["sheet_id"]
    assert giai_quyet_het(client, a)["status"] == "graded"
    b = client.get(f"/sheets/{tai(client, eid, '0002_C3').json()['sheet_id']}").json()
    assert "duplicate_sbd" in b["review"]["reasons"] and b["review"]["priority"] == 1
    fin = giai_quyet_het(client, b["sheet_id"])
    assert fin["status"] == "needs_review" and fin["score"]["official"] is None            # không ghi đè điểm phiếu đầu
    assert conn_thu.execute("SELECT count(*) AS n FROM results WHERE exam_id = %s", (eid,)).fetchone()["n"] == 1


def test_tai_nhieu_anh_loi_mot_anh_khong_keo_ca_lo(client, conn_thu):
    can_anh("0002_C2", "0003_C3")
    eid = tao_de(client)
    files = [("files", ("0002_C2.jpg", (RAW / "0002_C2.jpg").read_bytes(), "image/jpeg")),
             ("files", ("trang.jpg", anh_trang(), "image/jpeg")),
             ("files", ("rac.jpg", b"xxxx", "image/jpeg")),
             ("files", ("0003_C3.jpg", (RAW / "0003_C3.jpg").read_bytes(), "image/jpeg"))]
    r = client.post(f"/exams/{eid}/sheets/batch", files=files)
    assert r.status_code == 201 and r.json()["tong"] == 4
    kq = r.json()["results"]
    # Lệnh AU (T3): tệp rác (không phải ảnh) nay bị kiem_anh.py từ chối theo TỪNG ẢNH (`error`, không tạo phiếu); các ảnh còn lại không bị ảnh hưởng.
    assert [x.get("status") for x in kq] == ["needs_review", "rejected", None, "needs_review"]
    assert [x.get("reject_code") for x in kq] == [None, "thieu_marker", None, None]
    assert "không phải ảnh" in kq[2]["error"] and kq[2]["filename"] == "rac.jpg"
    d = client.get(f"/exams/{eid}").json()["sheets"]
    assert d == {"tong": 3, "da_cham": 0, "can_xem": 2, "bi_tu_choi": 1}
    assert conn_thu.execute("SELECT count(*) AS n FROM answer_sheets WHERE batch_id = %s", (r.json()["batch_id"],)).fetchone()["n"] == 3
    assert client.get(f"/exams/{eid}/sheets?status=rejected").json().__len__() == 1


def test_anh_len_ky_thi_khong_ton_tai(client):
    assert tai(client, 999999, "x", anh_trang()).status_code == 404
    assert client.get("/sheets/999999").status_code == 404
    assert client.get("/sheets/999999/review-questions").status_code == 404
    assert client.post("/exams/999999/sheets/batch", files=[("files", ("a.jpg", anh_trang(), "image/jpeg"))]).status_code == 404


def test_ky_thi_it_cau_hon_phieu(client):
    """Kỳ thi 10 câu: chỉ chấm 10 câu đầu, các câu còn lại của phiếu bị bỏ qua."""
    can_anh("0002_C2")
    eid = tao_de(client, n=10, ma_de=("101", "102", "103", "104"))
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    assert len(client.get(f"/sheets/{sid}").json()["questions"]) == 10


def test_anh_dinh_kem_khong_thoat_thu_muc_luu_tru(client, conn_thu, cau_hinh_thu):
    can_anh("0002_C2")
    eid = tao_de(client)
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    conn_thu.execute("UPDATE answer_sheets SET aligned_image_path = '../../.env' WHERE sheet_id = %s", (sid,))
    assert client.get(f"/sheets/{sid}/image?kind=aligned").status_code == 404


def test_migration_chay_lai_duoc(conn_thu):
    from backend.migrate import ds_file
    for f in ds_file():
        conn_thu.execute(f.read_text(encoding="utf-8"))
        conn_thu.execute(f.read_text(encoding="utf-8"))


def test_thieu_cau_hinh_bao_loi_ro(monkeypatch):
    from backend.config import LoiCauHinh, lay_cau_hinh
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(LoiCauHinh):
        lay_cau_hinh()


def test_get_conn_rollback_khi_loi(csdl_san_sang):
    """Yêu cầu lỗi -> giao dịch rollback (không để lại dòng nào) và kết nối được đóng."""
    from backend.db import ket_noi
    from backend.main import get_conn
    ma = ma_mon()
    g = get_conn()
    conn = next(g)
    conn.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, 'x')", (ma,))
    with pytest.raises(RuntimeError):
        g.throw(RuntimeError("lỗi giả"))
    assert conn.closed
    with ket_noi() as c2:
        assert c2.execute("SELECT count(*) AS n FROM subjects WHERE subject_code = %s", (ma,)).fetchone()["n"] == 0


# ------------------------------------------------------------------------------------------------ đường tự chốt (không cần xem)
def omr_gia(sbd="795125", ma_de="101", chon=None, mo=(), nhieu=()):
    """KetQuaOMR dựng tay (ảnh thật nào cũng có câu cần xem nên đường tự chốt phải kiểm bằng dữ liệu tạo ra)."""
    from cv_engine.omr import KetQuaCau, KetQuaCot, KetQuaOMR
    chon = chon or {}
    xs = {o: {"blank": 0.99, "faint": 0.0, "filled": 0.01} for o in "ABCD"}
    cau = []
    for q in range(1, 41):
        s = chon.get(q, "")
        if q in mo:
            cau.append(KetQuaCau(q, "mo", s, xs, 0.95, True, ("o_mo",)))
        elif q in nhieu:
            cau.append(KetQuaCau(q, "nhieu", "AB", xs, 0.95, True, ("nhieu_o",)))
        else:
            cau.append(KetQuaCau(q, "ro" if s else "trong", s, xs, 0.99, False, ()))

    def cot(truong, so):
        return tuple(KetQuaCot(truong, i + 1, d, tuple(1.0 if k == int(d) else 0.0 for k in range(10)), 0.99, False, ())
                     for i, d in enumerate(so))
    return KetQuaOMR(cau=tuple(cau), sbd=sbd, sbd_cot=cot("sbd", sbd), ma_de=ma_de, ma_de_cot=cot("ma_de", ma_de), can_xem=bool(mo or nhieu),
                     sbd_can_xem=False, ma_de_can_xem=False, dich_chuyen_mm={}, nguon_anh="anh_nan", phien_ban_mo_hinh="omr_m1",
                     thoi_gian_ms=1.0)


def ocr_khop(monkeypatch, *cap):
    """Thay kênh CHỮ VIẾT TAY (CNN) bằng kết quả dựng tay: mỗi phiếu đọc ĐÚNG như bubble giả (sbd, ma_de), độ tin cậy 0,99.
    Các test này kiểm đường OMR / chấm / chốt điểm, nên hai kênh phải khớp; một cặp = dùng cho mọi phiếu, nhiều cặp = lần lượt.
    (Hành vi khi hai kênh LỆCH được kiểm riêng bằng CNN thật ở test_backend_ocr.py.)"""
    from cv_engine.ocr import CotOCR, KetQuaOCR
    cap = cap or (("795125", "101"),)
    it = iter(cap) if len(cap) > 1 else None

    def cot(so):
        return [CotOCR(i, d, [(int(d), 0.99)], 0.99, False, "", True, True, None, np.full((20, 12), 255, np.uint8)) for i, d in enumerate(so)]

    def gia(kq, layout, mh):
        sbd, ma = next(it) if it else cap[0]
        return KetQuaOCR(cot(sbd), cot(ma), 1.0)
    monkeypatch.setattr("backend.service.ocr_cnn.doc_chu_so", gia)


def test_phieu_sach_tu_chot_auto_va_doi_chieu_csdl(client, conn_thu, monkeypatch):
    """Không còn gì cần xem -> chấm tự động, ghi results 'auto' (không confirmed_by); điểm = điểm tính tay; đối chiếu fn_grade_sheet."""
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    key = demo.khoa_demo("101")
    chon = {q: (key[q - 1] if q % 2 else "A" if key[q - 1] != "A" else "B") for q in range(1, 38)}     # lẻ: đúng, chẵn: sai; 38–40 bỏ trống
    dung = sum(q % 2 == 1 for q in range(1, 38))
    monkeypatch.setattr("backend.service.omr.doc_phieu", lambda kq, layout, mh: omr_gia(chon=chon))
    ocr_khop(monkeypatch)
    t = tai(client, eid, "0002_C2").json()
    assert t["status"] == "graded" and t["pending_questions"] == 0
    assert t["official_score"] == pytest.approx(0.25 * dung)
    v = client.get(f"/sheets/{t['sheet_id']}").json()
    assert v["score"]["result_status"] == "auto" and v["review"] is None and v["student"]["student_code"] == "795125"
    r = conn_thu.execute("SELECT status::text AS s, confirmed_by FROM results WHERE sheet_id = %s", (t["sheet_id"],)).fetchone()
    assert r["s"] == "auto" and r["confirmed_by"] is None
    assert all(q["is_correct"] is not None for q in v["questions"])
    assert client.post(f"/sheets/{t['sheet_id']}/questions/1/review", json={"action": "confirm"}).status_code == 409   # đã chốt


@pytest.mark.parametrize("loai", ["mo", "nhieu"])
def test_mot_cau_can_xem_la_khong_tu_chot(client, monkeypatch, loai):
    """Chỉ MỘT câu mờ / nhiều ô cũng đủ để cả phiếu không có điểm chính thức; câu đó không được chấm (dù máy đọc đúng đáp án)."""
    can_anh("0002_C2")
    eid = tao_de(client)
    key = demo.khoa_demo("101")
    chon = {q: key[q - 1] for q in range(1, 41)}                                     # làm đúng hết 40 câu
    monkeypatch.setattr("backend.service.omr.doc_phieu", lambda kq, layout, mh: omr_gia(chon=chon, **{loai: (7,)}))
    ocr_khop(monkeypatch)
    t = tai(client, eid, "0002_C2").json()
    assert t["status"] == "needs_review" and t["official_score"] is None and t["pending_questions"] == 1
    v = client.get(f"/sheets/{t['sheet_id']}").json()
    assert v["score"]["provisional"] == pytest.approx(0.25 * 39) and v["score"]["max_possible"] == pytest.approx(10.0)
    assert next(q for q in v["questions"] if q["question_no"] == 7)["is_correct"] is None


def test_ma_de_khong_co_trong_ky_thi_khong_cham(client, monkeypatch):
    can_anh("0002_C2")
    eid = tao_de(client, ma_de=("101", "102"))
    monkeypatch.setattr("backend.service.omr.doc_phieu", lambda kq, layout, mh: omr_gia(ma_de="104"))
    ocr_khop(monkeypatch, ("795125", "104"))
    v = client.get(f"/sheets/{tai(client, eid, '0002_C2').json()['sheet_id']}").json()
    assert v["status"] == "needs_review" and "exam_code_not_found" in v["review"]["reasons"]
    assert v["score"]["provisional"] is None and v["score"]["official"] is None and all(q["is_correct"] is None for q in v["questions"])
    r = client.put(f"/sheets/{v['sheet_id']}/identity", json={"exam_code": "102"})
    assert r.status_code == 200 and r.json()["exam_code"]["matched_code"] == "102" and r.json()["score"]["provisional"] is not None
