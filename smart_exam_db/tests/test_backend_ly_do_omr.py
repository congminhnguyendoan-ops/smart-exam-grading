"""Mọi mã lý do CÂU của omr.MA_LY_DO_OMR phải được backend xử lý (service.LY_DO_OMR_CAU / multiple_marks), nếu không câu cần xem bị bỏ qua khi gom
lý do: danh_gia_phieu coi phiếu "hết lý do" và dừng bằng RuntimeError (chốt an toàn) thay vì đưa vào hàng đợi giáo viên. Lỗi này đã xảy ra với
'vet_nho' và 'to_nhat' (28/10/2026, phát hiện khi chạy thử tools/eval_dot2.py trên ảnh giả hoá)."""
from backend import service
from cv_engine import omr

CHI_CO_O_COT = {"khong_o_nao"}        # chỉ sinh ở cột chữ số (ap_luat_cot)
DUNG_RIENG = {"nhieu_o"}              # -> review_reason multiple_marks


def test_moi_ma_ly_do_cau_deu_duoc_backend_xu_ly():
    chua = set(omr.MA_LY_DO_OMR) - CHI_CO_O_COT - DUNG_RIENG - service.LY_DO_OMR_CAU
    assert not chua, f"mã lý do OMR chưa vào service.LY_DO_OMR_CAU: {chua}"
