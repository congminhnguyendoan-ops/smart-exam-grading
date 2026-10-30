"""
main.py - API FastAPI của Smart Exam (demo 13/10/2026). Chạy (từ smart_exam_db/):

    uvicorn backend.main:app --port 8000        # tài liệu tự sinh: http://127.0.0.1:8000/docs  (Swagger)  ·  /redoc

Nguyên tắc: endpoint mỏng – chỉ đổi HTTP <-> backend.service. Mỗi yêu cầu một kết nối + một giao dịch (commit khi thành công,
rollback khi lỗi). ĐĂNG NHẬP (nhánh cai-tien-b): AUTH_MODE=on (mặc định) -> cookie phiên HttpOnly hoặc Authorization: Bearer; mọi endpoint theo id
kiểm quyền theo lớp (backend/phan_quyen.py). AUTH_MODE=demo giữ hành vi cũ (DEMO_USER / header X-User, không kiểm quyền) – chỉ dev + test cũ.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path as DuongDan

import psycopg
from fastapi import Depends, FastAPI, File, Header, Path, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from urllib.parse import quote

from . import auth, bang_diem, don_anh, loi_khuyen, mang, nguoi_dung, nhat_ky, phan_quyen, phieu_trung, quan_tri, schemas, service, trang_bia
from .config import CauHinh, LoiCauHinh, lay_cau_hinh
from .db import ket_noi

log = logging.getLogger("smart_exam.api")
VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = lay_cau_hinh()
    app.state.cfg = cfg
    app.state.mo_hinh = service.nap_mo_hinh(cfg)          # nạp OMR + CNN chữ số một lần
    log.info("Đã nạp mô hình OMR %s, CNN chữ số %s", app.state.mo_hinh.phien_ban, app.state.mo_hinh.phien_ban_ocr)
    # Dọn ảnh tạm CHỈ khi ANH_XOA_TU_DONG=1 (tools/chay_server_lan.py --bat-don-anh – lệnh Z). pytest / tools/* (TestClient trên CSDL thật) để tắt.
    luong = don_anh.LuongDon(cfg).bat() if cfg.anh_xoa_tu_dong else None
    yield
    if luong:
        luong.tat()


app = FastAPI(
    title="Smart Exam API", version=VERSION, lifespan=lifespan,
    description="Chấm tự động phiếu trắc nghiệm từ ảnh chụp điện thoại. Câu OMR **cần xem** không bao giờ được chấm như câu "
                "chắc chắn: phiếu còn mục cần xem có status `needs_review`, chỉ có điểm tạm; điểm chính thức (`results`) chỉ có "
                "khi giáo viên đã xem hết. Cần đăng nhập (POST /auth/login); giáo viên chỉ thấy lớp / kỳ thi / phiếu của mình.")


# ------------------------------------------------------------------------------------------------ phụ thuộc
def get_cau_hinh(request: Request) -> CauHinh:
    return request.app.state.cfg


def get_mo_hinh(request: Request) -> service.MoHinhDichVu:
    return request.app.state.mo_hinh


def get_conn():
    """Một kết nối + một giao dịch cho mỗi yêu cầu (pytest ghi đè hàm này bằng giao dịch rollback)."""
    conn = ket_noi()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_nguoi_dung(request: Request, conn=Depends(get_conn), cfg: CauHinh = Depends(get_cau_hinh),
                   authorization: str | None = Header(default=None, description="Bearer <token> (công cụ / test; trình duyệt dùng cookie)"),
                   x_user: str | None = Header(default=None, description="CHỈ khi AUTH_MODE=demo: username giáo viên")) -> auth.NguoiDung:
    """Người dùng hiện tại: 401 nếu chưa đăng nhập / phiên hết hạn. Trong AUTH_MODE=on header X-User bị BỎ QUA."""
    token = request.cookies.get(auth.COOKIE)
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    return nguoi_dung.xac_thuc(conn, cfg, token, x_user)


def giao_vien(nd: auth.NguoiDung = Depends(get_nguoi_dung)) -> auth.NguoiDung:
    """API chấm / kỳ thi / lớp: chỉ admin và teacher; student -> 403."""
    if nd.role not in ("admin", "teacher"):
        raise nguoi_dung.KhongCoQuyen("Tài khoản sinh viên không dùng được chức năng này.")
    return nd


def chi_admin(nd: auth.NguoiDung = Depends(get_nguoi_dung)) -> auth.NguoiDung:
    """API quản trị (/admin/...): CHỈ vai trò admin – giáo viên / sinh viên -> 403 (kể cả AUTH_MODE=demo: X-User phải là admin)."""
    if nd.role != "admin":
        raise nguoi_dung.KhongCoQuyen("Chỉ quản trị viên dùng được chức năng này.")
    return nd


@app.exception_handler(service.LoiDichVu)
def _loi_dich_vu(_: Request, e: service.LoiDichVu):
    return JSONResponse({"detail": str(e)}, status_code=e.ma_http)


_CO_MAT_KHAU = ("/auth/", "/me", "/admin/users")


@app.exception_handler(RequestValidationError)
async def _loi_dau_vao(request: Request, e: RequestValidationError):
    """Như mặc định của FastAPI, NHƯNG với đường dẫn có trường mật khẩu thì bỏ "input" / "ctx" (pydantic chép lại giá trị gửi lên -> lộ mật khẩu)."""
    if not request.url.path.startswith(_CO_MAT_KHAU):
        return await request_validation_exception_handler(request, e)          # hành vi mặc định, không đổi
    loi = [{k: v for k, v in x.items() if k not in ("input", "ctx")} for x in e.errors()]
    return JSONResponse({"detail": jsonable_encoder(loi)}, status_code=422)


@app.exception_handler(psycopg.errors.IntegrityError)
def _loi_rang_buoc(_: Request, e: psycopg.errors.IntegrityError):
    return JSONResponse({"detail": f"Vi phạm ràng buộc dữ liệu: {e.diag.message_primary}"}, status_code=409)


@app.exception_handler(LoiCauHinh)
def _loi_cau_hinh(_: Request, e: LoiCauHinh):
    return JSONResponse({"detail": str(e)}, status_code=500)


# ------------------------------------------------------------------------------------------------ hệ thống
@app.get("/health", tags=["Hệ thống"], summary="Kiểm tra sống")
def health(request: Request):
    """Trả 200 khi API chạy và nối được CSDL; 503 nếu không nối được CSDL."""
    mh = getattr(request.app.state, "mo_hinh", None)
    thong_tin = {"status": "ok", "version": VERSION, "omr_model": mh.phien_ban if mh else None,
                 "ocr_model": mh.phien_ban_ocr if mh else None}
    try:
        with ket_noi() as conn:
            conn.execute("SELECT 1")
        thong_tin["db"] = "ok"
        return thong_tin
    except psycopg.Error as e:
        return JSONResponse({**thong_tin, "status": "loi", "db": f"không nối được CSDL: {type(e).__name__}"}, status_code=503)


@app.get("/meta/reject-reasons", response_model=dict[str, schemas.LyDoTuChoi], tags=["Hệ thống"],
         summary="Mã từ chối ảnh + thông báo + lời khuyên chụp lại")
def ly_do_tu_choi():
    """Cho giao diện: mỗi mã `reject_code` (MA_LY_DO của preprocess) kèm thông báo tiếng Việt và lời khuyên chụp lại."""
    return loi_khuyen.danh_sach()


@app.get("/meta/ket-noi", response_model=schemas.KetNoi, tags=["Hệ thống"], summary="Địa chỉ cho điện thoại (IP LAN, QR) – cần đăng nhập")
def ket_noi_dien_thoai(request: Request, cfg: CauHinh = Depends(get_cau_hinh), nd: auth.NguoiDung = Depends(giao_vien)):
    """Cho nút "Kết nối điện thoại": IP mạng nội bộ ứng viên, URL trang /m + mã QR. Chỉ người đã đăng nhập (không lộ thông tin mạng cho người lạ).
    `lan_bat = false` nghĩa là server chỉ nghe 127.0.0.1 – điện thoại không vào được (khởi động bằng tools/chay_server_lan.py)."""
    return {**mang.thong_tin_ket_noi(request.url.port or mang.CONG_MAC_DINH), "gioi_han_anh_mb": cfg.gioi_han_anh_mb}


# ------------------------------------------------------------------------------------------------ đề thi
@app.post("/exams", status_code=201, response_model=schemas.KyThiTao, tags=["Đề thi"], summary="Tạo kỳ thi + mã đề + đáp án")
def tao_ky_thi(body: schemas.KyThiMoi, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """CHỈ quản trị viên (lệnh H, 29/10/2026): giáo viên không tự tạo kỳ thi -> 403; admin tạo + gán giáo viên phụ trách ở POST /admin/exams.
    (AUTH_MODE=demo giữ hành vi cũ cho công cụ / test cũ.) `class_id` / `class_code` tuỳ chọn: phải là lớp ĐÃ CÓ; không tự tạo lớp."""
    if not nd.demo and not nd.la_admin:
        raise nguoi_dung.KhongCoQuyen("Giáo viên không tự tạo kỳ thi – nhờ quản trị viên tạo (trang Quản trị) và gán bạn phụ trách.")
    d = body.model_dump()
    d["class_id"] = phan_quyen.giai_lop_cho_ky_thi(conn, nd, body.class_id, body.class_code)
    return {"exam_id": service.tao_ky_thi(conn, d, nd.user_id)}


@app.get("/exams", response_model=list[schemas.KyThiTomTat], tags=["Đề thi"], summary="Danh sách kỳ thi")
def ds_ky_thi(conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """Admin: tất cả. Giáo viên: kỳ thi mình tạo + kỳ thi thuộc lớp mình dạy. Kèm môn và lớp."""
    return service.ds_ky_thi(conn, *phan_quyen.dieu_kien_ky_thi(nd))


@app.get("/exams/{exam_id}", response_model=schemas.KyThiOut, tags=["Đề thi"], summary="Xem kỳ thi + đáp án các mã đề")
def xem_ky_thi(exam_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    return service.doc_ky_thi(conn, exam_id)


@app.get("/exams/{exam_id}/cover.pdf", tags=["Đề thi"], summary="Trang bìa kỳ thi (PDF) – mã QR mở /m?kythi=<id>")
def trang_bia_ky_thi(exam_id: int, request: Request, conn=Depends(get_conn), cfg: CauHinh = Depends(get_cau_hinh),
                     nd: auth.NguoiDung = Depends(giao_vien)):
    """Giáo viên phụ trách / admin in trang này kẹp trên xấp phiếu. Địa chỉ gốc của QR: PUBLIC_BASE_URL, rỗng thì lấy từ yêu cầu. Không có đáp án."""
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    tt = trang_bia.thong_tin(conn, exam_id)
    pdf = trang_bia.tao_pdf(tt, trang_bia.url_ky_thi(trang_bia.dia_chi_goc(cfg.public_base_url, request.base_url), exam_id))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="trang_bia_ky_thi_{exam_id}.pdf"'})


# ------------------------------------------------------------------------------------------------ tải ảnh
def _tom_tat_tai(conn, sheet_id: int, da_ton_tai: bool) -> dict:
    v = service.xem_phieu(conn, sheet_id)
    sc = v["score"] or {}
    return {"sheet_id": sheet_id, "da_ton_tai": da_ton_tai, "status": v["status"], "reject_code": v["reject_code"],
            "reject_message": v["reject_message"], "pending_questions": sc.get("pending_questions", 0),
            "provisional_score": sc.get("provisional"), "official_score": sc.get("official")}


@app.post("/exams/{exam_id}/sheets", status_code=201, response_model=schemas.TaiAnhOut, tags=["Phiếu"],
          summary="Tải MỘT ảnh phiếu và chấm ngay")
def tai_mot_anh(exam_id: int, file: UploadFile = File(description="Ảnh phiếu (JPG / PNG / HEIC)"), conn=Depends(get_conn),
                cfg: CauHinh = Depends(get_cau_hinh), mh=Depends(get_mo_hinh), nd: auth.NguoiDung = Depends(giao_vien)):
    """Ảnh không dùng được (mờ, thiếu marker, ...) vẫn trả 201 với `status = rejected` + `reject_code` + thông báo – không có điểm.
    Kỳ thi đã đóng (quản trị viên đóng) -> 409, không nhận ảnh."""
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    quan_tri.kiem_dang_mo(conn, exam_id)
    sheet_id, da_co = service.nhan_anh(conn, cfg, mh, exam_id, file.file.read(), file.filename, nd.user_id)
    return _tom_tat_tai(conn, sheet_id, da_co)


@app.post("/exams/{exam_id}/sheets/batch", status_code=201, response_model=schemas.TaiNhieuOut, tags=["Phiếu"],
          summary="Tải NHIỀU ảnh phiếu (một lô) và chấm")
def tai_nhieu_anh(exam_id: int, files: list[UploadFile] = File(description="Nhiều ảnh phiếu"), conn=Depends(get_conn),
                  cfg: CauHinh = Depends(get_cau_hinh), mh=Depends(get_mo_hinh), nd: auth.NguoiDung = Depends(giao_vien)):
    """Mỗi ảnh xử lý độc lập (điểm lưu riêng): ảnh lỗi không làm hỏng các ảnh còn lại; lỗi của ảnh nào ghi ở `error` của ảnh đó."""
    user_id = nd.user_id
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    if not conn.execute("SELECT 1 FROM exams WHERE exam_id = %s", (exam_id,)).fetchone():
        raise service.KhongTimThay(f"Không có kỳ thi {exam_id}.")
    quan_tri.kiem_dang_mo(conn, exam_id)
    batch_id = conn.execute("INSERT INTO scan_batches (exam_id, uploaded_by, total_sheets) VALUES (%s, %s, %s) RETURNING batch_id",
                            (exam_id, user_id, len(files))).fetchone()["batch_id"]
    ket_qua = []
    for f in files:
        try:
            with conn.transaction():                       # savepoint: lỗi một ảnh không kéo cả lô
                sid, da_co = service.nhan_anh(conn, cfg, mh, exam_id, f.file.read(), f.filename, user_id, batch_id)
                t = _tom_tat_tai(conn, sid, da_co)
            ket_qua.append({"filename": f.filename, "sheet_id": sid, "da_ton_tai": da_co, "status": t["status"],
                            "reject_code": t["reject_code"], "reject_message": t["reject_message"],
                            "pending_questions": t["pending_questions"]})
        except service.LoiDichVu as e:
            ket_qua.append({"filename": f.filename, "error": str(e)})
        except Exception as e:  # noqa: BLE001 – ghi log đầy đủ, báo lỗi theo từng ảnh
            log.exception("Lỗi xử lý ảnh %s", f.filename)
            ket_qua.append({"filename": f.filename, "error": f"Lỗi nội bộ: {type(e).__name__}"})
    return {"batch_id": batch_id, "tong": len(files), "results": ket_qua}


@app.get("/exams/{exam_id}/sheets", response_model=list[schemas.PhieuTomTat], tags=["Phiếu"], summary="Danh sách phiếu của kỳ thi")
def ds_phieu(exam_id: int, status: str | None = Query(default=None, description="graded | needs_review | rejected | ..."),
             conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    return service.ds_phieu_ky_thi(conn, exam_id, status)


# ------------------------------------------------------------------------------------------------ kết quả
@app.get("/sheets/{sheet_id}", response_model=schemas.PhieuOut, tags=["Phiếu"], summary="Xem kết quả một phiếu")
def xem_phieu(sheet_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """Điểm chính thức (`score.official`) chỉ có khi `status = graded`. Khi `needs_review` chỉ có điểm tạm + điểm tối đa có thể đạt."""
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    return service.xem_phieu(conn, sheet_id)


@app.get("/sheets/{sheet_id}/image", tags=["Phiếu"], summary="Ảnh phiếu (gốc hoặc đã nắn phẳng)")
def anh_phieu(sheet_id: int, kind: str = Query(default="aligned", pattern="^(original|aligned)$"), conn=Depends(get_conn),
              cfg: CauHinh = Depends(get_cau_hinh), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    return FileResponse(service.duong_dan_anh(conn, cfg, sheet_id, "goc" if kind == "original" else "nan"))


@app.get("/sheets/{sheet_id}/questions/{question_no}/image", tags=["Review"], summary="Ảnh cắt hàng câu (đã nắn) để giáo viên xem")
def anh_cau(sheet_id: int, question_no: int, conn=Depends(get_conn), cfg: CauHinh = Depends(get_cau_hinh),
           nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    return Response(service.cat_anh_cau(conn, cfg, sheet_id, question_no), media_type="image/png")


@app.get("/sheets/{sheet_id}/digits/{field}/{position}/image", tags=["Review"],
         summary="Ảnh ô viết tay (SBD / mã đề) đã cắt, để so với chữ số bubble")
def anh_chu_so(sheet_id: int, field: str = Path(pattern="^(sbd|exam_code)$"), position: int = Path(ge=0, le=9), conn=Depends(get_conn),
               cfg: CauHinh = Depends(get_cau_hinh), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    return FileResponse(service.anh_chu_so(conn, cfg, sheet_id, field, position), media_type="image/png")


# ------------------------------------------------------------------------------------------------ review (giáo viên)
@app.get("/sheets/{sheet_id}/review-questions", response_model=list[schemas.CauCanXem], tags=["Review"],
         summary="Các câu cần xem của một phiếu")
def cau_can_xem_phieu(sheet_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    return service.cau_can_xem(conn, sheet_id=sheet_id)


@app.get("/exams/{exam_id}/review-questions", response_model=list[schemas.CauCanXem], tags=["Review"],
         summary="Các câu cần xem của cả kỳ thi")
def cau_can_xem_ky_thi(exam_id: int, limit: int = Query(default=500, ge=1, le=5000), conn=Depends(get_conn),
                       nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    if not conn.execute("SELECT 1 FROM exams WHERE exam_id = %s", (exam_id,)).fetchone():
        raise service.KhongTimThay(f"Không có kỳ thi {exam_id}.")
    return service.cau_can_xem(conn, exam_id=exam_id, gioi_han=limit)


@app.post("/sheets/{sheet_id}/questions/{question_no}/review", response_model=schemas.PhieuOut, tags=["Review"],
          summary="Giáo viên xác nhận / sửa MỘT câu cần xem")
def xu_ly_cau(sheet_id: int, question_no: int, body: schemas.XuLyCau, conn=Depends(get_conn),
              nd: auth.NguoiDung = Depends(giao_vien)):
    """Sau mỗi lần xử lý, hệ thống tính lại. Hết mục cần xem (và SBD / mã đề ổn) thì phiếu được chốt: `status = graded`,
    `score.official` có giá trị, `score.result_status = confirmed`."""
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    service.xu_ly_cau(conn, sheet_id, question_no, body.action, body.selected_options, nd.user_id, body.note)
    return service.xem_phieu(conn, sheet_id)


@app.put("/sheets/{sheet_id}/identity", response_model=schemas.PhieuOut, tags=["Review"],
         summary="Giáo viên chốt số báo danh / mã đề của phiếu")
def sua_dinh_danh(sheet_id: int, body: schemas.DinhDanh, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    service.sua_dinh_danh(conn, sheet_id, body.sbd, body.exam_code, nd.user_id, body.note)
    return service.xem_phieu(conn, sheet_id)


@app.post("/sheets/{sheet_id}/duplicate/discard", response_model=schemas.KetQuaTrung, tags=["Review"],
          summary="Phiếu bị giữ vì trùng SBD: BỎ phiếu chụp lại này, giữ phiếu cũ")
def bo_phieu_trung(sheet_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """Phiếu này (`duplicate_sbd`) bị loại (`rejected`, mã `chup_lai_bi_bo`); phiếu cũ và điểm chính thức không đổi. 409 nếu phiếu không còn bị giữ vì trùng."""
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    r = phieu_trung.bo_phieu_chup_lai(conn, sheet_id, nd.user_id, nd.username)
    return {"hanh_dong": r["hanh_dong"], "phieu": service.xem_phieu(conn, sheet_id), "phieu_cu": r["giu_phieu"]}


@app.post("/sheets/{sheet_id}/duplicate/replace", response_model=schemas.KetQuaTrung, tags=["Review"],
          summary="Phiếu bị giữ vì trùng SBD: DÙNG phiếu này thay phiếu cũ (rút điểm cũ, ghi nhật ký)")
def thay_phieu_trung(sheet_id: int, body: schemas.ThayPhieuCu, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """MỘT giao dịch: điểm chính thức của phiếu cũ bị rút (`results.status = void`, `score_audit_logs` ghi ai / lúc nào / phiếu nào thay phiếu nào), phiếu cũ không
    còn tính, phiếu này được đánh giá lại để duyệt tiếp hoặc chốt. `old_sheet_id` phải là phiếu cũ giáo viên đã xác nhận, đổi trong lúc chờ -> 409. Không bao giờ có hai điểm chính thức."""
    phan_quyen.kiem_phieu(conn, nd, sheet_id)
    phan_quyen.kiem_phieu(conn, nd, body.old_sheet_id)
    r = phieu_trung.thay_phieu_cu(conn, sheet_id, body.old_sheet_id, nd.user_id, nd.username)
    return {"hanh_dong": r["hanh_dong"], "phieu": service.xem_phieu(conn, sheet_id), "phieu_cu": r["phieu_cu"], "diem_cu_da_rut": r["diem_cu"]}


# ------------------------------------------------------------------------------------------------ bảng điểm
@app.get("/exams/{exam_id}/results", response_model=schemas.BangDiemOut, tags=["Bảng điểm"],
         summary="Bảng điểm: mỗi thí sinh trong danh sách dự thi một dòng")
def bang_diem_ky_thi(exam_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """`score` là điểm CHÍNH THỨC (chỉ phiếu `official`). Phiếu chưa duyệt xong (`pending`) chỉ có `provisional_score`."""
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    return bang_diem.bang_diem(conn, exam_id)


@app.get("/exams/{exam_id}/export.xlsx", tags=["Bảng điểm"], summary="Xuất Excel: sheet 'Bảng điểm' + sheet 'Chi tiết'")
def xuat_excel(exam_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
    du_lieu, ten = bang_diem.xuat_excel(conn, exam_id)
    ascii_ten = f"bang_diem_{exam_id}.xlsx"
    return Response(du_lieu, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=\"{ascii_ten}\"; filename*=UTF-8''{quote(ten)}"})


# ------------------------------------------------------------------------------------------------ đăng nhập / hồ sơ / lớp
@app.post("/auth/login", response_model=schemas.HoSo, tags=["Tài khoản"], summary="Đăng nhập (đặt cookie phiên HttpOnly)")
def dang_nhap(body: schemas.DangNhap, request: Request, response: Response, conn=Depends(get_conn), cfg: CauHinh = Depends(get_cau_hinh)):
    """Mọi lỗi (sai tên, sai mật khẩu, tài khoản bị khoá) trả CÙNG một thông báo, 401. Sai quá 5 lần / 15 phút (mỗi tên + IP): 429.
    Phiên hết hạn sau `SESSION_HOURS` giờ. Công cụ có thể dùng `Authorization: Bearer <token>` (token trong cookie)."""
    if cfg.auth_mode == "demo":
        raise service.DuLieuSai("Đang ở AUTH_MODE=demo (chỉ dev): không có đăng nhập.")
    token, nd = nguoi_dung.dang_nhap(conn, cfg, body.username, body.password, request.client.host if request.client else "?")
    response.set_cookie(auth.COOKIE, token, max_age=int(cfg.session_hours * 3600), httponly=True, samesite="lax", secure=cfg.cookie_secure, path="/")
    return nguoi_dung.ho_so(conn, nd)


@app.post("/auth/logout", status_code=204, tags=["Tài khoản"], summary="Đăng xuất (xoá cookie phiên)")
def dang_xuat():
    r = Response(status_code=204)
    r.delete_cookie(auth.COOKIE, path="/", httponly=True, samesite="lax")
    return r


@app.get("/me", response_model=schemas.HoSo, tags=["Tài khoản"], summary="Thông tin cá nhân")
def toi(conn=Depends(get_conn), nd: auth.NguoiDung = Depends(get_nguoi_dung)):
    return nguoi_dung.ho_so(conn, nd)


@app.patch("/me", response_model=schemas.HoSo, tags=["Tài khoản"], summary="Sửa họ tên / email của mình")
def sua_toi(body: schemas.SuaHoSo, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(get_nguoi_dung)):
    return nguoi_dung.sua_ho_so(conn, nd, body.full_name, body.email)


@app.post("/me/password", status_code=204, tags=["Tài khoản"], summary="Đổi mật khẩu (cần mật khẩu cũ)")
def doi_mat_khau(body: schemas.DoiMatKhau, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(get_nguoi_dung)):
    """Mật khẩu mới ≥ 8 ký tự và khác mật khẩu cũ. Đổi mật khẩu làm mọi phiên cũ (cả phiên này) hết hiệu lực: đăng nhập lại."""
    nguoi_dung.doi_mat_khau(conn, nd, body.old_password, body.new_password)
    return Response(status_code=204)


@app.get("/me/classes", response_model=list[schemas.LopCuaToi], tags=["Lớp"], summary="Lớp tôi phụ trách (kèm môn, số sinh viên)")
def lop_cua_toi(conn=Depends(get_conn), nd: auth.NguoiDung = Depends(giao_vien)):
    """Giáo viên: các lớp trong `teacher_classes`. Admin: mọi lớp."""
    return nguoi_dung.lop_cua_toi(conn, nd)


@app.get("/classes/{class_id}/students", response_model=schemas.DsSinhVienLop, tags=["Lớp"], summary="Sinh viên của một lớp mình phụ trách")
def sinh_vien_lop(class_id: int, q: str | None = Query(default=None, max_length=100, description="Tìm theo mã hoặc họ tên"),
                  page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200), conn=Depends(get_conn),
                  nd: auth.NguoiDung = Depends(giao_vien)):
    phan_quyen.kiem_lop(conn, nd, class_id)
    r = nguoi_dung.sinh_vien_lop(conn, class_id, q, page, page_size)
    return {"lop": r["class"], "tong": r["tong"], "trang": r["trang"], "co_trang": r["co_trang"], "sinh_vien": r["sinh_vien"]}


# ------------------------------------------------------------------------------------------------ quản trị (chỉ admin)
# Lệnh V4: mọi thao tác GHI thành công để lại MỘT dòng admin_audit_log (nhat_ky.ghi) – ghi SAU hàm quan_tri.*, cùng giao dịch:
# hàm ném lỗi (409 / 404 / 422) thì không tới dòng ghi; giao dịch rollback thì nhật ký mất theo. Không ghi mật khẩu.
_COT_KY_THI = ("exam_title", "exam_date", "class_id", "status", "teacher_user_id")


@app.get("/admin/audit", response_model=schemas.NhatKyTrang, tags=["Quản trị"], summary="Nhật ký thao tác quản trị (mới nhất trước)")
def qt_nhat_ky(page: int = Query(default=1, ge=1), page_size: int = Query(default=100, ge=1, le=200), conn=Depends(get_conn),
               nd: auth.NguoiDung = Depends(chi_admin)):
    """Chỉ admin (giáo viên 403). Chỉ thao tác thành công; `details` không chứa mật khẩu / token."""
    return nhat_ky.ds(conn, page, page_size)


@app.get("/admin/exams", response_model=list[schemas.KyThiQuanTri], tags=["Quản trị"], summary="Mọi kỳ thi (kèm giáo viên phụ trách, trạng thái)")
def qt_ds_ky_thi(conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    return quan_tri.ds_ky_thi(conn)


@app.post("/admin/exams", status_code=201, response_model=schemas.KyThiQuanTri, tags=["Quản trị"],
          summary="Tạo kỳ thi + mã đề + đáp án, gán giáo viên phụ trách")
def qt_tao_ky_thi(body: schemas.KyThiQuanTriMoi, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Cùng quy tắc kiểm đáp án với POST /exams. `teacher_user_id`: giáo viên phụ trách (thấy và chụp phiếu cho kỳ thi này)."""
    d = body.model_dump(exclude={"teacher_user_id"})
    d["class_id"] = phan_quyen.giai_lop_cho_ky_thi(conn, nd, body.class_id, body.class_code)
    e = quan_tri.mot_ky_thi(conn, quan_tri.tao_ky_thi_qt(conn, nd, d, body.teacher_user_id))
    nhat_ky.ghi(conn, nd, "tao_ky_thi", e["exam_id"], {"exam_title": e["exam_title"], "class_code": e["class_code"], "subject_code": e["subject_code"],
                                                       "teacher_username": e["teacher_username"], "ma_de": e["ma_de"]})
    return e


@app.patch("/admin/exams/{exam_id}", response_model=schemas.KyThiQuanTri, tags=["Quản trị"], summary="Sửa tên / ngày thi")
def qt_sua_ky_thi(exam_id: int, body: schemas.SuaKyThi, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Chỉ sửa trường có gửi; `exam_date: null` xoá ngày. Không đổi đáp án (đáp án sửa sau khi đã có phiếu là nợ kỹ thuật – cần chấm lại)."""
    cu = quan_tri.mot_ky_thi(conn, exam_id)
    e = quan_tri.sua_ky_thi(conn, exam_id, {k: getattr(body, k) for k in body.model_fields_set})
    nhat_ky.ghi(conn, nd, "sua_ky_thi", exam_id, {"exam_title": e["exam_title"], "thay": nhat_ky.thay_doi(cu, e, _COT_KY_THI)})
    return e


@app.post("/admin/exams/{exam_id}/status", response_model=schemas.KyThiQuanTri, tags=["Quản trị"], summary="Đóng / mở lại kỳ thi")
def qt_dong_mo(exam_id: int, body: schemas.DongMoKyThi, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Đóng: không nhận ảnh mới (409 khi tải). Duyệt phiếu, bảng điểm, Excel vẫn dùng được."""
    cu = quan_tri.mot_ky_thi(conn, exam_id)
    e = quan_tri.dat_dong_mo(conn, exam_id, body.closed)
    nhat_ky.ghi(conn, nd, "dong_ky_thi" if body.closed else "mo_ky_thi", exam_id,
                {"exam_title": e["exam_title"], "status": {"cu": cu["status"], "moi": e["status"]}})
    return e


@app.delete("/admin/exams/{exam_id}", status_code=204, tags=["Quản trị"], summary="Xoá kỳ thi CHƯA có phiếu")
def qt_xoa_ky_thi(exam_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Đã có phiếu / lô tải / kết quả -> 409 (chỉ đóng được)."""
    cu = quan_tri.mot_ky_thi(conn, exam_id)
    quan_tri.xoa_ky_thi(conn, exam_id)
    nhat_ky.ghi(conn, nd, "xoa_ky_thi", exam_id, {"exam_title": cu["exam_title"], "class_code": cu["class_code"], "subject_code": cu["subject_code"]})
    log.info("Quản trị %s xoá kỳ thi %s (chưa có phiếu)", nd.username, exam_id)
    return Response(status_code=204)


@app.get("/admin/users", response_model=list[schemas.TaiKhoan], tags=["Quản trị"], summary="Tài khoản admin + giáo viên")
def qt_ds_tai_khoan(conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    return quan_tri.ds_tai_khoan(conn)


@app.post("/admin/users", status_code=201, response_model=schemas.TaiKhoan, tags=["Quản trị"], summary="Tạo tài khoản giáo viên")
def qt_tao_tai_khoan(body: schemas.TaiKhoanMoi, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Vai trò luôn là teacher. Mật khẩu băm scrypt; phản hồi / nhật ký không bao giờ chứa mật khẩu. Trùng tên / email -> 409."""
    u = quan_tri.tao_giao_vien(conn, nd, body.username, body.full_name, body.email, body.password, body.class_ids)
    nhat_ky.ghi(conn, nd, "tao_tai_khoan", u["user_id"], {"username": u["username"], "full_name": u["full_name"], "email": u["email"], "lop": u["lop"]})
    return u


@app.post("/admin/users/{user_id}/password", status_code=204, tags=["Quản trị"], summary="Đặt lại mật khẩu giáo viên")
def qt_dat_lai_mat_khau(user_id: int, body: schemas.DatMatKhau, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Mọi phiên cũ của giáo viên đó hết hiệu lực. Chỉ tài khoản giáo viên (admin khác: dùng `python -m backend.tai_khoan`)."""
    quan_tri.dat_lai_mat_khau(conn, nd, user_id, body.new_password)
    nhat_ky.ghi(conn, nd, "dat_lai_mat_khau", user_id, {"username": quan_tri.ten_dang_nhap(conn, user_id)})     # KHÔNG ghi mật khẩu
    return Response(status_code=204)


@app.post("/admin/users/{user_id}/active", response_model=schemas.TaiKhoan, tags=["Quản trị"], summary="Vô hiệu hoá / kích hoạt lại giáo viên")
def qt_kich_hoat(user_id: int, body: schemas.KichHoat, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    u = quan_tri.dat_hoat_dong(conn, nd, user_id, body.is_active)
    nhat_ky.ghi(conn, nd, "kich_hoat_tai_khoan" if body.is_active else "vo_hieu_hoa_tai_khoan", user_id, {"username": u["username"]})
    return u


@app.get("/admin/users/{user_id}/exams", response_model=list[schemas.KyThiCuaGiaoVien], tags=["Quản trị"], summary="Kỳ thi giáo viên thấy")
def qt_ky_thi_cua_gv(user_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    return quan_tri.ky_thi_cua_giao_vien(conn, user_id)


@app.put("/admin/users/{user_id}/exams/{exam_id}", response_model=list[schemas.KyThiCuaGiaoVien], tags=["Quản trị"],
         summary="Gán kỳ thi cho giáo viên (thành người phụ trách)")
def qt_gan_ky_thi(user_id: int, exam_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    cu = quan_tri.tim_ky_thi(conn, exam_id)                                       # không ném: gan_ky_thi tự kiểm (giữ thứ tự lỗi cũ)
    ds = quan_tri.gan_ky_thi(conn, nd, user_id, exam_id)
    nhat_ky.ghi(conn, nd, "gan_ky_thi", user_id, {"username": quan_tri.ten_dang_nhap(conn, user_id), "exam_id": exam_id, "exam_title": cu["exam_title"],
                                                  "phu_trach_truoc": cu["teacher_username"]})
    return ds


@app.delete("/admin/users/{user_id}/exams/{exam_id}", response_model=list[schemas.KyThiCuaGiaoVien], tags=["Quản trị"],
            summary="Bỏ gán kỳ thi (người phụ trách chuyển về admin đang thao tác)")
def qt_bo_gan_ky_thi(user_id: int, exam_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    ds = quan_tri.bo_gan_ky_thi(conn, nd, user_id, exam_id)
    e = quan_tri.mot_ky_thi(conn, exam_id)
    nhat_ky.ghi(conn, nd, "bo_gan_ky_thi", user_id, {"username": quan_tri.ten_dang_nhap(conn, user_id), "exam_id": exam_id, "exam_title": e["exam_title"],
                                                     "phu_trach_sau": e["teacher_username"]})
    return ds


@app.get("/admin/classes", response_model=list[schemas.LopQuanTri], tags=["Quản trị"], summary="Mọi lớp (số giáo viên, sinh viên, kỳ thi)")
def qt_ds_lop(conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    return quan_tri.ds_lop(conn)


@app.post("/admin/classes", status_code=201, response_model=schemas.LopQuanTri, tags=["Quản trị"], summary="Tạo lớp")
def qt_tao_lop(body: schemas.LopMoi, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Mã lớp trùng (không phân biệt hoa thường) -> 409."""
    l = quan_tri.tao_lop(conn, nd, body.class_code, body.class_name, body.academic_year)
    nhat_ky.ghi(conn, nd, "tao_lop", l["class_id"], {"class_code": l["class_code"], "class_name": l["class_name"], "academic_year": l["academic_year"]})
    return l


@app.patch("/admin/classes/{class_id}", response_model=schemas.LopQuanTri, tags=["Quản trị"], summary="Sửa tên / năm học của lớp")
def qt_sua_lop(class_id: int, body: schemas.SuaLop, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    cu = quan_tri.mot_lop(conn, class_id)
    l = quan_tri.sua_lop(conn, class_id, {k: getattr(body, k) for k in body.model_fields_set})
    nhat_ky.ghi(conn, nd, "sua_lop", class_id, {"class_code": l["class_code"], "thay": nhat_ky.thay_doi(cu, l, ("class_name", "academic_year"))})
    return l


@app.post("/admin/classes/{class_id}/status", response_model=schemas.LopQuanTri, tags=["Quản trị"], summary="Vô hiệu hoá / kích hoạt lại lớp")
def qt_trang_thai_lop(class_id: int, body: schemas.KichHoatLop, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    l = quan_tri.dat_hoat_dong_lop(conn, nd, class_id, body.is_active)
    nhat_ky.ghi(conn, nd, "kich_hoat_lop" if body.is_active else "vo_hieu_hoa_lop", class_id, {"class_code": l["class_code"]})
    return l


@app.delete("/admin/classes/{class_id}", status_code=204, tags=["Quản trị"], summary="Xoá lớp CHƯA gắn kỳ thi và chưa có sinh viên")
def qt_xoa_lop(class_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    cu = quan_tri.mot_lop(conn, class_id)
    quan_tri.xoa_lop(conn, nd, class_id)
    nhat_ky.ghi(conn, nd, "xoa_lop", class_id, {"class_code": cu["class_code"], "class_name": cu["class_name"]})
    return Response(status_code=204)


@app.get("/admin/classes/{class_id}/teachers", response_model=list[schemas.GiaoVienCuaLop], tags=["Quản trị"], summary="Giáo viên của lớp")
def qt_gv_cua_lop(class_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    return quan_tri.giao_vien_cua_lop(conn, class_id)


@app.put("/admin/classes/{class_id}/teachers/{user_id}", response_model=list[schemas.GiaoVienCuaLop], tags=["Quản trị"],
         summary="Thêm giáo viên (đang hoạt động) vào lớp (đang hoạt động)")
def qt_them_gv_vao_lop(class_id: int, user_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Một giáo viên nhiều lớp, một lớp nhiều giáo viên. Có hiệu lực ở lần gọi kế tiếp của giáo viên."""
    ds = quan_tri.them_giao_vien_vao_lop(conn, nd, class_id, user_id)
    nhat_ky.ghi(conn, nd, "them_giao_vien_vao_lop", class_id, {"class_code": quan_tri.mot_lop(conn, class_id)["class_code"], "user_id": user_id,
                                                                "username": quan_tri.ten_dang_nhap(conn, user_id)})
    return ds


@app.delete("/admin/classes/{class_id}/teachers/{user_id}", response_model=list[schemas.GiaoVienCuaLop], tags=["Quản trị"],
            summary="Bỏ giáo viên khỏi lớp (mất quyền theo lớp ngay ở lần gọi kế tiếp)")
def qt_bo_gv_khoi_lop(class_id: int, user_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    ds = quan_tri.bo_giao_vien_khoi_lop(conn, nd, class_id, user_id)
    nhat_ky.ghi(conn, nd, "bo_giao_vien_khoi_lop", class_id, {"class_code": quan_tri.mot_lop(conn, class_id)["class_code"], "user_id": user_id,
                                                               "username": quan_tri.ten_dang_nhap(conn, user_id)})
    return ds


@app.get("/admin/users/{user_id}/classes", response_model=list[schemas.LopCuaGiaoVienQT], tags=["Quản trị"], summary="Lớp của giáo viên")
def qt_lop_cua_gv(user_id: int, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    return quan_tri.lop_cua_giao_vien(conn, user_id)


@app.put("/admin/users/{user_id}/classes", response_model=list[schemas.LopCuaGiaoVienQT], tags=["Quản trị"],
         summary="Đặt danh sách lớp của giáo viên (tick nhiều lớp)")
def qt_dat_lop_cho_gv(user_id: int, body: schemas.DatLop, conn=Depends(get_conn), nd: auth.NguoiDung = Depends(chi_admin)):
    """Lớp thêm mới phải đang hoạt động; lớp giữ lại giữ nguyên môn dạy; id lớp không có -> 422 (không đổi gì)."""
    truoc = {r["class_code"] for r in quan_tri.lop_cua_giao_vien(conn, user_id)}
    ds = quan_tri.dat_lop_cho_giao_vien(conn, nd, user_id, body.class_ids)
    sau = {r["class_code"] for r in ds}
    if truoc != sau:                                                              # lưu mà không đổi gì: không ghi nhật ký
        nhat_ky.ghi(conn, nd, "dat_lop_giao_vien", user_id, {"username": quan_tri.ten_dang_nhap(conn, user_id),
                                                             "them": sorted(sau - truoc), "bo": sorted(truoc - sau)})
    return ds


# ------------------------------------------------------------------------------------------------ giao diện (HTML + JS thuần)
FRONTEND_DIR = DuongDan(__file__).resolve().parent.parent / "frontend"


@app.get("/", include_in_schema=False)
def trang_chu():
    return RedirectResponse("/app/")


@app.get("/m", include_in_schema=False)
def trang_dien_thoai():
    """Trang chụp phiếu cho điện thoại – HTML TĨNH (không dữ liệu); mọi API nó gọi vẫn cần đăng nhập."""
    return FileResponse(FRONTEND_DIR / "m.html", media_type="text/html", headers={"Cache-Control": "no-cache"})


app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")   # đặt SAU các route API
