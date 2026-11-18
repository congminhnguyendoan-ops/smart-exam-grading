from backend import service
from cv_engine import omr

CHI_CO_O_COT = {"khong_o_nao"}
DUNG_RIENG = {"nhieu_o"}


def test_moi_ma_ly_do_cau_deu_duoc_backend_xu_ly():
    chua = set(omr.MA_LY_DO_OMR) - CHI_CO_O_COT - DUNG_RIENG - service.LY_DO_OMR_CAU
    assert not chua, f"mã lý do OMR chưa vào service.LY_DO_OMR_CAU: {chua}"
