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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from urllib.parse import quote

from . import auth, bang_diem, don_anh, loi_khuyen, mang, nguoi_dung, phan_quyen, schemas, service
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
    # Dọn ảnh tạm CHỈ khi ANH_XOA_TU_DONG=1 (tools/chay_server_lan.py). pytest / tools/* (TestClient trên CSDL thật) để tắt.
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


@app.exception_handler(service.LoiDichVu)
def _loi_dich_vu(_: Request, e: service.LoiDichVu):
    return JSONResponse({"detail": str(e)}, status_code=e.ma_http)


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
    """`class_id` / `class_code` tuỳ chọn: phải là lớp ĐÃ CÓ và thuộc lớp bạn phụ trách (admin: bất kỳ); không tự tạo lớp."""
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
    """Ảnh không dùng được (mờ, thiếu marker, ...) vẫn trả 201 với `status = rejected` + `reject_code` + thông báo – không có điểm."""
    phan_quyen.kiem_ky_thi(conn, nd, exam_id)
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
