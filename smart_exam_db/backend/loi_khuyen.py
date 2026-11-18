from cv_engine.preprocessing import MA_LY_DO

LOI_KHUYEN = {
    "khong_doc_duoc": "Kiểm tra file có phải ảnh (JPG / PNG / HEIC) và không bị hỏng, rồi tải lại.",
    "thieu_marker": "Chụp trọn cả phiếu: thấy đủ 4 ô vuông đen ở 4 góc, không để ngón tay hay vật khác che.",
    "marker_khong_dat": "Đặt phiếu phẳng trên mặt bàn, chụp thẳng góc, đủ sáng; tránh nếp gấp ở góc phiếu.",
    "nhieu_phieu": "Chỉ để MỘT phiếu trong khung hình; dời các tờ giấy khác ra xa rồi chụp lại.",
    "marker_mo_ho": "Chụp lại sát hơn và rõ nét; tránh bóng đổ hoặc loá sáng đè lên 4 ô vuông đen ở góc.",
    "marker_cham_mep": "Lùi máy ra một chút để cả 4 ô vuông đen nằm hẳn trong khung hình, cách mép ảnh.",
    "anh_mo": "Giữ chắc tay, chạm vào màn hình để lấy nét trước khi chụp, chụp nơi đủ sáng.",
    "khong_khop_bo_cuc": "Đảm bảo đúng loại phiếu của hệ thống, chụp rõ nét, không bị che hoặc nhoè rồi chụp lại.",
    "khong_ro_chieu": "Chụp lại rõ nét, thấy rõ phần tiêu đề và các ô đáp án của phiếu.",
}


def danh_sach() -> dict[str, dict]:
    return {ma: {"message": msg, "advice": LOI_KHUYEN.get(ma, "Chụp lại phiếu rõ nét, đủ sáng, thấy đủ 4 góc.")}
            for ma, msg in MA_LY_DO.items()}
